"""v26 disclosure diet: the director (2026-10-08 ~18:55): "maybe make the disclosures like trajectory schematic not to
scale in any clips smaller and not so important/takes so much space on the screen if it doesnt add anything to the vid".
Applied on top of polish_v24 + polish_v26 when build.py's V26_DISCLOSURE = True. hud_v23.py, hud_v25.py, polish_v24.py
and polish_v26.py are unchanged, so V26_DISCLOSURE = False draws the previous overlays exactly.

ONE quiet footnote style for every disclosure (FOOT_*): Franklin Medium Cond 40 (cap 27 px at 1080p = 9 px at 360p;
v23's TAG 56 was 37.5 / 12.5), cream at 75 % alpha, tracked 3 like the system's medium lines, one line, NO plate,
bezel or box. A soft local shadow (the glyph mask blurred 6 px, black, peak 0.9: a dark halo, no edge) only where the footage is bright behind
the slot (measured: the archive slot, p95 luminance 0.98 on the staging film; the slot under the MOCR monitor, 0.74).

  (1) hud_v25 'TRAJECTORY SCHEMATIC · NOT TO SCALE' (frames 741-793): footnote, top-left slot (x 112, baseline 100),
      no plate, no shadow (black space behind it). Same alpha curve.
  (2) hud_v23 'ARCHIVE: OTHER SATURN V FLIGHT' (frames 636-714): footnote, the same slot, no plate, soft shadow.
  (3) hud_v23 'TIME-COMPRESSED' (the MOCR section, 1174-1349): footnote centred under the monitor (baseline 864,
      28 px under the housing), no plate, soft shadow; alpha follows the monitor's power-on as before.
  (4) the ascent top-left block (frames 524-635): the section title 'ASCENT · FIRST 3 MINUTES' keeps its style (LBL_L
      demi amber + scale rule, same position); the four disclosure rows become ONE footnote line under the rule
      (ASC_NOTE); the plate goes. asc_tl_box() is the block's new extent (title + rule + footnote), still the fixed box
      asc_layout() keeps the event labels clear of, so the layout gates still apply.
      ASC_NOTE is 'EXAGGERATED 6X · NASA VALUES' (569 px), not the brief's example 'HEIGHT + DISTANCE EXAGGERATED 6X ·
      VALUES AS CALLED BY NASA' (1,173 px): the Earth limb leaves the top-left block at most x 694 (clearance after the
      16 px limb pad, every displayed frame), i.e. <= 574 px of footnote at this size; no other clear band in the frame
      is wider than ~890 px. Any other wording <= 574 px drops in via ASC_NOTE.
  (5) the end card (1853-1890): the two lines become quiet footnote lines centred under the date line (baselines 494
      and 540). One line ('EDITED WITH AN AI AGENT · ARCHIVAL NASA FOOTAGE', 923 px) would run past the title-safe edge
      (x 931-1854 at centre 1392) and outspan the date line. Same alpha (gone before 1891).
Not disclosures, untouched: the flash-forward tag, MAX Q / INBOARD ENGINE CUTOFF, the readouts, the TLI and distance
cards, the captions.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import hud_v23
import hud_v25
import polish_v24
from hud_v23 import CREAM, fnt, tracked

FOOT_FACE, FOOT_SIZE, FOOT_TRACK, FOOT_ALPHA = "med", 40, 3, 0.75
SHADOW_BLUR, SHADOW_GAIN, SHADOW_PEAK = 6, 4.0, 0.9    # dry run 1 (5, 1.8, 0.6) measured 1.1-1.3:1 on the bright frames
SLOT_X, SLOT_BASE = 112, 100          # the top-left tag slot (trajectory, archive)
TIME_BASE = 864                       # under the MOCR housing (y 826): cap top 837
ASC_NOTE = "EXAGGERATED 6X · NASA VALUES"
ASC_NOTE_BASE = 168                   # title baseline 108, its scale rule at 120; footnote cap top 141
END_BASES = (494, 540)                # date line 'APOLLO 11 · JULY 16-24, 1969' centred at y 420
BOX_PAD = 8                           # gate boxes: the ink box + 8 px (the shadow's visible reach)
_APPLIED: list[bool] = []


def _cap() -> int:
    return round(0.67 * FOOT_SIZE)


def _w(s: str) -> float:
    return tracked(ImageDraw.Draw(Image.new("L", (8, 8))), (0, 0), s, fnt(FOOT_FACE, FOOT_SIZE), 0, FOOT_TRACK)


def footnote(hud: Image.Image, xy: tuple, s: str, a: float, anchor: str = "ls", shadow: bool = False) -> None:
    """The one footnote: medium, cream at FOOT_ALPHA * a, tracked, no plate; optional very soft local shadow."""
    if a <= 0:
        return
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    tracked(ImageDraw.Draw(tmp), xy, s, fnt(FOOT_FACE, FOOT_SIZE), CREAM + (int(255 * a * FOOT_ALPHA),), FOOT_TRACK,
            anchor)
    if shadow:
        m = np.asarray(tmp.getchannel("A"), np.float32) / 255.0
        bb = tmp.getchannel("A").getbbox()
        if bb:
            x0, y0 = max(bb[0] - 24, 0), max(bb[1] - 24, 0)
            x1, y1 = min(bb[2] + 24, hud.width), min(bb[3] + 24, hud.height)
            sub = Image.fromarray((m[y0:y1, x0:x1] * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(SHADOW_BLUR))
            sa = np.clip(np.asarray(sub, np.float32) / 255.0 * SHADOW_GAIN, 0, 1) * SHADOW_PEAK * a
            sh = np.zeros((y1 - y0, x1 - x0, 4), np.uint8)
            sh[..., 3] = (sa * 255).astype(np.uint8)
            hud.alpha_composite(Image.fromarray(sh, "RGBA"), (x0, y0))
    hud.alpha_composite(tmp)


def _box(x: float, base: float, w: float, anchor: str = "l") -> tuple[int, int, int, int]:
    x0 = x - w / 2 if anchor == "m" else x
    return (int(x0 - BOX_PAD), int(base - _cap() - BOX_PAD), int(x0 + w + BOX_PAD), int(base + BOX_PAD))


# (1) trajectory schematic label (hud_v25)
def label_box() -> tuple[int, int, int, int]:
    return _box(SLOT_X, SLOT_BASE, _w(hud_v25.LABEL_TEXT))


def render_label(hud: Image.Image, fi: int) -> None:
    footnote(hud, (SLOT_X, SLOT_BASE), hud_v25.LABEL_TEXT, hud_v25.label_alpha(fi))


# (2) archive tag (hud_v23)
def archive_box() -> tuple[int, int, int, int]:
    return _box(SLOT_X, SLOT_BASE, _w(hud_v23.ARCHIVE_TEXT))


def render_archive(hud: Image.Image, it: dict) -> None:
    footnote(hud, (SLOT_X, SLOT_BASE), hud_v23.ARCHIVE_TEXT, it["a"], shadow=True)


# (3) TIME-COMPRESSED under the MOCR monitor
def _time_cx() -> float:
    return hud_v23.CRT_X + hud_v23.CRT_W / 2


def timetag_box() -> tuple[int, int, int, int]:
    return _box(_time_cx(), TIME_BASE, _w("TIME-COMPRESSED"), "m")


def render_timetag(hud: Image.Image, a: float) -> None:
    footnote(hud, (_time_cx(), TIME_BASE), "TIME-COMPRESSED", hud_v23.clamp(a * 3), "ms", shadow=True)


# (4) the ascent top-left block
def asc_tl_box() -> tuple[int, int, int, int]:
    """Title (LBL_L demi, tracked 2) + scale rule + the footnote line; x from 96 (v23's plate edge, SAFE x0)."""
    d = ImageDraw.Draw(Image.new("L", (8, 8)))
    s0, face0, size0, _, _ = hud_v23.ASC_TL_ROWS[0]
    w = max(tracked(d, (0, 0), s0, fnt(face0, size0), 0, 2), _w(ASC_NOTE))
    return hud_v23.ASC_TL_X - 16, 62, int(hud_v23.ASC_TL_X + w + BOX_PAD), ASC_NOTE_BASE + BOX_PAD


def render_ascent(hud: Image.Image, it: dict) -> None:
    """hud_v23.render_ascent with the top-left block as title + rule + one footnote, no plate. Readouts and event
    labels: hud_v23's code, verbatim."""
    h = hud_v23
    j = h.asc_frame(it["fi"])
    g = h.ASC["geom"][str(j)]
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)
    s0, face0, size0, col0, yb0 = h.ASC_TL_ROWS[0]
    w_ = tracked(d, (h.ASC_TL_X, yb0), s0, fnt(face0, size0), col0 + (255,), 2, "ls")
    h.scale_rule(d, h.ASC_TL_X, yb0 + 12, w_, 1.0)
    for lab, key, yl, yv in h.ASC_ROWS:
        tracked(d, (h.ASC_COL_X, yl), lab, fnt("demi", h.LBL_L), h.AMBER + (255,), 3, "ls")
        num, unit = g["values"][key].rsplit(" ", 1)
        w_ = tracked(d, (h.ASC_COL_X, yv), num, fnt("demi", h.ASC_VAL), CREAM + (255,), 2, "ls")
        tracked(d, (h.ASC_COL_X + w_ + 12, yv), unit, fnt("demi", h.LBL_L), CREAM + (235,), 2, "ls")
    hud.alpha_composite(tmp)
    footnote(hud, (h.ASC_TL_X, ASC_NOTE_BASE), ASC_NOTE, 1.0)
    for name, lines, box, k, _, _ in h.ASC["layout"][j]:
        lt = Image.new("RGBA", hud.size, (0, 0, 0, 0))
        ld = ImageDraw.Draw(lt)
        cap = 0.67 * h.ASC_EVT
        for n_, s_ in enumerate(lines):
            tracked(ld, (box[0], box[1] + cap + n_ * (h.ASC_EVT + 2)), s_, fnt("demi", h.ASC_EVT), h.AMBER + (255,), 2,
                    "ls")
        lt.putalpha(Image.fromarray((np.asarray(lt.getchannel("A"), np.float32) * k).astype(np.uint8)))
        hud.alpha_composite(lt)


