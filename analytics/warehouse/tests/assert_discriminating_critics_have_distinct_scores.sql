-- A critic recorded as discriminating (critics seed) must never give two different
-- versions the identical score vector. If it does, the flag is wrong: either the seed
-- is out of date or the critic has stopped measuring. Returns one row per offending critic.
-- Critics that give one number per version (categories_per_version = 1) are left out: two
-- versions sharing a half-point 'overall' is expected there.

SELECT
    critic_id,
    n_versions_scored,
    n_distinct_vectors,
    n_versions_sharing_a_vector,
    categories_per_version,
FROM {{ ref('mart_critic_reliability') }}
WHERE flagged_discriminating
    AND observed_identical_vectors
    AND categories_per_version > 1
