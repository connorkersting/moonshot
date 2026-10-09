WITH source_qc_dialogue AS (
    SELECT
        version,
        line_no,
        t,
        speaker,
        dialog_db,
        bed_db,
        ratio_db,
        ratio_low_flag,
        whisper_recall,
        recall_low_flag,
    FROM {{ source('moonshot_raw', 'qc_dialogue') }}
),

renamed_qc_dialogue AS (
    SELECT
        'v' || version || '-l' || line_no AS dialogue_line_id,
        'v' || version AS version_id,
        line_no,
        t AS line_start_s,
        speaker,
        dialog_db AS dialogue_db,
        bed_db,
        ratio_db AS dialogue_to_bed_db,
        ratio_low_flag AS is_ratio_low,
        whisper_recall,
        recall_low_flag AS is_recall_low,
    FROM source_qc_dialogue
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
    is_ratio_low,
    whisper_recall,
    is_recall_low,
FROM renamed_qc_dialogue
