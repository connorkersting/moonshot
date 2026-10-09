WITH session_events AS (
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
    FROM {{ ref('stg_moonshot__session_events') }}
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
FROM session_events
