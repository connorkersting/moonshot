"""Measure a MOONSHOT export without rendering or changing source files.

Usage: py trailer_metrics.py N [--json out.json]
       py trailer_metrics.py --selftest

Thresholds are proposals from editing heuristics, not standards. Beat tracking
assumes one dominant tempo; dialogue, rubato, and tempo changes can confuse it.
Hits are prominent spectral-flux onsets, not semantic impact classifications.
Onset timestamps are refined to local 20-ms energy rises, avoiding centered
STFT look-ahead when associating a hit with the end of a quiet gap.
Gap/button detection uses 20-ms mono RMS, a short-term loudness proxy: a 3-s
EBU S window would smear a subsecond silence. Actual loudness uses FFmpeg's
EBU R128 S/I/LRA on the original channel layout, including per-act gating.
ASL splits shots at act boundaries. Windows/acts are half-open [start, end).
Frame comparisons use 24 fps, 160x90 grayscale; thresholds use 0-255 units.
The final-image hold is measured from the later of the final hit and the last
image boundary through EOF (credits/black count as an image). SHOTS describe
the current build.py, which may differ from a historical export. CAPTIONS are
reported as supplied, since their time coordinate may differ from SHOTS.

Only --json writes a file, exclusively creating it to avoid overwriting an
existing file. All decoding is piped in memory, with one FFmpeg worker thread.
No dependencies beyond NumPy and the standard library are needed.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

sys.dont_write_bytecode = True

# After the bytecode guard so dependency imports also stay read-only.
import numpy as np  # noqa: E402
from numpy.typing import NDArray  # noqa: E402

# Editing proposals; change these to match the intended edit.
CUT_TO_BEAT_MIN = 0.70
ACT3_ASL_MAX_S = 1.5
TITLE_OR_CUT_RUNTIME_FRACTION = 0.20
DROP_GAP_MIN_S = 0.3
DROP_GAP_MAX_S = 1.2
ACT3_LIFT_MIN_LU = 6.0
LRA_MIN_LU = 8.0
BUTTON_QUIET_MIN_S = 0.5
BUTTON_QUIET_MAX_S = 2.0
LAST_IMAGE_MIN_S = 2.0
LAST_IMAGE_MAX_S = 5.0
BEAT_TOLERANCE_S = 1.0 / 24.0
HOOK_MAX_S = 3.0
BLACK_MAX_S = 0.3
BLACK_MEAN_MAX = 8.0
BLACK_PIXEL_MAX = 16
BLACK_PIXEL_FRACTION_MIN = 0.98
VISUAL_CHANGE_MIN = 2.0
VISUAL_HARD_CUT_MIN = 18.0
GAP_DROP_MIN_DB = 15.0
DEAD_AIR_MIN_S = 0.25
DEAD_AIR_MAX_DBFS = -50.0
ONSET_AUDIBLE_MIN_DBFS = -50.0
BIG_ONSET_PERCENTILE = 75.0
GAP_TO_HIT_MAX_S = 0.15
ONSET_PEAK_SEPARATION_S = 0.12
TEMPO_MIN_BPM = 60.0
TEMPO_MAX_BPM = 180.0
SAMPLE_RATE = 22050
VIDEO_FPS = 24.0
RMS_BLOCK_S = 0.02
STFT_SIZE = 1024
STFT_HOP = 220
WINDOW_S = 3.0
CUT_WINDOW_S = 5.0
ACT_STARTS = (
    ("cold open", 0.0), ("act1", 10.6), ("act2", 19.0),
    ("act3", 40.3), ("outro", 61.9),
)

type JsonValue = (
    None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]
)
type Audio = NDArray[np.float32]
type Floats = NDArray[np.float64]
type Interval = tuple[float, float]


@dataclass
class Beats:
    """Onsets and an estimated beat/half-beat lattice in real seconds."""

    tempo_bpm: float | None
    beats_s: list[float]
    half_beats_s: list[float]
    onsets_s: list[float]
    onset_strengths: list[float]
    big_onsets_s: list[float]
    biggest_hit_s: float | None
    first_audible_onset_s: float | None


@dataclass
class Edit:
    """Optional metadata from the current sibling build.py."""

    cuts: list[float]
    total: float | None
    title_s: float | None
    captions: JsonValue
    available: bool
    warnings: list[str]


@dataclass
class Loudness:
    """EBU measurements; None represents unavailable/ungated data."""

    integrated_lufs: float | None
    lra_lu: float | None
    short_term: list[tuple[float, float | None]]


@dataclass
class Report:
    """Serializable measurements and a human-readable rule table."""

    data: dict[str, JsonValue]
    rows: list[tuple[str, str, str]]


def run_process(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    """Run a read-only decoder, reporting useful errors without shell use."""
    result = subprocess.run(
        command, capture_output=True, check=False, timeout=300,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"{command[0]} failed: {message}")
    return result


def ffmpeg_input(path: Path) -> list[str]:
    """Limit decoder and filter parallelism."""
    return [
        "ffmpeg", "-nostdin", "-hide_banner", "-nostats",
        "-threads", "1", "-filter_threads", "1", "-i", str(path),
    ]


def probe_duration(path: Path) -> float:
    """Read the actual export runtime, rather than assuming build TOTAL."""
    result = run_process([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ])
    duration = float(json.loads(result.stdout)["format"]["duration"])
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError(f"Invalid export duration: {duration}")
    return duration


def decode_audio(path: Path) -> Audio:
    """Decode mono float PCM at 22050 Hz in memory."""
    result = run_process(ffmpeg_input(path) + [
        "-v", "error", "-map", "0:a:0", "-vn", "-ac", "1",
        "-ar", f"{SAMPLE_RATE}", "-f", "f32le", "pipe:1",
    ])
    audio = np.frombuffer(result.stdout, dtype="<f4")
    if not audio.size or not np.all(np.isfinite(audio)):
        raise ValueError("Decoded audio is empty or has nonfinite samples")
    return audio


def rms_levels(audio: Audio) -> tuple[Floats, Floats]:
    """Return 20-ms RMS energies and dBFS (including a partial last block)."""
    block = round(RMS_BLOCK_S * SAMPLE_RATE)
    starts = np.arange(0, len(audio), block)
    lengths = np.minimum(block, len(audio) - starts)
    energy = np.add.reduceat(audio.astype(np.float64) ** 2, starts) / lengths
    return energy, 10.0 * np.log10(np.maximum(energy, 1e-12))


def local_peaks(values: Floats, minimum: float) -> list[int]:
    """Pick local maxima, suppressing neighbors around stronger peaks."""
    candidates = np.flatnonzero(
        (values >= np.roll(values, 1))
        & (values > np.roll(values, -1)) & (values > minimum)
    )
    separation = round(ONSET_PEAK_SEPARATION_S * SAMPLE_RATE / STFT_HOP)
    blocked = np.zeros(len(values), dtype=np.bool_)
    selected: list[int] = []
    for index in candidates[np.argsort(values[candidates])[::-1]]:
        if not blocked[index]:
            selected.append(int(index))
            blocked[max(0, index - separation):index + separation + 1] = True
    return sorted(selected)


def analyze_beats(audio: Audio) -> Beats:
    """Autocorrelate spectral flux and peak-pick a tempo-aligned beat grid."""
    padded = np.pad(audio, (STFT_SIZE // 2, STFT_SIZE // 2))
    frames = np.lib.stride_tricks.sliding_window_view(
        padded, STFT_SIZE,
    )[::STFT_HOP]
    window = np.hanning(STFT_SIZE)
    # Chunking avoids holding the complete complex spectrogram.
    envelope = np.zeros(len(frames), dtype=np.float64)
    previous = np.zeros(STFT_SIZE // 2 + 1)
    for start in range(0, len(frames), 512):
        magnitudes = np.log1p(np.abs(np.fft.rfft(
            frames[start:start + 512] * window, axis=1,
        )))
        differences = np.diff(
            magnitudes, axis=0, prepend=previous[np.newaxis, :],
        )
        envelope[start:start + len(magnitudes)] = np.maximum(
            differences, 0.0,
        ).mean(axis=1)
        previous = magnitudes[-1]
    duration = len(audio) / SAMPLE_RATE
    energies, levels = rms_levels(audio)
    audible = np.flatnonzero(levels > ONSET_AUDIBLE_MIN_DBFS)
    first = float(audible[0] * RMS_BLOCK_S) if audible.size else None
    if envelope.max(initial=0.0) <= 1e-9 or not audible.size:
        return Beats(None, [], [], [], [], [], None, first)
    threshold = max(
        float(envelope.max()) * 0.04,
        float(np.median(envelope) + 0.5 * np.std(envelope)),
    )
    indices = local_peaks(envelope, threshold)
    times = np.array(indices, dtype=np.float64) * STFT_HOP / SAMPLE_RATE
    strengths = envelope[indices]
    # A centered STFT sees a transient before its RMS block starts. Test
    # the entire supporting window rather than only the peak's time block.
    block_indices = (times / RMS_BLOCK_S).astype(int)
    radius = math.ceil(STFT_SIZE / (2 * SAMPLE_RATE * RMS_BLOCK_S))
    audible_mask = np.array([
        np.max(levels[
            max(0, index - radius):min(len(levels), index + radius + 1)
        ]) > ONSET_AUDIBLE_MIN_DBFS for index in block_indices
    ])
    times, strengths = times[audible_mask], strengths[audible_mask]
    if not len(times):
        return Beats(None, [], [], [], [], [], None, first)
    rises = np.maximum(np.diff(energies, prepend=0.0), 0.0)
    half_window = STFT_SIZE / (2 * SAMPLE_RATE)
    for position, time in enumerate(times):
        start = max(0, math.ceil((time - half_window) / RMS_BLOCK_S))
        end = min(len(rises), math.floor(
            (time + half_window) / RMS_BLOCK_S,
        ) + 1)
        if start < end and rises[start:end].max() > 0:
            block = start + int(np.argmax(rises[start:end]))
            times[position] = block * RMS_BLOCK_S
    big = times[strengths >= np.percentile(
        strengths, BIG_ONSET_PERCENTILE,
    )].tolist()
    biggest = float(times[int(np.argmax(strengths))])
    if len(times) < 3 or duration < 2.0:
        return Beats(
            None, [], [], times.tolist(), strengths.tolist(), big,
            biggest, first,
        )
    centered = envelope - envelope.mean()
    size = 1 << (2 * len(centered) - 1).bit_length()
    spectrum = np.fft.rfft(centered, n=size)
    correlation = np.fft.irfft(spectrum * spectrum.conj(), n=size)
    minimum_lag = 60 * SAMPLE_RATE / (TEMPO_MAX_BPM * STFT_HOP)
    maximum_lag = 60 * SAMPLE_RATE / (TEMPO_MIN_BPM * STFT_HOP)
    low = math.floor(minimum_lag)
    high = min(
        len(envelope) - 2,
        math.ceil(maximum_lag),
    )
    lags = np.arange(low, high + 1)
    # A broad 120-BPM prior resolves otherwise ambiguous octave choices.
    bpms = 60 * SAMPLE_RATE / (lags * STFT_HOP)
    scores = correlation[lags] / (len(envelope) - lags)
    scores *= np.exp(-0.5 * (np.log2(bpms / 120.0) / 0.65) ** 2)
    best = int(lags[int(np.argmax(scores))])
    if correlation[best] <= 0:
        return Beats(
            None, [], [], times.tolist(), strengths.tolist(), big,
            biggest, first,
        )
    left, center, right = correlation[best - 1:best + 2]
    denominator = left - 2 * center + right
    offset = (0.5 * (left - right) / denominator
              if abs(denominator) > 1e-12 else 0.0)
    lag = float(np.clip(best + offset, minimum_lag, maximum_lag))
    period = lag * STFT_HOP / SAMPLE_RATE
    tempo = 60.0 / period
    phases = np.arange(0.0, period, STFT_HOP / SAMPLE_RATE)
    distances = np.abs(
        (times[:, None] - phases[None, :] + period / 2) % period
        - period / 2
    )
    phase_scores = (
        strengths[:, None] * np.exp(-0.5 * (distances / 0.04) ** 2)
    ).sum(axis=0)
    phase = float(phases[int(np.argmax(phase_scores))])
    grid = np.arange(phase, duration, period)
    # Snap to an observed peak within 20% of a beat, preserving missing beats.
    tracked: list[float] = []
    for predicted in grid:
        nearby = np.flatnonzero(np.abs(times - predicted) < period * 0.20)
        if nearby.size:
            score = strengths[nearby] * np.exp(
                -0.5 * ((times[nearby] - predicted) / 0.04) ** 2,
            )
            tracked.append(float(times[nearby[int(np.argmax(score))]]))
        else:
            tracked.append(float(predicted))
    half_beats = sorted(tracked + [
        (left + right) / 2 for left, right in zip(tracked, tracked[1:])
    ])
    # Include half-beats between the first/last grid beat and the file edges.
    if tracked and tracked[0] - period / 2 >= 0:
        half_beats.insert(0, tracked[0] - period / 2)
    if tracked and tracked[-1] + period / 2 < duration:
        half_beats.append(tracked[-1] + period / 2)
    return Beats(
        tempo, tracked, half_beats, times.tolist(), strengths.tolist(), big,
        biggest, first,
    )


def cut_alignment(cuts: list[float], grid: list[float]) -> float | None:
    """Share of cuts within one 24-fps frame of a beat or half-beat."""
    if not cuts or not grid:
        return None
    beats = np.array(grid)
    aligned = sum(
        float(np.min(np.abs(beats - cut))) <= BEAT_TOLERANCE_S + 1e-9
        for cut in cuts
    )
    return aligned / len(cuts)


def json_value(value: object) -> JsonValue:
    """Convert optional build metadata to strict JSON values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return str(value)


