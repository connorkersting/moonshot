You are an independent judge in a blind visual comparison of two cuts of the same short trailer. You are given six comparison sheets, each covering one section of the trailer. The folder is:

{CALL_DIR}

Each sheet is one image. It shows eight frames sampled evenly across the section. The top row is cut A and the bottom row is cut B; each frame carries its row label. When both cuts run for the same time, the frames also carry a timestamp. Which cut is labelled A and which is labelled B is assigned at random on every sheet: the labels say nothing about which cut is newer, better or the original.

You cannot hear audio. Judge only what is visible on the sheets. Judge each sheet on its own, without reference to the other sheets. Do not open any file in the folder other than the sheets listed below, and do not look for information about where the cuts came from.

Sheets in this call:

{SHEET_LIST}

# Rubric

The rubric below is fixed and is applied the same way on every call.

# Fixed blind A/B rubric (MOONSHOT) — identical every iteration

For each section sheet (top row = cut A, bottom row = cut B, same timestamps; A/B assignment is random per section):

Score each cut 0-2 on each criterion (0 = worse, 1 = same, 2 = better than the other cut):
1. Picture: exposure, clarity, colour; can you see what the shot is of?
2. Text legibility at phone size (imagine the frame 6 cm wide).
3. Craft of graphics / titles / 3D (does it look professional, integrated with the footage?).
4. Errors: black or broken frames, glitches that hide content, collisions, text over subjects (2 = fewer errors).
5. Story clarity: does the sequence of frames explain what is happening?

Winner per section = higher total; tie if equal. Report: section | A total | B total | winner | confidence | one-line reason naming the visible difference.
Intentional style elements that are NOT errors: 1-frame black strobes between countdown cuts (0-10.6 s); the white flash then ~1 s black at the landing (~68.6-69.6 s); credits on black at the end.

# Output

For each sheet decide `A`, `B` or `TIE` (a tie when the totals are equal), and say how confident you are. Your final message must contain one JSON block and nothing else: no preamble, no commentary after it.

```json
{
  "decisions": [
    {"sheet": "sheet_1", "a_total": 0, "b_total": 0, "winner": "A", "confidence": "high", "reason": "..."}
  ]
}
```

Rules for the JSON: exactly one entry per sheet listed above (six entries); `sheet` is the sheet's file name without the extension; `a_total` and `b_total` are whole numbers from 0 to 10 (the sum of the five criterion scores for that cut); `winner` is exactly `A`, `B` or `TIE` and agrees with the totals; `confidence` is exactly `high`, `med` or `low`; `reason` is one short line naming the visible difference.
