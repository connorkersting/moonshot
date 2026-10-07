"""Write exports/moonshot/edl.csv from build.py's SHOTS/DIALOG/score tables (one row per picture shot,
plus audio rows). Usage: py edl.py N (N = version the tables describe)."""
import csv
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import build
import score_pd

OUT = (CRAFTWORK / "exports/moonshot/edl.csv")
SRC_NAME = {"SV": "saturnv_enhanced_1080.mp4", "L70": "launch_70mm.mp4", "BR": "broll25_720.mp4", "BR16": "broll25_720.mp4", "BR16H": "broll25_720.mp4", "BR16L": "broll25_720.mp4", "BRD": "broll25_720.mp4"}


def main() -> None:
    ver = sys.argv[1] if len(sys.argv) > 1 else "?"
    rows = []
    for i, s in enumerate(build.SHOTS):
        dur = s.t1 - s.t0
        if s.src in SRC_NAME:
            src, sin, sout = SRC_NAME[s.src], s.src_in, s.src_in + dur * s.speed
            notes = [f"crop {s.crop or build.CROP.get(s.src, 'none')}", f"grade[{build.GRADE[s.src]}]", "LUT+halation+vignette+grain"]
            if s.speed != 1.0:
                notes.append(f"speed {s.speed:g}x")
            if s.push != (1.0, 1.0):
                notes.append(f"push {s.push[0]:g}->{s.push[1]:g}")
            if s.darken:
                notes.append(f"darken {s.darken:g}")
        elif s.src == "STILL":
            src, sin, sout = s.img, 0.0, 0.0
            notes = [f"Ken Burns {s.kb}", "LUT+halation+vignette+grain"]
            if s.darken:
                notes.append(f"darken {s.darken:g}")
        else:
            src, sin, sout = "GENERATED", 0.0, 0.0
            notes = [s.src.lower()]
        rows.append({"version": ver, "track": "V1", "shot": f"s{i:02d}", "timeline_in": f"{s.t0:.3f}",
                     "timeline_out": f"{s.t1:.3f}", "source_file": src, "source_in": f"{sin:.3f}",
                     "source_out": f"{sout:.3f}", "notes": f"{s.note}; " + "; ".join(notes)})
    for j, (src, a, b, t, g) in enumerate(build.DIALOG):
        rows.append({"version": ver, "track": "A1-dialog", "shot": f"d{j:02d}", "timeline_in": f"{t:.3f}",
                     "timeline_out": f"{t + b - a:.3f}", "source_file": Path(src).name, "source_in": f"{a:.3f}",
                     "source_out": f"{b:.3f}", "notes": f"craft_tools.restore audio; HP120/LP7k; level-matched -20 dBFS; gain {g:+g} dB"})
    for j, (src, a, b, t, g, fi, fo) in enumerate(score_pd.MUSIC):
        rows.append({"version": ver, "track": "A2-music", "shot": f"m{j:02d}", "timeline_in": f"{t:.3f}",
                     "timeline_out": f"{t + b - a:.3f}", "source_file": Path(src).name, "source_in": f"{a:.3f}",
                     "source_out": f"{b:.3f}", "notes": f"fade in {fi}s / out {fo}s; bus automation; ducked -10 dB under dialogue"})
    for j, (rel, t, g, align, maxlen) in enumerate(score_pd.SONNISS):
        rows.append({"version": ver, "track": "A3-sfx", "shot": f"x{j:02d}", "timeline_in": f"{t:.3f}",
                     "timeline_out": f"{t + maxlen:.3f}", "source_file": Path(rel).name, "source_in": "0.000",
                     "source_out": f"{maxlen:.3f}", "notes": f"Sonniss GDC 2024; {align}-aligned; {g:+g} dB"})
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
