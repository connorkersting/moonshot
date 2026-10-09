"""Render an aligned, labelled supercut; use --selftest without ffmpeg."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch


FPS = 24
CROSSFADE_FRAMES = 4
TITLE_SECONDS = 2
# The v8 edit removes 6.7 seconds from the middle. Moments are expressed
# on the v8+ timeline; older sources need this offset from 33.3 seconds on.
VERSION_TIME_SHIFT = 6.7
SHIFT_START = 33.3
SHIFT_VERSION = 8
STATUSES = {"kept", "reverted", "not_best", "final", "ab_only"}


@dataclass(frozen=True)
class Score:
    """One critic score and its editing outcome."""

    overall: float | None
    status: str


@dataclass(frozen=True)
class MediaInfo:
    """The metadata needed for safe extraction."""

    duration: float
    has_audio: bool


@dataclass(frozen=True)
class Plan:
    """Commands run sequentially inside the temporary working directory."""

    commands: list[list[str]]
    duration: float


def positive_float(value: str) -> float:
    """Parse a finite positive number for argparse."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a number") from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("expected a finite positive number")
    return number


def nonnegative_float(value: str) -> float:
    """Parse a finite nonnegative number for argparse."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a number") from exc
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError(
            "expected a finite nonnegative number"
        )
    return number


def parse_moments(value: str) -> list[float]:
    """Parse comma-separated seconds, retaining the specified order."""
    return [nonnegative_float(part.strip()) for part in value.split(",")]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse inputs; self-tests do not require any external files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions-dir", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--moments", type=parse_moments,
                        default="13.4,44.8,56.2,64.5")
    parser.add_argument("--per-clip", type=positive_float, default=1.2)
    parser.add_argument("--font", type=Path, help="TTF used by drawtext")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--version-time-shift", type=nonnegative_float,
                        default=VERSION_TIME_SHIFT,
                        help="pre-v8 offset after 33.3s; use 0 to disable")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if not args.selftest:
        for option in ("versions_dir", "scores", "font", "out"):
            if getattr(args, option) is None:
                parser.error(f"--{option.replace('_', '-')} is required")
    if round(args.per_clip * FPS) <= CROSSFADE_FRAMES:
        parser.error("--per-clip must exceed the four-frame crossfade")
    return args


def version_number(value: str) -> int:
    """Accept CSV versions such as 7 or v7."""
    match = re.fullmatch(r"v?([1-9]\d*)", value.strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"Invalid version: {value!r}; expected 7 or v7")
    return int(match.group(1))


def read_scores(path: Path) -> dict[int, Score]:
    """Validate scores, accepting an empty overall as unavailable."""
    result: dict[int, Score] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        if not {"version", "overall", "status"} <= columns:
            raise ValueError("Scores CSV needs version,overall,status columns")
        for row in reader:
            version = version_number(row.get("version") or "")
            status = (row.get("status") or "").strip()
            raw_score = (row.get("overall") or "").strip()
            overall = float(raw_score) if raw_score else None
            if overall is not None and not math.isfinite(overall):
                raise ValueError(f"Non-finite score for v{version}")
            if status not in STATUSES or version in result:
                raise ValueError(
                    f"Invalid status or duplicate row for v{version}"
                )
            result[version] = Score(overall, status)
    return result


def discover_versions(directory: Path) -> list[tuple[int, Path]]:
    """Find existing sources and sort numerically, including numbering gaps."""
    if not directory.is_dir():
        raise ValueError(f"Not a versions directory: {directory}")
    result: list[tuple[int, Path]] = []
    for path in directory.iterdir():
        match = re.fullmatch(r"moonshot_v([1-9]\d*)\.mp4", path.name)
        if match is not None and path.is_file():
            result.append((int(match.group(1)), path.resolve()))
    if not result:
        raise ValueError(f"No moonshot_vN.mp4 files in {directory}")
    return sorted(result)


def aligned_time(moment: float, version: int, shift: float) -> float:
    """Map a v8+ timeline timestamp to an older source timestamp."""
    if version < SHIFT_VERSION and moment >= SHIFT_START:
        return moment + shift
    return moment


def filter_value(value: str) -> str:
    """Escape an option value through both FFmpeg filter parsing layers.

    Normalize path separators before calling this for a Windows font path.
    In particular C:/Fonts/font.ttf becomes C\\\\:/Fonts/font.ttf in the
    argument passed directly to subprocess (there is no shell parsing).
    """
    option = "".join(f"\\{char}" if char in "\\':" else char
                     for char in value)
    return "".join(f"\\{char}" if char in "\\'[],;" else char
                   for char in option)


def probe_command(path: Path) -> list[str]:
    """Create the metadata command independently of running it."""
    return ["ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,duration", "-of", "json",
            str(path)]


def probe_media(path: Path) -> MediaInfo:
    """Read duration and audio presence using ffprobe."""
    result = subprocess.run(probe_command(path), check=True,
                            capture_output=True, text=True)
    data = cast(dict[str, Any], json.loads(result.stdout))
    streams = data.get("streams", [])
    video = next((item for item in streams
                  if item.get("codec_type") == "video"), None)
    if video is None:
        raise ValueError(f"No video stream in {path}")
    duration = video.get("duration", data.get("format", {}).get("duration"))
    if duration in (None, "N/A"):
        duration = data.get("format", {}).get("duration")
    try:
        seconds = float(duration)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Cannot determine duration of {path}") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError(f"Invalid duration in {path}")
    return MediaInfo(seconds, any(item.get("codec_type") == "audio"
                                  for item in streams))


def intermediate_output(path: Path, frames: int) -> list[str]:
    """Keep all temporary video lossless and audio at 48 kHz stereo."""
    return ["-t", f"{frames / FPS:.9f}", "-frames:v", str(frames),
            "-r", str(FPS), "-fps_mode", "cfr", "-c:v", "ffv1",
            "-level", "3", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le",
            "-ar", "48000", "-ac", "2", str(path)]


def build_plan(
    args: argparse.Namespace,
    versions: list[tuple[int, Path]],
    scores: dict[int, Score],
    work: Path,
    metadata: dict[int, MediaInfo] | None = None,
) -> Plan:
    """Generate render, crossfade and final concat commands, without tools."""
    commands: list[list[str]] = []
    blocks: list[Path] = []
    clip_frames = round(args.per_clip * FPS)
    fade_seconds = CROSSFADE_FRAMES / FPS
    font = filter_value(args.font.resolve().as_posix())
    base = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y"]
    for version, _ in versions:
        if version not in scores:
            raise ValueError(f"Scores CSV has no row for v{version}")
        score = scores[version]
        overall = "n/a" if score.overall is None else f"{score.overall:.1f}"
        (work / f"label_v{version}.txt").write_text(
            f"v{version} · editor {overall} · {score.status}", encoding="utf-8"
        )
    for index, moment in enumerate(args.moments):
        title_text = work / f"title_{index}.txt"
        title_text.write_text(
            f"THE SAME {args.per_clip:g} SECONDS, {len(versions)} VERSIONS",
            encoding="utf-8",
        )
        title = work / f"title_{index}.mkv"
        title_filter = (
            f"drawtext=fontfile={font}:textfile={title_text.name}:"
            "expansion=none:fontcolor=white:fontsize=64:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        commands.append(base + [
            "-f", "lavfi", "-i", f"color=c=black:s=1920x1080:r={FPS}",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
            "-map", "0:v:0", "-map", "1:a:0", "-vf", title_filter,
        ] + intermediate_output(title, TITLE_SECONDS * FPS))
        blocks.append(title)
        previous: Path | None = None
        accumulated_frames = 0
        for version, source in versions:
            start = aligned_time(moment, version, args.version_time_shift)
            info = metadata.get(version) if metadata is not None else None
            if info is not None and start + clip_frames / FPS > info.duration:
                raise ValueError(
                    f"v{version}: moment {moment:g}s maps to {start:g}s; "
                    f"clip exceeds source duration {info.duration:g}s"
                )
            clip = work / f"moment_{index}_v{version}.mkv"
            command = base + ["-ss", f"{start:.9f}", "-i", str(source)]
            audio_map = "0:a:0"
            if info is not None and not info.has_audio:
                command += ["-f", "lavfi", "-i",
                            "anullsrc=r=48000:cl=stereo"]
                audio_map = "1:a:0"
            video_filter = (
                f"fps={FPS},scale=1920:1080:force_original_aspect_ratio="
                "decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,"
                "settb=1/24,setpts=PTS-STARTPTS,format=yuv420p,"
                f"drawtext=fontfile={font}:textfile=label_v{version}.txt:"
                "expansion=none:fontcolor=white:fontsize=42:"
                "box=1:boxcolor=black@0.75:boxborderw=18:x=64:y=h-110"
            )
            audio_filter = (
                "aresample=48000,aformat=channel_layouts=stereo,"
                f"apad,atrim=duration={clip_frames / FPS:.9f},"
                "asetpts=PTS-STARTPTS"
            )
            commands.append(command + [
                "-map", "0:v:0", "-map", audio_map, "-vf", video_filter,
                "-af", audio_filter,
            ] + intermediate_output(clip, clip_frames))
            if previous is None:
                previous = clip
                accumulated_frames = clip_frames
                continue
            merged = work / f"moment_{index}_through_v{version}.mkv"
            offset = (accumulated_frames - CROSSFADE_FRAMES) / FPS
            graph = (
                "[0:v]settb=1/24,setpts=PTS-STARTPTS[v0];"
                "[1:v]settb=1/24,setpts=PTS-STARTPTS[v1];"
                f"[v0][v1]xfade=transition=fade:duration={fade_seconds:.9f}:"
                f"offset={offset:.9f},format=yuv420p[v];"
                "[0:a]asetpts=PTS-STARTPTS[a0];"
                "[1:a]asetpts=PTS-STARTPTS[a1];"
                f"[a0][a1]acrossfade=d={fade_seconds:.9f}:c1=tri:c2=tri[a]"
            )
            accumulated_frames += clip_frames - CROSSFADE_FRAMES
            commands.append(base + [
                "-i", str(previous), "-i", str(clip), "-filter_complex", graph,
                "-map", "[v]", "-map", "[a]",
            ] + intermediate_output(merged, accumulated_frames))
            previous = merged
        if previous is not None:
            blocks.append(previous)
    # Basenames are generated here, so quotes and Windows drive letters never
    # enter the concat file. FFmpeg resolves entries relative to this file.
    concat_file = work / "concat.txt"
    concat_file.write_text("".join(f"file '{path.name}'\n" for path in blocks),
                           encoding="utf-8")
    commands.append(base + [
        "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264",
        "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-fps_mode", "cfr", "-af",
        "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
        "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
        "-f", "mp4", str(args.out.resolve()),
    ])
    frames_per_moment = (TITLE_SECONDS * FPS + len(versions) * clip_frames
                         - (len(versions) - 1) * CROSSFADE_FRAMES)
    return Plan(commands, len(args.moments) * frames_per_moment / FPS)


def display_command(command: list[str]) -> str:
    """Print a platform-appropriate representation; never execute a shell."""
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def run(args: argparse.Namespace) -> None:
    """Validate inputs and render, or print commands without running tools."""
    versions = discover_versions(args.versions_dir)
    scores = read_scores(args.scores)
    if not args.font.is_file() or args.font.suffix.lower() != ".ttf":
        raise ValueError(f"--font must name an existing TTF: {args.font}")
    if args.out.resolve() in {path for _, path in versions}:
        raise ValueError("Output must not overwrite a source video")
    if args.out.exists() and not args.dry_run:
        raise ValueError(f"Output already exists: {args.out}")
    metadata: dict[int, MediaInfo] | None = None
    if args.dry_run:
        for _, source in versions:
            print(display_command(probe_command(source)))
    else:
        metadata = {
            version: probe_media(source) for version, source in versions
        }
    with tempfile.TemporaryDirectory(prefix="moonshot-supercut-") as name:
        work = Path(name)
        plan = build_plan(args, versions, scores, work, metadata)
        print(f"Duration: {plan.duration:.2f}s; {len(versions)} versions; "
              f"24 fps, {round(args.per_clip * FPS)} frames per clip")
        if args.dry_run:
            print(f"# Working directory: {work}")
            print("# Assumes each source has audio; no metadata was probed.")
            print("# Temporary labels and concat list are removed on exit.")
            for command in plan.commands:
                print(display_command(command))
        else:
            args.out.resolve().parent.mkdir(parents=True, exist_ok=True)
            for command in plan.commands:
                subprocess.run(command, cwd=work, check=True)
            print(f"Wrote {args.out.resolve()}")


def selftest() -> None:
    """Exercise parsing, time alignment and commands with fake media."""
    with tempfile.TemporaryDirectory(prefix="supercut-test-") as name:
        root = Path(name)
        versions = root / "versions"
        versions.mkdir()
        for version in (1, 7, 8, 10):
            (versions / f"moonshot_v{version}.mp4").write_bytes(b"fake")
        scores = root / "scores.csv"
        scores.write_text(
            "version,overall,status\n1,4.0,reverted\n7,6.5,kept\n"
            "8,7.0,not_best\n10,8.0,final\n", encoding="utf-8"
        )
        font = root / "font.ttf"
        font.write_bytes(b"fake")
        args = parse_args([
            "--versions-dir", str(versions), "--scores", str(scores),
            "--font", str(font), "--out", str(root / "out.mp4"),
            "--dry-run",
        ])
        assert args.moments == [13.4, 44.8, 56.2, 64.5]
        assert aligned_time(33.3, 7, 6.7) == 40.0
        assert aligned_time(33.3, 8, 6.7) == 33.3
        assert aligned_time(33.2, 1, 6.7) == 33.2
        assert aligned_time(44.8, 1, 0.0) == 44.8
        assert filter_value("C:/Fonts/test.ttf").startswith("C\\\\:")
        sources = discover_versions(versions)
        assert [number for number, _ in sources] == [1, 7, 8, 10]
        work = root / "work"
        work.mkdir()
        plan = build_plan(args, sources, read_scores(scores), work)
        commands = "\n".join(" ".join(cmd) for cmd in plan.commands)
        assert "xfade=transition=fade:duration=0.166666667" in commands
        assert "acrossfade=d=0.166666667" in commands
        assert "loudnorm=I=-14" in commands
        assert "-crf 18" in commands and "-c:a aac" in commands
        assert "51.500000000" in commands
        assert "THE SAME 1.2 SECONDS, 4 VERSIONS" in (
            work / "title_0.txt"
        ).read_text(encoding="utf-8")
        assert "v7 · editor 6.5 · kept" in (
            work / "label_v7.txt"
        ).read_text(encoding="utf-8")
        assert (work / "concat.txt").read_text().count("file '") == 8
        info = {number: MediaInfo(200.0, False) for number, _ in sources}
        silent_plan = build_plan(
            args, sources, read_scores(scores), work, info
        )
        silent_command = next(
            command for command in silent_plan.commands
            if command[-1].endswith("moment_0_v1.mkv")
        )
        assert "1:a:0" in silent_command
        assert "anullsrc=r=48000:cl=stereo" in silent_command
        try:
            build_plan(args, sources, read_scores(scores), work,
                       {1: MediaInfo(1.0, True)})
        except ValueError as exc:
            assert "exceeds source duration" in str(exc)
        else:
            raise AssertionError("Accepted a moment beyond its source")
        single_plan = build_plan(args, sources[:1], read_scores(scores), work)
        assert all("xfade=" not in " ".join(command)
                   for command in single_plan.commands)
        # Restore the full preview inputs before testing its CLI execution.
        build_plan(args, sources, read_scores(scores), work)
        with patch("subprocess.run", side_effect=AssertionError("ran tool")):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                run(args)
        assert "ffmpeg" in output.getvalue()
        assert "ffprobe" in output.getvalue()
        assert not (root / "out.mp4").exists()
        assert parse_args(["--selftest"]).selftest
        with contextlib.redirect_stderr(io.StringIO()):
            for bad in ("nan", "-1", ""):
                try:
                    parse_args(["--moments", bad, "--selftest"])
                except SystemExit:
                    pass
                else:
                    raise AssertionError(f"Accepted invalid moments: {bad}")
    print("supercut selftest: PASS")


def main() -> None:
    """CLI entry point with concise input and subprocess errors."""
    args = parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            run(args)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"supercut: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
