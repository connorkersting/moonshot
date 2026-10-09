-- 15-minute buckets from the first to the last recorded activity, including the
-- idle gap between the two session parts (those buckets are kept, with zeros, so
-- a timeline chart shows the gap instead of closing it).

WITH llm_requests AS (
    SELECT
        message_id,
        agent_id,
        is_subagent,
        requested_at_utc,
        total_tokens_known,
    FROM {{ ref('fct_llm_requests') }}
),

codex_requests AS (
    SELECT
        codex_request_id,
        requested_at_utc,
        total_tokens,
    FROM {{ ref('fct_codex_requests') }}
),

interventions AS (
    SELECT
        intervention_id,
        intervened_at_utc,
    FROM {{ ref('fct_interventions') }}
),

session_events AS (
    SELECT
        session_event_id,
        event_type,
        event_at_utc,
    FROM {{ ref('fct_session_events') }}
),

agent_runs AS (
    SELECT
        subagent_id,
        first_request_at_utc,
        ended_at_utc,
    FROM {{ ref('fct_agent_runs') }}
),

session_parts AS (
    SELECT
        session_part,
        wall_start_at_utc,
        wall_end_at_utc,
    FROM {{ ref('dim_session_part') }}
),

activity_times AS (
    SELECT requested_at_utc AS activity_at_utc FROM llm_requests
    UNION ALL
    SELECT requested_at_utc FROM codex_requests
    UNION ALL
    SELECT intervened_at_utc FROM interventions
    UNION ALL
    SELECT event_at_utc FROM session_events
),

timeline_bounds AS (
    SELECT
        time_bucket(INTERVAL 15 MINUTE, MIN(activity_at_utc)) AS first_bucket_utc,
        time_bucket(INTERVAL 15 MINUTE, MAX(activity_at_utc)) AS last_bucket_utc,
    FROM activity_times
),

buckets AS (
    SELECT
        UNNEST(generate_series(first_bucket_utc, last_bucket_utc, INTERVAL 15 MINUTE)) AS bucket_start_utc,
    FROM timeline_bounds
),

llm_activity AS (
    SELECT
        time_bucket(INTERVAL 15 MINUTE, requested_at_utc) AS bucket_start_utc,
        COUNT(*) AS llm_requests,
        COUNT(*) FILTER (WHERE is_subagent) AS subagent_llm_requests,
        SUM(total_tokens_known) AS llm_tokens_known,
        COUNT(DISTINCT agent_id) AS active_agents,
        COUNT(DISTINCT agent_id) FILTER (WHERE is_subagent) AS active_subagents,
    FROM llm_requests
    GROUP BY 1
),

codex_activity AS (
    SELECT
        time_bucket(INTERVAL 15 MINUTE, requested_at_utc) AS bucket_start_utc,
        COUNT(*) AS codex_requests,
        SUM(total_tokens) AS codex_tokens,
    FROM codex_requests
    GROUP BY 1
),

intervention_activity AS (
    SELECT
        time_bucket(INTERVAL 15 MINUTE, intervened_at_utc) AS bucket_start_utc,
        COUNT(*) AS interventions,
    FROM interventions
    GROUP BY 1
),

compaction_activity AS (
    SELECT
        time_bucket(INTERVAL 15 MINUTE, event_at_utc) AS bucket_start_utc,
        COUNT(*) AS compactions,
    FROM session_events
    WHERE event_type = 'compaction'
    GROUP BY 1
),

running_subagents AS (
    -- A subagent counts as running in every bucket its first-to-last request span
    -- touches, even when it made no request inside that bucket.
    SELECT
        b.bucket_start_utc,
        COUNT(r.subagent_id) AS running_subagents,
    FROM buckets AS b
    LEFT JOIN agent_runs AS r
        ON r.first_request_at_utc < b.bucket_start_utc + INTERVAL 15 MINUTE
        AND r.ended_at_utc >= b.bucket_start_utc
    GROUP BY b.bucket_start_utc
),

bucket_session_parts AS (
    SELECT
        b.bucket_start_utc,
        MIN(sp.session_part) AS session_part,
    FROM buckets AS b
    LEFT JOIN session_parts AS sp
        ON sp.wall_start_at_utc < b.bucket_start_utc + INTERVAL 15 MINUTE
        AND sp.wall_end_at_utc >= b.bucket_start_utc
    GROUP BY b.bucket_start_utc
),

timeline AS (
    SELECT
        b.bucket_start_utc,
        b.bucket_start_utc + INTERVAL 15 MINUTE AS bucket_end_utc,
        timezone('America/New_York', timezone('UTC', b.bucket_start_utc)) AS bucket_start_local,
        p.session_part,
        COALESCE(l.llm_requests, 0) AS llm_requests,
        COALESCE(l.subagent_llm_requests, 0) AS subagent_llm_requests,
        COALESCE(l.llm_tokens_known, 0) AS llm_tokens_known,
        COALESCE(l.active_agents, 0) AS active_agents,
        COALESCE(l.active_subagents, 0) AS active_subagents,
        COALESCE(rs.running_subagents, 0) AS running_subagents,
        COALESCE(c.codex_requests, 0) AS codex_requests,
        COALESCE(c.codex_tokens, 0) AS codex_tokens,
        COALESCE(i.interventions, 0) AS interventions,
        COALESCE(k.compactions, 0) AS compactions,
        COALESCE(l.llm_requests, 0) > 0 AS is_active_bucket,
    FROM buckets AS b
    LEFT JOIN bucket_session_parts AS p
        ON b.bucket_start_utc = p.bucket_start_utc
    LEFT JOIN llm_activity AS l
        ON b.bucket_start_utc = l.bucket_start_utc
    LEFT JOIN running_subagents AS rs
        ON b.bucket_start_utc = rs.bucket_start_utc
    LEFT JOIN codex_activity AS c
        ON b.bucket_start_utc = c.bucket_start_utc
    LEFT JOIN intervention_activity AS i
        ON b.bucket_start_utc = i.bucket_start_utc
    LEFT JOIN compaction_activity AS k
        ON b.bucket_start_utc = k.bucket_start_utc
)

SELECT
    bucket_start_utc,
    bucket_end_utc,
    bucket_start_local,
    session_part,
    llm_requests,
    subagent_llm_requests,
    llm_tokens_known,
    active_agents,
    active_subagents,
    running_subagents,
    codex_requests,
    codex_tokens,
    interventions,
    compactions,
    is_active_bucket,
FROM timeline
