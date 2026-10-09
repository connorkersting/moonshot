"""v16: a live altitude / descent readout under the bingo counter, synced to Aldrin's REAL callouts. Apply to the v15
source (build.py + score_pd.py, tag v15-src).

    py patch_v16.py                      # the real build.py + score_pd.py in work/
    py patch_v16.py BUILD.py SCORE.py    # dry run on copies

Times are REAL for SHOTS / DIALOG / MUSIC and LOGICAL for Gfx.draw / CAPTIONS (tl = t below frame 799,
(fi + 161) / 24 from it). TIMELINE FREEZE: SHOTS, DIALOG, CAPTIONS, score_pd.py, TOTAL 81.8 / 1963 frames unchanged.
Graphics only: re-render  py build.py comp 16  then  py build.py mix 16  (no shots / music / dialog stage).

DATA: Apollo Lunar Surface Journal, "The First Lunar Landing" (corrected transcript, E. M. Jones),
https://www.nasa.gov/wp-content/uploads/static/history/alsj/a11/a11.landing.html, fetched 2026-10-07;
table in data/alsj_descent_callouts.csv. Aldrin's calls used (GET, ft, ft/s down, ft/s forward):
  102:44:45 100 / 3.5 / 9    102:44:54 75 / 0.5 / 6    102:45:08 60 / 2.5 / 2    102:45:17 40 / 2.5 / -
  102:45:21 30 / 2.5 / -     102:45:25 20 / 0.5 / 4    102:45:40 "Contact Light."
 1  Shared GET map (get_at): the bingo counter's own dialogue-anchor map, moved to module level so the counter and
    the readout read ONE time-compressed clock, plus one anchor at Aldrin's "40 feet" (pao_land 25.65 = real 50.95 by
    the speech envelope; GET 102:45:17): (57.625, 17.0), frame 1222, one frame before the word. Without it the v15 map
    reads GET :13.7 on "40 feet" (the readout would still say 60 FT). Effect on the bingo counter, logical 55.7-60.3
    only: rate 6.5x -> 7.8x (55.7-57.625) and 5.6x (57.625-60.3); largest change -2.45 s at 57.625 (47.45 -> 45.00);
    unchanged at "60 seconds" (60.0), "30 seconds" (30.0), contact (22.0) and everywhere outside 55.7-60.3.
 2  Gfx.descent: under the bingo plate, same x (plate 1300-1821 x 492-828; bingo plate 1300-1821 x 102-472, caption
    box top >= 892, title safe). ALDRIN'S CALLOUTS (bebas40 amber), ALT anton150 white + FT, DOWN / FWD ft/s
    (bebas60 values), a vertical altitude bar (0-100 ft, x 1784-1798), TIME-COMPRESSED (bebas40 grey, the bingo's own
    label). Every field is STEP-HELD at Aldrin's last stated value at the mapped GET: no interpolation (the bar eases
    0.2 s between called values; it is a gauge, not a number). A new altitude flashes amber for 4 frames. At
    "Contact light" (61.9, the bingo's contact anchor) the block turns white, ALT reads CONTACT, the bar empties and
    DOWN / FWD dim (no altitude is called after 20 ft). Dark plate until the insert (61.79), like the bingo; in at
    55.75 (3 frames after the bingo), cut by the white frame at 62.9 with the bingo.
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
assert "def get_at(" not in s and "def descent(" not in s, "v16 already applied"
R = [
    # ---- 1: the shared GET map + Aldrin's callouts (module level, after the DSKY constants)
    ('''DSKY_LEFT_T = 52.37      # v12: s23's (v14 s26, v15 s25) source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again
''',
     '''DSKY_LEFT_T = 52.37      # v12: s23's (v14 s26, v15 s25) source cuts back to the LM window at frame 1096 (real 45.667, tl 52.375): top-left again

# v16: LOGICAL timeline -> GET seconds after 102:45:00 via the dialogue anchors, ONE time-compressed clock shared by the
# bingo counter (fuel) and the altitude readout (descent). "60 seconds" 102:45:02 (55.7, the PAO tape 825.3); Aldrin's
# "40 feet" 102:45:17 (57.625 = frame 1222, one frame before the word: pao_land 25.65 = real 50.95; v16 anchor);
# "30 seconds" (60.3 -> :32, so the counter reads 30.0 on the words); "Contact light" 102:45:40 (61.9); engine stop.
GET_ANCHORS = [(55.7, 2.0), (57.625, 17.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
# v16: Aldrin's callouts, Apollo Lunar Surface Journal a11.landing.html (data/alsj_descent_callouts.csv):
# (GET s after 102:45:00, altitude ft, down ft/s, forward ft/s); None = not stated in that call (the field holds)
CALLOUTS = [(-15.0, 100, 3.5, 9), (-6.0, 75, 0.5, 6), (8.0, 60, 2.5, 2), (17.0, 40, 2.5, None),
            (21.0, 30, 2.5, None), (25.0, 20, 0.5, 4)]
CONTACT_GET = 40.0          # 102:45:40 Aldrin: "Contact Light."


def get_at(tl: float) -> float:
    """GET (s after 102:45:00) on the shared dialogue map at logical time tl; clamped outside the anchors."""
    if tl <= GET_ANCHORS[0][0]:
        return GET_ANCHORS[0][1]
    if tl >= GET_ANCHORS[-1][0]:
        return GET_ANCHORS[-1][1]
    for (ta, ga), (tb, gb) in zip(GET_ANCHORS, GET_ANCHORS[1:]):
        if ta <= tl <= tb:
            return ga + (gb - ga) * (tl - ta) / (tb - ta)
    return GET_ANCHORS[-1][1]


def tl_of_get(g: float) -> float:
    """Inverse of get_at (the map is strictly increasing): logical time at which the clock reads GET g."""
    if g <= GET_ANCHORS[0][1]:
        return GET_ANCHORS[0][0]
    for (ta, ga), (tb, gb) in zip(GET_ANCHORS, GET_ANCHORS[1:]):
        if ga <= g <= gb:
            return ta + (tb - ta) * (g - ga) / (gb - ga)
    return GET_ANCHORS[-1][0]
'''),
    # ---- 2: draw the readout with the bingo (3 frames later), cut by the same white frame
    ('''        if 55.6 <= t < 62.9:      # v9: the bingo HUD holds over the CONTACT insert, cut by the white frame
            self.fuel(d, t)
''',
     '''        if 55.6 <= t < 62.9:      # v9: the bingo HUD holds over the CONTACT insert, cut by the white frame
            self.fuel(d, t)
        if 55.75 <= t < 62.9:     # v16: Aldrin's altitude callouts under the bingo, same clock, same white-frame cut
            self.descent(d, t)
'''),
    # ---- 1: the bingo counter reads the shared map
    ('''        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors
        anchors = [(55.7, 2.0), (60.3, 32.0), (61.9, 40.0), (62.5, 44.0)]
        contact = 61.9               # v9: "Contact light" (logical): the counter stops here and holds
        held = t >= contact
        tg = min(t, contact)
        if tg <= anchors[0][0]:
            g = anchors[0][1]
        elif tg >= anchors[-1][0]:
            g = anchors[-1][1]
        else:
            for (ta, ga), (tb, gb) in zip(anchors, anchors[1:]):
                if ta <= tg <= tb:
                    g = ga + (gb - ga) * (tg - ta) / (tb - ta)
                    break
        rem = max(0.0, 62.0 - g)''',
     '''        # timeline -> mission time (GET seconds after 102:45:00) via the dialogue anchors (v16: get_at, shared with
        # the altitude readout; adds Aldrin's "40 feet" at 57.625)
        contact = 61.9               # v9: "Contact light" (logical): the counter stops here and holds
        held = t >= contact
        tg = min(t, contact)
        g = get_at(tg)
        rem = max(0.0, 62.0 - g)'''),
    # ---- 2: the readout
    ('''    def chart(self, layer, d, u):
''',
     '''    def descent(self, d, t):
        """v16: Aldrin's altitude callouts as a live readout under the bingo counter (same x; plate 1300-1821 x
        492-828, caption box top >= 892). REAL values only: ALT ft, DOWN ft/s and FWD ft/s are each STEP-HELD at
        Aldrin's last stated value (CALLOUTS, from the Apollo Lunar Surface Journal) at the GET the shared dialogue map
        gives this frame (get_at, the bingo's clock: TIME-COMPRESSED, same label). Never interpolated; the bar eases
        0.2 s between called values. 40 FT from frame 1222 (tl 57.625), one frame before Aldrin's "40 feet". At
        "Contact light" (61.9) the block turns white like the bingo and reads CONTACT; the bar empties (nothing is
        called below 20 ft). No plate over the black insert (61.79+); cut by the white frame (62.9) with the bingo."""
        contact = 61.9
        held = t >= contact
        g = get_at(min(t, contact))
        alt = down = fwd = None
        g_alt = prev_alt = None
        for cg, ca, cdn, cf in CALLOUTS:
            if cg <= g + 1e-6:
                if ca is not None:
                    prev_alt, alt, g_alt = alt, ca, cg
                if cdn is not None:
                    down = cdn
                if cf is not None:
                    fwd = cf
        a = min(1.0, max(0.0, (t - 55.75) / 0.3))
        x0, y0 = 1320, 510
        if t < 61.79:              # dark plate for the 16mm dust and the white shirts in Mission Control (as the bingo)
            d.rounded_rectangle([x0 - 20, y0 - 18, x0 + 501, y0 + 318], radius=12, fill=(0, 0, 0, int(150 * a)))
        lab = WHITE if held else AMBER
        self.text(d, (x0, y0), "ALDRIN'S CALLOUTS", "bebas40", lab, "la", a, track=3)
        t_step = tl_of_get(g_alt) if g_alt is not None and g_alt > GET_ANCHORS[0][1] else -1.0
        fresh = (not held) and 0.0 <= t - t_step < 4 / 24          # a new called altitude flashes amber for 4 frames
        if held:
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
        self.text(d, (x0, y0 + 266), "TIME-COMPRESSED", "bebas40", (190, 190, 190), "la", a * 0.8, track=3)
        # altitude bar, 0-100 ft (gauge for the called value; eases 0.2 s from the previous call)
        bx0, bx1, by0, by1 = 1784, 1798, y0 + 14, y0 + 290
        col = WHITE if held else AMBER
        d.rectangle([bx0, by0, bx1, by1], outline=col + (int(200 * a),), width=2)
        if not held and alt is not None:
            k = ease_out((t - t_step) / 0.2) if prev_alt is not None and t_step > 0 else 1.0
            v = (prev_alt + (alt - prev_alt) * k) if prev_alt is not None else alt
            yb = by1 - (by1 - by0) * min(v, 100) / 100.0
            d.rectangle([bx0, yb, bx1, by1], fill=col + (int(230 * a),))
            d.rectangle([bx0 - 12, yb - 1, bx0 - 4, yb + 1], fill=col + (int(230 * a),))

    def chart(self, layer, d, u):
'''),
]
s = apply(s, R, "build")
# ============================================================== score_pd.py (unchanged in v16; loaded for the EOL check)
sc = load(S)
save(P, s)
print(f"v16: build {len(R)} patches, score 0. Re-render: py build.py comp 16, then mix 16 (graphics only).")
