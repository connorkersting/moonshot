"""Audio-engineer QC for a MOONSHOT version: measurements, not impressions.

    py audio_qc.py N

Reads the exported MP4 plus the pre-normalization mix components saved by build.py mix
(audio/dlg_vN.f32, audio/bed_vN.f32). Writes exports/moonshot/qc/vN/audio_qc.md and spectrogram.png:
  * per-section integrated loudness, LRA and true peak (ffmpeg ebur128 on the decoded final)
  * dialogue-to-bed ratio (dB, RMS over each caption line) from the stems actually mixed
  * click/pop scan at every music, SFX and dialogue join in the final mix
  * whisper pass over the final mix vs the caption track: word recall per line (< 0.6 = flagged)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402
import score_pd  # noqa: E402

N = int(sys.argv[1])
SR = 48000
ROOT = CRAFTWORK
VID = ROOT / "exports" / "moonshot" / "versions" / f"moonshot_v{N}.mp4"
QC = ROOT / "exports" / "moonshot" / "qc" / f"v{N}"
AUD = build.AUD
SECTIONS = [("cold open", 0.0, 10.6), ("drop + title", 10.6, 19.0), ("act 2 stats/chart", 19.0, 40.0),
            ("lunar transition", 40.0, 47.0), ("1202 alarm", 47.0, 55.6), ("bingo fuel", 55.6, 63.0),
            ("landing", 63.0, 68.6), ("silence", 68.6, 69.6), ("outro", 69.6, 87.5), ("credits", 87.5, 90.0)]
if N >= 8:   # v8: act 2 is 6.7 s shorter
    SECTIONS = [("cold open", 0.0, 10.6), ("drop + title", 10.6, 19.0), ("act 2 stats/ascent", 19.0, 33.3),
                ("lunar transition", 33.3, 40.3), ("1202 alarm", 40.3, 48.9), ("bingo fuel", 48.9, 56.3),
                ("landing", 56.3, 61.9), ("silence", 61.9, 62.9), ("outro", 62.9, 79.0), ("credits", 79.0, float(build.TOTAL))]
ACT2_D = 6.7   # v8+: captions and the v7 times below are logical; real() maps them onto this version's timeline


def real(t: float) -> float:
    """v7 (logical) time -> this version's real time (identity before v8)."""
    return round(t - ACT2_D, 3) if N >= 8 and t >= 40.0 else t


def ebur(t0: float, t1: float) -> dict:
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", str(VID),
                        "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    s = e[e.rfind("Summary:"):]
    get = lambda k: (re.search(rf"{k}:\s+(-?[\d.]+|-inf)", s) or [None, "nan"])[1]
    return {"I": get("I"), "LRA": get("LRA"), "TP": get("Peak")}


def decode_final() -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(VID), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12))


def joins() -> list[tuple[float, str]]:
    j = []
    for src, a, b, t, *_ in build.DIALOG:
        j += [(t, f"dialog in {Path(src).name}"), (t + b - a, f"dialog out {Path(src).name}")]
    for src, a, b, t, *_ in score_pd.MUSIC:
        j += [(t, f"music in {Path(src).name}"), (t + b - a, f"music out {Path(src).name}")]
    for rel, t, g, align, maxlen in score_pd.SONNISS:
        j.append((t, f"sfx {Path(rel).name[:40]}"))
    for s in build.SHOTS:
        pass
    j += [(real(68.6), "flash cut to silence"), (real(69.6), "swell in")]
    return sorted(j)


def click_scan(x: np.ndarray) -> list[str]:
    out = []
    d = np.abs(np.diff(x))
    for t, what in joins():
        i = int(t * SR)
        if i < 2400 or i > len(d) - 2400:
            continue
        near = d[i - 480:i + 480]            # +-10 ms
        ctx = np.concatenate([d[i - 4800:i - 960], d[i + 960:i + 4800]])
        ratio = float(near.max() / (np.percentile(ctx, 99) + 1e-9))
        if ratio > 3.0:
            out.append(f"| {t:6.2f} | {what} | {ratio:.1f}x |")
    return out


