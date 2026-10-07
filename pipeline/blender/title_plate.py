"""MOONSHOT title "in the plate": same animation as title_anim.py, but the world the steel reflects is the
real Apollo 11 70mm launch plate (the frames the title sits on, as an animated environment) plus a still of the
ignition fireball, instead of a studio HDRI. Transparent film; build.py adds light wrap, shadow and the grade.

    blender.exe -b --factory-startup --python title_plate.py -- <out_dir> [w h first last]
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

HERE = Path(__file__).parent
ENV = HERE / "plate_env"
sys.path.insert(0, str(HERE))
import title_anim  # noqa: E402  (scene + animation)


def plate_world() -> None:
    sc = bpy.context.scene
    w = sc.world
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    seq = nt.nodes.new("ShaderNodeTexEnvironment")
    img = bpy.data.images.load(str(ENV / "env_0001.png"))
    img.source = "SEQUENCE"
    seq.image = img
    seq.image_user.frame_duration = len(list(ENV.glob("env_*.png")))
    seq.image_user.frame_start = 1
    seq.image_user.use_auto_refresh = True
    fire = nt.nodes.new("ShaderNodeTexEnvironment")
    fire.image = bpy.data.images.load(str(ENV / "fire_still.png"))
    # lower hemisphere = fire (light from below, like the engines), upper = the launch plate
    geo = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["From Min"].default_value = 0.12
    ramp.inputs["From Max"].default_value = 0.32
    nt.links.new(sep.outputs["Z"], ramp.inputs["Value"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(ramp.outputs[0], mix.inputs[0])
    nt.links.new(fire.outputs["Color"], mix.inputs[6])
    nt.links.new(seq.outputs["Color"], mix.inputs[7])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.35
    nt.links.new(mix.outputs[2], bg.inputs["Color"])
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs[0])


if __name__ == "__main__":
    ex = sys.argv[sys.argv.index("--") + 1:]
    o = Path(ex[0])
    W = int(ex[1]) if len(ex) > 1 else 1920
    H = int(ex[2]) if len(ex) > 2 else 1080
    a = int(ex[3]) if len(ex) > 3 else 1
    b = int(ex[4]) if len(ex) > 4 else 110
    title_anim.build()
    plate_world()
    title_anim.render(o, W, H, a, b)
    print(f"RENDERED plate title {a}-{b} -> {o}")
