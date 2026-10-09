"""Study 1 supplement: repeat means vs the original in-loop editor scores (descriptive only).

Why this file exists: `s1_analyze.py` was frozen on 2026-10-07 and looks for rows with critic == "editor" in
data/raw/critic_scores.csv. The v28 data refresh renamed that critic to "fable_editor" (the editor's own review)
and added "fable_editor_rescored" (a later review re-scoring an earlier version). With the old label the frozen
script finds no original scores and prints "No original scores for the versions analysed". This script leaves the
frozen script untouched, reuses its own functions, and uses the renamed label. It reads only "fable_editor" rows:
the editor's own review of each version, which is what the pre-registered comparison meant. Rescored rows are left
out because they were scored in a later sitting with other versions in view.

Run (from C:\\dev\\moonshot-repo\\analytics):
    set PYTHONUTF8=1 && py studies\\s1_vs_original.py

Writes studies/s1/results_vs_original.csv (per version x category) and studies/s1/results_vs_original.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s1_analyze as s1  # noqa: E402  (frozen analysis; functions reused unchanged)

ORIGINAL_CRITIC_LABEL = "fable_editor"


def load_original_renamed(path: Path) -> dict[tuple[int, str], float]:
    """Same as s1_analyze.load_original, but with the critic label used since the v28 data refresh."""
    frame = pd.read_csv(path)
    frame = frame[frame["critic"] == ORIGINAL_CRITIC_LABEL]
    grouped = frame.groupby(["version", "category"])["score"].mean()
    return {(int(v), str(c)): float(s) for (v, c), s in grouped.items()}


def main() -> int:
    key = json.loads((s1.STUDY_DIR / "key.json").read_text(encoding="utf-8"))
    wide, status = s1.load_results(s1.STUDY_DIR / "results", key)
    if wide.empty:
        print("no usable results")
        return 1
    original = load_original_renamed(s1.ORIGINAL_SCORES)
    summary = s1.per_version_summary(wide, original)
    comparison, extra = s1.original_comparison(summary)

    out_csv = s1.STUDY_DIR / "results_vs_original.csv"
    summary.to_csv(out_csv, index=False, encoding="utf-8")

    overall = summary[summary["category"] == s1.PRIMARY][
        ["version", "n", "mean", "sd", "original_in_loop_score", "mean_minus_original"]]
    lines = [
        "# Study 1 supplement: repeat means vs the original in-loop editor scores\n",
        f"Descriptive only. Original = critic `{ORIGINAL_CRITIC_LABEL}` in `data/raw/critic_scores.csv` (the "
        "editor's own review of that version). See the docstring of `s1_vs_original.py` for why this is a "
        "separate file.\n",
        f"Usable evaluations: {int((status['status'] == 'ok').sum())} of {len(key)}.\n",
        "## `overall` by version\n",
        s1.md_table(overall) + "\n",
        "## Every category, versions with an original score\n",
        s1.md_table(comparison) + "\n" if not comparison.empty else "No original scores found.\n",
    ]
    for name, value in extra.items():
        lines.append(f"- {name}: {s1.fmt(value)}\n")
    lines.append("\nThe in-loop editor saw the run's history and its own earlier scores; the repeats saw neither. "
                 "A gap therefore mixes anchoring, context and sampling noise, and is not a measure of anything on "
                 "its own.\n")
    (s1.STUDY_DIR / "results_vs_original.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_csv.name} and results_vs_original.md; versions with an original overall: "
          f"{int(overall['original_in_loop_score'].notna().sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
