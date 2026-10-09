-- Grain: one row per loop phase. A phase is either a ledger segment (the agent's own
-- record of loop time, run_ledger.csv) or the gap between two segments. Gaps are kept
-- because the transcript shows real work in them (planning before a segment was opened,
-- Q&A during a usage pause), and a ledger-only total would hide it.
-- phase_end is NULL for the open segment; ledger_hours then runs to the last request
-- in the data.

WITH segments AS (
    SELECT
        loop_segment_id,
        segment_start_at_utc,
        segment_end_at_utc,
        segment_end_reason,
    FROM {{ ref('stg_moonshot__loop_segments') }}
),

last_request AS (
    SELECT
        MAX(requested_at_utc) AS last_request_at_utc,
    FROM {{ ref('fct_llm_requests') }}
),

segments_with_next AS (
    SELECT
        loop_segment_id,
        segment_start_at_utc,
        segment_end_at_utc,
        segment_end_reason,
        LEAD(segment_start_at_utc) OVER (ORDER BY loop_segment_id) AS next_segment_start_at_utc,
    FROM segments
),

segment_phases AS (
    SELECT
        'segment_' || loop_segment_id AS loop_phase_id,
        'ledger_segment' AS phase_kind,
        2 * loop_segment_id - 1 AS phase_order,
        'Ledger segment ' || loop_segment_id || ' (' || segment_end_reason || ')' AS phase_label,
        loop_segment_id,
        segment_start_at_utc AS phase_start_at_utc,
        segment_end_at_utc AS phase_end_at_utc,
    FROM segments
),

gap_phases AS (
    SELECT
        'gap_after_segment_' || loop_segment_id AS loop_phase_id,
        'gap' AS phase_kind,
        2 * loop_segment_id AS phase_order,
        'Gap after segment ' || loop_segment_id AS phase_label,
        CAST(NULL AS INTEGER) AS loop_segment_id,
        segment_end_at_utc AS phase_start_at_utc,
        next_segment_start_at_utc AS phase_end_at_utc,
    FROM segments_with_next
    WHERE segment_end_at_utc IS NOT NULL
),

lead_gap AS (
    SELECT
        'gap_after_segment_0' AS loop_phase_id,
        'gap' AS phase_kind,
        0 AS phase_order,
        'Before segment 1' AS phase_label,
        CAST(NULL AS INTEGER) AS loop_segment_id,
        CAST(NULL AS TIMESTAMP) AS phase_start_at_utc,
        MIN(segment_start_at_utc) AS phase_end_at_utc,
    FROM segments
),

all_phases AS (
    SELECT
        loop_phase_id,
        phase_kind,
        phase_order,
        phase_label,
        loop_segment_id,
        phase_start_at_utc,
        phase_end_at_utc,
    FROM lead_gap
    UNION ALL
    SELECT
        loop_phase_id,
        phase_kind,
        phase_order,
        phase_label,
        loop_segment_id,
        phase_start_at_utc,
        phase_end_at_utc,
    FROM segment_phases
    UNION ALL
    SELECT
        loop_phase_id,
        phase_kind,
        phase_order,
        phase_label,
        loop_segment_id,
        phase_start_at_utc,
        phase_end_at_utc,
    FROM gap_phases
),

activity AS (
    SELECT
        loop_phase_id,
        n_active_intervals,
        active_hours,
        first_request_at_utc,
        last_request_at_utc,
    FROM {{ ref('int_loop_phase_activity') }}
)

SELECT
    p.loop_phase_id,
    p.phase_kind,
    p.phase_order,
    p.phase_label,
    p.loop_segment_id,
    p.phase_start_at_utc,
    p.phase_end_at_utc,
    p.phase_end_at_utc IS NULL AND p.phase_kind = 'ledger_segment' AS is_open,
    CASE
        WHEN p.phase_kind = 'ledger_segment' THEN
            DATE_DIFF('second', p.phase_start_at_utc, COALESCE(p.phase_end_at_utc, l.last_request_at_utc)) / 3600.0
    END AS ledger_hours,
    COALESCE(a.n_active_intervals, 0) AS n_active_intervals,
    COALESCE(a.active_hours, 0) AS active_hours,
    a.first_request_at_utc,
    a.last_request_at_utc,
    DATE_DIFF('second', a.first_request_at_utc, a.last_request_at_utc) / 3600.0 AS transcript_wall_hours,
FROM all_phases AS p
CROSS JOIN last_request AS l
LEFT JOIN activity AS a
    ON p.loop_phase_id = a.loop_phase_id
