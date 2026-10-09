"""Build a self-contained offline comparison page for Moonshot proxies."""

from __future__ import annotations

import argparse
import contextlib
import csv
import html
import io
import json
import math
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path


VERSION_TIME_SHIFT = 6.7
SHIFT_START = 33.3
SHIFT_VERSION = 8
FPS = 24
STATUSES = {"kept", "reverted", "not_best", "final", "ab_only"}


@dataclass(frozen=True)
class Version:
    """Embedded data for one available proxy."""

    version: int
    overall: float | None
    status: str
    scores: dict[str, float | None]
    media: str
    notes: str


@dataclass(frozen=True)
class Verdict:
    """A comparison identified explicitly by its two version numbers."""

    comparison: str
    pair: list[int]
    section: str
    picked_version: int | None
    confidence: str


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse build inputs; --selftest requires no other arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proxies-dir", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--notes-dir", type=Path)
    parser.add_argument("--ab", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--version-time-shift", type=float,
                        default=VERSION_TIME_SHIFT,
                        help="pre-v8 offset after 33.3s (default: 6.7)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if not args.selftest:
        for option in ("proxies_dir", "scores", "out_dir"):
            if getattr(args, option) is None:
                parser.error(f"--{option.replace('_', '-')} is required")
    if (not math.isfinite(args.version_time_shift)
            or args.version_time_shift < 0):
        parser.error("--version-time-shift must be finite and nonnegative")
    return args


def version_number(value: str) -> int:
    """Read a positive numeric version, optionally prefixed with v."""
    match = re.fullmatch(r"v?([1-9]\d*)", value.strip(), re.IGNORECASE)
    if match is None:
        raise ValueError(f"Invalid version: {value!r}; expected 7 or v7")
    return int(match.group(1))


def numeric_score(value: str) -> float | None:
    """An empty score stays unavailable rather than becoming zero."""
    if not value.strip():
        return None
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Non-finite score: {value!r}")
    return number


def load_versions(
    args: argparse.Namespace,
) -> tuple[list[Version], list[str], dict[int, Path]]:
    """Join numerically sorted proxies to scores and optional notes."""
    if not args.proxies_dir.is_dir():
        raise ValueError(f"Not a proxies directory: {args.proxies_dir}")
    if args.notes_dir is not None and not args.notes_dir.is_dir():
        raise ValueError(f"Not a notes directory: {args.notes_dir}")
    proxies: dict[int, Path] = {}
    for path in args.proxies_dir.iterdir():
        match = re.fullmatch(r"moonshot_v([1-9]\d*)_480p\.mp4", path.name)
        if match is not None and path.is_file():
            proxies[int(match.group(1))] = path.resolve()
    if not proxies:
        raise ValueError("No moonshot_vN_480p.mp4 files found")
    versions: dict[int, Version] = {}
    seen: set[int] = set()
    with args.scores.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if not {"version", "overall", "status"} <= set(columns):
            raise ValueError("Scores CSV needs version,overall,status columns")
        categories = [name for name in columns
                      if name not in {"version", "overall", "status"}]
        if len(categories) != 10 or len(set(columns)) != len(columns):
            raise ValueError(
                "Scores CSV must have ten distinct category columns"
            )
        for row in reader:
            number = version_number(row.get("version") or "")
            status = (row.get("status") or "").strip()
            if number in seen or status not in STATUSES:
                raise ValueError(
                    f"Duplicate version or invalid status: v{number}"
                )
            seen.add(number)
            category_scores = {category: numeric_score(row.get(category) or "")
                               for category in categories}
            overall = numeric_score(row.get("overall") or "")
            if number not in proxies:
                continue
            note = "No critic notes available."
            if args.notes_dir is not None:
                note_path = args.notes_dir / f"v{number}.md"
                if note_path.is_file():
                    note = note_path.read_text(encoding="utf-8-sig")
            versions[number] = Version(
                number, overall, status, category_scores,
                f"media/{proxies[number].name}", note,
            )
    missing = sorted(set(proxies) - set(versions))
    if missing:
        raise ValueError(f"Scores missing for proxy versions: {missing}")
    ordered = [versions[number] for number in sorted(versions)]
    return ordered, categories, proxies


def load_verdicts(path: Path | None) -> list[Verdict]:
    """Accept comparisons such as v1_vs_v8 or 1 vs 8, with optional ties."""
    if path is None:
        return []
    result: list[Verdict] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"comparison", "section", "picked_version", "confidence"}
        if not required <= set(reader.fieldnames or []):
            columns = ', '.join(sorted(required))
            raise ValueError(f"A/B CSV needs columns: {columns}")
        for row in reader:
            comparison = (row.get("comparison") or "").strip()
            pair = [int(number) for number in re.findall(r"\d+", comparison)]
            if len(pair) != 2 or min(pair) < 1 or pair[0] == pair[1]:
                raise ValueError(
                    f"Comparison must identify two versions: {comparison!r}"
                )
            raw_pick = (row.get("picked_version") or "").strip()
            picked = (None if raw_pick.lower() in {"", "tie", "none"}
                      else version_number(raw_pick))
            if picked is not None and picked not in pair:
                raise ValueError(f"Picked v{picked} is outside {comparison!r}")
            result.append(Verdict(
                comparison, pair, row.get("section") or "",
                picked, row.get("confidence") or "",
            ))
    return result


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Moonshot · version explorer</title>
<style>
:root { color-scheme:dark; --accent:#FFB040; --bg:#101216;
  --panel:#1b1e24; --muted:#abb1bc; --border:#363b44; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:#f0f1f3;
  font:16px/1.5 system-ui,sans-serif; }
