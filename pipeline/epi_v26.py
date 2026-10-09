"""v26: the epilogue stills from the original high-resolution film scans (stills_hq/), real pixels only.

Three shots (frames 1702-1890; the cut points, captions and the end title are unchanged):
    as11-40-5903  1702-1743  a camera push into Aldrin's visor reflection (replaces the px_aldrin Blender parallax,
                              which enlarged a 5189 px library JPEG ~4x past its pixels)
    as11-40-5878  1744-1840  a restrained push across the bootprint (replaces the library JPEG, 3896 px)
    as11-44-6642  1841-1890  the end-title plate, more detail and a small push anchored on the horizon, so the title,
                              date line and AI-assist note (drawn later by the comp) sit on the same composition

Two parts:
  make   (py epi_v26.py make [ID ...]) grades each scan ONCE and caches a working crop in work/stills_v26/, plus
         manifest.json: the source sha1/bytes/pixels, the registration against the graded library still, the crop
         rectangle, the grade (per-channel quantile curve fitted to the library still, a soft highlight shoulder,
         deterministic dither), the output sha256, and, per shot, the move, the per-frame source rectangles, the
         sampling ratios and the sha256 of every rendered frame. One large scan at a time (each is decoded, cropped
         and released before the next).
  build  render_still_v26(shot, path) (build.py's shots stage) renders the frames from the cached crop with PIL:
         float32 per channel, LANCZOS with a float source box (sub-pixel exact, no snapping, no shimmer), the
         render_still ease (0.85 smoothstep + 0.15 linear) on a log-zoom homothety; every frame must reproduce its
         manifest sha256, sit inside the working crop, and sample >= 1.0 source px per output px, or the build stops.
         check(shots) is the preflight: files, sizes, sha256, this module's own sha256 and the shot table vs the
         manifest, before any output is opened. No Blender, no network, no scipy at build time.

Shot.kb for these shots is in ORIGINAL-SCAN coordinates: (cx, cy) in 0..1 of the full scan, zoom = scan width / crop
width. The move is a homothety (a camera push toward one fixed point) with the zoom geometric in the eased parameter.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None          # the 10.5k scans are 110-134 Mpx (PIL's bomb guard stops at 89 Mpx)

ROOT = CRAFTWORK
INBOX = ROOT / "inbox" / "moonshot"
WORK = INBOX / "work"
HQ = INBOX / "stills_hq"
LIB = INBOX / "stills"
DIR = "stills_v26"
W, H, FPS = 1920, 1080, 24
MIN_RATIO = 1.0                         # source px per output px, every frame (Codex all-out plan, v26 acceptance)

# Working crops in full-scan px (x0, y0, x1, y1): the union of every frame's source box plus a margin, clear of the
# film edges (5903 / 5878 are edge-free scans; 6642's border ends at x 52 / starts at x ~4217, bottom ~4170).
# scale: the crop is stored at 1/scale (a 2x2 box average for the bootprint, which samples >= 3 scan px per output px).
SCANS: dict[str, dict] = {
    "5903": {"src": "as11-40-5903_commons.jpg", "lib": "as11-40-5903.jpg", "rect": (3150, 2150, 7450, 4700),
             "scale": 1, "out": "as11-40-5903_v26.png"},
    "5878": {"src": "as11-40-5878_commons.jpg", "lib": "as11-40-5878.jpg", "rect": (1900, 3700, 10538, 9000),
             "scale": 2, "out": "as11-40-5878_v26.png"},
    "6642": {"src": "as11-44-6642_commons.jpg", "lib": "as11-44-6642.jpg", "rect": (64, 1200, 4210, 3800),
             "scale": 1, "out": "as11-44-6642_v26.png"},
}
SHOULDER = (232.0, 20.0)                # graded values above 232 roll off toward 252 (232 + 20): no new clipping
DITHER_SEED = 2600                      # +-0.5 LSB triangular dither before the 8-bit store (the curve stretches)
GRAIN = {"5903": 0.0, "5878": 0.0, "6642": 0.0}    # extra film grain sigma (levels), set from the noise measurement
# The shots as build.py's SHOTS carries them (V26_SCANS = True): (t0, t1) real seconds, kb in full-scan coordinates.
# check() refuses a SHOTS table that drifts from these (and from the manifest), so the two cannot disagree silently.
SHOT_T = {"5903": (70.90, 72.675), "5878": (72.675, 76.70), "6642": (76.70, 78.80)}
KB = {
    "5903": ((0.50152, 0.27274, 2.48306), (0.51549, 0.23372, 5.3623)),
    "5878": ((0.59860, 0.62288, 1.2578), (0.64718, 0.65205, 1.64656)),
    "6642": ((0.50094, 0.57855, 1.03762), (0.50094, 0.57331, 1.08431)),
}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def sha1_file(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest()


def scan_id(img: str) -> str:
    """'stills_v26/as11-40-5903_v26.png' -> '5903'."""
    for k, v in SCANS.items():
        if img == f"{DIR}/{v['out']}":
            return k
    raise SystemExit(f"v26: {img} is not a stills_v26 working crop")


# ------------------------------------------------------------------------------------------------ the move
def ease(x: float) -> float:
    """render_still's curve: 0.85 smoothstep + 0.15 linear."""
    x = min(max(x, 0.0), 1.0)
    return 0.85 * x * x * (3 - 2 * x) + 0.15 * x


