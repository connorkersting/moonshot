"""v26 CANDIDATE: the epilogue photographs from the original high-resolution film scans (stills_hq/), real pixels only.
Apply to the v23 source (build.py at tag v23-src), alone or after patch_v24 / patch_v25 (in either order):

    py patch_v26.py              # the real build.py
    py patch_v26.py BUILD.py     # dry run on a copy (epi_v26.py must sit next to BUILD.py's folder's work/... see below)

epi_v26.py is imported from work/ (it reads work/stills_v26/, written once by `py epi_v26.py make`; manifest.json
holds the source sha1/bytes, the registration, the crop rectangles, the grade, the per-frame source boxes, the
sampling ratios and the sha256 of every rendered frame).

Changes (build.py only; every anchor below is KEPT VERBATIM and the v26 lines are inserted after it, so the patch
composes with any other patch that also inserts after the same anchor; the three SHOTS lines are v26's alone):
 1  after `import assets_v23 ...`: import epi_v26, V26_SCANS = True (False: v23 exactly), V26_ENDPLATE = True and
    V26_BOOTPRINT = False (per-shot switches under V26_SCANS).
 2  SHOTS 70.90-72.675 (frames 1702-1743): STILL stills_v26/as11-40-5903_v26.png, a push into the visor reflection,
    2.48x -> 5.36x of the 10553 px scan (source px per output px 2.21 -> 1.025), replaces the px_aldrin parallax.
 3  SHOTS 72.675-76.70 (frames 1744-1840): with V26_BOOTPRINT the scan (5878, 10538 px, stored at 1/2) and a
    restrained push across the print (ratio 2.18 -> 1.67 of the stored crop, 4.4 -> 3.3 of the scan). OFF by default:
    the scan holds no more optical detail than the library JPEG the cut uses now (evidence in the v26 report), so
    the v23 shot stays unless the director prefers the scan's grain / move.
 4  SHOTS 76.70-78.80 (frames 1841-1890): STILL stills_v26/as11-44-6642_v26.png, the 4275 px full-frame scan (the
    film edges cropped), the same composition as v23 (Earth and horizon within 2 px on frame 1841), push 1.0047 -> 1.048
    anchored on the horizon so the end title / date line / AI note (unchanged, drawn by the comp) keep their ground.
    Switch V26_ENDPLATE (on): detail is at parity with the library JPEG (which was never undersampled here); the
    gain is fewer clipped LM-foil highlights and the scan's provenance. False keeps v23's plate.
 5  render_still: a stills_v26/ image goes to epi_v26.render_still_v26 (anchor: the `def render_still` line).
 6  preflight: for "shots" / "all", epi_v26.check(SHOTS) before anything is written (anchor: the
    `rife_cache_check()` call inside preflight). Not needed for comp / mix (they do not read stills_v26).

Kept exactly: the cut points, DIALOG / CAPTIONS, every comp step (LUT, bg_darken 0.5, title, halation, vignette,
grain), the credits 1891+ (no v26 frame reaches 1891), the audio.

Re-render chain (real tree): py epi_v26.py check; py build.py shots 26 <i5903>,<i6642> (43,45 on v23; v25 may shift
the indices: `py -c "import build; print([i for i, s in enumerate(build.SHOTS) if (s.img or '').startswith('stills_v26/')])"`);
py build.py comp 26; py build.py mix 26; py flashqc2.py ..\\..\\..\\exports\\moonshot\\versions\\moonshot_v26.mp4.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build.py is CRLF)."""
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
assert "import assets_v23" in s and "V23_HUD = True" in s and "def preflight" in s, "apply patch_v23 first (v23-src)"
assert "epi_v26" not in s and "V26_SCANS" not in s, "v26 already applied"
assert (W / "epi_v26.py").is_file() and (W / "stills_v26" / "manifest.json").is_file(), \
    "work/epi_v26.py + work/stills_v26/manifest.json required (py epi_v26.py make)"
if P.parent != W:
    assert (P.parent / "epi_v26.py").is_file(), f"copy epi_v26.py next to {P.name} for a dry run"

