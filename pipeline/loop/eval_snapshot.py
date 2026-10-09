"""Freeze MOONSHOT evaluation inputs: py eval_snapshot.py N [--force].

Evidence copies live below qc/vN/snapshot_evidence in a unique directory.
Consumers must use snapshot.json's tables and copied paths when re-scoring.
Missing final tags are explicitly recorded, never replaced with HEAD.
The offline --selftest requires neither git nor ffmpeg.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import types
import uuid
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.dont_write_bytecode = True

WORK = Path(__file__).resolve().parent
EXPORTS = WORK.parents[2] / "exports" / "moonshot"
TABLE_NAMES = ("SHOTS", "CAPTIONS", "DIALOG")


def selftest() -> None:
    """Catch live-table leakage, damaged copies, and overwrite regressions."""
    with tempfile.TemporaryDirectory(prefix="snapshot-test-") as folder:
        base = Path(folder)
        work = base / "work"
        exports = base / "exports"
        work.mkdir()
        video = exports / "versions" / "moonshot_v7.mp4"
        video.parent.mkdir(parents=True)
        video.write_bytes(b"abc")
        source = work / "build.py"
        source.write_text(
            "from __future__ import annotations\n"
            "import sys\n"
            "from dataclasses import dataclass\n"
            "from pathlib import Path\n"
            "VERSION = int(sys.argv[2])\n"
            "@dataclass\n"
            "class Shot:\n"
            "    t0: float\n"
            "    img: Path\n"
            "SHOTS = [Shot(2.0, Path('moon.jpg'))]\n"
            "CAPTIONS = [(40.0, 41.0, 'EAGLE', 'Hello')]\n"
            "DIALOG = [(Path('speech.wav'), 0, 1, 33.3, 0)]\n"
            "if __name__ == '__main__':\n"
            "    raise RuntimeError('must not run the pipeline')\n",
            encoding="utf-8",
        )
        qc = exports / "qc" / "v7"
        qc.mkdir(parents=True)
        (qc / "contact.jpg").write_bytes(b"original contact")
        (qc / "key_01.0.jpg").write_bytes(b"key")
        (qc / "k360_01.0.jpg").write_bytes(b"phone key")
        (qc / "audio_qc.md").write_text("original", encoding="utf-8")
        (qc / "trailer_metrics.json").write_text("{}", encoding="utf-8")
        argv, search_path = sys.argv[:], sys.path[:]
        with patch(__name__ + ".resolve_tag", return_value=("a" * 40, None)):
            manifest = create_snapshot(7, work, exports)
            assert manifest["sha256"] == (
                "ba7816bf8f01cfea414140de5dae2223b0"
                "0361a396177a9cb410ff61f20015ad"
            )
            assert manifest["commit"] == "a" * 40
            assert manifest["tables"]["SHOTS"][0]["t0"] == 2.0
            assert manifest["tables"]["SHOTS"][0]["img"] == "moon.jpg"
            assert manifest["tables"]["CAPTIONS"][0][0] == 40.0
            assert sys.argv == argv and sys.path == search_path
            saved = (qc / "snapshot.json").read_bytes()
            source.write_text("raise RuntimeError('bad import')\n")
            (qc / "contact.jpg").write_bytes(b"newer contact")
            try:
                create_snapshot(7, work, exports)
            except FileExistsError:
                pass
            else:
                raise AssertionError("Snapshot overwrite was accepted")
            assert (qc / "snapshot.json").read_bytes() == saved
            for name, evidence in manifest["evidence"].items():
                frozen = qc / evidence["path"]
                assert sha256(frozen) == evidence["sha256"]
                if name == "contact.jpg":
                    assert frozen.read_bytes() == b"original contact"
            forced = create_snapshot(7, work, exports, force=True)
            assert forced["tables"] is None
            assert forced["build_sha256"] == sha256(source)
            assert forced["tables_error"]
            written = json.loads((qc / "snapshot.json").read_text())
            assert written == forced
    print("eval_snapshot selftest passed: freeze, hashes, guard, fallback.")


def sha256(path: Path) -> str:
    """Hash a file without loading media into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_value(value: Any) -> Any:
    """Serialize paths, dataclass Shot objects, and nested table values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite table value")
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: json_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    raise TypeError(f"Unsupported table value: {type(value).__name__}")


def load_tables(source: Path, version: int) -> dict[str, Any]:
    """Exec build into a fresh registered namespace, never as __main__.

    Registration supports dataclasses with postponed annotations. Neutral
    argv prevents the caller's flags reaching build's VERSION expression.
    No render functions are invoked; work is on sys.path for local helpers.
    """
    name = f"_eval_build_{uuid.uuid4().hex}"
    module = types.ModuleType(name)
    module.__file__ = str(source)
    original_argv = sys.argv
    original_path = sys.path[:]
    bytecode = sys.dont_write_bytecode
    sys.modules[name] = module
    try:
        sys.dont_write_bytecode = True
        sys.argv = [str(source), "snapshot", str(version)]
        sys.path.insert(0, str(source.parent))
        code = compile(source.read_bytes(), str(source), "exec")
        exec(code, module.__dict__)
        return {
            key: json_value(module.__dict__[key]) for key in TABLE_NAMES
        }
    finally:
        sys.argv = original_argv
        sys.path[:] = original_path
        sys.dont_write_bytecode = bytecode
        sys.modules.pop(name, None)


def resolve_tag(work: Path, version: int) -> tuple[str | None, str | None]:
    """Resolve the final tag's commit; retain an explicit missing-tag error."""
    tag = f"v{version}-final"
    try:
        result = subprocess.run(
            ["git", "-C", str(work), "rev-parse", f"{tag}^{{commit}}"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        commit = result.stdout.strip()
        if not commit:
            raise ValueError(f"Empty commit for {tag}")
        return commit, None
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return None, f"Cannot resolve {tag}: {error}"


def evidence_files(qc: Path) -> list[Path]:
    """Select review evidence, excluding old snapshot directories."""
    selected = {
        path for pattern in (
            "contact.jpg", "key_*", "k360_*", "audio_qc.md",
            "*trailer*metrics*.json", "techqc.json", "qc.json",
            "spectrogram.png",
        )
        for path in qc.glob(pattern) if path.is_file()
    }
    return sorted(selected)


def create_snapshot(
    version: int, work: Path, exports: Path, force: bool = False,
) -> dict[str, Any]:
    """Copy evidence and publish its manifest after all hashes are known."""
    qc = exports / "qc" / f"v{version}"
    destination = qc / "snapshot.json"
    if destination.exists() and not force:
        raise FileExistsError(f"Snapshot exists: {destination}; use --force")
    video = exports / "versions" / f"moonshot_v{version}.mp4"
    video_hash = sha256(video)
    commit, tag_error = resolve_tag(work, version)
    source = work / "build.py"
    source_hash = sha256(source)
    tables: dict[str, Any] | None = None
    tables_error: str | None = None
    try:
        tables = load_tables(source, version)
        if sha256(source) != source_hash:
            raise RuntimeError("build.py changed while loading tables")
    except (Exception, SystemExit) as error:
        tables = None
        tables_error = f"{type(error).__name__}: {error}"
    qc.mkdir(parents=True, exist_ok=True)
    copies = qc / "snapshot_evidence" / uuid.uuid4().hex
    copies.mkdir(parents=True)
    evidence: dict[str, Any] = {}
    for path in evidence_files(qc):
        frozen = copies / path.name
        shutil.copyfile(path, frozen)
        evidence[path.name] = {
            "path": frozen.relative_to(qc).as_posix(),
            "sha256": sha256(frozen),
        }
    manifest: dict[str, Any] = {
        "version": version,
        "video": f"versions/{video.name}",
        "sha256": video_hash,
        "tag": f"v{version}-final",
        "commit": commit,
        "tag_error": tag_error,
        "tables": tables,
        "tables_source": str(source),
        "build_sha256": source_hash,
        "tables_error": tables_error,
        "time_coordinates": {
            "SHOTS": "real seconds", "DIALOG": "real seconds",
            "CAPTIONS": "as supplied (logical seconds in current build)",
        },
        "evidence": evidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    content = f"{json.dumps(manifest, indent=2, allow_nan=False)}\n"
    if force:
        staged = qc / f".snapshot-{uuid.uuid4().hex}.tmp"
        try:
            with staged.open("x", encoding="utf-8") as handle:
                handle.write(content)
            os.replace(staged, destination)
        finally:
            staged.unlink(missing_ok=True)
    else:
        with destination.open("x", encoding="utf-8") as handle:
            handle.write(content)
    return manifest


def main() -> None:
    """Run a version snapshot or the offline verification path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=int, nargs="?", metavar="N")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if args.version is None or args.version < 1:
        parser.error("N must be a positive version number")
    try:
        result = create_snapshot(args.version, WORK, EXPORTS, args.force)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Error: {error}\n")
    print(f"Snapshot: {EXPORTS / 'qc' / f'v{args.version}' / 'snapshot.json'}")
    if result["tables_error"]:
        print(f"Tables unavailable; build hash recorded: "
              f"{result['tables_error']}")
    if result["tag_error"]:
        print(f"Warning: {result['tag_error']}")


if __name__ == "__main__":
    main()
