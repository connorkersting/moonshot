"""v2 soundtrack: public-domain orchestral recordings cut to the picture, plus a Sonniss SFX layer.

Writes work/audio/music_pd.f32 and work/audio/sonniss.f32 (48 kHz stereo float32, TOTAL seconds).
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np

ROOT = CRAFTWORK
AUD = ROOT / "inbox" / "moonshot" / "work" / "audio"
PD = ROOT / "music" / "pd"
SON = ROOT / "sfx" / "sonniss-gdc2024"
SR = 48000
TOTAL = 81.8            # v8 (v7: 88.5)
USE_PD = True

# (file, src_in, src_out, timeline_in, gain_db, fade_in_s, fade_out_s)
MUSIC = [
    # Dvorak 9 iv: string build under the countdown; the tutti theme (src 11.9) lands on the drop (10.6).
    # v8: act 2 is 6.7 s shorter, so src 24.9-31.6 is cut out at two detected onsets (splice at timeline 23.6);
    # the phrase still ends with the orchestra's cutoff at src 41.0 (timeline 33.0), 0.18 s before Mars as in v7.
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 1.3, 24.9, 0.0, 0.0, 0.6, 0.03),
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.12, 23.6, 0.0, 0.03, 0.10),
    # Holst Mars (USAF Band): ostinato fades in under the lunar transition; the brass climax (src 85.0) lands
    # under "The Eagle has landed" (v8 ~59.3); hard cut at the white flash (v8 61.9).
    (PD / "holst_mars_usaf_band.ogg", 59.0, 87.6, 33.3, 0.0, 2.5, 0.03),
    # Dvorak 9 ii Largo: the opening brass chorale swells out of the silence; its forte (src ~19) peaks on the end title.
    (PD / "dvorak9_ii_largo.ogg", 5.2, 24.0, 62.9, 0.0, 1.4, 1.6),
]
# gain automation on the music bus: (time, dB), linear in dB between points
MUSIC_AUTO = [(0, -10), (10.4, -6), (10.6, 0), (19, 0), (19.5, -8), (32.3, -8), (33.2, -6.65), (33.3, -2), (40.3, -3), (40.8, -5.53), (48.3, 1.5), (50.0, 1.5), (53.6, 4.0), (56.2, 5.5), (58.7, 8.0), (61.9, 8.0), (62.9, -0.5), (81.3, 1.5)]     # v11: Holst ramps 50.0 -> +4 by "30 seconds" (53.6), +5.5 at the touchdown cut, +8 under the landing; v9: act-2 plateau -1.5 dB; lunar valley 33.3-40.3 +3 dB (guards 33.2 / 40.8); v8: act 2 shorter, later points -6.7
# (file under SON, timeline_t, gain_db, align: "attack" = onset at t | "peak" = loudest 50 ms at t, max_len_s)
SONNISS = [
    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_02.wav", 10.6, -2.0, "attack", 6.0),
    ("DavidDumais - Explosion SFX Pack/EXPLDsgn_Nuclear Explosion 07_DDUMAIS_NONE.wav", 10.62, -8.0, "attack", 9.0),
    ("Mechanical Wave - Cinematic Feel/WHSH_Sci-Fi Heavy Whoosh_MWSFX_CF 29.wav", 13.15, -6.0, "peak", 6.0),
    ("Mechanical Wave - Cinematic Feel/DSGNBoom_Cinematic Hit_MWSFX_CF 05.wav", 13.2, -4.0, "attack", 5.0),
    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 17.45, -8.0, "peak", 3.0),
    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 21.95, -10.0, "peak", 3.0),
    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -12.0, "attack", 4.0),   # v10: -5 dB (stage separation)
    ("Jake Fielding - Haunted Metal Vol.2 - Cinematic Creaks & Risers/DSGNRise_Cinematic Metallic Riser, Trailer, Designed Eerie Wail_JF_Haunted Metal Vol 2_02.wav", 40.3, -10.0, "peak", 14.0),
    ("BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_glitch_malfunction_004.wav", 40.383, -9.0, "attack", 0.6),
    ("BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_alarm_005.wav", 40.5, -14.0, "attack", 2.4),
    ("BluezoneCorp - Futuristic User Interface/Bluezone_BC0303_futuristic_user_interface_data_glitch_003.wav", 42.9, -10.0, "attack", 0.5),
    ("BluezoneCorp - Alien Tripod/Bluezone_BC0292_alien_tripod_debris_rock_collapse_earthquake_rumble_large_005.wav", 50.7, -14.0, "attack", 5.5),
    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_18.wav", 76.7, -5.0, "attack", 6.4),
]


def load_stereo(path: Path, t_in: float = 0.0, t_out: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}"]
    if t_out is not None:
        cmd += ["-t", f"{t_out - t_in:.3f}"]
    cmd += ["-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def place(bus: np.ndarray, x: np.ndarray, i0: int, s0: int = 0) -> None:
    n = len(bus)
    if i0 < 0:
        s0 += -i0
        i0 = 0
    i1 = min(i0 + len(x) - s0, n)
    if i1 > i0:
        bus[i0:i1] += x[s0:s0 + i1 - i0]


def stage_music() -> None:
    n = int(TOTAL * SR)
    mus = np.zeros((n, 2), np.float32)
    for src, a, b, t, g, fi, fo in MUSIC:
        x = load_stereo(src, a, b) * np.float32(10 ** (g / 20))
        k1, k2 = max(int(fi * SR), 1), max(int(fo * SR), 1)
        x[:k1] *= np.linspace(0, 1, k1, dtype=np.float32)[:, None]
        x[-k2:] *= np.linspace(1, 0, k2, dtype=np.float32)[:, None]
        place(mus, x, int(t * SR))
        print(f"  music {src.name} {a:.2f}-{b:.2f} @ {t:.2f}")
    tt = np.arange(n) / SR
    auto = np.interp(tt, [p[0] for p in MUSIC_AUTO], [p[1] for p in MUSIC_AUTO])
    mus *= (10 ** (auto / 20)).astype(np.float32)[:, None]
    mus[int(61.9 * SR):int(62.9 * SR)] = 0.0          # the silence after the flash (v8; v7 68.6-69.6)
    son = np.zeros((n, 2), np.float32)
    hop = int(0.05 * SR)
    for rel, t, g, align, maxlen in SONNISS:
        x = load_stereo(SON / rel)[: int(maxlen * SR)]
        if align == "peak":
            blocks = np.sqrt(np.mean((x[: len(x) // hop * hop, 0] ** 2).reshape(-1, hop), axis=1))
            ref = int(blocks.argmax()) * hop
        else:
            env = np.abs(x).max(axis=1)
            ref = int(np.argmax(env > 0.3 * env.max()))
        x = x * np.float32(10 ** (g / 20))
        f = int(0.03 * SR)
        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        h3 = int(0.010 * SR)
        x[:h3] *= np.linspace(0, 1, h3, dtype=np.float32)[:, None]   # no click at the head
        place(son, x, int(t * SR) - ref)
        print(f"  sfx {Path(rel).name[:58]:58s} @ {t:6.2f} ({align}, ref {ref / SR:.2f}s)")
    son[int(61.96 * SR):int(62.9 * SR)] = 0.0       # v8 (v7 68.66-69.6)
    assert np.isfinite(mus).all() and np.isfinite(son).all()
    mus.astype(np.float32).tofile(AUD / "music_pd.f32")
    son.astype(np.float32).tofile(AUD / "sonniss.f32")
    print("music_pd + sonniss stems written")


if __name__ == "__main__":
    stage_music()
