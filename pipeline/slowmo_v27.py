"""v27 slow-mo (director, 2026-10-08 ~22:15, side-by-side A/B: "i like righ more"): the smoke-under-the-title shot
(13.00-17.6667 s, frames 312-423, L70 at speed 0.5) from RIFE in-betweens instead of ffmpeg's framerate blend.

Measured (scratchpad/rife27): the blend makes every other frame ~15% softer (odd/even Laplacian variance 0.847,
frame-to-frame sharpness jitter 36.9); RIFE holds 0.978 / 7.1, with no warping of the tower in the detail strip.

Asset work/slowmo_v27/ (tracked; builds need no RIFE):
  l70_rife_1220x686.mp4  112 frames, 24 fps, yuv444p x264 crf 4: launch_70mm.mp4 frames 432-491 (src 18.0 s, the
                         shot's in-point) -> rife-ncnn-vulkan 20221029, model rife-v4.6, -n 119 (frame k = source time
                         k/2), frames 1-112, cropped to the shot's crop 1220:686:520:980
  manifest.json          the asset's sha256 + the recipe above
render() checks the sha256, then scales and grades exactly like build.render_video_shot (lanczos, GRADE["L70"], 24 fps).
"""
import hashlib
import json
import subprocess
from pathlib import Path

DIR = Path(__file__).resolve().parent / "slowmo_v27"
ASSET = DIR / "l70_rife_1220x686.mp4"
T0, SRC, NFR = 13.00, "L70", 112


def is_slowmo_shot(s) -> bool:
    return s.src == SRC and abs(s.t0 - T0) < 1e-6


def check() -> None:
    man = json.loads((DIR / "manifest.json").read_text(encoding="utf-8"))
    got = hashlib.sha256(ASSET.read_bytes()).hexdigest()
    if got != man["sha256"]:
        raise SystemExit(f"slowmo_v27: {ASSET.name} sha256 {got[:12]} != manifest {man['sha256'][:12]} (stale asset)")


def render(s, path: Path, w: int, h: int, fps: int, grade: str, nframes: int) -> None:
    check()
    if nframes != NFR:
        raise SystemExit(f"slowmo_v27: the shot needs {nframes} frames, the asset holds {NFR}")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ASSET), "-vf",
                    f"scale={w}:{h}:flags=lanczos,{grade},fps={fps},format=yuv420p", "-frames:v", str(nframes), "-an",
                    "-c:v", "libx264", "-crf", "14", "-preset", "veryfast", str(path)], check=True)
