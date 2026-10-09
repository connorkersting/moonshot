"""Build the raw tables from a frozen snapshot and reconcile them.

Run from the analytics/ folder:  uv run python ingest/reconcile.py

Steps
  1. Snapshot the live sources (the main transcript keeps growing while a
     session is open) into a temp folder that is deleted afterwards.
  2. Run parse_sessions.py and parse_artifacts.py on the snapshot into
     data/raw/, then a second time into a temp folder, and require
     byte-identical CSVs (idempotence).
  3. Recount tokens straight from the snapshot JSONL with separate, simpler
     code and compare with agent_messages.csv: per file, per model, before
     and after de-duplication.
  4. Grain, linkage, coverage and privacy checks, plus the critic-source, promotion and
     loop-ledger checks added with the version-history tables.
Everything is printed and written to data/raw/_reconciliation.txt. The source-vs-target
counts and sums are also appended to data/reconciliation_log.csv, one row per check per run,
so a past reconciliation can be looked up.
Exit code 1 if any check FAILs.
"""

from __future__ import annotations

import csv
import filecmp
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

from common import ANALYTICS_DIR, LOCAL_TZ, RAW_DIR, load_dotenv, parse_ts, require_dir, session_id

INGEST_DIR = Path(__file__).resolve().parent
TABLES = [
    "agent_messages.csv", "agent_spawns.csv", "subagents.csv", "session_parts.csv",
    "session_events.csv", "interventions.csv", "codex_requests.csv", "versions.csv",
    "critic_scores.csv", "ab_votes.csv", "qc_sections.csv", "qc_dialogue.csv", "loop_segments.csv",
    "director_picks.csv",
]
GRAIN = {
    "agent_messages.csv": ["message_id"],
    "agent_spawns.csv": ["spawn_id"],
    "subagents.csv": ["subagent_id"],
    "session_parts.csv": ["session_part"],
    "interventions.csv": ["intervention_id"],
    "codex_requests.csv": ["codex_session_id", "request_seq"],
    "versions.csv": ["version"],
    "critic_scores.csv": ["version", "critic", "category"],
    "loop_segments.csv": ["segment_id"],
    "director_picks.csv": ["pick_id"],
    "ab_votes.csv": ["evaluation_id", "repeat_no", "section_no"],
    "qc_sections.csv": ["version", "section_no"],
    "qc_dialogue.csv": ["version", "line_no"],
}
TOKENS = ["input_tokens", "output_tokens", "cache_creation_tokens", "cache_read_tokens"]
MSG_DTYPES = {
    "message_id": "string", "request_id": "string", "session_id": "string",
    "agent_id": "string", "is_subagent": "boolean", "agent_role": "string",
    "model": "string", "ts_utc": "string", "ts_local": "string", "session_part": "Int64",
    "input_tokens": "Int64", "output_tokens": "Int64", "output_tokens_lower_bound": "Int64",
    "usage_final": "boolean", "cache_creation_tokens": "Int64",
    "cache_read_tokens": "Int64", "thinking_tokens": "Int64", "stop_reason": "string",
    "tool_names": "string", "n_tool_calls": "Int64", "n_jsonl_lines": "Int64",
}


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0
        self.rec_rows: list[tuple] = []

    def __call__(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def count(self, name: str, source: int | float, target: int | float, tolerance: float = 0.0) -> None:
        """Record a source-vs-target number, print the delta, and fail if it exceeds the tolerance."""
        delta = target - source
        ok = abs(delta) <= tolerance
        self.rec_rows.append((name, source, target, delta, "PASS" if ok else "FAIL"))
        self.check(f"{name}", ok, f"source {source:,} / target {target:,} / delta {delta:+,}")

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        if not ok:
            self.failures += 1
        self(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}")


def snapshot(tmp: Path) -> dict[str, str]:
    """Copy the live sources into tmp; return env overrides pointing at the copy."""
    sid = session_id()
    project = require_dir("CLAUDE_PROJECT_DIR")
    snap_project = tmp / "claude_project"
    (snap_project / sid).mkdir(parents=True)
    shutil.copy2(project / f"{sid}.jsonl", snap_project / f"{sid}.jsonl")
    for src in (project / sid).rglob("agent-*"):
        if src.suffix in (".jsonl", ".json"):
            dest = snap_project / sid / src.relative_to(project / sid)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    env = {"CLAUDE_PROJECT_DIR": str(snap_project)}
    codex = os.environ.get("CODEX_SESSIONS_DIR", "").strip()
    if codex and Path(codex).is_dir():
        # only rollouts dated on the run's days (filename carries the local date)
        with (project / f"{sid}.jsonl").open(encoding="utf-8") as fh:
            first = parse_ts(json.loads(next(l for l in fh if '"timestamp"' in l))["timestamp"])
        days = {first.astimezone(LOCAL_TZ).date().isoformat()}
        days |= {datetime.now(LOCAL_TZ).date().isoformat()}
        snap_codex = tmp / "codex"
        for src in Path(codex).rglob("rollout-*.jsonl"):
            if src.name[8:18] >= min(days) and src.name[8:18] <= max(days):
                dest = snap_codex / src.relative_to(codex)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        env["CODEX_SESSIONS_DIR"] = str(snap_codex)
    return env


def run_parsers(env_over: dict[str, str], out_dir: Path) -> None:
    env = {**os.environ, **env_over, "ANALYTICS_RAW_DIR": str(out_dir), "PYTHONUTF8": "1"}
    for script in ("parse_sessions.py", "parse_artifacts.py"):
        subprocess.run([sys.executable, str(INGEST_DIR / script)], env=env, check=True, cwd=INGEST_DIR)


def recount(project: Path, sid: str) -> dict:
    """Independent token recount, straight from the JSONL (no shared code)."""
    files = [("main", project / f"{sid}.jsonl")]
    files += [(p.stem.replace("agent-", ""), p) for p in sorted((project / sid).rglob("agent-*.jsonl"))]
    per_file = {}
    for agent, path in files:
        lines = asst = 0
        naive = defaultdict(int)
        best: dict[str, dict] = {}
        synthetic: set[str] = set()
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                lines += 1
                rec = json.loads(line)
                if rec.get("type") != "assistant":
                    continue
                asst += 1
                msg = rec["message"]
                u = msg.get("usage") or {}
                vals = {
                    "input_tokens": u.get("input_tokens") or 0,
                    "output_tokens": u.get("output_tokens") or 0,
                    "cache_creation_tokens": u.get("cache_creation_input_tokens") or 0,
                    "cache_read_tokens": u.get("cache_read_input_tokens") or 0,
                }
                for k, v in vals.items():
                    naive[(msg.get("model"), k)] += v
                if msg.get("model") == "<synthetic>":
                    # client-written placeholder (for example an API error notice), no provider request;
                    # parse_sessions skips these too, so they are counted apart, not as requests
                    synthetic.add(msg["id"])
                    continue
                cur = best.setdefault(msg["id"], {"model": msg.get("model"), **{k: 0 for k in vals}})
                for k, v in vals.items():
                    cur[k] = max(cur[k], v)
        dedup = defaultdict(int)
        for m in best.values():
            for k in TOKENS:
                dedup[(m["model"], k)] += m[k]
        per_file[agent] = {"lines": lines, "assistant_lines": asst, "unique_ids": len(best),
                           "n_synthetic": len(synthetic), "ids": set(best), "naive": naive, "dedup": dedup}
    return per_file


def cost_state_snapshot(path: Path) -> tuple[dict, str | None]:
    """The transcript's cost-state record (written by the client) and the last timestamp before it."""
    last_ts = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("type") == "cost-state":
                return rec.get("modelUsage") or {}, last_ts
            if "timestamp" in rec:
                last_ts = rec["timestamp"]
    return {}, None


def main() -> None:
    load_dotenv()
    log = Log()
    log(f"MOONSHOT ingest reconciliation, run {datetime.now(LOCAL_TZ).isoformat(timespec='seconds')}")
    sid = session_id()
    tmp = Path(tempfile.mkdtemp(prefix="moonshot_recon_"))
    try:
        env_over = snapshot(tmp)
        run_parsers(env_over, RAW_DIR)
        second = tmp / "run2"
        run_parsers(env_over, second)

        log("\n== 1. idempotence (two runs over the same snapshot)")
        for t in TABLES:
            same = (second / t).exists() and filecmp.cmp(RAW_DIR / t, second / t, shallow=False)
            log.check(f"byte-identical {t}", same)

        dfs = {t: pd.read_csv(RAW_DIR / t, dtype=MSG_DTYPES if t == "agent_messages.csv" else None,
                              keep_default_na=True) for t in TABLES}
        msgs = dfs["agent_messages.csv"]

        log("\n== 2. row counts per table")
        for t in TABLES:
            log(f"  {t:22s} {len(dfs[t]):6d}")

        log("\n== 3. grain (declared key is unique and not null)")
        for t, key in GRAIN.items():
            df = dfs[t]
            ok = not df.duplicated(key).any() and not df[key].isna().any().any() if len(df) else True
            log.check(f"{t} unique on {key}", ok)

        log("\n== 4. token recount from source JSONL (independent code path)")
        rc = recount(Path(env_over["CLAUDE_PROJECT_DIR"]), sid)
        total_lines = sum(f["lines"] for f in rc.values())
        total_asst = sum(f["assistant_lines"] for f in rc.values())
        total_ids = sum(f["unique_ids"] for f in rc.values())
        log(f"  source files: {len(rc)} (1 main + {len(rc) - 1} subagent)")
        log(f"  JSONL lines: {total_lines}; assistant lines: {total_asst}; unique message ids: {total_ids}")
        total_synth = sum(f["n_synthetic"] for f in rc.values())
        log(f"  dedupe delta: {total_asst - total_ids - total_synth} assistant lines were repeat chunks of an earlier line")
        log(f"  excluded: {total_synth} client-written '<synthetic>' placeholder message(s), not provider requests")
        all_ids = [i for f in rc.values() for i in f["ids"]]
        log.check("no message id appears in two transcript files", len(all_ids) == len(set(all_ids)),
                  f"{len(all_ids) - len(set(all_ids))} shared ids")
        log.count("agent_messages rows vs unique message ids in source", total_ids, len(msgs))
        log.count("subagents rows vs subagent transcript files", len(rc) - 1, len(dfs["subagents.csv"]))
        main_spawn_ids: set[str] = set()
        with (Path(env_over["CLAUDE_PROJECT_DIR"]) / f"{sid}.jsonl").open(encoding="utf-8") as fh:
            for line in fh:
                if '"name":"Agent"' not in line and '"name":"Task"' not in line:
                    continue
                rec = json.loads(line)
                if rec.get("type") != "assistant":
                    continue
                for block in rec["message"].get("content") or []:
                    if block.get("type") == "tool_use" and block.get("name") in ("Agent", "Task"):
                        main_spawn_ids.add(block["id"])
        log.count("agent_spawns rows vs Agent tool calls in the main transcript", len(main_spawn_ids), len(dfs["agent_spawns.csv"]))
        bad = []
        for agent, f in rc.items():
            sub = msgs[msgs["agent_id"] == agent]
            if len(sub) != f["unique_ids"]:
                bad.append(f"{agent}: rows {len(sub)} vs ids {f['unique_ids']}")
            for (model, k), v in f["dedup"].items():
                col = "output_tokens_lower_bound" if k == "output_tokens" else k
                got = int(sub.loc[sub["model"] == model, col].fillna(0).sum())
                if got != v:
                    bad.append(f"{agent}/{model}/{k}: table {got} vs recount {v}")
        log.check("per-file, per-model token sums match recount", not bad, "; ".join(bad[:5]))
        recount_totals: dict[tuple, int] = defaultdict(int)
        for f in rc.values():
            for key, v in f["dedup"].items():
                recount_totals[key] += v
        for (model, k), v in sorted(recount_totals.items()):
            col = "output_tokens_lower_bound" if k == "output_tokens" else k
            log.count(f"{model} {k} (money column: recount vs table)", v, int(msgs.loc[msgs["model"] == model, col].fillna(0).sum()))

        log("\n  tokens by model: before dedupe (naive line sum) vs after dedupe (table)")
        naive_m: dict[tuple, int] = defaultdict(int)
        for f in rc.values():
            for key, v in f["naive"].items():
                naive_m[key] += v
        by_model = msgs.groupby("model")[TOKENS].sum()
        by_model["output_tokens"] = msgs.groupby("model")["output_tokens_lower_bound"].sum()
        for model, row in by_model.iterrows():
            log(f"  {model}")
            for k in TOKENS:
                log(f"    {k:22s} naive {naive_m[(model, k)]:>14,d}   deduped {int(row[k]):>14,d}   "
                    f"inflation {naive_m[(model, k)] - int(row[k]):>13,d}")

        log("\n  client cost-state record vs table (informational; the record is a point-in-time "
            "snapshot and also counts calls not logged as transcript messages, e.g. compaction "
            "and web-fetch summarisation)")
        usage, cutoff = cost_state_snapshot(Path(env_over["CLAUDE_PROJECT_DIR"]) / f"{sid}.jsonl")
        if usage and cutoff:
            upto = msgs[msgs["ts_utc"] <= parse_ts(cutoff).strftime("%Y-%m-%dT%H:%M:%S.999Z")]
            log(f"  cost-state written after {cutoff}; table rows up to then: {len(upto)}")
            mapping = {"inputTokens": "input_tokens", "outputTokens": "output_tokens",
                       "cacheCreationInputTokens": "cache_creation_tokens", "cacheReadInputTokens": "cache_read_tokens"}
            for model, mu in sorted(usage.items()):
                parts = []
                for src_k, k in mapping.items():
                    ours = int(upto.loc[upto["model"] == model, k].fillna(0).sum())
                    parts.append(f"{k} cost-state {mu.get(src_k, 0):,} / table {ours:,}")
                log(f"  {model}: " + "; ".join(parts))
            final = msgs["usage_final"].fillna(False)
            log(f"  requests without a closing usage line (output_tokens NULL): {int((~final).sum())} of {len(msgs)}; "
                f"their streamed placeholder output sums to {int(msgs.loc[~final, 'output_tokens_lower_bound'].sum()):,}. "
                f"This is why table output < cost-state output; input and cache counts are complete.")
        else:
            log("  no cost-state record found")

        log("\n== 5. linkage and coverage")
        spawns, subs = dfs["agent_spawns.csv"], dfs["subagents.csv"]
        log.check("every Agent call links to a subagent transcript",
                  spawns["linked_subagent_id"].notna().all(),
                  f"{spawns['linked_subagent_id'].isna().sum()} unlinked")
        log.check("every subagent transcript links to an Agent call", subs["spawn_linked"].all(),
                  ", ".join(subs.loc[~subs["spawn_linked"], "subagent_id"].astype(str)))
        empty = subs[subs["n_messages"] == 0]
        log(f"  subagents with no assistant messages (still starting / failed): {len(empty)}")
        votes = dfs["ab_votes.csv"]
        work = require_dir("MOONSHOT_WORK")
        keys = sorted(p.stem.removeprefix("ab_key_") for p in work.glob("ab_key_v*_v*.json"))   # judged comparisons; the audio audition keys are checked below
        comps = sorted(votes["comparison"].unique())
        log.check("one A/B verdict per key file", comps == keys, f"keys {len(keys)}, verdicts {len(comps)}")
        picks = dfs["director_picks.csv"]
        audio_clips = {(k.name, c) for k in work.glob("ab_key_v*_sound.json") for c in json.loads(k.read_text(encoding="utf-8")).get("clips", {})}
        picked = {(r.key_file, r.clip_key) for r in picks.dropna(subset=["key_file"]).itertuples()}
        log.check("every clip of a blind audio audition key has a director pick", audio_clips == picked,
                  f"clips {len(audio_clips)}, picks {len(picked)}")
        per = votes.groupby("comparison").size()
        log.check("7 sections per A/B comparison", (per == 7).all(), per[per != 7].to_dict().__repr__())
        all_scores = dfs["critic_scores.csv"]
        scores = all_scores[all_scores["critic"] == "fable_editor"]
        both = scores.dropna(subset=["score", "progress_md_score"])
        diff = both[both["score"] != both["progress_md_score"]]
        log.check("editor report scores == PROGRESS.md scores where both exist", diff.empty,
                  f"{len(diff)} of {len(both)} differ")
        only_report = sorted(int(v) for v in scores.loc[scores["progress_md_score"].isna(), "version"].unique())
        log(f"  versions scored only in a critic report (missing from PROGRESS.md): {only_report}")
        log(f"  versions with no editor critique: "
            f"{sorted(set(dfs['versions.csv']['version']) - set(scores['version']))}")
        per_critic = all_scores.groupby(["version", "critic"]).size().reset_index(name="n")
        rescored_ok = per_critic.loc[per_critic["critic"] == "fable_editor_rescored", "n"].eq(1).all()
        rubric_ok = per_critic.loc[~per_critic["critic"].isin(["crowd_ftv", "fable_editor_rescored"]), "n"].eq(10).all() and rescored_ok
        crowd_ok = per_critic.loc[per_critic["critic"] == "crowd_ftv", "n"].isin([2, 3]).all()
        log.check("rubric critics score ten categories per version; the crowd scores two or three", bool(rubric_ok and crowd_ok))
        log.check("no NULL score in critic_scores", bool(all_scores["score"].notna().all()),
                  f"{int(all_scores['score'].isna().sum())} NULL")
        vers = dfs["versions.csv"]
        log(f"  versions without aqc (audio QC) file: {vers.loc[~vers['has_aqc'], 'version'].tolist()}")
        log(f"  versions without tqc (tech QC) file: {vers.loc[~vers['has_tqc'], 'version'].tolist()}")
        ints = dfs["interventions.csv"]
        log.check("every intervention has a label", (ints["kind"] != "unlabelled").all())
        progress = require_dir("MOONSHOT_EXPORTS") / "PROGRESS.md"
        n_direct = len(re.findall(r"CONNOR \(direct\)", progress.read_text(encoding="utf-8"))) if progress.exists() else 0
        log(f"  PROGRESS.md 'CONNOR (direct)' mentions: {n_direct}; interventions from transcript: {len(ints)} "
            f"(different sources; the log paraphrases, the transcript is authoritative)")

        log("\n== 5b. critic sources and A/B verdicts, source vs target")
        exports = require_dir("MOONSHOT_EXPORTS")
        qc_root = exports / "qc"
        rows_per_file = [
            ("fable_editor", "qc_json", "v*/fable_editor.json", 10),
            ("codex_critic", None, "v*/codex_critic.json", 10),
            ("gemini_pro_web", None, "v*/gemini_web_critic.json", 10),
            ("gemini_flash", None, "v*/gemini_critic_run*.json", 10),
            ("twelvelabs", None, "v*/twelvelabs_critic_raw_run*.json", 10),
            ("crowd_ftv", "qc_json", "v*/crowd_ftv.json", 3),
        ]
        for critic, kind, pattern, per in rows_per_file:
            n_files = len(list(qc_root.glob(pattern)))
            sub = all_scores[all_scores["critic"] == critic]
            if kind:
                sub = sub[sub["source_kind"] == kind]
            log.count(f"{critic}: score files vs score rows / {per}", n_files, len(sub) // per)
        keys_n = len(list(work.glob("ab_key_v*_v*.json")))
        log.count("A/B: key files vs comparisons in ab_votes", keys_n, votes["comparison"].nunique())
        log.count("A/B: ab_votes rows vs 7 sections per key file", keys_n * 7, len(votes))
        mp4s = len(list((exports / "versions").glob("moonshot_v*.mp4")))
        log.count("versions: exported mp4 files vs versions with an export time", mp4s, int(vers["export_time"].notna().sum()))
        ledger_n = sum(1 for _ in csv.DictReader((exports / "run_ledger.csv").open(encoding="utf-8")))
        log.count("loop_segments rows vs run_ledger.csv rows", ledger_n, len(dfs["loop_segments.csv"]))
        cross = RAW_DIR / "_ab_crosscheck.txt"
        for line in cross.read_text(encoding="utf-8").splitlines() if cross.exists() else []:
            m = re.search(r"(\d+) of (\d+) section picks agree", line)
            if m:
                log.check(f"A/B {line.split(':', 1)[0]}: judge_sonnet.json agrees with the hand-back", m.group(1) == m.group(2), line.split(": ", 1)[1])
            else:
                log(f"  note: {line}")

        log("\n== 5c. promotion record and loop ledger")
        best = json.loads((exports / "BEST.json").read_text(encoding="utf-8"))
        flagged = vers.loc[vers["is_best_final"], "version"].tolist()
        log.check("BEST.json version is the one version flagged is_best_final", flagged == [best["version"]], f"flagged {flagged}, BEST.json v{best['version']}")
        best_file = exports / best["file"]
        if best_file.exists():
            digest = hashlib.sha256(best_file.read_bytes()).hexdigest()
            log.check("BEST.json sha256 matches the promoted mp4", digest == best["sha256"], f"{best['file']}")
        else:
            log(f"  note: promoted file {best['file']} not found; hash not checked")
        header_best = re.search(r"^BEST:\s*v(\d+)", progress.read_text(encoding="utf-8"), re.M) if progress.exists() else None
        if header_best and int(header_best.group(1)) != best["version"]:
            log(f"[FINDING] PROGRESS.md header line says BEST: v{header_best.group(1)} but BEST.json (promote.py) says v{best['version']}; "
                f"the ingest uses BEST.json.")
        segs = dfs["loop_segments.csv"]
        stamps = pd.to_datetime(msgs["ts_utc"], utc=True).sort_values().reset_index(drop=True)
        chain_gap = pd.Timedelta(minutes=5)
        log("  each ledger boundary against the chain of requests that is continuous (no gap over 5 min) through it:")
        for _, seg in segs.iterrows():
            start = pd.Timestamp(seg["start_utc"])
            i = stamps[stamps >= start].index[0]
            while i > 0 and stamps[i] - stamps[i - 1] <= chain_gap:
                i -= 1
            d_start = (start - stamps[i]).total_seconds() / 60
            line = (f"  segment {seg['segment_id']}: ledger start {seg['start_local']} vs activity chain start "
                    f"{stamps[i].tz_convert(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')} ({d_start:+.0f} min)")
            off = abs(d_start)
            if isinstance(seg["end_utc"], str):
                end = pd.Timestamp(seg["end_utc"])
                j = stamps[stamps < end].index[-1]
                while j < len(stamps) - 1 and stamps[j + 1] - stamps[j] <= chain_gap:
                    j += 1
                d_end = (end - stamps[j]).total_seconds() / 60
                line += (f"; ledger end {seg['end_local']} vs activity chain end "
                         f"{stamps[j].tz_convert(LOCAL_TZ).strftime('%Y-%m-%d %H:%M')} ({d_end:+.0f} min)")
                off = max(off, abs(d_end))
            log(line + ("" if off <= 5 else "   [FINDING: off by more than 5 min]"))

        log("\n== 6. privacy scan of every output CSV")
        home = Path.home().name
        patterns = [re.compile(r"(?i)\b[a-z]:[\\/]"), re.compile(r"(?i)[\\/]users[\\/]"),
                    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(rf"(?i)[\\/]{re.escape(home)}([\\/]|$)")]
        hits = []
        for t in TABLES:
            text = (RAW_DIR / t).read_text(encoding="utf-8")
            hits += [f"{t}: {p.pattern}" for p in patterns if p.search(text)]
        log.check("no drive paths, home paths or e-mail addresses in outputs", not hits, "; ".join(hits))

        log("\n== 7. summary")
        # total = input + cache + output where the output is known (final line seen)
        msgs["total"] = msgs[TOKENS].fillna(0).sum(axis=1)
        for dim in ("model", "agent_role", "session_part"):
            log(f"  tokens by {dim}:")
            g = msgs.groupby(dim)[TOKENS + ["output_tokens_lower_bound", "total"]].sum()
            g["requests"] = msgs.groupby(dim).size()
            log("    " + g.to_string().replace("\n", "\n    "))
        parts = dfs["session_parts.csv"]
        log("  session parts:\n    " + parts.to_string(index=False).replace("\n", "\n    "))
        cx = dfs["codex_requests.csv"]
        if len(cx):
            log(f"  codex requests: {len(cx)} in {cx['codex_session_id'].nunique()} sessions; "
                f"input {int(cx['input_tokens'].sum()):,} (cached {int(cx['cached_input_tokens'].sum()):,}), "
                f"output {int(cx['output_tokens'].sum()):,} (reasoning {int(cx['reasoning_output_tokens'].sum()):,})")
        log(f"\n{log.failures} check(s) failed" if log.failures else "\nall checks passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    (RAW_DIR / "_reconciliation.txt").write_text("\n".join(log.lines) + "\n", encoding="utf-8")
    log_path = ANALYTICS_DIR / "data" / "reconciliation_log.csv"
    is_new = not log_path.exists()
    run_at = datetime.now(LOCAL_TZ).isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        if is_new:
            writer.writerow(["run_at_local", "check_name", "source_count", "target_count", "delta", "status"])
        for name, source, target, delta, status in log.rec_rows:
            writer.writerow([run_at, name, source, target, delta, status])
    sys.exit(1 if log.failures else 0)


if __name__ == "__main__":
    main()
