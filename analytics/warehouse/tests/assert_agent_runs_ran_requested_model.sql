-- Each subagent was asked for a model alias (opus / sonnet / fable). The model it
-- actually ran must be from that family; a silent fallback to another model would
-- change cost and quality numbers without anyone noticing. A subagent spawned without
-- a model ('inherit', from the v23 builders on) must have run a model family the main
-- agent itself used.

WITH agent_runs AS (
    SELECT
        subagent_id,
        requested_model_alias,
        model_id,
    FROM {{ ref('fct_agent_runs') }}
),

models AS (
    SELECT
        model_id,
        model_family,
    FROM {{ ref('dim_model') }}
),

main_families AS (
    SELECT DISTINCT
        m.model_family,
    FROM {{ ref('fct_llm_requests') }} AS r
    INNER JOIN models AS m
        ON r.model_id = m.model_id
    WHERE NOT r.is_subagent
),

compared AS (
    SELECT
        r.subagent_id,
        r.requested_model_alias,
        r.model_id,
        m.model_family,
    FROM agent_runs AS r
    LEFT JOIN models AS m
        ON r.model_id = m.model_id
)

SELECT
    subagent_id,
    requested_model_alias,
    model_id,
    model_family,
FROM compared
WHERE (requested_model_alias <> 'inherit' AND model_family IS DISTINCT FROM requested_model_alias)
    OR (requested_model_alias = 'inherit' AND model_family NOT IN (SELECT model_family FROM main_families))
