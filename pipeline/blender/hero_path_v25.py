"""v25 hero beat (frames 715-798): the camera path, the bodies and the schematic route, in pure Python (no bpy).

Shared by blender/hero_v25.py (which renders the scene with exactly these cameras) and by the planner / the overlay
geometry, so the 2D route the overlay draws is the projection of the same 3D curve the Blender camera looks at.

Scene units: the Moon is a unit sphere at the origin (blender/moon_portrait.py's Moon, same rotation, same sun);
the Earth is 3.67 Moon radii (true ratio) but only ~18 Moon radii away (true: ~221): a SCHEMATIC, NOT TO SCALE.
The last camera is moon_portrait.py's camera (0.25, -8.5, 0.1) looking at the origin, with moon_beat_frames.py's
frame-799 crop folded in (zoom 1.12 -> lens 56 mm; centre 0.455 of the width -> shift_x -0.0504), so frame 798 lands
on the protected portrait's framing.
"""
from __future__ import annotations

import math

N = 84                       # output frames 715..798
F0 = 715
W, H = 1920, 1080
LENS = 50.0 * 1.12           # moon_beat_frames.py: 4K still cropped at zoom 1.12 for frame 799
SENSOR = 36.0
SHIFT_X = (0.455 - 0.5) * 1.12   # -0.0504 (Blender shift is in units of the frame width)
FPX = LENS / SENSOR * W      # focal length in px

MOON = (0.0, 0.0, 0.0)
RM = 1.0
EARTH = (14.0, 22.0, -0.6)
RE = 3.67
CAM_END = (0.25, -8.5, 0.1)  # moon_portrait.py
SUN_ROT = (80.0, 0.0, 58.0)  # moon_portrait.py sun rotation_euler (deg)

