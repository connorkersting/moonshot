"""Manifest for the tracked v23 ascent render (work/ascent_blender_v23), per BRIEF_v22 R4 (NEW tool).

    py ascent_manifest_v23.py            # write ascent_blender_v23/manifest.json (refuses to overwrite)
    py ascent_manifest_v23.py --check    # verify the folder (the same assets_v23.check_ascent build.py runs)

The frames: blender/ascent3d_v23.py (v5's scene, no baked text) rendered straight into ascent_blender_v23/asc_####.png
plus geometry.json (per-frame projected tube / rings / limb / values, written by the same run). The manifest records
the recipe (source hash, command, renderer), the format, the sha256 of every frame and of geometry.json, and the
DISPLAY MAP: which asset frame each of the shot's output frames shows. The map is measured, not modelled: index-coded
probe frames go through render_seq's own ffmpeg chain (-framerate 24 * speed -i ..., fps=24), so the overlay reads
exactly the frame the picture shows (the fps filter's rounding is not a simple formula).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image

from assets_v23 import ASC_FRAMES, check_ascent, sha

W = Path(__file__).resolve().parent
D = W / "ascent_blender_v23"
SHOT_T0, SHOT_T1, SPEED, FPS = 21.8333, 26.50, 1.70, 24      # build.py SHOTS: the ascent SEQ shot (v19 timing)
NFR = int(round(SHOT_T1 * FPS)) - int(round(SHOT_T0 * FPS))  # 112
BLUEMARBLE = (CRAFTWORK / "inbox/moonshot/stills/bluemarble/bluemarble_8k.jpg")


def display_map() -> list[int]:
    tmp = Path(tempfile.mkdtemp(prefix="asc_map_"))
    try:
        for j in range(1, ASC_FRAMES + 1):
            a = np.zeros((16, 32, 3), np.uint8)
            a[..., 0], a[..., 1] = j % 256, j // 256
            Image.fromarray(a).save(tmp / f"p_{j:04d}.png")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-framerate", f"{FPS * SPEED:g}", "-i", str(tmp / "p_%04d.png"),
                              "-vf", f"fps={FPS}", "-frames:v", str(NFR), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True, check=True).stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    f = np.frombuffer(raw, np.uint8).reshape(-1, 16, 32, 3)
    m = [int(x[8, 16, 0]) + 256 * int(x[8, 16, 1]) for x in f]
    if len(m) != NFR:
        raise SystemExit(f"display map: {len(m)} frames, expected {NFR}")
    return m


def main() -> None:
    mp = D / "manifest.json"
    if "--check" in sys.argv:
        man = check_ascent(W, D.name, SHOT_T0, SPEED, NFR)
        print(f"ascent asset {D.name}: {len(man['frames'])} frames, geometry, sources and the display map verified")
        return
    if mp.exists():
        raise SystemExit(f"{mp} exists; not overwriting")
    frames = {}
    for k in range(1, ASC_FRAMES + 1):
        p = D / f"asc_{k:04d}.png"
        with Image.open(p) as im:
            assert im.size == (1920, 1080), (p, im.size)
            frames[p.name] = {"sha256": sha(p), "size": list(im.size), "mode": im.mode}
    geo = json.loads((D / "geometry.json").read_text(encoding="utf-8"))
    assert len(geo["frames"]) == ASC_FRAMES, len(geo["frames"])
    blender = (Path(os.environ.get("CRAFT_TOOLS", "craft-tools")) / "bin/blender-5.2.2-windows-x64/blender.exe")
    man = {
        "what": "MOONSHOT 3D ascent beat, v23: v5's scene with no baked text (build.py SHOTS ascent SEQ, frames 524-635)",
        "sources": {"blender/ascent3d_v23.py": sha(W / "blender" / "ascent3d_v23.py")},
        "commands": ["blender.exe -b --factory-startup --python blender/ascent3d_v23.py -- work/ascent_blender_v23 "
                     "1920 1080 1 192"],
        "inputs": {"bluemarble_8k.jpg": sha(BLUEMARBLE)},
        "renderer": {"blender": "5.2.2 LTS (hash d13f752e3b9c, built 2026-09-15)",
                     "blender_exe_sha256": sha(blender) if blender.is_file() else None,
                     "engine": "EEVEE, view transform Standard, PNG RGBA 8-bit, no compositor glare (the Scene."
                               "node_tree API is gone in 5.x; v5 rendered the same way)"},
        "format": {"size": [1920, 1080], "fps": 24, "numbering": "asc_####.png, 1-based, contiguous",
                   "range": [1, ASC_FRAMES], "alpha": "opaque (alpha 255); render_seq colour-keys black over the stars"},
        "geometry_sha256": sha(D / "geometry.json"),
        "display": {"t0": SHOT_T0, "speed": SPEED, "n": NFR, "first_output_frame": int(round(SHOT_T0 * FPS)),
                    "how": "index-coded probe PNGs through ffmpeg -framerate 40.8 -i ... -vf fps=24 (render_seq's chain)",
                    "frames": display_map()},
        "frames": frames,
    }
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"wrote {mp}: {len(frames)} frames, display map {man['display']['frames'][:6]}...")


if __name__ == "__main__":
    main()
