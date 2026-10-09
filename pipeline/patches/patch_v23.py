"""v23 CANDIDATE: the ascent beat rebuilt in the overlay system, a cold-open flash-forward tag, phone-size disclosure
tags, an on-screen AI-assist line on the end card, and the Codex v22 engineering items. Apply to the v22 source
(build.py + title_manifest_v22.py at tag v22-src / v22-final):

    py patch_v23.py                                  # the real build.py, title_manifest_v22.py, repo_src/make_repo.py
    py patch_v23.py BUILD.py TITLEMAN.py MAKEREPO.py # dry run on copies (hud_v20-23.py + assets_v23.py next to BUILD.py)

Brief: the v23 builder brief (2026-10-08; BRIEF_v22 R1-R6 still hold) + exports/moonshot/AUDIT_2026-10-08.md queue
items 1-2 and their acceptance tests; critics: qc/v22/fable_editor.json (typography / colour: the ascent card is the
last off-system card), qc/v22/crowd_ftv.json (no on-screen AI disclosure on a shared clip; phone-size honesty tags);
engineering: work/codex_review_v22.md. Drawing lives in the NEW module hud_v23.py (its docstring lists every change),
asset validation in the NEW module assets_v23.py; hud_v20-22 are unchanged and V23_HUD = False draws v22 exactly
(including the v5 ascent render).

Kept exactly: 2,100 frames; the frame-799 map (tl = fi / 24 below 799, (fi + 161) / 24 from it); DIALOG / CAPTIONS; the
cut list; every value computation; the Moon beat 799-877 (EXCEPT the director-approved drum-style 240,000 card,
V22_DISTANCE = True: frames 830-877 change, timing unchanged), the 1:02 transition 1486-1524 and the credits 1891-2099 (no
v23 element draws there: the end note is gone before 1891 by the date line's own alpha); the AUDIO (v22's AAC stream,
= v21's, copied and verified by md5).

 1  ASCENT (frames 524-635): the shot reads work/ascent_blender_v23 (blender/ascent3d_v23.py: v5's scene with NO baked
    text; manifest + geometry.json + the measured display map, ascent_manifest_v23.py). hud_v23.render_ascent draws the
    title, the 6x disclosure (TAG), the readouts (v5's strings for the displayed asset frame) and the MAX Q / INBOARD
    ENGINE CUTOFF labels at positions proven clear of the projected tube, both rings and the limb on every frame
    (hud_v23.asc_layout). hud_v23.globe_grain adds 16 mm-matched grain to the CG globe in stage_comp.
 2  COLD OPEN: the flash-forward block (frames 94-201) carries '4 DAYS LATER' / 'THE MOON' in the countdown slot
    (the countdown HUD is gated off on those shots; the tag is skipped on any frame where it is not).
 3  DISCLOSURE TAGS at >= 12 px cap at 360p (TAG = 56): TIME-COMPRESSED (to a plate under the monitor),
    ARCHIVE: OTHER SATURN V FLIGHT (to the top-left slot), HEIGHT + DISTANCE EXAGGERATED 6X (ascent plate).
 4  END CARD: 'EDITED WITH AN AI AGENT' / 'ARCHIVAL NASA FOOTAGE' under the date line, with the date line's alpha.
 5  REUSE_AUDIO_FROM (Codex v22 high): the source's audio stream must match a pinned packet md5 and duration BEFORE
    the destination is opened; the mux writes a .part file, which must decode to exactly 2,100 frames and carry the
    pinned audio md5 before it is renamed (no silent -shortest truncation).
 6  Title manifest (Codex v22 medium): validate_assets() and title_manifest_v22.py --check share
    assets_v23.check_title, which also checks the recorded renderer + postprocessor source hashes.
 7  Preflight (Codex v22 medium): preflight(stage) runs at the entrypoint before any stage writes: every manifested
    asset (title, ascent), the RIFE cache files against their manifest, and the reused audio.
 10 make_repo.py (Codex v22 medium): exports hud_v23 / assets_v23 / ascent_manifest_v23 / ascent3d_v23, and rewrites the
    craft-tools drive paths (audio_qc2.py CRAFT, the manifest tools' Blender path) to the CRAFT_TOOLS setting, so the
    scrub scan passes.
 +  IDR at frame 1891 in the comp and export encodes (-force_key_frames expr:eq(n,1891) -forced-idr 1), and
    MOONSHOT_FRAME_HASHES=<path> makes stage_comp write the sha256 of every frame BEFORE encoding (the protected-frame
    gate compares pre-encode frames, not decodes).

Re-render chain (real tree, after the Blender render + manifest are committed):
    py patch_v23.py; py title_manifest_v22.py --check; py ascent_manifest_v23.py --check;
    py build.py shots 23 17 (the ascent SEQ shot); py build.py comp 23; py build.py mix 23 (v22's audio, verified);
    py flashqc2.py ..\\..\\..\\exports\\moonshot\\versions\\moonshot_v23.mp4 (must PASS).
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
T = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "title_manifest_v22.py"

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build.py is CRLF)."""
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
assert "import hud_v22" in s and "V22_HUD = True" in s and "def validate_assets" in s, "apply patch_v22 first (v22-src)"
assert "hud_v23" not in s, "v23 already applied"
for mod in ("hud_v20.py", "hud_v21.py", "hud_v22.py", "hud_v23.py", "assets_v23.py"):
    assert (P.parent / mod).exists(), f"{mod} must sit next to {P.name}"
