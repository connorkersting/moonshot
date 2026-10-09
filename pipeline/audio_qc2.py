"""Whisper recall per caption line on a MOONSHOT export, with windows that cover EVERY caption (NEW tool, v22).

    py audio_qc2.py VIDEO.mp4 OUT_DIR [--offline-captions build.py]

Why (Codex review of the v22 brief, P0 2): audio_qc.whisper_check() transcribes five fixed windows (real 0-20,
39.8-48.9, 48.7-55.9, 55.7-62.3, 62.9-77.3 s). None of them contains 26.55 "Staging." or 28.30 "And ignition.", so
the "0.00 recall" those two lines carried for four versions was never measured. audio_qc.py is unchanged.

What this does (read-only on the video; writes only into OUT_DIR, which must not be a pipeline folder):
  1. CAPTIONS are read from build.py with ast (nothing in build.py runs) and mapped to real time exactly as
     audio_qc.real() does (logical t >= 40.0 plays at t - 6.7).
  2. Pass A, "cluster": captions are grouped into windows (a new window starts when the gap to the previous caption
     exceeds 3 s or the window would pass 20 s); each window runs 1.0 s before its first caption to 1.0 s after its
     last. Asserted: every caption lies inside exactly one window.
  3. Pass B, "isolated": every caption gets its own window, t0 - 0.6 s to t1 + 0.8 s (Whisper drops short lines
     next to music in long windows; this is the per-line listening test).
  4. Each window is cut from the final mix (mono 16 kHz) and transcribed FRESH by whisper.cpp large-v3-turbo through
     craft_tools.captions (stale JSON is deleted first; a window that produces no JSON is an error, not a skip).
  5. Recall = share of the caption's words (a-z0-9 tokens, "½" -> "and a half") heard in segments overlapping
     [t0 - 0.4, t1 + 0.8]. LOW < 0.6.
Writes OUT_DIR/audio_qc2.md and audio_qc2.json (both passes, per line, plus the window table).
"""
from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

WORK = Path(__file__).resolve().parent
CRAFT = Path(os.environ.get("CRAFT_TOOLS", "craft-tools"))
ACT2_D = 6.7
PIPE_DIRS = {WORK / "seg", WORK / "audio", WORK, (CRAFTWORK / "exports/moonshot/versions")}


def captions(build_py: Path) -> list[tuple[float, float, str, str]]:
    tree = ast.parse(build_py.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "CAPTIONS" for t in node.targets):
            return [tuple(c) for c in ast.literal_eval(node.value)]
    raise SystemExit(f"CAPTIONS not found in {build_py}")


def real(t: float) -> float:
    return round(t - ACT2_D, 3) if t >= 40.0 else t


def norm(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower().replace("½", " and a half"))


def cluster_windows(caps: list[tuple[float, float]]) -> list[tuple[float, float]]:
    groups: list[list[tuple[float, float]]] = []
    for a, b in caps:
        if groups and a - groups[-1][-1][1] <= 3.0 and b - groups[-1][0][0] <= 20.0:
            groups[-1].append((a, b))
        else:
            groups.append([(a, b)])
    return [(max(0.0, g[0][0] - 1.0), g[-1][1] + 1.0) for g in groups]


def transcribe(video: Path, out: Path, tag: str, w0: float, w1: float) -> list[tuple[float, float, str]]:
    wav = out / f"{tag}.wav"
    js = out / f"{tag}.json"
    for p in (js, out / f"{tag}.srt", out / f"{tag}.vtt"):
        p.unlink(missing_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{w0:.3f}", "-t", f"{w1 - w0:.3f}", "-i", str(video),
                    "-ac", "1", "-ar", "16000", str(wav)], check=True)
    r = subprocess.run(["uv", "run", "python", "-m", "craft_tools.captions", str(wav), "--max-chars", "30",
                        "--out", str(out)], cwd=str(CRAFT), capture_output=True, text=True)
    if r.returncode != 0 or not js.is_file():
        raise SystemExit(f"whisper failed on {tag} ({w0:.2f}-{w1:.2f}): exit {r.returncode} {r.stderr[-400:]}")
    d = json.loads(js.read_text(encoding="utf-8"))
    segs = []
    for sg in d.get("transcription", []):
        o = sg.get("offsets", {})
        segs.append((w0 + o.get("from", 0) / 1000, w0 + o.get("to", 0) / 1000, sg.get("text", "")))
    return segs


