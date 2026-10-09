"""v22 CANDIDATE: one overlay system + the v21 critics' defects + the adopt-if-time grade. Apply to the v21 source
(build.py + score_pd.py, tag v21-src / v21-final):

    py patch_v22.py                      # the real build.py + score_pd.py in work/
    py patch_v22.py BUILD.py SCORE.py    # dry run on copies (hud_v20.py, hud_v21.py, hud_v22.py next to BUILD.py)

Brief: exports/moonshot/BRIEF_v22.md (its REVISION R1-R6 after exports/moonshot/codex_brief_v22_review.md supersedes
the items above it). Critics: exports/moonshot/qc/v21/fable_editor.json (new_problems 1 and 3, remaining_fixes 2-3),
qc/v21/crowd_ftv.json (comment 3, "a skin per scene"); the odometer bug from evidence/effectcraft_trial.

Drawing lives in the NEW module work/hud_v22.py (its docstring lists every change); hud_v20 / hud_v21 are unchanged and
V22_HUD = False draws v21 exactly. build.py keeps every value computation (the count curves, prior-frame shutter
inputs, fuel(), descent(), get_at, READOUT_HOLDS, the LOW / contact thresholds, tl = fi / 24 below frame 799 and
(fi + 161) / 24 from it). Kept exactly: 2,100 frames, the frame-799 map, DIALOG / CAPTIONS, the cut list, the Moon
beat 799-877 (V22_DISTANCE = False: v19's card, bit-identical), the 1:02 transition 1486-1524 (the EARTHRISE label
starts at 1514, inside it, so it stays v21's), the credits 1891-2099, and the AUDIO (R2: v21's AAC stream copied).

 1  Odometer carry (hud_v22.odometer_positions): each wheel carries from the DISPLAYED position of the wheel below
    (v21: raw value; the TLI thousands wheel was half-rolled at 23,950). thrust_wheels() is not a carry chain and is
    unchanged; the dry-run gate checks every displayed frame of the thrust, TLI and (preview) distance rolls.
 2  DSKY over Mission Control: the legend is a header plate on the panel's top edge (y 372-422); the assembly ends at
    796, 96 px above the caption box (v21: legend plate to 850, 42 px).
 3  CONTACT insert: drawn by hud_v22 in the shared housing, 40 px left (x 584-1256): 44 px from the monitor (v21 4).
 4  One overlay system (hud_v22/DESIGN.md): one label face and size scale, one amber, one plate, one housing, one
    film pass. The cold-open countdown / hook header, the archive tag, STAGE SEPARATION and the DAY 5 chapter card
    move from Gfx into the HUD (with the top gradient under them, as before). Not touched: captions (frozen), the
    big count numeral, the EARTHRISE label (protected frames), the end-card date line and the credits (frozen).
 5  Remotion: NOT used. The only remaining old-style card in scope is the DAY 5 card (type-on + rule + two lines); the
    PIL stat-card renderer draws it in the same system with the same quality (the EffectCraft trial found parity with
    PIL for exactly this kind of card), with no cached asset to keep in sync. The EARTHRISE label cannot start after
    1524, so it is out of scope (R5).
 6  The 240,000 card in the drum style: hud_v22.render_distance behind V22_DISTANCE (default False). The director's
    preview is a separate render (exports/moonshot/auditions/v22_distance_card_preview.mp4).
 7  Title bevel: the title frames come from work/title3d_v22 (blender/title_v22.py: stronger, tighter rim + a weak
    cool left fill; bloom by title_post_v18.py, unchanged) with work/title3d_v22/manifest.json. validate_assets()
    runs FIRST in stage_comp (before any output is opened) and fails on a missing manifest, a missing / extra / stale
    frame (sha256); title_layer no longer clamps a short sequence (it raises).
 8  Grade (R6): variant b (deflicker size 9 + hqdn3d 1.2:1.2:3:3) on the LM-window shot at broll 1254 only (new key
    BRW; flicker 1.38 -> 0.52 in evidence/grade_chain/BR_1254_final). 1258.5, 1399, 1206, 1176 unchanged.
 9  Audio (R2): stage_mix muxes v21's AAC stream by copy (REUSE_AUDIO_FROM); no mix is computed. audio_qc2.py (new
    file) measures Whisper recall with windows covering every caption.

Re-render chain (real tree): py patch_v22.py; py title_manifest_v22.py --check; py build.py shots 22 26 (the BRW shot);
py build.py comp 22; py build.py mix 22 (audio copied from moonshot_v21.mp4); py flashqc2.py
..\\..\\..\\exports\\moonshot\\versions\\moonshot_v22.mp4 (must PASS).
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


s = load(P)
assert "import hud_v21" in s and "V21_HUD = True" in s and "rife_cache_v21" in s, "apply patch_v21 first (tag v21-src)"
assert "hud_v22" not in s, "v22 already applied"
for mod in ("hud_v20.py", "hud_v21.py", "hud_v22.py"):
    assert (P.parent / mod).exists(), f"{mod} must sit next to {P.name}"
R = [
    # ---- module + flags
    ('''import hud_v21      # v21: the same HUD legible at 360p (bigger CRT numerals + tube, no redraw ghost, DSKY 1.2x, drums)
''',
     '''import hud_v21      # v21: the same HUD legible at 360p (bigger CRT numerals + tube, no redraw ghost, DSKY 1.2x, drums)
import hud_v22      # v22: one overlay system (labels, plates, housings, one film pass), odometer carry fix, DSKY header
'''),
    ('''V21_HUD = True          # v21: draw with hud_v21 (phone-size legibility, no CRT ghost); False: hud_v20 exactly (v20)
''',
     '''V21_HUD = True          # v21: draw with hud_v21 (phone-size legibility, no CRT ghost); False: hud_v20 exactly (v20)
V22_HUD = True          # v22: draw with hud_v22 (one overlay system, carry fix, DSKY header, CONTACT in the HUD); False: v21
V22_DISTANCE = False    # v22: the drum-style 240,000 card (hud_v22). True changes the protected Moon beat (frames 830-877):
#                         only for the director's preview (auditions/v22_distance_card_preview.mp4) unless he approves
'''),
    # ---- title: new renders + manifest validation, no silent clamp
    ('''TITLE_DIR = "title3d_v18"   # v18: matte brushed metal, fire-lit edges, bloom (blender/title_v18.py); v3-v17 "title3d_blender" (steel)
''',
     '''TITLE_DIR = "title3d_v22"   # v22: title_v22.py (stronger rim + weak left fill: the bevel reads); v18-v21 "title3d_v18"
TITLE_FRAMES = {"open": 104, "end": 56}     # v22 (R4): exact sequence lengths the manifest must hold


def validate_assets() -> None:
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


def title_idx(frames: list, dt: float) -> int:
    """v22 (R4): the title frame index for dt seconds into its window; raises instead of clamping a short sequence."""
    idx = int(round(dt * FPS))
    if not 0 <= idx < len(frames):
        raise SystemExit(f"title: frame index {idx} outside the {len(frames)}-frame sequence")
    return idx
'''),
    ('''        idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)''',
     '''        idx = title_idx(gfx.title, t - 13.0)          # v22: no clamp'''),
    ('''        idx = min(int(round((t - 83.4) * FPS)), len(gfx.title_end) - 1)''',
     '''        idx = title_idx(gfx.title_end, t - 83.4)      # v22: no clamp'''),
    ('''def stage_comp() -> None:
    run(["ffmpeg",''',
     '''def stage_comp() -> None:
    validate_assets()            # v22 (R4): before any output is opened
    run(["ffmpeg",'''),
    # ---- Gfx: route the moved elements to the HUD
    ('''        self.title_end = sorted((WORK / TITLE_DIR).glob("end_*.png"))
''',
     '''        self.title_end = sorted((WORK / TITLE_DIR).glob("end_*.png"))

    def v22(self) -> bool:
        """v22: draw this element with hud_v22 (one system, one film pass) instead of on the graphics layer."""
        return V22_HUD and self.h20 is not None
'''),
    ('''        if 0.0 <= t < 13.0 or 44.0 <= t < 47.0:
            top = Image.new("RGBA", (W, 240), (0, 0, 0, 0))''',
     '''        if (0.0 <= t < 13.0 or 44.0 <= t < 47.0) and self.v22():   # v22: the gradient goes under the HUD labels
            self.h20.add("topgrad")
        elif 0.0 <= t < 13.0 or 44.0 <= t < 47.0:
            top = Image.new("RGBA", (W, 240), (0, 0, 0, 0))'''),
    ('''        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))     # v18: blended (was d.rectangle)
        site = 0.0 if 3.9 <= t < 8.4 else 1.0
''',
     '''        site = 0.0 if 3.9 <= t < 8.4 else 1.0
        if self.v22():           # v22: the system's faces through the HUD film pass; the count numeral stays here
            self.h20.add("countdown", a=a, site=site, s=s)
            if layer is not None:
                self.countdown_numeral(layer, t, n, n_ts)
            return
        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))     # v18: blended (was d.rectangle)
'''),
    ('''        a = ease_out((t - 0.15) / 0.3)
        x, y = 112, 70
''',
     '''        a = ease_out((t - 0.15) / 0.3)
        if self.v22():
            self.h20.add("hook", a=a)
            return
        x, y = 112, 70
'''),
    ('''        if a <= 0:
            return
        s_, f = "ARCHIVE: OTHER SATURN V FLIGHT", "bebas34"
''',
     '''        if a <= 0:
            return
        if self.v22():
            self.h20.add("archive", a=a)
            return
        s_, f = "ARCHIVE: OTHER SATURN V FLIGHT", "bebas34"
'''),
    ('''        a = ease_out(u / 0.12) * (1 - ease_in_out((u - (dur - 0.14)) / 0.14))
''',
     '''        a = ease_out(u / 0.12) * (1 - ease_in_out((u - (dur - 0.14)) / 0.14))
        if self.v22():
            self.h20.add("stage", a=a)
            return
'''),
    ('''        a = ease_out(u / 0.5) * (1 - ease_in_out((u - 3.2) / 0.5))
''',
     '''        a = ease_out(u / 0.5) * (1 - ease_in_out((u - 3.2) / 0.5))
        if self.v22():
            self.h20.add("chapter", u=u, a=a)
            return
'''),
    ('''        on = u >= 0.12 and not (0.25 <= u < 0.33)
        cx, cy = W / 2, H / 2 - 40
''',
     '''        if self.v22():           # v22: hud_v22.render_contact (shared housing, 40 px left, same lamp timing)
            self.h20.add("contact", u=u)
            return
        on = u >= 0.12 and not (0.25 <= u < 0.33)
        cx, cy = W / 2, H / 2 - 40
'''),
    ('''        if V20_HUD and V20_DISTANCE:''',
     '''        if V20_HUD and (V20_DISTANCE or V22_DISTANCE):     # v22: V22_DISTANCE (default False) = hud_v22's drum card'''),
    ('''        hud = hud_v21 if V21_HUD else hud_v20      # v21''',
     '''        hud = hud_v22 if V22_HUD else (hud_v21 if V21_HUD else hud_v20)      # v21, v22'''),
    # ---- grade b on the 1254 LM-window shot only (R6)
    ('''    "BRS": INBOX / "video" / "broll25_720.mp4",               # v20: BR swing arm, magenta cast removed (215-226)
''',
     '''    "BRS": INBOX / "video" / "broll25_720.mp4",               # v20: BR swing arm, magenta cast removed (215-226)
    "BRW": INBOX / "video" / "broll25_720.mp4",               # v22: BR LM window at 1254, deflickered (R6 grade b)
'''),
    ('''    "BRS": "1036:583:115:70",
''',
     '''    "BRS": "1036:583:115:70",
    "BRW": "1036:583:115:70",
'''),
    ('''    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
''',
     '''    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
    # v22 (R6, evidence/grade_chain/BR_1254_final variant b): the LM-window shot flickers (frame-to-frame mean-luma
    # std 1.38 with BR's chain); deflicker size 9 + a milder hqdn3d -> 0.52, noise ratio 1.12 (BR 1.15). That shot only.
    "BRW": "deflicker=size=9:mode=am,hqdn3d=1.2:1.2:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
'''),
    ('''    Shot(40.30, 42.30, "BR", 1254.0, push=(1.0, 1.06), note="descent, LM window"),''',
     '''    Shot(40.30, 42.30, "BRW", 1254.0, push=(1.0, 1.06), note="descent, LM window; v22: grade b (BRW, deflicker)"),'''),
    # ---- audio: v21's AAC by stream copy (R2)
    ('''def stage_mix() -> None:
    n = int(TOTAL * SR)
''',
     '''REUSE_AUDIO_FROM = OUT / "moonshot_v21.mp4"   # v22 (R2): no audio change; None = compute the mix as v21


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


def stage_mix() -> None:
    if REUSE_AUDIO_FROM is not None:      # v22 (R2)
        mux_reused_audio(REUSE_AUDIO_FROM)
        return
    n = int(TOTAL * SR)
'''),
]
s = apply(s, R, "build")

# ============================================================== score_pd.py: unchanged (v19b expected)
sc = load(S)
assert "v19b" in sc, "score_pd.py: v19b expected"
save(P, s)
print(f"v22: build {len(R)} replacements; score_pd unchanged. Re-render: shots 22 26 (BRW); comp 22; mix 22 "
      "(audio copied from v21).")
