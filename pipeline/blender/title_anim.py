"""MOONSHOT animated hero title (Blender EEVEE, transparent film, real camera motion blur).

    blender.exe -b --factory-startup --python title_anim.py -- <out_dir> [width height first last]

110 frames @ 24 fps = the 13.00-17.58 s title window:
  f1-8    camera rockets in from deep space (text tiny -> full), slight roll
  f8-12   overshoot and settle
  f12-96  slow push-in, title turns a few degrees, engine-glow rim flickers
  f96-110 camera flies through the letters (the compositor cuts away at f102)
"""
from __future__ import annotations

import math
import random
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy

FONT = (CRAFTWORK / "fonts/Anton-Regular.ttf")
HDRI = (CRAFTWORK / "bg/hdri/studio_small_09.hdr")


def area(name, energy, color, size, loc, rot):
    lt = bpy.data.lights.new(name, type="AREA")
    lt.energy, lt.color, lt.size = energy, color, size
    ob = bpy.data.objects.new(name, lt)
    ob.location = loc
    ob.rotation_euler = tuple(math.radians(r) for r in rot)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def key(obj, frame, **kw):
    for k, v in kw.items():
        setattr(obj, k, v)
        obj.keyframe_insert(data_path=k, frame=frame)


def build() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, 110
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(HDRI))
    nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 1.1
    sc.world = world

    bpy.ops.object.text_add(location=(0, 0, 0))
    t = bpy.context.object
    t.data.body = "MOONSHOT"
    t.data.font = bpy.data.fonts.load(str(FONT))
    t.data.align_x, t.data.align_y = "CENTER", "CENTER"
    t.data.space_character = 1.06
    t.data.extrude = 0.16
    t.data.bevel_depth = 0.024
    t.data.bevel_resolution = 4
    mat = bpy.data.materials.new("Steel")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.88, 0.86, 0.82, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.26
    t.data.materials.append(mat)
    key(t, 1, rotation_euler=(math.radians(90), 0, math.radians(-22)))
    key(t, 10, rotation_euler=(math.radians(90), 0, math.radians(-7)))
    key(t, 96, rotation_euler=(math.radians(90), 0, math.radians(3)))

    area("Key", 650, (0.82, 0.9, 1.0), 5, (2.5, -5, 4), (50, 0, 25))
    rim = area("Rim", 2200, (1.0, 0.42, 0.10), 5, (0.0, 1.2, -2.4), (-140, 0, 180))
    area("Under", 900, (1.0, 0.5, 0.15), 6, (0.0, -3.0, -3.2), (35, 0, 0))   # fire-light bouncing up onto the faces
    rnd = random.Random(11)
    for f in range(1, 111, 3):                       # engine-glow flicker
        rim.data.energy = 2200 * (0.8 + 0.4 * rnd.random())
        rim.data.keyframe_insert(data_path="energy", frame=f)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 40
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    rot = (math.radians(90), 0, 0)
    key(co, 1, location=(0.3, -95.0, 0.6), rotation_euler=(rot[0], math.radians(-6), 0))
    key(co, 8, location=(0.0, -3.75, 0.04), rotation_euler=(rot[0], math.radians(1.2), 0))
    key(co, 12, location=(0.0, -4.1, 0.0), rotation_euler=rot)
    key(co, 96, location=(0.0, -3.4, -0.04), rotation_euler=rot)
    key(co, 110, location=(0.15, 0.6, 0.1), rotation_euler=rot)
    for fc in co.animation_data.action.fcurves if co.animation_data.action and hasattr(co.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"


def render(out_dir: Path, w: int, h: int, first: int, last: int) -> None:
    sc = bpy.context.scene
    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(n for n in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if n in avail)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.6
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    sc.frame_start, sc.frame_end = first, last
    out_dir.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out_dir / "title_")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    ex = sys.argv[sys.argv.index("--") + 1:]
    out = Path(ex[0])
    w = int(ex[1]) if len(ex) > 1 else 1920
    h = int(ex[2]) if len(ex) > 2 else 1080
    first = int(ex[3]) if len(ex) > 3 else 1
    last = int(ex[4]) if len(ex) > 4 else 110
    build()
    render(out, w, h, first, last)
    print(f"RENDERED frames {first}-{last} -> {out}")
