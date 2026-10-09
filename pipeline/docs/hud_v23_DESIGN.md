# MOONSHOT v22 overlays: one system

Code: `work/hud_v22.py` (drawing + the film pass) and `work/patch_v22.py` (wires it into build.py; `V22_HUD = False`
draws v21 exactly). Brief: `exports/moonshot/BRIEF_v22.md` (its REVISION R1-R6 governs). Written 2026-10-08.
v20's hardware design (`hud_v20/DESIGN.md`) still holds; this file adds the rules that make the pieces one family.

## 1. The problem (critics on v21)

- Crowd/FTV v21, comment 3: "Count the overlay dialects: amber stat cards, a green guidance computer, a white-and-blue
  fuel panel, a blue lamp, plain white text. It's a skin per scene."
- Fable v21:
  - the DSKY legend sat 42 px above the caption box, reading as a three-line amber/amber/white stack at 360p;
  - the CONTACT insert and the monitor were 4 px apart and read as one object.

In v21 the overlays came from three generations of code:
- Bebas / Anton / mono labels in build.py's Gfx, with cyan and white accents;
- the v20/v21 HUD in Franklin Gothic and OCR-A;
- the CONTACT insert's own grey frame.

Only the HUD went through the film pass.

## 2. The rules

**Two kinds of overlay, and a rule for each.**

| Kind | What it is | How it is drawn |
|---|---|---|
| Hardware | DSKY, MOCR monitor, CONTACT lamp, drum counters | The object itself, with its authentic emission: DSKY EL green 124/255/140, CRT phosphor 214/232/255, the blue LUNAR CONTACT lamp 120/190/255. Never re-coloured to match the labels. |
| Print | stat cards, legends, chapter card, tags | 1969 flight-plan / press-kit typography, in one face, one scale and one accent. |

**One label face.**
- Franklin Gothic Demi Cond for labels (legends, headlines).
- Franklin Gothic Medium Cond for secondary lines.
- Data on a screen is OCR-A, the CRT's own face. The cold-open clock is print (Franklin Demi `LBL_M` cream): in the
  first dry run it was OCR-A 34 px, and at 360p over the bright pad sky it was thinner than v21's mono, so it was
  rejected.
- Hardware digits are drawn segment by segment (DSKY) or on drums.

No Bebas, Anton or mono remains in any overlay that v22 draws (see section 4 for what is outside the system).

**One size scale (px at 1080p; cap height at 360p in brackets).**

| Token | Size | Used for |
|---|---|---|
| `LBL_XL` | 56 (~13 px) | Card headlines: DAY 5 · JULY 20, 1969; STAGE SEPARATION |
| `LBL_L` | 44 (~10 px) | Legends: LIFTOFF THRUST, SPEED AT TRANSLUNAR INJECTION CUTOFF, 1202 = COMPUTER OVERLOADED, AVERAGE DISTANCE |
| `LBL_M` | 40 | Secondary lines: POUNDS · FIVE F-1 ENGINES, FROM 17,400 IN EARTH ORBIT, LUNAR MODULE EAGLE · POWERED DESCENT |
| `LBL_S` | 30 | Tags: the cold-open site line, APOLLO 11 (hook), ARCHIVE tag, LM GUIDANCE COMPUTER |

The exceptions are hardware-scale numerals: the drum digits, the CRT's 160 px values, the DSKY segments, and the
CONTACT lamp legend, which is engraved on the lens (demi 66).

**One accent.** Every printed label is the house amber, 255/176/64. Every secondary line is cream, 238/234/222.
v21's cyan chapter bar and sub-line, the white stage label, the grey archive tag, the grey DSKY name and the
blue-grey TLI sub-line are gone.

