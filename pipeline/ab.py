"""Blind A/B sheets: per section, 8 frames of version X (top row) and version Y (bottom row), with the
two versions randomly assigned to labels A/B per section. The key goes to work/ab_key_vX_vY.json and
is never shown to the judge.  Usage: py ab.py NEW OLD"""
import json
import random
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

new, old = int(sys.argv[1]), int(sys.argv[2])
ROOT = (CRAFTWORK / "exports/moonshot")
OUT = ROOT / "qc" / f"ab_v{new}_v{old}"
OUT.mkdir(parents=True, exist_ok=True)
KEY = Path(__file__).parent / f"ab_key_v{new}_v{old}.json"
FONT = "fontfile='C\\:/Windows/Fonts/arialbd.ttf'"
SECTIONS = [("1_cold_open", 0.0, 10.6), ("2_drop_title", 10.6, 19.0), ("3_stats_chart", 19.0, 40.0),
            ("4_moon_lm", 40.0, 47.0), ("5_alarm", 47.0, 55.6), ("6_fuel_landing", 55.6, 69.6),
            ("7_outro", 69.6, 90.0)]
ACT2_D = 6.7   # v8+: act 2 is 6.7 s shorter; SECTIONS above are v7 times


def vt(ver: int, t: float) -> float:
    """Section time t (v7 timeline) on version ver's timeline: from v8 on, the Moon (40.0) and after are 6.7 s earlier."""
    return round(t - ACT2_D, 3) if ver >= 8 and t >= 40.0 else t


rng = random.Random(new * 1000 + old)
key = {}
for name, a, b in SECTIONS:
    top_is_new = rng.random() < 0.5
    # a section whose length differs between the versions would give away the rows by their timestamps
    same_len = abs((vt(new, b) - vt(new, a)) - (vt(old, b) - vt(old, a))) < 1e-6
    stamp = "  %{pts\\:hms}" if same_len else ""
    rows = []
    for label, ver in (("A", new if top_is_new else old), ("B", old if top_is_new else new)):
        va, vb = vt(ver, a), vt(ver, b)
        step = (vb - va) / 8
        png = OUT / f"_{name}_{label}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{va + step / 2:.3f}", "-t", f"{vb - va:.3f}",
                        "-i", str(ROOT / "versions" / f"moonshot_v{ver}.mp4"), "-vf",
                        f"fps=1/{step:.4f},scale=400:-1,drawtext={FONT}:text='{label}{stamp}':x=6:y=6:fontsize=20:"
                        f"fontcolor=yellow:box=1:boxcolor=black@0.7,tile=8x1", "-frames:v", "1", str(png)], check=True)
        rows.append(png)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(rows[0]), "-i", str(rows[1]), "-filter_complex",
                    "vstack", "-frames:v", "1", str(OUT / f"{name}.jpg")], check=True)
    for r in rows:
        r.unlink()
    key[name] = {"A": new if top_is_new else old, "B": old if top_is_new else new}
KEY.write_text(json.dumps(key, indent=2))
print(f"sheets in {OUT}; key in {KEY.name} (do not show the judge)")
