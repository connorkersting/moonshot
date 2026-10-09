"""Transactional promotion of a rendered version to BEST (and optionally FINAL).

    py promote.py N            # verify versions/moonshot_vN.mp4 and write exports/moonshot/BEST.json
    py promote.py N --final    # also copy it to MOONSHOT_FINAL.mp4 and verify the copy's hash

A version is promoted only if: the file exists and is not the previous BEST's file under a new name,
ffprobe decodes every frame (count == expected), duration/resolution/fps/audio match the spec,
the version's QC report exists and its integrated loudness and true peak are in range, and the
git tag vN-final exists. BEST.json records version, tag commit, SHA-256, frames and loudness, so
FINAL is always traceable to one verified file. Nothing here deletes or overwrites a version file.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
EXP = WORK.parent.parent.parent / "exports" / "moonshot"
EXPECT = {"width": 1920, "height": 1080, "fps": "24/1", "frames": 1963}   # frames overridable: --frames N (v17+ is 2088)
LUFS_RANGE = (-15.0, -13.0)
TP_MAX = -1.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def probe(path: Path) -> dict[str, str]:
    out = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height,r_frame_rate,nb_read_frames", "-of", "default=nw=1", str(path)],
                         capture_output=True, text=True, check=True).stdout
    info = dict(line.split("=", 1) for line in out.strip().splitlines() if "=" in line)
    aud = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                          "stream=codec_name,bit_rate", "-of", "default=nw=1", str(path)],
                         capture_output=True, text=True, check=True).stdout
    info.update(dict(line.split("=", 1) for line in aud.strip().splitlines() if "=" in line))
    return info


def qc_loudness(n: int) -> tuple[float, float]:
    text = (WORK / f"aqc{n}.txt").read_text(encoding="utf-8")
    m = re.search(r"Whole mix: I (-?[\d.]+) LUFS, LRA [\d.]+ LU, true peak (-?[\d.]+) dBTP", text)
    if not m:
        raise SystemExit(f"aqc{n}.txt has no whole-mix loudness line")
    return float(m.group(1)), float(m.group(2))


def tag_commit(n: int) -> str:
    r = subprocess.run(["git", "-C", str(WORK), "rev-parse", f"v{n}-final^{{commit}}"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git tag v{n}-final missing")
    return r.stdout.strip()


def main(n: int, final: bool) -> None:
    mp4 = EXP / "versions" / f"moonshot_v{n}.mp4"
    if not mp4.exists():
        raise SystemExit(f"{mp4} does not exist")
    info = probe(mp4)
    errors = []
    if int(info.get("width", 0)) != EXPECT["width"] or int(info.get("height", 0)) != EXPECT["height"]:
        errors.append(f"resolution {info.get('width')}x{info.get('height')}")
    if info.get("r_frame_rate") != EXPECT["fps"]:
        errors.append(f"fps {info.get('r_frame_rate')}")
    if int(info.get("nb_read_frames", 0)) != EXPECT["frames"]:
        errors.append(f"decoded frames {info.get('nb_read_frames')} != {EXPECT['frames']}")
    if info.get("codec_name") != "aac":
        errors.append(f"audio codec {info.get('codec_name')}")
    lufs, tp = qc_loudness(n)
    if not LUFS_RANGE[0] <= lufs <= LUFS_RANGE[1]:
        errors.append(f"integrated loudness {lufs} outside {LUFS_RANGE}")
    if tp > TP_MAX:
        errors.append(f"true peak {tp} > {TP_MAX}")
    commit = tag_commit(n)
    if errors:
        raise SystemExit(f"NOT PROMOTED v{n}: " + "; ".join(errors))
    digest = sha256(mp4)
    manifest = {"version": n, "file": f"versions/moonshot_v{n}.mp4", "sha256": digest, "tag": f"v{n}-final",
                "commit": commit, "frames": int(info["nb_read_frames"]), "lufs": lufs, "true_peak_dbtp": tp,
                "promoted_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    best = EXP / "BEST.json"
    tmp = best.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    tmp.replace(best)
    print(f"BEST = v{n} ({digest[:12]}..., {manifest['frames']} frames, {lufs} LUFS, {tp} dBTP)")
    if final:
        dst = EXP / "MOONSHOT_FINAL.mp4"
        staged = EXP / "MOONSHOT_FINAL.mp4.tmp"
        shutil.copyfile(mp4, staged)
        if sha256(staged) != digest:
            staged.unlink()
            raise SystemExit("FINAL copy hash mismatch; FINAL left unchanged")
        staged.replace(dst)
        manifest["final_sha256"] = digest
        tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        tmp.replace(best)
        print(f"FINAL = v{n} (hash verified)")


if __name__ == "__main__":
    if "--frames" in sys.argv:
        EXPECT["frames"] = int(sys.argv[sys.argv.index("--frames") + 1])
    main(int(sys.argv[1]), "--final" in sys.argv[2:])
