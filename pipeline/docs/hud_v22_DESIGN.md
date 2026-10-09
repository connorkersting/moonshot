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
