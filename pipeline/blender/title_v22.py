"""MOONSHOT v22 title: title_v18.py (unchanged, tag v21-src) with a light rig that makes the bevel read (Fable, carried
since v19: "the fire-lit bevel reads as a flat brown label at 1080p and 360p in both uses"):
  rim   1.6x the v18 energy on the opening (the end card 2.6x of its v18 0.35 glow scale), a tighter source (4 text
        heights, v18 6) a little higher behind the letters, so the bevel and the letters' top edges catch a bright line;
        on the end card the rim is paler (moonlight, not engine fire);
  fill  NEW weak cool fill from the left (about 1/6 of the key), so the left faces of the bevels separate from the
        letter faces instead of falling into one brown value.
Geometry, material, camera, timing, frame counts and file names are the v18 ones. Output folder: work/title3d_v22
(raw renders in a scratch folder, then title_post_v18.py for the bloom, unchanged).

v18 docstring follows.
MOONSHOT v18 title (Blender 5.2 EEVEE, transparent film): matte brushed metal, warm engine-fire edge glow, slight
depth of field, slow push. Replaces the chrome/bevel fly-in of title_anim.py (critics on v17: "massive dated 3D
title eclipses the liftoff", "chrome bevel reads early-2000s", "2009 AE preset").

    blender.exe -b --factory-startup --python title_v18.py -- <out_dir> <open|end> [w h first last]

open: 104 frames for the 13.00-17.25 title window (build.py title_layer uses idx 0..102). The title is framed with
      lens shift in the open sky right of the launch tower (centre x 1380, y ~400 at 1920x1080, ~44% of the frame width;
      the rocket + tower are x 400-860, the caption box x ~650-1270 / y 892-1006), rises ~190 px over the first ~1.3 s
      and drifts up slowly while the camera pushes in.
end:  56 frames for the end card (83.4-85.5 logical): centred, ~52% width, between the Earth (y < 115) and the date
      line (y 510), slow push + drift; the fire glow at a third (it is the Moon).
Raw RGBA PNGs (straight alpha) go to <out_dir>/<mode>_####.png; title_post_v18.py adds the bloom.
"""
from __future__ import annotations

import math
import random
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy
from mathutils import Vector

FONT = (CRAFTWORK / "fonts/Anton-Regular.ttf")
HDRI = (CRAFTWORK / "bg/hdri/studio_small_09.hdr")
W0, H0 = 1920, 1080
MODES = {
    # frames, centre px (x, y) at the end of the rise, width fraction, rise px, yaw deg (start, end), push (start, end),
    # glow scale
    "open": dict(n=104, cx=1380, cy=400, frac=0.44, rise=190, yaw=(-10.0, -5.0), push=(1.05, 0.965), glow=1.0,
                 rim=1.6, rim_col=(1.0, 0.52, 0.2)),
    "end": dict(n=56, cx=960, cy=318, frac=0.52, rise=0, yaw=(5.0, 2.5), push=(1.035, 0.985), glow=0.35,
                rim=0.9, rim_col=(1.0, 0.82, 0.62)),
}
FILL = 70.0          # v22: weak cool fill from the left, in text-height^2 units (key 420)


