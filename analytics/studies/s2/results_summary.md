# Study 2: A/B judge position bias, results

Calls expected 8; usable 8; missing 0; malformed 0. Usable decisions 48 of 48.

## Primary: does the judge favour the A (top) position?

- Ties: 10 of 48 = 0.208 (95% Wilson 0.117 to 0.343). Tie rate with the newer cut on top 0.208, with the older on top 0.208.

- Among 38 decisive decisions, A won 18: P(A) = **0.474** (95% exact 0.310 to 0.642).
- Exact binomial test against 0.5, two-sided: p = 0.8714 (assumes independent decisions; they are not).
- Item-block randomization test: p = 0.6683 (observed 18.000 A picks vs null mean 16.000; 5 items had a version flip and so carry the information).
- Descriptive: the newer cut won 0.553 of decisive decisions (95% exact 0.383 to 0.714). Orders are balanced, so this is not contaminated by position bias.

## Order-flip consistency

24 item x repeat pairs had both orders usable: 11 picked the same cut in both orders, 3 picked A both times, 1 picked B both times, 9 involved a tie.

Same-cut rate among pairs without a tie: **0.733** (95% Wilson 0.480 to 0.891). 1 means the verdict follows the content; 0 means it follows the position; a judge guessing at random would sit near 0.5.

Test-retest: the same item in the same order got the same verdict in both repeats in 0.583 of 24 pairs.

## Items

| item_id | comparison | section | n_decisions | n_ties | n_decisive | newer_picked | older_picked | A_picked | B_picked | pattern |
|---|---|---|---|---|---|---|---|---|---|---|
| i01 | v5_v4 | 1_cold_open | 4 | 0 | 4 | 3 | 1 | 3 | 1 | mixed |
| i02 | v8_v7 | 3_stats_chart | 4 | 0 | 4 | 3 | 1 | 3 | 1 | mixed |
| i03 | v9_v7 | 3_stats_chart | 4 | 0 | 4 | 3 | 1 | 3 | 1 | mixed |
| i04 | v4_v3 | 3_stats_chart | 4 | 0 | 4 | 0 | 4 | 2 | 2 | same version every time |
| i05 | v4_v3 | 7_outro | 4 | 2 | 2 | 0 | 2 | 0 | 2 | same version every time |
| i06 | v7_v5 | 7_outro | 4 | 3 | 1 | 1 | 0 | 0 | 1 | one decisive pick |
| i07 | v3_v2 | 6_fuel_landing | 4 | 1 | 3 | 0 | 3 | 1 | 2 | same version every time |
| i08 | v3_v2 | 4_moon_lm | 4 | 0 | 4 | 4 | 0 | 2 | 2 | same version every time |
| i09 | v5_v4 | 5_alarm | 4 | 0 | 4 | 3 | 1 | 1 | 3 | mixed |
| i10 | v7_v5 | 6_fuel_landing | 4 | 2 | 2 | 0 | 2 | 1 | 1 | same version every time |
| i11 | v4_v3 | 6_fuel_landing | 4 | 0 | 4 | 2 | 2 | 2 | 2 | mixed |
| i12 | v9_v7 | 2_drop_title | 4 | 2 | 2 | 2 | 0 | 0 | 2 | same version every time |

## Reading this honestly

- n = 48 planned decisions on 12 items. The decisions are not independent: each item appears 4 times (2 orders x 2 repeats), and the two repeats are the same model re-asked. The exact binomial p-value is therefore optimistic; the item-block randomization test is the fairer one, and with 12 items even it has little power.
- Items where the judge is firmly content-driven carry no information about position bias, by construction of the balanced design. Only items where the verdict flips across orders do.
- A is always the top row: label bias and top-row bias cannot be separated.
- The judge cannot hear audio and sees eight frames per cut, so 'correct' is not defined here. This measures whether the verdict depends on presentation order, not whether it is right.
- Items were chosen because the cuts visibly differ (and not at random), so results describe sheets of that kind, not every comparison in the run.
