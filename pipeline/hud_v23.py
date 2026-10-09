"""MOONSHOT v23 HUD: v22's one overlay system, extended to the ascent beat, the cold open and the end card, with every
disclosure tag at phone size (design: hud_v23/DESIGN.md, a v23 section appended to a copy of hud_v22/DESIGN.md).

A copy of hud_v22.py (tag v22-src) with the changes below; hud_v22.py is unchanged, so build.py's V23_HUD = False
draws v22 exactly.

v23 changes:
  TAG       a new size token TAG = 56 for disclosure tags: Franklin cap height 0.67 em = 37.5 px at 1080p = 12.5 px at
            360p (>= 12 px, the audit's acceptance test; LBL_S 30 was ~6.7 px).
  ascent    render_ascent(): the labels, the mission clock and the values of the 3D ascent beat (frames 524-635),
            drawn here instead of baked in the Blender render (ascent_blender_v23 has no text). Values and timings are
            v5's: the same strings per asset frame (geometry.json 'values', formatted exactly as ascent3d_v5.py did),
            the same asset frame per output frame (the manifest's 'display' map, measured from render_seq's own
            ffmpeg filter), the event labels fade with their rings (v5's k). Layout: the title + the 6x disclosure on a
            plate top-left (Earth side, clear of the limb on every frame), the readouts in a column on the space side,
            each event label next to its ring at the first clear candidate position (asc_layout(): a per-frame bbox
            test against the projected tube, both rings and the limb; the choice sticks while it stays clear).
  grain     globe_grain(): 16 mm-matched grain on the CG globe before the grade (mid-tone weighted, 2 px clumps,
            seeded per frame), so the globe is not cleaner than the film around it.
  flashtag  render_flashtag(): the cold-open flash-forward block (frames 94-201: Moon, Eagle, dust, visor, Earthrise)
            carries one tag in the countdown's own slot (where the hook said 'JULY 16, 1969'): '4 DAYS LATER' amber /
            'THE MOON' cream, both TAG size. The countdown HUD is gated off there (l70_window), the numeral is
            bottom-right and no caption runs in 3.9-8.4, so nothing shares the slot.
  timetag   'TIME-COMPRESSED' leaves the CRT glass (OCR-A 30, ~6.5 px cap at 360p) for a system plate under the monitor
            (x 1300-1820, y 832-890), TAG medium cream, with the monitor's alpha.
  archive   'ARCHIVE: OTHER SATURN V FLIGHT' at TAG size on its plate, moved to the top-left slot (at TAG size it would
            reach the centred caption box at the bottom; top-left it clears the captions and STAGE SEPARATION).
  endnote   render_endnote(): the on-screen AI-assist disclosure on the end-title card (frames 1853-1890, the date
            line's own alpha; never in the credits 1891+): 'EDITED WITH AN AI AGENT' amber / 'ARCHIVAL NASA FOOTAGE'
            cream, TAG size, centred under the date line, clear of the title, the date line and the LM.

v22 docstring follows.
MOONSHOT v22 HUD: v21's hardware HUD as ONE overlay system, plus the v21 critics' defects (design: hud_v22/DESIGN.md).

A copy of hud_v21.py (tag v21-src) with the changes below; hud_v21.py is unchanged, so build.py's V22_HUD = False draws
v21 exactly. build.py keeps every value computation (count curves, fuel(), descent(), get_at, READOUT_HOLDS, the
thresholds); the Gfx methods hand values to a HudFrame and stage_comp calls composite() (render + ONE film pass).

v22 changes:
  odometer  odometer_positions() chains each wheel's carry from the DISPLAYED (carry-delayed) position of the wheel
            below (v21 used the raw value: the TLI thousands wheel was half-rolled at 23,950, ~10x too early). Rest
            values identical. thrust_wheels() (the 7 / .5 wheels are not a carry chain) unchanged; both gated.
  dsky      over Mission Control the legend '1202 = COMPUTER OVERLOADED' is a HEADER plate on the panel's top edge
            (y 372-422), so the assembly ends at the panel bottom (796): 96 px above the caption box (v21: 42 px).
  contact   the CONTACT LIGHT insert is drawn here (v21: build.py Gfx), in the shared housing (same bezel as the
            CRT and DSKY), 40 px further left (housing x 584-1256): 44 px clear of the monitor (v21: 4 px). The lamp
            keeps its blue emission, timing and flicker.
  system    one label face (Franklin Gothic Demi / Medium Cond), one size scale (LBL_XL 56 / LBL_L 44 / LBL_M 40 /
            LBL_S 30), one amber (AMBER) for every label, cream (CREAM) for every secondary line, one plate (dark fill +
            the drum-window bezel), one housing for hardware, one film pass (composite). The cold-open countdown /
            hook header, the archive tag, STAGE SEPARATION and the DAY 5 chapter card move here from build.py (with
            their top gradient, so the order under the labels is unchanged).
  distance  render_distance() in the flight-plan drum style (only with build.py V22_DISTANCE = True; default False
            keeps v19's card, the protected Moon beat): AVERAGE DISTANCE / 6 drum wheels / MILES TO THE MOON, rule cut
            to the counter width (clear of the Moon limb), sub-line in demi 48 (the EffectCraft trial's weak spots).

v21 docstring follows.
MOONSHOT v21 HUD: v20's authentic 1969 hardware, made to read at PHONE SIZE (360p).

A copy of hud_v20.py (tag v20-src; design: work/hud_v20/DESIGN.md) with the changes below. hud_v20.py is unchanged,
so build.py's V21_HUD = False reproduces v20's drawing exactly. build.py keeps every value computation; its Gfx
methods hand the values to a HudFrame and stage_comp calls composite() (render + film pass, under the captions layer).

v21 changes (critics on v20: Fable editor top_fixes 1, 2, 4; blind A/B judge on the landing section, which preferred
v19 because v20's HUD was too small at phone size and its reverse-video bingo read as a glitch):
  crt     1.5x numerals: the bingo seconds and ALT feet are 160 px OCR-A (v20 107): cap height 104 px = 35 px at 360p
          (v20 69 / 23). The redundant 'SEC' after the bingo value goes (the heading says SEC TO BINGO); GET moves to a
          small footer line above TIME-COMPRESSED (both 30 px, kept for honesty). Panel 520 x 736 at x 1300-1820,
          y 90-826 (v20 y 90-748; the caption box top is >= 892, captions here are centred and narrow).
          The tube survives the downscale: bezel 22 px (v20 14) with a top-lit gradient and a dark recessed lip; glass
          with rounded inner corners (r 46); an inner shadow where the glass meets the bezel; a 12 % edge vignette
          over face AND phosphor; a soft glass highlight top-left; scanlines on every 2nd row (v20 every 3rd).
          Urgency reads as intentional: at <= 30.0 s (displayed; the same frames as v20 and v19's red) the WHOLE bingo
          line is reverse video (a full-width phosphor bar with the digits knocked out) and a steady boxed 'LOW' tag
          sits beside the heading, in the same phosphor. No blink; normal video again at contact.
          Redraw without ghost: an altitude step never shows the old and the new value on one frame (v20 frame 1256
          read '90 FT': the old 4 at 0.45 under the new 3 at 0.6). Step frame 0: the old value alone, persisting at
          0.45; frame 1: the new value struck at 0.6; frames 2-3: 1.35 / 1.15 flare; then 1.0. alt_glyphs() is the
          one source for what the ALT row draws (the dry-run gate checks it on every frame).
  dsky    1.2x on the LM window (768 x 446 at 112, 70; v20 1.0x). 1.0x on the Mission Control side (v20 0.85x),
          moved down so its top is at y 424 (v20 384, on the far-right controller's chin), bottom 796; the legend
          there is the amber line '1202 = COMPUTER OVERLOADED' alone on its plate (the grey 'LM GUIDANCE COMPUTER'
          line names the device on the LM window 2 s earlier), plate bottom 850, 42 px above the caption box.
          Unlit segments, unlit sign bars and unlit plates dimmed from 24/36/28 to 14/20/16 (Fable), so R2 / R3 read
          as dark glass at 360p instead of two live rows of 8s.
  drums   No legible wrong values: the thrust 7 rolls at constant speed and lands at u 0.32 (frame 463.7; v20 u 0.90 on
          an ease-out that dwelt on 2.5 / 4.8 / 5.1 / 6.x MILLION for 18 frames); the .5 wheel's one extra turn lands at
          u 0.36 (frame 464.6). Every moving wheel (thrust and TLI) is motion-blurred over a 180-degree shutter, so a
          digit only resolves when its wheel is (nearly) still. Digits at the full legend cream (cylinder shading only
          at the window edges; v20 shaded the digit body down to ~45 %); window bezels 3 px on a 6 px margin (v20 2 / 4),
          so the figure leads its unit word at 360p. The TLI count curve and every rest value are unchanged.

Elements:
  dsky      the LM DSKY upper panel: 2 x 7 annunciator lamps (white status / amber caution, LM legends), the green
            electroluminescent display (COMP ACTY, PROG / VERB / NOUN plates, three signed 5-digit registers with
            separator bars), slanted 7-segment digits with the unlit segments faintly visible, EL bloom and flicker,
            1-2 frames of segment persistence, incandescent PROG lamp rise.
  crt       the MOCR console readout (bingo counter + Aldrin's callouts on one monitor): OCR-A (1968) data face,
            blue-white P4-like phosphor, bloom, scanlines, raster draw-on, phosphor persistence / flare on a redraw.
  thrust, speed, distance
            flight-plan / press-kit data blocks: Franklin Gothic condensed legends, an engineering scale rule,
            mechanical drum counters (Veeder-Root style windows, edge shading, carry roll, motion blur).
Fonts (Windows system fonts, no downloads): Franklin Gothic Demi Cond / Medium Cond (legends), OCR-A Extended (CRT data).
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 1080
FPS = 24
WINFONTS = Path(r"C:\Windows\Fonts")
FONT_FILES = {"demi": "FRADMCN.TTF", "med": "FRAMDCN.TTF", "ocr": "OCRAEXT.TTF"}

# palette
EL = np.array([124, 255, 140], np.float32)          # lit EL segment (DSKY green)
EL_OFF = (14, 20, 16)                                 # v21: unlit EL segment, dark glass (v20 24/36/28)
EL_PLATE_OFF = (12, 18, 14)                           # v21: unlit plate (v20 20/30/23)
AMBER_LAMP = np.array([255, 168, 52], np.float32)     # caution lamp lit
LAMP_OFF = (50, 52, 50)
PHOS = np.array([214, 232, 255], np.float32)          # MOCR phosphor (blue-white)
PHOS_GLOW = np.array([110, 160, 255], np.float32)
CREAM = (238, 234, 222)                               # printed ink (stat cards)
AMBER = (255, 176, 64)                                # house amber (legends)
GREY = (176, 178, 172)
# v22: the unified overlay system (hud_v22/DESIGN.md): one label face, one size scale, one amber, one plate, one housing
LBL_XL, LBL_L, LBL_M, LBL_S = 56, 44, 40, 30      # card headline / legend / secondary line / tag
TAG = 56            # v23: disclosure tags; Franklin cap 0.67 em = 37.5 px at 1080p = 12.5 px at 360p (>= 12)
ARCHIVE_TEXT = "ARCHIVE: OTHER SATURN V FLIGHT"
PLATE_FILL = (8, 8, 7)                           # legend / tag plate (alpha per use)
BEZEL_INK = (168, 163, 152)                      # the drum-window bezel colour, also the plate edge
HOUSING_RIM = (16, 17, 18)                       # hardware housings: outer rim, top catch-light, recessed lip
HOUSING_CATCH = (104, 106, 108)
CONTACT_CX = 920          # v22 (v21 960 in build.py): the CONTACT housing x 584-1256, 44 px clear of the CRT (1300)

DSKY_PROG_MODE = "63"     # P63 (braking phase) was running at the 1202 (ALSJ 102:38: P64 only from 102:41:32); "" blanks it
DSKY_SCALE_LEFT = 1.2     # v21 (v20 1.0): on the LM window
DSKY_SCALE_RIGHT = 1.0    # v21 (v20 0.85): over Mission Control
DSKY_RIGHT_BOTTOM = 796   # v21 (v20 700): top at 796 - 372 = 424, off the far-right controller's chin


@lru_cache(None)
def fnt(kind: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(WINFONTS / FONT_FILES[kind]), size)


def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return min(max(x, a), b)


def ease_out(x: float) -> float:
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = clamp(x)
    return x * x * (3 - 2 * x)


def tracked(d: ImageDraw.ImageDraw, xy: tuple, s: str, f: ImageFont.FreeTypeFont, fill, track: float = 0.0,
            anchor: str = "ls") -> float:
    """Letter-spaced text; anchor l/m/r + vertical code. Returns the width."""
    widths = [d.textlength(c, font=f) for c in s]
    total = sum(widths) + track * max(len(s) - 1, 0)
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c, w_ in zip(s, widths):
        d.text((x, y), c, font=f, fill=fill, anchor="l" + anchor[1])
        x += w_ + track
    return total


class HudFrame:
    """The HUD items of one output frame (kind -> the values build.py computed)."""

    def __init__(self, fi: int, tl: float) -> None:
        self.fi, self.tl = fi, tl
        self.items: dict[str, dict] = {}

    def add(self, kind: str, **kw) -> None:
        self.items[kind] = kw


# ====================================================================== DSKY
SEGS = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc", "7": "abc",
        "8": "abcdefg", "9": "abcdfg", " ": ""}


def seg_polys(x: float, y: float, w: float, h: float, th: float, slant: float) -> dict[str, list]:
    """Slanted 7-segment geometry with pointed (hexagonal) segment ends, the DSKY EL digit look."""
    g = th * 0.22
    hv = th / 2

    def hor(vc: float) -> list:
        u0, u1 = hv + g, w - hv - g
        return [(u0, vc), (u0 + hv, vc - hv), (u1 - hv, vc - hv), (u1, vc), (u1 - hv, vc + hv), (u0 + hv, vc + hv)]

    def ver(uc: float, v0: float, v1: float) -> list:
        return [(uc, v0), (uc + hv, v0 + hv), (uc + hv, v1 - hv), (uc, v1), (uc - hv, v1 - hv), (uc - hv, v0 + hv)]

    loc = {"a": hor(hv), "g": hor(h / 2), "d": hor(h - hv),
           "f": ver(hv, hv + g, h / 2 - g), "e": ver(hv, h / 2 + g, h - hv - g),
           "b": ver(w - hv, hv + g, h / 2 - g), "c": ver(w - hv, h / 2 + g, h - hv - g)}
    return {k: [(x + u + slant * (h - v) / h, y + v) for u, v in p] for k, p in loc.items()}


def sign_polys(x: float, y: float, w: float, h: float, th: float, slant: float) -> dict[str, list]:
    """'+' / '-' sign column: a horizontal bar (h) and a vertical bar (v) at mid-height."""
    vc, hv = h / 2, th / 2
    bar = [(0, vc - hv), (w, vc - hv), (w, vc + hv), (0, vc + hv)]
    vl = h * 0.30
    vb = [(w / 2 - hv, vc - vl), (w / 2 + hv, vc - vl), (w / 2 + hv, vc + vl), (w / 2 - hv, vc + vl)]
    return {k: [(x + u + slant * (h - v) / h, y + v) for u, v in p] for k, p in (("h", bar), ("v", vb))}


LAMPS = [("UPLINK\nACTY", "w"), ("TEMP", "a"), ("NO ATT", "w"), ("GIMBAL\nLOCK", "a"), ("STBY", "w"), ("PROG", "a"),
         ("KEY REL", "w"), ("RESTART", "a"), ("OPR ERR", "w"), ("TRACKER", "a"), ("PRIO\nDISP", "w"), ("ALT", "a"),
         ("NO DAP", "w"), ("VEL", "a")]          # LM DSKY lamp block, left column white status, right column amber
DSKY_W, DSKY_H, DM = 640, 372, 36                  # face size at scale 1, glow margin


@lru_cache(None)
def dsky_static(sc: float) -> tuple[Image.Image, dict]:
    """Housing, lamp block (unlit), EL window with unlit segments and dark plates; geometry for the live parts."""
    s = lambda v: v * sc      # noqa: E731
    cw, ch = int(round(s(DSKY_W) + 2 * DM)), int(round(s(DSKY_H) + 2 * DM))
    im = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = DM, DM, DM + s(DSKY_W), DM + s(DSKY_H)
    # housing: grey cast panel, bevel, faint texture
    d.rounded_rectangle([x0, y0, x1, y1], radius=s(14), fill=(62, 64, 64, 255))
    d.rounded_rectangle([x0, y0, x1, y1], radius=s(14), outline=(30, 31, 32, 255), width=max(2, int(s(3))))
    d.line([(x0 + s(10), y0 + s(2)), (x1 - s(10), y0 + s(2))], fill=(98, 100, 100, 255), width=max(1, int(s(2))))
    arr = np.asarray(im, np.float32).copy()
    rng = np.random.default_rng(1969)
    tex = rng.normal(0, 2.2, arr.shape[:2]).astype(np.float32)
    m = arr[..., 3] > 0
    arr[..., :3][m] += tex[m][:, None]
    im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(im)
    for sx, sy in ((x0 + s(9), y0 + s(9)), (x1 - s(9), y0 + s(9)), (x0 + s(9), y1 - s(9)), (x1 - s(9), y1 - s(9))):
        r = s(4.5)
        d.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(84, 86, 86, 255), outline=(36, 37, 38, 255))
        d.line([(sx - r * 0.7, sy), (sx + r * 0.7, sy)], fill=(34, 35, 36, 255), width=max(1, int(s(1.5))))
    geo: dict = {"lamps": {}, "plates": {}, "digits": {}}
    # lamp block
    lx0, ly0, lx1, ly1 = x0 + s(20), y0 + s(20), x0 + s(298), y1 - s(20)
    d.rectangle([lx0, ly0, lx1, ly1], fill=(16, 17, 17, 255))
    gap = s(7)
    lw = (lx1 - lx0 - 3 * gap) / 2
    lh = (ly1 - ly0 - 8 * gap) / 7
    for i, (name, kind) in enumerate(LAMPS):
        r_, c_ = divmod(i, 2)
        bx = lx0 + gap + c_ * (lw + gap)
        by = ly0 + gap + r_ * (lh + gap)
        box = [bx, by, bx + lw, by + lh]
        d.rectangle(box, fill=LAMP_OFF + (255,), outline=(28, 29, 29, 255), width=max(1, int(s(1.5))))
        d.line([(bx + 2, by + 2), (bx + lw - 2, by + 2)], fill=(64, 66, 64, 255), width=1)
        f = fnt("med", max(8, int(round(s(13 if "\n" in name else 15)))))
        d.multiline_text((bx + lw / 2, by + lh / 2), name, font=f, fill=(96, 98, 94, 255), anchor="mm", align="center",
                         spacing=max(0, int(s(1))))
        geo["lamps"][name.replace("\n", " ")] = (box, kind, name)
    # EL window
    ex0, ey0, ex1, ey1 = x0 + s(314), y0 + s(20), x1 - s(20), y1 - s(20)
    d.rectangle([ex0, ey0, ex1, ey1], fill=(9, 11, 9, 255), outline=(24, 25, 25, 255), width=max(1, int(s(2))))
    e = lambda u, v: (ex0 + s(u), ey0 + s(v))      # noqa: E731
    plates = {"COMP\nACTY": (14, 12, 104, 74), "PROG": (196, 12, 292, 34), "VERB": (14, 90, 110, 112),
              "NOUN": (196, 90, 292, 112)}
    for name, (a_, b_, c_, d_) in plates.items():
        p0, p1 = e(a_, b_), e(c_, d_)
        d.rectangle([p0[0], p0[1], p1[0], p1[1]], fill=EL_PLATE_OFF + (255,))
        geo["plates"][name] = [p0[0], p0[1], p1[0], p1[1]]
    th, slant = s(5.2), s(4.5)
    dh, dw = s(42), s(25)

    def add_digits(key: str, xs: list[float], v: float, sign: bool = False) -> None:
        polys = []
        for k, u in enumerate(xs):
            px, py = e(u, v)
            if sign and k == 0:
                polys.append(("sign", sign_polys(px, py, dw, dh, th, slant)))
            else:
                polys.append(("seg", seg_polys(px, py, dw, dh, th, slant)))
        geo["digits"][key] = polys
        for _, pp in polys:
            for poly in pp.values():
                d.polygon(poly, fill=EL_OFF + (255,))

    add_digits("prog", [222, 256], 38)
    add_digits("verb", [32, 66], 116)
    add_digits("noun", [222, 256], 116)
    geo["bars"] = []
    for k, key in enumerate(("r1", "r2", "r3")):
        vb = 166 + 58 * k
        p0, p1 = e(12, vb), e(294, vb + 3.5)
        geo["bars"].append([p0[0], p0[1], p1[0], p1[1]])
        d.rectangle([p0[0], p0[1], p1[0], p1[1]], fill=EL_OFF + (255,))
        add_digits(key, [14, 58, 104, 150, 196, 242], vb + 9, sign=True)
    geo["face"] = (x0, y0, x1, y1)
    return im, geo


def dsky_content(u: float) -> dict[str, str]:
    """What the display shows at u (s after the alarm): the program, then V05 N09 keyed and R1 = alarm code 01202
    (the AGC shows alarm codes in octal, sign column blank); R2 / R3 blank (not stated in our sources)."""
    c = {"prog": DSKY_PROG_MODE.rjust(2) if u >= 0.0 else "  ", "verb": "  ", "noun": "  ",
         "r1": "      ", "r2": "      ", "r3": "      "}
    if u >= 0.25:
        c["verb"] = "05"
    if u >= 0.42:
        c["noun"] = "09"
    if u >= 0.58:
        c["r1"] = " 01202"
    return c


def lit_set(c: dict[str, str]) -> set:
    out = set()
    for key, sx in c.items():
        for k, ch in enumerate(sx):
            if key.startswith("r") and k == 0:
                if ch in "+-":
                    out.add((key, 0, "h"))
                if ch == "+":
                    out.add((key, 0, "v"))
                continue
            for sg in SEGS[ch]:
                out.add((key, k, sg))
    return out


def el_flicker(fi: int) -> float:
    r = np.random.default_rng(5000 + fi // 2).random()
    return 0.955 + 0.045 * r


def dsky_box(right: bool) -> tuple[float, float, float, float]:
    """v21: the DSKY face's screen box (x0, y0, x1, y1) on each side (also used by the dry-run collision check)."""
    sc = DSKY_SCALE_RIGHT if right else DSKY_SCALE_LEFT
    fw, fh = DSKY_W * sc, DSKY_H * sc
    if right:
        return 1808 - fw, DSKY_RIGHT_BOTTOM - fh, 1808, DSKY_RIGHT_BOTTOM
    return 112, 70, 112 + fw, 70 + fh


