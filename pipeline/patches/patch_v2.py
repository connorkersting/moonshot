"""v2 code patches for build.py (graphics, compositor, shot types). Each replacement must match exactly once."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = (CRAFTWORK / "inbox/moonshot/work/build.py")
s = P.read_text(encoding="utf-8")

R = []
# --- shot types: BR16 (levels pass on 16mm), INSERT (graphic on black), WHITE
R.append(('''GRADE = {
    "SV": "eq=saturation=0.88:contrast=1.04",''', '''GRADE = {
    "BR16": "hqdn3d=3:3:6:6,eq=contrast=1.38:brightness=-0.07:saturation=0.85:gamma=0.92,unsharp=5:5:0.7",
    "SV": "eq=saturation=0.88:contrast=1.04",'''))
R.append(('''    "BR": "1036:583:115:70",
}''', '''    "BR": "1036:583:115:70",
    "BR16": "1036:583:115:70",
}'''))
R.append(('''    "BR": INBOX / "video" / "broll25_720.mp4",
}''', '''    "BR": INBOX / "video" / "broll25_720.mp4",
    "BR16": INBOX / "video" / "broll25_720.mp4",
}'''))
R.append(('''        if s.src == "BLACK":
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=black:s={W}x{H}:r={FPS}",''',
          '''        if s.src in ("BLACK", "INSERT", "WHITE"):
            col = "white" if s.src == "WHITE" else "black"
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={col}:s={W}x{H}:r={FPS}",'''))
R.append(('''        if s.src not in ("STILL", "BLACK"):''', '''        if s.src not in ("STILL", "BLACK", "INSERT", "WHITE"):'''))
# --- title: v2 render, graded with the plate (composited before LUT), drop shadow, faded exit, cut at 17.25
R.append(('''        self.title = sorted((WORK / "title3d").glob("title_*.png"))''',
          '''        self.title = sorted((WORK / "title3d_v2").glob("title_*.png"))'''))
R.append(('''        fr = lut[fr, [0, 1, 2]] if False else np.stack([lut[fr[..., c], c] for c in range(3)], -1)
        f = fr.astype(np.float32)''', '''        tl = title_layer(gfx, t)
        if tl is not None:
            f0 = fr.astype(np.float32)
            ta = np.asarray(tl, np.float32)
            a_ = ta[..., 3:4] / 255.0
            sh = np.asarray(tl.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(10)).resize((W, H)), np.float32)[..., None] / 255.0
            sh = np.roll(np.roll(sh, 18, axis=0), 10, axis=1)
            f0 = f0 * (1 - 0.55 * sh)
            fr = np.clip(f0 * (1 - a_) + ta[..., :3] * a_, 0, 255).astype(np.uint8)
        fr = np.stack([lut[fr[..., c], c] for c in range(3)], -1)
        f = fr.astype(np.float32)'''))
R.append(('''        if 13.0 <= t < 17.6:
            idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)
            layer.alpha_composite(Image.open(gfx.title[idx]).convert("RGBA"))
        if 83.4 <= t < 87.5:
            idx = min(int(round((t - 83.4) * FPS)), 92)
            ti = Image.open(gfx.title[idx]).convert("RGBA")
            if t > 87.0:
                ti.putalpha(Image.fromarray((np.asarray(ti.getchannel("A")) * max(0.0, 1 - (t - 87.0) / 0.5)).astype(np.uint8)))
            layer.alpha_composite(ti)
''', ''''''))
R.append(('''GLITCH_WINDOWS = [''', '''def title_layer(gfx: "Gfx", t: float) -> Image.Image | None:
    """3D title frame for time t (graded with the plate by the caller), or None."""
    if 13.0 <= t < 17.25:
        idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)
        fade = 1 - ease_in_out((t - 16.92) / 0.33)
    elif 83.4 <= t < 87.5:
        idx = min(int(round((t - 83.4) * FPS)), 92)
        fade = 1 - ease_in_out((t - 87.0) / 0.5)
    else:
        return None
    ti = Image.open(gfx.title[idx]).convert("RGBA")
    if t >= 83.4:   # end card: title sits higher, clear of the LM
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        canvas.alpha_composite(ti, (0, -150))
        ti = canvas
    if fade < 1:
        ti.putalpha(Image.fromarray((np.asarray(ti.getchannel("A")) * max(0.0, fade)).astype(np.uint8)))
    return ti


GLITCH_WINDOWS = ['''))
# --- end-card subtitle above the LM, under the raised title
R.append(('''            self.text(d, (W / 2, 790), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)''',
          '''            self.text(d, (W / 2, 640), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)'''))
# --- graphics schedule: chart 26-31, speed 31-34, distance 37-40, contact insert, top gradient
R.append(('''        if 0.2 <= t < 13.0:
            self.countdown_hud(d, t)''', '''        if 0.2 <= t < 13.0 or 40.2 <= t < 43.9:
            top = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
            ImageDraw.Draw(top)
            g = np.zeros((240, W, 4), np.uint8)
            g[..., 3] = (np.linspace(120, 0, 240)[:, None] * np.ones((1, W))).astype(np.uint8)
            layer.alpha_composite(Image.fromarray(g, "RGBA"))
        if 0.2 <= t < 13.0:
            self.countdown_hud(d, t)
        if 61.8 <= t < 62.9:
            self.contact_insert(layer, d, t - 61.8)'''))
R.append(('''        if 26.0 <= t < 34.0:
            self.chart(layer, d, t - 26.0)
        if 34.0 <= t < 37.0:
            self.stat_speed(layer, d, t - 34.0)''', '''        if 26.0 <= t < 31.0:
            self.chart(layer, d, t - 26.0)
        if 31.0 <= t < 34.0:
            self.stat_speed(layer, d, t - 31.0)'''))
# --- stat speed: bottom-left on a dark gradient plate instead of over the white plume
R.append(('''    def stat_speed(self, layer, d, u):
        sc = 1.0 + 0.35 * (1 - ease_out(u / 0.25))
        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.7) / 0.3))
        tmp = Image.new("RGBA", (1400, 260), (0, 0, 0, 0))
        td = ImageDraw.Draw(tmp)
        td.text((700, 130), "24,200 MPH", font=self.f["anton200"], fill=WHITE + (int(255 * a),), anchor="mm")
        if sc != 1.0:
            tmp = tmp.resize((int(1400 * sc), int(260 * sc)), Image.Resampling.BICUBIC)
            if u < 0.2:
                tmp = tmp.filter(ImageFilter.BoxBlur(int(8 * (1 - u / 0.2)) + 1))
        layer.alpha_composite(tmp, (int(W / 2 - tmp.width / 2), int(560 - tmp.height / 2)))
        self.text(d, (W / 2, 410), "TRANSLUNAR INJECTION · ESCAPE SPEED", "bebas40", AMBER, "mm", a * ease_out((u - 0.2) / 0.4), track=4)''',
          '''    def stat_speed(self, layer, d, u):
        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.7) / 0.3))
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = np.clip(200 * (1 - np.hypot((xx - 200) / 1300, (yy - 900) / 650)), 0, 200).astype(np.uint8) * a
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        sc = 1.0 + 0.30 * (1 - ease_out(u / 0.25))
        tmp = Image.new("RGBA", (1300, 260), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((0, 200), "24,200 MPH", font=self.f["anton200"], fill=WHITE + (int(255 * a),), anchor="ls")
        if sc != 1.0:
            tmp = tmp.resize((int(1300 * sc), int(260 * sc)), Image.Resampling.BICUBIC)
            if u < 0.2:
                tmp = tmp.filter(ImageFilter.BoxBlur(int(8 * (1 - u / 0.2)) + 1))
        layer.alpha_composite(tmp, (120, int(930 - 200 * sc)))
        self.text(d, (124, 700), "TOP SPEED · TRANSLUNAR INJECTION", "bebas40", AMBER, "ls", a * ease_out((u - 0.2) / 0.4), track=4)'''))
# --- distance: inside title safe, leader ends on Earth's limb (Earth ~x 1560? measured on plate below)
R.append(('''        xr = 1800''', '''        xr = 1712'''))
R.append(('''        p = ease_out((u - 0.35) / 0.7)
        if p > 0:
            x0, y0 = xr - 640, 500
            x1 = x0 - p * 280''', '''        p = ease_out((u - 0.35) / 0.7)
        if p > 0:
            x0, y0 = xr - 600, 500
            x1 = x0 - p * (x0 - EARTH_LIMB_X)'''))
# --- DSKY + fuel inside title safe, counter holds on the radio calls
R.append(('''        x0, y0, x1, y1 = 1390, 110, 1824, 400''', '''        x0, y0, x1, y1 = 1280, 110, 1714, 400'''))
R.append(('''        anchors = [(55.7, 2.0), (57.5, 17.0), (60.3, 31.0), (61.9, 40.0), (62.5, 44.0)]''',
          '''        anchors = [(55.7, 2.0), (57.3, 2.0), (60.3, 32.0), (61.75, 32.0), (61.9, 40.0), (62.5, 44.0)]'''))
R.append(('''        x0, y0 = 1440, 120
        col = AMBER if rem > 30 else RED''', '''        x0, y0 = 1320, 120
        col = AMBER if rem > 30.05 else RED'''))
R.append(('''        self.text(d, (x0, y0 + 250), label, "mono22", WHITE, "la", a * 0.85)''',
          '''        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * 0.85)'''))
# --- chart: 5 s, race from T+40 so the curve moves at once; units right after values; bigger source line
R.append(('''        a = min(1.0, u / 0.4) * (1 - ease_in_out((u - 7.6) / 0.4))''', '''        a = min(1.0, u / 0.3) * (1 - ease_in_out((u - 4.65) / 0.35))'''))
R.append(('''        p = ease_in_out((u - 0.5) / 6.4)
        tt = tmax * p''', '''        p = ease_in_out((u - 0.25) / 3.6)
        tt = 40.0 + (tmax - 40.0) * p'''))
R.append(('''            self.text(d, (rx, yy + 38), val, "anton96", WHITE, "lt", a)
            self.text(d, (rx + 360, yy + 100), unit, "bebas40", AMBER, "la", a)''',
          '''            vw = self.text(d, (rx, yy + 38), val, "anton96", WHITE, "lt", a)
            self.text(d, (rx + vw + 14, yy + 130), unit, "bebas40", AMBER, "ls", a)'''))
R.append(('''        self.text(d, (X0 - 100, Y1 + 108), "DATA: APOLLO 11 LAUNCH COMMENTARY (NASA PAO) · ○ = VALUE CALLED OUT LIVE", "body22", WHITE, "la", a * 0.75)''',
          '''        self.text(d, (X0 - 100, Y1 + 104), "DATA: APOLLO 11 LAUNCH COMMENTARY (NASA PAO)  ·  ○ = VALUE CALLED OUT LIVE", "body26", WHITE, "la", a * 0.85)'''))
# --- captions: speaker tag inside the box
R.append(('''                tw = d.textlength(s, font=f)
                y = 978
                pad = 18
                d.rounded_rectangle([W / 2 - tw / 2 - pad, y - 34, W / 2 + tw / 2 + pad, y + 26], radius=8,
                                    fill=(0, 0, 0, int(150 * a)))
                d.text((W / 2, y), s, font=f, fill=WHITE + (int(255 * a),), anchor="ms")
                if who:
                    self.text(d, (W / 2, y - 52), who, "bebas30", AMBER, "ms", a, track=4)''',
          '''                tw = max(d.textlength(s, font=f), d.textlength(who, font=self.f["bebas30"]) + 4 * len(who))
                y = 984
                pad = 22
                top = y - (82 if who else 40)
                d.rounded_rectangle([W / 2 - tw / 2 - pad, top, W / 2 + tw / 2 + pad, y + 22], radius=8,
                                    fill=(0, 0, 0, int(165 * a)))
                d.text((W / 2, y), s, font=f, fill=WHITE + (int(255 * a),), anchor="ms")
                if who:
                    self.text(d, (W / 2, y - 48), who, "bebas30", AMBER, "ms", a, track=4)'''))
# --- credits: title face, disclaimer last
R.append(('''        lines = [("MOONSHOT", "bebas60", WHITE), ("", "body26", WHITE),
                 ("FOOTAGE, PHOTOGRAPHS AND MISSION AUDIO: NASA (PUBLIC DOMAIN)", "body26", WHITE),
                 ("ORIGINAL SCORE AND SOUND DESIGN · NARRATION VOICE: KOKORO TTS", "body26", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body26", AMBER)]
        y = 400
        for s, f, c in lines:
            if s:
                self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += 70 if f == "bebas60" else 52''',
          '''        lines = [("MOONSHOT", "anton96", WHITE), ("", "body26", WHITE),
                 ("FOOTAGE, PHOTOGRAPHS AND MISSION AUDIO: NASA (PUBLIC DOMAIN)", "body26", WHITE),
                 ("MUSIC: DVOŘÁK, SYMPHONY NO. 9 (IV, II) · HOLST, \\"MARS\\" (U.S. AIR FORCE BAND) · PUBLIC DOMAIN RECORDINGS", "body26", WHITE),
                 ("SOUND EFFECTS: SONNISS GDC 2024 BUNDLE", "body26", WHITE),
                 ("", "body26", WHITE),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body26", WHITE)]
        y = 380
        for s, f, c in lines:
            if s:
                self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += 100 if f == "anton96" else 52'''))
# --- chapter tag stays (narration cut)
for a_, b_ in R:
    n = s.count(a_)
    assert n == 1, f"{n} matches for: {a_[:80]!r}"
    s = s.replace(a_, b_)
# new graphic: contact-light lamp insert (Apollo LM 'LUNAR CONTACT' lamps were blue)
s = s.replace('''    def chapter(self, d, u):''', '''    def contact_insert(self, layer, d, u):
        on = u >= 0.12
        cx, cy = W / 2, H / 2 - 40
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        if on:
            gd.rounded_rectangle([cx - 330, cy - 120, cx + 330, cy + 120], radius=14, fill=(70, 150, 255, 200))
            layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        d.rounded_rectangle([cx - 300, cy - 100, cx + 300, cy + 100], radius=10,
                            fill=(120, 190, 255, 255) if on else (26, 32, 44, 255), outline=(90, 90, 90, 255), width=4)
        self.text(d, (cx, cy - 22), "LUNAR", "bebas60", (10, 20, 40) if on else (70, 80, 95), "mm", 1.0, track=10)
        self.text(d, (cx, cy + 40), "CONTACT", "bebas60", (10, 20, 40) if on else (70, 80, 95), "mm", 1.0, track=10)

    def chapter(self, d, u):''', 1)
s = s.replace('''PAO_ALT = [''', '''EARTH_LIMB_X = 1010   # Earth's right limb on the 37-40 s plate after the push (checked on a QC frame)
PAO_ALT = [''', 1)
P.write_text(s, encoding="utf-8")
print(f"applied {len(R)} patches + contact insert")
