"""v9b: v8 A/B fixes. (1) the wide Mission Control shot started on the tail of the Earthrise clip (src 1236.0)
-> 1237.5; (2) the 24,200 MPH card ghosted across the cut -> fade done by u=3.25 (window 3.5 s)."""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
s = P.read_text(encoding="utf-8")
R = [('"BR", 1236.0, push=(1.0, 1.05), note="flight controller, tense (Houston: 30 seconds)"',
      '"BR", 1237.5, push=(1.0, 1.05), note="Mission Control consoles, tense (Houston: 30 seconds)"'),
     ("a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 3.2) / 0.3))     # v8: 3.5 s window (v7 3.0: 2.7)",
      "a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.9) / 0.35))    # v9: fade done before the 33.3 cut")]
for a, b in R:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
print(f"v9b: {len(R)} patches")
