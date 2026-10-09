"""v27 fixes: Fable's v26 review (exports/moonshot/qc/v26/fable_editor.json), overlay only, on top of polish_v26b when
build.py's V27_FIXES = True. hud_v23.py, hud_v25.py and polish_v24/v26/v26b are unchanged, so V27_FIXES = False draws
v26 exactly.

  (1) bright-frame legibility: ARCHIVE (636-714, over the separation plume) and TIME-COMPRESSED (1174-1349, over the
      landing dust) get a tight soft LOCAL scrim behind the glyphs: a rounded box SCRIM_PAD px beyond the ink, blurred
      SCRIM_BLUR px, black. Its alpha is set per frame from the measured local background (the composite's own frame,
      before the HUD): the smallest alpha in 0..SCRIM_MAX whose predicted text-vs-surround contrast reaches
      SCRIM_TARGET. On dark frames it is 0 (the v26 footnote exactly). It rises at once and releases by SCRIM_RELEASE per
      frame, so it never flickers with the grain. hud_v23.composite is wrapped to measure; nothing else in it changes.
  (2) caption out-point: the cut to the end plate is frame 1812 (v26 outro, 75.50 s), so 'one giant leap for mankind.'
      ended 10 frames onto the plate. Gfx.caption draws nothing on output frames 1812-1890 (logical 82.2083 <= t <
      85.5). CAPTIONS is unchanged; only 1812-1821 had a caption in that window.
  (3) ascent footnote copy: 'NOT TO SCALE (6X) · NASA FIGURES' (v26 'EXAGGERATED 6X · NASA VALUES' could read as the
      figures being exaggerated), Franklin medium 38 (cap 26 px at 1080p) tracked 2: 552 px, inside the 574 px the
      Earth limb allows; asc_tl_box follows it.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import hud_v23
import polish_v26b as p
from hud_v23 import fnt, tracked

SCRIM_PAD, SCRIM_BLUR, SCRIM_MAX = 14, 6, 0.75
SCRIM_TARGET = 4.0                     # predicted text:surround (the gate is >= 3:1 on the encoded frames)
SCRIM_RELEASE = 0.04                   # alpha per frame
ASC_NOTE = "NOT TO SCALE (6X) · NASA FIGURES"
ASC_NOTE_SIZE, ASC_NOTE_TRACK = 38, 2
CAPTION_OFF = (1812, 1890)             # output frames with no caption (the end plate up to the credits)
STATE: dict = {"fi": None, "scrim": {}, "prev": {}}
_APPLIED: list[bool] = []
_composite_v23 = hud_v23.composite


# ---------------------------------------------------------------- (1) the local scrim
def _tag_ink(tag: str) -> tuple[tuple, str, str]:
    if tag == "archive":
        return (p.SLOT_X, p.SLOT_BASE), hud_v23.ARCHIVE_TEXT, "ls"
    return (p._time_cx(), p.TIME_BASE), "TIME-COMPRESSED", "ms"


def ink_box(tag: str) -> tuple[int, int, int, int]:
    xy, s, anc = _tag_ink(tag)
    w = p._w(s)
    x0 = xy[0] - w / 2 if anc[0] == "m" else xy[0]
    return int(x0), int(xy[1] - p._cap()), int(x0 + w), int(xy[1])


def _lin(v: np.ndarray) -> np.ndarray:
    c = np.clip(v, 0, 255) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _lum(rgb: np.ndarray) -> np.ndarray:
    c = _lin(rgb)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


def needed_alpha(region: np.ndarray, a: float) -> float:
    """Smallest scrim alpha whose predicted contrast (cream at FOOT_ALPHA * a over the scrimmed background vs the
    scrimmed surround, p75 of the region) reaches SCRIM_TARGET. The scrim scales the sRGB values by (1 - s); the
    surround ring sits in its feather (~0.8 of s)."""
    bg = np.percentile(region.reshape(-1, 3), 75, axis=0)
    cream = np.array(hud_v23.CREAM, np.float32)
    ta = p.FOOT_ALPHA * a
    for s in np.arange(0, SCRIM_MAX + 1e-6, 0.025):
        txt = cream * ta + bg * (1 - s) * (1 - ta)
        sur = bg * (1 - 0.8 * s)
        lt, ls = float(_lum(txt[None])[0]), float(_lum(sur[None])[0])
        if (max(lt, ls) + 0.05) / (min(lt, ls) + 0.05) >= SCRIM_TARGET and lt > ls:
            return float(s)
    return SCRIM_MAX


def scrim(hud: Image.Image, tag: str, s: float) -> None:
    if s <= 0:
        return
    x0, y0, x1, y1 = ink_box(tag)
    m = SCRIM_PAD + 3 * SCRIM_BLUR
    w, h = x1 - x0 + 2 * m, y1 - y0 + 2 * m
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).rounded_rectangle([m - SCRIM_PAD, m - SCRIM_PAD, w - m + SCRIM_PAD, h - m + SCRIM_PAD],
                                         radius=SCRIM_PAD, fill=int(round(255 * s)))
    im = im.filter(ImageFilter.GaussianBlur(SCRIM_BLUR))
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    layer.putalpha(im)
    hud.alpha_composite(layer, (x0 - m, y0 - m))


def composite(f: np.ndarray, hf) -> np.ndarray:
    """hud_v23.composite, with the scrim alphas for this frame measured on f (the frame before the HUD) first."""
    it = hf.items
    STATE["fi"] = hf.fi
    cur = {}
    for tag, key in (("archive", "archive"), ("timetag", "fuel")):
        if key not in it:
            continue
        a = it[key]["a"] if tag == "archive" else hud_v23.clamp(it[key]["a"] * 3)
        x0, y0, x1, y1 = ink_box(tag)
        g = 12
        reg = f[max(y0 - g, 0):y1 + g, max(x0 - g, 0):x1 + g]
        need = needed_alpha(reg, a) if a > 0 else 0.0
        prev = STATE["prev"].get((tag, hf.fi - 1), 0.0)
        cur[tag] = max(need, prev - SCRIM_RELEASE, 0.0)
        STATE["prev"][(tag, hf.fi)] = cur[tag]
    STATE["scrim"] = cur
    return _composite_v23(f, hf)


def render_archive(hud: Image.Image, it: dict) -> None:
    scrim(hud, "archive", STATE["scrim"].get("archive", 0.0) * it["a"])
    p.render_archive(hud, it)


def render_timetag(hud: Image.Image, a: float) -> None:
    scrim(hud, "timetag", STATE["scrim"].get("timetag", 0.0) * hud_v23.clamp(a * 3))
    p.render_timetag(hud, a)


# ---------------------------------------------------------------- (3) the ascent footnote copy
class _AscNote:
    def __enter__(self) -> None:
        self.saved = (p.ASC_NOTE, p.FOOT_SIZE, p.FOOT_TRACK)
        p.ASC_NOTE, p.FOOT_SIZE, p.FOOT_TRACK = ASC_NOTE, ASC_NOTE_SIZE, ASC_NOTE_TRACK

    def __exit__(self, *exc) -> None:
        p.ASC_NOTE, p.FOOT_SIZE, p.FOOT_TRACK = self.saved


def asc_tl_box() -> tuple[int, int, int, int]:
    with _AscNote():
        return p.asc_tl_box()


def render_ascent(hud: Image.Image, it: dict) -> None:
    with _AscNote():
        p.render_ascent(hud, it)


# ---------------------------------------------------------------- (2) the caption out-point
def apply_caption(gfx_cls: type, act2_f0: int, act2_df: int, fps: int) -> None:
    """Wrap Gfx.caption (called with LOGICAL t): nothing on output frames CAPTION_OFF[0]..CAPTION_OFF[1]."""
    orig = gfx_cls.caption
    assert not getattr(orig, "_v27", False), "polish_v27 caption hook already applied"
    lo, hi = (CAPTION_OFF[0] + act2_df) / fps, (CAPTION_OFF[1] + 1 + act2_df) / fps
    assert CAPTION_OFF[0] >= act2_f0

    def caption(self, d, t):
        if lo - 1e-9 <= t < hi - 1e-9:
            return None
        return orig(self, d, t)

    caption._v27 = True
    gfx_cls.caption = caption


def apply() -> None:
    """Call once, after polish_v26b.apply() and before hud_v23.load_ascent computes the ascent layout."""
    assert not _APPLIED, "polish_v27 already applied"
    assert hud_v23.render_archive is p.render_archive and hud_v23.asc_tl_box is p.asc_tl_box, "apply polish_v26b first"
    assert hud_v23.ASC["layout"] is None, "apply before the ascent layout is computed (validate_assets)"
    _APPLIED.append(True)
    hud_v23.composite = composite
    hud_v23.render_archive = render_archive
    hud_v23.render_timetag = render_timetag
    hud_v23.asc_tl_box = asc_tl_box
    hud_v23.render_ascent = render_ascent
