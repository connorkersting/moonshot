"""v7b: v5 senior-editor fixes. Apply right after patch_v7.py."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = [
    # ascent: true-colour v3 render at 2x (4 s), staging 30-33, interstage 33-37
    ('img="ascent_blender_v2/asc_%04d.png"', 'img="ascent_blender_v3/asc_%04d.png"'),
    ('''    Shot(26.00, 31.00, "SEQ", 1.0, speed=1.6,''', '''    Shot(26.00, 30.00, "SEQ", 1.0, speed=2.0,'''),
    ('''    Shot(31.00, 33.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),''',
     '''    Shot(30.00, 33.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),'''),
    # 1202: every EAGLE line over Eagle footage, Houston over Mission Control
    ('''    Shot(50.60, 52.80, "BR", 1237.0, push=(1.0, 1.05), note="Mission Control hears the question"),''',
     '''    Shot(50.60, 52.80, "BR", 1251.0, push=(1.0, 1.06), note="descent, LM window (Eagle asks for a reading)"),'''),
    # bingo run: 16mm for Aldrin's calls, a tense controller for Duke's "30 seconds"
    ('''    Shot(57.40, 59.00, "BR16", 1360.2, push=(1.0, 1.06), note="16mm: dust"),
    Shot(59.00, 60.20, "BR", 1278.0, push=(1.0, 1.05), note="Mission Control faces"),''',
     '''    Shot(57.40, 60.20, "BR16", 1360.2, push=(1.0, 1.08), note="16mm: dust (Aldrin's calls)"),'''),
    ('''    Shot(60.20, 61.80, "BR16", 1383.0, push=(1.0, 1.06), note="16mm: dust and the LM shadow"),''',
     '''    Shot(60.20, 61.80, "BR", 1242.0, push=(1.04, 1.0), note="flight controller, tense (Houston: 30 seconds)"),'''),
    # landing in the right order: both lines over one continuous touchdown, then the reaction
    ('''    Shot(62.96, 65.40, "BR", 1279.0, push=(1.0, 1.05), note="Mission Control, waiting on the call"),
    Shot(65.40, 68.60, "BR16H", 1399.5, speed=0.5, push=(1.0, 1.12), note="16mm: touchdown, half speed, hard grade"),''',
     '''    Shot(62.96, 67.90, "BR16H", 1398.3, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed, one continuous shot under both lines"),
    Shot(67.90, 68.60, "BR", 1280.2, push=(1.0, 1.04), note="Mission Control: the reaction, after the line"),'''),
    # ladder TV: lift it so "one small step" has an image
    ('''    Shot(74.00, 77.60, "BR", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV)"),''',
     '''    Shot(74.00, 77.60, "BR16", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV), lifted"),'''),
    # HUD: no "LAUNCH COMPLEX 39A" over the flash-forwards (keep the count)
    ('''        self.text(d, (x + 20, y - 4), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas34", AMBER, "la", a * 0.95, track=3)''',
     '''        site = 0.0 if 3.9 <= t < 8.4 else 1.0
        self.text(d, (x + 20, y - 4), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas34", AMBER, "la", a * 0.95 * site, track=3)'''),
    ('''"TIME-COMPRESSED", "bebas30"''', '''"TIME-COMPRESSED", "bebas40"'''),
    # render honesty moves to the credits
    ('''            self.text(d, (1808, 1022), "3D RENDER · NASA LRO DATA", "bebas26", (170, 170, 170), "rs", max(0.0, ar) * 0.7, track=3)''', ''''''),
    ('''        lines = [("NASA FOOTAGE, PHOTOGRAPHS AND MISSION AUDIO (PUBLIC DOMAIN)", "body34", WHITE),
                 ("SOME ENGINE-CAMERA SHOTS ARE FROM OTHER SATURN V FLIGHTS", "body34", WHITE),
                 ("MUSIC: DVOŘÁK, HOLST (PUBLIC-DOMAIN RECORDINGS)  ·  SFX: SONNISS", "body34", WHITE),
                 ("", "body34", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body34", AMBER)]''',
     '''        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, HOLST (PD)", "body34", WHITE),
                 ("SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS  ·  MOON + ASCENT: 3D RENDERS FROM NASA DATA", "body34", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body34", AMBER)]'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:90]!r}"
    s = s.replace(a, b)
# ignition line: duck 4 dB deeper (cap 12 -> 16 dB) through the end of "All engines running"
a = "    c0, c1 = int(10.6 * SR), int(11.4 * SR)\n    env_db[c0:c1] = np.minimum(env_db[c0:c1], 12.0)"
assert s.count(a) == 1
s = s.replace(a, "    c0, c1 = int(10.6 * SR), int(11.4 * SR)\n    env_db[c0:c1] = np.minimum(env_db[c0:c1], 16.0)")
P.write_text(s, encoding="utf-8")

S = W / "score_pd.py"
t = S.read_text(encoding="utf-8")
A = [("(55.0, -1.0),\n              (63.0, 2.0), (68.6, 2.0)", "(55.0, 0.0),\n              (65.4, 4.0), (68.6, 4.0)"),       # Mars builds into the climax
     ('(PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 40.0, 0.0, 2.5, 0.015)', '(PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 40.0, 0.0, 2.5, 0.03)'),
     ("        h3 = int(0.004 * SR)", "        h3 = int(0.010 * SR)")]
for a, b in A:
    assert t.count(a) == 1, a[:60]
    t = t.replace(a, b)
S.write_text(t, encoding="utf-8")
print(f"v7b: {len(R)} + ignition duck + {len(A)} audio")
