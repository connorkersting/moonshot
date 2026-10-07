"""v9c: senior-editor fixes on v8. Apply AFTER patch_v9a.py and patch_v9b.py.

    py patch_v9c.py                      # the real build.py + score_pd.py in work/
    py patch_v9c.py BUILD.py SCORE.py    # dry run on copies

Times are REAL (v8 timeline) for SHOTS / DIALOG / MUSIC_AUTO and LOGICAL (v7) for Gfx.draw / CAPTIONS / comp flashes.
1 landing: touchdown in 1398.6 -> 1399.0; the REAL cause of its black first frame is the comp's decode pipe (ffmpeg's
  CFR output re-timed the 1-frame WHITE segment: white dropped, black insert frame duplicated, every later frame one
  frame late), fixed with -fps_mode passthrough; bingo counter freezes at "Contact light" and turns white over the lamp
  insert; LUNAR CONTACT blinks on like an annunciator inside a dark panel; Mission Control reaction held 1.5 s.
2 mid sag: 24,200 MPH counts up; lunar valley 33.3-40.3 +3 dB on the music automation.
3 mix arc: "The Eagle has landed" +2.0 dB, "Contact light" +1.5 dB; act-2 plateau -1.5 dB.
4 title plate: L70 recrop (no utility pole, clear of the film-gate corner); smoke-in-front pass over the title.
5 countdown: big spoken-count numeral bottom-right for phones.
6 small: DSKY flicker blanks; glitch red tint halved; dark plate behind the bingo HUD; "Liftoff on Apollo 11." caption.
"""
import ast
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"

# Mission Control reaction: the editor asked for 1.5 s ("0.65 s + 0.85 s"); the v8 shot is really 17 frames (0.71 s),
# so 1.5 s means a cut at 60.40 (36 frames). NOTE: "The Eagle has landed." is at eagle.wav 3.95-4.95 = real 60.45-61.45,
# so with this cut the WHOLE line plays over the reaction. For "touchdown carries the line, only 'landed' on the
# reaction" use REACT_T0 = 61.05 (reaction 0.85 s).
REACT_T0 = 60.40
# L70 title plate. The editor's crop "1260:709:520:980" removes the pole (source x ~464) but its bottom-right corner
# reaches the 70mm film-gate's rounded corner (dark from y 1634 at x 1780, from y 1674 at x 1760): a black wedge.
# Same top-left, 3% tighter: right edge 1740 (gate dark from y 1702 there), bottom 1666.
L70_CROP = "1220:686:520:980"

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


cw, ch, cx, cy = (int(v) for v in L70_CROP.split(":"))
assert cx + cw <= 1812 and cy + ch <= 1812, L70_CROP
assert abs(cw / ch - 16 / 9) < 0.002, L70_CROP

