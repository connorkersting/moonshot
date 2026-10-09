WITH source_interventions AS (
    SELECT
        intervention_id,
        ts_utc,
        ts_local,
        session_part,
        kind,
        label,
        source,
        n_chars,
    FROM {{ source('moonshot_raw', 'interventions') }}
),

renamed_interventions AS (
    SELECT
        intervention_id,
        CAST(REPLACE(ts_utc, 'Z', '') AS TIMESTAMP) AS intervened_at_utc,
        CAST(LEFT(ts_local, 19) AS TIMESTAMP) AS intervened_at_local,
        CAST(session_part AS INTEGER) AS session_part,
        kind AS intervention_kind,
        label AS intervention_label,
        source AS intervention_source,
        n_chars AS message_chars,
    FROM source_interventions
)

SELECT
    intervention_id,
    intervened_at_utc,
    intervened_at_local,
    session_part,
    intervention_kind,
    intervention_label,
    intervention_source,
    message_chars,
FROM renamed_interventions