def boxes(kb: tuple, scan_wh: tuple[int, int], n: int) -> list[tuple[float, float, float, float]]:
    """Source boxes (full-scan px) for n frames: zoom geometric in the eased parameter, centre on the homothety
    through the start and end boxes (a push toward one fixed point; a pure pan if the zoom does not change)."""
    sw, sh = scan_wh
    (cx0, cy0, z0), (cx1, cy1, z1) = kb
    w0, w1 = sw / z0, sw / z1
    c0, c1 = np.array([cx0 * sw, cy0 * sh]), np.array([cx1 * sw, cy1 * sh])
    out = []
    for i in range(n):
        u = ease(i / max(n - 1, 1))
        w = w0 * (w1 / w0) ** u
        if abs(w1 - w0) < 1e-6:
            c = c0 + (c1 - c0) * u
        else:
            k_end = w1 / w0
            f = (c1 - k_end * c0) / (1 - k_end)
            c = f + (c0 - f) * (w / w0)
        h = w * H / W
        out.append((float(c[0] - w / 2), float(c[1] - h / 2), float(c[0] + w / 2), float(c[1] + h / 2)))
    return out


# ------------------------------------------------------------------------------------------------ render
class Plate:
    """The cached working crop as three float32 PIL images (resampled per channel: no 8-bit rounding mid-chain)."""

    def __init__(self, key: str) -> None:
        sp = SCANS[key]
        a = np.asarray(Image.open(WORK / DIR / sp["out"]).convert("RGB"))
        self.key = key
        self.rect = sp["rect"]
        self.scale = sp["scale"]
        self.size = (a.shape[1], a.shape[0])
        self.ch = [Image.fromarray(np.ascontiguousarray(a[..., c]).astype(np.float32), "F") for c in range(3)]

    def frame(self, box: tuple[float, float, float, float], fi: int) -> tuple[np.ndarray, float]:
        """One output frame (uint8 HxWx3) from a full-scan box; returns it and the sampling ratio (working px per
        output px). Raises if the box leaves the working crop or undersamples."""
        x0, y0, sc = self.rect[0], self.rect[1], self.scale
        b = ((box[0] - x0) / sc, (box[1] - y0) / sc, (box[2] - x0) / sc, (box[3] - y0) / sc)
        if b[0] < 0 or b[1] < 0 or b[2] > self.size[0] or b[3] > self.size[1]:
            raise SystemExit(f"v26 {self.key}: frame {fi} box {box} leaves the working crop {self.rect}")
        ratio = (b[2] - b[0]) / W
        if ratio < MIN_RATIO:
            raise SystemExit(f"v26 {self.key}: frame {fi} samples {ratio:.3f} px per output px (< {MIN_RATIO})")
        f = np.stack([np.asarray(c.resize((W, H), Image.Resampling.LANCZOS, box=b), np.float32) for c in self.ch], -1)
        g = GRAIN[self.key]
        if g > 0:
            rng = np.random.default_rng(26000 + fi)
            n_ = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
            n_ = np.asarray(Image.fromarray(n_).resize((W, H), Image.Resampling.BILINEAR), np.float32)
            lum = f.mean(axis=2) / 255.0
            f = f + (n_ * g * (0.35 + 2.6 * lum * (1 - lum)))[..., None]
        return np.clip(f + 0.5, 0, 255).astype(np.uint8), ratio


