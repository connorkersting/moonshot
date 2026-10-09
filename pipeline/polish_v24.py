"""v24 polish: Fable's v23 overlay notes (exports/moonshot/qc/v23/fable_editor.json), applied to hud_v23 at import time
when build.py's V24_POLISH = True. hud_v23.py itself is unchanged; V24_POLISH = False draws v23 exactly.

  (b) ascent event labels sit 28 px from their marker ring (v23: 16; MAX Q read as touching the ring at phone size).
      The layout is recomputed by hud_v23.asc_layout with the same clearance rules, so the existing gates still apply
      (no missing label on any frame, no placement switch or jump while a label is visible).
  (c) the drum distance card's heading reads AVERAGE DISTANCE, ROUNDED: the drum settles on a rounded 240,000 and the
      mean Earth-Moon distance is about 238,900 miles. Timing, wheels and sub-line unchanged (frames 830-877).
  (d) the end-card disclosure lines are cream (v23: the first was amber and outranked the date line).

Not taken: (a) dropping VALUES CALLED OUT LIVE BY NASA from the ascent plate. It is the plate's provenance line, and
the credits (Fable's suggested new home) are frozen.
"""
import hud_v23

LABEL_GAP = 28
HEADING = "AVERAGE DISTANCE, ROUNDED"


def _candidates(rb: tuple, c: tuple, w: float, h: float) -> list[tuple[str, tuple]]:
    """hud_v23._candidates with LABEL_GAP between the ring's box and the label (same eight positions, same order)."""
    g_ = LABEL_GAP
    return [("L", (rb[0] - g_ - w, c[1] - h / 2, rb[0] - g_, c[1] + h / 2)),
            ("UL", (c[0] - 8 - w, rb[1] - g_ - h, c[0] - 8, rb[1] - g_)),
            ("DL", (c[0] - 8 - w, rb[3] + g_, c[0] - 8, rb[3] + g_ + h)),
            ("R", (rb[2] + g_, c[1] - h / 2, rb[2] + g_ + w, c[1] + h / 2)),
            ("UR", (c[0] + 8, rb[1] - g_ - h, c[0] + 8 + w, rb[1] - g_)),
            ("DR", (c[0] + 8, rb[3] + g_, c[0] + 8 + w, rb[3] + g_ + h)),
            ("U", (c[0] - w / 2, rb[1] - g_ - h, c[0] + w / 2, rb[1] - g_)),
            ("D", (c[0] - w / 2, rb[3] + g_, c[0] + w / 2, rb[3] + g_ + h))]


_type_on_v23 = hud_v23.type_on


def _type_on(s: str, u: float) -> str:
    """The distance heading is the only type_on caller with this string; every other string passes through."""
    return _type_on_v23(HEADING if s == "AVERAGE DISTANCE" else s, u)


def apply() -> None:
    """Patch hud_v23 in place (call once, before hud_v23.load_ascent computes the ascent layout)."""
    assert hud_v23._candidates.__module__ == "hud_v23", "polish_v24 already applied"
    hud_v23._candidates = _candidates
    hud_v23.type_on = _type_on
    hud_v23.END_LINES = tuple((s_, face, hud_v23.CREAM, yb) for s_, face, _, yb in hud_v23.END_LINES)
