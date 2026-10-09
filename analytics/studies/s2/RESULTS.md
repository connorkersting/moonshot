# Study 2 results: position bias in the blind A/B judge

Run 2026-10-09, 08:43 to about 09:05 UTC. Pre-registered design and analysis in `../README.md`. The numbers below
come from the frozen `s2_analyze.py`, unchanged (full output in `results_summary.md`, `results_stats.csv`,
`results_items.csv`, `results_decisions.csv`).

## Design, as run

- 12 items (version pair x section, picked by the fixed rule in `s2_prepare.py`). Each item was shown in both orders
  (newer cut on top, older on top) x 2 repeats, for 48 decisions in 8 calls of 6 sheets.
- Each call was a fresh-context Claude Code subagent (`general-purpose` type, model alias `sonnet`). The transcripts
  show every call resolved to `claude-sonnet-5-5`, the same `judge_model` the in-loop A/B judge used
  (`data/raw/ab_votes.csv`). See `../run_audit.csv`.
- **Deviation 1 (transport).** The subagent received `calls/<call_id>/instructions.md` verbatim, followed by a
  three-line runner note: deliver the JSON block as the final report and do not create, modify or delete files. The
  subagent also carries Claude Code's own system prompt and the user's global instruction files.
- **Deviation 2 (concurrency).** One call ran as a pilot, then the rest in two concurrent batches of 4 and 3, each
  taken in `dispatch.csv` order. Calls shared no state.
- **Raw responses.** Each `results/<call_id>.json` is the subagent's final message exactly as delivered. All 8 were
  checked against the hand-back text in the transcripts and matched. The 48 sheets were re-hashed after the run and
  match `manifest.json`. Each judge made 6 tool calls, all inside its own call folder (`../run_audit.csv`), so
  `key.json` was never opened.

## n completed

8 of 8 calls usable; 48 of 48 decisions (`results_status.csv`).

## Estimates

| statistic | value |
|---|---|
| ties | 10 of 48 = **0.21** (95% Wilson 0.12 to 0.34); 0.21 with the newer cut on top, 0.21 with the older on top |
| P(A wins), decisive decisions | 18 of 38 = **0.47** (95% Clopper-Pearson 0.31 to 0.64) |
| item-block randomization test (primary), two-sided | **p = 0.67** (20000 shuffles; 5 items flipped verdicts across orders and carry the information) |
| exact binomial vs 0.5 (optimistic, assumes independence) | p = 0.87 |
| order-flip consistency (same cut wins in both orders, pairs without a tie) | 11 of 15 = **0.73** (95% Wilson 0.48 to 0.89); 3 pairs went A both times, 1 went B both times, 9 pairs involved a tie |
| test-retest (same item, same order, two repeats, same A/B/TIE verdict) | 14 of 24 = 0.58 |
| P(newer cut wins), decisive, descriptive | 0.55 (95% 0.38 to 0.71) |

Against the hypotheses set before the data:

- **H0 not rejected.** No position preference was detected. P(A) is 0.47 and the primary randomization test gives
  p = 0.67. The interval (0.31 to 0.64) still allows a moderate bias in either direction, so this is "no large
  bias found", not "no bias".
- **Secondary.** The judge follows content more often than position: 0.73 consistency against the 0.5 a coin would
  give, though the interval reaches down to 0.48. One decision in five is a tie. The same sheet in the same order
  got the same verdict only 58% of the time, so a single A/B call is a noisy measurement even with position out of
  the picture.

## Limits

- **Same-model consistency is not accuracy.** This tests whether the verdict depends on presentation order, not
  whether it is right. A judge that ignores position can still prefer the worse cut.
- **Image sheets are not watching video.** Each verdict rests on 8 stills per cut and no audio. Pacing, timing and
  sound differences cannot be seen.
- **Sample size and dependence.** 48 decisions on 12 items, each item seen 4 times by the same model. The binomial
  p-value treats them as independent and is optimistic. The item-block test is fairer but has little power with 12
  items, and only 5 items flipped. Only a large position bias would have been detected.
- **A is always the top row.** A preference for the label and a preference for the top position cannot be told apart.
- **Item selection.** Items were chosen because the two cuts visibly differ. Results describe sheets of that kind,
  not every comparison in the run.
- **Context differs from the loop.** The judges ran in fresh subagents with the frozen study prompt, not inside the
  loop's own A/B step.