def render_dsky(hud: Image.Image, it: dict, fi: int) -> None:
    u, right, a = it["u"], it["right"], it["a"]
    if a <= 0:
        return
    sc = DSKY_SCALE_RIGHT if right else DSKY_SCALE_LEFT
    static, geo = dsky_static(sc)
    pan = static.copy()
    emis = Image.new("RGB", pan.size, (0, 0, 0))
    d, de = ImageDraw.Draw(pan), ImageDraw.Draw(emis)
    strike = (0.0, 0.35, 0.75, 1.0)[min(3, max(0, int((u - 0.04) * FPS + 1e-6) + 1))] if u >= 0.04 else 0.0
    m = strike * el_flicker(fi)

    def elc(i: float) -> tuple:
        c = np.array(EL_OFF, np.float32) * (1 - min(i, 1.0)) + EL * i
        return tuple(int(v) for v in np.clip(c, 0, 255))

    # label plates: lit green, black legend
    for name, box in geo["plates"].items():
        if name.startswith("COMP"):
            on = np.random.default_rng(900 + fi // 2).random() < 0.55
            i = m * (1.0 if on else 0.0)
        else:
            i = m
        if i <= 0:
            continue
        d.rectangle(box, fill=elc(i) + (255,))
        de.rectangle(box, fill=tuple(int(v * i * 0.55) for v in EL))
        f = fnt("demi", max(8, int(round((box[3] - box[1]) * (0.36 if "\n" in name else 0.78)))))
        d.multiline_text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), name, font=f, fill=(8, 14, 8, 255),
                         anchor="mm", align="center", spacing=0)
    for box in geo["bars"]:
        if m > 0:
            d.rectangle(box, fill=elc(m * 0.85) + (255,))
            de.rectangle(box, fill=tuple(int(v * m * 0.5) for v in EL))
    # digits with 1-2 frames of persistence: a new segment rises over one frame, a dropped one decays over two
    now = lit_set(dsky_content(u))
    p1 = lit_set(dsky_content(u - 1 / FPS))
    p2 = lit_set(dsky_content(u - 2 / FPS))
    for key, polys in geo["digits"].items():
        for k, (kind, pp) in enumerate(polys):
            for sg, poly in pp.items():
                idx = (key, k, sg)
                if idx in now:
                    i = 1.0 if idx in p1 else 0.55
                elif idx in p1:
                    i = 0.40
                elif idx in p2:
                    i = 0.12
                else:
                    continue
                i *= m
                if i <= 0:
                    continue
                d.polygon(poly, fill=elc(i) + (255,))
                de.polygon(poly, fill=tuple(int(v * i) for v in EL))
    # PROG caution lamp: steady (the 1202 lights it), incandescent rise over ~2 frames
    box, _, name = geo["lamps"]["PROG"]
    li = clamp(u / (2 / FPS))
    if li > 0:
        col = np.array(LAMP_OFF, np.float32) * (1 - li) + AMBER_LAMP * li
        d.rectangle(box, fill=tuple(int(v) for v in col) + (255,))
        f = fnt("demi", max(8, int(round((box[3] - box[1]) * 0.42))))
        d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "PROG", font=f, fill=(46, 26, 4, 255), anchor="mm")
        de.rectangle(box, fill=tuple(int(v * li * 0.7) for v in AMBER_LAMP))
    # bloom: two blurs of the emissive layer, added (premultiplied) and given alpha outside the housing
    g1 = np.asarray(emis.filter(ImageFilter.GaussianBlur(4 * sc)), np.float32)
    g2 = np.asarray(emis.filter(ImageFilter.GaussianBlur(15 * sc)), np.float32)
    glow = g1 * 0.55 + g2 * 0.75
    P = np.asarray(pan, np.float32)
    pa = P[..., 3:] / 255.0
    rgb = P[..., :3] * pa + glow
    al = np.clip(np.maximum(pa[..., 0], glow.max(-1) / 255.0), 0, 1)
    out = np.zeros_like(P)
    out[..., :3] = np.clip(rgb / np.maximum(al[..., None], 1e-4), 0, 255)
    out[..., 3] = al * 255 * a
    img = Image.fromarray(out.astype(np.uint8), "RGBA")
    ox, oy, _, yb = dsky_box(right)
    fw = geo["face"][2] - geo["face"][0]
    hud.alpha_composite(img, (int(round(ox - DM)), int(round(oy - DM))))
    # legends (printed, outside the hardware): what it is; what the code means (from u 1.0, as v19)
    la = a * clamp((u - 1.0) / 0.4)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    if right:      # v22: a HEADER plate on the panel's top edge (v21: under it, 42 px above the caption box)
        bx = dsky_header_box()
        legend_plate(hud, bx, a)
        if la > 0:
            tracked(td, ((bx[0] + bx[2]) / 2, bx[3] - 12), "1202 = COMPUTER OVERLOADED", fnt("demi", LBL_L),
                    AMBER + (int(255 * la),), 1, "ms")      # centred, track 1: 600 px inside the 640 px plate
    else:          # v22: the name in the secondary cream (v21 grey 28), the meaning in the label amber
        tracked(td, (ox, yb + 40), "LM GUIDANCE COMPUTER", fnt("med", LBL_S), CREAM + (int(235 * a),), 3, "ls")
        if la > 0:
            tracked(td, (ox, yb + 88), "1202 = COMPUTER OVERLOADED", fnt("demi", LBL_L), AMBER + (int(255 * la),), 3,
                    "ls")
    hud.alpha_composite(tmp)


