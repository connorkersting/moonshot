"""Parse the MOONSHOT Claude Code transcripts into metadata-only tables.

Run from the analytics/ folder:  uv run python ingest/parse_sessions.py

Reads (read-only):
  $CLAUDE_PROJECT_DIR/<MOONSHOT_SESSION_ID>.jsonl                  main agent
  $CLAUDE_PROJECT_DIR/<MOONSHOT_SESSION_ID>/**/agent-*.jsonl (+ .meta.json)  subagents
  $CODEX_SESSIONS_DIR/**/rollout-*.jsonl                           optional, Codex CLI

Writes to analytics/data/raw/:
  agent_messages.csv   one row per provider request (LLM call)
  agent_spawns.csv     one row per Agent tool call attempt
  subagents.csv        one row per subagent invocation (transcript file)
  session_parts.csv    one row per session part (wall clock + active time)
  session_events.csv   one row per compaction / session-part start
  interventions.csv    one row per human message or answer
  codex_requests.csv   one row per Codex request (token_count event)

Privacy: message text, prompts, tool inputs and tool outputs are never
written. Human-message text is read only to de-duplicate queued copies; the
published label comes from the hand-written ingest/intervention_labels.csv.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from common import (
    SchemaDriftError,
    active_intervals,
    iter_jsonl,
    load_dotenv,
    main_transcript_path,
    parse_ts,
    read_meta,
    role_for,
    session_id,
    session_part,
    session_part_bounds,
    subagent_files,
    to_local_str,
    to_utc_str,
    write_csv,
)

LABELS_PATH = Path(__file__).resolve().parent / "intervention_labels.csv"

# usage keys we read, and keys we know about and deliberately ignore. Anything
# else is upstream drift: fail, look, then add it to one list or the other.
USAGE_READ = {
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens_details",
}
USAGE_IGNORED = {
    "cache_creation",  # 5m/1h TTL split of cache_creation_input_tokens: never added on top
    "server_tool_use",
    "service_tier",
    "inference_geo",
    "iterations",  # per-iteration copy of the same counters
    "speed",
    "fallback_credit",
}
TOKEN_FIELDS = {
    "input_tokens": "input_tokens",
    "cache_creation_tokens": "cache_creation_input_tokens",
    "cache_read_tokens": "cache_read_input_tokens",
}

# queued-message prefixes that are machine traffic, not a person typing
MACHINE_PREFIXES = ("<agent-message", "<cross-session-message", "<task-notification")
HUMAN_DEDUPE_WINDOW = timedelta(seconds=120)
LABEL_MATCH_WINDOW = timedelta(seconds=5)

MESSAGE_COLUMNS = [
    "message_id", "request_id", "session_id", "agent_id", "is_subagent", "agent_role",
    "model", "ts_utc", "ts_local", "session_part", "input_tokens", "output_tokens",
    "output_tokens_lower_bound", "usage_final", "cache_creation_tokens",
    "cache_read_tokens", "thinking_tokens", "stop_reason",
    "tool_names", "n_tool_calls", "n_jsonl_lines",
]
SPAWN_COLUMNS = [
    "spawn_id", "parent_agent_id", "parent_message_id", "ts_utc", "ts_local",
    "session_part", "description", "agent_role", "subagent_type", "requested_model",
    "run_in_background", "linked_subagent_id",
]
SUBAGENT_COLUMNS = [
    "subagent_id", "description", "agent_role", "agent_type", "requested_model",
    "actual_models", "spawn_id", "spawn_linked", "spawn_depth", "first_ts_utc",
    "last_ts_utc", "duration_s", "session_part", "n_messages", "n_jsonl_lines",
    "n_tool_calls", "n_messages_usage_final", "input_tokens", "output_tokens_final_only",
    "output_tokens_lower_bound", "cache_creation_tokens", "cache_read_tokens",
]
PART_COLUMNS = [
    "session_part", "wall_start_utc", "wall_end_utc", "wall_start_local",
    "wall_end_local", "wall_hours", "active_hours", "n_active_intervals",
    "n_requests", "n_subagent_requests",
]
EVENT_COLUMNS = [
    "ts_utc", "ts_local", "session_part", "event", "trigger", "pre_tokens",
    "post_tokens", "duration_ms",
]
INTERVENTION_COLUMNS = [
    "intervention_id", "ts_utc", "ts_local", "session_part", "kind", "label",
    "source", "n_chars",
]
CODEX_COLUMNS = [
    "codex_session_id", "request_seq", "ts_utc", "ts_local", "model", "workdir",
    "attribution", "input_tokens", "cached_input_tokens", "output_tokens",
    "reasoning_output_tokens", "primary_used_pct", "secondary_used_pct",
]


@dataclass
class MessageAgg:
    """Accumulates the JSONL lines that belong to one provider request."""

    message_id: str
    agent_id: str
    model: str
    first_ts: datetime
    request_id: str | None
    tokens: dict[str, int | None]
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    stop_reason: str | None = None
    usage_final: bool = False
    tool_names: list[str] = field(default_factory=list)
    seen_tool_ids: set[str] = field(default_factory=set)
    n_lines: int = 0


@dataclass
class ParseState:
    aggs: dict[str, MessageAgg] = field(default_factory=dict)
    spawns: list[dict] = field(default_factory=list)
    request_to_message: dict[str, str] = field(default_factory=dict)
    cross_file_duplicates: int = 0
    excluded_records: int = 0


def _max_opt(a: int | None, b: int | None) -> int | None:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def absorb_assistant(rec: dict, agent_id: str, source: str, state: ParseState) -> None:
    """Fold one assistant JSONL line into its per-request aggregate.

    One provider response is written as several lines (one per content block
    while streaming). Input and cache counters repeat unchanged on every line;
    output grows until the final line. So: dedupe on message.id (cross-checked
    against requestId), input/cache from any line (asserted equal), output =
    max, stop_reason = last non-null, tool calls de-duplicated by tool_use id.
    A message id already owned by another transcript file is copied history
    (resume / compaction) and is skipped. Missing usage stays NULL, not 0.
    """
    msg = rec.get("message")
    if not isinstance(msg, dict) or "id" not in msg or "timestamp" not in rec:
        raise SchemaDriftError(source, "assistant.message", "dict with id + timestamp", type(msg).__name__)
    if rec.get("isCompactSummary") or msg.get("model") == "<synthetic>":
        state.excluded_records += 1
        return
    usage = msg.get("usage")
    if usage is not None:
        unknown = set(usage) - USAGE_READ - USAGE_IGNORED
        if unknown:
            raise SchemaDriftError(source, "message.usage", "known keys only", f"new keys {sorted(unknown)}")
    usage = usage or {}
    mid = str(msg["id"])
    rid = rec.get("requestId")
    if rid:
        owner = state.request_to_message.setdefault(str(rid), mid)
        if owner != mid:
            raise SchemaDriftError(source, f"requestId {rid}", "one message.id per requestId", "two message ids")
    ts = parse_ts(rec["timestamp"])
    tokens = {col: (int(usage[key]) if usage.get(key) is not None else None) for col, key in TOKEN_FIELDS.items()}
    agg = state.aggs.get(mid)
    if agg is not None and agg.agent_id != agent_id:
        state.cross_file_duplicates += 1
        return
    if agg is None:
        agg = MessageAgg(
            message_id=mid, agent_id=agent_id, model=str(msg.get("model", "")),
            first_ts=ts, request_id=str(rid) if rid else None, tokens=tokens,
        )
        state.aggs[mid] = agg
    else:
        if agg.tokens != tokens:
            raise SchemaDriftError(source, f"usage of {mid}", "constant input/cache counts across chunks", "values that change")
        agg.first_ts = min(agg.first_ts, ts)
    agg.n_lines += 1
    out = usage.get("output_tokens")
    agg.output_tokens = _max_opt(agg.output_tokens, int(out) if out is not None else None)
    details = usage.get("output_tokens_details")
    if isinstance(details, dict) and details.get("thinking_tokens") is not None:
        agg.thinking_tokens = _max_opt(agg.thinking_tokens, int(details["thinking_tokens"]))
    if msg.get("stop_reason"):
        agg.stop_reason = str(msg["stop_reason"])
    # The closing line of a response carries stop_reason and the final output
    # count. Earlier streaming lines carry a placeholder output count (~1-100).
    # Some responses never got a closing line written; their output is unknown.
    if msg.get("stop_reason") or "output_tokens_details" in usage:
        agg.usage_final = True
    for block in msg.get("content") or []:
        if block.get("type") != "tool_use" or block.get("id") in agg.seen_tool_ids:
            continue
        agg.seen_tool_ids.add(block["id"])
        agg.tool_names.append(str(block.get("name", "")))
        if block.get("name") in ("Agent", "Task"):
            tool_input = block.get("input") or {}
            state.spawns.append({
                "spawn_id": block["id"],
                "parent_agent_id": agent_id,
                "parent_message_id": mid,
                "ts": ts,
                "description": str(tool_input.get("description", "")),
                "subagent_type": str(tool_input.get("subagent_type", "") or "general-purpose (default)"),
                "requested_model": str(tool_input.get("model", "") or "inherit"),
                "run_in_background": bool(tool_input.get("run_in_background", False)),
            })


def human_text(rec: dict) -> str | None:
    """Return the text of a person-typed user message, else None (internal use)."""
    if rec.get("isMeta") or rec.get("isCompactSummary"):
        return None
    origin = rec.get("origin") or {}
    if origin.get("kind") != "human":
        return None
    content = rec.get("message", {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content):
            return None
        return " ".join(str(b.get("text", "")) for b in content if b.get("type") == "text")
    return None


def load_labels() -> list[tuple[datetime, str, str]]:
    if not LABELS_PATH.exists():
        return []
    with LABELS_PATH.open(encoding="utf-8", newline="") as fh:
        return [(parse_ts(r["ts_utc"]), r["kind"], r["label"]) for r in csv.DictReader(fh)]


def parse_main(path: Path, state: ParseState) -> dict:
    all_ts: list[datetime] = []
    events: list[dict] = []
    humans: list[dict] = []
    ask_ids: set[str] = set()
    for _, rec in iter_jsonl(path):
        if "timestamp" in rec:
            all_ts.append(parse_ts(rec["timestamp"]))
        rtype = rec.get("type")
        if rtype == "assistant":
            absorb_assistant(rec, "main", path.name, state)
            for block in rec["message"].get("content") or []:
                if block.get("type") == "tool_use" and block.get("name") == "AskUserQuestion":
                    ask_ids.add(block["id"])
        elif rtype == "system" and rec.get("subtype") == "compact_boundary":
            meta = rec.get("compactMetadata") or {}
            events.append({
                "ts": parse_ts(rec["timestamp"]), "event": "compaction",
                "trigger": meta.get("trigger"), "pre_tokens": meta.get("preTokens"),
                "post_tokens": meta.get("postTokens"), "duration_ms": meta.get("durationMs"),
            })
        elif rtype == "user":
            text = human_text(rec)
            if text is not None:
                humans.append({"ts": parse_ts(rec["timestamp"]), "text": text, "source": "user_message"})
            content = rec.get("message", {}).get("content")
            if isinstance(content, list):
                for block in content:
                    if block.get("type") == "tool_result" and block.get("tool_use_id") in ask_ids:
                        humans.append({"ts": parse_ts(rec["timestamp"]), "text": str(block.get("content", "")), "source": "ask_user_answer"})
        elif rtype == "queue-operation" and rec.get("operation") == "enqueue":
            text = str(rec.get("content", ""))
            if not text.strip().startswith(MACHINE_PREFIXES):
                humans.append({"ts": parse_ts(rec["timestamp"]), "text": text, "source": "queued_message"})
    return {"all_ts": all_ts, "events": events, "humans": humans}


def dedupe_humans(humans: list[dict]) -> list[dict]:
    """A typed message can land twice: once queued, once delivered. Keep the earliest.

    Records within LABEL_MATCH_WINDOW of a kept record are treated as copies
    too, which also makes two genuinely separate messages typed within 5 s
    count once (accepted: not observed in this run).
    """
    kept: list[dict] = []
    for h in sorted(humans, key=lambda x: (x["ts"], x["source"])):
        norm = " ".join(h["text"].split())
        dup = any(
            (" ".join(k["text"].split()) == norm and h["ts"] - k["ts"] <= HUMAN_DEDUPE_WINDOW)
            # the delivered copy of a slash command is re-wrapped, so its text
            # differs; nobody types two messages within a few seconds
            or h["ts"] - k["ts"] <= LABEL_MATCH_WINDOW
            for k in kept
        )
        if not dup:
            kept.append(h)
    return kept


def parse_codex(starts: list[datetime], run_end: datetime | None) -> list[dict]:
    """Codex CLI rollouts, metadata only. Optional: skipped if CODEX_SESSIONS_DIR is unset.

    Attribution: a rollout counts toward MOONSHOT if its working directory
    path contains 'moonshot', or if it ran in the craftapps project while a
    MOONSHOT session part was live (that is where the loop invoked Codex).
    Rollouts from any other project are dropped.
    """
    load_dotenv()
    root = os.environ.get("CODEX_SESSIONS_DIR", "").strip()
    if not root or not Path(root).is_dir() or not starts:
        return []
    rows: list[dict] = []
    for path in sorted(Path(root).rglob("rollout-*.jsonl"), key=lambda p: p.name):
        sid, cwd, model = "", "", ""
        last_total: int | None = None
        seq = 0
        pending: list[dict] = []
        for _, rec in iter_jsonl(path):
            payload = rec.get("payload") or {}
            if rec.get("type") == "session_meta":
                sid, cwd = str(payload.get("id", "")), str(payload.get("cwd", ""))
            elif rec.get("type") == "turn_context" and payload.get("model"):
                model = str(payload["model"])
            elif rec.get("type") == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                total = (info.get("total_token_usage") or {}).get("total_tokens")
                last = info.get("last_token_usage")
                # token_count is re-emitted without a new request; only a
                # rising running total marks a new request
                if not last or not total or (last_total is not None and total <= last_total):
                    continue
                # context-size probes carry a total but zero input/output: not a request
                if not (last.get("input_tokens") or last.get("output_tokens")):
                    continue
                last_total = total
                seq += 1
                limits = payload.get("rate_limits") or {}
                pending.append({
                    "codex_session_id": sid, "request_seq": seq,
                    "ts": parse_ts(rec["timestamp"]), "model": model,
                    "input_tokens": last.get("input_tokens"),
                    "cached_input_tokens": last.get("cached_input_tokens"),
                    "output_tokens": last.get("output_tokens"),
                    "reasoning_output_tokens": last.get("reasoning_output_tokens"),
                    "primary_used_pct": (limits.get("primary") or {}).get("used_percent"),
                    "secondary_used_pct": (limits.get("secondary") or {}).get("used_percent"),
                })
        if not pending:
            continue
        workdir = Path(cwd.replace("\\", "/")).name
        first = pending[0]["ts"]
        if "moonshot" in cwd.lower():
            attribution = "workdir_moonshot"
        elif workdir.lower() == "craftapps" and starts[0] <= first <= (run_end or first):
            attribution = "craftapps_during_run"
        else:
            continue
        for row in pending:
            ts = row.pop("ts")
            row.update({"ts_utc": to_utc_str(ts), "ts_local": to_local_str(ts), "workdir": workdir, "attribution": attribution})
            rows.append(row)
    rows.sort(key=lambda r: (r["ts_utc"], r["codex_session_id"], r["request_seq"]))
    return rows


def main() -> None:
    sid = session_id()
    state = ParseState()
    parsed = parse_main(main_transcript_path(), state)
    starts = session_part_bounds(parsed["all_ts"])

    # ---- subagents -------------------------------------------------------
    sub_rows: list[dict] = []
    sub_desc: dict[str, str] = {}
    for agent_id, jsonl, meta_path in subagent_files():
        meta = read_meta(meta_path)
        n_lines = 0
        before = set(state.aggs)
        for _, rec in iter_jsonl(jsonl):
            n_lines += 1
            if rec.get("type") == "assistant":
                absorb_assistant(rec, agent_id, jsonl.name, state)
        mine = [state.aggs[k] for k in sorted(set(state.aggs) - before)]
        desc = str(meta.get("description", ""))
        sub_desc[agent_id] = desc
        first = min((m.first_ts for m in mine), default=None)
        last = max((m.first_ts for m in mine), default=None)

        def total(col: str) -> int | None:
            vals = [m.tokens[col] for m in mine if m.tokens[col] is not None]
            return sum(vals) if vals else None

        outs = [m.output_tokens for m in mine if m.output_tokens is not None and m.usage_final]
        lower = [m.output_tokens for m in mine if m.output_tokens is not None]
        sub_rows.append({
            "subagent_id": agent_id,
            "description": desc,
            "agent_role": role_for(desc, True),
            "agent_type": meta.get("agentType", ""),
            "requested_model": meta.get("model", "") or "inherit",   # no model in the meta file = the subagent ran the parent's model
            "actual_models": ";".join(sorted({m.model for m in mine})),
            "spawn_id": str(meta.get("toolUseId", "")),
            "spawn_linked": False,  # filled below
            "spawn_depth": meta.get("spawnDepth", ""),
            "first_ts_utc": to_utc_str(first) if first else "",
            "last_ts_utc": to_utc_str(last) if last else "",
            "duration_s": round((last - first).total_seconds(), 1) if first and last else "",
            "session_part": session_part(first, starts) if first else "",
            "n_messages": len(mine),
            "n_jsonl_lines": n_lines,
            "n_tool_calls": sum(len(m.tool_names) for m in mine),
            "n_messages_usage_final": sum(1 for m in mine if m.usage_final),
            "input_tokens": total("input_tokens"),
            "output_tokens_final_only": sum(outs) if outs else None,
            "output_tokens_lower_bound": sum(lower) if lower else None,
            "cache_creation_tokens": total("cache_creation_tokens"),
            "cache_read_tokens": total("cache_read_tokens"),
        })
    spawn_ids = {s["spawn_id"] for s in state.spawns}
    for row in sub_rows:
        row["spawn_linked"] = bool(row["spawn_id"]) and row["spawn_id"] in spawn_ids
    link_by_spawn = {r["spawn_id"]: r["subagent_id"] for r in sub_rows if r["spawn_id"]}

    # ---- agent_messages (one row per provider request) --------------------
    msg_rows = []
    for agg in sorted(state.aggs.values(), key=lambda a: (a.first_ts, a.agent_id, a.message_id)):
        is_sub = agg.agent_id != "main"
        msg_rows.append({
            "message_id": agg.message_id,
            "request_id": agg.request_id or "",
            "session_id": sid,
            "agent_id": agg.agent_id,
            "is_subagent": is_sub,
            "agent_role": role_for(sub_desc.get(agg.agent_id), is_sub),
            "model": agg.model,
            "ts_utc": to_utc_str(agg.first_ts),
            "ts_local": to_local_str(agg.first_ts),
            "session_part": session_part(agg.first_ts, starts),
            "input_tokens": agg.tokens["input_tokens"],
            "output_tokens": agg.output_tokens if agg.usage_final else None,
            "output_tokens_lower_bound": agg.output_tokens,
            "usage_final": agg.usage_final,
            "cache_creation_tokens": agg.tokens["cache_creation_tokens"],
            "cache_read_tokens": agg.tokens["cache_read_tokens"],
            "thinking_tokens": agg.thinking_tokens if agg.usage_final else None,
            "stop_reason": agg.stop_reason or "",
            "tool_names": ";".join(agg.tool_names),
            "n_tool_calls": len(agg.tool_names),
            "n_jsonl_lines": agg.n_lines,
        })
    ids = [r["message_id"] for r in msg_rows]
    if len(ids) != len(set(ids)):
        raise AssertionError("agent_messages grain violated: message_id not unique")

    # ---- agent_spawns (one row per Agent tool call attempt) --------------
    spawn_rows = [{
        "spawn_id": s["spawn_id"],
        "parent_agent_id": s["parent_agent_id"],
        "parent_message_id": s["parent_message_id"],
        "ts_utc": to_utc_str(s["ts"]),
        "ts_local": to_local_str(s["ts"]),
        "session_part": session_part(s["ts"], starts),
        "description": s["description"],
        "agent_role": role_for(s["description"], True),
        "subagent_type": s["subagent_type"],
        "requested_model": s["requested_model"],
        "run_in_background": s["run_in_background"],
        "linked_subagent_id": link_by_spawn.get(s["spawn_id"], ""),
    } for s in sorted(state.spawns, key=lambda x: (x["ts"], x["spawn_id"]))]

    # ---- session parts: wall clock vs active time ------------------------
    req_ts = [a.first_ts for a in state.aggs.values()]
    part_rows = []
    for i, start in enumerate(starts, start=1):
        in_part = [a for a in state.aggs.values() if session_part(a.first_ts, starts) == i]
        main_ts = [t for t in parsed["all_ts"] if session_part(t, starts) == i]
        all_part_ts = main_ts + [a.first_ts for a in in_part]
        wall_end = max(all_part_ts)
        intervals = active_intervals([a.first_ts for a in in_part])
        active_s = sum((e - s).total_seconds() for s, e in intervals)
        part_rows.append({
            "session_part": i,
            "wall_start_utc": to_utc_str(start),
            "wall_end_utc": to_utc_str(wall_end),
            "wall_start_local": to_local_str(start),
            "wall_end_local": to_local_str(wall_end),
            "wall_hours": round((wall_end - start).total_seconds() / 3600, 3),
            "active_hours": round(active_s / 3600, 3),
            "n_active_intervals": len(intervals),
            "n_requests": len(in_part),
            "n_subagent_requests": sum(1 for a in in_part if a.agent_id != "main"),
        })

    # ---- session events --------------------------------------------------
    event_rows = [{
        "ts_utc": to_utc_str(e["ts"]), "ts_local": to_local_str(e["ts"]),
        "session_part": session_part(e["ts"], starts), "event": e["event"],
        "trigger": e["trigger"], "pre_tokens": e["pre_tokens"],
        "post_tokens": e["post_tokens"], "duration_ms": e["duration_ms"],
    } for e in parsed["events"]]
    for i, start in enumerate(starts, start=1):
        event_rows.append({
            "ts_utc": to_utc_str(start), "ts_local": to_local_str(start),
            "session_part": i, "event": "session_part_start", "trigger": "",
            "pre_tokens": None, "post_tokens": None, "duration_ms": None,
        })
    event_rows.sort(key=lambda r: (r["ts_utc"], r["event"]))

    # ---- interventions ---------------------------------------------------
    labels = load_labels()
    int_rows = []
    for i, h in enumerate(dedupe_humans(parsed["humans"]), start=1):
        match = [(k, lab) for ts, k, lab in labels if abs(ts - h["ts"]) <= LABEL_MATCH_WINDOW]
        kind, label = match[0] if match else ("unlabelled", "unlabelled (add to intervention_labels.csv)")
        int_rows.append({
            "intervention_id": f"h{i:03d}",
            "ts_utc": to_utc_str(h["ts"]),
            "ts_local": to_local_str(h["ts"]),
            "session_part": session_part(h["ts"], starts),
            "kind": kind,
            "label": label,
            "source": h["source"],
            "n_chars": len(h["text"]),
        })

    codex_rows = parse_codex(starts, max(req_ts) if req_ts else None)

    write_csv(msg_rows, MESSAGE_COLUMNS, "agent_messages.csv")
    write_csv(spawn_rows, SPAWN_COLUMNS, "agent_spawns.csv")
    write_csv(sorted(sub_rows, key=lambda r: r["subagent_id"]), SUBAGENT_COLUMNS, "subagents.csv")
    write_csv(part_rows, PART_COLUMNS, "session_parts.csv")
    write_csv(event_rows, EVENT_COLUMNS, "session_events.csv")
    write_csv(int_rows, INTERVENTION_COLUMNS, "interventions.csv")
    write_csv(codex_rows, CODEX_COLUMNS, "codex_requests.csv")

    unlabelled = sum(1 for r in int_rows if r["kind"] == "unlabelled")
    print(f"agent_messages:  {len(msg_rows)} requests ({sum(1 for r in msg_rows if r['is_subagent'])} subagent); "
          f"skipped {state.cross_file_duplicates} cross-file copies, {state.excluded_records} summary/synthetic records")
    print(f"agent_spawns:    {len(spawn_rows)} rows ({sum(1 for r in spawn_rows if r['linked_subagent_id'])} linked)")
    print(f"subagents:       {len(sub_rows)} rows ({sum(1 for r in sub_rows if not r['spawn_linked'])} without a spawn row)")
    print(f"session_parts:   {len(part_rows)} rows")
    print(f"session_events:  {len(event_rows)} rows")
    print(f"interventions:   {len(int_rows)} rows ({unlabelled} unlabelled)")
    print(f"codex_requests:  {len(codex_rows)} rows")


if __name__ == "__main__":
    main()
