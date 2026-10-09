-- The baseline block's final scores must equal the same review's own scores in
-- fct_critic_scores (the review scored the final version once, not twice), and each delta
-- must be final minus baseline. One row per mismatch.

WITH baseline AS (
    SELECT
        review_version_id,
        score_category,
        baseline_score,
        final_score,
        score_delta,
    FROM {{ ref('fct_baseline_to_final') }}
),

review_scores AS (
    SELECT
        version_id,
        score_category,
        score,
    FROM {{ ref('fct_critic_scores') }}
    WHERE critic_id = 'fable_editor'
),

compared AS (
    SELECT
        b.review_version_id,
        b.score_category,
        b.final_score,
        r.score AS review_score,
        b.score_delta,
        b.final_score - b.baseline_score AS expected_delta,
    FROM baseline AS b
    LEFT JOIN review_scores AS r
        ON b.review_version_id = r.version_id
        AND b.score_category = r.score_category
)

SELECT
    review_version_id,
    score_category,
    final_score,
    review_score,
    score_delta,
    expected_delta,
FROM compared
WHERE review_score IS DISTINCT FROM final_score
    OR ABS(score_delta - expected_delta) > 0.001