R = [
    # ---- modules + flag
    ('''import hud_v22      # v22: one overlay system (labels, plates, housings, one film pass), odometer carry fix, DSKY header
''',
     '''import hud_v22      # v22: one overlay system (labels, plates, housings, one film pass), odometer carry fix, DSKY header
import hud_v23      # v23: ascent text in the system (no baked labels), flash-forward tag, TAG-size disclosures, end note
import assets_v23   # v23: the one validator for manifested assets (title + ascent), shared with the manifest tools
'''),
    ('''SHOTS: list[Shot] = [
''',
     '''V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly
SHOTS: list[Shot] = [
'''),
    # ---- director (Connor, 2026-10-08 16:40, "yes use new style"): the drum-style 240,000 card inside the Moon beat
    ('''V22_DISTANCE = False    # v22: the drum-style 240,000 card (hud_v22). True changes the protected Moon beat (frames 830-877):
#                         only for the director's preview (auditions/v22_distance_card_preview.mp4) unless he approves
''',
     '''V22_DISTANCE = True     # v23: the director approved the drum-style 240,000 card (2026-10-08 16:40, after the preview
#                         auditions/v22_distance_card_preview.mp4); frames 830-877 change, timing unchanged. False: v22
'''),
    # ---- 1: the text-free ascent render
    ('''    Shot(21.8333, 26.50, "SEQ", 1.0, speed=1.70, img="ascent_blender_v5/asc_%04d.png", note="Blender:''',
     '''    # v23: ascent_blender_v23 (blender/ascent3d_v23.py): v5's scene, NO baked text; hud_v23 draws the text
    Shot(21.8333, 26.50, "SEQ", 1.0, speed=1.70, img=("ascent_blender_v23/asc_%04d.png" if V23_HUD else "ascent_blender_v5/asc_%04d.png"), note="Blender:'''),
    # ---- 6 + 1: one validator (frames + recorded source hashes), the ascent asset, its layout
    ('''def validate_assets() -> None:
    """v22 (R4, Codex): the pre-rendered title is a tracked asset (work/title3d_v22: open_0001-0104.png, end_0001-0056.png,
    manifest.json with sources, props, font / HDRI hashes, renderer versions, size, fps, alpha convention and sha256 per
    frame; written by title_manifest_v22.py). Checked BEFORE stage_comp opens any output: a missing manifest, a missing,
    extra or changed frame, or a wrong size fails the build. No Blender needed."""
    d = WORK / TITLE_DIR
    mp = d / "manifest.json"
    if not mp.is_file():
        raise SystemExit(f"title asset: {mp} missing (render with blender/title_v22.py + title_post_v18.py, then "
                         "py title_manifest_v22.py)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    for mode, n in TITLE_FRAMES.items():
        want = [f"{mode}_{k:04d}.png" for k in range(1, n + 1)]
        have = sorted(p.name for p in d.glob(f"{mode}_*.png"))
        if have != want:
            raise SystemExit(f"title asset {d.name}: {mode} frames {len(have)} on disk, expected {n} "
                             f"({sorted(set(want) ^ set(have))[:4]})")
        for name in want:
            e = man["frames"].get(name)
            b = (d / name).read_bytes()
            if e is None or hashlib.sha256(b).hexdigest() != e["sha256"]:
                raise SystemExit(f"title asset {d.name}/{name}: not in the manifest or sha256 differs (stale)")
            if tuple(e["size"]) != (W, H):
                raise SystemExit(f"title asset {d.name}/{name}: manifest size {e['size']}, expected {W}x{H}")
    print(f"  title asset {d.name}: {sum(TITLE_FRAMES.values())} frames verified against manifest.json")
''',
     '''def ascent_shot() -> "Shot":
    """v23: the ascent SEQ shot (the one that reads the ascent render)."""
    return next(s for s in SHOTS if s.src == "SEQ" and s.img and s.img.startswith("ascent_"))


def validate_assets() -> None:
    """v22 (R4, Codex) + v23: every pre-rendered asset is checked BEFORE any output is opened, by assets_v23 (the same
    code as title_manifest_v22.py --check and ascent_manifest_v23.py --check):
      title   work/title3d_v22: exact frame names, sha256 per frame, size, AND the recorded renderer + postprocessor
              source hashes (Codex v22: a changed blender/title_v22.py with old PNGs used to pass);
      ascent  work/ascent_blender_v23 (V23_HUD): 192 frames, sha256 + size, geometry.json, blender/ascent3d_v23.py's
              hash, and the display map's shot parameters against SHOTS; then hud_v23 loads the geometry and
              computes the label layout once. No Blender needed."""
    n = assets_v23.check_title(WORK, TITLE_DIR, TITLE_FRAMES, (W, H))
    print(f"  title asset {TITLE_DIR}: {n} frames + sources verified against manifest.json")
    if V23_HUD:
        s = ascent_shot()
        folder = s.img.split("/")[0]
        assets_v23.check_ascent(WORK, folder, s.t0, s.speed, nframes(s), (W, H))
        hud_v23.load_ascent(WORK / folder, int(round(s.t0 * FPS)))
        miss = sum(len(r["missing"]) for r in hud_v23.ASC["report"].values())
        if miss:
            raise SystemExit(f"ascent layout: {miss} label-frames have no clear position (hud_v23.asc_layout)")
        print(f"  ascent asset {folder}: 192 frames + geometry + display map verified; layout clear on every frame")


def rife_cache_check() -> None:
    """v23 preflight: every RIFE cache PNG matches its manifest sha256 (the ramp reads them; RIFE is not needed)."""
    if not RAMP_RIFE or RIFE_REGEN or RIFE_SEED:
        return
    mp = RIFE_CACHE / "manifest.json"
    if not mp.is_file():
        raise SystemExit(f"RIFE cache missing: {mp}")
    for i, e in json.loads(mp.read_text(encoding="utf-8"))["frames"].items():
        p = RIFE_CACHE / f"f{int(i):03d}.png"
        if not p.is_file() or sha256(p.read_bytes()) != e["out"]:
            raise SystemExit(f"RIFE cache: {p.name} missing or not its manifest sha256")
    print(f"  RIFE cache {RIFE_CACHE.name}: files verified against manifest.json")


def preflight(stage: str) -> None:
    """v23 (Codex v22 medium): run at the entrypoint BEFORE any stage writes anything: the manifested assets for the
    stages that read them (title + ascent for comp, the RIFE cache for shots) and the reused audio for mix."""
    if stage in ("all", "comp"):
        validate_assets()
    if stage in ("all", "shots"):
        rife_cache_check()
    if stage in ("all", "mix") and REUSE_AUDIO_FROM is not None:
        reused_audio_check(REUSE_AUDIO_FROM)
'''),
    # ---- 2 + 1: the flash-forward tag and the ascent text (hud_v23)
    ('''        if 0.15 <= t < HOOK_OUT:  # v18: what this is, before the L70 HUD takes the slot at the 1.2 cut
            self.hook(d, t)
''',
     '''        if 0.15 <= t < HOOK_OUT:  # v18: what this is, before the L70 HUD takes the slot at the 1.2 cut
            self.hook(d, t)
        if V23_HUD and self.v22():    # v23: the flash-forward tag (frames 94-201) and the ascent text (524-635)
            fi_ = self.h20.fi
            if FLASH_F[0] <= fi_ < FLASH_F[1] and "countdown" not in self.h20.items:
                self.h20.add("flashtag", a=ease_out((fi_ - FLASH_F[0] + 1) / 4))
            if ASC_F[0] <= fi_ < ASC_F[1]:
                self.h20.add("ascent", fi=fi_)
'''),
    # ---- 4: the end-card AI-assist line, with the date line's alpha (gone before 1891)
    ('''        if 83.9 <= t < 85.5:
            a = ease_out((t - 83.9) / 0.5) * (1 - ease_in_out((t - 85.15) / 0.35))
''',
     '''        if 83.9 <= t < 85.5:
            a = ease_out((t - 83.9) / 0.5) * (1 - ease_in_out((t - 85.15) / 0.35))
            if V23_HUD and self.v22():      # v23: on-screen AI-assist disclosure under the date line
                self.h20.add("endnote", a=a)
'''),
    ('''HOOK_OUT = round(1.2 * FPS) / FPS          # v18: the first L70 frame (29): the countdown HUD takes the slot
''',
     '''HOOK_OUT = round(1.2 * FPS) / FPS          # v18: the first L70 frame (29): the countdown HUD takes the slot
FLASH_F = (int(round(3.9 * FPS)), int(round(8.4 * FPS)))      # v23: the flash-forward inserts, frames 94-201
ASC_F = (int(round(21.8333 * FPS)), int(round(26.5 * FPS)))   # v23: the ascent shot, frames 524-635
CREDITS_F0 = 1891         # v23: first credits frame; an IDR is forced here in the comp and export encodes
IDR_ARGS = ["-force_key_frames", f"expr:eq(n,{CREDITS_F0})", "-forced-idr", "1"]
FRAME_HASHES = os.environ.get("MOONSHOT_FRAME_HASHES", "")    # v23 gate: sha256 per frame before encoding
'''),
    # ---- stage_comp: hud_v23, globe grain, IDR, pre-encode frame hashes
    ('''        hud = hud_v22 if V22_HUD else (hud_v21 if V21_HUD else hud_v20)      # v21, v22''',
     '''        hud = hud_v23 if V23_HUD else (hud_v22 if V22_HUD else (hud_v21 if V21_HUD else hud_v20))   # v21-v23'''),
    ('''            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, pd_ + dx, 0, 1, pd_ + dy), Image.Resampling.BILINEAR))
''',
     '''            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, pd_ + dx, 0, 1, pd_ + dy), Image.Resampling.BILINEAR))
            if V23_HUD and s.img.startswith(hud_v23.ASC_DIR):      # v23: 16 mm-matched grain on the CG globe
                fr = hud_v23.globe_grain(fr, fi)
'''),
    ('''                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast",
                            "-pix_fmt", "yuv420p", str(WORK / "comp.mp4")], stdin=subprocess.PIPE)''',
     '''                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast", *IDR_ARGS,
                            "-pix_fmt", "yuv420p", str(WORK / "comp.mp4")], stdin=subprocess.PIPE)
    hashes: list[str] = []'''),
    ('''        enc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
''',
     '''        out_ = np.clip(f, 0, 255).astype(np.uint8).tobytes()
        if FRAME_HASHES:
            hashes.append(hashlib.sha256(out_).hexdigest())
        enc.stdin.write(out_)
'''),
    ('''    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    print("comp written")''',
     '''    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    if FRAME_HASHES:
        Path(FRAME_HASHES).write_text(json.dumps(hashes), encoding="utf-8")
    print("comp written")'''),
    # ---- 5: verified audio reuse, no silent truncation
    ('''REUSE_AUDIO_FROM = OUT / "moonshot_v21.mp4"   # v22 (R2): no audio change; None = compute the mix as v21


def mux_reused_audio(src: Path) -> None:
    """v22 (R2): the comp + the audio stream of src by STREAM COPY (the AAC packets are v21's, bit for bit); same video
    encode as stage_mix. Nothing in the mix is recomputed."""
    if not src.is_file():
        raise SystemExit(f"REUSE_AUDIO_FROM {src} missing")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"moonshot_v{VERSION}.mp4"
    if dst.exists():
        raise SystemExit(f"{dst} exists; versions are never overwritten")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(WORK / "comp.mp4"), "-i", str(src),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-vf", "setsar=1", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
         "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(dst)])
    print(f"wrote {dst} (audio stream copied from {src.name})")
''',
     '''REUSE_AUDIO_FROM = OUT / "moonshot_v22.mp4"   # v23: v22's AAC stream (= v21's); None = compute the mix as v21
REUSE_AUDIO_MD5 = "b489934da50e9c2ee4acce2f94f712ae"    # v23 (Codex v22 high): the approved stream's packet md5
REUSE_AUDIO_DUR = 87.5                                   # seconds (AAC stream duration, ffprobe)


def audio_md5(path: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"],
                         capture_output=True, text=True)
    return out.stdout.strip().removeprefix("MD5=") if out.returncode == 0 else ""


def reused_audio_check(src: Path) -> None:
    """v23 (Codex v22 high): the reused file is authenticated by its audio stream (packet md5 + duration), not its name."""
    if not src.is_file():
        raise SystemExit(f"REUSE_AUDIO_FROM {src} missing")
    got = audio_md5(src)
    if got != REUSE_AUDIO_MD5:
        raise SystemExit(f"REUSE_AUDIO_FROM {src.name}: audio packet md5 {got or '(none)'}, pinned {REUSE_AUDIO_MD5}")
    dur = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                          "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip()
    if not dur or abs(float(dur) - REUSE_AUDIO_DUR) > 0.001:
        raise SystemExit(f"REUSE_AUDIO_FROM {src.name}: audio duration {dur or '(none)'} s, pinned {REUSE_AUDIO_DUR}")


def mux_reused_audio(src: Path) -> None:
    """v22 (R2) + v23: the comp + the audio stream of src by STREAM COPY; same video encode as stage_mix plus an IDR at
    the first credits frame. v23: the source is verified (md5 + duration) before the destination is opened; the
    export is written to a .part file that must decode to exactly NFRAMES frames and carry the pinned audio, else it
    is deleted and the build fails (no silent -shortest truncation)."""
    reused_audio_check(src)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"moonshot_v{VERSION}.mp4"
    if dst.exists():
        raise SystemExit(f"{dst} exists; versions are never overwritten")
    part = dst.with_name(dst.stem + ".part.mp4")
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(WORK / "comp.mp4"), "-i", str(src),
             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS,
             "-pix_fmt", "yuv420p",
             "-r", str(FPS), "-vf", "setsar=1", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
             "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
             "-c:a", "copy", "-movflags", "+faststart", "-shortest", str(part)])
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", str(part)],
                                 capture_output=True, text=True).stdout.strip() or 0)
        if got != NFRAMES:
            raise SystemExit(f"mux: {part.name} decodes to {got} frames, expected {NFRAMES} (truncated); deleted")
        if audio_md5(part) != REUSE_AUDIO_MD5:
            raise SystemExit(f"mux: {part.name} audio is not the pinned stream; deleted")
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)
    print(f"wrote {dst} (audio stream copied from {src.name}, md5 + {NFRAMES} frames verified)")
'''),
    # ---- 7: preflight at the entrypoint, before any stage writes
    ('''    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    if stage in ("shots", "all"):''',
     '''    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    preflight(stage)          # v23 (Codex v22): every manifested asset + the reused audio, before anything is written
    if stage in ("shots", "all"):'''),
]
s = apply(s, R, "build")

