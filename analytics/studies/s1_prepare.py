"""Study 1 (same-model repeatability of the editor critic): build the blinded evidence packs.

Design (pre-registered, see studies/README.md):
  * 8 versions x 3 fresh-context repeats = 24 evaluations.
  * Every evaluation gets a pack in studies/s1/packs/<eval_id>/ (eval_id is random, from a recorded seed).
  * Packs of the same version are byte-identical apart from the folder name, so the repeats are true repeats.
  * The key (eval_id -> version, repeat) goes to studies/s1/key.json and is never shown to a critic.

Run (from C:\\dev\\moonshot-repo\\analytics):
    set PYTHONUTF8=1 && py studies\\s1_prepare.py            (add --force to rebuild an existing study)

Needs Pillow (only to make phone-size frames for cuts that have none). No model is called.
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
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ingest"))
from common import require_dir  # noqa: E402  (reads MOONSHOT_EXPORTS / MOONSHOT_WORK from the shell or analytics/.env)

QC_ROOT = require_dir("MOONSHOT_EXPORTS") / "qc"
STUDY_DIR = Path(__file__).resolve().parent / "s1"

VERSIONS: list[int] = [1, 2, 4, 6, 8, 10, 11, 13]
REPEATS: int = 3
SEED: int = 20261007

# Frame targets, in seconds on the v7 timeline (the timeline the QC key frames were first cut on).
# From v8 on, everything at or after 40.0 s sits 6.7 s earlier (same rule as ab.py's vt()).
ACT2_START_S: float = 40.0
ACT2_SHIFT_S: float = 6.7
TARGETS_V7_S: list[float] = [
    1.0, 3.0, 11.5, 13.4, 15.0, 17.3, 20.0,                  # countdown, drop, title, launch
    27.0, 31.5, 34.8, 38.8,                                  # act 2: ascent graphics, Earth, Moon
    47.4, 51.5, 53.5, 56.5, 59.0, 62.3, 64.5, 68.7,          # lunar module, alarm, fuel, landing
    72.0, 76.0, 85.5,                                        # outro (footprint, credits side)
]
MAX_DELTA_S: float = 1.6          # a target may map to a key frame at most this far from the ideal time
PHONE_SIZE: tuple[int, int] = (640, 360)

PROMPT_PATH = STUDY_DIR / "prompt.md"
FORBIDDEN_IN_PACK = re.compile(r"(?i)\bv\d+\b|moonshot_v\d+")


@dataclass(frozen=True)
class FrameChoice:
    """One frame slot of the fixed subset, resolved for one version."""

    index: int               # 1-based slot number in the pack
    target_s: float          # nominal time on the v7 timeline
    version: int
    src_s: float             # actual time of the chosen key frame on this version's own timeline
    delta_s: float           # src_s minus the ideal time on this version's timeline
    key_file: Path
    phone_file: Path | None  # None means: make it from the key frame


def version_time(version: int, t_v7: float) -> float:
    """Ideal time of a v7-timeline moment on a given version's timeline."""
    if version >= 8 and t_v7 >= ACT2_START_S:
        return round(t_v7 - ACT2_SHIFT_S, 3)
    return t_v7


def list_times(qc_dir: Path, prefix: str) -> dict[float, Path]:
    """Map time-in-seconds -> file for key_<t>.jpg or k360_<t>.jpg in a QC folder."""
    pattern = re.compile(rf"^{prefix}_(\d+\.\d)\.jpg$")
    found: dict[float, Path] = {}
    for path in sorted(qc_dir.iterdir()):
        match = pattern.match(path.name)
        if match:
            found[float(match.group(1))] = path
    return found


def choose_frames(version: int) -> list[FrameChoice]:
    """Resolve the fixed target list to the nearest available key frame of one version."""
    qc_dir = QC_ROOT / f"v{version}"
    keys = list_times(qc_dir, "key")
    phones = list_times(qc_dir, "k360")
    # if the version has phone-size frames, only consider moments that have both, so the pairs match
    candidates = sorted(t for t in keys if t in phones) if phones else sorted(keys)
    choices: list[FrameChoice] = []
    for index, target in enumerate(TARGETS_V7_S, start=1):
        ideal = version_time(version, target)
        src = min(candidates, key=lambda t: (abs(t - ideal), t))
        if abs(src - ideal) > MAX_DELTA_S:
            raise RuntimeError(f"v{version}: no key frame within {MAX_DELTA_S}s of {ideal} (nearest {src})")
        choices.append(FrameChoice(index, target, version, src, round(src - ideal, 3), keys[src], phones.get(src)))
    srcs = [c.src_s for c in choices]
    if len(set(srcs)) != len(srcs):
        raise RuntimeError(f"v{version}: two targets mapped to the same key frame: {srcs}")
    return choices


