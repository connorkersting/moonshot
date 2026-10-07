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

import json
import math
import subprocess
import sys
from dataclasses import dataclass, field
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = CRAFTWORK
INBOX = ROOT / "inbox" / "moonshot"
WORK = INBOX / "work"
SEG = WORK / "seg"
AUD = WORK / "audio"
OUT = ROOT / "exports" / "moonshot" / "versions"
FONTS = ROOT / "fonts"
W, H, FPS = 1920, 1080, 24
TOTAL = 81.8            # v8: act 2 is 6.7 s shorter (v7: 88.5)
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
    "L70": "eq=contrast=1.12:saturation=1.05:gamma=0.97,colorbalance=rs=0.05:gs=0.0:bs=-0.06:rh=0.04:bh=-0.04",
    "BR": "hqdn3d=1.5:1.5:3:3,eq=contrast=1.10:saturation=1.08,unsharp=5:5:0.6",
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
    Shot(8.40, 9.40, "BR", 694.0, push=(1.06, 1.0), note="back to the firing room"),
    Shot(9.40, 10.60, "BR", 691.78, speed=0.66, push=(1.0, 1.10), note="engine bells (0.8 s shot, slowed)"),
    # BEAT DROP
    Shot(10.60, 11.80, "SV", 34.2, push=(1.12, 1.0), note="ignition fireball, high-speed camera"),
    Shot(11.80, 13.00, "L70", 16.6, crop="1300:731:256:700", push=(1.0, 1.06), note="Apollo 11 70mm: flames at the base, wide"),
    Shot(13.00, 17.60, "L70", 18.0, speed=0.5, crop="1220:686:520:980", push=(1.0, 1.08), darken=0.25, note="smoke under the title (v9: recrop, no pole through the M, clear of the gate corner)"),
    Shot(17.60, 19.00, "SV", 100.0, push=(1.0, 1.05), note="rocket climbs past the tower"),
    # ACT 2 (v8: 19.0-33.3, was 19.0-40.0): thrust stat, 3D ascent, staging, interstage, TLI speed
    Shot(19.00, 22.00, "SV", 70.0, push=(1.0, 1.06), darken=0.1, note="F-1 engine bells (stat 1)"),
    Shot(22.00, 26.50, "SEQ", 1.0, speed=1.77, img="ascent_blender_v4/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values (108 fr x 1.77 = 191 of 192)"),
    Shot(26.50, 28.00, "BRD", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky (STAGE SEPARATION label)"),
    Shot(28.00, 29.80, "BRD", 961.0, push=(1.0, 1.08), note="interstage falls away over Earth"),
    Shot(29.80, 33.30, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.55)), note="Apollo 11 Earth on translunar coast, pulling away (stat: TLI speed)"),
    # LUNAR TRANSITION
    Shot(33.30, 37.30, "SEQ", img="moon_blender/moon_%04d.png", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer"),
    # ACT 3: descent
    Shot(37.30, 40.30, "STILL", img="as11-44-6581.jpg", kb=((0.5, 0.48, 1.25), (0.5, 0.5, 1.45)), note="Eagle undocked"),
    Shot(40.30, 42.30, "BR", 1254.0, push=(1.0, 1.06), note="descent, LM window"),
    Shot(42.30, 43.90, "BR", 1258.5, push=(1.0, 1.08), note="descent, LM window (Eagle: 1202)"),
    Shot(43.90, 46.10, "BR", 1251.0, push=(1.0, 1.06), note="Mission Control (Eagle asks for a reading); source cuts back to the LM window at frame 1096 (real 45.667)"),
    Shot(46.10, 48.30, "BR", 1248.55, speed=0.85, push=(1.0, 1.05), note="controller points: we're go (Houston)"),
    Shot(48.30, 50.70, "BR16L", 1345.5, push=(1.0, 1.06), note="16mm descent, final approach"),
    Shot(50.70, 53.50, "BR16L", 1360.2, push=(1.0, 1.08), note="16mm: dust (Aldrin's calls)"),
    Shot(53.50, 55.10, "BR", 1237.5, push=(1.0, 1.05), note="Mission Control consoles, tense (Houston: 30 seconds)"),
    Shot(55.10, 56.20, "INSERT", note="CONTACT LIGHT lamp insert (graphic)"),
    Shot(56.20, 56.26, "WHITE"),
    Shot(56.26, 59.70, "BR16H", 1399.0, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed (v12: out at 59.70, 0.70 s earlier for the reaction)"),
    Shot(59.70, 61.90, "BR", 1279.49, push=(1.0, 1.04), note="Mission Control: the reaction, 2.20 s (v12: in 1279.49 = 1280.2 - 17/24; source shot starts at 1279.40)"),
    Shot(61.90, 62.90, "BLACK"),
    # OUTRO
    Shot(62.90, 67.30, "SEQ", 1.0, img="px_earthrise_v2/px_%04d.png", note="Apollo 11 Earthrise: Blender parallax (3 PIL depth planes), Earth rises"),
    Shot(67.30, 70.90, "BR16", 1409.0, push=(1.0, 1.08), note="Armstrong on the ladder (TV), lifted"),
    Shot(70.90, 72.675, "SEQ", 1.0, img="px_aldrin/px_%04d.png", note="Aldrin: Blender parallax, opens on the visor, pushes into the reflection"),
    Shot(72.675, 76.70, "STILL", img="as11-40-5878.jpg", kb=((0.62, 0.62, 1.25), (0.62, 0.62, 1.6)), note="bootprint (one giant leap)"),
    Shot(76.70, 78.80, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.04)), darken=0.35, note="end title: Earth high, LM low (inside safe)"),
    Shot(78.80, 81.80, "BLACK", note="credits"),
]