def dsky_header_box() -> tuple[int, int, int, int]:
    """v22: the right-side legend header plate (x0, y0, x1, y1): the panel's width, 50 px tall, 2 px above its top."""
    x0, y0, x1, _ = dsky_box(True)
    return int(round(x0)), int(round(y0)) - 52, int(round(x1)), int(round(y0)) - 2


def legend_plate(hud: Image.Image, box: tuple, a: float) -> None:
    """v22: the one plate of the system (legends, tags): dark fill, 2 px edge in the drum-window bezel colour."""
    if a <= 0:
        return
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    pl = Image.new("RGBA", (x1 - x0, y1 - y0), PLATE_FILL + (int(200 * a),))
    ImageDraw.Draw(pl).rectangle([0, 0, x1 - x0 - 1, y1 - y0 - 1], outline=BEZEL_INK + (int(200 * a),), width=2)
    hud.alpha_composite(pl, (x0, y0))


# ====================================================================== MOCR CRT
CRT_X, CRT_Y, CRT_W, CRT_H = 1300, 90, 520, 736   # v21: y 90-826 (v20 to 748); x capped by the CONTACT insert (1296)
REVERSE_AT = 30.0       # the displayed bingo value at or below this is drawn in reverse video (v19: red from 30.0)
BZ = 22                 # v21: bezel (v20 14)
SCR_R = 46              # v21: rounded inner screen corners (v20 22)
CRT_L = 18              # left / right text margin inside the glass
F_BIG = 160             # v21: bingo seconds and ALT feet (v20 107)


def reverse_video(fu: dict) -> bool:
    """Reverse video while the DISPLAYED counter is <= 30.0 s and the counter runs (at contact it reverts, as v19's
    red turned white)."""
    return (not fu["held"]) and float(f"{fu['rem']:04.1f}") <= REVERSE_AT + 1e-9