def frames(key: str, kb: tuple, n: int, t0_frame: int):
    """Yield (frame index, uint8 frame, full-scan box, working ratio) for a shot."""
    man = manifest()
    sw, sh = man["scans"][key]["source_px"]
    p = Plate(key)
    for i, box in enumerate(boxes(kb, (sw, sh), n)):
        fr, ratio = p.frame(box, t0_frame + i)
        yield t0_frame + i, fr, box, ratio


def manifest() -> dict:
    return json.loads((WORK / DIR / "manifest.json").read_text(encoding="utf-8"))


def render_still_v26(s, path: Path) -> None:
    """build.py shots stage: render the shot from its working crop, verify every frame against the manifest, encode
    like the px_ sequences (libx264 crf 12)."""
    key = scan_id(s.img)
    n = int(round(s.t1 * FPS)) - int(round(s.t0 * FPS))
    f0 = int(round(s.t0 * FPS))
    want = manifest()["shots"][key]
    if want["frames"] != n or want["first_frame"] != f0 or [list(k) for k in s.kb] != want["kb"]:
        raise SystemExit(f"v26 {key}: SHOTS (frames {n} from {f0}, kb {s.kb}) differ from the manifest "
                         f"(frames {want['frames']} from {want['first_frame']}, kb {want['kb']}); re-run "
                         f"py epi_v26.py make {key}")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "veryfast",
                            "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    try:
        for k, (fi, fr, _box, _ratio) in enumerate(frames(key, s.kb, n, f0)):
            b = fr.tobytes()
            if sha256_bytes(b) != want["frame_sha256"][k]:
                raise SystemExit(f"v26 {key}: frame {fi} does not reproduce its manifest sha256")
            enc.stdin.write(b)
    finally:
        enc.stdin.close()
        enc.wait()
    if enc.returncode != 0:
        raise SystemExit(f"v26 {key}: ffmpeg exit {enc.returncode}")


def check(shots: list) -> int:
    """Preflight (before any output is opened): the manifest, every working crop's size + sha256, the sources'
    byte sizes, this module's sha256, and each v26 shot's frame count / first frame / kb against the manifest."""
    mp = WORK / DIR / "manifest.json"
    if not mp.is_file():
        raise SystemExit(f"v26: {mp} missing (py epi_v26.py make)")
    man = manifest()
    me = sha256_file(Path(__file__))
    if man["tool_sha256"] != me:
        raise SystemExit(f"v26: epi_v26.py changed since the manifest was written ({me[:12]} vs "
                         f"{man['tool_sha256'][:12]}); re-run py epi_v26.py make")
    for key, sp in SCANS.items():
        e = man["scans"][key]
        p = WORK / DIR / sp["out"]
        if not p.is_file() or sha256_file(p) != e["out_sha256"]:
            raise SystemExit(f"v26: {p.name} missing or not its manifest sha256")
        src = HQ / sp["src"]
        if not src.is_file() or src.stat().st_size != e["source_bytes"]:
            raise SystemExit(f"v26: source {src.name} missing or not {e['source_bytes']} bytes")
    seen = 0
    for s in shots:
        if s.src == "STILL" and s.img and s.img.startswith(DIR + "/"):
            key = scan_id(s.img)
            w = man["shots"][key]
            n = int(round(s.t1 * FPS)) - int(round(s.t0 * FPS))
            if w["frames"] != n or w["first_frame"] != int(round(s.t0 * FPS)) or [list(k) for k in s.kb] != w["kb"]:
                raise SystemExit(f"v26 {key}: SHOTS differ from the manifest; re-run py epi_v26.py make {key}")
            if (s.t0, s.t1) != SHOT_T[key] or tuple(map(tuple, s.kb)) != KB[key]:
                raise SystemExit(f"v26 {key}: SHOTS ({s.t0}, {s.t1}, {s.kb}) differ from epi_v26.SHOT_T / KB")
            if min(w["ratio_work"]) < MIN_RATIO:
                raise SystemExit(f"v26 {key}: manifest records a frame under {MIN_RATIO} px per output px")
            seen += 1
    return seen