def whisper_check(x: np.ndarray) -> list[str]:
    """Transcribe each dialogue window of the FINAL mix separately (whisper hallucinates long segments
    across music-only stretches when fed the whole 90 s), then score word recall per caption line."""
    windows = [(0.0, 20.0), (46.5, 55.6), (55.4, 62.6), (62.4, 69.0), (69.6, 84.0)]
    windows = [(real(a), real(b)) for a, b in windows]      # v8+: shift with the picture
    segs = []
    for k, (w0, w1) in enumerate(windows):
        wav = QC / f"mixwin{k}.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{w0}", "-t", f"{w1 - w0}", "-i", str(VID),
                        "-ac", "1", "-ar", "16000", str(wav)], check=True)
        subprocess.run(["uv", "run", "python", "-m", "craft_tools.captions", str(wav), "--max-chars", "30",
                        "--out", str(QC)], cwd=os.environ.get("CRAFT_TOOLS", "craft-tools"), capture_output=True)
        js = QC / f"mixwin{k}.json"
        if not js.exists():
            continue
        d = json.loads(js.read_text(encoding="utf-8"))
        for sg in d.get("transcription", []):
            o = sg.get("offsets", {})
            segs.append((w0 + o.get("from", 0) / 1000, w0 + o.get("to", 0) / 1000, sg.get("text", "")))
    norm = lambda s: re.findall(r"[a-z0-9]+", s.lower().replace("½", " and a half"))
    rows = []
    for t0, t1, who, text in build.CAPTIONS:
        t0, t1 = real(t0), real(t1)                         # captions are logical (v7) time from v8 on
        heard = " ".join(tx for a, b, tx in segs if b >= t0 - 0.4 and a <= t1 + 0.8 and (b - a) < 12)
        hw = set(norm(heard))
        want = norm(text)
        hit = sum(1 for w in want if w in hw)
        rec = hit / max(len(want), 1)
        flag = "LOW" if rec < 0.6 else ""
        rows.append(f"| {t0:6.2f} | {who or '-'} | {text} | {rec:.2f} {flag} | {heard.strip()[:70]} |")
    return rows


def main() -> None:
    QC.mkdir(parents=True, exist_ok=True)
    lines = [f"# Audio QC v{N}", "", f"File: {VID.name}", ""]
    full = ebur(0, 90)
    lines += [f"Whole mix: I {full['I']} LUFS, LRA {full['LRA']} LU, true peak {full['TP']} dBTP", "",
              "## Per section", "", "| section | t | I (LUFS) | LRA | TP |", "|---|---|---|---|---|"]
    for name, a, b in SECTIONS:
        m = ebur(a, b)
        lines.append(f"| {name} | {a:.1f}-{b:.1f} | {m['I']} | {m['LRA']} | {m['TP']} |")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(VID), "-lavfi",
                    "showspectrumpic=s=1800x500:legend=1:scale=log", str(QC / "spectrogram.png")])
    lines += ["", "Spectrogram: spectrogram.png", ""]
    dlg_p, bed_p = AUD / f"dlg_v{N}.f32", AUD / f"bed_v{N}.f32"
    if dlg_p.exists() and bed_p.exists():
        dlg = np.fromfile(dlg_p, np.float32)
        bed = np.fromfile(bed_p, np.float32)
        lines += ["## Dialogue-to-bed ratio per line (target >= +10 dB; music+SFX after ducking)", "",
                  "| t | speaker | line | dialog dB | bed dB | ratio |", "|---|---|---|---|---|---|"]
        for t0, t1, who, text in build.CAPTIONS:
            t0, t1 = real(t0), real(t1)                     # stems are real time; captions logical from v8 on
            a, b = int(t0 * SR), int(t1 * SR)
            dd, bb = rms_db(dlg[a:b]), rms_db(bed[a:b])
            flag = " LOW" if dd - bb < 10 else ""
            lines.append(f"| {t0:.2f} | {who or '-'} | {text[:40]} | {dd:.1f} | {bb:.1f} | {dd - bb:+.1f}{flag} |")
    else:
        lines.append("(no dlg/bed stems saved for this version; ratio skipped)")
    x = decode_final()
    clicks = click_scan(x)
    lines += ["", "## Click/pop scan at joins (sample-diff peak vs 99th pct of surrounding 100 ms; > 3x listed)", ""]
    lines += (["| t | join | spike |", "|---|---|---|"] + clicks) if clicks else ["none above 3x"]
    lines += ["", "## Whisper on the final mix vs captions (word recall; LOW = a viewer may not hear it)", "",
              "| t | speaker | caption | recall | whisper heard |", "|---|---|---|---|---|"] + whisper_check(x)
    (QC / "audio_qc.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
