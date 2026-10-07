"""v12: final patch on v11 (senior-editor + blind A/B notes on v11). Apply to the v11 source (build.py + score_pd.py,
tag v11-src).

    py patch_v12.py                      # the real build.py in work/
    py patch_v12.py BUILD.py SCORE.py    # dry run on copies (SCORE is accepted for the usual call shape; not changed)

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS
(tl = (fi + 161) / 24 from frame 799).
1 DSKY panel: s23 (real 43.90-46.10, BR 1251.0) is NOT one picture: the source cuts Mission Control -> LM window at
  frame 1096 (real 45.667, tl 52.375; frame diff MAD 48 on base.mp4), so v11's lower-right panel sat over the LM
  window for frames 1096-1106. The panel is lower-right only for tl 50.62 <= t < 52.37 (frames 1054-1095, the
  Mission Control picture) and back top-left from frame 1096 until it is gone (fade tl 52.5-52.8, s24 cut frame 1106).
  Over Mission Control it also moves up 40 px (y 500-800 -> 460-760): legend plate y 766-818, 74 px above the
  caption box top (892; v11: 34 px).
  s23's note now says it is Mission Control with an internal source cut back to the LM window.
2 Climax picture: the reaction shot (s31) starts 0.70 s earlier, as early as its source shot allows. The BR source
  (29.97 fps) has a hard scene cut at 1279.40 s (scdet 1279.41; luma 44 -> 79) from a wide gallery shot, so real
  58.75 (src_in 1278.53) is not possible. New src_in 1279.49 (= 1280.2 - 17/24, so the tail frames are unchanged;
  first rendered frames checked: close reaction shot, luma 80, no wide-shot frame, no blend). Cut s30/s31 at real
  59.70 (frame 1433, was 1450): s30 56.26-59.70 (83 frames, was 100), s31 59.70-61.90 (53 frames, was 36);
  contiguous, 1963 frames. "Tranquility Base here." (58.9-60.15) is now ~0.45 s over the faces; "The Eagle has
  landed." (60.40-61.65) stays on them. Nothing in Gfx / captions / glitches / flashes is keyed to this cut.
3 Audio, captions, MUSIC_AUTO: unchanged. Re-render shots 30,31 (`py build.py shots 12 30,31`), then comp + mix.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"     # not modified by v12

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


assert S.exists(), S
# ============================================================== build.py
s = load(P)
R = [
    # ---- 1: DSKY lower-right only over the Mission Control picture; back top-left at the in-shot cut to the LM window
    ('''DSKY_RIGHT_T = 50.62     # v11: logical time of the cut to Mission Control (s23, frame 1054 -> tl 50.625, under the 50.6 glitch)
''',
     '''DSKY_RIGHT_T = 50.62     # v11: logical time of the cut to Mission Control (s23, frame 1054 -> tl 50.625, under the 50.6 glitch)
DSKY_LEFT_T = 52.37      # v12: s23's source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again
'''),
    ('''            self.dsky(d, t - 47.2, right=t >= DSKY_RIGHT_T)''',
     '''            self.dsky(d, t - 47.2, right=DSKY_RIGHT_T <= t < DSKY_LEFT_T)'''),
    ('''        if right:     # v11: over Mission Control the top-left panel sat on a controller's head; right side = shirts/desk
            x0, y0, x1, y1 = 1360, 500, 1808, 800
''',
     '''        if right:     # v11: over Mission Control the top-left panel sat on a controller's head; right side = shirts/desk
            x0, y0, x1, y1 = 1360, 460, 1808, 760     # v12: 40 px up (legend plate bottom 818, caption box top 892)
'''),
    ('''        if right:     # v11: the legend sits over white shirts here: dark backing plate (x 1266-1808, y 806-858)''',
     '''        if right:     # v11: the legend sits over white shirts here: dark backing plate (x 1266-1808, v12: y 766-818)'''),
    ('''    Shot(43.90, 46.10, "BR", 1251.0, push=(1.0, 1.06), note="descent, LM window (Eagle asks for a reading)"),''',
     '''    Shot(43.90, 46.10, "BR", 1251.0, push=(1.0, 1.06), note="Mission Control (Eagle asks for a reading); source cuts back to the LM window at frame 1096 (real 45.667)"),'''),
    # ---- 2: the reaction cut 0.70 s earlier (frame 1433), same source shot (its source cut is at 1279.40)
    ('''    Shot(56.26, 60.40, "BR16H", 1399.0, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed (v9: in 1399.0, out 0.80 s earlier for the reaction hold)"),
    Shot(60.40, 61.90, "BR", 1280.2, push=(1.0, 1.04), note="Mission Control: the reaction, held 1.50 s (v9; source continuous 1280.2-1282.2)"),''',
     '''    Shot(56.26, 59.70, "BR16H", 1399.0, speed=0.5, push=(1.0, 1.14), note="16mm: touchdown, half speed (v12: out at 59.70, 0.70 s earlier for the reaction)"),
    Shot(59.70, 61.90, "BR", 1279.49, push=(1.0, 1.04), note="Mission Control: the reaction, 2.20 s (v12: in 1279.49 = 1280.2 - 17/24; source shot starts at 1279.40)"),'''),
]
s = apply(s, R, "build")
save(P, s)
print(f"v12: build {len(R)} patches (DSKY, s23 note, reaction cut); score unchanged. "
      f"Re-render shots 30,31 (py build.py shots 12 30,31), then comp and mix (audio unchanged).")