def load_edit(duration: float) -> Edit:
    """Import the local build with neutral argv and no bytecode writes.

    The existing build's render entrypoint is guarded by __main__. Importing
    that file reads its tables; none of its pipeline functions are called.
    """
    path = Path(__file__).resolve().with_name("build.py")
    if not path.is_file():
        return Edit([], None, None, None, False, ["build.py is absent"])
    name = "_trailer_metrics_build"
    original_argv = sys.argv
    previous_module = sys.modules.get(name)
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        # build.py reads argv[2] at import; --json must not reach that code.
        sys.argv = [str(path)]
        spec.loader.exec_module(module)
        shots = getattr(module, "SHOTS", [])
        available = bool(shots)
        cuts = sorted({
            float(shot.t0) for shot in shots
            if math.isfinite(float(shot.t0)) and 0 < float(shot.t0) < duration
        })
        total_value = getattr(module, "TOTAL", None)
        total = float(total_value) if total_value is not None else None
        titles = [
            float(shot.t0) for shot in shots
            if "title" in str(getattr(shot, "note", "")).lower()
            and 0 <= float(shot.t0) < duration
        ]
        warnings = [
            "Cut metadata is from current build.py, not a versioned EDL.",
            "CAPTIONS use supplied coordinates; no time remap applied.",
        ]
        if total is not None and abs(total - duration) > BEAT_TOLERANCE_S:
            warnings.append(
                f"build TOTAL {total:.3f}s != export {duration:.3f}s"
            )
        return Edit(
            cuts, total, min(titles) if titles else None,
            json_value(getattr(module, "CAPTIONS", None)), available, warnings,
        )
    except (Exception, SystemExit) as error:
        # Literal-table fallback avoids requiring build's rendering packages.
        try:
            return load_literal_edit(path, duration, f"Import failed: {error}")
        except (OSError, ValueError, SyntaxError, TypeError) as literal_error:
            return Edit([], None, None, None, False, [
                f"Cannot import build metadata: {error}",
                f"Cannot read literal tables: {literal_error}",
            ])
    finally:
        sys.argv = original_argv
        if previous_module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_module


