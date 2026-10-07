"""v8b: v7 senior-editor fixes, applied AFTER patch_v8.py. Line-based edits so they survive v8's time shifts."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)
import re
import sys

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
s = P.read_text(encoding="utf-8")
nl = "\r\n" if "\r\n" in s else "\n"


def line_sub(text: str, must_contain: str, old: str, new: str) -> str:
    lines = text.split(nl)
    hits = [i for i, ln in enumerate(lines) if must_contain in ln]
    assert len(hits) == 1, f"{len(hits)} lines contain {must_contain!r}"
    i = hits[0]
    assert old in lines[i], f"{old!r} not in line {lines[i]!r}"
    lines[i] = lines[i].replace(old, new)
    return nl.join(lines)


# 1. dead black frame after the white pop: the touchdown source starts on a dark frame
s = line_sub(s, '"BR16H", 1398.3', "1398.3", "1398.6")
# 2. bingo HUD sat on the controller's face: wide console shot instead (Houston's "30 seconds")
s = line_sub(s, 'flight controller, tense (Houston: 30 seconds)', '"BR", 1242.0, push=(1.04, 1.0)', '"BR", 1236.0, push=(1.0, 1.05)')
# 3. grade the act-2 outliers (blue contrail / magenta interstage) toward the launch look
s = line_sub(s, 'staging: interstage falls away against blue sky', '"BR", 940.0', '"BRD", 940.0')
s = line_sub(s, 'interstage falls away over Earth', '"BR", 961.0', '"BRD", 961.0')
R = [
    ('''    "BR16H": "1036:583:115:70",''', '''    "BR16H": "1036:583:115:70",
    "BRD": "1036:583:115:70",'''),
    ('''    "BR16H": INBOX / "video" / "broll25_720.mp4",''', '''    "BR16H": INBOX / "video" / "broll25_720.mp4",
    "BRD": INBOX / "video" / "broll25_720.mp4",'''),
    ('''    "BR16H": "hqdn3d=3:3:6:6,''', '''    "BRD": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.06:saturation=0.62,colorbalance=rm=-0.03:gm=0.02:bm=-0.07:rh=-0.02:bh=-0.05,unsharp=5:5:0.6",
    "BR16H": "hqdn3d=3:3:6:6,'''),
    # 4. captions: numerals; no "(a)" footnote at the emotional peak (audible wording)
    ('''"thirty-two minutes past the hour."''', '''"32 minutes past the hour."'''),
    ('''"That's one small step for (a) man,"''', '''"That's one small step for man,"'''),
    # 5. 240k: dark gradient behind, bigger ABOUT
    ('''        self.wipe_text(layer, (xl, 720), "ABOUT", "bebas48", AMBER, (u - 0.05) / 0.3, anchor="ls", alpha=a)''',
     '''        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = (np.clip(190 * (1 - np.hypot((xx - 300) / 1100, (yy - 860) / 420)), 0, 190) * a).astype(np.uint8)
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        self.wipe_text(layer, (xl, 716), "ABOUT", "bebas60", AMBER, (u - 0.05) / 0.3, anchor="ls", alpha=a)'''),
    # 6. credits: say the Earthrise / Aldrin moves are parallax from the photographs
    ('''("SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS  ·  MOON + ASCENT: 3D RENDERS FROM NASA DATA", "body34", WHITE),''',
     '''("SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS  ·  MOON + ASCENT: 3D RENDERS FROM NASA DATA", "body34", WHITE),
                 ("EARTHRISE + ALDRIN MOVES: 2.5D PARALLAX BUILT FROM AS11-44-6550 / AS11-40-5903", "body34", WHITE),'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:80]!r}"
    s = s.replace(a, b)
# 7. dynamics: countdown dialogue 4 dB down so the ignition is a real drop
s = line_sub(s, '(RST / "countdown.wav", 12.0,', ", 0.0, 0.0),", ", 0.0, -4.0),")
# 8. bigger-label ascent render if it finished
asc4 = W / "ascent_blender_v4"
if asc4.exists() and len(list(asc4.glob("asc_*.png"))) >= 192:
    s = s.replace('img="ascent_blender_v3/asc_%04d.png"', 'img="ascent_blender_v4/asc_%04d.png"')
P.write_text(s, encoding="utf-8")

# 9. music dynamics: quiet cold open rising into the drop; act 2 down; landing + outro up
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"
t = S.read_text(encoding="utf-8")
m = re.search(r"MUSIC_AUTO = \[.*?\]", t, re.S)
assert m, "MUSIC_AUTO not found"
pts = [tuple(map(float, p)) for p in re.findall(r"\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)", m.group(0))]
new = []
for tt, db in pts:
    if tt <= 10.4:
        db = -10.0 if tt < 1.0 else -6.0          # 0.0 -> -10, 10.4 -> -6
    elif 19.0 < tt <= 32.3:
        db -= 2.0                                  # act 2 plateau 2 dB lower
    elif 48.0 <= tt <= 61.95:
        db += 1.5                                  # Mars into the landing
    elif tt >= 62.9:
        db += 1.5                                  # Largo outro
    new.append((tt, db))
txt = "MUSIC_AUTO = [" + ", ".join(f"({a:g}, {b:g})" for a, b in new) + "]"
t = t[:m.start()] + txt + t[m.end():]
S.write_text(t, encoding="utf-8")
print("v8b applied:", txt)
