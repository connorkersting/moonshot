WITH codex_requests AS (
    SELECT
        codex_request_id,
        codex_session_id,
        request_seq,
        requested_at_utc,
        requested_at_local,
        model_id,
        workdir_name,
        attribution,
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        plan_5h_used_pct,
        plan_weekly_used_pct,
    FROM {{ ref('stg_moonshot__codex_requests') }}
),

session_parts AS (
    SELECT
        session_part,
        wall_start_at_utc,
        wall_end_at_utc,
    FROM {{ ref('dim_session_part') }}
),

requests_in_parts AS (
    SELECT
        c.codex_request_id,
        c.codex_session_id,
        c.request_seq,
        c.requested_at_utc,
        c.requested_at_local,
        -- Codex logs carry no session part; assign it from the Claude session's
        -- wall-clock window. NULL when the request falls outside both parts.
        sp.session_part,
        c.model_id,
        c.workdir_name,
        c.attribution,
        c.input_tokens,
        c.cached_input_tokens,
        c.input_tokens - c.cached_input_tokens AS uncached_input_tokens,
        c.output_tokens,
        c.reasoning_output_tokens,
        c.input_tokens + c.output_tokens AS total_tokens,
        c.plan_5h_used_pct,
        c.plan_weekly_used_pct,
    FROM codex_requests AS c
    LEFT JOIN session_parts AS sp
        ON c.requested_at_utc BETWEEN sp.wall_start_at_utc AND sp.wall_end_at_utc
)

SELECT
    codex_request_id,
    codex_session_id,
    request_seq,
    requested_at_utc,
    requested_at_local,
    session_part,
    model_id,
    workdir_name,
    attribution,
    input_tokens,
    cached_input_tokens,
    uncached_input_tokens,
    output_tokens,
    reasoning_output_tokens,
    total_tokens,
    plan_5h_used_pct,
    plan_weekly_used_pct,
FROM requests_in_parts