**One frame language.** Two components, both in hud_v22:
- **Housing** (hardware, `housing()`). It uses the CRT bezel recipe at any size:
  - a top-lit grey gradient body with faint texture;
  - a 3 px dark rim and a top catch-light;
  - four screws (the DSKY's);
  - a recessed dark lip around the active face.

  The CONTACT insert now uses it. The DSKY (cast panel, screws, rim) and the CRT (gradient, rim, lip) already had the
  same parts.
- **Plate** (print, `legend_plate()`). A dark 8/8/7 fill at about 200 alpha with a 2 px edge in the drum-window bezel
  colour 168/163/152. It carries:
  - the DSKY header legend;
  - the archive tag.

  Stat cards and the chapter card need no plate. The scale rule (14 px minor ticks, a major every 5th) is the print
  family's line element: the stat cards, the chapter card, STAGE SEPARATION and the distance card all use it.

**One film pass.** Every element above is drawn into the HudFrame layer and goes through `composite()`:
- weave, sigma 0.32 px;
- 0.6 px softening;
- the footage's halation recipe on the graphics' own highlights.

The layer sits under the captions. The cold-open top gradient moved into the HUD with the labels, so the stacking is
unchanged: gradient, then labels.

## 3. Element changes

| Element | Time / frames | v21 | v22 |
|---|---|---|---|
| Countdown HUD + hook | 0.15-13.0 (0-311) | Bebas amber + mono white on the layer | Franklin demi LBL_S amber + LBL_M cream clock / date. Same bar, alpha, L70 gating and timing. The big count numeral stays (phone numeral, on the layer). |
| Archive tag | 26.5-29.8 (636-714) | Bebas grey on a rounded plate | Plate + Franklin medium LBL_S cream, same position (baseline 1004) |
| STAGE SEPARATION | 26.5-27.25 (636-653) | Bebas 72 white with a white bar | Franklin demi LBL_XL amber, right-aligned at 1808, scale rule under it, same fast in/out |
| Stat cards | thrust 456-527, TLI 715-798 | legends 42 px, sub-lines 46 / 40 px (TLI grey-blue) | LBL_L legends, LBL_M cream sub-lines; drums unchanged except the carry fix |
| DAY 5 chapter | tl 44-47 (895-966) | Bebas white + cyan, cyan bar | Flight-plan block: date types on in LBL_XL amber, rule draws, phase types on in LBL_M cream; same alpha |
| DSKY over MC | 1045-1095 | Legend plate under the panel, 42 px above the captions | Header plate on the panel's top edge (x 1168-1808, y 372-422). The assembly ends at 796, 96 px above the caption box. |
| CONTACT insert | 1322-1348 | Gfx frame, 4 px from the monitor | Shared housing, 40 px left (x 584-1256): 44 px clear. Same lamp colour, glow, flicker and timing; Franklin legend |
| 240,000 card | 830-877 | v19's Anton/Bebas card | Unchanged in the candidate (`V22_DISTANCE = False`, the protected Moon beat). See the next paragraph. |

**The 240,000 drum card (preview only).** `V22_DISTANCE = True` draws it in the drum style:
- AVERAGE DISTANCE / six wheels / MILES TO THE MOON;
- the rule is cut to the counter's width (it grazed the Moon limb in the EffectCraft trial);
- the sub-line is demi 48 cream (medium read weak at 360p);
- first active frame 830, hard-absent at 878.

## 4. Outside the system, on purpose

| Element | Why it is outside |
|---|---|
| Captions (Bahnschrift + Bebas speaker tag) | Frozen (text and timing), and a caption is a different layer of meaning. |
| The EARTHRISE label (tl 69.8-73.6) | It starts at frame 1514, inside the protected 1:02 transition (1486-1524), so any change breaks the protection (R5). |
| The end-card date line and both credits cards | Frozen. |
| The ascent graphics (Blender bake, frames 524-635) | A rendered plate, not an overlay. |

## 5. Remotion

Not used. The only in-scope old-style card was DAY 5: two typed lines and a rule. The PIL renderer that draws the stat
cards draws it in the same system at the same quality. The EffectCraft trial found PIL parity for exactly this kind of
card. A Remotion version would add:
- a cached frame sequence and a manifest to keep in sync with the timing;
- a second renderer's anti-aliasing next to the PIL cards it must match.

It would add no visible gain. The title, a real 3D render, is the one pre-rendered asset, and it has a manifest
(`title3d_v22/manifest.json`, checked by `validate_assets()`).

## 6. Fonts

The same Windows system fonts as v20/v21: Franklin Gothic Demi Cond / Medium Cond (FRADMCN.TTF, FRAMDCN.TTF) and
OCR-A Extended (OCRAEXT.TTF). Nothing was downloaded.

---

# v23 additions (code: `work/hud_v23.py`, `work/patch_v23.py`; written 2026-10-08)

Sections 1-6 above are v22's and still hold. v23 extends the same system to the three places that were still outside
it or unreadable at phone size, and adds one token.

## 7. A disclosure-tag token

| Token | Size | Cap at 1080p / 360p | Used for |
|---|---|---|---|
| `TAG` | 56 | 37.5 / 12.5 px | Every disclosure: TIME-COMPRESSED, ARCHIVE: OTHER SATURN V FLIGHT, HEIGHT + DISTANCE / EXAGGERATED 6X, the flash-forward date, the end-card AI line |

Franklin's cap height is 0.67 em, so 54 px is the smallest size that reaches 12 px at 360p; 56 matches `LBL_XL`. A
disclosure is set in medium cream on the plate (or demi amber when it is the line that carries the warning).

## 8. Where each disclosure went

| Tag | v22 | v23 | Why it moved |
|---|---|---|---|
| TIME-COMPRESSED | OCR-A 30 inside the CRT glass (~6.5 px cap at 360p) | Plate under the monitor, the panel's width (x 1300-1820, y 832-890), monitor alpha | At 56 px OCR-A the line is wider than the glass; and it is a note ABOUT the display, not data ON it. Captions in that window are centred and end left of x ~1220. |
| ARCHIVE: OTHER SATURN V FLIGHT | LBL_S plate, bottom-left (baseline 1004) | TAG plate, top-left slot (x 100-~930, y 62-130) | At TAG size the bottom-left plate would run into the centred "Staging." / "And ignition." caption box. Top-left also thins Fable's "lower band" density note for 26.5-29.15. |
| HEIGHT + DISTANCE EXAGGERATED 6X | Baked Bebas, ~7 px at 360p | Ascent plate, two TAG lines | See section 9. |

## 9. The ascent beat (frames 524-635)

The Blender render (`ascent_blender_v23`, `blender/ascent3d_v23.py`) is v5's scene with no text. Everything that was
baked is drawn in the system, with v5's values and timings:

- **Values**: `geometry.json` stores, per asset frame, the strings v5's frame handler built (`T+{t:.0f} S`,
  `{alt:.1f} NMI`, `{mph:,.0f} MPH`). Which asset frame shows at which output frame is MEASURED (index-coded probe
  frames through render_seq's own `-framerate 40.8 ... fps=24` chain) and stored in the manifest's display map, so the
  clock can only show what v22's picture showed at that frame.
- **Top-left plate** (Earth side): ASCENT · FIRST 3 MINUTES (LBL_L amber + scale rule), HEIGHT + DISTANCE (TAG cream),
  EXAGGERATED 6X (TAG amber), VALUES CALLED OUT / LIVE BY NASA (LBL_M cream, a source line, not a warning). The plate
  is 96-626 px wide because the limb's top reaches x 712 late in the shot; the source line is split to keep it there.
- **Readout column** (space side, x 1440): MISSION TIME / ALTITUDE / VELOCITY in LBL_L amber over demi 108 cream
  figures with LBL_L units: the stat cards' legend-over-figure grammar without drums (these are called-out values, not
  a counter).
