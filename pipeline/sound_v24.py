"""v24 sound arc (anticipation -> release -> pressure -> relief): a candidate audio master for MOONSHOT.

NEW file; reads the pipeline's stems and tables, writes only into OUT_DIR (default scratchpad\\v24) and
work\\audio_v24\\ (the master + its manifest, used by patch_v24's build path).

    py sound_v24.py [OUT_DIR] [--synth-dir DIR]

Method (bounded replacement, Codex all-out plan v24):
  1. BASELINE = the approved AAC stream of versions\\moonshot_v22.mp4 (= v21's; packet md5 pinned) decoded to 48 kHz
     float PCM.
  2. The v21 mix is rebuilt from the stems that made it (audio/dialog.f32, music_pd.f32, sonniss.f32, the v1 synth
     SFX stem split into families by sound_v24_synth.py) with stage_mix()'s arithmetic, and checked against
     audio/mix.f32 (v21).
  3. The CANDIDATE mix is the same arithmetic with the v24 changes (below). The adaptive duck depths are frozen at
     v21's values, so the dialogue/bed balance only changes where the bed changes.
  4. v21's loudnorm ran in dynamic mode (not linear), so its gain is a curve: g(t) is estimated per 10 ms from
     audio/mix_raw.wav -> audio/mix_norm.wav and applied to the CHANGE: master = baseline + w(t) * g(t) * (cand - v21)
     * (v21's peak scale). w(t) = 1 inside the unlocked windows (frames 0-779 and 888-1460), 0 elsewhere, with 20 ms
     linear ramps inside the windows (baseline and candidate are the same signal at the edges, so an equal-gain
     ramp is the right crossfade; equal power would bump +3 dB). Outside the windows master == baseline sample for
     sample. No normalisation afterwards.

v24 changes (all inside the windows; times are real seconds):
  countdown  - the v1 synth heartbeat (66 -> 110 bpm under the count) is removed;
             - a restrained PRESSURE layer (E1 sub + low brown-noise rumble, no pulse) rises from "Ignition sequence
               starts" (2.2) to 10.33 under the authentic count and is cut together with the existing suck-back, so
               10.35-10.6 stays near-silent and the ignition (10.6) lands on contrast.
  staging    - the quindar-like 4.7 kHz "comm tick" at 26.17 is removed (no fake Quindar);
             - a MECHANICAL RELEASE motif (latch click 27.94 -> heavy mechanical clunk 28.0, Sonniss) sits on the
               28.0 separation cut, in the gap between "Staging." (ends 27.0) and "And ignition." (28.34); it
               escapes the duck for 27.92-28.10 and is back under it before the line.
  alarm/descent
             - the v1 synth clock ticks (37.3-59.3), the synth master-alarm squares (40.5-42.9) and both synth glitch
               bursts are removed; the Sonniss data glitch at 42.9 (on Aldrin's "1202.") is removed;
             - the Sonniss computer alarm moves to the 40.30 picture glitch, -4 dB, and stops by 41.2 (it used to run
               under "Program alarm" and "It's a 1202" to 42.9);
             - the Egmont's general pause (42.4-43.4) keeps a low air bed (the 0:33 hold's space_air_v19b, not
               Sonniss) instead of synth alarm/glitch, so "1202." sits in space rather than a dropout;
             - the PRESSURE layer returns from 49.0 ("60 seconds") and grows to 55.05;
             - the heartbeat (45.3 -> ) and the synth riser stop at 55.05: "Contact light." (55.2) sits in a
               cleared bed, then the touchdown impact + Egmont tutti (56.2) is the payoff, and the heartbeat no
               longer runs under "Houston, Tranquility Base here" (relief); the music bed dips a further 4 dB
               under "Contact light." (54.95-56.2, back for the hit).
  level      - a peak limiter acts only inside the windows (ceiling -1.65 dBTP, 4x oversampled; max 0.38 dB): the
               approved stream sits at -1.47 dBTP (4x) and an AAC re-encode would otherwise land above -1.5.
Untouched: every voice line, the Dvorak/Egmont/Largo, the 0:33 Moon beat, the 1:02 transition, the credits.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np

WORK = (CRAFTWORK / "inbox/moonshot/work")
AUD = WORK / "audio"
SON = (CRAFTWORK / "sfx/sonniss-gdc2024")
V22 = (CRAFTWORK / "exports/moonshot/versions/moonshot_v22.mp4")
V22_AUDIO_MD5 = "b489934da50e9c2ee4acce2f94f712ae"
SCRATCH = Path(os.environ.get("MOONSHOT_SCRATCH", "scratch")) / "v24"
MASTER_DIR = WORK / "audio_v24"
SR = 48000
FPS = 24
SPF = SR // FPS                    # 2000 samples per picture frame
TOTAL = 87.5
N = int(TOTAL * SR)
WINDOWS_F = [(0, 780), (888, 1461)]     # unlocked picture frames [a, b): 0-32.5 s and 37.0-60.875 s
RAMP = int(0.020 * SR)

sys.path.insert(0, str(WORK))
import score_pd  # noqa: E402  (read-only: tables + load_stereo/place)


# ---------------------------------------------------------------- io
def decode(path: Path, extra: list[str] | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", str(path), *(extra or []), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def audio_md5(path: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-c", "copy", "-f", "md5", "-"],
                         capture_output=True, text=True)
    return out.stdout.strip().removeprefix("MD5=")


def f32(path: Path, ch: int) -> np.ndarray:
    x = np.fromfile(path, np.float32)
    return (x.reshape(-1, 2) if ch == 2 else x)[:N].astype(np.float64)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


# ---------------------------------------------------------------- tables read from build.py without running it
def dialog_spans() -> list[tuple[float, float]]:
    """(timeline_t, length) per DIALOG entry, from build.py's DIALOG literal (ast; the RST paths are skipped)."""
    tree = ast.parse((WORK / "build.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "DIALOG" for t in node.targets):
            out = []
            for el in node.value.elts:
                a, b, t = (ast.literal_eval(el.elts[i]) for i in (1, 2, 3))
                out.append((float(t), float(b) - float(a)))
            return out
    raise SystemExit("DIALOG not found in build.py")


# ---------------------------------------------------------------- synth SFX families (v1 stem, v8 timeline)
def synth_v8_families(synth_dir: Path) -> dict[str, np.ndarray]:
    """build.synth_sfx_v8() applied to each family: old 33.3-40.0 cut with a 20 ms crossfade, then the v11 declick
    gain (computed on the FULL stem exactly as build.py does, then applied to every family)."""
    fams = {}
    for p in sorted(synth_dir.glob("synth_*.f32")):
        fams[p.stem.removeprefix("synth_")] = np.fromfile(p, np.float32).reshape(-1, 2).astype(np.float64)
    a0, a1 = int(33.3 * SR), int(40.0 * SR)
    xf = int(0.02 * SR)
    ramp = np.linspace(0, 1, xf, dtype=np.float32).astype(np.float64)[:, None]

    def cut(full: np.ndarray) -> np.ndarray:
        head = full[:a0].copy()
        tail = full[a1:].copy()
        head[-xf:] = head[-xf:] * (1 - ramp) + tail[:xf] * ramp
        out = np.concatenate([head, tail[xf:]])
        res = np.zeros((N, 2))
        res[:min(N, len(out))] = out[:N]
        return res

    out = {k: cut(v) for k, v in fams.items()}
    full = sum(out.values())
    g = np.ones(N)
    k0 = int(40.25 * SR)
    jumps = k0 + 1 + np.flatnonzero(np.abs(np.diff(full[k0:int(40.35 * SR)].astype(np.float32), axis=0)).max(axis=1) > 0.02)
    if jumps.size:
        a_ = int(jumps[0])
        b_ = int(jumps[jumps <= a_ + int(0.02 * SR)][-1])
        fo, fi = int(0.005 * SR), int(0.012 * SR)
        g[a_ - fo:a_] *= np.linspace(1, 0, fo, dtype=np.float32)
        g[a_:b_] = 0.0
        g[b_:b_ + fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    return {k: v * g[:, None] for k, v in out.items()}


# ---------------------------------------------------------------- Sonniss bus (score_pd.stage_music's SFX loop)
def stage_sfx(table: list[tuple], fades: dict[int, float] | None = None) -> np.ndarray:
    """score_pd's Sonniss placement for `table`; `fades` maps a row index to a longer cosine fade-out (s)."""
    son = np.zeros((N, 2), np.float32)
    hop = int(0.05 * SR)
    for k, (rel, t, g, align, maxlen) in enumerate(table):
        x = score_pd.load_stereo(score_pd.SON / rel)[: int(maxlen * SR)]
        if align == "peak":
            blocks = np.sqrt(np.mean((x[: len(x) // hop * hop, 0] ** 2).reshape(-1, hop), axis=1))
            ref = int(blocks.argmax()) * hop
        else:
            env = np.abs(x).max(axis=1)
            ref = int(np.argmax(env > 0.3 * env.max()))
        x = x * np.float32(10 ** (g / 20))
        f = int(0.03 * SR)
        x[-f:] *= np.linspace(1, 0, f, dtype=np.float32)[:, None]
        if fades and k in fades:
            fl = int(fades[k] * SR)
            x[-fl:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fl))).astype(np.float32)[:, None]
        h3 = int(0.010 * SR)
        x[:h3] *= np.linspace(0, 1, h3, dtype=np.float32)[:, None]
        score_pd.place(son, x, int(t * SR) - ref)
    son[int(61.96 * SR):int(62.9 * SR)] = 0.0
    return son.astype(np.float64)


# ---------------------------------------------------------------- v24 synthesis: the pressure layer
def onepole_lp(x: np.ndarray, fc: np.ndarray | float) -> np.ndarray:
    """Time-varying one-pole low-pass (per-sample cutoff), vectorised in 10 ms blocks."""
    from scipy.signal import lfilter
    fc = np.broadcast_to(np.asarray(fc, dtype=np.float64), (len(x),))
    y = np.zeros_like(x)
    yprev = np.zeros((1,) + x.shape[1:])
    blk = 480
    for i in range(0, len(x), blk):
        a = 1.0 - np.exp(-2 * np.pi * fc[i] / SR)
        out, _ = lfilter([a], [1, -(1 - a)], x[i:i + blk], axis=0, zi=yprev * (1 - a))
        y[i:i + blk] = out
        yprev = out[-1:]
    return y


def pressure(t0: float, t1: float, t_cut: float, peak: float, seed: int) -> np.ndarray:
    """Restrained low pressure: E1 sine (41.2 Hz) + a quieter E2, and stereo brown-noise rumble whose low-pass opens
    90 -> 240 Hz; amplitude rises as u^2 (u = 0..1 over t0..t_cut) to `peak` (linear), 25 ms cosine cut at t_cut.
    No pulse, no tremolo: pressure, not a beat. Returns a full-length stereo bus."""
    rng = np.random.default_rng(seed)
    n = int((t1 - t0) * SR)
    tt = np.arange(n) / SR
    u = np.clip(tt / (t_cut - t0), 0, 1)
    sub = np.sin(2 * np.pi * 41.2 * tt) + 0.35 * np.sin(2 * np.pi * 82.4 * tt + 0.7)
    wn = rng.standard_normal((n, 2))
    brown = np.cumsum(wn, axis=0)
    brown -= np.linspace(brown[0], brown[-1], n)            # no drift
    from scipy.signal import butter, sosfiltfilt
    sos_hp = butter(2, 25.0, "highpass", fs=SR, output="sos")
    brown = sosfiltfilt(sos_hp, brown, axis=0)
    fc = 90.0 + 150.0 * u ** 1.5
    rum = onepole_lp(brown, fc)
    rum = onepole_lp(rum, fc)
    rum /= np.sqrt(np.mean(rum ** 2)) + 1e-12
    sub /= np.sqrt(np.mean(sub ** 2))
    x = 0.75 * sub[:, None] + 0.55 * rum
    x /= np.abs(x).max()
    env = u ** 1.6
    kc = int((t_cut - t0) * SR)
    fc_n = int(0.025 * SR)
    env[kc - fc_n:kc] *= 0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fc_n))
    env[kc:] = 0.0
    fi = int(0.05 * SR)
    env[:fi] *= np.linspace(0, 1, fi)
    bus = np.zeros((N, 2))
    i0 = int(t0 * SR)
    bus[i0:i0 + n] = x * (env * peak)[:, None]
    return bus


def gain_curve(points: list[tuple[float, float]]) -> np.ndarray:
    """Piecewise-linear gain (time s, linear gain) over the whole timeline; flat outside the points."""
    tt = np.arange(N) / SR
    xs, ys = zip(*points)
    return np.interp(tt, xs, ys)


# ---------------------------------------------------------------- stage_mix arithmetic (build.py v21 path)
def rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(np.square(x, dtype=np.float64))) + 1e-12))