def load_literal_edit(path: Path, duration: float, reason: str) -> Edit:
    """Read literal Shot calls and tables without executing any build code."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    tables: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    tables[target.id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
        ):
            if node.value is not None:
                tables[node.target.id] = node.value
    shots = tables.get("SHOTS")
    if not isinstance(shots, (ast.List, ast.Tuple)) or not shots.elts:
        raise ValueError("SHOTS is not a nonempty literal sequence")
    cuts: list[float] = []
    titles: list[float] = []
    for node in shots.elts:
        if not isinstance(node, ast.Call):
            raise ValueError("SHOTS contains a non-call expression")
        if not isinstance(node.func, ast.Name) or node.func.id != "Shot":
            raise ValueError("SHOTS contains a call other than Shot")
        keywords = {key.arg: key.value for key in node.keywords}
        time_node = node.args[0] if node.args else keywords.get("t0")
        if time_node is None:
            raise ValueError("Shot lacks t0")
        time = float(ast.literal_eval(time_node))
        if not math.isfinite(time):
            raise ValueError("Shot has a nonfinite t0")
        if 0 < time < duration:
            cuts.append(time)
        note_node = keywords.get("note")
        note = (
            str(ast.literal_eval(note_node)) if note_node is not None else ""
        )
        if "title" in note.lower() and 0 <= time < duration:
            titles.append(time)
    total_node = tables.get("TOTAL")
    total = (
        float(ast.literal_eval(total_node))
        if total_node is not None else None
    )
    captions_node = tables.get("CAPTIONS")
    captions = (
        json_value(ast.literal_eval(captions_node))
        if captions_node is not None else None
    )
    warnings = [
        f"Literal build tables used without rendering imports ({reason}).",
        "Cut metadata is from current build.py, not a versioned EDL.",
        "CAPTIONS use supplied coordinates; no logical-time remap applied.",
    ]
    if total is not None and abs(total - duration) > BEAT_TOLERANCE_S:
        warnings.append(f"build TOTAL {total:.3f}s != export {duration:.3f}s")
    return Edit(
        sorted(set(cuts)), total, min(titles) if titles else None,
        captions, True, warnings,
    )


def acts(duration: float) -> list[tuple[str, float, float]]:
    """Clip the requested fixed act boundaries to the actual runtime."""
    result: list[tuple[str, float, float]] = []
    for index, (name, start) in enumerate(ACT_STARTS):
        end = (
            ACT_STARTS[index + 1][1]
            if index + 1 < len(ACT_STARTS) else duration
        )
        if start < duration:
            result.append((name, start, min(end, duration)))
    return result


def mask_intervals(mask: NDArray[np.bool_], step: float,
                   duration: float) -> list[Interval]:
    """Return contiguous true intervals, including intervals touching EOF."""
    transitions = np.diff(np.r_[False, mask, False].astype(np.int8))
    return [
        (float(start * step), min(float(end * step), duration))
        for start, end in zip(
            np.flatnonzero(transitions == 1),
            np.flatnonzero(transitions == -1),
        )
    ]


def visual_metrics(path: Path, duration: float,
                   full_scan: bool = False) -> dict[str, JsonValue]:
    """Measure the visual hook; scan EOF only if SHOTS are unavailable."""
    raw = run_process(ffmpeg_input(path) + [
        "-v", "error", "-map", "0:v:0", "-an", "-vf",
        f"fps={VIDEO_FPS},scale=160:90,format=gray",
        "-t", f"{duration if full_scan else min(duration, HOOK_MAX_S)}",
        "-threads", "1", "-f", "rawvideo", "pipe:1",
    ]).stdout
    frame_size = 160 * 90
    count = len(raw) // frame_size
    if count < 2:
        raise ValueError("Fewer than two decoded video frames")
    frames = np.frombuffer(raw, dtype=np.uint8)[:count * frame_size].reshape(
        count, frame_size,
    )
    differences = np.zeros(count, dtype=np.float64)
    for start in range(1, count, 128):
        stop = min(start + 128, count)
        differences[start:stop] = np.abs(
            frames[start:stop].astype(np.int16)
            - frames[start - 1:stop - 1].astype(np.int16)
        ).mean(axis=1)
    opening_count = min(count, math.ceil(HOOK_MAX_S * VIDEO_FPS))
    opening = frames[:opening_count]
    black = (
        (opening.mean(axis=1) <= BLACK_MEAN_MAX)
        & ((opening <= BLACK_PIXEL_MAX).mean(axis=1)
           >= BLACK_PIXEL_FRACTION_MIN)
    )
    black_spans = mask_intervals(
        black, 1 / VIDEO_FPS, min(duration, HOOK_MAX_S),
    )
    changes = np.flatnonzero(
        differences[1:opening_count] >= VISUAL_CHANGE_MIN,
    ) + 1
    hard_cuts = np.flatnonzero(differences >= VISUAL_HARD_CUT_MIN)
    return {
        "first_visual_change_s": float(changes[0] / VIDEO_FPS)
        if changes.size else None,
        "first_detected_hard_cut_s": float(hard_cuts[0] / VIDEO_FPS)
        if hard_cuts.size else None,
        "detected_hard_cuts_s": json_value((hard_cuts / VIDEO_FPS).tolist()),
        "opening_black_intervals_s": json_value(black_spans),
        "opening_black_over_0_3_s": json_value([
            span for span in black_spans if span[1] - span[0] > BLACK_MAX_S
        ]),
    }


def finite_number(text: str) -> float | None:
    """Map FFmpeg -inf/nan and the ungated -70 LUFS sentinel to null."""
    value = float(text)
    return value if math.isfinite(value) and value > -70.0 else None


def measure_loudness(path: Path, span: Interval | None = None) -> Loudness:
    """Parse EBU R128 verbose S frames and the final I/LRA summary."""
    filters = "ebur128=framelog=verbose"
    if span is not None:
        start, end = span
        filters = (
            f"atrim=start={start}:end={end},asetpts=PTS-STARTPTS,{filters}"
        )
    result = run_process(ffmpeg_input(path) + [
        "-loglevel", "verbose", "-map", "0:a:0", "-vn",
        "-af", filters, "-f", "null", "-",
    ])
    log = result.stderr.decode("utf-8", errors="replace")
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+|inf|nan)"
    frames = re.findall(
        rf"\bt:\s*({number}).*?\bS:\s*({number})", log,
    )
    short_term = [
        (float(time), finite_number(level)) for time, level in frames
    ]
    summary = log[log.rfind("Summary:"):]
    integrated = re.search(rf"\bI:\s*({number})\s*LUFS", summary)
    lra = re.search(rf"\bLRA:\s*({number})\s*LU", summary)
    if integrated is None or lra is None or not frames:
        raise RuntimeError("Could not parse FFmpeg EBU R128 S/I/LRA output")
    return Loudness(
        finite_number(integrated[1]), finite_number(lra[1]), short_term,
    )


def loudness_windows(measurement: Loudness,
                     duration: float) -> list[JsonValue]:
    """Sample trailing 3-s S values at window ends, using exact frame times."""
    windows: list[JsonValue] = []
    for start in np.arange(0, duration, WINDOW_S):
        end = min(float(start + WINDOW_S), duration)
        # FFmpeg timestamps the first completed 3-s window near 2.99995.
        candidates = [
            (time, level) for time, level in measurement.short_term
            if time <= end + 0.001 and time >= WINDOW_S - 0.001
        ]
        time, level = candidates[-1] if candidates else (None, None)
        windows.append({
            "start_s": float(start), "end_s": end,
            "S_lufs": level, "measurement_time_s": time,
            "partial_window": bool(end - start < WINDOW_S - 0.001),
        })
    return windows


def detect_gaps(energy: Floats, levels: Floats,
                duration: float) -> list[dict[str, JsonValue]]:
    """Freeze each gap's threshold at its preceding 3-s energy baseline."""
    prefix = np.r_[0.0, np.cumsum(energy)]
    preceding = round(WINDOW_S / RMS_BLOCK_S)
    gaps: list[dict[str, JsonValue]] = []
    index = 1
    while index < len(levels):
        start_index = max(0, index - preceding)
        baseline = 10 * math.log10(max(
            (prefix[index] - prefix[start_index]) / (index - start_index),
            1e-12,
        ))
        threshold = baseline - GAP_DROP_MIN_DB
        if baseline > DEAD_AIR_MAX_DBFS and levels[index] <= threshold:
            end = index + 1
            while end < len(levels) and levels[end] <= threshold:
                end += 1
            start_s = index * RMS_BLOCK_S
            end_s = min(end * RMS_BLOCK_S, duration)
            length = end_s - start_s
            if DROP_GAP_MIN_S - 1e-9 <= length <= DROP_GAP_MAX_S + 1e-9:
                gaps.append({
                    "start_s": start_s, "end_s": end_s,
                    "duration_s": length, "preceding_3s_dbfs": baseline,
                    "gap_dbfs": float(10 * np.log10(max(
                        float(energy[index:end].mean()), 1e-12,
                    ))),
                })
            index = end
        else:
            index += 1
    return gaps


