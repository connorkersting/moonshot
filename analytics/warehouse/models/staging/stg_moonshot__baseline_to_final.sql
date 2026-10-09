WITH source_baseline_to_final AS (
    SELECT
        review_version,
        baseline_version,
        category,
        baseline_score,
        final_score,
        delta,
    FROM {{ source('moonshot_raw', 'baseline_to_final') }}
),

renamed_baseline_to_final AS (
    SELECT
        'v' || review_version || '-v' || baseline_version || '-' || category AS baseline_comparison_id,
        'v' || review_version AS review_version_id,
        'v' || baseline_version AS baseline_version_id,
        category AS score_category,
        baseline_score,
        final_score,
        delta AS score_delta,
    FROM source_baseline_to_final
)

SELECT
    baseline_comparison_id,
    review_version_id,
    baseline_version_id,
    score_category,
    baseline_score,
    final_score,
    score_delta,
FROM renamed_baseline_to_final
