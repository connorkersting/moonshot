# MOONSHOT run analytics

This folder turns the raw logs of the MOONSHOT run (one Claude Code agent loop that cut 28
versions of an Apollo 11 trailer, with critic subagents, blind A/B judges and Codex reviews)
into tidy, metadata-only tables, models them in dbt + DuckDB, and renders an offline dashboard
and a run-accounting report.

| Folder | What it is |
|---|---|
| `ingest/` | Parsers and `reconcile.py`: transcripts, QC files and critic reports to 14 CSVs in `data/raw/` |
| `warehouse/` | dbt + DuckDB project: staging, intermediate, core (dimensions and facts) and mart models, 531 data tests. See `warehouse/README.md` |
| `dashboard/` | `build_dashboard.py`: one static page (`site/index.html`) and the standalone plateau chart (`site/plateau.html`) |
| `reports/` | `build_run_accounting.py`: project-only tokens and time per phase, as Markdown |
| `studies/` | Frozen harnesses for the reliability and position-bias studies (not yet run) |

Numbers on this page are from the ingest run of **2026-10-09 01:19 EDT** (versions v1 to v28) (the transcript is live,
so a re-run picks up more). `data/raw/_reconciliation.txt` has the exact figures of the latest
run and `data/reconciliation_log.csv` keeps every run's source-vs-target counts.

## Run it

```bash
cd analytics
cp .env.example .env            # then fill in the five paths (the file is git-ignored)
export DO_NOT_TRACK=1 PYTHONUTF8=1
uv run python ingest/reconcile.py                          # snapshot -> parse twice -> recount -> checks
(cd warehouse && uv run dbt build --full-refresh)          # seeds, models, tests
uv run python dashboard/build_dashboard.py                 # site/index.html, site/plateau.html, plateau PNG
uv run python reports/build_run_accounting.py              # run_accounting.md
```

`reconcile.py` is the entry point. It copies the live transcripts into a temp folder (the main
transcript keeps growing while a session is open), runs both parsers on that snapshot into
`data/raw/`, runs them again into a temp folder and requires byte-identical output, recounts
tokens with separate code, and writes everything to `data/raw/_reconciliation.txt`. It exits 1
if any check fails. The parsers also run on their own:

```bash
uv run python ingest/parse_sessions.py    # transcripts -> agent_* / session_* / interventions / codex
uv run python ingest/parse_artifacts.py   # PROGRESS.md, BEST.json, run ledger, git tags, QC files, critic and judge reports
```

### Configuration

| Variable | Points to |
|---|---|
| `CLAUDE_PROJECT_DIR` | the Claude Code project folder that holds `<session>.jsonl` and `<session>/subagents/` |
| `MOONSHOT_SESSION_ID` | the transcript id |
| `MOONSHOT_WORK` | the run's working folder (git repo, `ab_key_*.json`, `qcN/aqcN/tqcN.txt`) |
| `MOONSHOT_EXPORTS` | the run's export folder (`PROGRESS.md`, `BEST.json`, `run_ledger.csv`, `versions/*.mp4`, `qc/vN/*.json`, `qc/ab_vN_vM/judge_sonnet.json`) |
| `CODEX_SESSIONS_DIR` | optional, Codex CLI session logs; empty skips `codex_requests.csv` |
| `SESSION_GAP_HOURS` | optional, idle gap that starts a new session part (default 3) |
| `ACTIVE_GAP_MINUTES` | optional, gap rule for active time (default 5) |

Shell variables override `.env`. `python-dotenv` is not installed, so `ingest/common.py` has a
ten-line loader with the same precedence. No personal path is written in tracked code; the
dashboard and the accounting report find their output folder through the same variables.

## Privacy

Outputs hold metadata only: timestamps, model ids, token counts, tool names, the short
descriptions given when subagents were spawned, scores, picks and audio measurements. Message
text, prompts, tool inputs and outputs are never written. Human messages are read only to
de-duplicate queued copies; their published `label` comes from the hand-written
`ingest/intervention_labels.csv` (97 rows). The run ledger's free-text note column is dropped
because it names people. Judge and critic reports are parsed in memory for their verdict and
score tables. `reconcile.py` scans every CSV for drive paths, home paths and e-mail addresses
and fails if it finds one.

## Tables (`data/raw/`)

Times are given twice: `*_utc` (ISO, `Z`) and `*_local` (America/New_York, with offset). The
transcripts store UTC.

