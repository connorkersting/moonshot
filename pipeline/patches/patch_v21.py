"""v21 CANDIDATE: v20's authentic HUD made legible at PHONE SIZE + the listed v20 defects + the Codex v20 engineering
findings. Apply to the v20 source (build.py + score_pd.py, tag v20-src):

    py patch_v21.py                      # the real build.py + score_pd.py in work/
    py patch_v21.py BUILD.py SCORE.py    # dry run on copies (hud_v20.py and hud_v21.py must sit next to BUILD.py)

Why: the Fable editor scored v20 8.5 (v19 8.0), but the blind A/B judge preferred v19 on the landing section: v20's
MOCR monitor read small at 360p and its reverse-video bingo value looked like a glitch. Evidence:
exports/moonshot/qc/v20/fable_editor.json (top_fixes, new_problems), qc/ab_v20_v19/judge_sonnet.json,
work/codex_review_v20.md.

Drawing lives in the NEW module work/hud_v21.py (its docstring lists every change and the numbers); hud_v20.py is
unchanged and V21_HUD = False draws v20's HUD exactly. build.py keeps every value computation (fuel(), descent(),
get_at, READOUT_HOLDS, the stat curves): the values handed to the HUD are unchanged. Kept exactly: 2,100 frames, the
frame-799 map, DIALOG / CAPTIONS, the cut list, the audio (score_pd.py not changed, checked only), the Moon beat
799-877 (incl. v19's 240,000 card), the 1:02 transition 1486-1524, the credits (timing and text, as v20).

 1  MOCR monitor (tl 55.6-62.9 [real 48.9-56.2]): the bingo seconds and ALT feet 1.5x (160 px OCR-A, cap 35 px at
    360p; v20 107 px / 23); 'SEC' after the value dropped (the heading says it); GET and TIME-COMPRESSED a 30 px
    footer; panel 520 x 736 at x 1300-1820, y 90-826 (v20 to 748; caption box >= 892). A tube at every size: 22 px
    top-lit bezel with a recessed lip (v20 14), rounded inner corners, inner shadow, 12 % edge vignette over face and
    phosphor, soft glass highlight, scanlines every 2nd row (v20 every 3rd). <= 30.0 s: the WHOLE bingo line in
    reverse video plus a steady boxed 'LOW' tag beside the heading (v20: a block round the digits only, read as a
    glitch); same frames as v20 (v19's red), steady, normal again at contact.
 2  CRT redraw ghost: never the old and the new value on one frame (v20 frame 1256 showed '90 FT', the old 4 under
    the new 3). Step frame 0: the old value alone at 0.45 (persistence); frame 1: the new value struck at 0.6; flare
    1.35 / 1.15; 1.0. On every altitude step (the frame-0 value is the old one: the only overlay-value change).
 3  DSKY (tl 47.2-52.375 [40.5-45.67]): 1.2x on the LM window, 1.0x over Mission Control (v20 1.0 / 0.85), moved
    down there to top y 424 (v20 384, on the far-right controller's chin), legend one amber line on its plate ending
    y 850 (42 px above the caption box); unlit segments / sign bars / plates 14/20/16 (v20 24/36/28).
 4  Stat drums (thrust tl 19.0-22.0, TLI tl 29.79-33.3): the thrust 7 lands by frame 463.7 at constant speed (v20:
    an ease-out that showed 2.5 / 4.8 / 5.1 / 6.x MILLION for 18 frames), the .5's extra turn by 464.6; motion blur
    (180-degree shutter) on every moving wheel, thrust and TLI; digits at full legend cream, bezels 3 px on a 6 px
    margin (v20 2 / 4). The TLI count curve and all rest values unchanged.
 5  Grades: swing arm (BRS, 215-225): the magenta cast lives in the purple mid-shadow plate (Lab a +5.8 b -2.0 on the
    plate before the comp LUT), so a hue-selective fix, not a global shadow shift (colorbalance gs pushed the whole
    shadow range yellow-green): selectivecolor magentas -1 M (+0.2 C, +0.1 Y), blues -0.4 M (+0.2 Y) -> plate a +1.7
    b +0.8, rest of the frame unchanged within 0.5. Long-lens rocket (SVW, 444-455): ~+300 K (colortemperature 6200)
    and +10 % saturation (0.95 -> 1.045): mean b* 8.9 -> 11.2 toward its fire-lit neighbours (s14 / s16 ~ +15).
 6  Engineering (Codex v20 review): the 14 RIFE in-betweens of the ignition ramp are a tracked asset,
    work/rife_cache_v21/ (f###.png + 96x54 input thumbnails + manifest.json with the source frame, phase and sha256
    of both inputs and the output). A normal build reads and verifies the cache: no RIFE, GPU or local dev tooling
    needed. MOONSHOT_RIFE_REGEN=1 regenerates: preflight (exe + model files + a 64x64 test interpolation) BEFORE any
    output is opened, a unique temp dir per run (tempfile.mkdtemp) removed in finally. MOONSHOT_RIFE_SEED=<dir> fills
    the cache from an earlier run's f###_0/_1/_rife.png, inputs verified pixel-equal to this decode (the v21 cache is
    seeded from work/rife_v20, the frames v20 shipped). MOONSHOT_RIFE_EXE / _MODEL / _CACHE configure the paths. The
    ramp segment is encoded to s11.part.mp4 and renamed only after a clean encode. repo_src/make_repo.py exports
    hud_v21.py and rewrites the RIFE tool path to a relative default (its text exporter does not copy the PNG cache:
    an exported checkout regenerates it or sets RAMP_RIFE = False).
Not changed (director's calls): the credits timing, the 240,000-miles card, the title bevel, any cut, caption or audio.

Re-render chain (real tree): py patch_v21.py; set MOONSHOT_RIFE_SEED=...\\work\\rife_v20 for ONE run of
py build.py shots 21 9,11,15 (seeds work/rife_cache_v21; later builds need no RIFE); py build.py comp 21;
py build.py mix 21 (audio unchanged; mix re-muxes); py flashqc2.py ..\\..\\..\\exports\\moonshot\\versions\\moonshot_v21.mp4
(must PASS).
"""
import sys
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build/score are CRLF)."""
    EOL[path] = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    return path.read_text(encoding="utf-8")


def save(path: Path, text: str) -> None:
    path.write_text(text.replace("\n", EOL[path]), encoding="utf-8", newline="")


def apply(text: str, pairs: list[tuple[str, str]], what: str) -> str:
    for a, b in pairs:
        n = text.count(a)
        assert n == 1, f"{what}: {n} matches for {a[:90]!r}"
        text = text.replace(a, b)
    return text


s = load(P)
assert "import hud_v20" in s and "RAMP_RIFE = True" in s, "apply patch_v20 first (tag v20-src)"
assert "hud_v21" not in s, "v21 already applied"
for mod in ("hud_v20.py", "hud_v21.py"):
    assert (P.parent / mod).exists(), f"{mod} must sit next to {P.name}"
R = [
    # ---- modules + flag
    ('''import hud_v20      # v20: the 1969-hardware HUD (DSKY, MOCR monitor, drum-counter stat cards) + its film pass
''',
     '''import hud_v20      # v20: the 1969-hardware HUD (DSKY, MOCR monitor, drum-counter stat cards) + its film pass
import hud_v21      # v21: the same HUD legible at 360p (bigger CRT numerals + tube, no redraw ghost, DSKY 1.2x, drums)
'''),
    ('''import json
import math
import os
import subprocess
import sys
''',
     '''import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
'''),
    ('''V20_DISTANCE = False    # v20: the 240,000 card sits in the protected Moon beat (frames 829-877): kept as v19 unless approved
''',
     '''V20_DISTANCE = False    # v20: the 240,000 card sits in the protected Moon beat (frames 829-877): kept as v19 unless approved
V21_HUD = True          # v21: draw with hud_v21 (phone-size legibility, no CRT ghost); False: hud_v20 exactly (v20)
'''),
    ('''        gfx.h20 = hud_v20.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw
        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        if gfx.h20 is not None and gfx.h20.items:      # v20: hardware HUD + film pass, under the captions layer
            f = hud_v20.composite(f, gfx.h20)''',
     '''        hud = hud_v21 if V21_HUD else hud_v20      # v21
        gfx.h20 = hud.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw
        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        if gfx.h20 is not None and gfx.h20.items:      # v20: hardware HUD + film pass, under the captions layer
            f = hud.composite(f, gfx.h20)'''),
    # ---- grades (v20 panel fixes, finished)
    ('''            "eq=contrast=1.10:saturation=0.85,curves=all='0/0 0.12/0.08 0.5/0.5 1/1'"),
''',
     '''            "eq=contrast=1.10:saturation=0.85,curves=all='0/0 0.12/0.08 0.5/0.5 1/1',"
            # v21 (Fable: still magenta): the cast is the purple mid-shadow plate; hue-selective, the rest unchanged
            "selectivecolor=correction_method=absolute:magentas='0.2 -1 0.1 0':blues='0 -0.4 0.2 0'"),
'''),
    ('''            "eq=contrast=1.12:gamma=0.94:saturation=0.95"),
''',
     '''            "eq=contrast=1.12:gamma=0.94:saturation=1.045,colortemperature=temperature=6200"),   # v21: +10 % sat, ~+300 K
'''),
    # ---- RIFE: tracked cache, preflighted regeneration, unique temp dir, configurable paths
    ('''RAMP_RIFE = True
RIFE_EXE = Path(r"moonshot-tools\\bin\\rife-ncnn-vulkan\\rife-ncnn-vulkan.exe")
RIFE_TMP = WORK / "rife_v20"
''',
     '''RAMP_RIFE = True
# v21 (Codex v20 review): the in-betweens are a TRACKED asset (work/rife_cache_v21: f###.png, input thumbnails,
# manifest.json with source frame, phase and sha256 of inputs and output). A normal build reads and verifies it (no
# RIFE, GPU or external tooling). MOONSHOT_RIFE_REGEN=1 regenerates (preflight before any output is opened, unique temp
# dir removed in finally); MOONSHOT_RIFE_SEED=<dir> fills the cache from an earlier run's f###_0/_1/_rife.png.
RIFE_EXE = Path(os.environ.get("MOONSHOT_RIFE_EXE", r"moonshot-tools\\bin\\rife-ncnn-vulkan\\rife-ncnn-vulkan.exe"))
RIFE_MODEL = Path(os.environ.get("MOONSHOT_RIFE_MODEL", str(RIFE_EXE.parent / "rife-v4.6")))
RIFE_CACHE = Path(os.environ.get("MOONSHOT_RIFE_CACHE", str(WORK / "rife_cache_v21")))
RIFE_REGEN = os.environ.get("MOONSHOT_RIFE_REGEN", "") == "1"
RIFE_SEED = os.environ.get("MOONSHOT_RIFE_SEED", "")
'''),
    ('''def rife_between(a: np.ndarray, b: np.ndarray, w: float, i: int) -> np.ndarray:
    """v20: ONE RIFE v4.6 frame between two neighbouring source frames at time step w (0..1). Raises on failure."""
    RIFE_TMP.mkdir(parents=True, exist_ok=True)
    p0, p1, po = RIFE_TMP / f"f{i:03d}_0.png", RIFE_TMP / f"f{i:03d}_1.png", RIFE_TMP / f"f{i:03d}_rife.png"
    Image.fromarray(a).save(p0)
    Image.fromarray(b).save(p1)
    if po.exists():
        po.unlink()
    run([str(RIFE_EXE), "-0", str(p0), "-1", str(p1), "-o", str(po), "-s", f"{w:.6f}",
         "-m", str(RIFE_EXE.parent / "rife-v4.6")])
    out = np.asarray(Image.open(po).convert("RGB"))
    if out.shape != a.shape:
        raise SystemExit(f"RIFE: {po.name} is {out.shape}, expected {a.shape}")
    return out
''',
     '''def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rife_thumb(a: np.ndarray) -> np.ndarray:
    return np.asarray(Image.fromarray(a).resize((96, 54), Image.Resampling.BOX), np.int16)


def rife_preflight(tmp: Path) -> None:
    """v21 (Codex): before any output is opened: the executable and model files exist and one 64x64 test
    interpolation runs (catches a missing GPU / Vulkan backend). Raises SystemExit naming what is missing."""
    missing = [p for p in (RIFE_EXE, RIFE_MODEL / "flownet.param", RIFE_MODEL / "flownet.bin") if not p.is_file()]
    if missing:
        raise SystemExit("RIFE regeneration requested, missing: " + ", ".join(map(str, missing))
                         + " (set MOONSHOT_RIFE_EXE / MOONSHOT_RIFE_MODEL)")
    t0, t1, to = tmp / "pre_0.png", tmp / "pre_1.png", tmp / "pre_o.png"
    Image.new("RGB", (64, 64), (40, 40, 40)).save(t0)
    Image.new("RGB", (64, 64), (200, 200, 200)).save(t1)
    r = subprocess.run([str(RIFE_EXE), "-0", str(t0), "-1", str(t1), "-o", str(to), "-s", "0.5", "-m", str(RIFE_MODEL)],
                       capture_output=True, text=True)
    if r.returncode != 0 or not to.is_file():
        raise SystemExit(f"RIFE preflight failed (exit {r.returncode}): {r.stderr[-600:]}")


def rife_frames(src: np.ndarray, plan: list[tuple[int, int, float]]) -> dict[int, np.ndarray]:
    """v21: the ramp's in-between frames {output index: RGB}. plan: (i, k, w) = output frame i between source frames
    k and k + 1 at phase w. Read from the tracked cache and verified (output sha256; inputs by sha256, or within
    2.0 levels on a 96x54 thumbnail when a different ffmpeg decodes the source a hair differently); regenerated
    (MOONSHOT_RIFE_REGEN=1) or seeded (MOONSHOT_RIFE_SEED) into the cache first when asked. Raises, never falls back."""
    man_p = RIFE_CACHE / "manifest.json"
    want = {str(i): {"k": k, "w": round(w, 6), "in0": sha256(src[k].tobytes()), "in1": sha256(src[k + 1].tobytes())}
            for i, k, w in plan}
    if RIFE_REGEN or RIFE_SEED:
        made: dict[int, bytes] = {}
        if RIFE_REGEN:
            tmp = Path(tempfile.mkdtemp(prefix="moonshot_rife_"))      # unique per run (Codex: no shared names)
            try:
                rife_preflight(tmp)
                for i, k, w in plan:
                    p0, p1, po = tmp / f"f{i:03d}_0.png", tmp / f"f{i:03d}_1.png", tmp / f"f{i:03d}_rife.png"
                    Image.fromarray(src[k]).save(p0)
                    Image.fromarray(src[k + 1]).save(p1)
                    run([str(RIFE_EXE), "-0", str(p0), "-1", str(p1), "-o", str(po), "-s", f"{w:.6f}",
                         "-m", str(RIFE_MODEL)])
                    made[i] = po.read_bytes()
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            how = f"regenerated with {RIFE_EXE.name} -m {RIFE_MODEL.name}"
        else:
            sd = Path(RIFE_SEED)
            for i, k, w in plan:
                for j, kk in ((0, k), (1, k + 1)):
                    got = np.asarray(Image.open(sd / f"f{i:03d}_{j}.png").convert("RGB"))
                    if not np.array_equal(got, src[kk]):
                        raise SystemExit(f"RIFE seed {sd}: f{i:03d}_{j}.png is not this decode's source frame {kk}")
                made[i] = (sd / f"f{i:03d}_rife.png").read_bytes()
            how = f"seeded from {sd.name} ({RIFE_MODEL.name} outputs of an earlier run; inputs verified pixel-equal)"
        RIFE_CACHE.mkdir(parents=True, exist_ok=True)
        for i, k, w in plan:
            (RIFE_CACHE / f"f{i:03d}.png").write_bytes(made[i])
            Image.fromarray(rife_thumb(src[k]).astype(np.uint8)).save(RIFE_CACHE / f"f{i:03d}_in0.png")
            Image.fromarray(rife_thumb(src[k + 1]).astype(np.uint8)).save(RIFE_CACHE / f"f{i:03d}_in1.png")
            want[str(i)]["out"] = sha256(made[i])
        man = {"what": "MOONSHOT ignition ramp (s11) RIFE in-betweens; build.py render_ramp_shot", "how": how,
               "frames": want}
        tmp_m = man_p.with_name("manifest.json.tmp")
        tmp_m.write_text(json.dumps(man, indent=1), encoding="utf-8")
        os.replace(tmp_m, man_p)
        print(f"  RIFE cache {RIFE_CACHE.name}: {len(plan)} frames {how}")
    if not man_p.is_file():
        raise SystemExit(f"RIFE cache missing: {man_p}. Regenerate (MOONSHOT_RIFE_REGEN=1, needs RIFE + a GPU) or set "
                         "RAMP_RIFE = False (v19's blends)")
    man = json.loads(man_p.read_text(encoding="utf-8"))["frames"]
    out: dict[int, np.ndarray] = {}
    for i, k, w in plan:
        e, exp = man.get(str(i)), want[str(i)]
        if e is None or e["k"] != exp["k"] or abs(e["w"] - exp["w"]) > 1e-6:
            raise SystemExit(f"RIFE cache stale at output frame {i} (the ramp map changed): regenerate")
        for j, kk in (("in0", k), ("in1", k + 1)):
            if e[j] != exp[j]:
                ref = np.asarray(Image.open(RIFE_CACHE / f"f{i:03d}_{j}.png"), np.int16)
                dev = float(np.abs(ref - rife_thumb(src[kk])).mean())
                if dev > 2.0:
                    raise SystemExit(f"RIFE cache stale at output frame {i}: source frame {kk} differs "
                                     f"({dev:.2f} levels on the thumbnail): regenerate")
                print(f"  RIFE cache: frame {i} {j} decodes {dev:.2f} levels off the cached input (accepted)")
        b = (RIFE_CACHE / f"f{i:03d}.png").read_bytes()
        if sha256(b) != e["out"]:
            raise SystemExit(f"RIFE cache: f{i:03d}.png does not match its manifest sha256")
        fr = np.asarray(Image.open(io.BytesIO(b)).convert("RGB"))
        if fr.shape != src[k].shape:
            raise SystemExit(f"RIFE cache: f{i:03d}.png is {fr.shape}, expected {src[k].shape}")
        out[i] = fr
    return out
'''),
    ('''        raise SystemExit(f"ramp: decoded {len(src)} source frames from {s.src} {s.src_in}, the map needs {need}")
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "14", "-preset", "veryfast",
                            "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    exact = 0
    for i in range(n):
        x = pos[i] * sfps
        k = int(math.floor(x + 1e-9))
        w = x - k
        if w < 1e-6:
            fr = src[k]
            exact += 1
        elif RAMP_RIFE:      # v20: flow in-between at the mapped phase (v19: the linear blend below)
            fr = rife_between(src[k], src[k + 1], w, i)
        else:
            fr = (src[k].astype(np.float32) * (1 - w) + src[k + 1].astype(np.float32) * w + 0.5).astype(np.uint8)
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
''',
     '''        raise SystemExit(f"ramp: decoded {len(src)} source frames from {s.src} {s.src_in}, the map needs {need}")
    plan = []
    for i in range(n):
        x = pos[i] * sfps
        k = int(math.floor(x + 1e-9))
        if x - k >= 1e-6:
            plan.append((i, k, x - k))
    rife = rife_frames(src, plan) if RAMP_RIFE else {}     # v21: cache / regeneration BEFORE any output is opened
    part = path.with_name(path.stem + ".part.mp4")          # v21: the segment is replaced only after a clean encode
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "14", "-preset", "veryfast",
                            "-pix_fmt", "yuv420p", str(part)], stdin=subprocess.PIPE)
    exact = 0
    for i in range(n):
        x = pos[i] * sfps
        k = int(math.floor(x + 1e-9))
        w = x - k
        if w < 1e-6:
            fr = src[k]
            exact += 1
        elif RAMP_RIFE:      # v20: flow in-between at the mapped phase (v19: the linear blend below)
            fr = rife[i]
        else:
            fr = (src[k].astype(np.float32) * (1 - w) + src[k + 1].astype(np.float32) * w + 0.5).astype(np.uint8)
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        part.unlink(missing_ok=True)
        raise SystemExit(f"ramp: encoding {part.name} failed; {path.name} left as it was")
    os.replace(part, path)
'''),
]
s = apply(s, R, "build")

# ============================================================== score_pd.py: unchanged (v19b expected)
sc = load(S)
assert "v19b" in sc, "score_pd.py: v19b expected"
save(P, s)
print(f"v21: build {len(R)} replacements; score_pd unchanged. Re-render: shots 21 9,11,15 (seed the RIFE cache once); "
      "comp 21; mix 21.")
