# MOONSHOT

MOONSHOT is an 87.5-second Apollo 11 trailer cut by a Claude Code agent loop, plus a dbt + DuckDB
warehouse that measures how that loop behaved. The loop ran on one Windows laptop, with no cloud
renders, for a budget of 24 hours of loop time between 2026-10-07 and 2026-10-09. It exported 28
versions. Each one had to pass automated gates and was scored by AI critics that didn't build it,
and a human director, Connor Kersting, made the calls the critics couldn't, mostly on sound. Every
picture and voice in the trailer is real 1969 NASA material; the 3D shots are built from NASA data
and the music is public-domain recordings. This repo is the record of that run: the pipeline, the
loop's gates and critics, and a tested warehouse built from the run's logs, so each claim below
can be checked against a file.

![Contact sheet of the final cut, v28](docs/v28_contact_sheet.jpg)

*The final cut (v28), one frame every 3.6 seconds, from the run's QC contact sheet. The video file
itself is not in the repo.*

## Result

![Every critic's score per version, v1 to v28](docs/plateau_chart.png)

After the loop closed, the senior-editor critic (Claude Fable, an AI reviewer) scored the first
and last versions on the same ten-category rubric in one sitting
([`analytics/data/raw/baseline_to_final.csv`](analytics/data/raw/baseline_to_final.csv)):

| Category | v1 | v28 | Change |
|---|---:|---:|---:|
| Hook | 5.0 | 8.5 | +3.5 |
| Pacing | 5.5 | 8.0 | +2.5 |
| Visual variety | 6.0 | 9.0 | +3.0 |
| Motion | 4.5 | 9.5 | +5.0 |
| Typography | 4.5 | 9.5 | +5.0 |
| Colour | 5.5 | 9.5 | +4.0 |
| Sound (judged by structure; the critic can't hear) | 5.5 | 8.0 | +2.5 |
| Captions | 7.0 | 8.5 | +1.5 |
| Story | 5.5 | 9.5 | +4.0 |
| Overall | 5.0 | 9.5 | +4.5 |

The 9.5 answers "would a top YouTube editor ship this". In the same review the critic put v28 at
7.5 against a trailer house's own standard, and named the gap (see [Honest limits](#honest-limits)).

The run in numbers, from the run ledger and the warehouse:
- 28 versions exported, none overwritten: v6 reverted after losing a blind A/B, and v8, v15, v16
  and v20 not promoted.
- The run ledger records 24 h 01 m of loop time in seven segments; the transcript shows about
  16 h of active work inside them. The rest is renders and waits.
- The blind A/B judge gave 161 section verdicts in 23 comparisons: the newer version won 39, lost
  25 and tied 97.
- 5,114 Claude requests (Opus 3,461, Sonnet 1,409, Fable 244), 107 subagents, 491 Codex requests
  (an upper bound) and 99 messages from the director.
- The final file is 2,100 frames at 24 fps, 1920x1080, −13.8 LUFS and −1.5 dBTP. `BEST.json`
  pins it by sha256 and git tag.

## My role

<!-- Connor writes this paragraph in his own words -->

## How the loop worked

Each version went through the same four steps:

1. **Generate.** The lead agent or a builder subagent wrote a small patch script (exact-string
   replacements with asserts) and dry-ran it on copies; from v14, Codex reviewed the patches
   adversarially. The loop applied the patch, tagged the source in git and rendered the new
   version. `pipeline/build.py` turns three tables (shots, dialogue, captions) into a graded,
   captioned 1080p24 master, and `pipeline/patches/` holds the edit's history as code.
2. **Gate.** Protected sections had to stay bit-identical, a WCAG 2.3.1 flash-safety check had to
   pass, the audio had to be identical or change only where intended, and the file had to be
   exactly 2,100 frames. `pipeline/loop/promote.py` decodes the whole file and writes the
   sha256-pinned manifest.
3. **Critics.** A senior-editor critic gave ten scores and the fixes that would help most. A blind
   A/B judge compared unlabelled frame strips of the new version and the current best, section by
   section, against a fixed rubric (`pipeline/ab_rubric.md`). Crowd and first-time-viewer critics,
   Codex as a second critic, and scripts measuring loudness, dialogue clarity and frames added to
   the record.
4. **Promote or keep.** The blind A/B decided keep or revert, with every exception logged. From
   v17 on, the director's picks counted too. State lived in a `PROGRESS.md` memory file (the
   current best, the score table, the backlog, every instruction from the director), so the loop
   could resume after each context compaction.

The director's role, from the run log: he set the 24-hour budget and what counts toward it, and
approved the tools and the plateau rule. He caught two audio faults by ear that the measurements
missed (a dropout at 0:33 and a late music entry at 1:02) and approved the fixes by ear. He
rejected the early overlays as looking cheap, which led to the 1969-hardware HUD. He made five
recorded picks: three blind audio pairs on v24 (one change adopted), the v25 Earth-to-Moon hero
shot and the v27 slow-motion (`fct_director_picks`). The loop prompt is in
[`prompts/moonshot_loop_prompt.md`](prompts/moonshot_loop_prompt.md).

## What the analytics layer measures

[`analytics/`](analytics/README.md) turns the run's transcripts, QC files and critic reports into
15 metadata-only CSVs (no message text, prompts or tool outputs), committed in
`analytics/data/raw/`. A dbt + DuckDB project models them:

- **Staging (15 models):** one per raw table, renamed and cast.
- **Intermediate (8):** grain changes, for example A/B votes rolled up to one row per comparison.
- **Core (18):** dimensions including versions, critics, models, agent roles and loop phases;
  facts including LLM requests, critic scores, A/B votes, audio QC, director picks, Codex
  requests and the v1-against-v28 review.
- **Marts (7):** the version scorecard, the critic plateau (the chart above), critic reliability,
  run accounting by loop phase and by agent role, token usage, and a 15-minute run timeline.

The project has 4 seeds, 48 models and 554 data tests: `not_null` and `unique` on every grain,
`relationships` on every foreign key, `accepted_values` on every enum, score and token ranges, a
header contract on each source file, and 15 singular tests that reconcile models against each
other and check business rules (for example, the final version must be the one `BEST.json`
names). The last build passed 605 of 606 nodes with 1 warning and 0 errors. The warning is
deliberate: Gemini Flash is flagged as a critic that doesn't separate versions, but the evidence
for that is in the run log, because the stored v18 file is a retry that overwrote the first run.

The ingest step (`reconcile.py`) compares source and target row counts on every run and logs them
to `analytics/data/reconciliation_log.csv`. The warehouse's data-quality findings, such as the
ledger and the transcript disagreeing about loop time, are written up in
[`analytics/warehouse/README.md`](analytics/warehouse/README.md).

## How to run

**Analytics.** This works from a clean clone, on the committed CSVs. It needs
[uv](https://docs.astral.sh/uv/); dependencies are pinned in `analytics/pyproject.toml` (Python
3.13+, dbt-core 1.12.5, dbt-duckdb 1.11.0).

```bash
cd analytics/warehouse
export DO_NOT_TRACK=1 DBT_SEND_ANONYMOUS_USAGE_STATS=False PYTHONUTF8=1
uv run dbt build --full-refresh                                  # 4 seeds, 48 models, 554 tests
cd ..
uv run python dashboard/build_dashboard.py                       # dashboard/site/index.html
uv run python reports/build_run_accounting.py --out run_accounting.md
```

Re-running the ingest (`uv run python ingest/reconcile.py`) needs the original transcripts and
export folder, which are not public; `analytics/.env.example` lists the paths it expects.

**The trailer pipeline.** Rebuilding the cut needs local media and Blender 5.x, plus Python 3.11+
(numpy, Pillow, scipy) and ffmpeg 6+, and it was only run on Windows 11. The binary assets (NASA
media, pre-rendered Blender frames, the Sonniss effects) are not in the repo.
[`pipeline/ASSETS.md`](pipeline/ASSETS.md) lists each one with its recipe and hash,
`pipeline/fetch_assets.py` downloads the public ones, and `build.py` refuses to build if an
asset doesn't match its manifest. The exported pipeline was checked for syntax and leftover
personal paths, but not rebuilt from a clean checkout.

## Honest limits

- **The scores come from AI critics.** The senior-editor critic can't hear, so its sound score is
  a judgement from structure. Its scale also moved between reviews: it gave v17 8.0 in its own
  review and 7.0 when re-scoring it a version later. The v1-to-v28 table above is the one
  comparison made on a single scale in one sitting.
- **The ceiling is 7.5 against a trailer house's standard.** The critic's final review names the
  gap: act 3 isn't cut to the track (0.38 of cuts land on a beat), the sound ducks a
  public-domain recording instead of designing each hit, the soft 16 mm scans are carried as they
  are, there are six seconds of CG explainer in an archive trailer, and 8.7 s of black credit
  cards close it. Its stated causes: the edit lived in a frame compositor with no scrubbable
  timeline, so nothing was worked by ear; the assets are public-domain recordings, not a score
  written to the picture; and the budget was 24 hours.
- **Progress flattened.** The editor went from 8.0 at v14 (6.9 loop hours) to 9.5 at v28 (23.9
  loop hours): 17 more hours for 1.5 points.
- **Two video critics didn't work.** Gemini Flash and TwelveLabs did not separate versions
  (TwelveLabs gave v19 and v21 identical scores in all ten categories), so they were kept as data
  and left out of every promotion decision.
- **The final review gets two facts wrong:** it says no licensed effects library was used, and
  that a label collision on the ascent was still open. MAKING-OF corrects both.
- **Not done:** a viewer test with people, the critic reliability and position-bias studies
  (the harnesses in `analytics/studies/` are frozen but not run), a vertical teaser, cutdowns and
  a poster, and captions regenerated for the final timeline (the SRT and VTT files date from v16).
- **Token counts are partial.** 52% of requests never logged a final output count, so output
  tokens are a floor, and 97% of tokens are cache reads, which measure context size, not work.

## Credits and licences

- All footage, photographs and mission audio are NASA works, public domain in the US.
- **Not affiliated with or endorsed by NASA.** No NASA insignia is used. The trailer's end
  credits mark it as cut by an AI agent from NASA source material.
- Music: three Musopen public-domain recordings, Dvořák's "New World" finale and Largo and
  Beethoven's Egmont overture (Czech National Symphony Orchestra). Versions v2 to v12 used a
  recording of Holst's "Mars" whose arrangement had an unconfirmed copyright status; v13 replaced
  it, so only v13 and later are cleared on music.
- Sound effects: the Sonniss GDC 2024 bundle, used under its licence. The files are not in this
  repo: the licence forbids redistributing them or using them to train AI.
- Fonts: Anton and Bebas Neue (SIL OFL).
- Full sources and links: [CREDITS.md](CREDITS.md). Code and docs: MIT ([LICENSE](LICENSE)).

## More

- [MAKING-OF.md](MAKING-OF.md): the version-by-version history, what broke and what it taught,
  and the director's calls in detail.
- [analytics/README.md](analytics/README.md): the tables, the reconciliation checks and how the
  transcripts were cleaned.
- [RELATED-WORK.md](RELATED-WORK.md): a short search for similar agent-editing work (2026-10-07).
