"""v24b: the director's blind-A/B verdict applied (2026-10-08): ONLY the staging change of v24 is kept.

NEW file. Uses sound_v24.py's functions read-only; writes work\\audio_v24\\master_v24b.wav and
scratchpad\\v24\\b\\sound_v24b_report.json.

    py sound_v24b.py [OUT_DIR] [--synth-dir DIR]

Kept from v24 (pair 2, preferred): the quindar-like comm tick at 26.17 is removed, and the mechanical-release motif
(latch 27.94 -> clunk on the 28.0 cut) is added on its own post-duck bus. Dropped (pairs 1 and 3, baseline kept):
everything in the countdown and in 37.0-60.9.

master = baseline PCM + w(t) * g(t) * (cand - v21) * scale, where w is 1 only inside a staging sub-window whose
edges are whole picture frames chosen with >= 2 frames of margin around every non-zero sample of the change, with
10 ms equal-power (sine) ramps inside it. The change is exactly zero on those ramps, so the master equals the
baseline sample for sample everywhere outside the sub-window AND on its ramps (an equal-power fade of two identical
signals would bump +3 dB; here only the zero-valued change is faded, so there is nothing to bump).
"""
from __future__ import annotations

import json
import subprocess
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

import numpy as np

WORK = (CRAFTWORK / "inbox/moonshot/work")
sys.path.insert(0, str(WORK))
import score_pd  # noqa: E402
import sound_v24 as sv  # noqa: E402

RAMP = int(0.010 * sv.SR)
MARGIN_F = 2


def main() -> None:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else sv.SCRATCH / "b"
    synth_dir = Path(sys.argv[sys.argv.index("--synth-dir") + 1]) if "--synth-dir" in sys.argv else sv.SCRATCH / "stems"
    out_dir.mkdir(parents=True, exist_ok=True)
    rep: dict = {}
    got = sv.audio_md5(sv.V22)
    if got != sv.V22_AUDIO_MD5:
        raise SystemExit(f"baseline audio md5 {got} != pinned {sv.V22_AUDIO_MD5}")
    base = sv.decode(sv.V22, ["-map", "0:a:0"])
    assert not np.any(base[sv.N:]), "baseline: non-silent samples past 87.5 s"
    base = base[:sv.N]
    spans = sv.dialog_spans()
    dlg = sv.f32(sv.AUD / "dialog.f32", 1)
    music = sv.f32(sv.AUD / "music_pd.f32", 2)
    son = sv.f32(sv.AUD / "sonniss.f32", 2)
    synth = sum(sv.synth_v8_families(synth_dir).values())
    sfx_v21 = son + synth * 10 ** (-4.0 / 20)
    depths = sv.duck_depths(spans, music + sfx_v21, dlg)
    mix_v21 = sv.mix(music, sfx_v21, dlg, spans, depths, [(56.15, 56.45, 0.15)])
    scale = 0.7 / float(np.max(np.abs(mix_v21)))
    err = float(np.abs(mix_v21 * scale - sv.f32(sv.AUD / "mix.f32", 2)).max())
    print(f"  v21 rebuild vs audio/mix.f32: max |diff| {err:.2e}")
    if err > 1e-5:
        raise SystemExit("the v21 mix could not be rebuilt; stop")
    # candidate: v21 + (no comm tick) + the release motif, nothing else
    rows = [r for r in score_pd.SONNISS if Path(r[0]).name != sv.QUINDARISH]
    assert len(rows) == len(score_pd.SONNISS) - 1
    sfx_c = sv.stage_sfx(rows) + synth * 10 ** (-4.0 / 20)
    mix_c = sv.mix(music, sfx_c, dlg, spans, depths, [(56.15, 56.45, 0.15)], (sv.v24_motif(), (27.92, 28.10, 0.15)))
    g = sv.loudnorm_gain()
    delta = (mix_c - mix_v21) * scale * g[:, None]
    nz = np.flatnonzero(np.abs(delta).max(axis=1) > 0)
    fa = int(nz[0] // sv.SPF) - MARGIN_F
    fb = int(nz[-1] // sv.SPF) + 1 + MARGIN_F
    a, b = fa * sv.SPF, fb * sv.SPF
    w = np.zeros(sv.N)
    w[a:b] = 1.0
    u = (np.arange(RAMP) + 0.5) / RAMP
    w[a:a + RAMP] = np.sin(np.pi / 2 * u)
    w[b - RAMP:b] = np.cos(np.pi / 2 * u)
    assert not np.any(delta[a:a + RAMP]) and not np.any(delta[b - RAMP:b]), "the change reaches a ramp"
    print(f"  change support {nz[0] / sv.SR:.3f}-{nz[-1] / sv.SR:.3f} s -> sub-window frames {fa}-{fb - 1} "
          f"({a / sv.SR:.4f}-{b / sv.SR:.4f} s)")
    master = (base.astype(np.float64) + delta * w[:, None]).astype(np.float32)
    master, gr, t_lim = sv.window_limiter(master, w, sv.TP_CEIL_DB)
    outside = w < 1.0
    ident = float(np.abs(master[outside] - base[outside]).max())
    print(f"  limiter in the sub-window: {gr:.2f} dB over {t_lim:.3f} s; identity outside the full sub-window: {ident}")
    rep.update({"sub_window_frames": [fa, fb - 1], "sub_window_s": [a / sv.SR, b / sv.SR],
                "change_support_s": [nz[0] / sv.SR, nz[-1] / sv.SR], "ramp_ms": 10, "ramp_shape": "equal power (sine)",
                "limiter": {"max_gr_db": gr, "seconds": t_lim}, "identity_outside_max_abs": ident,
                "samples_outside": int(outside.sum())})
    wav = sv.MASTER_DIR / "master_v24b.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(sv.SR), "-ac", "2", "-i", "-",
                    "-c:a", "pcm_f32le", str(wav)], input=master.tobytes(), check=True)
    rep["master"] = {"path": str(wav), "sha256": sv.sha256_file(wav), "samples": int(len(master))}
    (out_dir / "sound_v24b_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    np.save(out_dir / "stems_v24b.npy", np.stack([mix_v21 * scale, mix_c * scale]).astype(np.float32))
    print(f"wrote {wav} sha256 {rep['master']['sha256']}")


if __name__ == "__main__":
    main()
