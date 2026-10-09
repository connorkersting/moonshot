-- Puts every Claude request in the ledger segment that was open when it ran, or in the
-- gap before the next segment when none was. The ledger (run_ledger.csv) is the agent's
-- own record of loop time; the transcript is the evidence it is checked against, so
-- activity that falls between segments is kept visible instead of being dropped.
-- Segments do not overlap, so each request matches at most one; a test guards the grain.

WITH llm_requests AS (
    SELECT
        message_id,
        requested_at_utc,
    FROM {{ ref('fct_llm_requests') }}
),

segments AS (
    SELECT
        loop_segment_id,
        segment_start_at_utc,
        segment_end_at_utc,
    FROM {{ ref('stg_moonshot__loop_segments') }}
),

requests_with_segment AS (
    SELECT
        r.message_id,
        r.requested_at_utc,
        s.loop_segment_id,
    FROM llm_requests AS r
    LEFT JOIN segments AS s
        ON r.requested_at_utc >= s.segment_start_at_utc
        AND (s.segment_end_at_utc IS NULL OR r.requested_at_utc < s.segment_end_at_utc)
),

-- For a request in no segment, the number of segments that started before it says
-- which gap it is in (gap_after_segment_1 is between segment 1 and segment 2).
requests_with_phase AS (
    SELECT
        r.message_id,
        r.requested_at_utc,
        r.loop_segment_id,
        CASE
            WHEN r.loop_segment_id IS NOT NULL THEN 'segment_' || r.loop_segment_id
            ELSE 'gap_after_segment_' || (
                SELECT COUNT(*) FROM segments AS s WHERE s.segment_start_at_utc <= r.requested_at_utc
            )
        END AS loop_phase_id,
    FROM requests_with_segment AS r
)

SELECT
    message_id,
    requested_at_utc,
    loop_segment_id,
    loop_phase_id,
    loop_segment_id IS NOT NULL AS is_inside_ledger_segment,
FROM requests_with_phase
