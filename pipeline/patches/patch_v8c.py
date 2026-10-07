"""v8c (Codex review of patch_v8): the synthesized SFX stem (heartbeat, ticks, master alarm, flash hit) was
rendered on the v1-v7 timeline. Cut old 33.3-40.0 out of it (20 ms crossfade) so every cue at >= old 40.0
lands exactly -6.7 s, matching the re-timed picture, dialogue and music. Apply after patch_v8b.py."""
import sys
import os
from pathlib import Path

CRAFTWORK = Path(os.environ.get("CRAFTWORK", "CraftWork"))   # workspace root (media, fonts, renders)

W = (CRAFTWORK / "inbox/moonshot/work")
P = Path(sys.argv[1]) if len(sys.argv) > 1 else W / "build.py"
s = P.read_text(encoding="utf-8")
a = '''               + load_stem(AUD / "sfx.wav") * 10 ** (-4.0 / 20))'''
b = '''               + synth_sfx_v8() * 10 ** (-4.0 / 20))'''
assert s.count(a) == 1, "sfx.wav load not found"
s = s.replace(a, b)
helper = '''

def synth_sfx_v8() -> np.ndarray:
    """The synth SFX stem was rendered for the 88.5 s cut: drop old 33.3-40.0 so later cues shift -6.7 s."""
    old = load_stem(AUD / "sfx.wav")             # padded/truncated to the CURRENT TOTAL by load_stem
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(AUD / "sfx.wav"), "-ac", "2", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    full = np.frombuffer(raw, np.float32).reshape(-1, 2)
    a0, a1 = int(33.3 * SR), int(40.0 * SR)
    xf = int(0.02 * SR)
    head = full[:a0].copy()
    tail = full[a1:].copy()
    ramp = np.linspace(0, 1, xf, dtype=np.float32)[:, None]
    head[-xf:] = head[-xf:] * (1 - ramp) + tail[:xf] * ramp
    out = np.concatenate([head, tail[xf:]])
    n = len(old)
    res = np.zeros_like(old)
    res[:min(n, len(out))] = out[:n]
    return res
'''
anchor = "def stage_mix() -> None:"
assert s.count(anchor) == 1
s = s.replace(anchor, helper.strip("\n") + "\n\n\n" + anchor)
P.write_text(s, encoding="utf-8")
print("v8c: synth SFX stem retimed")