main { max-width:1240px; padding:24px; margin:auto; }
h1 { margin:0; font-size:clamp(24px,4vw,38px); }
h2 { font-size:20px; margin:0 0 12px; }
p { margin:8px 0 16px; }
.muted, small { color:var(--muted); }
.players, .notes { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
article, section { min-width:0; background:var(--panel); padding:16px;
  border:1px solid var(--border); border-radius:12px; margin-bottom:16px; }
label { display:block; }
select, button { font:inherit; background:#282d35; color:inherit;
  border:1px solid var(--border); border-radius:6px; padding:8px 12px; }
select { width:100%; margin:8px 0 12px; }
button { cursor:pointer; min-height:44px; }
button:disabled { opacity:.5; cursor:wait; }
button:hover, button:focus-visible, select:focus-visible { border-color:var(--accent); }
button:focus-visible, input:focus-visible, [tabindex]:focus-visible {
  outline:2px solid var(--accent); outline-offset:3px; }
video { width:100%; aspect-ratio:16/9; background:black; display:block; }
.controls { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
#scrub { width:100%; margin:16px 0; accent-color:var(--accent); }
#time { font-variant-numeric:tabular-nums; }
.toggle { margin-top:14px; display:flex; align-items:center; gap:8px; }
input[type=checkbox] { accent-color:var(--accent); width:18px; height:18px; }
.table-wrap { overflow:auto; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
td, th { text-align:right; padding:9px 10px; border-bottom:1px solid var(--border); }
th:first-child, td:first-child { text-align:left; overflow-wrap:anywhere; }
.positive { color:var(--accent); } .negative { color:#ed9b9b; }
pre { font:inherit; white-space:pre-wrap; overflow-wrap:anywhere; margin:0; }
#chart { width:100%; height:auto; display:block; }
#chart text { fill:var(--muted); font:13px system-ui,sans-serif; }
#chart polyline { fill:none; stroke:var(--accent); stroke-width:2; }
#chart circle { fill:var(--accent); cursor:pointer; }
#chart .hit { fill:transparent; stroke:none; }
#chart [aria-pressed=true] circle { stroke:white; stroke-width:2; }
#error { color:#ed9b9b; min-height:24px; margin:8px 0 0; }
ul { padding-left:20px; } li { margin:8px 0; overflow-wrap:anywhere; }
@media (max-width:650px) {
  main { padding:12px; } .players, .notes { grid-template-columns:1fr; gap:0; }
  article, section { padding:12px; } td, th { padding:8px 5px; font-size:14px; }
}
</style>
</head>
<body><main>
<h1>Moonshot <span class="muted">/ version explorer</span></h1>
<p class="muted">Compare the same moment across edits. Everything stays offline.</p>
<div class="players">
<article><label for="left-version">Left version</label>
<select id="left-version">__OPTIONS__</select>
<video id="left-video" preload="metadata" playsinline aria-label="Left edit"></video>
<small id="left-source">Loading…</small></article>
<article><label for="right-version">Right version</label>
<select id="right-version">__OPTIONS__</select>
<video id="right-video" preload="metadata" playsinline muted aria-label="Right edit"></video>
<small id="right-source">Loading…</small></article>
</div>
<section aria-label="Shared playback controls">
<div class="controls">
<button id="play" disabled>Play</button>
<button id="back" disabled aria-label="Back one frame">← Frame</button>
<button id="forward" disabled aria-label="Forward one frame">Frame →</button>
<output id="time">0.000 / 0.000 s</output>
</div>
<label for="scrub">Shared timeline (v8+ seconds when alignment is on)</label>
<input id="scrub" type="range" min="0" max="0" step="0.041666667" value="0" disabled>
<label class="toggle"><input id="shift" type="checkbox" checked>
Align pre-v8 edits at 33.3 s (+<span id="shift-amount"></span> s)</label>
<label for="audio">Listen to</label><select id="audio">
<option value="0">Left audio</option><option value="1">Right audio</option>
<option value="none">Mute both</option></select>
<small>Space: play/pause · comma / period: one frame at 24 fps.</small>
<p id="error" role="status" aria-live="polite"></p>
</section>
<section><h2>Overall score by version</h2>
<p class="muted">Select a point to load that version on the left.</p>
<svg id="chart" viewBox="0 0 760 200" role="group" aria-label="Overall scores"></svg>
</section>
<section><h2>Score comparison</h2><p class="muted">Deltas = right minus left.</p>
<div class="table-wrap"><table><thead><tr><th scope="col">Category</th>
<th id="left-heading" scope="col">Left</th><th id="right-heading" scope="col">Right</th>
<th scope="col">Δ</th></tr></thead><tbody id="scores"></tbody></table></div></section>
<div class="notes">
<article><h2 id="left-notes-heading">Left critic notes</h2><pre id="left-notes"></pre></article>
<article><h2 id="right-notes-heading">Right critic notes</h2><pre id="right-notes"></pre></article>
</div>
<section><h2>A/B verdicts</h2><div id="verdicts"></div></section>
<noscript>This offline explorer requires JavaScript enabled in your browser.</noscript>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>
'use strict';
const data = JSON.parse(document.getElementById('data').textContent);
const byId = id => document.getElementById(id);
const videos = [byId('left-video'), byId('right-video')];
const pickers = [byId('left-version'), byId('right-version')];
const sides = ['left', 'right'];
const versions = new Map(data.versions.map(v => [v.version, v]));
const selected = [data.versions[0], data.versions[data.versions.length - 1]];
const ready = [false, false];
let time = 0, limit = 0, playing = false, starting = false;
let stamp = null, playToken = 0;
const mapped = (t, v) => byId('shift').checked && v.version < data.shiftVersion &&
  t >= data.shiftStart ? t + data.shift : t;
const logicalDuration = (duration, v) => {
  if (!byId('shift').checked || v.version >= data.shiftVersion) return duration;
  if (duration >= data.shiftStart + data.shift) return duration - data.shift;
  return Math.min(duration, data.shiftStart);
};
const available = () => ready.every(Boolean) && Number.isFinite(limit) && limit > 0;
function showError(message) { byId('error').textContent = message; }
function pause() {
  playing = false; starting = false; stamp = null; playToken++;
  videos.forEach(v => v.pause()); byId('play').textContent = 'Play';
}
function refreshControls() {
  limit = ready.every(Boolean) ? Math.min(...videos.map((v, i) =>
    logicalDuration(v.duration, selected[i]))) : 0;
  if (!Number.isFinite(limit)) limit = 0;
  time = Math.max(0, Math.min(time, limit));
  ['play', 'back', 'forward', 'scrub'].forEach(id => {
    byId(id).disabled = !available();
  });
  byId('scrub').max = limit;
  renderTime();
}
function renderTime() {
  byId('scrub').value = time;
  byId('time').textContent = `${time.toFixed(3)} / ${limit.toFixed(3)} s`;
  videos.forEach((v, i) => {
    byId(`${sides[i]}-source`).textContent =
      `v${selected[i].version} source: ${v.currentTime.toFixed(3)} s`;
  });
}
function seek(t) {
  time = Math.max(0, Math.min(t, limit));
  videos.forEach((v, i) => {
    if (ready[i]) v.currentTime = Math.min(mapped(time, selected[i]), v.duration);
  });
  stamp = null; renderTime();
}
async function play() {
  if (!available() || starting) return;
  if (time >= limit) seek(0);
  showError('');
  const token = ++playToken;
  starting = true; byId('play').textContent = 'Pause';
  try {
    await Promise.all(videos.map(v => v.play()));
    if (token !== playToken) return;
    starting = false;
    playing = true; stamp = null; byId('play').textContent = 'Pause';
  } catch (error) {
    if (token !== playToken) return;
    pause(); showError(`Playback could not start: ${error.message}`);
  }
}
function togglePlay() { if (playing || starting) pause(); else void play(); }
function step(direction) {
  if (!available()) return;
  pause(); seek((Math.round(time * data.fps) + direction) / data.fps);
}
function tick(now) {
  if (playing && available()) {
    const buffering = videos.some(v => v.readyState < 2 || v.seeking);
    if (!buffering && stamp !== null) time += (now - stamp) / 1000;
    stamp = now;
    if (time >= limit) { pause(); seek(limit); }
    else if (!buffering) {
      videos.forEach((v, i) => {
        const target = mapped(time, selected[i]);
        if (Math.abs(v.currentTime - target) > 0.075) v.currentTime = target;
      });
    }
    renderTime();
  }
  requestAnimationFrame(tick);
}
function textElement(tag, text) {
  const element = document.createElement(tag);
  element.textContent = text; return element;
}
const scoreText = value => value === null ? '—' : value.toFixed(1);
function renderComparison() {
  byId('scores').replaceChildren();
  sides.forEach((side, i) => {
    const v = selected[i];
    byId(`${side}-heading`).textContent = `v${v.version}`;
    byId(`${side}-notes-heading`).textContent = `v${v.version} critic notes`;
    byId(`${side}-notes`).textContent = v.notes;
  });
  ['overall', ...data.categories, 'status'].forEach(category => {
    const row = document.createElement('tr');
    const heading = textElement('th', category);
    heading.scope = 'row'; row.append(heading);
    const values = selected.map(v => category === 'overall' ? v.overall :
      category === 'status' ? v.status : v.scores[category]);
    values.forEach(value => row.append(textElement('td',
      category === 'status' ? value : scoreText(value))));
    let delta = '—', difference = null;
    if (category !== 'status' && values.every(v => v !== null)) {
      difference = values[1] - values[0];
      delta = `${difference > 0 ? '+' : ''}${difference.toFixed(1)}`;
    }
    const cell = textElement('td', delta);
    if (difference > 0) cell.className = 'positive';
    if (difference < 0) cell.className = 'negative';
    row.append(cell); byId('scores').append(row);
  });
  const pair = selected.map(v => v.version).sort((a, b) => a - b);
  const verdicts = data.ab.filter(v => {
    const numbers = [...v.pair].sort((a, b) => a - b);
    return pair[0] !== pair[1] && numbers[0] === pair[0] && numbers[1] === pair[1];
  });
  byId('verdicts').replaceChildren();
  if (!verdicts.length) {
    byId('verdicts').append(textElement('p', 'No A/B verdicts for this pair.'));
  } else {
    const list = document.createElement('ul');
    verdicts.forEach(v => list.append(textElement('li',
      `${v.comparison} · ${v.section} · ${v.picked_version === null ?
        'No preference' : `picked v${v.picked_version}`} · confidence: ${v.confidence}`)));
    byId('verdicts').append(list);
  }
  document.querySelectorAll('#chart [data-version]').forEach(point => {
    point.setAttribute('aria-pressed',
      Number(point.dataset.version) === selected[0].version ? 'true' : 'false');
  });
}
function load(side, number) {
  pause(); ready[side] = false;
  selected[side] = versions.get(number); pickers[side].value = number;
  const v = videos[side]; v.src = selected[side].media; v.load();
  showError(''); renderComparison();
  // Preserve the logical cursor while metadata for the replacement loads.
  ['play', 'back', 'forward', 'scrub'].forEach(id => { byId(id).disabled = true; });
}
function svgElement(tag, attrs, text = '') {
  const node = document.createElementNS(byId('chart').namespaceURI, tag);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  node.textContent = text; return node;
}
function drawChart() {
  const chart = byId('chart');
  const points = data.versions.filter(v => v.overall !== null);
  if (!points.length) {
    chart.append(svgElement('text', {x:30,y:100}, 'No overall scores available.'));
    return;
  }
  const first = data.versions[0].version;
  const last = data.versions[data.versions.length - 1].version;
  const low = Math.min(...points.map(v => v.overall));
  const high = Math.max(...points.map(v => v.overall));
  const x = v => last === first ? 400 : 56 + (v.version-first)/(last-first)*680;
  const y = v => high === low ? 90 : 156 - (v.overall-low)/(high-low)*124;
  chart.append(svgElement('text', {x:4,y:34}, high.toFixed(1)));
  chart.append(svgElement('text', {x:4,y:158}, low.toFixed(1)));
  chart.append(svgElement('polyline', {points:points.map(v => `${x(v)},${y(v)}`).join(' ')}));
  points.forEach(v => {
    const group = svgElement('g', {tabindex:0,role:'button',
      'aria-label':`Load v${v.version}, overall ${v.overall}`,
      'data-version':v.version});
    group.append(svgElement('circle', {cx:x(v),cy:y(v),r:5}));
    group.append(svgElement('circle', {cx:x(v),cy:y(v),r:14,class:'hit'}));
    group.append(svgElement('title', {}, `v${v.version}: ${v.overall}`));
    group.addEventListener('click', () => load(0, v.version));
    group.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault(); event.stopPropagation(); load(0, v.version);
      }
    });
    chart.append(group);
  });
  // Keep axis labels sparse enough to read on a phone.
  const labels = data.versions.filter((v, i) => i === 0 ||
    i === data.versions.length-1 || i % Math.ceil(data.versions.length/5) === 0);
  labels.forEach(v => chart.append(svgElement('text',
    {x:x(v),y:190,'text-anchor':'middle'}, `v${v.version}`)));
}
videos.forEach((v, i) => {
  v.addEventListener('loadedmetadata', () => {
    ready[i] = true;
    if (ready.every(Boolean)) { refreshControls(); seek(time); }
  });
  v.addEventListener('error', () => {
    pause(); ready[i] = false; refreshControls();
    showError(`Cannot load v${selected[i].version}. Check its copied MP4 and browser codec support.`);
  });
  v.addEventListener('ended', () => {
    if (playing) { pause(); seek(limit); }
  });
  v.addEventListener('seeked', renderTime);
  pickers[i].addEventListener('change', () => load(i, Number(pickers[i].value)));
});
byId('play').addEventListener('click', togglePlay);
byId('back').addEventListener('click', () => step(-1));
byId('forward').addEventListener('click', () => step(1));
byId('scrub').addEventListener('input', () => {
  pause(); seek(Number(byId('scrub').value));
});
byId('shift').addEventListener('change', () => {
  pause(); refreshControls(); seek(time);
});
byId('audio').addEventListener('change', () => {
  videos.forEach((v, i) => { v.muted = byId('audio').value !== String(i); });
});
document.addEventListener('keydown', event => {
  if (event.ctrlKey || event.altKey || event.metaKey ||
      event.target.closest('input,select,textarea,button,[contenteditable]')) return;
  if (event.key === ' ') { event.preventDefault(); togglePlay(); }
  if (event.key === ',') { event.preventDefault(); step(-1); }
  if (event.key === '.') { event.preventDefault(); step(1); }
});
byId('shift-amount').textContent = data.shift;
drawChart(); load(0, selected[0].version); load(1, selected[1].version);
requestAnimationFrame(tick);
</script></body></html>
"""


def render_html(
    versions: list[Version],
    categories: list[str],
    verdicts: list[Verdict],
    shift: float,
) -> str:
    """Embed JSON safely, even when a note contains a closing script tag."""
    data = {
        "versions": [asdict(version) for version in versions],
        "categories": categories,
        "ab": [asdict(verdict) for verdict in verdicts],
        "shift": shift, "shiftStart": SHIFT_START,
        "shiftVersion": SHIFT_VERSION, "fps": FPS,
    }
    serialized = json.dumps(data, ensure_ascii=True, allow_nan=False)
    for character, escape in (("<", "\\u003c"), (">", "\\u003e"),
                              ("&", "\\u0026")):
        serialized = serialized.replace(character, escape)
    options = "".join(
        f'<option value="{v.version}">v{v.version} · '
        f'{html.escape(v.status)}</option>' for v in versions
    )
    return PAGE.replace("__OPTIONS__", options).replace("__DATA__", serialized)


def build(args: argparse.Namespace) -> None:
    """Copy proxies and write a page that can be opened directly from disk."""
    versions, categories, proxies = load_versions(args)
    verdicts = load_verdicts(args.ab)
    page = render_html(versions, categories, verdicts, args.version_time_shift)
    destination = args.out_dir.resolve()
    if destination == args.proxies_dir.resolve():
        raise ValueError(
            "Output directory must differ from the proxies directory"
        )
    index = destination / "index.html"
    inputs = [args.scores, args.ab]
    if any(path is not None and index == path.resolve() for path in inputs):
        raise ValueError("Output index.html would overwrite an input")
    media = destination / "media"
    media.mkdir(parents=True, exist_ok=True)
    for number in sorted(proxies):
        source = proxies[number]
        target = media / source.name
        if target.resolve() != source:
            shutil.copy2(source, target)
    index.write_text(page, encoding="utf-8")
    print(f"Wrote {index} ({len(versions)} versions)")


class PageInspector(HTMLParser):
    """Collect tags and IDs to test generated HTML structurally."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.ids: set[str] = set()

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.tags.append(tag)
        for key, value in attrs:
            if key == "id" and value is not None:
                self.ids.add(value)


def selftest() -> None:
    """Build an offline site from fake files and check embedded data."""
    with tempfile.TemporaryDirectory(prefix="explorer-test-") as name:
        root = Path(name)
        proxies = root / "proxies"
        proxies.mkdir()
        for version in (1, 8, 10):
            (proxies / f"moonshot_v{version}_480p.mp4").write_bytes(
                f"fake-v{version}".encode()
            )
        scores = root / "scores.csv"
        categories = [f"category_{number}" for number in range(10)]
        with scores.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["version", "overall", *categories, "status"])
            for version in (1, 8, 10):
                writer.writerow([version, version / 2, *([6] * 10), "kept"])
        notes = root / "notes"
        notes.mkdir()
        malicious = '</script><script>alert("x")</script> & critic'
        (notes / "v1.md").write_text(malicious, encoding="utf-8")
        ab = root / "ab.csv"
        ab.write_text(
            "comparison,section,picked_version,confidence\n"
            "v1_vs_v8,middle,v8,high\n", encoding="utf-8"
        )
        args = parse_args([
            "--proxies-dir", str(proxies), "--scores", str(scores),
            "--notes-dir", str(notes), "--ab", str(ab),
            "--out-dir", str(root / "site"),
        ])
        build(args)
        page = (root / "site" / "index.html").read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(page)
        assert inspector.tags.count("video") == 2
        assert inspector.tags.count("script") == 2
        assert {"left-version", "right-version", "scrub", "chart"} <= (
            inspector.ids
        )
        assert malicious not in page and "\\u003c/script" in page
        assert "requestAnimationFrame" in page
        assert "#FFB040" in page and "@media" in page
        assert "http://" not in page and "https://" not in page
        assert '"pair": [1, 8]' in page
        assert '"version": 10' in page
        assert (root / "site/media/moonshot_v8_480p.mp4").read_bytes() == (
            b"fake-v8"
        )
        assert parse_args(["--selftest"]).selftest
        args.notes_dir = None
        args.ab = None
        build(args)
        assert "No critic notes available." in (
            root / "site/index.html"
        ).read_text(encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                parse_args([])
            except SystemExit:
                pass
            else:
                raise AssertionError("Accepted missing required inputs")
    print("build_explorer selftest: PASS")


def main() -> None:
    """CLI entry point."""
    args = parse_args()
    try:
        if args.selftest:
            selftest()
        else:
            build(args)
    except (OSError, ValueError) as exc:
        print(f"build_explorer: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
