"""v18 title bloom (the Glare / fog-glow pass, done on the RGBA frames so the glow can spill past the letters).

    py title_post_v18.py RAW_DIR OUT_DIR [mode ...]      (modes default: open end)

For each RAW_DIR/<mode>_####.png (straight-alpha RGBA from title_v18.py): premultiply; take the highlights
(smoothstep 0.50-0.90 on max(R, G, B)) weighted toward warm pixels; blur at three radii (6 / 20 / 56 px at 1920 wide,
scaled with the frame) and add as a warm glow; the glow's luminance becomes alpha outside the letters, so the
compositor's straight-alpha over gives title + additive glow (background under the glow dimmed by at most GLOW_MAX).
Writes OUT_DIR/<mode>_####.png with the same names. Never overwrites an existing file.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

GAIN = {"open": 1.0, "end": 0.45}
GLOW_MAX = 0.55


def box(a: np.ndarray, rad: int, ax: int) -> np.ndarray:
    p = np.pad(a, [(rad + 1, rad) if i == ax else (0, 0) for i in range(a.ndim)], mode="constant")
    c = np.cumsum(p, axis=ax)
    n_ = c.shape[ax]
    return (np.take(c, range(2 * rad + 1, n_), axis=ax) - np.take(c, range(0, n_ - 2 * rad - 1), axis=ax)) / (2 * rad + 1)


def blur(a: np.ndarray, r: float) -> np.ndarray:
    """~Gaussian blur (sigma r px) of an HxWx3 float array: downscale, three box passes per axis, upscale."""
    h, w = a.shape[:2]
    k = max(1, int(r // 4))
    rad = max(1, int(round(r / k * 0.9)))
    out = []
    for c in range(3):
        sm = np.asarray(Image.fromarray(np.ascontiguousarray(a[..., c], np.float32), "F")
                        .resize((max(w // k, 1), max(h // k, 1)), Image.Resampling.BILINEAR), np.float32)
        for _ in range(3):
            sm = box(box(sm, rad, 0), rad, 1)
        out.append(np.asarray(Image.fromarray(sm.astype(np.float32), "F").resize((w, h), Image.Resampling.BILINEAR), np.float32))
    return np.stack(out, -1)


def bloom(rgba: np.ndarray, gain: float) -> np.ndarray:
    h, w = rgba.shape[:2]
    s = w / 1920
    a = rgba[..., 3:4].astype(np.float32) / 255
    p = rgba[..., :3].astype(np.float32) / 255 * a                 # premultiplied
    mx = p.max(axis=2, keepdims=True)
    hi = np.clip((mx - 0.50) / 0.40, 0, 1)
    hi = hi * hi * (3 - 2 * hi)
    warm = np.clip((p[..., :1] - p[..., 2:3]) * 2.5 + 0.25, 0, 1)    # R - B: the fire-lit edges bloom most
    src = p * hi * warm
    glow = blur(src, 6 * s) * 0.55 + blur(src, 20 * s) * 0.45 + blur(src, 56 * s) * 0.35
    glow *= gain * np.array([1.0, 0.82, 0.62], np.float32)
    out_p = p + glow
    ga = np.clip(glow.max(axis=2, keepdims=True), 0, GLOW_MAX)
    a2 = np.maximum(a, ga)
    col = np.where(a2 > 1e-4, out_p / np.maximum(a2, 1e-4), 0)
    return np.dstack([np.clip(col * 255, 0, 255), np.clip(a2 * 255, 0, 255)]).round().astype(np.uint8)


def main() -> None:
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    modes = sys.argv[3:] or ["open", "end"]
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for m in modes:
        for f in sorted(raw.glob(f"{m}_*.png")):
            dst = out / f.name
            if dst.exists():
                raise SystemExit(f"{dst} exists; not overwriting")
            Image.fromarray(bloom(np.asarray(Image.open(f).convert("RGBA")), GAIN[m]), "RGBA").save(dst)
            n += 1
    print(f"bloom: {n} frames -> {out}")


if __name__ == "__main__":
    main()
