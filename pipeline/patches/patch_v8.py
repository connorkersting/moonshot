"""v8: act 2 compressed by 6.7 s (19.0-40.0 -> 19.0-33.3) so the story reaches the Moon and the 1202 sooner.

Apply to the v7 source (build.py + score_pd.py at commit "v7 source") and the QC helpers:
    py patch_v8.py                                  # the real files in work/
    py patch_v8.py BUILD.py SCORE.py HELPER_DIR     # dry run on copies (HELPER_DIR holds ab.py, qc.py, audio_qc.py)

Time model after v8:
  * REAL time (the v8 timeline): SHOTS, DIALOG, stage_mix (room tone), score_pd MUSIC / MUSIC_AUTO / SONNISS.
  * LOGICAL time (the v7 timeline): CAPTIONS, everything inside Gfx.draw / title_layer, GLITCH_WINDOWS and the
    flash blocks in stage_comp. The comp maps real -> logical per frame: tl = t before the Moon cut (frame 799),
    tl = (fi + 161) / FPS from it on (= t + 6.7 to within 0.2 frame, but exactly on the v7 frame grid).
  * Exceptions re-timed in draw() because their pictures moved inside act 2: the 24,200 MPH stat (v7 37-40 ->
    real 29.8-33.3) and a new STAGE SEPARATION lower third over the staging shot (real 26.5-28.0).
"""
import re
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"
HLP = Path(sys.argv[3]) if len(sys.argv) > 3 else W
D = 6.7          # seconds removed from act 2
T0 = 33.3        # new time of the old 40.0 (the cut to the Moon)


def fmt2(x: float) -> str:
    """SHOTS style: at least 2 decimals (33.30, 72.675)."""
    s = f"{round(x, 3):.3f}"
    return s[:-1] if s.endswith("0") else s


def fmt1(x: float) -> str:
    """DIALOG / SONNISS / MUSIC_AUTO style: at least 1 decimal (40.5, 43.75, 49.0)."""
    s = f"{round(x, 3):.3f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def apply(text: str, pairs: list[tuple[str, str]], what: str) -> str:
    for a, b in pairs:
        n = text.count(a)
        assert n == 1, f"{what}: {n} matches for {a[:90]!r}"
        text = text.replace(a, b)
    return text


EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build/score are CRLF, ab/audio_qc LF)."""
    EOL[path] = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    return path.read_text(encoding="utf-8")


def save(path: Path, text: str) -> None:
    path.write_text(text.replace("\n", EOL[path]), encoding="utf-8", newline="")


def block(text: str, start: str, end: str) -> tuple[int, int]:
    i0 = text.index(start)
    i1 = text.index(end, i0)
    return i0, i1


# ============================================================== build.py
s = load(P)
R = [
    # total + the act-2 constants the comp uses
    (r'''TOTAL = 88.5
NFRAMES = int(round(TOTAL * FPS))''',
     r'''TOTAL = 81.8            # v8: act 2 is 6.7 s shorter (v7: 88.5)
NFRAMES = int(round(TOTAL * FPS))
# v8 time model: SHOTS / DIALOG / mix are REAL time; CAPTIONS, Gfx.draw, title_layer, GLITCH_WINDOWS and the comp's
# flashes are LOGICAL (v7) time. The comp maps real -> logical: from the Moon cut on, logical = real + ACT2_D.
ACT2_T0 = 33.3                                    # real time of the cut to the Moon (v7: 40.0)
ACT2_D = 6.7                                      # seconds removed from act 2
ACT2_F0 = int(round(ACT2_T0 * FPS))               # 799: first Moon frame in v8
ACT2_DF = int(round(40.0 * FPS)) - ACT2_F0        # 161: the v7 Moon cut was frame 960'''),
    # cold open: open on motion (firing room), then the pad
    (r'''    # COLD OPEN (v5): Apollo 11 on the pad, first flames, then 1-s flash-forwards on the counts (promise of the story)
    Shot(0.00, 1.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.10), note="Apollo 11 on the pad, 70mm, push"),
    Shot(1.20, 2.20, "BR", 667.0, push=(1.0, 1.08), note="firing room wide (people moving)"),''',
     r'''    # COLD OPEN (v8): opens on motion (firing room), the pad, first flames, then 1-s flash-forwards on the counts
    Shot(0.00, 1.20, "BR", 667.0, push=(1.0, 1.08), note="firing room wide (people moving): v8 opens on motion"),
    Shot(1.20, 2.20, "L70", 3.8, crop="980:551:470:150", push=(1.0, 1.10), note="Apollo 11 on the pad, 70mm, push"),'''),
    # act 2: 21 s -> 14.3 s
    (r'''    # ACT 2: ascent, stats, data-viz
    Shot(19.00, 22.00, "SV", 70.0, push=(1.0, 1.06), darken=0.1, note="F-1 engine bells (stat 1)"),
    Shot(22.00, 23.00, "BR", 789.6, push=(1.0, 1.08), note="fin and falling debris (trimmed, was blown out)"),
    Shot(23.00, 26.00, "SV", 122.2, push=(1.04, 1.0), darken=0.18, note="ice sheets falling past"),
    Shot(26.00, 30.00, "SEQ", 1.0, speed=2.0, img="ascent_blender_v3/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values"),
    Shot(30.00, 33.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky"),
    Shot(33.00, 37.00, "BR", 961.0, push=(1.0, 1.08), note="interstage falls away over Earth"),
    Shot(37.00, 40.00, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.55)), note="Apollo 11 Earth on translunar coast, pulling away (stat: TLI speed)"),''',
     r'''    # ACT 2 (v8: 19.0-33.3, was 19.0-40.0): thrust stat, 3D ascent, staging, interstage, TLI speed
    Shot(19.00, 22.00, "SV", 70.0, push=(1.0, 1.06), darken=0.1, note="F-1 engine bells (stat 1)"),
    Shot(22.00, 26.50, "SEQ", 1.0, speed=1.77, img="ascent_blender_v3/asc_%04d.png", note="Blender: 3D ascent over Blue Marble Earth, PAO-called values (108 fr x 1.77 = 191 of 192)"),
    Shot(26.50, 28.00, "BR", 940.0, push=(1.0, 1.06), note="staging: interstage falls away against blue sky (STAGE SEPARATION label)"),
    Shot(28.00, 29.80, "BR", 961.0, push=(1.0, 1.08), note="interstage falls away over Earth"),
    Shot(29.80, 33.30, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.55)), note="Apollo 11 Earth on translunar coast, pulling away (stat: TLI speed)"),'''),
    # CAPTIONS stay in v7 time; say so where the table is
    (r'''# (t0, t1, speaker, text) — wording corrected against the Apollo Lunar Surface Journal / KSC commentary
CAPTIONS = [''',
     r'''# (t0, t1, speaker, text) — wording corrected against the Apollo Lunar Surface Journal / KSC commentary
# v8: LOGICAL (v7) time. The comp looks captions up with tl; on the v8 timeline a caption at t >= 40.0 plays at t - 6.7.
CAPTIONS = ['''),
    (r'''EARTH_LIMB_X = 1040   # Earth's right limb on the 37-40 s plate after the push (checked on a QC frame)''',
     r'''EARTH_LIMB_X = 1040   # Earth's right limb on the as11-36-5355 plate after the push (v7 37-40 s; v8 29.8-33.3; unused)'''),
    # draw(): the 24,200 MPH stat follows its still (real 29.8-33.3; before ACT2_T0 logical == real); staging label
    (r'''        if 37.0 <= t < 40.0:
            self.stat_speed(layer, d, t - 37.0)''',
     r'''        if 26.5 <= t < 28.0:     # v8: staging shot (before ACT2_T0, logical time == real time)
            self.stage_label(d, t - 26.5, 1.5)
        if round(29.8 * FPS) / FPS <= t < ACT2_T0:     # v8: over the as11-36-5355 still (cut 29.8 = frame 715)
            self.stat_speed(layer, d, t - round(29.8 * FPS) / FPS)'''),
    # stat_speed: 3.5 s window now, fade out over its last 0.3 s
    (r'''        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 2.7) / 0.3))''',
     r'''        a = min(1.0, u / 0.08) * (1 - ease_in_out((u - 3.2) / 0.3))     # v8: 3.5 s window (v7 3.0: 2.7)'''),
    # new lower third, label() style, bottom-left inside safe (x >= 112, bottom <= 1010)
    (r'''    def dsky(self, d, u):''',
     r'''    def stage_label(self, d, u, dur):
        """v8: small lower third over the staging shot, in label()'s style. Bottom-RIGHT inside safe (x <= 1808):
        the exhaust plume wanders over the left half of this shot (checked on v7 frames 30.1-31.4)."""
        a = ease_out(u / 0.3) * (1 - ease_in_out((u - (dur - 0.35)) / 0.35))
        s, f, track = "STAGE SEPARATION", "bebas48", 6
        tw = sum(d.textlength(c, font=self.f[f]) + track for c in s) - track
        x, y = 1808 - 22 - tw, 900
        d.rectangle([x, y, x + 6, y + 48], fill=WHITE + (int(200 * a),))
        self.text(d, (x + 22, y - 2), s, f, WHITE, "la", a, track=track)

    def dsky(self, d, u):'''),
    # comp: logical time per frame
    (r'''        t = fi / FPS
        s = shot_at(t)''',
     r'''        t = fi / FPS                 # REAL time: picture (shot_at, push, black_lead) and the end fade
        s = shot_at(t)
        # v8 LOGICAL (v7) time for graphics, captions, title, glitches and flashes. Frame-exact: from the Moon cut
        # (frame ACT2_F0 = 799) every frame is fi + 161 on the v7 grid (= t + 6.7 within 0.2 frame; t + 6.7 itself
        # would start every later window one frame after its cut).
        tl = t if fi < ACT2_F0 else (fi + ACT2_DF) / FPS'''),
    # the title layer used to be called tl: rename it, and evaluate it in logical time
    (r'''        tl = title_layer(gfx, t)
        if tl is not None:
            f0 = fr.astype(np.float32)
            ta = np.asarray(tl, np.float32)
            a_ = ta[..., 3:4] / 255.0
            sh = np.asarray(tl.getchannel("A")''',
     r'''        ttl = title_layer(gfx, tl)
        if ttl is not None:
            f0 = fr.astype(np.float32)
            ta = np.asarray(ttl, np.float32)
            a_ = ta[..., 3:4] / 255.0
            sh = np.asarray(ttl.getchannel("A")'''),
    (r'''            edge = np.asarray(tl.getchannel("A")''', r'''            edge = np.asarray(ttl.getchannel("A")'''),
    (r'''            if g0 <= t < g1:
                f = glitch(np.clip(f, 0, 255).astype(np.uint8), t, amt).astype(np.float32)''',
     r'''            if g0 <= tl < g1:
                f = glitch(np.clip(f, 0, 255).astype(np.uint8), tl, amt).astype(np.float32)'''),
    (r'''        if 10.6 <= t < 10.75:
            f += 255 * (1 - (t - 10.6) / 0.15) * 0.9''',
     r'''        if 10.6 <= tl < 10.75:
            f += 255 * (1 - (tl - 10.6) / 0.15) * 0.9'''),
    (r'''        if 68.6 <= t < 68.95:
            k = max(0.0, (t - 68.68) / 0.27)''',
     r'''        if 68.6 <= tl < 68.95:
            k = max(0.0, (tl - 68.68) / 0.27)'''),
    (r'''        if 69.6 <= t < 70.2:
            f *= ease_in_out((t - 69.6) / 0.6)
        if TOTAL - 0.5 <= t:''',
     r'''        if 69.6 <= tl < 70.2:
            f *= ease_in_out((tl - 69.6) / 0.6)
        if TOTAL - 0.5 <= t:            # real time against the v8 TOTAL'''),
    (r'''        gfx.draw(t, layer)
        gfx.caption(ImageDraw.Draw(layer), t)''',
     r'''        gfx.draw(tl, layer)
        gfx.caption(ImageDraw.Draw(layer), tl)'''),
    # mix: room tone in the post-flash silence (real time)
    (r'''    i0, i1 = int(68.62 * SR), int(69.6 * SR)''', r'''    i0, i1 = int(61.92 * SR), int(62.9 * SR)       # v8 (v7: 68.62-69.6)'''),
]
s = apply(s, R, "build")

# every shot that started at or after the old 40.0 moves 6.7 s earlier (t0 and t1)
i0, i1 = block(s, "SHOTS: list[Shot] = [\n", "\n]\n")
pat = re.compile(r"^(    Shot\()(\d+\.\d+), (\d+\.\d+), ", re.M)
shifted = 0


def _shot(m: re.Match) -> str:
    global shifted
    a, b = float(m.group(2)), float(m.group(3))
    if a < 40.0:
        return m.group(0)
    shifted += 1
    return f"{m.group(1)}{fmt2(a - D)}, {fmt2(b - D)}, "


s = s[:i0] + pat.sub(_shot, s[i0:i1]) + s[i1:]
assert shifted == 20, f"shifted {shifted} shots, expected 20"

# DIALOG: every line at timeline_t >= 40.0 moves 6.7 s earlier
i0, i1 = block(s, "DIALOG = [\n", "\n]\n")
pat = re.compile(r"^(    \(RST / \"[^\"]+\", [\d.]+, [\d.]+, )([\d.]+)(, [-\d.]+\),)$", re.M)
dshift = 0


def _dlg(m: re.Match) -> str:
    global dshift
    t = float(m.group(2))
    if t < 40.0:
        return m.group(0)
    dshift += 1
    return f"{m.group(1)}{fmt1(t - D)}{m.group(3)}"


s = s[:i0] + pat.sub(_dlg, s[i0:i1]) + s[i1:]
assert dshift == 12, f"shifted {dshift} dialog lines, expected 12"
save(P, s)

# ============================================================== score_pd.py
t = load(S)
A = [
    (r'''TOTAL = 88.5''', r'''TOTAL = 81.8            # v8 (v7: 88.5)'''),
    (r'''    # Dvorak 9 iv: string build under the countdown; the tutti theme (src 11.9) lands on the drop (10.6);
    # the phrase ends with the orchestra's cutoff at src 41.0 (timeline 39.7).
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 1.3, 41.12, 0.0, 0.0, 0.6, 0.10),''',
     r'''    # Dvorak 9 iv: string build under the countdown; the tutti theme (src 11.9) lands on the drop (10.6).
    # v8: act 2 is 6.7 s shorter, so src 24.9-31.6 is cut out at two detected onsets (splice at timeline 23.6);
    # the phrase still ends with the orchestra's cutoff at src 41.0 (timeline 33.0), 0.18 s before Mars as in v7.
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 1.3, 24.9, 0.0, 0.0, 0.6, 0.03),
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.12, 23.6, 0.0, 0.03, 0.10),'''),
    (r'''    # under "The Eagle has landed" (~66.0); hard cut at the white flash (68.6).
    (PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 40.0, 0.0, 2.5, 0.03),''',
     r'''    # under "The Eagle has landed" (v8 ~59.3); hard cut at the white flash (v8 61.9).
    (PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 33.3, 0.0, 2.5, 0.03),'''),
    (r'''    (PD / "dvorak9_ii_largo.ogg", 5.2, 24.0, 69.6, 0.0, 1.4, 1.6),''',
     r'''    (PD / "dvorak9_ii_largo.ogg", 5.2, 24.0, 62.9, 0.0, 1.4, 1.6),'''),
    # automation: act-2 plateau ends at 32.3, ramps to the lunar level at 33.3; everything after shifts -6.7
    (r'''MUSIC_AUTO = [(0.0, -4.0), (10.4, -4.0), (10.6, 0.0), (19.0, 0.0), (19.5, -4.5), (39.0, -4.5), (40.0, -5.0), (47.0, -6.0), (55.0, 0.0),
              (65.4, 4.0), (68.6, 4.0), (69.6, -2.0), (88.0, 0.0)]''',
     r'''MUSIC_AUTO = [(0.0, -4.0), (10.4, -4.0), (10.6, 0.0), (19.0, 0.0), (19.5, -4.5), (32.3, -4.5), (33.3, -5.0), (40.3, -6.0), (48.3, 0.0),
              (58.7, 4.0), (61.9, 4.0), (62.9, -2.0), (81.3, 0.0)]     # v8: act 2 shorter, later points -6.7'''),
    (r'''    mus[int(68.6 * SR):int(69.6 * SR)] = 0.0          # the silence after the flash''',
     r'''    mus[int(61.9 * SR):int(62.9 * SR)] = 0.0          # the silence after the flash (v8; v7 68.6-69.6)'''),
    (r'''    son[int(68.66 * SR):int(69.6 * SR)] = 0.0''', r'''    son[int(61.96 * SR):int(62.9 * SR)] = 0.0       # v8 (v7 68.66-69.6)'''),
]
t = apply(t, A, "score_pd")

# SONNISS: act-2 hits follow their cuts; everything from the old 40.0 on shifts -6.7
#   25.95 whoosh (peak 50 ms before the old ascent cut at 26.0) -> 21.95, before the new ascent cut at 22.0
#   34.0 impact (a v3/v4 cut hit onto "interstage falls away over Earth"; stale in v7) -> 28.0, that shot's v8 cut
MOVE = {25.95: 21.95, 34.0: 28.0}
i0, i1 = block(t, "SONNISS = [\n", "\n]\n")
pat = re.compile(r'^(    \("[^"]+", )([\d.]+)(, )', re.M)
moved = {"act2": 0, "shift": 0}


def _sfx(m: re.Match) -> str:
    v = float(m.group(2))
    if v in MOVE:
        moved["act2"] += 1
        return f"{m.group(1)}{fmt1(MOVE[v])}{m.group(3)}"
    if v >= 40.0:
        moved["shift"] += 1
        return f"{m.group(1)}{fmt1(v - D)}{m.group(3)}"
    assert v < 19.0, f"unhandled act-2 SFX at {v}"
    return m.group(0)


t = t[:i0] + pat.sub(_sfx, t[i0:i1]) + t[i1:]
assert moved == {"act2": 2, "shift": 6}, moved
save(S, t)

# ============================================================== helpers (v >= 8 only; older versions unchanged)
ab = HLP / "ab.py"
x = load(ab)
x = apply(x, [
    (r'''            ("7_outro", 69.6, 90.0)]
''',
     r'''            ("7_outro", 69.6, 90.0)]
ACT2_D = 6.7   # v8+: act 2 is 6.7 s shorter; SECTIONS above are v7 times


def vt(ver: int, t: float) -> float:
    """Section time t (v7 timeline) on version ver's timeline: from v8 on, the Moon (40.0) and after are 6.7 s earlier."""
    return round(t - ACT2_D, 3) if ver >= 8 and t >= 40.0 else t


