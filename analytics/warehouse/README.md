# MOONSHOT run analytics: dbt warehouse

A dbt + DuckDB project that models the raw tables in `../data/raw/` (written by `../ingest/`)
into tested dimensions, facts and analysis-ready marts. The warehouse is a single local
DuckDB file, `moonshot.duckdb`, which is rebuilt from the CSVs on every run and is git-ignored.

## Run it

```bash
cd analytics/warehouse
export DO_NOT_TRACK=1 DBT_SEND_ANONYMOUS_USAGE_STATS=False PYTHONUTF8=1
uv run dbt build --full-refresh   # seeds, models and all tests, in DAG order
uv run dbt docs generate          # optional: lineage and column docs in target/
```

`profiles.yml` sits in this folder, so dbt finds it when run from here. Use `--full-refresh`
whenever a seed's columns change (the seed tables are otherwise reused and the load fails on the
new column count). To build against another snapshot of the raw CSVs:
`uv run dbt build --vars '{raw_data_dir: path/to/raw}'`. If `uv` cannot write to the system temp
folder on Windows, point `TMP` and `TEMP` at a folder inside `analytics/` (`.tmp/` is git-ignored).

Last build (2026-10-09, raw snapshot from reconcile run 01:19 EDT, versions v1 to v28): **4 seeds,
46 models, 531 data tests: PASS=580, WARN=1, ERROR=0** (581 nodes) in about 90 seconds. The one
warning is deliberate and explained under "Data-quality findings", item 8.

## DAG

```
sources (moonshot_raw, 14 CSVs read in place with read_csv and an explicit column list)
  |
  +-- stg_moonshot__<table>  x14            one per raw table: rename, cast, parse timestamps, build keys
  |
seeds: version_outcomes, agent_roles, score_categories, critics
  |
intermediate (grain changes)
  int_llm_requests_by_agent       <- stg agent_messages
  int_ab_comparison_results       <- stg ab_votes
  int_editor_scores_pivoted       <- stg critic_scores (Fable editor only)
  int_critic_scores_by_version    <- stg critic_scores (one column per critic)
  int_version_audio_summary       <- stg qc_sections + stg qc_dialogue
  int_version_effort_at_export    <- stg versions + stg loop_segments + stg agent_messages
  int_requests_in_loop_segments   <- fct_llm_requests + stg loop_segments
  int_loop_phase_activity         <- int_requests_in_loop_segments
  |
core
  dim_version          <- stg versions + seed version_outcomes + int_critic_scores_by_version + int_ab_comparison_results + int_version_effort_at_export
  dim_critic           <- seed critics + stg critic_scores
  dim_agent_role       <- seed agent_roles + stg subagents
  dim_model            <- distinct model ids from stg agent_messages, codex_requests, Fable critic scores, ab_votes
  dim_score_category   <- seed score_categories
  dim_session_part     <- stg session_parts
  dim_loop_phase       <- stg loop_segments + int_loop_phase_activity (a ledger segment or the gap between two)
  fct_llm_requests     <- stg agent_messages
  fct_agent_runs       <- stg subagents + stg agent_spawns + int_llm_requests_by_agent
  fct_critic_scores    <- stg critic_scores
  fct_director_picks   <- stg director_picks
  fct_ab_votes         <- stg ab_votes
  fct_version_audio    <- stg qc_sections
  fct_dialogue_lines   <- stg qc_dialogue
  fct_codex_requests   <- stg codex_requests + dim_session_part
  fct_interventions    <- stg interventions + dim_session_part
  fct_session_events   <- stg session_events
  |
marts
  mart_version_scorecard            <- dim_version + int_editor_scores_pivoted + int_ab_comparison_results + int_version_audio_summary
  mart_critic_plateau               <- fct_critic_scores + dim_score_category + dim_version + dim_critic
  mart_critic_reliability           <- fct_critic_scores + dim_score_category + dim_critic
  mart_run_accounting_by_phase      <- dim_loop_phase + int_requests_in_loop_segments + fct_llm_requests + fct_codex_requests + fct_interventions + dim_version
  mart_run_accounting_by_role       <- int_requests_in_loop_segments + fct_llm_requests + dim_model
  mart_token_usage_by_role_session  <- fct_llm_requests + dim_model
  mart_run_timeline                 <- fct_llm_requests + fct_codex_requests + fct_interventions + fct_session_events + fct_agent_runs + dim_session_part
```