OLD_ALDRIN = '''    Shot(70.90, 72.675, "SEQ", 1.0, img="px_aldrin/px_%04d.png", note="Aldrin: Blender parallax, opens on the visor, pushes into the reflection"),
'''
OLD_BOOT = '''    Shot(72.675, 76.70, "STILL", img="as11-40-5878.jpg", kb=((0.62, 0.62, 1.25), (0.62, 0.62, 1.6)), note="bootprint (one giant leap)"),
'''
OLD_END = '''    Shot(76.70, 78.80, "STILL", img="as11-44-6642.jpg", kb=((0.5, 0.585, 1.0), (0.5, 0.585, 1.02)), bg_darken=0.5, note="end title: Earth high, LM low (inside safe); v19 (R5): plate darkened 0.5 before the title (v18: 0.35 after it), push halved so the horizon stays under the raised title"),
'''
ANCHOR_IMPORT = '''import assets_v23   # v23: the one validator for manifested assets (title + ascent), shared with the manifest tools
'''
ANCHOR_RENDER = '''def render_still(s: Shot, path: Path) -> None:
'''
ANCHOR_PRE = '''    if stage in ("all", "shots"):
        rife_cache_check()
'''
R = [
    # ---- 1: module + switches
    (ANCHOR_IMPORT, ANCHOR_IMPORT + '''import epi_v26      # v26: the epilogue stills from the original film scans (work/stills_v26, manifested)
V26_SCANS = True        # v26: frames 1702-1743 (5903 visor) and 1841-1890 (6642 end plate) from the scans; False: v23
V26_ENDPLATE = True     # v26: 1841-1890 from the 6642 scan (detail at parity, fewer clipped highlights); False: v23
V26_BOOTPRINT = False   # v26: 1744-1840 from the 5878 scan too; off: no more optical detail than the library JPEG
'''),
    # ---- 2: the visor
    (OLD_ALDRIN, '''    (Shot(70.90, 72.675, "STILL", img="stills_v26/as11-40-5903_v26.png", kb=((0.50152, 0.27274, 2.48306), (0.51549, 0.23372, 5.3623)), note="v26: AS11-40-5903 original scan (10553 px), push into the visor reflection, real pixels (2.21 -> 1.025 source px per output px); kb in scan coordinates (epi_v26)")
     if V26_SCANS else
''' + OLD_ALDRIN.replace("    Shot(", "     Shot(", 1).replace("),\n", ")),\n")),
    # ---- 3: the bootprint (switch, off)
    (OLD_BOOT, '''    (Shot(72.675, 76.70, "STILL", img="stills_v26/as11-40-5878_v26.png", kb=((0.59860, 0.62288, 1.2578), (0.64718, 0.65205, 1.64656)), note="v26: AS11-40-5878 original scan (10538 px, stored 1/2), v23's opening frame, a restrained push across the print (scan 4.4 -> 3.3 px per output px)")
     if V26_SCANS and V26_BOOTPRINT else
''' + OLD_BOOT.replace("    Shot(", "     Shot(", 1).replace("),\n", ")),\n")),
    # ---- 4: the end-title plate
    (OLD_END, '''    (Shot(76.70, 78.80, "STILL", img="stills_v26/as11-44-6642_v26.png", kb=((0.50094, 0.57855, 1.03762), (0.50094, 0.57331, 1.08431)), bg_darken=0.5, note="v26: AS11-44-6642 full-frame scan (4275 px, film edges cropped), v23's composition, push 1.0047 -> 1.048 anchored on the horizon (title, date line and AI note unchanged); scan 2.15 -> 2.05 px per output px")
     if V26_SCANS and V26_ENDPLATE else
''' + OLD_END.replace("    Shot(", "     Shot(", 1).replace("),\n", ")),\n")),
    # ---- 5: the render path
    (ANCHOR_RENDER, ANCHOR_RENDER + '''    if s.img.startswith(epi_v26.DIR + "/"):      # v26: original-scan stills (epi_v26: PIL, manifest-verified frames)
        return epi_v26.render_still_v26(s, path)
'''),
    # ---- 6: preflight
    (ANCHOR_PRE, ANCHOR_PRE + '''        if V26_SCANS:             # v26: stills_v26 crops, sources and the shot table vs its manifest
            print(f"  v26 scans: {epi_v26.check(SHOTS)} shots verified against stills_v26/manifest.json")
'''),
]
s = apply(s, R, "build")
assert s.count("V26_SCANS") >= 5 and "epi_v26.render_still_v26" in s
save(P, s)
print(f"v26: build {len(R)} replacements. Re-render: shots 26 (the stills_v26 shots), comp 26, mix 26.")
