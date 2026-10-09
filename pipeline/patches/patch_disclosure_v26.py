"""v26 disclosure diet: wire polish_v26b.py into build.py behind V26_DISCLOSURE = True, right after polish_v26.

    py patch_disclosure_v26.py            # the real build.py (needs patch_polish_v26)
    py patch_disclosure_v26.py BUILD.py   # a copy (dry run)

Changes (one insertion): after the 'polish_v26.apply()' block that patch_polish_v26 added, a V26_DISCLOSURE flag and
'polish_v26b.apply()' (every disclosure as one quiet footnote: medium, cap 27 px, cream 75 %, no plate; see the module
docstring). False: the previous overlays exactly. Anchor: patch_polish_v26's block; no other patch touches it.
Refuses a double apply; keeps the file's EOL (build.py is CRLF).
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
if "polish_v26b" in s:
    sys.exit("patch_disclosure_v26 already applied")
assert "polish_v26.apply()" in s, "apply patch_polish_v26 first"
A = '''if V24_POLISH and V26_POLISH2:
    import polish_v26
    polish_v26.apply()
'''
B = A + '''V26_DISCLOSURE = True   # v26: polish_v26b.apply() (director: disclosures smaller and quieter): every disclosure as one
#                         footnote style (Franklin medium 40, cream 75 %, no plate); False: the previous overlays exactly
if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE:
    import polish_v26b
    polish_v26b.apply()
'''
assert s.count(A) == 1, f"{s.count(A)} matches for the polish_v26 block"
s = s.replace(A, B)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"disclosure_v26: 1 insertion in {P.name}")
