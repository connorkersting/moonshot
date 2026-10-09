WITH source_critic_scores AS (
    SELECT
        version,
        critic,
        category,
        score,
        critic_model,
        evaluation_id,
        source_kind,
        progress_md_score,
        progress_md_flagged,
        note,
    FROM {{ source('moonshot_raw', 'critic_scores') }}
),

renamed_critic_scores AS (
    SELECT
        'v' || version || '-' || critic || '-' || category AS critic_score_id,
        'v' || version AS version_id,
        critic AS critic_id,
        category AS score_category,
        score,
        critic_model AS critic_model_id,
        evaluation_id,
        source_kind,
        progress_md_score,
        progress_md_flagged AS is_progress_md_flagged,
        NULLIF(note, '') AS score_note,
    FROM source_critic_scores
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
    score_note,
FROM renamed_critic_scores
