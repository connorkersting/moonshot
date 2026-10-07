"""QC for a MOONSHOT version: 24-frame contact sheet, close-ups at every text/graphic moment,
ebur128 loudness, black-frame scan. Usage: py qc.py N"""
import json
import re
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

N = int(sys.argv[1])
ROOT = (CRAFTWORK / "exports/moonshot")
VID = ROOT / "versions" / f"moonshot_v{N}.mp4"
QC = ROOT / "qc" / f"v{N}"
QC.mkdir(parents=True, exist_ok=True)
FONT = "fontfile='C\\:/Windows/Fonts/arialbd.ttf'"

# graphic / text moments (timeline seconds)
KEY = [1.0, 3.0, 11.5, 13.4, 15.0, 17.3, 20.0, 21.2, 27.0, 28.3, 30.0, 33.0, 35.5, 38.5, 41.5, 45.5, 47.4,
       49.8, 51.5, 53.5, 56.5, 59.0, 61.0, 62.3, 64.5, 67.0, 68.7, 70.5, 72.0, 76.0, 78.5, 81.0, 84.5, 85.5, 87.5]
if N >= 8:   # v8: act 2 is 6.7 s shorter (Moon at 33.3): new act-2 keys (ascent, staging, interstage, 24,200 MPH)
    KEY = [k for k in KEY if k < 22.0] + [23.5, 27.0, 29.0, 31.5] + [round(k - 6.7, 2) for k in KEY if k >= 40.0]


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def main() -> None:
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(VID)],
                               capture_output=True, text=True).stdout)
    # 24-frame contact sheet
    step = dur / 24
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(VID), "-vf",
        f"fps=1/{step:.4f},scale=480:-1,drawtext={FONT}:text='%{{pts\\:hms}}':x=6:y=6:fontsize=20:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=6x4",
        "-frames:v", "1", str(QC / "contact.jpg")])
    for t in KEY:
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(VID), "-frames:v", "1", "-vf", "scale=960:-1",
            str(QC / f"key_{t:05.1f}.jpg")])
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(VID), "-frames:v", "1", "-vf", "scale=640:360",
            str(QC / f"k360_{t:05.1f}.jpg")])   # phone-size legibility check
    # loudness
    e = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(VID), "-af", "ebur128=peak=true", "-f", "null", "-"])
    summ = e[e.rfind("Summary:"):]
    vals = {k: re.search(rf"{k}:\s+(-?[\d.]+)", summ).group(1) for k in ["I", "LRA", "Peak"]}
    # black frames (intentional ones: 0-0.2, 68.6-69.6 after flash, 87.5-90 credits are on black)
    b = sh(["ffmpeg", "-hide_banner", "-nostats", "-i", str(VID), "-vf", "blackdetect=d=0.08:pix_th=0.06", "-an", "-f", "null", "-"])
    blacks = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", b)
    rep = {"duration": dur, "integrated_LUFS": vals["I"], "LRA": vals["LRA"], "true_peak_dBTP": vals["Peak"],
           "black_segments": blacks}
    (QC / "qc.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
