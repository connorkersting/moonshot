-- Reconciliation: raw agent_messages -> fct_llm_requests -> mart_token_usage_by_role_session.
-- Row counts and every token sum must match at each hop, per model. Returns one
-- row per model and measure that drifts, with the numbers at each layer.

WITH source_totals AS (
    SELECT
        model AS model_id,
        COUNT(*) AS request_count,
        SUM(input_tokens) AS input_tokens,
        SUM(cache_creation_tokens) AS cache_creation_tokens,
        SUM(cache_read_tokens) AS cache_read_tokens,
        COALESCE(SUM(output_tokens), 0) AS output_tokens,
    FROM {{ source('moonshot_raw', 'agent_messages') }}
    GROUP BY model
),

fact_totals AS (
    SELECT
        model_id,
        COUNT(*) AS request_count,
        SUM(input_tokens) AS input_tokens,
        SUM(cache_creation_tokens) AS cache_creation_tokens,
        SUM(cache_read_tokens) AS cache_read_tokens,
        COALESCE(SUM(output_tokens), 0) AS output_tokens,
    FROM {{ ref('fct_llm_requests') }}
    GROUP BY model_id
),

mart_totals AS (
    SELECT
        model_id,
        SUM(request_count) AS request_count,
        SUM(input_tokens) AS input_tokens,
        SUM(cache_creation_tokens) AS cache_creation_tokens,
        SUM(cache_read_tokens) AS cache_read_tokens,
        SUM(output_tokens_final) AS output_tokens,
    FROM {{ ref('mart_token_usage_by_role_session') }}
    GROUP BY model_id
),

source_long AS (
    UNPIVOT source_totals
    ON request_count, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens
    INTO NAME measure VALUE source_value
),

fact_long AS (
    UNPIVOT fact_totals
    ON request_count, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens
    INTO NAME measure VALUE fact_value
),

mart_long AS (
    UNPIVOT mart_totals
    ON request_count, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens
    INTO NAME measure VALUE mart_value
),

compared AS (
    SELECT
        COALESCE(s.model_id, f.model_id, m.model_id) AS model_id,
        COALESCE(s.measure, f.measure, m.measure) AS measure,
        s.source_value,
        f.fact_value,
        m.mart_value,
    FROM source_long AS s
    FULL OUTER JOIN fact_long AS f
        ON s.model_id = f.model_id
        AND s.measure = f.measure
    FULL OUTER JOIN mart_long AS m
        ON COALESCE(s.model_id, f.model_id) = m.model_id
        AND COALESCE(s.measure, f.measure) = m.measure
)

SELECT
    model_id,
    measure,
    source_value,
    fact_value,
    mart_value,
FROM compared
WHERE source_value IS DISTINCT FROM fact_value
    OR fact_value IS DISTINCT FROM mart_value
