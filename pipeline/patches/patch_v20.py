"""v20 CANDIDATE: the authentic-1969-hardware HUD (exports/moonshot/BRIEF_v20_HUD.md) + the v19 panel fixes.
Apply to the v19 source (build.py + score_pd.py, tag v19-final = v19-src):

    py patch_v20.py                      # the real build.py + score_pd.py in work/
    py patch_v20.py BUILD.py SCORE.py    # dry run on copies (hud_v20.py must sit next to BUILD.py)

Design notes, diagnosis, references and fonts: work/hud_v20/DESIGN.md. The drawing lives in the NEW module
work/hud_v20.py; build.py keeps every value computation and hands the values to it (V20_HUD = False restores v19's
drawing exactly). score_pd.py is NOT changed (checked only). Kept exactly: 2,100 frames, the frame-799 map,
DIALOG / CAPTIONS, the Moon beat 799-877 (picture: V20_DISTANCE = False keeps v19's 240,000 card there), the audio,
the 1:02 transition, the landing anchors (white 1349, touchdown 1350).

HUD (logical windows unchanged; REAL times in brackets):
 1  DSKY tl 47.2-52.375 [40.5-45.67]: the LM DSKY's upper panel (2 x 7 annunciator lamps with the LM legends, PROG
    lit amber, steady, 2-frame incandescent rise; EL display with COMP ACTY (busy flicker), PROG / VERB / NOUN plates,
    three signed 5-digit registers and separator bars; slanted 7-segment digits, unlit segments faintly visible, EL
    bloom, +-2.5% flicker, 1-2 frame segment persistence). Content: PROG 63 (P63 was running at the 1202), V05 N09
    keyed (VERB at u 0.25, NOUN 0.42), R1 01202 (u 0.58); R2 / R3 blank. Top-left at 0.9x (576 x 335) on the LM
    window; from the MC cut (frame 1045) right side at 0.8x, bottom y 690 (v19: 760, legend 818) so the legend ends
    y ~792, 100 px clear of the caption box (Gemini: crowding at 40-46). Same fade-in, side switch and fade-out.
 2  Bingo + altitude tl 55.6 / 55.75-62.9 [48.9-56.2]: ONE MOCR console monitor (x 1300-1820, y 90-748: clear of the
    CONTACT insert 624-1296, title safe and the caption box; v19 used two plates 1300-1821 x 102-828). v20b (review):
    type 1.3x (values 107 px, labels 32-34 px, readable at 360p), "LM DESCENT" dropped; from 30.0 s (v19's red
    threshold) the bingo counter is in REVERSE VIDEO (solid phosphor block, dark digits), steady, no blink, normal
    again at contact (v19's white). OCR-A data face, blue-white phosphor, bloom, scanlines, raster power-on (no fade),
    the callout block draws on at 55.75; a new altitude redraws (0.6 -> 1.35 flare -> 1.0, the old value persists two
    frames) where v19 flashed amber for 4 frames. Every value, label and step time from the unchanged code (fuel(),
    descent(), get_at, READOUT_HOLDS: see 6). Removed (no information): the altitude bar (repeats the number), the
    colour change (the monitor is monochrome; "30 seconds" is in the captions).
 3  Stat cards (thrust tl 19.0-22.0, TLI tl 29.79-33.3): flight-plan data blocks, Franklin Gothic condensed legends
    (type-on), an engineering scale rule, the numbers on mechanical drum counters (7 and .5 roll up; 17,400 -> 24,200
    on a carry odometer driven by the same count curve; rest values identical). Exits unchanged.
 4  All v20 graphics get a film pass (gate weave 0.32 px per frame, 0.6 px softening, the footage's halation recipe on
    their highlights) on their own layer, under the captions layer; the comp grain covers both as before.
 5  RIFE (MIT, rife-ncnn-vulkan, model v4.6) replaces the 2-frame blends of the ignition ramp (s11) with flow
    in-betweens at the mapped phase (RAMP_RIFE = False: v19's blends). Same source map, same frame count.
v19 panel fixes (coordinator 2026-10-08):
 6  Caption/speaker: the Houston glasses face moves from 1254-1266 to 1242-1256 (14 fr, taken from the dust shot before
    it), so "Picking up some dust." (EAGLE, from frame 1257) starts on the dust; dust continuous from 1256 (src
    1360.2 + 39/24, push 1.0 -> 1.08 kept over 1217-1284). The 30 FT readout step (READOUT_HOLDS[1]) moves with the cut
    from tl 58.95 (frame 1254, now 2 frames before the cut) to frame 1256 (tl 59.042): still after the "40 feet"
    caption (ends 1254) and before "Picking up some dust." (1257). Values unchanged.
 7  Both new MC faces (1242-1256 glasses, 1312-1322 crew-cut) graded BRF: BR + ~0.5 stop mid lift + contrast 1.06.
 8  Swing arm (215-226): BRS = BR minus the magenta cast + contrast / black point (no revert needed).
 9  Long-lens grey rocket (444-456): SVW = SV warmed toward the s14 / s16 fire-lit shots, contrast 1.12, gamma 0.94.
10  Credits card 1: the music line names the recordings on its own line ("MUSIC: DVOŘÁK, BEETHOVEN · MUSOPEN
    RECORDINGS (PUBLIC DOMAIN)"); the NASA line keeps its own public-domain claim. Four lines centred on 540; card
    length unchanged (this changes frames of the protected credits section on purpose).
Not done: presence +2 dB on "Staging." / "And ignition." (the two-pass loudnorm would shift every sample, incl. the
approved Moon-beat audio); the Blender title rim light.

Re-render chain: py patch_v20.py; py build.py shots 20 9,11,15,31,32,33,35 (RIFE needs the GPU; writes
work/rife_v20/); py build.py comp 20; py build.py mix 20 (audio unchanged; mix re-muxes); then
py flashqc2.py ..\\..\\..\\exports\\moonshot\\versions\\moonshot_v20.mp4 (must PASS).
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
assert "v19b (Codex, R7)" in s, "apply patch_v19 + patch_v19b first (tag v19-final)"
assert "hud_v20" not in s, "v20 already applied"
assert (P.parent / "hud_v20.py").exists(), f"hud_v20.py must sit next to {P.name}"
R = [
    # ---- module + flags
    ('''from PIL import Image, ImageDraw, ImageFilter, ImageFont
''',
     '''from PIL import Image, ImageDraw, ImageFilter, ImageFont

import hud_v20      # v20: the 1969-hardware HUD (DSKY, MOCR monitor, drum-counter stat cards) + its film pass
'''),
    ('''SRC = {
    "SV": INBOX / "video" / "saturnv_enhanced_1080.mp4",
''',
     '''SRC = {
    "SV": INBOX / "video" / "saturnv_enhanced_1080.mp4",
    "SVW": INBOX / "video" / "saturnv_enhanced_1080.mp4",     # v20: SV warmed (the long-lens rocket, 444-456)
    "BRF": INBOX / "video" / "broll25_720.mp4",               # v20: BR faces lifted (1242-1256, 1312-1322)
    "BRS": INBOX / "video" / "broll25_720.mp4",               # v20: BR swing arm, magenta cast removed (215-226)
'''),
    ('''CROP = {
    "SV": "1920:1080:0:0",
''',
     '''CROP = {
    "SV": "1920:1080:0:0",
    "SVW": "1920:1080:0:0",
    "BRF": "1036:583:115:70",
    "BRS": "1036:583:115:70",
'''),
    ('''    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
}''',
     '''    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
    # v20 (v19 panel): the two MC faces read as dark smears at phone size: BR + ~0.5 stop in the mids (0.5 -> 0.62)
    # and a little contrast
    "BRF": ("hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6,"
            "curves=all='0/0 0.1/0.14 0.5/0.62 0.85/0.92 1/1',eq=contrast=1.06"),
    # v20: the swing arm read murky (magenta cast, grey blacks): cast out, contrast, black point
    "BRS": ("hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6,"
            "colorbalance=rs=-0.04:bs=-0.03:rm=-0.10:gm=0.04:bm=-0.06:rh=-0.02:bh=-0.03,"
            "eq=contrast=1.10:saturation=0.85,curves=all='0/0 0.12/0.08 0.5/0.5 1/1'"),
    # v20: the grey long-lens rocket was a 0.5 s cold jump between two fire-lit shots: warmed, firmer
    "SVW": ("eq=saturation=0.88:contrast=1.04,colorbalance=rs=0.05:bs=-0.07:rm=0.08:gm=0.01:bm=-0.09:rh=0.05:bh=-0.06,"
            "eq=contrast=1.12:gamma=0.94:saturation=0.95"),
}'''),
    ('''RAMP_IGNITION = True
''',
     '''RAMP_IGNITION = True
# v20: the ramp's in-between frames (14 of 29) come from RIFE v4.6 flow interpolation instead of a 2-frame blend;
# False = v19's blends. RIFE is MIT (moonshot-tools\\VETTING_v20.md); a RIFE failure raises (no silent fallback).
RAMP_RIFE = True
RIFE_EXE = Path(r"moonshot-tools\\bin\\rife-ncnn-vulkan\\rife-ncnn-vulkan.exe")
RIFE_TMP = WORK / "rife_v20"
'''),
    # ---- shots (v19 panel fixes)
    ('''    Shot(8.9583, 9.40, "BR", 683.30,''', '''    Shot(8.9583, 9.40, "BRS", 683.30,'''),
    ('''    Shot(18.50, 19.00, "SV", 137.2,''', '''    Shot(18.50, 19.00, "SVW", 137.2,'''),
    ('''    Shot(50.70, 52.25, "BR16L", 1360.2, push=(1.0, 1.044), note="16mm: dust (Aldrin's calls); v19: out at frame 1254 (the 52.23 accent, after '40 feet, down 2 1/2' ends 52.16)"),
    Shot(52.25, 52.75, "BR", 1242.6, push=(1.0, 1.02), note="v19: Houston listening, a controller in glasses (BR shot 1241.54-1246.01), 12 fr"),
    Shot(52.75, 53.50, "BR16L", 1362.2417, push=(1.0585, 1.08), note="v19: back on the dust at 'Picking' (52.76); source and push continuous (1360.2 + 49/24)"),''',
     '''    Shot(50.70, 51.75, "BR16L", 1360.2, push=(1.0, 1.0299), note="16mm: dust (Aldrin's calls); v20: out at frame 1242 (v19 1254), push 1.0 -> 1.08 over 1217-1284 as v19"),
    Shot(51.75, 52.3333, "BRF", 1242.6, push=(1.0, 1.02), note="v20 (panel): Houston listening, the controller in glasses, 1242-1256 (14 fr; v19 1254-1266), so Aldrin's 'Picking up some dust.' (caption from 1257) starts on the dust; lifted (BRF)"),
    Shot(52.3333, 53.50, "BR16L", 1361.825, push=(1.0466, 1.08), note="v20: back on the dust from 1256; source and push continuous (1360.2 + 39/24)"),'''),
    ('''    Shot(54.6667, 55.10, "BR", 1246.4,''', '''    Shot(54.6667, 55.10, "BRF", 1246.4,'''),
    # ---- the 30 FT step follows the moved cut (frame 1254 -> 1256); values unchanged
    ('''READOUT_HOLDS = [(57.625, 17.0), (58.95, 21.0), ((1284 + ACT2_DF) / FPS, 25.0)]''',
     '''READOUT_HOLDS = [(57.625, 17.0), ((1256 + ACT2_DF) / FPS, 21.0), ((1284 + ACT2_DF) / FPS, 25.0)]   # v20: 30 FT on the
# 1256 cut back to the dust (v17-v19: tl 58.95 = frame 1254, the "40 feet" caption's end; no caption 1254-1256)'''),
    # ---- RIFE in-betweens
    ('''def render_ramp_shot(s: Shot, path: Path) -> None:
''',
     '''def rife_between(a: np.ndarray, b: np.ndarray, w: float, i: int) -> np.ndarray:
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


def render_ramp_shot(s: Shot, path: Path) -> None:
'''),
    ('''        else:
            fr = (src[k].astype(np.float32) * (1 - w) + src[k + 1].astype(np.float32) * w + 0.5).astype(np.uint8)''',
     '''        elif RAMP_RIFE:      # v20: flow in-between at the mapped phase (v19: the linear blend below)
            fr = rife_between(src[k], src[k + 1], w, i)
        else:
            fr = (src[k].astype(np.float32) * (1 - w) + src[k + 1].astype(np.float32) * w + 0.5).astype(np.uint8)'''),
    ('''          f"{bool((d > 0).all())}; {exact} exact source frames, {n - exact} two-frame blends")''',
     '''          f"{bool((d > 0).all())}; {exact} exact source frames, {n - exact} {'RIFE in-betweens' if RAMP_RIFE else 'two-frame blends'}")'''),
    # ---- HUD flags
    ('''EARTH_LIMB_X = 1040''',
     '''V20_HUD = True          # v20: DSKY / MOCR monitor / stat cards drawn by hud_v20 (False: v19's drawing, unchanged)
V20_DISTANCE = False    # v20: the 240,000 card sits in the protected Moon beat (frames 829-877): kept as v19 unless approved
EARTH_LIMB_X = 1040'''),
    ('''        self.title = sorted((WORK / TITLE_DIR).glob("open_*.png"))''',
     '''        self.h20 = None       # v20: the frame's hud_v20.HudFrame (set by stage_comp)
        self.title = sorted((WORK / TITLE_DIR).glob("open_*.png"))'''),
    ('''    def stat_thrust(self, layer, d, u):
''',
     '''    def stat_thrust(self, layer, d, u):
        if V20_HUD:          # v20: drum-counter data block (hud_v20.render_thrust), same window and exit
            self.h20.add("thrust", u=u)
            return
'''),
    ('''    def stat_speed(self, layer, d, u):
''',
     '''    def stat_speed(self, layer, d, u):
        if V20_HUD:          # v20: the same alpha and count curve (lines below), on a carry odometer
            a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.9) / 0.35))
            vc = 17400 + 6800 * ease_out((u - 0.4) / 1.2)
            self.h20.add("speed", u=u, a=a, vc=vc, val=int(round(vc / 10.0)) * 10)
            return
'''),
    ('''        a = ease_out(u / 0.4)                      # v18m: the scrim fades in with the text (v17: on from the cut)
''',
     '''        a = ease_out(u / 0.4)                      # v18m: the scrim fades in with the text (v17: on from the cut)
        if V20_HUD and V20_DISTANCE:
            self.h20.add("distance", u=u, a=a)
            return
'''),
    ('''        a = min(1.0, u / 0.1) * (1 - ease_in_out((u + 47.2 - DSKY_OUT[0]) / (DSKY_OUT[1] - DSKY_OUT[0])))
''',
     '''        a = min(1.0, u / 0.1) * (1 - ease_in_out((u + 47.2 - DSKY_OUT[0]) / (DSKY_OUT[1] - DSKY_OUT[0])))
        if V20_HUD:          # v20: the real DSKY (hud_v20.render_dsky); same window, side switch and fade
            self.h20.add("dsky", u=u, right=right, a=a)
            return
'''),
    ('''        a = min(1.0, (t - 55.6) / 0.3)      # v9: no fade-out; held over the lamp insert until the white frame
''',
     '''        a = min(1.0, (t - 55.6) / 0.3)      # v9: no fade-out; held over the lamp insert until the white frame
        if V20_HUD:          # v20: the MOCR monitor (hud_v20.render_crt); label as below
            if held:
                label = "CONTACT  ·  102:45:" + f"{int(g):02d}"
            else:
                label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
            self.h20.add("fuel", t=t, rem=rem, held=held, g=g, a=a, label=label.replace("  ·  ", " "))
            return
'''),
    ('''        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
''',
     '''        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
        if V20_HUD:          # v20: the same values on the MOCR monitor (t_step / fresh as below)
            t_step = readout_step_t(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0
            fresh = (not held) and 0.0 <= t - t_step < 4 / 24
            self.h20.add("descent", alt=alt, prev_alt=prev_alt, down=down, fwd=fwd_now, held=held, fresh=fresh,
                         t_step=t_step, a=a)
            return
'''),
    # ---- credits card 1 (panel): the music line names the recordings
    ('''        lines = [("NASA FILM, PHOTOS & MISSION AUDIO  ·  MUSIC: DVOŘÁK, BEETHOVEN  ·  ALL PUBLIC DOMAIN", "body34", WHITE, 62),
                 ("CUT BY AN AI AGENT (CLAUDE CODE)  ·  3D FROM NASA DATA  ·  SOME LAUNCH FILM FROM OTHER FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 474          # v18: three-line block centred on ~540''',
     '''        # v20 (panel): the music line names the recordings (Musopen, PD worldwide: CREDITS.md); the NASA claim keeps
        # its own line. Four lines, first/last centres 447/633 (block centred on 540), widths 1189-1644 px (safe 1728)
        lines = [("NASA FILM, PHOTOS & MISSION AUDIO: PUBLIC DOMAIN", "body34", WHITE, 54),
                 ("MUSIC: DVOŘÁK, BEETHOVEN  ·  MUSOPEN RECORDINGS (PUBLIC DOMAIN)", "body34", WHITE, 62),
                 ("CUT BY AN AI AGENT (CLAUDE CODE)  ·  3D FROM NASA DATA  ·  SOME LAUNCH FILM FROM OTHER FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 447          # v20: four lines (v18-v19: three from 474)'''),
    # ---- comp: the v20 HUD on its own layer + film pass, under the captions layer
    ('''        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        la = np.asarray(layer, np.float32)''',
     '''        gfx.h20 = hud_v20.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw
        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        if gfx.h20 is not None and gfx.h20.items:      # v20: hardware HUD + film pass, under the captions layer
            f = hud_v20.composite(f, gfx.h20)
        la = np.asarray(layer, np.float32)'''),
]
s = apply(s, R, "build")

# ============================================================== score_pd.py: unchanged (v19b expected)
sc = load(S)
assert "v19b" in sc, "score_pd.py: v19b expected"
save(P, s)
print(f"v20: build {len(R)} replacements; score_pd unchanged. Re-render: shots 20 9,11,15,31,32,33,35; comp 20; mix 20.")
