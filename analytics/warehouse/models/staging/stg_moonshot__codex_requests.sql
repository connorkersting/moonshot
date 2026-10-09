WITH source_codex_requests AS (
    SELECT
        codex_session_id,
        request_seq,
        ts_utc,
        ts_local,
        model,
        workdir,
        attribution,
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        primary_used_pct,
        secondary_used_pct,
    FROM {{ source('moonshot_raw', 'codex_requests') }}
),

renamed_codex_requests AS (
    SELECT
        codex_session_id || '-' || LPAD(CAST(request_seq AS VARCHAR), 4, '0') AS codex_request_id,
        codex_session_id,
        request_seq,
        CAST(REPLACE(ts_utc, 'Z', '') AS TIMESTAMP) AS requested_at_utc,
        CAST(LEFT(ts_local, 19) AS TIMESTAMP) AS requested_at_local,
        model AS model_id,
        workdir AS workdir_name,
        attribution,
        -- OpenAI convention: input_tokens already includes the cached part.
        input_tokens,
        cached_input_tokens,
        output_tokens,
        reasoning_output_tokens,
        primary_used_pct AS plan_5h_used_pct,
        secondary_used_pct AS plan_weekly_used_pct,
    FROM source_codex_requests
)

SELECT
    codex_request_id,
    codex_session_id,
    request_seq,
    requested_at_utc,
    requested_at_local,
    model_id,
    workdir_name,
    attribution,
    input_tokens,
    cached_input_tokens,
    output_tokens,
    reasoning_output_tokens,
    plan_5h_used_pct,
    plan_weekly_used_pct,
FROM renamed_codex_requests
