"""techqc.py: first video/audio tracks; findings make delivery QC fail.
Times are seconds from container start. Exclusions are [start,end), by frame PTS.
Black: full-range 8-bit gray mean <16. Freeze: adjacent-frame MAD <0.5,
including a two-frame pair. Clicks: exact centered ~50 ms median, each channel;
edge windows use reflection. Click candidates are heuristic, not proof of a click.
Audio is held in RAM. Exit codes: 0 PASS, 1 findings, 2 analysis/I/O error.
Only --json writes a file. Requires numpy, scipy, ffmpeg and ffprobe.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
import numpy as np
from scipy.ndimage import median_filter

FPS, BLACK, FREEZE = 24.0, 16.0, 0.5
FF = ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-xerror"]
def run(cmd: list[str]) -> subprocess.CompletedProcess[bytes]:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(p.stderr.decode("utf-8", "replace")[-4000:])
    return p

def probe(path: str, extra: list[str]) -> dict:
    return json.loads(run(["ffprobe", "-v", "error", "-of", "json", *extra, path]).stdout)

def ranges(text: str) -> list[tuple[float, float]]:
    result = []
    for part in text.split(",") if text else []:
        m = re.fullmatch(r"\s*(\d+(?:\.\d*)?)\s*-\s*(\d+(?:\.\d*)?)\s*", part)
        if not m:
            raise argparse.ArgumentTypeError("Use START-END[,START-END], in seconds")
        a, b = map(float, m.groups())
        if not math.isfinite(b) or not 0 <= a < b:
            raise argparse.ArgumentTypeError("Ranges must be finite and 0 <= START < END")
        result.append((a, b))
    return sorted(result)

def number(s: dict, key: str) -> float:
    x = float(s[key])
    if not math.isfinite(x):
        raise ValueError(f"Invalid {key}: {s[key]}")
    return x

def segments(mask: list[bool], t: np.ndarray, end: np.ndarray, pair: bool) -> list[dict]:
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False].astype(np.int8)))
    return [{"start_s": float(t[a - int(pair)]), "end_s": float(end[b - 1]),
             "first_frame": int(a - int(pair)), "last_frame": int(b - 1),
             "frames": int(b - a + int(pair))} for a, b in edges.reshape(-1, 2)]

def video(path: str, t: np.ndarray, end: np.ndarray,
          intended: list[tuple[float, float]]) -> tuple[list[dict], list[dict], int]:
    cmd = [*FF, "-v", "error", "-noautorotate", "-i", path, "-map", "0:v:0",
           "-an", "-vf", "scale=160:90:flags=area:out_range=full,format=gray",
           "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)  # stderr inherited: no pipe deadlock
    black, frozen, previous, previous_ok, n = [], [], None, False, 0
    try:
        assert p.stdout is not None
        while raw := p.stdout.read(160 * 90):
            if len(raw) != 160 * 90 or n >= len(t):
                raise RuntimeError("Partial frame or decode/probe frame-count mismatch")
            frame = np.frombuffer(raw, dtype=np.uint8).astype(np.int16)
            ok = not any(a <= t[n] < b for a, b in intended)
            black.append(bool(ok and frame.mean() < BLACK))
            frozen.append(bool(ok and previous_ok and previous is not None
                               and np.abs(frame - previous).mean() < FREEZE))
            previous, previous_ok, n = frame, ok, n + 1
        if p.wait() or n != len(t):
            raise RuntimeError("Video decoding failed or frame counts disagree")
    finally:
        p.stdout.close()
        if p.poll() is None:
            p.kill()
        p.wait()
    return segments(black, t, end, False), segments(frozen, t, end, True), n

def clicks(x: np.ndarray, rate: int, start: float) -> tuple[list[dict], int]:
    window = max(3, round(rate * 0.050) | 1)
    found, total = [], 0
    for ch in range(x.shape[1]):
        d = np.abs(np.diff(x[:, ch].astype(np.float64)))
        if not len(d):
            continue
        local = median_filter(d, size=window, mode="reflect")
        indices = np.flatnonzero(d > 12.0 * local)
        total += len(indices)
        # "Worst" = largest absolute jump; no silence floor changes the requested rule.
        if len(indices) > 20:
            indices = indices[np.argpartition(d[indices], -20)[-20:]]
        for i in indices:
            found.append({"time_s": float(start + (i + 1) / rate), "channel": ch + 1,
                          "sample": int(i + 1), "jump": float(d[i]),
                          "local_median": float(local[i]),
                          "ratio": float(d[i] / local[i]) if local[i] else "infinity"})
    return sorted(found, key=lambda v: v["jump"], reverse=True)[:20], int(total)

def audio(path: str, stream: dict, origin: float) -> tuple[dict, list[dict], int]:
    rate, channels = int(stream["sample_rate"]), int(stream["channels"])
    p = run([*FF, "-v", "info", "-i", path, "-map", "0:a:0", "-vn",
             "-af", "ebur128=peak=true:framelog=verbose",
             "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"])
    log = p.stderr.decode("utf-8", "replace")
    summary = log.rsplit("Summary:", 1)[-1]
    im = re.search(r"\bI:\s*([+-]?(?:\d+(?:\.\d*)?|inf))\s*LUFS", summary)
    pm = re.search(r"True peak:\s*Peak:\s*([+-]?(?:\d+(?:\.\d*)?|inf))", summary)
    if not im or not pm or not p.stdout or len(p.stdout) % (4 * channels):
        raise RuntimeError("Missing ebur128 summary or invalid decoded audio")
    tp = float(pm.group(1))
    upper = tp + 0.05  # ebur128 summary rounds to 0.1 dB; borderline is inconclusive.
    x = np.frombuffer(p.stdout, dtype="<f4").reshape(-1, channels)
    if not np.isfinite(x).all():
        raise RuntimeError("Non-finite decoded audio samples")
    first = probe(path, ["-select_streams", "a:0", "-read_intervals", "%+1",
                        "-show_frames", "-show_entries", "frame=best_effort_timestamp_time"])
    frames = first.get("frames", [])
    start = number(frames[0], "best_effort_timestamp_time") if frames else number(stream, "start_time")
    start -= origin
    detected, count = clicks(x, rate, start)
    metrics = {"start_s": start, "end_s": start + len(x) / rate,
               "integrated_lufs": float(im.group(1)), "true_peak_dbtp": tp,
               "true_peak_upper_bound_dbtp": upper, "measurement_resolution_db": 0.1}
    return metrics, detected, count

def clean(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--intended-black", type=ranges, default=[])
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = {"file": str(args.video), "intended_black": args.intended_black, "flags": []}
    flags = report["flags"]
    try:
        path = str(args.video.resolve(strict=True))
        if args.json and args.json.resolve() == args.video.resolve():
            raise ValueError("--json must not overwrite the input video")
        meta = probe(path, ["-show_format", "-show_streams"])
        report["metadata"] = meta
        streams = meta["streams"]
        videos = [s for s in streams if s["codec_type"] == "video"]
        audios = [s for s in streams if s["codec_type"] == "audio"]
        if len(videos) != 1 or len(audios) != 1:
            raise ValueError("Expected exactly one video stream and one audio stream")
        v, a = videos[0], audios[0]
        origin = number(meta["format"], "start_time")
        for s, expected in [(v, "h264"), (a, "aac")]:
            if s.get("codec_name") != expected:
                flags.append(f"Stream {s['index']} codec is not {expected}")
        for key, expected in [("color_primaries", "bt709"), ("color_transfer", "bt709"),
                              ("color_space", "bt709"), ("sample_aspect_ratio", "1:1"),
                              ("r_frame_rate", "24/1"), ("avg_frame_rate", "24/1")]:
            if v.get(key) != expected:
                flags.append(f"{key}={v.get(key, 'MISSING')}; expected {expected}")
        frames = probe(path, ["-select_streams", "v:0", "-show_frames", "-show_entries",
                             "frame=best_effort_timestamp_time,duration_time,pkt_duration_time"])["frames"]
        t = np.array([number(f, "best_effort_timestamp_time") - origin for f in frames])
        if not len(t) or np.any(np.diff(t) <= 0):
            raise ValueError("Missing or non-increasing video timestamps")
        vd, ad = number(v, "duration"), number(a, "duration")
        last = float(frames[-1].get("duration_time", frames[-1].get("pkt_duration_time", 1 / FPS)))
        end = np.r_[t[1:], t[-1] + (last if last > 0 else 1 / FPS)]
        black, frozen, count = video(path, t, end, args.intended_black)
        report.update(black=black, frozen=frozen, decoded_frames=count,
                      video_duration_s=vd, audio_duration_s=ad, expected_frames=vd * FPS)
        if abs(vd - ad) > 1 / FPS + 1e-6:
            flags.append("Video/audio stream durations differ by >1 frame")
        if abs(count - vd * FPS) > 0.001:
            flags.append("Decoded frame count differs from video duration *24")
        if "nb_frames" in v and int(v["nb_frames"]) != count:
            flags.append("Tagged nb_frames differs from decoded frame count")
        if np.any(np.abs(np.diff(t) - 1 / FPS) > 1e-5):
            flags.append("Decoded frame timestamps are not uniformly 24 fps")
        metrics, detected, click_count = audio(path, a, origin)
        report.update(audio=metrics, clicks=detected, click_candidates=click_count)
        if metrics["true_peak_dbtp"] > -1:
            flags.append("Decoded true peak >-1.0 dBTP")
        elif metrics["true_peak_upper_bound_dbtp"] > -1:
            flags.append("True peak is too close to -1.0 to certify from rounded ebur128 output")
        if black or frozen or click_count:
            flags.append(f"{len(black)} black runs; {len(frozen)} freeze runs; {click_count} click candidates")
        code = int(bool(flags))
    except (OSError, ValueError, RuntimeError, KeyError, IndexError) as exc:
        flags.append(f"Analysis error: {exc}")
        code = 2
    for key in ("metadata", "video_duration_s", "audio_duration_s", "decoded_frames", "expected_frames"):
        if key in report:
            print(f"{key}: {json.dumps(report[key], ensure_ascii=False)}")
    for kind in ("black", "frozen", "clicks"):
        for item in report.get(kind, []):
            print(f"{kind.upper()}: {json.dumps(item)}")
    if "audio" in report:
        print("AUDIO:", json.dumps(clean(report["audio"])))
    for flag in flags:
        print("FLAG:", flag)
    report["status"] = "PASS" if code == 0 else "FAIL"
    if args.json:
        try:
            args.json.write_text(json.dumps(clean(report), indent=2, allow_nan=False), encoding="utf-8")
        except OSError as exc:
            print(f"FLAG: JSON write failed: {exc}")
            code = 2
    print("PASS" if code == 0 else "FAIL")
    return code
if __name__ == "__main__":
    sys.exit(main())