Schemas in `moonshot.duckdb`: `staging` and `intermediate` (views), `core` and `marts`
(tables), `seeds`. The model for version history is `dim_version` (one row per version; the
singular name follows the other dimensions), joined to `fct_critic_scores` (one row per version x
critic x category).

## Grains

| Model | One row per | Key |
|---|---|---|
| `dim_version` | trailer version (v1 to v28): decision, reason, director's note, each critic's headline score, A/B result, loop hours at export | `version_id` |
| `dim_critic` | critic that scored versions, with the reliability flag | `critic_id` |
| `dim_agent_role` | agent role (main + six subagent roles) | `agent_role` |
| `dim_model` | model id seen anywhere in the run | `model_id` |
| `dim_score_category` | score category (ten rubric + three crowd) | `score_category` |
| `dim_session_part` | session part (1 overnight, 2 extension, 3 tool expansion) | `session_part` |
| `dim_loop_phase` | ledger segment or the gap between two segments | `loop_phase_id` |
| `fct_llm_requests` | Claude provider request (deduplicated message id) | `message_id` |
| `fct_agent_runs` | subagent run | `subagent_id` |
| `fct_critic_scores` | version x critic x score category | `critic_score_id` |
| `fct_ab_votes` | A/B evaluation x repeat x section | `ab_vote_id` |
| `fct_director_picks` | one pick the director made on a blind audition or side-by-side clip | `director_pick_id` |
| `fct_version_audio` | version x loudness section | `version_section_id` |
| `fct_dialogue_lines` | version x dialogue line | `dialogue_line_id` |
| `fct_codex_requests` | Codex session x request sequence | `codex_request_id` |
| `fct_interventions` | human message or answer | `intervention_id` |
| `fct_session_events` | session-part start or compaction | `session_event_id` |
| `int_llm_requests_by_agent` | agent (main or subagent) | `agent_id` |
| `int_ab_comparison_results` | A/B comparison | `evaluation_id` |
| `int_editor_scores_pivoted` | version with a Fable editor critique | `version_id` |
| `int_critic_scores_by_version` | version that any critic scored | `version_id` |
| `int_version_audio_summary` | version with audio QC | `version_id` |
| `int_version_effort_at_export` | exported version | `version_id` |
| `int_requests_in_loop_segments` | Claude request, placed in a loop phase | `message_id` |
| `int_loop_phase_activity` | loop phase with requests | `loop_phase_id` |
| `mart_version_scorecard` | version | `version_id` |
| `mart_critic_plateau` | version x critic x headline category | `plateau_point_id` |
| `mart_critic_reliability` | critic | `critic_id` |
| `mart_run_accounting_by_phase` | loop phase | `loop_phase_id` |
| `mart_run_accounting_by_role` | loop phase x agent role x model | `phase_role_model_id` |
| `mart_token_usage_by_role_session` | agent role x session part x model | `role_session_model_id` |
| `mart_run_timeline` | 15-minute bucket, first to last activity, idle gap included | `bucket_start_utc` |

Composite grains get a text key built in staging (for example
`critic_score_id = v14-codex_critic-overall`), and the raw composite key is checked on the
source with the custom `unique_combination` test.

## Tests

| Layer | Tests | What they cover |
|---|---:|---|
| Sources | 58 | `not_null` + `unique` on every primary key (composite keys via `unique_combination`), plus a `csv_header_matches` schema contract per file |
| Seeds | 20 | keys and the decision, category and critic enums |
| Staging | 28 | grain only: `not_null` + `unique` on the key as staging names it |
| Intermediate | 28 | the new grain of each model, plus one-comparison-per-version and one-editor-per-version guards |
| Dimensions | 77 | grain, enums, ranges, relationships between versions |
| Facts | 190 | grain, `relationships` on every foreign key, `accepted_values` on every enum, score and token ranges |
| Marts | 116 | grain, relationships, enums, score and share ranges |
| Singular | 14 | cross-model reconciliation and business rules (below) |
| **Total** | **531** | |

By type: 239 `not_null`, 65 `unique`, 7 `unique_combination`, 47 `accepted_values`,
41 `relationships`, 39 `value_in_range`, 65 `non_negative`, 14 `csv_header_matches`, 14 singular.

Custom generic tests (`tests/generic/`): `unique_combination`, `value_in_range` (scores 1 to
10, shares 0 to 1, correlations -1 to 1), `non_negative` (tokens, durations, hours), and
`csv_header_matches`.

Singular tests (`tests/`):

- `assert_llm_requests_reconcile_to_source`: request count and every token sum per model
  match from raw CSV to `fct_llm_requests` to `mart_token_usage_by_role_session`.
