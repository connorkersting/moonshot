"""SDR/sRGB flash QC, using the requested W3C amplitude-based red rule.

    py flashqc2.py VIDEO [--json out.json] [--selftest]
    py flashqc2.py --selftest

General: opposing changes of >=0.10 in linear relative luminance (maximum
1.0), with the darker endpoint <0.80. Red: opposing changes strictly >20 in
max(R-G-B, 0)*320, with either endpoint saturated: R/(R+G+B) >=0.8. RGB here
is linearized sRGB. Each tracker retains the colour of its tracked extreme;
an ineligible intermediate state never discards that endpoint.

Reference: https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html
The current WCAG 2.2 explanatory note uses CIE UCS chromaticity distance
>0.2 for red. This tool deliberately implements the amplitude rule requested
by the caller, not that newer explanatory method.

Spatial assumption: full-screen 1920x1080 at a typical viewing distance,
using W3C's 341x256 rectangle on a 1024x768 reference display (15-17 inches,
22-26 inch viewing distance). Scale the axes independently: the approximate
10-degree field is 639.375x360 display pixels. Decode to 320x180 with area
resampling, and test EVERY placement of a 107x60 rectangle (rounded up from
106.5625x60). This is an SDR spatial approximation, not a physical display
measurement; resampling can suppress very small patterns. It assumes video
fills the reference display and does not implement the fine-pattern exception.

At each pixel, accepted transitions alternate. Adjacent opposing transitions
form pairs; two separate parity tracks cover both possible NON-overlapping
pair alignments. Pair masks combine brightening and darkening pixels BEFORE
area testing. Concurrency is sampled at decoded frame timestamps: a regional
pair event consists of pixels completing a pair at the same PTS. For each
sliding (end-1 second, end] window, filter each pair's pixels so BOTH
transitions lie in the window, then require strictly >25% combined area for
that event. Count qualifying events separately for each parity; never add
overlapping pairs from the two parities. FAIL at >3 complete general OR red
flashes in any such window. Areas from separate times are never pooled.
There is no nominal-fps window or arbitrary two-frame event merge.

ffprobe's decoded frame PTS and count are used, including VFR. Missing,
duplicate or decreasing timestamps fail. ffprobe errors, advertised count/
duration inconsistencies, empty scans, partial raw frames, decoder errors
and scan/probe count mismatches all FAIL with a nonzero CLI exit. A physically
truncated file is rejected when its container/decoder/count/duration exposes
the truncation; a valid file rewritten to describe only a prefix cannot reveal
the length of a formerly longer source. No PASS is a universal safety claim.
Dependencies: Python stdlib, numpy, ffmpeg and ffprobe on PATH.
"""

import argparse
import json
import math
import subprocess
import sys
import tempfile
from collections import deque
from contextlib import closing
from fractions import Fraction
from pathlib import Path

import numpy as np


