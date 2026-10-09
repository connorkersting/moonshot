"""v19 CANDIDATE: the music-locked montage recut (RECUT_BRIEF_v19.md, revision R1-R7 after codex_recut_review.md).
Apply to the v18 source (build.py + score_pd.py, tag v18-final):

    py patch_v19.py                      # the real build.py + score_pd.py in work/
    py patch_v19.py BUILD.py SCORE.py    # dry run on copies

Kept exactly (R1/R5): 2,100 frames at 24 fps; the frame-799 logical map (tl = fi/24 below, (fi + 161)/24 from it);
DIALOG, CAPTIONS and the spoken-count table; the Moon beat (frames 799-877); the Egmont stop 61.9 + ring-out; the
Largo entry 62.39; the Earthrise from frame 1510; the credits from frame 1891; every music span; white frame 1349 and
touchdown from 1350. Every cut is an integer frame inside a fixed block; nothing downstream ripples. The authored sync
map, the cut list and the overlay table: work/recut_v19/EVENT_MAP.md, work/recut_v19/OVERLAY_TABLE.md.

Changes (REAL times / output frames):
 1  Cold open, count "2" (frames 202-226): split on the music's quarter pulse. Firing room 202-215 (13 fr), then the
    umbilical swing arm retracting 215-226 (11 fr, BR 683.30; source shot 683.15-684.15). Count "1" (226-254, the
    slowed engine bells) is kept as the held breath into the drop. Counts 10-3 keep v18's count-locked cuts.
 2  Drop 254-283: the ONE speed-ramp experiment (R4) on the ignition fireball (SV 34.2; source shot 33.17-35.71).
    Speed knots (output frame, x): 1.0 to f3, eases to 0.44 by f10 (the 10.98 accent), holds 0.44 to f19, SNAPS to 1.0
    at f19 (frame 273, the 11.38 accent), real time to the 283 cut (11.77 accent). 0.44 makes the source position at
    f19 exactly 12 source frames, so the real-time tail shows whole source frames, not 50/50 blends. Frames are selected from the
    original source timestamps (one bounded decode, source fps read from the file), source position = integral of the
    speed (continuous through the snap), linear blend between the two neighbouring source frames only (no blending
    across a source cut: the ramp uses src 34.20-35.08 inside one shot), no clamping (raises if the decode is short).
    RAMP_IGNITION = False is the constant-speed fallback (the v18 1.0x render of the same shot).
 3  Launch tail 422-456: the smoke/title shot runs to frame 424 (17.667, the z7.0 accent at 17.676; title gone 17.25),
    the tower climb 424-444 (20 fr, out on the 18.506 accent), NEW long-lens rocket clear in a grey sky 444-456
    (SV 137.2, source shot 136.75-140.83, 12 fr), then act 2 at 456 (19.0, phrase change) as before.
 4  Act 2: the F-1/thrust shot ends at frame 524 (21.833, the z5.6 accent at 21.844; was 528). The thrust stat's
    exit moves 0.15 s earlier with it (out 2.45-2.80 s, gone before the cut). The 3D ascent starts at 524 and plays
    at 1.70x (112 fr x 1.70 = 190.4 of 192 rendered frames; was 108 fr x 1.77). The whoosh peaks move with their cuts
    (score: 17.45 -> 17.53, 21.95 -> 21.83: the same offset before each cut as in v18).
 5  Act 3, 1202: the cut to Mission Control moves from frame 1054 to 1045 (43.542), the Allegro's re-entry after
    Beethoven's general pause (strongest Egmont onset, z8.8 at 43.526). The MC shot starts 9 frames earlier in its
    source (1250.625; the group shot starts at 1250.38), so its internal source cut back to the LM window stays at frame
    1096 (DSKY_OUT unchanged). DSKY_RIGHT_T = frame 1045 and the cut's glitch moves with it (frames 1045-1047).
 6  Landing montage 1217-1322 (R3: recognizable details, 10-37 fr, no flashes, no new labels): dust 1217-1254 (out on
    the 52.23 accent, after "40 feet, down 2 1/2" ends at 52.16) -> NEW Houston face, a controller in glasses listening
    1254-1266 (BR 1242.6, source shot 1241.54-1246.01) -> back on the dust at "Picking" 1266-1284 (source continuous:
    1360.2 + 49/24) -> consoles 1284-1312 (the altitude step at 1284 kept; holds through "30 seconds", out on the
    54.65 accent) -> NEW crew-cut controller looking down 1312-1322 (BR 1246.4, source shot 1246.01-1248.45, 10 fr) ->
    the CONTACT insert 1322-1349 (unchanged, held through "Contact light.") -> white 1349 -> touchdown 1350.
 7  l70_window (R1): an L70 run shorter than 18 frames never shows the countdown HUD (no 6-frame half-alpha blink).
 8  Opening title (Fable note): composited 1.08x about its right edge (x 1823) and its baseline (y 485), lifted 14 px:
    ~49% of the frame width at full size (v18 ~46%), right-anchored, still clear of the tower truss. Compositing only:
    the Blender render (title3d_v18) is untouched. The rim light at 360p is NOT changed (that needs a Blender re-render).
 9  End card (R5): the plate is darkened 0.5 BEFORE the title is laid in (Shot.bg_darken; v18 darkened 0.35 after
    the title, then lifted the title RGB 1.35x to compensate: dropped). The end title is scaled 0.80 (~42% width) and set
    in the black sky right of the Earth (glyph box x 985-1800, y 118-272; Earth x 801-897, y 82-140; horizon y >= 296
    under the title): the v18 title sat across the horizon at 52% width, centred. The subtitle moves under it (centre
    x 1392, y 420, on the darkened ground); the still's push is halved (1.04 -> 1.02) so the horizon stays put.

Re-render chain (after review): py patch_v19.py, then py build.py shots 19 (all: SHOTS gains 6 entries, indices
shift), py build.py music 19 (two whoosh times), py build.py comp 19, py build.py mix 19 (dialog stem unchanged; run
dialog 19 too if in doubt). QC: py flashqc.py ..\\..\\..\\exports\\moonshot\\versions\\moonshot_v19.mp4 (must PASS).
"""
import sys
import os
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