def area(name, energy, color, size, loc, aim=(0.0, 0.0, 0.0)):
    """Area light at loc whose emitting side (-Z) points at `aim`."""
    lt = bpy.data.lights.new(name, type="AREA")
    lt.energy, lt.color, lt.size = energy, color, size
    ob = bpy.data.objects.new(name, lt)
    ob.location = loc
    ob.rotation_euler = (Vector(aim) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def ease_out(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def metal_material(glow: float) -> bpy.types.Material:
    """Brushed, low-specular metal: roughness 0.38-0.52 streaked along the letters' x axis, faint bump, specular
    IOR level 0.25. Warm emission only on grazing faces (bevel / sides) and stronger toward the letters' feet."""
    mat = bpy.data.materials.new("BrushedMetal")
    mat.use_nodes = True
    nt, L = mat.node_tree, mat.node_tree.links
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.46, 0.45, 0.43, 1.0)
    b.inputs["Metallic"].default_value = 0.85
    if "Specular IOR Level" in b.inputs:
        b.inputs["Specular IOR Level"].default_value = 0.2
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1.5, 160.0, 1.5)        # streaks run along x (brushed)
    L.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 6.0
    L.new(mp.outputs["Vector"], nz.inputs["Vector"])
    rr = nt.nodes.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.50
    rr.inputs["To Max"].default_value = 0.64
    L.new(nz.outputs["Fac"], rr.inputs["Value"])
    L.new(rr.outputs["Result"], b.inputs["Roughness"])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.04
    L.new(nz.outputs["Fac"], bump.inputs["Height"])
    L.new(bump.outputs["Normal"], b.inputs["Normal"])
    # warm edge glow: (1 - facing)^2.2 x foot gradient (object-space y: the letters' feet are y < 0)
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "POWER"
    L.new(lw.outputs["Facing"], inv.inputs[0])
    inv.inputs[1].default_value = 2.2
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(tc.outputs["Object"], sep.inputs[0])
    grad = nt.nodes.new("ShaderNodeMapRange")       # y 0.45 (top) -> 0.25, y -0.45 (feet) -> 1.0
    grad.inputs["From Min"].default_value = 0.45
    grad.inputs["From Max"].default_value = -0.45
    grad.inputs["To Min"].default_value = 0.25
    grad.inputs["To Max"].default_value = 1.0
    L.new(sep.outputs["Y"], grad.inputs["Value"])
    m1 = nt.nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    L.new(inv.outputs[0], m1.inputs[0])
    L.new(grad.outputs["Result"], m1.inputs[1])
    m2 = nt.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    L.new(m1.outputs[0], m2.inputs[0])
    m2.inputs[1].default_value = 2.4 * glow
    b.inputs["Emission Color"].default_value = (1.0, 0.40, 0.11, 1.0)
    L.new(m2.outputs[0], b.inputs["Emission Strength"])
    return mat


