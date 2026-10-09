WITH baseline_to_final AS (
    SELECT
        baseline_comparison_id,
        review_version_id,
        baseline_version_id,
        score_category,
        baseline_score,
        final_score,
        score_delta,
    FROM {{ ref('stg_moonshot__baseline_to_final') }}
)

SELECT
    baseline_comparison_id,
    review_version_id,
    baseline_version_id,
    score_category,
    baseline_score,
    final_score,
    score_delta,
FROM baseline_to_final
