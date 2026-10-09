-- One row per critic that scored versions. The reliability flag
-- (discriminates_between_versions) is hand-recorded in the critics seed with its
-- evidence; mart_critic_reliability measures the same thing from the scores so the
-- two can be compared.

WITH critics AS (
    SELECT
        critic_id,
        critic_label,
        critic_kind,
        provider,
        can_hear_audio,
        used_for_promotion,
        discriminates_between_versions,
        reliability_note,
    FROM {{ ref('critics') }}
),

coverage AS (
    SELECT
        critic_id,
        COUNT(DISTINCT version_id) AS n_versions_scored,
        MIN(CAST(SUBSTRING(version_id, 2) AS INTEGER)) AS first_version_number,
        MAX(CAST(SUBSTRING(version_id, 2) AS INTEGER)) AS last_version_number,
    FROM {{ ref('stg_moonshot__critic_scores') }}
    GROUP BY critic_id
)

SELECT
    c.critic_id,
    c.critic_label,
    c.critic_kind,
    c.provider,
    c.can_hear_audio,
    c.used_for_promotion,
    c.discriminates_between_versions,
    c.reliability_note,
    COALESCE(v.n_versions_scored, 0) AS n_versions_scored,
    v.first_version_number,
    v.last_version_number,
FROM critics AS c
LEFT JOIN coverage AS v
    ON c.critic_id = v.critic_id