def score(segs: list[tuple[float, float, str]], t0: float, t1: float, text: str) -> tuple[float, str]:
    heard = " ".join(tx for a, b, tx in segs if b >= t0 - 0.4 and a <= t1 + 0.8 and (b - a) < 12)
    hw = set(norm(heard))
    want = norm(text)
    return sum(1 for w in want if w in hw) / max(len(want), 1), heard.strip()


def main() -> None:
    video, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    bp = Path(sys.argv[sys.argv.index("--offline-captions") + 1]) if "--offline-captions" in sys.argv else WORK / "build.py"
    if out in PIPE_DIRS:
        raise SystemExit(f"{out} is a pipeline folder; give a QC folder")
    out.mkdir(parents=True, exist_ok=True)
    caps = [(real(a), real(b), who, text) for a, b, who, text in captions(bp)]
    wins = cluster_windows([(a, b) for a, b, _, _ in caps])
    for a, b, _, text in caps:
        inside = [w for w in wins if w[0] <= a and b <= w[1]]
        assert len(inside) == 1, f"caption {a}-{b} {text!r} in {len(inside)} windows"
    segs_a: list[tuple[float, float, str]] = []
    for k, (w0, w1) in enumerate(wins):
        segs_a += transcribe(video, out, f"clus{k:02d}", w0, w1)
    rows = []
    for i, (a, b, who, text) in enumerate(caps):
        ra, ha = score(segs_a, a, b, text)
        segs_b = transcribe(video, out, f"line{i:02d}", max(0.0, a - 0.6), b + 0.8)
        rb, hb = score(segs_b, a, b, text)
        rows.append({"t0": a, "t1": b, "speaker": who, "caption": text, "recall_cluster": round(ra, 2),
                     "heard_cluster": ha, "recall_isolated": round(rb, 2), "heard_isolated": hb})
        print(f"{a:6.2f} {text[:40]:40s} cluster {ra:.2f}  isolated {rb:.2f}  | {hb[:60]}", flush=True)
    md = [f"# audio_qc2: Whisper recall per caption ({video.name})", "",
          "whisper.cpp large-v3-turbo-q5_0 via craft_tools.captions; fresh transcription per window. Pass A windows:",
          ", ".join(f"{a:.2f}-{b:.2f}" for a, b in wins) + " (every caption inside exactly one window).", "",
          "| t (real) | speaker | caption | recall A (cluster) | recall B (isolated) | heard (B) |", "|---|---|---|---|---|---|"]
    for r in rows:
        fl = lambda v: f"{v:.2f}{' LOW' if v < 0.6 else ''}"   # noqa: E731
        md.append(f"| {r['t0']:.2f} | {r['speaker']} | {r['caption']} | {fl(r['recall_cluster'])} | "
                  f"{fl(r['recall_isolated'])} | {r['heard_isolated'][:70]} |")
    ma = sum(r["recall_cluster"] for r in rows) / len(rows)
    mb = sum(r["recall_isolated"] for r in rows) / len(rows)
    md += ["", f"Mean recall: A {ma:.3f}, B {mb:.3f} over {len(rows)} captions."]
    (out / "audio_qc2.md").write_text("\n".join(md), encoding="utf-8")
    (out / "audio_qc2.json").write_text(json.dumps({"video": str(video), "windows": wins, "lines": rows,
                                                    "mean_cluster": ma, "mean_isolated": mb}, indent=1),
                                        encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
