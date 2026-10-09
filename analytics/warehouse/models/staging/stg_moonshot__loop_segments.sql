WITH source_loop_segments AS (
    SELECT
        segment_id,
        start_local,
        end_local,
        start_utc,
        end_utc,
        end_reason,
    FROM {{ source('moonshot_raw', 'loop_segments') }}
),

renamed_loop_segments AS (
    SELECT
        CAST(segment_id AS INTEGER) AS loop_segment_id,
        CAST(start_local AS TIMESTAMP) AS segment_start_at_local,
        CAST(end_local AS TIMESTAMP) AS segment_end_at_local,
        CAST(REPLACE(start_utc, 'Z', '') AS TIMESTAMP) AS segment_start_at_utc,
        CAST(REPLACE(end_utc, 'Z', '') AS TIMESTAMP) AS segment_end_at_utc,
        end_reason AS segment_end_reason,
    FROM source_loop_segments
)

SELECT
    loop_segment_id,
    segment_start_at_local,
    segment_end_at_local,
    segment_start_at_utc,
    segment_end_at_utc,
    segment_end_reason,
FROM renamed_loop_segments
