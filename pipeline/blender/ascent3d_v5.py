"""v18 (ascent3d_v5.py, renders ascent_blender_v5): the event labels (MAX Q, INBOARD ENGINE CUTOFF) and their rings
no longer slide off the bottom of the frame or into the HUD column: each label is right-aligned so it ends over its ring
(the HUD values start at x ~0.68 of the frame), fades in over 3 mission-seconds, and fades out (label + ring) as its
ring's projected position drops from 18% to 12% of the frame height above the bottom edge (title safe is 5%), so nothing
is drawn below y ~950 px. Projection is computed from the camera pose set in the same frame handler. Otherwise
identical to ascent3d.py (v4 frames).

MOONSHOT 3D ascent beat (Blender EEVEE): Apollo 11's first three minutes as a glowing trajectory tube
rising off a NASA Blue Marble Earth from Cape Canaveral, the camera chasing the tube head, with real
Anton readouts counting up from the values the NASA PAO called out live.

    blender.exe -b --factory-startup --python ascent3d.py -- <out_dir> [w h first last]

192 frames @ 24 fps = timeline 26.0-34.0 s. Mission time runs T+0 -> T+180 s (eased), then holds.
Altitude and downrange are both exaggerated 6x so the climb reads on screen (labelled on screen).
Data (nautical miles, ft/s) = PAO call-outs re-timed per the AS-506 flight evaluation report:
  T+56 2 nmi; T+66 4 nmi, 2,195 ft/s (Mach 1); T+106 12 nmi, 4,000 ft/s; T+148 30 nmi; T+180 43 nmi,
  9,300 ft/s, 70 nmi downrange.  Max Q T+83.0, center (inboard) engine cutoff T+135.2.
"""
from __future__ import annotations

import math
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import bpy
from mathutils import Matrix, Vector

FONT = (CRAFTWORK / "fonts/Anton-Regular.ttf")
BEBAS = (CRAFTWORK / "fonts/BebasNeue-Regular.ttf")
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
FADE_LOG: dict[int, tuple] = {}


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


def text_obj(body, font, size, color, strength=1.0, align="LEFT", fade=False):
    bpy.ops.object.text_add()
    t = bpy.context.object
    t.data.body = body
    t.data.font = bpy.data.fonts.load(str(font), check_existing=True)
    t.data.size = size
    t.data.align_x = align
    t.data.materials.append(fading_emission("txt", color, strength) if fade else emission("txt", color, strength))
    return t


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
    bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=R * 1.012)
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
    cu.bevel_depth = 0.012
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

    # event markers: ring + 3D label facing the camera
    cam = bpy.data.cameras.new("Cam")
    cam.lens = 30
    cam.clip_start = 0.005
    co = bpy.data.objects.new("Cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    markers = []
    for et, name in EVENTS:
        p = pos(et)
        bpy.ops.mesh.primitive_torus_add(major_radius=0.06, minor_radius=0.004, location=p)
        ring = bpy.context.object
        ring.rotation_euler = (pos(et + 1) - pos(et - 1)).to_track_quat("Z", "Y").to_euler()
        ring.data.materials.append(fading_emission("Ring", (0.55, 0.86, 1.0), 2.0))
        ring.hide_render = True
        ring.visible_shadow = False
        lab = text_obj(name, BEBAS, 0.075, (0.55, 0.86, 1.0), 2.0, align="RIGHT", fade=True)   # v18: was CENTER
        lab.location = p + (p.normalized() * 0.07)
        lab.hide_render = True
        lab.visible_shadow = False
        c = lab.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = co, "TRACK_Z", "UP_Y"
        markers.append((et, ring, lab))

    # HUD readouts: real 3D Anton text parented to the camera (fixed in frame, inside title-safe)
    hud = []
    rows = [("MISSION TIME", 0.13), ("ALTITUDE", -0.04), ("VELOCITY", -0.21)]
    for label, y in rows:
        lt = text_obj(label, BEBAS, 0.034 * 0.3, AMBER, 1.6)
        vt = text_obj("0", FONT, 0.085 * 0.3, (1, 1, 1), 1.6)
        for obj, dy in ((lt, 0.088), (vt, 0.0)):
            obj.parent = co
            obj.location = (0.25 * 0.3, (y + dy) * 0.3, -0.3)
        hud.append(vt)
    note = text_obj("HEIGHT + DISTANCE EXAGGERATED 6x  ·  VALUES CALLED OUT LIVE BY NASA", BEBAS, 0.034 * 0.3,
                    (0.85, 0.85, 0.85), 1.2)
    note.parent = co
    note.location = (-0.535 * 0.3, 0.215 * 0.3, -0.3)
    ttl = text_obj("ASCENT  ·  FIRST 3 MINUTES", BEBAS, 0.04 * 0.3, (1, 1, 1), 1.6)
    ttl.parent = co
    ttl.location = (-0.535 * 0.3, 0.255 * 0.3, -0.3)

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
        hud[0].data.body = f"T+{t:.0f} S"
        hud[1].data.body = f"{interp(ALT, t):.1f} NMI"
        hud[2].data.body = f"{interp(VEL, t) * 0.681818:,.0f} MPH"
        rotq = (look - campos).to_track_quat("-Z", "Y").to_euler()
        lr = cam.lens / cam.sensor_width
        asp = scene.render.resolution_x / scene.render.resolution_y
        for et, ring, lab in markers:
            vis = et - 1.0 <= t
            _, y = ndc(campos, rotq, lr, asp, pos(et))
            k = min(max((t - (et - 1.0)) / 3.0, 0.0), 1.0) * min(max((y - 0.12) / 0.06, 0.0), 1.0)
            k = k * k * (3 - 2 * k)
            vis = vis and k > 0.002
            ring.hide_render = not vis
            lab.hide_render = not vis
            for ob in (ring, lab):
                ob.active_material.node_tree.nodes["Fade"].outputs[0].default_value = k
            FADE_LOG[f] = FADE_LOG.get(f, ()) + ((et, round(y, 3), round(k, 3)),)

    bpy.app.handlers.frame_change_pre.append(update)
    sc.frame_set(1)


def render(out: Path, w: int, h: int, first: int, last: int) -> None:
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
    sc.frame_start, sc.frame_end = first, last
    out.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(out / "asc_")
    bpy.ops.render.render(animation=True)
    for f in sorted(FADE_LOG):
        print(f"FADE f{f} " + " ".join(f"{et:.0f}:y{y:.3f}/k{k:.2f}" for et, y, k in FADE_LOG[f]))


if __name__ == "__main__":
    ex = sys.argv[sys.argv.index("--") + 1:]
    o = Path(ex[0]).resolve()
    W = int(ex[1]) if len(ex) > 1 else 1920
    H = int(ex[2]) if len(ex) > 2 else 1080
    a = int(ex[3]) if len(ex) > 3 else 1
    b = int(ex[4]) if len(ex) > 4 else FRAMES
    build()
    render(o, W, H, a, b)
    print(f"RENDERED frames {a}-{b} -> {o}")
