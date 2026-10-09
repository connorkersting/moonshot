WITH source_qc_sections AS (
    SELECT
        version,
        section_no,
        section,
        t0,
        t1,
        lufs,
        lra,
        tp,
    FROM {{ source('moonshot_raw', 'qc_sections') }}
),

renamed_qc_sections AS (
    SELECT
        'v' || version || '-s' || section_no AS version_section_id,
        'v' || version AS version_id,
        section_no,
        section AS section_name,
        t0 AS section_start_s,
        t1 AS section_end_s,
        lufs AS section_lufs,
        lra AS section_lra_lu,
        tp AS section_true_peak_dbtp,
    FROM source_qc_sections
)

SELECT
    version_section_id,
    version_id,
    section_no,
    section_name,
    section_start_s,
    section_end_s,
    section_lufs,
    section_lra_lu,
    section_true_peak_dbtp,
FROM renamed_qc_sections
