"""2.5D parallax of a NASA still in Blender: RGBA depth planes (original pixels, hand-masked with PIL) placed at
different depths and scaled so frame 1 reproduces the photo; a real camera then moves through them.

    blender.exe -b --factory-startup --python parallax.py -- <preset> <out_dir> [w h first last]

presets:
  earthrise  AS11-44-6550: sky (far) / Earth (mid) / lunar surface (near). Camera cranes up and pushes in,
             so the near horizon sinks faster than the Earth: the Earth rises. 106 frames (69.6-74.0 s).
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy

PL = (CRAFTWORK / "inbox/moonshot/work/blender/planes")
PRESETS = {
    "earthrise": {
        "frames": 106,
        "planes": [("earthrise_sky.png", 60.0), ("earthrise_earth.png", 34.0), ("earthrise_surface.png", 14.0)],
        # frame-1 view: centre (u, v) in the image (0..1, v down) and visible width fraction (1/zoom)
        "view": (0.5, 0.45, 1 / 1.35),
        "cam": [(1, (0.0, 0.0, 0.0)), (106, (0.05, 0.85, -2.4))],   # (frame, (x, y, z)) offsets: y up, z forward(-)
    },
    # AS11-40-5903: Aldrin (near, cutout) over the ground (far, silhouette filled). 43 frames (77.6-79.4 s).
    # Start: medium (zoom 1.9 on v=0.24). End: the visor (u 0.51, v 0.10) at zoom 4.2 on the near plane:
    #   near depth 10 -> end distance 10*1.9/4.2 = 4.52 (z -5.48); visor sits 0.14*img_h = 1.87 above start centre.
    "aldrin": {
        "frames": 43,
        "planes": [("aldrin_far.png", 13.0), ("aldrin_near.png", 10.0)],
        "view": (0.51, 0.13, 1 / 2.6),
        "cam": [(1, (0.0, 0.0, 0.0)), (43, (-0.09, 0.68, -6.0))],   # opens on the helmet, ends in the reflection (zoom 6.5)
    },
}


def plane(img_path: Path, depth: float, view, aspect_w: float) -> None:
    img = bpy.data.images.load(str(img_path))
    w, h = img.size
    u0, v0, frac = view
    # at distance `depth` with a 50 mm lens on a 36 mm sensor, the frame is depth*36/50 units wide
    frame_w = depth * 36.0 / 50.0
    img_w = frame_w / frac                     # the visible fraction of the image spans the frame width
    img_h = img_w * h / w
    bpy.ops.mesh.primitive_plane_add(size=1)
    p = bpy.context.object
    p.scale = (img_w, img_h, 1)
    # image point (u0, v0) must sit on the optical axis
    p.location = ((0.5 - u0) * img_w, (v0 - 0.5) * img_h, -depth)
    m = bpy.data.materials.new(img_path.stem)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Cubic"
    em = nt.nodes.new("ShaderNodeEmission")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(m, attr):
            try:
                setattr(m, attr, val)
            except Exception:
                pass
    p.data.materials.append(m)


def main() -> None:
    ex = sys.argv[sys.argv.index("--") + 1:]
    cfg = PRESETS[ex[0]]
    out = Path(ex[1])
    W = int(ex[2]) if len(ex) > 2 else 1920
    H = int(ex[3]) if len(ex) > 3 else 1080
    first = int(ex[4]) if len(ex) > 4 else 1
    last = int(ex[5]) if len(ex) > 5 else cfg["frames"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    world = bpy.data.worlds.new("Black")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = world
    for name, depth in cfg["planes"]:
        plane(PL / name, depth, cfg["view"], W / H)
    cam = bpy.data.cameras.new("Cam")
    cam.lens, cam.sensor_width, cam.sensor_fit = 50, 36, "HORIZONTAL"
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    for f, (x, y, z) in cfg["cam"]:
        co.location = (x, y, z)
        co.keyframe_insert("location", frame=f)
    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(n for n in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if n in avail)
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.frame_start, sc.frame_end = first, last
    out.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out / "px_")
    bpy.ops.render.render(animation=True)
    print(f"RENDERED {ex[0]} {first}-{last} -> {out}")


if __name__ == "__main__":
    main()
