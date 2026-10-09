"""v25 hero beat (frames 715-798, 29.79-33.29 s): one continuous Earth-to-Moon move, Blender EEVEE.

    blender.exe -b --factory-startup --python hero_v25.py -- <out_dir> [w h first last step] [--still-check]

Renders hr_0001..hr_0084.png (RGBA, film transparent: the bodies are opaque, the sky alpha 0, so the star layer is
composited by ALPHA in hero_post_v25.py, never by a black key). The camera, the bodies and the route all come from
blender/hero_path_v25.py (pure Python), so the 2D overlay (hud_v25) projects the same geometry.

Scene: the Moon is blender/moon_portrait.py's Moon EXACTLY (same sphere, NASA CGI Moon Kit colour + LDEM height,
displacement scale, rotation -20 deg, sun 5.5 at (80, 0, 58) deg, EEVEE, Standard view), so the last frame lands on
the locked portrait (frame 799). The Earth: Blue Marble Next Generation (December, topo + bathy, 8K) with the Blue
Marble cloud layer (cloud_combined_8192.tif, NASA Visible Earth 57747), the ascent beat's atmosphere shell, lit by
the same sun. Schematic, not to scale: the Earth sits ~25 Moon radii away (true ~221).
--still-check: also renders the last camera WITHOUT the LDEM height (displacement check) to <out_dir>/nodisp_0084.png.
"""
from __future__ import annotations

import json
import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hero_path_v25 as hp  # noqa: E402

KIT = (CRAFTWORK / "bg/nasa-moon")
BM = (CRAFTWORK / "inbox/moonshot/stills/bluemarble")
EARTH_ROT_Z = -77.0          # deg: Africa / Europe on the lit, camera-facing side at the start
EARTH_SPIN = 1.2             # deg over the shot (barely: alive, not a time-lapse)


def equirect(nt, L, obj_coord_socket):
    """Equirectangular UV from object-space normals (lon 0 on +X), as blender/ascent3d_v23.py."""
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(obj_coord_socket, nrm.inputs[0])
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    L.new(nrm.outputs[0], sep.inputs[0])
    at = nt.nodes.new("ShaderNodeMath")
    at.operation = "ARCTAN2"
    L.new(sep.outputs["Y"], at.inputs[0])
    L.new(sep.outputs["X"], at.inputs[1])
    u = nt.nodes.new("ShaderNodeMath")
    u.operation = "MULTIPLY_ADD"
    L.new(at.outputs[0], u.inputs[0])
    u.inputs[1].default_value = 1 / (2 * math.pi)
    u.inputs[2].default_value = 0.5
    asn = nt.nodes.new("ShaderNodeMath")
    asn.operation = "ARCSINE"
    L.new(sep.outputs["Z"], asn.inputs[0])
    v = nt.nodes.new("ShaderNodeMath")
    v.operation = "MULTIPLY_ADD"
    L.new(asn.outputs[0], v.inputs[0])
    v.inputs[1].default_value = 1 / math.pi
    v.inputs[2].default_value = 0.5
    cmb = nt.nodes.new("ShaderNodeCombineXYZ")
    L.new(u.outputs[0], cmb.inputs["X"])
    L.new(v.outputs[0], cmb.inputs["Y"])
    return cmb.outputs[0]


def build_moon():
    """moon_portrait.py's Moon, unchanged."""
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
    link = l.new(disp.outputs["Displacement"], n["Material Output"].inputs["Displacement"])
    moon.data.materials.append(mat)
    moon.rotation_euler = (0, 0, math.radians(-20))
    return moon, mat, link


