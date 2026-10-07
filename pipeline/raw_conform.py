"""RAW conform + RAW vs FINAL side-by-side.

    py raw_conform.py N        (N = the version that becomes FINAL; uses build.py's tables as they are now)

1. exports/moonshot/MOONSHOT_RAW_conform.mp4: every shot cut from the UNTOUCHED source at the same timeline
   in/out and source in-point as the edit: no crop, grade, restore, speed change, push, graphics, captions,
   music or SFX. Video sources play at 1x from their source in-point, letterboxed into 1920x1080. Stills are
   shown whole and static. Blender shots show the plain un-composited render (or, for parallax shots, the
   original NASA still they were built from). Black/white/insert graphics show a neutral card. Audio = the
   unprocessed mission audio (pre-restoration) at the same timeline positions.
2. exports/moonshot/MOONSHOT_RAW_vs_FINAL.mp4: 1920x1080, left = RAW (960x540), right = FINAL (960x540),
   frame-synced, "RAW" / "FINAL" labels in Bebas Neue, a thin timecode strip, the FINAL mix as audio.
"""
from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import build  # noqa: E402

N = int(sys.argv[1])
EXP = (CRAFTWORK / "exports/moonshot")
RAWDIR = build.WORK / "raw"
RAWDIR.mkdir(exist_ok=True)
W, H, FPS, SR = build.W, build.H, build.FPS, build.SR
BEBAS = str((CRAFTWORK / "fonts/BebasNeue-Regular.ttf").resolve()).replace("\\", "/").replace(":", "\\:")
PAD = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
PARALLAX_SRC = {"px_earthrise": "as11-44-6550.jpg", "px_earthrise_v2": "as11-44-6550.jpg", "px_aldrin": "as11-40-5903.jpg"}
RAW_AUDIO = {   # restored window -> (raw source, offset of the window in that source)
    "countdown.wav": (build.WORK / "activities_tail.wav", 240.0),
    "pao_alarm.wav": (build.PAO, 420.0),
    "pao_land.wav": (build.PAO, 815.0),
    "eagle.wav": (build.INBOX / "audio" / "commons_eagle_has_landed.mp3", 0.0),
    "step.wav": (build.INBOX / "audio" / "commons_small_step.ogg", 0.0),
}


def card(text: str, n: int, out: Path) -> None:
    build.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=0x202020:s={W}x{H}:r={FPS}",
               "-vf", f"drawtext=fontfile='{BEBAS}':text='{text}':fontcolor=0xbbbbbb:fontsize=64:x=(w-tw)/2:y=(h-th)/2",
               "-frames:v", str(n), "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(out)])


def main() -> None:
    for i, s in enumerate(build.SHOTS):
        n = build.nframes(s)
        out = RAWDIR / f"r{i:02d}.mp4"
        if s.src in build.SRC:
            span = n / FPS * s.speed                     # the exact source span the edit uses, at native speed
            build.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s.src_in:.3f}", "-t", f"{span:.3f}", "-i", str(build.SRC[s.src]),
                       "-vf", f"{PAD},fps={FPS},tpad=stop_mode=clone:stop_duration=60,format=yuv420p", "-frames:v", str(n), "-an",
                       "-c:v", "libx264", "-crf", "16", str(out)])
        elif s.src == "STILL" or (s.src == "SEQ" and s.img.split("/")[0] in PARALLAX_SRC):
            img = s.img if s.src == "STILL" else PARALLAX_SRC[s.img.split("/")[0]]
            build.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i",
                       str(build.INBOX / "stills" / img), "-vf", f"{PAD},format=yuv420p", "-frames:v", str(n),
                       "-c:v", "libx264", "-crf", "16", str(out)])
        elif s.src == "SEQ":
            start = ["-start_number", str(int(s.src_in))] if s.src_in and s.src_in > 1 else []
            build.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), *start, "-i",
                       str(build.WORK / s.img), "-vf", f"{PAD},format=yuv420p", "-frames:v", str(n),
                       "-c:v", "libx264", "-crf", "16", str(out)])
        else:
            card("GENERATED – NO RAW SOURCE", n, out)
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", str(out)], capture_output=True,
                                 text=True).stdout.strip().split(",")[0] or 0)   # ffprobe may print "20,"
        if got != n:
            raise SystemExit(f"raw r{i:02d}: {got} frames, expected {n}")
    (RAWDIR / "list.txt").write_text("".join(f"file 'r{i:02d}.mp4'\n" for i in range(len(build.SHOTS))))
    # raw audio: unprocessed mission audio at the edit's positions, nothing else
    n_s = int(build.TOTAL * SR)
    bus = np.zeros(n_s, np.float32)
    for src, a, b, t, g in build.DIALOG:
        raw_src, off = RAW_AUDIO[Path(src).name]
        x = build.load_audio(raw_src, a + off, b + off)
        i0 = int(t * SR)
        bus[i0:i0 + len(x)] += x[: max(0, min(len(x), n_s - i0))]
    bus *= 0.5 / max(np.abs(bus).max(), 1e-6)
    bus.astype(np.float32).tofile(RAWDIR / "raw_audio.f32")
    raw_mp4 = EXP / "MOONSHOT_RAW_conform.mp4"
    build.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(RAWDIR / "list.txt"),
               "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", str(RAWDIR / "raw_audio.f32"),
               "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(raw_mp4)])
    final = EXP / "versions" / f"moonshot_v{N}.mp4"
    sbs = EXP / "MOONSHOT_RAW_vs_FINAL.mp4"
    lab = f"fontfile='{BEBAS}':fontcolor=white:fontsize=72:y=150"
    fc = (f"[0:v]scale=960:540,setsar=1[l];[1:v]scale=960:540,setsar=1[r];"
          f"color=black:s={W}x{H}:r={FPS}[bg];[bg][l]overlay=0:270[a];[a][r]overlay=960:270:shortest=1,"
          f"drawtext={lab}:text='RAW':x=480-tw/2,drawtext={lab}:text='FINAL':x=1440-tw/2,"
          f"drawbox=x=959:y=270:w=2:h=540:color=0x444444:t=fill,"
          f"drawtext=fontfile='{BEBAS}':fontcolor=0x999999:fontsize=34:x=(w-tw)/2:y=880:"
          f"text='%{{pts\\:hms}}   ·   SAME EDIT POINTS, LEFT UNTOUCHED SOURCES, RIGHT FINISHED CUT',"
          f"drawbox=x=0:y=930:w=iw*t/{build.TOTAL}:h=4:color=0xffb040:t=fill")
    build.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw_mp4), "-i", str(final), "-filter_complex", fc,
               "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
               "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(sbs)])
    print(f"wrote {raw_mp4.name} and {sbs.name}")


if __name__ == "__main__":
    main()
