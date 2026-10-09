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
TOTAL = 87.5            # v18: credits 3.45 + 4.45 s, black to 87.5; tables unchanged (silence from 86.3) (v17 87.0; v8-v16 81.8; v7: 88.5)
USE_PD = True

# (file, src_in, src_out, timeline_in, gain_db, fade_in_s, fade_out_s)
MUSIC = [
    # Dvorak 9 iv: string build under the countdown; the tutti theme (src 11.9) lands on the drop (10.6).
    # v8: act 2 is 6.7 s shorter, so src 24.9-31.6 is cut out at two detected onsets (splice at timeline 23.6);
    # the phrase still ends with the orchestra's cutoff at src 41.0 (timeline 33.0), 0.18 s before Mars as in v7.
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 1.3, 24.9, 0.0, 0.0, 0.6, 0.03),
    # v17: to src 41.45 (before the next phrase ~41.5) with a 1.3 s equal-power fade, 32.15 -> 33.45 (was out at 33.12)
    # v18m: to src 41.35, 0.2 s ease: the E-minor chord (src 40.0 = 32.0) decays alone, no overlap with the Egmont
    (PD / "dvorak9_iv_allegro_con_fuoco.ogg", 31.6, 41.35, 23.6, 0.0, 0.03, 0.06),   # v19b: 0.2 -> 0.06 s so RING_OUT[1] rings on the chord (the 0.2 s fade left the ring nothing)
    # v13 (rights fix; Holst "Mars" / USAF Band out): Beethoven, Egmont Overture Op. 84, Czech National SO / Musopen
    # (PD worldwide). One continuous span, no splice: the hushed chords after Egmont's death fade in under the lunar
    # transition; Beethoven's general pause (src 442.25-443.25) falls at 42.40-43.40 under "1202."; the Allegro con
    # brio's pp -> ff string crescendo drives the alarm and the fuel countdown; the F-major tutti (attack src 456.10)
    # lands on the touchdown flash (56.25); hard stop at 61.9 (src 461.75), one eighth after the beat-3 accent (461.58).
    # v17: pre-lap 1.0 s (src 432.15 at 32.30: pp chords; 433.15 stays on 33.3), 1.0 s u^2 fade-in; out 0.06 s + ring-out
    # v18m: enters at 34.0 (src 433.85; same map, 433.15 = 33.3) under the locked-off Moon, 0.8 s ease
    (PD / "beethoven_egmont_overture_musopen.flac", 433.85, 461.75, 34.0, 0.0, 0.8, 0.06),   # v15: fade-in 2.5 -> 1.0 s; v16b: 0.15 s
    # Dvorak 9 ii Largo: the opening brass chorale swells out of the silence; its forte (src ~19) peaks on the end title.
    # v17: fade-in 1.4 -> 1.8 s (smoothstep); to src 28.6 under both credit cards (the chorale's phrase ends ~24.2 =
    # 81.9, then the pp Db chord, -38..-40 dBFS in the source), 1.8 s smoothstep fade to 86.3, then 0.7 s of silence
    # v18m: same map (src 5.2 = 62.9) from the B-flat onset src 4.69 = 62.39, 0.5 s ease: F -> B-flat (V -> I) in the black
    (PD / "dvorak9_ii_largo.ogg", 4.69, 29.05, 62.39, 0.0, 0.5, 1.8),     # v18m: to src 29.05 = 86.75 (patch_v18's card 2 end; the pp D-flat chord holds -39 dB to src 29.4)
]
# v17: fade shapes per MUSIC index (in, out): lin | sq (u^2) | sine (equal power) | ease (smoothstep); default lin/lin
FADE_SHAPE = {1: ("lin", "ease"), 2: ("ease", "lin"), 3: ("ease", "ease")}     # v18m: 1 out sine -> ease, 2 in sq -> ease
# v17: per-entry automation across the 33.3 crossfade: MUSIC_AUTO is read at max(t, lo) / min(t, hi) for that entry, so
# the Dvorak holds the 33.2 value (-6.65 dB) while it fades and the Egmont pre-lap takes the 33.3 value (+11.5 dB)
AUTO_CLAMP = {1: (None, 33.2), 2: (34.0, None), 3: (62.9, None)}     # v18m: Egmont from 34.0; Largo's pre-lap at the 62.9 value
# v17: ring-out after the Egmont hard stop (61.9): (window s, RT60 s, wet dB re the dry's last 100 ms, tail s)
RING_OUT = {1: (0.30, 1.8, -6.0, 1.6), 2: (0.30, 1.6, -8.0, 1.8)}     # v19b: the Dvorak's E-minor chord rings out through the 0:33 hold
# gain automation on the music bus: (time, dB), linear in dB between points
# v15: lunar valley 33.3-39.9 +1.5 dB (v14 8.5 -> 8.0), ramps back to v14's 8.0 by 40.3; with the 1.0 s Egmont fade, emulated
# (real 2-pass loudnorm) lunar -16.7 -> -15.5 LUFS, 1202 -14.1 -> -14.3, bingo -13.2 -> -13.3, landing -11.0 -> -11.1 (loudest)
# v16b: lunar valley +1.5 dB more (33.3 10.0 -> 11.5, 39.9 9.5 -> 11.0); 40.3 on unchanged
MUSIC_AUTO = [(0, -10), (10.4, -6), (10.6, 0), (19, 0), (19.5, -8), (32.3, -8), (33.2, -6.65), (34.0, 6.0), (35.0, 11.5), (39.9, 11.0), (40.3, 8.0), (43.4, 7.0), (48.9, 5.5), (53.6, 1.0), (56.2, 2.0), (58.7, 4.0), (61.9, 4.0), (62.9, -0.5), (81.3, 1.5)]     # v13: 33.3-61.9 re-tuned for Egmont (pp chords lifted, the written crescendo flattened, tutti held under the landing); v11: Holst ramps 50.0 -> +4 by "30 seconds" (53.6), +5.5 at the touchdown cut, +8 under the landing; v9: act-2 plateau -1.5 dB; lunar valley 33.3-40.3 +3 dB (guards 33.2 / 40.8); v8: act 2 shorter, later points -6.7
# (file under SON, timeline_t, gain_db, align: "attack" = onset at t | "peak" = loudest 50 ms at t, max_len_s)
SONNISS = [
    # v19b: pitchless space-air bed under the 0:33 hold (absolute path: generated by patch_v19b, not Sonniss);
    # "attack" aligns ~0.15 s into its 0.5 s fade-in, so it starts at ~33.0
    (str((CRAFTWORK / "inbox/moonshot/work/audio_assets/space_air_v19b.wav")), 33.15, -7.0, "attack", 2.2),
    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_02.wav", 10.6, -2.0, "attack", 6.0),
    ("DavidDumais - Explosion SFX Pack/EXPLDsgn_Nuclear Explosion 07_DDUMAIS_NONE.wav", 10.62, -8.0, "attack", 9.0),
    ("Mechanical Wave - Cinematic Feel/WHSH_Sci-Fi Heavy Whoosh_MWSFX_CF 29.wav", 13.15, -6.0, "peak", 6.0),
    ("Mechanical Wave - Cinematic Feel/DSGNBoom_Cinematic Hit_MWSFX_CF 05.wav", 13.2, -4.0, "attack", 5.0),
    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 17.53, -8.0, "peak", 3.0),    # v19: 17.45 -> 17.53 with the cut (17.6 -> 17.667)
    ("Chupapsound - Essential Scifi/WHOOSH PASS SF LOW.wav", 21.783, -10.0, "peak", 3.0),   # v19b: v18's 50 ms lead on the 21.8333 cut (Codex)   # v19: 21.95 -> 21.83 with the cut (22.0 -> 21.833)
    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 28.0, -12.0, "attack", 4.0),   # v10: -5 dB (stage separation)
    ("Jake Fielding - Haunted Metal Vol.2 - Cinematic Creaks & Risers/DSGNRise_Cinematic Metallic Riser, Trailer, Designed Eerie Wail_JF_Haunted Metal Vol 2_02.wav", 40.3, -10.0, "peak", 14.0),
    ("BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_glitch_malfunction_004.wav", 40.383, -9.0, "attack", 0.6),
    ("BluezoneCorp - Retrofuturistic Computer/Bluezone_BC0304_retrofuturistic_computer_alarm_005.wav", 40.5, -14.0, "attack", 2.4),
    ("BluezoneCorp - Futuristic User Interface/Bluezone_BC0303_futuristic_user_interface_data_glitch_003.wav", 42.9, -10.0, "attack", 0.5),
    ("BluezoneCorp - Alien Tripod/Bluezone_BC0292_alien_tripod_debris_rock_collapse_earthquake_rumble_large_005.wav", 50.7, -14.0, "attack", 5.5),
    ("Jake Fielding - Haunted Metal Vol.1 - Cinematic Hits & Impacts/DSGNBoom_Cinematic Metallic Hit, Boom, Trailer, Sub_JF_Haunted Metal Vol 1_18.wav", 76.7, -5.0, "attack", 9.0),   # v17: 6.4 -> 9.0 s: decays to ~-62 dBFS by 84.5 inside the film (v16 was cut by the file end at 81.8)
    # v17: touchdown transient on the 56.2 white flash (the 28.0 stage-separation impact, reused)
    ("BluezoneCorp - Modern Cinematic Impact/Bluezone_BC0294_modern_cinematic_impact_boom_003.wav", 56.2, -4.0, "attack", 3.0),
    # v17: a quiet comm tick (quindar-like 80 ms beep, 4.7 kHz) before Armstrong's "Staging." (speech 26.55, duck from 26.25)
    ("BluezoneCorp - Futuristic User Interface/Bluezone_BC0303_futuristic_user_interface_high_tech_beep_038.wav", 26.17, -30.0, "attack", 0.08),
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


