"""v25 CANDIDATE: the signature shot. Frames 715-798 (29.79-33.29 s) become ONE continuous Earth-to-Moon move (a
Blender schematic, not to scale) that settles on the locked Moon portrait's own framing at frame 799. Apply to the
v23 source (build.py at tag v23-src); composes with patch_v24 (audio only) and patch_v26 (SHOTS 70.90-78.80) in either
order: every edit INSERTS next to an unchanged anchor line except the two SHOTS lines this beat owns.

    py patch_v25.py              # the real work/build.py
    py patch_v25.py BUILD.py     # dry run on a copy (hud_v23/hud_v25/assets_v23/assets_v25 next to BUILD.py)

Brief: exports/moonshot/BRIEF_allout.md + codex_allout_plan.md 'v25 - build the signature Earth-to-Moon beat'.
New files (none of them edits a tracked file): blender/hero_v25.py (the scene), blender/hero_path_v25.py (camera,
bodies, route: pure Python, shared with the overlay), blender/hero_post_v25.py (stars by ALPHA + geometry.json),
hero_manifest_v25.py + assets_v25.py (manifest / validator), hud_v25.py (route + label in the hud_v23 system),
work/hero_v25/ (84 frames + geometry.json + manifest.json).

Changes to build.py:
 1  V25_HERO = True (+ import hud_v25, assets_v25), before V23_HUD. False: v23 exactly.
 2  SHOTS: the as11-36-5355 still (29.80-31.00) and the 16 mm Earth (31.00-33.30) become one SEQ shot 29.80-33.30
    reading hero_v25/hv_%04d.png with the Moon portrait's CG16 grade. Frames: round(29.8*24) = 715 to
    round(33.3*24) = 799 -> 84 frames (715-798), the same cut points as v23 (the brief's 29.7917-33.2917 maps to the
    same frames; 29.80/33.30 keeps every other 29.8 / ACT2_T0 reference in build.py exact). The two shots were s21 +
    s22; the hero is s21 and every later shot's index drops by one (old s23 -> s22, ...; 47 -> 46 shots): copy the
    old s(i+1).mp4 to s(i).mp4 for i >= 22 (as the dry run does), then 'py build.py shots 25 21' renders s21 and
    rewrites seg/list.txt (or re-render every shot). On the 3d62d3c base the v26 visor still moves 43 -> 42.
 3  render_seq: a hero_v25 branch BEFORE the px_ branch: opaque frames (the stars were composited by alpha in the
    asset), so NO colorkey over stars.png; CG16 appended like the portrait's. 1:1 (-framerate 24, no fps filter).
 4  hero_check() (new, before rife_cache_check) validates hero_v25 with assets_v25.check_hero (frame names, sha256,
    size, mode, geometry.json, source hashes, the shot's first frame + count) and loads the overlay geometry; called
    from validate_assets() (comp) and preflight('shots').
 5  Gfx.draw: on frames 715-798 the HudFrame gets a 'hero' item (after the unchanged stat_speed call).
 6  stage_comp: on frames 715-798 the HUD module is hud_v25 (hud_v23.render unchanged + the route under the card +
    the label over it, hud_v23's film pass verbatim). Every other frame: hud_v23 exactly.
    Lead review (v25 r2): hud_v25 multiplies the TLI card's alpha by card_fade() on the hero frames (1 to frame 762,
    eased to 0 at 769, before the Moon's limb reaches the card at 770); the route is 9 px + glow + a bright head.
Kept exactly: the TLI card's values, u timeline and position (stat_speed / hud_v23.render_speed untouched; only the
alpha hud_v25 hands to it is scaled after 762), 2,100 frames, frame 799 onward, DIALOG / CAPTIONS, every other shot.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
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


s = load(P)
assert "import hud_v23" in s and "V23_HUD = True" in s and "def preflight" in s, "apply patch_v23 first (v23-src)"
if "V25_HERO" in s:
    sys.exit("v25 already applied")

STILL = ('    Shot(29.80, 31.00, "STILL", img="as11-36-5355.jpg", kb=((0.40, 0.5, 1.95), (0.40, 0.5, 1.60)), note="Apollo 11 '
         'Earth, pulling away fast (stat: TLI speed counts here); v14: 1.2 s, out on the Dvorak hit 31.02"),\n')
BR16 = ('    Shot(31.00, 33.30, "BR", 1113.25, push=(1.12, 1.0), darken=0.15, note="v14: 16mm, the whole Earth from the '
        'spacecraft, handheld drift, receding (24,200 MPH holds; Earth clear of the card)"),\n')
HERO = ('    Shot(29.80, 33.30, "SEQ", 1.0, img="hero_v25/hv_%04d.png", grade="CG16", note="v25: ONE Earth-to-Moon move, '
        'Blender schematic not to scale (blender/hero_v25.py: Blue Marble + clouds, the portrait\'s Moon and sun), '
        'route launches on the Dvorak hit 31.02 (frame 744), settles on the portrait camera for the cut at 799; '
        'stars by alpha in the asset, overlay hud_v25"),\n')

s = apply(s, [
    # 1  the switch (before V23_HUD; the V23_HUD line itself is untouched)
    ("V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly\n",
     "import hud_v25      # v25: the hero beat's route + schematic label, in the hud_v23 system (frames 715-798 only)\n"
     "import assets_v25   # v25: the hero_v25 asset validator (shared with hero_manifest_v25.py --check)\n"
     "V25_HERO = True         # v25: frames 715-798 = one Blender Earth-to-Moon move (hero_v25) + hud_v25; False: v23 "
     "exactly\n"
     "V23_HUD = True          # v23: hud_v23 + the text-free ascent render (ascent_blender_v23); False: v22 exactly\n"),
    # 2  SHOTS: the two Earth plates -> one SEQ shot (False keeps them verbatim)
    (STILL + BR16,
     "    *((  # v25: V25_HERO replaces the two Earth plates with the hero SEQ shot (False: v23's two shots verbatim)\n"
     + HERO + "    ) if V25_HERO else (\n" + STILL + BR16 + "    )),\n"),
    # 3  render_seq: the opaque hero branch, inserted before the px_ branch
    ('    if s.img.startswith("px_"):\n',
     '    if V25_HERO and s.img.startswith(hud_v25.HERO_DIR + "/"):    # v25: opaque (stars by alpha in the asset): no '
     'colorkey\n'
     '        run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(WORK / s.img), "-filter_complex",\n'
     '             f"[0:v]format=rgb24,{GRADE[s.grade] + \',\' if s.grade else \'\'}format=yuv420p", "-frames:v", str(n),\n'
     '             "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", str(path)])\n'
     '        return\n'
     '    if s.img.startswith("px_"):\n'),
    # 4  hero_check (new function, before rife_cache_check) + its two call sites
    ("def rife_cache_check() -> None:\n",
     "def hero_check() -> None:\n"
     "    \"\"\"v25: the hero_v25 asset (assets_v25.check_hero: names, sha256, size, mode, geometry.json, sources, the "
     "shot)\n"
     "    against the SEQ shot build.py will render, then hud_v25 loads its geometry. No Blender needed.\"\"\"\n"
     "    if not V23_HUD:\n"
     "        raise SystemExit(\"V25_HERO needs V23_HUD (hud_v25 draws in the hud_v23 system)\")\n"
     "    s = next(x for x in SHOTS if x.src == \"SEQ\" and x.img and x.img.startswith(hud_v25.HERO_DIR + \"/\"))\n"
     "    f0 = int(round(s.t0 * FPS))\n"
     "    if (f0, f0 + nframes(s)) != hud_v25.HERO_F:\n"
     "        raise SystemExit(f\"hero shot frames {f0}-{f0 + nframes(s) - 1}, hud_v25 expects {hud_v25.HERO_F}\")\n"
     "    assets_v25.check_hero(WORK, hud_v25.HERO_DIR, f0, nframes(s), (W, H))\n"
     "    hud_v25.load(WORK / hud_v25.HERO_DIR)\n"
     "    print(f\"  hero asset {hud_v25.HERO_DIR}: {nframes(s)} frames + geometry + sources verified (frames {f0}-\"\n"
     "          f\"{f0 + nframes(s) - 1})\")\n"
     "\n\n"
     "def rife_cache_check() -> None:\n"),
    ('        print(f"  ascent asset {folder}: 192 frames + geometry + display map verified; layout clear on every frame")\n',
     '        print(f"  ascent asset {folder}: 192 frames + geometry + display map verified; layout clear on every frame")\n'
     '    if V25_HERO:            # v25\n'
     '        hero_check()\n'),
    ('    if stage in ("all", "shots"):\n',
     '    if stage == "shots" and V25_HERO:      # v25: stage_shots reads the hero frames\n'
     '        hero_check()\n'
     '    if stage in ("all", "shots"):\n'),
    # 5  Gfx.draw: the hero item (after the unchanged TLI card call)
    ("            self.stat_speed(layer, d, t - round(29.8 * FPS) / FPS)\n",
     "            self.stat_speed(layer, d, t - round(29.8 * FPS) / FPS)\n"
     "        if V25_HERO and self.v22() and hud_v25.HERO_F[0] <= self.h20.fi < hud_v25.HERO_F[1]:   # v25: route + label\n"
     "            self.h20.add(\"hero\", fi=self.h20.fi)\n"),
    # 6  stage_comp: hud_v25 on the hero frames only
    ("        gfx.h20 = hud.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw\n",
     "        if V25_HERO and V23_HUD and hud_v25.HERO_F[0] <= fi < hud_v25.HERO_F[1]:\n"
     "            hud = hud_v25        # v25: hud_v23's items unchanged + the hero route / label (frames 715-798 only)\n"
     "        gfx.h20 = hud.HudFrame(fi, tl) if V20_HUD else None     # v20: filled by gfx.draw\n"),
], "build.py")
save(P, s)
print(f"patched {P} (v25: hero beat 715-798)")
