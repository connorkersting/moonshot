-- Grain: one row per version x critic x score category.
-- A critic that did not score a version has no rows for it (never a zero).

WITH critic_scores AS (
    SELECT
        critic_score_id,
        version_id,
        critic_id,
        score_category,
        score,
        critic_model_id,
        evaluation_id,
        source_kind,
        progress_md_score,
        is_progress_md_flagged,
        score_note,
    FROM {{ ref('stg_moonshot__critic_scores') }}
),

compared_scores AS (
    SELECT
        critic_score_id,
        version_id,
        critic_id,
        score_category,
        score,
        critic_model_id,
        evaluation_id,
        source_kind,
        progress_md_score,
        is_progress_md_flagged,
        progress_md_score IS NOT NULL AS is_in_progress_md,
        progress_md_score IS NOT NULL AND progress_md_score <> score AS differs_from_progress_md,
        score_note,
    FROM critic_scores
)

SELECT
    critic_score_id,
    version_id,
    critic_id,
    score_category,
    score,
    critic_model_id,
    evaluation_id,
    source_kind,
    progress_md_score,
    is_progress_md_flagged,
    is_in_progress_md,
    differs_from_progress_md,
    score_note,
FROM compared_scores
