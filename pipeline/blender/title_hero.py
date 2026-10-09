"""MOONSHOT hero title, Blender headless (EEVEE). Renders transparent-background stills of the extruded
Anton title with a studio-HDRI brushed-steel material, a cool key and a hot engine-glow rim from below.

    blender.exe -b --factory-startup --python title_hero.py -- <out_dir> [width height]

Writes <out_dir>/title_hero.png (straight alpha). The fly-in / push / light sweep are animated in 2D by
the compositor (build.py), which keeps render time to one frame on an integrated GPU.
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy

FONT = (CRAFTWORK / "fonts/Anton-Regular.ttf")
HDRI = (CRAFTWORK / "bg/hdri/studio_small_09.hdr")


def args() -> tuple[Path, int, int]:
    extra = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out = Path(extra[0])
    w = int(extra[1]) if len(extra) > 1 else 1920
    h = int(extra[2]) if len(extra) > 2 else 1080
    return out, w, h


def area(name: str, energy: float, color: tuple, size: float, loc: tuple, rot: tuple) -> None:
    lt = bpy.data.lights.new(name, type="AREA")
    lt.energy, lt.color, lt.size = energy, color, size
    ob = bpy.data.objects.new(name, lt)
    ob.location = loc
    ob.rotation_euler = tuple(math.radians(r) for r in rot)
    bpy.context.scene.collection.objects.link(ob)


def build() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    nt = world.node_tree
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(HDRI))
    bg = nt.nodes["Background"]
    bg.inputs["Strength"].default_value = 1.2
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    scene.world = world

    bpy.ops.object.text_add(location=(0, 0, 0))
    t = bpy.context.object
    t.data.body = "MOONSHOT"
    t.data.font = bpy.data.fonts.load(str(FONT))
    t.data.align_x = "CENTER"
    t.data.align_y = "CENTER"
    t.data.space_character = 1.06
    t.data.extrude = 0.16
    t.data.bevel_depth = 0.022
    t.data.bevel_resolution = 4
    t.rotation_euler = (math.radians(90), 0, 0)

    mat = bpy.data.materials.new("Steel")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.86, 0.84, 0.80, 1.0)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.28
    t.data.materials.append(mat)

    area("Key", 700, (0.85, 0.92, 1.0), 5, (2.5, -5, 4), (50, 0, 25))          # cool moonlight key
    area("Rim", 1500, (1.0, 0.45, 0.12), 4, (0, 2.5, -2.6), (-125, 0, 180))     # engine glow from below/behind
    area("Fill", 120, (1.0, 0.8, 0.6), 6, (-4, -4, -1), (100, 0, -45))

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 50
    co = bpy.data.objects.new("Cam", cam)
    co.location = (0.0, -8.6, -0.35)
    co.rotation_euler = (math.radians(92.5), 0, 0)
    scene.collection.objects.link(co)
    scene.camera = co


def render(out_dir: Path, w: int, h: int) -> None:
    scene = bpy.context.scene
    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = next(n for n in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if n in avail)
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    out_dir.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(out_dir / "title_hero.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    o, W, H = args()
    build()
    render(o, W, H)
    print(f"RENDERED {o / 'title_hero.png'}")
