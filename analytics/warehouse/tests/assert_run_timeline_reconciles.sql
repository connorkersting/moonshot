-- Every event lands in exactly one timeline bucket: the bucket totals must equal
-- the fact-table totals. A bucket range that started too late or ended too early
-- would drop events silently.

WITH timeline_totals AS (
    SELECT
        SUM(llm_requests) AS llm_requests,
        SUM(llm_tokens_known) AS llm_tokens_known,
        SUM(codex_requests) AS codex_requests,
        SUM(codex_tokens) AS codex_tokens,
        SUM(interventions) AS interventions,
        SUM(compactions) AS compactions,
    FROM {{ ref('mart_run_timeline') }}
),

llm_totals AS (
    SELECT
        COUNT(*) AS llm_requests,
        SUM(total_tokens_known) AS llm_tokens_known,
    FROM {{ ref('fct_llm_requests') }}
),

codex_totals AS (
    SELECT
        COUNT(*) AS codex_requests,
        SUM(total_tokens) AS codex_tokens,
    FROM {{ ref('fct_codex_requests') }}
),

intervention_totals AS (
    SELECT
        COUNT(*) AS interventions,
    FROM {{ ref('fct_interventions') }}
),

compaction_totals AS (
    SELECT
        COUNT(*) AS compactions,
    FROM {{ ref('fct_session_events') }}
    WHERE event_type = 'compaction'
),

compared AS (
    SELECT
        t.llm_requests AS timeline_llm_requests,
        l.llm_requests AS fact_llm_requests,
        t.llm_tokens_known AS timeline_llm_tokens,
        l.llm_tokens_known AS fact_llm_tokens,
        t.codex_requests AS timeline_codex_requests,
        c.codex_requests AS fact_codex_requests,
        t.codex_tokens AS timeline_codex_tokens,
        c.codex_tokens AS fact_codex_tokens,
        t.interventions AS timeline_interventions,
        i.interventions AS fact_interventions,
        t.compactions AS timeline_compactions,
        k.compactions AS fact_compactions,
    FROM timeline_totals AS t
    CROSS JOIN llm_totals AS l
    CROSS JOIN codex_totals AS c
    CROSS JOIN intervention_totals AS i
    CROSS JOIN compaction_totals AS k
)

SELECT
    timeline_llm_requests,
    fact_llm_requests,
    timeline_llm_tokens,
    fact_llm_tokens,
    timeline_codex_requests,
    fact_codex_requests,
    timeline_codex_tokens,
    fact_codex_tokens,
    timeline_interventions,
    fact_interventions,
    timeline_compactions,
    fact_compactions,
FROM compared
WHERE timeline_llm_requests IS DISTINCT FROM fact_llm_requests
    OR timeline_llm_tokens IS DISTINCT FROM fact_llm_tokens
    OR timeline_codex_requests IS DISTINCT FROM fact_codex_requests
    OR timeline_codex_tokens IS DISTINCT FROM fact_codex_tokens
    OR timeline_interventions IS DISTINCT FROM fact_interventions
    OR timeline_compactions IS DISTINCT FROM fact_compactions
