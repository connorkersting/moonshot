"""MOONSHOT build pipeline.

Stages (run in order, each can be re-run on its own):
    py build.py shots   conform every shot to 1920x1080/24p segments (ffmpeg; stills rendered with Ken Burns)
    py build.py dialog  assemble the mission-dialogue stem from the edit decision list
    py build.py comp    composite: base edit + push-ins + graphics + captions + grade/grain -> video only
    py build.py mix     duck music under dialogue, sum stems, normalize, mux -> versions/moonshot_vN.mp4
    py build.py all     everything

Edit decisions live in the SHOTS / DIALOG / CAPTIONS tables below. Times are timeline seconds.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import hud_v20      # v20: the 1969-hardware HUD (DSKY, MOCR monitor, drum-counter stat cards) + its film pass
import hud_v21      # v21: the same HUD legible at 360p (bigger CRT numerals + tube, no redraw ghost, DSKY 1.2x, drums)
import hud_v22      # v22: one overlay system (labels, plates, housings, one film pass), odometer carry fix, DSKY header
import hud_v23      # v23: ascent text in the system (no baked labels), flash-forward tag, TAG-size disclosures, end note
import polish_v24   # v24: Fable's v23 notes on hud_v23 (label gap 28 px, 'AVERAGE DISTANCE, ROUNDED', cream end note)
import assets_v23   # v23: the one validator for manifested assets (title + ascent), shared with the manifest tools
import epi_v26      # v26: the epilogue stills from the original film scans (work/stills_v26, manifested)
V26_SCANS = True        # v26: frames 1702-1743 (5903 visor) and 1841-1890 (6642 end plate) from the scans; False: v23
V26_ENDPLATE = False    # v26: 1841-1890 from the 6642 scan (detail at parity, fewer clipped highlights); False: v23. Lead (v24 build): OFF, no visible gain = minimum change
V26_BOOTPRINT = False   # v26: 1744-1840 from the 5878 scan too; off: no more optical detail than the library JPEG

ROOT = CRAFTWORK
INBOX = ROOT / "inbox" / "moonshot"
WORK = INBOX / "work"
SEG = WORK / "seg"
AUD = WORK / "audio"
OUT = ROOT / "exports" / "moonshot" / "versions"
FONTS = ROOT / "fonts"
W, H, FPS = 1920, 1080, 24
TOTAL = 87.5            # v18: card 1 3.45 s + card 2 4.45 s + 0.75 s black (v17: 87.0; v8-v16: 81.8; v7: 88.5)
NFRAMES = int(round(TOTAL * FPS))
# v8 time model: SHOTS / DIALOG / mix are REAL time; CAPTIONS, Gfx.draw, title_layer, GLITCH_WINDOWS and the comp's
# flashes are LOGICAL (v7) time. The comp maps real -> logical: from the Moon cut on, logical = real + ACT2_D.
ACT2_T0 = 33.3                                    # real time of the cut to the Moon (v7: 40.0)
ACT2_D = 6.7                                      # seconds removed from act 2
ACT2_F0 = int(round(ACT2_T0 * FPS))               # 799: first Moon frame in v8
ACT2_DF = int(round(40.0 * FPS)) - ACT2_F0        # 161: the v7 Moon cut was frame 960
SR = 48000
VERSION = int(sys.argv[2]) if len(sys.argv) > 2 else 1

SRC = {
    "SV": INBOX / "video" / "saturnv_enhanced_1080.mp4",
    "SVW": INBOX / "video" / "saturnv_enhanced_1080.mp4",     # v20: SV warmed (the long-lens rocket, 444-456)
    "BRF": INBOX / "video" / "broll25_720.mp4",               # v20: BR faces lifted (1242-1256, 1312-1322)
    "BRS": INBOX / "video" / "broll25_720.mp4",               # v20: BR swing arm, magenta cast removed (215-226)
    "BRW": INBOX / "video" / "broll25_720.mp4",               # v22: BR LM window at 1254, deflickered (R6 grade b)
    "L70": INBOX / "video" / "launch_70mm.mp4",
    "BR": INBOX / "video" / "broll25_720.mp4",
    "BR16": INBOX / "video" / "broll25_720.mp4",
    "BR16H": INBOX / "video" / "broll25_720.mp4",
    "BR16L": INBOX / "video" / "broll25_720.mp4",
    "BRD": INBOX / "video" / "broll25_720.mp4",
}
# Active-picture crops (w:h:x:y) that give 16:9 from each source.
CROP = {
    "SV": "1920:1080:0:0",
    "SVW": "1920:1080:0:0",
    "BRF": "1036:583:115:70",
    "BRS": "1036:583:115:70",
    "BRW": "1036:583:115:70",
    "BR": "1036:583:115:70",
    "BR16": "1036:583:115:70",
    "BR16H": "1036:583:115:70",
    "BR16L": "1036:583:115:70",
    "BRD": "1036:583:115:70",
}
GRADE = {
    "BR16": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.3/0.46 0.65/0.85 1/1',eq=saturation=0.85,unsharp=5:5:0.7",
    "BRD": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.06:saturation=0.62,colorbalance=rm=-0.03:gm=0.02:bm=-0.07:rh=-0.02:bh=-0.05,unsharp=5:5:0.6",
    # v11: BR16H (touchdown only) mids 0.35/0.36 -> 0.41, 0.62/0.80 -> 0.85 (curve-only contrast; blacks unchanged)
    "BR16H": "hqdn3d=3:3:6:6,curves=all='0/0 0.12/0.02 0.35/0.41 0.62/0.85 1/1',eq=saturation=0.8,unsharp=5:5:1.0",
    # v11: BR16L = BR16 for the 48.3-53.5 landing shots with a firmer upper half: 0.35 -> 0.565 (BR16 ~0.52 there, via
    # 0.3/0.46), 0.65/0.85 -> 0.88; highlights reach ~225 instead of ~218, no clipping after the comp LUT + halation
    "BR16L": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.35/0.565 0.65/0.88 1/1',eq=saturation=0.85,unsharp=5:5:0.7",
    "SV": "eq=saturation=0.88:contrast=1.04",
    "L70": "eq=contrast=1.12:saturation=1.05:gamma=0.97,colorbalance=rs=0.05:gs=0.0:bs=-0.06:rh=0.04:bh=-0.04,curves=g='0/0 0.5/0.465 1/0.97'",   # v15: green pulled (70mm pad)
    # v15: the Blender Moon (s20) toward the 16mm around it: black lifted to the 16mm teal-green black, faint screen glow
    # (halation-like limb bloom), 0.5x downscale with luma grain at the low res (clumped), back up (softness)
    # v16b: + 35% desaturation and contrast 0.94 (softer terminator) first; mid-tones pulled to the 16mm green-grey of
    # s21 / s22 (Cb -3..-5, Cr -1..-3, G-(R+B)/2 +7 measured on the v15 segments)
    "CG16": ("eq=saturation=0.65:contrast=0.94,"
             "curves=r='0/0.008 0.5/0.495 1/1':g='0/0.032 0.5/0.507 1/1':b='0/0.022 0.5/0.486 1/1',split[cga][cgb];[cgb]gblur=sigma=18[cgg];"
             "[cga][cgg]blend=all_mode=screen:all_opacity=0.06,scale=960:540:flags=bicubic,format=yuv444p,"
             "noise=c0s=12:c0f=t+u,scale=1920:1080:flags=bicubic"),
    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
    # v22 (R6, evidence/grade_chain/BR_1254_final variant b): the LM-window shot flickers (frame-to-frame mean-luma
    # std 1.38 with BR's chain); deflicker size 9 + a milder hqdn3d -> 0.52, noise ratio 1.12 (BR 1.15). That shot only.
    "BRW": "deflicker=size=9:mode=am,hqdn3d=1.2:1.2:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
    # v20 (v19 panel): the two MC faces read as dark smears at phone size: BR + ~0.5 stop in the mids (0.5 -> 0.62)
    # and a little contrast
    "BRF": ("hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6,"
            "curves=all='0/0 0.1/0.14 0.5/0.62 0.85/0.92 1/1',eq=contrast=1.06"),
    # v20: the swing arm read murky (magenta cast, grey blacks): cast out, contrast, black point
    "BRS": ("hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6,"
            "colorbalance=rs=-0.04:bs=-0.03:rm=-0.10:gm=0.04:bm=-0.06:rh=-0.02:bh=-0.03,"
            "eq=contrast=1.10:saturation=0.85,curves=all='0/0 0.12/0.08 0.5/0.5 1/1',"
            # v21 (Fable: still magenta): the cast is the purple mid-shadow plate; hue-selective, the rest unchanged
            "selectivecolor=correction_method=absolute:magentas='0.2 -1 0.1 0':blues='0 -0.4 0.2 0'"),
    # v20: the grey long-lens rocket was a 0.5 s cold jump between two fire-lit shots: warmed, firmer
    "SVW": ("eq=saturation=0.88:contrast=1.04,colorbalance=rs=0.05:bs=-0.07:rm=0.08:gm=0.01:bm=-0.09:rh=0.05:bh=-0.06,"
            "eq=contrast=1.12:gamma=0.94:saturation=1.045,colortemperature=temperature=6200"),   # v21: +10 % sat, ~+300 K
}


@dataclass
class Shot:
    t0: float
    t1: float
    src: str                      # SV | L70 | BR | STILL | BLACK
    src_in: float = 0.0           # source seconds (video) or image filename (stills via `img`)
    speed: float = 1.0
    crop: str | None = None       # override crop w:h:x:y in source px
    img: str | None = None        # still filename in inbox/moonshot/stills
    kb: tuple = ((0.5, 0.5, 1.0), (0.5, 0.5, 1.1))  # stills: (cx, cy, zoom) start -> end, cx/cy in 0..1 of image
    push: tuple = (1.0, 1.0)      # video shots: zoom start -> end applied in comp
    darken: float = 0.0           # 0..1 extra darkening (for graphics backplates)
    black_lead: int = 0           # frames of black at the head (strobe cuts)
    note: str = ""
    grade: str | None = None      # v15: SEQ only: a GRADE key appended to the render (CG -> 16mm match)
    ramp: tuple | None = None     # v19 (R4): ((output frame, speed), ...) piecewise-linear speed; None = constant `speed`
    bg_darken: float = 0.0        # v19 (R5): darkens the PLATE before the title is laid in (`darken` acts after it)


# v19 (R4): the one speed-ramp experiment, the ignition fireball (s11). Knots (output frame, speed): real time on the
# drop, eases to 0.44x by the 10.98 accent (f10), holds, snaps back to 1.0x on the 11.38 accent (f19 = frame 273).
# RAMP_IGNITION = False: constant-speed fallback (v18's 1.0x render of the same source in-point).
RAMP_IGNITION = True
# v20: the ramp's in-between frames (14 of 29) come from RIFE v4.6 flow interpolation instead of a 2-frame blend;
# False = v19's blends. RIFE is MIT (moonshot-tools\VETTING_v20.md); a RIFE failure raises (no silent fallback).
RAMP_RIFE = True
# v21 (Codex v20 review): the in-betweens are a TRACKED asset (work/rife_cache_v21: f###.png, input thumbnails,
# manifest.json with source frame, phase and sha256 of inputs and output). A normal build reads and verifies it (no
# RIFE, GPU or external tooling). MOONSHOT_RIFE_REGEN=1 regenerates (preflight before any output is opened, unique temp
# dir removed in finally); MOONSHOT_RIFE_SEED=<dir> fills the cache from an earlier run's f###_0/_1/_rife.png.
RIFE_EXE = Path(os.environ.get("MOONSHOT_RIFE_EXE", r"moonshot-tools\bin\rife-ncnn-vulkan\rife-ncnn-vulkan.exe"))
RIFE_MODEL = Path(os.environ.get("MOONSHOT_RIFE_MODEL", str(RIFE_EXE.parent / "rife-v4.6")))
RIFE_CACHE = Path(os.environ.get("MOONSHOT_RIFE_CACHE", str(WORK / "rife_cache_v21")))
RIFE_REGEN = os.environ.get("MOONSHOT_RIFE_REGEN", "") == "1"
RIFE_SEED = os.environ.get("MOONSHOT_RIFE_SEED", "")
IGNITION_RAMP = ((0, 1.0), (3, 1.0), (10, 0.44), (19, 0.44), (19, 1.0), (29, 1.0))   # 3 + 3.5 x 1.44 + 9 x 0.44 = 12.0 source frames at f19: the real-time tail lands on whole source frames (no blend)

import hud_v25      # v25: the hero beat's route + schematic label, in the hud_v23 system (frames 715-798 only)
import assets_v25   # v25: the hero_v25 asset validator (shared with hero_manifest_v25.py --check)
V25_HERO = True         # v25: frames 715-798 = one Blender Earth-to-Moon move (hero_v25) + hud_v25; False: v23 exactly
V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly
V24_POLISH = True       # v24: polish_v24.apply() patches hud_v23 (Fable v23 notes b, c, d); False: v23's overlays exactly
if V24_POLISH:
    polish_v24.apply()
V26_POLISH2 = True      # v26: polish_v26.apply() (Fable v24 notes: 'AVG DISTANCE, ROUNDED' inside its rule, medium-weight
#                         end-card disclosure under the date line); False: v24's overlays exactly
if V24_POLISH and V26_POLISH2:
    import polish_v26
    polish_v26.apply()
V26_DISCLOSURE = True   # v26: polish_v26b.apply() (director: disclosures smaller and quieter): every disclosure as one
#                         footnote style (Franklin medium 40, cream 75 %, no plate); False: the previous overlays exactly
if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE:
    import polish_v26b
    polish_v26b.apply()
V27_FIXES = True        # v27: polish_v27 (Fable v26 review): local scrim behind ARCHIVE / TIME-COMPRESSED on bright frames,
#                         no caption on the end plate (1812-1890), ascent note 'NOT TO SCALE (6X) · NASA FIGURES'; False: v26
if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE and V27_FIXES:
    import polish_v27
    polish_v27.apply()
V26_OUTRO = True        # v26 (director): end plate from 75.50 s, the title lands on the 76.7 boom and holds still
OUTRO_T0 = 75.50 if V26_OUTRO else 76.70     # real s: the bootprint -> end-plate cut
OUTRO_SETTLE = 4 if V26_OUTRO else 0         # the end title's 56-frame settle plays this many times faster, then holds
SHOTS: list[Shot] = [
    # COLD OPEN (v8): opens on motion (firing room), the pad, first flames, then 1-s flash-forwards on the counts
    Shot(0.00, 1.20, "BR", 667.0, push=(1.0, 1.08), note="firing room wide (people moving): v8 opens on motion"),
    Shot(1.20, 2.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.10), note="Apollo 11 on the pad, 70mm, push"),
    Shot(2.20, 3.90, "L70", 15.6, speed=0.5, crop="900:506:400:1100", push=(1.0, 1.08), note="Apollo 11 70mm: first flames at the base (ignition sequence starts)"),
    Shot(3.90, 4.80, "SEQ", 70.0, img="moon_blender/moon_%04d.png", note="flash-forward: the Moon (Blender render, frames 70+)"),
    Shot(4.80, 5.60, "STILL", img="as11-44-6581.jpg", kb=((0.5, 0.5, 1.5), (0.5, 0.5, 1.7)), note="flash-forward: Eagle"),
    Shot(5.60, 6.60, "BR16", 1361.0, push=(1.0, 1.08), note="flash-forward: dust at touchdown"),
    Shot(6.60, 7.40, "STILL", img="as11-40-5903.jpg", kb=((0.51, 0.11, 3.4), (0.51, 0.10, 4.0)), note="flash-forward: the visor"),
    Shot(7.40, 8.40, "STILL", img="as11-44-6550.jpg", kb=((0.5, 0.44, 1.6), (0.5, 0.43, 1.75)), note="flash-forward: Earthrise"),
    # v19: count "2" split on the quarter pulse (cut 215 = 8.958, the 8.945 accent): firing room, then the swing arm
    Shot(8.40, 8.9583, "BR", 694.0, push=(1.03, 1.0), note="v19: back to the firing room, 13 fr (v18: 24 fr)"),
    Shot(8.9583, 9.40, "BRS", 683.30, push=(1.0, 1.02), note="v19: umbilical swing arm retracting (BR shot 683.15-684.15), 11 fr; count 1 holds after it"),
    Shot(9.40, 10.60, "BR", 691.78, speed=0.66, push=(1.0, 1.10), note="engine bells (0.8 s shot, slowed)"),
    # BEAT DROP
    Shot(10.60, 11.80, "SV", 34.2, push=(1.12, 1.0), ramp=IGNITION_RAMP, note="ignition fireball, high-speed camera; v19: speed ramp 1.0 -> 0.44 -> snap 1.0 at frame 273 (src 34.20-35.12, shot 33.17-35.71)"),
    Shot(11.80, 13.00, "L70", 16.6, crop="1300:731:256:700", push=(1.0, 1.06), note="Apollo 11 70mm: flames at the base, wide"),
    Shot(13.00, 17.6667, "L70", 18.0, speed=0.5, crop="1220:686:520:980", push=(1.0, 1.08), darken=0.25, note="smoke under the title (v9: recrop, no pole through the M, clear of the gate corner); v19: out at frame 424 (the 17.676 accent; was 422)"),
    Shot(17.6667, 18.50, "SV", 100.0, push=(1.0, 1.03), note="rocket climbs past the tower; v19: 20 fr, out on the 18.506 accent"),
    Shot(18.50, 19.00, "SVW", 137.2, push=(1.0, 1.0), note="v19: long lens, the rocket clear of the pad in a grey sky (SV shot 136.75-140.83), 12 fr"),
    # ACT 2 (v8: 19.0-33.3, was 19.0-40.0): thrust stat, 3D ascent, staging, interstage, TLI speed
    Shot(19.00, 21.8333, "SV", 70.0, push=(1.0, 1.057), darken=0.1, note="F-1 engine bells (stat 1); v19: out at frame 524 (the 21.844 accent; was 528)"),
    # v18: ascent_blender_v5 (blender/ascent3d_v5.py): event labels fade before the frame edge (v4 + asc_label_clean)
    # v23: ascent_blender_v23 (blender/ascent3d_v23.py): v5's scene, NO baked text; hud_v23 draws the text
    Shot(21.8333, 26.50, "SEQ", 1.0, speed=1.70, img=("ascent_blender_v23/asc_%04d.png" if V23_HUD else "ascent_blender_v5/asc_%04d.png"), note="Blender: 3D ascent over Blue Marble Earth, PAO-called values (v19: 112 fr x 1.70 = 190.4 of 192; v18 108 fr x 1.77)"),
    Shot(26.50, 27.25, "BRD", 940.75, push=(1.0, 1.06), note="staging: the S-IC plume against blue sky (STAGE SEPARATION label); v15: 0.75 s (was 940.0 for 1.5 s), src 940.75-941.5: plume rises from bottom-left to mid-left, upper right empty"),
    # v14: the middle re-cut for pace (5 shots -> 8 in 26.5-40.3; every graphics-keyed cut kept: 28.0, 29.8, 33.3, 37.3)
    # v18 (staging white-out lost 3 blind A/B rounds): split at the 28.0 impact (frame 672). The lit ring before the white
    # plateau (src 988.0-988.9, luma 169-178), then the ring breaking away from the flash; v17 kept 0.52 s of white-out on 28.0
    Shot(27.25, 28.00, "BRD", 987.20, push=(1.0, 1.04), note="v18: S-II interstage ring lit by the ignition glow, src 987.20-987.95 at 1.0x (18 frames, before the white-out)"),
    Shot(28.00, 29.80, "BRD", 989.20, speed=1.18, push=(1.0, 1.08), note="v18: cut on the 28.0 impact to the ring separating from the flash, src 989.20-991.31 at 1.18x, tumbles away over Earth"),
    # v17 s17 (replaced):
    # Shot(27.25, 29.80, "BRD", 987.40, speed=(988.55 - 987.40) / 0.75, push=(1.0, 1.10), note="v16b: src 987.40 at 1.533x: the ring reads 0.4 s (src 987.40-988.05), white-out 0.52 s, luma peak 988.55 still on 28.0, out 991.31; v14: S-II interstage ring; v15: in at 27.25 on src 987.80 (lit ring, ignition glow building), white-out src 988.3-988.55 peaks on the 28.0 impact (map from 28.0 = v14), the ring emerges (src 989.0 = 28.45) and tumbles away over Earth"),
    *((  # v25: V25_HERO replaces the two Earth plates with the hero SEQ shot (False: v23's two shots verbatim)
    Shot(29.80, 33.30, "SEQ", 1.0, img="hero_v25/hv_%04d.png", grade="CG16", note="v25: ONE Earth-to-Moon move, Blender schematic not to scale (blender/hero_v25.py: Blue Marble + clouds, the portrait's Moon and sun), route launches on the Dvorak hit 31.02 (frame 744), settles on the portrait camera for the cut at 799; stars by alpha in the asset, overlay hud_v25"),
    ) if V25_HERO else (
    Shot(29.80, 31.00, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.60)), note="Apollo 11 Earth, pulling away fast (stat: TLI speed counts here); v14: 1.2 s, out on the Dvorak hit 31.02"),
    Shot(31.00, 33.30, "BR", 1113.25, push=(1.12, 1.0), darken=0.15, note="v14: 16mm, the whole Earth from the spacecraft, handheld drift, receding (24,200 MPH holds; Earth clear of the card)"),
    )),
    # LUNAR TRANSITION
    Shot(33.30, 36.60, "SEQ", speed=1.0, img="moon_portrait_v18/mp_%04d.png", grade="CG16", note="v18m (Connor): still 4K Blender Moon portrait (NASA CGI Moon Kit), locked off 33.3-34.0 while the Dvorak decays, ease-in drift 1.12 -> 1.18 from the Egmont entry (moon_beat_frames.py) + star layer + CG16; replaces v14-v17's 1.7x approach and the Eagle-undocked shot (35.58-36.6)"),
    Shot(36.60, 38.20, "BR", 1176.0, push=(1.0, 1.10), note="v16b: v14's lunar limb back (blind A/B preferred v14's limb + terrain pair), black sky top-left under the DAY 5 card (src 1176.0-1177.6, no cut in 1174-1179)"),
    # ACT 3: descent
    Shot(38.20, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v16b: terrain from the new Egmont phrase (~38.15), 2.1 s: 16mm low oblique horizon, black sky top third under the DAY 5 chapter card (take 1205.77-1214)"),
    Shot(40.30, 42.30, "BRW", 1254.0, push=(1.0, 1.06), note="descent, LM window; v22: grade b (BRW, deflicker)"),
    Shot(42.30, 43.5417, "BR", 1258.5, push=(1.0, 1.062), note="descent, LM window (Eagle: 1202); v19: out at frame 1045 (was 1054)"),
    Shot(43.5417, 46.10, "BR", 1250.625, push=(1.0, 1.07), note="Mission Control (Eagle asks for a reading); v19: in at frame 1045 on the Allegro's re-entry after the general pause (43.526), src 1250.625 (group shot from 1250.38), so the source still cuts back to the LM window at frame 1096 (real 45.667)"),
    Shot(46.10, 48.30, "BR", 1248.55, speed=0.85, push=(1.0, 1.05), note="controller points: we're go (Houston)"),
    Shot(48.30, 50.70, "BR16L", 1345.5, push=(1.0, 1.06), note="16mm descent, final approach"),
    Shot(50.70, 51.75, "BR16L", 1360.2, push=(1.0, 1.0299), note="16mm: dust (Aldrin's calls); v20: out at frame 1242 (v19 1254), push 1.0 -> 1.08 over 1217-1284 as v19"),
    Shot(51.75, 52.3333, "BRF", 1242.6, push=(1.0, 1.02), note="v20 (panel): Houston listening, the controller in glasses, 1242-1256 (14 fr; v19 1254-1266), so Aldrin's 'Picking up some dust.' (caption from 1257) starts on the dust; lifted (BRF)"),
    Shot(52.3333, 53.50, "BR16L", 1361.825, push=(1.0466, 1.08), note="v20: back on the dust from 1256; source and push continuous (1360.2 + 39/24)"),
    Shot(53.50, 54.6667, "BR", 1237.5, push=(1.0, 1.04), note="Mission Control consoles, tense (Houston: 30 seconds); v19: 28 fr, out on the 54.654 accent after the line"),
    Shot(54.6667, 55.10, "BRF", 1246.4, push=(1.0, 1.02), note="v19: a crew-cut controller looking down (BR shot 1246.01-1248.45), 10 fr, into the CONTACT insert"),
    Shot(55.10, 56.20, "INSERT", note="CONTACT LIGHT lamp insert (graphic)"),
    Shot(56.20, 56.26, "WHITE"),
    Shot(56.26, 59.70, "BR16H", 1399.0, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed (v12: out at 59.70, 0.70 s earlier for the reaction)"),
    Shot(59.70, 61.90, "BR", 1279.49, push=(1.0, 1.04), note="Mission Control: the reaction, 2.20 s (v12: in 1279.49 = 1280.2 - 17/24; source shot starts at 1279.40)"),
    Shot(61.90, 62.90, "BLACK"),
    # OUTRO
    Shot(62.90, 67.30, "SEQ", 1.0, img="px_earthrise_v2/px_%04d.png", note="Apollo 11 Earthrise: Blender parallax (3 PIL depth planes), Earth rises"),
    Shot(67.30, 70.90, "BR16", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV), lifted"),
    (Shot(70.90, 72.675, "STILL", img="stills_v26/as11-40-5903_v26.png", kb=((0.50152, 0.27274, 2.48306), (0.51549, 0.23372, 5.3623)), note="v26: AS11-40-5903 original scan (10553 px), push into the visor reflection, real pixels (2.21 -> 1.025 source px per output px); kb in scan coordinates (epi_v26)")
     if V26_SCANS else
     Shot(70.90, 72.675, "SEQ", 1.0, img="px_aldrin/px_%04d.png", note="Aldrin: Blender parallax, opens on the visor, pushes into the reflection")),
    (Shot(72.675, OUTRO_T0, "STILL", img="stills_v26/as11-40-5878_v26.png", kb=((0.59860, 0.62288, 1.2578), (0.64718, 0.65205, 1.64656)), note="v26: AS11-40-5878 original scan (10538 px, stored 1/2), v23's opening frame, a restrained push across the print (scan 4.4 -> 3.3 px per output px)")
     if V26_SCANS and V26_BOOTPRINT else
     Shot(72.675, OUTRO_T0, "STILL", img="as11-40-5878.jpg", kb=((0.62, 0.62, 1.25), (0.62, 0.62, 1.6)), note="bootprint (one giant leap)")),
    (Shot(OUTRO_T0, 78.80, "STILL", img="stills_v26/as11-44-6642_v26.png", kb=((0.50094, 0.57855, 1.03762), (0.50094, 0.57331, 1.08431)), bg_darken=0.5, note="v26: AS11-44-6642 full-frame scan (4275 px, film edges cropped), v23's composition, push 1.0047 -> 1.048 anchored on the horizon (title, date line and AI note unchanged); scan 2.15 -> 2.05 px per output px")
     if V26_SCANS and V26_ENDPLATE else
     Shot(OUTRO_T0, 78.80, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.02)), bg_darken=0.5, note="end title: Earth high, LM low (inside safe); v19 (R5): plate darkened 0.5 before the title (v18: 0.35 after it), push halved so the horizon stays under the raised title")),
    Shot(78.80, 87.50, "BLACK", note="credits; v18: card 1 78.85-82.3, card 2 82.3-86.75, black to 87.5 (silence from 86.3)"),
]

PAO = INBOX / "audio" / "alsj_a11a1023114-4746_PAO.mp3"
RST = WORK / "restore"
# (source, src_in, src_out, timeline_t, gain_db). v2: restored windows (craft_tools.restore audio).
# Window offsets: pao_alarm = PAO from 420 s, pao_land = PAO from 815 s, countdown = activities_tail from 240 s.
DIALOG = [
    (RST / "countdown.wav", 12.0, 22.5, 0.0, -9.0),     # "10 ... ignition sequence starts ... 1" (v10: -5 dB, the drop hits harder)
    (RST / "countdown.wav", 25.0, 31.15, 11.2, -0.5),
    # v16b: Armstrong, AFJ 000:02:44 "Staging." / 000:02:46 "And ignition." (ascent = activities_tail from 420 s; speech
    # 6.76-7.22 and 9.14-9.72 by the envelope): speech at 26.55 (stage-separation cut) and 28.34 (after the 28.0 impact)
    (RST / "ascent.wav", 6.66, 7.40, 26.45, 0.0),
    (RST / "ascent.wav", 9.00, 9.90, 28.20, 0.0),    # "liftoff! we have a liftoff, 32 minutes past the hour" (v10: was 13.0 @ -2.0; "zero, all engines running" cut; +1.5 dB: duck is maxed under the title hits)
    (RST / "pao_alarm.wav", 11.0, 11.75, 40.5, 0.0),
    (RST / "pao_alarm.wav", 15.1, 16.2, 41.6, 0.0),
    (RST / "pao_alarm.wav", 17.0, 17.9, 42.8, 0.0),
    (RST / "pao_alarm.wav", 32.9, 35.3, 43.75, 0.0),
    (RST / "pao_alarm.wav", 37.35, 40.15, 46.15, 0.0),
    (RST / "pao_land.wav", 10.3, 11.9, 49.0, 0.0),
    (RST / "pao_land.wav", 25.5, 28.3, 50.8, 2.0),       # v10: "40 feet, down 2 1/2. Picking up some dust." +2.0 dB
    (RST / "pao_land.wav", 39.3, 40.8, 53.6, 1.0),       # v11: "30 seconds" +1.0 dB (bingo rises into the landing)
    (RST / "pao_land.wav", 48.3, 49.1, 55.2, 2.5),       # v11: "Contact light" +2.5 dB (v9 +1.5)
    (RST / "eagle.wav", 0.0, 5.3, 56.5, 4.5),            # v11: "Houston ... The Eagle has landed" +4.5 dB (v9 +2.0): the landing is the loudest section
    (RST / "pao_land.wav", 77.6, 81.1, 63.7, 0.0),
    (RST / "step.wav", 14.8, 24.12, 67.1, 0.0),
]

# (t0, t1, speaker, text) — wording corrected against the Apollo Lunar Surface Journal / KSC commentary
# v8: LOGICAL (v7) time. The comp looks captions up with tl; on the v8 timeline a caption at t >= 40.0 plays at t - 6.7.
CAPTIONS = [
    (2.20, 3.90, "LAUNCH CONTROL", "Ignition sequence starts."),
    (11.40, 13.80, "LAUNCH CONTROL", "Liftoff! We have a liftoff,"),      # v10: -1.8 s with the line
    (13.90, 15.75, "LAUNCH CONTROL", "32 minutes past the hour."),      # v10: -1.8 s (speech ends tl 15.6)
    (15.90, 17.15, "LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v10: src 29.75-30.9 (tl 15.95-17.1)
    (26.55, 27.25, "ARMSTRONG", "Staging."),          # v17: tag was "APOLLO 11 · ARMSTRONG" (picture: unidentified Saturn V film)          # v16b: AFJ 000:02:44 (speech 26.55-27.0), 11.4 cps
    (28.30, 29.15, "ARMSTRONG", "And ignition."),     # v17: tag was "APOLLO 11 · ARMSTRONG" (picture: Apollo 4/6 interstage film, probable)     # v16b: AFJ 000:02:46 (speech 28.34-28.92), 15.3 cps; out before the TLI card (29.79)
    (47.20, 48.15, "EAGLE · ARMSTRONG", "Program alarm."),
    (48.30, 49.40, "EAGLE · ARMSTRONG", "It's a 1202."),
    (49.50, 50.40, "EAGLE · ALDRIN", "1202."),
    (50.50, 52.75, "EAGLE · ARMSTRONG", "Give us a reading on the 1202 program alarm."),
    (52.90, 55.55, "HOUSTON · DUKE", "Roger. We got you... We're go on that alarm."),
    (55.70, 57.30, "HOUSTON · DUKE", "60 seconds."),
    # v17: split at the speech (pao_land.wav envelope: "Forty feet, down two and a half" src 25.68-26.84 = tl 57.68-58.84,
    # "Picking up some dust" 27.46-28.15 = tl 59.46-60.15): 12.8 cps / 18.3 cps. Part 1 starts with the readout's 40 FT
    # (frame 1222, tl 57.625, one frame before "Forty"), which holds through it (READOUT_HOLDS); no number on screen
    # contradicts part 2 or "30 seconds."
    (57.625, 58.95, "EAGLE · ALDRIN", "40 feet, down 2½."),
    (59.05, 60.20, "EAGLE · ALDRIN", "Picking up some dust."),
    (60.30, 61.75, "HOUSTON · DUKE", "30 seconds."),
    (61.90, 62.85, "EAGLE · ALDRIN", "Contact light."),
    (63.40, 66.85, "EAGLE · ARMSTRONG", "Houston, Tranquility Base here."),   # v15: one caption (v10 split at real 58.5/58.9), 9.0 cps
    (67.10, 68.35, "EAGLE · ARMSTRONG", "The Eagle has landed."),
    (70.20, 72.40, "HOUSTON · DUKE", "You got a bunch of guys about to turn blue."),   # v11: 19.5 cps (was 22.1)
    (72.50, 74.25, "HOUSTON · DUKE", "We're breathing again."),       # v11: condensed caption (audio unchanged), 12.6 cps
    (74.35, 77.60, "ARMSTRONG", "That's one small step for man,"),
    (79.40, 82.70, "ARMSTRONG", "one giant leap for mankind."),
]


# ---------------------------------------------------------------- helpers
def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd[:6])}...\n{r.stderr[-2000:]}")


def nframes(s: Shot) -> int:
    return int(round(s.t1 * FPS)) - int(round(s.t0 * FPS))


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    paths = {
        "anton": FONTS / "Anton-Regular.ttf",
        "bebas": FONTS / "BebasNeue-Regular.ttf",
        "body": Path(r"C:\Windows\Fonts\bahnschrift.ttf"),
        "mono": Path(r"C:\Windows\Fonts\consolab.ttf"),
    }
    return ImageFont.truetype(str(paths[name]), size)


def ease_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_in_out(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- stage A: shots
def render_still(s: Shot, path: Path) -> None:
    if s.img.startswith(epi_v26.DIR + "/"):      # v26: original-scan stills (epi_v26: PIL, manifest-verified frames)
        return epi_v26.render_still_v26(s, path)
    img = Image.open(INBOX / "stills" / s.img).convert("RGB")
    iw, ih = img.size
    n = nframes(s)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "14",
                            "-preset", "veryfast", "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
    (cx0, cy0, z0), (cx1, cy1, z1) = s.kb
    for i in range(n):
        u = ease_in_out(i / max(n - 1, 1)) * 0.85 + (i / max(n - 1, 1)) * 0.15
        cx, cy, z = cx0 + (cx1 - cx0) * u, cy0 + (cy1 - cy0) * u, z0 + (z1 - z0) * u
        # crop window: 16:9 box that covers the frame at zoom z (z=1 -> full image width)
        cw = iw / z
        ch = cw * H / W
        if ch > ih / z * 1.0 and ch > ih:
            ch = ih
            cw = ch * W / H
        x0 = min(max(cx * iw - cw / 2, 0), iw - cw)
        y0 = min(max(cy * ih - ch / 2, 0), ih - ch)
        frame = img.transform((W, H), Image.Transform.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.Resampling.BICUBIC)
        enc.stdin.write(frame.tobytes())
    enc.stdin.close()
    enc.wait()


def render_seq(s: Shot, path: Path) -> None:
    """Blender PNG sequence over a slowly drifting star layer (stars only show where the render is black)."""
    n = nframes(s)
    fc = (f"[1:v]crop={W}:{H}:x='60+t*18':y='40+t*6',format=rgba[st];"
          f"[0:v]fps={FPS},format=rgba,colorkey=black:0.02:0.0[mo];[st][mo]overlay=shortest=1:format=rgb,{GRADE[s.grade] + ',' if s.grade else ''}format=yuv420p")
    start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []
    if V25_HERO and s.img.startswith(hud_v25.HERO_DIR + "/"):    # v25: opaque (stars by alpha in the asset): no colorkey
        run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(WORK / s.img), "-filter_complex",
             f"[0:v]format=rgb24,{GRADE[s.grade] + ',' if s.grade else ''}format=yuv420p", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])
        return
    if s.img.startswith("px_"):
        run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i",
             str(WORK / s.img), "-vf", f"fps={FPS},format=yuv420p", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])
        return
    run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i", str(WORK / "blender" / "..") + "/" + s.img,
         "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / "blender" / "stars.png"),
         "-filter_complex", fc, "-frames:v", str(n), "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])


def ramp_map(knots: tuple, n: int) -> np.ndarray:
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


def sha256(b: bytes) -> str:
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
    d = np.diff(pos)
    print(f"  ramp {s.src} src {s.src_in:.3f}-{s.src_in + pos[-1]:.3f} ({pos[-1] * sfps:.2f} source frames at "
          f"{sfps:g} fps) for {n} output frames; step min {d.min() * FPS:.3f}x max {d.max() * FPS:.3f}x, monotonic "
          f"{bool((d > 0).all())}; {exact} exact source frames, {n - exact} {'RIFE in-betweens' if RAMP_RIFE else 'two-frame blends'}")


V27_SLOWMO = True       # v27 (director's A/B): the 13.00 s smoke-under-the-title shot from RIFE in-betweens (slowmo_v27)


def render_video_shot(s: Shot, path: Path) -> None:
    if s.ramp is not None and RAMP_IGNITION:     # v19 (R4); RAMP_IGNITION = False renders the constant-speed shot
        render_ramp_shot(s, path)
        return
    if V27_SLOWMO:
        import slowmo_v27
        if slowmo_v27.is_slowmo_shot(s):
            slowmo_v27.render(s, path, W, H, FPS, GRADE[s.src], nframes(s))
            return
    n = nframes(s)
    src_dur = n / FPS * s.speed + 0.5
    crop = s.crop or CROP.get(s.src)
    vf = []
    if crop:
        vf.append(f"crop={crop}")
    vf.append(f"scale={W}:{H}:flags=lanczos")
    vf.append(GRADE[s.src])
    if s.speed != 1.0:
        vf.append(f"setpts=(PTS-STARTPTS)/{s.speed}")
        vf.append(f"framerate=fps={FPS}")
    else:
        vf.append(f"fps={FPS}")
    vf.append("format=yuv420p")
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s.src_in:.3f}", "-t", f"{src_dur:.3f}", "-i", str(SRC[s.src]),
         "-vf", ",".join(vf), "-frames:v", str(n), "-an", "-c:v", "libx264", "-crf", "14", "-preset", "veryfast",
         str(path)])


def stage_shots() -> None:
    SEG.mkdir(parents=True, exist_ok=True)
    only = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None
    for i, s in enumerate(SHOTS):
        if only is not None and i not in only:
            continue
        p = SEG / f"s{i:02d}.mp4"
        if s.src in ("BLACK", "INSERT", "WHITE"):
            col = "white" if s.src == "WHITE" else "black"
            run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color={col}:s={W}x{H}:r={FPS}",
                 "-frames:v", str(nframes(s)), "-c:v", "libx264", "-crf", "14", "-pix_fmt", "yuv420p", str(p)])
        elif s.src == "STILL":
            render_still(s, p)
        elif s.src == "SEQ":
            render_seq(s, p)
        else:
            render_video_shot(s, p)
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                  "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(p)],
                                 capture_output=True, text=True).stdout.strip() or 0)
        if got != nframes(s):
            raise SystemExit(f"s{i:02d}: rendered {got} frames, expected {nframes(s)}; the concat would drift")
        flag = ""
        print(f"s{i:02d} {s.t0:6.2f}-{s.t1:6.2f} {s.src:5s} frames={got}{flag}  {s.note}")
    with open(SEG / "list.txt", "w") as f:
        for i in range(len(SHOTS)):
            f.write(f"file 's{i:02d}.mp4'\n")


# ---------------------------------------------------------------- audio helpers
def load_audio(path: Path, t_in: float, t_out: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}", "-t", f"{t_out - t_in:.3f}", "-i", str(path),
                          "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def load_stem(path: Path) -> np.ndarray:
    if not path.exists():
        print(f"  (missing {path.name}; using silence)")
        return np.zeros((int(TOTAL * SR), 2), np.float32)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()
    out = np.zeros((int(TOTAL * SR), 2), np.float32)
    out[: min(len(x), len(out))] = x[: len(out)]
    return out


def biquad(x: np.ndarray, kind: str, f0: float, q: float = 0.707) -> np.ndarray:
    w0 = 2 * math.pi * f0 / SR
    alpha = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    if kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    else:
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    a = [1 + alpha, -2 * c, 1 - alpha]
    b = [v / a[0] for v in b]
    a = [v / a[0] for v in a]
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):  # small clips only; fine in pure Python
        xi = float(x[i])
        yi = b[0] * xi + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


# v17: restored windows that only a patch used to create (Codex on v16: DIALOG needs restore/ascent.wav, which only
# patch_v16b made). name -> (source under WORK, start s, length s); the same step as patch_v16b: ffmpeg stream copy of the
# window, then craft_tools.restore audio at its default strength (it reproduces restore/countdown.wav bit-exactly).
CRAFT = Path(os.environ.get("CRAFT_TOOLS", "craft-tools"))
RESTORE_WINDOWS = {"ascent.wav": ("activities_tail.wav", 420.0, 20.0)}


def ensure_restored(path: Path) -> None:
    """Create a missing restored window from RESTORE_WINDOWS. Never overwrites (exists -> return; ffmpeg -n)."""
    if path.exists():
        return
    if path.name not in RESTORE_WINDOWS:
        raise SystemExit(f"missing {path} and no RESTORE_WINDOWS recipe for it")
    src, ss, dur = RESTORE_WINDOWS[path.name]
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_name(path.stem + "_raw.wav")
    if not raw.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-ss", f"{ss:g}", "-t", f"{dur:g}", "-i", str(WORK / src),
                        "-c", "copy", str(raw)], check=True)
    tmp = CRAFT / ".tmp"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TMP=str(tmp), TEMP=str(tmp), PYTHONUTF8="1")
    r = subprocess.run(["uv", "run", "python", "-m", "craft_tools.restore", "audio", str(raw), str(path)], cwd=CRAFT,
                       env=env, capture_output=True, text=True)
    if r.returncode != 0 or not path.exists():
        raise SystemExit(f"restore of {path.name} failed:\n{r.stderr[-1500:]}")
    print(f"  restored window written: {path} ({r.stdout.strip()})")


# v17: per-DIALOG-index presence lift in dB (RBJ peaking EQ, 3.2 kHz, Q 0.8: about 2.3-4.5 kHz), applied before the
# level match. Armstrong's "Staging." / "And ignition." (indices 2, 3: whisper recall 0 on the v16 mix)
DIALOG_PRESENCE = {2: 4.0, 3: 4.0}


def presence(x: np.ndarray, gain_db: float, f0: float = 3200.0, q: float = 0.8) -> np.ndarray:
    """RBJ peaking biquad (pure Python loop like biquad(): short clips only)."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    b0, b1, b2, a0, a1, a2 = 1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        xi = float(x[i])
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


