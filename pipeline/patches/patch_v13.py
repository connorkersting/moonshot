"""v13: rights fix on v12. Apply to the v12 source (build.py + score_pd.py, tag v12-src).

    py patch_v13.py                      # the real build.py + score_pd.py in work/
    py patch_v13.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS.
1 Act-3 music: Holst "Mars" (U.S. Air Force Band, holst_mars_usaf_band.ogg) is out. The recording plays a 1998
  wind-band arrangement whose copyright is unconfirmed. Replacement: Beethoven, Egmont Overture Op. 84, Czech National
  Symphony Orchestra / Musopen (public domain worldwide, verified 2026-10-07),
  music/pd/beethoven_egmont_overture_musopen.flac (540.9 s, 48 kHz).
  ONE continuous span, no splice: src 433.15-461.75 at timeline 33.3-61.9. It is the overture's own arc from Egmont's
  death to the victory symphony:
    33.3-40.3  lunar transition  hushed woodwind/brass chords (Sostenuto, chords from src 429.25; 2.5 s fade-in), S -30
    40.3-48.9  1202 alarm        the chords die away; Beethoven's general pause (src 442.25-443.25 = 42.40-43.40, under
                                 the ducked "1202."); the Allegro con brio enters pp (src 443.3 = 43.45), strings creep up
    48.9-56.2  bingo fuel        the coda's string crescendo, pp -> ff (S -27 -> -10), quarter ~154 bpm
    56.25      touchdown         the F-major tutti (attack src 456.10, the loudest arrival in the recording)
                                 lands on the white flash / touchdown cut (56.20 / 56.26)
    61.9       stop              hard stop (0.03 s fade) at src 461.75: one eighth after the beat-3 accent (src 461.58),
                                 just before the next onset (461.76). Bars: 456.10, 457.70, 459.20, 460.80 (~1.55 s).
  MUSIC_AUTO re-tuned for the new source (Egmont is 11 dB quieter than Mars under the lunar transition and 3.6 dB
  louder under the landing, before automation); decided with the stage_mix emulation + the exact 2-pass loudnorm.
2 Credits: "MUSIC: DVOŘÁK, HOLST (PD)" -> "MUSIC: DVOŘÁK, BEETHOVEN (PD)" (inside title safe x 96-1824).
Re-render: music, comp (credits), mix. No shot changes.
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


assert ((CRAFTWORK / "music/pd") / "beethoven_egmont_overture_musopen.flac").exists()
# ============================================================== score_pd.py
sc = load(S)
RS = [
    ('''    # Holst Mars (USAF Band): ostinato fades in under the lunar transition; the brass climax (src 85.0) lands
    # under "The Eagle has landed" (v8 ~59.3); hard cut at the white flash (v8 61.9).
    (PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 33.3, 0.0, 2.5, 0.03),
''',
     '''    # v13 (rights fix; Holst "Mars" / USAF Band out): Beethoven, Egmont Overture Op. 84, Czech National SO / Musopen
    # (PD worldwide). One continuous span, no splice: the hushed chords after Egmont's death fade in under the lunar
    # transition; Beethoven's general pause (src 442.25-443.25) falls at 42.40-43.40 under "1202."; the Allegro con
    # brio's pp -> ff string crescendo drives the alarm and the fuel countdown; the F-major tutti (attack src 456.10)
    # lands on the touchdown flash (56.25); hard stop at 61.9 (src 461.75), one eighth after the beat-3 accent (461.58).
    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 2.5, 0.03),
'''),
    ('''MUSIC_AUTO = [(0, -10), (10.4, -6), (10.6, 0), (19, 0), (19.5, -8), (32.3, -8), (33.2, -6.65), (33.3, -2), (40.3, -3), (40.8, -5.53), (48.3, 1.5), (50.0, 1.5), (53.6, 4.0), (56.2, 5.5), (58.7, 8.0), (61.9, 8.0), (62.9, -0.5), (81.3, 1.5)]     # v11: Holst ramps''',
     '''MUSIC_AUTO = [(0, -10), (10.4, -6), (10.6, 0), (19, 0), (19.5, -8), (32.3, -8), (33.2, -6.65), @@AUTO@@, (62.9, -0.5), (81.3, 1.5)]     # v13: 33.3-61.9 re-tuned for Egmont (pp chords lifted, the written crescendo flattened, tutti held under the landing); v11: Holst ramps'''),
]
# 33.3-40.3 pp chords +8.5 -> +8 (Mars sat at -2..-3; Egmont is 11 dB quieter here); 43.4-48.9 the pp strings +7 -> +5.5
# (the music still rises ~3 dB under the alarm lines); 48.9-56.2 the written crescendo (11 dB) is flattened to ~6.5 dB:
# +5.5 -> +1 by "30 seconds" (53.6) -> +2 at the touchdown; the tutti +2 -> +4 under the landing (Mars was +5.5..+8;
# Egmont's tutti is 3.6 dB louder raw). Emulated: lunar -17.1, alarm -14.0, bingo -13.1, landing -10.9 LUFS.
AUTO = "(33.3, 8.5), (40.3, 8.0), (43.4, 7.0), (48.9, 5.5), (53.6, 1.0), (56.2, 2.0), (58.7, 4.0), (61.9, 4.0)"
RS[1] = (RS[1][0], RS[1][1].replace("@@AUTO@@", AUTO))
sc = apply(sc, RS, "score")
# ============================================================== build.py
s = load(P)
R = [
    ('''MUSIC: DVOŘÁK, HOLST (PD)", "body34", WHITE, 62),''',
     '''MUSIC: DVOŘÁK, BEETHOVEN (PD)", "body34", WHITE, 62),'''),
]
s = apply(s, R, "build")
save(S, sc)
save(P, s)
print(f"v13: score {len(RS)} patches (Egmont replaces Mars, MUSIC_AUTO 33.3-61.9), build {len(R)} (credits). "
      f"Re-render: py build.py music 13, py build.py comp 13, py build.py mix 13 (no shots).")