# ============================================================== build.py
s = load(P)
assert "moon_portrait_v18" in s and 'TITLE_DIR = "title3d_v18"' in s, "apply patch_v18 + patch_v18m first (tag v18-final)"
assert "IGNITION_RAMP" not in s and "bg_darken" not in s, "v19 already applied"
R = [
    # ---- Shot fields
    ('''    grade: str | None = None      # v15: SEQ only: a GRADE key appended to the render (CG -> 16mm match)
''',
     '''    grade: str | None = None      # v15: SEQ only: a GRADE key appended to the render (CG -> 16mm match)
    ramp: tuple | None = None     # v19 (R4): ((output frame, speed), ...) piecewise-linear speed; None = constant `speed`
    bg_darken: float = 0.0        # v19 (R5): darkens the PLATE before the title is laid in (`darken` acts after it)
'''),
    ('''

SHOTS: list[Shot] = [
''',
     '''

# v19 (R4): the one speed-ramp experiment, the ignition fireball (s11). Knots (output frame, speed): real time on the
# drop, eases to 0.44x by the 10.98 accent (f10), holds, snaps back to 1.0x on the 11.38 accent (f19 = frame 273).
# RAMP_IGNITION = False: constant-speed fallback (v18's 1.0x render of the same source in-point).
RAMP_IGNITION = True
IGNITION_RAMP = ((0, 1.0), (3, 1.0), (10, 0.44), (19, 0.44), (19, 1.0), (29, 1.0))   # 3 + 3.5 x 1.44 + 9 x 0.44 = 12.0 source frames at f19: the real-time tail lands on whole source frames (no blend)

SHOTS: list[Shot] = [
'''),
    # ---- 1  cold open, count "2"
    ('''    Shot(8.40, 9.40, "BR", 694.0, push=(1.06, 1.0), note="back to the firing room"),
''',
     '''    # v19: count "2" split on the quarter pulse (cut 215 = 8.958, the 8.945 accent): firing room, then the swing arm
    Shot(8.40, 8.9583, "BR", 694.0, push=(1.03, 1.0), note="v19: back to the firing room, 13 fr (v18: 24 fr)"),
    Shot(8.9583, 9.40, "BR", 683.30, push=(1.0, 1.02), note="v19: umbilical swing arm retracting (BR shot 683.15-684.15), 11 fr; count 1 holds after it"),
'''),
    # ---- 2  drop: the ramp
    ('''    Shot(10.60, 11.80, "SV", 34.2, push=(1.12, 1.0), note="ignition fireball, high-speed camera"),
''',
     '''    Shot(10.60, 11.80, "SV", 34.2, push=(1.12, 1.0), ramp=IGNITION_RAMP, note="ignition fireball, high-speed camera; v19: speed ramp 1.0 -> 0.44 -> snap 1.0 at frame 273 (src 34.20-35.12, shot 33.17-35.71)"),
'''),
    # ---- 3  launch tail
    ('''    Shot(13.00, 17.60, "L70", 18.0, speed=0.5, crop="1220:686:520:980", push=(1.0, 1.08), darken=0.25, note="smoke under the title (v9: recrop, no pole through the M, clear of the gate corner)"),
    Shot(17.60, 19.00, "SV", 100.0, push=(1.0, 1.05), note="rocket climbs past the tower"),
''',
     '''    Shot(13.00, 17.6667, "L70", 18.0, speed=0.5, crop="1220:686:520:980", push=(1.0, 1.08), darken=0.25, note="smoke under the title (v9: recrop, no pole through the M, clear of the gate corner); v19: out at frame 424 (the 17.676 accent; was 422)"),
    Shot(17.6667, 18.50, "SV", 100.0, push=(1.0, 1.03), note="rocket climbs past the tower; v19: 20 fr, out on the 18.506 accent"),
    Shot(18.50, 19.00, "SV", 137.2, push=(1.0, 1.0), note="v19: long lens, the rocket clear of the pad in a grey sky (SV shot 136.75-140.83), 12 fr"),
'''),
    # ---- 4  act 2
    ('''    Shot(19.00, 22.00, "SV", 70.0, push=(1.0, 1.06), darken=0.1, note="F-1 engine bells (stat 1)"),
''',
     '''    Shot(19.00, 21.8333, "SV", 70.0, push=(1.0, 1.057), darken=0.1, note="F-1 engine bells (stat 1); v19: out at frame 524 (the 21.844 accent; was 528)"),
'''),
    ('''    Shot(22.00, 26.50, "SEQ", 1.0, speed=1.77, img="ascent_blender_v5/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values (108 fr x 1.77 = 191 of 192)"),
''',
     '''    Shot(21.8333, 26.50, "SEQ", 1.0, speed=1.70, img="ascent_blender_v5/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values (v19: 112 fr x 1.70 = 190.4 of 192; v18 108 fr x 1.77)"),
'''),
    # ---- 5  act 3, the cut to Mission Control on the Allegro's re-entry
    ('''    Shot(42.30, 43.90, "BR", 1258.5, push=(1.0, 1.08), note="descent, LM window (Eagle: 1202)"),
    Shot(43.90, 46.10, "BR", 1251.0, push=(1.0, 1.06), note="Mission Control (Eagle asks for a reading); source cuts back to the LM window at frame 1096 (real 45.667)"),
''',
     '''    Shot(42.30, 43.5417, "BR", 1258.5, push=(1.0, 1.062), note="descent, LM window (Eagle: 1202); v19: out at frame 1045 (was 1054)"),
    Shot(43.5417, 46.10, "BR", 1250.625, push=(1.0, 1.07), note="Mission Control (Eagle asks for a reading); v19: in at frame 1045 on the Allegro's re-entry after the general pause (43.526), src 1250.625 (group shot from 1250.38), so the source still cuts back to the LM window at frame 1096 (real 45.667)"),
'''),
    # ---- 6  landing montage
    ('''    Shot(50.70, 53.50, "BR16L", 1360.2, push=(1.0, 1.08), note="16mm: dust (Aldrin's calls)"),
    Shot(53.50, 55.10, "BR", 1237.5, push=(1.0, 1.05), note="Mission Control consoles, tense (Houston: 30 seconds)"),
''',
     '''    Shot(50.70, 52.25, "BR16L", 1360.2, push=(1.0, 1.044), note="16mm: dust (Aldrin's calls); v19: out at frame 1254 (the 52.23 accent, after '40 feet, down 2 1/2' ends 52.16)"),
    Shot(52.25, 52.75, "BR", 1242.6, push=(1.0, 1.02), note="v19: Houston listening, a controller in glasses (BR shot 1241.54-1246.01), 12 fr"),
    Shot(52.75, 53.50, "BR16L", 1362.2417, push=(1.0585, 1.08), note="v19: back on the dust at 'Picking' (52.76); source and push continuous (1360.2 + 49/24)"),
    Shot(53.50, 54.6667, "BR", 1237.5, push=(1.0, 1.04), note="Mission Control consoles, tense (Houston: 30 seconds); v19: 28 fr, out on the 54.654 accent after the line"),
    Shot(54.6667, 55.10, "BR", 1246.4, push=(1.0, 1.02), note="v19: a crew-cut controller looking down (BR shot 1246.01-1248.45), 10 fr, into the CONTACT insert"),
'''),
    # ---- 9  end card
    ('''    Shot(76.70, 78.80, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.04)), darken=0.35, note="end title: Earth high, LM low (inside safe)"),
''',
     '''    Shot(76.70, 78.80, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.02)), bg_darken=0.5, note="end title: Earth high, LM low (inside safe); v19 (R5): plate darkened 0.5 before the title (v18: 0.35 after it), push halved so the horizon stays under the raised title"),
'''),
    # ---- 2  ramp renderer
    ('''def render_video_shot(s: Shot, path: Path) -> None:
    n = nframes(s)
''',
     '''def ramp_map(knots: tuple, n: int) -> np.ndarray:
    """v19 (R4): source offset (s) of each output frame i = the integral of the speed from the shot's first frame to i
    (midpoint rule per frame: exact for piecewise-linear speed with knots on whole frames), so a speed step keeps the
    source position continuous. Knots ((output frame, speed), ...): starts at 0, non-decreasing (a repeated frame is a
    step), covers n frames, speeds > 0. A bad map raises (no clamping)."""
    fr = [float(k[0]) for k in knots]
    sp = [float(k[1]) for k in knots]
    if fr[0] != 0 or fr[-1] < n or any(b < a for a, b in zip(fr, fr[1:])) or min(sp) <= 0:
        raise SystemExit(f"bad ramp knots {knots} for {n} frames")

    def speed(u: float) -> float:
        for a, va, b, vb in zip(fr, sp, fr[1:], sp[1:]):
            if a <= u < b:
                return va + (vb - va) * (u - a) / (b - a)
        return sp[-1]

    pos = np.zeros(n)
    for i in range(1, n):
        pos[i] = pos[i - 1] + speed(i - 0.5) / FPS
    return pos


def render_ramp_shot(s: Shot, path: Path) -> None:
    """v19 (R4): a time-remapped video shot. ONE bounded decode from src_in at the source's own frame rate (no fps
    conversion), then each output frame takes the source frame at its mapped timestamp, or a linear blend of the two
    neighbouring source frames between them (the shot never crosses a source cut). Raises if the decode is short."""
    n = nframes(s)
    pos = ramp_map(s.ramp, n)
    rate = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                           "-of", "csv=p=0", str(SRC[s.src])], capture_output=True, text=True).stdout.strip()
    num, den = (int(v) for v in rate.split("/"))
    sfps = num / den
    need = int(math.floor(pos[-1] * sfps + 1e-9)) + 2          # last source frame used, + its blend partner
    crop = s.crop or CROP.get(s.src)
    vf = ([f"crop={crop}"] if crop else []) + [f"scale={W}:{H}:flags=lanczos", GRADE[s.src], "format=rgb24"]
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{s.src_in:.3f}", "-i", str(SRC[s.src]), "-vf", ",".join(vf),
                          "-fps_mode", "passthrough", "-frames:v", str(need), "-an", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    src = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
    if len(src) < need:
        raise SystemExit(f"ramp: decoded {len(src)} source frames from {s.src} {s.src_in}, the map needs {need}")
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
        else:
            fr = (src[k].astype(np.float32) * (1 - w) + src[k + 1].astype(np.float32) * w + 0.5).astype(np.uint8)
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
    d = np.diff(pos)
    print(f"  ramp {s.src} src {s.src_in:.3f}-{s.src_in + pos[-1]:.3f} ({pos[-1] * sfps:.2f} source frames at "
          f"{sfps:g} fps) for {n} output frames; step min {d.min() * FPS:.3f}x max {d.max() * FPS:.3f}x, monotonic "
          f"{bool((d > 0).all())}; {exact} exact source frames, {n - exact} two-frame blends")


def render_video_shot(s: Shot, path: Path) -> None:
    if s.ramp is not None and RAMP_IGNITION:     # v19 (R4); RAMP_IGNITION = False renders the constant-speed shot
        render_ramp_shot(s, path)
        return
    n = nframes(s)
'''),
    # ---- 7  l70_window: short runs never show the HUD
    ('''    for f0, f1 in runs:
        a, b = f0 / FPS, (f1 - 1) / FPS
''',
     '''    for f0, f1 in runs:
        if f1 - f0 < 18:      # v19 (R1): a short L70 insert (< 0.75 s) never shows the HUD (was a 6-frame half-alpha blink)
            continue
        a, b = f0 / FPS, (f1 - 1) / FPS
'''),
    # ---- 5  DSKY side switch on the moved cut
    ('''DSKY_RIGHT_T = 50.62     # v11: logical time of the cut to Mission Control (s23, v14 s26, v15 s25, frame 1054 -> tl 50.625, under the 50.6 glitch)
''',
     '''DSKY_RIGHT_T = (1045 + 161) / 24   # v19: the cut to Mission Control moved to frame 1045 (tl 50.25); v11-v18 50.62 (frame 1054)
'''),
    ('''GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (49.0, 49.2, 1.0), (50.6, 50.72, 0.6)]
''',
     '''GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (49.0, 49.2, 1.0), (50.24, 50.36, 0.6)]   # v19: the last one follows the MC cut (frames 1045-1047; v18 50.6-50.72 = 1054-1056)
'''),
    # ---- 4  thrust stat out before the 524 cut
    ('''        out = ease_in_out((u - 2.6) / 0.35)
''',
     '''        out = ease_in_out((u - 2.45) / 0.35)     # v19: gone by u 2.80 (real 21.80), before the 524 cut (v18 2.6-2.95)
'''),
    # ---- 9  end-card subtitle under the raised title
    ('''            self.text(d, (W / 2, 510), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)
''',
     '''            self.text(d, (1392, 420), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)   # v19: under the raised title (x 985-1800), on the darkened ground (v18 centre, y 510)
'''),
    # ---- 8 + 9  title placement (compositing only)
    ('''def title_layer(gfx: "Gfx", t: float) -> Image.Image | None:
''',
     '''# v19: title placement in the comp (the Blender renders are untouched). (scale, anchor x, anchor y, new x, new y): the
# anchor point of the render moves to (new x, new y) and the letters scale about it.
TITLE_OPEN_FIT = (1.08, 1823.0, 485.0, 1823.0, 471.0)   # right edge + baseline: ~49% width, lifted 14 px, clear of the truss
TITLE_END_FIT = (0.80, 1470.0, 220.0, 1800.0, 118.0)    # glyph box right/top (1470, 220) -> (1800, 118): in the black sky right of the Earth


def fit_title(ti: Image.Image, fit: tuple) -> Image.Image:
    """v19: scale an RGBA title frame about an anchor and move the anchor (premultiplied resampling: no dark fringes)."""
    sc, ax, ay, nx, ny = fit
    pm = ti.convert("RGBa").transform((W, H), Image.Transform.AFFINE,
                                      (1 / sc, 0, ax - nx / sc, 0, 1 / sc, ay - ny / sc), Image.Resampling.BICUBIC)
    return pm.convert("RGBA")


def title_layer(gfx: "Gfx", t: float) -> Image.Image | None:
'''),
    ('''        ti = Image.open(gfx.title_end[idx]).convert("RGBA")
        # v18: the comp darkens this shot by 35% (darken=0.35) AFTER the title is laid in; lift the matte title's RGB so
        # it is not muddy on the grey surface (dry-run preview)
        ta_ = np.asarray(ti, np.float32)
        ta_[..., :3] = np.clip(ta_[..., :3] * 1.35, 0, 255)
        ti = Image.fromarray(ta_.astype(np.uint8), "RGBA")
''',
     '''        # v19 (R5): the plate is darkened BEFORE the title (Shot.bg_darken), so the v18 1.35x RGB lift is gone; the
        # title sits in the black sky between the Earth and the horizon (TITLE_END_FIT)
        ti = fit_title(Image.open(gfx.title_end[idx]).convert("RGBA"), TITLE_END_FIT)
'''),
    ('''    if t < 83.4:
        ti = Image.open(gfx.title[idx]).convert("RGBA")
''',
     '''    if t < 83.4:
        ti = fit_title(Image.open(gfx.title[idx]).convert("RGBA"), TITLE_OPEN_FIT)     # v19: more presence
'''),
    # ---- 9  plate darkening before the title
    ('''        ttl = title_layer(gfx, tl)
''',
     '''        if s.bg_darken:                  # v19 (R5): darken the plate only; the title is laid in after this, undarkened
            fr = (fr.astype(np.float32) * (1 - s.bg_darken) + 0.5).astype(np.uint8)
        ttl = title_layer(gfx, tl)
'''),
]
s = apply(s, R, "build")

