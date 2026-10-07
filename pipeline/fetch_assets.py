"""Download the public-domain media MOONSHOT is built from, from the official sources.

    python fetch_assets.py [--root $CRAFTWORK]

Downloads into the layout build.py expects: $CRAFTWORK/inbox/moonshot/{video,stills,audio},
$CRAFTWORK/music/pd and $CRAFTWORK/bg/nasa-moon.

Nothing here is redistributed by this repo: NASA footage, photos and audio are U.S. government works
(public domain in the U.S.); the music recordings are public domain per Wikimedia Commons.
Get these by hand (no stable direct URL, or the licence forbids scripted redistribution):
  - Sonniss GDC 2024 sound effects (free bundle, no redistribution): https://sonniss.com/gdc-bundle-license/
    -> unpack to $CRAFTWORK/sfx/sonniss-gdc2024
  - Blue Marble Next Generation, December, world.topo.bathy.200412.3x21600x10800.jpg (NASA Earth Observatory):
    https://science.nasa.gov/earth/earth-observatory/blue-marble-next-generation/base-topography-bathymetry
    -> $CRAFTWORK/inbox/moonshot/stills/bluemarble/ (blender/ascent3d.py reads an 8K downsample, bluemarble_8k.jpg)
  - Poly Haven HDRI studio_small_09, 2k .hdr (CC0): https://polyhaven.com/a/studio_small_09 -> $CRAFTWORK/bg/hdri/
  - Anton and Bebas Neue (SIL OFL) from github.com/google/fonts -> $CRAFTWORK/fonts/
Total download is about 4.6 GB (the 25th-anniversary B-roll reel is 3.9 GB of it).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

NASA_VIDEO = "https://images-assets.nasa.gov/video"
NASA_IMAGE = "https://images-assets.nasa.gov/image"

VIDEOS = {
    "video/saturnv_enhanced_1080.mp4": ("Ultimate Saturn V Launch w Enhanced Sound", "orig"),
    "video/launch_70mm.mp4": ("KSC_69-71212-sRGB", "orig"),
    "video/broll25_720.mp4": ("KSC-19690716-MH-NAS01-0001-Apollo_11_Historical_Footage_and_Broll-DVC_1560", "orig"),
    "video/activities_mobile.mp4": ("KSC-19690716-MH-NAS01-0001-Apollo_11_Breakfast_C7Exit_Convoy_WhiteRmHatchClosing_Launch-HM_0083", "mobile"),
}
STILLS = ["as11-44-6550", "as11-44-6642", "as11-44-6581", "as11-37-5448", "as11-40-5903", "as11-40-5875",
          "as11-40-5878", "as11-36-5355", "as08-14-2383"]
AUDIO = {
    # Apollo Lunar Surface Journal public-affairs loop (NASA JSC); NASA's current host 404s, so the Internet Archive copy
    "audio/alsj_a11a1023114-4746_PAO.mp3": "http://web.archive.org/web/2019id_/https://www.hq.nasa.gov/alsj/a11/a11a1023114-4746.mp3",
    "audio/commons_eagle_has_landed.mp3": "https://upload.wikimedia.org/wikipedia/commons/8/87/Apollo_11_Eagle_Has_Landed.mp3",
    "audio/commons_small_step.ogg": "https://upload.wikimedia.org/wikipedia/commons/d/dd/Armstrong_Small_Step.ogg",
}
MUSIC = {
    "music/holst_mars_usaf_band.ogg": "https://commons.wikimedia.org/wiki/Special:FilePath/Holst-_mars.ogg",
    "music/dvorak9_iv_allegro_con_fuoco.ogg": "https://commons.wikimedia.org/wiki/Special:FilePath/Antonin_Dvorak_-_symphony_no._9_in_e_minor_'from_the_new_world',_op._95_-_iv._allegro_con_fuoco.ogg",
    "music/dvorak9_ii_largo.ogg": "https://commons.wikimedia.org/wiki/Special:FilePath/Antonin_Dvorak_-_symphony_no._9_in_e_minor_'from_the_new_world',_op._95_-_ii._largo.ogg",
}
MOON_KIT = {  # NASA SVS #4720 CGI Moon Kit (public domain)
    "bg/nasa-moon/lroc_color_16bit_srgb_4k.tif": "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/lroc_color_16bit_srgb_4k.tif",
    "bg/nasa-moon/ldem_16.tif": "https://svs.gsfc.nasa.gov/vis/a000000/a004700/a004720/ldem_16.tif",
}


def get(url: str, dst: Path) -> None:
    if dst.exists() and dst.stat().st_size > 0:
        print(f"  have {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"  get  {dst}  <-  {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "moonshot-fetch/1.0 (open-source trailer pipeline)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dst, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.environ.get("CRAFTWORK", "CraftWork"),
                    help="workspace root; build.py reads the same folder from $CRAFTWORK")
    root = Path(ap.parse_args().root)
    media = root / "inbox" / "moonshot"              # build.py: INBOX = CRAFTWORK/inbox/moonshot
    for rel, (nasa_id, variant) in VIDEOS.items():
        q = urllib.parse.quote(nasa_id)
        get(f"{NASA_VIDEO}/{q}/{q}~{variant}.mp4", media / rel)
    for sid in STILLS:
        get(f"{NASA_IMAGE}/{sid}/{sid}~orig.jpg", media / "stills" / f"{sid}.jpg")
    for rel, url in AUDIO.items():
        get(url, media / rel)
    for rel, url in MUSIC.items():                   # score_pd.py: CRAFTWORK/music/pd
        get(url, root / "music" / "pd" / Path(rel).name)
    for rel, url in MOON_KIT.items():                # blender/moon_anim.py: CRAFTWORK/bg/nasa-moon
        get(url, root / rel)
    # the launch countdown is cut from the KSC "Apollo 11 Activities" reel's audio (last 8 minutes)
    tail = media / "work" / "activities_tail.wav"
    if not tail.exists() and shutil.which("ffmpeg"):
        tail.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-480", "-i", str(media / "video/activities_mobile.mp4"),
                        "-vn", "-ac", "1", "-ar", "16000", str(tail)], check=True)
    print("done. Still to get by hand (see docstring): Sonniss SFX, Blue Marble texture, Poly Haven HDRI, fonts.")


if __name__ == "__main__":
    sys.exit(main())
