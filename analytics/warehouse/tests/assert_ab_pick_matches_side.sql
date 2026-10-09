-- The picked version, the tie flag and the newer version's outcome must all follow
-- from side_picked and the side assignment in the A/B key file. A mismatch means
-- the key file and the verdict table were joined on the wrong section.

WITH ab_votes AS (
    SELECT
        ab_vote_id,
        newer_version_id,
        side_a_version_id,
        side_b_version_id,
        side_picked,
        is_tie,
        picked_version_id,
        newer_outcome,
    FROM {{ ref('fct_ab_votes') }}
),

expected AS (
    SELECT
        ab_vote_id,
        side_picked,
        is_tie,
        picked_version_id,
        newer_outcome,
        CASE side_picked
            WHEN 'A' THEN side_a_version_id
            WHEN 'B' THEN side_b_version_id
        END AS expected_picked_version_id,
        side_picked = 'TIE' AS expected_is_tie,
        CASE
            WHEN side_picked = 'TIE' THEN 'tie'
            WHEN (CASE side_picked WHEN 'A' THEN side_a_version_id ELSE side_b_version_id END) = newer_version_id THEN 'win'
            ELSE 'loss'
        END AS expected_newer_outcome,
        side_a_version_id <> side_b_version_id AS sides_differ,
    FROM ab_votes
)

SELECT
    ab_vote_id,
    side_picked,
    is_tie,
    expected_is_tie,
    picked_version_id,
    expected_picked_version_id,
    newer_outcome,
    expected_newer_outcome,
    sides_differ,
FROM expected
WHERE picked_version_id IS DISTINCT FROM expected_picked_version_id
    OR is_tie IS DISTINCT FROM expected_is_tie
    OR newer_outcome IS DISTINCT FROM expected_newer_outcome
    OR NOT sides_differ