def alt_glyphs(fu: dict, de: dict) -> list[tuple[str, float]]:
    """v21: what the ALT row draws this frame, as (text, intensity); always exactly ONE value (no ghost). On a
    redraw: step frame 0 the old value alone at 0.45 (phosphor persistence), frame 1 the new value struck at 0.6,
    frames 2-3 the flare 1.35 / 1.15, then 1.0. With no previous value the new one strikes on frame 0."""
    if de["held"]:
        return [("CONTACT", 1.0)]
    new = f"{de['alt']:>3}"
    if not de["fresh"]:
        return [(new, 1.0)]
    k = int(math.floor((fu["t"] - de["t_step"]) * FPS + 1e-6)) if de["t_step"] > 0 else 99
    if de["prev_alt"] is not None:
        if k <= 0:
            return [(f"{de['prev_alt']:>3}", 0.45)]
        return [(new, {1: 0.6, 2: 1.35, 3: 1.15}.get(k, 1.0))]
    return [(new, {0: 0.6, 1: 1.35, 2: 1.15, 3: 1.05}.get(k, 1.0))]


@lru_cache(None)
def crt_static() -> tuple[Image.Image, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """v21: the tube. Bezel (top-lit gradient, outer rim, recessed lip), glass face (blue-black, brighter centre,
    rounded corners r 46) and the screen-space maps applied after the phosphor: scanline gain (every 2nd row),
    vignette x inner shadow (multiplies face AND phosphor), glass highlight (added on top)."""
    im = Image.new("RGBA", (CRT_W, CRT_H), (0, 0, 0, 0))
    # bezel body: vertical gradient, lit from above
    yy = np.linspace(0, 1, CRT_H, dtype=np.float32)[:, None]
    body = (np.array([66, 68, 71], np.float32) * (1 - yy) + np.array([34, 35, 37], np.float32) * yy)[:, None, :]
    body = np.broadcast_to(body.reshape(CRT_H, 1, 3), (CRT_H, CRT_W, 3)).copy()
    rng = np.random.default_rng(1968)
    body += rng.normal(0, 1.6, body.shape[:2]).astype(np.float32)[..., None]
    mask = Image.new("L", (CRT_W, CRT_H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, CRT_W - 1, CRT_H - 1], radius=26, fill=255)
    im = Image.fromarray(np.clip(body, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    im.putalpha(mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CRT_W - 1, CRT_H - 1], radius=26, outline=(16, 17, 18, 255), width=3)
    d.line([(20, 3), (CRT_W - 20, 3)], fill=(104, 106, 108, 255), width=2)          # top edge catch-light
    d.rounded_rectangle([BZ - 7, BZ - 7, CRT_W - BZ + 6, CRT_H - BZ + 6], radius=SCR_R + 7,
                        fill=(14, 15, 16, 255))                                      # recessed lip around the glass
    d.rounded_rectangle([BZ - 7, BZ - 7, CRT_W - BZ + 6, CRT_H - BZ + 6], radius=SCR_R + 7,
                        outline=(80, 82, 84, 255), width=1)
    sw, sh = CRT_W - 2 * BZ, CRT_H - 2 * BZ
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    nx, ny = (xx - sw / 2) / (sw / 2), (yy - sh / 2) / (sh / 2)
    r = np.hypot(nx, ny) / math.sqrt(2)
    face = np.zeros((sh, sw, 3), np.float32)
    face[:] = np.array([11, 14, 18], np.float32)
    face += (np.clip(1 - r * 1.25, 0, 1) ** 1.4)[..., None] * np.array([13, 16, 21], np.float32)
    face[1::2] *= 0.86                                    # raster on the face itself, every 2nd row
    smask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(smask).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=SCR_R, fill=255)
    scr = Image.fromarray(np.clip(face, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    scr.putalpha(smask)
    im.alpha_composite(scr, (BZ, BZ))
    # screen-space maps
    scan = np.ones((sh, 1), np.float32)
    scan[1::2] = 0.58
    edge = np.asarray(smask.filter(ImageFilter.GaussianBlur(9)), np.float32) / 255.0      # inner shadow at the lip
    vig = (1 - 0.12 * np.clip(np.maximum(np.abs(nx), np.abs(ny)) ** 4 + 0.35 * r ** 2, 0, 1)) * (0.55 + 0.45 * edge)
    hx, hy = (xx - sw * 0.27) / (sw * 0.46), (yy - sh * 0.15) / (sh * 0.22)
    hl = np.clip(1 - np.hypot(hx, hy), 0, 1) ** 2 * 34.0                                  # soft glass highlight
    arc = np.exp(-((np.hypot((xx - sw * 0.55) / (sw * 0.62), (yy - sh * 0.62) / (sh * 0.66)) - 1.0) / 0.012) ** 2)
    hl += arc * (yy < sh * 0.3) * (xx < sw * 0.75) * 14.0                                  # thin specular arc, top-left
    hl *= np.asarray(smask, np.float32) / 255.0
    return im, scan, vig.astype(np.float32), hl.astype(np.float32), np.asarray(smask, np.float32)[..., None] / 255.0


class Ink:
    """Phosphor intensity accumulator for the CRT screen (float, may exceed 1 for a fresh redraw)."""

    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.a = np.zeros((h, w), np.float32)

    def text(self, xy: tuple, s: str, f: ImageFont.FreeTypeFont, i: float = 1.0, anchor: str = "ls",
             track: float = 0.0) -> float:
        if i <= 0 or not s:
            return 0.0
        m = Image.new("L", (self.w, self.h), 0)
        wdt = tracked(ImageDraw.Draw(m), xy, s, f, 255, track, anchor)
        self.a = np.maximum(self.a, np.asarray(m, np.float32) / 255.0 * i)
        return wdt

    def rect(self, box: list, i: float) -> None:
        x0, y0, x1, y1 = (int(round(v)) for v in box)
        self.a[max(y0, 0):y1, max(x0, 0):x1] = np.maximum(self.a[max(y0, 0):y1, max(x0, 0):x1], i)

    def frame(self, box: list, i: float, wd: int = 3) -> None:
        x0, y0, x1, y1 = box
        for b in ([x0, y0, x1, y0 + wd], [x0, y1 - wd, x1, y1], [x0, y0, x0 + wd, y1], [x1 - wd, y0, x1, y1]):
            self.rect(b, i)


def render_crt(hud: Image.Image, fu: dict, de: dict | None, fi: int) -> None:
    """v21 layout (screen coordinates inside the glass, 476 x 692): heading 'SEC TO BINGO' / 'LAND OR ABORT' (32 px)
    with the 'LOW' tag right of it while reverse; the bingo value 160 px (baseline 226); the 30-tick gauge (2 s per
    tick, 60 s full scale); 'ALDRIN CALLOUTS'; ALT 160 px (baseline 470); DOWN / FWD 58 px; footer GET and
    TIME-COMPRESSED 30 px."""
    bez, scan, vig, hl, smask = crt_static()
    a = fu["a"]
    if a <= 0:
        return
    sw, sh = CRT_W - 2 * BZ, CRT_H - 2 * BZ
    ink = Ink(sw, sh)
    held, rem, label = fu["held"], fu["rem"], fu["label"]
    L = CRT_L
    f_lab, f_big, f_mid, f_unit, f_foot = fnt("ocr", 32), fnt("ocr", F_BIG), fnt("ocr", 58), fnt("ocr", 34), fnt("ocr", 30)
    ink.text((L, 46), "SEC TO BINGO", f_lab, 0.9)
    ink.text((L, 82), "LAND OR ABORT", f_lab, 0.9)
    val = f"{rem:04.1f}"
    if reverse_video(fu):
        # the whole line in reverse video: a full-width phosphor bar, the digits knocked out dark
        m = Image.new("L", (sw, sh), 0)
        md = ImageDraw.Draw(m)
        md.text((L + 6, 226), val, font=f_big, fill=255, anchor="ls")
        bb = md.textbbox((L + 6, 226), val, font=f_big, anchor="ls")
        ink.rect([L - 8, bb[1] - 14, sw - L + 8, 226 + 14], 0.92)
        ink.a[np.asarray(m) > 96] = 0.03
        # steady 'LOW' tag in the same phosphor, boxed, beside the heading
        tb = [sw - L - 112, 18, sw - L, 90]
        ink.frame(tb, 1.0, 3)
        ink.text(((tb[0] + tb[2]) / 2, 70), "LOW", fnt("ocr", 44), 1.0, anchor="ms")
    else:
        ink.text((L + 6, 226), val, f_big, 1.0)
    # bingo gauge: 30 ticks, 2 s each (the v19 bar's 60 s full scale)
    n = rem / 2.0
    pitch = (sw - 2 * L) / 30
    for k in range(30):
        x = L + k * pitch
        i = 1.0 if k + 1 <= n else (0.18 + 0.82 * (n - k) if k < n else 0.16)
        ink.rect([x, 256, x + pitch - 4.5, 280], i)
    ink.rect([L, 296, sw - L, 297], 0.3)
    if de is not None:
        da = de["a"]
        rows = Ink(sw, sh)
        rows.text((L, 336), "ALDRIN CALLOUTS", f_lab, 0.9)
        if de["held"]:
            rows.text((L, 466), "CONTACT", fnt("ocr", 100), 1.0)
        else:
            rows.text((L, 470), "ALT", f_unit, 0.85)
            wv = 0.0
            for s_, i_ in alt_glyphs(fu, de):
                wv = rows.text((L + 84, 470), s_, f_big, i_)
            rows.text((L + 84 + wv + 14, 470), "FT", f_unit, 0.85)
        ri = 0.35 if de["held"] else 1.0
        down = de["down"]
        rows.text((L, 536), "DOWN", f_unit, 0.85 * ri)
        rows.text((L + 104, 536), f"{down:.1f}" if down is not None else "-", f_mid, ri)
        rows.text((L + 236, 536), "FT/S", f_unit, 0.85 * ri)
        if de["fwd"] is not None and not de["held"]:
            rows.text((L, 598), "FWD", f_unit, 0.85)
            rows.text((L + 104, 598), f"{de['fwd']:g}", f_mid, 1.0)
            rows.text((L + 236, 598), "FT/S", f_unit, 0.85)
        # raster draw-on of the callout block (55.75 + 0.3 s), not a crossfade
        ry = 300 + (sh - 300) * ease_out(da)
        rows.a[int(ry):] = 0
        ink.a = np.maximum(ink.a, rows.a)
    ink.text((L, 640), label, f_foot, 0.85 if held else 0.75)          # v21: GET / CONTACT time as a footer
    # v23: 'TIME-COMPRESSED' moved out of the glass to the TAG plate under the monitor (render_timetag)
    # power-on: the whole screen draws top to bottom with the beam line at the edge
    ry = sh * ease_out(a)
    ink.a[int(ry):] = 0
    if a < 1:
        ink.a[max(0, int(ry) - 2):int(ry)] = np.maximum(ink.a[max(0, int(ry) - 2):int(ry)], 0.5)
    # phosphor: core + bloom, scanlines, faint refresh shimmer; then the glass (vignette x inner shadow, highlight)
    shimmer = 0.97 + 0.03 * np.random.default_rng(7000 + fi).random()
    core = ink.a * scan * shimmer
    cimg = Image.fromarray(np.clip(core * 180, 0, 255).astype(np.uint8), "L")
    b1 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(2.2)), np.float32) / 180
    b2 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(9)), np.float32) / 180
    face = np.asarray(bez.crop((BZ, BZ, BZ + sw, BZ + sh)), np.float32)
    rgb = face[..., :3] + np.minimum(core, 1.0)[..., None] * PHOS + np.maximum(core - 1.0, 0)[..., None] * PHOS * 0.6 \
        + (b1 * 0.45)[..., None] * PHOS_GLOW + (b2 * 0.35)[..., None] * PHOS_GLOW
    rgb = rgb * vig[..., None] + hl[..., None]
    out = np.dstack([np.clip(rgb, 0, 255), face[..., 3:]]).astype(np.uint8)
    panel = bez.copy()
    scr = Image.fromarray(out, "RGBA")
    panel.alpha_composite(scr, (BZ, BZ))
    pa = np.asarray(panel, np.float32).copy()
    pa[..., 3] *= clamp(a * 3) * 0.97
    hud.alpha_composite(Image.fromarray(pa.astype(np.uint8), "RGBA"), (CRT_X, CRT_Y))


