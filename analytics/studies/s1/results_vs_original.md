# Study 1 supplement: repeat means vs the original in-loop editor scores

Descriptive only. Original = critic `fable_editor` in `data/raw/critic_scores.csv` (the editor's own review of that version). See the docstring of `s1_vs_original.py` for why this is a separate file.

Usable evaluations: 24 of 24.

## `overall` by version

| version | n | mean | sd | original_in_loop_score | mean_minus_original |
|---|---|---|---|---|---|
| 1 | 3 | 6.67 | 0.58 | 5.50 | 1.17 |
| 2 | 3 | 6.50 | 0.00 | 6.50 | 0.00 |
| 4 | 3 | 6.33 | 0.29 | 6.00 | 0.33 |
| 6 | 3 | 7.17 | 0.29 | n/a | n/a |
| 8 | 3 | 7.17 | 0.29 | 6.50 | 0.67 |
| 10 | 3 | 7.17 | 0.29 | 7.50 | -0.33 |
| 11 | 3 | 7.17 | 0.29 | 7.50 | -0.33 |
| 13 | 3 | 7.17 | 0.58 | n/a | n/a |

## Every category, versions with an original score

| category | n_versions | mean_diff_repeat_minus_original | mean_abs_diff | max_abs_diff |
|---|---|---|---|---|
| hook | 6 | 0.44 | 0.50 | 1.50 |
| pacing | 6 | 0.58 | 0.58 | 1.00 |
| variety | 6 | 0.67 | 0.67 | 1.33 |
| motion | 6 | 0.28 | 0.56 | 2.00 |
| type | 6 | -0.06 | 0.78 | 1.17 |
| color | 6 | -0.22 | 0.50 | 0.67 |
| sound | 6 | -0.58 | 0.75 | 3.00 |
| captions | 6 | -0.11 | 0.44 | 1.00 |
| story | 6 | 0.64 | 0.64 | 1.33 |
| overall | 6 | 0.25 | 0.47 | 1.17 |

- spearman_overall_repeat_mean_vs_original: 0.69

- n_versions_with_original: 6.00


The in-loop editor saw the run's history and its own earlier scores; the repeats saw neither. A gap therefore mixes anchoring, context and sampling noise, and is not a measure of anything on its own.