def duck_depths(spans: list[tuple[float, float]], pre_bed: np.ndarray, dlg: np.ndarray) -> list[float]:
    out = []
    for t, ln in spans:
        i0, i1 = int(t * SR), min(int((t + ln) * SR), N)
        need = rms_db(pre_bed[i0:i1]) - rms_db(dlg[i0:i1]) + 12.0
        out.append(float(np.clip(need, 10.0, 22.0)))
    return out


def mix(music: np.ndarray, sfx: np.ndarray, dlg: np.ndarray, spans: list[tuple[float, float]],
        depths: list[float], unduck: list[tuple[float, float, float]],
        post: tuple[np.ndarray, tuple[float, float, float]] | None = None) -> np.ndarray:
    """build.stage_mix() from the adaptive duck to the room tone, with the per-line duck depths given. `post` =
    (stereo bus, (u0, u1, release)): a v24 bus that escapes the duck only for u0-u1 and then follows the duck
    (so the release motif is not a reason to unduck the rest of the SFX bus)."""
    target = np.zeros(N, np.float32)
    for (t, ln), depth in zip(spans, depths):
        i0, i1 = int(t * SR), min(int((t + ln) * SR), N)
        j0, j1 = max(0, i0 - int(0.20 * SR)), min(N, i1 + int(0.10 * SR))
        target[j0:j1] = np.maximum(target[j0:j1], depth)
    step = 48
    ctrl = target[::step]
    env_db = np.zeros_like(ctrl)
    lvl = 0.0
    k_att, k_rel = step / (0.06 * SR), step / (0.40 * SR)
    for i, c in enumerate(ctrl):
        lvl += (c - lvl) * (k_att if c > lvl else k_rel)
        env_db[i] = lvl
    env_db = np.repeat(env_db, step)[:N]
    gain = (10 ** (-env_db / 20)).astype(np.float32)
    sgain = gain
    tt_ = np.arange(N) / SR
    for u0, u1, rel in unduck:
        w_ = np.interp(tt_, [u0 - 0.02, u0, u1, u1 + rel], [0.0, 1.0, 1.0, 0.0]).astype(np.float32)
        w_ = 0.5 - 0.5 * np.cos(np.pi * w_)
        sgain = sgain + (1.0 - sgain) * w_
    bed = music.astype(np.float32) * gain[:, None] + sfx.astype(np.float32) * sgain[:, None]
    for d0, d1, ddb in [(10.6, 19.0, -1.5)]:                       # build.BED_DIP
        bed *= (10 ** (np.interp(tt_, [d0 - 0.10, d0 - 0.02, d1, d1 + 0.4], [0.0, ddb, ddb, 0.0]) / 20)).astype(np.float32)[:, None]
    if post is not None:
        x, (u0, u1, rel) = post
        w_ = np.interp(tt_, [u0 - 0.02, u0, u1, u1 + rel], [0.0, 1.0, 1.0, 0.0]).astype(np.float32)
        w_ = 0.5 - 0.5 * np.cos(np.pi * w_)
        bed = bed + x.astype(np.float32) * (gain + (1.0 - gain) * w_)[:, None]
    out = bed + dlg.astype(np.float32)[:, None] * 1.0
    rng = np.random.default_rng(3)
    i0, i1 = int(61.92 * SR), int(63.5 * SR)
    tone = rng.normal(0, 1, (i1 - i0, 2)).astype(np.float32)
    tone = np.cumsum(tone, axis=0)
    tone -= np.linspace(tone[0], tone[-1], len(tone))
    tone *= 10 ** (-52 / 20) / max(np.sqrt(np.mean(tone ** 2)), 1e-9)
    fo_ = int(0.4 * SR)
    tone[-fo_:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, fo_, dtype=np.float32)))[:, None]
    out[i0:i1] += tone
    return out


