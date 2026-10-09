# Evaluation studies: critic repeatability and A/B position bias

Two small studies on the AI critics used in the MOONSHOT edit loop. Both are designed and frozen before any
critic output exists. This folder holds the harness only: preparation scripts, frozen prompts, analysis scripts.
No critic or judge has been run.

Written 2026-10-07. Everything below describes the harness as built on that date.

**Status, 2026-10-09:** both studies have been run (24 of 24 evaluations, 48 of 48 decisions). Results, deviations and
limits are in `s1/RESULTS.md` and `s2/RESULTS.md`. Raw critic output is in `s1/results/` and `s2/results/`.
`run_log.csv` records each call (model alias, batch, tokens, duration), and `run_audit.csv` lists the resolved
model and the tool calls made outside the critic's own folder (none). The sentence above, "No critic or judge has
been run", describes the harness as frozen.

## Study 1: same-model repeatability of the editor critic

**Question.** If the same critic model is shown the same evidence twice in fresh contexts, how much do its scores
move, and does it keep the versions in the same order?

**Hypotheses (set before data).**
- H1 (primary): single-rating agreement on `overall` is at least good: ICC(2,1) >= 0.75. The 95% bootstrap
  interval is reported next to the point estimate and the conclusion rests on the interval, not the point.
- H2 (secondary): the pooled within-version SD of `overall` is 0.5 points or less, and the mean Spearman between
  repeats is 0.8 or more.
- Reading rule: the in-loop editor scores moved in steps of 0.5 to 1.0 between adjacent versions. If the
  repeatability coefficient (2.77 x within-version SD) is above 1.0 point, score changes of that size between
  adjacent versions cannot be told apart from re-asking the same critic.

**Design.**
- 8 versions spanning the run: v1, v2, v4, v6 (rejected), v8, v10, v11, v13. 3 fresh-context repeats each = **24
  evaluations**.
- Each evaluation gets a blinded evidence pack in `s1/packs/<eval_id>/`. The `eval_id` is random, drawn from a
  recorded seed (20261007). Packs of one version are byte-identical apart from the folder name (verified by hash at
  build time), so repeats are true repeats.
- A pack holds: `contact.jpg`, 22 full-resolution key frames (`frames/frame_NN.jpg`), the matching 640x360 frames
  (`phone/phone_NN.jpg`), `audio_qc.md` with the version number and any `vN` string removed, and `index.md` (frame
  number -> time in that cut). No version history, no previous scores, no hints.
- Frame subset: 22 target moments defined on the v7 timeline; for each version the nearest existing key frame on
  that version's own timeline (from v8 on, everything at or after 40.0 s is 6.7 s earlier, the same rule ab.py
  uses). Mean offset 0.05 s, maximum 1.5 s. The full mapping is in `s1/frame_map.csv`. For v4 and v6 only moments
  that also have a phone-size frame are candidates, so each pair matches.
- Presentation order is shuffled: `s1/dispatch.csv` lists the 24 evaluations in a random run order with no version
  information, so repeats are not run back to back.
- The critic prompt (`s1/prompt.md`) is frozen: senior film editor, 10 categories scored 1 to 10 in half points
  (`hook`, `pacing`, `variety`, `motion`, `type`, `color`, `sound`, `captions`, `story`, `overall`), output a
  strict JSON block `{"scores": {...}, "top_fixes": [...]}`. Its SHA-256 is recorded in `s1/manifest.json` and
  checked by the analysis script. The rendered per-evaluation prompts are in `s1/prompts/<eval_id>.md`.

**Statistics (what each one means).**
- Per version and category: mean, SD, min, max, range over the 3 repeats. The SD is the critic's own noise.
- ICC(2,1): the share of score variance that is real difference between versions, as opposed to repeat-to-repeat
  noise, for a single rating with absolute agreement (the score itself, not just the ranking, has to repeat).
  0 = scores are noise; 1 = identical every time. Conventional labels (Koo and Li 2016): below 0.5 poor, 0.5 to
  0.75 moderate, 0.75 to 0.9 good, above 0.9 excellent. Because the three repeats of a version are exchangeable,
  ICC(1,1) (one-way) is reported alongside as the matching figure.
- 95% CI for ICC(2,1): percentile bootstrap over the 8 versions (5000 resamples). With 8 subjects this is wide.
- Kendall's W and mean pairwise Spearman between repeats: do the repeats rank the versions the same way? W = 1 is
  perfect concordance. W's p-value is a permutation p-value, not a table lookup.
