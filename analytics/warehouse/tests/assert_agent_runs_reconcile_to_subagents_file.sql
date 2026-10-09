-- Cross-source reconciliation: the ingest wrote per-run totals into subagents.csv
-- from the transcript files; fct_agent_runs rebuilds them from request rows. The
-- two must agree run by run. Returns each run and measure that differs.

WITH file_totals AS (
    SELECT
        subagent_id,
        n_messages AS request_count,
        n_messages_usage_final AS requests_usage_final,
        n_tool_calls,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens_final_only AS output_tokens_final,
    FROM {{ ref('stg_moonshot__subagents') }}
),

model_totals AS (
    SELECT
        subagent_id,
        request_count,
        requests_usage_final,
        n_tool_calls,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens_final,
    FROM {{ ref('fct_agent_runs') }}
),

file_long AS (
    UNPIVOT file_totals
    ON request_count, requests_usage_final, n_tool_calls, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens_final
    INTO NAME measure VALUE file_value
),

model_long AS (
    UNPIVOT model_totals
    ON request_count, requests_usage_final, n_tool_calls, input_tokens, cache_creation_tokens, cache_read_tokens, output_tokens_final
    INTO NAME measure VALUE model_value
),

compared AS (
    SELECT
        COALESCE(f.subagent_id, m.subagent_id) AS subagent_id,
        COALESCE(f.measure, m.measure) AS measure,
        f.file_value,
        m.model_value,
    FROM file_long AS f
    FULL OUTER JOIN model_long AS m
        ON f.subagent_id = m.subagent_id
        AND f.measure = m.measure
)

SELECT
    subagent_id,
    measure,
    file_value,
    model_value,
FROM compared
WHERE file_value IS DISTINCT FROM model_value
