# MOONSHOT: making-of

MOONSHOT is an 87.5-second Apollo 11 trailer. Claude Code (Opus) built it as a self-paced loop on
one Windows laptop (CPU and integrated GPU, no cloud renders), over three days: 2026-10-07 to
2026-10-09. Every picture and every voice is real NASA material from 1969. The 3D shots are built
from NASA data, and the music is public-domain recordings.

**Final: v28** (`MOONSHOT_FINAL.mp4`, 87.5 s, 2,100 frames, 1920×1080, 24 fps, −13.8 LUFS,
−1.5 dBTP; `BEST.json` pins its sha256 `d0e1069b…1264` and the tag `v28-final`). Twenty-eight
versions came out of a loop-time budget of 24 hours, kept in a ledger of seven segments (24 h
01 m in the ledger; about 16 h of that is active work in the transcript, the rest is renders and
waits; see `analytics/`). The senior-editor critic went from 5.5 (v1) to 8.0 (v14), 8.5 (v20,
v21), 9.0 (v22) and 9.5 (v23, v24, v26). v27 and v28 were exported after its last review and had
no fresh critic pass; v28 was checked against v27 by blind A/B (seven ties, no regression) and
by the gates below.

The first twelve versions came out of the first night (02:43 to 08:52 on 10-07). Versions v13 to
v28 came from six more ledger segments, covered in "From v13 to v28" below.

## Version history

