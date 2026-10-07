"""v6: B3 title in the plate (Blender, launch plate as reflection environment) + light wrap in the compositor,
and the fixed ascent render (no mirrored label shadows, footnote clear of MAX Q). Apply after v5's chain."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = (CRAFTWORK / "inbox/moonshot/work/build.py")
s = P.read_text(encoding="utf-8")
R = [
    ('TITLE_DIR = "title3d_blender"', 'TITLE_DIR = "title3d_plate"   # v6: plate-reflection title (v3-v5: "title3d_blender" steel)'),
    ('img="ascent_blender/asc_%04d.png"', 'img="ascent_blender_v2/asc_%04d.png"'),
    # light wrap: the plate's blurred light bleeds over the title's edges so it sits in the shot
    ('''            f0 = f0 * (1 - 0.55 * sh)
            fr = np.clip(f0 * (1 - a_) + ta[..., :3] * a_, 0, 255).astype(np.uint8)''',
     '''            f0 = f0 * (1 - 0.55 * sh)
            plate_blur = np.asarray(Image.fromarray(fr).resize((W // 8, H // 8)).filter(ImageFilter.GaussianBlur(4))
                                    .resize((W, H)), np.float32)
            edge = np.asarray(tl.getchannel("A").resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6))
                              .resize((W, H)), np.float32)[..., None] / 255.0
            wrap = np.clip(a_ * (1 - edge), 0, 1)        # inner edge band of the letters (0 deep inside)
            title_rgb = ta[..., :3] * (1 - 0.45 * wrap) + plate_blur * 0.45 * wrap
            fr = np.clip(f0 * (1 - a_) + title_rgb * a_, 0, 255).astype(np.uint8)'''),
    # Codex review #4: stars must sit BEHIND the render (lighten put stars on the lit Moon)
    ('''    fc = (f"[1:v]crop={W}:{H}:x='60+t*18':y='40+t*6',format=rgb24[st];"
          f"[0:v]format=rgb24[mo];[st][mo]blend=all_mode=lighten,format=yuv420p")''',
     '''    fc = (f"[1:v]crop={W}:{H}:x='60+t*18':y='40+t*6',format=rgba[st];"
          f"[0:v]format=rgba,colorkey=black:0.02:0.0[mo];[st][mo]overlay=shortest=1,format=yuv420p")'''),
    # Codex #5: Aldrin sequence has 43 frames; cut at 79.375 so the shot is exactly 43
    ('''    Shot(77.60, 79.40, "SEQ",''', '''    Shot(77.60, 79.375, "SEQ",'''),
    ('''    Shot(79.40, 83.40, "STILL",''', '''    Shot(79.375, 83.40, "STILL",'''),
    # Codex #6: weave with edge padding (no black border flicker)
    ('''            im_ = Image.fromarray(fr).filter(ImageFilter.GaussianBlur(0.7))
            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, dx, 0, 1, dy), Image.Resampling.BILINEAR))''',
     '''            pd_ = int(math.ceil(max(abs(dx), abs(dy)))) + 1
            padded = np.pad(fr, ((pd_, pd_), (pd_, pd_), (0, 0)), mode="edge")
            im_ = Image.fromarray(padded).filter(ImageFilter.GaussianBlur(0.7))
            fr = np.asarray(im_.transform((W, H), Image.Transform.AFFINE, (1, 0, pd_ + dx, 0, 1, pd_ + dy), Image.Resampling.BILINEAR))'''),
    # Codex #7: exactly one white frame (use the WHITE shot itself, not a time window)
    ('''        if 62.9 <= t < 62.96:          # one white frame between "Contact light" and "Houston, Tranquility Base"''',
     '''        if s.src == "WHITE":            # one white frame between "Contact light" and "Houston, Tranquility Base"'''),
    # SAR flag on the export (techqc: sample_aspect_ratio missing)
    ('''"-r", str(FPS), "-colorspace", "bt709",''', '''"-r", str(FPS), "-vf", "setsar=1", "-colorspace", "bt709",'''),
]
# Codex #8: the thrust underline fades with the text instead of vanishing early
R.append(('''            self.text(d, (x, 600 - out * 30), "POUNDS  ·  FIVE F-1 ENGINES", "bebas48", WHITE, "ls", layer_alpha * 0.9)
            return''', '''            self.text(d, (x, 600 - out * 30), "POUNDS  ·  FIVE F-1 ENGINES", "bebas48", WHITE, "ls", layer_alpha * 0.9)
            d.rectangle([x, 628 - out * 30, x + 520, 632 - out * 30], fill=AMBER + (int(220 * layer_alpha),))
            return'''))
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:80]!r}"
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
print(f"v6: {len(R)} patches")