def make_phone_jpeg(key_file: Path) -> bytes:
    """Phone-size (640x360) JPEG from a full-res key frame, for cuts QC'd before phone frames existed."""
    image = Image.open(key_file).convert("RGB").resize(PHONE_SIZE, Image.BICUBIC)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def scrub_audio_qc(version: int) -> str:
    """audio_qc.md text with the version number and any 'vN' string removed (or a whole-mix stub for v1)."""
    qc_dir = QC_ROOT / f"v{version}"
    source = qc_dir / "audio_qc.md"
    if source.exists():
        text = source.read_text(encoding="utf-8").replace("\r\n", "\n")
        lines: list[str] = []
        for line in text.split("\n"):
            if re.match(r"^File: moonshot_v\d+\.mp4\s*$", line):
                continue
            if line.startswith("Spectrogram:"):
                continue                      # the spectrogram image is not part of the pack
            if re.match(r"^# Audio QC v\d+\s*$", line):
                line = "# Audio QC"
            lines.append(line)
        cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    else:
        # v1 predates the audio-QC tool: only whole-mix loudness exists (qc.json from the same QC pass)
        qc = json.loads((qc_dir / "qc.json").read_text(encoding="utf-8"))
        cleaned = (
            "# Audio QC\n\n"
            f"Whole mix: I {qc['integrated_LUFS']} LUFS, LRA {qc['LRA']} LU, true peak {qc['true_peak_dBTP']} dBTP\n\n"
            "Per-section loudness, dialogue-to-bed ratios, the click scan and the caption-recall check were not\n"
            "measured for this cut; only the whole-mix figures above exist.\n"
        )
    if FORBIDDEN_IN_PACK.search(cleaned):
        bad = FORBIDDEN_IN_PACK.search(cleaned)
        raise RuntimeError(f"v{version}: version string left in audio_qc after scrub: {bad.group(0)!r}")
    return cleaned.rstrip("\n") + "\n"


def build_index_md(choices: list[FrameChoice]) -> str:
    """Neutral index of the frame slots: slot number -> time in this cut."""
    rows = "\n".join(f"| {c.index:02d} | {c.src_s:.1f} |" for c in choices)
    text = (
        "# Evidence pack index\n\n"
        "Times are seconds from the start of this cut.\n\n"
        "- `contact.jpg`: contact sheet of evenly spaced frames, timestamp burned into each tile.\n"
        "- `frames/frame_NN.jpg`: full-resolution key frame (960x540).\n"
        "- `phone/phone_NN.jpg`: the same moment at phone size (640x360). Use it to judge text legibility.\n"
        "- `audio_qc.md`: audio measurements (you cannot hear the cut).\n\n"
        "| NN | time (s) |\n|---|---|\n"
        f"{rows}\n"
    )
    if FORBIDDEN_IN_PACK.search(text):
        raise RuntimeError("version string in index.md")
    return text


def build_pack_files(version: int, choices: list[FrameChoice]) -> dict[str, bytes]:
    """All files of one version's pack as {relative posix path: bytes}. Built once, written once per repeat."""
    qc_dir = QC_ROOT / f"v{version}"
    files: dict[str, bytes] = {
        "contact.jpg": (qc_dir / "contact.jpg").read_bytes(),
        "audio_qc.md": scrub_audio_qc(version).encode("utf-8"),
        "index.md": build_index_md(choices).encode("utf-8"),
    }
    for c in choices:
        files[f"frames/frame_{c.index:02d}.jpg"] = c.key_file.read_bytes()
        phone = c.phone_file.read_bytes() if c.phone_file else make_phone_jpeg(c.key_file)
        files[f"phone/phone_{c.index:02d}.jpg"] = phone
    return files


def tree_hash(files: dict[str, bytes]) -> str:
    """sha256 over sorted (path, content hash) pairs."""
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(rel.encode("utf-8"))
        digest.update(hashlib.sha256(files[rel]).digest())
    return digest.hexdigest()


def dir_hash(root: Path) -> str:
    """Same hash computed from what is actually on disk (verifies the write)."""
    files = {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}
    return tree_hash(files)


