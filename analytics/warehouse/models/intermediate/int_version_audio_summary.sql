-- One row per version that has audio QC. Section loudness and dialogue lines are
-- aggregated separately to version grain, then joined, so neither side fans out.

WITH qc_sections AS (
    SELECT
        version_id,
        section_no,
        section_name,
        section_lufs,
    FROM {{ ref('stg_moonshot__qc_sections') }}
),

qc_dialogue AS (
    SELECT
        version_id,
        dialogue_to_bed_db,
        whisper_recall,
        is_ratio_low,
        is_recall_low,
    FROM {{ ref('stg_moonshot__qc_dialogue') }}
),

section_loudness AS (
    SELECT
        version_id,
        COUNT(*) AS n_sections,
        MAX(section_lufs) AS loudest_section_lufs,
        ARG_MAX(section_name, section_lufs) AS loudest_section_name,
        MIN(section_lufs) AS quietest_section_lufs,
        MAX(section_lufs) - MIN(section_lufs) AS section_loudness_spread_lu,
        MAX(section_lufs) FILTER (WHERE section_name = 'landing') AS landing_lufs,
        MAX(section_lufs) FILTER (WHERE section_no = 1) AS cold_open_lufs,
    FROM qc_sections
    GROUP BY version_id
),

dialogue_clarity AS (
    SELECT
        version_id,
        COUNT(*) AS n_dialogue_lines,
        MIN(dialogue_to_bed_db) AS min_dialogue_to_bed_db,
        MEDIAN(dialogue_to_bed_db) AS median_dialogue_to_bed_db,
        COUNT(*) FILTER (WHERE dialogue_to_bed_db < 10) AS lines_below_10db,
        COUNT(*) FILTER (WHERE is_ratio_low) AS lines_flagged_ratio_low,
        AVG(whisper_recall) AS mean_whisper_recall,
        COUNT(*) FILTER (WHERE is_recall_low) AS lines_flagged_recall_low,
    FROM qc_dialogue
    GROUP BY version_id
),

version_audio AS (
    SELECT
        COALESCE(s.version_id, d.version_id) AS version_id,
        s.n_sections,
        s.loudest_section_name,
        s.loudest_section_lufs,
        s.quietest_section_lufs,
        s.section_loudness_spread_lu,
        s.landing_lufs,
        s.cold_open_lufs,
        d.n_dialogue_lines,
        d.min_dialogue_to_bed_db,
        d.median_dialogue_to_bed_db,
        d.lines_below_10db,
        d.lines_flagged_ratio_low,
        d.mean_whisper_recall,
        d.lines_flagged_recall_low,
    FROM section_loudness AS s
    FULL OUTER JOIN dialogue_clarity AS d
        ON s.version_id = d.version_id
)

SELECT
    version_id,
    n_sections,
    loudest_section_name,
    loudest_section_lufs,
    quietest_section_lufs,
    section_loudness_spread_lu,
    landing_lufs,
    cold_open_lufs,
    n_dialogue_lines,
    min_dialogue_to_bed_db,
    median_dialogue_to_bed_db,
    lines_below_10db,
    lines_flagged_ratio_low,
    mean_whisper_recall,
    lines_flagged_recall_low,
FROM version_audio