# ====================================================================== stat cards: drum counters
@lru_cache(None)
def drum_strip(h: int, w: int) -> np.ndarray:
    """Digits 0..9,0,1 stacked (cell h); float 0..1 ink (12 cells so a blurred window past 9.x still has a drum)."""
    f = fnt("demi", int(round(h * 1.02)))
    im = Image.new("L", (w, h * 12), 0)
    d = ImageDraw.Draw(im)
    for k in range(12):
        d.text((w / 2, k * h + h * 0.52), str(k % 10), font=f, fill=255, anchor="mm")
    return np.asarray(im, np.float32) / 255.0


@lru_cache(None)
def edge_shade(h: int) -> np.ndarray:
    """v21: the drum's curvature only at the window edges; the digit body at full cream (v20: sin shading over the
    whole cell, the digit body down to ~45 %)."""
    v = (np.arange(h, dtype=np.float32) + 0.5) / h
    return (np.clip(np.sin(np.pi * v) / 0.55, 0, 1) ** 0.8)[:, None]


def drum_ink(h: int, w: int, ps: list[float]) -> np.ndarray:
    """The drum window's ink averaged over the positions ps (motion blur: the positions the wheel passes during the
    open shutter)."""
    strip = drum_strip(h, w)
    acc = np.zeros((h, w), np.float32)
    for p in ps:
        off = int(round((p % 10) * h))
        acc += strip[off:off + h]
    return acc / len(ps)


def shutter_positions(p_now: float, p_prev: float, n_max: int = 24) -> list[float]:
    """Wheel positions sampled over a 180-degree shutter ending at this frame (half the move since the last frame)."""
    dv = p_now - p_prev
    n = int(min(n_max, max(1, math.ceil(abs(dv) * 0.5 * 12))))
    if n == 1:
        return [p_now]
    return [p_now - dv * 0.5 * (1 - k / (n - 1)) for k in range(n)]


def wheel(hud: Image.Image, x: int, y: int, w: int, h: int, ps: list[float], alpha: float) -> None:
    """One counter wheel: a dark window with a bevel (v21: 3 px on a 6 px margin, v20 2 / 4); the digit drum at the
    positions ps (one position = still; several = motion blur; digit = p mod 10, rolls up)."""
    if alpha <= 0:
        return
    mg = 6
    win = Image.new("RGBA", (w + 2 * mg, h + 2 * mg), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    d.rectangle([0, 0, w + 2 * mg - 1, h + 2 * mg - 1], fill=(10, 10, 9, int(225 * alpha)),
                outline=(168, 163, 152, int(235 * alpha)), width=3)
    d.rectangle([3, 3, w + 2 * mg - 4, h + 2 * mg - 4], outline=(40, 39, 36, int(220 * alpha)), width=1)
    hud.alpha_composite(win, (x - mg, y - mg))
    shade = edge_shade(h)
    ink = drum_ink(h, w, ps) * shade
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., :3] = (np.array(CREAM, np.float32)[None, None] * (0.7 + 0.3 * shade[..., None])).astype(np.uint8)
    rgba[..., 3] = np.clip(ink * 255 * alpha, 0, 255).astype(np.uint8)
    hud.alpha_composite(Image.fromarray(rgba, "RGBA"), (x, y))


def odometer_positions(v: float, n: int) -> list[float]:
    """Wheel positions, most significant first, for a counter of n wheels whose tens wheel turns continuously
    (units wheel fixed: the values are whole tens) and each higher wheel carries over the last tenth of the turn of
    the wheel below AS DISPLAYED. v22: the carry chains from the lower wheel's displayed (carry-delayed) position;
    v21 used the raw value (v / 10 ** (k - 1)), so the thousands wheel began its carry at x,x900 instead of x,x990
    (half-rolled at 23,950). Rest values (whole numbers) are identical."""
    p = {0: 0.0}
    if n > 1:
        p[1] = v / 10
    for k in range(2, n):
        lo = p[k - 1]
        p[k] = math.floor(lo / 10 + 1e-9) + clamp((lo % 10) - 9)
    return [p[k] for k in range(n - 1, -1, -1)]


def scale_rule(d: ImageDraw.ImageDraw, x: int, y: int, ln: float, a: float) -> None:
    """Engineering scale rule: hairline with minor ticks every 14 px, majors every 5th."""
    if ln <= 0 or a <= 0:
        return
    d.rectangle([x, y, x + ln, y + 2], fill=CREAM + (int(220 * a),))
    k = 0
    while k * 14 <= ln:
        tx = x + k * 14
        d.rectangle([tx, y, tx + 1, y + (14 if k % 5 == 0 else 6)], fill=CREAM + (int(200 * a),))
        k += 1


def type_on(s: str, prog: float) -> str:
    return s[:int(round(len(s) * clamp(prog)))]


def thrust_wheels(u: float) -> tuple[float, float]:
    """v21: the two thrust wheel positions at u. The 7 rolls 0 -> 7 at constant speed over u 0.10-0.32 (lands at frame
    463.7); the .5 wheel turns once more, -10 -> 5 over u 0.10-0.36 (lands at frame 464.6), the settle tick."""
    p7 = 7 * clamp((u - 0.10) / 0.22)
    p5 = 5 - 15 * (1 - clamp((u - 0.10) / 0.26))
    return p7, p5


def render_thrust(hud: Image.Image, it: dict) -> None:
    u = it["u"]
    out = ease_in_out((u - 2.45) / 0.35)          # v19 exit, gone by u 2.80 (before the 524 cut)
    a = 1 - out
    if a <= 0:
        return
    dy = -int(round(out * 30))
    x = 120
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    tracked(d, (x, 352 + dy), type_on("LIFTOFF THRUST", (u - 0.05) / 0.3), fnt("demi", LBL_L), AMBER + (255,), 5)
    scale_rule(d, x, 368 + dy, ease_out((u - 0.2) / 0.6) * 588, 1.0)
    hgt, wd = 150, 96
    wa = clamp((u - 0.1) / 0.15)
    p7, p5 = thrust_wheels(u)
    q7, q5 = thrust_wheels(u - 1 / FPS)
    wheel(tmp, x, 400 + dy, wd, hgt, shutter_positions(p7, q7), wa)                # 7 rolls up from 0
    d.ellipse([x + wd + 12, 400 + dy + hgt - 26, x + wd + 30, 400 + dy + hgt - 8], fill=CREAM + (int(255 * wa),))
    wheel(tmp, x + wd + 42, 400 + dy, wd, hgt, shutter_positions(p5, q5), wa)     # .5: one extra turn
    tracked(d, (x + 2 * wd + 70, 400 + dy + hgt - 12), "MILLION", fnt("demi", 150), CREAM + (int(255 * wa),), 2)
    tracked(d, (x, 600 + dy), type_on("POUNDS  ·  FIVE F-1 ENGINES", (u - 0.35) / 0.35), fnt("med", LBL_M),
            CREAM + (230,), 3)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


def radial_scrim(cx: float, cy: float, rx: float, ry: float, amax: float, a: float) -> Image.Image:
    g = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    g[..., 3] = (np.clip(amax * (1 - np.hypot((xx - cx) / rx, (yy - cy) / ry)), 0, amax) * a).astype(np.uint8)
    return Image.fromarray(g, "RGBA")


def tli_count(u: float) -> float:
    """build.py's TLI count curve (stat_speed: 17400 + 6800 * ease_out((u - 0.4) / 1.2)); used ONLY for the previous
    frame's position (motion blur). The frame's own value always comes from build.py (it['vc'])."""
    return 17400 + 6800 * ease_out((u - 0.4) / 1.2)


