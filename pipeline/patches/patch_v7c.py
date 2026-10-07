"""v7c: BT.709 primaries/transfer actually written (x264-params), Earthrise parallax with a bigger rise."""
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = W / "build.py"
s = P.read_text(encoding="utf-8")
R = [('''"-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",''',
      '''"-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",''')]
if (W / "px_earthrise_v2").exists() and len(list((W / "px_earthrise_v2").glob("px_*.png"))) >= 106:
    R.append(('img="px_earthrise/px_%04d.png"', 'img="px_earthrise_v2/px_%04d.png"'))

# v6 A/B: plate-lit title LOST (both title sections) -> back to the steel title, light wrap removed with it
R.append(('TITLE_DIR = "title3d_plate"   # v6: plate-reflection title (v3-v5: "title3d_blender" steel)',
          'TITLE_DIR = "title3d_blender"   # steel; v6 plate-lit title lost its blind A/B'))
R.append(("            title_rgb = ta[..., :3] * (1 - 0.45 * wrap) + plate_blur * 0.45 * wrap",
          "            title_rgb = ta[..., :3]   # light wrap dropped with the plate title (v6 A/B)"))
# v6 A/B: the colorkey+overlay path shifted colour (purple Earth); composite in RGB, convert once
R.append(("[st][mo]overlay=shortest=1,format=yuv420p\")", "[st][mo]overlay=shortest=1:format=rgb,format=yuv420p\")"))
for a, b in R:
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)
P.write_text(s, encoding="utf-8")
print(f"v7c: {len(R)} patches")
