-- Grain: one row per trailer version.
-- Attributes, the promote/keep decision with its reason, the director's note that shaped
-- the version (if any), each critic's headline score and the blind A/B result against the
-- version it was compared with, and the loop hours and project tokens spent by its export.
-- Critic columns are NULL where that critic did not score
-- the version.

WITH versions AS (
    SELECT
        version_id,
        version_number,
        src_tagged_at_local,
        final_tagged_at_local,
        exported_at_utc,
        exported_at_local,
        progress_logged_at_local,
        is_best_final,
        duration_s,
        integrated_lufs,
        loudness_range_lu,
        true_peak_dbtp,
        tqc_verdict,
        tqc_black_runs,
        tqc_freeze_runs,
        tqc_click_candidates,
        tqc_flag_count,
        has_qc,
        has_aqc,
        has_tqc,
    FROM {{ ref('stg_moonshot__versions') }}
),

version_outcomes AS (
    SELECT
        version_id,
        outcome,
        decision_basis,
        decided_at_local,
        decision_reason,
        director_input,
    FROM {{ ref('version_outcomes') }}
),

critic_scores AS (
    SELECT
        version_id,
        fable_editor_overall,
        fable_editor_rescored_overall,
        codex_critic_overall,
        gemini_flash_overall,
        gemini_pro_web_overall,
        twelvelabs_overall,
        crowd_shareability,
        crowd_ai_slop_perception,
        crowd_would_watch_to_end,
        n_critics_scoring,
    FROM {{ ref('int_critic_scores_by_version') }}
),

effort AS (
    SELECT
        version_id,
        loop_hours_at_export,
        project_tokens_known_at_export,
    FROM {{ ref('int_version_effort_at_export') }}
),

ab_results AS (
    SELECT
        newer_version_id,
        older_version_id,
        newer_section_wins,
        newer_section_losses,
        section_ties,
        newer_ab_result,
    FROM {{ ref('int_ab_comparison_results') }}
),

versions_with_outcomes AS (
    SELECT
        v.version_id,
        v.version_number,
        LAG(v.version_id) OVER (ORDER BY v.version_number) AS previous_version_id,
        v.src_tagged_at_local,
        v.final_tagged_at_local,
        v.exported_at_utc,
        v.exported_at_local,
        v.progress_logged_at_local,
        v.duration_s,
        v.integrated_lufs,
        v.loudness_range_lu,
        v.true_peak_dbtp,
        v.tqc_verdict,
        v.tqc_black_runs,
        v.tqc_freeze_runs,
        v.tqc_click_candidates,
        v.tqc_flag_count,
        v.has_qc,
        v.has_aqc,
        v.has_tqc,
        v.is_best_final,
        -- A version with no recorded decision is in progress only while it has not
        -- been exported. Exported and undecided stays NULL so not_null fails.
        COALESCE(
            o.outcome,
            CASE WHEN v.exported_at_utc IS NULL THEN 'in_progress' END
        ) AS outcome,
        o.decision_basis,
        o.decided_at_local,
        o.decision_reason,
        o.director_input,
        c.fable_editor_overall,
        c.fable_editor_rescored_overall,
        c.codex_critic_overall,
        c.gemini_flash_overall,
        c.gemini_pro_web_overall,
        c.twelvelabs_overall,
        c.crowd_shareability,
        c.crowd_ai_slop_perception,
        c.crowd_would_watch_to_end,
        COALESCE(c.n_critics_scoring, 0) AS n_critics_scoring,
        ab.older_version_id AS ab_compared_with_version_id,
        ab.newer_section_wins AS ab_section_wins,
        ab.newer_section_losses AS ab_section_losses,
        ab.section_ties AS ab_section_ties,
        ab.newer_ab_result AS ab_result,
        e.loop_hours_at_export,
        e.project_tokens_known_at_export,
    FROM versions AS v
    LEFT JOIN version_outcomes AS o
        ON v.version_id = o.version_id
    LEFT JOIN critic_scores AS c
        ON v.version_id = c.version_id
    LEFT JOIN ab_results AS ab
        ON v.version_id = ab.newer_version_id
    LEFT JOIN effort AS e
        ON v.version_id = e.version_id
)

SELECT
    version_id,
    version_number,
    previous_version_id,
    outcome,
    outcome IN ('kept', 'final') AS is_promoted,
    outcome = 'final' AS is_final,
    decision_basis,
    decided_at_local,
    decision_reason,
    director_input,
    director_input IS NOT NULL AS has_director_input,
    is_best_final,
    fable_editor_overall,
    fable_editor_rescored_overall,
    codex_critic_overall,
    gemini_flash_overall,
    gemini_pro_web_overall,
    twelvelabs_overall,
    crowd_shareability,
    crowd_ai_slop_perception,
    crowd_would_watch_to_end,
    n_critics_scoring,
    ab_compared_with_version_id,
    ab_section_wins,
    ab_section_losses,
    ab_section_ties,
    ab_result,
    loop_hours_at_export,
    project_tokens_known_at_export,
    src_tagged_at_local,
    final_tagged_at_local,
    exported_at_utc,
    exported_at_local,
    progress_logged_at_local,
    duration_s,
    integrated_lufs,
    loudness_range_lu,
    true_peak_dbtp,
    tqc_verdict,
    tqc_black_runs,
    tqc_freeze_runs,
    tqc_click_candidates,
    tqc_flag_count,
    has_qc,
    has_aqc,
    has_tqc,
FROM versions_with_outcomes
