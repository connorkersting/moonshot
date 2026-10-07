"""v10: senior-editor polish on v9. Apply to the v9 source (build.py + score_pd.py at commit "v9 source").

    py patch_v10.py                      # the real build.py + score_pd.py in work/
    py patch_v10.py BUILD.py SCORE.py    # dry run on copies

Times are REAL (v8 timeline) for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS /
comp flashes (tl = t before frame 799; captions at >= 40 are real + 6.7). Everything before 33.3 has tl == t.
1 drop rebuild: the "zero, all engines running" entry and its caption are gone; "liftoff! we have a liftoff, 32 minutes
  past the hour" moves 13.0 -> 11.2 (same source span, now runs to 17.35) and its three captions move -1.8 s.
2 loudness arc: countdown entry -4 -> -9 dB; the stage-separation impact (Bluezone boom, 28.0) -7 -> -12 dB; plus the
  MUSIC_AUTO change in IGN_AUTO (see below) if the emulation needed it.
3 count numeral: also shown 2.2-3.9 (the "8"; it clears the bottom-centre caption), gone from tl 10.45 (no "1" on the
  fireball).
4 "40 feet, down 2 1/2. Picking up some dust." (pao_land 25.5-28.3) +2.0 dB.
5 "Houston, Tranquility Base here." split at the measured pause: real 56.7-58.5 / 58.9-60.15 -> tl 63.40-65.20 /
  65.60-66.85.
6 credits: three lines, the disclaimer ~20% larger (body41 vs body34), inside title safe x 96-1824.
7 24,200 MPH counts from u 0.4 (the Earth is still sliding in) and still lands at u 1.6.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"

LIFT_T = 11.2            # new timeline time of countdown.wav src 25.0 (v9: 13.0)
LIFT_D = LIFT_T - 13.0   # -1.8 s for its captions (all < 40, so logical == real)
# Change 2 follow-up, decided from the in-memory mix emulation (see the v10 report). None = MUSIC_AUTO untouched.
IGN_AUTO = None

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build/score are CRLF)."""
    EOL[path] = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    return path.read_text(encoding="utf-8")


def save(path: Path, text: str) -> None:
    path.write_text(text.replace("\n", EOL[path]), encoding="utf-8", newline="")


def apply(text: str, pairs: list[tuple[str, str]], what: str) -> str:
    for a, b in pairs:
        n = text.count(a)
        assert n == 1, f"{what}: {n} matches for {a[:90]!r}"
        text = text.replace(a, b)
    return text


def cap(t0: float, t1: float) -> str:
    return f"({t0 + LIFT_D:.2f}, {t1 + LIFT_D:.2f}, "


CREDITS = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, HOLST (PD)", "body34"),
           ("3D RENDERS + PARALLAX BUILT FROM NASA DATA  ·  SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS", "body34"),
           ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body41")]
try:   # title-safe check on the real font (centred at x 960: half width <= 864)
    from PIL import ImageFont
    for txt, fk in CREDITS:
        f = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(fk[4:]))
        assert f.getlength(txt) <= 2 * (960 - 96), (txt, f.getlength(txt))
except ImportError:
    print("v10: PIL missing, credits width not checked")

