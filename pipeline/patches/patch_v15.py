"""v15: senior-editor notes on v14 (8.0). Apply to the v14 source (build.py + score_pd.py, tag v14-src).

    py patch_v15.py                      # the real build.py + score_pd.py in work/
    py patch_v15.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS
(tl = t below frame 799, (fi + 161) / 24 from it).
TIMELINE FREEZE: TOTAL 81.8 / 1963 frames, the 799/161 logical map, every cut outside real 26.5-40.3 and DIALOG are
unchanged.
 1  TLI counter (stat_speed): runs 17,400 -> 24,200 MPH with the same timing (holds 17,400 to u 0.4, ease-out to
    u 1.6), not 0 -> 24,200 (the ascent HUD showed 5,901 MPH two seconds earlier). 17,400 = Earth parking-orbit speed
    before the TLI burn (25,567 ft/s = 17,432 mph). Label unchanged; a sub-label "FROM 17,400 IN EARTH ORBIT" (bebas40,
    baseline 1004) under the number, inside title safe.
 2  Lunar energy dip: Egmont fade-in 2.5 -> 1.0 s; MUSIC_AUTO +1.5 dB in 33.3-39.9, ramped back to
    v14's +8.0 dB by 40.3 so the 1202 section's bed (and its adaptive ducks) start where v14's did. Emulated with the
    real 2-pass loudnorm: lunar -16.7 -> -15.5 LUFS (momentary at 34.3: -21.6 -> -16.5), 1202 -14.1 -> -14.3, bingo
    -13.2 -> -13.3, landing -11.0 -> -11.1 (still the loudest); dialogue-to-bed unchanged (worst +11.0 dB, the 11.40
    liftoff line, as v14). No low bed under 31.0-33.3: it measures -14.6 LUFS (momentary -11.5..-16.6), not the dip.
 3  Staging: s16 26.50-27.25 (0.75 s, src 940.75: the plume rises from bottom-left to mid-left, upper right empty sky);
    no music onset between 26.85 and 27.71, so the cut sits on the 0.75 s mark. s17 (ring) gains the 0.75 s: in at
    27.25 on src 987.80 (lit ring, S-II ignition glow building); its src->timeline map from 28.0 on equals v14's, so
    the white-out (src 988.3-988.55) still peaks on the 28.0 Bluezone impact (kept at 28.0: it lands on the flash,
    not on an unaccented cut). STAGE SEPARATION label: bebas72, upper right over empty sky (x <= 1808, y 150-222), 0.75 s.
 4  Caption: "Houston, ..." + "Tranquility Base here." -> one caption 63.40-66.85 (31 chars / 3.45 s = 9.0 cps; ends
    0.25 s before "The Eagle has landed." at 67.10).
 5  Moon render (s20 33.30-35.58): new GRADE["CG16"] applied by render_seq through Shot.grade: black lifted toward the
    16mm black (teal-green, like the neighbouring 16mm), a faint screen-blended glow (halation-like limb bloom),
    downscale 0.5x -> upscale (softness) with luma grain added at the low resolution (clumped, film-like). The s03
    flash-forward (same frames) is untouched. 240,000 MILES card: fades u 1.99-2.29, gone on the 35.58 cut (frame 854,
    tl 42.2917). Limb + terrain near-twins -> ONE 3 s shot 37.30-40.30: BR 1206.0-1209.0 (terrain, low oblique,
    black sky top third under the DAY 5 card; take 1205.77-1214).
 6  L70 grade (the 70mm pad only, s01 / s02 / s11 / s12): curves g 0.5 -> 0.465 (green pulled ~8 levels in the mids;
    whites stay warm, green never drops below blue: no magenta). The firing room (BR) measured neutral on v14
    (mid-tone G-(R+B)/2 -0.6 at 0.6 s): its grade is shared by every BR shot, left alone.
Shots 42 -> 41 (indices after s22 shift by -1). Re-render: py build.py shots 15 (FULL run), music 15, comp 15, mix 15.
Dialogue stem unchanged (stage dialog not needed).
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
    # ---- 6: L70 green pull; 5: the CG film grade (new key, used only via Shot.grade)
    ('''    "L70": "eq=contrast=1.12:saturation=1.05:gamma=0.97,colorbalance=rs=0.05:gs=0.0:bs=-0.06:rh=0.04:bh=-0.04",
''',
     '''    "L70": "eq=contrast=1.12:saturation=1.05:gamma=0.97,colorbalance=rs=0.05:gs=0.0:bs=-0.06:rh=0.04:bh=-0.04,curves=g='0/0 0.5/0.465 1/0.97'",   # v15: green pulled (70mm pad)
    # v15: the Blender Moon (s20) toward the 16mm around it: black lifted to the 16mm teal-green black, faint screen glow
    # (halation-like limb bloom), 0.5x downscale with luma grain at the low res (clumped), back up (softness)
    "CG16": ("curves=r='0/0.008 1/1':g='0/0.032 1/1':b='0/0.022 1/1',split[cga][cgb];[cgb]gblur=sigma=18[cgg];"
             "[cga][cgg]blend=all_mode=screen:all_opacity=0.06,scale=960:540:flags=bicubic,format=yuv444p,"
             "noise=c0s=12:c0f=t+u,scale=1920:1080:flags=bicubic"),
'''),
    ('''    note: str = ""
''',
     '''    note: str = ""
    grade: str | None = None      # v15: SEQ only: a GRADE key appended to the render (CG -> 16mm match)
'''),
    # ---- 3 + 5: the window shots
    ('''    Shot(26.50, 28.00, "BRD", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky (STAGE SEPARATION label)"),
''',
     '''    Shot(26.50, 27.25, "BRD", 940.75, push=(1.0, 1.06), note="staging: the S-IC plume against blue sky (STAGE SEPARATION label); v15: 0.75 s (was 940.0 for 1.5 s), src 940.75-941.5: plume rises from bottom-left to mid-left, upper right empty"),
'''),
    ('''    Shot(28.00, 29.80, "BRD", 988.55, push=(1.0, 1.10), note="v14: S-II interstage ring: opens in the ignition flash (on the 28.0 impact), the ring emerges (src 989.0 = 28.45) and tumbles away over Earth"),
''',
     '''    Shot(27.25, 29.80, "BRD", 987.80, push=(1.0, 1.10), note="v14: S-II interstage ring; v15: in at 27.25 on src 987.80 (lit ring, ignition glow building), white-out src 988.3-988.55 peaks on the 28.0 impact (map from 28.0 = v14), the ring emerges (src 989.0 = 28.45) and tumbles away over Earth"),
'''),
    ('''    Shot(33.30, 35.58, "SEQ", speed=1.7, img="moon_blender/moon_%04d.png", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer; v14: 1.7x (55 fr x 1.7 = 94 of 96)"),
''',
     '''    Shot(33.30, 35.58, "SEQ", speed=1.7, img="moon_blender/moon_%04d.png", grade="CG16", note="Blender: photoreal Moon approach (NASA CGI Moon Kit) + star layer; v14: 1.7x (55 fr x 1.7 = 94 of 96); v15: CG16 film grade"),
'''),
    ('''    Shot(37.30, 38.71, "BR", 1176.0, push=(1.0, 1.10), note="v14: 16mm, the lunar limb from orbit, the limb rising, black sky top-left (DAY 5 chapter card)"),
    Shot(38.71, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v14: 16mm, low oblique horizon, terrain sliding, black sky top (chapter card); Egmont onset 38.71"),
''',
     '''    Shot(37.30, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v15: ONE 3 s shot (v14 limb 1176.0 + terrain were near-twins): 16mm low oblique horizon, terrain sliding, black sky top third under the DAY 5 chapter card (take 1205.77-1214)"),
'''),
    # ---- 5: render_seq applies Shot.grade (moon path only; the px_ parallax path is untouched)
    ('''[st][mo]overlay=shortest=1:format=rgb,format=yuv420p")''',
     '''[st][mo]overlay=shortest=1:format=rgb,{GRADE[s.grade] + ',' if s.grade else ''}format=yuv420p")'''),
    # ---- 4: one caption
    ('''    (63.40, 65.20, "EAGLE · ARMSTRONG", "Houston, ..."),                 # v10: real 56.7-58.5 ("Houston, uh")
    (65.60, 66.85, "EAGLE · ARMSTRONG", "Tranquility Base here."),       # v10: real 58.9-60.15
''',
     '''    (63.40, 66.85, "EAGLE · ARMSTRONG", "Houston, Tranquility Base here."),   # v15: one caption (v10 split at real 58.5/58.9), 9.0 cps
'''),
    # ---- 3: label window = the 0.75 s staging shot
    ('''        if 26.5 <= t < 28.0:     # v8: staging shot (before ACT2_T0, logical time == real time)
            self.stage_label(d, t - 26.5, 1.5)''',
     '''        if 26.5 <= t < 27.25:    # v8: staging shot (before ACT2_T0, logical time == real time); v15: 0.75 s
            self.stage_label(d, t - 26.5, 0.75)'''),
    ('''        """v8: small lower third over the staging shot, in label()'s style. Bottom-RIGHT inside safe (x <= 1808):
        the exhaust plume wanders over the left half of this shot (checked on v7 frames 30.1-31.4)."""
        a = ease_out(u / 0.3) * (1 - ease_in_out((u - (dur - 0.35)) / 0.35))
        s, f, track = "STAGE SEPARATION", "bebas48", 6
        tw = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
        x, y = 1808 - 22 - tw, 900
        d.rectangle([x, y, x + 6, y + 48], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 22, y - 2), s, f, WHITE, "la", a, track=track)''',
     '''        """v8: label over the staging shot, in label()'s style. v15: the shot is 0.75 s (src 940.75-941.5, the plume
        rising from bottom-left to mid-left): bebas72 (24 px at 640x360), right-aligned at x 1808 in the upper sky
        (y 150-222, clear of the plume on all 18 frames), fast
        in/out (0.12 / 0.14 s) so it holds ~0.5 s at full."""
        a = ease_out(u / 0.12) * (1 - ease_in_out((u - (dur - 0.14)) / 0.14))
        s, f, track = "STAGE SEPARATION", "bebas72", 8
        if f not in self.f:
            self.f[f] = font("bebas", 72)
        tw = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
        x, y = round(1808 - (tw + 30)), 150
        d.rectangle([x, y, x + 8, y + 72], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 30, y - 3), s, f, WHITE, "la", a, track=track)'''),
    # ---- 1: TLI counter from the parking-orbit speed + sub-label
    ('''        # v10: holds 0 while the Earth slides in, counts 0 -> 24,200 over u 0.4-1.6 (ease-out), then holds;
        # right-aligned, so "MPH" stays put
        val = int(round(24200 * ease_out((u - 0.4) / 1.2) / 10.0)) * 10''',
     '''        # v10: holds while the Earth slides in, counts over u 0.4-1.6 (ease-out), then holds; right-aligned, so "MPH"
        # stays put. v15: from 17,400 (Earth parking orbit before the burn: 25,567 ft/s = 17,432 mph), not from 0
        val = int(round((17400 + 6800 * ease_out((u - 0.4) / 1.2)) / 10.0)) * 10'''),
    ('''        self.text(d, (124, 700), "SPEED AT TRANSLUNAR INJECTION CUTOFF", "bebas40", AMBER, "ls", a * ease_out((u - 0.2) / 0.4), track=4)''',
     '''        self.text(d, (124, 700), "SPEED AT TRANSLUNAR INJECTION CUTOFF", "bebas40", AMBER, "ls", a * ease_out((u - 0.2) / 0.4), track=4)
        # v15: where the count starts (baseline 1004: clear of the number's comma, inside title safe y <= 1026)
        self.text(d, (124, 1004), "FROM 17,400 IN EARTH ORBIT", "bebas40", (200, 210, 220), "ls",
                  a * 0.9 * ease_out((u - 0.3) / 0.4), track=4)'''),
    # ---- 5: the 240,000 MILES card is gone on the 35.58 cut (frame 854 = tl 42.2917 -> u 2.2917)
    ('''        a = 1 - ease_in_out((u - 2.6) / 0.4)
        xl = 112''',
     '''        a = 1 - ease_in_out((u - 1.99) / 0.30)     # v15: out by the 35.58 cut (u 2.29; v14 rode 0.7 s into s21)
        xl = 112'''),
    # ---- comments: shot indices after the limb/terrain merge
    ('''(s23, v14 s26, frame 1054''', '''(s23, v14 s26, v15 s25, frame 1054'''),
    ('''# v12: s23's (v14 s26) source cuts back''', '''# v12: s23's (v14 s26, v15 s25) source cuts back'''),
]
s = apply(s, R, "build")
# ============================================================== score_pd.py
sc = load(S)
RS = [
    ('''    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 2.5, 0.03),''',
     '''    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 1.0, 0.03),   # v15: fade-in 2.5 -> 1.0 s'''),
    ('''(33.2, -6.65), (33.3, 8.5), (40.3, 8.0), (43.4, 7.0),''',
     '''(33.2, -6.65), (33.3, 10.0), (39.9, 9.5), (40.3, 8.0), (43.4, 7.0),'''),
    ('''MUSIC_AUTO = [''', '''# v15: lunar valley 33.3-39.9 +1.5 dB (v14 8.5 -> 8.0), ramps back to v14's 8.0 by 40.3; with the 1.0 s Egmont fade, emulated
# (real 2-pass loudnorm) lunar -16.7 -> -15.5 LUFS, 1202 -14.1 -> -14.3, bingo -13.2 -> -13.3, landing -11.0 -> -11.1 (loudest)
MUSIC_AUTO = ['''),
]
sc = apply(sc, RS, "score")
save(P, s)
save(S, sc)
print(f"v15: build {len(R)} patches, score {len(RS)}. "
      f"Re-render: py build.py shots 15 (FULL run: 42 -> 41 shots), music 15, comp 15, mix 15.")