def make_eval_ids(rng: random.Random, n: int) -> list[str]:
    """n distinct random eval ids."""
    ids: set[str] = set()
    while len(ids) < n:
        ids.add("e" + "".join(rng.choices("0123456789abcdef", k=10)))
    out = sorted(ids)
    rng.shuffle(out)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--force", action="store_true", help="delete and rebuild packs/key/manifest")
    args = parser.parse_args()

    if not PROMPT_PATH.exists():
        print(f"missing frozen prompt template {PROMPT_PATH}", file=sys.stderr)
        return 1
    packs_dir = STUDY_DIR / "packs"
    key_path = STUDY_DIR / "key.json"
    if (packs_dir.exists() or key_path.exists()) and not args.force:
        print("studies/s1 already prepared; pass --force to rebuild (this invalidates any results)", file=sys.stderr)
        return 1
    results_dir = STUDY_DIR / "results"
    if args.force and results_dir.exists() and any(results_dir.glob("*.json")):
        print("results/ already holds critic output; move it away first, --force would orphan it", file=sys.stderr)
        return 1
    if args.force:
        for folder in (packs_dir, STUDY_DIR / "prompts"):
            if folder.exists():
                shutil.rmtree(folder)

    rng = random.Random(args.seed)
    pairs = [(v, r) for v in VERSIONS for r in range(1, REPEATS + 1)]
    ids = make_eval_ids(rng, len(pairs))
    rng.shuffle(pairs)
    key = {eid: {"version": v, "repeat": r} for eid, (v, r) in zip(ids, pairs)}
    run_order = list(ids)
    rng.shuffle(run_order)

    template = PROMPT_PATH.read_text(encoding="utf-8")
    if "{PACK_DIR}" not in template:
        print("prompt.md must contain the {PACK_DIR} placeholder", file=sys.stderr)
        return 1

    frame_rows: list[list[object]] = []
    files_by_version: dict[int, dict[str, bytes]] = {}
    for version in VERSIONS:
        choices = choose_frames(version)
        files_by_version[version] = build_pack_files(version, choices)
        for c in choices:
            frame_rows.append([version, c.index, c.target_s, c.key_file.name, c.src_s, c.delta_s,
                               c.phone_file.name if c.phone_file else "generated from key frame"])

    (STUDY_DIR / "prompts").mkdir(parents=True, exist_ok=True)
    (STUDY_DIR / "results").mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    dispatch: list[dict[str, str]] = []
    for eid, meta in key.items():
        files = files_by_version[meta["version"]]
        pack = packs_dir / eid
        for rel, data in files.items():
            target = pack / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        hashes[eid] = dir_hash(pack)
        if hashes[eid] != tree_hash(files):
            raise RuntimeError(f"pack {eid} differs from its in-memory source")
        prompt_file = STUDY_DIR / "prompts" / f"{eid}.md"
        prompt_file.write_text(template.replace("{PACK_DIR}", str(pack)), encoding="utf-8", newline="\n")
        dispatch.append({"eval_id": eid, "pack_dir": str(pack), "prompt_file": str(prompt_file),
                         "result_path": str(STUDY_DIR / "results" / f"{eid}.json")})

    # repeats of one version must hash identically; different versions must differ
    by_version: dict[int, set[str]] = {}
    for eid, meta in key.items():
        by_version.setdefault(meta["version"], set()).add(hashes[eid])
    if any(len(h) != 1 for h in by_version.values()):
        raise RuntimeError("repeats of one version are not byte-identical")
    if len({next(iter(h)) for h in by_version.values()}) != len(by_version):
        raise RuntimeError("two different versions produced identical packs")

    key_path.write_text(json.dumps(key, indent=2, sort_keys=True), encoding="utf-8")
    with (STUDY_DIR / "frame_map.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["version", "pack_slot", "target_s_v7_timeline", "key_file", "key_time_s_in_cut",
                         "delta_s_vs_ideal", "phone_source"])
        writer.writerows(frame_rows)
    with (STUDY_DIR / "dispatch.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["eval_id", "pack_dir", "prompt_file", "result_path"])
        writer.writeheader()
        for eid in run_order:
            writer.writerow(next(d for d in dispatch if d["eval_id"] == eid))

    manifest = {
        "study": "s1_editor_critic_repeatability",
        "created": datetime.now().isoformat(timespec="seconds"),
        "seed": args.seed,
        "versions": VERSIONS,
        "repeats": REPEATS,
        "n_evaluations": len(key),
        "targets_v7_timeline_s": TARGETS_V7_S,
        "max_delta_s": MAX_DELTA_S,
        "prompt_sha256": hashlib.sha256(PROMPT_PATH.read_bytes()).hexdigest(),
        "run_order": run_order,
        "pack_tree_sha256": hashes,
        "notes": [
            "key.json and this manifest must never be shown to a critic.",
            "dispatch.csv lists the evaluations in run order with no version information.",
            "v1 has no per-section audio QC (only whole-mix loudness); this is a documented confound.",
            "v1 and v2 have no phone-size frames on disk; theirs are generated from the key frames.",
        ],
    }
    (STUDY_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    sizes = [sum(p.stat().st_size for p in (packs_dir / eid).rglob("*") if p.is_file()) for eid in key]
    n_files = sum(1 for p in packs_dir.rglob("*") if p.is_file())
    deltas = [abs(float(r[5])) for r in frame_rows]
    print(f"packs: {len(key)} in {packs_dir}")
    print(f"files: {n_files} ({n_files // len(key)} per pack), {len(TARGETS_V7_S)} frame slots per pack")
    print(f"size per pack: {min(sizes) / 1e6:.1f}-{max(sizes) / 1e6:.1f} MB; total {sum(sizes) / 1e6:.1f} MB")
    print(f"frame mapping: max |delta| {max(deltas):.2f}s, mean {sum(deltas) / len(deltas):.2f}s (see frame_map.csv)")
    print(f"byte-identical repeats verified for {len(by_version)} versions; seed {args.seed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