def subtract_intervals(spans: list[Interval],
                       excluded: list[Interval]) -> list[Interval]:
    """Keep portions of absolute silence outside detected editorial gaps."""
    result: list[Interval] = []
    for start, end in spans:
        pieces = [(start, end)]
        for left, right in excluded:
            remainder: list[Interval] = []
            for a, b in pieces:
                if right <= a or left >= b:
                    remainder.append((a, b))
                else:
                    if a < left:
                        remainder.append((a, left))
                    if right < b:
                        remainder.append((right, b))
            pieces = remainder
        result.extend(pieces)
    return result


def final_quiet(levels: Floats, hit: float | None) -> float | None:
    """Measure contiguous relative quiet immediately before the final hit."""
    if hit is None:
        return None
    index = min(int(hit / RMS_BLOCK_S), len(levels) - 1)
    # Look immediately after the onset too: STFT peaks may lead the hit.
    local = levels[index:min(len(levels), index + 6)]
    hit_level = float(local.max(initial=DEAD_AIR_MAX_DBFS))
    threshold = max(DEAD_AIR_MAX_DBFS, hit_level - GAP_DROP_MIN_DB)
    cursor = index - 1
    while cursor >= 0 and levels[cursor] < threshold:
        cursor -= 1
    return max(0.0, hit - (cursor + 1) * RMS_BLOCK_S)