# ============================================================== score_pd.py
sc = load(S)
assert "(PD / \"dvorak9_ii_largo.ogg\", 4.69, 29.05, 62.39" in sc, "apply patch_v18m first (score)"
assert "17.53, -8.0" not in sc, "v19 already applied (score)"
RS = [
    ('''    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 17.45, -8.0, "peak", 3.0),
''',
     '''    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 17.53, -8.0, "peak", 3.0),    # v19: 17.45 -> 17.53 with the cut (17.6 -> 17.667)
'''),
    ('''    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 21.95, -10.0, "peak", 3.0),
''',
     '''    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 21.83, -10.0, "peak", 3.0),   # v19: 21.95 -> 21.83 with the cut (22.0 -> 21.833)
'''),
]
sc = apply(sc, RS, "score")

# ============================================================== invariants on the patched text (no import side effects)
ns: dict = {}
argv_, sys.argv = sys.argv, ["build.py"]          # the head reads VERSION from argv[2]
exec(compile(s.split("# ---------------------------------------------------------------- helpers")[0], "build_head", "exec"), ns)
sys.argv = argv_
shots, fps = ns["SHOTS"], ns["FPS"]
fr = [(int(round(x.t0 * fps)), int(round(x.t1 * fps))) for x in shots]
assert fr[0][0] == 0 and fr[-1][1] == 2100, fr[-1]
assert all(b > a for a, b in fr), "non-positive shot"
assert all(fr[i][1] == fr[i + 1][0] for i in range(len(fr) - 1)), "gap or overlap"
cuts = {a for a, _ in fr}
for f_ in (29, 254, 312, 456, 636, 654, 672, 715, 744, 799, 878, 1096 - 51, 1284, 1322, 1349, 1350, 1486, 1510, 1891):
    assert f_ in cuts, f"anchor cut {f_} missing"
moon = [x for x in shots if "moon_portrait_v18" in (x.img or "")]
assert len(moon) == 1 and fr[shots.index(moon[0])] == (799, 878)
save(P, s)
save(S, sc)
print(f"v19: build {len(R)} patches, score {len(RS)}; {len(shots)} shots, {len(cuts) - 1} cuts, 2100 frames contiguous. "
      f"Re-render: py build.py shots 19 (all), music 19, comp 19, mix 19; then py flashqc.py on the export.")
