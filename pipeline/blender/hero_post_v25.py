"""v25 hero beat post: the Blender RGBA frames over the star layer, composited by ALPHA (never a black key), written
as opaque RGB PNGs hv_0001..hv_0084.png (the tracked asset, work/hero_v25).

    py blender/hero_post_v25.py <render_dir> <out_dir> [w h]

The star layer is blender/stars.png, the same plate render_seq lays under the Moon portrait from frame 799, treated
as a picture of the sky at infinity seen by the LAST camera: every earlier frame samples it through the rotation
homography H = K R_end R_k^T K^-1 (pure camera rotation; stars do not parallax), on a 3x3 tiling of the plate, with
render_seq's own drift continued backwards (crop x = 60 + 18 t, y = 40 + 6 t, t = 0 at frame 799), so frame 798's
stars sit where frame 799's are, one frame of drift earlier. Motion blur: 3 sub-frame homographies over the
shutter 0.35 (the Blender render's own shutter). Deterministic; pure Pillow + numpy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hero_path_v25 as hp  # noqa: E402

STARS = Path(__file__).resolve().parent / "stars.png"
DRIFT = (60.0, 40.0, 18.0, 6.0)        # render_seq: crop x = 60 + 18 t, y = 40 + 6 t (t in s from frame 799)


def cam_rows(k: float) -> np.ndarray:
    pos, tgt = hp.camera(k)
    rt, up, fw = hp.basis(pos, tgt)
    return np.array([rt, [-v for v in up], fw], float)        # camera coords: x right, y down, z forward


def kmat(w: int, h: int) -> np.ndarray:
    f = hp.FPX * w / hp.W
    return np.array([[f, 0, w / 2 - hp.SHIFT_X * w], [0, f, h / 2], [0, 0, 1.0]])


def star_plate() -> tuple[Image.Image, int, int]:
    st = Image.open(STARS).convert("RGB")
    sw, sh = st.size
    big = Image.new("RGB", (sw * 3, sh * 3))
    for i in range(3):
        for j in range(3):
            big.paste(st, (i * sw, j * sh))
    return big, sw, sh


def star_frame(big: Image.Image, sw: int, sh: int, k: float, w: int, h: int) -> np.ndarray:
    """The star layer for output frame k at w x h (sky only; the caller masks it by the render's alpha)."""
    K = kmat(w, h)
    sc = w / hp.W
    t = (k - hp.N) / 24.0                                    # seconds relative to frame 799 (k = 84)
    ox, oy = (DRIFT[0] + DRIFT[2] * t) * sc, (DRIFT[1] + DRIFT[3] * t) * sc
    M = K @ cam_rows(hp.N - 1) @ cam_rows(k).T @ np.linalg.inv(K)
    T = np.array([[1, 0, ox + sw * sc], [0, 1, oy + sh * sc], [0, 0, 1.0]])
    M = T @ M
    M = M / M[2, 2]
    plate = big if sc == 1 else big.resize((int(big.width * sc), int(big.height * sc)), Image.Resampling.BILINEAR)
    coef = (M[0, 0], M[0, 1], M[0, 2], M[1, 0], M[1, 1], M[1, 2], M[2, 0], M[2, 1])
    return np.asarray(plate.transform((w, h), Image.Transform.PERSPECTIVE, coef, Image.Resampling.BILINEAR),
                      np.float32)


def compose(src: Path, k: int, big: Image.Image, sw: int, sh: int) -> Image.Image:
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    a = np.asarray(im, np.float32)
    al = a[..., 3:4] / 255.0
    stars = sum(star_frame(big, sw, sh, k + d, w, h) for d in (-0.175, 0.0, 0.175)) / 3.0
    out = a[..., :3] * al + stars * (1 - al)
    return Image.fromarray(np.clip(out + 0.5, 0, 255).astype(np.uint8), "RGB")


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    big, sw, sh = star_plate()
    n = 0
    for p in sorted(src.glob("hr_*.png")):
        k = int(p.stem[3:]) - 1
        compose(p, k, big, sw, sh).save(dst / f"hv_{k + 1:04d}.png", optimize=False)
        n += 1
    geo = {"what": "hero_v25 per-frame geometry (hero_path_v25.frame_geometry): camera, body circles, route polyline "
                   "[x, y, depth, visible] in 1920x1080 px", "frames": [hp.frame_geometry(k) for k in range(hp.N)]}
    (dst / "geometry.json").write_text(json.dumps(geo), encoding="utf-8")
    print(f"post: {n} frames + geometry.json -> {dst}")


if __name__ == "__main__":
    main()
