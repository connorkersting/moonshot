"""v11: last polish on v10 (senior-editor notes on v10, 7.5). Apply to the v10 source (build.py + score_pd.py, tag v10-src).

    py patch_v11.py                      # the real build.py + score_pd.py (+ edl.py) in work/
    py patch_v11.py BUILD.py SCORE.py    # dry run on copies (edl.py untouched)

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS (captions >= 40
are real + 6.7). Decided from the in-memory mix emulation with stage_mix's exact two-pass loudnorm (see the v11 report).
1 climax loudest: landing 56.3-61.9 was -12.7 LUFS (drop -11.6). The landing is wall-to-wall dialogue under a 21 dB
  duck, so music alone moved it +0.1 LU (+4 dB of Holst: -12.6). The lever is the voice: "Houston ... The Eagle has
  landed" +2.0 -> +4.5 dB, "Contact light" +1.5 -> +2.5, "30 seconds" 0 -> +1.0 (bingo rises into it), plus MUSIC_AUTO:
  Holst holds +1.5 to 50.0, ramps to +4 by 53.6 ("30 seconds"), +5.5 at the 56.2 touchdown cut, +8 under the landing.
  Emulated: landing -10.9, bingo -13.1 (53.6-56.3: -12.9), drop -11.7, cold open -14.5; every line >= +11.0 dB.
2 "Liftoff on Apollo 11": no change. The SFX bus IS ducked with the music (stage_mix: sgain = gain, -22 dB there) and
  the explosion/whoosh/hit tails sit 46-80 dB under the line in 300-3400 Hz; whisper heard "Apollo 11." as its own
  segment at 17.58 s, 0.03 s past audio_qc's +0.4 s match window (a QC matching artefact, not masking).
3 the 40.30 click is not the riser (it runs continuously through its peak there): the legacy synth SFX stem's
  1202-alarm cue starts on a hard step (sfx.wav old 47.01 s -> 40.29 s after synth_sfx_v8). 15 ms fade-in at its onset.
4 16 mm landing grade: BR16 shots 48.3-53.5 move to a new key BR16L (BR16 is also used at 5.6 and 67.3); BR16H is used
  only by the 56.26 touchdown shot and is changed in place. Curve-only contrast (no eq contrast: its 0.5 pivot crushed
  the shadows and lowered the median on these sources).
5 DSKY panel: from the cut to Mission Control (s23, logical 50.625, under the 50.6 glitch) it moves to the right
  (x 1360-1808, y 500-800, legend right-aligned to x 1808) over shirts/desk, clear of every face; top-left before that.
6 captions: Duke "You got a bunch of guys about to turn blue." 70.20-72.40 (19.5 cps; 70.25 would be exactly 20.0)
  and "We're breathing again." 72.50-74.25 (condensed; audio unchanged).
7 yellow vs amber: skipped, there is no separate yellow constant (see report).
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"
E = Path(sys.argv[3]) if len(sys.argv) > 3 else (W / "edl.py" if len(sys.argv) == 1 else None)

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
R = [
    # ---- 1: climax loudest (DIALOG)
    ('''    (RST / "pao_land.wav", 39.3, 40.8, 53.6, 0.0),''',
     '''    (RST / "pao_land.wav", 39.3, 40.8, 53.6, 1.0),       # v11: "30 seconds" +1.0 dB (bingo rises into the landing)'''),
    ('''    (RST / "pao_land.wav", 48.3, 49.1, 55.2, 1.5),       # v9: "Contact light" +1.5 dB''',
     '''    (RST / "pao_land.wav", 48.3, 49.1, 55.2, 2.5),       # v11: "Contact light" +2.5 dB (v9 +1.5)'''),
    ('''    (RST / "eagle.wav", 0.0, 5.3, 56.5, 2.0),            # v9: "The Eagle has landed" +2.0 dB (loudest line)''',
     '''    (RST / "eagle.wav", 0.0, 5.3, 56.5, 4.5),            # v11: "Houston ... The Eagle has landed" +4.5 dB (v9 +2.0): the landing is the loudest section'''),
    # ---- 4: 16 mm landing grade (BR16L for the two BR16 shots 48.3-53.5; BR16H is only the touchdown shot)
    ('''    "BR16H": INBOX / "video" / "broll25_720.mp4",
''',
     '''    "BR16H": INBOX / "video" / "broll25_720.mp4",
    "BR16L": INBOX / "video" / "broll25_720.mp4",
'''),
    ('''    "BR16H": "1036:583:115:70",
''',
     '''    "BR16H": "1036:583:115:70",
    "BR16L": "1036:583:115:70",
'''),
    ('''    "BR16H": "hqdn3d=3:3:6:6,curves=all='0/0 0.12/0.02 0.35/0.36 0.62/0.80 1/1',eq=saturation=0.8,unsharp=5:5:1.0",''',
     '''    # v11: BR16H (touchdown only) mids 0.35/0.36 -> 0.41, 0.62/0.80 -> 0.85 (curve-only contrast; blacks unchanged)
    "BR16H": "hqdn3d=3:3:6:6,curves=all='0/0 0.12/0.02 0.35/0.41 0.62/0.85 1/1',eq=saturation=0.8,unsharp=5:5:1.0",
    # v11: BR16L = BR16 for the 48.3-53.5 landing shots with a firmer upper half: 0.35 -> 0.565 (BR16 ~0.52 there, via
    # 0.3/0.46), 0.65/0.85 -> 0.88; highlights reach ~225 instead of ~218, no clipping after the comp LUT + halation
    "BR16L": "hqdn3d=3:3:6:6,curves=all='0/0 0.06/0.03 0.35/0.565 0.65/0.88 1/1',eq=saturation=0.85,unsharp=5:5:0.7",'''),
    ('''    Shot(48.30, 50.70, "BR16", 1345.5,''', '''    Shot(48.30, 50.70, "BR16L", 1345.5,'''),
    ('''    Shot(50.70, 53.50, "BR16", 1360.2,''', '''    Shot(50.70, 53.50, "BR16L", 1360.2,'''),
    # ---- 6: Duke's captions under 20 cps
    ('''    (70.40, 72.35, "HOUSTON · DUKE", "You got a bunch of guys about to turn blue."),''',
     '''    (70.20, 72.40, "HOUSTON · DUKE", "You got a bunch of guys about to turn blue."),   # v11: 19.5 cps (was 22.1)'''),
    ('''    (72.45, 73.85, "HOUSTON · DUKE", "We're breathing again. Thanks a lot."),''',
     '''    (72.50, 74.25, "HOUSTON · DUKE", "We're breathing again."),       # v11: condensed caption (audio unchanged), 12.6 cps'''),
    # ---- 5: DSKY panel moves right on the cut to Mission Control
    ('''

class Gfx:
''',
     '''
DSKY_RIGHT_T = 50.62     # v11: logical time of the cut to Mission Control (s23, frame 1054 -> tl 50.625, under the 50.6 glitch)


class Gfx:
'''),
    ('''            self.dsky(d, t - 47.2)''', '''            self.dsky(d, t - 47.2, right=t >= DSKY_RIGHT_T)'''),
    ('''    def dsky(self, d, u):
        a = min(1.0, u / 0.1) * (1 - ease_in_out((u - 5.3) / 0.3))
        x0, y0, x1, y1 = 112, 70, 560, 370
''',
     '''    def dsky(self, d, u, right: bool = False):
        a = min(1.0, u / 0.1) * (1 - ease_in_out((u - 5.3) / 0.3))
        x0, y0, x1, y1 = 112, 70, 560, 370
        if right:     # v11: over Mission Control the top-left panel sat on a controller's head; right side = shirts/desk
            x0, y0, x1, y1 = 1360, 500, 1808, 800
'''),
    ('''        self.text(d, (x0, y1 + 46), "1202 = COMPUTER OVERLOADED", "bebas48", AMBER, "ls",''',
     '''        if right:     # v11: the legend sits over white shirts here: dark backing plate (x 1266-1808, y 806-858)
            d.rounded_rectangle([1266, y1 + 6, x1, y1 + 58], radius=8,
                                fill=(0, 0, 0, int(160 * a * min(1.0, max(0.0, (u - 1.0) / 0.4)))))
        self.text(d, (x1 if right else x0, y1 + 46), "1202 = COMPUTER OVERLOADED", "bebas48", AMBER, "rs" if right else "ls",'''),
    # ---- 3: the 40.30 click (legacy synth stem)
    ('''    res = np.zeros_like(old)
    res[:min(n, len(out))] = out[:n]
    return res
''',
     '''    res = np.zeros_like(old)
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
'''),
]
s = apply(s, R, "build")
save(P, s)

# ============================================================== score_pd.py
t = load(S)
RS = [
    ('''(40.8, -5.53), (48.3, 1.5), (58.7, 5.5), (61.9, 5.5), (62.9, -0.5)''',
     '''(40.8, -5.53), (48.3, 1.5), (50.0, 1.5), (53.6, 4.0), (56.2, 5.5), (58.7, 8.0), (61.9, 8.0), (62.9, -0.5)'''),
    (''']     # v9: act-2 plateau''',
     ''']     # v11: Holst ramps 50.0 -> +4 by "30 seconds" (53.6), +5.5 at the touchdown cut, +8 under the landing; v9: act-2 plateau'''),
]
t = apply(t, RS, "score")
save(S, t)

# ============================================================== edl.py (real run only): BR16L is the same source file
ne = 0
if E is not None:
    e = load(E)
    e = apply(e, [('''"BR16H": "broll25_720.mp4", ''', '''"BR16H": "broll25_720.mp4", "BR16L": "broll25_720.mp4", ''')], "edl")
    save(E, e)
    ne = 1
print(f"v11: build {len(R)} patches; score {len(RS)} patches; edl {ne} patch"
      f"{'' if ne else ' (skipped: dry run on copies)'}. Re-render shots 25,26,30 (grade), then dialog, music, comp, mix.")
