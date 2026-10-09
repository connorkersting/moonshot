WITH source_events AS (
    SELECT
        ts_utc,
        ts_local,
        session_part,
        event,
        trigger,
        pre_tokens,
        post_tokens,
        duration_ms,
    FROM {{ source('moonshot_raw', 'session_events') }}
),

renamed_events AS (
    SELECT
        -- The raw table has no id; event + UTC timestamp is its declared key.
        event || '@' || ts_utc AS session_event_id,
        event AS event_type,
        CAST(REPLACE(ts_utc, 'Z', '') AS TIMESTAMP) AS event_at_utc,
        CAST(LEFT(ts_local, 19) AS TIMESTAMP) AS event_at_local,
        CAST(session_part AS INTEGER) AS session_part,
        trigger AS compaction_trigger,
        pre_tokens AS context_tokens_before,
        post_tokens AS context_tokens_after,
        duration_ms,
    FROM source_events
)

SELECT
    session_event_id,
    event_type,
    event_at_utc,
    event_at_local,
    session_part,
    compaction_trigger,
    context_tokens_before,
    context_tokens_after,
    duration_ms,
FROM renamed_events