Vec = tuple[float, float, float]


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, k: float) -> Vec:
    return (a[0] * k, a[1] * k, a[2] * k)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a: Vec) -> Vec:
    n = math.sqrt(dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def lerp(a: Vec, b: Vec, u: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


def bezier(pts: list[Vec], u: float) -> Vec:
    p = list(pts)
    while len(p) > 1:
        p = [lerp(a, b, u) for a, b in zip(p, p[1:])]
    return p[0]


def smooth(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# --------------------------------------------------------------------------- timing
# Speed profile of the journey (per output frame k = 0..83): a slow drift while the speed card counts (715-738),
# a lift on the Dvorak hit at frame 744 (k 29), the fastest stretch through ~760, then a long deceleration into
# rest at k 83 (frame 798): no velocity left at the cut to the locked-off portrait.
HIT = 29
ARRIVE = 55


def speed(k: float) -> float:
    if k < HIT:
        return 0.16 + 0.06 * smooth(k / HIT)
    if k < HIT + 4:                       # the beat: the move picks up over 4 frames from the hit
        return 0.22 + 0.78 * smooth((k - HIT) / 4)
    if k < 50:
        return 1.0
    return max(0.0, 1.0 - smooth((k - 50) / 33.0)) ** 1.15


def _progress_table() -> list[float]:
    acc, out = 0.0, []
    for k in range(N):
        out.append(acc)
        acc += 0.5 * (speed(k) + speed(k + 1))
    total = out[-1]
    return [x / total for x in out]


PROG = _progress_table()

# --------------------------------------------------------------------------- camera
CAM_CTRL: list[Vec] = [(12.6, -5.0, 0.3), (11.0, -12.0, 0.6), (5.0, -27.0, 1.6), (1.5, -18.0, 0.6),
                       (0.3, -10.5, 0.12), CAM_END]
TGT_EARTH: Vec = (EARTH[0] - 2.3, EARTH[1], EARTH[2] - 0.3)   # Earth sits right of centre, a little high


def camera(k: float) -> tuple[Vec, Vec]:
    """(position, look-at target) at output frame k (0..83; fractional k for motion-blur sub-frames)."""
    k0 = min(max(int(math.floor(k)), 0), N - 1)
    k1 = min(k0 + 1, N - 1)
    fr = min(max(k - k0, 0.0), 1.0) if k1 > k0 else 0.0
    s = PROG[k0] + (PROG[k1] - PROG[k0]) * fr
    pos = bezier(CAM_CTRL, s)
    w = smooth((s - 0.12) / 0.80)
    mid = (6.0, 9.0, -1.6)
    tgt = bezier([TGT_EARTH, mid, mid, MOON], w)
    if k >= N - 1:
        pos, tgt = CAM_END, MOON
    return pos, tgt


def basis(pos: Vec, tgt: Vec) -> tuple[Vec, Vec, Vec]:
    """(right, up, forward) of a look-at camera with world +Z up (Blender TRACK_TO -Z / UP_Y)."""
    fw = norm(sub(tgt, pos))
    rt = norm(cross(fw, (0.0, 0.0, 1.0)))
    up = cross(rt, fw)
    return rt, up, fw


def project(p: Vec, pos: Vec, tgt: Vec) -> tuple[float, float, float]:
    """Pixel (x right, y down) and depth of world point p."""
    rt, up, fw = basis(pos, tgt)
    v = sub(p, pos)
    z = dot(v, fw)
    if z <= 1e-6:
        return float("nan"), float("nan"), z
    return W / 2 + FPX * dot(v, rt) / z - SHIFT_X * W, H / 2 - FPX * dot(v, up) / z, z


def sphere_px(c: Vec, r: float, pos: Vec, tgt: Vec) -> tuple[float, float, float]:
    x, y, z = project(c, pos, tgt)
    d = math.sqrt(dot(sub(c, pos), sub(c, pos)))
    return x, y, FPX * r / math.sqrt(max(d * d - r * r, 1e-9)) * (d / z if z > 0 else 1)


# --------------------------------------------------------------------------- the schematic route
def _route_ctrl() -> list[Vec]:
    to_moon = norm(sub(MOON, EARTH))
    side = norm(cross(to_moon, (0.0, 0.0, 1.0)))           # points toward -Y (the camera side)
    # departure on the lit disc near the terminator (preview 3: a start on the night limb floated in empty space)
    a = add(EARTH, mul(norm((-0.45, -0.75, 0.48)), RE * 1.01))
    b = add(MOON, mul(norm((1.0, -0.30, 0.42)), RM * 1.10))
    ab = sub(b, a)
    return [a, add(add(a, mul(ab, 0.30)), (0.0, -1.0, 0.9)), add(add(a, mul(ab, 0.72)), (0.0, -0.6, 0.9)), b]


ROUTE = _route_ctrl()
ROUTE_STEPS = 160


def route_point(u: float) -> Vec:
    return bezier(ROUTE, u)


def reveal(k: int) -> float:
    """Route parameter drawn by output frame k: launches on the hit (k 29), lands on the Moon at k 55 (frame 770)
    while both bodies are still in frame; ease-in-out so the head leaves the departure point with the move."""
    if k < HIT:
        return 0.0
    x = (k - HIT) / (ARRIVE - HIT)
    return 1.0 if x >= 1 else 0.5 * (x + x * x * (3 - 2 * x))


def occluded(p: Vec, pos: Vec) -> bool:
    """True if a body hides p from the camera (segment pos -> p hits the Earth or the Moon first)."""
    d = sub(p, pos)
    L = math.sqrt(dot(d, d))
    dn = mul(d, 1 / L)
    for c, r in ((EARTH, RE * 1.01), (MOON, RM * 1.01)):
        oc = sub(pos, c)
        b = dot(oc, dn)
        q = dot(oc, oc) - r * r
        disc = b * b - q
        if disc > 0:
            t = -b - math.sqrt(disc)
            if 1e-4 < t < L - 1e-3:
                return True
    return False


def sun_dir() -> Vec:
    """Unit vector toward the sun (moon_portrait.py's sun: rotation_euler (80, 0, 58) deg, light along local -Z)."""
    ax, _, az = (math.radians(v) for v in SUN_ROT)
    lx = (0.0, math.sin(ax), -math.cos(ax))           # Rx * (0, 0, -1)
    ld = (lx[0] * math.cos(az) - lx[1] * math.sin(az), lx[0] * math.sin(az) + lx[1] * math.cos(az), lx[2])
    return mul(ld, -1.0)


def frame_geometry(k: int) -> dict:
    pos, tgt = camera(k)
    ex, ey, er = sphere_px(EARTH, RE, pos, tgt)
    mx, my, mr = sphere_px(MOON, RM, pos, tgt)
    u_end = reveal(k)
    pts = []
    for i in range(ROUTE_STEPS + 1):
        u = i / ROUTE_STEPS
        if u > u_end + 1e-9:
            break
        p = route_point(u)
        x, y, z = project(p, pos, tgt)
        pts.append([round(x, 2), round(y, 2), round(z, 3), 0 if occluded(p, pos) else 1])
    if 0 < u_end < 1 and pts:
        x, y, z = project(route_point(u_end), pos, tgt)
        pts.append([round(x, 2), round(y, 2), round(z, 3), 0 if occluded(route_point(u_end), pos) else 1])
    return {"k": k, "frame": F0 + k, "cam": [list(pos), list(tgt)], "earth": [ex, ey, er], "moon": [mx, my, mr],
            "reveal": u_end, "route": pts}
