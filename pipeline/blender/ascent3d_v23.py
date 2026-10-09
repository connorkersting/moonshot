"""v23 (ascent3d_v23.py, renders ascent_blender_v23): a copy of ascent3d_v5.py with ALL baked text disabled, plus a
per-frame screen-geometry export so the 2D overlay (hud_v23.ascent_overlay) can place its labels clear of the scene.

Changes from v5 (everything else, including the camera, Earth, atmosphere, tube, rings, their fades and the glare,
is byte-for-byte the v5 logic):
  1. No text objects are created: the MAX Q / INBOARD ENGINE CUTOFF labels, the MISSION TIME / ALTITUDE / VELOCITY
     readouts, the "ASCENT · FIRST 3 MINUTES" title and the "EXAGGERATED 6x" note are gone from the render. They are
     drawn in 2D by hud_v23 in the unified hud_v22 system (the v10-v22 collision: the baked labels were struck by
     their own rings and the trajectory tube at ~23.5-25.0 s).
  2. The rings keep v5's fade law exactly (3 mission-seconds in from et - 1, out as the ring's projected y drops from
     18% to 12% of the frame height), so the 2D labels can reuse the same k per frame.
  3. geometry.json (next to the PNGs): for every rendered frame, in 1920x1080 pixel coordinates (x right, y down):
       mission_t; head [x, y]; tube: projected polyline of the revealed tube (1 mission-second steps + the head) with a
       per-point projected radius in px; rings: per event its centre, projected bbox (major + minor radius), fade k
       and visibility; limb: the projected silhouette of the atmosphere shell (R * 1.012) as a polyline of on-screen
       points; values: the PAO-called values exactly as v5 formatted them (T+{t:.0f} S, {alt:.1f} NMI, {mph:,.0f} MPH).
  4. --geometry-only: steps the frames and writes geometry.json without rendering (seconds, not ~25 min).

    blender.exe -b --factory-startup --python ascent3d_v23.py -- <out_dir> [w h first last] [--geometry-only]

v5 docstring (still true for the scene):
MOONSHOT 3D ascent beat (Blender EEVEE): Apollo 11's first three minutes as a glowing trajectory tube rising off a NASA
Blue Marble Earth from Cape Canaveral, the camera chasing the tube head. 192 frames @ 24 fps. Mission time runs
T+0 -> T+180 s (eased), then holds. Altitude and downrange are both exaggerated 6x so the climb reads on screen.
Data (nautical miles, ft/s) = PAO call-outs re-timed per the AS-506 flight evaluation report: T+56 2 nmi; T+66 4 nmi,
2,195 ft/s (Mach 1); T+106 12 nmi, 4,000 ft/s; T+148 30 nmi; T+180 43 nmi, 9,300 ft/s, 70 nmi downrange.
Max Q T+83.0, center (inboard) engine cutoff T+135.2.
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

EARTH = (CRAFTWORK / "inbox/moonshot/stills/bluemarble/bluemarble_8k.jpg")
R = 10.0                 # Earth radius in scene units
NMI_R = 3440.0           # Earth radius in nautical miles
EX = 6.0                 # exaggeration for altitude and downrange
LAT, LON = 28.573, -80.649   # LC-39A
AZ = 72.0                # launch azimuth, degrees from north
FRAMES = 192
ALT = [(0, 0.0), (30, 0.6), (56, 2.0), (66, 4.0), (106, 12.0), (148, 30.0), (180, 43.0)]
DR = [(0, 0.0), (66, 1.0), (106, 8.0), (148, 35.0), (180, 70.0)]
VEL = [(0, 0.0), (66, 2195.0), (106, 4000.0), (180, 9300.0)]
EVENTS = [(83.0, "MAX Q"), (135.2, "INBOARD ENGINE CUTOFF")]
AMBER = (1.0, 0.62, 0.18)
TUBE_R = 0.012
RING_MAJOR, RING_MINOR = 0.06, 0.004
ATM_R = R * 1.012
GEOM: dict[int, dict] = {}


def interp(tab, x):
    if x <= tab[0][0]:
        return tab[0][1]
    for (x0, y0), (x1, y1) in zip(tab, tab[1:]):
        if x <= x1:
            u = (x - x0) / (x1 - x0)
            u = u * u * (3 - 2 * u) * 0.35 + u * 0.65       # gentle smoothing inside segments
            return y0 + (y1 - y0) * u
    return tab[-1][1]


def mission_t(frame: int) -> float:
    u = min(max((frame - 6) / (FRAMES - 30), 0.0), 1.0)
    return 180.0 * (u * u * (3 - 2 * u) * 0.5 + u * 0.5)


def frames_basis():
    la, lo = math.radians(LAT), math.radians(LON)
    up = Vector((math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)))
    east = Vector((-math.sin(lo), math.cos(lo), 0.0))
    north = up.cross(east).normalized()
    head = (north * math.cos(math.radians(AZ)) + east * math.sin(math.radians(AZ))).normalized()
    return up, head


UP, HEAD = frames_basis()
AXIS = UP.cross(HEAD).normalized()


def pos(t: float) -> Vector:
    theta = interp(DR, t) * EX / NMI_R
    rad = R * (1 + interp(ALT, t) * EX / NMI_R)
    return (Matrix.Rotation(theta, 3, AXIS) @ UP) * rad


def emission(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (*color, 1)
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def fading_emission(name, color, strength):
    """v18: emission mixed with transparency; the material's 'Fade' value node (0..1) is set per frame."""
    m = emission(name, color, strength)
    nt = m.node_tree
    em = next(n for n in nt.nodes if n.type == "EMISSION")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    val = nt.nodes.new("ShaderNodeValue")
    val.name = "Fade"
    val.outputs[0].default_value = 1.0
    nt.links.new(val.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def ndc(campos, camrot, lens_ratio, aspect, p):
    """Normalized frame position (x right, y up, 0..1) of world point p for a camera at campos with rotation camrot
    (Euler), horizontal sensor fit; lens_ratio = lens / sensor_width."""
    q = camrot.to_matrix().transposed() @ (p - campos)
    if q.z >= -1e-6:
        return 0.5, -1.0
    return 0.5 + q.x / -q.z * lens_ratio, 0.5 + q.y / -q.z * lens_ratio * aspect


def project_px(campos, camrot, lens_ratio, w, h, p):
    """v23: pixel position (x right, y down) and depth of world point p; None when behind the camera."""
    q = camrot.to_matrix().transposed() @ (p - campos)
    if q.z >= -1e-6:
        return None
    x = 0.5 + q.x / -q.z * lens_ratio
    y = 0.5 + q.y / -q.z * lens_ratio * (w / h)
    return x * w, (1.0 - y) * h, -q.z


def build() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    world = bpy.data.worlds.new("Space")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    sc.world = world

    # Earth: equirectangular Blue Marble mapped from object-space normals (lon 0 on +X, matching the map)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=R)
    earth = bpy.context.object
    bpy.ops.object.shade_smooth()
    m = bpy.data.materials.new("Earth")
    m.use_nodes = True
    nt, L = m.node_tree, m.node_tree.links
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nrm = nt.nodes.new("ShaderNodeVectorMath")
    nrm.operation = "NORMALIZE"
    L.new(tc.outputs["Object"], nrm.inputs[0])
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
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(EARTH))
    img.interpolation = "Cubic"
    L.new(cmb.outputs[0], img.inputs["Vector"])
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.9
    for name in ("Specular IOR Level", "Specular"):          # no milky sheen over the oceans
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.0
    L.new(img.outputs["Color"], bsdf.inputs["Base Color"])
    earth.data.materials.append(m)

    # thin atmosphere shell: fresnel-weighted blue emission, additive
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=ATM_R)
    atm = bpy.context.object
    bpy.ops.object.shade_smooth()
    am = bpy.data.materials.new("Atmos")
    am.use_nodes = True
    an, al = am.node_tree, am.node_tree.links
    for n in list(an.nodes):
        an.nodes.remove(n)
    lw = an.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    em = an.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.25, 0.55, 1.0, 1)
    pw = an.nodes.new("ShaderNodeMath")
    pw.operation = "POWER"
    al.new(lw.outputs["Facing"], pw.inputs[0])
    pw.inputs[1].default_value = 9.0
    mul = an.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    al.new(pw.outputs[0], mul.inputs[0])
    mul.inputs[1].default_value = 0.7
    al.new(mul.outputs[0], em.inputs["Strength"])
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

    sun = bpy.data.lights.new("Sun", type="SUN")
    sun.energy = 9.0
    so = bpy.data.objects.new("Sun", sun)
    # morning sun from the east-southeast of the Cape
    sdir = (UP * 0.55 + HEAD * 0.6 + AXIS * -0.55).normalized()
    so.rotation_euler = sdir.to_track_quat("Z", "Y").to_euler()
    sc.collection.objects.link(so)

    # trajectory tube: a poly curve through the whole ascent, revealed with bevel_factor_end
    cu = bpy.data.curves.new("Traj", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = TUBE_R
    cu.bevel_resolution = 4
    sp = cu.splines.new("POLY")
    ts = [i * 1.0 for i in range(0, 181)]
    sp.points.add(len(ts) - 1)
    for p, t in zip(sp.points, ts):
        q = pos(t)
        p.co = (q.x, q.y, q.z, 1)
    tube = bpy.data.objects.new("Traj", cu)
    sc.collection.objects.link(tube)
    tube.visible_shadow = False
    tube.data.materials.append(emission("Glow", AMBER, 1.6))
    # head: a bright point
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.02)
    headobj = bpy.context.object
    headobj.visible_shadow = False
    headobj.data.materials.append(emission("Head", (1.0, 0.9, 0.7), 8.0))

    # event markers: ring only (v23: the 3D labels are not created; hud_v23 draws them in 2D)
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 30
    cam.clip_start = 0.005
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    markers = []
    for et, name in EVENTS:
        p = pos(et)
        bpy.ops.mesh.primitive_torus_add(major_radius=RING_MAJOR, minor_radius=RING_MINOR, location=p)
        ring = bpy.context.object
        ring.rotation_euler = (pos(et + 1) - pos(et - 1)).to_track_quat("Z", "Y").to_euler()
        ring.data.materials.append(fading_emission("Ring", (0.55, 0.86, 1.0), 2.0))
        ring.hide_render = True
        ring.visible_shadow = False
        markers.append((et, name, ring))

    # v23: no HUD readouts, no title, no note (v5 built them here as camera-parented 3D text)

    def update(scene, *_):
        f = scene.frame_current
        t = mission_t(f)
        hpos = pos(t)
        headobj.location = hpos
        tube.data.bevel_factor_end = max(t / 180.0, 0.002)
        # chase camera: behind and above the head, looking a little ahead, Earth's limb in frame
        upv = hpos.normalized()
        theta = interp(DR, t) * EX / NMI_R
        fwd = (Matrix.Rotation(theta, 3, AXIS) @ HEAD).normalized()      # local horizontal, downrange
        side = fwd.cross(upv).normalized()
        k = 1.1 + 0.6 * (t / 180.0)
        base = upv * R                                                   # ground point under the head
        campos = base + upv * (0.35 + 1.1 * interp(ALT, t) * EX / NMI_R * R) - fwd * k - side * 0.85
        co.location = campos
        look = hpos * 0.6 + (base + fwd * 0.6) * 0.4
        co.rotation_euler = (look - campos).to_track_quat("-Z", "Y").to_euler()
        rotq = (look - campos).to_track_quat("-Z", "Y").to_euler()
        lr = cam.lens / cam.sensor_width
        w, h = scene.render.resolution_x, scene.render.resolution_y
        asp = w / h
        fpx = lr * w                                       # focal length in px (horizontal fit)
        g = {"mission_t": round(t, 4),
             "values": {"clock": f"T+{t:.0f} S", "alt": f"{interp(ALT, t):.1f} NMI",
                        "vel": f"{interp(VEL, t) * 0.681818:,.0f} MPH"},
             "rings": []}
        hp = project_px(campos, rotq, lr, w, h, hpos)
        g["head"] = [round(hp[0], 2), round(hp[1], 2)] if hp else None
        # revealed tube: 1 s steps up to t, plus the head; per-point projected radius
        tube_pts = []
        for ti in [float(i) for i in range(0, int(t) + 1)] + [t]:
            pp = project_px(campos, rotq, lr, w, h, pos(ti))
            if pp:
                tube_pts.append([round(pp[0], 2), round(pp[1], 2), round(TUBE_R * fpx / pp[2], 3)])
        g["tube"] = tube_pts
        for et, name, ring in markers:
            vis = et - 1.0 <= t
            _, y = ndc(campos, rotq, lr, asp, pos(et))
            kk = min(max((t - (et - 1.0)) / 3.0, 0.0), 1.0) * min(max((y - 0.12) / 0.06, 0.0), 1.0)
            kk = kk * kk * (3 - 2 * kk)
            vis = vis and kk > 0.002
            ring.hide_render = not vis
            ring.active_material.node_tree.nodes["Fade"].outputs[0].default_value = kk
            # ring outline: 48 points on the major circle in the ring's own plane, padded by the minor radius
            rm = ring.rotation_euler.to_matrix()
            c = pos(et)
            pts = []
            for i in range(48):
                a = 2 * math.pi * i / 48
                pw_ = c + rm @ Vector((math.cos(a) * RING_MAJOR, math.sin(a) * RING_MAJOR, 0.0))
                pp = project_px(campos, rotq, lr, w, h, pw_)
                if pp:
                    pad = RING_MINOR * fpx / pp[2]
                    pts.append((pp[0] - pad, pp[1] - pad, pp[0] + pad, pp[1] + pad))
            cc = project_px(campos, rotq, lr, w, h, c)
            g["rings"].append({
                "event_t": et, "name": name, "visible": bool(vis), "k": round(kk, 4),
                "center": [round(cc[0], 2), round(cc[1], 2)] if cc else None,
                "bbox": [round(min(p[0] for p in pts), 2), round(min(p[1] for p in pts), 2),
                         round(max(p[2] for p in pts), 2), round(max(p[3] for p in pts), 2)] if pts else None,
            })
        # limb: the silhouette circle of the atmosphere shell seen from campos
        d = campos.length
        rs = ATM_R * math.sqrt(max(1.0 - (ATM_R / d) ** 2, 0.0))
        cs = campos.normalized() * (ATM_R ** 2 / d)
        nrm_ = campos.normalized()
        e1 = nrm_.cross(Vector((0.0, 0.0, 1.0)))
        if e1.length < 1e-6:
            e1 = nrm_.cross(Vector((1.0, 0.0, 0.0)))
        e1.normalize()
        e2 = nrm_.cross(e1).normalized()
        limb = []
        for i in range(2048):
            a = 2 * math.pi * i / 2048
            pp = project_px(campos, rotq, lr, w, h, cs + (e1 * math.cos(a) + e2 * math.sin(a)) * rs)
            if pp and -200 <= pp[0] <= w + 200 and -200 <= pp[1] <= h + 200:
                limb.append([round(pp[0], 2), round(pp[1], 2)])
        g["limb"] = limb
        GEOM[f] = g

    bpy.app.handlers.frame_change_pre.append(update)
    sc.frame_set(1)