def build(mode: str) -> None:
    cfg = MODES[mode]
    n = cfg["n"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    sc.frame_start, sc.frame_end = 1, n
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    wn = world.node_tree
    env = wn.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(HDRI))
    wn.links.new(env.outputs["Color"], wn.nodes["Background"].inputs["Color"])
    wn.nodes["Background"].inputs["Strength"].default_value = 0.32
    sc.world = world

    bpy.ops.object.text_add(location=(0, 0, 0))
    t = bpy.context.object
    t.data.body = "MOONSHOT"
    t.data.font = bpy.data.fonts.load(str(FONT))
    t.data.align_x, t.data.align_y = "CENTER", "CENTER"
    t.data.space_character = 1.12          # a touch more tracking than v17 (1.06)
    t.data.extrude = 0.06                  # v17: 0.16 deep slab + 0.024 bevel
    t.data.bevel_depth = 0.006
    t.data.bevel_resolution = 2
    t.data.materials.append(metal_material(cfg["glow"]))
    t.rotation_euler = (math.radians(90), 0, 0)
    bpy.context.view_layer.update()
    tw, th = t.dimensions.x, t.dimensions.y

    cam = bpy.data.cameras.new("Cam")
    cam.lens = 70
    cam.sensor_fit = "HORIZONTAL"
    cam.sensor_width = 36
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    # distance at which the text spans cfg["frac"] of the frame width; lens shift puts its centre at (cx, cy)
    D = tw / (cfg["frac"] * cam.sensor_width / cam.lens)
    cam.shift_x = -(cfg["cx"] - W0 / 2) / W0
    cam.shift_y = (cfg["cy"] - H0 / 2) / W0
    cam.dof.use_dof = True
    cam.dof.focus_distance = D
    cam.dof.aperture_fstop = 2.0
    co.rotation_euler = (math.radians(90), 0, 0)
    frame_h_units = D * cam.sensor_width / cam.lens * H0 / W0
    rise_u = cfg["rise"] / H0 * frame_h_units
    rnd = random.Random(11)
    for f in range(1, n + 1):
        u = (f - 1) / max(n - 1, 1)
        p = cfg["push"][0] + (cfg["push"][1] - cfg["push"][0]) * smooth(u)
        co.location = (0.0, -D * p, 0.0)
        co.keyframe_insert("location", frame=f)
        # rise: ease-out over the first 32 frames, then a slow 12% drift for the rest
        r = ease_out((f - 1) / 31) * 0.88 + 0.12 * u if cfg["rise"] else 0.0
        t.location = (0.0, 0.0, -rise_u * (1 - r))
        t.keyframe_insert("location", frame=f)
        yaw = cfg["yaw"][0] + (cfg["yaw"][1] - cfg["yaw"][0]) * smooth(u)
        t.rotation_euler = (math.radians(90), 0, math.radians(yaw))
        t.keyframe_insert("rotation_euler", frame=f)

    s = th                                                           # light rig in text-height units
    # key: cool, high front-left; fire: warm, low front-left (the engines are lower-left of the title in the plate);
    # rim: warm, low behind (lights the back edges)
    # (test 2: fire light at front-left washed the faces out to peach; now from below, grazing the letters' feet)
    area("Key", 420 * s * s, (0.86, 0.9, 1.0), 8 * s, (-4 * s, -9 * s, 6 * s))
    under = area("Fire", 380 * s * s * cfg["glow"] + 40 * s * s, (1.0, 0.42, 0.12), 8 * s, (-2 * s, -1.2 * s, -5 * s))
    rim = area("Rim", 600 * s * s * cfg["rim"], cfg["rim_col"], 4 * s, (-1 * s, 3 * s, -1.8 * s))   # v22 (v18: x glow, 6 s, z -3 s)
    area("Fill", FILL * s * s, (0.86, 0.92, 1.0), 10 * s, (-11 * s, -5 * s, 1.0 * s))                 # v22: weak left fill
    if mode == "open":                                                   # engine-glow flicker (softer than v17)
        for f in range(1, n + 1, 3):
            k = 0.85 + 0.3 * rnd.random()
            under.data.energy = (380 * s * s + 40 * s * s) * k
            under.data.keyframe_insert("energy", frame=f)
            rim.data.energy = 600 * s * s * cfg["rim"] * k
            rim.data.keyframe_insert("energy", frame=f)
    print(f"text {tw:.3f} x {th:.3f}, D {D:.2f}, shift {cam.shift_x:.4f} {cam.shift_y:.4f}, rise {rise_u:.3f}")


def render(out_dir: Path, mode: str, w: int, h: int, first: int, last: int) -> None:
    sc = bpy.context.scene
    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(n for n in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if n in avail)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.film_transparent = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.5
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    if hasattr(sc, "eevee") and hasattr(sc.eevee, "taa_render_samples"):
        sc.eevee.taa_render_samples = 64
    sc.frame_start, sc.frame_end = first, last
    out_dir.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out_dir / f"{mode}_")
    bpy.ops.render.render(animation=True)


if __name__ == "__main__":
    ex = sys.argv[sys.argv.index("--") + 1:]
    out = Path(ex[0]).resolve()        # (Blender resolves a relative render path against the drive root)
    mode = ex[1]
    w = int(ex[2]) if len(ex) > 2 else 1920
    h = int(ex[3]) if len(ex) > 3 else 1080
    first = int(ex[4]) if len(ex) > 4 else 1
    last = int(ex[5]) if len(ex) > 5 else MODES[mode]["n"]
    build(mode)
    render(out, mode, w, h, first, last)
    print(f"RENDERED {mode} frames {first}-{last} -> {out}")
