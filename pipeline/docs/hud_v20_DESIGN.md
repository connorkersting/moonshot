# MOONSHOT v20 HUD: authentic 1969 hardware

Code: `work/hud_v20.py` (drawing + film pass), `work/patch_v20.py` (wires it into build.py; `V20_HUD = False` restores
v19's drawing). Brief: `exports/moonshot/BRIEF_v20_HUD.md`. Written 2026-10-08.

## 1. Why the v19 HUD read cheap (from v19 frames at 20.5, 31.5, 35.8, 41-45, 49.5-55.5 s)

| Element | What was wrong |
|---|---|
| DSKY (40.5-45.7) | A rounded dark rectangle with three UI chips: an amber "PROG" pill, a grey "KEY REL" pill, "V05 N09" in Consolas, and "01202" in 110 px Consolas Bold green. No 7-segment digits, no register layout, no lamp block. It reads as a web widget labelled "guidance computer". It blinked at 2 Hz, and the code blanked on a timer. Over Mission Control it sat bottom-right with its legend at y 818, 75 px above the caption box and overlapping it horizontally (Gemini: crowding). |
| Bingo + altitude (48.9-56.2) | Two stacked rounded plates, each with a different hierarchy (Bebas label, Anton number, Bebas unit, Consolas GET line, Bebas footnote). Colour carried the state: amber, then red, then white. Two bars (bingo, altitude) restated the numbers. In total five type styles in 300 px, and nothing about it says 1969 or Mission Control. |
| Stat cards (19-21.8, 29.8-33.3, 34.6-36.6) | Anton numerals with Bebas labels: the 2020s YouTube-explainer look. The motion was a generic rising wipe, plus a scale-pop with blur on the TLI number. The distance card was a plain wipe-in. |
| All | No physical relationship to the footage: perfectly sharp vector edges over soft, grainy, halated 16mm. No bezel, glass or glow. Every motion was a linear fade or blink. |

## 2. Design

One rule throughout: **draw the actual object, or the actual document, and nothing that carries no information.**

**Type system (two faces plus hardware digits).**
- Legends: *Franklin Gothic* condensed (Demi Cond and Medium Cond), the American grotesk of 1960s technical and press
  documents.
- Data on screens: *OCR-A* (OCR-A Extended), the 1966-68 USASI machine-readable font, a computer-output face of the period.
- The DSKY digits are drawn segment by segment, as the hardware does it, not set in a font.

All of these are Windows system fonts already on the machine. Nothing was downloaded, so there are no new font files,
no OFL entries and no VETTING change. Captions keep Bahnschrift (frozen).

**Palette.**
- DSKY EL green: lit 124/255/140, unlit 24/36/28.
- Caution amber: 255/168/52; the white status lamps stay unlit.
- MOCR phosphor: blue-white 214/232/255, bloom 110/160/255.
- Printed ink: cream 238/234/222, with the house amber for legends.

### DSKY (tl 47.2-52.375, the 1202)
The upper half of the LM DSKY, in its real arrangement and proportions (about 640 x 372 px at 1.0x).

**Annunciator block (left).** 2 x 7 lamps with the LM legends:
- white status column: UPLINK ACTY, NO ATT, STBY, KEY REL, OPR ERR, PRIO DISP, NO DAP;
- amber caution column: TEMP, GIMBAL LOCK, PROG, RESTART, TRACKER, ALT, VEL.

Only PROG lights. It comes on steady, with a 2-frame incandescent rise. The real lamp latches on, so it no longer
blinks, and the flash count drops too.

**EL display (right).**
- COMP ACTY flickers busy, a pseudo-random 2-frame cadence: the computer *was* overloaded.
- PROG / VERB / NOUN are lit green plates with black legends.
- Three signed 5-digit registers, separated by EL bars.
- Slanted 7-segment digits with pointed segment ends. Unlit segments, and the unlit +/- of the sign columns, stay faintly visible.
- EL strike over 3 frames, +-2.5 % flicker, a new segment at 0.55 for its first frame, and dropped segments decaying 0.40 then 0.12.
- Bloom from two blurs of an emissive pass.

**Content.**
- PROG 63: the braking-phase program in which the 1202 occurred. P64 began at about 102:41:32 per the ALSJ. **Verify before
  promotion**: this comes from memory of the ALSJ, not from a local file. Set `DSKY_PROG_MODE = ""` to blank it.
- V05 N09 keyed (VERB at u 0.25, NOUN at 0.42).
- R1 = 01202 at u 0.58. The AGC shows alarm codes in octal with the sign column blank.
- R2 and R3 are left blank (unlit). Our sources do not state their contents.

The legends sit outside the hardware, printed: "LM GUIDANCE COMPUTER" in grey and, from u 1.0, "1202 = COMPUTER
OVERLOADED" in amber.

**Placement.**
- 1.0x top-left over the LM window.
- From the MC cut (frame 1045), 0.85x on the right, bottom at y 700, legend to about y 792 on a dark plate: 100 px clear of the caption box.

### MOCR console monitor (tl 55.6-62.9: bingo + Aldrin's callouts)
**v20b revision (review, 2026-10-08).** The first version read as calm data: the urgency of v19's red counter was
gone, and the numbers were tiny at 360p.
- Type is now 1.3x: the values are 107 px and every label is 32-34 px OCR-A, about 11 px at 360p.
- "LM DESCENT" is dropped, and "SEC TO BINGO / LAND OR ABORT" is on two lines.
- The panel is 520 x 658 at x 1300-1820, y 90-748. Its width is capped by the CONTACT insert (right edge 1296) and
  title safe (1824), so it grows downward. That keeps it clear of the caption box (top >= 892, captions here are
  centred and narrow).
- Urgency in the CRT's own vocabulary: once the DISPLAYED counter is at or below 30.0 s (v19's red threshold), it is
  drawn in **reverse video**, a solid phosphor block with the digits knocked out dark.
