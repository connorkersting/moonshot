"""Parse the MOONSHOT run artefacts into tidy tables.

Run from the analytics/ folder:  uv run python ingest/parse_artifacts.py

Reads (read-only):
  $MOONSHOT_WORK     git tags, ab_key_vN_vM.json, qcN.txt, aqcN.txt, tqcN.txt
  $MOONSHOT_EXPORTS  PROGRESS.md (score table), BEST.json, run_ledger.csv,
                     versions/moonshot_vN.mp4 (mtime), qc/vN/*.json (Fable, Codex, Gemini,
                     TwelveLabs and crowd scores) and qc/ab_vN_vM/judge_sonnet.json
  ingest/crowd_scores_progress.csv  crowd scores that exist only as prose in PROGRESS.md
  subagent transcripts (A/B judge and editor critic hand-back reports, parsed
  in memory for structured fields only)

Writes to analytics/data/raw/:
  versions.csv, critic_scores.csv, ab_votes.csv, qc_sections.csv, qc_dialogue.csv,
  loop_segments.csv, director_picks.csv
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import (
    LOCAL_TZ,
    RAW_DIR,
    SchemaDriftError,
    final_report,
    read_meta,
    require_dir,
    subagent_files,
    to_local_str,
    write_csv,
)

CATEGORIES: list[tuple[str, str]] = [
    # (canonical name, regex on the row label); order matters for "overall"
    ("hook", r"^hook"),
    ("pacing", r"^pacing"),
    ("variety", r"^visual variety|^variety"),
    ("motion", r"^motion"),
    ("type", r"^typo|^type"),
    ("color", r"^colou?r"),
    ("sound", r"^sound"),
    ("captions", r"^captions?"),
    ("story", r"^story"),
    ("overall", r"^overall"),
]
PROGRESS_SCORE_HEADER = ["version", "hook", "pacing", "variety", "motion", "type", "color",
                         "sound", "captions", "story", "overall"]
# Key names used by the JSON critic files (fable_editor, codex_critic, gemini, twelvelabs)
# mapped to the ten canonical editor categories above.
JSON_CATEGORY_MAP = {
    "hook": "hook", "pacing": "pacing", "visual_variety": "variety", "motion_design": "motion",
    "typography_collisions": "type", "colour": "color", "sound_design_mix": "sound",
    "captions": "captions", "storytelling": "story", "overall": "overall",
}
LEDGER_HEADER = ["segment", "start_local_edt", "end_local_edt", "end_reason", "note"]
LOOP_SEGMENT_COLUMNS = ["segment_id", "start_local", "end_local", "start_utc", "end_utc", "end_reason"]
CROWD_CATEGORIES = ["shareability", "ai_slop_perception", "would_watch_to_end"]
CROWD_PROGRESS_FILE = Path(__file__).resolve().parent / "crowd_scores_progress.csv"
DIRECTOR_PICKS_FILE = Path(__file__).resolve().parent / "director_picks.csv"
DIRECTOR_PICKS_HEADER = ["pick_id", "decided_at_local", "subject", "key_file", "clip_key", "side_picked",
                         "option_text", "adopted", "version_effect", "source_ref"]
DIRECTOR_PICK_COLUMNS = ["pick_id", "decided_at_local", "decided_at_utc", "subject", "key_file", "clip_key",
                         "side_picked", "option_picked", "mapped_through_key", "adopted", "version_effect",
                         "source_ref"]
AQC_SECTION_HEADER = ["section", "t", "I (LUFS)", "LRA", "TP"]
AQC_RATIO_HEADER = ["t", "speaker", "line", "dialog dB", "bed dB", "ratio"]
AQC_WHISPER_HEADER = ["t", "speaker", "caption", "recall", "whisper heard"]
CONFIDENCE_RANK = {"low": 1.0, "low-med": 1.5, "med": 2.0, "med-high": 2.5, "high": 3.0}

VERSION_COLUMNS = [
    "version", "version_label", "src_tag_time", "final_tag_time", "export_time",
    "progress_logged_time", "is_best_final", "duration_s", "integrated_lufs", "lra_lu",
    "true_peak_dbtp", "tqc_verdict", "tqc_black_runs", "tqc_freeze_runs",
    "tqc_click_candidates", "tqc_flag_count", "has_qc", "has_aqc", "has_tqc",
]
SCORE_COLUMNS = [
    "version", "critic", "category", "score", "critic_model", "evaluation_id", "source_kind",
    "progress_md_score", "progress_md_flagged", "note",
]
AB_COLUMNS = [
    "evaluation_id", "comparison", "repeat_no", "newer_version", "older_version",
    "section_no", "section", "side_A_version", "side_B_version", "side_picked",
    "is_tie", "version_picked", "newer_outcome", "is_marginal", "confidence",
    "confidence_rank", "confidence_raw", "score_A", "score_B", "judge_model",
]
QC_SECTION_COLUMNS = ["version", "section_no", "section", "t0", "t1", "lufs", "lra", "tp"]
QC_DIALOGUE_COLUMNS = [
    "version", "line_no", "t", "speaker", "dialog_db", "bed_db", "ratio_db",
    "ratio_low_flag", "whisper_recall", "recall_low_flag",
]

_NUM = re.compile(r"^\s*([+-]?\d+(?:\.\d+)?)")


def num(text: str) -> float | None:
    m = _NUM.match(text.replace("−", "-"))
    return float(m.group(1)) if m else None


def md_table(lines: list[str], start: int) -> tuple[list[str], list[list[str]]]:
    """Parse a markdown table starting at ``lines[start]`` (the header row)."""
    header = [c.strip() for c in lines[start].strip().strip("|").split("|")]
    rows: list[list[str]] = []
    for line in lines[start + 2:]:
        if not line.strip().startswith("|"):
            break
        rows.append([c.strip() for c in line.strip().strip("|").split("|")])
    return header, rows


# --------------------------------------------------------------------------
# versions
# --------------------------------------------------------------------------

def git_tags(work: Path) -> dict[str, str]:
    proc = subprocess.run(
        ["git", "-C", str(work), "for-each-ref", "refs/tags",
         "--format=%(refname:short)|%(creatordate:iso-strict)"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print("warning: MOONSHOT_WORK is not a git repository; tag times left NULL")
        return {}
    out = proc.stdout
    return dict(line.split("|", 1) for line in out.splitlines() if "|" in line)


def parse_tqc(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    flags = [ln for ln in lines if ln.startswith("FLAG:")]
    counts = {"black": None, "freeze": None, "click": None}
    for flag in flags:
        for key, pat in (("black", r"(\d+) black runs"), ("freeze", r"(\d+) freeze runs"), ("click", r"(\d+) click candidates")):
            m = re.search(pat, flag)
            if m:
                counts[key] = int(m.group(1))
    verdict = next((ln.strip() for ln in reversed(lines) if ln.strip() in ("PASS", "FAIL")), None)
    return {"verdict": verdict, "flag_count": len(flags), **counts}


def parse_techqc_json(path: Path) -> dict:
    """The v23+ tech-QC file: one FLAG string like '5 black runs; 1 freeze runs; 3808 click candidates'."""
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    flags = obj.get("flags")
    if not isinstance(flags, list):
        raise SchemaDriftError(path.name, "flags", "a list of strings", type(flags).__name__)
    counts = {"black": None, "freeze": None, "click": None}
    for flag in flags:
        for key, pat in (("black", r"(\d+) black runs"), ("freeze", r"(\d+) freeze runs"), ("click", r"(\d+) click candidates")):
            m = re.search(pat, flag)
            if m:
                counts[key] = int(m.group(1))
    # the .txt report ends with PASS or FAIL: FAIL whenever there is any flag
    return {"verdict": "FAIL" if flags else "PASS", "flag_count": len(flags), **counts}


def parse_qc_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").lstrip()
    obj, _ = json.JSONDecoder().raw_decode(text)
    for key in ("duration", "integrated_LUFS", "LRA", "true_peak_dBTP"):
        if key not in obj:
            raise SchemaDriftError(path.name, key, "present in qc JSON", "missing")
    return obj


def progress_scores(progress: Path) -> tuple[dict[int, dict[str, tuple[float | None, bool]]], dict[int, str], int | None]:
    """Score table from PROGRESS.md: {version: {category: (score, flagged)}}, logged times, best version."""
    lines = progress.read_text(encoding="utf-8").splitlines()
    start_date = next((m.group(1) for ln in lines if (m := re.match(r"START:\s*(\d{4}-\d{2}-\d{2})", ln))), None)
    best = next((int(m.group(1)) for ln in lines if (m := re.match(r"BEST:\s*v(\d+)", ln))), None)
    idx = next((i for i, ln in enumerate(lines) if ln.strip() == "## Scores"), None)
    scores: dict[int, dict[str, tuple[float | None, bool]]] = {}
    logged: dict[int, str] = {}
    if idx is None:
        return scores, logged, best
    header_idx = next(i for i in range(idx, len(lines)) if lines[i].strip().startswith("|"))
    header, rows = md_table(lines, header_idx)
    norm = [h.lower() for h in header[:11]]
    if norm != PROGRESS_SCORE_HEADER:
        raise SchemaDriftError("PROGRESS.md", "score table header", str(PROGRESS_SCORE_HEADER), str(norm))
    for row in rows:
        m = re.match(r"v(\d+)(?:\s*\((\d{2}:\d{2})\))?", row[0])
        if not m:
            continue
        version = int(m.group(1))
        if m.group(2) and start_date:
            logged[version] = f"{start_date}T{m.group(2)}:00"
        cells = {}
        for cat, cell in zip(PROGRESS_SCORE_HEADER[1:], row[1:11]):
            value = num(cell)
            # anything beyond the bare number (asterisk, "(measured)", notes) is a flag
            flagged = value is not None and cell.strip() != (f"{value:g}" if value % 1 else f"{int(value)}")
            cells[cat] = (value, flagged)
        scores[version] = cells
    return scores, logged, best


def build_versions(work: Path, exports: Path, logged: dict[int, str], best: int | None, qc_root: Path) -> list[dict]:
    tags = git_tags(work)
    found: set[int] = set()
    for pat, rx in (("moonshot_v*.mp4", r"moonshot_v(\d+)\.mp4"),):
        for p in (exports / "versions").glob(pat):
            found.add(int(re.fullmatch(rx, p.name).group(1)))
    for p in work.glob("*qc*.txt"):
        m = re.fullmatch(r"(?:a|t)?qc(\d+)\.txt", p.name)
        if m:
            found.add(int(m.group(1)))
    for tag in tags:
        m = re.fullmatch(r"v(\d+)-(?:src|final)", tag)
        if m:
            found.add(int(m.group(1)))
    found |= set(logged)
    rows = []
    for v in sorted(found):
        mp4 = exports / "versions" / f"moonshot_v{v}.mp4"
        qc, aqc, tqc = work / f"qc{v}.txt", work / f"aqc{v}.txt", work / f"tqc{v}.txt"
        # v23 on, the loop wrote its QC only to exports/qc/vN/{qc,techqc}.json; use those when the
        # work folder's qcN.txt / tqcN.txt do not exist (same content, same parsers).
        qc_alt, tq_alt = qc_root / f"v{v}" / "qc.json", qc_root / f"v{v}" / "techqc.json"
        if not qc.exists() and qc_alt.exists():
            qc = qc_alt
        qcj = parse_qc_json(qc) if qc.exists() else {}
        if tqc.exists():
            tq = parse_tqc(tqc)
        elif tq_alt.exists():
            tq = parse_techqc_json(tq_alt)
            tqc = tq_alt
        else:
            tq = {}
        export_time = (
            to_local_str(datetime.fromtimestamp(mp4.stat().st_mtime, tz=timezone.utc)) if mp4.exists() else None
        )
        rows.append({
            "version": v,
            "version_label": f"v{v}",
            "src_tag_time": tags.get(f"v{v}-src"),
            "final_tag_time": tags.get(f"v{v}-final"),
            "export_time": export_time,
            "progress_logged_time": logged.get(v),
            "is_best_final": best == v,
            "duration_s": float(qcj["duration"]) if qcj else None,
            "integrated_lufs": float(qcj["integrated_LUFS"]) if qcj else None,
            "lra_lu": float(qcj["LRA"]) if qcj else None,
            "true_peak_dbtp": float(qcj["true_peak_dBTP"]) if qcj else None,
            "tqc_verdict": tq.get("verdict"),
            "tqc_black_runs": tq.get("black"),
            "tqc_freeze_runs": tq.get("freeze"),
            "tqc_click_candidates": tq.get("click"),
            "tqc_flag_count": tq.get("flag_count"),
            "has_qc": qc.exists(),
            "has_aqc": aqc.exists(),
            "has_tqc": tqc.exists(),
        })
    return rows


# --------------------------------------------------------------------------
# audio QC
# --------------------------------------------------------------------------

def find_header(lines: list[str], header: list[str], source: str, required: bool) -> int | None:
    for i, ln in enumerate(lines):
        cells = [c.strip() for c in ln.strip().strip("|").split("|")] if ln.strip().startswith("|") else []
        if cells == header:
            return i
    if required:
        raise SchemaDriftError(source, "table header", str(header), "not found")
    return None


def parse_aqc(path: Path, version: int) -> tuple[list[dict], list[dict]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    sec_rows: list[dict] = []
    h = find_header(lines, AQC_SECTION_HEADER, path.name, required=True)
    for i, row in enumerate(md_table(lines, h)[1], start=1):
        t0, t1 = (float(x) for x in row[1].split("-", 1))
        sec_rows.append({"version": version, "section_no": i, "section": row[0], "t0": t0, "t1": t1,
                         "lufs": num(row[2]), "lra": num(row[3]), "tp": num(row[4])})
    dlg: dict[float, dict] = {}
    # v22 on, the report says "(no dlg/bed stems saved for this version; ratio skipped)" and has no ratio
    # table. That marker is the only accepted reason for its absence; the whisper table then defines the lines.
    ratio_skipped = any(ln.strip().startswith("(no dlg/bed stems saved") for ln in lines)
    h = find_header(lines, AQC_RATIO_HEADER, path.name, required=not ratio_skipped)
    if h is not None:
        for i, row in enumerate(md_table(lines, h)[1], start=1):
            t = round(float(row[0]), 2)
            dlg[t] = {"version": version, "line_no": i, "t": t, "speaker": row[1],
                      "dialog_db": num(row[3]), "bed_db": num(row[4]), "ratio_db": num(row[5]),
                      "ratio_low_flag": "LOW" in row[5], "whisper_recall": None, "recall_low_flag": None}
    h = find_header(lines, AQC_WHISPER_HEADER, path.name, required=ratio_skipped)
    if h is not None:
        for i, row in enumerate(md_table(lines, h)[1], start=1):
            t = round(float(row[0]), 2)
            if t not in dlg:
                if not ratio_skipped:
                    raise SchemaDriftError(path.name, f"whisper row t={t}", "a matching dialogue-ratio row", "no match")
                dlg[t] = {"version": version, "line_no": i, "t": t, "speaker": row[1],
                          "dialog_db": None, "bed_db": None, "ratio_db": None,
                          "ratio_low_flag": None, "whisper_recall": None, "recall_low_flag": None}
            dlg[t]["whisper_recall"] = num(row[3])
            dlg[t]["recall_low_flag"] = "LOW" in row[3]
    return sec_rows, sorted(dlg.values(), key=lambda r: r["line_no"])


# --------------------------------------------------------------------------
# subagent reports: editor scores and A/B votes
# --------------------------------------------------------------------------

def editor_scores(report: str, version: int | None = None) -> dict[str, float]:
    """First score per category from a critic report.

    Handles four layouts the critic used: a markdown table (one column per version when
    the header names ``vN``; otherwise the first value column), a bullet or bold line,
    and a single line with the categories separated by ``|``.
    """
    found: dict[str, float] = {}
    value_col = 1
    for raw in report.splitlines():
        line = raw.strip()
        candidates: list[tuple[str, float | None]] = []
        if line.startswith("|"):
            cells = [c.strip().strip("*").strip() for c in line.strip("|").split("|")]
            if version is not None and f"v{version}" in cells[1:]:
                value_col = cells.index(f"v{version}")
            if len(cells) <= value_col:
                continue
            candidates.append((cells[0].lower(), num(cells[value_col].strip("*"))))
        else:
            plain = re.sub(r"^[-*\s]+", "", line).replace("*", "")
            plain = re.sub(r"(?i)^scores?:\s*", "", plain)
            segments = [seg.strip() for seg in plain.split("|")] if plain.count("|") >= 3 else [plain]
            for seg in segments:
                m = re.match(r"^([A-Za-z][A-Za-z /&()-]*?)\s+(\d+(?:\.\d+)?)\b", seg)
                if m:
                    candidates.append((m.group(1).lower(), float(m.group(2))))
        for label, value in candidates:
            if value is None or not 0 <= value <= 10:
                continue
            for cat, rx in CATEGORIES:
                if cat not in found and re.search(rx, label):
                    found[cat] = value
                    break
    return found


_CONF_ORDER = {"low": 1, "med": 2, "high": 3}


def norm_confidence(text: str) -> str:
    """Normalise a judge's confidence wording to low / low-med / med / med-high / high.

    Handles 'low-to-medium', 'medium-low' and 'med-high' alike; the pair is put in
    ascending order. Anything else comes back unchanged so the accepted_values test
    on the fact table fails loudly.
    """
    t = text.lower().replace("medium", "med")
    words = re.findall(r"low|med|high", t)
    if len(words) == 1 and re.fullmatch(r"\W*(low|med|high)\W*", t):
        return words[0]
    if len(words) == 2 and words[0] != words[1]:
        pair = sorted(words, key=_CONF_ORDER.__getitem__)
        return "-".join(pair)
    t = re.sub(r"\s+", "", t.replace("–", "-"))
    for key in ("low-med", "med-high", "high", "med", "low"):
        if t.startswith(key):
            return key
    return t


def ab_votes_from_json(path: Path, key: dict, comparison: str, newer: int, older: int,
                       evaluation_id: str, judge_model: str) -> list[dict]:
    """Verdicts from qc/ab_vN_vM/judge_sonnet.json.

    The judge wrote four slightly different layouts over the run (sections as a list
    or a dict, ``a_total`` or ``A_total``, an overall block named differently). All are
    accepted; a missing section, an unknown winner or a missing total stops the run.
    """
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    sections = obj.get("sections")
    if isinstance(sections, dict):
        items = [{"section": k, **v} for k, v in sections.items()]
    elif isinstance(sections, list):
        items = sections
    else:
        raise SchemaDriftError(comparison, "sections", "list or dict", type(sections).__name__)
    by_name = {s["section"]: s for s in items}
    out = []
    for sec_key in sorted(key, key=lambda k: int(k.split("_", 1)[0])):
        if sec_key not in by_name:
            raise SchemaDriftError(comparison, f"section {sec_key}", "present in judge_sonnet.json", "missing")
        sec = by_name[sec_key]
        # v23 on, the judge wrote {"pick": "A|B|TIE", "confidence": <int>, "reasons": ...} with no rubric totals
        # and an integer confidence (2 was called "weak" in its report; the scale is not documented). That
        # layout is kept as `confidence_raw`; the word-scale confidence stays NULL rather than guessed.
        numeric_layout = "pick" in sec and "winner" not in sec
        winner = str(sec.get("pick" if numeric_layout else "winner", "")).strip()
        side = "TIE" if winner.lower() == "tie" else winner.upper()
        if side not in ("A", "B", "TIE"):
            raise SchemaDriftError(comparison, f"winner in {sec_key}", "A/B/tie", winner[:10] or "empty")
        totals: dict[str, float | None] = {}
        for letter in ("A", "B"):
            raw = sec.get(f"{letter}_total", sec.get(f"{letter.lower()}_total"))
            if raw is None and not numeric_layout:
                raise SchemaDriftError(comparison, f"{letter}_total in {sec_key}", "a number", "missing")
            totals[letter] = None if raw is None else float(raw)
        if numeric_layout:
            raw_conf = sec.get("confidence")
            if isinstance(raw_conf, bool) or not isinstance(raw_conf, int) or not 1 <= raw_conf <= 5:
                raise SchemaDriftError(comparison, f"confidence in {sec_key}", "integer 1..5", repr(raw_conf)[:12])
            conf, conf_raw = None, raw_conf
            reason_text = str(sec.get("reasons", ""))
        else:
            conf, conf_raw = norm_confidence(str(sec.get("confidence", ""))), None
            reason_text = str(sec.get("reason", ""))
        version = key[sec_key][side] if side != "TIE" else None
        out.append({
            "evaluation_id": evaluation_id,
            "comparison": comparison,
            "repeat_no": 1,
            "newer_version": newer,
            "older_version": older,
            "section_no": int(sec_key.split("_", 1)[0]),
            "section": sec_key,
            "side_A_version": key[sec_key]["A"],
            "side_B_version": key[sec_key]["B"],
            "side_picked": side,
            "is_tie": side == "TIE",
            "version_picked": version,
            "newer_outcome": "tie" if side == "TIE" else ("win" if version == newer else "loss"),
            "is_marginal": bool(re.search(r"(?i)marginal|narrow", reason_text)),
            "confidence": conf,
            "confidence_rank": CONFIDENCE_RANK.get(conf),
            "confidence_raw": conf_raw,
            "score_A": totals["A"],
            "score_B": totals["B"],
            "judge_model": judge_model,
        })
    return out


def ab_votes(report: str, key: dict, comparison: str, newer: int, older: int,
             evaluation_id: str, judge_model: str) -> list[dict]:
    lines = report.splitlines()
    header_idx = next(
        (i for i, ln in enumerate(lines) if ln.strip().startswith("|") and re.search(r"(?i)\|\s*section\s*\|", ln)),
        None,
    )
    if header_idx is None:
        raise SchemaDriftError(comparison, "A/B verdict table", "a '| section |' table", "none found")
    header, rows = md_table(lines, header_idx)
    cols = [h.lower() for h in header]
    pick_col = next(i for i, c in enumerate(cols) if c in ("winner", "pick"))
    conf_col = cols.index("confidence")
    a_col = next((i for i, c in enumerate(cols) if c in ("a", "a total")), None)
    b_col = next((i for i, c in enumerate(cols) if c in ("b", "b total")), None)
    sections = {int(k.split("_", 1)[0]): k for k in key}
    out = []
    for row in rows:
        m = re.match(r"(\d+)", row[0])
        if not m:
            continue
        sec_no = int(m.group(1))
        section = sections[sec_no]
        pick_cell = row[pick_col].strip()
        side = "TIE" if pick_cell.lower().startswith("tie") else pick_cell[:1].upper()
        if side not in ("A", "B", "TIE"):
            raise SchemaDriftError(comparison, f"pick in section {sec_no}", "A/B/TIE", pick_cell[:10])
        version = key[section][side] if side != "TIE" else None
        score_a = num(row[a_col]) if a_col is not None else None
        score_b = num(row[b_col]) if b_col is not None else None
        if a_col is None and side != "TIE":  # "A (7 vs 5)" form
            m2 = re.search(r"\((\d+(?:\.\d+)?)\s*vs\s*(\d+(?:\.\d+)?)\)", pick_cell)
            if m2:
                winner, loser = float(m2.group(1)), float(m2.group(2))
                score_a, score_b = (winner, loser) if side == "A" else (loser, winner)
        conf = norm_confidence(row[conf_col])
        out.append({
            "evaluation_id": evaluation_id,
            "comparison": comparison,
            "repeat_no": 1,
            "newer_version": newer,
            "older_version": older,
            "section_no": sec_no,
            "section": section,
            "side_A_version": key[section]["A"],
            "side_B_version": key[section]["B"],
            "side_picked": side,
            "is_tie": side == "TIE",
            "version_picked": version,
            "newer_outcome": "tie" if side == "TIE" else ("win" if version == newer else "loss"),
            "is_marginal": bool(re.search(r"(?i)marginal|narrow", pick_cell)),
            "confidence": conf,
            "confidence_rank": CONFIDENCE_RANK.get(conf),
            "confidence_raw": None,
            "score_A": score_a,
            "score_B": score_b,
            "judge_model": judge_model,
        })
    return out


_PLAIN_ROW = re.compile(r"^\s*(\d+)\s+([a-z_]+)\s*\|\s*(A|B|TIE)\b[^|]*\|\s*([^|]+?)\s*\|\s*(.*)$", re.I)


def plain_verdict_rows(report: str) -> list[re.Match]:
    return [m for ln in report.splitlines() if (m := _PLAIN_ROW.match(ln))]


def ab_votes_from_lines(report: str, key: dict, comparison: str, newer: int, older: int,
                        evaluation_id: str, judge_model: str) -> list[dict]:
    """Hand-back written as 'N section | WINNER | confidence | reason' lines (no leading pipe)."""
    sections = {int(k.split("_", 1)[0]): k for k in key}
    out = []
    for m in plain_verdict_rows(report):
        sec_no = int(m.group(1))
        section = sections[sec_no]
        side = m.group(3).upper()
        conf = norm_confidence(m.group(4))
        version = key[section][side] if side != "TIE" else None
        out.append({
            "evaluation_id": evaluation_id, "comparison": comparison, "repeat_no": 1,
            "newer_version": newer, "older_version": older, "section_no": sec_no, "section": section,
            "side_A_version": key[section]["A"], "side_B_version": key[section]["B"],
            "side_picked": side, "is_tie": side == "TIE", "version_picked": version,
            "newer_outcome": "tie" if side == "TIE" else ("win" if version == newer else "loss"),
            "is_marginal": bool(re.search(r"(?i)marginal|narrow", m.group(5))),
            "confidence": conf, "confidence_rank": CONFIDENCE_RANK.get(conf), "confidence_raw": None,
            "score_A": None, "score_B": None, "judge_model": judge_model,
        })
    return out


def loop_segments(exports: Path) -> list[dict]:
    """Read run_ledger.csv (the agent's own record of loop time) into loop_segments.csv.

    Times in the ledger are America/New_York wall-clock minutes. They are also written
    as UTC so they can be compared with transcript timestamps. An empty end means the
    segment is still open. The free-text note column is left out (it names people). A changed header stops the run.
    """
    import csv

    path = exports / "run_ledger.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != LEDGER_HEADER:
            raise SchemaDriftError(path.name, "header", str(LEDGER_HEADER), str(reader.fieldnames))
        rows = []
        for rec in reader:
            def to_utc(text: str) -> str | None:
                if not text.strip():
                    return None
                local = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
                return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            rows.append({
                "segment_id": int(rec["segment"]),
                "start_local": rec["start_local_edt"].strip() or None,
                "end_local": rec["end_local_edt"].strip() or None,
                "start_utc": to_utc(rec["start_local_edt"]),
                "end_utc": to_utc(rec["end_local_edt"]),
                "end_reason": rec["end_reason"].strip() or "open",
            })
    return rows


def director_picks(work: Path) -> list[dict]:
    """The director's own picks, read from ingest/director_picks.csv (hand-written, like the intervention labels).

    A pick on a blind audio audition is mapped through its key file (`ab_key_v24_sound.json`: which clip was
    the baseline and which the candidate on side A and side B), so `option_picked` is what he chose, not which
    side he heard. A pick with no key file kept (the hero clip and the slow-mo) carries the option PROGRESS.md
    records as adopted, and `mapped_through_key` is false. A changed header, an unknown side, or a key file or
    clip that is not there stops the run.
    """
    import csv

    if not DIRECTOR_PICKS_FILE.exists():
        return []
    rows: list[dict] = []
    with DIRECTOR_PICKS_FILE.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != DIRECTOR_PICKS_HEADER:
            raise SchemaDriftError(DIRECTOR_PICKS_FILE.name, "header", str(DIRECTOR_PICKS_HEADER), str(reader.fieldnames))
        for rec in reader:
            side = rec["side_picked"].strip().upper()
            if side not in ("A", "B", "NONE", "TOP", "BOTTOM", "LEFT", "RIGHT"):
                raise SchemaDriftError(rec["pick_id"], "side_picked", "A/B/NONE/TOP/BOTTOM/LEFT/RIGHT", side or "empty")
            keyed = bool(rec["key_file"].strip())
            if keyed:
                key_path = work / rec["key_file"].strip()
                if not key_path.exists():
                    raise SchemaDriftError(rec["pick_id"], "key_file", "an existing file in MOONSHOT_WORK", rec["key_file"])
                clips = load_json(key_path).get("clips") or {}
                clip = clips.get(rec["clip_key"].strip())
                if clip is None or "A" not in clip or "B" not in clip:
                    raise SchemaDriftError(rec["pick_id"], "clip_key", "a clip with A and B in the key", rec["clip_key"])
                option = "no preference" if side == "NONE" else str(clip[side])
            else:
                option = rec["option_text"].strip()
                if not option:
                    raise SchemaDriftError(rec["pick_id"], "option_text", "text when there is no key file", "empty")
            local = datetime.strptime(rec["decided_at_local"].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=LOCAL_TZ)
            rows.append({
                "pick_id": rec["pick_id"].strip(),
                "decided_at_local": rec["decided_at_local"].strip(),
                "decided_at_utc": local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "subject": rec["subject"].strip(),
                "key_file": rec["key_file"].strip() or None,
                "clip_key": rec["clip_key"].strip() or None,
                "side_picked": side,
                "option_picked": option,
                "mapped_through_key": keyed,
                "adopted": rec["adopted"].strip().lower() == "true",
                "version_effect": rec["version_effect"].strip(),
                "source_ref": rec["source_ref"].strip(),
            })
    return rows


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def best_from_json(exports: Path) -> int | None:
    """The promoted version, from BEST.json (written by promote.py).

    PROGRESS.md's own 'BEST:' header line is not used: it was left at v17 while the
    run promoted v21, so it is checked in reconcile.py and reported as a finding.
    """
    path = exports / "BEST.json"
    if not path.exists():
        return None
    obj = load_json(path)
    if "version" not in obj or "sha256" not in obj:
        raise SchemaDriftError(path.name, "version / sha256", "both present", f"keys {sorted(obj)}")
    return int(obj["version"])


def canonical_scores(raw: dict, source: str) -> dict[str, float]:
    """Map a JSON critic's score dict to the ten canonical categories; fail on any drift."""
    got = set(raw)
    expected = set(JSON_CATEGORY_MAP)
    if got != expected:
        raise SchemaDriftError(
            source, "scores keys", f"exactly {sorted(expected)}",
            f"missing {sorted(expected - got)}, extra {sorted(got - expected)}",
        )
    out = {}
    for key, cat in JSON_CATEGORY_MAP.items():
        value = raw[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 10:
            raise SchemaDriftError(source, f"scores.{key}", "number in 0..10", repr(value)[:20])
        out[cat] = float(value)
    return out


def embedded_scores(path: Path) -> tuple[dict[str, float], str, str]:
    """Scores and model of a Gemini or TwelveLabs raw response.

    Gemini keeps the critique as a JSON string in candidates[0].content.parts[0].text,
    TwelveLabs in ``data``. Returns (scores, actual model, model label the script wrote).
    """
    obj = load_json(path)
    if "candidates" in obj:
        text = obj["candidates"][0]["content"]["parts"][0]["text"]
        actual = str(obj.get("modelVersion", ""))
    elif "data" in obj:
        text = obj["data"]
        actual = str(obj.get("_critic_model", ""))
    else:
        raise SchemaDriftError(path.name, "response body", "candidates[] or data", f"keys {sorted(obj)[:6]}")
    inner = json.loads(text)
    return canonical_scores(inner.get("scores") or {}, path.name), actual, str(obj.get("_critic_model", ""))


def score_rows_for(version: int, critic: str, scores: dict[str, float], model: str, evaluation_id: str,
                   source_kind: str, note: str = "") -> list[dict]:
    return [{
        "version": version, "critic": critic, "category": cat, "score": scores[cat],
        "critic_model": model, "evaluation_id": evaluation_id, "source_kind": source_kind,
        "progress_md_score": None, "progress_md_flagged": False, "note": note,
    } for cat, _ in CATEGORIES]


def json_critic_rows(qc_root: Path) -> list[dict]:
    """Codex, Gemini, TwelveLabs and crowd scores stored as JSON under qc/vN/."""
    rows: list[dict] = []
    for vdir in sorted(qc_root.glob("v[0-9]*"), key=lambda p: int(p.name[1:])):
        version = int(vdir.name[1:])
        codex = vdir / "codex_critic.json"
        if codex.exists():
            scores = canonical_scores(load_json(codex).get("scores") or {}, f"{vdir.name}/codex_critic.json")
            rows += score_rows_for(version, "codex_critic", scores, "codex_cli", f"codex_critic_v{version}", "qc_json")
        web = vdir / "gemini_web_critic.json"
        if web.exists():
            obj = load_json(web)
            scores = canonical_scores(obj.get("scores") or {}, f"{vdir.name}/gemini_web_critic.json")
            rows += score_rows_for(version, "gemini_pro_web", scores, "gemini-pro (app)",
                                   f"gemini_pro_web_v{version}", "qc_json", "scored by hand-off through the Gemini app")
        for gem in sorted(vdir.glob("gemini_critic_run*.json")):
            scores, actual, label = embedded_scores(gem)
            note = f"script labelled the run '{label}' but the API answered as '{actual}'" if label and label != actual else ""
            rows += score_rows_for(version, "gemini_flash", scores, actual, f"gemini_flash_v{version}_{gem.stem[-4:]}",
                                   "qc_json", note)
        for tl in sorted(vdir.glob("twelvelabs_critic_raw_run*.json")):
            scores, actual, _ = embedded_scores(tl)
            rows += score_rows_for(version, "twelvelabs", scores, actual, f"twelvelabs_v{version}_{tl.stem[-4:]}", "qc_json")
        crowd = vdir / "crowd_ftv.json"
        if crowd.exists():
            obj = load_json(crowd)
            try:
                share = obj["crowd"]["scores"]["shareability"]
                slop = obj["crowd"]["scores"]["ai_slop_perception"]
                watch = obj["first_time_viewer"]["would_watch_to_end"]["score"]
            except KeyError as exc:
                raise SchemaDriftError(f"{vdir.name}/crowd_ftv.json", "crowd scores", "shareability, ai_slop_perception, would_watch_to_end", f"missing {exc}") from exc
            for cat, val in zip(CROWD_CATEGORIES, (share, slop, watch)):
                rows.append({
                    "version": version, "critic": "crowd_ftv", "category": cat, "score": float(val),
                    "critic_model": "claude-sonnet", "evaluation_id": f"crowd_ftv_v{version}", "source_kind": "qc_json",
                    "progress_md_score": None, "progress_md_flagged": False, "note": "",
                })
    return rows


def fable_rescore_rows(qc_root: Path) -> list[dict]:
    """The Fable editor's re-score of an older version, written inside a later review.

    A review of vN carries ``vM_overall`` for each baseline it compared against. The same
    critic gave v17 an 8.0 in its own review and a 7.0 when it reviewed v18 "on the same
    evidence", so scores from different reviews do not share one scale. The earliest later
    review that re-scored a version is kept, as a one-row 'overall' score.
    """
    first: dict[int, tuple[int, float]] = {}
    for vdir in sorted(qc_root.glob("v[0-9]*"), key=lambda p: int(p.name[1:])):
        path = vdir / "fable_editor.json"
        if not path.exists():
            continue
        reviewed = int(vdir.name[1:])
        for key, value in load_json(path).items():
            m = re.fullmatch(r"v(\d+)_overall", key)
            if not m:
                continue
            baseline = int(m.group(1))
            if baseline >= reviewed:
                raise SchemaDriftError(f"{vdir.name}/fable_editor.json", key, "a baseline older than the reviewed version", f"v{baseline}")
            if not isinstance(value, (int, float)) or not 0 <= value <= 10:
                raise SchemaDriftError(f"{vdir.name}/fable_editor.json", key, "number in 0..10", repr(value)[:20])
            if baseline not in first:
                first[baseline] = (reviewed, float(value))
    return [{
        "version": baseline, "critic": "fable_editor_rescored", "category": "overall", "score": value,
        "critic_model": "claude-fable", "evaluation_id": f"fable_editor_v{reviewed}_rescore", "source_kind": "qc_json",
        "progress_md_score": None, "progress_md_flagged": False,
        "note": f"v{baseline} re-scored by the Fable editor inside its review of v{reviewed}",
    } for baseline, (reviewed, value) in sorted(first.items())]


def crowd_progress_rows(covered: set[int]) -> list[dict]:
    """Crowd scores that exist only as prose in PROGRESS.md (hand-transcribed, one row per version)."""
    import csv

    if not CROWD_PROGRESS_FILE.exists():
        return []
    rows: list[dict] = []
    with CROWD_PROGRESS_FILE.open(encoding="utf-8", newline="") as fh:
        for rec in csv.DictReader(fh):
            version = int(rec["version"])
            if version in covered:
                continue  # a structured file wins over the transcription
            for cat in CROWD_CATEGORIES:
                if rec[cat] == "":
                    continue
                rows.append({
                    "version": version, "critic": "crowd_ftv", "category": cat, "score": float(rec[cat]),
                    "critic_model": "claude-sonnet", "evaluation_id": f"crowd_progress_md_v{version}",
                    "source_kind": "progress_md_prose", "progress_md_score": None,
                    "progress_md_flagged": False, "note": rec["source_ref"],
                })
    return rows


def actual_model(jsonl: Path) -> str:
    models: set[str] = set()
    with jsonl.open(encoding="utf-8") as fh:
        for line in fh:
            if '"type":"assistant"' in line:
                models.add(json.loads(line)["message"].get("model", ""))
    return ";".join(sorted(models))


def has_verdict_table(report: str) -> bool:
    return any(ln.strip().startswith("|") and re.search(r"(?i)\|\s*section\s*\|", ln) for ln in report.splitlines())


def main() -> None:
    work = require_dir("MOONSHOT_WORK")
    exports = require_dir("MOONSHOT_EXPORTS")
    progress = exports / "PROGRESS.md"
    pscores, logged, header_best = progress_scores(progress) if progress.exists() else ({}, {}, None)
    best = best_from_json(exports)
    if best is None:
        print("warning: BEST.json not found; falling back to the BEST line in PROGRESS.md")
        best = header_best
    qc_root = exports / "qc"

    version_rows = build_versions(work, exports, logged, best, qc_root)

    sec_rows: list[dict] = []
    dlg_rows: list[dict] = []
    for row in version_rows:
        aqc = work / f"aqc{row['version']}.txt"
        if aqc.exists():
            s, d = parse_aqc(aqc, row["version"])
            sec_rows += s
            dlg_rows += d

    score_rows: list[dict] = []
    vote_rows: list[dict] = []
    editor_seen: set[int] = set()
    ab_agents: dict[str, tuple[str, str, str]] = {}  # comparison -> (agent_id, model, report)
    pending_ab: set[str] = set()                      # comparisons whose judge subagent is still running
    for agent_id, jsonl, meta_path in subagent_files():
        desc = str(read_meta(meta_path).get("description", ""))
        m_ed = re.search(r"(?i)editor (?:critique|review) (?:of|on) v(\d+)", desc)
        m_ab = re.search(r"(?i)A/B (?:judge )?v(\d+) vs v(\d+)", desc)   # "Blind A/B judge v22 vs v21", "Blind Sonnet A/B v24 vs v23"
        if not (m_ed or m_ab):
            continue
        report = final_report(jsonl)
        if not report.strip():
            print(f"warning: subagent {agent_id} ({desc}) has no report yet; skipped")
            if m_ab:
                pending_ab.add(f"v{m_ab.group(1)}_v{m_ab.group(2)}")
            continue
        model = actual_model(jsonl)
        if m_ed:
            version = int(m_ed.group(1))
            if version in editor_seen:
                raise SchemaDriftError(desc, "editor critique", "one per version", f"second report for v{version}")
            editor_seen.add(version)
            json_path = qc_root / f"v{version}" / "fable_editor.json"
            if json_path.exists():
                scores = canonical_scores(load_json(json_path).get("scores") or {}, f"v{version}/fable_editor.json")
                parsed: dict[str, float | None] = dict(scores)
                kind = "qc_json"
            else:
                parsed = editor_scores(report, version)
                kind = "subagent_report"
            for cat, _ in CATEGORIES:
                pm = pscores.get(version, {}).get(cat, (None, False))
                score_rows.append({
                    "version": version, "critic": "fable_editor", "category": cat, "score": parsed.get(cat),
                    "critic_model": model, "evaluation_id": agent_id, "source_kind": kind,
                    "progress_md_score": pm[0], "progress_md_flagged": pm[1], "note": "",
                })
        else:
            ab_agents[f"v{m_ab.group(1)}_v{m_ab.group(2)}"] = (agent_id, model, report)

    crosscheck: list[str] = []
    # A/B verdicts: one per ab_key file. judge_sonnet.json wins when it exists; the hand-back
    # table is parsed when it has one, and the two are compared by reconcile.py.
    for key_path in sorted(work.glob("ab_key_v*_v*.json")):
        comparison = key_path.stem.removeprefix("ab_key_")
        m = re.fullmatch(r"v(\d+)_v(\d+)", comparison)
        newer, older = int(m.group(1)), int(m.group(2))
        key = json.loads(key_path.read_text(encoding="utf-8"))
        agent_id, model, report = ab_agents.get(comparison, (f"json_{comparison}", "", ""))
        judge_json = qc_root / f"ab_{comparison}" / "judge_sonnet.json"
        if judge_json.exists():
            json_votes = ab_votes_from_json(judge_json, key, comparison, newer, older, agent_id, model)
            vote_rows += json_votes
            other: list[dict] | None = None
            if has_verdict_table(report):
                other = ab_votes(report, key, comparison, newer, older, agent_id, model)
            elif len(plain_verdict_rows(report)) == len(key):
                other = ab_votes_from_lines(report, key, comparison, newer, older, agent_id, model)
            if other is None:
                crosscheck.append(f"{comparison}: judge_sonnet.json only (hand-back has no verdict lines)")
            else:
                theirs = {o["section_no"]: o["side_picked"] for o in other}
                differ = [v["section"] for v in json_votes if theirs.get(v["section_no"]) != v["side_picked"]]
                crosscheck.append(
                    f"{comparison}: judge_sonnet.json vs hand-back, {len(json_votes) - len(differ)} of "
                    f"{len(json_votes)} section picks agree" + (f"; differ: {', '.join(differ)}" if differ else "")
                )
        elif has_verdict_table(report):
            vote_rows += ab_votes(report, key, comparison, newer, older, agent_id, model)
        elif len(plain_verdict_rows(report)) == len(key):
            vote_rows += ab_votes_from_lines(report, key, comparison, newer, older, agent_id, model)
        elif comparison in pending_ab:
            print(f"warning: A/B {comparison} has a key but its judge is still running; no votes yet")
            crosscheck.append(f"{comparison}: judge still running at ingest time, no votes")
        else:
            raise SchemaDriftError(comparison, "A/B verdict source", "judge_sonnet.json, a '| section |' table or 'N section | winner | confidence |' lines", "none found")

    # Fable editor reviews with a qc/vN/fable_editor.json but no matching subagent description in the
    # transcript (the file is the primary source, so the review still counts)
    for vdir in sorted(qc_root.glob("v[0-9]*"), key=lambda p: int(p.name[1:])):
        version = int(vdir.name[1:])
        json_path = vdir / "fable_editor.json"
        if version in editor_seen or not json_path.exists():
            continue
        editor_seen.add(version)
        scores = canonical_scores(load_json(json_path).get("scores") or {}, f"{vdir.name}/fable_editor.json")
        for cat, _ in CATEGORIES:
            pm = pscores.get(version, {}).get(cat, (None, False))
            score_rows.append({
                "version": version, "critic": "fable_editor", "category": cat, "score": scores[cat],
                "critic_model": "", "evaluation_id": f"fable_editor_v{version}_json", "source_kind": "qc_json",
                "progress_md_score": pm[0], "progress_md_flagged": pm[1], "note": "no matching subagent transcript",
            })

    # editor scores that exist only in PROGRESS.md (none expected)
    for version, cells in sorted(pscores.items()):
        if version in editor_seen or all(v is None for v, _ in cells.values()):
            continue
        for cat, _ in CATEGORIES:
            value, flagged = cells.get(cat, (None, False))
            score_rows.append({
                "version": version, "critic": "fable_editor", "category": cat, "score": value,
                "critic_model": "", "evaluation_id": "progress_md", "source_kind": "progress_md_table",
                "progress_md_score": value, "progress_md_flagged": flagged, "note": "",
            })

    json_rows = json_critic_rows(qc_root)
    score_rows += json_rows
    score_rows += fable_rescore_rows(qc_root)
    covered_crowd = {r["version"] for r in json_rows if r["critic"] == "crowd_ftv"}
    score_rows += crowd_progress_rows(covered_crowd)

    cat_order = {c: i for i, (c, _) in enumerate(CATEGORIES)}
    cat_order.update({c: 20 + i for i, c in enumerate(CROWD_CATEGORIES)})
    score_rows.sort(key=lambda r: (r["version"], r["critic"], cat_order[r["category"]]))
    vote_rows.sort(key=lambda r: (r["newer_version"], r["older_version"], r["repeat_no"], r["section_no"]))

    # grain: version x critic x category, one row each
    seen_keys: set[tuple] = set()
    for r in score_rows:
        k = (r["version"], r["critic"], r["category"])
        if k in seen_keys:
            raise SchemaDriftError("critic_scores", "grain version x critic x category", "unique", f"duplicate {k}")
        seen_keys.add(k)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "_ab_crosscheck.txt").write_text("\n".join(crosscheck) + "\n", encoding="utf-8")
    segment_rows = loop_segments(exports)
    pick_rows = director_picks(work)
    write_csv(pick_rows, DIRECTOR_PICK_COLUMNS, "director_picks.csv")
    write_csv(segment_rows, LOOP_SEGMENT_COLUMNS, "loop_segments.csv")
    write_csv(version_rows, VERSION_COLUMNS, "versions.csv")
    write_csv(score_rows, SCORE_COLUMNS, "critic_scores.csv")
    write_csv(vote_rows, AB_COLUMNS, "ab_votes.csv")
    write_csv(sec_rows, QC_SECTION_COLUMNS, "qc_sections.csv")
    write_csv(dlg_rows, QC_DIALOGUE_COLUMNS, "qc_dialogue.csv")
    print(f"director_picks: {len(pick_rows)} rows")
    print(f"loop_segments: {len(segment_rows)} rows")
    print(f"versions:      {len(version_rows)} rows")
    print(f"critic_scores: {len(score_rows)} rows ({sum(1 for r in score_rows if r['score'] is None)} NULL scores) "
          f"from {len({r['critic'] for r in score_rows})} critics")
    print(f"ab_votes:      {len(vote_rows)} rows over {len({r['comparison'] for r in vote_rows})} comparisons")
    print(f"qc_sections:   {len(sec_rows)} rows")
    print(f"qc_dialogue:   {len(dlg_rows)} rows")


if __name__ == "__main__":
    main()
