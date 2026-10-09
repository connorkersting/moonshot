"""v18m: Connor's notes on v17 (watched with sound), auditioned and approved as exports/moonshot/auditions/
0m32_B_fix + 1m02_B_fix (music) and 0m32_C2_hold_then_drift (the Moon beat). Apply AFTER patch_v18.py:

    py patch_v18m.py                      # the real build.py + score_pd.py in work/
    py patch_v18m.py BUILD.py SCORE.py    # dry run on copies

Diagnosis (librosa chroma + 0.25 s RMS on v17 and the sources, PROGRESS 23:40):
 0:32  v17 faded the Dvorak's final E-minor chord (src 40.0-41.0) for 1.3 s under the Egmont's D-flat-major pre-lap
       (src 432.15 at 32.3): every note of one triad a semitone from the other's, for ~1 s; and a +6.8 dB level step
       on the 33.3 cut. Connor, after the B fix: still rushed ("mini climax, then instantly softer music, text, zoom").
 1:02  the Egmont stops on F major; the Largo entered at src 5.2, late in its B-flat chord, under a 1.8 s fade, so the
       first audible chord was its E major (~63.75): a semitone shift, 0.85 s after the Earthrise picture.

Changes (REAL times; the 799/161 logical map and TOTAL unchanged, every cut except 35.58 unchanged):
 1  Dvorak iv ends at src 41.35 with a 0.2 s ease: its E-minor chord decays on its own (no overlap).
 2  Moon beat 33.3-36.6: one shot from a still 4K Blender portrait (moon_beat_frames.py): locked off 33.3-34.0, then
    an ease-in drift 1.12 -> 1.18 from the Egmont entry, still moving at the cut. Stars + CG16 as before.
    The Eagle-undocked 16mm shot (35.58-36.6) is dropped to pay for the breath (SHOTS loses one entry: re-render
    all shots, indices after it shift).
 3  Egmont enters at 34.0 (src 433.85, the same src->timeline map as v13-v17: 433.15 = 33.3), 0.8 s ease; gain
    automation 34.0 +6.0 -> 35.0 +11.5 dB (was a step to +11.5 on 33.3); AUTO_CLAMP[2] = (34.0, None).
 4  The 33.45 Earth->Moon whoosh is removed (it was a fourth event on the cut).
 5  Distance stat: wipes in from 34.6 (logical 41.3, u 1.3), the dark scrim fades in with it, hard out on the 36.6 cut
    (frame 878, u 3.2917; was 35.58).
 7  Largo tail: to src 29.05 = 86.75, so its 1.8 s fade ends with patch_v18's card 2 (was 86.3, 0.45 s early).
 6  Largo: the same map (src 5.2 = 62.9) started at its B-flat onset, src 4.69 = 62.39 (0.5 s J-cut into the black),
    0.5 s ease; AUTO_CLAMP[3] = (62.9, None): F major -> B-flat is V -> I across the black.
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
assert "moon_portrait_v18" not in s, "v18m already applied"
assert (W / "moon_portrait_v18" / "mp_0079.png").exists(), "run moon_beat_frames.py first"
R = [
    ('''    Shot(33.30, 35.58, "SEQ", speed=1.7, img="moon_blender/moon_%04d.png", grade="CG16", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer; v14: 1.7x (55 fr x 1.7 = 94 of 96); v15: CG16 film grade"),
    Shot(35.58, 36.60, "BR", 1196.0, push=(1.0, 1.08), note="v14: 16mm from Columbia: Eagle undocked over the Moon (take 1194.59-1205.77), on the Egmont chord 35.58; v16b: 1.0 s (was 1.72 s, a near-freeze)"),
''',
     '''    Shot(33.30, 36.60, "SEQ", speed=1.0, img="moon_portrait_v18/mp_%04d.png", grade="CG16", note="v18m (Connor): still 4K Blender Moon portrait (NASA CGI Moon Kit), locked off 33.3-34.0 while the Dvorak decays, ease-in drift 1.12 -> 1.18 from the Egmont entry (moon_beat_frames.py) + star layer + CG16; replaces v14-v17's 1.7x approach and the Eagle-undocked shot (35.58-36.6)"),
'''),
    ('''        if u >= 2.29:                              # v16b: hard cut on the 35.58 cut (frame 854, u 2.2917); v15 faded 1.99-2.29
            return
        a = 1.0
''',
     '''        if u >= 3.29:                              # v18m: hard cut on the 36.6 cut (frame 878, u 3.2917); v16b-v17 at 35.58
            return
        u -= 1.25                                  # v18m: in from 34.6 real (u 1.3), after the Egmont entry (34.0)
        if u <= 0:
            return
        a = ease_out(u / 0.4)                      # v18m: the scrim fades in with the text (v17: on from the cut)
'''),
]
s = apply(s, R, "build")

# ============================================================== score_pd.py
sc = load(S)
RS = [
    ('''    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.45, 23.6, 0.0, 0.03, 1.30),''',
     '''    # v18m: to src 41.35, 0.2 s ease: the E-minor chord (src 40.0 = 32.0) decays alone, no overlap with the Egmont
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.35, 23.6, 0.0, 0.03, 0.20),'''),
    ('''    (PD / "beethoven_egmont_overture_musopen.flac", 432.15, 461.75, 32.3, 0.0, 1.0, 0.06),''',
     '''    # v18m: enters at 34.0 (src 433.85; same map, 433.15 = 33.3) under the locked-off Moon, 0.8 s ease
    (PD / "beethoven_egmont_overture_musopen.flac", 433.85, 461.75, 34.0, 0.0, 0.8, 0.06),'''),
    ('''    (PD / "dvorak9_ii_largo.ogg", 5.2, 28.6, 62.9, 0.0, 1.8, 1.8),''',
     '''    # v18m: same map (src 5.2 = 62.9) from the B-flat onset src 4.69 = 62.39, 0.5 s ease: F -> B-flat (V -> I) in the black
    (PD / "dvorak9_ii_largo.ogg", 4.69, 29.05, 62.39, 0.0, 0.5, 1.8),     # v18m: to src 29.05 = 86.75 (patch_v18's card 2 end; the pp D-flat chord holds -39 dB to src 29.4)'''),
    ('''FADE_SHAPE = {1: ("lin", "sine"), 2: ("sq", "lin"), 3: ("ease", "ease")}''',
     '''FADE_SHAPE = {1: ("lin", "ease"), 2: ("ease", "lin"), 3: ("ease", "ease")}     # v18m: 1 out sine -> ease, 2 in sq -> ease'''),
    ('''AUTO_CLAMP = {1: (None, 33.2), 2: (33.3, None)}''',
     '''AUTO_CLAMP = {1: (None, 33.2), 2: (34.0, None), 3: (62.9, None)}     # v18m: Egmont from 34.0; Largo's pre-lap at the 62.9 value'''),
    ('''(33.2, -6.65), (33.3, 11.5), (39.9, 11.0)''',
     '''(33.2, -6.65), (34.0, 6.0), (35.0, 11.5), (39.9, 11.0)'''),
    ('''    ("Rescopic Sound - Distinct Whooshes/WHSH_Pure SciFi-Whoosh Fast 03_RSCPC_DW.wav", 33.45, -10.0, "peak", 1.8),     # v14: Earth -> Moon whoosh, fills the hole after the Dvorak cutoff (33.12)
''', ''),
]
sc = apply(sc, RS, "score")
save(P, s)
save(S, sc)
print(f"v18m: build {len(R)} patches, score {len(RS)}. Re-render: py moon_beat_frames.py, then py build.py shots 18 "
      f"(all: SHOTS lost one entry), dialog 18 (stems follow TOTAL 87.5), music 18, comp 18, mix 18.")
