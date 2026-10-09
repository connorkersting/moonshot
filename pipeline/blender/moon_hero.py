"""Photoreal Moon still from NASA's CGI Moon Kit (SVS #4720, public domain), Blender headless (EEVEE).
Framed as an approach shot: the near side fills the lower frame, terminator raking across Mare Tranquillitatis.

    blender.exe -b --factory-startup --python moon_hero.py -- <out.png> [width height]

The compositor animates a slow push + drift over this 4K still (and a separate star layer for parallax).
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy

KIT = (CRAFTWORK / "bg/nasa-moon")
COLOR = KIT / "lroc_color_16bit_srgb_4k.tif"
ELEV = KIT / "ldem_16.tif"


def main() -> None:
    extra = sys.argv[sys.argv.index("--") + 1:]
    out = Path(extra[0])
    w = int(extra[1]) if len(extra) > 1 else 3840
    h = int(extra[2]) if len(extra) > 2 else 2160
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("Space")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    scene.world = world

    bpy.ops.mesh.primitive_uv_sphere_add(segments=384, ring_count=192, radius=1.0)
    moon = bpy.context.object
    bpy.ops.object.shade_smooth()
    # Sea of Tranquility (~23.5 E, 0.7 N) turned toward the camera, slightly right of centre
    moon.rotation_euler = (0, 0, math.radians(180 + 90 - 23.5 - 12))
    mat = bpy.data.materials.new("Moon")
    mat.use_nodes = True
    n, l = mat.node_tree.nodes, mat.node_tree.links
    bsdf = n["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.97
    col = n.new("ShaderNodeTexImage")
    col.image = bpy.data.images.load(str(COLOR))
    l.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    hgt = n.new("ShaderNodeTexImage")
    hgt.image = bpy.data.images.load(str(ELEV))
    hgt.image.colorspace_settings.name = "Non-Color"
    disp = n.new("ShaderNodeDisplacement")
    disp.inputs["Scale"].default_value = 0.006
    l.new(hgt.outputs["Color"], disp.inputs["Height"])
    l.new(disp.outputs["Displacement"], n["Material Output"].inputs["Displacement"])
    moon.data.materials.append(mat)

    sun = bpy.data.lights.new("Sun", type="SUN")
    sun.energy = 5.0
    sun.angle = math.radians(0.53)
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = (math.radians(90), 0, math.radians(125))   # low raking light -> long crater shadows
    scene.collection.objects.link(so)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 60
    co = bpy.data.objects.new("Cam", cam)
    co.location = (0.0, -3.05, 0.55)          # close: limb arcs across the upper third
    co.rotation_euler = (math.radians(82), 0, 0)
    scene.collection.objects.link(co)
    scene.camera = co

    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = next(x for x in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if x in avail)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    out.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print(f"RENDERED {out}")


if __name__ == "__main__":
    main()