# ============================================================== build.py
s = load(P)
R = [
    # ---- 1a/1d: touchdown in point + out point; reaction held 1.5 s
    (r'''    Shot(56.26, 61.20, "BR16H", 1398.6, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed, one continuous shot under both lines"),''',
     f'''    Shot(56.26, {REACT_T0:.2f}, "BR16H", 1399.0, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed (v9: in 1399.0, out {61.2 - REACT_T0:.2f} s earlier for the reaction hold)"),'''),
    (r'''    Shot(61.20, 61.90, "BR", 1280.2, push=(1.0, 1.04), note="Mission Control: the reaction, after the line"),''',
     f'''    Shot({REACT_T0:.2f}, 61.90, "BR", 1280.2, push=(1.0, 1.04), note="Mission Control: the reaction, held {61.9 - REACT_T0:.2f} s (v9; source continuous 1280.2-1282.2)"),'''),
    # ---- 1a root cause: decode base.mp4 frame-exact (no CFR re-timing of the 1-frame WHITE segment)
    (r'''    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(WORK / "base.mp4"), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],''',
     r'''    # v9: passthrough. ffmpeg's default CFR output re-timed the 1-frame WHITE segment (v8: white dropped, the black
    # insert frame duplicated, every frame after 56.2 one frame late, frame 1350 black).
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(WORK / "base.mp4"), "-fps_mode", "passthrough",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],'''),
    # ---- 1b/1c/5: draw() windows
    (r'''            self.countdown_hud(d, t)''', r'''            self.countdown_hud(d, t, layer)'''),
    (r'''        if 61.8 <= t < 62.9:''',
     r'''        if 61.79 <= t < 62.9:     # v9: from the insert's first frame (logical 61.792; 61.8 missed it)'''),
    (r'''        if 55.6 <= t < 61.8:''',
     r'''        if 55.6 <= t < 62.9:      # v9: the bingo HUD holds over the CONTACT insert, cut by the white frame'''),
    # ---- 5: big spoken-count numeral
    (r'''    def countdown_hud(self, d, t):''', r'''    def countdown_hud(self, d, t, layer=None):'''),
    (r'''        n = 10
        for ts, k in spoken:
            if t >= ts:
                n = k''',
     r'''        n, n_ts = 10, 0.2
        for ts, k in spoken:
            if t >= ts:
                n, n_ts = k, ts'''),
    (r'''        self.text(d, (x + 20, y + 32), s, "mono34", WHITE, "la", a)
''',
     r'''        self.text(d, (x + 20, y + 32), s, "mono34", WHITE, "la", a)
        if layer is not None:
            self.countdown_numeral(layer, t, n, n_ts)

    def countdown_numeral(self, layer, t, n, ts):
        """v9: the spoken count as a big Anton numeral for phone viewers, bottom-right inside title safe (right edge
        1800, baseline 1012: glyph bottom <= 1016). Pops 1.25 -> 1.0 over 0.15 s on each new count, alpha 0.9.
        Shown 0.2-10.6 only; hidden 2.2-3.9 under the "Ignition sequence starts." caption (re-entry at 3.9 pops)."""
        if not (0.2 <= t < 10.6) or 2.2 <= t < 3.9:
            return
        t0 = 3.9 if ts < 3.9 <= t else ts
        size = int(round(260 * (1.25 - 0.25 * ease_out((t - t0) / 0.15))))
        key = f"anton{size}"
        if key not in self.f:
            self.f[key] = font("anton", size)
        s = str(n)
        d2 = ImageDraw.Draw(layer)
        bb = d2.textbbox((1800, 1012), s, font=self.f[key], anchor="rs")
        pad = 40
        sh = Image.new("L", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), 0)
        ImageDraw.Draw(sh).text((1800 - bb[0] + pad, 1012 - bb[1] + pad), s, font=self.f[key], fill=105, anchor="rs")
        shadow = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(12)))
        layer.alpha_composite(shadow, (bb[0] - pad + 6, bb[1] - pad + 8))
        d2.text((1800, 1012), s, font=self.f[key], fill=WHITE + (int(255 * 0.9),), anchor="rs")
'''),
    # ---- 2a: 24,200 counts up, then holds
    (r'''        ImageDraw.Draw(tmp).text((0, 200), "24,200 MPH", font=self.f["anton200"], fill=WHITE + (int(255 * a),), anchor="ls")''',
     r'''        # v9: the number counts 0 -> 24,200 over the first 1.2 s (ease-out) and holds; right-aligned, so "MPH" stays put
        val = int(round(24200 * ease_out(u / 1.2) / 10.0)) * 10
        td = ImageDraw.Draw(tmp)
        nx = td.textlength("24,200", font=self.f["anton200"])
        td.text((nx, 200), f"{val:,}", font=self.f["anton200"], fill=WHITE + (int(255 * a),), anchor="rs")
        td.text((nx + td.textlength(" ", font=self.f["anton200"]), 200), "MPH", font=self.f["anton200"],
                fill=WHITE + (int(255 * a),), anchor="ls")'''),
    # ---- 1c: annunciator blink + dark panel frame
    (r'''    def contact_insert(self, layer, d, u):
        on = u >= 0.12
        cx, cy = W / 2, H / 2 - 40
''',
     r'''    def contact_insert(self, layer, d, u):
        # v9: an annunciator, not a fade: dark, on at 0.12 s, a quick off/on flicker (0.25-0.33 s), then steady
        on = u >= 0.12 and not (0.25 <= u < 0.33)
        cx, cy = W / 2, H / 2 - 40
        # v9: thin dark panel frame (bezel + four screws) around the lamp so it reads as a cockpit annunciator
        d.rounded_rectangle([cx - 336, cy - 136, cx + 336, cy + 136], radius=16, fill=(20, 22, 26, 255),
                            outline=(62, 64, 70, 255), width=3)
        for sx in (cx - 318, cx + 318):
            for sy in (cy - 118, cy + 118):
                d.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], fill=(80, 82, 88, 255))
'''),
    # ---- 6a: DSKY flicker = full blank
    (r'''        code = "01202" if (int(u * 6) % 3 != 0 or u > 2.0) else "01 2 2"''',
     r'''        code = "01202" if (int(u * 6) % 3 != 0 or u > 2.0) else ""     # v9: flicker blanks (was "01 2 2")'''),
    # ---- 6b: glitch red tint halved
    (r'''    tint = np.array([1.15, 0.85, 0.85]) if rng.random() < 0.5 else np.array([1.0, 1.0, 1.0])''',
     r'''    tint = np.array([1.075, 0.925, 0.925]) if rng.random() < 0.5 else np.array([1.0, 1.0, 1.0])   # v9: half the red'''),
    # ---- 3b: the landing is the loudest dialogue moment
    (r'''    (RST / "pao_land.wav", 48.3, 49.1, 55.2, 0.0),''',
     r'''    (RST / "pao_land.wav", 48.3, 49.1, 55.2, 1.5),       # v9: "Contact light" +1.5 dB'''),
    (r'''    (RST / "eagle.wav", 0.0, 5.3, 56.5, 0.0),''',
     r'''    (RST / "eagle.wav", 0.0, 5.3, 56.5, 2.0),            # v9: "The Eagle has landed" +2.0 dB (loudest line)'''),
    # ---- 6d: the PAO tail "Liftoff on Apollo 11" (countdown.wav src 29.75-30.9 = tl 17.75-18.9) gets its caption
    (r'''    (15.70, 18.95, "LAUNCH CONTROL", "32 minutes past the hour."),''',
     r'''    (15.70, 17.55, "LAUNCH CONTROL", "32 minutes past the hour."),      # v9: speech ends tl 17.4
    (17.70, 18.95, "LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v9: src 29.75-30.9 (tl 17.75-18.9)'''),
    # ---- 4: title plate recrop + smoke-in-front pass
    (r'''    Shot(13.00, 17.60, "L70", 18.0, speed=0.5, crop="1500:844:156:880", push=(1.0, 1.08), darken=0.25, note="smoke under the title"),''',
     f'''    Shot(13.00, 17.60, "L70", 18.0, speed=0.5, crop="{L70_CROP}", push=(1.0, 1.08), darken=0.25, note="smoke under the title (v9: recrop, no pole through the M, clear of the gate corner)"),'''),
    (r'''            fr = np.clip(f0 * (1 - a_) + title_rgb * a_, 0, 255).astype(np.uint8)''',
     r'''            plate0 = fr                                   # v9: the un-titled plate, for the smoke-in-front pass
            fr = np.clip(f0 * (1 - a_) + title_rgb * a_, 0, 255).astype(np.uint8)
            if 13.0 <= tl < 17.25:                        # v9: opening title only (the end card stays clean)
                fr = smoke_front(fr, plate0, a_)'''),
    (r'''

GLITCH_WINDOWS = [''',
     r'''

def smoke_front(comp: np.ndarray, plate: np.ndarray, a_: np.ndarray) -> np.ndarray:
    """v9: 'smoke in front' for the opening title. A soft luma key of the plate's brightest smoke is laid back over
    the bottom ~30% of the letters at 35%, so the title sits IN the exhaust cloud rather than pasted on it.
    comp: titled frame (uint8 HxWx3); plate: the same frame before the title; a_: title alpha (HxWx1, 0..1)."""
    alpha = a_[..., 0]
    rows = np.flatnonzero(alpha.max(axis=1) > 0.05)
    if rows.size == 0:
        return comp
    y0, y1 = int(rows[0]), int(rows[-1])
    yb = y1 - 0.30 * (y1 - y0)                    # top of the bottom-30% band
    ramp = max(0.08 * (y1 - y0), 1.0)              # soft top edge
    band = np.clip((np.arange(H, dtype=np.float32) - yb) / ramp, 0, 1)[:, None]
    pf = plate.astype(np.float32)
    lum = pf @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lo, hi = np.percentile(lum[::4, ::4], [70, 98])
    key = np.clip((lum - lo) / max(hi - lo, 1.0), 0, 1)
    key = key * key * (3 - 2 * key)
    key = np.asarray(Image.fromarray((key * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.Resampling.BILINEAR)
                     .filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.Resampling.BILINEAR), np.float32) / 255.0
    m = (0.35 * key * band * alpha)[..., None]
    smoke = np.asarray(Image.fromarray(plate).filter(ImageFilter.GaussianBlur(2)), np.float32)
    return np.clip(comp.astype(np.float32) * (1 - m) + smoke * m, 0, 255).astype(np.uint8)


GLITCH_WINDOWS = ['''),
]
s = apply(s, R, "build")

