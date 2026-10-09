-- Grain: one row per loop phase x agent role x model. The same token columns as
-- mart_run_accounting_by_phase, split by who spent them. Project-only; the account-wide
-- plan percentage is not used here. Output tokens are final-only and a separate floor
-- for the unfinalised requests (never summed together).

WITH requests AS (
    SELECT
        p.loop_phase_id,
        r.agent_role,
        r.model_id,
        r.message_id,
        r.is_usage_final,
        r.input_tokens,
        r.cache_creation_tokens,
        r.cache_read_tokens,
        r.output_tokens,
        r.output_tokens_unfinalised_lower_bound,
        r.total_tokens_known,
    FROM {{ ref('int_requests_in_loop_segments') }} AS p
    INNER JOIN {{ ref('fct_llm_requests') }} AS r
        ON p.message_id = r.message_id
),

models AS (
    SELECT
        model_id,
        model_family,
    FROM {{ ref('dim_model') }}
),

usage_by_group AS (
    SELECT
        r.loop_phase_id,
        r.agent_role,
        r.model_id,
        m.model_family,
        COUNT(*) AS request_count,
        COUNT(*) FILTER (WHERE r.is_usage_final) AS requests_usage_final,
        SUM(r.input_tokens) AS input_tokens,
        SUM(r.cache_creation_tokens) AS cache_creation_tokens,
        SUM(r.cache_read_tokens) AS cache_read_tokens,
        SUM(r.output_tokens) AS output_tokens_final,
        SUM(r.output_tokens_unfinalised_lower_bound) AS output_tokens_unfinalised_lower_bound,
        SUM(r.total_tokens_known) AS total_tokens_known,
    FROM requests AS r
    LEFT JOIN models AS m
        ON r.model_id = m.model_id
    GROUP BY
        r.loop_phase_id,
        r.agent_role,
        r.model_id,
        m.model_family
)

SELECT
    loop_phase_id || '|' || agent_role || '|' || model_id AS phase_role_model_id,
    loop_phase_id,
    agent_role,
    model_id,
    model_family,
    request_count,
    requests_usage_final,
    input_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    output_tokens_final,
    output_tokens_unfinalised_lower_bound,
    total_tokens_known,
FROM usage_by_group