def stage_dialog() -> None:
    AUD.mkdir(parents=True, exist_ok=True)
    for src in dict.fromkeys(x[0] for x in DIALOG):      # v17: rebuild a missing restored window (never overwrites)
        ensure_restored(src)
    out = np.zeros(int(TOTAL * SR), np.float32)
    active = np.zeros(int(TOTAL * SR), np.float32)
    for k_, (src, a, b, t, g) in enumerate(DIALOG):
        x = load_audio(src, a, b)
        x = biquad(x, "hp", 120.0)
        x = biquad(x, "lp", 7000.0)
        if k_ in DIALOG_PRESENCE:                # v17: per-entry presence lift (before the level match)
            x = presence(x, DIALOG_PRESENCE[k_])
        # level-match: speech RMS (over the louder half of 50 ms blocks) to -20 dBFS
        blk = 2400
        nb = max(len(x) // blk, 1)
        r = np.sqrt(np.mean(x[: nb * blk].reshape(nb, -1) ** 2, axis=1) + 1e-12)
        speech = np.sort(r)[nb // 2:]
        lvl = 20 * np.log10(np.mean(speech) + 1e-9)
        x = x * 10 ** ((-20.0 - lvl + g) / 20)
        f = int(0.015 * SR)
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
        i0 = int(t * SR)
        i1 = min(i0 + len(x), len(out))
        out[i0:i1] += x[: i1 - i0]
        active[i0:i1] = 1.0
        print(f"  dialog {src.name} {a:.2f}-{b:.2f} @ {t:.2f}  level {lvl:.1f} dBFS -> -20")
    peak = np.max(np.abs(out))
    if peak > 0.89:
        out *= 0.89 / peak
    out.astype(np.float32).tofile(AUD / "dialog.f32")
    active.astype(np.float32).tofile(AUD / "dialog_active.f32")
    run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(AUD / "dialog.f32"),
         "-c:a", "pcm_s24le", str(AUD / "dialog.wav")])
    print("dialog stem written")


