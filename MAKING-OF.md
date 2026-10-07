# MOONSHOT: making-of

MOONSHOT is an 81.8-second Apollo 11 trailer. Claude Code (Opus) built it overnight on
2026-10-07, running as a self-paced loop from 02:43 to about 11:15 EDT on one Windows laptop: CPU
and integrated GPU, no cloud renders. Every picture and every voice is real NASA material from
1969. The 3D shots are built from NASA data, and the music is public-domain recordings.

**Final: v12** (`MOONSHOT_FINAL.mp4`, 81.8 s, 1920×1080, 24 fps, −13.8 LUFS, −1.5 dBTP). Twelve
versions came out of about 6 hours of building (02:43 to 08:52); wrap-up took the rest. The
senior-editor critic went from 5.5 (v1) to 7.5 (v10 and v11). v12 was a small fix, judged by
blind A/B only. The brief set 8 as the bar for extras, so no thumbnails, vertical teaser or poster
were made. Usage: the 5-hour plan window peaked around 77% (05:06) and sat at 46% at 08:30. OpenAI
Codex, read-only, did 5 pipeline reviews and wrote one QC script.

## Version history

Each version is a new file in `versions\`; nothing was overwritten. The blind A/B judge and the
senior-editor critic decided BEST between them. When the A/B tied, or its picks turned out to be
misreads, the editor's score decided, and each of those calls is logged below. The editor scored
10 categories from 1 to 10.

| Version | Exported | Editor overall | Blind A/B | What changed | Outcome |
|---|---|---|---|---|---|
| v1 | 03:50 | 5.5 | – | complete rough cut: synthesised score, EffectCraft 3D title, PIL graphics, ffmpeg conform | baseline |
| v2 | 04:11 | 6.5 | – | public-domain orchestral score (Dvořák, Holst), Sonniss SFX layer, restored mission audio, landing intercuts | BEST |
| v3 | 04:26 | (A/B only) | won vs v2 | Blender steel title, Blender Moon approach, true 1-frame white flash | BEST |
| v4 | 04:40 | 6 (sound now measured) | 3-2 vs v3 | fact-check fixes, adaptive per-line ducking, cold-open rework | BEST |
| v5 | 05:20 | 6 | 2-2 vs v4 | Blender 3D ascent replaces the 2D chart, flash-forward cold open, Codex mix fixes | BEST (editor) |
| v6 | 05:41 | – | lost to v5 | "title in the plate" (fire reflections), light wrap | reverted |
| v7 | 06:03 | 6.5 | 2-2 vs v5 | steel title restored, Earthrise/Aldrin 2.5D parallax, end card in title-safe | BEST (editor) |
| v8 | 06:50 | 6.5 | lost 0-2 vs v7 | act 2 compressed by 6.7 s (88.5 → 81.8 s), logical-time graphics | not BEST |
| v9 | 07:27 | 7.0 | 3-0 vs v7 | big count numerals, freezing colour-coded bingo timer + annunciator lamp, measured caption timing, decode-pipe frame fix | BEST |
| v10 | 07:55 | 7.5 | 0-2 vs v9 (both picks verified misreads) | drop rebuild ("all engines running" cut, liftoff on the fireball): drop now +2.7 LU over the cold open; count numeral "8"; Houston caption split; 3-line credits | BEST (override logged) |
| v11 | 08:28 | 7.5 ("better by a hair") | 0-2 vs v10 (low; 1 sampling artefact, 1 real nit) | landing becomes the loudest section (−10.9 LUFS); alarm click removed; 16mm lift; DSKY off a controller's head; captions under 20 chars/s | BEST (override logged) |
| v12 | 08:52 | (A/B only) | 1-0 vs v11, 6 ties | DSKY panel back top-left after an internal source cut; Mission Control reaction starts 0.7 s earlier (2 frames clear of a hard cut in the source) | **FINAL** |

Editor sub-scores for v11: hook 7.5, pacing 6.5, visual variety 7.5, motion 7, typography 7.5,
colour 7, sound 7.5, captions 8, storytelling 7.5.

## How the loop worked

- Memory lived in `PROGRESS.md`: the start time, the schedule, which version was BEST, the score
  table, the backlog, every decision Connor made during the night, known tool traps and a resume
  point. The conversation was compacted several times, and each time the loop picked up from
  that file.
- `build.py` turns three tables (SHOTS, DIALOG, CAPTIONS) into stems and a graded, captioned
  1080p24 master. Most versions are a small patch script of exact-string replacements with
  asserts. Each patch was dry-run on copies first, then committed and tagged in a local git repo
  (`vN-src`, `vN-final`), so any revert is one `git checkout`.
- Each version went to a review panel:
  - a senior editor (Fable), giving 10 scores and the 5 fixes that would help most;
  - a blind A/B judge (Sonnet), seeing unlabeled frame strips per section with a fixed rubric and never the key file;
  - a "mean Twitter" crowd, for pile-ons, shareability and an AI-slop score;
  - a first-time viewer, asked where it would scroll away;
  - a script measuring the audio: section LUFS, dialogue-to-bed ratio per line, a click scan, and a whisper transcription of the final mix;
  - once, a historical fact-check with cited sources.
- Codex (OpenAI) was the second reviewer. Reading the pipeline without editing it, it found:
  - the ignition duck cap applied to the whole countdown;
  - the bed loudness measured in mono;
  - the SFX ducked only 60%;
  - stars drawn over the lit Moon;
  - an Aldrin shot one frame short;
  - the synth SFX stem left on the old timeline after act 2 was compressed;
  - the end-card Moon lander outside title-safe;
  - in the wrap-up scripts, a parallax source key and a speed-change span.

  It also wrote `techqc.py` from scratch. It never edited pipeline files: it proposed diffs, and the loop applied them.
- Builder subagents (Opus) wrote the larger patches, from the act-2 retime to v12, and dry-ran
  each one before anything touched the real files.

## Tools: what did what

| Tool | Used for |
|---|---|
| ffmpeg 8.1 + Python (numpy, PIL, scipy) | conform, grade (LUT, halation, vignette, grain, gate weave), all 2D graphics and captions, mix, 2-pass loudnorm to −14 LUFS / −1.5 dBTP, x264 export |
| Blender 5.2.2 (EEVEE, headless) | steel title, Moon approach, 3D ascent over Blue Marble Earth, 2.5D parallax of Earthrise and Aldrin |
| craft_tools.restore | mission-audio cleanup (noise floor about −33 → −43 dB) |
| craft_tools.cutout (BiRefNet) | Aldrin matte for the parallax split |
| whisper.cpp | caption drafts and the intelligibility check on the final mix |
| EffectCraft (alpha, MCP) | v1–v2 3D title; replaced by Blender in v3 |
| FilmCraft, PhotoCraft, VectorCraft, LightCraft (alpha, MCP) | not used in the final pipeline (see below) |

### What the alpha craft apps could and couldn't do here

- EffectCraft built a usable extruded 3D title over MCP in v1. Its text only uses system fonts,
  so Anton fell back silently, and a whole-number keyframe time overwrote the t=0 key (we used
  4.01). The Blender title beat it in the first blind A/B.
- Traps known from the last run decided the rest:
  - FilmCraft's quick export ignores loudness settings, and its frame render needs integer seconds.
  - VectorCraft can't use the brand fonts.
  - PhotoCraft can't place embedded files under automation.

  A frame-exact ffmpeg/PIL compositor was faster to iterate and fully scriptable, so the edit lived there.
- Thumbnails, the vertical teaser and the poster (PhotoCraft and DesignCraft work) were gated on
  an editor score of 8. The best score was 7.5, so they weren't made.

## Blender render times (this laptop, EEVEE)

| Shot | Frames | Time | Per frame |
|---|---|---|---|
| steel title | 110 | 4 m 17 s | 2.3 s |
| Moon approach | 96 | 2 m 38 s | 1.6 s |
| 3D ascent (8K Blue Marble + atmosphere + 3D text) | 192 | about 22 min | about 7 s |
| Earthrise parallax | 106 | 5 m 9 s | 2.9 s |
| Aldrin parallax | 43 | 1 m 45 s | 2.4 s |
| title in the plate (rejected) | 110 | 2 m 53 s | 1.6 s |

## What broke, and what it taught

- A one-frame white flash rendered black, and later went missing. The first fix was a comp
  flash. v9 found the real cause: the decode pipe re-timed frames, dropping the 1-frame white,
  duplicating a black, and pushing every frame after ~56 s one frame late. `-fps_mode
  passthrough` fixed it.
- The drop wasn't a drop. In v8 the cold open measured −14.2 LUFS and the ignition −13.2. The
  whole countdown was one dialogue entry, so the adaptive duck held the music down through the
  ignition. Splitting it into phrases fixed clarity. Capping the duck then buried the launch
  lines 7 dB under the bed, so v9 gave up the jump to keep the words audible. v10 got both:
  cutting "all engines running" and moving "Liftoff!" onto the fireball put the drop 2.7 LU over
  the cold open, with every line still at least +11 dB.
- The "The Eagle has landed" caption ran 1.7 s early from v2 to v8, because I had split it by
  guess. v9 places it at measured word times.
- A regex hit a comment instead of the assignment, so in v9 the Mission Control reaction cut
  stayed at 60.40 s instead of 61.05. The blind judge happened to prefer it ("room reaction on
  'The Eagle has landed'"), so it stayed. I'm logging it because it was luck, not design.
- Sourcing slipped once: a "Mission Control" shot started on the tail of an Earthrise clip, with
  Earth on screen during "30 seconds". The fact-check also found that the MSFC "Ultimate Saturn V"
  compilation is probably not all Apollo 11. No Apollo 11 captions sit on those shots, and the
  credits say so.
- The blind judge can't hear. In v10 it preferred v9 on two sections, and both picks rewarded
  things fixed on purpose: v9's countdown "1" sitting on the fireball, and a caption it called
  "early" that now matches the moved audio line. I checked both against the frames, kept v10 and
  logged the override. From v11 on, the judge's prompt says it can't hear and should judge only
  what it sees; the rubric stayed fixed. In v11 it gave v10 two low-confidence picks. The
  "missing caption" was a frame-sampling artefact (the frames are pixel-identical). The DSKY
  placement nit was real, and v12 fixed it.
- Two critic diagnoses were wrong, and measurements caught both:
  - "Liftoff on Apollo 11" scored 0.50 on the whisper check, but nothing was masking it. The
    effects bus was already ducked 22 dB there. My QC script's matching window missed a whisper
    segment by 0.03 s.
  - The click at 40.3 s wasn't the riser the editor named. It was a hard step in the synth alarm
    stem.
- Negative result: the "title in the plate." Lit by the real launch fire, the steel title looked
  like "flat salmon-rust plastic" to the blind judge, and the colour path added a purple cast.
  Reverted in v7.
- Act 2 was the top complaint three iterations running. The first-time viewer would have scrolled
  away at 0:30 in v7. v8 cut 6.7 s out of it, and the editor still calls 26–40 s the soft middle.
  (The flash-forward cold open in v5 had already moved that scroll point from 5.5 s to 31 s.)
- In Blender, the sun pointed backwards, the atmosphere shell rendered opaque, a 16K texture was
  too big, the chase camera sat inside the Earth, label shadows mirrored, and specular caused a
  purple haze. Each turned up on a 960×540 test frame before any full render.

## Rights notes

All footage, photos and mission audio are NASA works, public domain in the US. The Dvořák
recordings are Musopen public-domain releases. The Holst "Mars" recording is a US Air Force Band
performance, public domain as a federal work, but it plays a 1998 wind transcription by Merlin
Patterson whose own status I couldn't confirm. That's fine for private viewing; swap or clear it
before any public release. The Sonniss effects are used under their royalty-free licence and not
redistributed. Not affiliated with or endorsed by NASA. The full list is in `CREDITS.md`.

## Related work (searched 2026-10-07)

This was a 15-minute read-only search; details and links are in `RELATED-WORK.md`. Each piece
exists elsewhere:
- Anthropic's progress-file harness for long-running coding agents;
- MCP servers for Resolve, Premiere, Blender and ffmpeg;
- QA/critic agents in overnight generated-video pipelines.

MOONSHOT's own MCP use was thin: EffectCraft in v1–v2 only. What I didn't find in that search was
another public run that pairs a multi-hour progress-file loop with blind-A/B keep/revert and
licence-logged archival media plus a raw-vs-final cut.
