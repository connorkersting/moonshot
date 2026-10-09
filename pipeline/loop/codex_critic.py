"""Independent second critic: OpenAI Codex (read-only sandbox) scores a version from the same evidence the
Fable editor sees (contact sheet, 360p key frames, the measured audio QC report).

    py codex_critic.py N        -> exports/moonshot/qc/vN/codex_critic.json (+ .md raw reply)

Same 10 categories and 1-10 scale as the editor, strict JSON output, no version history or previous scores
in the prompt (so its numbers are not anchored on ours).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

WORK = Path(__file__).resolve().parent
QC = WORK.parent.parent.parent / "exports" / "moonshot" / "qc"
CATS = ["hook", "pacing", "visual_variety", "motion_design", "typography_collisions", "colour",
        "sound_design_mix", "captions", "storytelling", "overall"]
MAX_KEYS = 14

PROMPT = """You are a demanding senior film editor at a top trailer house. Review this {total:.1f}-second Apollo 11 trailer
("MOONSHOT", cut from real NASA footage, 1969 mission audio and public-domain orchestral recordings). You cannot
watch or hear it: the attached images are a 24-frame contact sheet (timestamps in yellow) and phone-size key frames
(file name = seconds), and below is the MEASURED audio report (section loudness, dialogue-to-music ratio per line,
click scan, speech-recognition recall). Judge only from this evidence.

Score 1-10 (half points allowed) on: hook, pacing, visual_variety, motion_design, typography_collisions, colour,
sound_design_mix (from the measurements), captions, storytelling, overall ("would a top YouTube editor ship this").
Then give the 5 highest-impact fixes with timestamps.

Reply with ONLY one JSON object, no prose before or after:
{"scores": {"hook": x, "pacing": x, "visual_variety": x, "motion_design": x, "typography_collisions": x,
"colour": x, "sound_design_mix": x, "captions": x, "storytelling": x, "overall": x},
"top_fixes": ["t=..s: ...", "..."]}

MEASURED AUDIO REPORT:
"""


def codex_bin() -> str:
    for name in ("codex.cmd", "codex"):
        found = shutil.which(name)
        if found:
            return found
    home = Path.home() / ".local" / "bin" / "codex.cmd"
    if home.exists():
        return str(home)
    raise SystemExit("codex CLI not found")


def main(n: int) -> None:
    vdir = QC / f"v{n}"
    audio = (vdir / "audio_qc.md").read_text(encoding="utf-8")
    audio = re.sub(r"moonshot_v\d+\.mp4", "trailer.mp4", audio)
    keys = sorted(vdir.glob("k360_*.jpg"))
    step = max(1, len(keys) // MAX_KEYS)
    images = [vdir / "contact.jpg"] + keys[::step][:MAX_KEYS]
    cmd = [codex_bin(), "exec", "-s", "read-only", "--skip-git-repo-check"]
    for img in images:
        cmd += ["-i", str(img)]
    cmd.append("-")                       # prompt via stdin: `-i` takes several values and would eat a trailing prompt
    total = float(re.search(r"^TOTAL = ([\d.]+)", (WORK / "build.py").read_text(encoding="utf-8"), re.M).group(1))
    out = subprocess.run(cmd, input=PROMPT.replace("{total:.1f}", f"{total:.1f}") + audio, capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=1800)
    raw = out.stdout
    (vdir / "codex_critic.md").write_text(raw + "\n\n--- stderr tail ---\n" + out.stderr[-2000:], encoding="utf-8")
    blocks = re.findall(r"\{.*\"scores\".*\}", raw, flags=re.S)
    if not blocks:
        raise SystemExit(f"no JSON in Codex reply (see {vdir / 'codex_critic.md'})")
    data = json.loads(blocks[-1][: blocks[-1].rfind("}") + 1])
    missing = [c for c in CATS if c not in data.get("scores", {})]
    if missing:
        raise SystemExit(f"Codex reply missing categories: {missing}")
    (vdir / "codex_critic.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"v{n} Codex critic overall {data['scores']['overall']}: " +
          ", ".join(f"{c}={data['scores'][c]}" for c in CATS[:-1]))


if __name__ == "__main__":
    main(int(sys.argv[1]))