# ============================================================== build.py
s = load(P)
R = [
    # ---- 1: drop rebuild (DIALOG)
    ('''    (RST / "countdown.wav", 22.5, 24.6, 10.5, -2.0),    # "zero, all engines running"
''', ''),
    ('''    (RST / "countdown.wav", 25.0, 31.15, 13.0, -2.0),    # "liftoff! we have a liftoff, 32 minutes past the hour"''',
     f'''    (RST / "countdown.wav", 25.0, 31.15, {LIFT_T:.1f}, -0.5),    # "liftoff! we have a liftoff, 32 minutes past the hour" (v10: was 13.0 @ -2.0; "zero, all engines running" cut; +1.5 dB: duck is maxed under the title hits)'''),
    # ---- 2: quieter cold open
    ('''    (RST / "countdown.wav", 12.0, 22.5, 0.0, -4.0),     # "10 ... ignition sequence starts ... 1"''',
     '''    (RST / "countdown.wav", 12.0, 22.5, 0.0, -9.0),     # "10 ... ignition sequence starts ... 1" (v10: -5 dB, the drop hits harder)'''),
    # ---- 4: Aldrin's dust line
    ('''    (RST / "pao_land.wav", 25.5, 28.3, 50.8, 0.0),''',
     '''    (RST / "pao_land.wav", 25.5, 28.3, 50.8, 2.0),       # v10: "40 feet, down 2 1/2. Picking up some dust." +2.0 dB'''),
    # ---- 1: captions (no caption between 10.4 and 11.2)
    ('''    (10.60, 12.45, "LAUNCH CONTROL", "All engines running."),
''', ''),
    ('''    (13.20, 15.60, "LAUNCH CONTROL", "Liftoff! We have a liftoff,"),''',
     f'''    {cap(13.20, 15.60)}"LAUNCH CONTROL", "Liftoff! We have a liftoff,"),      # v10: -1.8 s with the line'''),
    ('''    (15.70, 17.55, "LAUNCH CONTROL", "32 minutes past the hour."),      # v9: speech ends tl 17.4''',
     f'''    {cap(15.70, 17.55)}"LAUNCH CONTROL", "32 minutes past the hour."),      # v10: -1.8 s (speech ends tl 15.6)'''),
    ('''    (17.70, 18.95, "LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v9: src 29.75-30.9 (tl 17.75-18.9)''',
     f'''    {cap(17.70, 18.95)}"LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v10: src 29.75-30.9 (tl 15.95-17.1)'''),
    # ---- 5: split at the measured pause (real 56.7-58.5 "Houston, uh" / 58.9-60.15; logical = real + 6.7)
    ('''    (63.40, 66.90, "EAGLE · ARMSTRONG", "Houston, Tranquility Base here."),''',
     '''    (63.40, 65.20, "EAGLE · ARMSTRONG", "Houston, ..."),                 # v10: real 56.7-58.5 ("Houston, uh")
    (65.60, 66.85, "EAGLE · ARMSTRONG", "Tranquility Base here."),       # v10: real 58.9-60.15'''),
    # ---- 3: count numeral 0.2-10.45, no hole under the ignition caption
    ('''        Shown 0.2-10.6 only; hidden 2.2-3.9 under the "Ignition sequence starts." caption (re-entry at 3.9 pops)."""
        if not (0.2 <= t < 10.6) or 2.2 <= t < 3.9:
            return
        t0 = 3.9 if ts < 3.9 <= t else ts
''',
     '''        v10: shown 0.2-10.45: also 2.2-3.9 (the "8"; it clears the bottom-centre "Ignition sequence starts." caption)
        and gone 0.15 s before the 10.6 fireball, so no "1" or "0" sits on it."""
        if not (0.2 <= t < 10.45):
            return
        t0 = ts
'''),
    # ---- 7: 24,200 counts from u 0.4 to u 1.6
    ('''        # v9: the number counts 0 -> 24,200 over the first 1.2 s (ease-out) and holds; right-aligned, so "MPH" stays put
        val = int(round(24200 * ease_out(u / 1.2) / 10.0)) * 10''',
     '''        # v10: holds 0 while the Earth slides in, counts 0 -> 24,200 over u 0.4-1.6 (ease-out), then holds;
        # right-aligned, so "MPH" stays put
        val = int(round(24200 * ease_out((u - 0.4) / 1.2) / 10.0)) * 10'''),
    # ---- 6: credits
    ('''            "body30": font("body", 30),''',
     '''            "body30": font("body", 30), "body41": font("body", 41),'''),
    ('''        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, HOLST (PD)", "body34", WHITE),
                 ("SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS  ·  MOON + ASCENT: 3D RENDERS FROM NASA DATA", "body34", WHITE),
                 ("EARTHRISE + ALDRIN MOVES: 2.5D PARALLAX BUILT FROM AS11-44-6550 / AS11-40-5903", "body34", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body34", AMBER)]
        y = 330
        for s, f, c in lines:
            if s:
                self.text(d, (W / 2, y), s, "anton96" if f == "anton96" else "body34", c, "mm", a)
            y += 110 if f == "anton96" else 62
''',
     f'''        # v10: three lines; the disclaimer ~20% larger (body41 vs body34); all inside title safe x 96-1824
        lines = [("{CREDITS[0][0]}", "{CREDITS[0][1]}", WHITE, 62),
                 ("{CREDITS[1][0]}", "{CREDITS[1][1]}", WHITE, 70),
                 ("{CREDITS[2][0]}", "{CREDITS[2][1]}", AMBER, 0)]
        y = 330
        for s, f, c, step in lines:
            self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += step
'''),
]
s = apply(s, R, "build")
save(P, s)

# ============================================================== score_pd.py
t = load(S)
RS = [
    ('''    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -7.0, "attack", 4.0),''',
     '''    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -12.0, "attack", 4.0),   # v10: -5 dB (stage separation)'''),
]
if IGN_AUTO is not None:
    RS.append(IGN_AUTO)
t = apply(t, RS, "score")
save(S, t)
print(f"v10: build {len(R)} patches (liftoff @ {LIFT_T}, captions {LIFT_D:+.1f} s); score {len(RS)} patches"
      f"{' incl. MUSIC_AUTO' if IGN_AUTO is not None else ''}")