- Within-version SD, between-version SD, repeatability coefficient: the noise in score points and the smallest
  difference between two single scores that is bigger than that noise (about 95% of the time).
- Repeat means vs the original in-loop editor scores: a **descriptive difference only**. The in-loop editor saw
  history and earlier scores, so a gap mixes anchoring with sampling noise. Only v1, v2, v4, v8, v10, v11 have an
  original score; v6 and v13 have none.

## Study 2: A/B judge position bias

**Question.** When the blind A/B judge sees the same two cuts of a section with the sides swapped, does its verdict
follow the content or the position?

**Hypotheses (set before data).**
- H0: among decisive (non-tie) decisions, P(the A / top row wins) = 0.5.
- H1: P(A) differs from 0.5. Primary test: the item-block randomization test, alpha 0.05. The exact binomial test
  is reported for comparison and is optimistic (see limits).
- Secondary: tie rate; order-flip consistency (does the same cut win in both orders?). A content-driven judge scores
  near 1; a purely position-driven judge scores near 0.

**Design.**
- 12 distinct (version pair, section) items out of the 70 existing comparison sheets, picked by a fixed rule
  (`select_items` in `s2_prepare.py`, table in `s2/items.csv`, all 70 candidates in `s2/candidates.csv`): the two
  rows of the existing sheet must differ visibly, meaning at least 4 of the 8 frame pairs differ by more than 6
  grey levels (mean absolute difference after downscale). Candidates are ranked by that count, then by mean
  difference, and taken greedily with at most 3 items per version pair and at most 3 per section. Result: 6
  items where the original judge picked a cut and 6 where it called a tie, from 6 version pairs (v3_v2 to v9_v7).
  Sections whose cuts look alike (53 of the 70 sheets fail the rule) are excluded because a flip test on
  near-identical rows tests nothing.
- Each item is shown in BOTH orders (newer cut on top, older cut on top) x 2 fresh repeats = **48 decisions**.
- 8 judge calls of 6 sheets each. No item appears twice in a call. Each call has 3 sheets in each order. Per repeat
  the 12 items are split into two halves of 6; each half runs once as assigned and once flipped. Call and sheet
  order are shuffled; seed 20261008 is recorded.
- Sheets are rebuilt, not cropped: ab.py bakes a 70% black label box into the pixels, so a sheet cannot be flipped
  by cutting it apart. `s2_prepare.py` repeats ab.py's extraction (same section windows, same 6.7 s timeline shift,
  same ffmpeg filter, 8 frames at 400 px) without the label and stamps fresh `A`/`B` labels in the same font, size
  and box. Geometry (3200 x 450 = two rows of 225 px, eight 400 px tiles) was checked on all 70 existing sheets.
  Each item was also rebuilt in the orientation the original judge saw and compared with the original image: mean
  difference 2.4 grey levels outside the label boxes (max 3.0), which is JPEG noise.
- The judge instruction (`s2/prompt.md`) embeds `ab_rubric.md` verbatim (checked by the script), states that the
  judge cannot hear, and asks for A/B/TIE plus confidence in a strict JSON block. Per-call instruction files are in
  `s2/calls/<call_id>/instructions.md`; the sheets are `sheet_1.jpg` to `sheet_6.jpg` beside them.

**Statistics (what each one means).**
- Tie rate (Wilson interval), overall and by order.
- P(A | decisive) with an exact (Clopper-Pearson) interval. 0.5 means no position preference.
- Exact two-sided binomial test of P(A) = 0.5. Treats decisions as independent, which they are not.
- Item-block randomization test. Order labels are shuffled within each item, with the version picks held fixed,
  and the number of A picks recomputed (20000 shuffles). It asks: if the verdict depended only on the item and not
  on the order, how often would we see this many A picks? An item whose judge picks the same cut in both orders
  contributes exactly its balanced share whatever the shuffle, so only items with a flip carry information.
- Order-flip consistency: for each item x repeat, did the same cut win in both orders (`same_version`), did A win
  both times (`same_position_A`), did B win both times, or was a tie involved.
- Test-retest: same item, same order, two repeats, same verdict?
- P(newer wins), descriptive. Orders are balanced, so position cannot contaminate it.

## Limits, stated plainly

- **Same-model repeatability is not accuracy.** Study 1 can show the critic is stable; it cannot show the critic is
  right. A critic with a consistent blind spot would score perfectly on ICC.
