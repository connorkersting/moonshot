"""Run a MOONSHOT review panel: py panel.py N --vs M [--skip gemini,...].

Steps: qc, audio, techqc, metrics, snapshot, cuts, ab, codex, gemini.
Use --timeout STEP=SECONDS to override a step's limit. Failures/timeouts
are logged and do not prevent remaining steps or scorecard merging.
Claude's A/B judge, Fable editor and crowd are manual: their input paths
are printed, with the blind A/B key excluded from the judge's list.
This script never opens .env or reads an environment credential's value.
A .env-only credential cannot be verified without opening it, so Gemini
requires environment-key presence and runs from an empty working folder.
--selftest exercises fake reports without executing subprocesses.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch


def _build_total() -> float:
    """Trailer length from the current build.py (v17 grew it from 81.8 to 87.0 s); 81.8 if unreadable."""
    text = (Path(__file__).resolve().parent / "build.py").read_text(encoding="utf-8")
    m = re.search(r"^TOTAL\s*=\s*([0-9.]+)", text, flags=re.M)
    return float(m.group(1)) if m else 81.8


TOTAL_S = _build_total()

sys.dont_write_bytecode = True

from eval_snapshot import EXPORTS, WORK, sha256  # noqa: E402

DEFAULT_TIMEOUTS = {
    "qc": 300.0, "audio": 1800.0, "techqc": 600.0,
    "metrics": 600.0, "snapshot": 90.0, "cuts": 1200.0,
    "ab": 600.0, "codex": 1900.0, "gemini": 1800.0,
}
ALIASES = {
    "audio_qc": "audio", "trailer_metrics": "metrics",
    "eval_snapshot": "snapshot", "cut_review": "cuts",
    "codex_critic": "codex", "gemini_critic": "gemini",
}


@dataclass(frozen=True)
class Step:
    """One independently skippable, bounded script invocation."""

    name: str
    command: list[str]
    timeout: float


def selftest() -> None:
    """Test real report parsing, partial merging and immutable evidence."""
    with tempfile.TemporaryDirectory(prefix="panel-test-") as folder:
        base = Path(folder)
        work, exports = base / "work", base / "exports"
        work.mkdir()
        qc = exports / "qc" / "v9"
        qc.mkdir(parents=True)
        audio = (
            "# Audio QC v9\n\n## Per section\n"
            "| section | t | I (LUFS) | LRA | TP |\n"
            "|---|---|---|---|---|\n"
            "| cold open | 0.0-10.6 | -18.2 | 4.0 | -2.0 |\n"
            "| silence | 61.9-62.9 | -inf | 0.0 | -inf |\n"
            "## Dialogue-to-bed ratio per line (target >= +10 dB)\n"
            "| t | speaker | line | dialog dB | bed dB | ratio |\n"
            "|---|---|---|---|---|---|\n"
            "| 2.20 | LC | Ignition | -24.0 | -35.0 | +11.0 |\n"
            "| 40.50 | EAGLE | Alarm | -22.0 | -28.5 | +6.5 LOW |\n"
            "## Click/pop scan at joins\n"
            "| t | join | spike |\n|---|---|---|\n"
            "| 40.30 | music in | 3.1x |\n"
            "| 40.50 | dialog in | 4.0x |\n"
            "| 41.50 | dialog out | 3.0x |\n"
            "## Whisper on the final mix vs captions\n"
            "| t | speaker | caption | recall | whisper heard |\n"
            "|---|---|---|---|---|\n"
            "| 40.50 | EAGLE | Program alarm. | 0.50 LOW | alarm |\n"
            "| 42.00 | EAGLE | LOW fuel. | 1.00 | low fuel |\n"
        )
        (qc / "audio_qc.md").write_text(audio, encoding="utf-8")
        (qc / "techqc.json").write_text(
            json.dumps({"flags": ["freeze run"], "status": "FAIL"}),
        )
        (qc / "trailer_metrics.json").write_text(json.dumps({
            "version": 9, "rules": [
                {"rule": "hook", "status": "PASS", "measurement": 1},
                {"rule": "button", "status": "WARN", "measurement": 9},
            ],
        }))
        (qc / "codex_critic.json").write_text(
            json.dumps({"scores": {"overall": 7.5}}),
        )
        (qc / "gemini_critic.json").write_text(
            json.dumps({"scores": {"overall": 8.0}}),
        )
        ab = exports / "qc" / "ab_v9_v8"
        ab.mkdir()
        (ab / "1_cold_open.jpg").write_bytes(b"sheet")
        key = work / "ab_key_v9_v8.json"
        key.write_text("THIS KEY MUST NEVER BE PARSED")
        with (
            patch("subprocess.run", side_effect=AssertionError("process")),
            patch("subprocess.Popen", side_effect=AssertionError("process")),
        ):
            card = merge_scorecard(9, 8, work, exports)
            assert card["loudness_by_section"]["cold open"]["I_LUFS"] == -18.2
            assert card["loudness_by_section"]["silence"]["I_LUFS"] == "-inf"
            assert card["min_dialogue_ratio_db"] == 6.5
            assert card["click_count_above_3x"] == 2
            assert len(card["whisper_low_lines"]) == 1
            assert card["techqc_flags"] == ["freeze run"]
            statuses = [row["status"]
                        for row in card["trailer_metrics_rules"]]
            assert statuses == ["PASS", "WARN"]
            assert card["codex_scores"] == {"overall": 7.5}
            assert card["gemini_scores"] == {"overall": 8.0}
            assert card["paths"]["ab_key"] == str(key)
            assert card["paths"]["ab_sheets"] == [str(ab / "1_cold_open.jpg")]
            # Frozen audio wins over a changed live report.
            frozen = qc / "snapshot_evidence" / "fake" / "audio_qc.md"
            frozen.parent.mkdir(parents=True)
            frozen.write_text(audio, encoding="utf-8")
            (qc / "snapshot.json").write_text(json.dumps({
                "version": 9, "tables": {}, "evidence": {
                    "audio_qc.md": {
                        "path": frozen.relative_to(qc).as_posix(),
                        "sha256": sha256(frozen),
                    },
                },
            }))
            (qc / "audio_qc.md").write_text("new report")
            frozen_card = merge_scorecard(9, 8, work, exports)
            assert frozen_card["min_dialogue_ratio_db"] == 6.5
            assert frozen_card["paths"]["audio_qc"] == str(frozen)
            assert frozen_card["trailer_metrics_rules"] is None
            frozen.write_text("damaged evidence")
            damaged = merge_scorecard(9, 8, work, exports)
            assert damaged["min_dialogue_ratio_db"] is None
            assert damaged["errors"]
            # Missing and malformed reports must not look like passes.
            (qc / "gemini_critic.json").write_text("bad JSON")
            partial = merge_scorecard(10, 8, work, exports)
            assert partial["click_count_above_3x"] is None
            assert partial["codex_scores"] is None
            bad = merge_scorecard(9, 8, work, exports)
            assert bad["gemini_scores"] is None and bad["errors"]
            empty = parse_audio("## Click/pop scan at joins\nnone above 3x\n")
            assert empty["click_count_above_3x"] == 0
            assert empty["whisper_low_lines"] is None
            assert normalize_step("audio_qc.py") == "audio"
            steps = make_steps(9, 8, qc, work, exports, DEFAULT_TIMEOUTS)
            assert steps[2].command[-3:] == [
                f"61.9-63.1,79.0-{TOTAL_S:.1f}", "--json", str(qc / "techqc.json"),
            ]
            json.dumps(card, allow_nan=False)
    print("panel selftest passed: reports, partial merge, freeze, key paths.")


def numeric(text: str) -> float | str | None:
    """Parse report numbers without emitting nonstandard JSON infinity."""
    match = re.match(r"\s*([+-]?(?:\d+(?:\.\d*)?|inf|nan))", text, re.I)
    if not match:
        return None
    value = float(match.group(1))
    return value if math.isfinite(value) else match.group(1).lower()


def parse_audio(text: str) -> dict[str, Any]:
    """Read audio_qc's Markdown sections, distinguishing absent from zero."""
    section = ""
    loudness: dict[str, Any] = {}
    ratios: list[float] = []
    clicks: int | None = None
    low: list[dict[str, Any]] | None = None
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].lower()
            if section.startswith("click/pop"):
                clicks = 0
            if section.startswith("whisper"):
                low = []
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[-:\s]*", cell) for cell in cells):
            continue
        if section.startswith("per section") and len(cells) == 5:
            if cells[0].lower() == "section":
                continue
            loudness[cells[0]] = {
                "time_s": cells[1], "I_LUFS": numeric(cells[2]),
                "LRA_LU": numeric(cells[3]), "TP_dBTP": numeric(cells[4]),
            }
        elif section.startswith("dialogue-to-bed") and len(cells) == 6:
            ratio = numeric(cells[5])
            if isinstance(ratio, float):
                ratios.append(ratio)
        elif section.startswith("click/pop") and len(cells) == 3:
            ratio = numeric(cells[2])
            if isinstance(ratio, float) and ratio > 3.0:
                clicks = (clicks or 0) + 1
        elif section.startswith("whisper") and len(cells) == 5:
            if re.search(r"\bLOW\b", cells[3]) and low is not None:
                low.append({
                    "time_s": numeric(cells[0]), "speaker": cells[1],
                    "caption": cells[2], "recall": numeric(cells[3]),
                    "heard": cells[4],
                })
    return {
        "loudness_by_section": loudness or None,
        "min_dialogue_ratio_db": min(ratios) if ratios else None,
        "click_count_above_3x": clicks,
        "whisper_low_lines": low,
    }


