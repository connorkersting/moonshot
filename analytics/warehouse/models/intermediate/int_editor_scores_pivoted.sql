-- Reshapes the long editor-critic scores to one row per version, one column per
-- category. Written as explicit FILTER aggregates rather than PIVOT so the output
-- columns are fixed and a new upstream category cannot add a column silently
-- (the accepted_values test on fct_critic_scores.score_category catches it).

WITH critic_scores AS (
    SELECT
        evaluation_id,
        version_id,
        critic_model_id,
        score_category,
        score,
    FROM {{ ref('stg_moonshot__critic_scores') }}
    WHERE critic_id = 'fable_editor'
),

scores_by_version AS (
    SELECT
        version_id,
        COUNT(DISTINCT evaluation_id) AS n_editor_evaluations,
        MIN(evaluation_id) AS editor_evaluation_id,
        MIN(critic_model_id) AS editor_model_id,
        MAX(score) FILTER (WHERE score_category = 'hook') AS hook_score,
        MAX(score) FILTER (WHERE score_category = 'pacing') AS pacing_score,
        MAX(score) FILTER (WHERE score_category = 'variety') AS variety_score,
        MAX(score) FILTER (WHERE score_category = 'motion') AS motion_score,
        MAX(score) FILTER (WHERE score_category = 'type') AS type_score,
        MAX(score) FILTER (WHERE score_category = 'color') AS color_score,
        MAX(score) FILTER (WHERE score_category = 'sound') AS sound_score,
        MAX(score) FILTER (WHERE score_category = 'captions') AS captions_score,
        MAX(score) FILTER (WHERE score_category = 'story') AS story_score,
        MAX(score) FILTER (WHERE score_category = 'overall') AS overall_score,
        AVG(score) FILTER (WHERE score_category <> 'overall') AS mean_category_score,
    FROM critic_scores
    GROUP BY version_id
)

SELECT
    version_id,
    n_editor_evaluations,
    editor_evaluation_id,
    editor_model_id,
    hook_score,
    pacing_score,
    variety_score,
    motion_score,
    type_score,
    color_score,
    sound_score,
    captions_score,
    story_score,
    overall_score,
    mean_category_score,
FROM scores_by_version
