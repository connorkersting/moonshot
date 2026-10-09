{#
    Schema contract for a raw CSV source.

    The source is read positionally with an explicit column list (meta.csv_columns),
    so a renamed or reordered column with the same field count would load silently
    under the wrong name. This test reads the file's header line and fails when it
    differs from csv_columns, or when the documented YAML columns drift from
    csv_columns. Each failing row names the source table, what was expected, what
    arrived, and the columns added or missing.
#}
{% test csv_header_matches(model) %}

{%- set ns = namespace(node=none) -%}
{%- if execute -%}
    {%- for node in graph.sources.values() -%}
        {%- if node.identifier == model.identifier and node.meta.get('csv_columns') -%}
            {%- set ns.node = node -%}
        {%- endif -%}
    {%- endfor -%}
    {%- if ns.node is none -%}
        {{ exceptions.raise_compiler_error("csv_header_matches: no source with meta.csv_columns found for " ~ model.identifier) }}
    {%- endif -%}
{%- endif -%}

{%- set node = ns.node -%}
{%- set csv_path = (node.meta.raw_dir ~ '/' ~ node.name ~ '.csv') if node is not none else '' -%}
{%- set contract_columns = (node.meta.csv_columns.keys() | list) if node is not none else [] -%}
{%- set documented_columns = (node.columns.keys() | list) if node is not none else [] -%}

WITH file_header AS (
    SELECT
        string_split(rtrim(split_part(content, chr(10), 1), chr(13)), ',') AS arrived_columns,
    FROM read_text('{{ csv_path }}')
),

contract AS (
    SELECT
        [{% for c in contract_columns %}'{{ c }}'{{ ', ' if not loop.last }}{% endfor %}]::VARCHAR[] AS expected_columns,
        [{% for c in documented_columns %}'{{ c }}'{{ ', ' if not loop.last }}{% endfor %}]::VARCHAR[] AS documented_columns,
),

compared AS (
    SELECT
        '{{ node.source_name if node is not none else "" }}.{{ node.name if node is not none else "" }}' AS source_table,
        contract.expected_columns,
        file_header.arrived_columns,
        contract.documented_columns,
        list_filter(file_header.arrived_columns, c -> NOT list_contains(contract.expected_columns, c)) AS added_columns,
        list_filter(contract.expected_columns, c -> NOT list_contains(file_header.arrived_columns, c)) AS missing_columns,
    FROM file_header
    CROSS JOIN contract
)

SELECT
    source_table,
    expected_columns,
    arrived_columns,
    documented_columns,
    added_columns,
    missing_columns,
FROM compared
WHERE arrived_columns <> expected_columns
    OR documented_columns <> expected_columns

{% endtest %}
