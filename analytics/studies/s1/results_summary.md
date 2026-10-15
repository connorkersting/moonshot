# Study 1: editor critic repeatability, results

Evaluations expected 24; usable 24; missing 0; malformed 0.

## Primary: `overall` agreement across repeats

- ICC(2,1), single rating, absolute agreement: **0.38** (95% percentile bootstrap over versions -0.20 to 0.67; 8 complete versions, 5000 usable resamples).
- ICC(1,1), all ratings: 0.38.
- Kendall's W across repeats: 0.58 (permutation p = 0.0607).
- Spearman between repeats: mean 0.36, min 0.18, max 0.61.
- Pooled within-version SD: 0.37 points; SD of version means: 0.36; repeatability coefficient (2.77 x SD): 1.02 points.
- Benchmarks usually quoted (Koo and Li 2016): ICC below 0.5 poor, 0.5-0.75 moderate, 0.75-0.9 good, above 0.9 excellent. Judge the interval, not the point.

### `overall` by version

| version | n | mean | sd | min | max | range | original_in_loop_score | mean_minus_original |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 | 6.67 | 0.58 | 6.00 | 7.00 | 1.00 | n/a | n/a |
| 2 | 3 | 6.50 | 0.00 | 6.50 | 6.50 | 0.00 | n/a | n/a |
| 4 | 3 | 6.33 | 0.29 | 6.00 | 6.50 | 0.50 | n/a | n/a |
| 6 | 3 | 7.17 | 0.29 | 7.00 | 7.50 | 0.50 | n/a | n/a |
| 8 | 3 | 7.17 | 0.29 | 7.00 | 7.50 | 0.50 | n/a | n/a |
| 10 | 3 | 7.17 | 0.29 | 7.00 | 7.50 | 0.50 | n/a | n/a |
| 11 | 3 | 7.17 | 0.29 | 7.00 | 7.50 | 0.50 | n/a | n/a |
| 13 | 3 | 7.17 | 0.58 | 6.50 | 7.50 | 1.00 | n/a | n/a |

## Agreement, every category (only `overall` is the pre-registered primary)

| category | n_versions_complete | icc21 | icc21_ci_lo | icc21_ci_hi | icc11_all_ratings | kendall_w | kendall_w_perm_p | spearman_mean | sd_within_pooled | sd_between_version_means | repeatability_coef_2_77_sd |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hook | 8 | 0.15 | -0.28 | 0.38 | 0.16 | 0.42 | 0.27 | 0.12 | 0.41 | 0.30 | 1.13 |
| pacing | 8 | 0.35 | -0.11 | 0.56 | 0.35 | 0.58 | 0.07 | 0.37 | 0.34 | 0.32 | 0.94 |
| variety | 8 | 0.36 | -0.20 | 0.58 | 0.34 | 0.56 | 0.08 | 0.34 | 0.27 | 0.25 | 0.75 |
| motion | 8 | -0.09 | -0.37 | 0.15 | -0.11 | 0.26 | 0.73 | -0.11 | 0.31 | 0.15 | 0.85 |
| type | 8 | 0.06 | -0.18 | 0.40 | 0.03 | 0.37 | 0.38 | 0.05 | 0.41 | 0.25 | 1.13 |
| color | 8 | 0.26 | -0.27 | 0.46 | 0.26 | 0.47 | 0.18 | 0.21 | 0.40 | 0.33 | 1.09 |
| sound | 8 | 0.97 | 0.70 | 1.00 | 0.97 | 0.96 | 0.00 | 0.93 | 0.23 | 1.42 | 0.63 |
| captions | 8 | 0.32 | -0.14 | 0.72 | 0.32 | 0.53 | 0.10 | 0.30 | 0.42 | 0.38 | 1.17 |
| story | 8 | -0.15 | -0.34 | 0.08 | -0.17 | 0.16 | 0.90 | -0.26 | 0.41 | 0.18 | 1.13 |
| overall | 8 | 0.38 | -0.20 | 0.67 | 0.38 | 0.58 | 0.06 | 0.36 | 0.37 | 0.36 | 1.02 |

## Version means, every category

| version | hook | pacing | variety | motion | type | color | sound | captions | story | overall |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 6.67 | 6.17 | 7.33 | 7.00 | 6.17 | 5.67 | 7.00 | 6.83 | 7.83 | 6.67 |
| 2 | 7.50 | 6.67 | 7.83 | 6.83 | 6.33 | 6.17 | 4.00 | 7.67 | 7.83 | 6.50 |
| 4 | 7.00 | 6.33 | 7.67 | 6.67 | 6.17 | 6.33 | 4.00 | 7.33 | 7.67 | 6.33 |
| 6 | 7.50 | 6.67 | 7.67 | 6.67 | 6.33 | 6.67 | 6.17 | 7.67 | 7.83 | 7.17 |
| 8 | 7.17 | 7.00 | 7.83 | 6.67 | 6.83 | 6.67 | 6.50 | 8.00 | 8.00 | 7.17 |
| 10 | 7.33 | 6.83 | 8.00 | 6.67 | 6.50 | 6.50 | 7.00 | 7.00 | 7.50 | 7.17 |
| 11 | 7.50 | 7.00 | 7.83 | 6.83 | 6.67 | 6.33 | 7.50 | 7.50 | 8.00 | 7.17 |
| 13 | 7.33 | 7.00 | 8.17 | 7.00 | 6.67 | 6.50 | 7.33 | 7.33 | 8.00 | 7.17 |

## Repeat means vs the original in-loop editor scores (descriptive)

No original scores for the versions analysed.

## Reading this honestly

- This measures **same-model repeatability** (fresh contexts, identical evidence). A critic can be perfectly repeatable and still be wrong; it says nothing about accuracy.
- The critic cannot hear: `sound` rests on audio measurements, and v1 had only whole-mix loudness.
- 8 versions x 3 repeats: the ICC confidence interval is wide by construction, and the bootstrap resamples only 8 subjects. Treat the interval as the finding, not the point estimate.
- The three repeats of a version are exchangeable fresh contexts, so the repeat labels carry no meaning; ICC(2,1) is reported as pre-registered and ICC(1,1) is the matching one-way figure.
- The comparison with the original in-loop scores is descriptive. The in-loop editor saw history and previous scores; the repeats saw none, so a difference mixes anchoring with sampling noise.
- Only versions 1, 2, 4, 8, 10 and 11 have an original editor score; v6 and v13 have none.