# ============================================================== title_manifest_v22.py --check: the shared validator (6)
t = load(T)
assert "def main()" in t and "--check" in t, "title_manifest_v22.py (v22) expected"
assert "assets_v23" not in t, "v23 already applied to title_manifest_v22.py"
RT = [
    ('''    if "--check" in sys.argv:
        man = json.loads(mp.read_text(encoding="utf-8"))
        bad = [n for n, e in man["frames"].items() if sha(D / n) != e["sha256"]]
        have = sorted(p.name for p in D.glob("*_*.png"))
        extra = sorted(set(have) ^ set(man["frames"]))
        print(f"{len(man['frames'])} frames in manifest; sha mismatches {bad[:4]}; missing/extra {extra[:4]}")
        raise SystemExit(1 if bad or extra else 0)''',
     '''    if "--check" in sys.argv:          # v23 (Codex v22): build.py's own validator, frames AND source hashes
        from assets_v23 import check_title
        n = check_title(W, D.name, FRAMES)
        print(f"{n} frames, sizes and the recorded source hashes verified (assets_v23.check_title, as build.py)")
        raise SystemExit(0)'''),
]
t = apply(t, RT, "title_manifest")
# ============================================================== repo_src/make_repo.py: the v23 modules, no drive paths (10)
M = Path(sys.argv[3]) if len(sys.argv) > 3 else W / "repo_src" / "make_repo.py"
m = load(M)
assert "def sub_paths" in m and '"title_manifest_v22.py"' in m, "make_repo.py (v22) expected"
assert "hud_v23.py" not in m, "v23 already applied to make_repo.py"
RM = [
    ('''"audio_qc2.py", "title_manifest_v22.py", "flashqc2.py", "beatgrid.py"]''',
     '''"audio_qc2.py", "title_manifest_v22.py", "flashqc2.py", "beatgrid.py",
        "hud_v23.py", "assets_v23.py", "ascent_manifest_v23.py"]     # v23'''),
    ('''"title_plate.py", "ascent3d_v5.py", "title_v18.py", "title_post_v18.py", "moon_portrait.py", "title_v22.py"]''',
     '''"title_plate.py", "ascent3d_v5.py", "title_v18.py", "title_post_v18.py", "moon_portrait.py", "title_v22.py",
           "ascent3d_v23.py"]'''),
    ('''    # v21: the RIFE tool folder (build.py's configurable RIFE_EXE default and a comment): relative, not a drive path
''',
     '''    # v23 (Codex v22): craft-tools paths in audio_qc2.py (CRAFT) and the manifest tools (the Blender executable):
    # the CRAFT_TOOLS environment setting, like the whisper / restore calls above
    out, k = re.subn(r'Path\\(r"craft-tools(?P<rest>\\\\[^"]*)?"\\)',
                     lambda m_: ('(Path(os.environ.get("CRAFT_TOOLS", "craft-tools")) / "'
                                 + m_.group("rest").lstrip("\\\\").replace("\\\\", "/") + '")') if m_.group("rest")
                     else 'Path(os.environ.get("CRAFT_TOOLS", "craft-tools"))', out)
    if k and "import os\\n" not in out:
        out = out.replace("from pathlib import Path\\n", "import os\\nfrom pathlib import Path\\n", 1)
    # v21: the RIFE tool folder (build.py's configurable RIFE_EXE default and a comment): relative, not a drive path
'''),
]
m = apply(m, RM, "make_repo")
save(P, s)
save(T, t)
save(M, m)
print(f"v23: build {len(R)} replacements, title_manifest_v22 {len(RT)}, make_repo {len(RM)}. Re-render: shots 23 17 "
      "(ascent); comp 23; mix 23 (v22's audio, verified).")
