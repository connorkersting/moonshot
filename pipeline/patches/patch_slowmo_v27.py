"""v27 slow-mo: route the smoke-under-the-title shot (13.00-17.6667 s) through slowmo_v27.render (RIFE in-betweens)
behind V27_SLOWMO = True. The Shot entry, its src ("L70": the countdown-HUD gating reads it) and every other shot are
unchanged; False renders the ffmpeg framerate blend exactly as before.

    py patch_slowmo_v27.py            # the real build.py
    py patch_slowmo_v27.py BUILD.py   # a copy
Re-render: shots 27 13; comp; mix.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "slowmo_v27" not in s, "v27 slow-mo already applied"
A = '''def render_video_shot(s: Shot, path: Path) -> None:
    if s.ramp is not None and RAMP_IGNITION:     # v19 (R4); RAMP_IGNITION = False renders the constant-speed shot
        render_ramp_shot(s, path)
        return
'''
B = '''V27_SLOWMO = True       # v27 (director's A/B): the 13.00 s smoke-under-the-title shot from RIFE in-betweens (slowmo_v27)


def render_video_shot(s: Shot, path: Path) -> None:
    if s.ramp is not None and RAMP_IGNITION:     # v19 (R4); RAMP_IGNITION = False renders the constant-speed shot
        render_ramp_shot(s, path)
        return
    if V27_SLOWMO:
        import slowmo_v27
        if slowmo_v27.is_slowmo_shot(s):
            slowmo_v27.render(s, path, W, H, FPS, GRADE[s.src], nframes(s))
            return
'''
assert s.count(A) == 1, f"{s.count(A)} matches for render_video_shot's head"
s = s.replace(A, B)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"v27 slow-mo: 1 replacement in {P.name}")
