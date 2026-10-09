"""MOONSHOT v25 HUD: the hero beat's screen-space drafting (frames 715-798), in the hud_v23 overlay system.

NEW module; hud_v23.py is unchanged. build.py (patch_v25) uses this module's composite() ONLY on frames 715-798
(HERO_F) when V25_HERO is True; there it draws exactly what hud_v23 draws (the TLI speed card and anything else on
the frame, via hud_v23.render, unchanged) plus, UNDER the card:
  route   the schematic route from the Earth to the Moon: the per-frame projection of blender/hero_path_v25.py's 3D
          curve (work/hero_v25/geometry.json, written by blender/hero_post_v25.py, hashed in the manifest), the house
          AMBER, 3 px line + faint 9 px glow, 2x supersampled; segments a body hides are not drawn. It launches on the
          Dvorak hit (frame 744): a departure dot and one expanding ring (12 frames) mark the hit, the head is a small
          cream dot while the line draws (744-~787).
and OVER it:
  label   'TRAJECTORY SCHEMATIC · NOT TO SCALE' on the system plate in the top-left tag slot (the archive tag's slot,
          free from frame 715), Franklin Medium Cond TAG (56: 12.5 px cap at 360p), cream, from frame 741.
Both leave with the speed card's own exit curve (u 2.9-3.25: frames ~785-793), so 794-798 are clean for the cut to
the locked Moon portrait at 799. Text is screen space; the speed card does not move.
  card    (lead review 1) the TLI card leaves EARLY on the hero frames: its alpha (build.py's value, unchanged) times
          card_fade(): 1 until frame 762, eased to 0 at frame 769, 0 after. The count settled at 24,200 by ~754; the
          Moon's limb reaches the card's ink box (x 114-1079, y 671-1009) at frame 770 (21 px clear at 768, the last
          frame with card alpha > 0). Values, u timeline and position unchanged; build.py's stat_speed is untouched.
  weight  (lead review 2) the route reads at phone size: 9 px core (3 px at 360p), 26 px soft glow, a bright head.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import hud_v23
from hud_v23 import AMBER, CREAM, TAG, H, W, ease_in_out, ease_out, fnt, legend_plate, tracked

HERO_DIR = "hero_v25"
HERO_F = (715, 799)                      # output frames [715, 799): the hero SEQ shot
HIT_F = 744                              # the Dvorak hit (31.02 s): the route launches
LABEL_TEXT = "TRAJECTORY SCHEMATIC · NOT TO SCALE"
LABEL_IN = 741
CARD_FADE = (762, 769)                  # card alpha 1 at 762 -> 0 at 769 (eased)
HudFrame = hud_v23.HudFrame
GEO: dict[int, dict] = {}


def load(folder: Path) -> None:
    """Read the hero geometry (validated against the manifest by assets_v25 before this is called)."""
    g = json.loads((folder / "geometry.json").read_text(encoding="utf-8"))
    GEO.clear()
    for e in g["frames"]:
        GEO[int(e["frame"])] = e
    missing = [f for f in range(*HERO_F) if f not in GEO]
    if missing:
        raise SystemExit(f"hud_v25: geometry.json has no entry for frames {missing[:4]}")


def exit_alpha(fi: int) -> float:
    """build.py stat_speed's exit (a = ... * (1 - ease_in_out((u - 2.9) / 0.35)), u from frame 715)."""
    u = (fi - HERO_F[0]) / 24.0
    return 1 - ease_in_out((u - 2.9) / 0.35)


def card_fade(fi: int) -> float:
    """Multiplier on the TLI card's alpha on the hero frames (lead review: off the Moon before its limb arrives)."""
    return 1 - ease_in_out((fi - CARD_FADE[0]) / (CARD_FADE[1] - CARD_FADE[0]))


def label_box() -> tuple[int, int, int, int]:
    tw = tracked(ImageDraw.Draw(Image.new("L", (8, 8))), (0, 0), LABEL_TEXT, fnt("med", TAG), 0, 3)
    return 100, 62, int(128 + tw), 130


def label_alpha(fi: int) -> float:
    return ease_out((fi - LABEL_IN + 1) / 6) * exit_alpha(fi)


def route_layer(fi: int) -> Image.Image | None:
    e = GEO.get(fi)
    a = exit_alpha(fi)
    if e is None or a <= 0 or fi < HIT_F:
        return None
    ss = 2
    big = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    glow = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    d, dg = ImageDraw.Draw(big), ImageDraw.Draw(glow)
    pts = e["route"]
    runs, cur = [], []
    for p in pts:
        if p[3] and p[0] == p[0]:
            cur.append((p[0] * ss, p[1] * ss))
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    for r in runs:
        if len(r) > 1:
            dg.line(r, fill=AMBER + (int(110 * a),), width=26 * ss, joint="curve")
            d.line(r, fill=AMBER + (int(240 * a),), width=9 * ss, joint="curve")
    if pts and pts[0][3]:                                    # the departure point
        x, y = pts[0][0] * ss, pts[0][1] * ss
        rr = 9 * ss
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=AMBER + (int(255 * a),))
        k = fi - HIT_F                                       # the hit: one ring, 12 frames
        if 0 <= k < 12:
            q = k / 11
            rad = (12 + 52 * ease_out(q)) * ss
            d.ellipse([x - rad, y - rad, x + rad, y + rad], outline=AMBER + (int(230 * (1 - q) * a),), width=4 * ss)
    if e["reveal"] < 1 and pts and pts[-1][3]:               # the drawing head
        x, y = pts[-1][0] * ss, pts[-1][1] * ss
        rr = 22 * ss
        dg.ellipse([x - rr, y - rr, x + rr, y + rr], fill=AMBER + (int(150 * a),))
        rr = 10 * ss
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=CREAM + (int(255 * a),))
    glow = glow.filter(ImageFilter.GaussianBlur(7 * ss))
    glow.alpha_composite(big)
    return glow.resize((W, H), Image.Resampling.LANCZOS)


def render_label(hud: Image.Image, fi: int) -> None:
    a = label_alpha(fi)
    if a <= 0:
        return
    legend_plate(hud, label_box(), a * 0.85)
    tmp = Image.new("RGBA", hud.size, (0, 0, 0, 0))
    tracked(ImageDraw.Draw(tmp), (114, 115), LABEL_TEXT, fnt("med", TAG), CREAM + (int(255 * a * 0.95),), 3, "ls")
    hud.alpha_composite(tmp)


def render(hf: HudFrame) -> Image.Image | None:
    """hud_v23.render (unchanged items) over the route; the schematic label on top."""
    if "hero" not in hf.items:
        return hud_v23.render(hf)
    fi = hf.items["hero"]["fi"]
    if "speed" in hf.items:                     # the card's own values; only its alpha is scaled (a copy)
        sp = dict(hf.items["speed"])
        sp["a"] = sp["a"] * card_fade(fi)
        items = {**hf.items, "speed": sp}
        hf = HudFrame(hf.fi, hf.tl)
        hf.items = items
    top = hud_v23.render(hf)
    hud = route_layer(fi) or Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if top is not None:
        hud.alpha_composite(top)
    render_label(hud, fi)
    return hud


def composite(f: np.ndarray, hf: HudFrame) -> np.ndarray:
    """hud_v23.composite's film pass (gate weave, 0.6 px softening, halation on the graphics' highlights), verbatim,
    on this module's render()."""
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
    pm = np.asarray(crop, np.float32)
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
