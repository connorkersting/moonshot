"""Write the run-accounting report (project-only tokens and time per phase) as Markdown.

Reads the dbt + DuckDB warehouse read-only. Run after ``dbt build``:

    cd analytics
    export DO_NOT_TRACK=1 PYTHONUTF8=1
    uv run python reports/build_run_accounting.py [--out PATH]

Without --out the report goes to <MOONSHOT_EXPORTS>/evidence/run_accounting.md (the folder comes
from the shell or the untracked analytics/.env, like the ingest; no personal path is written here).

What the report counts: Claude Code requests in this project's transcript and the Codex requests
attributed to it, in tokens. It never uses the account-wide plan percentages (they include
everything else on the account), and it carries no dollar figures (the warehouse has no price
table for these model ids).
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
ANALYTICS = HERE.parent
DB_PATH = ANALYTICS / "warehouse" / "moonshot.duckdb"
RECONCILIATION = ANALYTICS / "data" / "raw" / "_reconciliation.txt"
LEDGER_TOLERANCE_MIN = 5

PHASE_NOTES = {
    "gap_after_segment_1": "Pre-loop planning after the 24-hour request (first human message about 17:09), before the ledger opened.",
    "gap_after_segment_2": "Marked a usage pause in the ledger, yet the transcript holds the director's Q&A and planning in this window.",
    "gap_after_segment_3": "Tool expansion (Remotion, TwelveLabs, EffectCraft, adopt-if-time items) and the director's notes, before the ledger reopened.",
    "gap_after_segment_4": "The v23 builder had died in a sign-out; the audit follow-up, the all-out plan request and the director's decisions before segment 5.",
    "gap_after_segment_7": "After the 24-hour budget closed: Phase B work (repo and analytics refresh), including this report's own refresh.",
}


def query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


def n(x: float | int | None, digits: int = 0) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x:,.{digits}f}"


def mtok(x: float | int | None) -> str:
    if x is None or pd.isna(x):
        return "n/a"
    return f"{x / 1e6:,.1f}M"


def hhmm(hours: float | None) -> str:
    if hours is None or pd.isna(hours):
        return "n/a"
    minutes = round(float(hours) * 60)
    return f"{minutes // 60} h {minutes % 60:02d} m"


def md_table(frame: pd.DataFrame, align_right: set[str] | None = None) -> str:
    align_right = align_right or set()
    head = "| " + " | ".join(frame.columns) + " |"
    rule = "|" + "|".join("---:" if c in align_right else "---" for c in frame.columns) + "|"
    rows = ["| " + " | ".join(str(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([head, rule, *rows])


def local(ts: pd.Timestamp | None) -> str:
    """UTC timestamp from the warehouse to a New York wall-clock string."""
    if ts is None or pd.isna(ts):
        return "n/a"
    return pd.Timestamp(ts).tz_localize("UTC").tz_convert("America/New_York").strftime("%m-%d %H:%M")


def out_path() -> Path:
    if "--out" in sys.argv:
        return Path(sys.argv[sys.argv.index("--out") + 1])
    sys.path.insert(0, str(ANALYTICS / "ingest"))
    from common import load_dotenv

    load_dotenv()
    root = os.environ.get("MOONSHOT_EXPORTS", "").strip()
    if not root or not Path(root).is_dir():
        raise SystemExit("config error: pass --out PATH or set MOONSHOT_EXPORTS")
    return Path(root) / "evidence" / "run_accounting.md"


def main() -> int:
    if not DB_PATH.exists():
        print(f"error: {DB_PATH} not found; run dbt build first", file=sys.stderr)
        return 1
    con = duckdb.connect(str(DB_PATH), read_only=True)
    phases = query(con, "SELECT * FROM marts.mart_run_accounting_by_phase ORDER BY phase_order")
    roles = query(con, "SELECT * FROM marts.mart_run_accounting_by_role")
    versions = query(
        con,
        """
        SELECT version_id, version_number, is_promoted, fable_editor_overall, loop_hours_at_export,
               project_tokens_known_at_export, exported_at_utc
        FROM core.dim_version ORDER BY version_number
        """,
    )
    last_req = query(con, "SELECT MAX(requested_at_utc) AS t FROM core.fct_llm_requests")["t"].iloc[0]
    req_ts = query(con, "SELECT requested_at_utc FROM core.fct_llm_requests")
    imputed = query(
        con,
        """
        WITH final_means AS (
            SELECT agent_role, model_id, AVG(output_tokens) AS mean_final_output
            FROM core.fct_llm_requests WHERE is_usage_final GROUP BY agent_role, model_id
        )
        SELECT
            SUM(f.output_tokens) AS output_final,
            SUM(f.output_tokens_unfinalised_lower_bound) AS output_floor_unfinalised,
            SUM(m.mean_final_output) FILTER (WHERE NOT f.is_usage_final) AS output_imputed_unfinalised,
            COUNT(*) FILTER (WHERE NOT f.is_usage_final) AS n_unfinalised,
            COUNT(*) AS n_requests
        FROM core.fct_llm_requests AS f
        LEFT JOIN final_means AS m ON f.agent_role = m.agent_role AND f.model_id = m.model_id
        """,
    ).iloc[0]
    by_family = query(
        con,
        """
        SELECT m.model_family, COUNT(*) AS requests,
               SUM(f.input_tokens) AS input_tokens, SUM(f.cache_creation_tokens) AS cache_creation_tokens,
               SUM(f.cache_read_tokens) AS cache_read_tokens, SUM(f.output_tokens) AS output_tokens_final,
               SUM(f.output_tokens_unfinalised_lower_bound) AS output_floor_unfinalised
        FROM core.fct_llm_requests AS f INNER JOIN core.dim_model AS m ON f.model_id = m.model_id
        GROUP BY m.model_family ORDER BY requests DESC
        """,
    )
    codex_attr = query(
        con,
        """
        SELECT attribution, COUNT(*) AS requests, COUNT(DISTINCT codex_session_id) AS sessions,
               SUM(input_tokens) AS input_tokens, SUM(cached_input_tokens) AS cached_input_tokens,
               SUM(output_tokens) AS output_tokens
        FROM core.fct_codex_requests GROUP BY attribution ORDER BY attribution
        """,
    )
    kinds = query(
        con,
        "SELECT intervention_kind, COUNT(*) AS n FROM core.fct_interventions GROUP BY intervention_kind ORDER BY n DESC",
    )
    findings = RECONCILIATION.read_text(encoding="utf-8") if RECONCILIATION.exists() else ""
    ingest_run = re.search(r"run (\S+)", findings.splitlines()[0]).group(1) if findings else "unknown"
    con.close()

    segs = phases[phases["phase_kind"] == "ledger_segment"].copy()
    gaps = phases[phases["phase_kind"] == "gap"].copy()
    closed = segs[~segs["phase_end_at_utc"].isna()]
    ledger_closed_h = float(closed["ledger_hours"].sum())
    ledger_all_h = float(segs["ledger_hours"].sum())
    active_in_segments = float(segs["active_hours"].sum())
    active_in_gaps = float(gaps["active_hours"].sum())
    total_requests = int(phases["claude_requests"].sum())
    cache_read_share = float(phases["cache_read_tokens"].sum()) / float(phases["total_tokens_known"].sum()) * 100
    no_final_share = float(phases["requests_without_final_usage"].sum()) / total_requests * 100

    out: list[str] = []
    out.append("# MOONSHOT run accounting: project-only tokens and time per phase\n")
    out.append(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} local from the warehouse (ingest run {ingest_run}; last Claude request in "
        f"the data {local(last_req)} EDT). Times are America/New_York.\n"
    )
    out.append("## What this counts, and what it does not\n")
    out.append(
        "- **Project-only.** Every Claude Code request in this project's transcript (the main agent plus all subagents) and the Codex "
        "requests attributed to it. Anything else on the account is not here.\n"
        "- **Never the plan percentage.** The Codex logs also record the account's 5-hour and weekly plan percentages. They include "
        "all other work on the account and are not used anywhere in this report.\n"
        "- **Tokens, not dollars.** The warehouse has no price table for these model ids, so there is no cost figure. Token counts are "
        "API-equivalent usage as logged, not a bill.\n"
        "- **Token types stay separate.** Uncached input, cache creation, cache read and output are never merged. Cache reads are "
        f"{cache_read_share:.0f}% of the volume because every request re-reads its context; that is a measure of context size, not of work.\n"
        f"- **Output is a floor.** {no_final_share:.0f}% of the requests never logged a closing usage record, so their output count is unknown "
        "(section 4).\n"
    )

    out.append("## 1. Loop time: the ledger against the transcript\n")
    out.append(
        "The run ledger (`run_ledger.csv`) is the agent's own record of loop time. Active time is the transcript's evidence: every "
        "request start time (main agent and subagents together) sorted, neighbours no more than 5 minutes apart merged into one "
        "interval, interval lengths summed. Parallel subagents count once.\n"
    )
    t = pd.DataFrame(
        {
            "Segment": segs["loop_phase_id"].str.replace("segment_", "", regex=False),
            "Ledger window": [f"{local(a)} to {local(b) if pd.notna(b) else 'open'}" for a, b in zip(segs["phase_start_at_utc"], segs["phase_end_at_utc"])],
            "Ledger hours": segs["ledger_hours"].map(hhmm),
            "Active hours": segs["active_hours"].map(hhmm),
            "Active / ledger": [f"{a / l * 100:.0f}%" if l else "n/a" for a, l in zip(segs["active_hours"], segs["ledger_hours"])],
            "Requests": segs["claude_requests"].map(n),
            "Intervals": segs["n_active_intervals"].map(n),
        }
    )
    out.append(md_table(t, {"Ledger hours", "Active hours", "Active / ledger", "Requests", "Intervals"}))
    out.append(
        f"\n- {len(closed)} of {len(segs)} ledger segments are closed and add up to **{hhmm(ledger_closed_h)}** of ledger time; "
        f"all segments together stand at {hhmm(ledger_all_h)}. The last segment ended with 'budget_complete': the 24-hour loop budget.\n"
        f"- The transcript supports **{hhmm(active_in_segments)}** of active time inside the ledger segments, "
        f"{active_in_segments / ledger_all_h * 100:.0f}% of the ledger. The rest is waiting: renders, rate-limit pauses and quiet stretches "
        "longer than 5 minutes.\n"
    )
    out.append("### Boundaries (reconciled to the transcript, tolerance 5 minutes)\n")
    out.append(
        "For each ledger boundary: follow the chain of requests that is continuous (no gap over 5 minutes) through it, and compare "
        "where that chain actually starts or stops. A positive start difference means the ledger opened *after* the work began; a "
        "negative end difference means the work carried on after the ledger closed.\n"
    )
    stamps = pd.to_datetime(req_ts["requested_at_utc"]).sort_values().reset_index(drop=True)
    gap = pd.Timedelta(minutes=5)
    bt = []
    for _, sg in segs.iterrows():
        start, end = sg["phase_start_at_utc"], sg["phase_end_at_utc"]
        inside_first = stamps[stamps >= start].index[0]
        i = inside_first
        while i > 0 and stamps[i] - stamps[i - 1] <= gap:
            i -= 1
        d_start = (start - stamps[i]).total_seconds() / 60
        if pd.notna(end):
            inside_last = stamps[stamps < end].index[-1]
            j = inside_last
            while j < len(stamps) - 1 and stamps[j + 1] - stamps[j] <= gap:
                j += 1
            d_end = (end - stamps[j]).total_seconds() / 60
            end_txt, chain_end_txt = local(end), local(stamps[j])
        else:
            d_end, end_txt, chain_end_txt = None, "open", "open"
        ok = abs(d_start) <= LEDGER_TOLERANCE_MIN and (d_end is None or abs(d_end) <= LEDGER_TOLERANCE_MIN)
        bt.append({
            "Segment": sg["loop_phase_id"].replace("segment_", ""),
            "Ledger start": local(start),
            "Activity chain starts": local(stamps[i]),
            "Start diff": f"{d_start:+.0f} min",
            "Ledger end": end_txt,
            "Activity chain ends": chain_end_txt,
            "End diff": f"{d_end:+.0f} min" if d_end is not None else "open",
            "Within 5 min": "yes" if ok else "no",
        })
    out.append(md_table(pd.DataFrame(bt)))
    out.append(
        "\nThe segment boundaries are the agent's own entries; where they differ from the transcript the transcript is the evidence. "
        "What the transcript holds outside the segments follows.\n"
    )
    out.append("### Work outside the ledger segments\n")
    g = pd.DataFrame(
        {
            "Window": [f"{local(a)} to {local(b) if pd.notna(b) else 'open'}" for a, b in zip(gaps["phase_start_at_utc"], gaps["phase_end_at_utc"])],
            "Active hours": gaps["active_hours"].map(hhmm),
            "Requests": gaps["claude_requests"].map(n),
            "Subagent requests": gaps["subagent_requests"].map(n),
            "Human messages": gaps["human_messages"].map(n),
            "Versions exported": gaps["versions_exported"].map(n),
            "Known tokens": gaps["total_tokens_known"].map(mtok),
            "What the transcript shows": [PHASE_NOTES.get(p, "") for p in gaps["loop_phase_id"]],
        }
    )
    g = g[gaps["claude_requests"].values > 0]
    out.append(md_table(g, {"Active hours", "Requests", "Subagent requests", "Human messages", "Versions exported", "Known tokens"}))
    for _, gp in gaps.iterrows():
        if gp["versions_exported"] > 0:
            inside = versions[
                (versions["exported_at_utc"] >= gp["phase_start_at_utc"]) & (versions["exported_at_utc"] < gp["phase_end_at_utc"])
            ]["version_id"].tolist()
            out.append(f"\nA version was exported inside the window {local(gp['phase_start_at_utc'])} to {local(gp['phase_end_at_utc'])}: "
                       f"{', '.join(inside)} (the ledger had that window as a pause).")
    share_outside = float(gaps["claude_requests"].sum()) / total_requests * 100
    out.append(
        f"\nThe gaps hold **{share_outside:.0f}% of all Claude requests** and {hhmm(active_in_gaps)} of active time. They are real project work "
        "that the ledger does not count as loop time (planning before a segment opened, Q&A during a pause, tool setup). "
        "Any statement of the form 'the loop ran for N hours' should say which of these it includes.\n"
    )

    out.append("## 2. Tokens per phase (Claude, project-only)\n")
    p = pd.DataFrame(
        {
            "Phase": [(f"Segment {lid.split('_')[1]}" if k == "ledger_segment" else f"Gap after {lid.split('_')[-1]}") for lid, k in zip(phases["loop_phase_id"], phases["phase_kind"])],
            "Requests": phases["claude_requests"].map(n),
            "Main": phases["main_agent_requests"].map(n),
            "Subagent": phases["subagent_requests"].map(n),
            "Input (uncached)": phases["input_tokens"].map(n),
            "Cache creation": phases["cache_creation_tokens"].map(n),
            "Cache read": phases["cache_read_tokens"].map(n),
            "Output (final only)": phases["output_tokens_final"].map(n),
            "Output floor (unfinalised)": phases["output_tokens_unfinalised_lower_bound"].map(n),
        }
    )
    p = p[phases["claude_requests"].values > 0]
    tot = pd.DataFrame(
        [{
            "Phase": "**Total**",
            "Requests": n(phases["claude_requests"].sum()),
            "Main": n(phases["main_agent_requests"].sum()),
            "Subagent": n(phases["subagent_requests"].sum()),
            "Input (uncached)": n(phases["input_tokens"].sum()),
            "Cache creation": n(phases["cache_creation_tokens"].sum()),
            "Cache read": n(phases["cache_read_tokens"].sum()),
            "Output (final only)": n(phases["output_tokens_final"].sum()),
            "Output floor (unfinalised)": n(phases["output_tokens_unfinalised_lower_bound"].sum()),
        }]
    )
    num_cols = set(p.columns) - {"Phase"}
    out.append(md_table(pd.concat([p, tot], ignore_index=True), num_cols))
    out.append(
        "\nOutput (final only) adds requests that have a closing usage record. Output floor adds the streamed placeholder of the rest. "
        "Neither is complete and they are not added together.\n"
    )
    out.append("### By model family\n")
    bf = pd.DataFrame(
        {
            "Family": by_family["model_family"],
            "Requests": by_family["requests"].map(n),
            "Input (uncached)": by_family["input_tokens"].map(n),
            "Cache creation": by_family["cache_creation_tokens"].map(n),
            "Cache read": by_family["cache_read_tokens"].map(n),
            "Output (final only)": by_family["output_tokens_final"].map(n),
            "Output floor (unfinalised)": by_family["output_floor_unfinalised"].map(n),
        }
    )
    out.append(md_table(bf, set(bf.columns) - {"Family"}))
    out.append("\n### By agent role (all phases)\n")
    rr = (
        roles.groupby("agent_role", as_index=False)[
            ["request_count", "input_tokens", "cache_creation_tokens", "cache_read_tokens", "output_tokens_final", "output_tokens_unfinalised_lower_bound"]
        ].sum().sort_values("request_count", ascending=False)
    )
    rt = pd.DataFrame(
        {
            "Role": rr["agent_role"],
            "Requests": rr["request_count"].map(n),
            "Input (uncached)": rr["input_tokens"].map(n),
            "Cache creation": rr["cache_creation_tokens"].map(n),
            "Cache read": rr["cache_read_tokens"].map(n),
            "Output (final only)": rr["output_tokens_final"].map(n),
            "Output floor (unfinalised)": rr["output_tokens_unfinalised_lower_bound"].map(n),
        }
    )
    out.append(md_table(rt, set(rt.columns) - {"Role"}))

    out.append("\n## 3. Codex, human messages and versions per phase\n")
    cx = pd.DataFrame(
        {
            "Phase": [(f"Segment {lid.split('_')[1]}" if k == "ledger_segment" else f"Gap after {lid.split('_')[-1]}") for lid, k in zip(phases["loop_phase_id"], phases["phase_kind"])],
            "Codex requests": phases["codex_requests"].map(n),
            "Codex input (incl. cached)": phases["codex_input_tokens"].map(n),
            "Codex cached input": phases["codex_cached_input_tokens"].map(n),
            "Codex output": phases["codex_output_tokens"].map(n),
            "Human messages": phases["human_messages"].map(n),
            "Versions exported": phases["versions_exported"].map(n),
            "Promoted": phases["versions_promoted"].map(n),
        }
    )
    cx = cx[(phases["claude_requests"].values > 0) | (phases["codex_requests"].values > 0)]
    out.append(md_table(cx, set(cx.columns) - {"Phase"}))
    out.append(
        "\nCodex input includes cached input (the OpenAI convention, unlike Claude's). Attribution is an **upper bound**: a Codex rollout "
        "counts when it ran in a folder named moonshot, or in the craftapps project while a session part was live. The second rule can pick "
        "up unrelated craftapps work, including Codex sessions the director ran himself.\n"
    )
    out.append(md_table(
        pd.DataFrame({
            "Attribution": codex_attr["attribution"],
            "Requests": codex_attr["requests"].map(n),
            "Sessions": codex_attr["sessions"].map(n),
            "Input (incl. cached)": codex_attr["input_tokens"].map(n),
            "Output": codex_attr["output_tokens"].map(n),
        }), {"Requests", "Sessions", "Input (incl. cached)", "Output"}))
    out.append(
        "\nHuman messages by kind: " + ", ".join(f"{r.intervention_kind} {int(r.n)}" for r in kinds.itertuples())
        + ". These are the messages the director typed or answered; each has a hand-written label in the ingest.\n"
    )

    out.append("## 4. The requests with no closing usage record\n")
    nf = int(phases["requests_without_final_usage"].sum())
    out.append(
        f"{nf:,} of {total_requests:,} Claude requests ({nf / total_requests * 100:.0f}%) have no closing usage line, so their output "
        "count is unknown (stored as NULL, never zero). Input and cache counts are complete for every request. "
        "The first ingest run (2026-10-07 17:41) reported 459 of 1,302 (35%), while PROGRESS.md and the audit quote 447; the share "
        "has risen as more subagent work was added, because a subagent response's last line is often not written.\n"
    )
    nfp = phases[phases["claude_requests"] > 0]
    out.append(md_table(
        pd.DataFrame({"Phase": nfp["loop_phase_id"], "Requests": nfp["claude_requests"].map(n),
                      "No closing usage": nfp["requests_without_final_usage"].map(n),
                      "Share": [f"{a / b * 100:.0f}%" for a, b in zip(nfp["requests_without_final_usage"], nfp["claude_requests"])]}),
        {"Requests", "No closing usage", "Share"}))
    out.append(
        f"\nOutput for the whole run, three ways, none of them exact:\n\n"
        f"- final records only: **{n(imputed['output_final'])}** tokens;\n"
        f"- plus the streamed placeholders of the unfinalised requests (a floor): **{n(imputed['output_final'] + imputed['output_floor_unfinalised'])}**;\n"
        f"- plus an *estimate* that gives each unfinalised request the mean final output of its role and model "
        f"({n(imputed['n_unfinalised'])} requests): **{n(imputed['output_final'] + imputed['output_imputed_unfinalised'])}**. "
        "This is an illustration of the size of the gap, not a measurement, and is not used elsewhere.\n\n"
        "Which treatment to report is a decision for the project owner. Until it is made, the report states the final-only and floor "
        "figures and labels them as floors.\n"
    )

    out.append("## 5. Effort against the score\n")
    v = versions.copy()
    v["Delta tokens (M)"] = (v["project_tokens_known_at_export"].diff() / 1e6)
    vt = pd.DataFrame(
        {
            "Version": v["version_id"],
            "Promoted": v["is_promoted"].map({True: "yes", False: "no"}),
            "Fable overall": v["fable_editor_overall"].map(lambda x: "" if pd.isna(x) else f"{x:.1f}"),
            "Loop hours at export": v["loop_hours_at_export"].map(lambda x: f"{x:.1f}"),
            "Project tokens at export": v["project_tokens_known_at_export"].map(mtok),
            "Tokens since previous version": v["Delta tokens (M)"].map(lambda x: "" if pd.isna(x) else f"{x:,.0f}M"),
        }
    )
    out.append(md_table(vt, set(vt.columns) - {"Version", "Promoted"}))
    scored = v[v["fable_editor_overall"].notna()]
    v14, vl = v[v["version_number"] == 14].iloc[0], scored.sort_values("version_number").iloc[-1]
    gain = vl["fable_editor_overall"] - v14["fable_editor_overall"]
    out.append(
        f"\nFable editor: {v14['fable_editor_overall']:.1f} at v14 ({v14['loop_hours_at_export']:.1f} ledger hours, "
        f"{mtok(v14['project_tokens_known_at_export'])} project tokens) against {vl['fable_editor_overall']:.1f} at {vl['version_id']} "
        f"({vl['loop_hours_at_export']:.1f} hours, {mtok(vl['project_tokens_known_at_export'])}), the last version it scored. The "
        f"{vl['loop_hours_at_export'] - v14['loop_hours_at_export']:.1f} hours and "
        f"{(vl['project_tokens_known_at_export'] - v14['project_tokens_known_at_export']) / 1e6:,.0f}M tokens in between bought {gain:+.1f} points, on a scale "
        "that moved between reviews (the same critic gave v17 an 8.0 in its own review and 7.0 when re-scoring it). "
        "v27 and v28, exported after that review, had no fresh critic pass. "
        "'Project tokens' is every Claude request up to the export, so it includes research, tooling and analytics work as well as trailer builds, "
        "and it is mostly cache reads.\n"
    )

    out.append("## 6. Data-quality notes that affect these numbers\n")
    out.append(
        "- **Snapshot.** The transcript is live. The ingest copies it once per run, so the numbers are internally consistent but stop at the "
        "snapshot time; this analytics work is itself in the data, in the window after the last ledger segment.\n"
        "- **Missing calls.** Haiku summarisation calls (about 0.7M input tokens in the client's cost record) and the compaction summaries are "
        "not logged as transcript messages, so they are not in these totals.\n"
        "- **Ledger vs transcript.** The ledger and the transcript disagree about what counts as loop time (section 1). The ledger's own note "
        "says the session clock ran about ten minutes behind wall time in session 1; the segment 1 boundaries match the transcript to within "
        "five minutes, so no correction was applied.\n"
        "- **PROGRESS.md header.** At the first refresh its `BEST:` line lagged BEST.json (v17 against v21); at this refresh "
        + ("it still lags (see the reconciliation file)" if "[FINDING] PROGRESS.md header" in findings else "the two agree")
        + ". The warehouse uses BEST.json either way.\n"
        "- **Codex attribution** is an upper bound (section 3).\n"
    )
    path = out_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
