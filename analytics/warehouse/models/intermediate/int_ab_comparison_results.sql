-- Tallies each blind A/B comparison from the newer version's side.

WITH ab_votes AS (
    SELECT
        evaluation_id,
        repeat_no,
        comparison_label,
        newer_version_id,
        older_version_id,
        newer_outcome,
        is_tie,
        is_marginal,
        confidence_rank,
        judge_model_id,
    FROM {{ ref('stg_moonshot__ab_votes') }}
),

comparison_tallies AS (
    SELECT
        evaluation_id,
        MIN(comparison_label) AS comparison_label,
        MIN(newer_version_id) AS newer_version_id,
        MIN(older_version_id) AS older_version_id,
        MIN(judge_model_id) AS judge_model_id,
        COUNT(DISTINCT repeat_no) AS n_repeats,
        COUNT(*) AS n_sections_judged,
        COUNT(*) FILTER (WHERE newer_outcome = 'win') AS newer_section_wins,
        COUNT(*) FILTER (WHERE newer_outcome = 'loss') AS newer_section_losses,
        COUNT(*) FILTER (WHERE is_tie) AS section_ties,
        COUNT(*) FILTER (WHERE is_marginal) AS marginal_picks,
        COUNT(*) FILTER (WHERE newer_outcome = 'win' AND confidence_rank >= 2.5) AS newer_confident_wins,
        COUNT(*) FILTER (WHERE newer_outcome = 'loss' AND confidence_rank >= 2.5) AS newer_confident_losses,
    FROM ab_votes
    GROUP BY evaluation_id
),

comparison_results AS (
    SELECT
        evaluation_id,
        comparison_label,
        newer_version_id,
        older_version_id,
        judge_model_id,
        n_repeats,
        n_sections_judged,
        newer_section_wins,
        newer_section_losses,
        section_ties,
        marginal_picks,
        newer_confident_wins,
        newer_confident_losses,
        CAST(section_ties AS DOUBLE) / n_sections_judged AS tie_rate,
        CASE
            WHEN newer_section_wins > newer_section_losses THEN 'win'
            WHEN newer_section_wins < newer_section_losses THEN 'loss'
            ELSE 'draw'
        END AS newer_ab_result,
    FROM comparison_tallies
)

SELECT
    evaluation_id,
    comparison_label,
    newer_version_id,
    older_version_id,
    judge_model_id,
    n_repeats,
    n_sections_judged,
    newer_section_wins,
    newer_section_losses,
    section_ties,
    marginal_picks,
    newer_confident_wins,
    newer_confident_losses,
    tie_rate,
    newer_ab_result,
FROM comparison_results