# ---------------------------------------------------------------- v21 loudnorm gain curve
def loudnorm_gain() -> np.ndarray:
    raw = decode(AUD / "mix_raw.wav").astype(np.float64)[:N]
    nrm = decode(AUD / "mix_norm.wav").astype(np.float64)[:N]
    blk = 480
    nb = N // blk
    r = raw[:nb * blk].reshape(nb, blk, 2)
    m = nrm[:nb * blk].reshape(nb, blk, 2)
    num = (r * m).sum(axis=(1, 2))
    den = (r * r).sum(axis=(1, 2))
    ok = den > 1e-7 * blk
    gb = np.where(ok, num / np.maximum(den, 1e-30), np.nan)
    idx = np.arange(nb)
    gb = np.interp(idx, idx[ok], gb[ok])
    gb = np.convolve(np.pad(gb, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    centers = (idx + 0.5) * blk
    g = np.interp(np.arange(N), centers, gb)
    res = nrm - g[:, None] * raw
    print(f"  loudnorm curve: median {np.median(g):.3f}, range {g.min():.3f}-{g.max():.3f}; "
          f"residual {rms_db(res) - rms_db(nrm):.1f} dB re the norm signal")
    return g


def window_weight(n: int) -> np.ndarray:
    w = np.zeros(n)
    for fa, fb in WINDOWS_F:
        a, b = fa * SPF, fb * SPF
        w[a:b] = 1.0
        if a > 0:
            w[a:a + RAMP] = np.linspace(0, 1, RAMP, endpoint=False) + 1.0 / RAMP
        w[b - RAMP:b] = np.linspace(1, 0, RAMP, endpoint=False)
    return np.clip(w, 0, 1)


# ---------------------------------------------------------------- v24 tables
LATCH = "BluezoneCorp - Industrial Lever Switch/Bluezone_BC0302_industrial_lever_switch_small_003.wav"
CLUNK = "BluezoneCorp - Steampunk Machines/Bluezone_BC0305_steampunk_machine_mechanical_texture_heavy_impact_011.wav"
QUINDARISH = "Bluezone_BC0303_futuristic_user_interface_high_tech_beep_038.wav"
DATA_GLITCH = "Bluezone_BC0303_futuristic_user_interface_data_glitch_003.wav"
COMP_ALARM = "Bluezone_BC0304_retrofuturistic_computer_alarm_005.wav"
PRESS_PEAK = (0.22, 0.17)       # pressure layer peak (linear, pre-mix scale): countdown, descent
ALARM_DB = -18.0                # the Sonniss computer alarm (v21: -14 dB at 40.5, ducked under "Program alarm")
MUSIC_DIP = (54.95, 55.10, 56.10, 56.20, -4.0)   # space for "Contact light." (55.2): music -4 dB more, back for the 56.2 hit
SPACE_AIR = str(WORK / "audio_assets" / "space_air_v19b.wav")   # the 0:33 hold's air bed (patch_v19b, not Sonniss): low, under the Egmont general pause (42.4-43.4) so "1202." sits in space, not a dropout
MOTIF_DB = (-18.0, -14.0)       # release motif: latch, clunk (they escape the duck, so they sit low)
TP_CEIL_DB = -1.65              # window-bounded limiter ceiling on the 4x-oversampled peak (AAC adds ~0.05-0.1 dB)


def window_limiter(master: np.ndarray, w: np.ndarray, ceil_db: float,
                   changed: np.ndarray | None = None) -> tuple[np.ndarray, float, float]:
    """Peak limiter on the master, applied ONLY where w == 1 (inside the windows, away from their ramps): the 4x
    oversampled peak per 1 ms block sets the needed gain, a +-3 ms min-filter + 3 ms average gives look-ahead and a
    smooth attack, a 60 ms one-pole release recovers. Returns (master, max gain reduction dB, seconds limited)."""
    from scipy.ndimage import minimum_filter1d, uniform_filter1d
    from scipy.signal import resample_poly
    ceil = 10 ** (ceil_db / 20)
    blk = 48
    nb = len(master) // blk + 1
    up = np.abs(resample_poly(master.astype(np.float64), 4, 1, axis=0)).max(axis=1)
    pk = np.zeros(nb * blk * 4)
    pk[:len(up)] = up
    pb = pk.reshape(nb, blk * 4).max(axis=1)
    req = np.minimum(1.0, ceil / np.maximum(pb, 1e-12))
    g = uniform_filter1d(minimum_filter1d(req, 7, mode="nearest"), 3, mode="nearest")
    a = 1.0 - np.exp(-blk / (0.060 * SR))
    out = np.empty(nb)
    y = 1.0
    for i, gi in enumerate(g.tolist()):
        y = gi if gi < y else y + (gi - y) * a
        out[i] = y
    gs = np.interp(np.arange(len(master)), (np.arange(nb) + 0.5) * blk, out)
    full = w >= 1.0
    ramp = (w > 0) & ~full
    if np.any(gs[ramp] < 1.0 - 1e-9):        # baseline content at a window edge (the change is zero there): left alone
        print(f"  (ramp samples over the ceiling, left as baseline: {int((gs[ramp] < 1.0 - 1e-9).sum())})")
    print(f"  (baseline regions over the ceiling outside the windows, left alone: {float((gs[w == 0] < 0.9999).sum() / SR):.3f} s)")
    gs = np.where(full, gs, 1.0)
    if changed is not None:                   # act only where v24 changed the signal (+-50 ms): approved content stays
        from scipy.ndimage import binary_dilation
        near = binary_dilation(changed[::blk], iterations=50)
        gs = np.where(np.repeat(near, blk)[:len(gs)], gs, 1.0)
        acted = np.flatnonzero(np.diff(np.r_[0, (gs < 0.9999).astype(int), 0]))
        print("  limiter acted at (s):", [(round(a / SR, 2), round(b / SR, 2)) for a, b in zip(acted[::2], acted[1::2])])
    return (master * gs[:, None]).astype(np.float32), float(-20 * np.log10(gs.min())), float((gs < 0.9999).sum() / SR)


def v24_sonniss() -> tuple[list[tuple], dict[int, float]]:
    rows: list[tuple] = []
    fades: dict[int, float] = {}
    for row in score_pd.SONNISS:
        name = Path(row[0]).name
        if name in (QUINDARISH, DATA_GLITCH):
            continue                                    # the comm tick (26.17) and the data glitch on "1202." (42.9)
        if name == COMP_ALARM:
            fades[len(rows)] = 0.35
            rows.append((row[0], 40.30, ALARM_DB, row[3], 0.90))   # on the 40.30 picture glitch, gone by 41.2 (was -14 dB at 40.5)
            continue
        rows.append(row)
    return rows, fades


def v24_motif() -> np.ndarray:
    """The mechanical-release motif bus: the latch lets go (27.94), the heavy mechanical clunk lands on the 28.0 cut."""
    return stage_sfx([(LATCH, 27.94, MOTIF_DB[0], "attack", 0.30), (CLUNK, 28.00, MOTIF_DB[1], "attack", 0.62)],
                     {0: 0.06, 1: 0.20})


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else SCRATCH
    synth_dir = Path(sys.argv[sys.argv.index("--synth-dir") + 1]) if "--synth-dir" in sys.argv else SCRATCH / "stems"
    out_dir.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)
    report: dict = {}

    # 1. baseline
    got = audio_md5(V22)
    if got != V22_AUDIO_MD5:
        raise SystemExit(f"baseline audio md5 {got} != pinned {V22_AUDIO_MD5}")
    base = decode(V22, ["-map", "0:a:0"])
    print(f"baseline: {V22.name} audio md5 {got} OK, {len(base)} samples")

    # 2. v21 rebuild
    spans = dialog_spans()
    dlg = f32(AUD / "dialog.f32", 1)
    music = f32(AUD / "music_pd.f32", 2)
    son = f32(AUD / "sonniss.f32", 2)
    son_re = stage_sfx(list(score_pd.SONNISS))
    print(f"  sonniss restage vs sonniss.f32: max |diff| {np.abs(son_re - son).max():.2e}")
    fams = synth_v8_families(synth_dir)
    synth = sum(fams.values())
    sfx_v21 = son + synth * 10 ** (-4.0 / 20)
    depths = duck_depths(spans, music + sfx_v21, dlg)
    mix_v21 = mix(music, sfx_v21, dlg, spans, depths, [(56.15, 56.45, 0.15)])
    scale = 0.7 / float(np.max(np.abs(mix_v21)))
    ref = f32(AUD / "mix.f32", 2)
    err = float(np.abs(mix_v21 * scale - ref).max())
    print(f"  v21 rebuild vs audio/mix.f32: max |diff| {err:.2e} (scale {scale:.6f})")
    report["v21_rebuild_max_abs_diff"] = err
    if err > 1e-5:
        raise SystemExit("the v21 mix could not be rebuilt; stop")

    # 3. candidate
    tl = np.arange(N) / SR
    keep = {k: np.ones(N) for k in fams}
    keep["heart"] = gain_curve([(0.0, 0.0), (10.55, 0.0), (10.6, 1.0), (54.90, 1.0), (55.05, 0.0)])
    keep["tick"] = np.zeros(N)
    keep["alarm"] = np.zeros(N)
    keep["glitch"] = np.zeros(N)
    keep["riser"] = gain_curve([(0.0, 1.0), (54.90, 1.0), (55.05, 0.0)])
    for k, g_ in keep.items():                      # the changes are bounded to the windows
        g_[(tl >= 32.5) & (tl < 37.0)] = 1.0
        g_[tl >= 60.875] = 1.0
    synth_c = sum(fams[k] * keep[k][:, None] for k in fams)
    rows, fades = v24_sonniss()
    son_c = stage_sfx(rows, fades) + stage_sfx([(SPACE_AIR, 41.95, -14.0, "attack", 1.75)], {0: 0.45})
    press = (pressure(2.2, 10.40, 10.33, PRESS_PEAK[0], 1969) + pressure(49.0, 55.12, 55.05, PRESS_PEAK[1], 1202))
    sfx_c = son_c + synth_c * 10 ** (-4.0 / 20) + press
    unduck_c = [(56.15, 56.45, 0.15)]
    md = MUSIC_DIP
    music_c = music * (10 ** (gain_curve([(0.0, 0.0), (md[0], 0.0), (md[1], md[4]), (md[2], md[4]), (md[3], 0.0)]) / 20))[:, None]
    mix_c = mix(music_c, sfx_c, dlg, spans, depths, unduck_c, (v24_motif(), (27.92, 28.10, 0.15)))
    depths_c = duck_depths(spans, music + sfx_c, dlg)
    for a_, b_ in [(6.0, 8.0), (8.0, 10.3), (51.0, 53.0), (53.0, 55.0)]:
        i0, i1 = int(a_ * SR), int(b_ * SR)
        print(f"  {a_:5.1f}-{b_:5.1f}: music {rms_db(music[i0:i1]):6.1f}  sfx v21 {rms_db(sfx_v21[i0:i1]):6.1f}  "
              f"sfx v24 {rms_db(sfx_c[i0:i1]):6.1f}  pressure {rms_db(press[i0:i1]):6.1f}  "
              f"mix v21 {rms_db(mix_v21[i0:i1]):6.1f}  mix v24 {rms_db(mix_c[i0:i1]):6.1f} dB (pre-scale)")

    # 4. master = baseline + w * g * (cand - v21) * scale
    g = loudnorm_gain()
    n_b = len(base)
    w = window_weight(n_b)
    delta = np.zeros((n_b, 2))
    delta[:N] = (mix_c - mix_v21) * scale * g[:, None]
    delta *= w[:, None]
    master = (base.astype(np.float64) + delta).astype(np.float32)
    master, gr, t_lim = window_limiter(master, w, TP_CEIL_DB)   # whole windows: the AAC re-encode of baseline peaks needs it (TP)
    print(f"  window limiter: max gain reduction {gr:.2f} dB over {t_lim:.3f} s (ceiling {TP_CEIL_DB} dBTP)")
    report["window_limiter"] = {"max_gr_db": gr, "seconds_limited": t_lim, "ceiling_dbtp": TP_CEIL_DB}
    # the decoder returns whole AAC frames: 448 samples past 87.5 s, all digital zero (credits silence) -> trim to
    # the film's exact length, so the new AAC stream is 87.5 s like the approved one
    assert not np.any(master[N:]), "non-silent samples past 87.5 s"
    report["trimmed_tail_samples"] = int(len(master) - N)
    master, base, w = master[:N], base[:N], w[:N]
    outside = w == 0
    ident = float(np.abs(master[outside] - base[outside]).max())
    print(f"  protected identity: max |master - baseline| outside the windows = {ident}")
    report["identity_outside_windows_max_abs"] = ident
    report["samples_outside_windows"] = int(outside.sum())
    report["duck_depths_v21"] = depths
    report["duck_need_candidate_unclamped_equiv"] = depths_c
    # per-line dialogue over bed, v21 vs candidate (stage_mix's measure, post-duck bed)
    lines = []
    for (t, ln), d in zip(spans, depths):
        i0, i1 = int(t * SR), min(int((t + ln) * SR), N)
        lines.append({"t": t, "dlg_db": rms_db(dlg[i0:i1]),
                      "bed_v21_db": rms_db((mix_v21[i0:i1] - dlg[i0:i1, None])),
                      "bed_v24_db": rms_db((mix_c[i0:i1] - dlg[i0:i1, None]))})
    report["lines"] = lines
    np.save(out_dir / "delta.npy", delta.astype(np.float32))
    wav = MASTER_DIR / "master_v24.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", str(wav)], input=master.tobytes(), check=True)
    report["master"] = {"path": str(wav), "sha256": sha256_file(wav), "samples": int(len(master)),
                        "duration_s": len(master) / SR}
    (out_dir / "sound_v24_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    np.save(out_dir / "stems_v24.npy", np.stack([mix_v21 * scale, mix_c * scale]).astype(np.float32))
    print(f"wrote {wav} sha256 {report['master']['sha256']}")


if __name__ == "__main__":
    main()
