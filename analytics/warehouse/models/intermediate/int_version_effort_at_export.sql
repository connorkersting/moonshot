-- Grain: one row per exported version.
-- How much loop time and how many project tokens had been spent when the version was
-- exported (the mp4's modification time).
--
--   loop_hours_at_export: ledger segments only (run_ledger.csv, the agent's own record of
--     loop time), summed up to the export. Time in a gap between segments is not counted.
--   project_tokens_known_at_export: every Claude request in the project up to the export
--     (all agents, input + cache + known output), so it includes work that never touched
--     the trailer. Output is the final count where one was written, otherwise zero here;
--     the floor for unfinalised requests is not added.

WITH exported_versions AS (
    SELECT
        version_id,
        exported_at_utc,
    FROM {{ ref('stg_moonshot__versions') }}
    WHERE exported_at_utc IS NOT NULL
),

segments AS (
    SELECT
        loop_segment_id,
        segment_start_at_utc,
        segment_end_at_utc,
    FROM {{ ref('stg_moonshot__loop_segments') }}
),

loop_hours AS (
    SELECT
        v.version_id,
        COALESCE(
            SUM(
                GREATEST(
                    0,
                    DATE_DIFF(
                        'second',
                        s.segment_start_at_utc,
                        LEAST(COALESCE(s.segment_end_at_utc, v.exported_at_utc), v.exported_at_utc)
                    )
                )
            ) / 3600.0,
            0
        ) AS loop_hours_at_export,
    FROM exported_versions AS v
    CROSS JOIN segments AS s
    GROUP BY v.version_id
),

project_tokens AS (
    SELECT
        v.version_id,
        SUM(
            r.input_tokens + r.cache_creation_tokens + r.cache_read_tokens + COALESCE(r.output_tokens, 0)
        ) AS project_tokens_known_at_export,
        COUNT(*) AS project_requests_at_export,
    FROM exported_versions AS v
    INNER JOIN {{ ref('stg_moonshot__agent_messages') }} AS r
        ON r.requested_at_utc <= v.exported_at_utc
    GROUP BY v.version_id
)

SELECT
    v.version_id,
    v.exported_at_utc,
    l.loop_hours_at_export,
    t.project_requests_at_export,
    t.project_tokens_known_at_export,
FROM exported_versions AS v
INNER JOIN loop_hours AS l
    ON v.version_id = l.version_id
LEFT JOIN project_tokens AS t
    ON v.version_id = t.version_id
