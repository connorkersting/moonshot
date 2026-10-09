"""v23b: the Codex v23 adversarial review's HIGH finding (exports/moonshot/codex_v23_review.md). mux_reused_audio mapped
EVERY audio track of the source ("-map 1:a") while both audio checks inspect only a:0, so a source with an extra,
unauthenticated track could publish it. Now: map exactly 1:a:0, and the .part file must hold exactly one audio stream
before it is renamed. No output change for a one-track source (moonshot_v23.mp4 has one video + one audio stream).

    py patch_v23b.py            # the real build.py
    py patch_v23b.py BUILD.py   # a copy (dry run)

Deferred, logged in PROGRESS.md (process risks, not in v23's output): the s17 segment is not bound to the ascent
manifest (the v23 chain regenerated s17: shots 23 17); the RIFE preflight checks cache integrity, not freshness.
"""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

P = Path(sys.argv[1]) if len(sys.argv) > 1 else (CRAFTWORK / "inbox/moonshot/work/build.py")
raw = P.read_bytes()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
assert "def mux_reused_audio" in s, "apply patch_v23 first"
assert "audio_streams(part)" not in s, "v23b already applied"
R = [
    ('''             "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS,''',
     '''             "-map", "0:v", "-map", "1:a:0", "-c:v", "libx264", "-crf", "18", "-preset", "slow", *IDR_ARGS,'''),
    ('''        if audio_md5(part) != REUSE_AUDIO_MD5:
            raise SystemExit(f"mux: {part.name} audio is not the pinned stream; deleted")
''',
     '''        if audio_md5(part) != REUSE_AUDIO_MD5:
            raise SystemExit(f"mux: {part.name} audio is not the pinned stream; deleted")
        if audio_streams(part) != 1:     # v23b (Codex): no second, unauthenticated audio track can ride along
            raise SystemExit(f"mux: {part.name} has {audio_streams(part)} audio streams, expected exactly 1; deleted")
'''),
    ('''def mux_reused_audio(src: Path) -> None:''',
     '''def audio_streams(path: Path) -> int:
    """v23b: the number of audio streams in path."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of",
                          "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    return len([x for x in out.split() if x.strip()])


def mux_reused_audio(src: Path) -> None:'''),
]
for a, b in R:
    n = s.count(a)
    assert n == 1, f"{n} matches for {a[:80]!r}"
    s = s.replace(a, b)
P.write_bytes((s.replace("\n", "\r\n") if crlf else s).encode("utf-8"))
print(f"v23b: {len(R)} replacements in {P.name} (map 1:a:0 + exactly one audio stream)")
