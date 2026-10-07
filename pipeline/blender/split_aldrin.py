"""Depth planes for AS11-40-5903 (Aldrin, photographed by Armstrong):
  near: Aldrin (alpha from craft_tools.cutout, BiRefNet MIT model, already on this machine)
  far:  the original with Aldrin's silhouette filled from its surroundings (iterative blur fill, PIL only),
        so a slow push reveals plausible ground instead of a hole. No generative fill.
"""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image, ImageFilter

SRC = (CRAFTWORK / "inbox/moonshot/stills/as11-40-5903.jpg")
CUT = (CRAFTWORK / "cutouts/as11-40-5903.png")
OUT = (CRAFTWORK / "inbox/moonshot/work/blender/planes")
OUT.mkdir(parents=True, exist_ok=True)

img = Image.open(SRC).convert("RGB")
cut = Image.open(CUT).convert("RGBA").resize(img.size)
alpha = np.asarray(cut.getchannel("A"), np.float32) / 255.0
a = np.asarray(img, np.float32)
h, w = alpha.shape
print(f"{w}x{h}; astronaut coverage {alpha.mean():.3f}")

# near plane: original pixels, cutout alpha (slightly choked to avoid halo)
al = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
near = np.dstack([a, np.asarray(al, np.float32)]).astype(np.uint8)
Image.fromarray(near, "RGBA").save(OUT / "aldrin_near.png")

# far plane: fill the silhouette (dilated) by repeated blur-and-restore at decreasing scale
hole = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(15)), np.float32) / 255.0
known = 1 - hole
# normalized convolution at a coarse scale: blur(img * known) / blur(known) only diffuses ground colour inward
small = 8
sw, sh = w // small, h // small


def blur_small(x: np.ndarray, r: float) -> np.ndarray:
    from scipy.ndimage import gaussian_filter   # PIL can't blur float images
    chans = []
    for c in range(x.shape[2]):
        im_ = Image.fromarray(x[..., c].astype(np.float32), mode="F").resize((sw, sh), Image.Resampling.BILINEAR)
        bl = gaussian_filter(np.asarray(im_, np.float32), r)
        chans.append(np.asarray(Image.fromarray(bl, mode="F").resize((w, h), Image.Resampling.BILINEAR), np.float32))
    return np.stack(chans, -1)


num = blur_small(a * known[..., None], 18)
den = blur_small(known[..., None], 18)
diffused = num / np.maximum(den, 1e-4)
fill = a * known[..., None] + diffused * hole[..., None]
far = np.dstack([np.clip(fill, 0, 255), np.full((h, w), 255.0)]).astype(np.uint8)
Image.fromarray(far, "RGBA").save(OUT / "aldrin_far.png")
print("aldrin planes written")
