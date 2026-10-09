"""v24 polish: wire polish_v24.py (Fable's v23 overlay notes b, c, d) into build.py behind V24_POLISH = True.

    py patch_polish_v24.py            # the real build.py (v23 + v23b or later)
    py patch_polish_v24.py BUILD.py   # a copy (dry run)

Anchors: the 'import hud_v23' line and the 'V23_HUD = True' line, which patch_v24 (audio), patch_v25 (hero) and
patch_v26 (scans) do not touch (checked by applying all four in both orders on a copy). polish_v24.apply() runs at
import time, before validate_assets() -> hud_v23.load_ascent() computes the ascent layout.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "import hud_v23" in s, "apply patch_v23 first"
assert "polish_v24" not in s, "polish_v24 already applied"
R = [
    ('''import hud_v23      # v23: ascent text in the system (no baked labels), flash-forward tag, TAG-size disclosures, end note
''',
     '''import hud_v23      # v23: ascent text in the system (no baked labels), flash-forward tag, TAG-size disclosures, end note
import polish_v24   # v24: Fable's v23 notes on hud_v23 (label gap 28 px, 'AVERAGE DISTANCE, ROUNDED', cream end note)
'''),
    ('''V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly
''',
     '''V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly
V24_POLISH = True       # v24: polish_v24.apply() patches hud_v23 (Fable v23 notes b, c, d); False: v23's overlays exactly
if V24_POLISH:
    polish_v24.apply()
'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:80]!r}"
    s = s.replace(a, b)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"polish_v24: {len(R)} replacements in {P.name}")
