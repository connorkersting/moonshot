-- Every request, token, Codex request, human message and exported version lands in exactly
-- one loop phase: the phase totals must equal the fact-table totals. A phase boundary that
-- overlapped or left a hole would drop or double-count events silently.

WITH phase_totals AS (
    SELECT
        SUM(claude_requests) AS claude_requests,
        SUM(total_tokens_known) AS total_tokens_known,
        SUM(codex_requests) AS codex_requests,
        SUM(human_messages) AS human_messages,
        SUM(versions_exported) AS versions_exported,
    FROM {{ ref('mart_run_accounting_by_phase') }}
),

role_totals AS (
    SELECT
        SUM(request_count) AS claude_requests,
        SUM(total_tokens_known) AS total_tokens_known,
    FROM {{ ref('mart_run_accounting_by_role') }}
),

fact_totals AS (
    SELECT
        (SELECT COUNT(*) FROM {{ ref('fct_llm_requests') }}) AS claude_requests,
        (SELECT SUM(total_tokens_known) FROM {{ ref('fct_llm_requests') }}) AS total_tokens_known,
        (SELECT COUNT(*) FROM {{ ref('fct_codex_requests') }}) AS codex_requests,
        (SELECT COUNT(*) FROM {{ ref('fct_interventions') }}) AS human_messages,
        (SELECT COUNT(*) FROM {{ ref('dim_version') }} WHERE exported_at_utc IS NOT NULL) AS versions_exported,
),

compared AS (
    SELECT
        p.claude_requests AS phase_claude_requests,
        r.claude_requests AS role_claude_requests,
        f.claude_requests AS fact_claude_requests,
        p.total_tokens_known AS phase_tokens,
        r.total_tokens_known AS role_tokens,
        f.total_tokens_known AS fact_tokens,
        p.codex_requests AS phase_codex_requests,
        f.codex_requests AS fact_codex_requests,
        p.human_messages AS phase_human_messages,
        f.human_messages AS fact_human_messages,
        p.versions_exported AS phase_versions_exported,
        f.versions_exported AS fact_versions_exported,
    FROM phase_totals AS p
    CROSS JOIN role_totals AS r
    CROSS JOIN fact_totals AS f
)

SELECT
    phase_claude_requests,
    role_claude_requests,
    fact_claude_requests,
    phase_tokens,
    role_tokens,
    fact_tokens,
    phase_codex_requests,
    fact_codex_requests,
    phase_human_messages,
    fact_human_messages,
    phase_versions_exported,
    fact_versions_exported,
FROM compared
WHERE phase_claude_requests <> fact_claude_requests
    OR role_claude_requests <> fact_claude_requests
    OR phase_tokens <> fact_tokens
    OR role_tokens <> fact_tokens
    OR phase_codex_requests <> fact_codex_requests
    OR phase_human_messages <> fact_human_messages
    OR phase_versions_exported <> fact_versions_exported