- `assert_agent_runs_reconcile_to_subagents_file`: per-run totals rebuilt from request rows
  match the totals the ingest wrote into `subagents.csv`, run by run.
- `assert_session_part_request_counts_match`: request counts per session part match
  `session_parts.csv`.
- `assert_run_timeline_reconciles`: the timeline buckets sum to the fact tables (requests,
  tokens, Codex requests, interventions, compactions), so no event falls outside the range.
- `assert_loop_phases_reconcile_to_facts`: the loop-phase accounting marts sum to the fact
  tables (Claude requests and tokens, Codex requests, human messages, exported versions), so a
  phase boundary that overlapped or left a hole fails.
- `assert_active_hours_not_above_wall_hours`: active time per phase never exceeds the time
  between its first and last request.
- `assert_ab_pick_matches_side`: picked version, tie flag and outcome all follow from the
  side picked and the randomised side assignment.
- `assert_one_final_version_matching_best_json`: exactly one FINAL version, and it is the one
  `BEST.json` names.
- `assert_critic_score_categories_complete`: every rubric critic has all ten categories per
  version, the crowd two or three, a Fable re-score one.
- `assert_dim_version_scores_match_fact`: every per-critic column on `dim_version` equals the
  fact row it was pivoted from, and no fact row is missing from it.
- `assert_discriminating_critics_have_distinct_scores`: a critic flagged as discriminating never
  gives two different versions the identical score vector. A critic that scores one category
  per version (the Fable re-score, 'overall' only) is left out, because two versions sharing a
  half-point score is expected there.
- `assert_non_discriminating_flag_is_visible_in_scores` (**warn**): a critic flagged as not
  discriminating should show it in the stored scores (see finding 8).
- `assert_agent_runs_ran_requested_model`: each subagent ran the model family it was asked for;
  a subagent spawned with no model (`inherit`) must have run a family the main agent used.
- `assert_interventions_are_labelled`: no human message is missing its hand-written label.

### Schema contracts on the raw files

Each source is read with `read_csv(..., auto_detect = false, strict_mode = true, columns = {...})`
and an explicit type for every column (IDs and timestamps as VARCHAR). An added or dropped
column changes the field count and the read fails ("Expected Number of Columns: 8 Found: 9").
A renamed or reordered column with the same field count would load silently under the wrong
name, so `csv_header_matches` reads the header line and fails with the source name, the
expected list, the arrived list, and the added and missing columns. Both guards were checked
against a doctored copy of the raw folder (one renamed header, one extra column): both failed
as intended. The ingest side has the same contract for what it reads: a changed critic JSON
key set, ledger header, PROGRESS.md score header or judge layout stops the run (see
`../README.md`).

## What the version-history models answer

- **`dim_version`** carries, for each of v1 to v28, whether it was promoted (`is_promoted`) and
  why (`decision_reason`), the director's note that shaped it (`director_input`, v17, v19 to v27),
  the Fable editor's overall score, the Codex, Gemini Flash, Gemini Pro (app) and TwelveLabs
  overall scores where they exist, the crowd's shareability, slop and watch-to-end scores, the
  blind A/B result against the version it was compared with, and the ledger loop hours and
  project tokens spent by its export.
- **`fct_critic_scores`** has every category score of every critic (363 rows).
- **`fct_director_picks`** has the five picks the director made on blind auditions and
  side-by-sides (v24 audio, the v25 hero beat, the v27 slow-mo), the audio ones mapped through
  their key file.
- **`mart_critic_plateau`** is the chart table: score per version per critic with the promotion
  mark, the director's-note mark and the effort at export. `../dashboard/` draws it.
- **`mart_critic_reliability`** measures how far each critic's scores move between versions and
  whether two versions share a full score vector.
- **`mart_run_accounting_by_phase`** and `_by_role` are the project-only token and time
  accounting; `../reports/build_run_accounting.py` writes them up.

## Data-quality findings and how they were handled

1. **Run with no finalised output (fixed in the models).** The ingest's own subagent
   (role `other`, part 2) had 54 requests and none with a closing usage line. `subagents.csv`
   records its output as NULL; the first draft of `fct_agent_runs` summed it to 0. The
   reconciliation test caught the difference. Output sums are now NULL when no request in the
   group was finalised (unknown, not zero), in `int_llm_requests_by_agent`, `fct_agent_runs`
   and the token marts; the `not_null` tests on those columns apply only where
   `requests_usage_final > 0`. `total_tokens_known` still adds the input side, which is
   complete for every request.
