"""v26 polish2: wire polish_v26.py (Fable's v24 notes 1-2) into build.py behind V26_POLISH2 = True, after polish_v24.

    py patch_polish_v26.py            # the real build.py (needs patch_polish_v24)
    py patch_polish_v26.py BUILD.py   # a copy (dry run)

Anchor: the 'polish_v24.apply()' block that patch_polish_v24 added; no other patch touches it.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "polish_v24.apply()" in s, "apply patch_polish_v24 first"
assert "polish_v26" not in s, "polish_v26 already applied"
A = '''if V24_POLISH:
    polish_v24.apply()
'''
B = '''if V24_POLISH:
    polish_v24.apply()
V26_POLISH2 = True      # v26: polish_v26.apply() (Fable v24 notes: 'AVG DISTANCE, ROUNDED' inside its rule, medium-weight
#                         end-card disclosure under the date line); False: v24's overlays exactly
if V24_POLISH and V26_POLISH2:
    import polish_v26
    polish_v26.apply()
'''
assert s.count(A) == 1, f"{s.count(A)} matches for the polish_v24 block"
s = s.replace(A, B)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"polish_v26: 1 replacement in {P.name}")