# ---------------------------------------------------------------- stage B: graphics
AMBER = (255, 176, 64)
WHITE = (242, 240, 234)
RED = (255, 64, 48)
GREEN = (120, 255, 150)
CYAN = (140, 220, 255)

V20_HUD = True          # v20: DSKY / MOCR monitor / stat cards drawn by hud_v20 (False: v19's drawing, unchanged)
V20_DISTANCE = False    # v20: the 240,000 card sits in the protected Moon beat (frames 829-877): kept as v19 unless approved
V21_HUD = True          # v21: draw with hud_v21 (phone-size legibility, no CRT ghost); False: hud_v20 exactly (v20)
V22_HUD = True          # v22: draw with hud_v22 (one overlay system, carry fix, DSKY header, CONTACT in the HUD); False: v21
V22_DISTANCE = True     # v23: the director approved the drum-style 240,000 card (2026-10-08 16:40, after the preview
#                         auditions/v22_distance_card_preview.mp4); frames 830-877 change, timing unchanged. False: v22
EARTH_LIMB_X = 1040   # Earth's right limb on the as11-36-5355 plate after the push (v7 37-40 s; v8 29.8-33.3; unused)
TITLE_DIR = "title3d_v22"   # v22: title_v22.py (stronger rim + weak left fill: the bevel reads); v18-v21 "title3d_v18"
TITLE_FRAMES = {"open": 104, "end": 56}     # v22 (R4): exact sequence lengths the manifest must hold


def ascent_shot() -> "Shot":
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
    if V25_HERO:            # v25
        hero_check()


