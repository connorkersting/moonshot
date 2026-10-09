-- Grain: one row per critic. How much each critic's scores move between versions, and how
-- well they track the Fable editor (the only critic used for promotion decisions).
--
--   n_versions_sharing_a_vector: versions whose full score vector (every category the
--     critic scored) is identical to another version's. A critic that gives visibly
--     different cuts the same ten numbers is not measuring them.
--   overall_range / overall_stddev: spread of the headline score across versions (the overall
--     score; shareability for the crowd).
--   corr_with_fable_overall: Pearson correlation of the headline score with the Fable
--     editor's, over the versions both scored. NULL below three shared versions, where a
--     correlation says nothing.
--   observed_identical_vectors is true when n_versions_sharing_a_vector > 0.
--   categories_per_version: the most categories the critic scored for one version. A critic that
--     gives one number per version (the Fable re-score, 'overall' only) will repeat a half-point
--     score for two versions without that meaning anything, so the identical-vector test below
--     only applies from two categories up.

WITH scores AS (
    SELECT
        s.version_id,
        s.critic_id,
        s.score_category,
        s.score,
        c.category_order,
        c.is_overall,
    FROM {{ ref('fct_critic_scores') }} AS s
    INNER JOIN {{ ref('dim_score_category') }} AS c
        ON s.score_category = c.score_category
),

vectors AS (
    SELECT
        critic_id,
        version_id,
        STRING_AGG(score_category || '=' || CAST(score AS VARCHAR), ';' ORDER BY category_order) AS score_vector,
        MAX(score) FILTER (WHERE is_overall OR score_category = 'shareability') AS headline_score,
        COUNT(*) AS n_categories,
    FROM scores
    GROUP BY
        critic_id,
        version_id
),

critic_spread AS (
    SELECT
        critic_id,
        COUNT(*) AS n_versions_scored,
        COUNT(DISTINCT score_vector) AS n_distinct_vectors,
        MAX(n_categories) AS categories_per_version,
        MIN(headline_score) AS overall_min,
        MAX(headline_score) AS overall_max,
        STDDEV_SAMP(headline_score) AS overall_stddev,
    FROM vectors
    GROUP BY critic_id
),

fable AS (
    SELECT
        version_id,
        headline_score AS fable_overall,
    FROM vectors
    WHERE critic_id = 'fable_editor'
),

agreement AS (
    SELECT
        v.critic_id,
        COUNT(*) AS n_versions_shared_with_fable,
        CORR(v.headline_score, f.fable_overall) AS corr_with_fable_overall,
    FROM vectors AS v
    INNER JOIN fable AS f
        ON v.version_id = f.version_id
    WHERE v.headline_score IS NOT NULL
    GROUP BY v.critic_id
),

critics AS (
    SELECT
        critic_id,
        critic_label,
        critic_kind,
        discriminates_between_versions,
    FROM {{ ref('dim_critic') }}
)

SELECT
    c.critic_id,
    c.critic_label,
    c.critic_kind,
    c.discriminates_between_versions AS flagged_discriminating,
    sp.n_versions_scored,
    sp.n_distinct_vectors,
    sp.categories_per_version,
    sp.n_versions_scored - sp.n_distinct_vectors AS n_versions_sharing_a_vector,
    sp.n_versions_scored > sp.n_distinct_vectors AS observed_identical_vectors,
    sp.overall_min,
    sp.overall_max,
    sp.overall_max - sp.overall_min AS overall_range,
    sp.overall_stddev,
    a.n_versions_shared_with_fable,
    CASE WHEN a.n_versions_shared_with_fable >= 3 THEN ROUND(a.corr_with_fable_overall, 3) END AS corr_with_fable_overall,
FROM critics AS c
INNER JOIN critic_spread AS sp
    ON c.critic_id = sp.critic_id
LEFT JOIN agreement AS a
    ON c.critic_id = a.critic_id