def render_speed(hud: Image.Image, it: dict) -> None:
    u, a, vc = it["u"], it["a"], it["vc"]
    if a <= 0:
        return
    # v19's scrim (same shape and strength): legibility over the Earth still / 16mm
    g = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    g[..., 3] = np.clip(200 * (1 - np.hypot((xx - 200) / 1300, (yy - 900) / 650)), 0, 200).astype(np.uint8) * a
    hud.alpha_composite(Image.fromarray(g, "RGBA"))
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    x = 120
    tracked(d, (x, 700), type_on("SPEED AT TRANSLUNAR INJECTION CUTOFF", (u - 0.15) / 0.45), fnt("demi", LBL_L),
            AMBER + (255,), 4)
    scale_rule(d, x, 716, ease_out((u - 0.2) / 0.6) * 840, 1.0)
    hgt, wd, gp = 168, 104, 10
    pos = odometer_positions(vc, 5)
    prev = odometer_positions(tli_count(u - 1 / FPS), 5)
    xx_ = x
    for k, (p, q) in enumerate(zip(pos, prev)):
        wheel(tmp, xx_, 748, wd, hgt, shutter_positions(p, q), 1.0)
        xx_ += wd + gp
        if k == 1:      # the printed thousands comma between the windows
            d.polygon([(xx_ + 2, 748 + hgt - 22), (xx_ + 18, 748 + hgt - 22), (xx_ + 8, 748 + hgt + 14),
                       (xx_ - 2, 748 + hgt + 14)], fill=CREAM + (255,))
            xx_ += 26
    tracked(d, (xx_ + 18, 748 + hgt - 10), "MPH", fnt("demi", 190), CREAM + (255,), 4)
    tracked(d, (124, 1004), type_on("FROM 17,400 IN EARTH ORBIT", (u - 0.3) / 0.4), fnt("med", LBL_M),
            CREAM + (int(255 * 0.9),), 4)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


def distance_count(u: float) -> float:
    """v22: the 240,000 card's count curve (0 -> 240,000, ease-out over u 0.10-0.70, lands at frame ~846)."""
    return 240000 * ease_out((u - 0.1) / 0.6)


def render_distance(hud: Image.Image, it: dict) -> None:
    """v22: the flight-plan drum card. Drawn only when build.py's V22_DISTANCE = True (default False: v19's card, the
    protected Moon beat). Timing from build.py unchanged: first active frame 830 (u > 0), staggered reveals (heading
    types on 0.05-0.25, rule 0.10-0.60, wheels from 0.10, count 0.10-0.70, sub-line 0.25-0.65), hard out at 878.
    EffectCraft-trial weak spots fixed: the rule stops at the counter's width (it grazed the Moon limb) and the
    sub-line is demi 48 cream (medium cream read weak at 360p)."""
    u, a = it["u"], it["a"]
    if a <= 0:
        return
    g = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    g[..., 3] = (np.clip(190 * (1 - np.hypot((xx - 300) / 1100, (yy - 860) / 420)), 0, 190) * a).astype(np.uint8)
    hud.alpha_composite(Image.fromarray(g, "RGBA"))
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    x = 112
    hgt, wd, gp, cm = 130, 82, 8, 22
    block = 6 * wd + 5 * gp + cm
    tracked(d, (x, 700), type_on("AVERAGE DISTANCE", (u - 0.05) / 0.2), fnt("demi", LBL_L), AMBER + (255,), 4)
    scale_rule(d, x, 714, ease_out((u - 0.1) / 0.5) * block, 1.0)
    wa = clamp((u - 0.1) / 0.15)
    e = ease_out((u - 0.1) / 0.6)
    pos = odometer_positions(distance_count(u), 6)
    prev = odometer_positions(distance_count(u - 1 / FPS), 6)
    if e >= 1:
        pos = prev = [float(int(c)) for c in "240000"]
    xx_ = x
    for k, (p, q) in enumerate(zip(pos, prev)):
        wheel(tmp, xx_, 740, wd, hgt, shutter_positions(p, q), wa)
        xx_ += wd + gp
        if k == 2:
            d.polygon([(xx_ + 2, 740 + hgt - 18), (xx_ + 15, 740 + hgt - 18), (xx_ + 7, 740 + hgt + 11),
                       (xx_ - 2, 740 + hgt + 11)], fill=CREAM + (int(255 * wa),))
            xx_ += cm
    tracked(d, (x, 942), type_on("MILES TO THE MOON", (u - 0.25) / 0.4), fnt("demi", 48), CREAM + (255,), 4)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


# ====================================================================== v22: the labels and the CONTACT insert
@lru_cache(None)
def housing(w: int, h: int, r: int = 18) -> Image.Image:
    """v22: the ONE hardware housing (the CRT's recipe at any size): top-lit grey gradient body with faint texture,
    3 px dark rim, a top catch-light, four screws (the DSKY's)."""
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    body = np.array([66, 68, 71], np.float32) * (1 - yy) + np.array([34, 35, 37], np.float32) * yy
    body = np.broadcast_to(body, (h, w, 3)).copy()
    body += np.random.default_rng(1969).normal(0, 1.6, (h, w)).astype(np.float32)[..., None]
    im = Image.fromarray(np.clip(body, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    im.putalpha(mask)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, outline=HOUSING_RIM + (255,), width=3)
    d.line([(r, 3), (w - r, 3)], fill=HOUSING_CATCH + (255,), width=2)
    for sx, sy in ((14, 14), (w - 15, 14), (14, h - 15), (w - 15, h - 15)):
        d.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], fill=(84, 86, 86, 255), outline=(36, 37, 38, 255))
        d.line([(sx - 3, sy), (sx + 3, sy)], fill=(34, 35, 36, 255), width=1)
    return im


def contact_box() -> tuple[int, int, int, int]:
    """v22: the CONTACT housing on screen (x0, y0, x1, y1) (also the dry-run clearance gate)."""
    cy = H // 2 - 40
    return CONTACT_CX - 336, cy - 136, CONTACT_CX + 336, cy + 136


def render_contact(hud: Image.Image, it: dict) -> None:
    """v22: v21's CONTACT LIGHT insert (build.py Gfx.contact_insert: dark at first, on at 0.12 s, off 0.25-0.33 s,
    then steady; the blue lamp with its 40 px glow) in the shared housing with a recessed lip, the legend in the
    system face, 40 px left of v21."""
    u = it["u"]
    on = u >= 0.12 and not (0.25 <= u < 0.33)
    x0, y0, x1, y1 = contact_box()
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    hud.alpha_composite(housing(x1 - x0, y1 - y0), (x0, y0))
    d = ImageDraw.Draw(hud)
    d.rounded_rectangle([cx - 312, cy - 112, cx + 312, cy + 112], radius=16, fill=(14, 15, 16, 255),
                        outline=(80, 82, 84, 255), width=1)                                   # recessed lip
    if on:
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).rounded_rectangle([cx - 330, cy - 120, cx + 330, cy + 120], radius=14,
                                               fill=(70, 150, 255, 200))
        hud.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        d = ImageDraw.Draw(hud)
    d.rounded_rectangle([cx - 300, cy - 100, cx + 300, cy + 100], radius=10,
                        fill=(120, 190, 255, 255) if on else (26, 32, 44, 255), outline=(90, 90, 90, 255), width=4)
    ink = (10, 20, 40, 255) if on else (70, 80, 95, 255)
    tracked(d, (cx, cy - 22 + 22), "LUNAR", fnt("demi", 66), ink, 10, "ms")
    tracked(d, (cx, cy + 40 + 22), "CONTACT", fnt("demi", 66), ink, 10, "ms")


def render_topgrad(hud: Image.Image, it: dict) -> None:
    """v21's top gradient (alpha 120 -> 0 over 240 rows), now under the HUD labels instead of on the graphics layer."""
    g = np.zeros((240, W, 4), np.uint8)
    g[..., 3] = (np.linspace(120, 0, 240)[:, None] * np.ones((1, W))).astype(np.uint8)
    hud.alpha_composite(Image.fromarray(g, "RGBA"))


def _bar(hud: Image.Image, a: float) -> None:
    hud.alpha_composite(Image.new("RGBA", (7, 65), AMBER + (int(230 * a),)), (112, 70))


def render_countdown(hud: Image.Image, it: dict) -> None:
    """v22: v21's cold-open countdown HUD (amber bar, site line, spoken-count clock; alpha and gating from build.py)
    in the system: the site line Franklin Demi LBL_S amber, the clock Franklin Demi LBL_M cream (OCR-A at 34 px was
    thinner than v21's mono over the bright pad sky at 360p: tried in the first dry run, rejected)."""
    a, site, s = it["a"], it["site"], it["s"]
    _bar(hud, a)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    if a * 0.95 * site > 0:
        tracked(td, (132, 94), "APOLLO 11  ·  LAUNCH COMPLEX 39A", fnt("demi", LBL_S), AMBER + (int(255 * a * 0.95 * site),),
                3, "ls")
    tracked(td, (132, 134), s, fnt("demi", LBL_M), CREAM + (int(255 * a),), 2, "ls")
    hud.alpha_composite(tmp)


def render_hook(hud: Image.Image, it: dict) -> None:
    """v22: v21's hook (0.15 s -> the 1.2 cut) in the countdown's slot and the system's faces."""
    a = it["a"]
    _bar(hud, a)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    tracked(td, (132, 94), "APOLLO 11", fnt("demi", LBL_S), AMBER + (int(255 * a * 0.95),), 3, "ls")
    tracked(td, (132, 134), "JULY 16, 1969", fnt("demi", LBL_M), CREAM + (int(255 * a),), 2, "ls")
    hud.alpha_composite(tmp)


def archive_box() -> tuple[int, int, int, int]:
    """v23: the archive tag's plate (top-left slot), sized to the TAG text."""
    tw = tracked(ImageDraw.Draw(Image.new("L", (8, 8))), (0, 0), ARCHIVE_TEXT, fnt("med", TAG), 0, 3)
    return 100, 62, int(128 + tw), 130


def render_archive(hud: Image.Image, it: dict) -> None:
    """v23: the provenance tag (26.5 -> the 29.8 cut) on the system plate at TAG size (12.5 px cap at 360p), in the
    top-left slot (v22: LBL_S 30, bottom-left at baseline 1004, ~6.7 px cap at 360p)."""
    a = it["a"]
    if a <= 0:
        return
    legend_plate(hud, archive_box(), a * 0.85)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    tracked(ImageDraw.Draw(tmp), (114, 115), ARCHIVE_TEXT, fnt("med", TAG), CREAM + (int(255 * a * 0.95),), 3, "ls")
    hud.alpha_composite(tmp)