- **Event labels**: MAX Q and INBOARD ENGINE CUTOFF in LBL_L amber, fading with their rings (v5's k). Each is placed by
  `asc_layout()`: candidate boxes around the ring's projected bbox (left, up-left, down-left, right, ...; INBOARD ENGINE
  CUTOFF may stack), the first one clear of the projected tube (radius + 10 px), every visible ring (+10 px), the limb
  (+16 px), the plate, the column and title safe; the choice sticks while it stays clear. Pads include the comp's SEQ
  weave (sigma 0.9 px). A frame with no clear position would drop the label and fail the build (none does).
- **The rings stay the scene's cyan-white**: they are part of the render (like the hardware's own emission), not print.
- **Grain** (`globe_grain`): monochrome 2 px clumps, mid-tone weighted, masked off black space, seeded per frame,
  sigma 4 levels before the grade; the comp's global grain still goes over everything.

## 10. The cold-open flash-forward tag

The block 3.9-8.4 s (frames 94-201: the Moon, Eagle, touchdown dust, the visor, Earthrise) was unlabeled, and FTV
critics scrolled there in four rounds. Options considered:

| Option | Problem |
|---|---|
| "JULY 20, 1969" on each insert | Only means "later" if the viewer caught the 1-second hook ("JULY 16, 1969", 0.15-1.2 s); five tags flashing on and off with every 0.8-1.0 s cut is noise. |
| "4 DAYS LATER" alone | Says "later" but not when; reads like a chapter card. |
| **"4 DAYS LATER" / "JULY 20, 1969"** in the hook's slot, held across the whole block (chosen) | One tag, on for the 4.5 s block, in the exact slot where the hook printed the launch date, so the reading is "launch July 16 -> this is July 20". Honest for every insert: the landing, the Eagle, the dust, the EVA visor and the lunar-orbit Earthrise are all July 20, 1969 (US time). |

It sits where the countdown HUD would sit; the countdown HUD is gated off on those (non-70 mm) shots, the numeral is
bottom-right, and no caption runs in 3.9-8.4. Bar + demi TAG amber + medium TAG cream, the hook's own grammar.

## 11. The end-card AI line

"EDITED WITH AN AI AGENT" (demi TAG amber) / "ARCHIVAL NASA FOOTAGE" (medium TAG cream), centred under the date line
(x 1392, baselines 516 / 584), with the date line's own alpha (in from 83.9, out 85.15-85.5 logical): frames 1853-1890,
never in the credits (1891+). Clear of the title (bottom ~280), the date line (~437) and the LM (x <= ~1000). Two short
lines instead of one long one: the single line at TAG size would run to x ~560, over the LM's top.

## 12. Still outside the system

The captions, the EARTHRISE label (protected frames), the end-card date line and both credits cards (frozen), and the
240,000 card (V22_DISTANCE = False). The Moon beat 799-877 and the 1:02 transition 1486-1524 are untouched.
