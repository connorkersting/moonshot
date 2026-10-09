"""v16b: three critics on v15 (Fable editor 8.0, Codex 7.5, blind A/B judge preferring v14 in two sections). Apply ON TOP of
patch_v16 (v15 source + patch_v16; tag v15-src):

    py patch_v16.py  && py patch_v16b.py                       # the real build.py + score_pd.py in work/
    py patch_v16.py B S && py patch_v16b.py B S                 # dry run on copies (restored window -> B's folder/restore)

Times are REAL for SHOTS / DIALOG / MUSIC / MUSIC_AUTO / SONNISS and LOGICAL for Gfx.draw / CAPTIONS (tl = t below frame
799, (fi + 161) / 24 from it; logical = real below 33.3). TIMELINE FREEZE: TOTAL 81.8 / 1963 frames, the 799/161 map and
every cut outside real 26.5-40.3 unchanged (keyed cuts 636 / 715 / 744 / 799 / 854 / 895 / 967 kept).
 1  VOICE IN THE MIDDLE. Armstrong's real staging call, Apollo Flight Journal "Launch and Reaching Earth Orbit"
    (apollojournals.org/afj/ap11fj/01launch.html, fetched 2026-10-07): "000:02:44 Armstrong: Staging." /
    "000:02:46 Armstrong: And ignition." Source: activities_tail.wav (KSC launch commentary reel) 426.76-427.22
    ("Staging.") and 429.14-429.72 ("And ignition."), speech envelope; whisper large-v3-turbo heard "Station." /
    "And ignition." New restored window restore/ascent.wav = activities_tail 420-440 through craft_tools.restore audio
    (default strength 0.85; the same step reproduces restore/countdown.wav bit-exactly from countdown_raw.wav), made by
    this patch if missing (never overwrites). Two DIALOG entries (the 1.9 s pause between the words shortened to 1.1 s):
    "Staging." speech 26.55 on the stage-separation cut (STAGE SEPARATION label), "And ignition." speech 28.34 just after
    the S-II ignition white-out peak / 28.0 impact (its duck pre-roll starts 28.14, after the impact's attack). Two
    captions on the words (APOLLO 11 · ARMSTRONG): "Staging." 26.55-27.25 (11.4 cps), "And ignition." 28.30-29.15
    (15.3 cps), gone before the TLI card (29.79); one caption over both measured +9.1 dB dialogue-to-bed in its window
    (the pause), the two measure >= +11. Duck: build's adaptive duck (target +12 dB).
 2  MUSIC HIT ON THE MOON CUT. Egmont fade-in 1.0 -> 0.15 s (the pp chord is in on the 33.3 cut; it is a sustained chord
    at src 433.15, -30 dBFS, not a silence); a Sonniss sub hit (Haunted Metal Vol.1 _60, attack 0.245 s into the file, cut
    at 1.6 s before its second hit) attacks on 33.30 at -9 dB; music bus +1.5 dB 33.3-39.9 (MUSIC_AUTO 10.0 -> 11.5,
    9.5 -> 11.0; back to 8.0 at 40.3 as before).
 3  MOON RENDER MATCH (s20, GRADE CG16): v15 s20 measured |C| 2.2 (neutral grey, Cr +0.2) vs the 16mm neighbours s21 /
    s22 |C| 5.6 / 4.4 with a green-cyan cast (Cb -5.4 / -3.2, Cr -1.0 / -2.9, mid-tone G-(R+B)/2 +7). CG16 now starts with
    eq=saturation=0.65:contrast=0.94 (35% desaturation, softer terminator) and its curves move the mid-tones toward the
    16mm green-grey (r 0.5 -> 0.495, g 0.5 -> 0.507, b 0.5 -> 0.486; a first try at 0.492 / 0.512 / 0.477
    overshot: |C| 6.6, G-(R+B)/2 +10).
 4  EAGLE + VARIETY. Eagle (BR 1196.0) 35.58-36.60 (1.0 s, was 1.72 s; push 1.0 -> 1.08 now over 1.0 s), the lunar limb
    (BR 1176.0, v14's shot; no source cut in 1174-1179) 36.60-38.20, terrain (BR 1206.0, take 1205.77-1214) 38.20-40.30
    on the new Egmont phrase (~38.15). The 37.30 cut (frame 895) goes; the DAY 5 card (logical 44.0-47.0) now spans the
    38.2 cut, both shots black sky top-left.
 5  RING SHOT OPENING. Source frames 987.40-988.05 show the ring clearly; the white-out is 988.10-988.90. v15 opened on
    987.80 (0.25 s of ring, then 0.8 s of white). Now src_in 987.40 at speed 1.5333 (= (988.55 - 987.40) / 0.75): the
    ring reads for 0.4 s, the white-out is 0.52 s, and the luma peak (988.55) still lands on 28.0 (the Bluezone impact).
    Out at src 991.31 (take 955.0-996.46; no source cut in 989-992).
 6  CLIPS. "INBOARD ENGINE CUTOFF" is baked into the Blender ascent PNGs (blender/ascent3d.py EVENTS, a 3D text object),
    so the comp removes it: asc_label_clean() keys the near-white label (and its ring) in the bottom band (y >= 840,
    x 380-1300; the yellow trajectory and the blue limb protected) and fills from a normalized blur, faded in 25.55 ->
    25.80 (real = logical). "240,000" card: no ghost fade across the Moon; full until the 35.58 cut, gone on it.
 7  CREDITS (NASA media guidelines, nasa.gov/nasa-brand-center/images-and-media, verified 2026-10-07: mark AI-generated
    products; do not imply NASA review or permission): new line "CUT BY AN AI AGENT LOOP (CLAUDE CODE) FROM NASA SOURCE
    MATERIAL" (body34, white, like the other credit lines) and the disclaimer "NOT AFFILIATED WITH, REVIEWED OR ENDORSED
    BY NASA" (body41, amber). Four lines at y 299 / 361 / 423 / 493 (steps 62, 62, 70): the block's centre stays at v15's
    y 396.
Shots 41 -> 42 (every index after s21 shifts +1). Re-render: py build.py shots 16 (FULL run), dialog 16, music 16, comp 16,
mix 16.
"""
import os
import subprocess
import sys
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
S = Path(sys.argv[2]) if len(sys.argv) > 2 else W / "score_pd.py"
RST_OUT = (P.parent / "restore") if len(sys.argv) > 1 else W / "restore"
CRAFT = Path(os.environ.get("CRAFT_TOOLS", "craft-tools"))

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