def display_number(value: float | None, unit: str = "") -> str:
    """Format unavailable measurements without accidentally passing a rule."""
    return f"{value:.3f}{unit}" if value is not None else "unavailable"


def analyze_export(path: Path, version: int) -> Report:
    """Assemble all metrics and PASS/WARN rules for one export."""
    duration = probe_duration(path)
    edit = load_edit(duration)
    audio = decode_audio(path)
    beat = analyze_beats(audio)
    energy, levels = rms_levels(audio)
    visuals = visual_metrics(path, duration, full_scan=not edit.available)
    overall_loudness = measure_loudness(path)
    sections = acts(duration)
    gaps = detect_gaps(energy, levels, min(duration, len(audio) / SAMPLE_RATE))
    for gap in gaps:
        end = cast(float, gap["end_s"])
        following = next(
            (time for time in beat.big_onsets_s if time >= end), None,
        )
        gap["next_big_onset_s"] = following
        gap["next_big_onset_delay_s"] = (
            following - end if following is not None else None
        )
    absolute_silences = mask_intervals(
        levels < DEAD_AIR_MAX_DBFS, RMS_BLOCK_S,
        min(duration, len(audio) / SAMPLE_RATE),
    )
    gap_spans = [
        (cast(float, gap["start_s"]), cast(float, gap["end_s"]))
        for gap in gaps
    ]
    dead_air = [
        (start, end) for start, end in subtract_intervals(
            absolute_silences, gap_spans,
        ) if end - start > DEAD_AIR_MIN_S
    ]
    final_onset = beat.onsets_s[-1] if beat.onsets_s else None
    final_hit = beat.big_onsets_s[-1] if beat.big_onsets_s else None
    quiet = final_quiet(levels, final_onset)
    final_hit_quiet = final_quiet(levels, final_hit)
    visual_cuts = cast(list[float], visuals["detected_hard_cuts_s"])
    image_boundaries = edit.cuts if edit.available else visual_cuts
    image_start = image_boundaries[-1] if image_boundaries else 0.0
    hold = (
        duration - max(image_start, final_hit)
        if final_hit is not None else None
    )
    alignment = cut_alignment(edit.cuts, beat.half_beats_s)
    rows: list[tuple[str, str, str]] = []

    def rule(name: str, passed: bool, value: str) -> None:
        rows.append((name, "PASS" if passed else "WARN", value))

    rule("Cut-to-beat overall",
         alignment is not None and alignment >= CUT_TO_BEAT_MIN,
         f"{display_number(alignment)}; target >= {CUT_TO_BEAT_MIN:.2f}")
    act_metrics: list[JsonValue] = []
    act_asl: dict[str, float | None] = {}
    act_loudness: dict[str, float | None] = {}
    for name, start, end in sections:
        # Boundary cuts begin the next act and do not create zero-length shots.
        inside = [cut for cut in edit.cuts if start < cut < end]
        asl = (end - start) / (len(inside) + 1) if edit.available else None
        act_asl[name] = asl
        section_cuts = [cut for cut in edit.cuts if start <= cut < end]
        share = cut_alignment(section_cuts, beat.half_beats_s)
        loudness = measure_loudness(path, (start, end)).integrated_lufs
        act_loudness[name] = loudness
        act_metrics.append({
            "act": name, "start_s": start, "end_s": end,
            "cuts": len(section_cuts) if edit.available else None,
            "shot_segments": len(inside) + 1 if edit.available else None,
            "ASL_s": asl, "cut_to_beat_share": share,
            "integrated_lufs": loudness,
        })
        rule(f"Cut-to-beat {name}",
             share is not None and share >= CUT_TO_BEAT_MIN,
             f"{display_number(share)}; cuts={len(section_cuts)}")
        rows.append((f"ASL / loudness {name}", "INFO",
                     f"{display_number(asl, ' s')} / "
                     f"{display_number(loudness, ' LUFS')}"))
    asl3 = act_asl.get("act3")
    rule("Act3 ASL", asl3 is not None and asl3 <= ACT3_ASL_MAX_S,
         f"{display_number(asl3, ' s')}; target <= {ACT3_ASL_MAX_S:.1f} s")
    hard_cut = cast(float | None, visuals["first_detected_hard_cut_s"])
    introductions = [time for time in (
        edit.title_s, edit.cuts[0] if edit.cuts else None, hard_cut,
    ) if time is not None]
    introduction = min(introductions) if introductions else None
    deadline = TITLE_OR_CUT_RUNTIME_FRACTION * duration
    rule("Title / hard cut",
         introduction is not None and introduction <= deadline,
         f"{display_number(introduction, ' s')}; deadline={deadline:.3f} s")
    first_visual = cast(float | None, visuals["first_visual_change_s"])
    rule("Audible hook", beat.first_audible_onset_s is not None
         and beat.first_audible_onset_s <= HOOK_MAX_S,
         display_number(beat.first_audible_onset_s, " s"))
    rule("Visual hook",
         first_visual is not None and first_visual <= HOOK_MAX_S,
         display_number(first_visual, " s"))
    black_spans = cast(list[JsonValue], visuals["opening_black_over_0_3_s"])
    rule("Opening black", not black_spans,
         f"{len(black_spans)} intervals > {BLACK_MAX_S:.1f} s")
    drop_before_hit = any(
        beat.biggest_hit_s is not None
        and 0 <= beat.biggest_hit_s - cast(float, gap["end_s"])
        <= GAP_TO_HIT_MAX_S
        for gap in gaps
    )
    rule("Drop before biggest hit", drop_before_hit,
         f"hit={display_number(beat.biggest_hit_s, ' s')}; gaps={len(gaps)}")
    act1, act3 = act_loudness.get("act1"), act_loudness.get("act3")
    lift = act3 - act1 if act3 is not None and act1 is not None else None
    rule("Act3 minus Act1", lift is not None and lift >= ACT3_LIFT_MIN_LU,
         f"{display_number(lift, ' LU')}; target >= {ACT3_LIFT_MIN_LU:.1f} LU")
    lra = overall_loudness.lra_lu
    rule("Overall LRA", lra is not None and lra >= LRA_MIN_LU,
         f"{display_number(lra, ' LU')}; target >= {LRA_MIN_LU:.1f} LU")
    rule("Button quiet", quiet is not None
         and BUTTON_QUIET_MIN_S <= quiet <= BUTTON_QUIET_MAX_S,
         f"{display_number(quiet, ' s')}; "
         f"target {BUTTON_QUIET_MIN_S}-{BUTTON_QUIET_MAX_S} s")
    rule("Last image after final hit", hold is not None
         and LAST_IMAGE_MIN_S <= hold <= LAST_IMAGE_MAX_S,
         f"{display_number(hold, ' s')}; "
         f"target {LAST_IMAGE_MIN_S}-{LAST_IMAGE_MAX_S} s")
    rule("Dead air candidates", not dead_air,
         f"{len(dead_air)} intervals > {DEAD_AIR_MIN_S} s "
         f"below {DEAD_AIR_MAX_DBFS:.0f} dBFS")
    rule("Build metadata available", edit.available,
         f"{len(edit.cuts)} cuts; TOTAL={display_number(edit.total, ' s')}")
    windows: list[JsonValue] = [
        {"start_s": float(start),
         "end_s": min(float(start + CUT_WINDOW_S), duration),
         "cuts": int(sum(
             start <= cut < start + CUT_WINDOW_S for cut in edit.cuts
         ))
         if edit.available else None}
        for start in np.arange(0, duration, CUT_WINDOW_S)
    ]
    notes = edit.warnings + [
        "Beat/hit/silence estimates are heuristic; review WARN by ear.",
        "A single dominant-tempo grid may misalign rubato or tempo changes.",
        "Dead air may include intentional opening/button/credit silence.",
        "Final image uses current SHOTS, or decoded hard cuts if absent.",
        "Partial final S window still uses a trailing 3-s measurement.",
    ]
    data: dict[str, JsonValue] = {
        "version": version, "video": str(path), "duration_s": duration,
        "thresholds": json_value({
            key: value for key, value in globals().items()
            if key.isupper() and isinstance(value, (int, float))
        }),
        "notes": json_value(notes),
        "edit": {"source": str(Path(__file__).resolve().with_name("build.py")),
                 "available": edit.available, "TOTAL_s": edit.total,
                 "cuts_s": json_value(edit.cuts), "CAPTIONS": edit.captions,
                 "title_hint_s": edit.title_s},
        "acts": act_metrics, "cuts_per_5s": windows,
        "rhythm": {"tempo_bpm": beat.tempo_bpm,
                   "beats_s": json_value(beat.beats_s),
                   "beat_or_half_beat_grid_s": json_value(beat.half_beats_s),
                   "onsets_s": json_value(beat.onsets_s),
                   "onset_strengths": json_value(beat.onset_strengths),
                   "big_onsets_s": json_value(beat.big_onsets_s),
                   "biggest_hit_s": beat.biggest_hit_s,
                   "cut_to_beat_share": alignment},
        "hook": {**visuals,
                 "first_audible_onset_s": beat.first_audible_onset_s,
                 "title_or_hard_cut_s": introduction},
        "loudness": {"method": "ffmpeg ebur128 on original channels",
                     "integrated_lufs": overall_loudness.integrated_lufs,
                     "LRA_lu": lra, "act3_minus_act1_lu": lift,
                     "per_3s_windows": loudness_windows(
                         overall_loudness, duration,
                     ),
                     "short_term_samples": json_value(
                         overall_loudness.short_term,
                     )},
        "gaps": json_value(gaps),
        "button": {"last_onset_s": final_onset, "final_hit_s": final_hit,
                   "quiet_before_last_onset_s": quiet,
                   "quiet_before_final_hit_s": final_hit_quiet,
                   "last_image_start_s": image_start,
                   "last_image_total_s": duration - image_start,
                   "last_image_after_final_hit_s": hold},
        "dead_air_candidates_s": json_value(dead_air),
        "rules": [{"rule": name, "status": status, "measurement": value}
                  for name, status, value in rows if status != "INFO"],
        "table": [{"metric": name, "status": status, "measurement": value}
                  for name, status, value in rows],
    }
    return Report(data, rows)


