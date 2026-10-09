WITH session_parts AS (
    SELECT
        session_part,
        wall_start_at_utc,
        wall_end_at_utc,
        wall_start_at_local,
        wall_end_at_local,
        wall_hours,
        active_hours,
        n_active_intervals,
        n_requests,
        n_subagent_requests,
    FROM {{ ref('stg_moonshot__session_parts') }}
),

labelled_session_parts AS (
    SELECT
        session_part,
        CASE session_part
            WHEN 1 THEN 'overnight run'
            WHEN 2 THEN '24-hour extension'
            WHEN 3 THEN 'tool expansion and v22'
        END AS session_part_label,
        wall_start_at_utc,
        wall_end_at_utc,
        wall_start_at_local,
        wall_end_at_local,
        wall_hours,
        active_hours,
        active_hours / NULLIF(wall_hours, 0) AS active_share_of_wall,
        n_active_intervals,
        n_requests AS ingest_reported_requests,
        n_subagent_requests AS ingest_reported_subagent_requests,
    FROM session_parts
)

SELECT
    session_part,
    session_part_label,
    wall_start_at_utc,
    wall_end_at_utc,
    wall_start_at_local,
    wall_end_at_local,
    wall_hours,
    active_hours,
    active_share_of_wall,
    n_active_intervals,
    ingest_reported_requests,
    ingest_reported_subagent_requests,
FROM labelled_session_parts
