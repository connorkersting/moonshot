# Moonshot showcase tools

Two standalone Python 3.13 tools. They use only the standard library (Pillow
is not needed). Paths are supplied through CLI arguments. CSV inputs use UTF-8;
a UTF-8 BOM is accepted. Versions may be `7` or `v7` in CSVs. Video filenames
use positive version numbers without leading zeroes. Numbering gaps are fine;
versions are sorted numerically, and every available video needs a score row.

## Supercut

Requires `ffmpeg` and `ffprobe` on PATH, with `drawtext`, `xfade`, `acrossfade`,
`loudnorm`, FFV1 and libx264 support, plus a local TTF font.

```sh
python showcase/supercut.py --versions-dir ./versions --scores ./scores.csv --font ./fonts/font.ttf --out ./supercut.mp4
python showcase/supercut.py --versions-dir ./versions --scores ./scores.csv --font ./fonts/font.ttf --out ./supercut.mp4 --dry-run
```

The versions directory contains `moonshot_v1.mp4`, `moonshot_v2.mp4`, etc.
The scores CSV requires these columns (extra columns are ignored):

```csv
version,overall,status
1,4.0,reverted
7,6.5,kept
8,7.0,not_best
15,8.5,final
```

Allowed statuses: `kept`, `reverted`, `not_best`, `final`, `ab_only`. All existing
versions are included regardless of status. A blank overall appears as `n/a`.
Each label includes the version, editor score and status, for example
`v7 · editor 6.5 · kept`.

For each moment, the tool makes a two-second black title card followed by that
moment from every available version. The title reflects the actual clip length
argument and version count: `THE SAME 1.2 SECONDS, 15 VERSIONS`. Clips retain
their own audio; sources without audio get silence. Adjacent version clips
crossfade video and audio for four frames. Title boundaries use straight cuts.
Source video is fitted into 1920 × 1080 with black padding when needed.

Defaults: `--moments 13.4,44.8,56.2,64.5`, `--per-clip 1.2`. Clip lengths are
rounded to the nearest 24 fps frame (1.2 seconds becomes 29 frames). The output
duration follows the requested moments and available versions, rather than
truncating clips to force exactly 60 seconds:

```text
duration = moment_count × (2 + version_count × clip_frames / 24
                            − (version_count − 1) × 4 / 24)
```

With 15 versions and the defaults this is about 71.17 seconds; 12 versions
produce 58.67 seconds. Use `--per-clip 1.0` with 15 versions for 58.67 seconds.
Clip length must exceed the four-frame overlap. Moments are nonnegative,
finite seconds and preserve the supplied order. A clip that extends beyond
its source video raises an error before rendering starts.

Temporary clips use lossless FFV1 video and PCM audio, so allow ample temporary
disk space. The tool crossfades successive clips into moment blocks, then
uses an FFmpeg concat filelist to assemble title cards and blocks. Final
encoding is H.264 CRF 18, 1920 × 1080, 24 fps, with 48 kHz stereo AAC at
192 kb/s and `loudnorm=I=-14:TP=-1.5:LRA=11`. This is single-pass loudness
normalization; completely silent audio stays silent. Existing output files
are rejected. Temporary files are cleaned up on success or error.

`--dry-run` prints the ffprobe and ffmpeg commands without executing either.
It validates filenames, scores and the font file, but assumes source audio
exists and cannot check durations. Printed commands reference a temporary
working directory whose labels and concat filelist are deleted on exit;
the output is a command preview rather than a runnable saved script.
Subprocesses run with argument lists and no shell. Windows font paths have
their colons escaped for both levels of FFmpeg filter parsing.

## Offline version explorer

```sh
python showcase/build_explorer.py --proxies-dir ./proxies --scores ./category_scores.csv --notes-dir ./notes --ab ./ab.csv --out-dir ./explorer
```

The proxies directory contains `moonshot_v1_480p.mp4`, etc. Browser-compatible
H.264/AAC MP4 proxies are recommended. No ffmpeg command runs during this build.
The scores CSV requires `version`, `overall`, `status`, and exactly ten
distinct numeric category columns. Category names and their order come from
the CSV header; blanks display as unavailable and do not yield a delta.

```csv
version,overall,hook,pacing,variety,motion,type,color,sound,captions,story,clarity,status
1,4.0,5,4,4,5,3,5,4,3,4,4,reverted
8,7.0,7,7,6,7,7,8,7,7,7,7,kept
```

Optional `--notes-dir` contains `v1.md`, `v8.md`, etc. Notes display as plain
text with line breaks preserved, including Markdown source. Missing notes
get a placeholder. Embedded notes and CSV values are escaped; they cannot
inject HTML or scripts.

Optional `--ab` takes:

```csv
comparison,section,picked_version,confidence
v1_vs_v8,middle,v8,high
v7_vs_v8,ending,8,0.85
```

`comparison` must contain exactly two distinct positive version numbers;
`v1_vs_v8`, `v1-v8` and `1 vs 8` work. `picked_version` must belong to that
pair; a blank, `tie` or `none` means no preference. Confidence and section
are displayed as supplied. Verdicts match either left/right ordering.

The builder writes `out-dir/index.html` and copies proxies to `out-dir/media/`.
Open `index.html` directly in a modern browser, or serve that directory
locally. The page needs no internet, frameworks, fonts or CDN resources.
Rebuilding replaces the generated page and copies; unrelated output files
are preserved. Copy the entire output directory when sharing it.

Choose left and right versions, scrub their shared timeline, or select a
score-chart point to load the left version. Shared playback uses
`requestAnimationFrame` and corrects source-time drift. Comparison length
is limited by the shorter aligned source. Left audio is audible by default;
the audio picker can select right audio or mute both. Changing a version,
scrubbing or changing alignment pauses playback. The page stacks the players
on narrow screens, including 390 px phones.

Keyboard shortcuts outside form controls: **Space** toggles playback;
**`,`** steps back one frame; **`.`** steps forward one frame at 24 fps.
The same actions have buttons. Video seeking depends on the browser's MP4
decoder; frame steps set exact timeline targets but do not decode frames
independently. Chart points also support Enter and Space.

## Version time shift

Both scripts document `VERSION_TIME_SHIFT = 6.7` and accept
`--version-time-shift SECONDS`. The canonical timeline is that of v8 and later.
For v1–v7 only, a canonical moment at or after **33.3 seconds** maps to source
time **moment + 6.7 seconds**. Earlier moments and v8+ are unchanged.
The explorer has an alignment checkbox, enabled initially, and skips this
removed middle segment during playback. Turning it off compares raw source
times. Set `--version-time-shift 0` to disable the offset in the supercut or
to make the explorer's toggle have no offset. Offsets must be nonnegative
and finite.

## Self-tests

```sh
python showcase/supercut.py --selftest
python showcase/build_explorer.py --selftest
```

Both tests generate fake CSVs and video files in a temporary directory,
exercise argument parsing and output generation, and clean up afterwards.
The supercut test checks the mapping, numeric version order, drawtext labels,
four-frame video/audio crossfades, concat filelist, encoding flags and
loudness settings; it guards against accidentally running a subprocess.
The explorer test builds a real static page with fake proxies and checks
the player structure, embedded data, media copies and script-injection
escaping. Neither test runs ffmpeg/ffprobe or decodes the fake videos.