def render_stage(hud: Image.Image, it: dict) -> None:
    """v22: STAGE SEPARATION (the 0.75 s staging shot) as a flight-plan legend: LBL_XL amber, right-aligned at 1808 in
    the upper sky (baseline 200), the scale rule under it; v21's fast in / out alpha."""
    a = it["a"]
    if a <= 0:
        return
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    tw = tracked(d, (1808, 200), "STAGE SEPARATION", fnt("demi", LBL_XL), AMBER + (255,), 6, "rs")
    scale_rule(d, int(1808 - tw), 214, tw, 1.0)
    tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


def render_chapter(hud: Image.Image, it: dict) -> None:
    """v22: the DAY 5 chapter card (real 37.3-40.3) as a flight-plan block, like the stat cards: the date types on in
    LBL_XL amber, the scale rule draws, the mission phase types on in LBL_M cream; v21's alpha (in 0.5 s)."""
    u, a = it["u"], it["a"]
    if a <= 0:
        return
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    x = 112
    head = "DAY 5  ·  JULY 20, 1969"
    tw = tracked(ImageDraw.Draw(Image.new("L", (8, 8))), (0, 0), head, fnt("demi", LBL_XL), 0, 5)
    tracked(d, (x, 118), type_on(head, (u - 0.05) / 0.35), fnt("demi", LBL_XL), AMBER + (255,), 5)
    scale_rule(d, x, 134, ease_out((u - 0.15) / 0.5) * max(tw, 640), 1.0)
    tracked(d, (x, 196), type_on("LUNAR MODULE EAGLE  ·  POWERED DESCENT", (u - 0.3) / 0.45), fnt("med", LBL_M),
            CREAM + (240,), 3)
    tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


# ====================================================================== v23: disclosure tags, flash-forward, end note
def render_timetag(hud: Image.Image, a: float) -> None:
    """v23: 'TIME-COMPRESSED' on a system plate under the MOCR monitor (the panel's width, y 832-890), TAG medium cream;
    alpha follows the monitor's power-on (render_crt: clamp(3a))."""
    k = clamp(a * 3)
    if k <= 0:
        return
    x0, y0, x1, y1 = timetag_box()
    legend_plate(hud, (x0, y0, x1, y1), k * 0.9)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    tracked(ImageDraw.Draw(tmp), ((x0 + x1) / 2, y1 - 11), "TIME-COMPRESSED", fnt("med", TAG),
            CREAM + (int(255 * k * 0.95),), 3, "ms")
    hud.alpha_composite(tmp)


def timetag_box() -> tuple[int, int, int, int]:
    return CRT_X, CRT_Y + CRT_H + 6, CRT_X + CRT_W, CRT_Y + CRT_H + 64


FLASH_LINES = (("4 DAYS LATER", "demi", AMBER, 120), ("THE MOON", "med", CREAM, 184))   # v23 (Codex all-out plan):
# not one date stamped over five inserts (and "JULY 20, 1969" repeats the DAY 5 card); every insert is at the Moon


def render_flashtag(hud: Image.Image, it: dict) -> None:
    """v23: the flash-forward tag (frames 94-201) in the countdown / hook slot: the amber bar, '4 DAYS LATER' (demi TAG
    amber) over 'THE MOON' (medium TAG cream). In over 0.15 s at the first insert, cut with the last one."""
    a = it["a"]
    if a <= 0:
        return
    hud.alpha_composite(Image.new("RGBA", (7, 124), AMBER + (int(230 * a),)), (112, 70))
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    for s_, face, col, yb in FLASH_LINES:
        tracked(td, (134, yb), s_, fnt(face, TAG), col + (int(255 * a),), 3, "ls")
    hud.alpha_composite(tmp)


def flashtag_box() -> tuple[int, int, int, int]:
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    w = max(tracked(d, (0, 0), s_, fnt(face, TAG), 0, 3) for s_, face, _, _ in FLASH_LINES)
    return 112, 70, int(134 + w), 194


END_LINES = (("EDITED WITH AN AI AGENT", "demi", AMBER, 516), ("ARCHIVAL NASA FOOTAGE", "med", CREAM, 584))
END_CX = 1392        # the end-card date line's centre (build.py: 'APOLLO 11 · JULY 16-24, 1969' at (1392, 420))


def render_endnote(hud: Image.Image, it: dict) -> None:
    """v23: the AI-assist disclosure on the end-title card, centred under the date line (x 1392), TAG size, the date
    line's alpha (build.py: in 83.9 + 0.5 s, out 85.15-85.5 logical = gone before frame 1891)."""
    a = it["a"]
    if a <= 0:
        return
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    for s_, face, col, yb in END_LINES:
        tracked(td, (END_CX, yb), s_, fnt(face, TAG), col + (int(255 * a),), 3, "ms")
    hud.alpha_composite(tmp)


def endnote_box() -> tuple[int, int, int, int]:
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    w = max(tracked(d, (0, 0), s_, fnt(face, TAG), 0, 3) for s_, face, _, _ in END_LINES)
    return int(END_CX - w / 2), END_LINES[0][3] - 38, int(END_CX + w / 2), END_LINES[-1][3] + 2


# ====================================================================== v23: the ascent beat (frames 524-635)
ASC_DIR = "ascent_blender_v23"
ASC: dict = {"geom": None, "map": None, "first": None, "layout": None, "report": None}
ASC_TL_X = 112
ASC_TL_ROWS = (("ASCENT · FIRST 3 MINUTES", "demi", LBL_L, AMBER, 108),
               ("HEIGHT + DISTANCE", "med", TAG, CREAM, 192),
               ("EXAGGERATED 6X", "demi", TAG, AMBER, 254),
               ("VALUES CALLED OUT", "med", LBL_M, CREAM, 306),
               ("LIVE BY NASA", "med", LBL_M, CREAM, 350))
ASC_COL_X = 1440
ASC_ROWS = (("MISSION TIME", "clock", 214, 318), ("ALTITUDE", "alt", 404, 508), ("VELOCITY", "vel", 594, 698))
ASC_VAL = 108                     # readout figures, demi (cap 72 px = 24 px at 360p)
ASC_EVT = LBL_L                   # event labels, demi amber
PAD_TUBE, PAD_RING, PAD_LIMB = 10, 10, 16      # px clearances at 1080p (glow + the comp's SEQ weave, sigma 0.9 px)
SAFE = (96, 54, 1824, 1026)


def asc_tl_box() -> tuple[int, int, int, int]:
    """The top-left plate: title (LBL_L amber + scale rule), the 6x disclosure (TAG), the source line (LBL_M)."""
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    w = max(tracked(d, (0, 0), s_, fnt(face, size), 0, 2 if i == 0 else 3)
            for i, (s_, face, size, _, _) in enumerate(ASC_TL_ROWS))
    return ASC_TL_X - 16, 62, int(ASC_TL_X + w + 18), 368


def asc_col_box() -> tuple[int, int, int, int]:
    """The readout column, sized for the widest values the beat shows (T+180 S, 43.0 NMI, 9,999 MPH)."""
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    w = max(tracked(d, (0, 0), "9,999", fnt("demi", ASC_VAL), 0, 2) + 12 + tracked(d, (0, 0), "MPH", fnt("demi", LBL_L), 0, 2),
            tracked(d, (0, 0), "MISSION TIME", fnt("demi", LBL_L), 0, 3))
    return ASC_COL_X - 4, ASC_ROWS[0][2] - 34, int(ASC_COL_X + w + 4), ASC_ROWS[-1][3] + 4


def _pt_rect(px: float, py: float, b: tuple) -> float:
    dx = max(b[0] - px, 0.0, px - b[2])
    dy = max(b[1] - py, 0.0, py - b[3])
    return math.hypot(dx, dy)


def seg_rect_dist(a: tuple, b: tuple, r: tuple) -> float:
    """Distance between segment a-b and axis-aligned rectangle r (0 if they touch)."""
    if _pt_rect(a[0], a[1], r) == 0 or _pt_rect(b[0], b[1], r) == 0:
        return 0.0
    n = max(int(math.hypot(b[0] - a[0], b[1] - a[1]) / 2.0), 1)        # 2 px sampling, exact enough at these pads
    return min(_pt_rect(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, r) for i in range(n + 1))


def clearance(box: tuple, g: dict) -> dict:
    """Clearance (px, after the pads; >0 = clear) of a box from the frame's tube, visible rings and limb."""
    tube = g["tube"]
    ct = min((seg_rect_dist(p, q, box) - max(p[2], q[2]) - PAD_TUBE for p, q in zip(tube, tube[1:])), default=1e9)
    if len(tube) == 1:
        ct = _pt_rect(tube[0][0], tube[0][1], box) - tube[0][2] - PAD_TUBE
    cr = min((max(r["bbox"][0] - box[2], box[0] - r["bbox"][2], r["bbox"][1] - box[3], box[1] - r["bbox"][3]) - PAD_RING
              for r in g["rings"] if r["visible"] and r["bbox"]), default=1e9)
    lm = g["limb"]
    cl = min((seg_rect_dist(p, q, box) - PAD_LIMB for p, q in zip(lm, lm[1:])
              if math.hypot(q[0] - p[0], q[1] - p[1]) < 200), default=1e9)
    return {"tube": round(ct, 1), "ring": round(cr, 1), "limb": round(cl, 1)}


def _evt_lines(name: str, stacked: bool) -> list[str]:
    return ["INBOARD ENGINE", "CUTOFF"] if stacked and name == "INBOARD ENGINE CUTOFF" else [name]


def _evt_size(lines: list[str]) -> tuple[float, float]:
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    w = max(tracked(d, (0, 0), s_, fnt("demi", ASC_EVT), 0, 2) for s_ in lines)
    cap = 0.67 * ASC_EVT
    return w, cap + (len(lines) - 1) * (ASC_EVT + 2)