def make_restored_window(dst: Path) -> None:
    """restore/ascent.wav = activities_tail.wav 420-440 s through craft_tools.restore audio (as the other windows).
    Never overwrites an existing file."""
    dst.mkdir(parents=True, exist_ok=True)
    raw, out = dst / "ascent_raw.wav", dst / "ascent.wav"
    if out.exists():
        print(f"  {out} exists (kept)")
        return
    if not raw.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-ss", "420", "-t", "20", "-i", str(W / "activities_tail.wav"),
                        "-c", "copy", str(raw)], check=True)
    tmp = CRAFT / ".tmp"
    tmp.mkdir(exist_ok=True)
    env = dict(os.environ, TMP=str(tmp), TEMP=str(tmp), PYTHONUTF8="1")
    r = subprocess.run(["uv", "run", "python", "-m", "craft_tools.restore", "audio", str(raw), str(out)], cwd=CRAFT,
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and out.exists(), r.stderr[-1500:]
    print(f"  restored window written: {out} ({r.stdout.strip()})")


# ============================================================== build.py
s = load(P)
assert "def get_at(" in s, "apply patch_v16 first"
assert "ascent.wav" not in s and "def asc_label_clean(" not in s, "v16b already applied"
R = [
    # ---- 3: CG16 toward the 16mm green-grey (desaturate 35%, softer terminator, mid-tones green-grey)
    ('''    "CG16": ("curves=r='0/0.008 1/1':g='0/0.032 1/1':b='0/0.022 1/1',split[cga][cgb];[cgb]gblur=sigma=18[cgg];"''',
     '''    # v16b: + 35% desaturation and contrast 0.94 (softer terminator) first; mid-tones pulled to the 16mm green-grey of
    # s21 / s22 (Cb -3..-5, Cr -1..-3, G-(R+B)/2 +7 measured on the v15 segments)
    "CG16": ("eq=saturation=0.65:contrast=0.94,"
             "curves=r='0/0.008 0.5/0.495 1/1':g='0/0.032 0.5/0.507 1/1':b='0/0.022 0.5/0.486 1/1',split[cga][cgb];[cgb]gblur=sigma=18[cgg];"'''),
    # ---- 5: ring shot opens on the readable ring, white-out shortened, peak still on 28.0
    ('''    Shot(27.25, 29.80, "BRD", 987.80, push=(1.0, 1.10), note="v14: S-II interstage ring; v15:''',
     '''    Shot(27.25, 29.80, "BRD", 987.40, speed=(988.55 - 987.40) / 0.75, push=(1.0, 1.10), note="v16b: src 987.40 at 1.533x: the ring reads 0.4 s (src 987.40-988.05), white-out 0.52 s, luma peak 988.55 still on 28.0, out 991.31; v14: S-II interstage ring; v15:'''),
    # ---- 4: Eagle 1.0 s, limb back, terrain on the new phrase
    ('''    Shot(35.58, 37.30, "BR", 1196.0, push=(1.0, 1.08), note="v14: 16mm from Columbia: Eagle undocked over the Moon (take 1194.59-1205.77), on the Egmont chord 35.58"),
    # ACT 3: descent
    Shot(37.30, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v15: ONE 3 s shot (v14 limb 1176.0 + terrain were near-twins): 16mm low oblique horizon, terrain sliding, black sky top third under the DAY 5 chapter card (take 1205.77-1214)"),
''',
     '''    Shot(35.58, 36.60, "BR", 1196.0, push=(1.0, 1.08), note="v14: 16mm from Columbia: Eagle undocked over the Moon (take 1194.59-1205.77), on the Egmont chord 35.58; v16b: 1.0 s (was 1.72 s, a near-freeze)"),
    Shot(36.60, 38.20, "BR", 1176.0, push=(1.0, 1.10), note="v16b: v14's lunar limb back (blind A/B preferred v14's limb + terrain pair), black sky top-left under the DAY 5 card (src 1176.0-1177.6, no cut in 1174-1179)"),
    # ACT 3: descent
    Shot(38.20, 40.30, "BR", 1206.0, push=(1.0, 1.08), note="v16b: terrain from the new Egmont phrase (~38.15), 2.1 s: 16mm low oblique horizon, black sky top third under the DAY 5 chapter card (take 1205.77-1214)"),
'''),
    # ---- 1: the staging call (two windows of one restored source)
    ('''    (RST / "countdown.wav", 25.0, 31.15, 11.2, -0.5),''',
     '''    (RST / "countdown.wav", 25.0, 31.15, 11.2, -0.5),
    # v16b: Armstrong, AFJ 000:02:44 "Staging." / 000:02:46 "And ignition." (ascent = activities_tail from 420 s; speech
    # 6.76-7.22 and 9.14-9.72 by the envelope): speech at 26.55 (stage-separation cut) and 28.34 (after the 28.0 impact)
    (RST / "ascent.wav", 6.66, 7.40, 26.45, 0.0),
    (RST / "ascent.wav", 9.00, 9.90, 28.20, 0.0),'''),
    ('''    (15.90, 17.15, "LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v10: src 29.75-30.9 (tl 15.95-17.1)
''',
     '''    (15.90, 17.15, "LAUNCH CONTROL", "Liftoff on Apollo 11."),          # v10: src 29.75-30.9 (tl 15.95-17.1)
    (26.55, 27.25, "APOLLO 11 · ARMSTRONG", "Staging."),          # v16b: AFJ 000:02:44 (speech 26.55-27.0), 11.4 cps
    (28.30, 29.15, "APOLLO 11 · ARMSTRONG", "And ignition."),     # v16b: AFJ 000:02:46 (speech 28.34-28.92), 15.3 cps; out before the TLI card (29.79)
'''),
    # ---- 6: 240,000 card: hard cut on the 35.58 cut (frame 854 = tl 42.2917 -> u 2.2917), no ghost over the Moon
    ('''        a = 1 - ease_in_out((u - 1.99) / 0.30)     # v15: out by the 35.58 cut (u 2.29; v14 rode 0.7 s into s21)
        xl = 112''',
     '''        if u >= 2.29:                              # v16b: hard cut on the 35.58 cut (frame 854, u 2.2917); v15 faded 1.99-2.29
            return
        a = 1.0
        xl = 112'''),
    # ---- 7: credits: AI-generation marking + disclaimer (NASA media guidelines); block re-centred on v15's y 396
    ('''                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA  ·  SOME LAUNCH SHOTS FROM OTHER SATURN V FLIGHTS", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 330''',
     '''                 ("3D RENDERS + PARALLAX BUILT FROM NASA DATA  ·  SOME LAUNCH SHOTS FROM OTHER SATURN V FLIGHTS", "body34", WHITE, 62),
                 # v16b: NASA media guidelines (nasa.gov/nasa-brand-center/images-and-media, 2026-10-07): mark AI-made
                 # products, imply no NASA review or permission; four lines, block centre kept at v15's y 396
                 ("CUT BY AN AI AGENT LOOP (CLAUDE CODE) FROM NASA SOURCE MATERIAL", "body34", WHITE, 70),
                 ("NOT AFFILIATED WITH, REVIEWED OR ENDORSED BY NASA", "body41", AMBER, 0)]
        y = 299'''),
    # ---- 6: INBOARD ENGINE CUTOFF label removal (baked into the Blender ascent frames)
    ('''GLITCH_WINDOWS = [''',
     '''def asc_label_clean(fr: np.ndarray, k: float) -> np.ndarray:
    """v16b: remove the 'INBOARD ENGINE CUTOFF' label + ring baked into the Blender ascent frames (blender/ascent3d.py
    EVENTS: a 3D text object that slides off the bottom in the shot's last 0.7 s). Near-white key in the bottom band
    (y >= 840, x 380-1300: the HUD values start at x ~1360), the yellow trajectory (R, G > 190, B < 215; dilated 4 px)
    and the blue limb (R < 0.75 B) excluded; filled from a normalized blur of the unkeyed pixels; k = 0..1 fade."""
    if k <= 0:
        return fr
    y0, x0, x1 = 840, 380, 1300
    band = fr[y0:, x0:x1].astype(np.float32)
    r, g, b = band[..., 0], band[..., 1], band[..., 2]
    line = (r > 190) & (g > 190) & (b < 215)
    line = np.asarray(Image.fromarray((line * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9))) > 0
    key = (g > 110) & (r > 0.75 * b) & (b > 0.95 * g) & ~line
    m = Image.fromarray((key * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.5))
    m = np.asarray(m, np.float32)[..., None] / 255.0
    keep = 1.0 - (m > 0.02).astype(np.float32)
    hb, wb = band.shape[:2]

    def box(a_: np.ndarray, rad: int, ax: int) -> np.ndarray:
        p = np.pad(a_, [(rad + 1, rad) if i == ax else (0, 0) for i in range(2)], mode="edge")
        c = np.cumsum(p, axis=ax)
        n_ = c.shape[ax]
        return (np.take(c, range(2 * rad + 1, n_), axis=ax) - np.take(c, range(0, n_ - 2 * rad - 1), axis=ax)) / (2 * rad + 1)

    def blur(a_: np.ndarray) -> np.ndarray:
        out_ = []
        for c in range(a_.shape[2]):
            sm = np.asarray(Image.fromarray(np.ascontiguousarray(a_[..., c])).resize((wb // 4, hb // 4), Image.Resampling.BILINEAR), np.float32)
            for _ in range(2):
                sm = box(box(sm, 6, 0), 6, 1)
            out_.append(np.asarray(Image.fromarray(sm.astype(np.float32)).resize((wb, hb), Image.Resampling.BILINEAR), np.float32))
        return np.stack(out_, -1)

    fill = blur(band * keep) / np.maximum(blur(np.repeat(keep, 3, axis=2)), 1e-3)
    a_ = np.clip(m * k, 0, 1)
    out = fr.copy()
    out[y0:, x0:x1] = np.clip(band * (1 - a_) + fill * a_, 0, 255).astype(np.uint8)
    return out


GLITCH_WINDOWS = ['''),
    ('''        if s.src == "SEQ":
            wr = np.random.default_rng(fi)''',
     '''        if s.src == "SEQ" and s.img.startswith("ascent_") and t >= 25.55:    # v16b: the baked label, gone by 25.8
            fr = asc_label_clean(fr, ease_in_out((t - 25.55) / 0.25))
        if s.src == "SEQ":
            wr = np.random.default_rng(fi)'''),
]
s = apply(s, R, "build")
# ============================================================== score_pd.py
sc = load(S)
RS = [
    ('''    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 1.0, 0.03),   # v15: fade-in 2.5 -> 1.0 s''',
     '''    (PD / "beethoven_egmont_overture_musopen.flac", 433.15, 461.75, 33.3, 0.0, 0.15, 0.03),   # v15: fade-in 2.5 -> 1.0 s; v16b: 0.15 s, the pp chord is in on the 33.3 cut'''),
    ('''(33.2, -6.65), (33.3, 10.0), (39.9, 9.5), (40.3, 8.0),''',
     '''(33.2, -6.65), (33.3, 11.5), (39.9, 11.0), (40.3, 8.0),'''),
    ('''MUSIC_AUTO = [''', '''# v16b: lunar valley +1.5 dB more (33.3 10.0 -> 11.5, 39.9 9.5 -> 11.0); 40.3 on unchanged
MUSIC_AUTO = ['''),
    ('''    ("Jake Fielding - Haunted Metal Vol.2 - Cinematic Creaks & Risers/''',
     '''    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_60.wav", 33.3, -9.0, "attack", 1.6),   # v16b: the hit on the Moon cut (cut before the file's second hit at ~1.8 s)
    ("Jake Fielding - Haunted Metal Vol.2 - Cinematic Creaks & Risers/'''),
]
sc = apply(sc, RS, "score")
make_restored_window(RST_OUT)
save(P, s)
save(S, sc)
print(f"v16b: build {len(R)} patches, score {len(RS)}. Re-render: py build.py shots 16 (FULL run: 41 -> 42 shots), "
      f"dialog 16, music 16, comp 16, mix 16.")