- It holds steady with no blink, so there is one luminance step and no flash pair. It returns to normal video at
  contact, as v19's red turned white.

The rest of this section describes the first v20 layout; positions and sizes above supersede it.

One monitor replaces the two plates. It has a thin grey bezel, a dark blue-black face slightly brighter at the centre,
and raster lines on every third row. It sits at x 1300-1808, y 90-560, clear of the CONTACT insert (x 624-1296).

The text is OCR-A in phosphor:
- a scanline-modulated core;
- two-radius bloom;
- a faint per-frame refresh shimmer.

Lines: "LM DESCENT" / "GET 102:45:05" (CONTACT 102:45:40 at the stop); "SEC TO BINGO-LAND OR ABORT"; the counter; a
30-tick gauge at 2 s per tick (v19's bar, also 60 s full scale); "ALDRIN CALLOUTS"; ALT; DOWN; FWD (only while the last
call states it); "TIME-COMPRESSED".

**Motion is a CRT's, not a crossfade.**
- The screen draws on top to bottom from 55.6, with a beam line.
- The callout block draws on from 55.75.
- A new altitude redraws: first frame at 0.6 while the old value persists at 0.45, then a 1.35 phosphor flare decaying
  to 1.0 over 4 frames. This takes v19's 4-frame amber "fresh" window.

**Removed, because it carried no information:** the altitude bar (it restated the number) and the amber/red/white
colour states (the monitor is monochrome; Duke's "30 seconds" is in the captions).

Every value and step time comes from the unchanged `fuel()` / `descent()` / `get_at()` / `READOUT_HOLDS` code. The one
exception is the 30 FT step, which follows the moved cut 1254 -> 1256 (panel fix).

### Stat cards (thrust tl 19.0-22.0, TLI tl 29.79-33.3)
Flight-plan or press-kit data blocks:
- an amber Franklin Gothic legend that types on;
- an engineering scale rule (a 14 px minor tick, a major every 5th) that draws on;
- the figure on **mechanical drum counters**: Veeder-Root style dark windows with a thin bezel, cream digits on a drum
  with cylinder shading.

| Card | Counter motion |
|---|---|
| Thrust | The 7 rolls up 0 -> 7; the .5 wheel turns once more, so it ticks like a counter settling. |
| TLI | A carry odometer driven by v19's exact count curve (17,400 -> 24,200, ease-out over u 0.4-1.6). The tens wheel turns continuously and the higher wheels carry over the last tenth of the lower wheel's turn. The rest values are identical and the printed comma sits between the windows. |

The v19 exits and the TLI scrim are unchanged.

The 240,000 card is implemented the same way (`render_distance`), but `V20_DISTANCE = False` keeps v19's card. It plays
inside the protected Moon beat (frames 829-877), which must stay bit-identical. Flip it only with approval.

### Integration: film pass
All v20 graphics render to their own layer, then:
1. gate weave: a per-frame sub-pixel offset, sigma 0.32 px;
2. 0.6 px Gaussian softening, to the 16mm's resolution;
3. halation on the graphics' own highlights, using the comp's footage recipe (lum 170-255, 1/8-res blur, warm 60/22/8, at 0.7x).

The layer then goes under the captions layer (the v19 order), and the comp's grain covers both. Frames without a v20
item skip all of this, so they are bit-identical to v19 before encoding.

## 3. References (descriptions only; no images copied in)
- The DSKY layout, lamp legends (LM version), the EL display (COMP ACTY, PROG/VERB/NOUN plates, three signed 5-digit
  registers, separator bars) and slanted segments: the Virtual AGC project's DSKY documentation (ibiblio.org/apollo),
  the Smithsonian NASM DSKY object descriptions, and the Apollo Operations Handbook DSKY description.
- The 1202 sequence (alarm -> V05 N09 -> code 01202) and the descent callouts: the Apollo Lunar Surface Journal,
  a11.landing.html. The callouts are in `data/alsj_descent_callouts.csv`.
- The MOCR consoles: NASA and JSC descriptions of the MOCR console TV displays (monochrome raster data displays).
- Period typography: the 1969 NASA press kit and the Apollo 11 Flight Plan (typewritten, with grotesk headings).

## 4. Fonts and licences
| Font | File | Source | Licence |
|---|---|---|---|
| Franklin Gothic Demi Cond / Medium Cond | C:\Windows\Fonts\FRADMCN.TTF, FRAMDCN.TTF | Windows / Office system fonts (already installed) | Microsoft system font EULA (local rendering) |
| OCR-A Extended | C:\Windows\Fonts\OCRAEXT.TTF | Windows / Office system font | Microsoft system font EULA |

Nothing was downloaded.

## 5. Other v20 changes in the same patch (see the patch_v20 docstring)
- RIFE v4.6 in-betweens for the ignition ramp.
- v19 panel fixes:
  - face shot 1242-1256;
  - BRF / BRS / SVW grades;
  - credits card 1 music line.
