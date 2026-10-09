"""MOONSHOT v23: ONE validator for every manifested pre-rendered asset (NEW module; Codex v22 review items 2-3).

Used by build.py's validate_assets() / preflight() (patch_v23) and by the manifest tools' --check
(title_manifest_v22.py --check via patch_v23, ascent_manifest_v23.py --check), so the build and the tools can never
disagree about what "valid" means. Pure Python + Pillow; no Blender, no ffmpeg.

  check_title(work, title_dir, frames)   the title3d_v22 sequences: exact frame names (no missing / extra), sha256 per
                                         frame, size, AND the recorded source hashes (blender/title_v22.py and
                                         blender/title_post_v18.py) against the files on disk (v22 checked frames only:
                                         a changed renderer with old PNGs passed).
  check_ascent(work, folder, shot)       the ascent_blender_v23 render: asc_0001-0192.png sha256 + size, geometry.json
                                         sha256, the source hash (blender/ascent3d_v23.py), and the display map's shot
                                         parameters (t0, speed, frame count) against the Shot build.py will render.
Each raises AssetError naming the asset, the item, what was expected and what was found.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image


class AssetError(SystemExit):
    pass


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _sources(work: Path, man: dict, what: str) -> None:
    src = man.get("sources")
    if not src:
        raise AssetError(f"{what}: manifest records no source hashes")
    for rel, want in src.items():
        p = work / rel
        if not p.is_file():
            raise AssetError(f"{what}: source {rel} missing (manifest expects sha256 {want[:12]})")
        got = sha(p)
        if got != want:
            raise AssetError(f"{what}: source {rel} changed since the render (manifest {want[:12]}, on disk {got[:12]}): "
                             "re-render and re-manifest")


def check_title(work: Path, title_dir: str, frames: dict[str, int], size: tuple[int, int] = (1920, 1080)) -> int:
    d = work / title_dir
    mp = d / "manifest.json"
    if not mp.is_file():
        raise AssetError(f"title asset: {mp} missing (render with blender/title_v22.py + title_post_v18.py, then "
                         "py title_manifest_v22.py)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    _sources(work, man, f"title asset {d.name}")
    n_all = 0
    for mode, n in frames.items():
        want = [f"{mode}_{k:04d}.png" for k in range(1, n + 1)]
        have = sorted(p.name for p in d.glob(f"{mode}_*.png"))
        if have != want:
            raise AssetError(f"title asset {d.name}: {mode} frames {len(have)} on disk, expected {n} "
                             f"({sorted(set(want) ^ set(have))[:4]})")
        for name in want:
            e = man["frames"].get(name)
            if e is None or sha(d / name) != e["sha256"]:
                raise AssetError(f"title asset {d.name}/{name}: not in the manifest or sha256 differs (stale)")
            if tuple(e["size"]) != tuple(size):
                raise AssetError(f"title asset {d.name}/{name}: manifest size {e['size']}, expected {size}")
        n_all += n
    extra = sorted(set(man["frames"]) - {f"{m}_{k:04d}.png" for m, n in frames.items() for k in range(1, n + 1)})
    if extra:
        raise AssetError(f"title asset {d.name}: manifest lists frames not expected: {extra[:4]}")
    return n_all


ASC_FRAMES = 192


def check_ascent(work: Path, folder: str, t0: float, speed: float, nframes: int,
                 size: tuple[int, int] = (1920, 1080)) -> dict:
    d = work / folder
    mp = d / "manifest.json"
    if not mp.is_file():
        raise AssetError(f"ascent asset: {mp} missing (render blender/ascent3d_v23.py, then py ascent_manifest_v23.py)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    _sources(work, man, f"ascent asset {d.name}")
    want = [f"asc_{k:04d}.png" for k in range(1, ASC_FRAMES + 1)]
    have = sorted(p.name for p in d.glob("asc_*.png"))
    if have != want:
        raise AssetError(f"ascent asset {d.name}: {len(have)} frames on disk, expected {ASC_FRAMES} "
                         f"({sorted(set(want) ^ set(have))[:4]})")
    for name in want:
        e = man["frames"].get(name)
        if e is None or sha(d / name) != e["sha256"]:
            raise AssetError(f"ascent asset {d.name}/{name}: not in the manifest or sha256 differs (stale)")
        if tuple(e["size"]) != tuple(size):
            raise AssetError(f"ascent asset {d.name}/{name}: manifest size {e['size']}, expected {size}")
    g = d / "geometry.json"
    if not g.is_file() or sha(g) != man["geometry_sha256"]:
        raise AssetError(f"ascent asset {d.name}: geometry.json missing or differs from the manifest")
    disp = man["display"]
    exp = {"t0": round(t0, 4), "speed": round(speed, 4), "n": nframes}
    got = {"t0": round(disp["t0"], 4), "speed": round(disp["speed"], 4), "n": disp["n"]}
    if got != exp or len(disp["frames"]) != nframes:
        raise AssetError(f"ascent asset {d.name}: display map made for {got}, build.py's shot is {exp}: re-manifest")
    if any(not 1 <= j <= ASC_FRAMES for j in disp["frames"]) or any(b < a for a, b in zip(disp["frames"],
                                                                                         disp["frames"][1:])):
        raise AssetError(f"ascent asset {d.name}: display map out of range or not monotonic")
    return man


def check_png_size(p: Path, size: tuple[int, int]) -> None:
    with Image.open(p) as im:
        if im.size != tuple(size):
            raise AssetError(f"{p}: {im.size}, expected {size}")