| Table | Rows | Grain: one row = | Key |
|---|---:|---|---|
| `agent_messages.csv` | 4,972 | one provider request (LLM call) by the main agent or a subagent | `message_id` |
| `agent_spawns.csv` | 107 | one Agent tool call attempt in the main transcript | `spawn_id` |
| `subagents.csv` | 107 | one subagent invocation (one transcript file) | `subagent_id` |
| `session_parts.csv` | 3 | one session part (1 overnight run, 2 the 24-hour extension, 3 tool expansion and v22 to v28) | `session_part` |
| `session_events.csv` | 6 | one compaction or session-part start | `ts_utc` + `event` |
| `interventions.csv` | 97 | one human message or answer to the agent | `intervention_id` |
| `codex_requests.csv` | 491 | one Codex CLI request attributed to the run | `codex_session_id` + `request_seq` |
| `versions.csv` | 28 | one exported trailer version | `version` |
| `critic_scores.csv` | 363 | one version x critic x score category | `version` + `critic` + `category` |
| `ab_votes.csv` | 161 | one blind A/B judge pick for one section of one comparison | `evaluation_id` + `repeat_no` + `section_no` |
| `qc_sections.csv` | 250 | one loudness section of one version's audio QC | `version` + `section_no` |
| `qc_dialogue.csv` | 519 | one dialogue line of one version's audio QC | `version` + `line_no` |
| `loop_segments.csv` | 7 | one segment of the run ledger (the agent's own record of loop time) | `segment_id` |
| `director_picks.csv` | 5 | one pick the director made on a blind audition or side-by-side clip | `pick_id` |

### agent_messages

`message_id` is the provider message id; `request_id` is the API request id (asserted 1:1
with `message_id`). `agent_id` is `main` or the subagent id. `agent_role` buckets agents by
their spawn description: `main`, `builder` (patch writers, score composer, version builders),
`critic-editor` ("editor critique" and "editor review" descriptions), `ab-judge`, `crowd`
(mean-commenter and first-time-viewer reactions), `researcher` (fact-check, tool research,
report triage), `other` (thumbnails, dashboards, tool installs and vetting, corpora, the audit and
this analytics work).
Token columns are kept separate and never summed into each other: `input_tokens` (uncached
input), `cache_creation_tokens`, `cache_read_tokens`, `output_tokens`. `thinking_tokens` is a
subset of `output_tokens`. `tool_names` lists every tool call in order, `;`-separated.

### agent_spawns, subagents

`agent_spawns` comes from the Agent tool calls in the main transcript (`requested_model` is the
alias asked for: opus / sonnet / fable). `subagents` comes from the subagent transcript files
and their `.meta.json`; `spawn_id` there is the meta file's `toolUseId`, which links back to
`agent_spawns.spawn_id` (`spawn_linked`). `duration_s` is first to last request of that
subagent.

### session_parts

`wall_*` is first to last event of the part. `active_hours` follows one rule: take every
request start time from the main agent and all subagents together, sort them, and merge
neighbours no more than `ACTIVE_GAP_MINUTES` (5) apart into one interval; active time is the
summed interval length. Parallel subagents are counted once and never added up, and an isolated
request adds zero. A new part starts after an idle gap of more than `SESSION_GAP_HOURS` (3):
part 1 is 6.4 h wall and 4.6 h active, part 2 is 12.8 h and 8.3 h, part 3 is 13.8 h and 6.6 h as of
this refresh (and still growing, because this refresh is part of it).

### loop_segments

The run ledger (`run_ledger.csv`) lists the stretches of "loop time" the agent counted toward
its 24-hour budget. The ingest reads it into `loop_segments.csv` with the bounds in local and UTC
time and an `end_reason`; an empty end means the segment is still open. The dbt layer compares
the ledger with the transcript (see `warehouse/README.md`).

### interventions

`kind` is `instruction`, `approval` or `question`; `label` is a short neutral summary written by
hand; `source` says where the message was found (`queued_message`, `user_message`,
`ask_user_answer`); `n_chars` is its length. A new human message makes the row `unlabelled`
until a line is added to `ingest/intervention_labels.csv` (matched on timestamp, within 5 s), and
reconcile fails until then.

### versions

Version tags (`vN-src`, `vN-final`) exist from v5 on, because the git repo started then.
`export_time` is the mp4's file modification time, so a later copy would move it.
`progress_logged_time` is the time written next to the version in the PROGRESS.md score table
(the agent's own clock, which ran a few minutes off wall time). `is_best_final` comes from
`BEST.json` (written by `promote.py`), not from the `BEST:` line at the top of PROGRESS.md, which
was left at v17 while v21 was promoted. Loudness columns come from `qcN.txt`; `tqc_*` from the
tech-QC file (the click detector is noisy: thousands of candidates on every version, so every
version reads FAIL).

### critic_scores

One row per version x critic x category, so a critic that did not score a version has no rows
for it (never a zero). Sources by critic:

| `critic` | Source | Versions | Categories |
|---|---|---|---|
| `fable_editor` | editor subagent's hand-back report (v1 to v17); `qc/vN/fable_editor.json` (v18 to v24 and v26) | 21 | the ten rubric categories |
| `fable_editor_rescored` | the baseline score inside the next review's `fable_editor.json` | v17 to v23 and v25 | `overall` |
| `codex_critic` | `qc/vN/codex_critic.json` | v14, v15, v18 to v22 | ten |
| `gemini_flash` | `qc/vN/gemini_critic_run1.json` (the critique is a JSON string inside the API response) | v18, v20 | ten |
| `gemini_pro_web` | `qc/v14/gemini_web_critic.json` | v14 | ten |
| `twelvelabs` | `qc/vN/twelvelabs_critic_raw_run1.json` | v19, v21 | ten |
| `crowd_ftv` | `qc/vN/crowd_ftv.json` (v18 to v22); `ingest/crowd_scores_progress.csv` (v2, v4, v5, v7, v17: prose in PROGRESS.md, transcribed by hand) | 10 | `shareability`, `ai_slop_perception` (10 = reads as slop), `would_watch_to_end` (v18 on) |

The ten rubric categories are hook, pacing, variety, motion, type, color, sound, captions, story
and overall. `progress_md_score` is the same cell as transcribed into PROGRESS.md (editor only),
kept for comparison; `progress_md_flagged` marks cells that carried an asterisk or a note
("6.5*", "4.5 (measured)"). `source_kind` says where each score was read from and `note` carries
anything odd about it. Every JSON file is checked against the ten expected keys; a missing or
extra key stops the run.

### ab_votes

Joins each judge's verdict with `ab_key_vN_vM.json`, which records which version was shown as side
A or B (randomised per section). Verdicts come from `qc/ab_vN_vM/judge_sonnet.json` where it exists
(v18 to v28; the layout changed over the run and the integer-confidence layout from v23 on is
accepted too, see `warehouse/README.md` finding 16) and from the judge subagent's
hand-back report otherwise (a markdown table, or `N section | winner | confidence | reason`
lines). Where both exist the picks are compared; 4 of 4 comparable pairs agree 7 of 7. `side_picked`
is A, B or TIE; `version_picked` is NULL for a tie; `newer_outcome` is win / loss / tie for the
newer version. `confidence` is normalised to low / low-med / med / med-high / high
(`confidence_rank` 1 to 3). `score_A` and `score_B` are the judge's rubric totals where the verdict
had them. Every comparison ran once, so `repeat_no` is 1.

### qc_sections, qc_dialogue

Parsed from `aqcN.txt` (audio QC, v4 on). `ratio_db` is dialogue over bed (target at least
+10 dB); `whisper_recall` is the share of caption words Whisper heard in the final mix. The
dialogue line text is left out.

### codex_requests

From the Codex CLI's own session logs. A rollout counts toward the run if its working folder
contains `moonshot`, or if it ran in the craftapps project during a session part; rollouts from
other projects are dropped. The second rule is an upper bound (it can include unrelated work).
`input_tokens` includes `cached_input_tokens` (OpenAI convention, unlike Claude's).
`primary_used_pct` and `secondary_used_pct` are the 5-hour and weekly plan windows of the whole
account and are never used as a project cost. `workdir` keeps only the folder name.

## Reconciliation

Every run of `reconcile.py` compares source with target and appends the numbers to
`data/reconciliation_log.csv` (run time, check, source count, target count, delta, status). The
checks as of the 2026-10-09 01:19 run, all with a delta of zero:

| Check | Source | Target |
|---|---:|---|
| unique message ids in the transcript files vs `agent_messages` rows | 4,972 | 4,972 |
| subagent transcript files vs `subagents` rows | 107 | 107 |
| Agent tool calls in the main transcript vs `agent_spawns` rows | 107 | 107 |
| tokens per model and token type, recounted with separate code, vs the table (12 sums) | see log | equal |
| `ab_key` files x 7 sections vs `ab_votes` rows | 161 | 161 |
| critic JSON files vs `critic_scores` rows (6 critics) | per file | equal |
| exported mp4 files vs versions with an export time | 28 | 28 |
| `run_ledger.csv` rows vs `loop_segments` rows | 7 | 7 |
| `director_picks` rows: every clip of a blind audio audition key has a pick | 3 | 3 |

Other checks in the same run: both parsers run twice over one snapshot give byte-identical CSVs
(14 of 14); the declared key of every table is unique and not null; `BEST.json` names the one
version flagged `is_best_final` and its sha256 matches the promoted mp4; every human message has
a label; no drive paths, home paths or e-mail addresses in any output. The run **fails** on any
of these. It reports, without failing, the ledger-against-transcript differences and the stale
`BEST:` line in PROGRESS.md.

## How the transcripts were cleaned

- **Streaming duplicates.** One response is written as several JSONL lines, one per content
  block. Rows are de-duplicated on `message.id` (cross-checked against `requestId`). Input
  and cache counts repeat unchanged on every line and are asserted equal. Summing lines instead
  would inflate cache reads 2x to 7x depending on the model (see `_reconciliation.txt`): 11,859
  assistant lines in the transcripts are 4,972 requests (plus 2 client-written `<synthetic>`
  placeholder messages, which are not provider requests and are skipped).
- **Missing final usage.** Streaming lines carry a placeholder output count (about 1 to 100).
  Only the closing line, which has `stop_reason`, holds the real one. 2,580 of 4,972 requests (52%)
  never got a closing line written. For those, `output_tokens` is NULL, `usage_final` is false
  and `output_tokens_lower_bound` keeps the placeholder. Input and cache counts are complete
  for every request.
- **TTL breakdown.** The `cache_creation` 5m/1h split repeats `cache_creation_input_tokens`.
  It is ignored, never added on top.
- **Copies across files.** A message id that shows up in a second transcript file (resumed
  subagent, copied history) would be skipped. This run has none.
- **Compaction.** Three compactions are in `session_events` (07:38 EDT auto on 10-07, 23:05 EDT
  manual, and 16:36 EDT on 10-08). A summary record is a user record and carries no usage. The API call that produced the
  summary is not logged as a message, so its tokens are missing from `agent_messages`.
- **Schema drift.** An unknown key in `message.usage`, a changed QC table header, a judge
  report with no verdict in any known layout, a critic JSON whose score keys changed, a changed
  `run_ledger.csv` header, a duplicate version x critic x category, or a missing A/B key file stops
  the run with an error that names the source, the field, what was expected and what arrived. A
  subagent that hasn't reported yet is skipped with a warning.

## Known gaps and caveats

- The client's own `cost-state` record (written at the end of session 1) is the independent
  total for that session. Against it, input and cache tokens match exactly for Fable and Sonnet.
  Output tokens come in lower, because of the missing closing lines. Opus input and cache come in a
  little lower too, because of the compaction call and other calls that are not logged as messages.
  Haiku calls (web-fetch summaries, about 0.7M input tokens) appear only in `cost-state`.
- The transcript is live. A re-run picks up new rows, including this analytics work (the window after
  the last ledger segment). The snapshot in reconcile makes each run internally consistent, and
  `_reconciliation.txt` records when it ran.
- PROGRESS.md "CONNOR (direct)" notes are the agent's paraphrases (21). They are counted in the
  reconciliation but are not a source for `interventions` (97 from the transcript).
- Crowd scores for v2, v4, v5, v7 and v17 exist only as prose in PROGRESS.md and are transcribed
  into `ingest/crowd_scores_progress.csv`. Watch-to-end was first scored at v18.
- The Fable editor re-scored v17 as 7.0 when it reviewed v18, after giving it 8.0 in its own
  review. Scores from different reviews do not share one scale; the re-scores are kept as their
  own critic (`fable_editor_rescored`).
- The Gemini Flash v18 file in `qc/` is a retry that replaced the first run. The log says the first
  v18 run scored 6.5 overall, identical to v20 in all ten categories; the stored v18 scores 6.0.
- The `_critic_model` label the Gemini script wrote for v20 ("gemini-3.7-flash") differs from the
  model the API answered as ("gemini-3.8-flash"); the table records the answered model and notes
  the label.
- `qc3.txt` shows a 90 s / LRA 9.0 file, the same as the v2 measurements in PROGRESS.md. It is
  kept as parsed.
- Versions v3, v6, v12 and v13 have no editor critique: v3, v12 and v13 were judged by A/B only or
  accepted on measured parity, and v6 was reverted.
- A version appears as soon as any trace of it exists (a git tag, a QC file, an mp4), so an
  in-progress version shows up with only `src_tag_time` filled.
- From v22 the audio QC report no longer measures dialogue over bed ("no dlg/bed stems saved");
  `qc_dialogue` keeps the Whisper recall for those versions and leaves the ratio NULL.
- From v23 the blind judge gives an integer confidence with no rubric totals; it is stored as
  `confidence_raw` and the word-scale `confidence` stays NULL for those rows.
- The version tables go to v28, but the Fable editor has no review of its own for v25, v27 and v28
  (v25 was re-scored inside the v26 review; v27 and v28 had no fresh critic pass). Codex and the
  crowd were last run on v22.
- `director_picks` is a hand-written table (`ingest/director_picks.csv`): five picks, three of them
  mapped through a key file (the v24 blind audio audition) and two (the v25 hero clip, the v27
  slow-mo) recorded from PROGRESS.md because no key file was kept.