def build_earth():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=hp.RE, location=hp.EARTH)
    earth = bpy.context.object
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Earth")
    m.use_nodes = True
    nt, L = m.node_tree, m.node_tree.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    uv = equirect(nt, L, tc.outputs["Object"])
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(BM / "bluemarble_8k.jpg"))
    img.interpolation = "Cubic"
    L.new(uv, img.inputs["Vector"])
    cl = nt.nodes.new("ShaderNodeTexImage")
    cl.image = bpy.data.images.load(str(BM / "cloud_combined_8192.tif"))
    cl.image.colorspace_settings.name = "Non-Color"
    cl.interpolation = "Cubic"
    L.new(uv, cl.inputs["Vector"])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    L.new(cl.outputs["Color"], bw.inputs[0])
    pw = nt.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    L.new(bw.outputs[0], pw.inputs[0])
    pw.inputs[1].default_value = 0.9
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    L.new(pw.outputs[0], mix.inputs["Factor"])
    L.new(img.outputs["Color"], mix.inputs["A"])
    mix.inputs["B"].default_value = (0.92, 0.93, 0.95, 1)
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    for name in ("Specular IOR Level", "Specular"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    L.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    earth.data.materials.append(m)
    earth.rotation_euler = (0, 0, math.radians(EARTH_ROT_Z))
    earth.keyframe_insert("rotation_euler", frame=1)
    earth.rotation_euler = (0, 0, math.radians(EARTH_ROT_Z + EARTH_SPIN))
    earth.keyframe_insert("rotation_euler", frame=hp.N)
    for fc in earth.animation_data.action.fcurves if hasattr(earth.animation_data.action, "fcurves") else []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"

    # thin atmosphere shell (ascent3d_v23.py's recipe), additive, culled back faces
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=hp.RE * 1.015, location=hp.EARTH)
    atm = bpy.context.object
    bpy.ops.object.shade_smooth()
    am = bpy.data.materials.new("Atmos")
    am.use_nodes = True
    an, al = am.node_tree, am.node_tree.links
    for nd in list(an.nodes):
        an.nodes.remove(nd)
    lw = an.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    em = an.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.25, 0.55, 1.0, 1)
    p2 = an.nodes.new("ShaderNodeMath")
    p2.operation = "POWER"
    al.new(lw.outputs["Facing"], p2.inputs[0])
    p2.inputs[1].default_value = 9.0
    mul = an.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    al.new(p2.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = 0.55
    # lit side only (a ring around the night side read as a ghost circle in preview 1): * clamp(N . sun + 0.15)
    geo = an.nodes.new("ShaderNodeNewGeometry")
    dp = an.nodes.new("ShaderNodeVectorMath")
    dp.operation = "DOT_PRODUCT"
    al.new(geo.outputs["Normal"], dp.inputs[0])
    dp.inputs[1].default_value = hp.sun_dir()
    lit = an.nodes.new("ShaderNodeMath")
    lit.operation = "ADD"
    lit.use_clamp = True
    al.new(dp.outputs["Value"], lit.inputs[0])
    lit.inputs[1].default_value = 0.15
    m2 = an.nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    al.new(mul.outputs[0], m2.inputs[0])
    al.new(lit.outputs[0], m2.inputs[1])
    al.new(m2.outputs[0], em.inputs["Strength"])
    tr = an.nodes.new("ShaderNodeBsdfTransparent")
    add = an.nodes.new("ShaderNodeAddShader")
    al.new(em.outputs[0], add.inputs[0])
    al.new(tr.outputs[0], add.inputs[1])
    out = an.nodes.new("ShaderNodeOutputMaterial")
    al.new(add.outputs[0], out.inputs[0])
    for attr, val in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        if hasattr(am, attr):
            try:
                setattr(am, attr, val)
            except Exception:
                pass
    am.use_backface_culling = True
    atm.data.materials.append(am)
    return earth


def look_at_matrix(pos, tgt) -> Matrix:
    rt, up, fw = hp.basis(pos, tgt)
    # Blender camera: looks down local -Z, local +Y up, local +X right
    m = Matrix(((rt[0], up[0], -fw[0], pos[0]),
                (rt[1], up[1], -fw[1], pos[1]),
                (rt[2], up[2], -fw[2], pos[2]),
                (0, 0, 0, 1)))
    return m


def main() -> None:
    ex = sys.argv[sys.argv.index("--") + 1:]
    flags = {a for a in ex if a.startswith("--")}
    ex = [a for a in ex if not a.startswith("--")]
    out = Path(ex[0])
    w = int(ex[1]) if len(ex) > 1 else 1920
    h = int(ex[2]) if len(ex) > 2 else 1080
    first = int(ex[3]) if len(ex) > 3 else 1
    last = int(ex[4]) if len(ex) > 4 else hp.N
    step = int(ex[5]) if len(ex) > 5 else 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    world = bpy.data.worlds.new("Space")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = world

    moon, moon_mat, disp_link = build_moon()
    build_earth()

    sun = bpy.data.lights.new("Sun", type="SUN")
    sun.energy = 5.5
    sun.angle = math.radians(0.53)
    so = bpy.data.objects.new("Sun", sun)
    so.rotation_euler = tuple(math.radians(v) for v in hp.SUN_ROT)
    sc.collection.objects.link(so)

    cam = bpy.data.cameras.new("Cam")
    cam.lens = hp.LENS
    cam.sensor_width = hp.SENSOR
    cam.sensor_fit = "HORIZONTAL"
    cam.shift_x = hp.SHIFT_X
    cam.clip_end = 500
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    prev = None
    for k in range(hp.N):
        pos, tgt = hp.camera(k)
        m = look_at_matrix(pos, tgt)
        co.location = m.to_translation()
        co.rotation_euler = m.to_euler("XYZ", prev) if prev is not None else m.to_euler("XYZ")
        prev = co.rotation_euler.copy()
        co.keyframe_insert("location", frame=k + 1)
        co.keyframe_insert("rotation_euler", frame=k + 1)

    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(x for x in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if x in avail)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = True
    sc.render.use_motion_blur = True
    sc.render.motion_blur_shutter = 0.35   # preview 5: 0.5 smeared the Moon in the fast stretch (frames 760-772)
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    out.mkdir(parents=True, exist_ok=True)

    # projection check: Blender's own projection of the body centres vs hero_path_v25's, every frame
    from bpy_extras.object_utils import world_to_camera_view
    chk = {}
    for k in range(hp.N):
        sc.frame_set(k + 1)
        pos, tgt = hp.camera(k)
        row = {}
        for name, c in (("moon", hp.MOON), ("earth", hp.EARTH)):
            v = world_to_camera_view(sc, co, Vector(c))
            mine = hp.project(c, pos, tgt)
            row[name] = [round(v.x * hp.W - mine[0], 3) if v.z > 0 else None,
                         round((1 - v.y) * hp.H - mine[1], 3) if v.z > 0 else None]
        chk[k + 1] = row
    (out / "projection_check.json").write_text(json.dumps(chk), encoding="utf-8")

    for f in range(first, last + 1, step):
        sc.frame_set(f)
        sc.render.filepath = str(out / f"hr_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"RENDERED frames {first}-{last} step {step} -> {out}")

    if "--still-check" in flags:
        sc.frame_set(hp.N)
        moon_mat.node_tree.links.remove(disp_link)
        sc.render.filepath = str(out / f"nodisp_{hp.N:04d}.png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED nodisp check")


if __name__ == "__main__":
    main()
