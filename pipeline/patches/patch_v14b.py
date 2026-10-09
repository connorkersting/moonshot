"""v14b (on top of patch_v14): (1) credits disclose that some LAUNCH shots (engine + staging/interstage, likely
Apollo 6) come from other Saturn V flights, not only engine shots; (2) darken the new 16mm Earth shot s19 by 0.15 so
its lifted grey-green black doesn't jump against the Earth still's true black at the 31.0 cut."""
import sys
from pathlib import Path

W = Path(__file__).resolve().parent
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
s = P.read_bytes().decode("utf-8")
R = [
    ('Shot(31.00, 33.30, "BR", 1113.25, push=(1.12, 1.0), note=',
     'Shot(31.00, 33.30, "BR", 1113.25, push=(1.12, 1.0), darken=0.15, note='),
    ("SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS", "SOME LAUNCH SHOTS FROM OTHER SATURN V FLIGHTS"),
]
for a, b in R:
    assert s.count(a) == 1, a[:60]
    s = s.replace(a, b)
P.write_bytes(s.encode("utf-8"))
print(f"v14b: {len(R)} patches")
