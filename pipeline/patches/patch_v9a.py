"""v9a: give the ignition a real drop. v8 measured cold open -14.2 vs drop -13.2 LUFS because the whole 0-18.9 s
countdown was ONE dialogue entry, so the adaptive duck held the music (and the ignition/title impacts) down by up to
22 dB through the drop. Fix: split the countdown into phrase entries, cap the duck on the hype lines, never duck the
impact SFX. Apply on the v8 source."""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
s = P.read_text(encoding="utf-8")
nl = "\r\n" if "\r\n" in s else "\n"
lines = s.split(nl)
hit = [i for i, ln in enumerate(lines) if '(RST / "countdown.wav", 12.0,' in ln]
assert len(hit) == 1, hit
ind = lines[hit[0]][: len(lines[hit[0]]) - len(lines[hit[0]].lstrip())]
lines[hit[0]] = nl.join([
    f'{ind}(RST / "countdown.wav", 12.0, 22.5, 0.0, -4.0),     # "10 ... ignition sequence starts ... 1"',
    f'{ind}(RST / "countdown.wav", 22.5, 24.6, 10.5, -2.0),    # "zero, all engines running"',
    f'{ind}(RST / "countdown.wav", 25.0, 31.15, 13.0, -2.0),    # "liftoff! we have a liftoff, 32 minutes past the hour"',
])
s = nl.join(lines)
a = "    c0, c1 = int(10.6 * SR), int(11.4 * SR)\n    env_db[c0:c1] = np.minimum(env_db[c0:c1], 16.0)"
a = a.replace("\n", nl)
assert s.count(a) == 1, "ignition cap block not found"
b = nl.join([
    "    # hype lines keep the music up (captions carry the words): cap the duck depth in these windows",
    "    for c0s, c1s, cap in ():   # v9: caps removed (they buried the launch lines; clarity first)",
    "        c0, c1 = int(c0s * SR), int(c1s * SR)",
    "        env_db[c0:c1] = np.minimum(env_db[c0:c1], cap)",
])
s = s.replace(a, b)
a2 = "    sgain = gain                                # SFX get the full computed depth (Codex #3)"
assert s.count(a2) == 1, "sgain line not found"
b2 = nl.join([
    a2,
    "    for i0s, i1s in ():   # v9: impacts duck with the bed (unducking buried the launch lines)",
    "        sgain = sgain.copy()",
    "        sgain[int(i0s * SR):int(i1s * SR)] = 1.0",
])
s = s.replace(a2, b2)
P.write_text(s, encoding="utf-8")
print("v9a: countdown split into 3 phrases, hype-line duck caps, impacts unducked")
