-- Every critic scores a full set per version: ten categories for the rubric critics, two
-- or three for the crowd (watch-to-end exists only from v18), one for a Fable re-score.
-- A partial set would make a wide column NULL for the wrong reason.

WITH counts AS (
    SELECT
        s.version_id,
        s.critic_id,
        c.critic_kind,
        COUNT(*) AS n_categories,
    FROM {{ ref('fct_critic_scores') }} AS s
    INNER JOIN {{ ref('dim_critic') }} AS c
        ON s.critic_id = c.critic_id
    GROUP BY
        s.version_id,
        s.critic_id,
        c.critic_kind
)

SELECT
    version_id,
    critic_id,
    n_categories,
FROM counts
WHERE (critic_id = 'fable_editor_rescored' AND n_categories <> 1)
    OR (critic_kind = 'llm_persona' AND n_categories NOT IN (2, 3))
    OR (critic_id <> 'fable_editor_rescored' AND critic_kind <> 'llm_persona' AND n_categories <> 10)
