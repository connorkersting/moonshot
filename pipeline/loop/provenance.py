"""Check visual provenance without importing or executing build.py.

Usage: python -B provenance.py [--version 16] [--selftest]
Only new report files are written. Edit the CSV template manually to verify
mission identities, source ranges and event order. This is visual QC, not a
licence audit of the music, fonts, audio or sound effects.
"""

from __future__ import annotations

import argparse
import ast
import csv
import math
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast


BASE = Path(__file__).resolve().parent
EXPORTS = BASE.parents[2] / "exports" / "moonshot"
FIELDS = (
    "source_key_or_file", "src_in_from", "src_in_to", "mission", "event",
    "nasa_id_or_url", "licence", "chronology_order", "verified_by", "notes",
)
ALLOW_LICENCES = {"public domain", "pd-usgov", "cc0", "pdm"}
Caption: TypeAlias = tuple[float, float, str, str]
Dialog: TypeAlias = tuple[str, float, float, float, float]
Window: TypeAlias = tuple[float, float, str]


@dataclass(frozen=True)
class Shot:
    t0: float
    t1: float
    src: str
    src_in: float = 0.0
    speed: float = 1.0
    img: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Tables:
    shots: list[Shot]
    sources: dict[str, str]
    captions: list[Caption]
    dialog: list[Dialog]
    total: float