def setup_render(w: int, h: int) -> None:
    sc = bpy.context.scene
    avail = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = next(n for n in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if n in avail)
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    # bloom via the compositor's Glare (fog glow)
    try:
        sc.use_nodes = True
        ct = sc.node_tree
        rl = ct.nodes.get("Render Layers") or ct.nodes.new("CompositorNodeRLayers")
        comp = ct.nodes.get("Composite") or ct.nodes.new("CompositorNodeComposite")
        gl = ct.nodes.new("CompositorNodeGlare")
        gl.glare_type = "FOG_GLOW"
        if hasattr(gl, "quality"):
            gl.quality = "HIGH"
        if hasattr(gl, "threshold"):
            gl.threshold = 0.8
        ct.links.new(rl.outputs["Image"], gl.inputs["Image"])
        ct.links.new(gl.outputs["Image"], comp.inputs["Image"])
    except Exception as e:  # compositor API differs across versions; the shot still works without bloom
        print(f"(no glare: {e})")


def render(out: Path, w: int, h: int, first: int, last: int, geometry_only: bool) -> None:
    sc = bpy.context.scene
    setup_render(w, h)
    sc.frame_start, sc.frame_end = first, last
    out.mkdir(parents=True, exist_ok=True)
    if geometry_only:
        for f in range(first, last + 1):
            sc.frame_set(f)
    else:
        sc.render.filepath = str(out / "asc_")
        bpy.ops.render.render(animation=True)
    geo = {"script": "ascent3d_v23.py", "width": w, "height": h, "frames": {str(f): GEOM[f] for f in sorted(GEOM)
                                                                          if first <= f <= last}}
    name = "geometry.json" if (first, last) == (1, FRAMES) else f"geometry_{first:04d}_{last:04d}.json"
    (out / name).write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
    print(f"GEOMETRY {len(geo['frames'])} frames -> {out / name}")


if __name__ == "__main__":
    ex = sys.argv[sys.argv.index("--") + 1:]
    geometry_only = "--geometry-only" in ex
    ex = [a for a in ex if a != "--geometry-only"]
    o = Path(ex[0]).resolve()
    W = int(ex[1]) if len(ex) > 1 else 1920
    H = int(ex[2]) if len(ex) > 2 else 1080
    a = int(ex[3]) if len(ex) > 3 else 1
    b = int(ex[4]) if len(ex) > 4 else FRAMES
    build()
    render(o, W, H, a, b, geometry_only)
    print(f"{'GEOMETRY ONLY' if geometry_only else 'RENDERED'} frames {a}-{b} -> {o}")
