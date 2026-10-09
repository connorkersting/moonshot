-- Grain: one row per version x critic x headline score category (the overall score for
-- the rubric critics; shareability, AI-slop perception and watch-to-end for the crowd).
-- This is the table behind the plateau chart. It adds the promotion mark, the
-- director's-note mark, the loop hours and project tokens spent up to the version's
-- export, and how the score moved from the critic's previous scored version.
--
-- loop_hours_at_export counts ledger segments only (the agent's own record of loop time).
-- Tokens are every Claude request in the project up to the export (all agents, input +
-- cache + known output), so they include work that never touched the trailer.

WITH headline_scores AS (
    SELECT
        s.version_id,
        s.critic_id,
        s.score_category,
        s.score,
    FROM {{ ref('fct_critic_scores') }} AS s
    INNER JOIN {{ ref('dim_score_category') }} AS c
        ON s.score_category = c.score_category
    WHERE c.is_overall OR c.category_group = 'crowd'
),

versions AS (
    SELECT
        version_id,
        version_number,
        outcome,
        is_promoted,
        is_final,
        has_director_input,
        director_input,
        exported_at_local,
        loop_hours_at_export,
        project_tokens_known_at_export,
    FROM {{ ref('dim_version') }}
),

critics AS (
    SELECT
        critic_id,
        discriminates_between_versions,
    FROM {{ ref('dim_critic') }}
),

plateau AS (
    SELECT
        h.version_id,
        v.version_number,
        h.critic_id,
        h.score_category,
        h.score,
        v.outcome,
        v.is_promoted,
        v.is_final,
        v.has_director_input,
        v.director_input,
        v.exported_at_local,
        v.loop_hours_at_export,
        v.project_tokens_known_at_export,
        c.discriminates_between_versions AS critic_discriminates,
        LAG(h.score) OVER (
            PARTITION BY h.critic_id, h.score_category
            ORDER BY v.version_number
        ) AS previous_scored_score,
        MAX(h.score) OVER (
            PARTITION BY h.critic_id, h.score_category
            ORDER BY v.version_number
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS best_score_so_far,
    FROM headline_scores AS h
    INNER JOIN versions AS v
        ON h.version_id = v.version_id
    INNER JOIN critics AS c
        ON h.critic_id = c.critic_id
)

SELECT
    version_id || '|' || critic_id || '|' || score_category AS plateau_point_id,
    version_id,
    version_number,
    critic_id,
    score_category,
    score,
    previous_scored_score,
    score - previous_scored_score AS score_change_vs_previous_scored,
    best_score_so_far,
    outcome,
    is_promoted,
    is_final,
    has_director_input,
    director_input,
    exported_at_local,
    loop_hours_at_export,
    project_tokens_known_at_export,
    critic_discriminates,
FROM plateau
