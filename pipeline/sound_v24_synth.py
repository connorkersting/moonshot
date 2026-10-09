"""v24 helper: split the v1 synth SFX stem (audio/sfx.wav, rendered by audio/score.py) into per-family stems.

Read-only use of audio/score.py: it is imported, the music generators are called only so the shared RNG is consumed
exactly as in the original render, and Bus.add is wrapped so every SFX item lands on a bus for its family
(heart, tick, impact, whoosh, suck, blip, glitch, alarm, riser, cymbal, flash). Each family bus is rendered
(linear: dry + convolution sends), high-passed and gated like the original, then given the SAME master gain and the
SAME limiter gain curve that score.master() computes for the full stem, so the families sum to sfx.wav.

Writes <out>/synth_<family>.f32 (48 kHz stereo float32, 90 s, OLD v1 timeline) and prints the reconstruction error.
Usage: py sound_v24_synth.py <out_dir>
"""
from __future__ import annotations

import importlib.util
import json
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np
from scipy.ndimage import minimum_filter1d, uniform_filter1d

WORK = (CRAFTWORK / "inbox/moonshot/work")
SR = 48000

FAMILY_OF = {
    "heart_thump": "heart", "tick": "tick", "sub_boom": "impact", "click_layer": "impact", "crack": "impact",
    "metal_ring": "impact", "whoosh": "whoosh", "suck_back": "suck", "blip": "blip", "glitch": "glitch",
    "master_alarm": "alarm", "sfx_riser": "riser", "reverse_cymbal": "cymbal",
}


def load_score():  # noqa: ANN201  (module object)
    spec = importlib.util.spec_from_file_location("score_v1", WORK / "audio" / "score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def limiter_gain(x: np.ndarray, ceiling: float, look: float = 0.004, release: float = 0.15,
                 blk: int = 16) -> np.ndarray:
    """score.limiter(), returning its per-sample gain curve instead of the limited signal (same arithmetic)."""
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
    return np.interp(np.arange(n), centers, out)


def main(out: Path) -> None:
    sc = load_score()
    out.mkdir(parents=True, exist_ok=True)
    cues = json.loads((WORK / "cues.json").read_text(encoding="utf-8"))
    T = sc.Timeline(cues)
    rng = np.random.default_rng(sc.SEED)
    ir_hall = sc.make_ir(2.4, 3.2, 0.02, rng)
    ir_long = sc.make_ir(5.0, 6.5, 0.04, rng, hf_ratio=0.35)
    # music generators: called only to consume the RNG exactly as main() does (nothing rendered)
    C = sc.Bus(0.0, T.cold[1] + 1.0)
    sc.music_cold_open(C, T, rng)
    M = sc.Bus(0.0, T.total)
    sc.music_drop(M, T, rng)
    sc.music_groove(M, T, rng)
    sc.music_lunar_descent(M, T, rng)
    sc.music_swell(M, T, rng)
    del M, C
    # SFX, routed by family
    current = {"fam": "other"}
    for name, fam in FAMILY_OF.items():
        orig = getattr(sc, name)

        def wrapped(*a, _o=orig, _f=fam, **k):  # noqa: ANN001, ANN002, ANN003, ANN202
            current["fam"] = _f
            return _o(*a, **k)
        setattr(sc, name, wrapped)
    buses: dict[str, object] = {}

    class Router(sc.Bus):
        def add(self, sig, t, **kw):  # noqa: ANN001, ANN003, ANN201
            fam = current["fam"]
            if fam not in buses:
                buses[fam] = sc.Bus(0.0, T.total)
            buses[fam].add(sig, t, **kw)
            current["fam"] = "other"

    sc.build_sfx(Router(0.0, 1.0 / SR * 2), T, rng, ir_hall)
    gate = sc.silence_gate(T, T.fade_end - 2.5)[:, None]
    fams = {f: sc.hp20(b.render(ir_hall, ir_long)) * gate for f, b in buses.items()}
    fl = sc.flash(rng)
    i = sc.ns(T.flash_t)
    flash = np.zeros((T.n, 2))
    flash[i:i + len(fl)] += fl * 0.9
    fams["flash"] = flash
    full = sum(fams.values())
    _, st = sc.master(full, sc.SFX_TARGET_LUFS, "sfx")
    gain = 10 ** (st["gain_db"] / 20)
    gs = limiter_gain(full * gain, 10 ** (st["ceiling_dbfs"] / 20))
    from scipy.io import wavfile
    _, ref = wavfile.read(str(WORK / "audio" / "sfx.wav"))
    ref = ref.astype(np.float64)
    tot = np.zeros_like(ref)
    for f, x in fams.items():
        y = x * gain * gs[:, None]
        tot += y
        y.astype(np.float32).tofile(out / f"synth_{f}.f32")
        print(f"  {f:8s} peak {np.abs(y).max():.4f}")
    err = np.abs(tot - ref).max()
    print(f"reconstruction max |err| {err:.3e} (ref peak {np.abs(ref).max():.4f}); master gain {st['gain_db']:.3f} dB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
