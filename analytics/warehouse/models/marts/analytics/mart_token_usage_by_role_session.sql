-- Claude token usage by agent role x session part x model. Token types stay in
-- separate columns; total_tokens_known adds them but never adds the lower-bound
-- placeholder for requests whose output count was never finalised.

WITH llm_requests AS (
    SELECT
        agent_role,
        session_part,
        model_id,
        is_usage_final,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens,
        output_tokens_unfinalised_lower_bound,
        total_tokens_known,
    FROM {{ ref('fct_llm_requests') }}
),

models AS (
    SELECT
        model_id,
        model_family,
    FROM {{ ref('dim_model') }}
),

usage_by_group AS (
    SELECT
        r.agent_role,
        r.session_part,
        r.model_id,
        m.model_family,
        COUNT(*) AS request_count,
        COUNT(*) FILTER (WHERE r.is_usage_final) AS requests_usage_final,
        SUM(r.input_tokens) AS input_tokens,
        SUM(r.cache_creation_tokens) AS cache_creation_tokens,
        SUM(r.cache_read_tokens) AS cache_read_tokens,
        -- NULL when no request in the group has a final usage record (unknown, not 0).
        SUM(r.output_tokens) AS output_tokens_final,
        SUM(r.output_tokens_unfinalised_lower_bound) AS output_tokens_unfinalised_lower_bound,
        SUM(r.total_tokens_known) AS total_tokens_known,
    FROM llm_requests AS r
    LEFT JOIN models AS m
        ON r.model_id = m.model_id
    GROUP BY
        r.agent_role,
        r.session_part,
        r.model_id,
        m.model_family
),

usage_with_shares AS (
    SELECT
        agent_role || '|' || session_part || '|' || model_id AS role_session_model_id,
        agent_role,
        session_part,
        model_id,
        model_family,
        request_count,
        requests_usage_final,
        CAST(requests_usage_final AS DOUBLE) / request_count AS usage_final_share,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens_final,
        output_tokens_unfinalised_lower_bound,
        total_tokens_known,
        CAST(cache_read_tokens AS DOUBLE) / NULLIF(total_tokens_known, 0) AS cache_read_share,
        CAST(total_tokens_known AS DOUBLE)
            / SUM(total_tokens_known) OVER (PARTITION BY session_part) AS share_of_session_part_tokens,
        CAST(total_tokens_known AS DOUBLE)
            / SUM(total_tokens_known) OVER () AS share_of_run_tokens,
    FROM usage_by_group
)

SELECT
    role_session_model_id,
    agent_role,
    session_part,
    model_id,
    model_family,
    request_count,
    requests_usage_final,
    usage_final_share,
    input_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    output_tokens_final,
    output_tokens_unfinalised_lower_bound,
    total_tokens_known,
    cache_read_share,
    share_of_session_part_tokens,
    share_of_run_tokens,
FROM usage_with_shares
