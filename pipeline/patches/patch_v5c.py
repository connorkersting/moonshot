"""v5 critic fixes (editor v4 + crowd v4) and the Blender Earthrise parallax. Apply after patch_v5b.py."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = [
    # --- shots
    ('''    Shot(23.00, 26.00, "SV", 122.2, push=(1.04, 1.0), note="ice sheets falling past"),''',
     '''    Shot(23.00, 26.00, "SV", 122.2, push=(1.04, 1.0), darken=0.18, note="ice sheets falling past"),'''),
    ('''    Shot(52.80, 55.00, "BR", 1248.0, push=(1.0, 1.05), note="controller points: we're go (Houston)"),''',
     '''    Shot(52.80, 55.00, "BR", 1248.55, speed=0.85, push=(1.0, 1.05), note="controller points: we're go (Houston)"),'''),
    ('''    Shot(65.40, 68.60, "BR16", 1398.0, speed=0.5, push=(1.0, 1.10), note="16mm: touchdown, half speed"),''',
     '''    Shot(65.40, 68.60, "BR16H", 1399.5, speed=0.5, push=(1.0, 1.12), note="16mm: touchdown, half speed, hard grade"),'''),
    ('''    Shot(69.60, 74.00, "STILL", img="as11-44-6550.jpg", kb=((0.5, 0.46, 1.35), (0.5, 0.44, 1.55)), note="Apollo 11 Earthrise"),''',
     '''    Shot(69.60, 74.00, "SEQ", 1.0, img="px_earthrise/px_%04d.png", note="Apollo 11 Earthrise: Blender parallax (3 PIL depth planes), Earth rises"),'''),
    ('''    Shot(83.40, 86.50, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.5, 1.0), (0.5, 0.5, 1.06)), darken=0.45, note="end title: LM low, Earth high"),
    Shot(86.50, 88.50, "BLACK"),''',
     '''    Shot(83.40, 85.50, "BLACK", note="end title on black + stars"),
    Shot(85.50, 88.50, "BLACK", note="credits"),'''),
    ('''    Shot(2.20, 3.90, "L70", 15.6, speed=0.5, crop="900:506:400:1187",''',
     '''    Shot(2.20, 3.90, "L70", 15.6, speed=0.5, crop="900:506:400:1100",'''),
    ('''    "BR16": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.3/0.46 0.65/0.85 1/1',eq=saturation=0.85,unsharp=5:5:0.7",''',
     '''    "BR16": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.3/0.46 0.65/0.85 1/1',eq=saturation=0.85,unsharp=5:5:0.7",
    "BR16H": "hqdn3d=3:3:6:6,curves=all='0/0 0.12/0.02 0.35/0.36 0.62/0.80 1/1',eq=saturation=0.8,unsharp=5:5:1.0",'''),
    ('''    "BR16": "1036:583:115:70",''', '''    "BR16": "1036:583:115:70",
    "BR16H": "1036:583:115:70",'''),
    ('''    "BR16": INBOX / "video" / "broll25_720.mp4",''', '''    "BR16": INBOX / "video" / "broll25_720.mp4",
    "BR16H": INBOX / "video" / "broll25_720.mp4",'''),
    # --- dialogue: stop the countdown clip before the stray "liftoff on Apollo 11"
    ('''    (RST / "countdown.wav", 12.0, 31.1, 0.0, 0.0),''', '''    (RST / "countdown.wav", 12.0, 30.9, 0.0, 0.0),'''),
    # --- graphics
    ('''        out = ease_in_out((u - 2.65) / 0.35)
        x = 120 - out * 900''', '''        out = ease_in_out((u - 2.6) / 0.35)
        x = 120
        if out > 0:          # fade + rise out (v4's slide-off cropped to "LLION")
            layer_alpha = 1 - out
            self.text(d, (x, 360 - out * 30), "LIFTOFF THRUST", "bebas40", AMBER, "ls", layer_alpha)
            self.text(d, (x, 520 - out * 30), "7.5 MILLION", "anton150", WHITE, "ls", layer_alpha)
            self.text(d, (x, 600 - out * 30), "POUNDS  ·  FIVE F-1 ENGINES", "bebas48", WHITE, "ls", layer_alpha * 0.9)
            return'''),
    ('''        rem = 10.6 - t
        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))
        sign = "−" if rem >= 0 else "+"
        v = abs(rem)
        s = f"T {sign} 00:00:{int(v):02d}.{int((v * 10) % 10)}"''',
     '''        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))
        # the readout follows the SPOKEN count (the picture already cuts on the voice)
        spoken = [(0.2, 10), (1.2, 9), (2.2, 8), (3.5, 7), (4.8, 6), (5.6, 5), (6.6, 4), (7.4, 3), (8.4, 2), (9.4, 1), (10.6, 0)]
        n = 10
        for ts, k in spoken:
            if t >= ts:
                n = k
        s = f"T − 00:00:{n:02d}" if t < 10.6 else f"T + 00:00:{int(t - 10.6):02d}"'''),
    ('''"TIME-COMPRESSED  ▸▸"''', '''"TIME-COMPRESSED"'''),
    ('''"LM GUIDANCE COMPUTER", "bebas26"''', '''"LM GUIDANCE COMPUTER", "bebas34"'''),
    ('''                    self.text(d, (W / 2, y - 48), who, "bebas30", AMBER, "ms", a, track=4)''',
     '''                    self.text(d, (W / 2, y - 48), who, "bebas40", AMBER, "ms", a, track=4)'''),
    ('''                tw = max(d.textlength(s, font=f), d.textlength(who, font=self.f["bebas30"]) + 4 * len(who))''',
     '''                tw = max(d.textlength(s, font=f), d.textlength(who, font=self.f["bebas40"]) + 4 * len(who))'''),
    ('''                top = y - (82 if who else 40)''', '''                top = y - (92 if who else 40)'''),
    # --- end card: title from Blender frame 12 (no tiny "sign"), stars behind, date under it, credits 3 s
    ('''    elif 83.4 <= t < 86.5:
        idx = min(int(round((t - 83.4) * FPS)), 60)
        fade = 1 - ease_in_out((t - 86.1) / 0.4)''', '''    elif 83.4 <= t < 85.5:
        idx = min(12 + int(round((t - 83.4) * FPS)), 70)
        fade = min(1.0, (t - 83.4) / 0.15) * (1 - ease_in_out((t - 85.15) / 0.35))'''),
    ('''        if 84.2 <= t < 86.5:
            a = ease_out((t - 84.2) / 0.6) * (1 - ease_in_out((t - 86.1) / 0.4))
            self.text(d, (W / 2, 770), "APOLLO 11  ·  JULY 16–24, 1969", "bebas60", WHITE, "mm", a, track=6)
        if 86.55 <= t < 88.5:
            self.credits(d, t - 86.55)''', '''        if 83.4 <= t < 85.5:
            st = Image.open(WORK / "blender" / "stars.png").convert("RGB").crop((100, 60, 100 + W, 60 + H))
            sa = np.asarray(st, np.uint8)
            stars = np.dstack([sa, (sa.max(axis=2) * 0.8).astype(np.uint8)])
            layer.alpha_composite(Image.fromarray(stars, "RGBA"))
        if 83.9 <= t < 85.5:
            a = ease_out((t - 83.9) / 0.5) * (1 - ease_in_out((t - 85.15) / 0.35))
            self.text(d, (W / 2, 760), "APOLLO 11  ·  JULY 16–24, 1969", "bebas60", WHITE, "mm", a, track=6)
        if 85.55 <= t < 88.5:
            self.credits(d, t - 85.55)'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:90]!r}"
    s = s.replace(a, b)
# speaker tags: consistent "SIDE · NAME" (ALSJ/AFJ attributions)
TAGS = [('(47.20, 48.15, "EAGLE",', '(47.20, 48.15, "EAGLE · ARMSTRONG",'),
        ('(48.30, 49.40, "EAGLE",', '(48.30, 49.40, "EAGLE · ARMSTRONG",'),
        ('(49.50, 50.40, "EAGLE",', '(49.50, 50.40, "EAGLE · ALDRIN",'),
        ('(50.50, 52.75, "EAGLE",', '(50.50, 52.75, "EAGLE · ARMSTRONG",'),
        ('(52.90, 55.55, "HOUSTON",', '(52.90, 55.55, "HOUSTON · DUKE",'),
        ('(55.70, 57.30, "HOUSTON",', '(55.70, 57.30, "HOUSTON · DUKE",'),
        ('(57.50, 60.15, "EAGLE",', '(57.50, 60.15, "EAGLE · ALDRIN",'),
        ('(60.30, 61.75, "HOUSTON",', '(60.30, 61.75, "HOUSTON · DUKE",'),
        ('(61.90, 62.85, "EAGLE",', '(61.90, 62.85, "EAGLE · ALDRIN",'),
        ('(63.25, 65.30, "EAGLE",', '(63.25, 65.30, "EAGLE · ARMSTRONG",'),
        ('(65.45, 68.25, "EAGLE",', '(65.45, 68.25, "EAGLE · ARMSTRONG",'),
        ('(70.40, 72.35, "HOUSTON",', '(70.40, 72.35, "HOUSTON · DUKE",'),
        ('(72.45, 73.85, "HOUSTON",', '(72.45, 73.85, "HOUSTON · DUKE",'),
        ('(74.35, 77.60, "ARMSTRONG",', '(74.35, 77.60, "ARMSTRONG",'),
        ]
for a, b in TAGS:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")

# --- audio: act 2 down 2.5 dB, 1-s ramp into the lunar section; stagger the two SFX at 47.0; 3 ms SFX head fades
S = W / "score_pd.py"
t = S.read_text(encoding="utf-8")
A = [("(10.6, 0.0), (39.9, 0.0), (40.0, -5.0)", "(10.6, 0.0), (19.0, 0.0), (19.5, -2.5), (39.0, -2.5), (40.0, -5.0)"),
     ('"BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_glitch_malfunction_004.wav", 47.0,',
      '"BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_glitch_malfunction_004.wav", 47.083,'),
     ("        f = int(0.03 * SR)\n        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]",
      "        f = int(0.03 * SR)\n        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]\n"
      "        h3 = int(0.004 * SR)\n        x[:h3] *= np.linspace(0, 1, h3, dtype=np.float32)[:, None]   # no click at the head")]
for a, b in A:
    assert t.count(a) == 1, a[:60]
    t = t.replace(a, b)
S.write_text(t, encoding="utf-8")
print(f"v5c: {len(R)} + {len(TAGS)} tags + {len(A)} audio")