def literal(node: ast.AST, names: dict[str, object]) -> object:
    """Evaluate only the small expression grammar used by the EDL tables."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name) and node.id in names:
        return names[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        values = [literal(item, names) for item in node.elts]
        return values if isinstance(node, ast.List) else tuple(values)
    if isinstance(node, ast.Dict):
        return {
            literal(key, names): literal(value, names)
            for key, value in zip(node.keys, node.values) if key is not None
        }
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -float(cast(float, literal(node.operand, names)))
    if isinstance(node, ast.BinOp):
        left = literal(node.left, names)
        right = literal(node.right, names)
        if isinstance(node.op, ast.Div) and isinstance(left, str):
            return f"{left.rstrip('/')}/{right}"
        a, b = float(cast(float, left)), float(cast(float, right))
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        if isinstance(node.op, ast.Mult):
            return a * b
        if isinstance(node.op, ast.Div):
            return a / b
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        if node.func.id == "Path" and len(node.args) == 1:
            return str(literal(node.args[0], names)).replace("\\", "/")
        if node.func.id == "Shot":
            fields = ("t0", "t1", "src", "src_in", "speed")
            values = {
                key: literal(value, names)
                for key, value in zip(fields, node.args)
            }
            for keyword in node.keywords:
                if keyword.arg in Shot.__dataclass_fields__:
                    values[keyword.arg] = literal(keyword.value, names)
            return Shot(**values)
    raise ValueError(f"Unsupported build table expression: {ast.dump(node)}")


def load_tables(path: Path) -> Tables:
    """Read named assignments; imports, functions and VERSION never execute."""
    if path.name.casefold() == ".env":
        raise ValueError("Refusing to read .env")
    names: dict[str, object] = {}
    wanted = {
        "ROOT", "INBOX", "WORK", "RST", "SRC", "SHOTS", "DIALOG",
        "CAPTIONS", "TOTAL",
    }
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and target.id in wanted:
            if value is not None:
                names[target.id] = literal(value, names)
    return Tables(
        cast(list[Shot], names["SHOTS"]),
        cast(dict[str, str], names["SRC"]),
        cast(list[Caption], names["CAPTIONS"]),
        cast(list[Dialog], names["DIALOG"]),
        float(cast(float, names["TOTAL"])),
    )


def logical_time(frame: int, version: int) -> float:
    return (frame + 161) / 24 if version >= 8 and frame >= 799 else frame / 24


def caption_real_time(logical: float, version: int) -> float:
    return logical - 6.7 if version >= 8 and logical >= 40.0 else logical


def graphics(version: int) -> list[Window]:
    """Logical mission windows transcribed from Gfx.draw in this build.

    Generic Moon distance and thrust statistics are not mission-specific.
    Update this explicit registry when graphics in build.py change.
    """
    speed_end = 33.3 if version >= 8 else 40.0
    return [
        (0.2, 3.9, "APOLLO 11 / LAUNCH COMPLEX 39A"),
        (8.4, 13.0, "APOLLO 11 / LAUNCH COMPLEX 39A"),
        (26.5, 27.25, "STAGE SEPARATION (Apollo 11 staging context)"),
        (round(29.8 * 24) / 24, speed_end, "Apollo 11 TLI speed"),
        (44.0, 47.0, "DAY 5 / JULY 20, 1969 / EAGLE DESCENT"),
        (47.2, 52.8, "Eagle 1202 program alarm / DSKY"),
        (55.6, 62.9, "Eagle fuel countdown / CONTACT"),
        (55.75, 62.9, "ALDRIN'S CALLOUTS"),
        (69.8, 73.6, "EARTHRISE / PHOTOGRAPHED FROM APOLLO 11"),
        (83.9, 85.5, "APOLLO 11 / JULY 16-24, 1969"),
    ]


def active_windows(
    shot: Shot, windows: list[Window], version: int,
) -> list[str]:
    """Use displayed frames, including the discontinuity at frame 799."""
    frames = range(round(shot.t0 * 24), round(shot.t1 * 24))
    times = [logical_time(frame, version) for frame in frames]
    return [
        f"logical {a:.3f}-{b:.3f}: {text}"
        for a, b, text in windows
        if any(a <= time < b for time in times)
    ]


def normal_file(value: str) -> str:
    return value.replace("\\", "/").casefold()


def source_span(shot: Shot) -> tuple[float, float]:
    """Conservatively cover nominal and frame-rounded source duration."""
    duration = max(
        shot.t1 - shot.t0,
        (round(shot.t1 * 24) - round(shot.t0 * 24)) / 24,
    )
    end = shot.src_in + duration * shot.speed
    return min(shot.src_in, end), max(shot.src_in, end)


def matching_rows(
    shot: Shot, sources: dict[str, str], rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    source = normal_file(sources.get(shot.src, shot.src))
    for row in rows:
        identity = normal_file(row["source_key_or_file"].strip())
        if shot.img:
            if identity == normal_file(shot.img):
                matches.append(row)
            continue
        identities = {normal_file(shot.src), source, source.rsplit('/', 1)[-1]}
        if identity not in identities:
            continue
        start, end = source_span(shot)
        if (float(row["src_in_from"]) - 1e-6 <= start
                and end <= float(row["src_in_to"]) + 1e-6):
            matches.append(row)
    return matches


def read_rows(path: Path) -> list[dict[str, str]]:
    if path.name.casefold() == ".env":
        raise ValueError("Refusing to read .env")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError(f"CSV columns must be: {', '.join(FIELDS)}")
        rows = list(reader)
    for number, row in enumerate(rows, 2):
        if any(value is None for value in row.values()) or None in row:
            raise ValueError(f"Malformed CSV row {number}")
        start, end = float(row["src_in_from"]), float(row["src_in_to"])
        valid = (
            math.isfinite(start) and math.isfinite(end) and 0 <= start <= end
        )
        if not valid:
            raise ValueError(f"Invalid source range at CSV row {number}")
        int(row["chronology_order"])
    return rows


def check(
    tables: Tables, rows: list[dict[str, str]], version: int,
    outro_start: float,
) -> tuple[list[str], list[str], list[str]]:
    hard: list[str] = []
    warnings: list[str] = []
    coverage: list[str] = []
    previous: tuple[int, str] | None = None
    for number, row in enumerate(rows, 2):
        if row["licence"].strip().casefold() not in ALLOW_LICENCES:
            hard.append(
                f"CSV row {number} ({row['source_key_or_file']}): disallowed "
                f"licence {row['licence']!r}."
            )
    captions = [
        (a, b, f"{speaker}: {text}" if speaker else text)
        for a, b, speaker, text in tables.captions
    ]
    ordered_shots = sorted(tables.shots, key=lambda item: item.t0)
    for index, shot in enumerate(ordered_shots):
        label = (
            f"Shot {index:02d}, real {shot.t0:.3f}-{shot.t1:.3f} ({shot.src})"
        )
        active = active_windows(shot, captions, version)
        gfx = active_windows(shot, graphics(version), version)
        matches = matching_rows(shot, tables.sources, rows)
        if not matches:
            hard.append(
                f"{label}: UNMATCHED; {shot.img or source_span(shot)}."
            )
            coverage.append(
                f"{label}: unmatched. Note: {shot.note or '(none)'}. "
                f"Active CAPTIONS: {'; '.join(active) or '(none)'}. "
                f"Graphics: {'; '.join(gfx) or '(none)'}"
            )
            continue
        if len(matches) > 1:
            warnings.append(
                f"{label}: ambiguous provenance ({len(matches)} rows)."
            )
        missions = sorted({row["mission"] for row in matches})
        events = sorted({row["event"] for row in matches})
        verifiers = sorted({row["verified_by"] for row in matches})
        coverage.append(
            f"{label}: mission={', '.join(missions)}; "
            f"event={', '.join(events)}; "
            f"verified_by={', '.join(verifiers)}. "
            f"Note: {shot.note or '(none)'}. "
            f"Active CAPTIONS: {'; '.join(active) or '(none)'}. "
            f"Graphics: {'; '.join(gfx) or '(none)'}"
        )
        unverified = any(
            row["verified_by"].strip().casefold() in {"", "unverified"}
            for row in matches
        )
        if unverified:
            warnings.append(f"{label}: provenance still unverified.")
        # All CAPTIONS in this trailer transcribe Apollo 11 mission dialogue.
        if any(m.strip().casefold() != "apollo 11" for m in missions):
            if active or gfx:
                warnings.append(
                    f"{label}: mission={', '.join(missions)} under Apollo 11 "
                    f"context. CAPTIONS: {'; '.join(active) or '(none)'}. "
                    f"Graphics: {'; '.join(gfx) or '(none)'}"
                )
        orders = {int(row["chronology_order"]) for row in matches}
        # Ignore pure graphic/blank inserts; generated depictions still count.
        if shot.src in {"BLACK", "WHITE", "INSERT"} or len(orders) != 1:
            continue
        if shot.t1 <= 10.6 or shot.t0 >= outro_start:
            continue
        order = next(iter(orders))
        if previous is not None and order < previous[0]:
            warnings.append(
                f"{label}: chronology goes backwards "
                f"{previous[0]} -> {order}; "
                f"previous: {previous[1]}."
            )
        previous = (order, label)
    return hard, warnings, coverage


def markdown(
    hard: list[str], warnings: list[str], coverage: list[str],
    version: int, outro_start: float,
) -> str:
    lines = [
        "# MOONSHOT visual provenance QC", "",
        f"Version timing model: v{version}. Hard failures: {len(hard)}. "
        f"Warnings: {len(warnings)}.", "",
        "Source ranges are inclusive and must cover the entire consumed clip. "
        "Image/sequence rows match the exact img filename or pattern; "
        "SEQ src_in is a frame number, not seconds.", "",
        "CAPTIONS are Apollo 11 mission dialogue. Non-Apollo 11 and generated "
        "visuals under that dialogue or mission graphics are review warnings, "
        "not automatic factual errors. Graphics registry: "
        "Gfx.draw in build.py. "
        "For v8+, logical = frame/24 before frame 799; afterwards "
        "logical = (frame + 161)/24.", "",
        f"Chronology exceptions (real seconds): 0-10.6 and {outro_start:.3f} "
        "through the end (outro). Blank and graphic inserts do not advance "
        "chronology. No footage identity was independently verified here.", "",
        "This report covers SHOTS visual assets only; the allow-list does not "
        "clear the soundtrack, fonts or other dependencies.", "",
    ]
    for title, items in (
        ("Hard failures", hard), ("Review warnings", warnings),
        ("Shot coverage and active captions", coverage),
    ):
        lines.extend([f"## {title}", ""])
        lines.extend(f"- {item.replace(chr(10), ' ')}" for item in items)
        if not items:
            lines.append("None.")
        lines.append("")
    return "\n".join(lines)


def write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


class ProvenanceTests(unittest.TestCase):
    def row(
        self, identity: str = "A", mission: str = "Apollo 11",
        order: int = 2, licence: str = "PD-USGov",
    ) -> dict[str, str]:
        return dict(zip(FIELDS, (
            identity, "10", "20", mission, "launch", "NASA ID", licence,
            str(order), "unverified", "fake row",
        )))

    def test_ranges_aliases_and_images(self) -> None:
        rows = [self.row("clip.mp4")]
        shot = Shot(12, 14, "A", 18, speed=1)
        matches = matching_rows(shot, {"A": "x/clip.mp4"}, rows)
        self.assertEqual(len(matches), 1)
        self.assertFalse(matching_rows(Shot(12, 14, "A", 19), {}, rows))
        self.assertFalse(matching_rows(Shot(12, 14, "A", 19),
                                       {"A": "x/clip.mp4"}, rows))
        self.assertEqual(len(matching_rows(
            Shot(1, 2, "STILL", img="a.jpg"), {}, [self.row("a.jpg")],
        )), 1)

    def test_hard_failures_and_mission_context(self) -> None:
        tables = Tables([Shot(40, 41, "A", 10), Shot(41, 42, "B")], {},
                        [(47, 48, "EAGLE", "Alarm")], [], 42)
        hard, warnings, coverage = check(
            tables, [self.row(mission="Apollo 6", licence="copyright")], 8, 63,
        )
        self.assertEqual(len(hard), 2)
        self.assertTrue(any("Apollo 6" in warning and "EAGLE: Alarm" in warning
                            for warning in warnings))
        self.assertEqual(len(coverage), 2)

    def test_frame_boundary_and_removed_interval(self) -> None:
        self.assertAlmostEqual(logical_time(798, 8), 33.25)
        self.assertEqual(logical_time(799, 8), 40)
        self.assertAlmostEqual(logical_time(799, 7), 799 / 24)
        self.assertAlmostEqual(caption_real_time(40, 8), 33.3)
        self.assertEqual(caption_real_time(40, 7), 40)
        self.assertFalse(active_windows(
            Shot(33, 33.5, "A"), [(34, 39, "removed")], 8,
        ))

    def test_chronology_exceptions_and_graphics(self) -> None:
        tables = Tables([
            Shot(0, 1, "A", 10), Shot(2, 3, "B", 10),
            Shot(11, 12, "A", 10), Shot(14, 15, "B", 10),
            Shot(63, 64, "B", 10),
        ], {}, [], [], 64)
        rows = [self.row(order=3), self.row("B", "Apollo 6", 1)]
        hard, warnings, _ = check(tables, rows, 8, 62.9)
        self.assertFalse(hard)
        self.assertEqual(sum("goes backwards" in w for w in warnings), 1)
        self.assertTrue(any("LAUNCH COMPLEX" in w for w in warnings))

    def test_safe_parser(self) -> None:
        self.assertAlmostEqual(literal(ast.parse(
            "(988.55 - 987.40) / 0.75", mode="eval",
        ).body, {}), 1.5333333333333)
        with self.assertRaises(ValueError):
            literal(ast.parse("open('.env')", mode="eval").body, {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, default=16)
    parser.add_argument("--build", type=Path, default=BASE / "build.py")
    parser.add_argument(
        "--csv", type=Path, default=BASE / "data/provenance.csv",
    )
    parser.add_argument("--report", type=Path,
                        default=EXPORTS / "qc/provenance_report.md")
    parser.add_argument(
        "--outro-start", type=float, default=62.9,
        help="Real outro start; set explicitly for older edits",
    )
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        loader = unittest.defaultTestLoader
        suite = loader.loadTestsFromTestCase(ProvenanceTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    try:
        tables = load_tables(args.build)
        hard, warnings, coverage = check(
            tables, read_rows(args.csv), args.version, args.outro_start,
        )
        write_new(args.report, markdown(
            hard, warnings, coverage, args.version, args.outro_start,
        ))
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        print(f"Provenance error: {error}", file=sys.stderr)
        return 1
    print(
        f"Wrote {args.report}; {len(hard)} hard failures, "
        f"{len(warnings)} warnings"
    )
    return 1 if hard else 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
