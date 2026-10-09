-- Grain: one row per loop phase (a ledger segment or the gap between two segments).
-- Project-only cost: Claude requests and Codex requests that belong to this project,
-- counted in tokens. It never carries the account-wide plan percentages that the Codex
-- logs record (plan_5h_used_pct, plan_weekly_used_pct): those include everything else
-- on the account and are not a project cost.
--
-- Output tokens are reported two ways because about a third of requests never got a
-- closing usage record: output_tokens_final adds only requests with a final count,
-- output_tokens_unfinalised_lower_bound adds the streamed placeholder of the rest (a
-- floor). Neither is a complete figure and they are never added together here.
--
-- Codex attribution is an upper bound: a rollout counts when it ran in a folder named
-- moonshot or in the craftapps project during the run (see the ingest README).

WITH phases AS (
    SELECT
        loop_phase_id,
        phase_kind,
        phase_order,
        phase_label,
        phase_start_at_utc,
        phase_end_at_utc,
        ledger_hours,
        active_hours,
        n_active_intervals,
        first_request_at_utc,
        last_request_at_utc,
        transcript_wall_hours,
    FROM {{ ref('dim_loop_phase') }}
),

requests AS (
    SELECT
        p.loop_phase_id,
        r.message_id,
        r.agent_id,
        r.is_subagent,
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

claude_usage AS (
    SELECT
        loop_phase_id,
        COUNT(*) AS claude_requests,
        COUNT(*) FILTER (WHERE NOT is_subagent) AS main_agent_requests,
        COUNT(*) FILTER (WHERE is_subagent) AS subagent_requests,
        COUNT(DISTINCT agent_id) FILTER (WHERE is_subagent) AS subagents_active,
        COUNT(*) FILTER (WHERE is_usage_final) AS requests_usage_final,
        COUNT(*) FILTER (WHERE NOT is_usage_final) AS requests_without_final_usage,
        SUM(input_tokens) AS input_tokens,
        SUM(cache_creation_tokens) AS cache_creation_tokens,
        SUM(cache_read_tokens) AS cache_read_tokens,
        SUM(output_tokens) AS output_tokens_final,
        SUM(output_tokens_unfinalised_lower_bound) AS output_tokens_unfinalised_lower_bound,
        SUM(total_tokens_known) AS total_tokens_known,
    FROM requests
    GROUP BY loop_phase_id
),

codex_in_phase AS (
    SELECT
        p.loop_phase_id,
        COUNT(*) AS codex_requests,
        SUM(c.input_tokens) AS codex_input_tokens,
        SUM(c.cached_input_tokens) AS codex_cached_input_tokens,
        SUM(c.output_tokens) AS codex_output_tokens,
    FROM {{ ref('fct_codex_requests') }} AS c
    INNER JOIN phases AS p
        ON c.requested_at_utc >= COALESCE(p.phase_start_at_utc, TIMESTAMP '1970-01-01')
        AND (p.phase_end_at_utc IS NULL OR c.requested_at_utc < p.phase_end_at_utc)
    GROUP BY p.loop_phase_id
),

interventions_in_phase AS (
    SELECT
        p.loop_phase_id,
        COUNT(*) AS human_messages,
    FROM {{ ref('fct_interventions') }} AS i
    INNER JOIN phases AS p
        ON i.intervened_at_utc >= COALESCE(p.phase_start_at_utc, TIMESTAMP '1970-01-01')
        AND (p.phase_end_at_utc IS NULL OR i.intervened_at_utc < p.phase_end_at_utc)
    GROUP BY p.loop_phase_id
),

versions_in_phase AS (
    SELECT
        p.loop_phase_id,
        COUNT(*) AS versions_exported,
        COUNT(*) FILTER (WHERE v.is_promoted) AS versions_promoted,
        MIN(v.version_number) AS first_version_number,
        MAX(v.version_number) AS last_version_number,
    FROM {{ ref('dim_version') }} AS v
    INNER JOIN phases AS p
        ON v.exported_at_utc >= COALESCE(p.phase_start_at_utc, TIMESTAMP '1970-01-01')
        AND (p.phase_end_at_utc IS NULL OR v.exported_at_utc < p.phase_end_at_utc)
    GROUP BY p.loop_phase_id
)

SELECT
    p.loop_phase_id,
    p.phase_kind,
    p.phase_order,
    p.phase_label,
    p.phase_start_at_utc,
    p.phase_end_at_utc,
    p.ledger_hours,
    p.active_hours,
    p.n_active_intervals,
    p.transcript_wall_hours,
    p.first_request_at_utc,
    p.last_request_at_utc,
    COALESCE(u.claude_requests, 0) AS claude_requests,
    COALESCE(u.main_agent_requests, 0) AS main_agent_requests,
    COALESCE(u.subagent_requests, 0) AS subagent_requests,
    COALESCE(u.subagents_active, 0) AS subagents_active,
    COALESCE(u.requests_usage_final, 0) AS requests_usage_final,
    COALESCE(u.requests_without_final_usage, 0) AS requests_without_final_usage,
    u.input_tokens,
    u.cache_creation_tokens,
    u.cache_read_tokens,
    u.output_tokens_final,
    u.output_tokens_unfinalised_lower_bound,
    u.total_tokens_known,
    COALESCE(cx.codex_requests, 0) AS codex_requests,
    cx.codex_input_tokens,
    cx.codex_cached_input_tokens,
    cx.codex_output_tokens,
    COALESCE(i.human_messages, 0) AS human_messages,
    COALESCE(v.versions_exported, 0) AS versions_exported,
    COALESCE(v.versions_promoted, 0) AS versions_promoted,
    v.first_version_number,
    v.last_version_number,
FROM phases AS p
LEFT JOIN claude_usage AS u
    ON p.loop_phase_id = u.loop_phase_id
LEFT JOIN codex_in_phase AS cx
    ON p.loop_phase_id = cx.loop_phase_id
LEFT JOIN interventions_in_phase AS i
    ON p.loop_phase_id = i.loop_phase_id
LEFT JOIN versions_in_phase AS v
    ON p.loop_phase_id = v.loop_phase_id
