"""v7: v5 review fixes (FTV/crowd/A-B). Apply after the v6 chain (and keep or revert v6's title per its A/B)."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = [
    # cold open: shorter static pad, firing room moves on "9"
    ('''    Shot(0.00, 2.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.12), note="Apollo 11 on the pad, 70mm, slow push"),''',
     '''    Shot(0.00, 1.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.10), note="Apollo 11 on the pad, 70mm, push"),
    Shot(1.20, 2.20, "BR", 667.0, push=(1.0, 1.08), note="firing room wide (people moving)"),'''),
    # the drop: fireball, then the wide 70mm so it reads as a launch, not an explosion
    ('''    Shot(10.60, 13.00, "SV", 34.2, push=(1.12, 1.0), note="ignition fireball, high-speed camera"),''',
     '''    Shot(10.60, 11.80, "SV", 34.2, push=(1.12, 1.0), note="ignition fireball, high-speed camera"),
    Shot(11.80, 13.00, "L70", 16.6, crop="1300:731:256:700", push=(1.0, 1.06), note="Apollo 11 70mm: flames at the base, wide"),'''),
    # ascent at 1.6x (26-31), then real staging, then the interstage over Earth as one longer breath
    ('''    Shot(26.00, 34.00, "SEQ", 1.0,''', '''    Shot(26.00, 31.00, "SEQ", 1.0, speed=1.6,'''),
    ('''    Shot(34.00, 37.00, "BR", 961.0, push=(1.0, 1.06), note="interstage falls away over Earth"),''',
     '''    Shot(31.00, 33.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),
    Shot(33.00, 37.00, "BR", 961.0, push=(1.0, 1.08), note="interstage falls away over Earth"),'''),
    # SEQ speed: read the sequence faster and drop frames to 24 fps
    ('''    run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), *start, "-i", str(WORK / "blender" / "..") + "/" + s.img,''',
     '''    run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i", str(WORK / "blender" / "..") + "/" + s.img,'''),
    ('''          f"[0:v]format=rgba,colorkey=black:0.02:0.0[mo];[st][mo]overlay=shortest=1,format=yuv420p")''',
     '''          f"[0:v]fps={FPS},format=rgba,colorkey=black:0.02:0.0[mo];[st][mo]overlay=shortest=1,format=yuv420p")'''),
    # 1202 + bingo in plain English
    ('''        code = "01202" if (int(u * 6) % 3 != 0 or u > 2.0) else "01 2 2"''',
     '''        code = "01202" if (int(u * 6) % 3 != 0 or u > 2.0) else "01 2 2"
        self.text(d, (x0, y1 + 46), "1202 = COMPUTER OVERLOADED", "bebas48", AMBER, "ls", a * min(1.0, max(0.0, (u - 1.0) / 0.4)), track=3)'''),
    ('''"SECONDS TO \'BINGO\' CALL", "bebas34"''', '''"SECONDS TO \'BINGO\' · LAND OR ABORT", "bebas34"'''),
    # 240k: "ABOUT" kicker, short sub-line; render tag smaller, bottom-right black
    ('''"MILES TO THE MOON · ON AVERAGE", "bebas60"''', '''"MILES TO THE MOON", "bebas60"'''),
    ('''        self.wipe_text(layer, (xl, 860), "240,000", "anton150", WHITE, (u - 0.1) / 0.4, anchor="ls", alpha=a)''',
     '''        self.wipe_text(layer, (xl, 720), "ABOUT", "bebas48", AMBER, (u - 0.05) / 0.3, anchor="ls", alpha=a)
        self.wipe_text(layer, (xl, 860), "240,000", "anton150", WHITE, (u - 0.1) / 0.4, anchor="ls", alpha=a)'''),
    ('''            self.text(d, (1808, 1000), "3D RENDER FROM NASA LRO DATA (CGI MOON KIT)", "bebas26", (200, 200, 200), "rs", max(0.0, ar) * 0.8, track=3)''',
     '''            self.text(d, (1808, 1022), "3D RENDER · NASA LRO DATA", "bebas26", (170, 170, 170), "rs", max(0.0, ar) * 0.7, track=3)'''),
    # end card over AS11-44-6642: LM inside safe, title scaled 0.8 between Earth and LM, date under the title
    ('''    Shot(83.40, 85.50, "BLACK", note="end title on black + stars"),''',
     '''    Shot(83.40, 85.50, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.04)), darken=0.35, note="end title: Earth high, LM low (inside safe)"),'''),
    ('''        canvas.alpha_composite(ti, (0, -40))''', '''        ti = ti.resize((int(W * 0.8), int(H * 0.8)), Image.Resampling.LANCZOS)
        canvas.alpha_composite(ti, (int(W * 0.1), int(H * 0.1) - 180))'''),
    ('''        if 83.4 <= t < 85.5:
            st = Image.open''', '''        if False:   # v7: end card is over the photo again (stars only for the old black card)
            st = Image.open'''),
    ('''            self.text(d, (W / 2, 760), "APOLLO 11  ·  JULY 16–24, 1969", "bebas60", WHITE, "mm", a, track=6)''',
     '''            self.text(d, (W / 2, 510), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)'''),
]
# no invented stars on shots made from real photographs (parallax of NASA stills): stars only behind CG renders
R.append(('''    start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []''',
          '''    start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []
    if s.img.startswith("px_"):
        run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i",
             str(WORK / s.img), "-vf", f"fps={FPS},format=yuv420p", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])
        return'''))
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:90]!r}"
    s = s.replace(a, b)
# credits: three big lines, no second "MOONSHOT" logo
c0 = s.index("        lines = [")
c1 = s.index("        y = 330")
s = s[:c0] + '''        lines = [("NASA FOOTAGE, PHOTOGRAPHS AND MISSION AUDIO (PUBLIC DOMAIN)", "body34", WHITE),
                 ("SOME ENGINE-CAMERA SHOTS ARE FROM OTHER SATURN V FLIGHTS", "body34", WHITE),
                 ("MUSIC: DVOŘÁK, HOLST (PUBLIC-DOMAIN RECORDINGS)  ·  SFX: SONNISS", "body34", WHITE),
                 ("", "body34", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body34", AMBER)]
''' + s[c1:]
P.write_text(s, encoding="utf-8")
S = W / "score_pd.py"
t = S.read_text(encoding="utf-8")
a = "(19.5, -2.5), (39.0, -2.5)"
assert t.count(a) == 1
S.write_text(t.replace(a, "(19.5, -4.5), (39.0, -4.5)"), encoding="utf-8")
print(f"v7: {len(R)} patches + credits + act-2 bed -2 dB")
