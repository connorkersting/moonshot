"""Shared helpers for the MOONSHOT analytics ingest.

Everything here is stdlib + pandas. Paths come from environment variables,
optionally loaded from an untracked ``analytics/.env`` file (see
``analytics/.env.example``). No path literals that name a person live in this
repository.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ANALYTICS_DIR = Path(__file__).resolve().parent.parent
# ANALYTICS_RAW_DIR lets reconcile.py write a second copy for the idempotence check.
RAW_DIR = Path(os.environ.get("ANALYTICS_RAW_DIR") or (ANALYTICS_DIR / "data" / "raw"))
LOCAL_TZ = ZoneInfo("America/New_York")
# Two requests closer than this belong to one stretch of active work.
ACTIVE_GAP_MINUTES = float(os.environ.get("ACTIVE_GAP_MINUTES", "5"))

# A gap longer than this between consecutive main-transcript events starts a
# new "session part". Session 1 ended ~09:10 EDT and the extension resumed the
# same transcript ~17:00 EDT, so anything between 1 h and 7 h separates them.
SESSION_GAP_HOURS = float(os.environ.get("SESSION_GAP_HOURS", "3"))


class SchemaDriftError(RuntimeError):
    """Raised when a source no longer has the shape this ingest pins."""

    def __init__(self, source: str, field: str, expected: str, got: str) -> None:
        super().__init__(
            f"schema drift in {source}: field '{field}' expected {expected}, got {got}"
        )


# --------------------------------------------------------------------------
# configuration
# --------------------------------------------------------------------------

def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (python-dotenv is not installed on this machine).

    KEY=VALUE per line, '#' comments, optional surrounding quotes. Existing
    environment variables win, so a shell export always overrides the file.
    """
    env_path = path or (ANALYTICS_DIR / ".env")
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def require_dir(name: str) -> Path:
    """Return the directory named by env var ``name`` or fail with a clear message."""
    load_dotenv()
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"config error: environment variable {name} is not set "
            f"(set it in the shell or in analytics/.env; see analytics/.env.example)"
        )
    path = Path(value)
    if not path.is_dir():
        raise SystemExit(f"config error: {name} does not point to a directory")
    return path


def session_id() -> str:
    load_dotenv()
    sid = os.environ.get("MOONSHOT_SESSION_ID", "").strip()
    if not sid:
        raise SystemExit("config error: MOONSHOT_SESSION_ID is not set")
    return sid


def main_transcript_path() -> Path:
    path = require_dir("CLAUDE_PROJECT_DIR") / f"{session_id()}.jsonl"
    if not path.is_file():
        raise SystemExit(
            "config error: CLAUDE_PROJECT_DIR does not contain <MOONSHOT_SESSION_ID>.jsonl"
        )
    return path


def subagent_dir() -> Path:
    return require_dir("CLAUDE_PROJECT_DIR") / session_id() / "subagents"


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def iter_jsonl(path: Path) -> Iterator[tuple[int, dict]]:
    """Yield (1-based line number, record). Malformed lines raise with the line number."""
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError as exc:
                raise SchemaDriftError(
                    path.name, f"line {line_no}", "valid JSON", f"decode error ({exc.msg})"
                ) from exc


def subagent_files() -> list[tuple[str, Path, Path]]:
    """Return (agent_id, jsonl_path, meta_path) for every subagent transcript.

    Walks the whole session folder recursively, so nested subagents (a
    subagent that spawned its own) are found wherever they are written.
    """
    out: list[tuple[str, Path, Path]] = []
    sdir = require_dir("CLAUDE_PROJECT_DIR") / session_id()
    if not sdir.is_dir():
        return out
    for jsonl in sorted(sdir.rglob("agent-*.jsonl"), key=lambda p: p.name):
        agent_id = jsonl.stem.removeprefix("agent-")
        out.append((agent_id, jsonl, jsonl.with_suffix(".meta.json")))
    return out


def read_meta(meta_path: Path) -> dict:
    if not meta_path.is_file():
        return {}
    return json.loads(meta_path.read_text(encoding="utf-8"))