'''),
    (r'''    top_is_new = rng.random() < 0.5
''',
     r'''    top_is_new = rng.random() < 0.5
    # a section whose length differs between the versions would give away the rows by their timestamps
    same_len = abs((vt(new, b) - vt(new, a)) - (vt(old, b) - vt(old, a))) < 1e-6
    stamp = "  %{pts\\:hms}" if same_len else ""
'''),
    (r'''        step = (b - a) / 8
''', r'''        va, vb = vt(ver, a), vt(ver, b)
        step = (vb - va) / 8
'''),
    (r'''f"{a + step / 2:.3f}", "-t", f"{b - a:.3f}",''', r'''f"{va + step / 2:.3f}", "-t", f"{vb - va:.3f}",'''),
    (r'''text='{label}  %{{pts\\:hms}}':''', r'''text='{label}{stamp}':'''),
], "ab")
save(ab, x)

qc = HLP / "qc.py"
x = load(qc)
x = apply(x, [
    (r'''       49.8, 51.5, 53.5, 56.5, 59.0, 61.0, 62.3, 64.5, 67.0, 68.7, 70.5, 72.0, 76.0, 78.5, 81.0, 84.5, 85.5, 87.5]
''',
     r'''       49.8, 51.5, 53.5, 56.5, 59.0, 61.0, 62.3, 64.5, 67.0, 68.7, 70.5, 72.0, 76.0, 78.5, 81.0, 84.5, 85.5, 87.5]
