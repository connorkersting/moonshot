"""v27 fixes: wire polish_v27.py (Fable's v26 review: bright-frame scrim for ARCHIVE / TIME-COMPRESSED, the caption
out-point at the 1812 cut, the ascent footnote copy) into build.py behind V27_FIXES = True.

    py patch_v27_fixes.py            # the real build.py (needs patch_disclosure_v26)
    py patch_v27_fixes.py BUILD.py   # a copy (dry run)

Changes (two insertions, SHOTS / DIALOG / CAPTIONS untouched):
  1  after the 'polish_v26b.apply()' block: the V27_FIXES flag and polish_v27.apply() (hud_v23 hooks);
  2  before 'from score_pd import USE_PD, stage_music' (after class Gfx): polish_v27.apply_caption(Gfx, ...).
False: v26 exactly. Refuses a double apply; keeps the file's EOL (build.py is CRLF).
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
if "polish_v27" in s:
    sys.exit("patch_v27_fixes already applied")
assert "polish_v26b.apply()" in s, "apply patch_disclosure_v26 first"
A = '''if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE:
    import polish_v26b
    polish_v26b.apply()
'''
B = A + '''V27_FIXES = True        # v27: polish_v27 (Fable v26 review): local scrim behind ARCHIVE / TIME-COMPRESSED on bright frames,
#                         no caption on the end plate (1812-1890), ascent note 'NOT TO SCALE (6X) · NASA FIGURES'; False: v26
if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE and V27_FIXES:
    import polish_v27
    polish_v27.apply()
'''
C = '''from score_pd import USE_PD, stage_music  # noqa: E402  (tables live in score_pd.py)
'''
D = '''if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE and V27_FIXES:    # v27: the caption out-point at the end-plate cut
    polish_v27.apply_caption(Gfx, ACT2_F0, ACT2_DF, FPS)
''' + C
for a, n in ((A, "the polish_v26b block"), (C, "the score_pd import")):
    assert s.count(a) == 1, f"{s.count(a)} matches for {n}"
s = s.replace(A, B).replace(C, D)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"v27_fixes: 2 insertions in {P.name}")
