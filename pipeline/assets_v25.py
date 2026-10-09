"""MOONSHOT v25: validator for the hero-beat asset work/hero_v25 (NEW module; same contract as assets_v23).

Used by build.py's validate_assets() (patch_v25) and by hero_manifest_v25.py --check, so the build and the tool agree.

  check_hero(work, folder, nframes, size)   hv_0001..hv_NNNN.png exact names (no missing / extra), sha256 + size +
                                            mode (opaque RGB: the stars are composited by alpha in the asset, so
                                            render_seq must NOT colour-key it), geometry.json sha256, the recorded
                                            source hashes (renderer, path, post) against the files on disk, and the
                                            shot it was made for (first output frame, frame count).
Raises assets_v23.AssetError naming the asset, the item, what was expected and what was found.
"""
from __future__ import annotations

import json
from pathlib import Path

from assets_v23 import AssetError, _sources, sha


def check_hero(work: Path, folder: str, first_frame: int, nframes: int,
               size: tuple[int, int] = (1920, 1080)) -> dict:
    d = work / folder
    mp = d / "manifest.json"
    if not mp.is_file():
        raise AssetError(f"hero asset: {mp} missing (render blender/hero_v25.py, post blender/hero_post_v25.py, "
                         "then py hero_manifest_v25.py)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    _sources(work, man, f"hero asset {d.name}")
    shot = man.get("shot", {})
    if shot.get("first_output_frame") != first_frame or shot.get("n") != nframes:
        raise AssetError(f"hero asset {d.name}: made for {shot}, build.py's shot starts at frame {first_frame} "
                         f"with {nframes} frames")
    want = [f"hv_{k:04d}.png" for k in range(1, nframes + 1)]
    have = sorted(p.name for p in d.glob("hv_*.png"))
    if have != want:
        raise AssetError(f"hero asset {d.name}: {len(have)} frames on disk, expected {nframes} "
                         f"({sorted(set(want) ^ set(have))[:4]})")
    if sorted(man["frames"]) != want:
        raise AssetError(f"hero asset {d.name}: the manifest lists {len(man['frames'])} frames, expected {nframes}")
    for name in want:
        e = man["frames"][name]
        if sha(d / name) != e["sha256"]:
            raise AssetError(f"hero asset {d.name}/{name}: sha256 differs from the manifest (stale)")
        if tuple(e["size"]) != tuple(size) or e["mode"] != "RGB":
            raise AssetError(f"hero asset {d.name}/{name}: manifest {e['size']} {e['mode']}, expected {size} RGB")
    g = d / "geometry.json"
    if not g.is_file() or sha(g) != man["geometry_sha256"]:
        raise AssetError(f"hero asset {d.name}: geometry.json missing or differs from the manifest")
    return man
