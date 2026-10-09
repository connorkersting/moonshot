"""v18: title redesign, staging white-out, ascent labels, HUD provenance, credits timing, hook label.
Apply to the v17 source (build.py + score_pd.py, tag v17-src):

    py patch_v18.py                      # the real build.py + score_pd.py in work/
    py patch_v18.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS / title_layer (tl = t
below frame 799, (fi + 161) / 24 from it; logical = real + 6.7 after 33.3).
TIMELINE: TOTAL 87.0 -> 87.5 (2088 -> 2100 frames; only the credits BLACK shot grows, 78.8-87.5). SHOTS 42 -> 43: s17 is
split at 28.0 (frame 672), so every later shot index moves up by one (s18-s41 -> s19-s42; segments unchanged in content
except the credits black). The 799/161 map is unchanged.
 1  TITLE (critics on v17: "massive dated 3D title eclipses the liftoff", "chrome bevel reads early-2000s", "2009 AE
    preset"): TITLE_DIR title3d_v18 (blender/title_v18.py + blender/title_post_v18.py): matte brushed metal (roughness
    0.50-0.64 streaked, specular 0.2, 0.06 extrude, 0.006 bevel), warm emission on grazing faces strongest at the letters'
    feet (engine fire), a fire light from below, the bloom pass, f/2 depth of field, slow push. It sits in the open sky
    right of the tower (ink x ~960-1812 = 44% of the width, y ~330-500 after a 190 px rise over the first 1.3 s; the rocket
    and tower are x 400-860) and fades in over 0.4 s (no fly-in). The drop shadow under the title 0.55 -> 0.20. End card:
    its own 56-frame render (end_####.png, centred, 52% width, slow push, fire glow at a third), composited full frame
    (v17 reused opening frames 12-62 scaled to 80% and shifted up 180 px).
 2  STAGING WHITE-OUT (lost 3 blind A/B rounds): s17 split at 28.0: 27.25-28.00 src 987.20 at 1.0x (the lit interstage
    ring, 18 frames, before the white plateau 988.0-988.9) and 28.00-29.80 src 989.20 at 1.18x (the ring breaking away
    from the flash, tumbling over Earth; out at src 991.31 as v17). The 28.0 impact lands on the cut to the separating
    ring; no white plateau (v17: 0.52 s of white-out peaking on 28.0). "And ignition." (DIALOG 28.20, caption 28.30-29.15)
    unchanged.
 3  ASCENT LABELS: s15 reads ascent_blender_v5 (blender/ascent3d_v5.py: MAX Q / INBOARD ENGINE CUTOFF right-aligned over
    their rings, fade in, fade out before they reach the bottom 12% of the frame); the v16b asc_label_clean() hack and its
    call are removed.
 4  PROVENANCE: (a) Gfx.text() no longer draws zero-alpha text and blends partly transparent text (alpha_composite);
    the HUD / hook bars are blended (rect_blend); countdown_hud() draws nothing while its alpha is 0. In
    v17 the gated (alpha 0) HUD text and bar REPLACED the top gradient's pixels (PIL draws RGBA without blending), so the
    HUD showed as a knocked-out ghost over every non-L70 shot 0.2-13.0, legible over the SV fireball 10.6-11.8. Now nothing
    is drawn over 3.9-11.8 (the L70 gate). (b) Tag "ARCHIVE: OTHER SATURN V FLIGHT" lower-left (bebas34 on a soft plate,
    x 112, baseline 1004) over the staging film 26.5-29.79 (cut frame 715), clear of the bottom-centre captions.
 5  CREDITS: card 1 = three lines (logical 85.55-89.0 = real 78.85-82.3, 3.45 s); card 2 unchanged text, logical 89.0-93.45
    (real 82.3-86.75, 4.45 s); black to 87.5. Audio: unchanged tables; the Largo fade still ends at 86.3, so 86.3-87.5 is
    true silence (card 2 fades out inside it).
 6  (frame 115 black at 4.79: not reproducible in v17: frames 113-116 YMAX >= 40, mean 91/31; no change.)
 7  HOOK: "APOLLO 11 / JULY 16, 1969" in the HUD's style and slot, top-left, 0.15 s to the 1.2 s cut (frame 29), where the
    L70 countdown HUD ("APOLLO 11 · LAUNCH COMPLEX 39A / T - 9") takes the same slot.
Re-render: py build.py shots 18 (all: indices from 15 on changed or moved; or 15, 17, 18 + rename s18..s41 -> s19..s42 and
render 42), dialog 18 (unchanged), music 18 (TOTAL), comp 18, mix 18.
QC tools that assume 87.0 / 2088 frames / 42 shots need the new TOTAL (they are TOTAL-aware) and the credits windows.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"

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


def cut_block(text: str, start: str, end: str, what: str) -> str:
    """Remove text from `start` (inclusive) to `end` (exclusive); both markers must occur exactly once, in order."""
    assert text.count(start) == 1 and text.count(end) == 1, f"{what}: markers {text.count(start)} / {text.count(end)}"
    i, j = text.index(start), text.index(end)
    assert i < j, what
    return text[:i] + text[j:]


# ============================================================== build.py
s = load(P)
assert "def credits2(" in s and "RESTORE_WINDOWS" in s, "apply patch_v17 first (tag v17-src)"
assert "def archive_tag(" not in s and 'TITLE_DIR = "title3d_v18"' not in s, "v18 already applied"
for d_ in ("title3d_v18", "ascent_blender_v5"):
    assert (W / d_).is_dir(), f"render {d_} first (blender/title_v18.py + title_post_v18.py, blender/ascent3d_v5.py)"
R = [
    # ---- timeline: the credits black grows by 0.5 s
    ('''TOTAL = 87.0            # v17: credits 4.5 s + a 3.0 s second card + 0.7 s silence (v8-v16: 81.8; v7: 88.5)''',
     '''TOTAL = 87.5            # v18: card 1 3.45 s + card 2 4.45 s + 0.75 s black (v17: 87.0; v8-v16: 81.8; v7: 88.5)'''),
    ('''    Shot(78.80, 87.00, "BLACK", note="credits; v17: card 1 78.85-83.35, card 2 83.35-86.35, black + silence to 87.0"),''',
     '''    Shot(78.80, 87.50, "BLACK", note="credits; v18: card 1 78.85-82.3, card 2 82.3-86.75, black to 87.5 (silence from 86.3)"),'''),
    # ---- 2: staging, split at the 28.0 impact so no white plateau is on screen
    ('''    Shot(27.25, 29.80, "BRD", 987.40, speed=(988.55 - 987.40) / 0.75, push=(1.0, 1.10), note="v16b: src 987.40 at 1.533x''',
     '''    # v18 (staging white-out lost 3 blind A/B rounds): split at the 28.0 impact (frame 672). The lit ring before the white
    # plateau (src 988.0-988.9, luma 169-178), then the ring breaking away from the flash; v17 kept 0.52 s of white-out on 28.0
    Shot(27.25, 28.00, "BRD", 987.20, push=(1.0, 1.04), note="v18: S-II interstage ring lit by the ignition glow, src 987.20-987.95 at 1.0x (18 frames, before the white-out)"),
    Shot(28.00, 29.80, "BRD", 989.20, speed=1.18, push=(1.0, 1.08), note="v18: cut on the 28.0 impact to the ring separating from the flash, src 989.20-991.31 at 1.18x, tumbles away over Earth"),
    # v17 s17 (replaced):
    # Shot(27.25, 29.80, "BRD", 987.40, speed=(988.55 - 987.40) / 0.75, push=(1.0, 1.10), note="v16b: src 987.40 at 1.533x'''),
    # ---- 3: ascent re-render with the labels inside the frame
    ('''    Shot(22.00, 26.50, "SEQ", 1.0, speed=1.77, img="ascent_blender_v4/asc_%04d.png",''',
     '''    # v18: ascent_blender_v5 (blender/ascent3d_v5.py): event labels fade before the frame edge (v4 + asc_label_clean)
    Shot(22.00, 26.50, "SEQ", 1.0, speed=1.77, img="ascent_blender_v5/asc_%04d.png",'''),
    ('''        if s.src == "SEQ" and s.img.startswith("ascent_") and t >= 25.55:    # v16b: the baked label, gone by 25.8
            fr = asc_label_clean(fr, ease_in_out((t - 25.55) / 0.25))
''', ''),
    # ---- 1: title
    ('''TITLE_DIR = "title3d_blender"   # steel; v6 plate-lit title lost its blind A/B   # v3: Blender steel title (v2 used "title3d_v2", EffectCraft)''',
     '''TITLE_DIR = "title3d_v18"   # v18: matte brushed metal, fire-lit edges, bloom (blender/title_v18.py); v3-v17 "title3d_blender" (steel)
TITLE_SHADOW = 0.20         # v18: drop shadow under the title (v3-v17 0.55)'''),
    ('''        self.title = sorted((WORK / TITLE_DIR).glob("title_*.png"))''',
     '''        # v18: opening frames open_####.png (104), end card end_####.png (56, own framing)
        self.title = sorted((WORK / TITLE_DIR).glob("open_*.png"))
        self.title_end = sorted((WORK / TITLE_DIR).glob("end_*.png"))'''),
    ('''    if 13.0 <= t < 17.25:
        idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)
        fade = 1 - ease_in_out((t - 16.92) / 0.33)
    elif 83.4 <= t < 85.5:
        idx = min(12 + int(round((t - 83.4) * FPS)), 70)
        fade = min(1.0, (t - 83.4) / 0.15) * (1 - ease_in_out((t - 85.15) / 0.35))
    else:
        return None
    ti = Image.open(gfx.title[idx]).convert("RGBA")
    if t >= 83.4:   # end card: title sits higher, clear of the LM
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ti = ti.resize((int(W * 0.8), int(H * 0.8)), Image.Resampling.LANCZOS)
        canvas.alpha_composite(ti, (int(W * 0.1), int(H * 0.1) - 180))
        ti = canvas
''',
     '''    if 13.0 <= t < 17.25:
        # v18: frames 0-102 of the v18 render; fades in over 0.4 s while it rises (v17 flew in from deep space)
        idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)
        fade = ease_in_out((t - 13.0) / 0.4) * (1 - ease_in_out((t - 16.92) / 0.33))
    elif 83.4 <= t < 85.5:
        # v18: its own render, framed for the end card (v17: opening frames 12-62 scaled to 80%, shifted up 180 px)
        idx = min(int(round((t - 83.4) * FPS)), len(gfx.title_end) - 1)
        fade = min(1.0, (t - 83.4) / 0.15) * (1 - ease_in_out((t - 85.15) / 0.35))
        ti = Image.open(gfx.title_end[idx]).convert("RGBA")
        # v18: the comp darkens this shot by 35% (darken=0.35) AFTER the title is laid in; lift the matte title's RGB so
        # it is not muddy on the grey surface (dry-run preview)
        ta_ = np.asarray(ti, np.float32)
        ta_[..., :3] = np.clip(ta_[..., :3] * 1.35, 0, 255)
        ti = Image.fromarray(ta_.astype(np.uint8), "RGBA")
    else:
        return None
    if t < 83.4:
        ti = Image.open(gfx.title[idx]).convert("RGBA")
'''),
    ('''            f0 = f0 * (1 - 0.55 * sh)''', '''            f0 = f0 * (1 - TITLE_SHADOW * sh)       # v18: 0.20 (v17 0.55)'''),
    # ---- 4a: zero-alpha text / HUD no longer knocks holes in the layer
    ('''    def text(self, d: ImageDraw.ImageDraw, xy, s, f, fill, anchor="la", alpha=1.0, track=0):
        col = fill + (int(255 * alpha),)
        if track:
            x, y = xy
            total = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for c in s:
                d.text((x, y), c, font=self.f[f], fill=col, anchor="l" + anchor[1])
                x += d.textlength(c, font=self.f[f]) + track
            return total
        d.text(xy, s, font=self.f[f], fill=col, anchor=anchor)
        return d.textlength(s, font=self.f[f])''',
     '''    def text(self, d: ImageDraw.ImageDraw, xy, s, f, fill, anchor="la", alpha=1.0, track=0):
        col = fill + (int(255 * alpha),)
        # v18: ImageDraw REPLACES RGBA pixels (no blending): zero-alpha text used to punch its glyphs out of whatever was
        # already on the layer (the v17 countdown HUD showed as a knocked-out ghost in the top gradient). Not drawn now.
        ink = col[3] > 0
        # v18: partly transparent text is blended (drawn opaque on a scratch layer, alpha scaled, alpha_composite), so a
        # fading HUD / label no longer lowers the alpha of the gradient or plate already under it
        im_ = getattr(d, "_image", None)
        if ink and col[3] < 255 and im_ is not None and im_.mode == "RGBA":
            tmp = Image.new("RGBA", im_.size, (0, 0, 0, 0))
            w_ = self.text(ImageDraw.Draw(tmp), xy, s, f, fill, anchor, 1.0, track)
            tmp.putalpha(tmp.getchannel("A").point(lambda v: v * col[3] // 255))
            im_.alpha_composite(tmp)
            return w_
        if track:
            x, y = xy
            total = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for c in s:
                if ink:
                    d.text((x, y), c, font=self.f[f], fill=col, anchor="l" + anchor[1])
                x += d.textlength(c, font=self.f[f]) + track
            return total
        if ink:
            d.text(xy, s, font=self.f[f], fill=col, anchor=anchor)
        return d.textlength(s, font=self.f[f])'''),
    ('''        s = f"T − 00:00:{n:02d}" if t < 10.6 else f"T + 00:00:{int(t - 10.6):02d}"
        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 64], fill=AMBER + (int(230 * a),))''',
     '''        s = f"T − 00:00:{n:02d}" if t < 10.6 else f"T + 00:00:{int(t - 10.6):02d}"
        x, y = 112, 70
        if int(230 * a) <= 0:      # v18: gated off (non-L70 shot): draw nothing (v17 knocked the bar + text out of the gradient)
            if layer is not None:
                self.countdown_numeral(layer, t, n, n_ts)
            return
        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))     # v18: blended (was d.rectangle)'''),
    # ---- 4b + 7: archive tag over the staging film; hook label before the first L70 shot
    ('''        if 26.5 <= t < 27.25:    # v8: staging shot (before ACT2_T0, logical time == real time); v15: 0.75 s''',
     '''        if 0.15 <= t < HOOK_OUT:  # v18: what this is, before the L70 HUD takes the slot at the 1.2 cut
            self.hook(d, t)
        if 26.5 <= t < ARCHIVE_OUT:   # v18 provenance: the staging film is from other Saturn V flights
            self.archive_tag(d, t)
        if 26.5 <= t < 27.25:    # v8: staging shot (before ACT2_T0, logical time == real time); v15: 0.75 s'''),
    ('''    def countdown_numeral(self, layer, t, n, ts):''',
     '''    def hook(self, d, t):
        """v18: top-left in the countdown HUD's slot and style (bar, bebas34 amber header, mono34 white line) over the
        firing-room shot 0.15 s -> the 1.2 s cut (frame 29), where the L70 HUD ("APOLLO 11 · LAUNCH COMPLEX 39A") eases in
        on the same slot. In 0.3 s, cut out with the shot."""
        a = ease_out((t - 0.15) / 0.3)
        x, y = 112, 70
        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))
        self.text(d, (x + 20, y - 4), "APOLLO 11", "bebas34", AMBER, "la", a * 0.95, track=3)
        self.text(d, (x + 20, y + 32), "JULY 16, 1969", "mono34", WHITE, "la", a)

    def rect_blend(self, d, box, rgba):
        """v18: a filled rectangle alpha-composited onto the layer (d.rectangle replaces the pixels under it)."""
        im_ = d._image
        tmp = Image.new("RGBA", (int(box[2] - box[0]) + 1, int(box[3] - box[1]) + 1), rgba)
        im_.alpha_composite(tmp, (int(box[0]), int(box[1])))

    def archive_tag(self, d, t):
        """v18 provenance: small lower-left tag over the staging film (26.5 -> the 29.8 cut, frame 715): bebas34 light grey
        on a soft dark plate, baseline 1004 at x 112 (title safe; the captions are bottom-centre, x >= ~800)."""
        a = ease_out((t - 26.5) / 0.2) * (1 - ease_in_out((t - (ARCHIVE_OUT - 0.2)) / 0.2))
        if a <= 0:
            return
        s_, f = "ARCHIVE: OTHER SATURN V FLIGHT", "bebas34"
        tw = sum(d.textlength(c, font=self.f[f]) + 3 for c in s_) - 3
        d.rounded_rectangle([100, 966, 124 + tw, 1014], radius=6, fill=(0, 0, 0, int(120 * a)))
        self.text(d, (112, 1004), s_, f, (215, 215, 210), "ls", a * 0.9, track=3)

    def countdown_numeral(self, layer, t, n, ts):'''),
    ('''DSKY_RIGHT_T = 50.62''',
     '''HOOK_OUT = round(1.2 * FPS) / FPS          # v18: the first L70 frame (29): the countdown HUD takes the slot
ARCHIVE_OUT = round(29.8 * FPS) / FPS      # v18: the cut to the Apollo 11 Earth still (frame 715)
DSKY_RIGHT_T = 50.62'''),
    # ---- 5: credits: card 1 three lines 3.45 s, card 2 4.45 s
    ('''        if 85.55 <= t < 90.05:   # v17: 4.5 s (was 2.95 s to the end of the film), real 78.85-83.35
            self.credits(d, t - 85.55)
        if 90.05 <= t < 93.05:   # v17: second card 3.0 s, real 83.35-86.35; black + silence after it to 87.0
            self.credits2(d, t - 90.05)''',
     '''        if 85.55 <= t < CARD2_T:   # v18: 3.45 s, real 78.85-82.3 (v17 4.5 s)
            self.credits(d, t - 85.55)
        if CARD2_T <= t < CARD2_T + 4.5:   # v18: 4.45 s, real 82.3-86.75 (v17 3.0 s); black after it to 87.5
            self.credits2(d, t - CARD2_T)'''),
    ('''        a = ease_out(u / 0.4) * (1 - ease_in_out((u - 4.1) / 0.35))     # v17: 4.5 s, out by 90.0 for the second card''',
     '''        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 3.1) / 0.35))     # v18: out by 89.0 (real 82.3) for card 2'''),
    ('''        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, BEETHOVEN (PD)", "body34", WHITE, 58),
                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA", "body34", WHITE, 58),
                 ("SATURN V LAUNCH AND STAGING SHOTS INCLUDE ENGINEERING FILM FROM OTHER FLIGHTS", "body34", WHITE, 58),
                 # v16b: NASA media guidelines (nasa.gov/nasa-brand-center/images-and-media, 2026-10-07): mark AI-made
                 # products, imply no NASA review or permission; four lines, block centre kept at v15's y 396
                 ("CUT BY AN AI AGENT LOOP (CLAUDE CODE) FROM NASA SOURCE MATERIAL", "body34", WHITE, 66),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]''',
     '''        # v18: three lines (Connor: card 1 reduced to 3 short lines, ~3.5 s): sources + music; how it was made (AI loop,
        # 3D from NASA data, other-flight film: the staging shots also carry an on-screen ARCHIVE tag); NASA disclaimer
        # (v16b: NASA media guidelines: mark AI-made products, imply no NASA review or permission)
        lines = [("NASA FILM, PHOTOS & MISSION AUDIO  ·  MUSIC: DVOŘÁK, BEETHOVEN  ·  ALL PUBLIC DOMAIN", "body34", WHITE, 62),
                 ("CUT BY AN AI AGENT (CLAUDE CODE)  ·  3D FROM NASA DATA  ·  SOME LAUNCH FILM FROM OTHER FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]'''),
    ('''        y = 420
        for s, f, c, step in lines:''',
     '''        y = 474          # v18: three-line block centred on ~540
        for s, f, c, step in lines:'''),
    ('''        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 2.5) / 0.4))
        if a <= 0:
            return
        self.text(d, (W / 2, 432), "DIRECTED BY CONNOR KERSTING"''',
     '''        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 4.05) / 0.4))     # v18: 4.45 s (v17: out 2.5-2.9)
        if a <= 0:
            return
        self.text(d, (W / 2, 432), "DIRECTED BY CONNOR KERSTING"'''),
    ('''GLITCH_WINDOWS = [''', '''# v18: the v16b asc_label_clean() hack is gone (ascent_blender_v5 keeps its labels inside the frame)
CARD2_T = 89.0      # v18: logical start of the creator card (real 82.3)


GLITCH_WINDOWS = ['''),
]
s = apply(s, R, "build")
# v18: the asc_label_clean hack (v16b) goes with the v5 ascent render (its call was removed above)
s = cut_block(s, "def asc_label_clean(fr: np.ndarray, k: float) -> np.ndarray:",
              "# v18: the v16b asc_label_clean() hack is gone", "build asc_label_clean")
assert "def asc_label_clean(" not in s and "fr = asc_label_clean(" not in s
# ============================================================== score_pd.py
sc = load(S)
assert "def ring_out(" in sc, "apply patch_v17 first (score)"
assert "TOTAL = 87.5" not in sc, "v18 already applied (score)"
RS = [
    ('''TOTAL = 87.0            # v17: credits 4.5 s + second card 3.0 s + 0.7 s silence (v8-v16 81.8; v7: 88.5)''',
     '''TOTAL = 87.5            # v18: credits 3.45 + 4.45 s, black to 87.5; tables unchanged (silence from 86.3) (v17 87.0; v8-v16 81.8; v7: 88.5)'''),
]
sc = apply(sc, RS, "score")
save(P, s)
save(S, sc)
print(f"v18: build {len(R)} patches + asc_label_clean removed, score {len(RS)}. TOTAL 87.5 (2100 frames), 43 shots. "
      f"Re-render: py build.py shots 18 (all), dialog 18 (its stems follow TOTAL: 87.0 -> 87.5), music 18, comp 18, mix 18.")
