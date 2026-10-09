WITH source_director_picks AS (
    SELECT
        pick_id,
        decided_at_local,
        decided_at_utc,
        subject,
        key_file,
        clip_key,
        side_picked,
        option_picked,
        mapped_through_key,
        adopted,
        version_effect,
        source_ref,
    FROM {{ source('moonshot_raw', 'director_picks') }}
),

renamed_director_picks AS (
    SELECT
        pick_id AS director_pick_id,
        CAST(decided_at_local AS TIMESTAMP) AS decided_at_local,
        CAST(REPLACE(decided_at_utc, 'Z', '') AS TIMESTAMP) AS decided_at_utc,
        subject AS pick_subject,
        NULLIF(key_file, '') AS key_file_name,
        NULLIF(clip_key, '') AS clip_key,
        side_picked,
        option_picked,
        mapped_through_key AS is_mapped_through_key,
        adopted AS is_adopted,
        version_effect AS version_effect_id,
        source_ref,
    FROM source_director_picks
)

SELECT
    director_pick_id,
    decided_at_local,
    decided_at_utc,
    pick_subject,
    key_file_name,
    clip_key,
    side_picked,
    option_picked,
    is_mapped_through_key,
    is_adopted,
    version_effect_id,
    source_ref,
FROM renamed_director_picks
