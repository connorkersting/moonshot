"""v18 portrait still (moon_anim frame 1 framing, camera at 8.5). Photoreal Moon approach (NASA CGI Moon Kit, SVS #4720, public domain), Blender EEVEE.

    blender.exe -b --factory-startup --python moon_anim.py -- <out_dir> [width height first last]

96 frames = the 40.0-44.0 s lunar transition: the camera drifts in from a full gibbous disc toward the
limb, the Moon slowly turning, low sun raking the craters near the terminator. A sparse star field
is added by the compositor (stars would strobe in a fast EEVEE render).
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy

KIT = (CRAFTWORK / "bg/nasa-moon")


def main() -> None:
    ex = sys.argv[sys.argv.index("--") + 1:]
    out = Path(ex[0])
    w = int(ex[1]) if len(ex) > 1 else 1920
    h = int(ex[2]) if len(ex) > 2 else 1080
    first = int(ex[3]) if len(ex) > 3 else 1
    last = int(ex[4]) if len(ex) > 4 else 96
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    world = bpy.data.worlds.new("Space")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = world

    bpy.ops.mesh.primitive_uv_sphere_add(segments=384, ring_count=192, radius=1.0)
    moon = bpy.context.object
    bpy.ops.object.shade_smooth()
    mat = bpy.data.materials.new("Moon")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.97
    col = n.new("ShaderNodeTexImage")
    col.image = bpy.data.images.load(str(KIT / "lroc_color_16bit_srgb_4k.tif"))
    l.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    hgt = n.new("ShaderNodeTexImage")
    hgt.image = bpy.data.images.load(str(KIT / "ldem_16.tif"))
    hgt.image.colorspace_settings.name = "Non-Color"
    disp = n.new("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.007
    l.new(hgt.outputs["Color"], disp.inputs["Height"])
    l.new(disp.outputs["Displacement"], n["Material Output"].inputs["Displacement"])
    moon.data.materials.append(mat)
    moon.rotation_euler = (0, 0, math.radians(-20))
    moon.keyframe_insert("rotation_euler", frame=1)
    moon.rotation_euler = (0, 0, math.radians(-14))
    moon.keyframe_insert("rotation_euler", frame=96)

    sun = bpy.data.lights.new("Sun", type="SUN")
    sun.energy = 5.5
    sun.angle = math.radians(0.53)
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = (math.radians(80), 0, math.radians(58))   # from front-right: gibbous, terminator on the left
    sc.collection.objects.link(so)

    target = bpy.data.objects.new("Target", None)
    sc.collection.objects.link(target)
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 50
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    tr = co.constraints.new("TRACK_TO")
    tr.target = target
    tr.track_axis, tr.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    # start: full disc, slightly low; end: close over the limb, Moon filling the lower frame
    co.location = (0.25, -8.5, 0.1)   # v18 portrait: farther, the disc ~59% of frame height
    co.keyframe_insert("location", frame=1)
    target.location = (0.0, 0.0, 0.0)
    target.keyframe_insert("location", frame=1)
    co.location = (0.05, -2.45, 0.62)
    co.keyframe_insert("location", frame=96)
    target.location = (0.0, -0.35, 0.62)
    target.keyframe_insert("location", frame=96)

    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(x for x in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if x in avail)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.frame_start, sc.frame_end = first, last
    out.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out / "moon_")
    bpy.ops.render.render(animation=True)
    print(f"RENDERED frames {first}-{last} -> {out}")


if __name__ == "__main__":
    main()
