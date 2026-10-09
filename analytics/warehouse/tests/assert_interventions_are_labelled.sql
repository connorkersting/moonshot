-- Every human message carries a hand-written label from
-- ingest/intervention_labels.csv. "unlabelled" means a new message arrived and the
-- label file was not updated, so the published label would be missing.

WITH interventions AS (
    SELECT
        intervention_id,
        intervened_at_local,
        intervention_label,
    FROM {{ ref('fct_interventions') }}
)

SELECT
    intervention_id,
    intervened_at_local,
    intervention_label,
FROM interventions
WHERE intervention_label = 'unlabelled'
