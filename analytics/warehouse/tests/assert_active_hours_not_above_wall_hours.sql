-- Active time is the union of request intervals, so it can never exceed the time between
-- a phase's first and last request. Returns the phases where it does (a double-counted
-- parallel subagent would show up here).

SELECT
    loop_phase_id,
    active_hours,
    transcript_wall_hours,
FROM {{ ref('dim_loop_phase') }}
WHERE active_hours > COALESCE(transcript_wall_hours, 0) + 0.001
