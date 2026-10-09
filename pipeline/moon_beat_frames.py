"""v18 Moon beat (Connor's 0:32 note): the 33.3-36.6 shot as a 1080p PNG sequence, rendered from one 4K Blender still
(blender/moon_portrait.py: moon_anim's frame-1 framing with the camera at 8.5, NASA CGI Moon Kit SVS #4720).

    py moon_beat_frames.py      -> moon_portrait_v18/mp_0001.png ... mp_0080.png (black sky; render_seq adds the
                                   drifting star layer and the CG16 grade like the old approach shot)

Locked off 33.3-34.0 while the Dvorak's E-minor chord decays, then an ease-in drift from the Egmont entry (34.0),
still moving at the 36.6 cut: zoom 1.12 -> 1.18 (v17's approach grew ~2.5x in 2.3 s). The disc sits right of
centre so the distance stat (wipes in from 34.6) has the left third. Auditioned by Connor as
exports/moonshot/auditions/0m32_C2_hold_then_drift.mp4.
"""
from pathlib import Path

from PIL import Image

WORK = Path(__file__).resolve().parent
STILL = WORK / "moon_hero_v18" / "moon_0001.png"
OUT = WORK / "moon_portrait_v18"
W, H, FPS = 1920, 1080, 24
F0 = 799                     # first frame of the shot (33.29 s); frame k of the sequence is video frame F0 + k - 1
COUNT = 80                   # the shot needs 79 (799-877); one spare
T_DRIFT, T_CUT = 34.0, 36.6


def view(t: float) -> tuple[float, float]:
    """(zoom, centre x as a fraction of the still's width) at video time t."""
    v = min(max(t - T_DRIFT, 0.0) / (T_CUT - T_DRIFT), 1.0)
    return 1.12 + 0.06 * (v * v * (2 - v)), 0.455 - 0.005 * v


def main() -> None:
    src = Image.open(STILL).convert("RGB")
    sw, sh = src.size
    OUT.mkdir(exist_ok=True)
    for k in range(1, COUNT + 1):
        z, cx = view((F0 + k - 1) / FPS)
        cw, ch = sw / z, sw / z * H / W
        cx = min(max(cx, cw / 2 / sw), 1 - cw / 2 / sw)
        box = (cx * sw - cw / 2, sh / 2 - ch / 2, cx * sw + cw / 2, sh / 2 + ch / 2)
        src.resize((W, H), Image.Resampling.LANCZOS, box=box).save(OUT / f"mp_{k:04d}.png")
    print(f"{COUNT} frames -> {OUT}")


if __name__ == "__main__":
    main()
