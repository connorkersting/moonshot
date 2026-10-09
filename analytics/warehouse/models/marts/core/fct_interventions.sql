WITH interventions AS (
    SELECT
        intervention_id,
        intervened_at_utc,
        intervened_at_local,
        session_part,
        intervention_kind,
        intervention_label,
        intervention_source,
        message_chars,
    FROM {{ ref('stg_moonshot__interventions') }}
),

session_parts AS (
    SELECT
        session_part,
        wall_start_at_utc,
    FROM {{ ref('dim_session_part') }}
),

timed_interventions AS (
    SELECT
        i.intervention_id,
        i.session_part,
        i.intervened_at_utc,
        i.intervened_at_local,
        DATE_DIFF('second', sp.wall_start_at_utc, i.intervened_at_utc) / 60.0 AS minutes_into_session_part,
        i.intervention_kind,
        i.intervention_source,
        i.intervention_label,
        i.message_chars,
    FROM interventions AS i
    LEFT JOIN session_parts AS sp
        ON i.session_part = sp.session_part
)

SELECT
    intervention_id,
    session_part,
    intervened_at_utc,
    intervened_at_local,
    minutes_into_session_part,
    intervention_kind,
    intervention_source,
    intervention_label,
    message_chars,
FROM timed_interventions
