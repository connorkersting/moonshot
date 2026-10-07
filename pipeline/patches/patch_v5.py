"""v5 patches: fact-check corrections (apply after v4's chain)."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = [
    # Apollo 11 sources in the cold open (the MSFC "Ultimate Saturn V" compilation is not all Apollo 11)
    ('''    Shot(2.20, 3.90, "SV", 33.0, speed=0.5, push=(1.0, 1.10), black_lead=1, note="first flame under the engines (ignition sequence start)"),''',
     '''    Shot(2.20, 3.90, "L70", 15.6, speed=0.5, crop="900:506:400:1187", push=(1.0, 1.08), black_lead=1, note="Apollo 11 70mm: first flames at the base (ignition sequence starts)"),'''),
    ('''    Shot(5.60, 6.60, "SV", 18.9, push=(1.0, 1.06), black_lead=1, note="vapour off the pad"),''',
     '''    Shot(5.60, 6.60, "BR", 760.0, push=(1.0, 1.06), black_lead=1, note="swing arm pulls away in vapour"),'''),
    # captions (ALSJ / KSC transcript wording)
    ('''    (2.20, 3.90, "LAUNCH CONTROL", "Ignition sequence start."),''', '''    (2.20, 3.90, "LAUNCH CONTROL", "Ignition sequence starts."),'''),
    ('''"Roger. We got... We're go on that alarm."''', '''"Roger. We got you... We're go on that alarm."'''),
    # TLI label; distance "on average"
    ('''"TOP SPEED · TRANSLUNAR INJECTION"''', '''"SPEED AT TRANSLUNAR INJECTION CUTOFF"'''),
    ('''"MILES TO THE MOON", "bebas60"''', '''"MILES TO THE MOON · ON AVERAGE", "bebas60"'''),
    # bingo HUD label
    ('''"TIME TO BINGO FUEL", "bebas34"''', '''"SECONDS TO \'BINGO\' CALL", "bebas34"'''),
    # PAO data re-timed (Mach 1 at T+66.3 = the "4 mi, 2,195 ft/s" call; 30 nmi ~T+148), nautical miles
    ('''PAO_ALT = [(0, 0.0), (30, 0.6), (56, 2.0), (78, 4.0), (106, 12.0), (140, 30.0), (180, 43.0)]''',
     '''PAO_ALT = [(0, 0.0), (30, 0.6), (56, 2.0), (66, 4.0), (106, 12.0), (148, 30.0), (180, 43.0)]   # nautical miles'''),
    ('''PAO_PTS = [(56, 2.0), (78, 4.0), (106, 12.0), (140, 30.0), (180, 43.0)]''',
     '''PAO_PTS = [(56, 2.0), (66, 4.0), (106, 12.0), (148, 30.0), (180, 43.0)]'''),
    ('''PAO_VEL = [(0, 0.0), (78, 2195.0), (106, 4000.0), (180, 9300.0)]''',
     '''PAO_VEL = [(0, 0.0), (66, 2195.0), (106, 4000.0), (180, 9300.0)]'''),
    ('''            self.text(d, (X0 - 18, yv), f"{v} mi", "body30", WHITE, "rm", a * 0.85)''',
     '''            self.text(d, (X0 - 18, yv), f"{v} nmi", "body30", WHITE, "rm", a * 0.85)'''),
    ('''("ALTITUDE", f"{alt:.1f}", "MI")''', '''("ALTITUDE", f"{alt:.1f}", "NMI")'''),
    # render honesty tag on the Moon approach
    ('''        if 40.0 <= t < 44.0:
            self.stat_distance(layer, d, t - 40.0)''', '''        if 40.0 <= t < 44.0:
            self.stat_distance(layer, d, t - 40.0)
            ar = min(1.0, (t - 40.2) / 0.4) * (1 - ease_in_out((t - 43.4) / 0.4))
            self.text(d, (1808, 1000), "3D RENDER FROM NASA LRO DATA (CGI MOON KIT)", "bebas26", (200, 200, 200), "rs", max(0.0, ar) * 0.8, track=3)'''),
    # credits: footage provenance note
    ('''                 ("SOUND EFFECTS: SONNISS GDC 2024 BUNDLE", "body26", WHITE),''',
     '''                 ("SOUND EFFECTS: SONNISS GDC 2024 BUNDLE", "body26", WHITE),
                 ("SOME SATURN V ENGINE-CAMERA SHOTS ARE FROM OTHER SATURN V FLIGHTS (MSFC COMPILATION)", "body26", WHITE),'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:90]!r}"
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
print(f"v5: {len(R)} fact-check patches")