def hero_check() -> None:
    """v25: the hero_v25 asset (assets_v25.check_hero: names, sha256, size, mode, geometry.json, sources, the shot)
    against the SEQ shot build.py will render, then hud_v25 loads its geometry. No Blender needed."""
    if not V23_HUD:
        raise SystemExit("V25_HERO needs V23_HUD (hud_v25 draws in the hud_v23 system)")
    s = next(x for x in SHOTS if x.src == "SEQ" and x.img and x.img.startswith(hud_v25.HERO_DIR + "/"))
    f0 = int(round(s.t0 * FPS))
    if (f0, f0 + nframes(s)) != hud_v25.HERO_F:
        raise SystemExit(f"hero shot frames {f0}-{f0 + nframes(s) - 1}, hud_v25 expects {hud_v25.HERO_F}")
    assets_v25.check_hero(WORK, hud_v25.HERO_DIR, f0, nframes(s), (W, H))
    hud_v25.load(WORK / hud_v25.HERO_DIR)
    print(f"  hero asset {hud_v25.HERO_DIR}: {nframes(s)} frames + geometry + sources verified (frames {f0}-"
          f"{f0 + nframes(s) - 1})")


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
    if stage == "shots" and V25_HERO:      # v25: stage_shots reads the hero frames
        hero_check()
    if stage in ("all", "shots"):
        rife_cache_check()
        if V26_SCANS:             # v26: stills_v26 crops, sources and the shot table vs its manifest
            print(f"  v26 scans: {epi_v26.check(SHOTS)} shots verified against stills_v26/manifest.json")
    if stage in ("all", "mix") and REUSE_AUDIO_FROM is not None:
        reused_audio_check(REUSE_AUDIO_FROM)


def title_idx(frames: list, dt: float) -> int:
    """v22 (R4): the title frame index for dt seconds into its window; raises instead of clamping a short sequence."""
    idx = int(round(dt * FPS))
    if not 0 <= idx < len(frames):
        raise SystemExit(f"title: frame index {idx} outside the {len(frames)}-frame sequence")
    return idx
TITLE_SHADOW = 0.20         # v18: drop shadow under the title (v3-v17 0.55)
PAO_ALT = [(0, 0.0), (30, 0.6), (56, 2.0), (66, 4.0), (106, 12.0), (148, 30.0), (180, 43.0)]   # nautical miles
PAO_PTS = [(56, 2.0), (66, 4.0), (106, 12.0), (148, 30.0), (180, 43.0)]   # values called out by the PAO
PAO_VEL = [(0, 0.0), (66, 2195.0), (106, 4000.0), (180, 9300.0)]           # ft/s called out by the PAO


def pchip(xs: list[float], ys: list[float], x: float) -> float:
    xs_a, ys_a = np.array(xs, float), np.array(ys, float)
    h = np.diff(xs_a)
    d = np.diff(ys_a) / h
    m = np.zeros_like(ys_a)
    for k in range(1, len(xs_a) - 1):
        if d[k - 1] * d[k] > 0:
            w1, w2 = 2 * h[k] + h[k - 1], h[k] + 2 * h[k - 1]
            m[k] = (w1 + w2) / (w1 / d[k - 1] + w2 / d[k])
    m[0], m[-1] = d[0], d[-1]
    k = int(np.clip(np.searchsorted(xs_a, x) - 1, 0, len(h) - 1))
    t = (x - xs_a[k]) / h[k]
    h00, h10, h01, h11 = 2 * t**3 - 3 * t**2 + 1, t**3 - 2 * t**2 + t, -2 * t**3 + 3 * t**2, t**3 - t**2
    return float(h00 * ys_a[k] + h10 * h[k] * m[k] + h01 * ys_a[k + 1] + h11 * h[k] * m[k + 1])

HOOK_OUT = round(1.2 * FPS) / FPS          # v18: the first L70 frame (29): the countdown HUD takes the slot
FLASH_F = (int(round(3.9 * FPS)), int(round(8.4 * FPS)))      # v23: the flash-forward inserts, frames 94-201
ASC_F = (int(round(21.8333 * FPS)), int(round(26.5 * FPS)))   # v23: the ascent shot, frames 524-635
CREDITS_F0 = 1891         # v23: first credits frame; an IDR is forced here in the comp and export encodes
IDR_ARGS = ["-force_key_frames", f"expr:eq(n,{CREDITS_F0})", "-forced-idr", "1"]
FRAME_HASHES = os.environ.get("MOONSHOT_FRAME_HASHES", "")    # v23 gate: sha256 per frame before encoding
ARCHIVE_OUT = round(29.8 * FPS) / FPS      # v18: the cut to the Apollo 11 Earth still (frame 715)
DSKY_RIGHT_T = (1045 + 161) / 24   # v19: the cut to Mission Control moved to frame 1045 (tl 50.25); v11-v18 50.62 (frame 1054)
DSKY_LEFT_T = 52.37      # v12: s23's (v14 s26, v15 s25) source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again
# v17: the right-side panel fades out over the 6 frames before frame 1096 (tl 52.104 -> 52.375) and is not drawn from it
# on: v16 drew it top-left again for 0.43 s (52.375-52.8), "switches sides of the screen for a split second"
DSKY_OUT = ((1089.5 + ACT2_DF) / FPS, (1096 + ACT2_DF) / FPS)


def l70_window(t: float) -> float:
    """v17 provenance: 0..1 visibility of the APOLLO 11 / LAUNCH COMPLEX 39A countdown HUD: only while an Apollo 11
    70mm (L70) shot is on screen. Eases in over 0.25 s from each L70 run's first frame and out to 0 on its last frame
    (frame-rounded cuts, as the segments). Before the Moon cut, so logical == real."""
    runs: list[list[int]] = []
    for s in SHOTS:
        f0, f1 = int(round(s.t0 * FPS)), int(round(s.t1 * FPS))
        if s.src == "L70":
            if runs and runs[-1][1] == f0:
                runs[-1][1] = f1
            else:
                runs.append([f0, f1])
    for f0, f1 in runs:
        if f1 - f0 < 18:      # v19 (R1): a short L70 insert (< 0.75 s) never shows the HUD (was a 6-frame half-alpha blink)
            continue
        a, b = f0 / FPS, (f1 - 1) / FPS
        if a - 1e-9 <= t <= b + 1e-9:
            return ease_in_out((t - a) / 0.25) * ease_in_out((b - t) / 0.25)
    return 0.0


# v17: the altitude readout's own step times (logical) from Aldrin's "40 feet" on: 40 FT holds through the caption that
# speaks it ("40 feet, down 2½." to 58.95), 30 FT (ALSJ 102:45:21, not in the edit's audio) from there under "Picking up
# some dust.", and the unspoken 30 -> 20 step falls on the Mission Control cut (frame 1284, tl 60.208), before Duke's
# "30 seconds." (60.3), so that caption sits next to 20 FT (ALSJ: 20 ft at 102:45:25, "30 seconds" at :31).
# (time, GET held): before the first entry the readout reads the shared GET map (bingo clock) as in v16.
READOUT_HOLDS = [(57.625, 17.0), ((1256 + ACT2_DF) / FPS, 21.0), ((1284 + ACT2_DF) / FPS, 25.0)]   # v20: 30 FT on the
# 1256 cut back to the dust (v17-v19: tl 58.95 = frame 1254, the "40 feet" caption's end; no caption 1254-1256)


def readout_get(tl: float) -> float:
    if tl < READOUT_HOLDS[0][0]:
        return get_at(tl)
    g = READOUT_HOLDS[0][1]
    for t_, g_ in READOUT_HOLDS:
        if tl >= t_:
            g = g_
    return g


def readout_step_t(g_alt: float) -> float:
    """Logical time at which the readout steps to the call made at GET g_alt."""
    for t_, g_ in READOUT_HOLDS:
        if abs(g_ - g_alt) < 1e-9:
            return t_
    return tl_of_get(g_alt)

