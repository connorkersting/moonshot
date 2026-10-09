-- One row per version: the editor's scores, the blind A/B result against the
-- version it was compared with (always the BEST at the time, so v7 was judged
-- against v5 after v6 was reverted), loudness and dialogue clarity, and the keep
-- decision. ab_agrees_with_decision shows where the agent overrode the A/B tally.

WITH versions AS (
    SELECT
        version_id,
        version_number,
        outcome,
        is_promoted,
        is_final,
        decision_basis,
        exported_at_local,
        duration_s,
        integrated_lufs,
        loudness_range_lu,
        true_peak_dbtp,
    FROM {{ ref('dim_version') }}
),

editor_scores AS (
    SELECT
        version_id,
        editor_evaluation_id,
        hook_score,
        pacing_score,
        variety_score,
        motion_score,
        type_score,
        color_score,
        sound_score,
        captions_score,
        story_score,
        overall_score,
        mean_category_score,
    FROM {{ ref('int_editor_scores_pivoted') }}
),

ab_results AS (
    SELECT
        newer_version_id,
        older_version_id,
        newer_section_wins,
        newer_section_losses,
        section_ties,
        tie_rate,
        newer_ab_result,
    FROM {{ ref('int_ab_comparison_results') }}
),

audio_summary AS (
    SELECT
        version_id,
        loudest_section_name,
        section_loudness_spread_lu,
        landing_lufs,
        cold_open_lufs,
        min_dialogue_to_bed_db,
        lines_below_10db,
        mean_whisper_recall,
    FROM {{ ref('int_version_audio_summary') }}
),

scored_versions AS (
    SELECT
        v.version_id,
        v.version_number,
        v.outcome,
        v.is_promoted,
        v.is_final,
        v.decision_basis,
        v.exported_at_local,
        e.editor_evaluation_id IS NOT NULL AS has_editor_score,
        e.overall_score AS editor_overall_score,
        e.hook_score,
        e.pacing_score,
        e.variety_score,
        e.motion_score,
        e.type_score,
        e.color_score,
        e.sound_score,
        e.captions_score,
        e.story_score,
        e.mean_category_score,
        ab.older_version_id AS ab_compared_with_version_id,
        ab.newer_section_wins AS ab_section_wins,
        ab.newer_section_losses AS ab_section_losses,
        ab.section_ties AS ab_section_ties,
        ab.tie_rate AS ab_tie_rate,
        ab.newer_ab_result AS ab_result,
        v.duration_s,
        v.integrated_lufs,
        v.loudness_range_lu,
        v.true_peak_dbtp,
        a.loudest_section_name,
        a.section_loudness_spread_lu,
        a.landing_lufs - a.cold_open_lufs AS landing_vs_cold_open_lu,
        a.min_dialogue_to_bed_db,
        a.lines_below_10db,
        a.mean_whisper_recall,
    FROM versions AS v
    LEFT JOIN editor_scores AS e
        ON v.version_id = e.version_id
    LEFT JOIN ab_results AS ab
        ON v.version_id = ab.newer_version_id
    LEFT JOIN audio_summary AS a
        ON v.version_id = a.version_id
),

scorecard AS (
    SELECT
        version_id,
        version_number,
        outcome,
        is_promoted,
        is_final,
        decision_basis,
        exported_at_local,
        has_editor_score,
        editor_overall_score,
        editor_overall_score - LAG(editor_overall_score) OVER (
            PARTITION BY has_editor_score
            ORDER BY version_number
        ) AS editor_overall_change_vs_previous_scored,
        hook_score,
        pacing_score,
        variety_score,
        motion_score,
        type_score,
        color_score,
        sound_score,
        captions_score,
        story_score,
        mean_category_score,
        ab_compared_with_version_id,
        ab_section_wins,
        ab_section_losses,
        ab_section_ties,
        ab_tie_rate,
        ab_result,
        CASE
            WHEN ab_result IS NULL OR outcome = 'in_progress' THEN NULL
            WHEN ab_result = 'win' THEN is_promoted
            WHEN ab_result = 'loss' THEN NOT is_promoted
            ELSE TRUE
        END AS ab_agrees_with_decision,
        duration_s,
        integrated_lufs,
        loudness_range_lu,
        true_peak_dbtp,
        loudest_section_name,
        section_loudness_spread_lu,
        landing_vs_cold_open_lu,
        min_dialogue_to_bed_db,
        lines_below_10db,
        mean_whisper_recall,
    FROM scored_versions
)

SELECT
    version_id,
    version_number,
    outcome,
    is_promoted,
    is_final,
    decision_basis,
    exported_at_local,
    has_editor_score,
    editor_overall_score,
    -- Only meaningful where has_editor_score is true; NULL for unscored versions.
    CASE WHEN has_editor_score THEN editor_overall_change_vs_previous_scored END AS editor_overall_change_vs_previous_scored,
    hook_score,
    pacing_score,
    variety_score,
    motion_score,
    type_score,
    color_score,
    sound_score,
    captions_score,
    story_score,
    mean_category_score,
    ab_compared_with_version_id,
    ab_section_wins,
    ab_section_losses,
    ab_section_ties,
    ab_tie_rate,
    ab_result,
    ab_agrees_with_decision,
    duration_s,
    integrated_lufs,
    loudness_range_lu,
    true_peak_dbtp,
    loudest_section_name,
    section_loudness_spread_lu,
    landing_vs_cold_open_lu,
    min_dialogue_to_bed_db,
    lines_below_10db,
    mean_whisper_recall,
FROM scorecard
