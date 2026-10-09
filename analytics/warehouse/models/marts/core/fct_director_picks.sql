WITH director_picks AS (
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
    FROM {{ ref('stg_moonshot__director_picks') }}
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
FROM director_picks