def fade_curve(u: np.ndarray, kind: str) -> np.ndarray:
    """v17: gain for fade position u (0 = silent end, 1 = full)."""
    if kind == "sq":
        return u * u
    if kind == "sine":
        return np.sin(np.pi / 2 * u)
    if kind == "ease":
        return u * u * (3 - 2 * u)
    return u


def ring_out(x: np.ndarray, win: float, rt60: float, wet_db: float, tail: float) -> np.ndarray:
    """v17: a hall-style ring-out after a hard musical stop: the last `win` s of x (rising half-Hann) convolved with an
    exponentially decaying stereo noise IR (RT60 `rt60`, rolled off above 3 kHz; FFT convolution = afir). The wet is
    scaled so its first 50 ms after the stop sit `wet_db` under the dry's last 100 ms (before the dry's own fade), comes
    in over the dry's last 80 ms and runs `tail` s past the end (50 ms fade at its end). Returns x + tail samples."""
    nw, nt = int(win * SR), int(tail * SR)
    seg = x[-nw:].astype(np.float64) * np.hanning(2 * nw)[:nw, None]
    rng = np.random.default_rng(1969)
    ir = rng.normal(0, 1, (nt, 2)) * np.exp(-6.908 * np.arange(nt) / SR / rt60)[:, None]
    f = np.fft.rfftfreq(nt, 1 / SR)
    ir = np.fft.irfft(np.fft.rfft(ir, axis=0) * np.exp(-0.5 * (np.maximum(f - 3000, 0) / 2500) ** 2)[:, None], n=nt, axis=0)
    m = nw + nt
    nfft = 1 << (m - 1).bit_length()
    wet = np.fft.irfft(np.fft.rfft(seg, nfft, axis=0) * np.fft.rfft(ir, nfft, axis=0), nfft, axis=0)[:m]
    rms = lambda y: float(np.sqrt(np.mean(np.square(y, dtype=np.float64))))  # noqa: E731
    ref = rms(x[-int(0.16 * SR):-int(0.06 * SR)])
    wet *= ref * 10 ** (wet_db / 20) / max(rms(wet[nw:nw + int(0.05 * SR)]), 1e-12)
    xf = int(0.08 * SR)
    wet *= np.clip((np.arange(m) - (nw - xf)) / xf, 0, 1)[:, None]
    fe = int(0.05 * SR)
    wet[-fe:] *= np.linspace(1, 0, fe)[:, None]
    out = np.zeros((len(x) + nt, 2), np.float32)
    out[:len(x)] = x
    out[len(x) - nw:] += wet.astype(np.float32)
    return out


