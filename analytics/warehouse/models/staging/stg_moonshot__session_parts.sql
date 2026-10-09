WITH source_session_parts AS (
    SELECT
        session_part,
        wall_start_utc,
        wall_end_utc,
        wall_start_local,
        wall_end_local,
        wall_hours,
        active_hours,
        n_active_intervals,
        n_requests,
        n_subagent_requests,
    FROM {{ source('moonshot_raw', 'session_parts') }}
),

renamed_session_parts AS (
    SELECT
        CAST(session_part AS INTEGER) AS session_part,
        CAST(REPLACE(wall_start_utc, 'Z', '') AS TIMESTAMP) AS wall_start_at_utc,
        CAST(REPLACE(wall_end_utc, 'Z', '') AS TIMESTAMP) AS wall_end_at_utc,
        CAST(LEFT(wall_start_local, 19) AS TIMESTAMP) AS wall_start_at_local,
        CAST(LEFT(wall_end_local, 19) AS TIMESTAMP) AS wall_end_at_local,
        wall_hours,
        active_hours,
        n_active_intervals,
        n_requests,
        n_subagent_requests,
    FROM source_session_parts
)

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
FROM renamed_session_parts