2. **Missing final usage (documented).** 2,580 of 4,972 requests (52%) have NULL
   `output_tokens` (at the first refresh, 1,821 of 3,643). It is concentrated in subagents (the
   main agent has a final usage record on 99.9% of requests, builders about 22%, researchers
   about 5%, at the first refresh). Output-token figures for
   subagents are therefore floors; the streamed placeholders are kept in
   `output_tokens_unfinalised_lower_bound` and never added to the known total. The first ingest
   run found 459 of 1,302 (35%); PROGRESS.md quotes 447.
3. **Section label drift in audio QC (documented).** Section 3 of `qc_sections` is called
   "act 2 stats/chart" up to v7 and "act 2 stats/ascent" from v8. The section number is stable,
   so models key on `section_no` and keep the label as text.
4. **Identical audio QC for v5/v6 and v11/v12 (documented, not treated as an error).** Every
   dialogue line matches to the decimal, and so do integrated loudness and LRA. PROGRESS.md
   describes both steps as picture work, so an unchanged mix is plausible. v17 to v21 also share
   their loudness figures (-13.8 LUFS, LRA 8.1), and every version from v22 on that has a QC file is -13.8 LUFS. This was not
   checked against the audio files themselves.
5. **Agent-type suffix (cleaned in staging).** `agent_spawns.subagent_type` holds both
   "general-purpose" and "general-purpose (default)"; staging strips the suffix into
   `is_default_subagent_type` so the type has one value.
6. **Keep decisions that disagree with the A/B tally (surfaced, by design).** v10 and v11
   were kept although each lost its blind A/B 0-2; v17 was promoted on a 1-1 tie as a logged
   override. `mart_version_scorecard.ab_agrees_with_decision` is false for exactly v10 and v11
   (a tie counts as agreeing).
7. **The Fable editor's scale moves between reviews (surfaced).** It gave v17 an 8.0 in its own
   review and re-scored v17 as 7.0 when reviewing v18 "on the same evidence"; v18 was 7.5, then
   8.0 when re-scored in the v19 review. Read as a series, the raw scores dip at v18 (8.0 to 7.5)
   although v18 beat v17. The re-scores are kept as a separate critic (`fable_editor_rescored`)
   and drawn as a dotted line on the plateau chart.
8. **The Gemini reliability claim rests on a file that was overwritten (surfaced, warned).**
   PROGRESS.md says Gemini Flash gave v20 exactly the scores of v18 (overall 6.5, all ten
   categories). The stored v18 file is a later retry (overall 6.0, nine of ten categories
   differ from v20). So the stored data shows a 0.5 difference between versions and a 0.5
   difference between two runs on the same video: the critic does not separate versions, but the
   "identical scores" evidence is in the log, not in the data. TwelveLabs does show it (v19 and
   v21 identical in all ten categories, overall 8.8, off the half-point scale). The `critics`
   seed flags both as non-discriminating with this note, and
   `assert_non_discriminating_flag_is_visible_in_scores` warns for Gemini Flash.
9. **The crowd critic is coarse (surfaced).** It scored v18, v19 and v20 identically (6 / 4 / 6)
   despite a HUD redesign, and v4 and v17 share a vector. It is flagged non-discriminating in the
   seed.
10. **PROGRESS.md named the wrong BEST (fixed at the source of truth).** At the first refresh
    its header said `BEST: v17` while `BEST.json` said v21 (sha256 verified against the promoted
    mp4); at the v28 refresh the two agree. The warehouse reads `BEST.json`, and
    `assert_one_final_version_matching_best_json` replaces the old PROGRESS.md comparison.
11. **The ledger and the transcript disagree about loop time (surfaced).** The ledger opens
    segment 2 at 17:45 while the transcript shows work from 17:25 (the 24-hour request arrived at
    17:09), closes it at 19:47 while the chain of requests runs to 20:01, and exported v16 at 19:57
    inside what the ledger calls a pause. Between segments the transcript holds about 14% of all
    requests. `dim_loop_phase` keeps the gaps as phases so neither number hides the other.
12. **Role and format drift in later versions (fixed).** "Fable editor review of vN" (v18 to v21)
    did not match the bucketing rule for editor critiques and fell into role `other`; the rule now
    accepts "review". The blind judge wrote its verdicts in four layouts across the run (a markdown
    table, plain `N section | winner | confidence |` lines, and two JSON layouts), and one hand-back has no verdict at all. The ingest failed loudly on the first unknown
    layout (v19 vs v18) and on the next one (v17 vs v14, plain lines), and now accepts all four,
    preferring `judge_sonnet.json` and comparing it with the hand-back where both parse.