def print_report(report: Report) -> None:
    """Print the rule table and detailed time windows/candidate gaps."""
    print(f"MOONSHOT v{report.data['version']}: "
          f"{report.data['duration_s']:.3f} s")
    rhythm = cast(dict[str, JsonValue], report.data["rhythm"])
    tempo = cast(float | None, rhythm["tempo_bpm"])
    print(f"Tempo: {display_number(tempo, ' BPM')}")
    print(f"{'Metric':<32} {'Rule':<5} Measurement")
    print("-" * 100)
    for name, status, value in report.rows:
        print(f"{name:<32} {status:<5} {value}")
    print("\nCuts per 5 s:")
    for value in cast(list[dict[str, JsonValue]], report.data["cuts_per_5s"]):
        print(f"  {value['start_s']:6.2f}-{value['end_s']:6.2f} s: "
              f"{value['cuts']}")
    print("\nShort-term loudness (trailing 3 s at each window end):")
    loudness = cast(dict[str, JsonValue], report.data["loudness"])
    for value in cast(list[dict[str, JsonValue]], loudness["per_3s_windows"]):
        level = display_number(cast(float | None, value["S_lufs"]), " LUFS")
        print(f"  {value['start_s']:6.2f}-{value['end_s']:6.2f} s: {level}")
    print("\nDetected drop gaps / next big onset:")
    gaps = cast(list[dict[str, JsonValue]], report.data["gaps"])
    for gap in gaps:
        following = display_number(
            cast(float | None, gap["next_big_onset_s"]), " s",
        )
        print(f"  {gap['start_s']:.3f}-{gap['end_s']:.3f} s -> {following}")
    if not gaps:
        print("  none")
    print(f"Dead air candidates: {report.data['dead_air_candidates_s']}")
    hook = cast(dict[str, JsonValue], report.data["hook"])
    print(f"Opening black intervals: {hook['opening_black_intervals_s']}")
    for note in cast(list[str], report.data["notes"]):
        print(f"Note: {note}")


