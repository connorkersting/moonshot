"""v9d: landing captions at the MEASURED word times (logical time; real + 6.7): eagle.wav 'Houston, uh, Tranquility
Base here.' real 56.7-60.15, 'The Eagle has landed.' real 60.45-61.45 -> tl 63.4-66.85 and 67.15-68.3."""
import sys
from pathlib import Path
P = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "build.py"
s = P.read_text(encoding="utf-8")
for a, b in (('(63.25, 65.30, "EAGLE · ARMSTRONG",', '(63.40, 66.90, "EAGLE · ARMSTRONG",'),
             ('(65.45, 68.25, "EAGLE · ARMSTRONG",', '(67.10, 68.35, "EAGLE · ARMSTRONG",')):
    assert s.count(a) == 1, a
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
print("v9d: landing captions re-timed")
