"""Manifest for the tracked v22 title frames (work/title3d_v22), per the v22 brief R4 (NEW tool).

    py title_manifest_v22.py            # write title3d_v22/manifest.json (refuses to overwrite)
    py title_manifest_v22.py --check    # verify the folder against the manifest (what build.py's validate_assets does)

The frames: blender/title_v22.py (raw straight-alpha RGBA PNGs, rendered in a scratch folder) -> blender/
title_post_v18.py (bloom, unchanged) -> title3d_v22/<mode>_####.png. The manifest records the recipe (source hashes,
props, font + HDRI hashes, renderer versions and settings, the exact commands), the format (size, frame range,
numbering, fps, alpha convention) and the sha256 of every frame, so a build needs no Blender and fails on a stale or
missing frame.
"""
from __future__ import annotations

import hashlib
import json
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

from PIL import Image

W = Path(__file__).resolve().parent
D = W / "title3d_v22"
FRAMES = {"open": 104, "end": 56}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    mp = D / "manifest.json"
    if "--check" in sys.argv:          # v23 (Codex v22): build.py's own validator, frames AND source hashes
        from assets_v23 import check_title
        n = check_title(W, D.name, FRAMES)
        print(f"{n} frames, sizes and the recorded source hashes verified (assets_v23.check_title, as build.py)")
        raise SystemExit(0)
    if mp.exists():
        raise SystemExit(f"{mp} exists; not overwriting")
    frames = {}
    for mode, n in FRAMES.items():
        for k in range(1, n + 1):
            p = D / f"{mode}_{k:04d}.png"
            im = Image.open(p)
            assert im.mode == "RGBA", (p, im.mode)
            frames[p.name] = {"sha256": sha(p), "size": list(im.size), "mode": im.mode}
    blender = (Path(os.environ.get("CRAFT_TOOLS", "craft-tools")) / "bin/blender-5.2.2-windows-x64/blender.exe")
    man = {
        "what": "MOONSHOT 3D title, v22 light rig (build.py title_layer: open 13.0-17.25 logical, end card 83.4-85.5)",
        "sources": {"blender/title_v22.py": sha(W / "blender" / "title_v22.py"),
                    "blender/title_post_v18.py": sha(W / "blender" / "title_post_v18.py")},
        "props": {"open": "104 frames, centre (1380, 400), 44% width, rise 190 px, yaw -10 -> -5, push 1.05 -> 0.965, "
                          "glow 1.0, rim 1.6 (1.0, 0.52, 0.2), fill 70",
                  "end": "56 frames, centre (960, 318), 52% width, no rise, yaw 5 -> 2.5, push 1.035 -> 0.985, glow "
                         "0.35, rim 0.9 (1.0, 0.82, 0.62), fill 70",
                  "post": "title_post_v18.py bloom GAIN open 1.0 / end 0.45, GLOW_MAX 0.55"},
        "commands": [
            "blender.exe -b --factory-startup --python blender/title_v22.py -- <raw_dir> open",
            "blender.exe -b --factory-startup --python blender/title_v22.py -- <raw_dir> end",
            "py blender/title_post_v18.py <raw_dir> work/title3d_v22 open end"],
        "inputs": {"font Anton-Regular.ttf": sha((CRAFTWORK / "fonts/Anton-Regular.ttf")),
                   "hdri studio_small_09.hdr": sha((CRAFTWORK / "bg/hdri/studio_small_09.hdr"))},
        "renderer": {"blender": "5.2.2 LTS (hash d13f752e3b9c, built 2026-09-15)", "blender_exe_sha256":
                     sha(blender) if blender.is_file() else None, "engine": "EEVEE, 64 TAA samples, film transparent, "
                     "motion blur shutter 0.5, view transform Standard, PNG RGBA 8-bit",
                     "post": "Python 3 + Pillow + numpy (title_post_v18.py)"},
        "format": {"size": [1920, 1080], "fps": 24, "numbering": "<mode>_####.png, 1-based, contiguous",
                   "ranges": {"open": [1, 104], "end": [1, 56]},
                   "alpha": "straight (unassociated) RGBA; the bloom's glow is in alpha outside the letters"},
        "frames": frames,
    }
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"wrote {mp}: {len(frames)} frames")


if __name__ == "__main__":
    main()
