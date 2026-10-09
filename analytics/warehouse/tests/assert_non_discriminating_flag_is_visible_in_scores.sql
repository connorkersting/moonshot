{{ config(severity = 'warn') }}

-- A critic recorded as NOT discriminating (critics seed) with at least two scored versions
-- should show it in the stored scores: two versions with an identical score vector.
-- TwelveLabs does (v19 = v21). Gemini Flash does not: the run that matched is the first v18
-- run in the log, and a retry overwrote that file, so the flag rests on the log, not on the
-- stored data. That is a data-quality finding, so this test warns instead of failing.

SELECT
    critic_id,
    n_versions_scored,
    n_distinct_vectors,
    overall_range,
FROM {{ ref('mart_critic_reliability') }}
WHERE NOT flagged_discriminating
    AND n_versions_scored >= 2
    AND NOT observed_identical_vectors
