"""v4 patches (apply AFTER v3's mix has run): merged editor v2 + crowd v2 + audio_qc fixes."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = []
# ---- timeline: 88.5 s total, re-planned 26-47, outro re-timed so lines land on their pictures
R.append(('TOTAL = 90.0', 'TOTAL = 88.5'))
R.append(('''    Shot(0.20, 1.20, "L70", 4.0, crop="1080:608:366:130",''', '''    Shot(0.20, 1.20, "L70", 4.0, crop="980:551:470:150",'''))
R.append(('''    Shot(0.00, 0.20, "BLACK"),
    Shot(0.20, 1.20, "L70"''', '''    Shot(0.00, 0.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.0), note="pad (open on picture, no black)"),
    Shot(0.20, 1.20, "L70"'''))
R.append(('''    Shot(26.00, 31.00, "SV", 135.0, push=(1.0, 1.08), darken=0.45, note="rocket arcing up (data-viz backplate)"),
    Shot(31.00, 34.00, "SV", 141.0, push=(1.0, 1.08), note="rocket arcs downrange (stat 2: speed)"),
    Shot(34.00, 37.00, "BR", 961.0, push=(1.0, 1.06), note="interstage falls away over Earth (no text: let it breathe)"),
    Shot(37.00, 40.00, "BR", 1093.0, push=(1.0, 1.10), note="Earth receding (stat 3: distance)"),''',
          '''    Shot(26.00, 28.60, "SV", 135.0, push=(1.0, 1.06), darken=0.35, note="rocket arcing up (full-frame chart over it)"),
    Shot(28.60, 31.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),
    Shot(31.00, 34.00, "SV", 141.0, push=(1.0, 1.08), note="rocket arcs downrange (no text: breathe)"),
    Shot(34.00, 37.00, "BR", 961.0, push=(1.0, 1.06), note="interstage falls away over Earth"),
    Shot(37.00, 40.00, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.55)), note="Apollo 11 Earth on translunar coast, pulling away (stat: TLI speed)"),'''))
R.append(('''    Shot(55.00, 57.40, "BR16", 1346.0,''', '''    Shot(55.00, 57.40, "BR16", 1345.5,'''))
R.append(('''    Shot(57.40, 59.00, "BR16", 1362.0,''', '''    Shot(57.40, 59.00, "BR16", 1360.2,'''))
R.append(('''    Shot(74.00, 78.50, "BR", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV)"),
    Shot(78.50, 81.00, "STILL", img="as11-40-5903.jpg", kb=((0.51, 0.24, 1.9), (0.51, 0.10, 4.2)), note="Aldrin: push into the visor"),
    Shot(81.00, 83.40, "STILL", img="as11-40-5878.jpg", kb=((0.62, 0.62, 1.3), (0.62, 0.62, 1.55)), note="bootprint"),
    Shot(83.40, 87.50, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.5, 1.0), (0.5, 0.5, 1.08)), darken=0.45, note="end title: LM low, Earth high"),
    Shot(87.50, 90.00, "BLACK"),''',
          '''    Shot(74.00, 77.60, "BR", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV)"),
    Shot(77.60, 79.40, "STILL", img="as11-40-5903.jpg", kb=((0.51, 0.20, 2.2), (0.51, 0.10, 4.2)), note="Aldrin: push into the visor"),
    Shot(79.40, 83.40, "STILL", img="as11-40-5878.jpg", kb=((0.62, 0.62, 1.25), (0.62, 0.62, 1.6)), note="bootprint (one giant leap)"),
    Shot(83.40, 86.50, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.5, 1.0), (0.5, 0.5, 1.06)), darken=0.45, note="end title: LM low, Earth high"),
    Shot(86.50, 88.50, "BLACK"),'''))
# ---- 16mm levels: curves lift (measured mean luma 60-82 pre-LUT vs 31-45)
R.append(('''    "BR16": "hqdn3d=3:3:6:6,eq=contrast=1.24:brightness=-0.025:saturation=0.85:gamma=1.04,unsharp=5:5:0.7",''',
          '''    "BR16": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.3/0.46 0.65/0.85 1/1',eq=saturation=0.85,unsharp=5:5:0.7",'''))
# ---- graphics schedule
R.append(('''        if 26.0 <= t < 31.0:
            self.chart(layer, d, t - 26.0)
        if 31.0 <= t < 34.0:
            self.stat_speed(layer, d, t - 31.0)''', '''        if 26.0 <= t < 28.6:
            self.chart(layer, d, t - 26.0)'''))
R.append(('''        if 37.0 <= t < 40.0:
            self.stat_distance(layer, d, t - 37.0)''', '''        if 37.0 <= t < 40.0:
            self.stat_speed(layer, d, t - 37.0)
        if 40.0 <= t < 44.0:
            self.stat_distance(layer, d, t - 40.0)'''))
R.append(('''        if 0.2 <= t < 13.0 or 40.2 <= t < 43.9:''', '''        if 0.0 <= t < 13.0 or 44.0 <= t < 47.0:'''))
R.append(('''        if 40.2 <= t < 43.9:
            self.chapter(d, t - 40.2)''', '''        if 44.0 <= t < 47.0:
            self.chapter(d, t - 44.0)
        if 69.8 <= t < 73.6:
            self.label(d, t - 69.8, "EARTHRISE", "PHOTOGRAPHED FROM APOLLO 11 · JULY 1969")'''))
R.append(('''        if 84.4 <= t < 87.5:
            a = ease_out((t - 84.4) / 0.8) * (1 - ease_in_out((t - 87.1) / 0.4))
            self.text(d, (W / 2, 640), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)
        if 87.6 <= t < 90.0:
            self.credits(d, t - 87.6)''', '''        if 84.2 <= t < 86.5:
            a = ease_out((t - 84.2) / 0.6) * (1 - ease_in_out((t - 86.1) / 0.4))
            self.text(d, (W / 2, 770), "APOLLO 11  ·  JULY 16–24, 1969", "bebas60", WHITE, "mm", a, track=6)
        if 86.55 <= t < 88.5:
            self.credits(d, t - 86.55)'''))
# ---- HUD / chapter / DSKY / fuel: bigger sub-labels, x=110, DSKY top-left
R.append(('''        x, y = 96, 72
        d.rectangle([x, y, x + 6, y + 44], fill=AMBER + (int(230 * a),))
        self.text(d, (x + 20, y - 2), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas26", AMBER, "la", a * 0.9, track=3)
        self.text(d, (x + 20, y + 22), s, "mono22", WHITE, "la", a)''', '''        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 64], fill=AMBER + (int(230 * a),))
        self.text(d, (x + 20, y - 4), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas34", AMBER, "la", a * 0.95, track=3)
        self.text(d, (x + 20, y + 32), s, "mono34", WHITE, "la", a)'''))
R.append(('''        a = min(1.0, (t - 0.2) / 0.3) * (1 - ease_in_out((t - 12.4) / 0.6))''', '''        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))'''))
R.append(('''        x, y = 96, 72
        d.rectangle([x, y, x + 6, y + 70], fill=CYAN + (int(220 * a),))
        self.text(d, (x + 22, y - 4), "DAY 5  ·  JULY 20, 1969", "bebas48", WHITE, "la", a, track=4)
        self.text(d, (x + 22, y + 46), "LUNAR MODULE EAGLE  ·  POWERED DESCENT", "bebas26", CYAN, "la", a * 0.9, track=3)''',
          '''        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 84], fill=CYAN + (int(220 * a),))
        self.text(d, (x + 22, y - 4), "DAY 5  ·  JULY 20, 1969", "bebas48", WHITE, "la", a, track=4)
        self.text(d, (x + 22, y + 48), "LUNAR MODULE EAGLE  ·  POWERED DESCENT", "bebas34", CYAN, "la", a * 0.95, track=3)

    def label(self, d, u, head, sub):
        a = ease_out(u / 0.5) * (1 - ease_in_out((u - 3.3) / 0.5))
        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 84], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 22, y - 4), head, "bebas48", WHITE, "la", a, track=6)
        self.text(d, (x + 22, y + 48), sub, "bebas34", (200, 210, 220), "la", a * 0.95, track=3)'''))
R.append(('''        x0, y0, x1, y1 = 1280, 110, 1714, 400''', '''        x0, y0, x1, y1 = 112, 70, 560, 370'''))
R.append(('''        self.text(d, (x0 + 316, y0 + 62), "V05 N09", "mono22", GREEN, "la", a * 0.9)''',
          '''        self.text(d, (x0 + 310, y0 + 60), "V05 N09", "mono34", GREEN, "la", a * 0.9)'''))
# ---- bingo counter: one near-constant rate, exactly 30.0 on the "30 seconds" call, tag the compression
R.append(('''        anchors = [(55.7, 2.0), (57.3, 2.0), (60.3, 32.0), (61.75, 32.0), (61.9, 40.0), (62.5, 44.0)]''',
          '''        anchors = [(55.7, 2.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]'''))
R.append(('''        label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * 0.85)''',
          '''        label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * 0.85)
        self.text(d, (x0, y0 + 296), "TIME-COMPRESSED  ▸▸", "bebas30", (190, 190, 190), "la", a * 0.8, track=3)'''))
# ---- glitch: first burst 4 frames; nothing on the controller's face (49.0-50.2)
R.append(('''GLITCH_WINDOWS = [(47.0, 47.55, 1.0), (48.25, 48.4, 0.6), (49.45, 49.6, 0.7), (49.6, 49.95, 1.0), (50.15, 50.35, 0.8), (51.6, 51.7, 0.5)]''',
          '''GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (50.2, 50.42, 1.0), (51.6, 51.7, 0.5)]'''))
# ---- flashes: 2 full-white frames then a fast decay; Earthrise fade 0.6 s; end at TOTAL
R.append(('''        if 68.6 <= t < 69.1:
            k = (t - 68.6) / 0.5
            f = f * 0 + 255 * (1 - k) ** 2''', '''        if 68.6 <= t < 68.95:
            k = max(0.0, (t - 68.68) / 0.27)
            f = f * 0 + 255 * (1 - k) ** 2'''))
R.append(('''        if 69.6 <= t < 70.8:
            f *= ease_in_out((t - 69.6) / 1.2)''', '''        if 69.6 <= t < 70.2:
            f *= ease_in_out((t - 69.6) / 0.6)'''))
R.append(('''        if 89.4 <= t:
            f *= max(0.0, 1 - (t - 89.4) / 0.6)''', '''        if TOTAL - 0.5 <= t:
            f *= max(0.0, 1 - (t - (TOTAL - 0.5)) / 0.5)'''))
# ---- end card: title not raised (it covered the Earth); credits bigger
R.append(('''        canvas.alpha_composite(ti, (0, -150))''', '''        canvas.alpha_composite(ti, (0, -40))'''))
R.append(('''    elif 83.4 <= t < 87.5:
        idx = min(int(round((t - 83.4) * FPS)), 92)
        fade = 1 - ease_in_out((t - 87.0) / 0.5)''', '''    elif 83.4 <= t < 86.5:
        idx = min(int(round((t - 83.4) * FPS)), 60)
        fade = 1 - ease_in_out((t - 86.1) / 0.4)'''))
R.append(('''        y = 380
        for s, f, c in lines:
            if s:
                self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += 100 if f == "anton96" else 52''', '''        y = 330
        for s, f, c in lines:
            if s:
                self.text(d, (W / 2, y), s, "anton96" if f == "anton96" else "body34", c, "mm", a)
            y += 110 if f == "anton96" else 62'''))
R.append(('''            "body44": font("body", 44), "body26": font("body", 26), "body22": font("body", 22),''',
          '''            "body44": font("body", 44), "body26": font("body", 26), "body22": font("body", 22), "body34": font("body", 34),
            "body30": font("body", 30),'''))
# ---- captions re-timed to the new outro cuts (step line unchanged, bootprint now from 79.4)
for a_, b_ in R:
    n = s.count(a_)
    assert n == 1, f"{n} matches for: {a_[:90]!r}"
    s = s.replace(a_, b_)

# ---- chart: full-frame, no panel/grid, 2.6 s, >= 26 px labels, no leading zero
a0 = s.index("    def chart(self, layer, d, u):")
a1 = s.index("    def credits(self, d, u):")
CHART = '''    def chart(self, layer, d, u):
        a = min(1.0, u / 0.25) * (1 - ease_in_out((u - 2.3) / 0.3))
        X0, Y0, X1, Y1 = 230, 200, 1250, 860
        tmax, amax = 180.0, 50.0
        def px(tt, alt):
            return X0 + (X1 - X0) * tt / tmax, Y1 - (Y1 - Y0) * alt / amax
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = (np.clip(150 * (1 - xx / 1500), 0, 150) * a).astype(np.uint8)
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        self.text(d, (X0, Y0 - 70), "ASCENT  ·  FIRST 3 MINUTES", "bebas48", WHITE, "la", a, track=4)
        for v in (10, 20, 30, 40):
            _, yv = px(0, v)
            self.text(d, (X0 - 18, yv), f"{v} mi", "body30", WHITE, "rm", a * 0.85)
            d.line([(X0, yv), (X0 + 14, yv)], fill=(255, 255, 255, int(160 * a)), width=2)
        for v in (0, 60, 120, 180):
            xv, _ = px(v, 0)
            self.text(d, (xv, Y1 + 18), f"T+{v}s", "body30", WHITE, "mt", a * 0.85)
        d.line([(X0, Y1), (X1, Y1)], fill=(255, 255, 255, int(150 * a)), width=2)
        p = ease_in_out((u - 0.15) / 1.85)
        tt = 40.0 + (tmax - 40.0) * p
        pts = [px(x, pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], x)) for x in np.linspace(0, tt, 160)]
        glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).line(pts, fill=AMBER + (int(170 * a),), width=16, joint="curve")
        layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
        d.line(pts, fill=(255, 214, 140, int(255 * a)), width=6, joint="curve")
        hx, hy = pts[-1]
        d.ellipse([hx - 10, hy - 10, hx + 10, hy + 10], fill=WHITE + (int(255 * a),))
        for (ct, cv) in PAO_PTS:
            if tt >= ct:
                cx, cy = px(ct, cv)
                d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=CYAN + (int(255 * a),), width=3)
        for (et, name) in [(83, "MAX Q"), (135, "INBOARD ENGINES OFF")]:
            if tt >= et:
                ex, ey = px(et, pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], et))
                d.line([(ex, ey - 16), (ex, ey - 70)], fill=CYAN + (int(200 * a),), width=2)
                self.text(d, (ex, ey - 78), name, "bebas34", CYAN, "ms", a, track=2)
        alt = pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], tt)
        vel = pchip([q[0] for q in PAO_VEL], [q[1] for q in PAO_VEL], tt) * 0.681818
        rx = 1360
        for i, (lab, val, unit) in enumerate([("MISSION TIME", f"T+{tt:.0f}", "S"), ("ALTITUDE", f"{alt:.1f}", "MI"),
                                               ("VELOCITY", f"{vel:,.0f}", "MPH")]):
            yy0 = 240 + i * 200
            self.text(d, (rx, yy0), lab, "bebas40", AMBER, "la", a, track=3)
            vw = self.text(d, (rx, yy0 + 40), val, "anton96", WHITE, "lt", a)
            self.text(d, (rx + vw + 14, yy0 + 132), unit, "bebas40", AMBER, "ls", a)
        self.text(d, (X0, Y1 + 72), "DATA: NASA LAUNCH COMMENTARY  ·  ○ = VALUE CALLED OUT LIVE", "body30", WHITE, "la", a * 0.85)

'''
s = s[:a0] + CHART + s[a1:]
P.write_text(s, encoding="utf-8")


# ---- distance stat now over the Blender Moon (40-44): lower-left clear zone, no leader line, out by 43.0
b = P.read_text(encoding="utf-8")
d0 = b.index("    def stat_distance(self, layer, d, u):")
d1 = b.index("    def contact_insert(self, layer, d, u):")
b = b[:d0] + '''    def stat_distance(self, layer, d, u):
        a = 1 - ease_in_out((u - 2.6) / 0.4)
        xl = 112
        self.wipe_text(layer, (xl, 860), "240,000", "anton150", WHITE, (u - 0.1) / 0.4, anchor="ls", alpha=a)
        self.wipe_text(layer, (xl, 932), "MILES TO THE MOON", "bebas60", AMBER, (u - 0.25) / 0.4, anchor="ls", alpha=a)

''' + b[d1:]
P.write_text(b, encoding="utf-8")

# ---- score + SFX: total 88.5, Largo trimmed, 15 ms fade on the 68.6 cut, descent bed +2 dB
S = W / "score_pd.py"
t = S.read_text(encoding="utf-8")
for a_, b_ in [('TOTAL = 90.0', 'TOTAL = 88.5'),
               ('(PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 40.0, 0.0, 2.5, 0.006)', '(PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 40.0, 0.0, 2.5, 0.015)'),
               ('(PD / "dvorak9_ii_largo.ogg", 5.2, 25.4, 69.6, 0.0, 1.4, 1.2)', '(PD / "dvorak9_ii_largo.ogg", 5.2, 24.0, 69.6, 0.0, 1.4, 1.6)'),
               ('(55.0, -3.0),\n              (63.0, 0.0), (68.6, 0.0), (69.6, -2.0), (89.0, 0.0)]', '(55.0, -1.0),\n              (63.0, 2.0), (68.6, 2.0), (69.6, -2.0), (88.0, 0.0)]')]:
    assert t.count(a_) == 1, a_[:60]
    t = t.replace(a_, b_)
S.write_text(t, encoding="utf-8")
print(f"v4: {len(R)} patches + chart rewrite + score_pd")