# (5) the end card
END_TEXT = ("EDITED WITH AN AI AGENT", "ARCHIVAL NASA FOOTAGE")


def endnote_box() -> tuple[int, int, int, int]:
    w = max(_w(s) for s in END_TEXT)
    return (int(hud_v23.END_CX - w / 2 - BOX_PAD), int(END_BASES[0] - _cap() - BOX_PAD),
            int(hud_v23.END_CX + w / 2 + BOX_PAD), int(END_BASES[-1] + BOX_PAD))


def render_endnote(hud: Image.Image, it: dict) -> None:
    for s, yb in zip(END_TEXT, END_BASES):
        footnote(hud, (hud_v23.END_CX, yb), s, it["a"], "ms")


def apply() -> None:
    """Call once, after polish_v26.apply() and before hud_v23.load_ascent computes the ascent layout."""
    assert not _APPLIED and hud_v23.render_archive.__module__ == "hud_v23", "polish_v26b already applied"
    assert hud_v23.type_on is polish_v24._type_on, "apply polish_v24 (and polish_v26) first"
    assert hud_v23.ASC["layout"] is None, "apply before the ascent layout is computed (validate_assets)"
    _APPLIED.append(True)
    hud_v25.render_label = render_label
    hud_v25.label_box = label_box
    hud_v23.render_archive = render_archive
    hud_v23.archive_box = archive_box
    hud_v23.render_timetag = render_timetag
    hud_v23.timetag_box = timetag_box
    hud_v23.asc_tl_box = asc_tl_box
    hud_v23.render_ascent = render_ascent
    hud_v23.render_endnote = render_endnote
    hud_v23.endnote_box = endnote_box