def selftest() -> dict:
    """Real encoded fixtures; keep clips and CLI reports in the system temp dir.

    These catch lost red endpoints, split-polarity area, transition/pair
    confusion, nominal-fps windows, and successful-prefix decode certification.
    """
    tmp = Path(tempfile.mkdtemp(prefix="flashqc2_"))
    print(f"Self-test clips: {tmp}", flush=True)
    results = []

    def full(value):
        return np.broadcast_to(np.array(value, dtype=np.uint8), (180, 320, 3)).copy()

    def clip(name, fn, count=72, vfr=False):
        path = tmp / f"{name}.mp4"
        # RGB lossless H.264 keeps the six-state red regression exact. Faststart
        # leaves the sample table readable after truncating the media tail.
        command = ["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-y",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "320x180",
                   "-r", "24", "-i", "pipe:0", "-an"]
        if vfr:
            # Four cycles' eight transitions lie in <1 real second, though
            # their nominal 24-fps frame indices span >1 second.
            command += ["-vf", "settb=1/2400,setpts=if(lt(N\\,36)\\,N*40\\,1440+(N-36)*200)",
                        "-fps_mode", "vfr", "-enc_time_base", "1:2400"]
        command += ["-c:v", "libx264rgb", "-crf", "0", "-preset", "ultrafast",
                    "-movflags", "+faststart", str(path)]
        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=err)
            try:
                for index in range(count):
                    proc.stdin.write(np.asarray(fn(index), dtype=np.uint8).tobytes())
                proc.stdin.close()
                code = proc.wait()
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
            err.seek(0)
            message = err.read().decode("utf-8", "replace").strip()
        if code or message:
            raise RuntimeError(f"Self-test encoder failed ({code}): {message}")
        return path

    def bands(index):
        image = full(128)
        rows = np.arange(180) % 30
        a, b = (235, 20) if (index // 3) % 2 else (20, 235)
        image[rows < 6] = a
        image[(rows >= 6) & (rows < 12)] = b
        return image

    red_states = [(125, 0, 0), (125, 0, 0), (125, 65, 0),
                  (0, 87, 0), (125, 65, 0), (125, 0, 0)]
    cases = [
        ("flash4hz_full", lambda i: full(235 if (i // 3) % 2 else 20), "FAIL", "general", False),
        ("static", lambda i: full(128), "PASS", None, False),
        ("flash2hz_full", lambda i: full(235 if (i // 6) % 2 else 20), "PASS", None, False),
        ("red_green_six_states", lambda i: full(red_states[i % 6]), "FAIL", "red", False),
        ("opposite_phase_20_plus_20", bands, "FAIL", "general", False),
        ("vfr_compressed_flashes", lambda i: full(235 if (i // 4) % 2 else 20), "FAIL", "general", True),
        # Seven opposing transitions in <1 s are only three complete pairs.
        ("seven_transitions", lambda i: full(235 if (i // 3) % 2 else 20), "PASS", None, False),
    ]
    for name, fn, expected, kind, vfr in cases:
        path = clip(name, fn, count=24 if name == "seven_transitions" else 72, vfr=vfr)
        report = analyze(path, quiet=True)
        passed = report["verdict"] == expected and not report["errors"]
        if kind:
            passed = passed and any(item["kind"] == kind for item in report["fail"])
        results.append({"name": name, "expected": expected, "actual": report["verdict"],
                        "ok": bool(passed), "errors": report["errors"]})
        print(f"  {name}: expected {expected}, got {report['verdict']} "
              f"{'OK' if passed else 'MISMATCH'}", flush=True)

    original = clip("truncate_source", lambda i: np.random.default_rng(i).integers(
        0, 256, size=(180, 320, 3), dtype=np.uint8))
    truncated = tmp / "truncated.mp4"
    data = original.read_bytes()
    truncated.write_bytes(data[:len(data) // 2])
    output = tmp / "truncated_report.json"
    # Check the actual CLI exit status as well as the failure report.
    run = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()),
                          str(truncated), "--json", str(output)], capture_output=True, text=True)
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    passed = run.returncode != 0 and report.get("verdict") == "FAIL" and bool(report.get("errors"))
    results.append({"name": "truncated", "expected": "FAIL/nonzero", "actual": report.get("verdict"),
                    "exit_code": run.returncode, "ok": bool(passed), "stderr": run.stderr})
    print(f"  truncated: {report.get('verdict')}, exit {run.returncode} "
          f"{'OK' if passed else 'MISMATCH'}", flush=True)
    empty = tmp / "empty.mp4"
    empty.write_bytes(b"")
    report = analyze(empty, quiet=True)
    passed = report["verdict"] == "FAIL" and bool(report["errors"]) and report["frames"] == 0
    results.append({"name": "empty", "expected": "FAIL", "actual": report["verdict"],
                    "ok": bool(passed), "errors": report["errors"]})
    print(f"  empty: {report['verdict']} {'OK' if passed else 'MISMATCH'}", flush=True)
    passed = all(item["ok"] for item in results)
    print("SELFTEST PASS" if passed else "SELFTEST FAIL", flush=True)
    return {"verdict": "PASS" if passed else "FAIL", "directory": str(tmp), "tests": results}


WS, HS = 320, 180
RW, RH = math.ceil(WS * 341 / 1024), math.ceil(HS * 256 / 768)
AREA = 0.25
TIME_EPS = 1e-9
L_WEIGHTS = np.array([0.2126, 0.7152, 0.0722])
_SRGB = np.arange(256, dtype=np.float64) / 255.0
LINEAR = np.where(_SRGB <= 0.04045, _SRGB / 12.92, ((_SRGB + 0.055) / 1.055) ** 2.4)


class QCError(RuntimeError):
    """An input/decoder failure must never become a successful QC result."""


def _integer(value):
    return None if value in (None, "N/A", "") else int(value)


def probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_frames", "-show_streams", "-show_entries",
               "stream=width,height,nb_frames,nb_read_frames,time_base,start_pts,duration_ts,color_transfer:"
               "frame=pts,best_effort_timestamp,pkt_duration,duration", "-of", "json", str(path)]
    run = subprocess.run(command, capture_output=True, text=True)
    if run.returncode or run.stderr.strip():
        raise QCError(f"ffprobe failed ({run.returncode}): {run.stderr.strip()}")
    data = json.loads(run.stdout)
    streams, records = data.get("streams", []), data.get("frames", [])
    if len(streams) != 1 or not records:
        raise QCError("No decoded video frames in probe")
    stream = streams[0]
    time_base = Fraction(stream["time_base"])
    if time_base <= 0:
        raise QCError("Invalid video time base")
    if stream.get("color_transfer") in ("smpte2084", "arib-std-b67"):
        raise QCError("HDR transfer function requires an HDR luminance analysis; this scanner assumes SDR/sRGB")
    times, durations = [], []
    for index, frame in enumerate(records):
        # These are timestamps of decoded frames, not packet DTS or index/fps.
        pts = _integer(frame.get("pts", frame.get("best_effort_timestamp")))
        if pts is None:
            raise QCError(f"Missing decoded PTS at frame {index}")
        timestamp = pts * time_base
        if times and timestamp <= times[-1]:
            raise QCError(f"Non-increasing decoded PTS at frame {index}")
        times.append(timestamp)
        duration = _integer(frame.get("duration", frame.get("pkt_duration")))
        durations.append(duration * time_base if duration is not None and duration > 0 else None)
    count = len(times)
    read_count = _integer(stream.get("nb_read_frames"))
    declared_count = _integer(stream.get("nb_frames"))
    if read_count is None or read_count != count:
        raise QCError(f"Probe frame count inconsistent: nb_read_frames={read_count}, PTS count={count}")
    if declared_count is not None and declared_count != count:
        raise QCError(f"Short/truncated probe: container declares {declared_count} frames, decoded {count}")
    start = _integer(stream.get("start_pts"))
    length = _integer(stream.get("duration_ts"))
    if length is not None and length > 0:
        expected_end = (start * time_base if start is not None else times[0]) + length * time_base
        last_duration = durations[-1]
        known_last_duration = last_duration is not None
        if last_duration is None and count > 1:
            last_duration = times[-1] - times[-2]
        if last_duration is None:
            raise QCError("Cannot verify the duration of a single-frame stream")
        # Exact packet/frame duration permits a tight check. With an unknown
        # final duration, allow one last observed frame interval, not a tail
        # of arbitrary length. This protects containers without nb_frames.
        tolerance = max(time_base * 2, Fraction(1, 1000))
        if not known_last_duration:
            tolerance = max(tolerance, last_duration)
        actual_end = times[-1] + last_duration
        if abs(expected_end - actual_end) > tolerance:
            raise QCError(f"Short/truncated or inconsistent stream duration: expected end "
                          f"{float(expected_end):.6f}, decoded end {float(actual_end):.6f}")
    return {"count": count, "times": times, "time_base": time_base,
            "declared_count": declared_count, "width": stream.get("width"),
            "height": stream.get("height")}


def frames(path: Path, expected_count: int):
    """Yield all frames; validate process status and completeness at EOF."""
    command = ["ffmpeg", "-hide_banner", "-v", "error", "-xerror", "-err_detect", "explode",
               "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
               "-vf", f"scale={WS}:{HS}:flags=area", "-fps_mode", "passthrough",
               "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    size, count, partial = WS * HS * 3, 0, 0
    # Spool stderr instead of using an undrained PIPE (which can deadlock).
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err)
        try:
            while True:
                buf = bytearray()
                while len(buf) < size:
                    block = proc.stdout.read(size - len(buf))
                    if not block:
                        break
                    buf.extend(block)
                if len(buf) != size:
                    partial = len(buf)
                    break
                count += 1
                if count > expected_count:
                    raise QCError(f"Decoder emitted more than the {expected_count} probed frames")
                yield np.frombuffer(buf, np.uint8).reshape(HS, WS, 3)
            proc.stdout.close()
            code = proc.wait()
            err.seek(0)
            message = err.read().decode("utf-8", "replace").strip()
            if code or message or partial or not count or count != expected_count:
                raise QCError(f"Incomplete decode: exit={code}, scanned={count}, probed={expected_count}, "
                              f"partial_frame_bytes={partial}; {message}")
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.kill()
                proc.wait()


def saturated(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] / np.maximum(rgb.sum(axis=2), 1e-12) >= 0.8


class Tracker:
    """Per-pixel hysteresis, retaining the RGB endpoint used for amplitude."""

    def __init__(self, kind: str):
        self.kind = kind
        self.ext = self.rgb = self.direction = None

    def update(self, rgb: np.ndarray) -> np.ndarray:
        value = (rgb @ L_WEIGHTS if self.kind == "general" else
                 np.maximum(rgb[..., 0] - rgb[..., 1] - rgb[..., 2], 0.0) * 320.0)
        if self.ext is None:
            self.ext, self.rgb = value.copy(), rgb.copy()
            self.direction = np.zeros(value.shape, np.int8)
            return self.direction.copy()
        follow = ((self.direction > 0) & (value > self.ext)) | ((self.direction < 0) & (value < self.ext))
        # At a flat extreme keep a saturated endpoint in preference to a
        # nonsaturated one with the very same scalar value.
        if self.kind == "red":
            follow |= (value == self.ext) & saturated(rgb) & ~saturated(self.rgb)
        self.ext[follow], self.rgb[follow] = value[follow], rgb[follow]
        delta = value - self.ext
        if self.kind == "general":
            eligible = (np.abs(delta) >= 0.10) & (np.minimum(self.ext, value) < 0.80)
        else:
            eligible = (np.abs(delta) > 20.0) & (saturated(self.rgb) | saturated(rgb))
        up = eligible & (delta > 0) & (self.direction <= 0)
        down = eligible & (delta < 0) & (self.direction >= 0)
        signs = up.astype(np.int8) - down.astype(np.int8)
        moved = up | down
        self.direction[moved] = signs[moved]
        self.ext[moved], self.rgb[moved] = value[moved], rgb[moved]
        # No reset for an ineligible intermediate colour/amplitude.
        return signs


def region_areas(mask: np.ndarray) -> np.ndarray:
    """Summed-area table: every overlapping 10-degree field, no sparse grid."""
    table = np.pad(mask.astype(np.int32), ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)
    return table[RH:, RW:] - table[:-RH, RW:] - table[RH:, :-RW] + table[:-RH, :-RW]


class FlashWindows:
    """Pixel-level opposing pairs, combined area, and real one-second windows."""

    def __init__(self, kind: str):
        self.kind = kind
        self.last_sign = np.zeros((HS, WS), np.int8)
        self.last_time = np.full((HS, WS), -np.inf)
        self.parity = np.zeros((HS, WS), bool)
        self.events = [deque(), deque()]
        self.maximum = {"flashes": 0, "region": None, "t": None}
        self.failures = []

    def update(self, signs: np.ndarray, timestamp: float, frame: int):
        moved = signs != 0
        if not moved.any():
            return
        paired = moved & (signs == -self.last_sign) & (self.last_sign != 0)
        left = timestamp - 1.0
        for phase in (0, 1):
            history = self.events[phase]
            while history and history[0][0] <= left + TIME_EPS:
                history.popleft()
            mask = paired & (self.parity == bool(phase))
            if not mask.any():
                continue
            # Copy the first-transition PTS before updating the pixel state.
            history.append((timestamp, mask, self.last_time.copy()))
            counts = np.zeros((HS - RH + 1, WS - RW + 1), np.int32)
            minimum_area = np.full(counts.shape, np.inf)
            for _, pixels, starts in history:
                # Both transitions must fall in this half-open one-second
                # window. Opposite polarities are united in 'pixels'.
                area = region_areas(pixels & (starts > left + TIME_EPS))
                qualifies = area > AREA * RW * RH
                counts += qualifies
                minimum_area = np.minimum(minimum_area, np.where(qualifies, area, np.inf))
            position = int(counts.argmax())
            y, x = np.unravel_index(position, counts.shape)
            flashes = int(counts[y, x])
            record = {"kind": self.kind, "region": [int(x), int(y), RW, RH],
                      "frame": frame, "t": timestamp, "window_start": left,
                      "window_end": timestamp, "flashes": flashes,
                      "transitions": flashes * 2, "pair_alignment": phase,
                      "minimum_combined_area_fraction": (float(minimum_area[y, x]) / (RW * RH)
                                                          if flashes else 0.0)}
            if flashes > self.maximum["flashes"]:
                self.maximum = record.copy()
            if flashes > 3:
                self.failures.append(record)
        self.last_sign[moved] = signs[moved]
        self.last_time[moved] = timestamp
        self.parity[moved] = ~self.parity[moved]


def analyze(path: Path, quiet: bool = False) -> dict:
    report = {"file": str(path), "frames": 0, "probed_frames": None,
              "verdict": "FAIL", "errors": [], "fail": [], "warn": [], "max": {},
              "method": {"timestamps": "ffprobe decoded frame PTS; VFR supported",
                         "red_rule": "linear RGB saturation >=0.8; max(R-G-B,0)*320 change >20",
                         "analysis_size": [WS, HS], "field_size": [RW, RH],
                         "reference_display": [1920, 1080], "display_field": [639.375, 360],
                         "area_threshold": ">25% combined concurrent pair area",
                         "frequency_threshold": ">3 nonoverlapping opposing pairs in 1 second",
                         "assumption": "full-screen SDR/sRGB at typical W3C viewing distance"}}
    trackers = {kind: Tracker(kind) for kind in ("general", "red")}
    windows = {kind: FlashWindows(kind) for kind in trackers}
    try:
        metadata = probe(path)
        report["probed_frames"] = metadata["count"]
        report["container_frames"] = metadata["declared_count"]
        report["source_size"] = [metadata["width"], metadata["height"]]
        report["start_pts_seconds"] = float(metadata["times"][0])
        # closing() ensures a consumer-side exception also terminates ffmpeg.
        with closing(frames(path, metadata["count"])) as decoded:
            for index, image in enumerate(decoded):
                report["frames"] = index + 1
                timestamp = float(metadata["times"][index])
                rgb = LINEAR[image]
                for kind, tracker in trackers.items():
                    windows[kind].update(tracker.update(rgb), timestamp, index)
        if report["frames"] != metadata["count"] or not report["frames"]:
            raise QCError("Empty scan or scanned/probed frame count mismatch")
    except (QCError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        report["errors"].append(str(error))
    for kind, counter in windows.items():
        report["max"][kind] = counter.maximum
        report["fail"].extend(counter.failures)
    report["verdict"] = "FAIL" if report["errors"] or report["fail"] else "PASS"
    if not quiet:
        print(f"{path.name}: scanned {report['frames']}, probed {report['probed_frames']} frames; "
              f"decoded-PTS windows, combined area in every {RW}x{RH} field")
        for error in report["errors"]:
            print(f"  ERROR: {error}")
        for kind in trackers:
            maximum = report["max"][kind]
            print(f"  max {kind}: {maximum['flashes']} complete flashes in 1 s")
        for event in report["fail"]:
            print(f"  FAIL {event['kind']} ({event['window_start']:.6f}, {event['window_end']:.6f}] "
                  f"region {event['region']}: {event['flashes']} flashes, minimum combined area "
                  f"{event['minimum_combined_area_fraction']:.1%}")
        print(report["verdict"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", nargs="?", type=Path)
    parser.add_argument("--json", type=Path, dest="json_path")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    result, status = None, 0
    if args.selftest or args.video is None:
        try:
            result = selftest()
            status = 1 if result["verdict"] == "FAIL" else 0
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            print(f"SELFTEST FAIL: {error}", file=sys.stderr)
            result, status = {"verdict": "FAIL", "errors": [str(error)]}, 1
    if args.video is not None:
        report = analyze(args.video)
        if result is not None:
            report["selftest"] = result
            if status:
                report["verdict"] = "FAIL"
                report["errors"].append("Self-test failed")
                print("FAIL (self-test failed)")
        result = report
        status = 1 if report["verdict"] == "FAIL" else 0
    if args.json_path is not None:
        try:
            args.json_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"FAIL: could not write JSON: {error}", file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
