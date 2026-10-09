"""Study 2 (A/B judge position bias): build the order-flipped sheets and the judge calls.

Design (pre-registered, see studies/README.md):
  * 12 distinct (version pair, section) items from the existing blind A/B comparisons, chosen by a fixed rule
    among sections where the two cuts visibly differ (see select_items; the table goes to s2/items.csv).
  * Every item is shown in BOTH orders (newer cut on top / older cut on top) x 2 fresh repeats = 48 decisions.
  * 8 judge calls x 6 sheets; no item twice in a call; 3 + 3 orders in every call.
  * The key (decision -> item, order, call, sheet) goes to s2/key.json and is never shown to a judge.

How the sheets are built. ab.py fixes the A/B side per pair and bakes the label into the pixels (a 70% black
box under yellow text), so a sheet cannot be flipped by cropping it. This script instead re-runs ab.py's own
frame extraction (same SECTIONS, same vt() timeline shift, same ffmpeg filter: 8 frames, 400 px wide, tile 8x1)
without the label, then stamps fresh "A"/"B" labels with the same font, size, position and box. Sheet geometry
(3200 x 450: two rows of 225 px, eight 400 px tiles) was verified on all 70 existing sheets. As a check, each
item is also rebuilt in the orientation the original judge saw and compared with the original sheet image.

Run (from C:\\dev\\moonshot-repo\\analytics):
    set PYTHONUTF8=1 && py studies\\s2_prepare.py            (add --force to rebuild)

Needs Pillow, numpy, pandas and ffmpeg on PATH. ffmpeg runs at below-normal priority with 2 threads. No model is
called.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
from common import require_dir  # noqa: E402  (reads MOONSHOT_EXPORTS / MOONSHOT_WORK from the shell or analytics/.env)

ROOT = require_dir("MOONSHOT_EXPORTS")
WORK = require_dir("MOONSHOT_WORK")
RUBRIC_PATH = WORK / "ab_rubric.md"
VOTES_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "ab_votes.csv"
STUDY_DIR = Path(__file__).resolve().parent / "s2"
PROMPT_PATH = STUDY_DIR / "prompt.md"
FONT_PATH = r"C:\Windows\Fonts\arialbd.ttf"

SEED: int = 20261008
N_ITEMS: int = 12
N_REPEATS: int = 2
SHEETS_PER_CALL: int = 6

# copied from ab.py (the section windows are on the v7 timeline; from v8 on, 40.0 s and later sit 6.7 s earlier)
SECTIONS: list[tuple[str, float, float]] = [
    ("1_cold_open", 0.0, 10.6), ("2_drop_title", 10.6, 19.0), ("3_stats_chart", 19.0, 40.0),
    ("4_moon_lm", 40.0, 47.0), ("5_alarm", 47.0, 55.6), ("6_fuel_landing", 55.6, 69.6), ("7_outro", 69.6, 90.0)]
SECTION_TIMES = {name: (a, b) for name, a, b in SECTIONS}
ACT2_D: float = 6.7
TILE_W, TILE_H, N_TILES = 400, 225, 8
LABEL_XY, LABEL_SIZE = (6, 6), 20

# selection rule (fixed before any judge ran)
MIN_TILES_DIFF: int = 4       # at least 4 of 8 frame pairs must differ visibly
TILE_DIFF_THRESHOLD: float = 6.0   # mean absolute grey difference (0-255) for a pair to count as "differs"
MAX_PER_PAIR: int = 3
MAX_PER_SECTION: int = 3


def vt(ver: int, t: float) -> float:
    """ab.py's vt(): section time t (v7 timeline) on version ver's timeline."""
    return round(t - ACT2_D, 3) if ver >= 8 and t >= 40.0 else t


@dataclass
class Item:
    """One (version pair, section) comparison."""

    item_id: str
    comparison: str
    newer: int
    older: int
    section: str
    same_len: bool          # same section length in both cuts, so the sheet carries timestamps
    mad: float
    tiles_diff: int
    orig_pick: str          # version picked by the original judge, or "TIE"
    orig_conf: str


# ---------------------------------------------------------------------------------------------- selection
def sheet_difference(sheet: Path) -> tuple[float, int]:
    """(mean abs grey difference between the two rows, number of the 8 frame pairs differing by > threshold)."""
    grey = np.asarray(Image.open(sheet).convert("L").resize((800, 112)), dtype=float)
    top, bottom = grey[:56], grey[56:]
    diffs: list[float] = []
    for k in range(N_TILES):
        a = top[:, k * 100:(k + 1) * 100][:, 40:]      # skip the label end of each tile
        b = bottom[:, k * 100:(k + 1) * 100][:, 40:]
        diffs.append(float(np.abs(a - b).mean()))
    return float(np.mean(diffs)), sum(d > TILE_DIFF_THRESHOLD for d in diffs)


def select_items() -> tuple[list[Item], pd.DataFrame]:
    """Apply the fixed selection rule to all 70 existing sheets. Returns (chosen items, full candidate table)."""
    votes = pd.read_csv(VOTES_PATH)
    rows: list[dict[str, object]] = []
    for folder in sorted((ROOT / "qc").glob("ab_v*")):
        match = re.fullmatch(r"ab_v(\d+)_v(\d+)", folder.name)
        if not match:
            continue
        newer, older = int(match.group(1)), int(match.group(2))
        comparison = f"v{newer}_v{older}"
        key = json.loads((WORK / f"ab_key_{comparison}.json").read_text(encoding="utf-8"))
        for section in key:
            mad, tiles = sheet_difference(folder / f"{section}.jpg")
            vote = votes[(votes["comparison"] == comparison) & (votes["section"] == section)].iloc[0]
            picked = "TIE" if bool(vote["is_tie"]) else f"v{int(vote['version_picked'])}"
            a, b = SECTION_TIMES[section]
            same_len = abs((vt(newer, b) - vt(newer, a)) - (vt(older, b) - vt(older, a))) < 1e-6
            rows.append({"comparison": comparison, "newer": newer, "older": older, "section": section,
                         "same_len": same_len, "mean_abs_diff": round(mad, 2), "tiles_diff": tiles,
                         "orig_pick": picked, "orig_conf": vote["confidence"]})
    table = pd.DataFrame(rows)
    ranked = table.sort_values(["tiles_diff", "mean_abs_diff"], ascending=[False, False], kind="stable")
    per_pair: dict[str, int] = {}
    per_section: dict[str, int] = {}
    chosen_idx: list[int] = []
    for idx, row in ranked.iterrows():
        if len(chosen_idx) == N_ITEMS:
            break
        if row["tiles_diff"] < MIN_TILES_DIFF:
            break
        if per_pair.get(row["comparison"], 0) >= MAX_PER_PAIR or per_section.get(row["section"], 0) >= MAX_PER_SECTION:
            continue
        per_pair[row["comparison"]] = per_pair.get(row["comparison"], 0) + 1
        per_section[row["section"]] = per_section.get(row["section"], 0) + 1
        chosen_idx.append(idx)
    if len(chosen_idx) != N_ITEMS:
        raise RuntimeError(f"selection rule produced {len(chosen_idx)} items, expected {N_ITEMS}")
    table["selected"] = table.index.isin(chosen_idx)
    items: list[Item] = []
    for number, idx in enumerate(chosen_idx, start=1):
        r = table.loc[idx]
        items.append(Item(f"i{number:02d}", r["comparison"], int(r["newer"]), int(r["older"]), r["section"],
                          bool(r["same_len"]), float(r["mean_abs_diff"]), int(r["tiles_diff"]),
                          str(r["orig_pick"]), str(r["orig_conf"])))
    return items, table


# ---------------------------------------------------------------------------------------------- sheets
def render_row(version: int, section: str, tmp_dir: Path) -> Image.Image:
    """One unlabeled 8-frame row for a version's cut of a section: ab.py's ffmpeg call minus the drawtext."""
    a, b = SECTION_TIMES[section]
    va, vb = vt(version, a), vt(version, b)
    step = (vb - va) / N_TILES
    out = tmp_dir / f"row_v{version}_{section}.png"
    command = ["ffmpeg", "-v", "error", "-y", "-threads", "2", "-ss", f"{va + step / 2:.3f}", "-t",
               f"{vb - va:.3f}", "-i", str(ROOT / "versions" / f"moonshot_v{version}.mp4"), "-an", "-vf",
               f"fps=1/{step:.4f},scale={TILE_W}:-1,tile={N_TILES}x1", "-frames:v", "1", str(out)]
    flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    subprocess.run(command, check=True, creationflags=flags)
    image = Image.open(out).convert("RGB")
    image.load()
    out.unlink()
    if image.size != (TILE_W * N_TILES, TILE_H):
        raise RuntimeError(f"row geometry {image.size} for v{version} {section}; expected {(TILE_W * N_TILES, TILE_H)}")
    return image


def hms(seconds: float) -> str:
    """ffmpeg's %{pts:hms} format, e.g. 00:00:02.625."""
    whole = int(seconds)
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{seconds - whole // 60 * 60:06.3f}"


def label_row(row: Image.Image, letter: str, stamped_step: float | None) -> Image.Image:
    """Stamp 'A' or 'B' (plus the frame timestamp when the section lengths match) on each of the 8 tiles."""
    font = ImageFont.truetype(FONT_PATH, LABEL_SIZE)
    base = row.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for k in range(N_TILES):
        text = letter if stamped_step is None else f"{letter}  {hms(k * stamped_step)}"
        x0, y0 = k * TILE_W + LABEL_XY[0], LABEL_XY[1]
        left, top, right, bottom = draw.textbbox((x0, y0), text, font=font)
        draw.rectangle((x0, y0, right + 1, bottom + 3), fill=(0, 0, 0, 178))          # black @ 0.7
        draw.text((x0, y0), text, font=font, fill=(255, 255, 0, 255))
    return Image.alpha_composite(base, overlay).convert("RGB")


def compose_sheet(top_row: Image.Image, bottom_row: Image.Image, same_len: bool, section: str,
                  top_version: int) -> Image.Image:
    """Stack two unlabeled rows with fresh 'A' (top) and 'B' (bottom) labels."""
    a, b = SECTION_TIMES[section]
    step = (vt(top_version, b) - vt(top_version, a)) / N_TILES if same_len else None
    sheet = Image.new("RGB", (TILE_W * N_TILES, TILE_H * 2))
    sheet.paste(label_row(top_row, "A", step), (0, 0))
    sheet.paste(label_row(bottom_row, "B", step), (0, TILE_H))
    return sheet


def jpeg_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def compare_to_original(rebuilt: Image.Image, original_path: Path) -> tuple[float, float]:
    """(whole-sheet MAD, MAD outside the label boxes) between a rebuilt sheet and the original JPEG, 0-255 scale."""
    a = np.asarray(rebuilt.convert("L"), dtype=float)
    b = np.asarray(Image.open(original_path).convert("L"), dtype=float)
    mask = np.ones_like(a, dtype=bool)
    for row_top in (0, TILE_H):
        for k in range(N_TILES):
            mask[row_top:row_top + 34, k * TILE_W:k * TILE_W + 175] = False
    diff = np.abs(a - b)
    return float(diff.mean()), float(diff[mask].mean())


# ---------------------------------------------------------------------------------------------- design
def design_calls(items: list[Item], rng: random.Random) -> tuple[list[dict[str, object]], dict[str, list[str]]]:
    """Decisions and calls. Per repeat: split items in two halves of 6, give each half 3 + 3 orders, then run each
    half once as assigned and once flipped. Every call therefore has 6 distinct items and 3 + 3 orders."""
    ids = [i.item_id for i in items]
    decisions: list[dict[str, object]] = []
    used_ids: set[str] = set()

    def new_id(prefix: str) -> str:
        while True:
            candidate = prefix + "".join(rng.choices("0123456789abcdef", k=8))
            if candidate not in used_ids:
                used_ids.add(candidate)
                return candidate

    calls: dict[str, list[str]] = {}
    for repeat in range(1, N_REPEATS + 1):
        shuffled = ids[:]
        rng.shuffle(shuffled)
        halves = [shuffled[:SHEETS_PER_CALL], shuffled[SHEETS_PER_CALL:]]
        newer_top: dict[str, bool] = {}
        for half in halves:
            flags = [True] * (len(half) // 2) + [False] * (len(half) - len(half) // 2)
            rng.shuffle(flags)
            newer_top.update(dict(zip(half, flags)))
        for flip in (False, True):
            for half in halves:
                call_id = new_id("j")
                members = half[:]
                rng.shuffle(members)
                calls[call_id] = []
                for sheet_no, item_id in enumerate(members, start=1):
                    decision_id = new_id("d")
                    decisions.append({
                        "decision_id": decision_id, "item_id": item_id, "repeat": repeat,
                        "newer_on_top": newer_top[item_id] != flip,
                        "call_id": call_id, "sheet_no": sheet_no,
                    })
                    calls[call_id].append(decision_id)
    return decisions, calls


def section_name(section: str) -> str:
    """'3_stats_chart' -> 'stats chart'."""
    return section.split("_", 1)[1].replace("_", " ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true", help="delete and rebuild calls/key/manifest")
    args = parser.parse_args()

    key_path = STUDY_DIR / "key.json"
    calls_dir = STUDY_DIR / "calls"
    results_dir = STUDY_DIR / "results"
    if (calls_dir.exists() or key_path.exists()) and not args.force:
        print("studies/s2 already prepared; pass --force to rebuild (this invalidates any results)", file=sys.stderr)
        return 1
    if args.force and results_dir.exists() and any(results_dir.glob("*.json")):
        print("results/ already holds judge output; move it away first, --force would orphan it", file=sys.stderr)
        return 1
    if args.force and calls_dir.exists():
        shutil.rmtree(calls_dir)
    template = PROMPT_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    rubric = RUBRIC_PATH.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    if rubric not in template:
        print("prompt.md does not contain ab_rubric.md verbatim", file=sys.stderr)
        return 1
    for placeholder in ("{CALL_DIR}", "{SHEET_LIST}"):
        if placeholder not in template:
            print(f"prompt.md is missing {placeholder}", file=sys.stderr)
            return 1

    rng = random.Random(args.seed)
    items, candidates = select_items()
    candidates.to_csv(STUDY_DIR / "candidates.csv", index=False, encoding="utf-8")
    with (STUDY_DIR / "items.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["item_id", "comparison", "newer", "older", "section", "same_length_stamps", "mean_abs_diff",
                         "tiles_differing_of_8", "original_pick", "original_confidence"])
        for it in items:
            writer.writerow([it.item_id, it.comparison, it.newer, it.older, it.section, it.same_len, it.mad,
                             it.tiles_diff, it.orig_pick, it.orig_conf])

    decisions, calls = design_calls(items, rng)
    by_item = {it.item_id: it for it in items}

    # rows (one ffmpeg run per item x version), the fidelity check, and the sheets in both orientations
    sheets: dict[tuple[str, bool], bytes] = {}
    fidelity: list[dict[str, object]] = []
    tmp = Path(tempfile.mkdtemp(prefix="s2_rows_"))
    try:
        for it in items:
            newer_row = render_row(it.newer, it.section, tmp)
            older_row = render_row(it.older, it.section, tmp)
            rows = {it.newer: newer_row, it.older: older_row}
            for newer_top in (True, False):
                top_v, bottom_v = (it.newer, it.older) if newer_top else (it.older, it.newer)
                sheet = compose_sheet(rows[top_v], rows[bottom_v], it.same_len, it.section, top_v)
                sheets[(it.item_id, newer_top)] = jpeg_bytes(sheet)
                original_key = json.loads((WORK / f"ab_key_{it.comparison}.json").read_text(encoding="utf-8"))
                if original_key[it.section]["A"] == top_v:       # same orientation the original judge saw
                    whole, outside = compare_to_original(sheet, ROOT / "qc" / f"ab_{it.comparison}" / f"{it.section}.jpg")
                    fidelity.append({"item_id": it.item_id, "mad_whole_sheet": round(whole, 2),
                                     "mad_outside_labels": round(outside, 2)})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    worst = max(f["mad_outside_labels"] for f in fidelity)          # type: ignore[type-var]
    if worst > 6:
        print(f"WARNING: rebuilt sheet differs from the original by {worst} grey levels outside the labels",
              file=sys.stderr)

    # write the call folders
    calls_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    decision_by_id = {d["decision_id"]: d for d in decisions}
    key_decisions: dict[str, dict[str, object]] = {}
    key_calls: dict[str, dict[str, str]] = {}
    sheet_hashes: dict[str, str] = {}
    dispatch: list[dict[str, str]] = []
    for call_id, decision_ids in calls.items():
        folder = calls_dir / call_id
        folder.mkdir(parents=True, exist_ok=True)
        listing: list[str] = []
        key_calls[call_id] = {}
        for decision_id in decision_ids:
            d = decision_by_id[decision_id]
            it = by_item[str(d["item_id"])]
            data = sheets[(it.item_id, bool(d["newer_on_top"]))]
            name = f"sheet_{d['sheet_no']}"
            (folder / f"{name}.jpg").write_bytes(data)
            sheet_hashes[f"{call_id}/{name}"] = hashlib.sha256(data).hexdigest()
            listing.append(f"- `{name}.jpg`: section \"{section_name(it.section)}\"")
            key_calls[call_id][name] = decision_id
            top_v = it.newer if d["newer_on_top"] else it.older
            key_decisions[decision_id] = {
                "item_id": it.item_id, "comparison": it.comparison, "section": it.section, "repeat": d["repeat"],
                "newer": it.newer, "older": it.older, "newer_on_top": d["newer_on_top"], "top_version": top_v,
                "bottom_version": it.older if d["newer_on_top"] else it.newer,
                "call_id": call_id, "sheet": name,
            }
        listing.sort(key=lambda line: int(re.search(r"sheet_(\d+)", line).group(1)))   # type: ignore[union-attr]
        text = template.replace("{CALL_DIR}", str(folder)).replace("{SHEET_LIST}", "\n".join(listing))
        instructions = folder / "instructions.md"
        instructions.write_text(text, encoding="utf-8", newline="\n")
        dispatch.append({"call_id": call_id, "call_dir": str(folder), "instructions_file": str(instructions),
                         "result_path": str(results_dir / f"{call_id}.json")})

    # sanity checks on the design
    for call_id, decision_ids in calls.items():
        members = [decision_by_id[x] for x in decision_ids]
        assert len({m["item_id"] for m in members}) == SHEETS_PER_CALL, "item repeated within a call"
        assert sum(bool(m["newer_on_top"]) for m in members) == SHEETS_PER_CALL // 2, "orders not balanced in call"
    for it in items:
        mine = [d for d in decisions if d["item_id"] == it.item_id]
        assert len(mine) == 2 * N_REPEATS and sum(bool(d["newer_on_top"]) for d in mine) == N_REPEATS, it.item_id
    assert len(decisions) == N_ITEMS * 2 * N_REPEATS and len(calls) == len(decisions) // SHEETS_PER_CALL

    run_order = list(calls)
    rng.shuffle(run_order)
    key = {"items": {it.item_id: {"comparison": it.comparison, "newer": it.newer, "older": it.older,
                                  "section": it.section} for it in items},
           "decisions": key_decisions, "calls": key_calls}
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True), encoding="utf-8")
    with (STUDY_DIR / "dispatch.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["call_id", "call_dir", "instructions_file", "result_path"])
        writer.writeheader()
        for call_id in run_order:
            writer.writerow(next(d for d in dispatch if d["call_id"] == call_id))
    manifest = {
        "study": "s2_ab_judge_position_bias",
        "created": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "n_items": N_ITEMS, "n_repeats": N_REPEATS, "n_decisions": len(decisions), "n_calls": len(calls),
        "sheets_per_call": SHEETS_PER_CALL,
        "selection_rule": {
            "metric": "per existing sheet: of 8 frame pairs, count with mean abs grey difference > "
                      f"{TILE_DIFF_THRESHOLD} (800x112 downscale, left 40% of each tile ignored)",
            "min_tiles_differing": MIN_TILES_DIFF, "max_per_pair": MAX_PER_PAIR, "max_per_section": MAX_PER_SECTION,
            "order": "tiles differing desc, then mean abs diff desc; greedy under the caps",
        },
        "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "rubric_sha256": hashlib.sha256(RUBRIC_PATH.read_bytes()).hexdigest(),
        "run_order": run_order,
        "fidelity_vs_original_sheets": fidelity,
        "sheet_sha256": sheet_hashes,
        "notes": [
            "key.json and this manifest must never be shown to a judge.",
            "A is always the top row, so label bias and top-position bias cannot be separated.",
            "Flipped repeats of an item are the same two rows; only the labels and the stacking order change.",
        ],
    }
    (STUDY_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    sizes = [p.stat().st_size for p in calls_dir.rglob("*.jpg")]
    print(f"items: {len(items)} -> {STUDY_DIR / 'items.csv'}")
    for it in items:
        print(f"  {it.item_id} {it.comparison:8s} {it.section:15s} tiles_diff={it.tiles_diff} mad={it.mad:5.1f} "
              f"orig={it.orig_pick} ({it.orig_conf})")
    print(f"calls: {len(calls)} x {SHEETS_PER_CALL} sheets = {len(sizes)} sheet files, "
          f"{sum(sizes) / 1e6:.1f} MB total ({min(sizes) / 1e3:.0f}-{max(sizes) / 1e3:.0f} KB each)")
    print(f"decisions: {len(decisions)}; seed {args.seed}")
    print(f"fidelity vs original sheets (grey levels, outside label boxes): max {worst}, "
          f"mean {np.mean([f['mad_outside_labels'] for f in fidelity]):.2f} over {len(fidelity)} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