# ------------------------------------------------------------------------------------------------ make (once)
def register(key: str) -> dict:
    """Scale + offset of the graded library still inside the scan (NCC of a central template, 1/8 draft scale)."""
    from scipy.signal import fftconvolve     # make-time only
    sp = SCANS[key]
    scan = Image.open(HQ / sp["src"])
    fw = scan.size[0]
    scan.draft("RGB", (scan.size[0] // 8, scan.size[1] // 8))
    S = np.asarray(scan.convert("L"), np.float32)
    ds = fw / S.shape[1]
    old = Image.open(LIB / sp["lib"]).convert("RGB")
    ow, oh = old.size

    def ncc(img: np.ndarray, tpl: np.ndarray) -> tuple[float, int, int]:
        t = tpl - tpl.mean()
        t /= np.sqrt((t * t).sum()) + 1e-6
        num = fftconvolve(img, t[::-1, ::-1], mode="valid")
        ones = np.ones_like(tpl)
        s1 = fftconvolve(img, ones, mode="valid")
        s2 = fftconvolve(img * img, ones, mode="valid")
        r = num / np.sqrt(np.maximum(s2 - s1 * s1 / tpl.size, 1e-6))
        k = int(np.argmax(r))
        y, x = divmod(k, r.shape[1])
        return float(r[y, x]), x, y

    lo, hi = 0.5 * S.shape[1] / ow, 1.6 * S.shape[1] / ow
    best = None
    for _ in range(3):
        res = []
        for sc in np.linspace(lo, hi, 15):
            tw, th = int(ow * sc), int(oh * sc)
            o = np.asarray(old.convert("L").resize((tw, th), Image.Resampling.BOX), np.float32)
            mx, my = int(tw * 0.2), int(th * 0.2)
            tpl = o[my:th - my, mx:tw - mx]
            if tpl.shape[0] >= S.shape[0] or tpl.shape[1] >= S.shape[1] or tpl.size < 1600:
                continue
            r, x, y = ncc(S, tpl)
            res.append((r, float(sc), x - mx, y - my))
        res.sort(reverse=True)
        best = res[0]
        step = (hi - lo) / 14
        lo, hi = best[1] - step, best[1] + step
    r, sc, x, y = best
    return {"ncc": round(r, 4), "lib_px": [ow, oh], "scale_lib_to_scan": round(sc * ds, 5),
            "lib_origin_in_scan": [round(x * ds, 1), round(y * ds, 1)], "draft_scale": round(ds, 4)}


def fit_grade(key: str, reg: dict) -> dict:
    """Per-channel tone curve scan -> library still: matched quantiles over their overlap at the 1/8 draft scale
    (neutralises the film base, sets black and white points, keeps the approved look of the cut)."""
    sp = SCANS[key]
    scan = Image.open(HQ / sp["src"])
    fw, fh = scan.size
    scan.draft("RGB", (fw // 8, fh // 8))
    scan = scan.convert("RGB")
    ds = fw / scan.size[0]
    old = Image.open(LIB / sp["lib"]).convert("RGB")
    sc = reg["scale_lib_to_scan"] / ds
    ox, oy = reg["lib_origin_in_scan"][0] / ds, reg["lib_origin_in_scan"][1] / ds
    olds = old.resize((round(old.size[0] * sc), round(old.size[1] * sc)), Image.Resampling.BOX)
    # overlap, in draft px of the scan, with a 3% inset against registration error at the edges
    x0 = max(0, math.ceil(ox)), max(0, math.ceil(oy))
    x1 = min(scan.size[0], math.floor(ox + olds.size[0])), min(scan.size[1], math.floor(oy + olds.size[1]))
    ins = int(0.03 * min(x1[0] - x0[0], x1[1] - x0[1]))
    a = np.asarray(scan, np.float32)[x0[1] + ins:x1[1] - ins, x0[0] + ins:x1[0] - ins]
    b = np.asarray(olds, np.float32)[x0[1] - round(oy) + ins:x1[1] - round(oy) - ins,
                                     x0[0] - round(ox) + ins:x1[0] - round(ox) - ins]
    hh, ww = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    a, b = a[:hh, :ww], b[:hh, :ww]
    qs = np.array([0.05, 0.2, 0.5, 1, 2, 3, 5, 8, 12, 17, 23, 30, 38, 46, 54, 62, 70, 77, 83, 88, 92, 95, 97, 98.5,
                   99.3, 99.7, 99.9, 99.97])
    knots = {}
    for c, nm in enumerate("rgb"):
        xs = np.percentile(a[..., c], qs)
        ys = np.percentile(b[..., c], qs)
        xs_k, ys_k = [0.0], [max(0.0, float(ys[0] - (xs[0]) * (ys[1] - ys[0]) / max(xs[1] - xs[0], 1e-3)))]
        for xv, yv in zip(xs, ys):
            if xv > xs_k[-1] + 0.75:
                xs_k.append(float(xv))
                ys_k.append(float(max(yv, ys_k[-1])))
        slope = (ys_k[-1] - ys_k[-2]) / max(xs_k[-1] - xs_k[-2], 1e-3)
        xs_k.append(255.0)
        ys_k.append(float(ys_k[-1] + slope * (255.0 - xs_k[-2])))
        ys_k[0] = min(max(ys_k[0], 0.0), ys_k[1])
        knots[nm] = [[round(v, 3) for v in xs_k], [round(v, 3) for v in ys_k]]
    return {"method": "per-channel matched quantiles vs the graded library still over their overlap (1/8 draft)",
            "quantiles_pct": qs.tolist(), "knots": knots, "shoulder": list(SHOULDER), "dither_seed": DITHER_SEED,
            "overlap_draft_px": [int(ww), int(hh)]}


def apply_grade(x: np.ndarray, kn: list) -> np.ndarray:
    y = np.interp(x, kn[0], kn[1]).astype(np.float32)
    s0, s1 = SHOULDER
    hi = y > s0
    y[hi] = s0 + s1 * (1 - np.exp(-(y[hi] - s0) / s1))
    return np.clip(y, 0, 255)


def make_scan(key: str) -> dict:
    sp = SCANS[key]
    src = HQ / sp["src"]
    reg = register(key)
    grade = fit_grade(key, reg)
    print(f"  {key}: registration {reg}", flush=True)
    im = Image.open(src)
    sw, sh = im.size
    x0, y0, x1, y1 = sp["rect"]
    if not (0 <= x0 < x1 <= sw and 0 <= y0 < y1 <= sh):
        raise SystemExit(f"{key}: crop {sp['rect']} outside the {sw}x{sh} scan")
    crop = im.crop(sp["rect"])          # decodes the full scan once
    crop.load()
    im.close()
    del im
    a = np.asarray(crop.convert("RGB"))
    del crop
    rng = np.random.default_rng(DITHER_SEED + int(key))
    chans = []
    for c, nm in enumerate("rgb"):
        x = a[..., c].astype(np.float32)
        if sp["scale"] == 2:
            hh, ww = (x.shape[0] // 2) * 2, (x.shape[1] // 2) * 2
            x = x[:hh, :ww].reshape(hh // 2, 2, ww // 2, 2).mean(axis=(1, 3))
        y = apply_grade(x, grade["knots"][nm])
        d = rng.random(y.shape, dtype=np.float32) - rng.random(y.shape, dtype=np.float32)
        chans.append(np.clip(np.floor(y + 0.5 + 0.5 * d), 0, 255).astype(np.uint8))
        del x, y, d
    del a
    out = np.stack(chans, -1)
    del chans
    (WORK / DIR).mkdir(exist_ok=True)
    op = WORK / DIR / sp["out"]
    Image.fromarray(out).save(op, compress_level=6)
    clip = int((out >= 254).all(axis=2).sum())
    return {"source": f"stills_hq/{sp['src']}", "source_bytes": src.stat().st_size, "source_sha1": sha1_file(src),
            "source_px": [sw, sh], "library_still": f"stills/{sp['lib']}",
            "library_sha1": sha1_file(LIB / sp["lib"]), "registration": reg, "crop_rect_scan_px": list(sp["rect"]),
            "store_scale": sp["scale"], "grade": grade, "out": sp["out"], "out_px": [out.shape[1], out.shape[0]],
            "out_sha256": sha256_file(op), "out_px_clipped_254": clip}


def make_shot(key: str, shot) -> dict:
    n = int(round(shot.t1 * FPS)) - int(round(shot.t0 * FPS))
    f0 = int(round(shot.t0 * FPS))
    hashes, ratios, rs, bx = [], [], [], []
    sc = SCANS[key]["scale"]
    for fi, fr, box, ratio in frames(key, shot.kb, n, f0):
        hashes.append(sha256_bytes(fr.tobytes()))
        ratios.append(round(ratio, 4))
        rs.append(round(ratio * sc, 4))
        bx.append([round(v, 2) for v in box])
    return {"t0": shot.t0, "t1": shot.t1, "first_frame": f0, "frames": n, "kb": [list(k) for k in shot.kb],
            "grain_sigma": GRAIN[key], "ease": "0.85 smoothstep + 0.15 linear, zoom geometric, homothety",
            "resample": "PIL LANCZOS, float32 per channel, float source box", "ratio_work": ratios,
            "ratio_scan": rs, "box_scan_px": bx, "frame_sha256": hashes}


def main() -> None:
    sys.path.insert(0, str(WORK))
    if len(sys.argv) < 2 or sys.argv[1] not in ("make", "check"):
        raise SystemExit("py epi_v26.py make [5903 5878 6642] | check")
    from types import SimpleNamespace
    shots = {k: SimpleNamespace(t0=SHOT_T[k][0], t1=SHOT_T[k][1], kb=KB[k], src="STILL", img=f"{DIR}/{v['out']}")
             for k, v in SCANS.items()}
    if sys.argv[1] == "check":
        print(f"v26 check: {check(list(shots.values()))} shots verified")
        return
    keys = sys.argv[2:] or list(SCANS)
    mp = WORK / DIR / "manifest.json"
    man = json.loads(mp.read_text(encoding="utf-8")) if mp.is_file() else {"scans": {}, "shots": {}}
    for k in keys:
        print(f"grading {k} (one scan at a time) ...", flush=True)
        man["scans"][k] = make_scan(k)
        mp.parent.mkdir(exist_ok=True)
        mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    for k in keys:
        if k in shots:
            man["shots"][k] = make_shot(k, shots[k])
            mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
            r = man["shots"][k]["ratio_work"]
            print(f"  shot {k}: {len(r)} frames, ratio min {min(r):.3f} max {max(r):.3f}", flush=True)
    man["tool"] = "epi_v26.py"
    man["tool_sha256"] = sha256_file(Path(__file__))
    man["frame_size"] = [W, H]
    man["fps"] = FPS
    man["pil"] = Image.__version__
    man["numpy"] = np.__version__
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")
    print("manifest written:", mp)


if __name__ == "__main__":
    main()
