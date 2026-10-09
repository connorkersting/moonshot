"""MOONSHOT v20 HUD: authentic 1969 hardware (exports/moonshot/BRIEF_v20_HUD.md, work/hud_v20/DESIGN.md).

build.py (patched by patch_v20.py) keeps every value computation; its Gfx methods hand the values to a HudFrame
(one per output frame) instead of drawing, and stage_comp calls composite(), which renders the elements and gives them
a film pass (gate weave, softening, halation like the footage's) before the captions layer goes on top. The comp's
grain then covers everything, as before.

Elements:
  dsky      the LM DSKY upper panel: 2 x 7 annunciator lamps (white status / amber caution, LM legends), the green
            electroluminescent display (COMP ACTY, PROG / VERB / NOUN plates, three signed 5-digit registers with
            separator bars), slanted 7-segment digits with the unlit segments faintly visible, EL bloom and flicker,
            1-2 frames of segment persistence, incandescent PROG lamp rise.
  crt       the MOCR console readout (bingo counter + Aldrin's callouts on one monitor): OCR-A (1968) data face,
            blue-white P4-like phosphor, bloom, scanlines, raster draw-on, phosphor flare / ghost on a redraw.
  thrust, speed, distance
            flight-plan / press-kit data blocks: Franklin Gothic condensed legends, an engineering scale rule,
            mechanical drum counters (Veeder-Root style windows, cylinder shading, carry roll).
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
EL_OFF = (24, 36, 28)                                 # unlit EL segment, faintly visible
EL_PLATE_OFF = (20, 30, 23)
AMBER_LAMP = np.array([255, 168, 52], np.float32)     # caution lamp lit
LAMP_OFF = (50, 52, 50)
PHOS = np.array([214, 232, 255], np.float32)          # MOCR phosphor (blue-white)
PHOS_GLOW = np.array([110, 160, 255], np.float32)
CREAM = (238, 234, 222)                               # printed ink (stat cards)
AMBER = (255, 176, 64)                                # house amber (legends)
GREY = (176, 178, 172)

DSKY_PROG_MODE = "63"     # P63 (braking phase) was running at the 1202 (ALSJ 102:38: P64 only from 102:41:32); "" blanks it


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
    """The v20 HUD items of one output frame (kind -> the values build.py computed)."""

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


def render_dsky(hud: Image.Image, it: dict, fi: int) -> None:
    u, right, a = it["u"], it["right"], it["a"]
    if a <= 0:
        return
    sc = 0.85 if right else 1.0
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
    fx0, fy0, fx1, fy1 = geo["face"]
    fw, fh = fx1 - fx0, fy1 - fy0
    if right:      # v20: over Mission Control, right side, bottom 700 (caption box top >= 892)
        ox, oy = 1808 - fw, 384
    else:
        ox, oy = 112, 70
    hud.alpha_composite(img, (int(round(ox - DM)), int(round(oy - DM))))
    # legends (printed, outside the hardware): what it is; what the code means (from u 1.0, as v19)
    hd = ImageDraw.Draw(hud)
    la = a * clamp((u - 1.0) / 0.4)
    yb = oy + fh
    if right:
        plate = Image.new("RGBA", (int(fw + 40), 104), (0, 0, 0, int(150 * a)))
        hud.alpha_composite(plate, (int(1808 - fw - 20), int(yb + 4)))
    xa, an = (1808, "rs") if right else (ox, "ls")
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    td = ImageDraw.Draw(tmp)
    tracked(td, (xa, yb + 40), "LM GUIDANCE COMPUTER", fnt("med", 28), GREY + (int(235 * a),), 3, an)
    if la > 0:
        tracked(td, (xa, yb + 88), "1202 = COMPUTER OVERLOADED", fnt("demi", 44), AMBER + (int(255 * la),), 3, an)
    hud.alpha_composite(tmp)
    del hd


# ====================================================================== MOCR CRT
CRT_X, CRT_Y, CRT_W, CRT_H = 1300, 90, 520, 658   # v20b: x 1300-1820 (CONTACT insert ends 1296, title safe 1824), y to 748
REVERSE_AT = 30.0       # v20b: the displayed bingo value at or below this is drawn in reverse video (v19: red from 30.0)


def reverse_video(fu: dict) -> bool:
    """Reverse video while the DISPLAYED counter is <= 30.0 s and the counter runs (at contact it reverts, as v19's
    red turned white)."""
    return (not fu["held"]) and float(f"{fu['rem']:04.1f}") <= REVERSE_AT + 1e-9
BZ = 14


@lru_cache(None)
def crt_static() -> tuple[Image.Image, np.ndarray]:
    """Bezel + screen face (dark blue-black, centre slightly brighter, raster lines)."""
    im = Image.new("RGBA", (CRT_W, CRT_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CRT_W - 1, CRT_H - 1], radius=16, fill=(38, 40, 42, 255), outline=(20, 21, 22, 255),
                        width=3)
    d.line([(14, 2), (CRT_W - 14, 2)], fill=(74, 76, 78, 255), width=2)
    sw, sh = CRT_W - 2 * BZ, CRT_H - 2 * BZ
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    r = np.hypot((xx - sw / 2) / (sw / 2), (yy - sh / 2) / (sh / 2))
    face = np.zeros((sh, sw, 3), np.float32)
    face[:] = np.array([10, 13, 17], np.float32)
    face += (np.clip(1 - r, 0, 1) ** 1.5)[..., None] * np.array([7, 9, 12], np.float32)
    face[::3] *= 0.8
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=22, fill=255)
    scr = Image.fromarray(np.clip(face, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    scr.putalpha(mask)
    im.alpha_composite(scr, (BZ, BZ))
    scan = np.ones((sh, 1), np.float32)
    scan[2::3] = 0.62
    return im, scan


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


def render_crt(hud: Image.Image, fu: dict, de: dict | None, fi: int) -> None:
    """v20b: type 1.3x (big values 82 -> 107 px, labels >= 32 px so they read at 360p), panel 520 x 658 (the width is
    capped by the CONTACT insert's right edge 1296 and title safe 1824, so it grows down). 'LM DESCENT' dropped;
    'SEC TO BINGO / LAND OR ABORT' on two lines. Urgency in the CRT's own vocabulary: from 30.0 s (v19's red
    threshold) the counter is drawn in REVERSE VIDEO, steady (no blink), back to normal at contact (v19: white)."""
    bez, scan = crt_static()
    a = fu["a"]
    if a <= 0:
        return
    sw, sh = CRT_W - 2 * BZ, CRT_H - 2 * BZ
    ink = Ink(sw, sh)
    held, rem, label = fu["held"], fu["rem"], fu["label"]
    L = 22
    f_lab, f_big, f_mid, f_unit = fnt("ocr", 32), fnt("ocr", 107), fnt("ocr", 52), fnt("ocr", 34)
    ink.text((L, 44), label, f_lab, 1.0 if held else 0.9)
    ink.rect([L, 58, sw - L, 60], 0.35)
    ink.text((L, 98), "SEC TO BINGO", f_lab, 0.9)
    ink.text((L, 134), "LAND OR ABORT", f_lab, 0.9)
    val = f"{rem:04.1f}"
    if reverse_video(fu):
        m = Image.new("L", (sw, sh), 0)
        md = ImageDraw.Draw(m)
        md.text((L, 246), val, font=f_big, fill=255, anchor="ls")
        bb = md.textbbox((L, 246), val, font=f_big, anchor="ls")
        ink.rect([L - 10, bb[1] - 10, bb[2] + 10, bb[3] + 10], 0.92)       # the solid phosphor block
        ink.a[np.asarray(m) > 96] = 0.03                                    # dark digits knocked out of it
        w_ = bb[2] - L
    else:
        w_ = ink.text((L, 246), val, f_big, 1.0)
    ink.text((L + w_ + 22, 246), "SEC", f_unit, 0.85)
    # bingo gauge: 30 ticks, 2 s each (the v19 bar's 60 s full scale)
    n = rem / 2.0
    for k in range(30):
        x = L + k * 15
        i = 1.0 if k + 1 <= n else (0.18 + 0.82 * (n - k) if k < n else 0.16)
        ink.rect([x, 262, x + 10, 284], i)
    ink.rect([L, 300, sw - L, 301], 0.3)
    if de is not None:
        da = de["a"]
        rows = Ink(sw, sh)
        rows.text((L, 340), "ALDRIN CALLOUTS", f_lab, 0.9)
        if de["held"]:
            rows.text((L, 448), "CONTACT", fnt("ocr", 98), 1.0)
        else:
            k = int(math.floor((fu["t"] - de["t_step"]) * FPS + 1e-6)) if de["t_step"] > 0 else 99
            i_new = {0: 0.6, 1: 1.35, 2: 1.15, 3: 1.05}.get(k, 1.0) if de["fresh"] else 1.0
            if de["fresh"] and k <= 1 and de["prev_alt"] is not None:      # the old value persists on the phosphor
                rows.text((L + 96, 448), f"{de['prev_alt']:>3}", f_big, 0.45 if k == 0 else 0.12)
            wv = rows.text((L + 96, 448), f"{de['alt']:>3}", f_big, i_new)
            rows.text((L + 96 + wv + 18, 448), "FT", f_unit, 0.85)
            rows.text((L, 448), "ALT", f_unit, 0.85)
        ri = 0.35 if de["held"] else 1.0
        down = de["down"]
        rows.text((L, 506), "DOWN", f_unit, 0.85 * ri)
        rows.text((L + 112, 506), f"{down:.1f}" if down is not None else "-", f_mid, ri)
        rows.text((L + 232, 506), "FT/S", f_unit, 0.85 * ri)
        if de["fwd"] is not None and not de["held"]:
            rows.text((L, 560), "FWD", f_unit, 0.85)
            rows.text((L + 112, 560), f"{de['fwd']:g}", f_mid, 1.0)
            rows.text((L + 232, 560), "FT/S", f_unit, 0.85)
        rows.text((L, 610), "TIME-COMPRESSED", f_lab, 0.75)
        # raster draw-on of the callout block (55.75 + 0.3 s), not a crossfade
        ry = 304 + (sh - 304) * ease_out(da)
        rows.a[int(ry):] = 0
        ink.a = np.maximum(ink.a, rows.a)
    # power-on: the whole screen draws top to bottom with the beam line at the edge
    ry = sh * ease_out(a)
    ink.a[int(ry):] = 0
    if a < 1:
        ink.a[max(0, int(ry) - 2):int(ry)] = np.maximum(ink.a[max(0, int(ry) - 2):int(ry)], 0.5)
    # phosphor: core + bloom, scanlines, faint refresh shimmer
    shimmer = 0.97 + 0.03 * np.random.default_rng(7000 + fi).random()
    core = ink.a * scan * shimmer
    cimg = Image.fromarray(np.clip(core * 180, 0, 255).astype(np.uint8), "L")
    b1 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(2.2)), np.float32) / 180
    b2 = np.asarray(cimg.filter(ImageFilter.GaussianBlur(9)), np.float32) / 180
    face = np.asarray(bez.crop((BZ, BZ, BZ + sw, BZ + sh)), np.float32)
    rgb = face[..., :3] + np.minimum(core, 1.0)[..., None] * PHOS + np.maximum(core - 1.0, 0)[..., None] * PHOS * 0.6 \
        + (b1 * 0.45)[..., None] * PHOS_GLOW + (b2 * 0.35)[..., None] * PHOS_GLOW
    out = np.dstack([np.clip(rgb, 0, 255), face[..., 3:]]).astype(np.uint8)
    panel = bez.copy()
    panel.paste(Image.fromarray(out, "RGBA"), (BZ, BZ))
    pa = np.asarray(panel, np.float32)
    pa[..., 3] *= clamp(a * 3) * 0.97
    hud.alpha_composite(Image.fromarray(pa.astype(np.uint8), "RGBA"), (CRT_X, CRT_Y))


# ====================================================================== stat cards: drum counters
@lru_cache(None)
def drum_strip(h: int, w: int) -> np.ndarray:
    """Digits 0..9,0 stacked (cell h); float 0..1 ink."""
    f = fnt("demi", int(round(h * 1.02)))
    im = Image.new("L", (w, h * 11), 0)
    d = ImageDraw.Draw(im)
    for k in range(11):
        d.text((w / 2, k * h + h * 0.52), str(k % 10), font=f, fill=255, anchor="mm")
    return np.asarray(im, np.float32) / 255.0


@lru_cache(None)
def cylinder(h: int) -> np.ndarray:
    v = (np.arange(h, dtype=np.float32) + 0.5) / h
    return (0.18 + 0.82 * np.sin(np.pi * v) ** 0.7)[:, None]


def wheel(hud: Image.Image, x: int, y: int, w: int, h: int, p: float, alpha: float) -> None:
    """One counter wheel: a dark window with a bevel; the digit drum at position p (digit = p mod 10, rolls up)."""
    if alpha <= 0:
        return
    win = Image.new("RGBA", (w + 8, h + 8), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    d.rectangle([0, 0, w + 7, h + 7], fill=(10, 10, 9, int(225 * alpha)), outline=(150, 146, 136, int(220 * alpha)),
                width=2)
    hud.alpha_composite(win, (x - 4, y - 4))
    strip = drum_strip(h, w)
    off = int(round((p % 10) * h))
    ink = strip[off:off + h] * cylinder(h)
    rgba = np.zeros((h, w, 4), np.uint8)
    shade = cylinder(h)
    rgba[..., :3] = (np.array(CREAM, np.float32)[None, None] * (0.55 + 0.45 * shade[..., None])).astype(np.uint8)
    rgba[..., 3] = np.clip(ink * 255 * alpha, 0, 255).astype(np.uint8)
    hud.alpha_composite(Image.fromarray(rgba, "RGBA"), (x, y))


def odometer_positions(v: float, n: int) -> list[float]:
    """Wheel positions, most significant first, for a counter of n wheels whose tens wheel turns continuously
    (units wheel fixed: the values are whole tens) and higher wheels carry over the last tenth of the lower turn."""
    pos = []
    for k in range(n - 1, -1, -1):
        if k == 0:
            pos.append(0.0)
            continue
        q = v / 10 ** k
        if k == 1:
            pos.append(q)
            continue
        lower = (v / 10 ** (k - 1)) % 10
        pos.append(math.floor(q + 1e-9) + clamp(lower - 9))
    return pos


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
    tracked(d, (x, 352 + dy), type_on("LIFTOFF THRUST", (u - 0.05) / 0.3), fnt("demi", 42), AMBER + (255,), 5)
    scale_rule(d, x, 368 + dy, ease_out((u - 0.2) / 0.6) * 588, 1.0)
    hgt, wd = 150, 96
    wa = clamp((u - 0.1) / 0.15)
    e = ease_out((u - 0.15) / 0.75)
    wheel(tmp, x, 400 + dy, wd, hgt, 7 * e, wa)                       # 7 rolls up from 0
    d.ellipse([x + wd + 12, 400 + dy + hgt - 26, x + wd + 30, 400 + dy + hgt - 8], fill=CREAM + (int(255 * wa),))
    wheel(tmp, x + wd + 42, 400 + dy, wd, hgt, 5 - 15 * (1 - e), wa)   # .5: one extra turn
    tracked(d, (x + 2 * wd + 70, 400 + dy + hgt - 12), "MILLION", fnt("demi", 150), CREAM + (int(255 * wa),), 2)
    tracked(d, (x, 600 + dy), type_on("POUNDS  ·  FIVE F-1 ENGINES", (u - 0.35) / 0.35), fnt("med", 46),
            CREAM + (230,), 3)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


def radial_scrim(cx: float, cy: float, rx: float, ry: float, amax: float, a: float) -> Image.Image:
    g = np.zeros((H, W, 4), np.uint8)
    yy, xx = np.mgrid[0:H, 0:W]
    g[..., 3] = (np.clip(amax * (1 - np.hypot((xx - cx) / rx, (yy - cy) / ry)), 0, amax) * a).astype(np.uint8)
    return Image.fromarray(g, "RGBA")


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
    tracked(d, (x, 700), type_on("SPEED AT TRANSLUNAR INJECTION CUTOFF", (u - 0.15) / 0.45), fnt("demi", 42),
            AMBER + (255,), 4)
    scale_rule(d, x, 716, ease_out((u - 0.2) / 0.6) * 840, 1.0)
    hgt, wd, gp = 168, 104, 10
    pos = odometer_positions(vc, 5)
    xx_ = x
    for k, p in enumerate(pos):
        wheel(tmp, xx_, 748, wd, hgt, p, 1.0)
        xx_ += wd + gp
        if k == 1:      # the printed thousands comma between the windows
            d.polygon([(xx_ + 2, 748 + hgt - 22), (xx_ + 18, 748 + hgt - 22), (xx_ + 8, 748 + hgt + 14),
                       (xx_ - 2, 748 + hgt + 14)], fill=CREAM + (255,))
            xx_ += 26
    tracked(d, (xx_ + 18, 748 + hgt - 10), "MPH", fnt("demi", 190), CREAM + (255,), 4)
    tracked(d, (124, 1004), type_on("FROM 17,400 IN EARTH ORBIT", (u - 0.3) / 0.4), fnt("med", 40),
            (200, 206, 212, int(255 * 0.9)), 4)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


def render_distance(hud: Image.Image, it: dict) -> None:
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
    tracked(d, (x, 700), type_on("ABOUT", (u - 0.05) / 0.2), fnt("demi", 52), AMBER + (255,), 5)
    scale_rule(d, x, 714, ease_out((u - 0.1) / 0.5) * 700, 1.0)
    hgt, wd, gp = 130, 82, 8
    e = ease_out((u - 0.1) / 0.6)
    pos = odometer_positions(240000 * e, 6)
    pos = [p if e < 1 else float(int(c)) for p, c in zip(pos, "240000")]
    xx_ = x
    for k, p in enumerate(pos):
        wheel(tmp, xx_, 740, wd, hgt, p, 1.0)
        xx_ += wd + gp
        if k == 2:
            d.polygon([(xx_ + 2, 740 + hgt - 18), (xx_ + 15, 740 + hgt - 18), (xx_ + 7, 740 + hgt + 11),
                       (xx_ - 2, 740 + hgt + 11)], fill=CREAM + (255,))
            xx_ += 22
    tracked(d, (x, 942), type_on("MILES TO THE MOON", (u - 0.25) / 0.4), fnt("demi", 56), AMBER + (255,), 5)
    if a < 1:
        tmp.putalpha(Image.fromarray((np.asarray(tmp.getchannel("A"), np.float32) * a).astype(np.uint8)))
    hud.alpha_composite(tmp)


# ====================================================================== render + film pass
def render(hf: HudFrame) -> Image.Image | None:
    if not hf.items:
        return None
    hud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    it = hf.items
    if "thrust" in it:
        render_thrust(hud, it["thrust"])
    if "speed" in it:
        render_speed(hud, it["speed"])
    if "distance" in it:
        render_distance(hud, it["distance"])
    if "dsky" in it:
        render_dsky(hud, it["dsky"], hf.fi)
    if "fuel" in it:
        render_crt(hud, it["fuel"], it.get("descent"), hf.fi)
    return hud


def composite(f: np.ndarray, hf: HudFrame) -> np.ndarray:
    """Film pass + over: gate weave (shared per-frame sub-pixel offset), 0.6 px softening (the 16mm's resolution),
    halation on the graphics' own highlights (the comp's footage recipe: lum 170-255, 1/8-res blur, warm 60/22/8).
    f: the frame (float32 HxWx3, after the footage halation / vignette / glitch / flashes); returns f."""
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
