{#
    Fails for every non-null value outside [min_value, max_value] (inclusive).
    Either bound may be left out. NULLs are not checked here; use not_null for that.
#}
{% test value_in_range(model, column_name, min_value=none, max_value=none) %}

{%- if min_value is none and max_value is none -%}
    {{ exceptions.raise_compiler_error("value_in_range on " ~ column_name ~ ": give min_value, max_value or both") }}
{%- endif -%}

WITH checked_values AS (
    SELECT
        {{ column_name }} AS checked_value,
    FROM {{ model }}
    WHERE {{ column_name }} IS NOT NULL
)

SELECT
    checked_value,
FROM checked_values
WHERE FALSE
    {% if min_value is not none -%}
    OR checked_value < {{ min_value }}
    {% endif -%}
    {% if max_value is not none -%}
    OR checked_value > {{ max_value }}
    {% endif %}

{% endtest %}


{#
    Shorthand for token counts, durations and other measures that can never be
    negative.
#}
{% test non_negative(model, column_name) %}
    {{ test_value_in_range(model, column_name, min_value=0) }}
{% endtest %}