# v16: LOGICAL timeline -> GET seconds after 102:45:00 via the dialogue anchors, ONE time-compressed clock shared by the
# bingo counter (fuel) and the altitude readout (descent). "60 seconds" 102:45:02 (55.7, the PAO tape 825.3); Aldrin's
# "40 feet" 102:45:17 (57.625 = frame 1222, one frame before the word: pao_land 25.65 = real 50.95; v16 anchor);
# "30 seconds" (60.3 -> :32, so the counter reads 30.0 on the words); "Contact light" 102:45:40 (61.9); engine stop.
GET_ANCHORS = [(55.7, 2.0), (57.625, 17.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
# v16: Aldrin's callouts, Apollo Lunar Surface Journal a11.landing.html (data/alsj_descent_callouts.csv):
# (GET s after 102:45:00, altitude ft, down ft/s, forward ft/s); None = not stated in that call (the field holds)
CALLOUTS = [(-15.0, 100, 3.5, 9), (-6.0, 75, 0.5, 6), (8.0, 60, 2.5, 2), (17.0, 40, 2.5, None),
            (21.0, 30, 2.5, None), (25.0, 20, 0.5, 4)]
CONTACT_GET = 40.0          # 102:45:40 Aldrin: "Contact Light."


def get_at(tl: float) -> float:
    """GET (s after 102:45:00) on the shared dialogue map at logical time tl; clamped outside the anchors."""
    if tl <= GET_ANCHORS[0][0]:
        return GET_ANCHORS[0][1]
    if tl >= GET_ANCHORS[-1][0]:
        return GET_ANCHORS[-1][1]
    for (ta, ga), (tb, gb) in zip(GET_ANCHORS, GET_ANCHORS[1:]):
        if ta <= tl <= tb:
            return ga + (gb - ga) * (tl - ta) / (tb - ta)
    return GET_ANCHORS[-1][1]


def tl_of_get(g: float) -> float:
    """Inverse of get_at (the map is strictly increasing): logical time at which the clock reads GET g."""
    if g <= GET_ANCHORS[0][1]:
        return GET_ANCHORS[0][0]
    for (ta, ga), (tb, gb) in zip(GET_ANCHORS, GET_ANCHORS[1:]):
        if ga <= g <= gb:
            return ta + (tb - ta) * (g - ga) / (gb - ga)
    return GET_ANCHORS[-1][0]


class Gfx:
    def __init__(self) -> None:
        self.f = {
            "anton150": font("anton", 150), "anton120": font("anton", 120), "anton200": font("anton", 200),
            "anton96": font("anton", 96),
            "bebas30": font("bebas", 30), "bebas40": font("bebas", 40), "bebas48": font("bebas", 48),
            "bebas60": font("bebas", 60), "bebas34": font("bebas", 34), "bebas26": font("bebas", 26),
            "body44": font("body", 44), "body26": font("body", 26), "body22": font("body", 22), "body34": font("body", 34),
            "body30": font("body", 30), "body41": font("body", 41),
            "mono34": font("mono", 34), "mono22": font("mono", 22), "mono60": font("mono", 60),
            "seg120": font("mono", 110),
        }
        # v18: opening frames open_####.png (104), end card end_####.png (56, own framing)
        self.h20 = None       # v20: the frame's hud_v20.HudFrame (set by stage_comp)
        self.title = sorted((WORK / TITLE_DIR).glob("open_*.png"))
        self.title_end = sorted((WORK / TITLE_DIR).glob("end_*.png"))

    def v22(self) -> bool:
        """v22: draw this element with hud_v22 (one system, one film pass) instead of on the graphics layer."""
        return V22_HUD and self.h20 is not None

    # -- shared primitives
    def text(self, d: ImageDraw.ImageDraw, xy, s, f, fill, anchor="la", alpha=1.0, track=0):
        col = fill + (int(255 * alpha),)
        # v18: ImageDraw REPLACES RGBA pixels (no blending): zero-alpha text used to punch its glyphs out of whatever was
        # already on the layer (the v17 countdown HUD showed as a knocked-out ghost in the top gradient). Not drawn now.
        ink = col[3] > 0
        # v18: partly transparent text is blended (drawn opaque on a scratch layer, alpha scaled, alpha_composite), so a
        # fading HUD / label no longer lowers the alpha of the gradient or plate already under it
        im_ = getattr(d, "_image", None)
        if ink and col[3] < 255 and im_ is not None and im_.mode == "RGBA":
            tmp = Image.new("RGBA", im_.size, (0, 0, 0, 0))
            w_ = self.text(ImageDraw.Draw(tmp), xy, s, f, fill, anchor, 1.0, track)
            tmp.putalpha(tmp.getchannel("A").point(lambda v: v * col[3] // 255))
            im_.alpha_composite(tmp)
            return w_
        if track:
            x, y = xy
            total = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for c in s:
                if ink:
                    d.text((x, y), c, font=self.f[f], fill=col, anchor="l" + anchor[1])
                x += d.textlength(c, font=self.f[f]) + track
            return total
        if ink:
            d.text(xy, s, font=self.f[f], fill=col, anchor=anchor)
        return d.textlength(s, font=self.f[f])

    def wipe_text(self, layer: Image.Image, xy, s, f, fill, prog, anchor="ls", alpha=1.0):
        """Text revealed by a rising mask: prog 0..1."""
        if prog <= 0:
            return
        tmp = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(tmp)
        bbox = d.textbbox(xy, s, font=self.f[f], anchor=anchor)
        rise = (1 - ease_out(prog)) * (bbox[3] - bbox[1]) * 0.9
        d.text((xy[0], xy[1] + rise), s, font=self.f[f], fill=fill + (int(255 * alpha),), anchor=anchor)
        mask = Image.new("L", layer.size, 0)
        ImageDraw.Draw(mask).rectangle([bbox[0] - 10, bbox[1] - 6, bbox[2] + 10, bbox[3] + 8], fill=255)
        tmp.putalpha(Image.fromarray(np.minimum(np.array(tmp.getchannel("A")), np.array(mask))))
        layer.alpha_composite(tmp)

    # -- graphics by time
    def draw(self, t: float, layer: Image.Image) -> None:
        d = ImageDraw.Draw(layer)
        if (0.0 <= t < 13.0 or 44.0 <= t < 47.0) and self.v22():   # v22: the gradient goes under the HUD labels
            self.h20.add("topgrad")
        elif 0.0 <= t < 13.0 or 44.0 <= t < 47.0:
            top = Image.new("RGBA", (W, 240), (0, 0, 0, 0))
            ImageDraw.Draw(top)
            g = np.zeros((240, W, 4), np.uint8)
            g[..., 3] = (np.linspace(120, 0, 240)[:, None] * np.ones((1, W))).astype(np.uint8)
            layer.alpha_composite(Image.fromarray(g, "RGBA"))
        if 0.2 <= t < 13.0:
            self.countdown_hud(d, t, layer)
        if 61.79 <= t < 62.9:     # v9: from the insert's first frame (logical 61.792; 61.8 missed it)
            self.contact_insert(layer, d, t - 61.8)
        if 19.0 <= t < 22.0:
            self.stat_thrust(layer, d, t - 19.0)
        if 0.15 <= t < HOOK_OUT:  # v18: what this is, before the L70 HUD takes the slot at the 1.2 cut
            self.hook(d, t)
        if V23_HUD and self.v22():    # v23: the flash-forward tag (frames 94-201) and the ascent text (524-635)
            fi_ = self.h20.fi
            if FLASH_F[0] <= fi_ < FLASH_F[1] and "countdown" not in self.h20.items:
                self.h20.add("flashtag", a=ease_out((fi_ - FLASH_F[0] + 1) / 4))
            if ASC_F[0] <= fi_ < ASC_F[1]:
                self.h20.add("ascent", fi=fi_)
        if 26.5 <= t < ARCHIVE_OUT:   # v18 provenance: the staging film is from other Saturn V flights
            self.archive_tag(d, t)
        if 26.5 <= t < 27.25:    # v8: staging shot (before ACT2_T0, logical time == real time); v15: 0.75 s
            self.stage_label(d, t - 26.5, 0.75)
        if round(29.8 * FPS) / FPS <= t < ACT2_T0:     # v8: over the as11-36-5355 still (cut 29.8 = frame 715); v14: still to 31.0, then the 16mm Earth
            self.stat_speed(layer, d, t - round(29.8 * FPS) / FPS)
        if V25_HERO and self.v22() and hud_v25.HERO_F[0] <= self.h20.fi < hud_v25.HERO_F[1]:   # v25: route + label
            self.h20.add("hero", fi=self.h20.fi)
        if 40.0 <= t < 44.0:
            self.stat_distance(layer, d, t - 40.0)
            ar = min(1.0, (t - 40.2) / 0.4) * (1 - ease_in_out((t - 43.4) / 0.4))

        if 44.0 <= t < 47.0:
            self.chapter(d, t - 44.0)
        if 69.8 <= t < 73.6:
            self.label(d, t - 69.8, "EARTHRISE", "PHOTOGRAPHED FROM APOLLO 11 · JULY 1969")
        if 47.2 <= t < DSKY_OUT[1]:      # v17: gone from the LM-window cut (frame 1096); v16 ran to 52.8 top-left
            self.dsky(d, t - 47.2, right=DSKY_RIGHT_T <= t)
        if 55.6 <= t < 62.9:      # v9: the bingo HUD holds over the CONTACT insert, cut by the white frame
            self.fuel(d, t)
        if 55.75 <= t < 62.9:     # v16: Aldrin's altitude callouts under the bingo, same clock, same white-frame cut
            self.descent(d, t)
        if False:   # v7: end card is over the photo again (stars only for the old black card)
            st = Image.open(WORK / "blender" / "stars.png").convert("RGB").crop((100, 60, 100 + W, 60 + H))
            sa = np.asarray(st, np.uint8)
            stars = np.dstack([sa, (sa.max(axis=2) * 0.8).astype(np.uint8)])
            layer.alpha_composite(Image.fromarray(stars, "RGBA"))
        d0, dd = (83.6, 0.3) if V26_OUTRO else (83.9, 0.5)     # v26: the date line sooner (director: too rushed)
        if d0 <= t < 85.5:
            a = ease_out((t - d0) / dd) * (1 - ease_in_out((t - 85.15) / 0.35))
            if V23_HUD and self.v22():      # v23: on-screen AI-assist disclosure under the date line
                self.h20.add("endnote", a=a)
            self.text(d, (1392, 420), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)   # v19: under the raised title (x 985-1800), on the darkened ground (v18 centre, y 510)
        if 85.55 <= t < CARD2_T:   # v18: 3.45 s, real 78.85-82.3 (v17 4.5 s)
            self.credits(d, t - 85.55)
        if CARD2_T <= t < CARD2_T + 4.5:   # v18: 4.45 s, real 82.3-86.75 (v17 3.0 s); black after it to 87.5
            self.credits2(d, t - CARD2_T)

    def countdown_hud(self, d, t, layer=None):
        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))
        a *= l70_window(t)       # v17 provenance: only over the Apollo 11 70mm shots (not the BR / SV launch film)
        # the readout follows the SPOKEN count (the picture already cuts on the voice)
        spoken = [(0.2, 10), (1.2, 9), (2.2, 8), (3.5, 7), (4.8, 6), (5.6, 5), (6.6, 4), (7.4, 3), (8.4, 2), (9.4, 1), (10.6, 0)]
        n, n_ts = 10, 0.2
        for ts, k in spoken:
            if t >= ts:
                n, n_ts = k, ts
        s = f"T − 00:00:{n:02d}" if t < 10.6 else f"T + 00:00:{int(t - 10.6):02d}"
        x, y = 112, 70
        if int(230 * a) <= 0:      # v18: gated off (non-L70 shot): draw nothing (v17 knocked the bar + text out of the gradient)
            if layer is not None:
                self.countdown_numeral(layer, t, n, n_ts)
            return
        site = 0.0 if 3.9 <= t < 8.4 else 1.0
        if self.v22():           # v22: the system's faces through the HUD film pass; the count numeral stays here
            self.h20.add("countdown", a=a, site=site, s=s)
            if layer is not None:
                self.countdown_numeral(layer, t, n, n_ts)
            return
        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))     # v18: blended (was d.rectangle)
        self.text(d, (x + 20, y - 4), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas34", AMBER, "la", a * 0.95 * site, track=3)
        self.text(d, (x + 20, y + 32), s, "mono34", WHITE, "la", a)
        if layer is not None:
            self.countdown_numeral(layer, t, n, n_ts)

    def hook(self, d, t):
        """v18: top-left in the countdown HUD's slot and style (bar, bebas34 amber header, mono34 white line) over the
        firing-room shot 0.15 s -> the 1.2 s cut (frame 29), where the L70 HUD ("APOLLO 11 · LAUNCH COMPLEX 39A") eases in
        on the same slot. In 0.3 s, cut out with the shot."""
        a = ease_out((t - 0.15) / 0.3)
        if self.v22():
            self.h20.add("hook", a=a)
            return
        x, y = 112, 70
        self.rect_blend(d, [x, y, x + 6, y + 64], AMBER + (int(230 * a),))
        self.text(d, (x + 20, y - 4), "APOLLO 11", "bebas34", AMBER, "la", a * 0.95, track=3)
        self.text(d, (x + 20, y + 32), "JULY 16, 1969", "mono34", WHITE, "la", a)

    def rect_blend(self, d, box, rgba):
        """v18: a filled rectangle alpha-composited onto the layer (d.rectangle replaces the pixels under it)."""
        im_ = d._image
        tmp = Image.new("RGBA", (int(box[2] - box[0]) + 1, int(box[3] - box[1]) + 1), rgba)
        im_.alpha_composite(tmp, (int(box[0]), int(box[1])))

    def archive_tag(self, d, t):
        """v18 provenance: small lower-left tag over the staging film (26.5 -> the 29.8 cut, frame 715): bebas34 light grey
        on a soft dark plate, baseline 1004 at x 112 (title safe; the captions are bottom-centre, x >= ~800)."""
        a = ease_out((t - 26.5) / 0.2) * (1 - ease_in_out((t - (ARCHIVE_OUT - 0.2)) / 0.2))
        if a <= 0:
            return
        if self.v22():
            self.h20.add("archive", a=a)
            return
        s_, f = "ARCHIVE: OTHER SATURN V FLIGHT", "bebas34"
        tw = sum(d.textlength(c, font=self.f[f]) + 3 for c in s_) - 3
        d.rounded_rectangle([100, 966, 124 + tw, 1014], radius=6, fill=(0, 0, 0, int(120 * a)))
        self.text(d, (112, 1004), s_, f, (215, 215, 210), "ls", a * 0.9, track=3)

    def countdown_numeral(self, layer, t, n, ts):
        """v9: the spoken count as a big Anton numeral for phone viewers, bottom-right inside title safe (right edge
        1800, baseline 1012: glyph bottom <= 1016). Pops 1.25 -> 1.0 over 0.15 s on each new count, alpha 0.9.
        v10: shown 0.2-10.45: also 2.2-3.9 (the "8"; it clears the bottom-centre "Ignition sequence starts." caption)
        and gone 0.15 s before the 10.6 fireball, so no "1" or "0" sits on it."""
        if not (0.2 <= t < 10.45):
            return
        t0 = ts
        size = int(round(260 * (1.25 - 0.25 * ease_out((t - t0) / 0.15))))
        key = f"anton{size}"
        if key not in self.f:
            self.f[key] = font("anton", size)
        s = str(n)
        d2 = ImageDraw.Draw(layer)
        bb = d2.textbbox((1800, 1012), s, font=self.f[key], anchor="rs")
        pad = 40
        sh = Image.new("L", (bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad), 0)
        ImageDraw.Draw(sh).text((1800 - bb[0] + pad, 1012 - bb[1] + pad), s, font=self.f[key], fill=105, anchor="rs")
        shadow = Image.new("RGBA", sh.size, (0, 0, 0, 0))
        shadow.putalpha(sh.filter(ImageFilter.GaussianBlur(12)))
        layer.alpha_composite(shadow, (bb[0] - pad + 6, bb[1] - pad + 8))
        d2.text((1800, 1012), s, font=self.f[key], fill=WHITE + (int(255 * 0.9),), anchor="rs")

    def stat_thrust(self, layer, d, u):
        if V20_HUD:          # v20: drum-counter data block (hud_v20.render_thrust), same window and exit
            self.h20.add("thrust", u=u)
            return
        out = ease_in_out((u - 2.45) / 0.35)     # v19: gone by u 2.80 (real 21.80), before the 524 cut (v18 2.6-2.95)
        x = 120
        if out > 0:          # fade + rise out (v4's slide-off cropped to "LLION")
            layer_alpha = 1 - out
            self.text(d, (x, 360 - out * 30), "LIFTOFF THRUST", "bebas40", AMBER, "ls", layer_alpha)
            self.text(d, (x, 520 - out * 30), "7.5 MILLION", "anton150", WHITE, "ls", layer_alpha)
            self.text(d, (x, 600 - out * 30), "POUNDS  ·  FIVE F-1 ENGINES", "bebas48", WHITE, "ls", layer_alpha * 0.9)
            d.rectangle([x, 628 - out * 30, x + 520, 632 - out * 30], fill=AMBER + (int(220 * layer_alpha),))
            return
        self.wipe_text(layer, (x, 360), "LIFTOFF THRUST", "bebas40", AMBER, (u - 0.05) / 0.35)
        self.wipe_text(layer, (x, 520), "7.5 MILLION", "anton150", WHITE, (u - 0.15) / 0.4)
        self.wipe_text(layer, (x, 600), "POUNDS  ·  FIVE F-1 ENGINES", "bebas48", WHITE, (u - 0.3) / 0.4, alpha=0.9)
        ln = ease_out((u - 0.2) / 0.6) * 520
        if ln > 0:
            d.rectangle([x, 628, x + ln, 632], fill=AMBER + (220,))

    def stat_speed(self, layer, d, u):
        if V20_HUD:          # v20: the same alpha and count curve (lines below), on a carry odometer
            a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.9) / 0.35))
            vc = 17400 + 6800 * ease_out((u - 0.4) / 1.2)
            self.h20.add("speed", u=u, a=a, vc=vc, val=int(round(vc / 10.0)) * 10)
            return
        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.9) / 0.35))    # v9: fade done before the 33.3 cut
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = np.clip(200 * (1 - np.hypot((xx - 200) / 1300, (yy - 900) / 650)), 0, 200).astype(np.uint8) * a
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        sc = 1.0 + 0.30 * (1 - ease_out(u / 0.25))
        tmp = Image.new("RGBA", (1300, 260), (0, 0, 0, 0))
        # v10: holds while the Earth slides in, counts over u 0.4-1.6 (ease-out), then holds; right-aligned, so "MPH"
        # stays put. v15: from 17,400 (Earth parking orbit before the burn: 25,567 ft/s = 17,432 mph), not from 0
        val = int(round((17400 + 6800 * ease_out((u - 0.4) / 1.2)) / 10.0)) * 10
        td = ImageDraw.Draw(tmp)
        nx = td.textlength("24,200", font=self.f["anton200"])
        td.text((nx, 200), f"{val:,}", font=self.f["anton200"], fill=WHITE + (int(255 * a),), anchor="rs")
        td.text((nx + td.textlength(" ", font=self.f["anton200"]), 200), "MPH", font=self.f["anton200"],
                fill=WHITE + (int(255 * a),), anchor="ls")
        if sc != 1.0:
            tmp = tmp.resize((int(1300 * sc), int(260 * sc)), Image.Resampling.BICUBIC)
            if u < 0.2:
                tmp = tmp.filter(ImageFilter.BoxBlur(int(8 * (1 - u / 0.2)) + 1))
        layer.alpha_composite(tmp, (120, int(930 - 200 * sc)))
        self.text(d, (124, 700), "SPEED AT TRANSLUNAR INJECTION CUTOFF", "bebas40", AMBER, "ls", a * ease_out((u - 0.2) / 0.4), track=4)
        # v15: where the count starts (baseline 1004: clear of the number's comma, inside title safe y <= 1026)
        self.text(d, (124, 1004), "FROM 17,400 IN EARTH ORBIT", "bebas40", (200, 210, 220), "ls",
                  a * 0.9 * ease_out((u - 0.3) / 0.4), track=4)

    def stat_distance(self, layer, d, u):
        if u >= 3.29:                              # v18m: hard cut on the 36.6 cut (frame 878, u 3.2917); v16b-v17 at 35.58
            return
        u -= 1.25                                  # v18m: in from 34.6 real (u 1.3), after the Egmont entry (34.0)
        if u <= 0:
            return
        a = ease_out(u / 0.4)                      # v18m: the scrim fades in with the text (v17: on from the cut)
        if V20_HUD and (V20_DISTANCE or V22_DISTANCE):     # v22: V22_DISTANCE (default False) = hud_v22's drum card
            self.h20.add("distance", u=u, a=a)
            return
        xl = 112
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = (np.clip(190 * (1 - np.hypot((xx - 300) / 1100, (yy - 860) / 420)), 0, 190) * a).astype(np.uint8)
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        self.wipe_text(layer, (xl, 716), "ABOUT", "bebas60", AMBER, (u - 0.05) / 0.3, anchor="ls", alpha=a)
        self.wipe_text(layer, (xl, 860), "240,000", "anton150", WHITE, (u - 0.1) / 0.4, anchor="ls", alpha=a)
        self.wipe_text(layer, (xl, 932), "MILES TO THE MOON", "bebas60", AMBER, (u - 0.25) / 0.4, anchor="ls", alpha=a)

    def contact_insert(self, layer, d, u):
        # v9: an annunciator, not a fade: dark, on at 0.12 s, a quick off/on flicker (0.25-0.33 s), then steady
        if self.v22():           # v22: hud_v22.render_contact (shared housing, 40 px left, same lamp timing)
            self.h20.add("contact", u=u)
            return
        on = u >= 0.12 and not (0.25 <= u < 0.33)
        cx, cy = W / 2, H / 2 - 40
        # v9: thin dark panel frame (bezel + four screws) around the lamp so it reads as a cockpit annunciator
        d.rounded_rectangle([cx - 336, cy - 136, cx + 336, cy + 136], radius=16, fill=(20, 22, 26, 255),
                            outline=(62, 64, 70, 255), width=3)
        for sx in (cx - 318, cx + 318):
            for sy in (cy - 118, cy + 118):
                d.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], fill=(80, 82, 88, 255))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        if on:
            gd.rounded_rectangle([cx - 330, cy - 120, cx + 330, cy + 120], radius=14, fill=(70, 150, 255, 200))
            layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(40)))
        d.rounded_rectangle([cx - 300, cy - 100, cx + 300, cy + 100], radius=10,
                            fill=(120, 190, 255, 255) if on else (26, 32, 44, 255), outline=(90, 90, 90, 255), width=4)
        self.text(d, (cx, cy - 22), "LUNAR", "bebas60", (10, 20, 40) if on else (70, 80, 95), "mm", 1.0, track=10)
        self.text(d, (cx, cy + 40), "CONTACT", "bebas60", (10, 20, 40) if on else (70, 80, 95), "mm", 1.0, track=10)

    def chapter(self, d, u):
        a = ease_out(u / 0.5) * (1 - ease_in_out((u - 3.2) / 0.5))
        if self.v22():
            self.h20.add("chapter", u=u, a=a)
            return
        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 84], fill=CYAN + (int(220 * a),))
        self.text(d, (x + 22, y - 4), "DAY 5  ·  JULY 20, 1969", "bebas48", WHITE, "la", a, track=4)
        self.text(d, (x + 22, y + 48), "LUNAR MODULE EAGLE  ·  POWERED DESCENT", "bebas34", CYAN, "la", a * 0.95, track=3)

    def label(self, d, u, head, sub):
        a = ease_out(u / 0.5) * (1 - ease_in_out((u - 3.3) / 0.5))
        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 84], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 22, y - 4), head, "bebas48", WHITE, "la", a, track=6)
        self.text(d, (x + 22, y + 48), sub, "bebas34", (200, 210, 220), "la", a * 0.95, track=3)

    def stage_label(self, d, u, dur):
        """v8: label over the staging shot, in label()'s style. v15: the shot is 0.75 s (src 940.75-941.5, the plume
        rising from bottom-left to mid-left): bebas72 (24 px at 640x360), right-aligned at x 1808 in the upper sky
        (y 150-222, clear of the plume on all 18 frames), fast
        in/out (0.12 / 0.14 s) so it holds ~0.5 s at full."""
        a = ease_out(u / 0.12) * (1 - ease_in_out((u - (dur - 0.14)) / 0.14))
        if self.v22():
            self.h20.add("stage", a=a)
            return
        s, f, track = "STAGE SEPARATION", "bebas72", 8
        if f not in self.f:
            self.f[f] = font("bebas", 72)
        tw = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
        x, y = round(1808 - (tw + 30)), 150
        d.rectangle([x, y, x + 8, y + 72], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 30, y - 3), s, f, WHITE, "la", a, track=track)

    def dsky(self, d, u, right: bool = False):
        # v17: out over the 6 frames before the LM-window cut (was 52.5-52.8, after it)
        a = min(1.0, u / 0.1) * (1 - ease_in_out((u + 47.2 - DSKY_OUT[0]) / (DSKY_OUT[1] - DSKY_OUT[0])))
        if V20_HUD:          # v20: the real DSKY (hud_v20.render_dsky); same window, side switch and fade
            self.h20.add("dsky", u=u, right=right, a=a)
            return
        x0, y0, x1, y1 = 112, 70, 560, 370
        if right:     # v11: over Mission Control the top-left panel sat on a controller's head; right side = shirts/desk
            x0, y0, x1, y1 = 1360, 460, 1808, 760     # v12: 40 px up (legend plate bottom 818, caption box top 892)
        d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=(14, 16, 14, int(215 * a)), outline=(90, 90, 80, int(255 * a)), width=2)
        self.text(d, (x0 + 20, y0 + 16), "LM GUIDANCE COMPUTER", "bebas34", (180, 180, 170), "la", a, track=3)
        blink = (int(u * 4) % 2 == 0) or u > 3.4
        lamp = AMBER if blink else (70, 50, 20)
        d.rectangle([x0 + 20, y0 + 56, x0 + 150, y0 + 104], fill=lamp + (int(255 * a),))
        self.text(d, (x0 + 85, y0 + 80), "PROG", "bebas40", (20, 14, 6), "mm", a)
        d.rectangle([x0 + 166, y0 + 56, x0 + 296, y0 + 104], fill=(70, 50, 20, int(255 * a)) if not blink else (60, 60, 56, int(255 * a)))
        self.text(d, (x0 + 231, y0 + 80), "KEY REL", "bebas34", (30, 30, 26), "mm", a)
        self.text(d, (x0 + 310, y0 + 60), "V05 N09", "mono34", GREEN, "la", a * 0.9)
        code = "01202" if (int(u * 6) % 3 != 0 or u > 2.0) else ""     # v9: flicker blanks (was "01 2 2")
        if right:     # v11: the legend sits over white shirts here: dark backing plate (x 1266-1808, v12: y 766-818)
            d.rounded_rectangle([1266, y1 + 6, x1, y1 + 58], radius=8,
                                fill=(0, 0, 0, int(160 * a * min(1.0, max(0.0, (u - 1.0) / 0.4)))))
        self.text(d, (x1 if right else x0, y1 + 46), "1202 = COMPUTER OVERLOADED", "bebas48", AMBER, "rs" if right else "ls", a * min(1.0, max(0.0, (u - 1.0) / 0.4)), track=3)
        self.text(d, (x1 - 24, y1 - 30), code, "seg120", GREEN, "rs", a)

    def fuel(self, d, t):
        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors (v16: get_at, shared with
        # the altitude readout; adds Aldrin's "40 feet" at 57.625)
        contact = 61.9               # v9: "Contact light" (logical): the counter stops here and holds
        held = t >= contact
        tg = min(t, contact)
        g = get_at(tg)
        rem = max(0.0, 62.0 - g)   # 60 s called at 102:45:02 -> bingo at 102:46:02
        a = min(1.0, (t - 55.6) / 0.3)      # v9: no fade-out; held over the lamp insert until the white frame
        if V20_HUD:          # v20: the MOCR monitor (hud_v20.render_crt); label as below
            if held:
                label = "CONTACT  ·  102:45:" + f"{int(g):02d}"
            else:
                label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
            self.h20.add("fuel", t=t, rem=rem, held=held, g=g, a=a, label=label.replace("  ·  ", " "))
            return
        x0, y0 = 1320, 120
        # v9: the number counts in the warning colour and the whole block turns white when the counter stops
        col = WHITE if held else (AMBER if rem > 30.05 else RED)
        if t < 61.79:              # v9: dark plate for the white shirts in Mission Control (not over the black insert)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 352], radius=12, fill=(0, 0, 0, int(150 * a)))
        self.text(d, (x0, y0), "SECONDS TO 'BINGO' · LAND OR ABORT", "bebas34", col, "la", a, track=3)
        self.text(d, (x0, y0 + 40), f"{rem:04.1f}", "anton150", col, "lt", a)
        self.text(d, (x0 + 300, y0 + 160), "SEC", "bebas40", col, "la", a)
        w = 380 * rem / 60.0
        d.rectangle([x0, y0 + 222, x0 + 380, y0 + 232], outline=col + (int(200 * a),), width=2)
        d.rectangle([x0, y0 + 222, x0 + w, y0 + 232], fill=col + (int(230 * a),))
        if held:
            label = "CONTACT  ·  102:45:" + f"{int(g):02d}"
        else:
            label = "ENGINE STOP" if g >= 44.0 else "GET 102:45:" + f"{int(g):02d}"
        self.text(d, (x0, y0 + 250), label, "mono34", WHITE, "la", a * (1.0 if held else 0.85))
        self.text(d, (x0, y0 + 296), "TIME-COMPRESSED", "bebas40", (190, 190, 190), "la", a * 0.8, track=3)

    def descent(self, d, t):
        """v16: Aldrin's altitude callouts as a live readout under the bingo counter (same x; plate 1300-1821 x
        492-828, caption box top >= 892). REAL values only: ALT ft, DOWN ft/s and FWD ft/s are each STEP-HELD at
        Aldrin's last stated value (CALLOUTS, from the Apollo Lunar Surface Journal) at the GET the shared dialogue map
        gives this frame (get_at, the bingo's clock: TIME-COMPRESSED, same label). Never interpolated; the bar eases
        0.2 s between called values. 40 FT from frame 1222 (tl 57.625), one frame before Aldrin's "40 feet". At
        "Contact light" (61.9) the block turns white like the bingo and reads CONTACT; the bar empties (nothing is
        called below 20 ft). No plate over the black insert (61.79+); cut by the white frame (62.9) with the bingo."""
        contact = 61.9
        held = t >= contact
        g = readout_get(min(t, contact))      # v17: caption-held steps (READOUT_HOLDS), not the raw GET map
        alt = down = fwd = fwd_now = None
        g_alt = prev_alt = None
        for cg, ca, cdn, cf in CALLOUTS:
            if cg <= g + 1e-6:
                if ca is not None:
                    prev_alt, alt, g_alt = alt, ca, cg
                if cdn is not None:
                    down = cdn
                if cf is not None:
                    fwd = cf
                fwd_now = cf          # v17: FWD only while the latest call states it
        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
        if V20_HUD:          # v20: the same values on the MOCR monitor (t_step / fresh as below)
            t_step = readout_step_t(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0
            fresh = (not held) and 0.0 <= t - t_step < 4 / 24
            self.h20.add("descent", alt=alt, prev_alt=prev_alt, down=down, fwd=fwd_now, held=held, fresh=fresh,
                         t_step=t_step, a=a)
            return
        x0, y0 = 1320, 510
        if "bebas72" not in self.f:
            self.f["bebas72"] = font("bebas", 72)
        if t < 61.79:              # dark plate for the 16mm dust and the white shirts in Mission Control (as the bingo)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 318], radius=12, fill=(0, 0, 0, int(150 * a)))
        lab = WHITE if held else AMBER
        # v17 (blind A/B on v16: tiny / cluttered at sheet size): the header is a small grey label; ALT anton150; one
        # DOWN line (bebas72 value); FWD on a second line only while the latest call states it; no TIME-COMPRESSED
        # label here (the bingo directly above carries it)
        self.text(d, (x0, y0), "ALDRIN'S CALLOUTS", "bebas34", (190, 190, 190), "la", a * 0.9, track=3)
        t_step = readout_step_t(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0
        fresh = (not held) and 0.0 <= t - t_step < 4 / 24          # a new called altitude flashes amber for 4 frames
        if held:
            self.text(d, (x0, y0 + 170), "CONTACT", "anton120", WHITE, "ls", a)
        else:
            nw = self.text(d, (x0, y0 + 170), f"{alt}", "anton150", AMBER if fresh else WHITE, "ls", a)
            self.text(d, (x0 + nw + 14, y0 + 170), "FT", "bebas60", AMBER, "ls", a, track=2)
        ra = a * (0.35 if held else 1.0)
        rows = [("DOWN", f"{down:.1f}" if down is not None else "-")]
        if fwd_now is not None and not held:
            rows.append(("FWD", f"{fwd_now:g}"))
        for k_, (name, val) in enumerate(rows):
            yb_ = y0 + 238 + 64 * k_
            x = x0
            x += self.text(d, (x, yb_), name, "bebas48", lab, "ls", ra, track=2) + 12
            x += self.text(d, (x, yb_), val, "bebas72", WHITE, "ls", ra) + 10
            self.text(d, (x, yb_), "FT/S", "bebas48", lab, "ls", ra, track=2)
        # altitude bar, 0-100 ft (gauge for the called value; eases 0.2 s from the previous call)
        bx0, bx1, by0, by1 = 1784, 1798, y0 + 14, y0 + 290
        col = WHITE if held else AMBER
        d.rectangle([bx0, by0, bx1, by1], outline=col + (int(200 * a),), width=2)
        if not held and alt is not None:
            k = ease_out((t - t_step) / 0.2) if prev_alt is not None and t_step > 0 else 1.0
            v = (prev_alt + (alt - prev_alt) * k) if prev_alt is not None else alt
            yb = by1 - (by1 - by0) * min(v, 100) / 100.0
            d.rectangle([bx0, yb, bx1, by1], fill=col + (int(230 * a),))
            d.rectangle([bx0 - 12, yb - 1, bx0 - 4, yb + 1], fill=col + (int(230 * a),))

    def chart(self, layer, d, u):
        a = min(1.0, u / 0.25) * (1 - ease_in_out((u - 2.3) / 0.3))
        X0, Y0, X1, Y1 = 230, 200, 1250, 860
        tmax, amax = 180.0, 50.0
        def px(tt, alt):
            return X0 + (X1 - X0) * tt / tmax, Y1 - (Y1 - Y0) * alt / amax
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = (np.clip(150 * (1 - xx / 1500), 0, 150) * a).astype(np.uint8)
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        self.text(d, (X0, Y0 - 70), "ASCENT  ·  FIRST 3 MINUTES", "bebas48", WHITE, "la", a, track=4)
        for v in (10, 20, 30, 40):
            _, yv = px(0, v)
            self.text(d, (X0 - 18, yv), f"{v} nmi", "body30", WHITE, "rm", a * 0.85)
            d.line([(X0, yv), (X0 + 14, yv)], fill=(255, 255, 255, int(160 * a)), width=2)
        for v in (0, 60, 120, 180):
            xv, _ = px(v, 0)
            self.text(d, (xv, Y1 + 18), f"T+{v}s", "body30", WHITE, "mt", a * 0.85)
        d.line([(X0, Y1), (X1, Y1)], fill=(255, 255, 255, int(150 * a)), width=2)
        p = ease_in_out((u - 0.15) / 1.85)
        tt = 40.0 + (tmax - 40.0) * p
        pts = [px(x, pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], x)) for x in np.linspace(0, tt, 160)]
        glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).line(pts, fill=AMBER + (int(170 * a),), width=16, joint="curve")
        layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(9)))
        d.line(pts, fill=(255, 214, 140, int(255 * a)), width=6, joint="curve")
        hx, hy = pts[-1]
        d.ellipse([hx - 10, hy - 10, hx + 10, hy + 10], fill=WHITE + (int(255 * a),))
        for (ct, cv) in PAO_PTS:
            if tt >= ct:
                cx, cy = px(ct, cv)
                d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=CYAN + (int(255 * a),), width=3)
        for (et, name) in [(83, "MAX Q"), (135, "INBOARD ENGINES OFF")]:
            if tt >= et:
                ex, ey = px(et, pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], et))
                d.line([(ex, ey - 16), (ex, ey - 70)], fill=CYAN + (int(200 * a),), width=2)
                self.text(d, (ex, ey - 78), name, "bebas34", CYAN, "ms", a, track=2)
        alt = pchip([q[0] for q in PAO_ALT], [q[1] for q in PAO_ALT], tt)
        vel = pchip([q[0] for q in PAO_VEL], [q[1] for q in PAO_VEL], tt) * 0.681818
        rx = 1360
        for i, (lab, val, unit) in enumerate([("MISSION TIME", f"T+{tt:.0f}", "S"), ("ALTITUDE", f"{alt:.1f}", "NMI"),
                                               ("VELOCITY", f"{vel:,.0f}", "MPH")]):
            yy0 = 240 + i * 200
            self.text(d, (rx, yy0), lab, "bebas40", AMBER, "la", a, track=3)
            vw = self.text(d, (rx, yy0 + 40), val, "anton96", WHITE, "lt", a)
            self.text(d, (rx + vw + 14, yy0 + 132), unit, "bebas40", AMBER, "ls", a)
        self.text(d, (X0, Y1 + 72), "DATA: NASA LAUNCH COMMENTARY  ·  ○ = VALUE CALLED OUT LIVE", "body30", WHITE, "la", a * 0.85)

    def credits(self, d, u):
        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 3.1) / 0.35))     # v18: out by 89.0 (real 82.3) for card 2
        # v10: three lines; the disclaimer ~20% larger (body41 vs body34); all inside title safe x 96-1824
        # v17 provenance: the launch/staging disclosure on its own line (joined it is wider than title safe); five
        # lines, steps 58/58/58/66; v17: block centred on the frame (first/last line centres 420/660, was centre 396)
        # v18: three lines (Connor: card 1 reduced to 3 short lines, ~3.5 s): sources + music; how it was made (AI loop,
        # 3D from NASA data, other-flight film: the staging shots also carry an on-screen ARCHIVE tag); NASA disclaimer
        # (v16b: NASA media guidelines: mark AI-made products, imply no NASA review or permission)
        # v20 (panel): the music line names the recordings (Musopen, PD worldwide: CREDITS.md); the NASA claim keeps
        # its own line. Four lines, first/last centres 447/633 (block centred on 540), widths 1189-1644 px (safe 1728)
        lines = [("NASA FILM, PHOTOS & MISSION AUDIO: PUBLIC DOMAIN", "body34", WHITE, 54),
                 ("MUSIC: DVOŘÁK, BEETHOVEN  ·  MUSOPEN RECORDINGS (PUBLIC DOMAIN)", "body34", WHITE, 62),
                 ("CUT BY AN AI AGENT (CLAUDE CODE)  ·  3D FROM NASA DATA  ·  SOME LAUNCH FILM FROM OTHER FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 447          # v20: four lines (v18-v19: three from 474)
        for s, f, c, step in lines:
            self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += step

    def credits2(self, d, u):
        """v17: second card (real 83.35-86.35, logical 90.05-93.05), house style (Anton name line, Bebas below),
        centred on y 540, inside title safe x 96-1824 (measured with the real fonts in the v17 dry run). In 0.35 s,
        out 2.5-2.9 (gone at real 86.25, before the Largo's fade ends at 86.3 and the 0.7 s of silence)."""
        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 4.05) / 0.4))     # v18: 4.45 s (v17: out 2.5-2.9)
        if a <= 0:
            return
        self.text(d, (W / 2, 432), "DIRECTED BY CONNOR KERSTING", "anton96", WHITE, "ms", a, track=4)
        d.rectangle([W / 2 - 60, 462, W / 2 + 60, 466], fill=AMBER + (int(220 * a),))
        self.text(d, (W / 2, 534), "M.S. BUSINESS ANALYTICS & ARTIFICIAL INTELLIGENCE CANDIDATE", "bebas48", WHITE, "ms", a, track=3)
        self.text(d, (W / 2, 592), "HASLAM COLLEGE OF BUSINESS  ·  THE UNIVERSITY OF TENNESSEE, KNOXVILLE", "bebas48",
                  (200, 210, 220), "ms", a, track=3)
        self.text(d, (W / 2, 660), "LINKEDIN.COM/IN/CONNORKERSTING", "bebas48", AMBER, "ms", a, track=4)
        self.text(d, (W / 2, 740), "PERSONAL PROJECT  ·  NOT AFFILIATED WITH OR ENDORSED BY UT OR NASA", "bebas40",
                  (190, 190, 190), "ms", a * 0.95, track=3)

    def caption(self, d, t):
        for t0, t1, who, s in CAPTIONS:
            if t0 <= t < t1:
                a = min(1.0, (t - t0) / 0.12, (t1 - t) / 0.12)
                f = self.f["body44"]
                tw = max(d.textlength(s, font=f), d.textlength(who, font=self.f["bebas40"]) + 4 * len(who))
                y = 984
                pad = 22
                top = y - (92 if who else 40)
                d.rounded_rectangle([W / 2 - tw / 2 - pad, top, W / 2 + tw / 2 + pad, y + 22], radius=8,
                                    fill=(0, 0, 0, int(165 * a)))
                d.text((W / 2, y), s, font=f, fill=WHITE + (int(255 * a),), anchor="ms")
                if who:
                    self.text(d, (W / 2, y - 48), who, "bebas40", AMBER, "ms", a, track=4)