13. **Model label mismatch (documented).** The Gemini script labelled the v20 run
    "gemini-3.7-flash" while the API response says "gemini-3.8-flash". The table keeps the
    answered model and records the label in `note`.
14. **v13 has no scores of any kind.** It was accepted as a required rights fix on measured audio
    parity, with no editor pass and no A/B; `decision_basis = required_fix`.
15. **Audio QC stops measuring dialogue-to-bed from v22 (documented).** The report says "no dlg/bed
    stems saved for this version; ratio skipped". `qc_dialogue` rows for v22 to v28 come from the
    Whisper table, so `dialogue_to_bed_db` and `meets_10db_target` are NULL there (154 rows,
    tested only where a ratio exists). The Whisper recall for "Staging." and "And ignition." reads
    0.00 in these reports. A later check with corrected windows found "And ignition." at full
    recall (the old windows had missed it) and "Staging." still at 0.00 (Whisper hears "Stay
    tuned"); the director listened and kept both lines.
16. **The blind judge's layout changed again at v23 (fixed).** It now writes `pick` and an
    integer `confidence` (1 to 5) with no rubric totals. The scale is not documented (a 2 was
    called "weak" in its report), so the integer is stored as `confidence_raw` and the word-scale
    `confidence` stays NULL for those rows, with a test that exactly one of the two is present.
    The A/B confident-win counts in `int_ab_comparison_results` therefore cover the older layouts
    only.
17. **Subagents spawned without a model (fixed).** From the v23 builders on, five subagents have
    no model in their meta file. They are recorded as `inherit` and checked against the families
    the main agent used, instead of failing the requested-model test.
18. **Client-written placeholder messages (fixed in the reconciliation).** Two assistant records
    with model `<synthetic>` (not provider requests) appeared in the transcript. The ingest skips
    them, and the independent recount now skips and reports them, so the row counts agree.
19. **v25, v27 and v28 have no editor review of their own.** v25 was re-scored 9.5 inside the v26
    review; v27 and v28 were promoted on the director's picks and gates, with no fresh critic
    pass. v28 has a blind A/B against v27: seven ties.

## Design choices and deviations

- **Sources, not seeds, for the raw CSVs.** The files are read in place, so a re-run of the
  ingest is picked up without copying data into `seeds/`. Seeds hold only hand-maintained
  reference data: `version_outcomes` (the decision, its reason and the director's note, from
  PROGRESS.md prose), `critics` (what each critic perceives and whether it separates versions),
  `score_categories` and `agent_roles`.
- **`version_outcomes` seed.** The keep or revert decision exists only in PROGRESS.md prose,
  so it is recorded once, by hand, in a 28-row seed. Everything else about a version is
  derived. A version without a row is `in_progress` until it is exported; an exported version
  without a row fails `not_null` on `dim_version.outcome`, which is the prompt to record the
  decision. The FINAL version must be the one `BEST.json` names or
  `assert_one_final_version_matching_best_json` fails. v12 is now `kept` (it was FINAL until v13).
- **Version keys.** IDs are text (`version_id = 'v12'`); `version_number` keeps the integer for
  ordering. `session_part` is cast to INTEGER because it is a three-value ordinal.
- **Staging naming.** `stg_moonshot__<table>` (source system, double underscore, table name).
- **Marts.** The `mart_` models sit in their own schema on top of the core star. They are tested
  to the same standard as the facts.
- **Loop hours.** `loop_hours_at_export` counts ledger segments only. "Project tokens" at an
  export is every Claude request up to then (all agents, input + cache + known output), so it
  includes research and tooling and is about 98% cache reads; read it as a measure of how much
  context was re-read, not of trailer work.
- **Staging tests overlap with source tests where the key is a plain rename** (for example
  `message_id`). Source tests guard the file; staging tests guard the keys staging builds
  (`version_id`, the composite text keys). Both are kept because the brief asks for grain
  tests at both layers.
- **No dollar costs.** The data has no prices for these model ids, so token figures are
  reported as tokens ("API-equivalent, not billed"). Haiku calls (web-fetch summaries) appear
  only in the client's cost record, not in the transcripts, so `dim_model` has no Haiku row.
- **Account-wide plan percentages are never a project cost.** `fct_codex_requests` keeps the
  5-hour and weekly plan percentages the Codex logs record, but no model or report uses them.
