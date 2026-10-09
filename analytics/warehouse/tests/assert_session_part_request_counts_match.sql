-- The ingest reports request counts per session part in session_parts.csv.
-- fct_llm_requests must hold the same number of rows per part, overall and for
-- subagents only.

WITH reported AS (
    SELECT
        session_part,
        ingest_reported_requests,
        ingest_reported_subagent_requests,
    FROM {{ ref('dim_session_part') }}
),

counted AS (
    SELECT
        session_part,
        COUNT(*) AS counted_requests,
        COUNT(*) FILTER (WHERE is_subagent) AS counted_subagent_requests,
    FROM {{ ref('fct_llm_requests') }}
    GROUP BY session_part
),

compared AS (
    SELECT
        COALESCE(r.session_part, c.session_part) AS session_part,
        r.ingest_reported_requests,
        c.counted_requests,
        r.ingest_reported_subagent_requests,
        c.counted_subagent_requests,
    FROM reported AS r
    FULL OUTER JOIN counted AS c
        ON r.session_part = c.session_part
)

SELECT
    session_part,
    ingest_reported_requests,
    counted_requests,
    ingest_reported_subagent_requests,
    counted_subagent_requests,
FROM compared
WHERE ingest_reported_requests IS DISTINCT FROM counted_requests
    OR ingest_reported_subagent_requests IS DISTINCT FROM counted_subagent_requests
