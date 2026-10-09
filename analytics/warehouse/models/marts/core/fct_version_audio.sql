WITH qc_sections AS (
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
    FROM {{ ref('stg_moonshot__qc_sections') }}
),

measured_sections AS (
    SELECT
        version_section_id,
        version_id,
        section_no,
        section_name,
        section_start_s,
        section_end_s,
        section_end_s - section_start_s AS section_duration_s,
        section_lufs,
        section_lra_lu,
        section_true_peak_dbtp,
    FROM qc_sections
)

SELECT
    version_section_id,
    version_id,
    section_no,
    section_name,
    section_start_s,
    section_end_s,
    section_duration_s,
    section_lufs,
    section_lra_lu,
    section_true_peak_dbtp,
FROM measured_sections
