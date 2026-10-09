"""v26 outro: the director's v24 note (Connor, 2026-10-08 ~19:20): "the outro/before the credits i feel like its too
rushed and text shaking a little too much ... do whatever u think best".

Diagnosis (scratchpad/outro): the end title is the v22 3D render played over 56 frames with yaw 5 -> 2.5 deg and a
1.035 -> 0.985 push while the 6642 plate pushes the other way, so its bevel highlights crawl every frame (the region
does not translate: phase correlation 0 px). The date line is fully up for only ~0.75 s (in 83.9 + 0.5, out 85.15).

Change, behind V26_OUTRO = True (False: the previous outro exactly):
 1  the cut to the end plate moves from 76.70 to 75.50 s (frame 1812; the bootprint still gives up 1.2 s: 4.0 -> 2.8 s),
    so the Earth-over-the-Moon plate breathes before the title;
 2  the title still lands at 76.70 s real (83.4 logical), ON the designed Sonniss boom at 76.7 (score_pd.py, untouched:
    no audio change). It plays its 56-frame settle 4x faster (OUTRO_SETTLE: ~0.58 s), then HOLDS its last frame: no
    rotation or scale crawl while the text is read;
 3  the date line (and the v23 end note, which shares its alpha) comes in at 83.6 logical over 0.3 s (was 83.9 + 0.5).
The fade-out (85.15-85.5 logical) and everything from frame 1891 (the credits) are unchanged.

    py patch_outro_v26.py            # the real build.py
    py patch_outro_v26.py BUILD.py   # a copy (dry run)
Re-render: shots <bootprint>,<end plate> (43,44 after v25's reindex), comp, mix.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "V26_OUTRO" not in s, "v26 outro already applied"
R = [
    ('''SHOTS: list[Shot] = [
''',
     '''V26_OUTRO = True        # v26 (director): end plate from 75.50 s, the title lands on the 76.7 boom and holds still
OUTRO_T0 = 75.50 if V26_OUTRO else 76.70     # real s: the bootprint -> end-plate cut
OUTRO_SETTLE = 4 if V26_OUTRO else 0         # the end title's 56-frame settle plays this many times faster, then holds
SHOTS: list[Shot] = [
''', 1),
    ('Shot(72.675, 76.70,', 'Shot(72.675, OUTRO_T0,', 2),
    ('Shot(76.70, 78.80,', 'Shot(OUTRO_T0, 78.80,', 2),
    ('''        idx = title_idx(gfx.title_end, t - 83.4)      # v22: no clamp
''',
     '''        idx = (min(len(gfx.title_end) - 1, int((t - 83.4) * FPS * OUTRO_SETTLE)) if OUTRO_SETTLE   # v26: settle,
               else title_idx(gfx.title_end, t - 83.4))      # then hold still; v22: no clamp
''', 1),
    ('''        if 83.9 <= t < 85.5:
            a = ease_out((t - 83.9) / 0.5) * (1 - ease_in_out((t - 85.15) / 0.35))
''',
     '''        d0, dd = (83.6, 0.3) if V26_OUTRO else (83.9, 0.5)     # v26: the date line sooner (director: too rushed)
        if d0 <= t < 85.5:
            a = ease_out((t - d0) / dd) * (1 - ease_in_out((t - 85.15) / 0.35))
''', 1),
]
for a, b, n in R:
    got = s.count(a)
    assert got == n, f"{got} matches (want {n}) for {a[:70]!r}"
    s = s.replace(a, b)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"v26 outro: {len(R)} replacements in {P.name}")
