-- Collapses requests to one row per agent BEFORE anything joins to them, so a
-- join to spawns or runs can never fan out and double-count tokens.

WITH llm_requests AS (
    SELECT
        agent_id,
        model_id,
        requested_at_utc,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens,
        output_tokens_lower_bound,
        is_usage_final,
        n_tool_calls,
    FROM {{ ref('stg_moonshot__agent_messages') }}
),

agent_request_totals AS (
    SELECT
        agent_id,
        COUNT(DISTINCT model_id) AS n_models,
        MIN(model_id) AS model_id,
        MIN(requested_at_utc) AS first_request_at_utc,
        MAX(requested_at_utc) AS last_request_at_utc,
        COUNT(*) AS request_count,
        COUNT(*) FILTER (WHERE is_usage_final) AS requests_usage_final,
        SUM(input_tokens) AS input_tokens,
        SUM(cache_creation_tokens) AS cache_creation_tokens,
        SUM(cache_read_tokens) AS cache_read_tokens,
        -- Known output only. Requests without a closing usage line add nothing here;
        -- their streamed placeholder is summed separately as a lower bound. NULL
        -- (not 0) when no request of the agent was finalised: the output is
        -- unknown, which is what subagents.csv records too.
        SUM(output_tokens) AS output_tokens_final,
        COALESCE(SUM(output_tokens_lower_bound) FILTER (WHERE NOT is_usage_final), 0) AS output_tokens_unfinalised_lower_bound,
        SUM(n_tool_calls) AS n_tool_calls,
    FROM llm_requests
    GROUP BY agent_id
)

SELECT
    agent_id,
    n_models,
    model_id,
    first_request_at_utc,
    last_request_at_utc,
    request_count,
    requests_usage_final,
    input_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    output_tokens_final,
    output_tokens_unfinalised_lower_bound,
    n_tool_calls,
FROM agent_request_totals