Each version is a new file in `versions\`; nothing was overwritten. The blind A/B judge and the
senior-editor critic decided BEST between them. When the A/B tied, or its picks turned out to be
misreads, the editor's score decided, and each of those calls is logged below. The editor scored
10 categories from 1 to 10.

v1 to v12 were all exported on 10-07; v13 on, the date is in the first column. "Editor overall"
is the Fable editor's own review score; a version with no review of its own says so.

| Version | Exported (EDT) | Editor overall | Blind A/B | What changed | Outcome |
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
| v12 | 08:52 | (A/B only) | 1-0 vs v11, 6 ties | DSKY panel back top-left after an internal source cut; Mission Control reaction starts 0.7 s earlier (2 frames clear of a hard cut in the source) | BEST until v13 |
| v13 | 10-07 17:51 | (none) | (none, picture identical to v12 but one credits line) | rights fix: Holst's "Mars" (a 1998 wind-band transcription of uncertain status) replaced by Beethoven's Egmont overture, a Czech National Symphony Orchestra recording released by Musopen | BEST (required fix, accepted on measured audio parity) |
| v14 | 10-07 18:11 | 8.0 | 2-0 vs v13 | middle re-cut inside 26.5-40.3 s: 5 to 8 shots, stills 6.5 s down to 1.2 s, cuts on music onsets | BEST; unlocked the extras gate (editor ≥ 8) |
| v15 | 10-07 19:06 | 8.0 (= v14) | v14 won 2-0 (low) | TLI counter run-up, Egmont fade, Moon grade match | not BEST (plateau 1 of 2) |
| v16 | 10-07 19:57 | 8.0 (= v14) | v14 won 2-1 | live descent readout from the Apollo Lunar Surface Journal callouts, Armstrong's "Staging... and ignition" | not BEST (plateau 2 of 2) |
| v17 | 10-07 22:43 | 8.0 (7.0 when re-scored in the v18 review) | 1-1 vs v14 | the director's notes on v16 (0:33 music, DSKY side jump, 1:02 stop), a creator credits card, AI-marking and provenance fixes; 87.0 s | BEST (logged override of a tie) |
| v18 | 10-08 00:08 | 7.5 (v17 7.0 in the same review) | 2-1 vs v17, 4 ties | Blender title redesign, staging split, a re-rendered ascent, the director-approved 0:33 Moon hold and 1:02 music entry; 87.5 s | BEST |
| v19 | 10-08 02:11 | 8.0 | 2-2 vs v18, 3 ties | music-locked recut (46 cuts, one RIFE ramp), a ring-out and ambience bed under the 0:33 hold | BEST (the director approved 0:33 and 1:02 by ear) |
| v20 | 10-08 04:13 | 8.5 | v19 won 1-0, 6 ties | the 1969-hardware HUD: DSKY, mission-control CRT, drum counters | not BEST (split verdict) |
| v21 | 10-08 05:31 | 8.5 | 3-1 vs v19, 3 ties | v20 made legible at phone size | BEST |
| v22 | 10-08 13:41 | 9.0 | 4-0 vs v21, 3 ties | one overlay system across every card, odometer carry fix | BEST |
| v23 | 10-08 17:15 | 9.5 | 5-0 vs v22, 2 ties | ascent rebuilt with no baked text, flash-forward tag on the cold open, the 240,000 card in the drum style, an AI-assist line on the end card | BEST |
| v24 | 10-08 18:25 | 9.5 | 1-0 vs v23, 6 ties | the staging sound change the director picked in a blind audition, the 10.5K Aldrin visor scan, heading and label polish | BEST |
| v25 | 10-08 19:08 | (none; 9.5 when re-scored in the v26 review) | (none) | Blender Earth-to-Moon hero beat, frames 715-798 | BEST (the director's pick) |
| v26 | 10-08 20:09 | 9.5 | 3-0 vs v25, 4 ties | "disclosure diet": every on-screen disclosure in one quiet footnote style; a steadier outro | BEST |
| v27 | 10-08 22:43 | (none) | (none) | the smoke-under-the-title shot as RIFE v4.6 slow motion instead of a frame-rate blend | BEST (the director's pick) |
| v28 | 10-08 23:57 | (none) | 7 ties vs v27 | the editor's three v26 fixes: a scrim under the ARCHIVE and TIME-COMPRESSED footnotes on bright frames, no caption on the end plate, ascent footnote copy | **FINAL** |

Editor sub-scores for v11: hook 7.5, pacing 6.5, visual variety 7.5, motion 7, typography 7.5,
colour 7, sound 7.5, captions 8, storytelling 7.5. For v26, the last full review: hook 8.5,
pacing 8, visual variety 9, motion 9.5, typography 9, colour 9.5, sound 8, captions 8,
storytelling 9.5, overall 9.5. The editor could not hear, so its sound score is unassessed (the
review says so).

## From v13 to v28

**The budget.** After the first night the director asked for "24 hours of agent run time". The
definition he settled on (10-07 20:35): loop-running wall clock, counting renders and agent waits
while the loop runs, and leaving out the gaps between sessions and every usage pause. The agent
kept it in `run_ledger.csv` (checked against the transcript in `analytics/`): seven segments, the
last closed at 00:06 on 10-09 with the budget at 24 h 01 m. A plateau rule ran alongside: two
versions in a row that don't beat BEST on blind A/B and the editor, and the loop stops polishing
video. v15 and v16 hit it. Versions after that came from clear levers: the director's notes (v17),
the HUD and legibility (v20, v21), then the all-out segment (v23 to v28).

**His ear beat every AI critic on audio.** The critics that could see couldn't hear, and the
measurements missed two things the director heard on v16:
- 0:33, the Dvořák-to-Egmont change. Measured, the emulated pre-mix between 33.25 and 34.0 s was
  digital silence (−180 dB) in v18, and at full volume it reads as a dropout. The fix kept the
  Dvořák chord ringing out and put a pitchless ambience bed under the hold.
- 1:02, the Egmont stop. The Largo entered late, on a chord a semitone away from where the Egmont
  stopped. Starting the Largo earlier (F to B-flat across the black) fixed it.

Each was auditioned as an A/B clip pair before it went into a version, and he approved both by
ear. Every promotion of audio since has gone the same way: waveforms never promote audio.

**What the critics couldn't do.** The Gemini Flash critic hears audio (a probe with a known
answer key: 3 of 4 right) but its scores are as noisy from run to run as the gaps between
versions. TwelveLabs gave v19 and v21 identical scores in all ten categories (8.8, off the
half-point scale). Both were kept as data for the reliability study and left out of every
promotion decision. A third critic, Codex, scored about half a point to a point under the Fable
editor, and its sound score fell from 8 to 7 on v22 although the audio was byte-identical to v21.
The warehouse (`analytics/`) keeps all of it.

**The Codex all-out plan.** With 5 h 45 m of budget left and the director asking to "push the
limits and go absolutely all out", the lead asked Codex (high effort) for a plan. It judged the
polish loop near its ceiling and that the upside was in bold structural moves. The plan was
accepted with one change, recorded in `BRIEF_allout.md`: sound is promoted only if the director
hears it and prefers it. The sequence was v23 (foundation), v24 (sound), v25 (an Earth-to-Moon
hero beat on frames 715-798), v26 (original film scans for the epilogue), with three builders
working in parallel on isolated copies and the lead integrating their patches in order. In the
end v24 was restructured to isolate risk: v24 carried the audio change and the 10.5K scan, v25
the hero beat on its own. The scan of the end plate was at parity and the bootprint scan gave no
gain, so both were left off; only the Aldrin visor push shipped.

**The director's blind audio pick (v24).** Three blind pairs, same picture and loudness, only the
sound differing (countdown and ignition, ascent staging, alarm and descent), with the sides drawn
at random in a key file kept away from him. He had no preference on the countdown, preferred
the staging candidate (he noted the sound of the pod being detached and liked it) and the baseline
on the alarm and descent. Decoded through the key: only the staging change was adopted. The
sound builder then made v24b: the baseline plus that one change, sample-identical elsewhere. The
analytics keep the pick as a row mapped through the key (`fct_director_picks`).

**The hero beat (v25).** The middle of the trailer (19-40 s) had been the critics' top complaint
for a dozen versions: info cards over slow space shots. v25 replaced a real Apollo 11 Earth
photo and a 16 mm Earth shot with one continuous Blender move, from the Earth to the Moon along
a schematic route, ending exactly on the locked Moon portrait. It is labelled TRAJECTORY
SCHEMATIC, NOT TO SCALE. The editor had named "a CG explainer in an archive trailer" as a tell,
and the swap trades some authenticity; the director saw the clip beside the footage it replaces
and chose it ("bottom for sure"). In the editor's next review it counted as the first structural
fix to the middle.

**The disclosure diet (v26).** The honesty tags (TRAJECTORY SCHEMATIC, ARCHIVE, TIME-COMPRESSED,
the 6X note on the ascent, the end-card AI line) had been enlarged in v23 because the crowd
critic couldn't read them at phone size. The director asked for the opposite: smaller and less
important wherever they add nothing. The decision kept every disclosure but moved all of them
into one quiet footnote style (about 9 px cap height at 360p, cream at 75%, one line, no plates).
That reversed the critics' push, and it's logged as the director outranking them. The editor's
review of v26 then found two tags on bright picture (the ARCHIVE tag over the separation plume,
TIME-COMPRESSED over the landing dust) readable by their shadow alone; v28 added a local scrim
under them only where the picture is bright. v26 also reworked the outro, which the director
called rushed and shaky: the end title's 3D render had been yawing and scaling against the plate's
push, so the bevel highlights crawled. The plate now comes in 1.2 s earlier, the title lands on
the existing boom and holds still, and the date line arrives sooner.

**The RIFE slow-mo (v27).** The smoke-under-the-title shot was a half-speed frame-rate blend:
every other frame was about 15% softer. Rebuilt from RIFE v4.6 in-betweens, odd/even sharpness
went from 0.847 to 0.978 and the sharpness jitter from 36.9 to 7.1. The director picked it in a
side-by-side. The asset is a 19 MB clip; a build checks its manifest hash and doesn't need RIFE.

**What was declined.** A CG astronaut footstep followed by the real bootprint photo was
declined: 3 to 5 hours or more, a high uncanny risk, and a conflict with the rule against
re-enacting archival moments. The cheaper camera-shutter beat would have landed on "one giant leap
for mankind" at 72.70 s.

**The gates.** Each video version had to pass the same checks before it could be promoted. Patches are
exact-string replacements with asserts, dry-run on copies, reviewed by Codex adversarially, then
rendered. Protected sections (the 0:33 Moon beat, the 1:02 transition and the credits) stay
bit-identical before encoding, except where a version deliberately changes them (v23 changed the
distance card inside the Moon beat). A per-frame hash of the picture says which frames changed and
the gate lists the windows that may. A flash-safety check (`flashqc2.py`, WCAG 2.3.1, written by
Codex after it found false PASSes in the first one) must pass. Audio must be identical or
change only where intended (a decoded difference of −240 dBFS where it should be nothing).
`promote.py` then checks the frame count, decodes the whole file, and writes `BEST.json` with the
sha256 and the git commit. v28 passed all of them. The mux of its first attempt produced a truncated
622-frame file; the guard caught it and deleted it, and the retry was clean.

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
| PhotoCraft (alpha, MCP) | three thumbnail candidates from v14 frames (not used in the video) |
| FilmCraft, VectorCraft, LightCraft (alpha, MCP) | not used in the final pipeline (see below) |
| RIFE v4.6 (rife-ncnn-vulkan, MIT; Vulkan on the integrated GPU) | the ignition ramp from v20 and the v27 slow-mo; the in-betweens are tracked assets, so a build needs no RIFE |
| Codex (OpenAI, read-only unless it was writing a new file) | adversarial review of every patch from v14 on, a second critic (`codex_critic.py`), the all-out plan, and new tools (`flashqc2.py`, `panel.py`, `trailer_metrics.py`) |
| librosa | beat grid of the music bed, to measure how the cuts sit on it |
| Gemini Flash, TwelveLabs | video-and-audio critics; kept as probes after they didn't separate versions |
| Remotion, Manim | vetted and tried; the overlays stayed in PIL (parity, faster to iterate) |

### What the alpha craft apps could and couldn't do here

- EffectCraft built a usable extruded 3D title over MCP in v1. Its text only uses system fonts,
  so Anton fell back silently, and a whole-number keyframe time overwrote the t=0 key (we used
  4.01). The Blender title beat it in the first blind A/B.
- Traps known from the last run decided the rest:
  - FilmCraft's quick export ignores loudness settings, and its frame render needs integer seconds.
  - VectorCraft can't use the brand fonts.
  - PhotoCraft can't place embedded files under automation.

  A frame-exact ffmpeg/PIL compositor was faster to iterate and fully scriptable, so the edit lived there.
- The extras were gated on an editor score of 8, which v14 reached. Three thumbnail candidates
  were then made in PhotoCraft over MCP (text overlays in PIL, because PhotoCraft only sees system
  fonts). The vertical teaser, cutdowns and poster were not made. An EffectCraft trial of the
  240,000-miles card matched the PIL version in quality but wasn't better, so it stayed a
  prototyping tool.

## Blender render times (this laptop, EEVEE)

| Shot | Frames | Time | Per frame |
|---|---|---|---|
| steel title | 110 | 4 m 17 s | 2.3 s |
| Moon approach | 96 | 2 m 38 s | 1.6 s |
| 3D ascent (8K Blue Marble + atmosphere + 3D text) | 192 | about 22 min | about 7 s |
| Earthrise parallax | 106 | 5 m 9 s | 2.9 s |
| Aldrin parallax | 43 | 1 m 45 s | 2.4 s |
| title in the plate (rejected) | 110 | 2 m 53 s | 1.6 s |

Later renders: the v23 ascent, 192 frames at 1080p, measured about 5.8 s per frame; RIFE
in-betweens took about 0.3 to 0.5 s per frame at 1080p on the integrated GPU.

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
- Stills-only critics reported the same false alarms for versions on end. "MILES TO THE MOON
  clipped at 34.8 s" came up in at least nine reports; each time it was a key frame caught
  mid-wipe, and the label is complete from frame 840. The loop only stopped it by writing a
  known-non-issues file (with the evidence) and giving it to every critic, and by requiring an
  adjacent-frame check before any "clipped" claim. A related measurement gap: the Whisper check
  never transcribed the windows for "Staging." and "And ignition.", so four versions carried a
  recall of 0.00 that said nothing about audibility. The director listened and kept the lines.
- The Sonniss effects licence forbids AI training, and mixes containing them had gone to two video
  critics that may train on uploads. An audit caught it, the uploads stopped, and the TwelveLabs
  training opt-out was switched off at the director's request. Both services turned out to be poor
  scorers anyway.
- A builder died mid-run when its login token expired. It had left new files uncommitted; the
  next segment finished the work from its gates and evidence instead of starting over.
- Editing build.py with `sed -i` rewrote the whole CRLF file as LF. It was restored, and the rule
  is now: edit CRLF files only with a byte replace in Python.
- A v24 gate deviation, explained instead of waved through: frames 1841-1852 changed although the
  new segment was byte-identical, because the segments carry mixed colour tags and the concat
  decode of one depends on its neighbours. The difference was below the encoder's own noise; the
  fix (tag every segment bt709) is still on the list.
- In Blender, the sun pointed backwards, the atmosphere shell rendered opaque, a 16K texture was
  too big, the chase camera sat inside the Earth, label shadows mirrored, and specular caused a
  purple haze. Each turned up on a 960×540 test frame before any full render.

## Rights notes

All footage, photos and mission audio are NASA works, public domain in the US. The three music
recordings (Dvořák's finale and Largo, Beethoven's Egmont overture) are Musopen public-domain
releases. Versions v2 to v12 used Holst's "Mars" in a US Air Force Band recording whose 1998
wind-band transcription had an unconfirmed status; v13 replaced it, so v13 and later are cleared
on the music side and v2 to v12 stay private. The Sonniss effects are used under their royalty-free licence and not
redistributed. Not affiliated with or endorsed by NASA. The full list is in `CREDITS.md`.

## Related work (searched 2026-10-07)

This was a 15-minute read-only search; details and links are in `RELATED-WORK.md`. Each piece
exists elsewhere:
- Anthropic's progress-file harness for long-running coding agents;
- MCP servers for Resolve, Premiere, Blender and ffmpeg;
- QA/critic agents in overnight generated-video pipelines.

MOONSHOT's own MCP use was thin: EffectCraft built the v1 and v2 title (plus a later trial) and
PhotoCraft made the thumbnail candidates. What I didn't find in that search was
another public run that pairs a multi-hour progress-file loop with blind-A/B keep/revert and
licence-logged archival media plus a raw-vs-final cut.