# ---- 1b + 6c: Gfx.fuel(): freeze at "Contact light", highlighted hold, dark plate behind the block
FUEL_OLD = r'''    def fuel(self, d, t):
        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors
        anchors = [(55.7, 2.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
        if t <= anchors[0][0]:
            g = anchors[0][1]
        elif t >= anchors[-1][0]:
            g = anchors[-1][1]
        else:
            for (ta, ga), (tb, gb) in zip(anchors, anchors[1:]):
                if ta <= t <= tb:
                    g = ga + (gb - ga) * (t - ta) / (tb - ta)
                    break
        rem = max(0.0, 62.0 - g)   # 60 s called at 102:45:02 -> bingo at 102:46:02
        a = min(1.0, (t - 55.6) / 0.3) * (1 - ease_in_out((t - 61.6) / 0.2))
        x0, y0 = 1320, 120
        col = AMBER if rem > 30.05 else RED
        self.text(d, (x0, y0), "SECONDS TO 'BINGO' · LAND OR ABORT", "bebas34", col, "la", a, track=3)
        self.text(d, (x0, y0 + 40), f"{rem:04.1f}", "anton150", WHITE, "lt", a)
        self.text(d, (x0 + 300, y0 + 160), "SEC", "bebas40", col, "la", a)
        w = 380 * rem / 60.0
        d.rectangle([x0, y0 + 222, x0 + 380, y0 + 232], outline=col + (int(200 * a),), width=2)
        d.rectangle([x0, y0 + 222, x0 + w, y0 + 232], fill=col + (int(230 * a),))
        label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * 0.85)
        self.text(d, (x0, y0 + 296), "TIME-COMPRESSED", "bebas40", (190, 190, 190), "la", a * 0.8, track=3)
'''
FUEL_NEW = r'''    def fuel(self, d, t):
        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors
        anchors = [(55.7, 2.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
        contact = 61.9               # v9: "Contact light" (logical): the counter stops here and holds
        held = t >= contact
        tg = min(t, contact)
        if tg <= anchors[0][0]:
            g = anchors[0][1]
        elif tg >= anchors[-1][0]:
            g = anchors[-1][1]
        else:
            for (ta, ga), (tb, gb) in zip(anchors, anchors[1:]):
                if ta <= tg <= tb:
                    g = ga + (gb - ga) * (tg - ta) / (tb - ta)
                    break
        rem = max(0.0, 62.0 - g)   # 60 s called at 102:45:02 -> bingo at 102:46:02
        a = min(1.0, (t - 55.6) / 0.3)      # v9: no fade-out; held over the lamp insert until the white frame
        x0, y0 = 1320, 120
        # v9: the number counts in the warning colour and the whole block turns white when the counter stops
        col = WHITE if held else (AMBER if rem > 30.05 else RED)
        if t < 61.79:              # v9: dark plate for the white shirts in Mission Control (not over the black insert)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 352], radius=12, fill=(0, 0, 0, int(150 * a)))
        self.text(d, (x0, y0), "SECONDS TO 'BINGO' · LAND OR ABORT", "bebas34", col, "la", a, track=3)
        self.text(d, (x0, y0 + 40), f"{rem:04.1f}", "anton150", col, "lt", a)
        self.text(d, (x0 + 300, y0 + 160), "SEC", "bebas40", col, "la", a)
        w = 380 * rem / 60.0
        d.rectangle([x0, y0 + 222, x0 + 380, y0 + 232], outline=col + (int(200 * a),), width=2)
        d.rectangle([x0, y0 + 222, x0 + w, y0 + 232], fill=col + (int(230 * a),))
        if held:
            label = "CONTACT  ·  102:45:" + f"{int(g):02d}"
        else:
            label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * (1.0 if held else 0.85))
        self.text(d, (x0, y0 + 296), "TIME-COMPRESSED", "bebas40", (190, 190, 190), "la", a * 0.8, track=3)
'''
s = apply(s, [(FUEL_OLD, FUEL_NEW)], "build fuel")
save(P, s)

