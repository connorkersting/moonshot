"""Draw docs/score_chart.png: the senior-editor critic's overall score per version.
v3, v6 and v12 have no editor score (v3 and v12 were judged by blind A/B only; v6 lost its A/B and was reverted)."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SCORES: dict[int, float | None] = {1: 5.5, 2: 6.5, 3: None, 4: 6.0, 5: 6.0, 6: None, 7: 6.5, 8: 6.5, 9: 7.0, 10: 7.5, 11: 7.5, 12: None}


def main(out: Path, extra: list[str]) -> None:
    scores = dict(SCORES)
    for item in extra:                      # e.g. "11=7.5" to add the last version's score
        v, s = item.split("=")
        scores[int(v)] = float(s)
    xs = [v for v, s in scores.items() if s is not None]
    ys = [scores[v] for v in xs]
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=120)
    ax.plot(xs, ys, marker="o", color="#ffb040", linewidth=2.2)
    for x, y in zip(xs, ys):
        ax.annotate(f"{y:g}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9, color="#dddddd")
    for v, s in scores.items():
        if s is None:
            ax.axvline(v, color="#555555", linewidth=1, linestyle=":")
            ax.text(v, 5.15, "A/B only" if v in (3, 12) else "reverted", rotation=90, fontsize=8, color="#999999", ha="right")
    ax.set_xticks(sorted(scores))
    ax.set_xticklabels([f"v{v}" for v in sorted(scores)])
    ax.set_ylim(5, 8.5)
    ax.axhline(8, color="#666666", linewidth=0.8, linestyle="--")
    ax.text(min(scores) - 0.3, 8.05, "extras unlock at 8", fontsize=8, color="#999999")
    ax.set_ylabel("editor overall (1-10)", color="#dddddd")
    ax.set_title("Senior-editor critic score per version", color="#ffffff", fontsize=11)
    fig.patch.set_facecolor("#111111")
    ax.set_facecolor("#111111")
    ax.tick_params(colors="#cccccc")
    for sp in ax.spines.values():
        sp.set_color("#444444")
    fig.tight_layout()
    fig.savefig(out, facecolor=fig.get_facecolor())
    print(f"wrote {out}")


if __name__ == "__main__":
    main(Path(__file__).resolve().parent.parent / "docs" / "score_chart.png", sys.argv[1:])