def selftest() -> None:
    """Check a synthesized 20-second, 120-BPM click track in memory."""
    audio = np.zeros(20 * SAMPLE_RATE, dtype=np.float32)
    cuts = np.arange(0.5, 20.0, 0.5)
    click = np.exp(-np.arange(220) / 30.0).astype(np.float32)
    for time in np.arange(0.0, 20.0, 0.5):
        start = int(time * SAMPLE_RATE)
        audio[start:start + len(click)] += click
    result = analyze_beats(audio)
    tempo = result.tempo_bpm
    assert tempo is not None and abs(tempo - 120.0) < 2.0, tempo
    share = cut_alignment(cuts.tolist(), result.half_beats_s)
    assert share == 1.0, share
    print(f"Selftest PASS: tempo={tempo:.2f} BPM, cut-to-beat={share:.3f}")
    silent = analyze_beats(np.zeros(SAMPLE_RATE * 3, dtype=np.float32))
    assert silent.tempo_bpm is None and not silent.onsets_s
    assert cut_alignment([], result.half_beats_s) is None
    assert cut_alignment([0.5], []) is None
    assert mask_intervals(np.array([True, False, True]), 0.5, 1.5) == [
        (0.0, 0.5), (1.0, 1.5),
    ]
    # Subsecond gap and >1.2-s silence must not be confused.
    fixture = np.full(500, -20.0)
    fixture[150:180] = -60.0
    fixture[300:400] = -60.0
    gaps = detect_gaps(10 ** (fixture / 10), fixture, 10.0)
    assert len(gaps) == 1
    assert abs(cast(float, gaps[0]["duration_s"]) - 0.6) < 1e-9
    assert subtract_intervals([(0.0, 2.0)], [(0.5, 1.0)]) == [
        (0.0, 0.5), (1.0, 2.0),
    ]
    # NumPy booleans from window arithmetic must become native JSON values.
    windows = loudness_windows(Loudness(-20.0, 9.0, [(3.0, -20.0)]), 3.5)
    json.dumps(windows, allow_nan=False)
    print("Selftest PASS: silence, missing-grid, gap, and interval edge cases")


def main() -> None:
    """Parse CLI arguments; write only an explicitly requested JSON file."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=int, nargs="?", metavar="N")
    parser.add_argument("--json", type=Path, metavar="OUT.JSON")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        if args.version is None:
            if args.json is not None:
                parser.error("--json requires a version N")
            return
    if args.version is None or args.version < 1:
        parser.error("provide a positive version N or --selftest")
    path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "exports" / "moonshot" / "versions"
        / f"moonshot_v{args.version}.mp4"
    )
    if args.json is not None and args.json.exists():
        parser.error(f"refusing to overwrite existing JSON path: {args.json}")
    try:
        if not path.is_file():
            raise FileNotFoundError(f"Export does not exist: {path}")
        for executable in ("ffmpeg", "ffprobe"):
            if shutil.which(executable) is None:
                raise FileNotFoundError(f"{executable} is unavailable on PATH")
        report = analyze_export(path, args.version)
        print_report(report)
        if args.json is not None:
            contents = json.dumps(report.data, indent=2, allow_nan=False)
            with args.json.open("x", encoding="utf-8") as handle:
                handle.write(f"{contents}\n")
            print(f"JSON written: {args.json}")
    except (OSError, ValueError, RuntimeError,
            subprocess.TimeoutExpired) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
