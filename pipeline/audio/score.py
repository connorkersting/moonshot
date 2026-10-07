"""MOONSHOT (Apollo 11 trailer): synthesized score and SFX stems.

Reads the cue sheet (cues.json) and renders two 48 kHz float32 stereo stems,
each exactly `total` seconds long:

    music.wav  drones, pads, bass ostinato, drums/toms, risers, the swell
    sfx.wav    impacts, sub booms, whooshes, heartbeat, clock ticks, glitches,
               master alarm, telemetry blips, reverse swells

Everything is synthesized with numpy/scipy. No samples, no downloads.

Usage:
    py score.py                          # reads ../cues.json, writes next to this file
    py score.py --cues X.json --out DIR

Section times and SFX times come from the cue sheet. Musical details the cue
sheet does not state as a field (riser lengths, the suck-back gap, Shepard
start, timpani target, fade end) are the constants below, expressed relative
to cue-sheet anchors, so moving a cue in the JSON moves the music with it.
Optional JSON overrides: act2_groove "hits": [..], swell_outro "fade_end": x.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile
from scipy.ndimage import minimum_filter1d, uniform_filter1d

SR = 48_000
SEED = 1969

# --- arrangement constants (seconds, relative to cue-sheet anchors) ---------
GAP_BEFORE_DROP = 0.25      # near-silence before the drop (10.35 -> 10.6)
SUCK_LEN = 0.45             # reverse suck-back, ends at drop - GAP (9.9 -> 10.35)
COLD_RISER_LEN = 4.35       # cold-open riser, ends at drop - GAP (6.0 -> 10.35)
SUB_SWELL_LEN = 7.0         # cold-open sub swell, ends at drop - GAP
HEART1_RAMP_LEAD = 0.6      # cold heartbeat reaches top tempo at drop - 0.6 (10.0)
HEART1_BPM = (66.0, 110.0)
HEART2_OFFSET = 8.0         # heartbeat returns at descent start + 8 (52.0)
HEART2_BPM = (90.0, 140.0)
CHOP_LEN = 2.0              # pad stutter from the first descent glitch burst (47 -> 49)
SHEPARD_OFFSET = 11.0       # Shepard riser starts at descent start + 11 (55.0), peaks at riser_peak
SFX_RISER_LEN = 4.0         # SFX riser that culminates at riser_peak
GROOVE_RISER_LEN = 2.0      # risers into groove hits and into the 40.0 cut
TIMP_TARGET_OFFSET = 6.4    # timpani roll lands at swell start + 6.4 (76.0)
TIMP_ROLL_LEN = 2.4
CHORD_LEN = 2.5             # swell progression chord length
FADE_LEAD = 0.2             # everything silent by total - 0.2 (89.8) unless "fade_end" given
FLASH_LEN = 0.06            # flash transient length (must be <= 0.08)

DIALOGUE_DUCK_DB = -9.0     # 1-4 kHz cut in music under dialogue sections
MUSIC_TARGET_LUFS = -20.0
SFX_TARGET_LUFS = -22.0
TP_LIMIT_DBTP = -3.0


# =============================================================================
# basic utilities
# =============================================================================
def ns(sec: float) -> int:
    return int(round(sec * SR))


def tvec(n: int) -> np.ndarray:
    return np.arange(n) / SR


def midi_hz(m: float | np.ndarray) -> np.ndarray | float:
    return 440.0 * 2.0 ** ((np.asarray(m, dtype=float) - 69.0) / 12.0)


def db(x: float) -> float:
    return 10.0 ** (x / 20.0)


def dexp(t: np.ndarray, tau: float) -> np.ndarray:
    """exp(-t/tau) for t >= 0, 1 before: never exp(+large)."""
    return np.exp(-np.maximum(t, 0.0) / tau)


def rise(t: np.ndarray, a: float) -> np.ndarray:
    """Raised-cosine 0 -> 1 over [0, a]."""
    if a <= 0:
        return np.ones_like(t)
    u = np.clip(t / a, 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * u)


def fall(t: np.ndarray, t0: float, t1: float) -> np.ndarray:
    """1 before t0, raised-cosine down to 0 at t1, 0 after."""
    u = np.clip((t - t0) / max(t1 - t0, 1e-9), 0.0, 1.0)
    return 0.5 + 0.5 * np.cos(np.pi * u)


def sat(x: np.ndarray, drive: float) -> np.ndarray:
    return np.tanh(drive * x) / np.tanh(drive)


def norm(x: np.ndarray, peak: float = 1.0) -> np.ndarray:
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return x * (peak / m) if m > 0 else x


def edge_fade(x: np.ndarray, fin: float = 0.005, fout: float = 0.005) -> np.ndarray:
    """Raised-cosine fades at both ends (>= 5 ms by default)."""
    y = np.array(x, dtype=float, copy=True)
    n = len(y)
    if n < 4:
        return y * 0.0
    a = min(max(ns(fin), 1), n // 2)
    b = min(max(ns(fout), 1), n // 2)
    ra = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    rb = (0.5 - 0.5 * np.cos(np.pi * np.arange(b) / b))[::-1]
    if y.ndim == 2:
        ra, rb = ra[:, None], rb[:, None]
    y[:a] *= ra
    y[n - b:] *= rb
    return y


def pan(x: np.ndarray, p: float | np.ndarray = 0.0) -> np.ndarray:
    """Equal-power pan of a mono signal; p in [-1, 1] (scalar or per-sample)."""
    a = (np.clip(p, -1.0, 1.0) + 1.0) * np.pi / 4.0
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1) * np.sqrt(2.0)


def to_stereo(x: np.ndarray, p: float | np.ndarray = 0.0) -> np.ndarray:
    return x if x.ndim == 2 else pan(x, p)


def haas(x: np.ndarray, ms: float = 14.0, right: bool = True) -> np.ndarray:
    """Haas widening: mono -> stereo with one side delayed."""
    d = ns(ms / 1000.0)
    late = np.concatenate([np.zeros(d), x[:-d]]) if d > 0 else x
    return np.stack([x, late] if right else [late, x], axis=1)


def curve(times: np.ndarray, pts: list[tuple[float, float]]) -> np.ndarray:
    pts = sorted(pts)
    return np.interp(times, [p[0] for p in pts], [p[1] for p in pts])


# =============================================================================
# oscillators
# =============================================================================
def phase_from_freq(f: float | np.ndarray, n: int, phase0: float = 0.0) -> np.ndarray:
    f = np.broadcast_to(np.asarray(f, dtype=float), (n,))
    c = np.cumsum(f)
    return phase0 + (c - f[0]) / SR


def sine(f: float | np.ndarray, n: int, phase0: float = 0.0) -> np.ndarray:
    return np.sin(2.0 * np.pi * phase_from_freq(f, n, phase0))


def saw_blep(f: float | np.ndarray, n: int, phase0: float = 0.0) -> np.ndarray:
    """Band-limited (polyBLEP) sawtooth with arbitrary frequency curve."""
    fa = np.broadcast_to(np.asarray(f, dtype=float), (n,))
    ph = np.mod(phase_from_freq(fa, n, phase0), 1.0)
    dt = np.clip(fa / SR, 1e-9, 0.5)
    y = 2.0 * ph - 1.0
    m = ph < dt
    x = ph[m] / dt[m]
    y[m] -= x + x - x * x - 1.0
    m = ph > 1.0 - dt
    x = (ph[m] - 1.0) / dt[m]
    y[m] -= x * x + x + x + 1.0
    return y


def supersaw(freq: float | np.ndarray, n: int, rng: np.random.Generator, voices: int = 7,
             detune: float = 14.0, width: float = 0.9, vib_rate: float = 0.0,
             vib_depth: float = 0.0) -> np.ndarray:
    """Detuned saw stack, voices spread across the stereo field. Returns (n, 2)."""
    freq = np.broadcast_to(np.asarray(freq, dtype=float), (n,))
    out = np.zeros((n, 2))
    offs = np.linspace(-1.0, 1.0, voices) if voices > 1 else np.zeros(1)
    t = tvec(n) if vib_depth else None
    for o in offs:
        cents = o * detune + rng.uniform(-1.5, 1.5)
        f = freq * 2.0 ** (cents / 1200.0)
        if vib_depth:
            rate = vib_rate * (1.0 + 0.12 * o)
            f = f * 2.0 ** (vib_depth / 1200.0 * np.sin(2 * np.pi * rate * t + rng.uniform(0, 2 * np.pi)))
        out += pan(saw_blep(f, n, rng.uniform()), o * width)
    return out / np.sqrt(len(offs))


def bl_square(f: float, n: int, top: float = 9000.0) -> np.ndarray:
    """Additive band-limited square."""
    y = np.zeros(n)
    k = 1
    while f * k < top:
        y += sine(f * k, n) / k
        k += 2
    return y * 4.0 / np.pi


# =============================================================================
# filters
# =============================================================================
def filt(x: np.ndarray, kind: str, fc: float | list[float], order: int = 2) -> np.ndarray:
    sos = signal.butter(order, fc, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, x, axis=0)


def rbj(kind: str, fc: float, q: float) -> tuple[np.ndarray, np.ndarray]:
    w0 = 2.0 * np.pi * fc / SR
    cw, sw = np.cos(w0), np.sin(w0)
    alpha = sw / (2.0 * q)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    elif kind == "bp":
        b = [alpha, 0.0, -alpha]
    else:
        raise ValueError(kind)
    a = [1 + alpha, -2 * cw, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


def tv_filter(x: np.ndarray, kind: str, fc: float | np.ndarray, q: float = 0.707,
              block: int = 128) -> np.ndarray:
    """Time-varying RBJ biquad (coefficients updated per block, state carried)."""
    x = np.asarray(x, dtype=float)
    mono = x.ndim == 1
    X = x[:, None] if mono else x
    n = len(X)
    fca = np.broadcast_to(np.asarray(fc, dtype=float), (n,))
    y = np.empty_like(X)
    zi = np.zeros((2, X.shape[1]))
    for s in range(0, n, block):
        e = min(n, s + block)
        f = float(np.clip(fca[(s + e - 1) // 2], 20.0, 0.45 * SR))
        b, a = rbj(kind, f, q)
        y[s:e], zi = signal.lfilter(b, a, X[s:e], axis=0, zi=zi)
    return y[:, 0] if mono else y


def lr4(x: np.ndarray, kind: str, fc: float) -> np.ndarray:
    sos = signal.butter(2, fc, btype=kind, fs=SR, output="sos")
    return signal.sosfilt(sos, signal.sosfilt(sos, x, axis=0), axis=0)


def mid_band_duck(x: np.ndarray, g: np.ndarray) -> np.ndarray:
    """3-band Linkwitz-Riley split at 1 kHz / 4 kHz; scale the mid band by g(t)."""
    low = lr4(x, "low", 1000.0)
    rest = lr4(x, "high", 1000.0)
    mid = lr4(rest, "low", 4000.0)
    high = lr4(rest, "high", 4000.0)
    low = lr4(low, "low", 4000.0) + lr4(low, "high", 4000.0)  # phase-match the low band
    return low + mid * g[:, None] + high


def feedback_delay(x: np.ndarray, delay: float, fb: float, taps: int, lp_start: float = 4000.0) -> np.ndarray:
    """Ping-pong delay, each repeat darker. x stereo; output longer by taps*delay."""
    d = ns(delay)
    out = np.zeros((len(x) + d * taps, 2))
    out[:len(x)] += x
    cur = x
    for k in range(1, taps + 1):
        cur = filt(cur, "low", max(lp_start / (1 + 0.5 * k), 300.0))
        rep = cur[:, ::-1] * (fb ** k)   # swap channels each repeat
        out[k * d:k * d + len(x)] += rep
    return out


# =============================================================================
# reverb
# =============================================================================
def make_ir(rt60: float, length: float, predelay: float, rng: np.random.Generator,
            hf_ratio: float = 0.45, lf_ratio: float = 1.2) -> np.ndarray:
    """Stereo decorrelated noise IR with band-dependent decay and early reflections."""
    n = ns(length)
    t = tvec(n)
    ir = np.zeros((n, 2))
    for ch in range(2):
        w = rng.standard_normal(n)
        lo = filt(w, "low", 450.0)
        hi = filt(w, "high", 3500.0)
        mid = w - lo - hi
        dec = lambda rt: 10.0 ** (-3.0 * t / rt)  # noqa: E731
        y = lo * dec(rt60 * lf_ratio) + mid * dec(rt60) + 0.6 * hi * dec(rt60 * hf_ratio)
        y *= rise(t, 0.04)
        for _ in range(12):
            i = ns(rng.uniform(0.004, 0.08))
            y[i] += rng.uniform(-3.0, 3.0)
        y *= fall(t, length * 0.85, length)
        ir[:, ch] = y
    ir = np.vstack([np.zeros((ns(predelay), 2)), ir])
    return ir / np.sqrt(np.sum(ir ** 2, axis=0))


# =============================================================================
# bus (dry + two reverb sends), allocated only over its own time range
# =============================================================================
class Bus:
    def __init__(self, t0: float, t1: float) -> None:
        self.i0 = ns(t0)
        self.n = ns(t1) - self.i0
        self.dry = np.zeros((self.n, 2))
        self.hall = np.zeros((self.n, 2))
        self.long = np.zeros((self.n, 2))

    def add(self, sig: np.ndarray, t: float, gain: float = 1.0, p: float | np.ndarray = 0.0,
            hall: float = 0.0, long: float = 0.0, dry: float = 1.0) -> None:
        s = to_stereo(np.asarray(sig, dtype=float), p) * gain
        i = ns(t) - self.i0
        j = 0
        if i < 0:
            j, i = -i, 0
        e = min(self.n, i + len(s) - j)
        if e <= i:
            return
        seg = s[j:j + (e - i)]
        if dry:
            self.dry[i:e] += seg * dry
        if hall:
            self.hall[i:e] += seg * hall
        if long:
            self.long[i:e] += seg * long

    def times(self) -> np.ndarray:
        return (np.arange(self.n) + self.i0) / SR

    def apply(self, g: np.ndarray) -> None:
        for b in (self.dry, self.hall, self.long):
            b *= g[:, None]

    def merge_into(self, other: "Bus") -> None:
        i = self.i0 - other.i0
        e = min(other.n, i + self.n)
        k = e - i
        other.dry[i:e] += self.dry[:k]
        other.hall[i:e] += self.hall[:k]
        other.long[i:e] += self.long[:k]

    def render(self, ir_hall: np.ndarray, ir_long: np.ndarray) -> np.ndarray:
        out = self.dry.copy()
        for send, ir in ((self.hall, ir_hall), (self.long, ir_long)):
            if not np.any(send):
                continue
            for ch in range(2):
                out[:, ch] += signal.oaconvolve(send[:, ch], ir[:, ch])[:self.n]
        return out


# =============================================================================
# instruments: percussion and impacts
# =============================================================================
def env_hit(n: int, tau: float, a: float = 0.005) -> np.ndarray:
    t = tvec(n)
    return rise(t, a) * dexp(t - a, tau)


def sub_boom(dur: float, f0: float, f1: float, drop_tau: float, tau: float, drive: float = 1.8) -> np.ndarray:
    """Pitch-dropping sine boom, 5 ms attack, soft-saturated for small-speaker harmonics."""
    n = ns(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / drop_tau)
    y = sat(sine(f, n) * env_hit(n, tau), drive)
    return edge_fade(y, 0.005, min(0.4, dur / 3))


def click_layer(rng: np.random.Generator, lo: float = 2000.0, dur: float = 0.012) -> np.ndarray:
    """Short windowed click transient (5 ms rise) for impact definition."""
    n = ns(dur)
    x = filt(rng.standard_normal(n), "high", lo)
    return edge_fade(norm(x * env_hit(n, 0.002)), 0.005, 0.004)


def crack(dur: float, lo: float, hi: float, tau: float, rng: np.random.Generator) -> np.ndarray:
    n = ns(dur)
    x = filt(rng.standard_normal((n, 2)), "bandpass", [lo, hi])
    return edge_fade(norm(x * env_hit(n, tau)[:, None]), 0.005, 0.02)


def metal_ring(dur: float, f0: float, rng: np.random.Generator) -> np.ndarray:
    """Inharmonic bell/plate partials with slow beating, stereo."""
    n = ns(dur)
    t = tvec(n)
    ratios = (0.56, 0.92, 1.19, 1.71, 2.0, 2.74, 3.0, 3.76, 4.07)
    out = np.zeros((n, 2))
    for i, r in enumerate(ratios):
        a = 1.0 / (1.0 + 0.35 * i)
        tau = 1.8 / (1.0 + 0.45 * i)
        for ch, det in ((0, 1.0 - 0.0015), (1, 1.0 + 0.0015)):
            out[:, ch] += a * sine(f0 * r * det, n, rng.uniform()) * dexp(t - 0.005, tau)
    out *= rise(t, 0.005)[:, None]
    return edge_fade(norm(out), 0.005, 0.2)


def metallic_808(n: int, scale: float = 1.0) -> np.ndarray:
    freqs = np.array([205.3, 304.4, 369.6, 522.7, 540.0, 800.0]) * scale
    return sum(np.sign(sine(f, n)) for f in freqs) / 6.0


def crash(dur: float, rng: np.random.Generator, tau: float = 0.8) -> np.ndarray:
    n = ns(dur)
    met = filt(metallic_808(n, 1.3), "high", 5000.0, 4)
    nz = filt(rng.standard_normal((n, 2)), "high", 4000.0, 2)
    x = nz * 0.7 + pan(met, 0.0) * 0.5
    return edge_fade(norm(x * env_hit(n, tau)[:, None]), 0.005, 0.3)


def big_drum(dur: float, f0: float, f1: float, rng: np.random.Generator, tau: float = 0.5) -> np.ndarray:
    """Taiko-like low drum: pitch-dropping body + skin noise."""
    n = ns(dur)
    t = tvec(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.06)
    body = sat(sine(f, n) * env_hit(n, tau) * 1.4, 1.6)
    skin = filt(rng.standard_normal((n, 2)), "bandpass", [80.0, 1500.0]) * env_hit(n, 0.07)[:, None]
    y = pan(norm(body), 0.0) * 0.8 + norm(skin) * 0.35
    return edge_fade(norm(y), 0.005, min(0.3, dur / 3))


def kick(rng: np.random.Generator) -> np.ndarray:
    n = ns(0.6)
    t = tvec(n)
    f = 48.0 + 92.0 * np.exp(-t / 0.035)
    body = sat(sine(f, n) * env_hit(n, 0.18) * 1.3, 1.5)
    cl = np.zeros(n)
    c = click_layer(rng, 1500.0)
    cl[:len(c)] = c
    return edge_fade(norm(body + 0.25 * cl), 0.005, 0.05)


def tom(rng: np.random.Generator, f0: float = 150.0) -> np.ndarray:
    n = ns(0.7)
    t = tvec(n)
    f = f0 * (0.65 + 0.35 * np.exp(-t / 0.05))
    body = sine(f, n) * env_hit(n, 0.25) + 0.4 * sine(1.5 * f, n) * env_hit(n, 0.12)
    skin = filt(rng.standard_normal(n), "bandpass", [200.0, 2500.0]) * env_hit(n, 0.03)
    y = sat(body * 1.2, 1.4) + 0.3 * norm(skin)
    return edge_fade(norm(y), 0.005, 0.05)


def hat(rng: np.random.Generator, open_: bool = False) -> np.ndarray:
    dur, tau = (0.4, 0.11) if open_ else (0.12, 0.022)
    n = ns(dur)
    met = filt(metallic_808(n, 1.7), "high", 7000.0, 4)
    nz = filt(rng.standard_normal(n), "high", 8000.0, 2)
    return edge_fade(norm((0.6 * met + 0.5 * nz) * env_hit(n, tau)), 0.005, 0.02)


TIMP_RATIOS = (1.0, 1.5, 1.98, 2.44, 2.9)


def timp_stroke(f0: float, vel: float, rng: np.random.Generator, dur: float = 2.6) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    glide = 1.0 + 0.025 * vel * np.exp(-t / 0.05)
    y = np.zeros(n)
    for i, r in enumerate(TIMP_RATIOS):
        a = (0.75 ** i) * (1.0 if i == 0 else 0.6)
        y += a * sine(f0 * r * glide, n, rng.uniform()) * dexp(t - 0.005, 1.2 / (1.0 + 0.7 * i))
    mallet = filt(rng.standard_normal(n), "low", 400.0 + 1200.0 * vel) * dexp(t, 0.012)
    y = (y + 0.5 * norm(mallet)) * rise(t, 0.005)
    return edge_fade(sat(y * 0.7, 1.2) * vel, 0.005, 0.3)


# =============================================================================
# instruments: tonal
# =============================================================================
def env_ahr(n: int, attack: float, hold_end: float, release: float) -> np.ndarray:
    """Raised-cosine attack, hold to hold_end (s), raised-cosine release."""
    t = tvec(n)
    return rise(t, max(attack, 0.005)) * fall(t, hold_end, hold_end + max(release, 0.005))


def pad_chord(midis: list[int], dur: float, attack: float, release: float, cutoff: float,
              rng: np.random.Generator, voices: int = 7, detune: float = 14.0,
              vib: float = 5.0, order: int = 4) -> np.ndarray:
    """String-like pad: detuned saw stacks, lowpassed, wide. Length dur + release."""
    n = ns(dur + release)
    out = np.zeros((n, 2))
    for m in midis:
        out += supersaw(midi_hz(m), n, rng, voices, detune, 0.95, vib_rate=4.6, vib_depth=vib)
    out = filt(out / np.sqrt(len(midis)), "low", cutoff, order)
    out *= env_ahr(n, attack, dur, release)[:, None]
    return edge_fade(out, 0.005, 0.005)


def brass(midis: list[int], dur: float, rng: np.random.Generator, f_lo: float, f_hi: float,
          t_open: float, f_settle: float, decay_tau: float = 3.0, drive: float = 2.5,
          release: float = 0.15) -> np.ndarray:
    """Distorted low brass-like chord: saw stack -> tanh -> opening lowpass."""
    n = ns(dur + release)
    t = tvec(n)
    x = np.zeros((n, 2))
    for m in midis:
        x += supersaw(midi_hz(m), n, rng, voices=5, detune=10.0, width=0.6, vib_rate=5.0, vib_depth=3.0)
    x = sat(x / np.sqrt(len(midis)) * 1.2, drive)
    up = f_lo * (f_hi / f_lo) ** np.clip(t / t_open, 0.0, 1.0)
    down = f_settle + (f_hi - f_settle) * dexp(t - t_open, 0.7)
    fc = np.where(t < t_open, up, down)
    x = tv_filter(tv_filter(x, "lp", fc, q=1.1), "lp", fc * 1.5, q=0.7)
    env = rise(t, 0.005) * (0.55 + 0.45 * dexp(t - 0.005, 0.4)) * dexp(t - 0.3, decay_tau)
    env *= fall(t, dur, dur + release)
    return edge_fade(norm(x * env[:, None]), 0.005, 0.005)


def riser(dur: float, rng: np.random.Generator, f_from: float, f_to: float,
          noise_lo: float, noise_hi: float, tone_cut: tuple[float, float],
          trem: tuple[float, float] = (3.0, 14.0), noise_kind: str = "bp") -> np.ndarray:
    """Noise sweep + pitch-rising supersaw + accelerating tremolo, ends at full level."""
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    nz = rng.standard_normal((n, 2))
    fcn = noise_lo * (noise_hi / noise_lo) ** u
    nz = norm(tv_filter(nz, noise_kind, fcn, q=1.3 if noise_kind == "bp" else 0.8, block=64))
    f = f_from * (f_to / f_from) ** (u ** 1.3)
    ton = supersaw(f, n, rng, voices=5, detune=25.0, width=0.9)
    ton = norm(tv_filter(ton, "lp", tone_cut[0] * (tone_cut[1] / tone_cut[0]) ** u, q=1.0))
    rate = trem[0] + (trem[1] - trem[0]) * u ** 2
    tr = 1.0 - 0.35 * u * (0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(rate) / SR))
    y = (0.6 * nz + 0.5 * ton) * ((u ** 2.2) * tr)[:, None]
    return edge_fade(norm(y), 0.05, 0.005)


# =============================================================================
# instruments: SFX
# =============================================================================
def whoosh(dur: float, mode: str, rng: np.random.Generator, f_lo: float = 300.0,
           f_hi: float = 6000.0, pan_from: float = -0.6, pan_to: float = 0.6) -> np.ndarray:
    n = ns(dur)
    u = tvec(n) / dur
    if mode == "in":
        fc = f_lo * (f_hi / f_lo) ** (u ** 1.6)
        amp, fin, fout = u ** 2.2, 0.03, 0.005
    elif mode == "out":
        fc = f_hi * (f_lo / f_hi) ** (u ** 0.6)
        amp, fin, fout = (1.0 - u) ** 1.8, 0.006, 0.02
    else:
        bell = np.sin(np.pi * u) ** 2
        fc = f_lo * (f_hi / f_lo) ** bell
        amp, fin, fout = bell, 0.02, 0.02
    air = norm(tv_filter(rng.standard_normal((n, 2)), "bp", fc, q=1.4, block=64))
    body = norm(tv_filter(rng.standard_normal(n), "lp", fc * 0.5, q=0.9, block=64))
    y = air * 0.7 + pan(body, pan_from + (pan_to - pan_from) * u) * 0.6
    return edge_fade(norm(y * amp[:, None]), fin, fout)


def heart_thump(rng: np.random.Generator) -> np.ndarray:
    n = ns(0.3)
    t = tvec(n)
    f = 36.0 + 22.0 * np.exp(-t / 0.03)
    body = sine(f, n) * env_hit(n, 0.07)
    knock = filt(rng.standard_normal(n), "low", 180.0) * env_hit(n, 0.025)
    y = sat(body + 0.4 * norm(knock), 2.5)
    return edge_fade(norm(filt(y, "low", 500.0)), 0.005, 0.03)


def heartbeat_times(t0: float, t_end: float, bpm0: float, bpm1: float, t_ramp_end: float) -> list[float]:
    times, t = [], t0
    while t < t_end:
        times.append(t)
        frac = np.clip((t - t0) / max(t_ramp_end - t0, 1e-9), 0.0, 1.0)
        t += 60.0 / (bpm0 + (bpm1 - bpm0) * frac)
    return times


def tick(rng: np.random.Generator, tock: bool) -> np.ndarray:
    n = ns(0.05)
    f1, f2 = (2000.0, 3050.0) if tock else (2600.0, 3950.0)
    y = (sine(f1, n) + 0.6 * sine(f2, n)) * env_hit(n, 0.008)
    y += 0.5 * filt(rng.standard_normal(n), "high", 3000.0) * env_hit(n, 0.003)
    return edge_fade(norm(y), 0.005, 0.01)


def blip(f: float) -> np.ndarray:
    n = ns(0.035)
    y = sine(f, n) * (0.7 + 0.3 * dexp(tvec(n), 0.01))
    return edge_fade(y, 0.005, 0.008)


def glitch(dur: float, rng: np.random.Generator) -> np.ndarray:
    """Bit-crushed, sample-and-held stutter fragments, randomly panned."""
    n = ns(dur)
    out = np.zeros((n, 2))
    pos = 0
    while pos < n:
        L = min(int(rng.integers(ns(0.015), ns(0.05))), n - pos)
        if L < ns(0.012):
            break
        kind = int(rng.integers(0, 3 if pos == 0 else 4))   # never open on a silent fragment
        tt = tvec(L)
        if kind == 0:
            x = saw_blep(rng.uniform(80, 600) * 2.0 ** (tt * rng.uniform(-40, 40)), L)
        elif kind == 1:
            x = rng.standard_normal(L) * 0.6
        elif kind == 2:
            x = np.sign(sine(rng.uniform(200, 2000), L)) * 0.6
        else:
            x = np.zeros(L)
        hold = int(rng.integers(2, 24))
        x = x[(np.arange(L) // hold) * hold]
        q = 2.0 ** int(rng.integers(3, 7))
        x = np.round(x * q) / q
        out[pos:pos + L] += pan(edge_fade(x, 0.005, 0.005), rng.uniform(-0.8, 0.8))
        pos += L
    return edge_fade(norm(filt(out, "high", 150.0)), 0.005, 0.005)


def master_alarm(dur: float, f_a: float = 750.0, f_b: float = 1250.0) -> np.ndarray:
    """Two-tone harsh beeping: A 0.1 s, B 0.1 s, gap 0.05 s."""
    n = ns(dur)
    out = np.zeros(n)
    beep_a = edge_fade(sat(bl_square(f_a, ns(0.1)) * 0.8, 2.0), 0.005, 0.005)
    beep_b = edge_fade(sat(bl_square(f_b, ns(0.1)) * 0.8, 2.0), 0.005, 0.005)
    t = 0.0
    while True:
        for bp, off in ((beep_a, 0.0), (beep_b, 0.1)):
            i = ns(t + off)
            if i + len(bp) <= n:
                out[i:i + len(bp)] += bp
        t += 0.25
        if ns(t) >= n:
            break
    return norm(out)


def reverse_cymbal(dur: float, rng: np.random.Generator) -> np.ndarray:
    c = crash(dur + 0.8, rng, tau=0.9)
    r = c[::-1][-ns(dur):]
    t = tvec(len(r))
    r = r * rise(t, 0.3)[:, None]
    return edge_fade(norm(r), 0.005, 0.005)


def suck_back(dur: float, rng: np.random.Generator, ir: np.ndarray) -> np.ndarray:
    """Reverse reverb swell + rising sub sweep, peaking at the end."""
    burst = crack(0.08, 300.0, 6000.0, 0.02, rng)
    wet = np.stack([signal.oaconvolve(burst[:, c], ir[:, c]) for c in range(2)], axis=1)
    rev = wet[::-1][-ns(dur):]
    n = len(rev)
    t = tvec(n)
    u = t / dur
    sweep = sine(40.0 * (3.0 ** u), n) * u ** 3
    y = norm(rev) * 0.8 + pan(sweep, 0.0) * 0.5
    y *= (u ** 2)[:, None]
    return edge_fade(norm(y), 0.02, 0.005)


def sfx_riser(dur: float, rng: np.random.Generator) -> np.ndarray:
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    nz = norm(tv_filter(rng.standard_normal((n, 2)), "hp", 1500.0 * (6.0 ** u), q=0.9, block=64))
    f = midi_hz(50) * 4.0 ** u
    ton = norm(tv_filter(saw_blep(f, n), "lp", 900.0 * (2.5 ** u), q=1.2))
    rate = 4.0 + 14.0 * u ** 2
    tr = 1.0 - 0.5 * u * (0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(rate) / SR))
    y = (nz * 0.6 + pan(ton, 0.0) * 0.4) * ((u ** 2.5) * tr)[:, None]
    return edge_fade(norm(y), 0.05, 0.005)


def flash(rng: np.random.Generator) -> np.ndarray:
    n = ns(FLASH_LEN)
    t = tvec(n)
    nz = filt(rng.standard_normal((n, 2)), "high", 2500.0)
    zap = sine(3200.0 * (0.55 ** (t / FLASH_LEN)), n)
    y = (norm(nz) * 0.7 + pan(zap, 0.0) * 0.4) * env_hit(n, 0.012)[:, None]
    return edge_fade(norm(y), 0.005, 0.01)


# =============================================================================
# timeline (all times from the cue sheet)
# =============================================================================
class Timeline:
    def __init__(self, cues: dict) -> None:
        self.total = float(cues["total"])
        self.n = ns(self.total)
        sec = {s["name"]: s for s in cues["sections"]}
        self.sfx = cues["sfx"]

        def span(name: str) -> tuple[float, float]:
            return float(sec[name]["start"]), float(sec[name]["end"])

        self.cold = span("cold_open")
        self.drop = span("drop")
        self.groove = span("act2_groove")
        self.lunar = span("lunar_transition")
        self.descent = span("descent_tension")
        self.flash = span("flash_silence")
        self.swell = span("swell_outro")
        self.bpm = float(sec["act2_groove"].get("bpm", 120))

        # cold open
        self.suck_end = self.cold[1] - GAP_BEFORE_DROP
        self.suck_start = self.suck_end - SUCK_LEN
        hb = self.first("heartbeat_start")
        self.heart1 = hb["t"] if hb else self.cold[0] + 0.3
        # drop
        d0, d1 = self.drop
        m = self.first("impact_metal", d0, d1)
        self.drop_metal = m["t"] if m else d0 + 2.6
        wo = self.first("whoosh_out", d0, d1)
        self.drop_whoosh_out = (wo["t"], wo.get("len", 0.4)) if wo else (d1 - 1.8, 0.4)
        # groove: risers into each whoosh_in end; hits = those + impact_small inside
        g0, g1 = self.groove
        self.groove_riser_targets = sorted(e["t"] + e.get("len", 0.3) for e in self.all("whoosh_in", g0, g1))
        smalls = [e["t"] for e in self.all("impact_small", g0 + 0.02, g1)]
        hits = sec["act2_groove"].get("hits") or (self.groove_riser_targets + smalls)
        self.groove_hits = sorted({round(float(h), 4) for h in hits})
        # lunar
        l0, l1 = self.lunar
        self.pings = [l0, l0 + (l1 - l0) / 2.0]
        # descent
        e0, e1 = self.descent
        self.heart2 = e0 + HEART2_OFFSET
        gl = self.first("glitch_burst", e0, e1)
        c0 = gl["t"] if gl else e0 + 3.0
        self.chop = (c0, c0 + CHOP_LEN)
        rp = self.first("riser_peak", e0, self.flash[0])
        self.riser_peak = rp["t"] if rp else e1
        self.shepard = (min(e0 + SHEPARD_OFFSET, self.riser_peak - 2.0), self.riser_peak)
        self.cluster = (self.riser_peak, self.flash[0])
        # flash
        fh = self.first("flash_hit", self.flash[0] - 0.5, self.flash[1])
        self.flash_t = fh["t"] if fh else self.flash[0]
        # swell
        s0, s1 = self.swell
        iw = self.first("impact_warm", s0, s1)
        self.final_hit = iw["t"] if iw else s0 + 12.4
        self.timp_target = s0 + TIMP_TARGET_OFFSET
        self.fade_end = float(sec["swell_outro"].get("fade_end", self.total - FADE_LEAD))

    def all(self, typ: str, lo: float = -1e9, hi: float = 1e9) -> list[dict]:
        return [e for e in self.sfx if e["type"] == typ and lo <= e["t"] < hi]

    def first(self, typ: str, lo: float = -1e9, hi: float = 1e9) -> dict | None:
        ev = self.all(typ, lo, hi)
        return ev[0] if ev else None

    def times(self) -> np.ndarray:
        return tvec(self.n)


# =============================================================================
# music
# =============================================================================
def music_cold_open(M: Bus, T: Timeline, rng: np.random.Generator) -> None:
    c0 = T.cold[0]
    cut = T.suck_end
    n = ns(cut - c0)
    t = tvec(n)
    dur = cut - c0
    # D1/D2 drone with a slow filter LFO that opens toward the drop
    dr = supersaw(midi_hz(26), n, rng, 5, 9.0, 0.5) + 0.8 * supersaw(midi_hz(38), n, rng, 5, 12.0, 0.95)
    fc = 110.0 + 330.0 * (0.5 - 0.5 * np.cos(2 * np.pi * t / 8.0)) * (0.5 + 0.5 * t / dur)
    dr = sat(norm(tv_filter(dr, "lp", fc, q=1.6)) * 0.9, 1.5)
    dr *= (rise(t, 2.5) * fall(t, dur - 0.02, dur))[:, None]
    M.add(edge_fade(dr), c0, gain=0.30, long=0.25)
    # sub swell (D1 + D2), cut with the suck-back
    sw0 = max(c0, cut - SUB_SWELL_LEN)
    m = ns(cut - sw0)
    ts = tvec(m)
    u = ts / (cut - sw0)
    sub = sat((sine(midi_hz(26), m) + 0.3 * sine(midi_hz(38), m)) * u ** 2 * 1.2, 1.4)
    M.add(edge_fade(sub, 0.005, 0.02), sw0, gain=0.38)
    # riser: air noise above the dialogue band + low tonal glide
    r0 = max(c0, cut - COLD_RISER_LEN)
    rz = riser(cut - r0, rng, midi_hz(38), midi_hz(62), 4000.0, 11000.0, (300.0, 900.0),
               noise_kind="hp")
    M.add(rz, r0, gain=0.32, long=0.15)


def music_drop(M: Bus, T: Timeline, rng: np.random.Generator) -> None:
    d0, d1 = T.drop
    hit2 = T.drop_metal
    wo_t, wo_len = T.drop_whoosh_out
    M.add(big_drum(2.5, 72.0, 34.0, rng, tau=0.6), d0, gain=0.9, hall=0.3)
    # distorted low brass chord D2 A2 D3 F3, lowpass opening; restrike at the title punch
    b1 = brass([38, 45, 50, 53], hit2 - d0 - 0.05, rng, 250.0, 2600.0, 0.9, 800.0, decay_tau=4.0, release=0.05)
    M.add(b1, d0, gain=0.7, hall=0.35, long=0.15)
    b2 = brass([38, 45, 50, 53, 57], wo_t + wo_len - hit2, rng, 400.0, 4200.0, 0.35, 900.0,
               decay_tau=1.8, release=0.3)
    M.add(b2, hit2, gain=0.62, hall=0.35, long=0.2)
    M.add(big_drum(1.6, 85.0, 40.0, rng, tau=0.35), hit2, gain=0.6, hall=0.3)
    # rumble bed: filtered brown noise under the whole section
    n = ns(d1 - d0)
    t = tvec(n)
    br = signal.lfilter([1.0], [1.0, -0.997], rng.standard_normal((n, 2)), axis=0)
    br = norm(filt(filt(br, "low", 110.0, 4), "high", 25.0))
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.23 * t)
    br *= (lfo * rise(t, 0.005) * fall(t, (d1 - d0) - 0.3, d1 - d0))[:, None]
    M.add(edge_fade(br), d0, gain=0.36)
    # muted 8th-note pulse building into the whoosh-out
    beat = 60.0 / T.bpm
    p0 = wo_t - 2.0
    k = 0
    while p0 + k * beat / 2 < wo_t - 1e-6:
        tp = p0 + k * beat / 2
        nn = ns(0.22)
        x = sine(midi_hz(38), nn) + 0.5 * filt(saw_blep(midi_hz(38), nn), "low", 400.0)
        x = edge_fade(x * env_hit(nn, 0.09), 0.005, 0.01)
        M.add(x, tp, gain=0.10 + 0.12 * k / 8)
        k += 1
    # reverse swell from end of whoosh-out into the groove downbeat
    rs0 = wo_t + wo_len
    m = ns(d1 - rs0)
    tm = tvec(m)
    u = tm / (d1 - rs0)
    sw = np.zeros((m, 2))
    for note in (50, 57, 62, 65):
        sw += supersaw(midi_hz(note), m, rng, 5, 16.0, 0.95)
    sw = tv_filter(sw, "lp", 300.0 * 10.0 ** u, q=0.9)
    sw = norm(sw) * (u ** 3)[:, None]
    M.add(edge_fade(sw, 0.05, 0.005), rs0, gain=0.32, long=0.1)


def music_groove(M: Bus, T: Timeline, rng: np.random.Generator) -> None:
    g0, g1 = T.groove
    beat = 60.0 / T.bpm
    s16 = beat / 4.0
    G = Bus(g0, g1 + 0.05)
    P = Bus(g0, g1 + 0.05)
    hits = [h for h in T.groove_hits if g0 < h < g1]
    marks = hits[:2]

    def stage(tt: float) -> int:
        return sum(tt >= mk - 1e-6 for mk in marks)

    n_beats = int(round((g1 - g0) / beat))
    kicks: list[float] = []
    for b in range(n_beats):
        tb = g0 + b * beat
        bar_i, beat_i = divmod(b, 4)
        st = stage(tb)
        if beat_i in (0, 2) or st >= 2:
            G.add(kick(rng), tb, gain=0.55 if beat_i in (0, 2) else 0.42)
            kicks.append(tb)
        if beat_i in (0, 2):
            G.add(tom(rng, 150.0 if beat_i == 0 else 118.0), tb, gain=0.32,
                  p=-0.3 if beat_i == 0 else 0.3, hall=0.15)
        if beat_i == 0 and bar_i % 2 == 0:
            G.add(big_drum(1.6, 75.0, 38.0, rng, tau=0.4), tb, gain=0.62, hall=0.3)
        if st >= 1 and beat_i == 3:
            G.add(tom(rng, 135.0), tb + beat / 2, gain=0.24, p=0.45, hall=0.15)
        sub = 4 if st >= 2 else 2
        for k in range(sub):
            th = tb + k * beat / sub
            off = (k % 2 == 1) if sub == 2 else (k == 2)
            G.add(hat(rng, open_=(st >= 1 and off and sub == 2)), th,
                  gain=0.09 if off else 0.05, p=0.25)
    # tom fills (16ths) into each riser target
    for tg in T.groove_riser_targets:
        for k in range(8):
            G.add(tom(rng, 190.0 - 10.0 * k), tg - 2 * beat + k * s16, gain=0.12 + 0.03 * k,
                  p=-0.5 + k / 7.0, hall=0.15)

    # 16th-note bass ostinato: D-D-D-F / D-D-C-A, phase-continuous, per-note filter env
    n = ns(g1 - g0)
    t = tvec(n)
    pattern = np.array([38, 38, 38, 41, 38, 38, 48, 45])
    idx = np.floor(t / s16 + 1e-9).astype(int)
    tn = t - idx * s16
    f = midi_hz(pattern[idx % 8])
    x = 0.5 * (saw_blep(f * 2 ** (7 / 1200), n) + saw_blep(f * 2 ** (-7 / 1200), n, 0.37))
    base = 380.0 + 700.0 * (t / (g1 - g0)) ** 1.5
    x = tv_filter(x, "lp", base * (1.0 + 3.0 * np.exp(-tn / 0.035)), q=2.0, block=32)
    gate = rise(tn, 0.005) * np.clip((s16 - tn) / 0.005, 0.0, 1.0)
    accent = np.where(idx % 4 == 0, 1.0, 0.8)
    amp = gate * accent * (0.35 + 0.65 * np.exp(-np.maximum(tn - 0.005, 0) / 0.06))
    subo = sine(f / 2.0, n) * gate * 0.8
    bass = sat(norm(x) * amp * 1.3 + subo, 1.8)
    G.add(edge_fade(norm(bass)), g0, gain=0.34)

    # pad i-VI-III-VII, 2 bars per chord, pumped against the kick
    chords = [[50, 57, 62, 65, 69], [46, 53, 58, 62, 65], [53, 57, 60, 65, 69], [48, 55, 60, 64, 67]]
    clen = 8 * beat
    k = 0
    tc = g0
    while tc < g1 - 0.01:
        st = stage(tc)
        dur = min(clen, g1 - tc)
        ch = pad_chord(chords[k % 4], dur, 0.12, 0.35, (1700.0, 2600.0, 3600.0)[min(st, 2)], rng)
        P.add(ch, tc, gain=0.22 + 0.04 * st, hall=0.3)
        k += 1
        tc += clen
    pump = np.ones(P.n)
    tp = P.times()
    for tk in kicks:
        i0 = max(0, ns(tk - 0.005) - P.i0)
        i1 = min(P.n, ns(tk + 1.0) - P.i0)
        tt = tp[i0:i1] - (tk - 0.005)
        shape = rise(tt, 0.005) * dexp(tt - 0.005, 0.16)
        pump[i0:i1] = np.minimum(pump[i0:i1], 1.0 - 0.6 * shape)
    P.apply(pump)
    P.merge_into(G)

    # risers into the hits that have whoosh-ins, and into the 40.0 cut
    for tg in T.groove_riser_targets + [g1]:
        r = riser(GROOVE_RISER_LEN, rng, midi_hz(62), midi_hz(74), 400.0, 7000.0, (800.0, 4000.0))
        G.add(r, tg - GROOVE_RISER_LEN, gain=0.30, hall=0.2)
    # impacts
    for h in hits:
        G.add(big_drum(2.0, 70.0, 34.0, rng, tau=0.5), h, gain=0.85, hall=0.35)
        G.add(brass([38, 45, 50, 53, 57], 1.4, rng, 400.0, 3500.0, 0.08, 900.0, decay_tau=0.5, release=0.4),
              h, gain=0.42, hall=0.35, long=0.15)
        G.add(crash(2.5, rng), h, gain=0.16, hall=0.25)
    # groove stops dead at the section end: dry and sends gated, reverb tail remains
    G.apply(curve(G.times(), [(g0, 1.0), (g1 - 0.005, 1.0), (g1, 0.0), (g1 + 1.0, 0.0)]))
    G.merge_into(M)


def music_lunar_descent(M: Bus, T: Timeline, rng: np.random.Generator) -> None:
    l0, l1 = T.lunar
    e0, e1 = T.descent
    rp = T.riser_peak
    beat = 60.0 / T.bpm
    # eerie high shimmer pad with slow tremolo, wide
    dur = (l1 - l0) + 0.6
    n = ns(dur)
    t = tvec(n)
    sh = np.zeros((n, 2))
    for i, note in enumerate((74, 81, 86, 88)):
        fq = midi_hz(note)
        for ch, cents in ((0, -4.0), (1, 4.0)):
            tone = sine(fq * 2 ** (cents / 1200), n, rng.uniform()) + 0.2 * sine(2 * fq, n, rng.uniform())
            trem = 1.0 - 0.5 * (0.5 + 0.5 * np.sin(2 * np.pi * (0.9 + 0.25 * i + 0.07 * ch) * t + rng.uniform(0, 6.3)))
            sh[:, ch] += tone * trem
    sh = norm(sh) * (rise(t, 0.35) * fall(t, (l1 - l0) - 1.0, dur))[:, None]
    M.add(edge_fade(sh), l0, gain=0.16, long=0.6)
    # sonar pings
    for tpg in T.pings:
        nn = ns(0.9)
        tt = tvec(nn)
        pg = sine(880.0 * (1.0 - 0.008 * tt), nn) * env_hit(nn, 0.22)
        pg = feedback_delay(pan(edge_fade(pg, 0.005, 0.05), -0.2), 0.375, 0.5, 4)
        M.add(pg, tpg, gain=0.20, long=0.3)

    # descent bus: sub drone (from lunar start), muted pulse, dark pad, Shepard; all end at riser_peak
    D = Bus(l0, rp + 0.05)
    n = ns(rp - l0)
    t = tvec(n)
    drone = sat((sine(midi_hz(26), n) + 0.25 * sine(midi_hz(38), n)) * (0.85 + 0.15 * np.sin(2 * np.pi * 0.17 * t)), 1.3)
    D.add(edge_fade(drone * rise(t, 0.6), 0.005, 0.02), l0, gain=0.18)
    # muted quarter-note pulse (8ths for the last 4 s)
    tq = e0
    while tq < rp - 1e-6:
        nn = ns(0.3)
        x = sine(midi_hz(38), nn) + 0.4 * filt(saw_blep(midi_hz(38), nn), "low", 280.0)
        x = edge_fade(x * env_hit(nn, 0.12), 0.005, 0.02)
        D.add(x, tq, gain=0.14)
        tq += beat / 2 if tq >= rp - 4.0 else beat
    # dark Dm pad
    pd = rp - e0
    pad = pad_chord([38, 50, 53, 57], pd, 1.5, 0.02, 520.0, rng, voices=5, detune=10.0, vib=3.0)
    nn = len(pad)
    pad = tv_filter(pad, "lp", 450.0 + 350.0 * tvec(nn) / pd, q=0.9)
    D.add(pad, e0, gain=0.3)
    # Shepard-Risset rising riser
    s0, s1 = T.shepard
    nn = ns(s1 - s0)
    tt = tvec(nn)
    u = tt / (s1 - s0)
    base, ncomp, center, sig = 27.5, 7, 170.0, 0.85
    cpos = np.log2(center / base)
    shp = np.zeros((nn, 2))
    for kk in range(ncomp):
        pos = np.mod(kk + 0.25 * tt, ncomp)
        w = np.exp(-0.5 * ((pos - cpos) / sig) ** 2)
        fq = base * 2.0 ** pos
        for ch, det in ((0, 1.0), (1, 1.004)):
            shp[:, ch] += w * (sine(fq * det, nn, rng.uniform()) + 0.3 * sine(2 * fq * det, nn, rng.uniform()))
    rate = 2.0 + 10.0 * u ** 2
    trem = 1.0 - 0.45 * u * (0.5 + 0.5 * np.cos(2 * np.pi * np.cumsum(rate) / SR))
    air = norm(filt(rng.standard_normal((nn, 2)), "high", 6000.0, 4)) * 0.15 * (u ** 3)[:, None]
    shp = norm(shp) * ((0.15 + 0.85 * u ** 1.5) * trem)[:, None] + air
    D.add(edge_fade(shp, 0.3, 0.005), s0, gain=0.42, hall=0.2)
    # 1202 alarm: duck and chop in 1/16 pulses
    td = D.times()
    c0, c1 = T.chop
    s16 = beat / 4.0
    inside = (td >= c0) & (td < c1)
    open_ = ((td - c0) % s16) < 0.55 * s16
    g = np.where(inside & ~open_, 0.0, 1.0)
    g = uniform_filter1d(g, ns(0.005))
    duck = curve(td, [(l0, 1.0), (c0 - 0.03, 1.0), (c0, 0.5), (c1, 0.5), (c1 + 0.1, 1.0), (rp + 1, 1.0)])
    cut = curve(td, [(l0, 1.0), (rp - 0.005, 1.0), (rp, 0.0), (rp + 1, 0.0)])
    D.apply(g * duck * cut)
    D.merge_into(M)

    # sustained high cluster from the riser peak to the flash, nothing else
    k0, k1 = T.cluster
    nn = ns(k1 - k0)
    tt = tvec(nn)
    cl = np.zeros((nn, 2))
    for note in (74, 76, 77, 79, 81):
        fq = midi_hz(note) * 2 ** (3 / 1200 * np.sin(2 * np.pi * 0.3 * tt + rng.uniform(0, 6.3)))
        for ch, cents in ((0, -4.0), (1, 4.0)):
            cl[:, ch] += sine(fq * 2 ** (cents / 1200), nn, rng.uniform()) + 0.12 * sine(2 * fq, nn, rng.uniform())
    cl = norm(cl) * ((0.8 + 0.2 * tt / (k1 - k0)) * rise(tt, 0.08))[:, None]
    M.add(edge_fade(cl, 0.005, 0.005), k0, gain=0.38, long=0.3)


SWELL_PAD = {"Bb": [46, 53, 58, 60, 62, 65], "F": [53, 57, 60, 65, 67, 69],
             "C": [48, 55, 60, 62, 64, 67], "D": [50, 57, 62, 64, 66, 69]}
SWELL_ROOT = {"Bb": 34, "F": 29, "C": 36, "D": 38}


def music_swell(M: Bus, T: Timeline, rng: np.random.Generator) -> None:
    s0, _ = T.swell
    hit = T.final_hit
    fe = T.fade_end
    # chord plan: Bb-F-C-D at CHORD_LEN, then Bb-C split up to the final hit, D holds after it
    plan: list[tuple[str, float, float]] = []
    tc = s0
    for name in ("Bb", "F", "C", "D"):
        if tc + CHORD_LEN <= hit + 1e-6:
            plan.append((name, tc, tc + CHORD_LEN))
            tc += CHORD_LEN
    if hit - tc > 1.0:
        mid = tc + (hit - tc) / 2.0
        plan += [("Bb", tc, mid), ("C", mid, hit)]
    elif hit > tc:
        plan.append(("C", tc, hit))
    plan.append(("D", hit, fe))
    for i, (name, a, b) in enumerate(plan):
        first = i == 0
        last = i == len(plan) - 1
        att = 1.5 if first else 0.3
        if last:
            hold, rel = (b - 4.0) - a, 4.0
        else:
            hold, rel = b - a, 0.5
        pd = pad_chord(SWELL_PAD[name], hold, att, rel, 1200.0, rng, voices=7, detune=15.0, vib=5.0)
        M.add(pd, a, gain=0.30, long=0.35)
        air = pad_chord([m + 12 for m in SWELL_PAD[name][2:]], hold, att * 2, rel, 12000.0, rng, voices=5)
        M.add(filt(air, "high", 5000.0, 4), a, gain=0.10, long=0.3)
        r = SWELL_ROOT[name]
        n = ns(hold + rel)
        st = supersaw(midi_hz(r), n, rng, 5, 8.0, 0.5, 5.5, 6.0) + supersaw(midi_hz(r + 12), n, rng, 5, 8.0, 0.8, 5.2, 6.0)
        st = filt(st, "low", 700.0, 4) * env_ahr(n, 1.5 if first else 0.5, hold, rel)[:, None]
        M.add(edge_fade(norm(st)), a, gain=0.26, long=0.25)
    # timpani roll into the target, crescendo, final stroke on the target
    roll0 = T.timp_target - TIMP_ROLL_LEN
    tr = roll0
    while tr < T.timp_target - 0.04:
        u = (tr - roll0) / TIMP_ROLL_LEN
        M.add(timp_stroke(midi_hz(38), 0.12 + 0.6 * u ** 1.6, rng), tr + rng.uniform(-0.004, 0.004),
              gain=0.2, p=rng.uniform(-0.3, 0.3), hall=0.3)
        tr += 0.09 - 0.035 * u
    M.add(timp_stroke(midi_hz(38), 1.0, rng), T.timp_target, gain=0.32, hall=0.35)
    # low-string 8ths building into the final hit (from the start of the last Bb-C push)
    push0 = plan[-3][1] if len(plan) >= 3 else hit - 2.0
    beat = 60.0 / T.bpm
    n8 = int(np.floor((hit - push0) / (beat / 2) + 1e-6))
    for k in range(n8, 0, -1):            # grid counted back from the hit so the 8ths land into it
        tp = hit - k * beat / 2
        u = (tp - push0) / max(hit - push0, 1e-6)
        nn = ns(0.24)
        x = supersaw(midi_hz(38), nn, rng, 3, 8.0, 0.4) + supersaw(midi_hz(50), nn, rng, 3, 8.0, 0.6)
        x = filt(x, "low", 600.0 + 600.0 * u) * env_ahr(nn, 0.01, 0.18, 0.05)[:, None]
        M.add(edge_fade(norm(x)), tp, gain=0.10 + 0.14 * u, long=0.15)
    # final title hit
    M.add(big_drum(3.5, 65.0, 32.0, rng, tau=0.8), hit, gain=0.85, long=0.4)
    M.add(timp_stroke(midi_hz(38), 1.0, rng, dur=3.5), hit, gain=0.5, long=0.3)
    M.add(brass([38, 45, 50, 54], 5.0, rng, 300.0, 1600.0, 0.5, 700.0, decay_tau=2.5, release=1.0),
          hit, gain=0.36, long=0.4)


# =============================================================================
# SFX
# =============================================================================
def build_sfx(S: Bus, T: Timeline, rng: np.random.Generator, ir_hall: np.ndarray) -> None:
    # heartbeat 1: cold open, accelerating, stops before the suck-back
    for tb in heartbeat_times(T.heart1, T.suck_start - 0.1, *HEART1_BPM, T.cold[1] - HEART1_RAMP_LEAD):
        u = (tb - T.heart1) / (T.suck_start - T.heart1)
        period = 60.0 / (HEART1_BPM[0] + (HEART1_BPM[1] - HEART1_BPM[0]) * min(u, 1.0))
        g = 0.45 + 0.3 * u
        S.add(heart_thump(rng), tb, gain=g)
        S.add(heart_thump(rng), tb + min(0.3 * period, 0.2), gain=g * 0.7)
    # heartbeat 2: descent
    e0, e1 = T.descent
    for tb in heartbeat_times(T.heart2, e1 - 0.05, *HEART2_BPM, e1):
        u = (tb - T.heart2) / (e1 - T.heart2)
        period = 60.0 / (HEART2_BPM[0] + (HEART2_BPM[1] - HEART2_BPM[0]) * u)
        g = 0.4 + 0.3 * u
        S.add(heart_thump(rng), tb, gain=g)
        S.add(heart_thump(rng), tb + min(0.3 * period, 0.2), gain=g * 0.7)
    # clock ticks, 8ths at the groove tempo, across the descent section
    step = 60.0 / T.bpm / 2.0
    k = 0
    while e0 + k * step < e1 - 1e-6:
        S.add(tick(rng, tock=bool(k % 2)), e0 + k * step, gain=0.13, p=0.15 if k % 2 else -0.15)
        k += 1
    # suck-back into the drop
    S.add(suck_back(SUCK_LEN, rng, ir_hall), T.suck_start, gain=0.55)

    for ev in T.sfx:
        t = float(ev["t"])
        ln = float(ev.get("len", 0.0))
        typ = ev["type"]
        if typ == "low_whoosh":
            S.add(whoosh(ln, "pass", rng, 120.0, 900.0, -0.7, 0.7), t, gain=0.4, hall=0.2)
        elif typ == "impact_big":
            S.add(sub_boom(2.5, 60.0, 28.0, 0.35, 0.9), t, gain=1.0)
            S.add(click_layer(rng), t, gain=0.35)
            S.add(crack(0.5, 600.0, 6000.0, 0.05, rng), t, gain=0.45, hall=0.45)
            S.add(sub_boom(0.6, 130.0, 55.0, 0.04, 0.15, 2.5), t, gain=0.45)
            debris = filt(rng.standard_normal((ns(2.0), 2)), "low", 500.0)
            S.add(edge_fade(norm(debris * env_hit(ns(2.0), 0.5)[:, None]), 0.005, 0.3), t, gain=0.18, long=0.4)
        elif typ == "impact_metal":
            S.add(sub_boom(1.4, 70.0, 34.0, 0.2, 0.45), t, gain=0.8)
            S.add(click_layer(rng, 3000.0), t, gain=0.4)
            S.add(crack(0.3, 2000.0, 9000.0, 0.03, rng), t, gain=0.45, hall=0.4)
            S.add(metal_ring(2.6, 380.0, rng), t, gain=0.26, hall=0.5)
        elif typ == "impact_small":
            S.add(sub_boom(1.0, 55.0, 32.0, 0.15, 0.3), t, gain=0.62)
            S.add(click_layer(rng), t, gain=0.25)
            S.add(crack(0.3, 1000.0, 6000.0, 0.03, rng), t, gain=0.3, hall=0.3)
        elif typ == "impact_warm":
            S.add(sub_boom(3.5, 50.0, 30.0, 0.4, 1.2, 1.5), t, gain=0.95)
            S.add(filt(click_layer(rng, 800.0), "low", 3000.0), t, gain=0.25)
            body = filt(rng.standard_normal((ns(1.2), 2)), "low", 1200.0) * env_hit(ns(1.2), 0.15)[:, None]
            S.add(edge_fade(norm(body), 0.005, 0.2), t, gain=0.3, long=0.5)
            nn = ns(4.0)
            tone = (sine(midi_hz(38), nn) + 0.5 * sine(midi_hz(45), nn)) * env_hit(nn, 1.2)
            S.add(edge_fade(norm(tone), 0.005, 0.5), t, gain=0.22, long=0.5)
        elif typ == "whoosh_in":
            S.add(whoosh(ln, "in", rng, 400.0, 7000.0, -0.5, 0.3), t, gain=0.42, hall=0.15)
        elif typ == "whoosh_out":
            S.add(whoosh(ln, "out", rng, 300.0, 7000.0, 0.3, -0.6), t, gain=0.42, hall=0.25)
        elif typ == "data_beep_seq":
            k = 0
            while k * 0.25 < ln - 1e-6:
                S.add(blip(float(rng.choice([1760.0, 2093.0, 2637.0, 3136.0]))), t + k * 0.25,
                      gain=0.05, p=rng.uniform(-0.6, 0.6))
                k += 1
        elif typ == "glitch_burst":
            S.add(glitch(ln, rng), t, gain=0.32)
        elif typ == "master_alarm":
            S.add(master_alarm(ln), t, gain=0.17, p=0.1, hall=0.1)
        elif typ == "riser_peak":
            S.add(sfx_riser(SFX_RISER_LEN, rng), t - SFX_RISER_LEN, gain=0.28, hall=0.25)
        elif typ == "reverse_cymbal_swell":
            S.add(reverse_cymbal(ln, rng), t, gain=0.22)
        # heartbeat_start handled above; flash_hit added after the silence gate


# =============================================================================
# loudness, limiting, mastering
# =============================================================================
KW_B1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
KW_A1 = [1.0, -1.69065929318241, 0.73248077421585]
KW_B2 = [1.0, -2.0, 1.0]
KW_A2 = [1.0, -1.99004745483398, 0.99007225036621]


def lufs_integrated(x: np.ndarray) -> float:
    """ITU-R BS.1770-4 gated integrated loudness (48 kHz coefficients)."""
    y = signal.lfilter(KW_B2, KW_A2, signal.lfilter(KW_B1, KW_A1, x, axis=0), axis=0)
    p = np.sum(y ** 2, axis=1)
    cs = np.concatenate([[0.0], np.cumsum(p)])
    blk, hop = ns(0.4), ns(0.1)
    st = np.arange(0, len(p) - blk + 1, hop)
    ms = (cs[st + blk] - cs[st]) / blk
    lk = -0.691 + 10 * np.log10(ms + 1e-20)
    g1 = ms[lk > -70.0]
    if g1.size == 0:
        return -np.inf
    rel = -0.691 + 10 * np.log10(np.mean(g1)) - 10.0
    g2 = ms[(lk > -70.0) & (lk > rel)]
    return float(-0.691 + 10 * np.log10(np.mean(g2)))


def true_peak_db(x: np.ndarray) -> float:
    m = 0.0
    for ch in range(x.shape[1]):
        up = signal.resample_poly(x[:, ch].astype(np.float32), 4, 1)
        m = max(m, float(np.max(np.abs(up))))
    return 20 * np.log10(max(m, 1e-12))


def limiter(x: np.ndarray, ceiling: float, look: float = 0.004, release: float = 0.15,
            blk: int = 16) -> tuple[np.ndarray, float]:
    """Look-ahead peak limiter (block-rate gain computer). Returns (y, max GR dB)."""
    peak = np.max(np.abs(x), axis=1)
    n = len(peak)
    nb = -(-n // blk)
    padded = np.zeros(nb * blk)
    padded[:n] = peak
    pb = padded.reshape(nb, blk).max(axis=1)
    req = np.minimum(1.0, ceiling / np.maximum(pb, 1e-12))
    k = max(1, int(round(look * SR / blk)))
    g = uniform_filter1d(minimum_filter1d(req, 2 * k + 1, mode="nearest"), 2 * k + 1, mode="nearest")
    a = 1.0 - np.exp(-blk / (release * SR))
    out = np.empty(nb)
    y = 1.0
    for i, gi in enumerate(g.tolist()):
        y = gi if gi < y else y + (gi - y) * a
        out[i] = y
    centers = (np.arange(nb) + 0.5) * blk
    gs = np.interp(np.arange(n), centers, out)
    return x * gs[:, None], float(-20 * np.log10(max(out.min(), 1e-12)))


def master(x: np.ndarray, target: float, label: str) -> tuple[np.ndarray, dict]:
    gain = 1.0
    ceil_db = TP_LIMIT_DBTP - 0.5
    y, gr, L, tp = x, 0.0, -np.inf, 0.0
    for _ in range(12):
        y, gr = limiter(x * gain, db(ceil_db))
        L = lufs_integrated(y)
        tp = true_peak_db(y)
        ok_l = abs(L - target) <= 0.1
        ok_tp = tp <= TP_LIMIT_DBTP - 0.1
        if ok_l and ok_tp:
            break
        if not ok_l:
            gain *= db(target - L)
        if not ok_tp:
            ceil_db -= tp - (TP_LIMIT_DBTP - 0.2)
    stats = {"label": label, "lufs": L, "true_peak_dbtp": tp, "limiter_max_gr_db": gr,
             "ceiling_dbfs": ceil_db, "gain_db": 20 * np.log10(gain)}
    return y, stats


def hp20(x: np.ndarray) -> np.ndarray:
    return filt(x, "high", 20.0, 4)


def dialogue_curve(T: Timeline) -> np.ndarray:
    """Mid-band gain: ducked under cold_open, descent+cluster, and swell_outro."""
    d = db(DIALOGUE_DUCK_DB)
    c1 = T.cold[1]
    e0 = T.descent[0]
    return curve(T.times(), [(0.0, d), (c1 - 0.2, d), (c1, 1.0), (e0 - 0.2, 1.0), (e0, d), (T.total, d)])


def silence_gate(T: Timeline, final_fade_start: float, near_silence: bool = True) -> np.ndarray:
    near = db(-45.0)
    f0, f1 = T.flash
    pts = [(0.0, 1.0), (f0 - 0.005, 1.0), (f0 - 0.5 / SR, 0.0), (f1, 0.0), (f1 + 0.005, 1.0), (T.total, 1.0)]
    if near_silence:
        pts += [(T.suck_end - 0.02, 1.0), (T.suck_end, near), (T.cold[1] - 0.005, near), (T.cold[1], 1.0)]
    return curve(T.times(), pts) * fall(T.times(), final_fade_start, T.fade_end)


def cold_open_gate(times: np.ndarray, T: Timeline) -> np.ndarray:
    """Cold-open bus: hard cut at the suck-back end, tail at -45 dB, fully gone by the drop."""
    return curve(times, [(0.0, 1.0), (T.suck_end - 0.02, 1.0), (T.suck_end, db(-45.0)),
                         (T.cold[1] - 0.06, db(-45.0)), (T.cold[1] - 0.001, 0.0), (T.cold[1] + 1.0, 0.0)])


# =============================================================================
# main
# =============================================================================
def write_wav(path: Path, x: np.ndarray) -> None:
    assert np.all(np.isfinite(x)), f"non-finite samples in {path.name}"
    wavfile.write(str(path), SR, x.astype(np.float32))


def main() -> None:
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cues", default=str(here.parent / "cues.json"))
    ap.add_argument("--out", default=str(here))
    args = ap.parse_args()
    t_start = time.time()
    cues = json.loads(Path(args.cues).read_text(encoding="utf-8"))
    T = Timeline(cues)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    ir_hall = make_ir(2.4, 3.2, 0.02, rng)
    ir_long = make_ir(5.0, 6.5, 0.04, rng, hf_ratio=0.35)

    # ---- music
    C = Bus(0.0, T.cold[1] + 1.0)           # cold open on its own bus so its tail never leaks into the drop
    music_cold_open(C, T, rng)
    M = Bus(0.0, T.total)
    music_drop(M, T, rng)
    music_groove(M, T, rng)
    music_lunar_descent(M, T, rng)
    music_swell(M, T, rng)
    duck = dialogue_curve(T)
    mus = hp20(mid_band_duck(M.render(ir_hall, ir_long), duck))
    # cold open: filtered first, then gated, so no filter ringing survives into the near-silence
    cold = hp20(mid_band_duck(C.render(ir_hall, ir_long), duck[:C.n]))
    mus[:C.n] += cold * cold_open_gate(C.times(), T)[:, None]
    mus *= silence_gate(T, T.fade_end - 4.0, near_silence=False)[:, None]
    mus, ms_stats = master(mus, MUSIC_TARGET_LUFS, "music")
    write_wav(out / "music.wav", mus)
    del M

    # ---- sfx
    S = Bus(0.0, T.total)
    build_sfx(S, T, rng, ir_hall)
    sfx = hp20(S.render(ir_hall, ir_long)) * silence_gate(T, T.fade_end - 2.5)[:, None]
    fl = flash(rng)
    i = ns(T.flash_t)
    sfx[i:i + len(fl)] += fl * 0.9
    sfx, sx_stats = master(sfx, SFX_TARGET_LUFS, "sfx")
    write_wav(out / "sfx.wav", sfx)

    for s in (ms_stats, sx_stats):
        print(f"{s['label']:5s}  {s['lufs']:6.2f} LUFS  TP {s['true_peak_dbtp']:6.2f} dBTP  "
              f"limiter max GR {s['limiter_max_gr_db']:.1f} dB  ceiling {s['ceiling_dbfs']:.2f} dBFS")
    print(f"wrote {out / 'music.wav'} and {out / 'sfx.wav'} "
          f"({T.n} samples, {T.total:.3f} s) in {time.time() - t_start:.1f} s")


if __name__ == "__main__":
    main()
