-- Active time per loop phase. Same rule as the ingest's session-part active time:
-- sort every request start time (main agent and subagents together), merge neighbours
-- no more than active_gap_minutes apart into one interval, and sum the interval
-- lengths. Parallel subagents are counted once; an isolated request adds zero.
-- Grain: one row per loop phase.

WITH requests AS (
    SELECT
        loop_phase_id,
        requested_at_utc,
    FROM {{ ref('int_requests_in_loop_segments') }}
),

with_previous AS (
    SELECT
        loop_phase_id,
        requested_at_utc,
        LAG(requested_at_utc) OVER (PARTITION BY loop_phase_id ORDER BY requested_at_utc) AS previous_request_at_utc,
    FROM requests
),

with_interval_start AS (
    SELECT
        loop_phase_id,
        requested_at_utc,
        CASE
            WHEN previous_request_at_utc IS NULL THEN 1
            WHEN requested_at_utc - previous_request_at_utc > to_minutes({{ var('active_gap_minutes') }}) THEN 1
            ELSE 0
        END AS starts_interval,
    FROM with_previous
),

with_interval_no AS (
    SELECT
        loop_phase_id,
        requested_at_utc,
        SUM(starts_interval) OVER (PARTITION BY loop_phase_id ORDER BY requested_at_utc) AS interval_no,
    FROM with_interval_start
),

intervals AS (
    SELECT
        loop_phase_id,
        interval_no,
        MIN(requested_at_utc) AS interval_start_at_utc,
        MAX(requested_at_utc) AS interval_end_at_utc,
    FROM with_interval_no
    GROUP BY
        loop_phase_id,
        interval_no
),

phase_activity AS (
    SELECT
        loop_phase_id,
        COUNT(*) AS n_active_intervals,
        SUM(DATE_DIFF('second', interval_start_at_utc, interval_end_at_utc)) / 3600.0 AS active_hours,
        MIN(interval_start_at_utc) AS first_request_at_utc,
        MAX(interval_end_at_utc) AS last_request_at_utc,
    FROM intervals
    GROUP BY loop_phase_id
)

SELECT
    loop_phase_id,
    n_active_intervals,
    active_hours,
    first_request_at_utc,
    last_request_at_utc,
FROM phase_activity