def final_report(jsonl_path: Path) -> str:
    """Return a subagent's hand-back text for INTERNAL parsing only.

    Prefers the last SubagentHandback tool input; falls back to the last
    non-empty assistant text block. Never written to any output.
    """
    handback: str | None = None
    last_text: str | None = None
    for _, rec in iter_jsonl(jsonl_path):
        if rec.get("type") != "assistant":
            continue
        for block in rec.get("message", {}).get("content", []) or []:
            if block.get("type") == "tool_use" and block.get("name") == "SubagentHandback":
                handback = str(block.get("input", {}).get("message", ""))
            elif block.get("type") == "text" and str(block.get("text", "")).strip():
                last_text = str(block["text"])
    return handback or last_text or ""


# --------------------------------------------------------------------------
# transforms
# --------------------------------------------------------------------------

def parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def to_utc_str(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def to_local_str(ts: datetime) -> str:
    return ts.astimezone(LOCAL_TZ).isoformat(timespec="seconds")


def session_part_bounds(timestamps: list[datetime]) -> list[datetime]:
    """Start time of each session part, split on idle gaps > SESSION_GAP_HOURS."""
    if not timestamps:
        return []
    ordered = sorted(timestamps)
    starts = [ordered[0]]
    gap = pd.Timedelta(hours=SESSION_GAP_HOURS).to_pytimedelta()
    for prev, cur in zip(ordered, ordered[1:]):
        if cur - prev > gap:
            starts.append(cur)
    return starts


def active_intervals(timestamps: list[datetime]) -> list[tuple[datetime, datetime]]:
    """Merge request timestamps into intervals of continuous activity.

    Rule: sort all request start times (main agent and every subagent
    together); consecutive requests no more than ACTIVE_GAP_MINUTES apart
    belong to the same interval. Active time is the summed length of the
    intervals, so parallel subagents are counted once, never added up. An
    isolated request contributes zero length.
    """
    if not timestamps:
        return []
    gap = pd.Timedelta(minutes=ACTIVE_GAP_MINUTES).to_pytimedelta()
    ordered = sorted(timestamps)
    intervals: list[tuple[datetime, datetime]] = []
    start = end = ordered[0]
    for ts in ordered[1:]:
        if ts - end <= gap:
            end = ts
        else:
            intervals.append((start, end))
            start = end = ts
    intervals.append((start, end))
    return intervals


def session_part(ts: datetime, starts: list[datetime]) -> int:
    part = 1
    for i, start in enumerate(starts, start=1):
        if ts >= start:
            part = i
    return part


_ROLE_RULES: list[tuple[str, str]] = [
    (r"analytics", "other"),
    (r"a/b", "ab-judge"),
    (r"editor (?:critique|review)", "critic-editor"),
    (r"mean-commenter|crowd|first-time viewer", "crowd"),
    (r"research|fact-check|safety-vet", "researcher"),
    (r"patch|builder|compose|build", "builder"),
]


def role_for(description: str | None, is_subagent: bool) -> str:
    """Bucket an agent by its spawn description (first matching rule wins)."""
    if not is_subagent:
        return "main"
    text = (description or "").lower()
    for pattern, role in _ROLE_RULES:
        if re.search(pattern, text):
            return role
    return "other"


_USER_PATH = re.compile(r"(?i)((?:[a-z]:)?[\\/]+(?:users|home)[\\/]+)[^\\/\s]+")


def redact_user(text: str) -> str:
    """Replace the account-name segment of a home path with <user>."""
    return _USER_PATH.sub(r"\1<user>", text)


def write_csv(rows: list[dict], columns: list[str], name: str) -> Path:
    """Write rows with a pinned column order; unknown keys are a bug, so fail."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for row in rows:
        extra = set(row) - set(columns)
        if extra:
            raise ValueError(f"{name}: unexpected columns {sorted(extra)}")
    frame = pd.DataFrame(rows, columns=columns)
    # integer columns that contain NULLs would otherwise be written as floats
    for col in columns:
        values = [r.get(col) for r in rows if r.get(col) is not None and r.get(col) != ""]
        if values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            frame[col] = pd.array([r.get(col) if r.get(col) != "" else None for r in rows], dtype="Int64")
    path = RAW_DIR / name
    frame.to_csv(path, index=False, lineterminator="\n")
    return path