def read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    """Load optional JSON, recording malformed reports instead of failing."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"),
                          parse_constant=invalid_constant)
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data
    except (OSError, ValueError) as error:
        errors.append(f"{path}: {error}")
        return None


def invalid_constant(value: str) -> None:
    """Reject NaN/Infinity rather than poison the merged JSON document."""
    raise ValueError(f"Invalid JSON number: {value}")


def frozen_path(
    qc: Path, name: str, snapshot: dict[str, Any] | None,
    frozen: bool, errors: list[str],
) -> Path | None:
    """Use hashed copies exclusively when a snapshot is present."""
    if not frozen:
        path = qc / name
        return path if path.is_file() else None
    if snapshot is None:
        return None
    try:
        item = snapshot.get("evidence", {}).get(name)
        if item is None:
            return None
        path = (qc / item["path"]).resolve()
        if not path.is_relative_to((qc / "snapshot_evidence").resolve()):
            raise ValueError("Frozen evidence path escapes snapshot_evidence")
        if sha256(path) != item["sha256"]:
            raise ValueError("Frozen evidence hash mismatch")
        return path
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        errors.append(f"{name}: {error}")
        return None


def merge_scorecard(
    version: int, versus: int, work: Path, exports: Path,
) -> dict[str, Any]:
    """Merge available measurements and critic scores without opening keys."""
    qc = exports / "qc" / f"v{version}"
    errors: list[str] = []
    snapshot_path = qc / "snapshot.json"
    frozen = snapshot_path.exists()
    snapshot = read_json(snapshot_path, errors)
    if snapshot and snapshot.get("version") != version:
        errors.append("Snapshot version mismatch")
        snapshot = None
    audio_path = frozen_path(qc, "audio_qc.md", snapshot, frozen, errors)
    audio = ""
    if audio_path:
        try:
            audio = audio_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            errors.append(f"{audio_path}: {error}")
    card = parse_audio(audio)
    tech_path = frozen_path(qc, "techqc.json", snapshot, frozen, errors)
    metrics_path = frozen_path(
        qc, "trailer_metrics.json", snapshot, frozen, errors,
    )
    tech = read_json(tech_path, errors) if tech_path else None
    metrics = read_json(metrics_path, errors) if metrics_path else None
    codex = read_json(qc / "codex_critic.json", errors)
    gemini = read_json(qc / "gemini_critic.json", errors)
    ab = exports / "qc" / f"ab_v{version}_v{versus}"
    key = work / f"ab_key_v{version}_v{versus}.json"
    if frozen:
        evidence = snapshot.get("evidence", {}) if snapshot else {}
        names = sorted(name for name in evidence
                       if name.startswith(("key_", "k360_")))
    else:
        names = sorted(path.name for path in qc.glob("k360_*")
                       if path.is_file())
        if not names:
            names = sorted(path.name for path in qc.glob("key_*")
                           if path.is_file())
    keys = [path for name in names if (
        path := frozen_path(qc, name, snapshot, frozen, errors)
    ) is not None]
    contact = frozen_path(qc, "contact.jpg", snapshot, frozen, errors)
    cuts_index = qc / "cuts" / "cuts_index.png"
    if not cuts_index.is_file():
        cuts_index = qc / "cuts_index.png"
    card.update({
        "version": version, "versus": versus,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "measurement_source": "snapshot" if frozen else "live QC",
        "techqc_flags": tech.get("flags") if tech else None,
        "techqc_status": tech.get("status") if tech else None,
        "trailer_metrics_rules": metrics.get("rules") if metrics else None,
        "codex_scores": codex.get("scores") if codex else None,
        "gemini_scores": gemini.get("scores") if gemini else None,
        "paths": {
            "video": str(exports / "versions" / f"moonshot_v{version}.mp4"),
            "snapshot": str(snapshot_path) if frozen else None,
            "contact": str(contact) if contact else None,
            "keys": [str(path) for path in keys],
            "audio_qc": str(audio_path) if audio_path else None,
            "techqc": str(tech_path) if tech_path else None,
            "trailer_metrics": str(metrics_path) if metrics_path else None,
            "cuts_index": str(cuts_index) if cuts_index.is_file() else None,
            "cut_sheets": [str(path) for path in sorted(
                (qc / "cuts").glob("cut_*.png"),
            )],
            "ab_sheets": [str(path) for path in sorted(ab.glob("*.jpg"))],
            "ab_key": str(key) if key.is_file() else None,
        },
        "errors": errors,
    })
    card["missing"] = [
        name for name in (
            "loudness_by_section", "min_dialogue_ratio_db",
            "click_count_above_3x", "whisper_low_lines", "techqc_flags",
            "trailer_metrics_rules", "codex_scores", "gemini_scores",
        ) if card[name] is None
    ]
    return card


def normalize_step(name: str) -> str:
    """Accept short step names and existing script stems."""
    name = name.strip().lower().removesuffix(".py")
    name = ALIASES.get(name, name)
    if name not in DEFAULT_TIMEOUTS:
        raise ValueError(f"Unknown step: {name}")
    return name


def make_steps(
    version: int, versus: int, qc: Path, work: Path, exports: Path,
    timeouts: dict[str, float],
) -> list[Step]:
    """Match existing script interfaces and requested execution order."""
    video = exports / "versions" / f"moonshot_v{version}.mp4"
    specifications = [
        ("qc", "qc.py", [str(version)]),
        ("audio", "audio_qc.py", [str(version)]),
        ("techqc", "techqc.py", [
            str(video), "--intended-black", f"61.9-63.1,79.0-{TOTAL_S:.1f}",
            "--json", str(qc / "techqc.json"),
        ]),
        ("metrics", "trailer_metrics.py", [
            str(version), "--json", str(qc / "trailer_metrics.json"),
        ]),
        ("snapshot", "eval_snapshot.py", [str(version)]),
        ("cuts", "cut_review.py", [str(version)]),
        ("ab", "ab.py", [str(version), str(versus)]),
        ("codex", "codex_critic.py", [str(version)]),
        ("gemini", "gemini_critic.py", [str(version)]),
    ]
    return [Step(name, [sys.executable, "-B", str(work / script), *args],
                 timeouts[name]) for name, script, args in specifications]


def stop_tree(process: subprocess.Popen[bytes]) -> None:
    """Terminate nested ffmpeg/critic workers when their step times out."""
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15, check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            pass


def run_step(step: Step, cwd: Path, log: Path) -> dict[str, Any]:
    """Stream subprocess output to the log and continue after errors."""
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[{step.name}] running (timeout {step.timeout:g}s)", flush=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"\n{stamp} [{step.name}] {step.command!r}\n")
        handle.flush()
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                step.command, cwd=cwd, stdout=handle, stderr=handle,
                start_new_session=os.name != "nt",
            )
            code = process.wait(timeout=step.timeout)
            result: dict[str, Any] = {
                "step": step.name, "status": "ok" if code == 0 else "failed",
                "returncode": code,
            }
        except subprocess.TimeoutExpired:
            if process:
                stop_tree(process)
            result = {"step": step.name, "status": "timeout"}
        except OSError as error:
            result = {"step": step.name, "status": "failed",
                      "error": str(error)}
        except KeyboardInterrupt:
            if process:
                stop_tree(process)
            raise
        handle.write(f"\nRESULT {json.dumps(result)}\n")
    print(f"[{step.name}] {result['status']}", flush=True)
    return result


def manual_inputs(card: dict[str, Any]) -> None:
    """Print ready-to-paste Claude inputs without leaking the blind key."""
    paths = card["paths"]
    print("\nClaude A/B judge inputs (blind sheets):")
    for path in paths["ab_sheets"]:
        print(f"  {path}")
    if not paths["ab_sheets"]:
        print("  No A/B sheets available.")
    inputs = [paths[name] for name in (
        "video", "snapshot", "contact", "audio_qc", "trailer_metrics",
        "techqc", "cuts_index",
    ) if paths[name]] + paths["keys"] + paths["cut_sheets"]
    for role in ("Fable editor", "crowd"):
        print(f"\nClaude {role} inputs:")
        for path in inputs:
            print(f"  {path}")
    if paths["ab_key"]:
        print(f"\nA/B key for adjudicator only: {paths['ab_key']}")


def main() -> None:
    """Run the panel or its dependency-free merge selftest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=int, nargs="?", metavar="N")
    parser.add_argument("--vs", type=int, metavar="M")
    parser.add_argument("--skip", default="", metavar="STEP,STEP,...")
    parser.add_argument("--timeout", action="append", default=[],
                        metavar="STEP=SECONDS")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if args.version is None or args.version < 1 or not args.vs or args.vs < 1:
        parser.error("positive N and --vs M are required")
    timeouts = DEFAULT_TIMEOUTS.copy()
    try:
        skipped = {normalize_step(name) for name in args.skip.split(",")
                   if name.strip()}
        for override in args.timeout:
            name, value = override.split("=", 1)
            seconds = float(value)
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("Timeout must be positive and finite")
            timeouts[normalize_step(name)] = seconds
    except ValueError as error:
        parser.error(str(error))
    qc = EXPORTS / "qc" / f"v{args.version}"
    qc.mkdir(parents=True, exist_ok=True)
    log = qc / "panel_log.txt"
    results: list[dict[str, Any]] = []
    try:
        for step in make_steps(args.version, args.vs, qc, WORK, EXPORTS,
                               timeouts):
            reason: str | None = None
            if step.name in skipped:
                reason = "requested --skip"
            elif step.name == "gemini" and "GEMINI_API_KEY" not in os.environ:
                exists = (WORK / ".env").is_file()
                reason = (
                    ".env exists, but its key cannot be checked without "
                    "reading it; set GEMINI_API_KEY in the environment"
                    if exists else "GEMINI_API_KEY absent; no .env file"
                )
            if reason:
                result = {"step": step.name, "status": "skipped",
                          "reason": reason}
                with log.open("a", encoding="utf-8") as handle:
                    handle.write(f"{json.dumps(result)}\n")
                print(f"[{step.name}] skipped: {reason}", flush=True)
            elif step.name == "gemini":
                # Even an empty env key cannot trigger reading work/.env.
                with tempfile.TemporaryDirectory(
                    prefix="panel-gemini-",
                ) as tmp:
                    result = run_step(step, Path(tmp), log)
            else:
                result = run_step(step, WORK, log)
            results.append(result)
    finally:
        card = merge_scorecard(args.version, args.vs, WORK, EXPORTS)
        card["steps"] = results
        scorecard = qc / "scorecard.json"
        scorecard.write_text(
            f"{json.dumps(card, indent=2, allow_nan=False)}\n",
            encoding="utf-8",
        )
        print(f"\nScorecard: {scorecard}\nLog: {log}")
        manual_inputs(card)


if __name__ == "__main__":
    main()
