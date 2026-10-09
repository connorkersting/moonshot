WITH source_spawns AS (
    SELECT
        spawn_id,
        parent_agent_id,
        parent_message_id,
        ts_utc,
        ts_local,
        session_part,
        description,
        agent_role,
        subagent_type,
        requested_model,
        run_in_background,
        linked_subagent_id,
    FROM {{ source('moonshot_raw', 'agent_spawns') }}
),

renamed_spawns AS (
    SELECT
        spawn_id,
        parent_agent_id,
        parent_message_id,
        CAST(REPLACE(ts_utc, 'Z', '') AS TIMESTAMP) AS spawned_at_utc,
        CAST(LEFT(ts_local, 19) AS TIMESTAMP) AS spawned_at_local,
        CAST(session_part AS INTEGER) AS session_part,
        description AS spawn_description,
        agent_role,
        -- "general-purpose (default)" and "general-purpose" are the same agent type;
        -- the suffix only records that the caller left the parameter out.
        REPLACE(subagent_type, ' (default)', '') AS subagent_type,
        subagent_type LIKE '% (default)' AS is_default_subagent_type,
        requested_model AS requested_model_alias,
        run_in_background,
        linked_subagent_id,
    FROM source_spawns
)

SELECT
    spawn_id,
    parent_agent_id,
    parent_message_id,
    spawned_at_utc,
    spawned_at_local,
    session_part,
    spawn_description,
    agent_role,
    subagent_type,
    is_default_subagent_type,
    requested_model_alias,
    run_in_background,
    linked_subagent_id,
FROM renamed_spawns
