WITH score_categories AS (
    SELECT
        score_category,
        category_order,
        category_group,
        is_overall,
        higher_is_better,
        category_description,
    FROM {{ ref('score_categories') }}
)

SELECT
    score_category,
    category_order,
    category_group,
    is_overall,
    higher_is_better,
    category_description,
FROM score_categories
