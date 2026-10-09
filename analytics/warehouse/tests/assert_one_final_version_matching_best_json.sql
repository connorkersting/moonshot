-- Exactly one version is FINAL, and it is the one BEST.json names (promote.py writes it;
-- is_best_final in versions.csv). The decision seed and the promotion record must not
-- disagree; when a later version becomes FINAL, both have to move together. PROGRESS.md's
-- own BEST: header line is not used: it was left at v17 while v21 was promoted.

WITH versions AS (
    SELECT
        version_id,
        is_final,
        is_best_final,
    FROM {{ ref('dim_version') }}
),

final_count AS (
    SELECT
        COUNT(*) FILTER (WHERE is_final) AS n_final_versions,
    FROM versions
),

disagreements AS (
    SELECT
        version_id,
        is_final,
        is_best_final,
        'decision seed and BEST.json disagree' AS problem,
    FROM versions
    WHERE is_final IS DISTINCT FROM is_best_final
),

count_problems AS (
    SELECT
        NULL AS version_id,
        NULL AS is_final,
        NULL AS is_best_final,
        'expected exactly one final version, found ' || n_final_versions AS problem,
    FROM final_count
    WHERE n_final_versions <> 1
),

all_problems AS (
    SELECT version_id, is_final, is_best_final, problem FROM disagreements
    UNION ALL
    SELECT version_id, is_final, is_best_final, problem FROM count_problems
)

SELECT
    version_id,
    is_final,
    is_best_final,
    problem,
FROM all_problems
