-- Every model id that appears anywhere in the run, with provider and family parsed
-- from the id. An id that matches no known pattern gets a NULL family, which the
-- not_null test turns into a loud failure instead of a silent "other".

WITH llm_request_models AS (
    SELECT DISTINCT
        model_id,
    FROM {{ ref('stg_moonshot__agent_messages') }}
),

codex_request_models AS (
    SELECT DISTINCT
        model_id,
    FROM {{ ref('stg_moonshot__codex_requests') }}
),

critic_models AS (
    SELECT DISTINCT
        critic_model_id AS model_id,
    FROM {{ ref('stg_moonshot__critic_scores') }}
    -- Only critics that ran inside this Claude Code project. Codex, Gemini and
    -- TwelveLabs model labels live in dim_critic instead.
    WHERE critic_id IN ('fable_editor')
),

judge_models AS (
    SELECT DISTINCT
        judge_model_id AS model_id,
    FROM {{ ref('stg_moonshot__ab_votes') }}
),

all_models AS (
    SELECT model_id FROM llm_request_models
    UNION
    SELECT model_id FROM codex_request_models
    UNION
    SELECT model_id FROM critic_models
    UNION
    SELECT model_id FROM judge_models
),

classified_models AS (
    SELECT
        model_id,
        CASE
            WHEN model_id LIKE 'claude-%' THEN 'anthropic'
            WHEN model_id LIKE 'gpt-%' THEN 'openai'
        END AS provider,
        CASE
            WHEN model_id LIKE 'claude-%' THEN split_part(model_id, '-', 2)
            WHEN model_id LIKE 'gpt-%' THEN 'gpt'
        END AS model_family,
        CASE
            WHEN model_id LIKE 'claude-%' THEN 'Claude Code'
            WHEN model_id LIKE 'gpt-%' THEN 'Codex CLI'
        END AS client,
    FROM all_models
    WHERE model_id IS NOT NULL
)

SELECT
    model_id,
    provider,
    model_family,
    client,
FROM classified_models
