"""v5 structure: flash-forward cold open, 1202 speaker/picture match, Blender ascent 26-34, CG match pass,
step caption "(a)", lunar loudness cliff. Apply after patch_v5.py."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
a0 = s.index("    # COLD OPEN: countdown, a hard cut on every count")
a1 = s.index("    # BEAT DROP")
COLD = '''    # COLD OPEN (v5): Apollo 11 on the pad, first flames, then 1-s flash-forwards on the counts (promise of the story)
    Shot(0.00, 2.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.12), note="Apollo 11 on the pad, 70mm, slow push"),
    Shot(2.20, 3.90, "L70", 15.6, speed=0.5, crop="900:506:400:1187", push=(1.0, 1.08), note="Apollo 11 70mm: first flames at the base (ignition sequence starts)"),
    Shot(3.90, 4.80, "SEQ", 70.0, img="moon_blender/moon_%04d.png", note="flash-forward: the Moon (Blender render, frames 70+)"),
    Shot(4.80, 5.60, "STILL", img="as11-44-6581.jpg", kb=((0.5, 0.5, 1.5), (0.5, 0.5, 1.7)), note="flash-forward: Eagle"),
    Shot(5.60, 6.60, "BR16", 1361.0, push=(1.0, 1.08), note="flash-forward: dust at touchdown"),
    Shot(6.60, 7.40, "STILL", img="as11-40-5903.jpg", kb=((0.51, 0.11, 3.4), (0.51, 0.10, 4.0)), note="flash-forward: the visor"),
    Shot(7.40, 8.40, "STILL", img="as11-44-6550.jpg", kb=((0.5, 0.44, 1.6), (0.5, 0.43, 1.75)), note="flash-forward: Earthrise"),
    Shot(8.40, 9.40, "BR", 694.0, push=(1.06, 1.0), note="back to the firing room"),
    Shot(9.40, 10.60, "BR", 691.78, speed=0.66, push=(1.0, 1.10), note="engine bells (0.8 s shot, slowed)"),
'''
s = s[:a0] + COLD + s[a1:]
R = [
    # Blender ascent replaces chart + staging + downrange shots
    ('''    Shot(26.00, 28.60, "SV", 135.0, push=(1.0, 1.06), darken=0.35, note="rocket arcing up (full-frame chart over it)"),
    Shot(28.60, 31.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),
    Shot(31.00, 34.00, "SV", 141.0, push=(1.0, 1.08), note="rocket arcs downrange (no text: breathe)"),''',
     '''    Shot(26.00, 34.00, "SEQ", 1.0, img="ascent_blender/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values"),'''),
    ('''        if 26.0 <= t < 28.6:
            self.chart(layer, d, t - 26.0)
''', ''),
    # 1202: Eagle's lines over the LM window, Houston's over Mission Control
    ('''    Shot(49.00, 50.20, "BR", 1242.0, push=(1.05, 1.0), note="flight controller close"),
    Shot(50.20, 52.40, "BR", 1260.0, push=(1.0, 1.08), note="descent, LM window"),
    Shot(52.40, 55.00, "BR", 1248.0, push=(1.0, 1.05), note="controller points: we're go"),''',
     '''    Shot(49.00, 50.60, "BR", 1258.5, push=(1.0, 1.08), note="descent, LM window (Eagle: 1202)"),
    Shot(50.60, 52.80, "BR", 1237.0, push=(1.0, 1.05), note="Mission Control hears the question"),
    Shot(52.80, 55.00, "BR", 1248.0, push=(1.0, 1.05), note="controller points: we're go (Houston)"),'''),
    ('''GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (50.2, 50.42, 1.0), (51.6, 51.7, 0.5)]''',
     '''GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (49.0, 49.2, 1.0), (50.6, 50.72, 0.6)]'''),
    # ALSJ convention for the inaudible article
    ('''"That's one small step for man,"''', '''"That's one small step for (a) man,"'''),
    # SEQ: optional start frame (src_in) for flash-forward excerpts
    ('''    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(WORK / "blender" / "..") + "/" + s.img,''',
     '''    start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []
    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), *start, "-i", str(WORK / "blender" / "..") + "/" + s.img,'''),
    # CG match: gate weave + softness on Blender shots (then the same LUT/halation/grain as everything else)
    ('''        tl = title_layer(gfx, t)''', '''        if s.src == "SEQ":
            wr = np.random.default_rng(fi)
            dx, dy = wr.normal(0, 0.9), wr.normal(0, 0.7)
            im_ = Image.fromarray(fr).filter(ImageFilter.GaussianBlur(0.7))
            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, dx, 0, 1, dy), Image.Resampling.BILINEAR))
        tl = title_layer(gfx, t)'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:90]!r}"
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
S = W / "score_pd.py"
t = S.read_text(encoding="utf-8")
a = "(40.0, -9.0), (47.0, -7.0)"
assert t.count(a) == 1
S.write_text(t.replace(a, "(40.0, -5.0), (47.0, -6.0)"), encoding="utf-8")
print(f"v5b: cold open + {len(R)} patches + lunar loudness")
