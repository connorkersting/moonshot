WITH qc_dialogue AS (
    SELECT
        dialogue_line_id,
        version_id,
        line_no,
        line_start_s,
        speaker,
        dialogue_db,
        bed_db,
        dialogue_to_bed_db,
        is_ratio_low,
        whisper_recall,
        is_recall_low,
    FROM {{ ref('stg_moonshot__qc_dialogue') }}
),

measured_lines AS (
    SELECT
        dialogue_line_id,
        version_id,
        line_no,
        line_start_s,
        speaker,
        dialogue_db,
        bed_db,
        dialogue_to_bed_db,
        -- The run's own target: dialogue at least +10 dB over the music bed.
        dialogue_to_bed_db >= 10 AS meets_10db_target,
        is_ratio_low,
        whisper_recall,
        is_recall_low,
    FROM qc_dialogue
)

SELECT
    dialogue_line_id,
    version_id,
    line_no,
    line_start_s,
    speaker,
    dialogue_db,
    bed_db,
    dialogue_to_bed_db,
    meets_10db_target,
    is_ratio_low,
    whisper_recall,
    is_recall_low,
FROM measured_lines