# ---------------------------------------------------------------- stage B: compositor
def shot_at(t: float) -> Shot:
    """Shot on screen at time t, using the same frame-rounded cut points as the rendered segments."""
    fi = int(round(t * FPS))
    for s in SHOTS:
        if int(round(s.t0 * FPS)) <= fi < int(round(s.t1 * FPS)):
            return s
    return SHOTS[-1]


def make_lut() -> np.ndarray:
    x = np.linspace(0, 1, 256)
    s = x + 0.10 * np.sin(np.pi * x) * (x - 0.5) * 2          # gentle S-curve
    r = np.clip(s * 1.02 + 0.010 * (1 - x) ** 3 * -1, 0, 1)
    g = np.clip(s * 1.00 + 0.012 * (1 - x) ** 2, 0, 1)
    b = np.clip(s * 0.97 + 0.035 * (1 - x) ** 2, 0, 1)        # teal-ish shadows, warm-ish highlights
    return (np.stack([r, g, b], 1) * 255).astype(np.uint8)


def apply_push(fr: np.ndarray, z: float) -> np.ndarray:
    if abs(z - 1.0) < 1e-4:
        return fr
    im = Image.fromarray(fr)
    cw, ch = W / z, H / z
    x0, y0 = (W - cw) / 2, (H - ch) / 2
    return np.asarray(im.transform((W, H), Image.Transform.EXTENT, (x0, y0, x0 + cw, y0 + ch), Image.Resampling.BILINEAR))


