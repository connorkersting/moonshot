"""v24 CANDIDATE (audio only): the sound-arc master from sound_v24.py replaces the reused v22 audio stream; the picture
is stream-copied from v23. Promoted ONLY if the director hears the blind A/B clips and prefers it.

    py patch_v24.py              # the real build.py
    py patch_v24.py BUILD.py     # dry run on a copy
    py patch_v24.py --v24b [BUILD.py]   # v24b (director's blind verdict 2026-10-08): the staging change only;
                                        # master_v24b.wav, AAC with -cutoff 20000 (true peak: see below)
Applies to build.py at commit 135f3c1 (v23-src + patch_v23b), before or after patch_v25 / patch_v26.

Changes to build.py (two anchors, both in the mix area; SHOTS, validate_assets() and preflight() are not touched, so
patch_v25 / patch_v26 apply before or after this one):
 1  After REUSE_AUDIO_DUR: V24_SOUND = True plus the pins of the new master and of the v23 picture, and two functions:
    - v24_master_check(): work/audio_v24/master_v24.wav must exist and match its pinned sha256 and sample count
      (4,200,000 = 87.5 s at 48 kHz) BEFORE anything is opened for writing;
    - mux_v24_master(): writes versions/moonshot_v<N>.part.mp4 from
        picture = V24_PICTURE_FROM (v23 by default; its video packet md5 is verified first) by STREAM COPY, or, with
                  V24_PICTURE_FROM = None, WORK/comp.mp4 encoded exactly like mux_reused_audio (x264 crf 18, BT.709,
                  the IDR at frame 1891) -- the setting for a build whose picture changes (v25 / v26);
        audio   = AAC 320k encode of the pinned master (no normalisation, no filter);
      the .part file must decode to exactly NFRAMES frames, its audio stream must be 87.5 s and match the pinned
      packet md5 (ffmpeg 8.1.2 native AAC is deterministic for this input; a different encoder fails loudly rather
      than shipping an unheard stream), it must hold exactly one audio stream (-map 1:a:0; patch_v23b's rule and
      its audio_streams() helper), and with a stream-copied picture its video packet md5 must equal the
      source's; only then is it renamed. Any failure deletes the .part file.
 2  stage_mix(): when V24_SOUND, mux_v24_master() runs instead of the v22 reuse path. V24_SOUND = False builds v23
    exactly (REUSE_AUDIO_FROM, unchanged).
preflight() still verifies REUSE_AUDIO_FROM (v22's stream) for the mix stage; that file is untouched.

The master is built by sound_v24.py (+ sound_v24_synth.py) from the v21 stems and the decoded v22 stream: outside the
unlocked windows (frames 0-779 and 888-1460 are the only ones it may change) it is sample-identical to the approved
stream's PCM, including the 0:33 Moon beat, the 1:02 transition and the credits.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
V24B = "--v24b" in sys.argv
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
P = Path(ARGS[0]) if ARGS else W / "build.py"

MASTER_SHA256 = "a1d746f8fa2444010fbcfb0d31d1ddeb9c2a48b590876384f94f17dd38c9cf0a"
MASTER_SAMPLES = 4200000
AUDIO_MD5 = "cb4b6f8bcdcd8cd078b50879f1e04bb0"           # packet md5 of the AAC 320k encode (ffmpeg 8.1.2)
PICTURE_MD5 = "540d2c716f991b97a9487f1f1ae1cba5"         # video packet md5 of versions/moonshot_v23.mp4
MASTER_NAME = "master_v24.wav"
AAC_EXTRA: list[str] = []
if V24B:   # sound_v24b.py: baseline PCM everywhere except frames 626-688 (comm tick out, release clunk in)
    MASTER_NAME = "master_v24b.wav"
    MASTER_SHA256 = "628c20fbd589081a0d4888091080ba14cb2450f1412423958ce277e22d296a26"
    AUDIO_MD5 = "444fc52b25750b4840ddb349d3ede039"       # AAC 320k -cutoff 20000 (ffmpeg 8.1.2)
    # the approved stream already peaks at -1.47 dBTP (4x) in places v24b must keep sample-identical; a default
    # re-encode overshoots to -1.42 (ebur128 -1.4). -cutoff 20000 (nothing audible above it) gives -1.455 (ebur128 -1.5)
    AAC_EXTRA = ["-cutoff", "20000"]

EOL: dict[Path, str] = {}


def load(path: Path) -> str:
    """Read with universal newlines; remember the file's own line ending (build.py is CRLF)."""
    EOL[path] = "\r\n" if b"\r\n" in path.read_bytes() else "\n"
    return path.read_text(encoding="utf-8")


def save(path: Path, text: str) -> None:
    path.write_text(text.replace("\n", EOL[path]), encoding="utf-8", newline="")


def apply(text: str, pairs: list[tuple[str, str]], what: str) -> str:
    for a, b in pairs:
        n = text.count(a)
        assert n == 1, f"{what}: {n} matches for {a[:90]!r}"
        text = text.replace(a, b)
    return text