if N >= 8:   # v8: act 2 is 6.7 s shorter (Moon at 33.3): new act-2 keys (ascent, staging, interstage, 24,200 MPH)
    KEY = [k for k in KEY if k < 22.0] + [23.5, 27.0, 29.0, 31.5] + [round(k - 6.7, 2) for k in KEY if k >= 40.0]
'''),
], "qc")
save(qc, x)

aq = HLP / "audio_qc.py"
x = load(aq)
x = apply(x, [
    (r'''            ("landing", 63.0, 68.6), ("silence", 68.6, 69.6), ("outro", 69.6, 87.5), ("credits", 87.5, 90.0)]
''',
     r'''            ("landing", 63.0, 68.6), ("silence", 68.6, 69.6), ("outro", 69.6, 87.5), ("credits", 87.5, 90.0)]
if N >= 8:   # v8: act 2 is 6.7 s shorter
    SECTIONS = [("cold open", 0.0, 10.6), ("drop + title", 10.6, 19.0), ("act 2 stats/ascent", 19.0, 33.3),
                ("lunar transition", 33.3, 40.3), ("1202 alarm", 40.3, 48.9), ("bingo fuel", 48.9, 56.3),
                ("landing", 56.3, 61.9), ("silence", 61.9, 62.9), ("outro", 62.9, 79.0), ("credits", 79.0, 81.8)]