- **The critics cannot hear.** The editor sees `sound` only through measurements; the A/B judge sees frames only.
  Any sound or music finding is inference from numbers.
- **Small n.** 24 evaluations on 8 versions; 48 decisions on 12 items. Intervals are wide and the point estimates
  should not be quoted without them. Study 2 detects only a large position bias.
- **Study 2 decisions are not independent.** Each item appears 4 times and the two repeats are one model re-asked,
  so the binomial p-value overstates the evidence. Items were chosen because the cuts differ visibly, so results
  describe sheets of that kind.
- **A is always the top row.** A preference for the A label and a preference for the top position cannot be
  separated.
- **Known evidence gaps in Study 1.** v1 has no per-section audio QC (only whole-mix loudness); the prompt tells the
  critic not to penalise missing tables, but this is a confound for v1's `sound` score. v1 and v2 have no phone-size
  frames on disk, so theirs are generated from the key frames (bicubic resize, JPEG 90). Frame times and the contact
  sheet carry the timeline, so a critic could guess an early or late cut; the version number itself is not shown.
- **The comparison with the original editor scores is descriptive.** The original editor's prompt and context
  differed (history, anchoring), so a gap is not a measure of anything on its own.
- **Blinding is by convention.** `key.json` and `manifest.json` sit in the same tree as the packs. Point critics
  only at the pack or call folder; do not give them the study folder.

## Files

```
studies/
  README.md
  s1_prepare.py      build 24 blinded packs, key, manifest, per-evaluation prompts
  s1_analyze.py      repeatability statistics; --selftest runs on synthetic data and deletes it
  s1/prompt.md       FROZEN critic prompt template ({PACK_DIR} placeholder)
  s1/packs/<eval_id>/        (generated)  contact.jpg, frames/, phone/, audio_qc.md, index.md
  s1/prompts/<eval_id>.md    (generated)  the rendered prompt for each evaluation
  s1/key.json        (generated)  eval_id -> version, repeat. Never show to a critic.
  s1/manifest.json   (generated)  seed, prompt hash, run order, pack hashes
  s1/dispatch.csv    (generated)  run order, pack path, prompt path, where to save the result
  s1/frame_map.csv   (generated)  frame mapping per version
  s1/results/<eval_id>.json    critic output goes here (you or a runner saves it)
  s2_prepare.py      select items, rebuild sheets in both orders, make 8 call folders, key, manifest
  s2_analyze.py      position-bias statistics; --selftest runs on synthetic data and deletes it
  s2/prompt.md       FROZEN judge prompt template (rubric verbatim; {CALL_DIR}, {SHEET_LIST} placeholders)
  s2/calls/<call_id>/        (generated)  sheet_1.jpg ... sheet_6.jpg and instructions.md
  s2/items.csv, candidates.csv (generated)  the 12 chosen items and all 70 candidates with the selection metric
  s2/key.json        (generated)  decision -> item, order, top version, call, sheet. Never show to a judge.
  s2/manifest.json   (generated)  seed, prompt and rubric hashes, rebuild fidelity, run order
  s2/dispatch.csv    (generated)  run order, call folder, instruction file, where to save the result
  s2/results/<call_id>.json    judge output goes here
```

## How to run

All commands from `C:\dev\moonshot-repo\analytics`, with `PYTHONUTF8=1`, using `py` (the project's uv environment
has no Pillow and no scipy; `py` has Pillow, numpy and pandas, which is all these scripts need).

```
set PYTHONUTF8=1
py studies\s1_prepare.py          # once; --force rebuilds (refuses if results/ has files)
py studies\s2_prepare.py          # once; renders 24 rows with ffmpeg at below-normal priority
py studies\s1_analyze.py --selftest
py studies\s2_analyze.py --selftest
```

Running the studies (not done yet): for each line of `s1/dispatch.csv` (in file order), start a fresh-context critic
with the contents of `prompt_file` and nothing else, and save its final JSON message as `result_path`. Same for
`s2/dispatch.csv` and the `instructions_file`. Then:

```
py studies\s1_analyze.py          # writes s1/results_summary.csv, results_agreement.csv, results_status.csv, results_summary.md
py studies\s2_analyze.py          # writes s2/results_decisions.csv, results_items.csv, results_stats.csv, results_status.csv, results_summary.md
```

Malformed or missing results are not repaired; they are listed in `results_status.csv` and left out. Do not edit a
prompt after preparation; the analysis scripts warn if the hash no longer matches. Do not re-run a critic that
returned a valid result because you disliked it.
