"""v26 polish (polish2): Fable's v24 overlay notes (exports/moonshot/qc/v24/fable_editor.json), applied on top of
polish_v24 when build.py's V26_POLISH2 = True. hud_v23.py and polish_v24.py are unchanged, so v24 rebuilds exactly with
V26_POLISH2 = False.

  (1) the drum distance heading 'AVERAGE DISTANCE, ROUNDED' (621 px) overhung its 554 px tick rule and drum by ~67 px.
      Now 'AVG DISTANCE, ROUNDED' (516 px): inside the rule, in the flight-plan abbreviation style.
  (2) end card: both disclosure lines in the medium face, so the date line (APOLLO 11 · JULY 16-24, 1969) outranks them.

Not taken: (3) a 6-frame separation between the drum settle and the type-on. That retimes the director-approved card
inside the protected Moon beat ("timing unchanged").
"""
import hud_v23
import polish_v24

HEADING = "AVG DISTANCE, ROUNDED"


def apply() -> None:
    """Call once, after polish_v24.apply()."""
    assert hud_v23.type_on is polish_v24._type_on, "apply polish_v24 first (and polish_v26 only once)"
    assert polish_v24.HEADING != HEADING, "polish_v26 already applied"
    polish_v24.HEADING = HEADING           # polish_v24._type_on reads the module global at call time
    hud_v23.END_LINES = tuple((s_, "med", col, yb) for s_, _, col, yb in hud_v23.END_LINES)