PAO = INBOX / "audio" / "alsj_a11a1023114-4746_PAO.mp3"
RST = WORK / "restore"
# (source, src_in, src_out, timeline_t, gain_db). v2: restored windows (craft_tools.restore audio).
# Window offsets: pao_alarm = PAO from 420 s, pao_land = PAO from 815 s, countdown = activities_tail from 240 s.
DIALOG = [
    (RST / "countdown.wav", 12.0, 22.5, 0.0, -9.0),     # "10 ... ignition sequence starts ... 1" (v10: -5 dB, the drop hits harder)
    (RST / "countdown.wav", 25.0, 31.15, 11.2, -0.5),    # "liftoff! we have a liftoff, 32 minutes past the hour" (v10: was 13.0 @ -2.0; "zero, all engines running" cut; +1.5 dB: duck is maxed under the title hits)
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
    (47.20, 48.15, "EAGLE · ARMSTRONG", "Program alarm."),
    (48.30, 49.40, "EAGLE · ARMSTRONG", "It's a 1202."),
    (49.50, 50.40, "EAGLE · ALDRIN", "1202."),
    (50.50, 52.75, "EAGLE · ARMSTRONG", "Give us a reading on the 1202 program alarm."),
    (52.90, 55.55, "HOUSTON · DUKE", "Roger. We got you... We're go on that alarm."),
    (55.70, 57.30, "HOUSTON · DUKE", "60 seconds."),
    (57.50, 60.15, "EAGLE · ALDRIN", "40 feet, down 2½. Picking up some dust."),
    (60.30, 61.75, "HOUSTON · DUKE", "30 seconds."),
    (61.90, 62.85, "EAGLE · ALDRIN", "Contact light."),
    (63.40, 65.20, "EAGLE · ARMSTRONG", "Houston, ..."),                 # v10: real 56.7-58.5 ("Houston, uh")
    (65.60, 66.85, "EAGLE · ARMSTRONG", "Tranquility Base here."),       # v10: real 58.9-60.15
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
          f"[0:v]fps={FPS},format=rgba,colorkey=black:0.02:0.0[mo];[st][mo]overlay=shortest=1:format=rgb,format=yuv420p")
    start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []
    if s.img.startswith("px_"):
        run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i",
             str(WORK / s.img), "-vf", f"fps={FPS},format=yuv420p", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])
        return
    run(["ffmpeg", "-v", "error", "-y", "-framerate", f"{FPS * s.speed:g}", *start, "-i", str(WORK / "blender" / "..") + "/" + s.img,
         "-loop", "1", "-framerate", str(FPS), "-i", str(WORK / "blender" / "stars.png"),
         "-filter_complex", fc, "-frames:v", str(n), "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])


def render_video_shot(s: Shot, path: Path) -> None:
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


def stage_dialog() -> None:
    AUD.mkdir(parents=True, exist_ok=True)
    out = np.zeros(int(TOTAL * SR), np.float32)
    active = np.zeros(int(TOTAL * SR), np.float32)
    for src, a, b, t, g in DIALOG:
        x = load_audio(src, a, b)
        x = biquad(x, "hp", 120.0)
        x = biquad(x, "lp", 7000.0)
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

EARTH_LIMB_X = 1040   # Earth's right limb on the as11-36-5355 plate after the push (v7 37-40 s; v8 29.8-33.3; unused)
TITLE_DIR = "title3d_blender"   # steel; v6 plate-lit title lost its blind A/B   # v3: Blender steel title (v2 used "title3d_v2", EffectCraft)
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

DSKY_RIGHT_T = 50.62     # v11: logical time of the cut to Mission Control (s23, frame 1054 -> tl 50.625, under the 50.6 glitch)
DSKY_LEFT_T = 52.37      # v12: s23's source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again


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
        self.title = sorted((WORK / TITLE_DIR).glob("title_*.png"))

    # -- shared primitives
    def text(self, d: ImageDraw.ImageDraw, xy, s, f, fill, anchor="la", alpha=1.0, track=0):
        col = fill + (int(255 * alpha),)
        if track:
            x, y = xy
            total = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
            if anchor[0] == "m":
                x -= total / 2
            elif anchor[0] == "r":
                x -= total
            for c in s:
                d.text((x, y), c, font=self.f[f], fill=col, anchor="l" + anchor[1])
                x += d.textlength(c, font=self.f[f]) + track
            return total
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
        if 0.0 <= t < 13.0 or 44.0 <= t < 47.0:
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
        if 26.5 <= t < 28.0:     # v8: staging shot (before ACT2_T0, logical time == real time)
            self.stage_label(d, t - 26.5, 1.5)
        if round(29.8 * FPS) / FPS <= t < ACT2_T0:     # v8: over the as11-36-5355 still (cut 29.8 = frame 715)
            self.stat_speed(layer, d, t - round(29.8 * FPS) / FPS)
        if 40.0 <= t < 44.0:
            self.stat_distance(layer, d, t - 40.0)
            ar = min(1.0, (t - 40.2) / 0.4) * (1 - ease_in_out((t - 43.4) / 0.4))

        if 44.0 <= t < 47.0:
            self.chapter(d, t - 44.0)
        if 69.8 <= t < 73.6:
            self.label(d, t - 69.8, "EARTHRISE", "PHOTOGRAPHED FROM APOLLO 11 · JULY 1969")
        if 47.2 <= t < 52.8:
            self.dsky(d, t - 47.2, right=DSKY_RIGHT_T <= t < DSKY_LEFT_T)
        if 55.6 <= t < 62.9:      # v9: the bingo HUD holds over the CONTACT insert, cut by the white frame
            self.fuel(d, t)
        if False:   # v7: end card is over the photo again (stars only for the old black card)
            st = Image.open(WORK / "blender" / "stars.png").convert("RGB").crop((100, 60, 100 + W, 60 + H))
            sa = np.asarray(st, np.uint8)
            stars = np.dstack([sa, (sa.max(axis=2) * 0.8).astype(np.uint8)])
            layer.alpha_composite(Image.fromarray(stars, "RGBA"))
        if 83.9 <= t < 85.5:
            a = ease_out((t - 83.9) / 0.5) * (1 - ease_in_out((t - 85.15) / 0.35))
            self.text(d, (W / 2, 510), "APOLLO 11  ·  JULY 16–24, 1969", "bebas48", WHITE, "mm", a, track=6)
        if 85.55 <= t < 88.5:
            self.credits(d, t - 85.55)

    def countdown_hud(self, d, t, layer=None):
        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))
        # the readout follows the SPOKEN count (the picture already cuts on the voice)
        spoken = [(0.2, 10), (1.2, 9), (2.2, 8), (3.5, 7), (4.8, 6), (5.6, 5), (6.6, 4), (7.4, 3), (8.4, 2), (9.4, 1), (10.6, 0)]
        n, n_ts = 10, 0.2
        for ts, k in spoken:
            if t >= ts:
                n, n_ts = k, ts
        s = f"T − 00:00:{n:02d}" if t < 10.6 else f"T + 00:00:{int(t - 10.6):02d}"
        x, y = 112, 70
        d.rectangle([x, y, x + 6, y + 64], fill=AMBER + (int(230 * a),))
        site = 0.0 if 3.9 <= t < 8.4 else 1.0
        self.text(d, (x + 20, y - 4), "APOLLO 11  ·  LAUNCH COMPLEX 39A", "bebas34", AMBER, "la", a * 0.95 * site, track=3)
        self.text(d, (x + 20, y + 32), s, "mono34", WHITE, "la", a)
        if layer is not None:
            self.countdown_numeral(layer, t, n, n_ts)

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
        out = ease_in_out((u - 2.6) / 0.35)
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
        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.9) / 0.35))    # v9: fade done before the 33.3 cut
        g = np.zeros((H, W, 4), np.uint8)
        yy, xx = np.mgrid[0:H, 0:W]
        g[..., 3] = np.clip(200 * (1 - np.hypot((xx - 200) / 1300, (yy - 900) / 650)), 0, 200).astype(np.uint8) * a
        layer.alpha_composite(Image.fromarray(g, "RGBA"))
        sc = 1.0 + 0.30 * (1 - ease_out(u / 0.25))
        tmp = Image.new("RGBA", (1300, 260), (0, 0, 0, 0))
        # v10: holds 0 while the Earth slides in, counts 0 -> 24,200 over u 0.4-1.6 (ease-out), then holds;
        # right-aligned, so "MPH" stays put
        val = int(round(24200 * ease_out((u - 0.4) / 1.2) / 10.0)) * 10
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

    def stat_distance(self, layer, d, u):
        a = 1 - ease_in_out((u - 2.6) / 0.4)
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
        """v8: small lower third over the staging shot, in label()'s style. Bottom-RIGHT inside safe (x <= 1808):
        the exhaust plume wanders over the left half of this shot (checked on v7 frames 30.1-31.4)."""
        a = ease_out(u / 0.3) * (1 - ease_in_out((u - (dur - 0.35)) / 0.35))
        s, f, track = "STAGE SEPARATION", "bebas48", 6
        tw = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
        x, y = 1808 - 22 - tw, 900
        d.rectangle([x, y, x + 6, y + 48], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 22, y - 2), s, f, WHITE, "la", a, track=track)

    def dsky(self, d, u, right: bool = False):
        a = min(1.0, u / 0.1) * (1 - ease_in_out((u - 5.3) / 0.3))
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
        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors
        anchors = [(55.7, 2.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
        contact = 61.9               # v9: "Contact light" (logical): the counter stops here and holds
        held = t >= contact
        tg = min(t, contact)
        if tg <= anchors[0][0]:
            g = anchors[0][1]
        elif tg >= anchors[-1][0]:
            g = anchors[-1][1]
        else:
            for (ta, ga), (tb, gb) in zip(anchors, anchors[1:]):
                if ta <= tg <= tb:
                    g = ga + (gb - ga) * (tg - ta) / (tb - ta)
                    break
        rem = max(0.0, 62.0 - g)   # 60 s called at 102:45:02 -> bingo at 102:46:02
        a = min(1.0, (t - 55.6) / 0.3)      # v9: no fade-out; held over the lamp insert until the white frame
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
        a = ease_out(u / 0.4)
        # v10: three lines; the disclaimer ~20% larger (body41 vs body34); all inside title safe x 96-1824
        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, HOLST (PD)", "body34", WHITE, 62),
                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA  ·  SOME ENGINE SHOTS FROM OTHER SATURN V FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 330
        for s, f, c, step in lines:
            self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += step

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


def title_layer(gfx: "Gfx", t: float) -> Image.Image | None:
    """3D title frame for time t (graded with the plate by the caller), or None."""
    if 13.0 <= t < 17.25:
        idx = min(int(round((t - 13.0) * FPS)), len(gfx.title) - 1)
        fade = 1 - ease_in_out((t - 16.92) / 0.33)
    elif 83.4 <= t < 85.5:
        idx = min(12 + int(round((t - 83.4) * FPS)), 70)
        fade = min(1.0, (t - 83.4) / 0.15) * (1 - ease_in_out((t - 85.15) / 0.35))
    else:
        return None
    ti = Image.open(gfx.title[idx]).convert("RGBA")
    if t >= 83.4:   # end card: title sits higher, clear of the LM
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ti = ti.resize((int(W * 0.8), int(H * 0.8)), Image.Resampling.LANCZOS)
        canvas.alpha_composite(ti, (int(W * 0.1), int(H * 0.1) - 180))
        ti = canvas
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


GLITCH_WINDOWS = [(47.0, 47.17, 1.0), (48.25, 48.38, 0.6), (49.0, 49.2, 1.0), (50.6, 50.72, 0.6)]


def stage_comp() -> None:
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(SEG / "list.txt"), "-c", "copy",
         str(WORK / "base.mp4")])
    # v9: passthrough. ffmpeg's default CFR output re-timed the 1-frame WHITE segment (v8: white dropped, the black
    # insert frame duplicated, every frame after 56.2 one frame late, frame 1350 black).
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(WORK / "base.mp4"), "-fps_mode", "passthrough",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "12", "-preset", "fast",
                            "-pix_fmt", "yuv420p", str(WORK / "comp.mp4")], stdin=subprocess.PIPE)
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
        if len(buf) < fsize:
            fr = np.zeros((H, W, 3), np.uint8)
        else:
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
        ttl = title_layer(gfx, tl)
        if ttl is not None:
            f0 = fr.astype(np.float32)
            ta = np.asarray(ttl, np.float32)
            a_ = ta[..., 3:4] / 255.0
            sh = np.asarray(ttl.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(10)).resize((W, H)), np.float32)[..., None] / 255.0
            sh = np.roll(np.roll(sh, 18, axis=0), 10, axis=1)
            f0 = f0 * (1 - 0.55 * sh)
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
        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)
        la = np.asarray(layer, np.float32)
        al = la[..., 3:4] / 255.0
        f = f * (1 - al) + la[..., :3] * al
        # grain over everything (luma-weighted)
        gr = grain[fi % len(grain)]
        gr = np.asarray(Image.fromarray(gr).resize((W, H), Image.Resampling.BILINEAR))[..., None]
        f += gr * 7.0
        enc.stdin.write(np.clip(f, 0, 255).astype(np.uint8).tobytes())
        if fi % 240 == 0:
            print(f"  frame {fi}/{NFRAMES}", flush=True)
    enc.stdin.close()
    enc.wait()
    dec.stdout.close()
    dec.wait()
    print("comp written")


# ---------------------------------------------------------------- v2: public-domain score + Sonniss layer
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


def stage_mix() -> None:
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
    bed = music * gain[:, None] + sfx * sgain[:, None]
    mix = bed + dlg[:, None] * 1.0
    bed.mean(axis=1).astype(np.float32).tofile(AUD / f"bed_v{VERSION}.f32")      # for audio_qc.py
    dlg.astype(np.float32).tofile(AUD / f"dlg_v{VERSION}.f32")
    # faint room tone in the post-flash silence (critic: dead digital zero reads as a playback fault)
    rng = np.random.default_rng(3)
    i0, i1 = int(61.92 * SR), int(62.9 * SR)       # v8 (v7: 68.62-69.6)
    tone = rng.normal(0, 1, (i1 - i0, 2)).astype(np.float32)
    tone = np.cumsum(tone, axis=0)
    tone -= np.linspace(tone[0], tone[-1], len(tone))
    tone *= 10 ** (-52 / 20) / max(np.sqrt(np.mean(tone ** 2)), 1e-9)
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
