"""v17: Connor's notes on v16 (watched with sound), the provenance audit, the v16 blind A/B and the Fable editor review.
Apply to the v16 source (build.py + score_pd.py, tag v16-src = v15 + patch_v16 + patch_v16b):

    py patch_v17.py                      # the real build.py + score_pd.py in work/
    py patch_v17.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS (tl = t below frame
799, (fi + 161) / 24 from it; logical = real + 6.7 after 33.3). TIMELINE CHANGE: TOTAL 81.8 -> 87.0 (1963 -> 2088
frames; only the credits BLACK shot s41 grows, 78.8-87.0); every cut and the 799/161 map unchanged.
 1  0:33 MOON CUT MUSIC: v16b's sub hit (Haunted Metal _60 at 33.3) removed. Crossfade: Dvorak iv runs to src 41.45 with
    a 1.3 s equal-power fade 32.15-33.45; Egmont pre-laps 1.0 s (src 432.15 at 32.30, u^2 fade-in, full on the cut; src
    433.15 stays on 33.3). AUTO_CLAMP gives each piece its own side of the 33.3 automation step. Emulated: the pieces
    are within 10 dB only 32.85-33.05 (about -29 dBFS each); music stem -19 -> -25 -> -22 dBFS, no gap.
 2  0:45 DSKY: the right-side panel fades over frames 1090-1095 and is not drawn from frame 1096 (the LM-window cut;
    v16 drew it top-left 1096-1105). Visible on the MC shot 1054-1095 (1.75 s; panel >= 210 alpha 1.58 s).
 3  1:02: the dry Egmont stop stays on 61.9 (on the white flash) and rings out: a convolved hall tail (RT60 1.6 s,
    -8 dB) decays with the flash and the black; no digital zero on the music bus; room tone 61.92-63.5; Largo fade-in
    1.4 -> 1.8 s smoothstep from 62.9 (with the picture's fade-up). Emulated mix below -50 dBFS only 62.80-63.05.
 4  CREDITS: card 1 4.5 s (logical 85.55-90.05 = real 78.85-83.35), card 2 3.0 s (90.05-93.05 = 83.35-86.35, "DIRECTED BY
    CONNOR KERSTING" + 4 lines, Anton / Bebas), both centred on the frame; the Largo runs to src 28.6 with a 1.8 s fade
    to 86.3, then 0.7 s of digital silence to 87.0. The Haunted Metal _18 sub (76.7) runs 9.0 s (was cut by the v16
    file end) and decays inside the film.
 5  REBUILD: stage_dialog recreates a missing restored window from RESTORE_WINDOWS (patch_v16b's exact step; never
    overwrites). Dry run: restore/ascent.wav reproduced bit-exactly.
 a  "Staging." / "And ignition." tag APOLLO 11 · ARMSTRONG -> ARMSTRONG (picture: Apollo 4/6 or unidentified film).
 b  Credits: "SATURN V LAUNCH AND STAGING SHOTS INCLUDE ENGINEERING FILM FROM OTHER FLIGHTS" on its own line (5 lines).
 c  Countdown HUD only over the L70 70mm shots (frames 30-92 and 284-311), eased in / out (max 61/255 per frame).
 d  (limb / Eagle swap NOT made: the DAY 5 card would sit on the Eagle shot's lit lunar surface, luma ~125 vs ~1.)
 e  "40 feet, down 2½." 57.625-58.95 / "Picking up some dust." 59.05-60.20 (was one caption to 60.15). Readout steps
    held to the captions (READOUT_HOLDS): 40 FT to 58.95, 30 FT under "Picking up some dust.", 20 FT from the Mission
    Control cut (60.208) before "30 seconds."; 0 contradicting frames. Readout simplified for phone size.
 f  TOUCHDOWN: the 28.0 Bluezone impact reused on the 56.2 white flash at -4 dB, out of the duck 56.15-56.45 (release
    by 56.6, before "Houston"); title bed (music + SFX) -1.5 dB 10.6-19.0 (BED_DIP; the dynamic loudnorm absorbs most of
    it). Emulated momentary max: touchdown -9.3 vs drop -9.9 LUFS; landing the loudest section (+0.6 LU).
 g  STAGING LINES: +4 dB presence bell at 3.2 kHz (Q 0.8) on DIALOG 2 and 3 (new per-entry DIALOG_PRESENCE; none
    existed); a quiet comm tick (Bluezone UI high-tech beep, 80 ms, 4.7 kHz, -30 dB) at 26.17 before "Staging.".
Not changed: the INBOARD ENGINE CUTOFF cleanup (a widened key leaves visible smears on the trajectory; see report).
Re-render: py build.py shots 17 41 (only the credits black grows), dialog 17, music 17, comp 17, mix 17.
QC tools that assume 81.8: panel.py intended-black "79.0-81.8" (x2), audio_qc.py SECTIONS, promote.py EXPECT frames 1963,
data/provenance.csv credits BLACK row, gemini_critic.py 82 s bound, codex_critic.py prompt.
"""
import sys
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
assert "def asc_label_clean(" in s, "apply patch_v16 + patch_v16b first (tag v16-src)"
assert "def credits2(" not in s and "RESTORE_WINDOWS" not in s, "v17 already applied"
R = [
    ('''import json
import math
import subprocess
''', '''import json
import math
import os
import subprocess
'''),
    # ---- 4: the timeline grows by the second card
    ('''TOTAL = 81.8            # v8: act 2 is 6.7 s shorter (v7: 88.5)''',
     '''TOTAL = 87.0            # v17: credits 4.5 s + a 3.0 s second card + 0.7 s silence (v8-v16: 81.8; v7: 88.5)'''),
    ('''    Shot(78.80, 81.80, "BLACK", note="credits"),''',
     '''    Shot(78.80, 87.00, "BLACK", note="credits; v17: card 1 78.85-83.35, card 2 83.35-86.35, black + silence to 87.0"),'''),
    # ---- a: speaker tags (Apollo 11 audio over probably Apollo 4/6 engineering film)
    ('''    (26.55, 27.25, "APOLLO 11 · ARMSTRONG", "Staging."),''',
     '''    (26.55, 27.25, "ARMSTRONG", "Staging."),          # v17: tag was "APOLLO 11 · ARMSTRONG" (picture: unidentified Saturn V film)'''),
    ('''    (28.30, 29.15, "APOLLO 11 · ARMSTRONG", "And ignition."),''',
     '''    (28.30, 29.15, "ARMSTRONG", "And ignition."),     # v17: tag was "APOLLO 11 · ARMSTRONG" (picture: Apollo 4/6 interstage film, probable)'''),
    # ---- e: split the 40-feet caption at the speech so it never sits over the readout's 30 / 20 FT
    ('''    (57.50, 60.15, "EAGLE · ALDRIN", "40 feet, down 2½. Picking up some dust."),''',
     '''    # v17: split at the speech (pao_land.wav envelope: "Forty feet, down two and a half" src 25.68-26.84 = tl 57.68-58.84,
    # "Picking up some dust" 27.46-28.15 = tl 59.46-60.15): 12.8 cps / 18.3 cps. Part 1 starts with the readout's 40 FT
    # (frame 1222, tl 57.625, one frame before "Forty"), which holds through it (READOUT_HOLDS); no number on screen
    # contradicts part 2 or "30 seconds."
    (57.625, 58.95, "EAGLE · ALDRIN", "40 feet, down 2½."),
    (59.05, 60.20, "EAGLE · ALDRIN", "Picking up some dust."),'''),
    # ---- e: the readout's altitude steps follow the captions, the unspoken 30 -> 20 falls on the Mission Control cut
    ('''        g = get_at(min(t, contact))
        alt = down = fwd = None''',
     '''        g = readout_get(min(t, contact))      # v17: caption-held steps (READOUT_HOLDS), not the raw GET map
        alt = down = fwd = None'''),
    ('''        t_step = tl_of_get(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0''',
     '''        t_step = readout_step_t(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0'''),
    # ---- 5: Staging lines: presence lift (whisper recall 0 on v16)
    ('''    for src, a, b, t, g in DIALOG:
        x = load_audio(src, a, b)
        x = biquad(x, "hp", 120.0)
        x = biquad(x, "lp", 7000.0)
''',
     '''    for k_, (src, a, b, t, g) in enumerate(DIALOG):
        x = load_audio(src, a, b)
        x = biquad(x, "hp", 120.0)
        x = biquad(x, "lp", 7000.0)
        if k_ in DIALOG_PRESENCE:                # v17: per-entry presence lift (before the level match)
            x = presence(x, DIALOG_PRESENCE[k_])
'''),
    # ---- e: the readout for phone size: small grey header, ALT big, DOWN on one line, FWD only when the call states it
    ('''        alt = down = fwd = None''', '''        alt = down = fwd = fwd_now = None'''),
    ('''                if cf is not None:
                    fwd = cf
''',
     '''                if cf is not None:
                    fwd = cf
                fwd_now = cf          # v17: FWD only while the latest call states it
'''),
    ('''        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
        x0, y0 = 1320, 510
        if t < 61.79:              # dark plate for the 16mm dust and the white shirts in Mission Control (as the bingo)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 318], radius=12, fill=(0, 0, 0, int(150 * a)))
        lab = WHITE if held else AMBER
        self.text(d, (x0, y0), "ALDRIN'S CALLOUTS", "bebas40", lab, "la", a, track=3)''',
     '''        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
        x0, y0 = 1320, 510
        if "bebas72" not in self.f:
            self.f["bebas72"] = font("bebas", 72)
        if t < 61.79:              # dark plate for the 16mm dust and the white shirts in Mission Control (as the bingo)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 318], radius=12, fill=(0, 0, 0, int(150 * a)))
        lab = WHITE if held else AMBER
        # v17 (blind A/B on v16: tiny / cluttered at sheet size): the header is a small grey label; ALT anton150; one
        # DOWN line (bebas72 value); FWD on a second line only while the latest call states it; no TIME-COMPRESSED
        # label here (the bingo directly above carries it)
        self.text(d, (x0, y0), "ALDRIN'S CALLOUTS", "bebas34", (190, 190, 190), "la", a * 0.9, track=3)'''),
    ('''        if held:
            self.text(d, (x0, y0 + 180), "CONTACT", "anton96", WHITE, "ls", a)
        else:
            nw = self.text(d, (x0, y0 + 180), f"{alt}", "anton150", AMBER if fresh else WHITE, "ls", a)
            self.text(d, (x0 + nw + 14, y0 + 180), "FT", "bebas48", AMBER, "ls", a, track=2)
        ra = a * (0.35 if held else 1.0)
        down_s = f"{down:.1f}" if down is not None else "-"
        fwd_s = f"{fwd:g}" if fwd is not None else "-"
        x = x0
        for name, val in (("DOWN", down_s), ("FWD", fwd_s)):
            x += self.text(d, (x, y0 + 250), name, "bebas40", lab, "ls", ra, track=2) + 10
            x += self.text(d, (x, y0 + 250), val, "bebas60", WHITE, "ls", ra) + 8
            x += self.text(d, (x, y0 + 250), "FT/S", "bebas40", lab, "ls", ra, track=2) + 40
        self.text(d, (x0, y0 + 266), "TIME-COMPRESSED", "bebas40", (190, 190, 190), "la", a * 0.8, track=3)''',
     '''        if held:
            self.text(d, (x0, y0 + 170), "CONTACT", "anton120", WHITE, "ls", a)
        else:
            nw = self.text(d, (x0, y0 + 170), f"{alt}", "anton150", AMBER if fresh else WHITE, "ls", a)
            self.text(d, (x0 + nw + 14, y0 + 170), "FT", "bebas60", AMBER, "ls", a, track=2)
        ra = a * (0.35 if held else 1.0)
        rows = [("DOWN", f"{down:.1f}" if down is not None else "-")]
        if fwd_now is not None and not held:
            rows.append(("FWD", f"{fwd_now:g}"))
        for k_, (name, val) in enumerate(rows):
            yb_ = y0 + 238 + 64 * k_
            x = x0
            x += self.text(d, (x, yb_), name, "bebas48", lab, "ls", ra, track=2) + 12
            x += self.text(d, (x, yb_), val, "bebas72", WHITE, "ls", ra) + 10
            self.text(d, (x, yb_), "FT/S", "bebas48", lab, "ls", ra, track=2)'''),
    # ---- 5: restored windows a fresh checkout can rebuild
    ('''def stage_dialog() -> None:
    AUD.mkdir(parents=True, exist_ok=True)
''',
     '''# v17: restored windows that only a patch used to create (Codex on v16: DIALOG needs restore/ascent.wav, which only
# patch_v16b made). name -> (source under WORK, start s, length s); the same step as patch_v16b: ffmpeg stream copy of the
# window, then craft_tools.restore audio at its default strength (it reproduces restore/countdown.wav bit-exactly).
CRAFT = Path(r"craft-tools")
RESTORE_WINDOWS = {"ascent.wav": ("activities_tail.wav", 420.0, 20.0)}


def ensure_restored(path: Path) -> None:
    """Create a missing restored window from RESTORE_WINDOWS. Never overwrites (exists -> return; ffmpeg -n)."""
    if path.exists():
        return
    if path.name not in RESTORE_WINDOWS:
        raise SystemExit(f"missing {path} and no RESTORE_WINDOWS recipe for it")
    src, ss, dur = RESTORE_WINDOWS[path.name]
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = path.with_name(path.stem + "_raw.wav")
    if not raw.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-ss", f"{ss:g}", "-t", f"{dur:g}", "-i", str(WORK / src),
                        "-c", "copy", str(raw)], check=True)
    tmp = CRAFT / ".tmp"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TMP=str(tmp), TEMP=str(tmp), PYTHONUTF8="1")
    r = subprocess.run(["uv", "run", "python", "-m", "craft_tools.restore", "audio", str(raw), str(path)], cwd=CRAFT,
                       env=env, capture_output=True, text=True)
    if r.returncode != 0 or not path.exists():
        raise SystemExit(f"restore of {path.name} failed:\\n{r.stderr[-1500:]}")
    print(f"  restored window written: {path} ({r.stdout.strip()})")


# v17: per-DIALOG-index presence lift in dB (RBJ peaking EQ, 3.2 kHz, Q 0.8: about 2.3-4.5 kHz), applied before the
# level match. Armstrong's "Staging." / "And ignition." (indices 2, 3: whisper recall 0 on the v16 mix)
DIALOG_PRESENCE = {2: 4.0, 3: 4.0}


def presence(x: np.ndarray, gain_db: float, f0: float = 3200.0, q: float = 0.8) -> np.ndarray:
    """RBJ peaking biquad (pure Python loop like biquad(): short clips only)."""
    A = 10 ** (gain_db / 40)
    w0 = 2 * math.pi * f0 / SR
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    b0, b1, b2, a0, a1, a2 = 1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        xi = float(x[i])
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


def stage_dialog() -> None:
    AUD.mkdir(parents=True, exist_ok=True)
    for src in dict.fromkeys(x[0] for x in DIALOG):      # v17: rebuild a missing restored window (never overwrites)
        ensure_restored(src)
'''),
    # ---- 2: DSKY fade before the internal LM-window cut; c: HUD only over the L70 shots
    ('''DSKY_LEFT_T = 52.37      # v12: s23's (v14 s26, v15 s25) source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again
''',
     '''DSKY_LEFT_T = 52.37      # v12: s23's (v14 s26, v15 s25) source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again
# v17: the right-side panel fades out over the 6 frames before frame 1096 (tl 52.104 -> 52.375) and is not drawn from it
# on: v16 drew it top-left again for 0.43 s (52.375-52.8), "switches sides of the screen for a split second"
DSKY_OUT = ((1089.5 + ACT2_DF) / FPS, (1096 + ACT2_DF) / FPS)


def l70_window(t: float) -> float:
    """v17 provenance: 0..1 visibility of the APOLLO 11 / LAUNCH COMPLEX 39A countdown HUD: only while an Apollo 11
    70mm (L70) shot is on screen. Eases in over 0.25 s from each L70 run's first frame and out to 0 on its last frame
    (frame-rounded cuts, as the segments). Before the Moon cut, so logical == real."""
    runs: list[list[int]] = []
    for s in SHOTS:
        f0, f1 = int(round(s.t0 * FPS)), int(round(s.t1 * FPS))
        if s.src == "L70":
            if runs and runs[-1][1] == f0:
                runs[-1][1] = f1
            else:
                runs.append([f0, f1])
    for f0, f1 in runs:
        a, b = f0 / FPS, (f1 - 1) / FPS
        if a - 1e-9 <= t <= b + 1e-9:
            return ease_in_out((t - a) / 0.25) * ease_in_out((b - t) / 0.25)
    return 0.0


# v17: the altitude readout's own step times (logical) from Aldrin's "40 feet" on: 40 FT holds through the caption that
# speaks it ("40 feet, down 2½." to 58.95), 30 FT (ALSJ 102:45:21, not in the edit's audio) from there under "Picking up
# some dust.", and the unspoken 30 -> 20 step falls on the Mission Control cut (frame 1284, tl 60.208), before Duke's
# "30 seconds." (60.3), so that caption sits next to 20 FT (ALSJ: 20 ft at 102:45:25, "30 seconds" at :31).
# (time, GET held): before the first entry the readout reads the shared GET map (bingo clock) as in v16.
READOUT_HOLDS = [(57.625, 17.0), (58.95, 21.0), ((1284 + ACT2_DF) / FPS, 25.0)]


def readout_get(tl: float) -> float:
    if tl < READOUT_HOLDS[0][0]:
        return get_at(tl)
    g = READOUT_HOLDS[0][1]
    for t_, g_ in READOUT_HOLDS:
        if tl >= t_:
            g = g_
    return g


def readout_step_t(g_alt: float) -> float:
    """Logical time at which the readout steps to the call made at GET g_alt."""
    for t_, g_ in READOUT_HOLDS:
        if abs(g_ - g_alt) < 1e-9:
            return t_
    return tl_of_get(g_alt)
'''),
    ('''        if 47.2 <= t < 52.8:
            self.dsky(d, t - 47.2, right=DSKY_RIGHT_T <= t < DSKY_LEFT_T)''',
     '''        if 47.2 <= t < DSKY_OUT[1]:      # v17: gone from the LM-window cut (frame 1096); v16 ran to 52.8 top-left
            self.dsky(d, t - 47.2, right=DSKY_RIGHT_T <= t)'''),
    ('''        a = min(1.0, u / 0.1) * (1 - ease_in_out((u - 5.3) / 0.3))''',
     '''        # v17: out over the 6 frames before the LM-window cut (was 52.5-52.8, after it)
        a = min(1.0, u / 0.1) * (1 - ease_in_out((u + 47.2 - DSKY_OUT[0]) / (DSKY_OUT[1] - DSKY_OUT[0])))'''),
    ('''        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))''',
     '''        a = min(1.0, t / 0.25) * (1 - ease_in_out((t - 12.4) / 0.6))
        a *= l70_window(t)       # v17 provenance: only over the Apollo 11 70mm shots (not the BR / SV launch film)'''),
    # ---- 4 + b: credits: card 1 fades out, five lines; card 2
    ('''        if 85.55 <= t < 88.5:
            self.credits(d, t - 85.55)''',
     '''        if 85.55 <= t < 90.05:   # v17: 4.5 s (was 2.95 s to the end of the film), real 78.85-83.35
            self.credits(d, t - 85.55)
        if 90.05 <= t < 93.05:   # v17: second card 3.0 s, real 83.35-86.35; black + silence after it to 87.0
            self.credits2(d, t - 90.05)'''),
    ('''        a = ease_out(u / 0.4)
        # v10: three lines; the disclaimer ~20% larger (body41 vs body34); all inside title safe x 96-1824
        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, BEETHOVEN (PD)", "body34", WHITE, 62),
                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA  ·  SOME LAUNCH SHOTS FROM OTHER SATURN V FLIGHTS", "body34", WHITE, 62),''',
     '''        a = ease_out(u / 0.4) * (1 - ease_in_out((u - 4.1) / 0.35))     # v17: 4.5 s, out by 90.0 for the second card
        # v10: three lines; the disclaimer ~20% larger (body41 vs body34); all inside title safe x 96-1824
        # v17 provenance: the launch/staging disclosure on its own line (joined it is wider than title safe); five
        # lines, steps 58/58/58/66; v17: block centred on the frame (first/last line centres 420/660, was centre 396)
        lines = [("NASA FOOTAGE, PHOTOS & MISSION AUDIO (PUBLIC DOMAIN)  ·  MUSIC: DVOŘÁK, BEETHOVEN (PD)", "body34", WHITE, 58),
                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA", "body34", WHITE, 58),
                 ("SATURN V LAUNCH AND STAGING SHOTS INCLUDE ENGINEERING FILM FROM OTHER FLIGHTS", "body34", WHITE, 58),'''),
    ('''                 ("CUT BY AN AI AGENT LOOP (CLAUDE CODE) FROM NASA SOURCE MATERIAL", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 299
        for s, f, c, step in lines:
            self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += step
''',
     '''                 ("CUT BY AN AI AGENT LOOP (CLAUDE CODE) FROM NASA SOURCE MATERIAL", "body34", WHITE, 66),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 420
        for s, f, c, step in lines:
            self.text(d, (W / 2, y), s, f, c, "mm", a)
            y += step

    def credits2(self, d, u):
        """v17: second card (real 83.35-86.35, logical 90.05-93.05), house style (Anton name line, Bebas below),
        centred on y 540, inside title safe x 96-1824 (measured with the real fonts in the v17 dry run). In 0.35 s,
        out 2.5-2.9 (gone at real 86.25, before the Largo's fade ends at 86.3 and the 0.7 s of silence)."""
        a = ease_out(u / 0.35) * (1 - ease_in_out((u - 2.5) / 0.4))
        if a <= 0:
            return
        self.text(d, (W / 2, 432), "DIRECTED BY CONNOR KERSTING", "anton96", WHITE, "ms", a, track=4)
        d.rectangle([W / 2 - 60, 462, W / 2 + 60, 466], fill=AMBER + (int(220 * a),))
        self.text(d, (W / 2, 534), "M.S. BUSINESS ANALYTICS & ARTIFICIAL INTELLIGENCE CANDIDATE", "bebas48", WHITE, "ms", a, track=3)
        self.text(d, (W / 2, 592), "HASLAM COLLEGE OF BUSINESS  ·  THE UNIVERSITY OF TENNESSEE, KNOXVILLE", "bebas48",
                  (200, 210, 220), "ms", a, track=3)
        self.text(d, (W / 2, 660), "LINKEDIN.COM/IN/CONNORKERSTING", "bebas48", AMBER, "ms", a, track=4)
        self.text(d, (W / 2, 740), "PERSONAL PROJECT  ·  NOT AFFILIATED WITH OR ENDORSED BY UT OR NASA", "bebas40",
                  (190, 190, 190), "ms", a * 0.95, track=3)
'''),
    # ---- touchdown transient out of the duck; title bed (music + SFX) -1.5 dB
    ('''    sgain = gain                                # SFX get the full computed depth (Codex #3)
    for i0s, i1s in ():   # v9: impacts duck with the bed (unducking buried the launch lines)
        sgain = sgain.copy()
        sgain[int(i0s * SR):int(i1s * SR)] = 1.0
    bed = music * gain[:, None] + sfx * sgain[:, None]
''',
     '''    sgain = gain                                # SFX get the full computed depth (Codex #3)
    for i0s, i1s in ():   # v9: impacts duck with the bed (unducking buried the launch lines)
        sgain = sgain.copy()
        sgain[int(i0s * SR):int(i1s * SR)] = 1.0
    # v17: SFX windows that escape the duck (start, end, release s): the touchdown impact on the 56.2 white flash sits in
    # the "Contact light" release / "Houston" pre-roll (~15-19 dB of duck); 20 ms in, cosine back to the duck by 56.6,
    # before Armstrong's first word (~56.7)
    tt_ = np.arange(n) / SR
    for u0, u1, rel in SFX_UNDUCK:
        w_ = np.interp(tt_, [u0 - 0.02, u0, u1, u1 + rel], [0.0, 1.0, 1.0, 0.0]).astype(np.float32)
        w_ = 0.5 - 0.5 * np.cos(np.pi * w_)
        sgain = sgain + (1.0 - sgain) * w_
    bed = music * gain[:, None] + sfx * sgain[:, None]
    # v17: the title bed (music + SFX, 10.6-19.0) -1.5 dB (ramps 10.50-10.58 and 19.0-19.4), dialogue untouched, so the
    # touchdown is the loudest moment (Fable editor on v16)
    for d0, d1, ddb in BED_DIP:
        bed *= (10 ** (np.interp(tt_, [d0 - 0.10, d0 - 0.02, d1, d1 + 0.4], [0.0, ddb, ddb, 0.0]) / 20)).astype(np.float32)[:, None]
'''),
    ('''def stage_mix() -> None:
''', '''SFX_UNDUCK = [(56.15, 56.45, 0.15)]      # v17: (start, end, release s), see stage_mix
BED_DIP = [(10.6, 19.0, -1.5)]           # v17: (start, end, dB) on music + SFX


def stage_mix() -> None:
'''),
    # ---- 3: room tone through the short breath before the Largo is audible, faded out under it
    ('''    i0, i1 = int(61.92 * SR), int(62.9 * SR)       # v8 (v7: 68.62-69.6)
    tone = rng.normal(0, 1, (i1 - i0, 2)).astype(np.float32)
    tone = np.cumsum(tone, axis=0)
    tone -= np.linspace(tone[0], tone[-1], len(tone))
    tone *= 10 ** (-52 / 20) / max(np.sqrt(np.mean(tone ** 2)), 1e-9)
''',
     '''    i0, i1 = int(61.92 * SR), int(63.5 * SR)       # v17: to 63.5 (the Largo fades in from 62.9); v8 61.92-62.9
    tone = rng.normal(0, 1, (i1 - i0, 2)).astype(np.float32)
    tone = np.cumsum(tone, axis=0)
    tone -= np.linspace(tone[0], tone[-1], len(tone))
    tone *= 10 ** (-52 / 20) / max(np.sqrt(np.mean(tone ** 2)), 1e-9)
    fo_ = int(0.4 * SR)                            # v17: 0.4 s fade-out under the Largo
    tone[-fo_:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo_, dtype=np.float32)))[:, None]
'''),
]
s = apply(s, R, "build")
# ============================================================== score_pd.py
sc = load(S)
assert "def ring_out(" not in sc, "v17 already applied (score)"
RS = [
    ('''TOTAL = 81.8            # v8 (v7: 88.5)''', '''TOTAL = 87.0            # v17: credits 4.5 s + second card 3.0 s + 0.7 s silence (v8-v16 81.8; v7: 88.5)'''),
    # ---- 1: crossfade at the Moon cut
    ('''    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.12, 23.6, 0.0, 0.03, 0.10),''',
     '''    # v17: to src 41.45 (before the next phrase ~41.5) with a 1.3 s equal-power fade, 32.15 -> 33.45 (was out at 33.12)
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.45, 23.6, 0.0, 0.03, 1.30),'''),
    ('''    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 0.15, 0.03),   # v15: fade-in 2.5 -> 1.0 s; v16b: 0.15 s, the pp chord is in on the 33.3 cut''',
     '''    # v17: pre-lap 1.0 s (src 432.15 at 32.30: pp chords; 433.15 stays on 33.3), 1.0 s u^2 fade-in; out 0.06 s + ring-out
    (PD / "beethoven_egmont_overture_musopen.flac", 432.15, 461.75, 32.3, 0.0, 1.0, 0.06),   # v15: fade-in 2.5 -> 1.0 s; v16b: 0.15 s'''),
    ('''    (PD / "dvorak9_ii_largo.ogg", 5.2, 24.0, 62.9, 0.0, 1.4, 1.6),''',
     '''    # v17: fade-in 1.4 -> 1.8 s (smoothstep); to src 28.6 under both credit cards (the chorale's phrase ends ~24.2 =
    # 81.9, then the pp Db chord, -38..-40 dBFS in the source), 1.8 s smoothstep fade to 86.3, then 0.7 s of silence
    (PD / "dvorak9_ii_largo.ogg", 5.2, 28.6, 62.9, 0.0, 1.8, 1.8),'''),
    # ---- 3: touchdown transient + title bed dip; 4: the _18 sub decays inside the film; 5: comm tick before "Staging."
    ('''Sub_JF_Haunted Metal Vol 1_18.wav", 76.7, -5.0, "attack", 6.4),''',
     '''Sub_JF_Haunted Metal Vol 1_18.wav", 76.7, -5.0, "attack", 9.0),   # v17: 6.4 -> 9.0 s: decays to ~-62 dBFS by 84.5 inside the film (v16 was cut by the file end at 81.8)
    # v17: touchdown transient on the 56.2 white flash (the 28.0 stage-separation impact, reused)
    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 56.2, -4.0, "attack", 3.0),
    # v17: a quiet comm tick (quindar-like 80 ms beep, 4.7 kHz) before Armstrong's "Staging." (speech 26.55, duck from 26.25)
    ("BluezoneCorp - Futuristic User Interface/Bluezone_BC0303_futuristic_user_interface_high_tech_beep_038.wav", 26.17, -30.0, "attack", 0.08),'''),
    ('''# gain automation on the music bus: (time, dB), linear in dB between points''',
     '''# v17: fade shapes per MUSIC index (in, out): lin | sq (u^2) | sine (equal power) | ease (smoothstep); default lin/lin
FADE_SHAPE = {1: ("lin", "sine"), 2: ("sq", "lin"), 3: ("ease", "ease")}
# v17: per-entry automation across the 33.3 crossfade: MUSIC_AUTO is read at max(t, lo) / min(t, hi) for that entry, so
# the Dvorak holds the 33.2 value (-6.65 dB) while it fades and the Egmont pre-lap takes the 33.3 value (+11.5 dB)
AUTO_CLAMP = {1: (None, 33.2), 2: (33.3, None)}
# v17: ring-out after the Egmont hard stop (61.9): (window s, RT60 s, wet dB re the dry's last 100 ms, tail s)
RING_OUT = {2: (0.30, 1.6, -8.0, 1.8)}
# gain automation on the music bus: (time, dB), linear in dB between points'''),
    # ---- 1: the sub hit goes
    ('''    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_60.wav", 33.3, -9.0, "attack", 1.6),   # v16b: the hit on the Moon cut (cut before the file's second hit at ~1.8 s)
''', ''),
    ('''def stage_music() -> None:
    n = int(TOTAL * SR)
    mus = np.zeros((n, 2), np.float32)
    for src, a, b, t, g, fi, fo in MUSIC:
        x = load_stereo(src, a, b) * np.float32(10 ** (g / 20))
        k1, k2 = max(int(fi * SR), 1), max(int(fo * SR), 1)
        x[:k1] *= np.linspace(0, 1, k1, dtype=np.float32)[:, None]
        x[-k2:] *= np.linspace(1, 0, k2, dtype=np.float32)[:, None]
        place(mus, x, int(t * SR))
        print(f"  music {src.name} {a:.2f}-{b:.2f} @ {t:.2f}")
    tt = np.arange(n) / SR
    auto = np.interp(tt, [p[0] for p in MUSIC_AUTO], [p[1] for p in MUSIC_AUTO])
    mus *= (10 ** (auto / 20)).astype(np.float32)[:, None]
    mus[int(61.9 * SR):int(62.9 * SR)] = 0.0          # the silence after the flash (v8; v7 68.6-69.6)
''',
     '''def fade_curve(u: np.ndarray, kind: str) -> np.ndarray:
    """v17: gain for fade position u (0 = silent end, 1 = full)."""
    if kind == "sq":
        return u * u
    if kind == "sine":
        return np.sin(np.pi / 2 * u)
    if kind == "ease":
        return u * u * (3 - 2 * u)
    return u


def ring_out(x: np.ndarray, win: float, rt60: float, wet_db: float, tail: float) -> np.ndarray:
    """v17: a hall-style ring-out after a hard musical stop: the last `win` s of x (rising half-Hann) convolved with an
    exponentially decaying stereo noise IR (RT60 `rt60`, rolled off above 3 kHz; FFT convolution = afir). The wet is
    scaled so its first 50 ms after the stop sit `wet_db` under the dry's last 100 ms (before the dry's own fade), comes
    in over the dry's last 80 ms and runs `tail` s past the end (50 ms fade at its end). Returns x + tail samples."""
    nw, nt = int(win * SR), int(tail * SR)
    seg = x[-nw:].astype(np.float64) * np.hanning(2 * nw)[:nw, None]
    rng = np.random.default_rng(1969)
    ir = rng.normal(0, 1, (nt, 2)) * np.exp(-6.908 * np.arange(nt) / SR / rt60)[:, None]
    f = np.fft.rfftfreq(nt, 1 / SR)
    ir = np.fft.irfft(np.fft.rfft(ir, axis=0) * np.exp(-0.5 * (np.maximum(f - 3000, 0) / 2500) ** 2)[:, None], n=nt, axis=0)
    m = nw + nt
    nfft = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(seg, nfft, axis=0) * np.fft.rfft(ir, nfft, axis=0), nfft, axis=0)[:m]
    rms = lambda y: float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))  # noqa: E731
    ref = rms(x[-int(0.16 * SR):-int(0.06 * SR)])
    wet *= ref * 10 ** (wet_db / 20) / max(rms(wet[nw:nw + int(0.05 * SR)]), 1e-12)
    xf = int(0.08 * SR)
    wet *= np.clip((np.arange(m) - (nw - xf)) / xf, 0, 1)[:, None]
    fe = int(0.05 * SR)
    wet[-fe:] *= np.linspace(1, 0, fe)[:, None]
    out = np.zeros((len(x) + nt, 2), np.float32)
    out[:len(x)] = x
    out[len(x) - nw:] += wet.astype(np.float32)
    return out


def stage_music() -> None:
    n = int(TOTAL * SR)
    mus = np.zeros((n, 2), np.float32)
    ax, ay = [p[0] for p in MUSIC_AUTO], [p[1] for p in MUSIC_AUTO]
    for i, (src, a, b, t, g, fi, fo) in enumerate(MUSIC):
        x = load_stereo(src, a, b) * np.float32(10 ** (g / 20))
        k1, k2 = max(int(fi * SR), 1), max(int(fo * SR), 1)
        shp_in, shp_out = FADE_SHAPE.get(i, ("lin", "lin"))
        x[:k1] *= fade_curve(np.linspace(0, 1, k1, dtype=np.float32), shp_in)[:, None]
        x[-k2:] *= fade_curve(np.linspace(1, 0, k2, dtype=np.float32), shp_out)[:, None]
        if i in RING_OUT:
            x = ring_out(x, *RING_OUT[i])
        # v17: MUSIC_AUTO per entry (was one bus multiply: identical for unclamped entries), clamped by AUTO_CLAMP
        lo, hi = AUTO_CLAMP.get(i, (None, None))
        te = (int(t * SR) + np.arange(len(x))) / SR
        te = np.clip(te, -np.inf if lo is None else lo, np.inf if hi is None else hi)
        x *= (10 ** (np.interp(te, ax, ay) / 20)).astype(np.float32)[:, None]
        place(mus, x, int(t * SR))
        print(f"  music {src.name} {a:.2f}-{b:.2f} @ {t:.2f}")
    # v17: no digital zero 61.9-62.9 any more (v8-v16): the Egmont rings out into it and the Largo fades in from 62.9
'''),
]
sc = apply(sc, RS, "score")
save(P, s)
save(S, sc)
print(f"v17: build {len(R)} patches, score {len(RS)}. TOTAL 87.0 (2088 frames). Re-render: py build.py shots 17 41, "
      f"dialog 17, music 17, comp 17, mix 17.")
