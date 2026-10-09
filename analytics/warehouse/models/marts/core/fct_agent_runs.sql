-- One row per subagent run. Request-level tokens are rolled up to agent grain in
-- int_llm_requests_by_agent first, so the joins below are all one-to-one.

WITH subagents AS (
    SELECT
        subagent_id,
        spawn_id,
        spawn_description,
        agent_role,
        requested_model_alias,
        actual_model_ids,
        session_part,
        duration_s,
    FROM {{ ref('stg_moonshot__subagents') }}
),

agent_spawns AS (
    SELECT
        spawn_id,
        spawned_at_utc,
        spawned_at_local,
        run_in_background,
    FROM {{ ref('stg_moonshot__agent_spawns') }}
),

request_totals AS (
    SELECT
        agent_id,
        n_models,
        model_id,
        first_request_at_utc,
        last_request_at_utc,
        request_count,
        requests_usage_final,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens_final,
        output_tokens_unfinalised_lower_bound,
        n_tool_calls,
    FROM {{ ref('int_llm_requests_by_agent') }}
),

agent_runs AS (
    SELECT
        s.subagent_id,
        s.spawn_id,
        s.agent_role,
        s.requested_model_alias,
        COALESCE(t.model_id, s.actual_model_ids) AS model_id,
        t.n_models,
        s.session_part,
        sp.run_in_background,
        sp.spawned_at_utc,
        sp.spawned_at_local,
        t.first_request_at_utc,
        t.last_request_at_utc AS ended_at_utc,
        DATE_DIFF('millisecond', sp.spawned_at_utc, t.first_request_at_utc) / 1000.0 AS spawn_to_first_request_s,
        s.duration_s AS active_duration_s,
        DATE_DIFF('millisecond', sp.spawned_at_utc, t.last_request_at_utc) / 1000.0 AS spawn_to_end_s,
        COALESCE(t.request_count, 0) AS request_count,
        COALESCE(t.requests_usage_final, 0) AS requests_usage_final,
        COALESCE(t.input_tokens, 0) AS input_tokens,
        COALESCE(t.cache_creation_tokens, 0) AS cache_creation_tokens,
        COALESCE(t.cache_read_tokens, 0) AS cache_read_tokens,
        t.output_tokens_final,
        COALESCE(t.output_tokens_unfinalised_lower_bound, 0) AS output_tokens_unfinalised_lower_bound,
        COALESCE(t.n_tool_calls, 0) AS n_tool_calls,
        s.spawn_description,
    FROM subagents AS s
    LEFT JOIN agent_spawns AS sp
        ON s.spawn_id = sp.spawn_id
    LEFT JOIN request_totals AS t
        ON s.subagent_id = t.agent_id
),

agent_run_totals AS (
    SELECT
        subagent_id,
        spawn_id,
        agent_role,
        requested_model_alias,
        model_id,
        n_models,
        session_part,
        run_in_background,
        spawned_at_utc,
        spawned_at_local,
        first_request_at_utc,
        ended_at_utc,
        spawn_to_first_request_s,
        active_duration_s,
        spawn_to_end_s,
        request_count,
        requests_usage_final,
        input_tokens,
        cache_creation_tokens,
        cache_read_tokens,
        output_tokens_final,
        output_tokens_unfinalised_lower_bound,
        input_tokens + cache_creation_tokens + cache_read_tokens + COALESCE(output_tokens_final, 0) AS total_tokens_known,
        n_tool_calls,
        spawn_description,
    FROM agent_runs
)

SELECT
    subagent_id,
    spawn_id,
    agent_role,
    requested_model_alias,
    model_id,
    n_models,
    session_part,
    run_in_background,
    spawned_at_utc,
    spawned_at_local,
    first_request_at_utc,
    ended_at_utc,
    spawn_to_first_request_s,
    active_duration_s,
    spawn_to_end_s,
    request_count,
    requests_usage_final,
    input_tokens,
    cache_creation_tokens,
    cache_read_tokens,
    output_tokens_final,
    output_tokens_unfinalised_lower_bound,
    total_tokens_known,
    n_tool_calls,
    spawn_description,
FROM agent_run_totals