def _candidates(rb: tuple, c: tuple, w: float, h: float) -> list[tuple[str, tuple]]:
    """Label boxes (x0, y0, x1, y1) around a ring: left, up-left, down-left, right, up-right, down-right, above, below."""
    g_ = 16
    return [("L", (rb[0] - g_ - w, c[1] - h / 2, rb[0] - g_, c[1] + h / 2)),
            ("UL", (c[0] - 8 - w, rb[1] - g_ - h, c[0] - 8, rb[1] - g_)),
            ("DL", (c[0] - 8 - w, rb[3] + g_, c[0] - 8, rb[3] + g_ + h)),
            ("R", (rb[2] + g_, c[1] - h / 2, rb[2] + g_ + w, c[1] + h / 2)),
            ("UR", (c[0] + 8, rb[1] - g_ - h, c[0] + 8 + w, rb[1] - g_)),
            ("DR", (c[0] + 8, rb[3] + g_, c[0] + 8 + w, rb[3] + g_ + h)),
            ("U", (c[0] - w / 2, rb[1] - g_ - h, c[0] + w / 2, rb[1] - g_)),
            ("D", (c[0] - w / 2, rb[3] + g_, c[0] + w / 2, rb[3] + g_ + h))]


def _boxes_apart(a: tuple, b: tuple, m: float = 12) -> bool:
    return a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1]


def asc_layout(geom: dict, frames: list[int]) -> tuple[dict, dict]:
    """Per asset frame: the event labels to draw [(name, lines, box, alpha, candidate)] and a clearance report.
    Deterministic: frames in ascending order; each event keeps its previous candidate while it stays clear, else takes
    the first clear one (single line first, then INBOARD ENGINE CUTOFF stacked). A label with no clear position is
    NOT drawn on that frame and is listed in the report (the dry-run gate requires zero such frames)."""
    fixed = [asc_tl_box(), asc_col_box()]
    prev: dict[str, str] = {}
    lay, rep = {}, {}
    for j in sorted(set(frames)):
        g = geom[str(j)]
        out, missing = [], []
        for r in g["rings"]:
            if not (r["visible"] and r["k"] > 0.002 and r["bbox"]):
                continue
            rb, c = tuple(r["bbox"]), tuple(r["center"])
            options = []
            for stacked in (False, True):
                lines = _evt_lines(r["name"], stacked)
                if stacked and len(lines) == 1:
                    continue
                w, h = _evt_size(lines)
                for key, box in _candidates(rb, c, w, h):
                    options.append((f"{key}{'2' if stacked else ''}", lines, box))
            options.sort(key=lambda o: o[0] != prev.get(r["name"]))        # stable sort: keep the last choice first
            pick = None
            for key, lines, box in options:
                if not (SAFE[0] <= box[0] and box[2] <= SAFE[2] and SAFE[1] <= box[1] and box[3] <= SAFE[3]):
                    continue
                if not all(_boxes_apart(box, fb) for fb in fixed + [o[2] for o in out]):
                    continue
                cl = clearance(box, g)
                if min(cl.values()) > 0:
                    pick = (key, lines, box, cl)
                    break
            if pick is None:
                missing.append(r["name"])
                continue
            prev[r["name"]] = pick[0]
            out.append((r["name"], pick[1], pick[2], r["k"], pick[0], pick[3]))
        lay[j] = out
        rep[j] = {"labels": [(n, cand, [round(v, 1) for v in box], cl) for n, _, box, _, cand, cl in out],
                  "missing": missing, "tl": clearance(asc_tl_box(), g), "col": clearance(asc_col_box(), g)}
    return lay, rep


def load_ascent(folder: Path, first_frame: int) -> None:
    """Load the (already validated) ascent geometry + display map and compute the layout once per build."""
    import json
    man = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    geom = json.loads((folder / "geometry.json").read_text(encoding="utf-8"))["frames"]
    dmap = man["display"]["frames"]
    lay, rep = asc_layout(geom, dmap)
    ASC.update(geom=geom, map=dmap, first=first_frame, layout=lay, report=rep)


def asc_frame(fi: int) -> int:
    return ASC["map"][fi - ASC["first"]]


def render_ascent(hud: Image.Image, it: dict) -> None:
    """v23: the ascent beat's text in the system: top-left plate (title, 6x disclosure, source line), the readout
    column (MISSION TIME / ALTITUDE / VELOCITY, v5's values for the displayed asset frame), the event labels at their
    asc_layout() positions with their rings' fade."""
    j = asc_frame(it["fi"])
    g = ASC["geom"][str(j)]
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    legend_plate(hud, asc_tl_box(), 0.85)
    for i, (s_, face, size, col, yb) in enumerate(ASC_TL_ROWS):
        w_ = tracked(d, (ASC_TL_X, yb), s_, fnt(face, size), col + (255,), 2 if i == 0 else 3, "ls")
        if i == 0:
            scale_rule(d, ASC_TL_X, yb + 12, w_, 1.0)
    for lab, key, yl, yv in ASC_ROWS:
        tracked(d, (ASC_COL_X, yl), lab, fnt("demi", LBL_L), AMBER + (255,), 3, "ls")
        num, unit = g["values"][key].rsplit(" ", 1)
        w_ = tracked(d, (ASC_COL_X, yv), num, fnt("demi", ASC_VAL), CREAM + (255,), 2, "ls")
        tracked(d, (ASC_COL_X + w_ + 12, yv), unit, fnt("demi", LBL_L), CREAM + (235,), 2, "ls")
    hud.alpha_composite(tmp)
    for name, lines, box, k, _, _ in ASC["layout"][j]:
        lt = Image.new("RGBA", hud.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lt)
        cap = 0.67 * ASC_EVT
        for n_, s_ in enumerate(lines):
            tracked(ld, (box[0], box[1] + cap + n_ * (ASC_EVT + 2)), s_, fnt("demi", ASC_EVT), AMBER + (255,), 2, "ls")
        lt.putalpha(Image.fromarray((np.asarray(lt.getchannel("A"), np.float32) * k).astype(np.uint8)))
        hud.alpha_composite(lt)


GRAIN_SIGMA = 4.0     # levels (0-255) at mid-grey before the grade; tuned in the dry run (DESIGN.md v23 section)


def globe_grain(fr: np.ndarray, fi: int) -> np.ndarray:
    """v23: 16 mm-matched grain on the CG globe (the render is clean; the 16 mm around it is not). Monochrome, 2 px
    clumps (half-res noise, bilinear up, like the comp's own grain), weighted to the mid-tones as film grain is,
    masked off black space (so the stars and the overlay are untouched). Seeded per output frame (deterministic)."""
    rng = np.random.default_rng(23000 + fi)
    n = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(n).resize((W, H), Image.Resampling.BILINEAR), np.float32)
    lum = fr.astype(np.float32).mean(axis=2) / 255.0
    wgt = np.clip((lum * 255.0 - 6.0) / 20.0, 0, 1) * (0.35 + 2.6 * lum * (1 - lum))
    return np.clip(fr.astype(np.float32) + (n * wgt * GRAIN_SIGMA)[..., None], 0, 255).astype(np.uint8)


# ====================================================================== render + film pass
def render(hf: HudFrame) -> Image.Image | None:
    if not hf.items:
        return None
    hud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    it = hf.items
    if "topgrad" in it:            # v22: the cold-open / chapter top gradient, under the labels (as in v21's layer)
        render_topgrad(hud, it["topgrad"])
    if "countdown" in it:
        render_countdown(hud, it["countdown"])
    if "hook" in it:
        render_hook(hud, it["hook"])
    if "archive" in it:
        render_archive(hud, it["archive"])
    if "flashtag" in it:           # v23
        render_flashtag(hud, it["flashtag"])
    if "ascent" in it:             # v23
        render_ascent(hud, it["ascent"])
    if "endnote" in it:            # v23
        render_endnote(hud, it["endnote"])
    if "stage" in it:
        render_stage(hud, it["stage"])
    if "chapter" in it:
        render_chapter(hud, it["chapter"])
    if "thrust" in it:
        render_thrust(hud, it["thrust"])
    if "speed" in it:
        render_speed(hud, it["speed"])
    if "distance" in it:
        render_distance(hud, it["distance"])
    if "dsky" in it:
        render_dsky(hud, it["dsky"], hf.fi)
    if "contact" in it:            # v22: drawn before the monitor (v21: on the graphics layer above it)
        render_contact(hud, it["contact"])
    if "fuel" in it:
        render_crt(hud, it["fuel"], it.get("descent"), hf.fi)
        render_timetag(hud, it["fuel"]["a"])          # v23: the disclosure under the monitor
    return hud


def composite(f: np.ndarray, hf: HudFrame) -> np.ndarray:
    """Film pass + over (unchanged from v20): gate weave (shared per-frame sub-pixel offset), 0.6 px softening (the
    16mm's resolution), halation on the graphics' own highlights (the comp's footage recipe: lum 170-255, 1/8-res
    blur, warm 60/22/8). f: the frame (float32 HxWx3, after the footage halation / vignette / glitch / flashes);
    returns f."""
    hud = render(hf)
    if hud is None:
        return f
    bb = hud.getchannel("A").getbbox()
    if not bb:
        return f
    m = 24
    x0, y0, x1, y1 = max(bb[0] - m, 0), max(bb[1] - m, 0), min(bb[2] + m, W), min(bb[3] + m, H)
    crop = hud.crop((x0, y0, x1, y1)).convert("RGBa")
    r = np.random.default_rng(31000 + hf.fi)
    dx, dy = (float(v) for v in r.normal(0, 0.32, 2))
    crop = crop.transform(crop.size, Image.Transform.AFFINE, (1, 0, -dx, 0, 1, -dy), Image.Resampling.BILINEAR)
    crop = crop.filter(ImageFilter.GaussianBlur(0.6))
    pm = np.asarray(crop, np.float32)                  # premultiplied RGB + alpha
    al = pm[..., 3:] / 255.0
    reg = f[y0:y1, x0:x1]
    reg = reg * (1 - al) + pm[..., :3]
    lum = pm[..., :3].mean(axis=2)
    hi = np.clip((lum - 170) / 85, 0, 1)
    if hi.max() > 0:
        hh, ww = hi.shape
        sm = Image.fromarray((hi * 255).astype(np.uint8)).resize((max(ww // 8, 1), max(hh // 8, 1)),
                                                                  Image.Resampling.BILINEAR)
        sm = sm.filter(ImageFilter.GaussianBlur(4)).resize((ww, hh), Image.Resampling.BILINEAR)
        reg = reg + np.asarray(sm, np.float32)[..., None] / 255.0 * np.array([60, 22, 8], np.float32) * 0.7
    f[y0:y1, x0:x1] = reg
    return f
