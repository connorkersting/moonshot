"""Manifest for the v25 hero-beat asset (work/hero_v25), per BRIEF_v22 R4 (NEW tool).

    py hero_manifest_v25.py            # write hero_v25/manifest.json (refuses to overwrite)
    py hero_manifest_v25.py --check    # verify the folder (the same assets_v25.check_hero build.py runs)

Recipe (both steps write into hero_v25 / a scratch render dir; neither is needed by a build):
    blender.exe -b --factory-startup --python blender/hero_v25.py -- <render_dir> 1920 1080 1 84
    py blender/hero_post_v25.py <render_dir> hero_v25        # stars by alpha -> hv_####.png (RGB) + geometry.json
The manifest records the source hashes (renderer scene, shared path, post), the inputs, the renderer, the format,
the sha256 of every frame and of geometry.json, and the shot it was made for (frames 715-798, 1:1, 24 fps).
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

from PIL import Image

from assets_v23 import sha
from assets_v25 import check_hero

W = Path(__file__).resolve().parent
D = W / "hero_v25"
FIRST, N = 715, 84                        # build.py: Shot(29.80, 33.30, "SEQ") -> round(29.8*24)=715 .. 798
SOURCES = ("blender/hero_v25.py", "blender/hero_path_v25.py", "blender/hero_post_v25.py", "blender/stars.png")
INPUTS = {
    "bluemarble_8k.jpg": (CRAFTWORK / "inbox/moonshot/stills/bluemarble/bluemarble_8k.jpg"),
    "cloud_combined_8192.tif": (CRAFTWORK / "inbox/moonshot/stills/bluemarble/cloud_combined_8192.tif"),
    "lroc_color_16bit_srgb_4k.tif": (CRAFTWORK / "bg/nasa-moon/lroc_color_16bit_srgb_4k.tif"),
    "ldem_16.tif": (CRAFTWORK / "bg/nasa-moon/ldem_16.tif"),
}


def main() -> None:
    mp = D / "manifest.json"
    if "--check" in sys.argv:
        man = check_hero(W, D.name, FIRST, N)
        print(f"hero asset {D.name}: {len(man['frames'])} frames, geometry and sources verified")
        return
    if mp.exists():
        raise SystemExit(f"{mp} exists; not overwriting")
    frames = {}
    for k in range(1, N + 1):
        p = D / f"hv_{k:04d}.png"
        with Image.open(p) as im:
            assert im.size == (1920, 1080) and im.mode == "RGB", (p, im.size, im.mode)
            frames[p.name] = {"sha256": sha(p), "size": list(im.size), "mode": im.mode}
    geo = json.loads((D / "geometry.json").read_text(encoding="utf-8"))
    assert len(geo["frames"]) == N, len(geo["frames"])
    blender = (Path(os.environ.get("CRAFT_TOOLS", "craft-tools")) / "bin/blender-5.2.2-windows-x64/blender.exe")
    man = {
        "what": "MOONSHOT v25 hero beat: one continuous Earth-to-Moon move, trajectory schematic (not to scale), "
                "build.py SHOTS SEQ 29.80-33.30 = frames 715-798; the last camera is the locked portrait's (frame 799)",
        "sources": {rel: sha(W / rel) for rel in SOURCES},
        "commands": ["blender.exe -b --factory-startup --python blender/hero_v25.py -- <render_dir> 1920 1080 1 84",
                     "py blender/hero_post_v25.py <render_dir> work/hero_v25"],
        "inputs": {name: sha(p) for name, p in INPUTS.items()},
        "input_provenance": {
            "bluemarble_8k.jpg": "NASA Blue Marble Next Generation, December topo+bathy (CREDITS.md, as the ascent)",
            "cloud_combined_8192.tif": "NASA Visible Earth #57747 'Blue Marble: Clouds' (public domain), downloaded "
                                       "2026-10-08 by the v25 builder from https://eoimages.gsfc.nasa.gov/images/"
                                       "imagerecords/57000/57747/cloud_combined_8192.tif",
            "lroc/ldem": "NASA SVS #4720 CGI Moon Kit (CREDITS.md, as the Moon portrait)"},
        "renderer": {"blender": "5.2.2 LTS (hash d13f752e3b9c, built 2026-09-15)",
                     "blender_exe_sha256": sha(blender) if blender.is_file() else None,
                     "engine": "EEVEE, view transform Standard, film transparent, motion blur shutter 0.35, PNG RGBA; "
                               "post: alpha over blender/stars.png through the camera-rotation homography"},
        "format": {"size": [1920, 1080], "fps": 24, "numbering": "hv_####.png, 1-based, contiguous", "range": [1, N],
                   "alpha": "opaque RGB (stars composited by alpha in post; render_seq must not colour-key it)"},
        "shot": {"first_output_frame": FIRST, "n": N, "speed": 1.0,
                 "display": "asset frame k = output frame 714 + k (ffmpeg -framerate 24 -i hv_%04d.png, no fps filter)"},
        "geometry_sha256": sha(D / "geometry.json"),
        "frames": frames,
    }
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print(f"wrote {mp}: {len(frames)} frames")


if __name__ == "__main__":
    main()
