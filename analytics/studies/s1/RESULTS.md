# Study 1 results: repeatability of the editor critic

Run 2026-10-09, 08:43 to about 09:15 UTC. Pre-registered design and analysis in `../README.md`. The numbers below
come from the frozen `s1_analyze.py`, unchanged (full output in `results_summary.md`, `results_agreement.csv`,
`results_summary.csv`).

## Design, as run

- 8 versions (v1, v2, v4, v6, v8, v10, v11, v13) x 3 repeats = 24 evaluations. Each one used the blinded pack and the
  rendered prompt in `prompts/<eval_id>.md`, launched in `dispatch.csv` order.
- Each evaluation was a fresh-context Claude Code subagent (`general-purpose` type, model alias `fable`). The
  transcripts show every call resolved to `claude-fable-5-1`, the same model ID the in-loop editor used
  (`data/raw/critic_scores.csv`). See `../run_audit.csv`.
- **Deviation 1 (transport).** The subagent received the rendered prompt verbatim, followed by a three-line runner
  note: deliver the JSON block as the final report and do not create, modify or delete files. A Claude Code
  subagent also carries its own system prompt and the user's global instruction files. The original in-loop
  editor's context was not identical, so these are repeats of "this model in a fresh subagent", not of the
  in-loop call.
- **Deviation 2 (concurrency).** The 24 calls ran in 4 concurrent batches (5, 6, 7 and 6 calls), each batch taken
  in dispatch order. Every call had a fresh context and shared no state, so running them concurrently does not
  break the independence of repeats.
- **Raw responses.** Each `results/<eval_id>.json` is the subagent's final message exactly as delivered. All 24 were
  checked against the hand-back text in the subagent transcripts and matched. The packs were re-hashed after the
  run and match `manifest.json`. No critic made a tool call outside its own pack folder (`../run_audit.csv`), so
  `key.json` was never opened.
- **Deviation 3 (supplement only).** The frozen script looks up original scores under the critic label `editor`.
  The v28 data refresh renamed that label to `fable_editor`, so the frozen script reports "No original scores".
  `../s1_vs_original.py` reuses the frozen functions with the new label and writes `results_vs_original.*`. The
  primary statistics are untouched.

## n completed

24 of 24 usable (`results_status.csv`: 24 ok, 0 missing, 0 malformed).

## Estimates (primary: `overall`)

| statistic | value |
|---|---|
| ICC(2,1), absolute agreement, single rating | **0.38**, 95% bootstrap CI **-0.20 to 0.67** (5000 resamples over 8 versions) |
| ICC(1,1) | 0.38 |
| Kendall's W across the 3 repeats | 0.58 (permutation p = 0.061) |
| Spearman between repeats | mean 0.36 (min 0.18, max 0.61) |
| pooled within-version SD | 0.37 points |
| SD of the version means | 0.36 points |
| repeatability coefficient (2.77 x within SD) | 1.02 points |

Against the hypotheses set before the data:

- **H1 (ICC(2,1) >= 0.75): not supported.** The whole 95% interval lies below 0.75. The point estimate is "poor" on
  the Koo and Li scale. The interval runs from "no agreement" to "moderate".
- **H2: half met.** The within-version SD is 0.37, inside the 0.5 bound. The mean Spearman is 0.36, well short of
  0.8.
- **Reading rule.** The repeatability coefficient is 1.02 points, just above the 1.0 threshold. A change of 0.5 to
  1.0 in `overall` between adjacent versions is within what re-asking the same critic produces.

What drives the low ICC is not large noise. Repeats rarely differ by more than 0.5, and v2 scored 6.5 all three
times. The problem is that the critic barely tells the versions apart: the version means span only 6.33 to 7.17,
and v6, v8, v10, v11 and v13 all average exactly 7.17. With so little real spread, ordinary half-point noise is
about as large as the differences between versions.

Other categories (descriptive, not pre-registered as primary): `sound` has ICC 0.97 (CI 0.70 to 1.00), because it
is read off the numeric `audio_qc.md` tables. v2 and v4 score 4.0 on every repeat, from their dialogue-to-bed
measurements. v1, which has only whole-mix loudness (the known confound), scores 7.0 on every repeat. `story`
(-0.15) and `motion` (-0.09) show no between-version signal at all. `hook`, `type`, `color`, `pacing`, `variety`
and `captions` fall between 0.06 and 0.36.

Repeat means vs the in-loop editor's own scores (`results_vs_original.md`, descriptive, 6 versions with an
original): Spearman 0.69; mean repeat minus original +0.25 on `overall`, largest for v1 (6.67 vs 5.5).

## Limits

- **Same-model repeatability is not accuracy.** This measures whether `claude-fable-5-1` gives the same score twice
  from the same evidence. A critic can be perfectly repeatable and still wrong; the `sound` ICC of 0.97 is
  repeatable because it reads numbers, not because it judges the mix well.
- **Image packs are not watching video.** The critic saw a contact sheet, 22 key frames, 22 phone-size frames and
  an audio measurement table. It saw no motion and heard nothing. Pacing, motion and sound scores are inferences
  from stills and numbers.
- **Sample size.** 8 versions x 3 repeats. The ICC interval (-0.20 to 0.67) is wide by construction, and the
  bootstrap resamples only 8 subjects. Quote the interval, not the point.
- **Context differs from the loop.** The repeats ran in fresh subagents with no history. The in-loop editor saw
  history and its earlier scores, so the comparison with original scores mixes anchoring with noise.
- **Not extended to later versions.** The task allowed adding later versions. That was not done: the 5-hour usage
  window reached 78% by the end of the 24 pre-registered calls.
