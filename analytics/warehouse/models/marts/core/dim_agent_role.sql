WITH agent_roles AS (
    SELECT
        agent_role,
        role_group,
        role_description,
    FROM {{ ref('agent_roles') }}
),

subagent_runs AS (
    SELECT
        agent_role,
        subagent_id,
        requested_model_alias,
    FROM {{ ref('stg_moonshot__subagents') }}
),

runs_by_role AS (
    SELECT
        agent_role,
        COUNT(*) AS n_subagent_runs,
        MODE(requested_model_alias) AS usual_requested_model_alias,
    FROM subagent_runs
    GROUP BY agent_role
),

roles_with_runs AS (
    SELECT
        r.agent_role,
        r.role_group,
        r.role_description,
        r.agent_role = 'main' AS is_main_agent,
        COALESCE(rr.n_subagent_runs, 0) AS n_subagent_runs,
        rr.usual_requested_model_alias,
    FROM agent_roles AS r
    LEFT JOIN runs_by_role AS rr
        ON r.agent_role = rr.agent_role
)

SELECT
    agent_role,
    role_group,
    role_description,
    is_main_agent,
    n_subagent_runs,
    usual_requested_model_alias,
FROM roles_with_runs
