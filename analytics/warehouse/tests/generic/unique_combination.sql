{#
    Fails for every combination of the given columns that appears more than once.
    Used for composite grains (for example evaluation_id + version + category) where
    no single column is unique. Pair it with not_null on each key column.
#}
{% test unique_combination(model, combination_of_columns) %}

WITH key_counts AS (
    SELECT
        {% for column in combination_of_columns -%}
        {{ column }},
        {% endfor -%}
        COUNT(*) AS n_rows,
    FROM {{ model }}
    GROUP BY ALL
)

SELECT
    {% for column in combination_of_columns -%}
    {{ column }},
    {% endfor -%}
    n_rows,
FROM key_counts
WHERE n_rows > 1

{% endtest %}
