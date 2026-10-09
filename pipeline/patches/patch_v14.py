"""v14: middle re-cut (pacing) on v13. Apply to the v13 source (build.py + score_pd.py, tag v13-src).

    py patch_v14.py                      # the real build.py + score_pd.py in work/
    py patch_v14.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS
(tl = t below frame 799, (fi + 161) / 24 from it).
Four critic passes: the middle (real 26.5-40.3) sags (a 3.5 s Earth pull, a 4 s Moon render, a 3 s Eagle still).
TIMELINE FREEZE: TOTAL 81.8 / 1963 frames, the logical-time map, every cut outside 26.5-40.3, DIALOG, CAPTIONS, MUSIC,
MUSIC_AUTO and every graphics timing are unchanged. Only the shots INSIDE 26.5-40.3 are re-cut: 5 shots -> 8, every
cut kept that a graphic is keyed to (26.5 / 28.0 STAGE SEPARATION, 29.8 the 24,200 MPH card, 33.3 the 240,000 MILES
card, 37.3 the DAY 5 chapter card, 40.3). Moving 16mm replaces most of the still / render time:
  26.50-28.00  BRD 940.0      staging (unchanged, STAGE SEPARATION label)
  28.00-29.80  BRD 988.55     S-II interstage ring: opens inside the ignition flash (on the 28.0 impact; Dvorak onset
                              28.21), the ring emerges (src 989.0 = 28.45) and tumbles away over the Earth
                              [was 961.0: the static engine-glow view]
  29.80-31.00  STILL Earth    as11-36-5355, pull 1.95 -> 1.60 in 1.2 s (v13 1.95 -> 1.55 in 3.5 s); the 24,200 MPH
                              card counts here (u 0.4-1.6); out on the Dvorak hit 31.02 (the loudest onset in the window)
  31.00-33.30  BR 1113.25     16mm: the whole Earth from the spacecraft, handheld drift, pull-out push 1.12 -> 1.0;
                              Earth bottom <= 0.59 of frame height, above the card's label (y 700) and number
  33.30-35.58  SEQ Moon x1.7  the Blender Moon approach at 1.7x (55 fr x 1.7 = 94 of 96); 240,000 MILES card
  35.58-37.30  BR 1196.0      16mm from Columbia: Eagle undocked, over the Moon (on the Egmont chord 35.58); the card
                              fades out (tl 42.6-43.0) over the dark window frame, lower left
  37.30-38.71  BR 1176.0      16mm: the lunar limb from orbit, limb rising, black sky top-left under the DAY 5 card
  38.71-40.30  BR 1206.0      16mm: low oblique horizon, terrain sliding, black sky top half (chapter card), into
                              the LM-window descent at 40.3 (Egmont onset 38.71)
  The Eagle still (as11-44-6581, also the 4.8 s flash-forward) is out of the window: no duplicate picture.
  All new BR spans checked frame by frame inside one source take (scene cuts 955-996.46, 1093.69-1120.85,
  1171.84-1181.78, 1194.59-1205.77, 1205.77-1214 flare-free), none used elsewhere in SHOTS.
Sonniss: one whoosh (Rescopic "Pure SciFi-Whoosh Fast 03", 1.8 s) peaks at 33.45 (-10 dB): Earth -> Moon, filling the
  momentary hole after the Dvorak cutoff (emulated M 33.6-33.8: -19.6/-20.5 -> -12.8/-12.9 LUFS); lunar section
  -17.1 -> -16.7 LUFS, landing still the loudest (-11.0), no dialogue within 7 s. (The act-2 "WHOOSH PASS SF LOW" at
  -12/-8/-5 dB and a spaceship pass-by moved the lunar section by <= 0.1 LU: low-frequency, K-weighting.)
Comments: the stat_speed / DSKY comments name the new shots (s26 = old s23). No graphics code changed.
Re-render: ALL shots (indices from s17 on shift by +3; `py build.py shots 14` full run, never a partial run: stale
s39-s42 files from older versions sit in seg/), then music, comp, mix. Dialogue unchanged.
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
R = [
    ('''    Shot(28.00, 29.80, "BRD", 961.0, push=(1.0, 1.08), note="interstage falls away over Earth"),
    Shot(29.80, 33.30, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.55)), note="Apollo 11 Earth on translunar coast, pulling away (stat: TLI speed)"),
    # LUNAR TRANSITION
    Shot(33.30, 37.30, "SEQ", img="moon_blender/moon_%04d.png", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer"),
    # ACT 3: descent
    Shot(37.30, 40.30, "STILL", img="as11-44-6581.jpg", kb=((0.5, 0.48, 1.25), (0.5, 0.5, 1.45)), note="Eagle undocked"),
''',
     '''    # v14: the middle re-cut for pace (5 shots -> 8 in 26.5-40.3; every graphics-keyed cut kept: 28.0, 29.8, 33.3, 37.3)
    Shot(28.00, 29.80, "BRD", 988.55, push=(1.0, 1.10), note="v14: S-II interstage ring: opens in the ignition flash (on the 28.0 impact), the ring emerges (src 989.0 = 28.45) and tumbles away over Earth"),
    Shot(29.80, 31.00, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.60)), note="Apollo 11 Earth, pulling away fast (stat: TLI speed counts here); v14: 1.2 s, out on the Dvorak hit 31.02"),
    Shot(31.00, 33.30, "BR", 1113.25, push=(1.12, 1.0), note="v14: 16mm, the whole Earth from the spacecraft, handheld drift, receding (24,200 MPH holds; Earth clear of the card)"),
    # LUNAR TRANSITION
    Shot(33.30, 35.58, "SEQ", speed=1.7, img="moon_blender/moon_%04d.png", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer; v14: 1.7x (55 fr x 1.7 = 94 of 96)"),
    Shot(35.58, 37.30, "BR", 1196.0, push=(1.0, 1.08), note="v14: 16mm from Columbia: Eagle undocked over the Moon (take 1194.59-1205.77), on the Egmont chord 35.58"),
    # ACT 3: descent
    Shot(37.30, 38.71, "BR", 1176.0, push=(1.0, 1.10), note="v14: 16mm, the lunar limb from orbit, the limb rising, black sky top-left (DAY 5 chapter card)"),
    Shot(38.71, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v14: 16mm, low oblique horizon, terrain sliding, black sky top (chapter card); Egmont onset 38.71"),
'''),
    ('''        if round(29.8 * FPS) / FPS <= t < ACT2_T0:     # v8: over the as11-36-5355 still (cut 29.8 = frame 715)''',
     '''        if round(29.8 * FPS) / FPS <= t < ACT2_T0:     # v8: over the as11-36-5355 still (cut 29.8 = frame 715); v14: still to 31.0, then the 16mm Earth'''),
    ('''(s23, frame 1054 -> tl 50.625, under the 50.6 glitch)''',
     '''(s23, v14 s26, frame 1054 -> tl 50.625, under the 50.6 glitch)'''),
    ('''# v12: s23's source cuts back''', '''# v12: s23's (v14 s26) source cuts back'''),
]
s = apply(s, R, "build")
# ============================================================== score_pd.py
sc = load(S)
RS = [
    ('''    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -12.0, "attack", 4.0),   # v10: -5 dB (stage separation)
''',
     '''    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -12.0, "attack", 4.0),   # v10: -5 dB (stage separation)
    ("Rescopic Sound - Distinct Whooshes/WHSH_Pure SciFi-Whoosh Fast 03_RSCPC_DW.wav", 33.45, -10.0, "peak", 1.8),     # v14: Earth -> Moon whoosh, fills the hole after the Dvorak cutoff (33.12)
'''),
]
sc = apply(sc, RS, "score")
save(P, s)
save(S, sc)
print(f"v14: build {len(R)} patches (26.5-40.3 re-cut, 5 -> 8 shots; comments), score {len(RS)} (one whoosh at 33.45). "
      f"Re-render: py build.py shots 14 (FULL run: indices from s17 shift +3), music 14, comp 14, mix 14.")