def glitch(fr: np.ndarray, t: float, amt: float) -> np.ndarray:
    rng = np.random.default_rng(int(t * 1000))
    out = fr.copy()
    sh = int(6 + 22 * amt)
    out[:, :, 0] = np.roll(fr[:, :, 0], sh, axis=1)
    out[:, :, 2] = np.roll(fr[:, :, 2], -sh, axis=1)
    for _ in range(int(4 + 10 * amt)):
        y = int(rng.integers(0, H - 40))
        hgt = int(rng.integers(6, 60))
        dx = int(rng.integers(-120, 120) * amt)
        out[y:y + hgt] = np.roll(out[y:y + hgt], dx, axis=1)
    out[::3] = (out[::3].astype(np.uint16) * 7 // 10).astype(np.uint8)
    tint = np.array([1.075, 0.925, 0.925]) if rng.random() < 0.5 else np.array([1.0, 1.0, 1.0])   # v9: half the red
    return np.clip(out * tint, 0, 255).astype(np.uint8)


# v19: title placement in the comp (the Blender renders are untouched). (scale, anchor x, anchor y, new x, new y): the
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
    """3D title frame for time t (graded with the plate by the caller), or None."""
    if 13.0 <= t < 17.25:
        # v18: frames 0-102 of the v18 render; fades in over 0.4 s while it rises (v17 flew in from deep space)
        idx = title_idx(gfx.title, t - 13.0)          # v22: no clamp
        fade = ease_in_out((t - 13.0) / 0.4) * (1 - ease_in_out((t - 16.92) / 0.33))
    elif 83.4 <= t < 85.5:
        # v18: its own render, framed for the end card (v17: opening frames 12-62 scaled to 80%, shifted up 180 px)
        idx = (min(len(gfx.title_end) - 1, int((t - 83.4) * FPS * OUTRO_SETTLE)) if OUTRO_SETTLE   # v26: settle,
               else title_idx(gfx.title_end, t - 83.4))      # then hold still; v22: no clamp
        fade = min(1.0, (t - 83.4) / 0.15) * (1 - ease_in_out((t - 85.15) / 0.35))
        # v19 (R5): the plate is darkened BEFORE the title (Shot.bg_darken), so the v18 1.35x RGB lift is gone; the
        # title sits in the black sky between the Earth and the horizon (TITLE_END_FIT)
        ti = fit_title(Image.open(gfx.title_end[idx]).convert("RGBA"), TITLE_END_FIT)
    else:
        return None
    if t < 83.4:
        ti = fit_title(Image.open(gfx.title[idx]).convert("RGBA"), TITLE_OPEN_FIT)     # v19: more presence
    if fade < 1:
        ti.putalpha(Image.fromarray((np.asarray(ti.getchannel("A")) * max(0.0, fade)).astype(np.uint8)))
    return ti


def smoke_front(comp: np.ndarray, plate: np.ndarray, a_: np.ndarray) -> np.ndarray:
    """v9: 'smoke in front' for the opening title. A soft luma key of the plate's brightest smoke is laid back over
    the bottom ~30% of the letters at 35%, so the title sits IN the exhaust cloud rather than pasted on it.
    comp: titled frame (uint8 HxWx3); plate: the same frame before the title; a_: title alpha (HxWx1, 0..1)."""
    alpha = a_[..., 0]
    rows = np.flatnonzero(alpha.max(axis=1) > 0.05)
    if rows.size == 0:
        return comp
    y0, y1 = int(rows[0]), int(rows[-1])
    yb = y1 - 0.30 * (y1 - y0)                    # top of the bottom-30% band
    ramp = max(0.08 * (y1 - y0), 1.0)              # soft top edge
    band = np.clip((np.arange(H, dtype=np.float32) - yb) / ramp, 0, 1)[:, None]
    pf = plate.astype(np.float32)
    lum = pf @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    lo, hi = np.percentile(lum[::4, ::4], [70, 98])
    key = np.clip((lum - lo) / max(hi - lo, 1.0), 0, 1)
    key = key * key * (3 - 2 * key)
    key = np.asarray(Image.fromarray((key * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.Resampling.BILINEAR)
                     .filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.Resampling.BILINEAR), np.float32) / 255.0
    m = (0.35 * key * band * alpha)[..., None]
    smoke = np.asarray(Image.fromarray(plate).filter(ImageFilter.GaussianBlur(2)), np.float32)
    return np.clip(comp.astype(np.float32) * (1 - m) + smoke * m, 0, 255).astype(np.uint8)


# v18: the v16b asc_label_clean() hack is gone (ascent_blender_v5 keeps its labels inside the frame)
CARD2_T = 89.0      # v18: logical start of the creator card (real 82.3)


GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (49.0, 49.2, 1.0), (50.24, 50.36, 0.6)]   # v19: the last one follows the MC cut (frames 1045-1047; v18 50.6-50.72 = 1054-1056)


