-- The per-critic columns on dim_version are a pivot of fct_critic_scores. Every headline
-- score on the dimension must equal the fact row it came from, and no fact row may be
-- missing from the dimension (the pivot lists critics explicitly).

WITH fact AS (
    SELECT
        version_id,
        critic_id,
        score_category,
        score,
    FROM {{ ref('fct_critic_scores') }}
    WHERE score_category IN ('overall', 'shareability', 'ai_slop_perception', 'would_watch_to_end')
),

dim AS (
    SELECT version_id, 'fable_editor' AS critic_id, 'overall' AS score_category, fable_editor_overall AS score FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'fable_editor_rescored', 'overall', fable_editor_rescored_overall FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'codex_critic', 'overall', codex_critic_overall FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'gemini_flash', 'overall', gemini_flash_overall FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'gemini_pro_web', 'overall', gemini_pro_web_overall FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'twelvelabs', 'overall', twelvelabs_overall FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'crowd_ftv', 'shareability', crowd_shareability FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'crowd_ftv', 'ai_slop_perception', crowd_ai_slop_perception FROM {{ ref('dim_version') }}
    UNION ALL
    SELECT version_id, 'crowd_ftv', 'would_watch_to_end', crowd_would_watch_to_end FROM {{ ref('dim_version') }}
),

dim_scored AS (
    SELECT
        version_id,
        critic_id,
        score_category,
        score,
    FROM dim
    WHERE score IS NOT NULL
)

SELECT
    COALESCE(f.version_id, d.version_id) AS version_id,
    COALESCE(f.critic_id, d.critic_id) AS critic_id,
    COALESCE(f.score_category, d.score_category) AS score_category,
    f.score AS fact_score,
    d.score AS dim_score,
FROM fact AS f
FULL OUTER JOIN dim_scored AS d
    ON f.version_id = d.version_id
    AND f.critic_id = d.critic_id
    AND f.score_category = d.score_category
WHERE f.score IS DISTINCT FROM d.score
