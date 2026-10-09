"""Beat grid of the music bed and how the cuts sit on it (the 'music-locked montage' recut, Connor 2026-10-08).

    <analytics venv python> beatgrid.py [music.f32] [--json out.json]

Reads the staged music stem (audio/music_pd.f32: float32 stereo, 48 kHz, the build's own placement of the Dvorak /
Egmont / Largo spans, before ducking) and the SHOTS table, then reports:
  - beats (librosa beat tracker, ONE global analysis of the whole stem) and onset-strength peaks above the 90th
    percentile (spectral-flux candidates, not musical downbeats; Codex 2026-10-08: use them only as candidates);
  - for every cut, the distance to the nearest beat and nearest hit in frames (24 fps);
  - per act, the share of cuts within +-2 frames of a beat ("locked").
Times are REAL seconds. Nothing is written except the optional JSON.
"""
import json
import re
import sys
from pathlib import Path

import librosa
import numpy as np

WORK = Path(__file__).resolve().parent
SR_IN, SR, FPS = 48000, 22050, 24
ACTS = [("cold open", 0.0, 10.6), ("launch", 10.6, 19.0), ("act 2", 19.0, 33.3), ("moon", 33.3, 40.3),
        ("act 3", 40.3, 61.9), ("epilogue", 61.9, 79.0)]


def cut_times() -> list[float]:
    src = (WORK / "build.py").read_text(encoding="utf-8")
    t0s = [float(m.group(1)) for m in re.finditer(r"^\s*Shot\(\s*([\d.]+)\s*,", src, re.M)]
    return sorted({t for t in t0s if t > 0})


def load_music(path: Path) -> np.ndarray:
    x = np.fromfile(path, dtype=np.float32).reshape(-1, 2).mean(axis=1)
    return librosa.resample(x, orig_sr=SR_IN, target_sr=SR)


def grid(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=256)
    tempo, beats = librosa.beat.beat_track(onset_envelope=env, sr=SR, hop_length=256, units="time")
    peaks = librosa.util.peak_pick(env, pre_max=8, post_max=8, pre_avg=20, post_avg=20, delta=0.05, wait=10)
    thr = np.percentile(env, 90)
    hits = librosa.frames_to_time(peaks[env[peaks] >= thr], sr=SR, hop_length=256)
    return np.asarray(beats), np.asarray(hits), float(np.atleast_1d(tempo)[0])


def nearest(t: float, arr: np.ndarray) -> float:
    return float(arr[np.argmin(np.abs(arr - t))] - t) if len(arr) else float("nan")


def main() -> None:
    argv = sys.argv[1:]
    if "--json" in argv:
        i = argv.index("--json")
        argv = argv[:i] + argv[i + 2:]
    args = [a for a in argv if not a.startswith("--")]
    path = Path(args[0]) if args else WORK / "audio" / "music_pd.f32"
    y = load_music(path)
    beats, hits, tempo = grid(y)
    cuts = cut_times()
    rows = []
    for c in cuts:
        db, dh = nearest(c, beats), nearest(c, hits)
        rows.append({"cut": c, "beat_off_fr": round(db * FPS, 1), "hit_off_fr": round(dh * FPS, 1)})
    print(f"tempo ~{tempo:.1f} BPM (global), {len(beats)} beats, {len(hits)} strong hits, {len(cuts)} cuts")
    acts = []
    for name, a, b in ACTS:
        sel = [r for r in rows if a <= r["cut"] < b]
        if not sel:
            continue
        locked = sum(abs(r["beat_off_fr"]) <= 2 or abs(r["hit_off_fr"]) <= 2 for r in sel) / len(sel)
        hit_t = [round(float(h), 2) for h in hits if a <= h < b]
        acts.append({"act": name, "cuts": len(sel), "locked_share": round(locked, 2), "hits": hit_t})
        print(f"{name:10s} cuts {len(sel):2d}  locked(+-2 fr) {locked:4.0%}  hits {hit_t}")
    print("cut     beat_off_fr  hit_off_fr")
    for r in rows:
        print(f"{r['cut']:6.2f}  {r['beat_off_fr']:+6.1f}      {r['hit_off_fr']:+6.1f}")
    if "--json" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--json") + 1])
        out.write_text(json.dumps({"tempo": tempo, "beats": [round(float(b), 3) for b in beats],
                                   "hits": [round(float(h), 3) for h in hits], "cuts": rows, "acts": acts},
                                  indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