# ============================================================== score_pd.py
t = load(S)
lines = t.split("\n")
hit = [i for i, ln in enumerate(lines) if ln.startswith("MUSIC_AUTO = [")]
assert len(hit) == 1, hit
ln = lines[hit[0]]
old = ast.literal_eval(ln[ln.index("["): ln.index("]") + 1])
V8 = [(0, -10), (10.4, -6), (10.6, 0), (19, 0), (19.5, -6.5), (32.3, -6.5), (33.3, -5), (40.3, -6), (48.3, 1.5),
      (58.7, 5.5), (61.9, 5.5), (62.9, -0.5), (81.3, 1.5)]
assert old == V8, old


def at(pts: list[tuple[float, float]], x: float) -> float:
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        if xa <= x <= xb:
            return ya + (yb - ya) * (x - xa) / (xb - xa)
    raise ValueError(x)


new = []
for x, y in old:
    if 19.5 <= x <= 32.3:              # 3c: act-2 plateau a further -1.5 dB
        new.append((x, y - 1.5))
    elif x == 33.3:                    # 2b: lunar valley +3 dB; guard at 33.2 (music bus silent 33.12-33.3) keeps
        new.append((33.2, round(at(old, 33.2) - 1.5, 2)))   # the 32.3 -> 33.3 swell on the lowered plateau
        new.append((x, y + 3.0))
    elif x == 40.3:                    # 2b: +3 dB to 40.3; guard at 40.8 rejoins the v8 ramp under the alarm duck
        new.append((x, y + 3.0))
        new.append((40.8, round(at(old, 40.8), 2)))
    else:
        new.append((x, y))
fmt = lambda v: f"{v:g}" if float(v).is_integer() else f"{v}"
body = ", ".join(f"({fmt(x)}, {fmt(y)})" for x, y in new)
lines[hit[0]] = (f"MUSIC_AUTO = [{body}]     # v9: act-2 plateau -1.5 dB; lunar valley 33.3-40.3 +3 dB "
                 f"(guards 33.2 / 40.8); v8: act 2 shorter, later points -6.7")
t = "\n".join(lines)
save(S, t)
print("v9c MUSIC_AUTO =", new)
print(f"v9c: build {len(R) + 1} patches (reaction cut {REACT_T0:.2f}, L70 crop {L70_CROP}); score MUSIC_AUTO rewritten")