def stage_comp() -> None:
    validate_assets()            # v22 (R4): before any output is opened
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(SEG / "list.txt"), "-c", "copy",
         str(WORK / "base.mp4")])
    # v9: passthrough. ffmpeg's default CFR output re-timed the 1-frame WHITE segment (v8: white dropped, the black
    # insert frame duplicated, every frame after 56.2 one frame late, frame 1350 black).
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(WORK / "base.mp4"), "-fps_mode", "passthrough",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast", *IDR_ARGS,
                            "-pix_fmt", "yuv420p", str(WORK / "comp.mp4")], stdin=subprocess.PIPE)
    hashes: list[str] = []
    gfx = Gfx()
    lut = make_lut()
    rng = np.random.default_rng(7)
    grain = [rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32) for _ in range(12)]
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.28 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) ** 1.4
    vig = np.clip(vig, 0.55, 1).astype(np.float32)[..., None]
    fsize = W * H * 3
    for fi in range(NFRAMES):
        buf = dec.stdout.read(fsize)
        if len(buf) < fsize:     # v19b (Codex, R7): a short decode is an error, not black frames
            raise RuntimeError(f"stage_comp: base decode ended at frame {fi} of {NFRAMES} ({len(buf)} bytes)")
        fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        t = fi / FPS                 # REAL time: picture (shot_at, push, black_lead) and the end fade
        s = shot_at(t)
        # v8 LOGICAL (v7) time for graphics, captions, title, glitches and flashes. Frame-exact: from the Moon cut
        # (frame ACT2_F0 = 799) every frame is fi + 161 on the v7 grid (= t + 6.7 within 0.2 frame; t + 6.7 itself
        # would start every later window one frame after its cut).
        tl = t if fi < ACT2_F0 else (fi + ACT2_DF) / FPS
        if s.src not in ("STILL", "BLACK", "INSERT", "WHITE", "SEQ"):
            u = (t - s.t0) / max(s.t1 - s.t0, 1e-6)
            fr = apply_push(fr, s.push[0] + (s.push[1] - s.push[0]) * ease_in_out(u))
        if s.src == "SEQ":
            wr = np.random.default_rng(fi)
            dx, dy = wr.normal(0, 0.9), wr.normal(0, 0.7)
            pd_ = int(math.ceil(max(abs(dx), abs(dy)))) + 1
            padded = np.pad(fr, ((pd_, pd_), (pd_, pd_), (0, 0)), mode="edge")
            im_ = Image.fromarray(padded).filter(ImageFilter.GaussianBlur(0.7))
            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, pd_ + dx, 0, 1, pd_ + dy), Image.Resampling.BILINEAR))
            if V23_HUD and s.img.startswith(hud_v23.ASC_DIR):      # v23: 16 mm-matched grain on the CG globe
                fr = hud_v23.globe_grain(fr, fi)
        if s.bg_darken:                  # v19 (R5): darken the plate only; the title is laid in after this, undarkened
            fr = (fr.astype(np.float32) * (1 - s.bg_darken) + 0.5).astype(np.uint8)
        ttl = title_layer(gfx, tl)
        if ttl is not None:
            f0 = fr.astype(np.float32)
            ta = np.asarray(ttl, np.float32)
            a_ = ta[..., 3:4] / 255.0
            sh = np.asarray(ttl.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(10)).resize((W, H)), np.float32)[..., None] / 255.0
            sh = np.roll(np.roll(sh, 18, axis=0), 10, axis=1)
            f0 = f0 * (1 - TITLE_SHADOW * sh)       # v18: 0.20 (v17 0.55)
            plate_blur = np.asarray(Image.fromarray(fr).resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(4))
                                    .resize((W, H)), np.float32)
            edge = np.asarray(ttl.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6))
                              .resize((W, H)), np.float32)[..., None] / 255.0
            wrap = np.clip(a_ * (1 - edge), 0, 1)        # inner edge band of the letters (0 deep inside)
            title_rgb = ta[..., :3]   # light wrap dropped with the plate title (v6 A/B)
            plate0 = fr                                   # v9: the un-titled plate, for the smoke-in-front pass
            fr = np.clip(f0 * (1 - a_) + title_rgb * a_, 0, 255).astype(np.uint8)
            if 13.0 <= tl < 17.25:                        # v9: opening title only (the end card stays clean)
                fr = smoke_front(fr, plate0, a_)
        fr = np.stack([lut[fr[..., c], c] for c in range(3)], -1)
        f = fr.astype(np.float32)
        if s.darken:
            f *= 1 - s.darken
        if s.black_lead and int(round((t - s.t0) * FPS)) < s.black_lead:
            f *= 0.0
        # halation: blurred highlights, warm tint
        lum = f.mean(axis=2)
        hi = np.clip((lum - 170) / 85, 0, 1)
        if hi.max() > 0:
            small = Image.fromarray((hi * 255).astype(np.uint8)).resize((W // 8, H // 8), Image.Resampling.BILINEAR)
            small = small.filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.Resampling.BILINEAR)
            hal = np.asarray(small, np.float32)[..., None] / 255.0
            f += hal * np.array([60, 22, 8], np.float32)
        f *= vig
        for g0, g1, amt in GLITCH_WINDOWS:
            if g0 <= tl < g1:
                f = glitch(np.clip(f, 0, 255).astype(np.uint8), tl, amt).astype(np.float32)
        # flashes
        if 10.6 <= tl < 10.75:
            f += 255 * (1 - (tl - 10.6) / 0.15) * 0.9
        if s.src == "WHITE":            # one white frame between "Contact light" and "Houston, Tranquility Base"
            f = f * 0 + 255.0
        if 68.6 <= tl < 68.95:
            k = max(0.0, (tl - 68.68) / 0.27)
            f = f * 0 + 255 * (1 - k) ** 2
        if 69.6 <= tl < 70.2:
            f *= ease_in_out((tl - 69.6) / 0.6)
        if TOTAL - 0.5 <= t:            # real time against the v8 TOTAL
            f *= max(0.0, 1 - (t - (TOTAL - 0.5)) / 0.5)
        # graphics + title + captions on an RGBA layer
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hud = hud_v23 if V23_HUD else (hud_v22 if V22_HUD else (hud_v21 if V21_HUD else hud_v20))   # v21-v23
        if V25_HERO and V23_HUD and hud_v25.HERO_F[0] <= fi < hud_v25.HERO_F[1]:
            hud = hud_v25        # v25: hud_v23's items unchanged + the hero route / label (frames 715-798 only)
        gfx.h20 = hud.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw
        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        if gfx.h20 is not None and gfx.h20.items:      # v20: hardware HUD + film pass, under the captions layer
            f = hud.composite(f, gfx.h20)
        la = np.asarray(layer, np.float32)
        al = la[..., 3:4] / 255.0
        f = f * (1 - al) + la[..., :3] * al
        # grain over everything (luma-weighted)
        gr = grain[fi % len(grain)]
        gr = np.asarray(Image.fromarray(gr).resize((W, H), Image.Resampling.BILINEAR))[..., None]
        f += gr * 7.0
        out_ = np.clip(f, 0, 255).astype(np.uint8).tobytes()
        if FRAME_HASHES:
            hashes.append(hashlib.sha256(out_).hexdigest())
        enc.stdin.write(out_)
        if fi % 240 == 0:
            print(f"  frame {fi}/{NFRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    if FRAME_HASHES:
        Path(FRAME_HASHES).write_text(json.dumps(hashes), encoding="utf-8")
    print("comp written")


# ---------------------------------------------------------------- v2: public-domain score + Sonniss layer
if V24_POLISH and V26_POLISH2 and V26_DISCLOSURE and V27_FIXES:    # v27: the caption out-point at the end-plate cut
    polish_v27.apply_caption(Gfx, ACT2_F0, ACT2_DF, FPS)
from score_pd import USE_PD, stage_music  # noqa: E402  (tables live in score_pd.py)


# ---------------------------------------------------------------- mix + export
def synth_sfx_v8() -> np.ndarray:
    """The synth SFX stem was rendered for the 88.5 s cut: drop old 33.3-40.0 so later cues shift -6.7 s."""
    old = load_stem(AUD / "sfx.wav")             # padded/truncated to the CURRENT TOTAL by load_stem
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(AUD / "sfx.wav"), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    full = np.frombuffer(raw, np.float32).reshape(-1, 2)
    a0, a1 = int(33.3 * SR), int(40.0 * SR)
    xf = int(0.02 * SR)
    head = full[:a0].copy()
    tail = full[a1:].copy()
    ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
    head[-xf:] = head[-xf:] * (1 - ramp) + tail[:xf] * ramp
    out = np.concatenate([head, tail[xf:]])
    n = len(old)
    res = np.zeros_like(old)
    res[:min(n, len(out))] = out[:n]
    # v11: the old stem's 1202-alarm cue starts on two hard steps 10 ms apart (old 47.01 / 47.02 s -> 40.29 / 40.30
    # here; v10 QC's "40.30 riser click"). Declick: 5 ms fade-out into the first step, silent to the last step,
    # 12 ms fade-in after it (steps = sample jumps > 0.02 within 20 ms of the first one in 40.25-40.35).
    k0 = int(40.25 * SR)
    jumps = k0 + 1 + np.flatnonzero(np.abs(np.diff(res[k0:int(40.35 * SR)], axis=0)).max(axis=1) > 0.02)
    if jumps.size:
        a_ = int(jumps[0])
        b_ = int(jumps[jumps <= a_ + int(0.02 * SR)][-1])      # the edit's steps only (not the cue's own waveform)
        fo, fi = int(0.005 * SR), int(0.012 * SR)
        res[a_ - fo:a_] *= np.linspace(1, 0, fo, dtype=np.float32)[:, None]
        res[a_:b_] = 0.0
        res[b_:b_ + fi] *= np.linspace(0, 1, fi, dtype=np.float32)[:, None]
    return res


SFX_UNDUCK = [(56.15, 56.45, 0.15)]      # v17: (start, end, release s), see stage_mix
BED_DIP = [(10.6, 19.0, -1.5)]           # v17: (start, end, dB) on music + SFX


REUSE_AUDIO_FROM = OUT / "moonshot_v22.mp4"   # v23: v22's AAC stream (= v21's); None = compute the mix as v21
REUSE_AUDIO_MD5 = "b489934da50e9c2ee4acce2f94f712ae"    # v23 (Codex v22 high): the approved stream's packet md5
REUSE_AUDIO_DUR = 87.5                                   # seconds (AAC stream duration, ffprobe)
V24_SOUND = True          # v24: the sound-arc master (sound_v24.py) instead of the reused v22 stream; False: v23 exactly
V24_MASTER = WORK / "audio_v24" / "master_v24b.wav"      # 48 kHz stereo float32 PCM, 87.5 s
V24_AAC_EXTRA = ['-cutoff', '20000']     # extra AAC encoder options (v24b: -cutoff 20000)
V24_MASTER_SHA256 = "628c20fbd589081a0d4888091080ba14cb2450f1412423958ce277e22d296a26"
V24_MASTER_SAMPLES = 4200000
V24_AUDIO_MD5 = "444fc52b25750b4840ddb349d3ede039"     # packet md5 of its AAC 320k encode (ffmpeg 8.1.2)
V24_PICTURE_FROM = None   # lead: v24 = v23 + the v26 visor scan + polish_v24, so its picture changes: encode WORK/comp.mp4
V24_PICTURE_MD5 = "540d2c716f991b97a9487f1f1ae1cba5"     # v23's video packet md5


def v24_master_check() -> None:
    """v24: the master is authenticated by content (sha256 + sample count), not by its name."""
    if not V24_MASTER.is_file():
        raise SystemExit(f"V24_MASTER {V24_MASTER} missing (run sound_v24.py)")
    h = hashlib.sha256()
    with open(V24_MASTER, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    if h.hexdigest() != V24_MASTER_SHA256:
        raise SystemExit(f"V24_MASTER sha256 {h.hexdigest()}, pinned {V24_MASTER_SHA256}")
    ts = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration_ts",
                         "-of", "csv=p=0", str(V24_MASTER)], capture_output=True, text=True).stdout.strip()
    if ts != str(V24_MASTER_SAMPLES):
        raise SystemExit(f"V24_MASTER: {ts or '(none)'} samples, pinned {V24_MASTER_SAMPLES}")


def video_md5(path: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"],
                         capture_output=True, text=True)
    return out.stdout.strip().removeprefix("MD5=") if out.returncode == 0 else ""


def mux_v24_master() -> None:
    """v24: picture (stream copy of V24_PICTURE_FROM, verified; or WORK/comp.mp4 encoded as mux_reused_audio does) +
    the AAC 320k encode of the pinned master. .part file -> frames, audio md5 + duration, (copied) video md5 -> rename."""
    v24_master_check()
    if V24_PICTURE_FROM is not None and video_md5(V24_PICTURE_FROM) != V24_PICTURE_MD5:
        raise SystemExit(f"V24_PICTURE_FROM {V24_PICTURE_FROM}: video packet md5 is not the pinned v23 picture")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"moonshot_v{VERSION}.mp4"
    if dst.exists():
        raise SystemExit(f"{dst} exists; versions are never overwritten")
    part = dst.with_name(dst.stem + ".part.mp4")
    if V24_PICTURE_FROM is not None:
        vin, vargs = str(V24_PICTURE_FROM), ["-c:v", "copy"]
    else:
        vin = str(WORK / "comp.mp4")
        vargs = ["-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS, "-pix_fmt", "yuv420p", "-r", str(FPS),
                 "-vf", "setsar=1", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                 "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", vin, "-i", str(V24_MASTER), "-map", "0:v:0", "-map", "1:a:0", *vargs,
             "-c:a", "aac", "-b:a", "320k", *V24_AAC_EXTRA, "-movflags", "+faststart", str(part)])
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", str(part)],
                                 capture_output=True, text=True).stdout.strip() or 0)
        if got != NFRAMES:
            raise SystemExit(f"mux: {part.name} decodes to {got} frames, expected {NFRAMES}; deleted")
        if audio_md5(part) != V24_AUDIO_MD5:
            raise SystemExit(f"mux: {part.name} audio is not the pinned v24 encode (encoder changed?); deleted")
        if audio_streams(part) != 1:      # v23b rule: exactly one (authenticated) audio stream
            raise SystemExit(f"mux: {part.name} has {audio_streams(part)} audio streams, expected exactly 1; deleted")
        dur = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                              "-of", "csv=p=0", str(part)], capture_output=True, text=True).stdout.strip()
        if not dur or abs(float(dur) - TOTAL) > 0.001:
            raise SystemExit(f"mux: {part.name} audio {dur or '(none)'} s, expected {TOTAL}; deleted")
        if V24_PICTURE_FROM is not None and video_md5(part) != V24_PICTURE_MD5:
            raise SystemExit(f"mux: {part.name} video packets differ from the copied picture; deleted")
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)
    print(f"wrote {dst} (v24 master AAC, md5 + {NFRAMES} frames verified; picture "
          f"{'stream-copied from ' + V24_PICTURE_FROM.name if V24_PICTURE_FROM else 'encoded from comp.mp4'})")


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


def audio_streams(path: Path) -> int:
    """v23b: the number of audio streams in path."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of",
                          "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return len([x for x in out.split() if x.strip()])


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
             "-map", "0:v", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS,
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
        if audio_streams(part) != 1:     # v23b (Codex): no second, unauthenticated audio track can ride along
            raise SystemExit(f"mux: {part.name} has {audio_streams(part)} audio streams, expected exactly 1; deleted")
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)
    print(f"wrote {dst} (audio stream copied from {src.name}, md5 + {NFRAMES} frames verified)")


def stage_mix() -> None:
    if V24_SOUND:                         # v24: the sound-arc master (verified) instead of the v22 stream
        mux_v24_master()
        return
    if REUSE_AUDIO_FROM is not None:      # v22 (R2)
        mux_reused_audio(REUSE_AUDIO_FROM)
        return
    n = int(TOTAL * SR)
    dlg = np.fromfile(AUD / "dialog.f32", np.float32)[:n]
    act = np.fromfile(AUD / "dialog_active.f32", np.float32)[:n]
    # pre-roll: start ducking 200 ms before each line so the music is fully down when speech starts
    pre = int(0.20 * SR)
    onsets = np.flatnonzero(np.diff(act, prepend=0.0) > 0.5)
    for o in onsets:
        act[max(0, o - pre):o] = 1.0
    if USE_PD:
        music = np.fromfile(AUD / "music_pd.f32", np.float32).reshape(-1, 2)[:n]
        sfx = (np.fromfile(AUD / "sonniss.f32", np.float32).reshape(-1, 2)[:n]
               + synth_sfx_v8() * 10 ** (-4.0 / 20))
    else:
        music = load_stem(AUD / "music.wav")
        sfx = load_stem(AUD / "sfx.wav")
    # ADAPTIVE ducking (v5): per dialogue line, measure the line and the un-ducked bed, then duck as deep as
    # needed for dialogue >= +12 dB over the bed (min 10 dB, max 22 dB; the 10.6-11.4 ignition hit keeps its punch).
    def rms_db(x: np.ndarray) -> float:
        return float(20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))
    pre_bed = music + sfx                       # stereo: rms_db averages both channels (no mono fold-down; Codex #2)
    target = np.zeros(n, np.float32)            # desired duck depth in dB (positive)
    duck_log = []
    for src, a_, b_, t, g in DIALOG:
        i0, i1 = int(t * SR), min(int((t + b_ - a_) * SR), n)
        need = rms_db(pre_bed[i0:i1]) - rms_db(dlg[i0:i1]) + 12.0
        depth = float(np.clip(need, 10.0, 22.0))
        j0, j1 = max(0, i0 - int(0.20 * SR)), min(n, i1 + int(0.10 * SR))
        target[j0:j1] = np.maximum(target[j0:j1], depth)
        duck_log.append(f"{t:6.2f} {Path(src).name[:18]:18s} need {need:5.1f} dB -> duck {depth:4.1f} dB")
    print("  adaptive duck:")
    for line in duck_log:
        print("   ", line)
    step = 48
    ctrl = target[::step]
    env_db = np.zeros_like(ctrl)
    lvl = 0.0
    k_att, k_rel = step / (0.06 * SR), step / (0.40 * SR)
    for i, c in enumerate(ctrl):
        lvl += (c - lvl) * (k_att if c > lvl else k_rel)
        env_db[i] = lvl
    env_db = np.repeat(env_db, step)[:n]
    # the ignition hit keeps its punch: cap only 10.6-11.4 s, after smoothing (Codex #1: the cap used to
    # apply to the whole 0-18.9 s countdown entry)
    # hype lines keep the music up (captions carry the words): cap the duck depth in these windows
    for c0s, c1s, cap in ():   # v9: caps removed (they buried the launch lines; clarity first)
        c0, c1 = int(c0s * SR), int(c1s * SR)
        env_db[c0:c1] = np.minimum(env_db[c0:c1], cap)
    gain = (10 ** (-env_db / 20)).astype(np.float32)
    sgain = gain                                # SFX get the full computed depth (Codex #3)
    for i0s, i1s in ():   # v9: impacts duck with the bed (unducking buried the launch lines)
        sgain = sgain.copy()
        sgain[int(i0s * SR):int(i1s * SR)] = 1.0
    # v17: SFX windows that escape the duck (start, end, release s): the touchdown impact on the 56.2 white flash sits in
    # the "Contact light" release / "Houston" pre-roll (~15-19 dB of duck); 20 ms in, cosine back to the duck by 56.6,
    # before Armstrong's first word (~56.7)
    tt_ = np.arange(n) / SR
    for u0, u1, rel in SFX_UNDUCK:
        w_ = np.interp(tt_, [u0 - 0.02, u0, u1, u1 + rel], [0.0, 1.0, 1.0, 0.0]).astype(np.float32)
        w_ = 0.5 - 0.5 * np.cos(np.pi * w_)
        sgain = sgain + (1.0 - sgain) * w_
    bed = music * gain[:, None] + sfx * sgain[:, None]
    # v17: the title bed (music + SFX, 10.6-19.0) -1.5 dB (ramps 10.50-10.58 and 19.0-19.4), dialogue untouched, so the
    # touchdown is the loudest moment (Fable editor on v16)
    for d0, d1, ddb in BED_DIP:
        bed *= (10 ** (np.interp(tt_, [d0 - 0.10, d0 - 0.02, d1, d1 + 0.4], [0.0, ddb, ddb, 0.0]) / 20)).astype(np.float32)[:, None]
    mix = bed + dlg[:, None] * 1.0
    bed.mean(axis=1).astype(np.float32).tofile(AUD / f"bed_v{VERSION}.f32")      # for audio_qc.py
    dlg.astype(np.float32).tofile(AUD / f"dlg_v{VERSION}.f32")
    # faint room tone in the post-flash silence (critic: dead digital zero reads as a playback fault)
    rng = np.random.default_rng(3)
    i0, i1 = int(61.92 * SR), int(63.5 * SR)       # v17: to 63.5 (the Largo fades in from 62.9); v8 61.92-62.9
    tone = rng.normal(0, 1, (i1 - i0, 2)).astype(np.float32)
    tone = np.cumsum(tone, axis=0)
    tone -= np.linspace(tone[0], tone[-1], len(tone))
    tone *= 10 ** (-52 / 20) / max(np.sqrt(np.mean(tone ** 2)), 1e-9)
    fo_ = int(0.4 * SR)                            # v17: 0.4 s fade-out under the Largo
    tone[-fo_:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo_, dtype=np.float32)))[:, None]
    mix[i0:i1] += tone
    peak = np.max(np.abs(mix))
    mix = mix / max(peak, 1e-6) * 0.7
    mix.astype(np.float32).tofile(AUD / "mix.f32")
    run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(AUD / "mix.f32"),
         "-c:a", "pcm_s24le", str(AUD / "mix_raw.wav")])
    # two-pass loudnorm to -14 LUFS / -1 dBTP
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(AUD / "mix_raw.wav"), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    af = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true,"
          f"aresample=48000")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(AUD / "mix_raw.wav"), "-af", af, "-c:a", "pcm_s24le", str(AUD / "mix_norm.wav")])
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"moonshot_v{VERSION}.mp4"
    if dst.exists():
        raise SystemExit(f"{dst} exists; versions are never overwritten")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(WORK / "comp.mp4"), "-i", str(AUD / "mix_norm.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-r", str(FPS), "-vf", "setsar=1", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
         "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", "-shortest", str(dst)])
    print(f"wrote {dst}")


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    preflight(stage)          # v23 (Codex v22): every manifested asset + the reused audio, before anything is written
    if stage in ("shots", "all"):
        stage_shots()
    if stage in ("dialog", "all"):
        stage_dialog()
    if stage in ("music", "all"):
        stage_music()
    if stage in ("comp", "all"):
        stage_comp()
    if stage in ("mix", "all"):
        stage_mix()
