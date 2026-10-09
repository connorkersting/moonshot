-- One row per version with each critic's headline score in its own column: the overall
-- score for the rubric critics, the three persona scores for the crowd. Written as
-- explicit FILTER aggregates so a new critic cannot add a column silently (the
-- relationships test from fct_critic_scores to dim_critic catches a new critic id).
-- A critic that did not score a version leaves NULL, never 0.

WITH critic_scores AS (
    SELECT
        version_id,
        critic_id,
        score_category,
        score,
    FROM {{ ref('stg_moonshot__critic_scores') }}
),

scores_by_version AS (
    SELECT
        version_id,
        MAX(score) FILTER (WHERE critic_id = 'fable_editor' AND score_category = 'overall') AS fable_editor_overall,
        MAX(score) FILTER (WHERE critic_id = 'fable_editor_rescored' AND score_category = 'overall') AS fable_editor_rescored_overall,
        MAX(score) FILTER (WHERE critic_id = 'codex_critic' AND score_category = 'overall') AS codex_critic_overall,
        MAX(score) FILTER (WHERE critic_id = 'gemini_flash' AND score_category = 'overall') AS gemini_flash_overall,
        MAX(score) FILTER (WHERE critic_id = 'gemini_pro_web' AND score_category = 'overall') AS gemini_pro_web_overall,
        MAX(score) FILTER (WHERE critic_id = 'twelvelabs' AND score_category = 'overall') AS twelvelabs_overall,
        MAX(score) FILTER (WHERE critic_id = 'crowd_ftv' AND score_category = 'shareability') AS crowd_shareability,
        MAX(score) FILTER (WHERE critic_id = 'crowd_ftv' AND score_category = 'ai_slop_perception') AS crowd_ai_slop_perception,
        MAX(score) FILTER (WHERE critic_id = 'crowd_ftv' AND score_category = 'would_watch_to_end') AS crowd_would_watch_to_end,
        COUNT(DISTINCT critic_id) FILTER (WHERE critic_id <> 'fable_editor_rescored') AS n_critics_scoring,
    FROM critic_scores
    GROUP BY version_id
)

SELECT
    version_id,
    fable_editor_overall,
    fable_editor_rescored_overall,
    codex_critic_overall,
    gemini_flash_overall,
    gemini_pro_web_overall,
    twelvelabs_overall,
    crowd_shareability,
    crowd_ai_slop_perception,
    crowd_would_watch_to_end,
    n_critics_scoring,
FROM scores_by_version