def stage_music() -> None:
    n = int(TOTAL * SR)
    mus = np.zeros((n, 2), np.float32)
    ax, ay = [p[0] for p in MUSIC_AUTO], [p[1] for p in MUSIC_AUTO]
    for i, (src, a, b, t, g, fi, fo) in enumerate(MUSIC):
        x = load_stereo(src, a, b) * np.float32(10 ** (g / 20))
        k1, k2 = max(int(fi * SR), 1), max(int(fo * SR), 1)
        shp_in, shp_out = FADE_SHAPE.get(i, ("lin", "lin"))
        x[:k1] *= fade_curve(np.linspace(0, 1, k1, dtype=np.float32), shp_in)[:, None]
        x[-k2:] *= fade_curve(np.linspace(1, 0, k2, dtype=np.float32), shp_out)[:, None]
        if i in RING_OUT:
            x = ring_out(x, *RING_OUT[i])
        # v17: MUSIC_AUTO per entry (was one bus multiply: identical for unclamped entries), clamped by AUTO_CLAMP
        lo, hi = AUTO_CLAMP.get(i, (None, None))
        te = (int(t * SR) + np.arange(len(x))) / SR
        te = np.clip(te, -np.inf if lo is None else lo, np.inf if hi is None else hi)
        x *= (10 ** (np.interp(te, ax, ay) / 20)).astype(np.float32)[:, None]
        place(mus, x, int(t * SR))
        print(f"  music {src.name} {a:.2f}-{b:.2f} @ {t:.2f}")
    # v17: no digital zero 61.9-62.9 any more (v8-v16): the Egmont rings out into it and the Largo fades in from 62.9
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