ACT2_D = 6.7   # v8+: captions and the v7 times below are logical; real() maps them onto this version's timeline


def real(t: float) -> float:
    """v7 (logical) time -> this version's real time (identity before v8)."""
    return round(t - ACT2_D, 3) if N >= 8 and t >= 40.0 else t
'''),
    (r'''    j += [(68.6, "flash cut to silence"), (69.6, "swell in")]''',
     r'''    j += [(real(68.6), "flash cut to silence"), (real(69.6), "swell in")]'''),
    (r'''    windows = [(0.0, 20.0), (46.5, 55.6), (55.4, 62.6), (62.4, 69.0), (69.6, 84.0)]
''',
     r'''    windows = [(0.0, 20.0), (46.5, 55.6), (55.4, 62.6), (62.4, 69.0), (69.6, 84.0)]
    windows = [(real(a), real(b)) for a, b in windows]      # v8+: shift with the picture
'''),
    (r'''    for t0, t1, who, text in build.CAPTIONS:
        heard =''',
     r'''    for t0, t1, who, text in build.CAPTIONS:
        t0, t1 = real(t0), real(t1)                         # captions are logical (v7) time from v8 on
        heard ='''),
    (r'''        for t0, t1, who, text in build.CAPTIONS:
            a, b = int(t0 * SR), int(t1 * SR)''',
     r'''        for t0, t1, who, text in build.CAPTIONS:
            t0, t1 = real(t0), real(t1)                     # stems are real time; captions logical from v8 on
            a, b = int(t0 * SR), int(t1 * SR)'''),
], "audio_qc")
save(aq, x)

print(f"v8: build {len(R)} patches + {shifted} shots + {dshift} dialog lines shifted; "
      f"score {len(A)} patches + {moved['act2']} act-2 SFX moved + {moved['shift']} shifted; ab/qc/audio_qc patched")
