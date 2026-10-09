{#
    Use the folder-level schema name as-is (staging, intermediate, core, marts, seeds)
    instead of dbt's default "<target_schema>_<custom_schema>". The warehouse is a
    single local DuckDB file, so there is no dev/prod schema split to protect.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