s = load(P)
assert "def mux_reused_audio" in s and "REUSE_AUDIO_MD5" in s and "IDR_ARGS" in s, "apply patch_v23 first (v23-src)"
assert "def audio_streams" in s, "apply patch_v23b first (commit 135f3c1: audio_streams() + exactly one audio stream)"
assert "V24_SOUND" not in s, "v24 already applied"
R = [
    ('''REUSE_AUDIO_DUR = 87.5                                   # seconds (AAC stream duration, ffprobe)
''',
     f'''REUSE_AUDIO_DUR = 87.5                                   # seconds (AAC stream duration, ffprobe)
V24_SOUND = True          # v24: the sound-arc master (sound_v24.py) instead of the reused v22 stream; False: v23 exactly
V24_MASTER = WORK / "audio_v24" / "{MASTER_NAME}"      # 48 kHz stereo float32 PCM, 87.5 s
V24_AAC_EXTRA = {AAC_EXTRA!r}     # extra AAC encoder options (v24b: -cutoff 20000)
V24_MASTER_SHA256 = "{MASTER_SHA256}"
V24_MASTER_SAMPLES = {MASTER_SAMPLES}
V24_AUDIO_MD5 = "{AUDIO_MD5}"     # packet md5 of its AAC 320k encode (ffmpeg 8.1.2)
V24_PICTURE_FROM = OUT / "moonshot_v23.mp4"   # stream-copied picture (v24 = v23's picture); None: encode WORK/comp.mp4
V24_PICTURE_MD5 = "{PICTURE_MD5}"     # v23's video packet md5


def v24_master_check() -> None:
    """v24: the master is authenticated by content (sha256 + sample count), not by its name."""
    if not V24_MASTER.is_file():
        raise SystemExit(f"V24_MASTER {{V24_MASTER}} missing (run sound_v24.py)")
    h = hashlib.sha256()
    with open(V24_MASTER, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    if h.hexdigest() != V24_MASTER_SHA256:
        raise SystemExit(f"V24_MASTER sha256 {{h.hexdigest()}}, pinned {{V24_MASTER_SHA256}}")
    ts = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration_ts",
                         "-of", "csv=p=0", str(V24_MASTER)], capture_output=True, text=True).stdout.strip()
    if ts != str(V24_MASTER_SAMPLES):
        raise SystemExit(f"V24_MASTER: {{ts or '(none)'}} samples, pinned {{V24_MASTER_SAMPLES}}")


def video_md5(path: Path) -> str:
    out = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "md5", "-"],
                         capture_output=True, text=True)
    return out.stdout.strip().removeprefix("MD5=") if out.returncode == 0 else ""


def mux_v24_master() -> None:
    """v24: picture (stream copy of V24_PICTURE_FROM, verified; or WORK/comp.mp4 encoded as mux_reused_audio does) +
    the AAC 320k encode of the pinned master. .part file -> frames, audio md5 + duration, (copied) video md5 -> rename."""
    v24_master_check()
    if V24_PICTURE_FROM is not None and video_md5(V24_PICTURE_FROM) != V24_PICTURE_MD5:
        raise SystemExit(f"V24_PICTURE_FROM {{V24_PICTURE_FROM}}: video packet md5 is not the pinned v23 picture")
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"moonshot_v{{VERSION}}.mp4"
    if dst.exists():
        raise SystemExit(f"{{dst}} exists; versions are never overwritten")
    part = dst.with_name(dst.stem + ".part.mp4")
    if V24_PICTURE_FROM is not None:
        vin, vargs = str(V24_PICTURE_FROM), ["-c:v", "copy"]
    else:
        vin = str(WORK / "comp.mp4")
        vargs = ["-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS, "-pix_fmt", "yuv420p", "-r", str(FPS),
                 "-vf", "setsar=1", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
                 "-x264-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709"]
    try:
        run(["ffmpeg", "-v", "error", "-y", "-i", vin, "-i", str(V24_MASTER), "-map", "0:v:0", "-map", "1:a:0", *vargs,
             "-c:a", "aac", "-b:a", "320k", *V24_AAC_EXTRA, "-movflags", "+faststart", str(part)])
        got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                  "stream=nb_read_frames", "-of", "csv=p=0", str(part)],
                                 capture_output=True, text=True).stdout.strip() or 0)
        if got != NFRAMES:
            raise SystemExit(f"mux: {{part.name}} decodes to {{got}} frames, expected {{NFRAMES}}; deleted")
        if audio_md5(part) != V24_AUDIO_MD5:
            raise SystemExit(f"mux: {{part.name}} audio is not the pinned v24 encode (encoder changed?); deleted")
        if audio_streams(part) != 1:      # v23b rule: exactly one (authenticated) audio stream
            raise SystemExit(f"mux: {{part.name}} has {{audio_streams(part)}} audio streams, expected exactly 1; deleted")
        dur = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                              "-of", "csv=p=0", str(part)], capture_output=True, text=True).stdout.strip()
        if not dur or abs(float(dur) - TOTAL) > 0.001:
            raise SystemExit(f"mux: {{part.name}} audio {{dur or '(none)'}} s, expected {{TOTAL}}; deleted")
        if V24_PICTURE_FROM is not None and video_md5(part) != V24_PICTURE_MD5:
            raise SystemExit(f"mux: {{part.name}} video packets differ from the copied picture; deleted")
        os.replace(part, dst)
    finally:
        part.unlink(missing_ok=True)
    print(f"wrote {{dst}} (v24 master AAC, md5 + {{NFRAMES}} frames verified; picture "
          f"{{'stream-copied from ' + V24_PICTURE_FROM.name if V24_PICTURE_FROM else 'encoded from comp.mp4'}})")
'''),
    ('''def stage_mix() -> None:
    if REUSE_AUDIO_FROM is not None:      # v22 (R2)
''',
     '''def stage_mix() -> None:
    if V24_SOUND:                         # v24: the sound-arc master (verified) instead of the v22 stream
        mux_v24_master()
        return
    if REUSE_AUDIO_FROM is not None:      # v22 (R2)
'''),
]
s = apply(s, R, "build")
save(P, s)
print(f"v24{'b' if V24B else ''}: build {len(R)} replacements. Then: py build.py mix 24 (needs work/audio_v24/master_v24.wav and "
      "versions/moonshot_v23.mp4; no other stage re-renders).")
