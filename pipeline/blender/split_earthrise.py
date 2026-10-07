"""Split AS11-44-6550 (Apollo 11 earthrise) into depth planes for a Blender parallax move.

Writes work/blender/planes/earthrise_{surface,earth,sky}.png (RGBA, original pixels, no generative fill):
  surface: lunar terrain below the horizon (per-column horizon found from the brightness edge)
  earth:   the Earth disc (bright, saturated blob above the horizon), slightly feathered
  sky:     everything else (black space), with the Earth painted out to black so it can move
"""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image, ImageFilter

SRC = (CRAFTWORK / "inbox/moonshot/stills/as11-44-6550.jpg")
OUT = (CRAFTWORK / "inbox/moonshot/work/blender/planes")
OUT.mkdir(parents=True, exist_ok=True)

im = Image.open(SRC).convert("RGB")
a = np.asarray(im).astype(np.float32)
h, w, _ = a.shape
lum = a.mean(axis=2)
sm = np.asarray(Image.fromarray(lum.astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)

# horizon: for each column, first row (from the top, below the Earth) where the smoothed luma stays bright
horizon = np.zeros(w, int)
start = int(h * 0.415)
for x in range(w):
    col = sm[start:, x]
    idx = np.flatnonzero(col > 38)
    horizon[x] = start + (idx[0] if len(idx) else h - start - 1)
horizon = np.asarray(Image.fromarray(horizon[None, :].astype(np.float32)).filter(ImageFilter.MedianFilter(1)))[0] \
    if False else np.convolve(np.pad(horizon, 40, mode="edge"), np.ones(81) / 81, mode="valid").astype(int)

yy = np.arange(h)[:, None]
surf_mask = (yy >= horizon[None, :] - 2).astype(np.float32)

# Earth: bright pixels above the horizon
above = yy < (horizon[None, :] - 12)
earth_mask = ((sm > 30) & above).astype(np.float32)
em = Image.fromarray((earth_mask * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(3))
earth_mask = np.asarray(em, np.float32) / 255.0
ys, xs = np.nonzero(earth_mask > 0.5)
print(f"image {w}x{h}; horizon rows {horizon.min()}-{horizon.max()}; earth bbox x {xs.min()}-{xs.max()} y {ys.min()}-{ys.max()}")

sm_f = np.asarray(Image.fromarray((surf_mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)), np.float32) / 255.0


def save(name: str, rgb: np.ndarray, alpha: np.ndarray) -> None:
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(OUT / f"earthrise_{name}.png")


save("surface", a, sm_f)
save("earth", a, earth_mask * (1 - sm_f))
sky = a * (1 - earth_mask[..., None]) * (1 - sm_f[..., None])   # Earth and terrain painted out: space only
save("sky", sky, np.ones((h, w), np.float32))
print("planes written to", OUT)
