"""Study 1 analysis: same-model repeatability of the editor critic.

Reads studies/s1/results/<eval_id>.json (one per evaluation) and studies/s1/key.json, and writes
  studies/s1/results_summary.csv    per version x category: n, mean, SD, min, max, range, original in-loop score
  studies/s1/results_agreement.csv  per category: ICC(2,1) + bootstrap CI, ICC(1,1), Kendall's W, Spearman, SDs
  studies/s1/results_status.csv     per evaluation: ok / missing / malformed (with the reason)
  studies/s1/results_summary.md     the same, readable

Run (from C:\\dev\\moonshot-repo\\analytics):
    set PYTHONUTF8=1 && py studies\\s1_analyze.py
    set PYTHONUTF8=1 && py studies\\s1_analyze.py --selftest     (synthetic data in a temp folder, deleted after)

numpy + pandas only; scipy is not installed in this project. Kendall's W uses a permutation p-value and the
ICC confidence interval is a percentile bootstrap over versions, so no distribution tables are needed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

STUDY_DIR = Path(__file__).resolve().parent / "s1"
ORIGINAL_SCORES = Path(__file__).resolve().parents[1] / "data" / "raw" / "critic_scores.csv"
CATEGORIES: list[str] = ["hook", "pacing", "variety", "motion", "type", "color", "sound", "captions", "story",
                         "overall"]
PRIMARY = "overall"
N_BOOT_DEFAULT = 5000
N_PERM_DEFAULT = 10000
SEED_DEFAULT = 20261009


# ---------------------------------------------------------------------------------------------- parsing
def extract_json_object(text: str) -> dict | None:
    """Last JSON object in `text` that has a "scores" key (handles fenced blocks and chatter around it)."""
    decoder = json.JSONDecoder()
    found: dict | None = None
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "scores" in obj:
            found = obj
    if found is not None:
        return found
    # a wrapper such as {"result": "<critic message>"}: look inside string values
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(whole, dict):
        for value in whole.values():
            if isinstance(value, str) and "scores" in value:
                inner = extract_json_object(value)
                if inner is not None:
                    return inner
    return None


def parse_result(path: Path) -> tuple[dict[str, float], list[str], list[str]]:
    """Return (scores, top_fixes, warnings) or raise ValueError with the reason the file is unusable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"unreadable: {exc}") from exc
    obj = extract_json_object(text)
    if obj is None:
        raise ValueError("no JSON object with a 'scores' key")
    scores = obj["scores"]
    if not isinstance(scores, dict):
        raise ValueError("'scores' is not an object")
    missing = [c for c in CATEGORIES if c not in scores]
    extra = [c for c in scores if c not in CATEGORIES]
    if missing or extra:
        raise ValueError(f"score keys wrong: missing {missing}, unexpected {extra}")
    clean: dict[str, float] = {}
    warnings: list[str] = []
    for category in CATEGORIES:
        value = scores[category]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"score for {category!r} is not a number: {value!r}")
        if not 1 <= value <= 10:
            raise ValueError(f"score for {category!r} out of range 1-10: {value}")
        if (value * 2) % 1 != 0:
            warnings.append(f"{category}={value} not on the half-point grid")
        clean[category] = float(value)
    fixes = obj.get("top_fixes", [])
    if not isinstance(fixes, list):
        warnings.append("top_fixes is not a list")
        fixes = []
    return clean, [str(f) for f in fixes], warnings


def load_results(results_dir: Path, key: dict[str, dict[str, int]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(wide scores one row per usable evaluation, status one row per expected evaluation / stray file)."""
    rows: list[dict[str, object]] = []
    status: list[dict[str, object]] = []
    for eval_id, meta in sorted(key.items()):
        path = results_dir / f"{eval_id}.json"
        base = {"eval_id": eval_id, "version": meta["version"], "repeat": meta["repeat"]}
        if not path.exists():
            status.append({**base, "status": "missing", "detail": "no results file"})
            continue
        try:
            scores, fixes, warnings = parse_result(path)
        except ValueError as exc:
            status.append({**base, "status": "malformed", "detail": str(exc)})
            continue
        rows.append({**base, **scores, "n_fixes": len(fixes)})
        status.append({**base, "status": "ok", "detail": "; ".join(warnings)})
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.json")):
            if path.stem not in key:
                status.append({"eval_id": path.stem, "version": None, "repeat": None, "status": "unknown_file",
                               "detail": "file name is not an eval_id in key.json; ignored"})
    columns = ["eval_id", "version", "repeat", *CATEGORIES, "n_fixes"]
    return pd.DataFrame(rows, columns=columns), pd.DataFrame(status)


# ---------------------------------------------------------------------------------------------- statistics
def icc_balanced(x: np.ndarray) -> dict[str, float]:
    """Shrout & Fleiss ICCs for an n-subjects x k-raters matrix with no missing cells.

    icc1 = ICC(1,1) one-way; icc2 = ICC(2,1) two-way random, absolute agreement, single rating;
    icc3 = ICC(3,1) two-way mixed, consistency. Also returns the mean squares.
    """
    n, k = x.shape
    grand = x.mean()
    row_means = x.mean(axis=1)
    col_means = x.mean(axis=0)
    ssr = k * float(((row_means - grand) ** 2).sum())
    ssc = n * float(((col_means - grand) ** 2).sum())
    sst = float(((x - grand) ** 2).sum())
    sse = sst - ssr - ssc
    msr = ssr / (n - 1)
    msc = ssc / (k - 1)
    mse = sse / ((n - 1) * (k - 1))
    msw = (ssc + sse) / (n * (k - 1))

    def ratio(num: float, den: float) -> float:
        return num / den if den > 1e-12 else float("nan")

    return {
        "icc1": ratio(msr - msw, msr + (k - 1) * msw),
        "icc2": ratio(msr - mse, msr + (k - 1) * mse + k * (msc - mse) / n),
        "icc3": ratio(msr - mse, msr + (k - 1) * mse),
        "msr": msr, "msc": msc, "mse": mse, "msw": msw,
    }


def icc_oneway_unbalanced(groups: list[np.ndarray]) -> float:
    """ICC(1,1) when subjects have different numbers of ratings (uses k0, the average group size)."""
    groups = [g for g in groups if len(g) >= 1]
    a = len(groups)
    sizes = np.array([len(g) for g in groups], dtype=float)
    total = sizes.sum()
    if a < 2 or total <= a:
        return float("nan")
    grand = np.concatenate(groups).mean()
    ssb = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    ssw = sum(((g - g.mean()) ** 2).sum() for g in groups)
    msb = ssb / (a - 1)
    msw = ssw / (total - a)
    k0 = (total - (sizes ** 2).sum() / total) / (a - 1)
    den = msb + (k0 - 1) * msw
    return (msb - msw) / den if den > 1e-12 else float("nan")


def bootstrap_icc2(x: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float, int]:
    """Percentile 95% CI for ICC(2,1), resampling subjects (versions) with replacement."""
    n = x.shape[0]
    draws: list[float] = []
    for _ in range(n_boot):
        sample = x[rng.integers(0, n, size=n)]
        value = icc_balanced(sample)["icc2"]
        if math.isfinite(value):
            draws.append(value)
    if len(draws) < max(20, n_boot // 10):
        return float("nan"), float("nan"), len(draws)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return float(lo), float(hi), len(draws)


def kendall_w(x: np.ndarray) -> float:
    """Kendall's coefficient of concordance for n subjects (rows) ranked by m raters (columns), tie-corrected."""
    n, m = x.shape
    ranks = np.column_stack([pd.Series(x[:, j]).rank(method="average").to_numpy() for j in range(m)])
    rank_sums = ranks.sum(axis=1)
    s = float(((rank_sums - rank_sums.mean()) ** 2).sum())
    tie_term = 0.0
    for j in range(m):
        _, counts = np.unique(x[:, j], return_counts=True)
        tie_term += float((counts ** 3 - counts).sum())
    den = m ** 2 * (n ** 3 - n) - m * tie_term
    return 12.0 * s / den if den > 0 else float("nan")


def kendall_w_perm_p(x: np.ndarray, n_perm: int, rng: np.random.Generator) -> float:
    """P(W_perm >= W_obs) when each repeat's scores are shuffled independently across versions."""
    observed = kendall_w(x)
    if not math.isfinite(observed):
        return float("nan")
    hits = 0
    for _ in range(n_perm):
        shuffled = np.column_stack([rng.permutation(x[:, j]) for j in range(x.shape[1])])
        if kendall_w(shuffled) >= observed - 1e-12:
            hits += 1
    return (hits + 1) / (n_perm + 1)


def pairwise_spearman(x: np.ndarray) -> tuple[float, float, float]:
    """Mean, min and max Spearman rho over all pairs of repeats (columns)."""
    ranks = np.column_stack([pd.Series(x[:, j]).rank(method="average").to_numpy() for j in range(x.shape[1])])
    rhos: list[float] = []
    for i in range(ranks.shape[1]):
        for j in range(i + 1, ranks.shape[1]):
            a, b = ranks[:, i], ranks[:, j]
            if a.std() == 0 or b.std() == 0:
                rhos.append(float("nan"))
            else:
                rhos.append(float(np.corrcoef(a, b)[0, 1]))
    arr = np.array(rhos, dtype=float)
    if np.isnan(arr).all():
        return float("nan"), float("nan"), float("nan")
    return float(np.nanmean(arr)), float(np.nanmin(arr)), float(np.nanmax(arr))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Spearman rho between two vectors (average ranks)."""
    ra = pd.Series(a).rank(method="average").to_numpy()
    rb = pd.Series(b).rank(method="average").to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.corrcoef(ra, rb)[0, 1])


def agreement_for_category(wide: pd.DataFrame, category: str, n_boot: int, n_perm: int,
                           rng: np.random.Generator) -> dict[str, object]:
    """All agreement statistics for one category."""
    pivot = wide.pivot(index="version", columns="repeat", values=category)
    complete = pivot.dropna()
    groups = [row.dropna().to_numpy(dtype=float) for _, row in pivot.iterrows()]
    out: dict[str, object] = {
        "category": category,
        "n_versions_total": int(pivot.shape[0]),
        "n_versions_complete": int(complete.shape[0]),
        "n_ratings": int(sum(len(g) for g in groups)),
    }
    nan = float("nan")
    out.update({"icc21": nan, "icc21_ci_lo": nan, "icc21_ci_hi": nan, "icc21_boot_ok": 0, "icc11_complete": nan,
                "kendall_w": nan, "kendall_w_perm_p": nan, "spearman_mean": nan, "spearman_min": nan,
                "spearman_max": nan})
    out["icc11_all_ratings"] = icc_oneway_unbalanced(groups)
    # within-version SD pooled over every version with at least 2 ratings (no need for complete cells)
    variances = [g.var(ddof=1) for g in groups if len(g) >= 2]
    sd_within = math.sqrt(float(np.mean(variances))) if variances else nan
    means = np.array([g.mean() for g in groups if len(g) >= 1])
    out["sd_within_pooled"] = sd_within
    out["sd_between_version_means"] = float(means.std(ddof=1)) if len(means) >= 2 else nan
    out["repeatability_coef_2_77_sd"] = 2.77 * sd_within if math.isfinite(sd_within) else nan
    if complete.shape[0] >= 3 and complete.shape[1] >= 2:
        x = complete.to_numpy(dtype=float)
        icc = icc_balanced(x)
        lo, hi, ok = bootstrap_icc2(x, n_boot, rng)
        out.update({"icc21": icc["icc2"], "icc21_ci_lo": lo, "icc21_ci_hi": hi, "icc21_boot_ok": ok,
                    "icc11_complete": icc["icc1"], "kendall_w": kendall_w(x),
                    "kendall_w_perm_p": kendall_w_perm_p(x, n_perm, rng)})
        mean_rho, min_rho, max_rho = pairwise_spearman(x)
        out.update({"spearman_mean": mean_rho, "spearman_min": min_rho, "spearman_max": max_rho})
    return out


# ---------------------------------------------------------------------------------------------- tables
def per_version_summary(wide: pd.DataFrame, original: pd.DataFrame) -> pd.DataFrame:
    """Per version x category: n, mean, SD, min, max, range, original in-loop score, mean minus original."""
    rows: list[dict[str, object]] = []
    for version, frame in wide.groupby("version"):
        for category in CATEGORIES:
            values = frame[category].to_numpy(dtype=float)
            orig = original.get((int(version), category), float("nan"))
            mean = float(values.mean())
            rows.append({
                "version": int(version), "category": category, "n": len(values), "mean": mean,
                "sd": float(values.std(ddof=1)) if len(values) > 1 else float("nan"),
                "min": float(values.min()), "max": float(values.max()),
                "range": float(values.max() - values.min()),
                "original_in_loop_score": orig,
                "mean_minus_original": mean - orig if math.isfinite(orig) else float("nan"),
            })
    return pd.DataFrame(rows)


def load_original(path: Path) -> dict[tuple[int, str], float]:
    """Original in-loop editor scores keyed (version, category); mean if a version was scored more than once."""
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    frame = frame[frame["critic"] == "editor"]
    grouped = frame.groupby(["version", "category"])["score"].mean()
    return {(int(v), str(c)): float(s) for (v, c), s in grouped.items()}


def fmt(value: object, digits: int = 2) -> str:
    """Compact number formatting for the markdown tables."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def md_table(frame: pd.DataFrame, digits: int = 2) -> str:
    """Markdown pipe table without needing `tabulate`."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    is_count = [str(c) in {"version", "repeat", "n"} or str(c).startswith("n_") for c in frame.columns]

    def cell(value: object, count: bool) -> str:
        if count and isinstance(value, (int, float, np.integer, np.floating)) and math.isfinite(float(value)):
            return str(int(value))
        return fmt(value, digits)

    body = ["| " + " | ".join(cell(v, c) for v, c in zip(row, is_count)) + " |"
            for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def original_comparison(summary: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Descriptive repeat-mean minus original, per category over versions that have an original."""
    has = summary[summary["original_in_loop_score"].notna()]
    rows: list[dict[str, object]] = []
    for category in CATEGORIES:
        sub = has[has["category"] == category]
        if sub.empty:
            continue
        rows.append({
            "category": category, "n_versions": len(sub),
            "mean_diff_repeat_minus_original": float(sub["mean_minus_original"].mean()),
            "mean_abs_diff": float(sub["mean_minus_original"].abs().mean()),
            "max_abs_diff": float(sub["mean_minus_original"].abs().max()),
        })
    extra: dict[str, float] = {}
    overall = has[has["category"] == PRIMARY]
    if len(overall) >= 3:
        extra["spearman_overall_repeat_mean_vs_original"] = spearman(overall["mean"].to_numpy(),
                                                                     overall["original_in_loop_score"].to_numpy())
        extra["n_versions_with_original"] = float(len(overall))
    return pd.DataFrame(rows), extra


def caveat_text() -> str:
    return (
        "## Reading this honestly\n\n"
        "- This measures **same-model repeatability** (fresh contexts, identical evidence). A critic can be "
        "perfectly repeatable and still be wrong; it says nothing about accuracy.\n"
        "- The critic cannot hear: `sound` rests on audio measurements, and v1 had only whole-mix loudness.\n"
        "- 8 versions x 3 repeats: the ICC confidence interval is wide by construction, and the bootstrap "
        "resamples only 8 subjects. Treat the interval as the finding, not the point estimate.\n"
        "- The three repeats of a version are exchangeable fresh contexts, so the repeat labels carry no meaning; "
        "ICC(2,1) is reported as pre-registered and ICC(1,1) is the matching one-way figure.\n"
        "- The comparison with the original in-loop scores is descriptive. The in-loop editor saw history and "
        "previous scores; the repeats saw none, so a difference mixes anchoring with sampling noise.\n"
        "- Only versions 1, 2, 4, 8, 10 and 11 have an original editor score; v6 and v13 have none.\n"
    )


# ---------------------------------------------------------------------------------------------- driver
def analyse(results_dir: Path, key_path: Path, out_dir: Path, n_boot: int = N_BOOT_DEFAULT,
            n_perm: int = N_PERM_DEFAULT, seed: int = SEED_DEFAULT,
            original_path: Path = ORIGINAL_SCORES, prompt_path: Path | None = None,
            manifest_path: Path | None = None) -> dict[str, object]:
    """Run the full Study 1 analysis and write the output files to out_dir."""
    key: dict[str, dict[str, int]] = json.loads(key_path.read_text(encoding="utf-8"))
    wide, status = load_results(results_dir, key)
    out_dir.mkdir(parents=True, exist_ok=True)
    status.to_csv(out_dir / "results_status.csv", index=False, encoding="utf-8")
    counts = status["status"].value_counts().to_dict()
    if wide.empty:
        raise SystemExit("no usable results; nothing to analyse")

    warnings: list[str] = []
    if prompt_path is not None and manifest_path is not None and manifest_path.exists() and prompt_path.exists():
        recorded = json.loads(manifest_path.read_text(encoding="utf-8")).get("prompt_sha256")
        actual = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
        if recorded != actual:
            warnings.append("prompt.md differs from the hash recorded at prepare time: the prompt was not frozen")

    rng = np.random.default_rng(seed)
    original = load_original(original_path)
    summary = per_version_summary(wide, original)
    summary.to_csv(out_dir / "results_summary.csv", index=False, encoding="utf-8")
    agreement = pd.DataFrame([agreement_for_category(wide, c, n_boot, n_perm, rng) for c in CATEGORIES])
    agreement.to_csv(out_dir / "results_agreement.csv", index=False, encoding="utf-8")
    comparison, extra = original_comparison(summary)

    primary = agreement[agreement["category"] == PRIMARY].iloc[0]
    overall_table = summary[summary["category"] == PRIMARY][
        ["version", "n", "mean", "sd", "min", "max", "range", "original_in_loop_score", "mean_minus_original"]]
    grid = summary.pivot(index="version", columns="category", values="mean")[CATEGORIES].reset_index()
    problems = status[status["status"].isin(["missing", "malformed", "unknown_file"])]
    agree_cols = ["category", "n_versions_complete", "icc21", "icc21_ci_lo", "icc21_ci_hi", "icc11_all_ratings",
                  "kendall_w", "kendall_w_perm_p", "spearman_mean", "sd_within_pooled",
                  "sd_between_version_means", "repeatability_coef_2_77_sd"]

    lines: list[str] = ["# Study 1: editor critic repeatability, results\n"]
    lines.append(f"Evaluations expected {len(key)}; usable {counts.get('ok', 0)}; "
                 f"missing {counts.get('missing', 0)}; malformed {counts.get('malformed', 0)}.\n")
    for w in warnings:
        lines.append(f"**WARNING:** {w}\n")
    if not problems.empty:
        lines.append(md_table(problems[["eval_id", "version", "repeat", "status", "detail"]]) + "\n")
    lines.append("## Primary: `overall` agreement across repeats\n")
    lines.append(
        f"- ICC(2,1), single rating, absolute agreement: **{fmt(primary['icc21'])}** "
        f"(95% percentile bootstrap over versions {fmt(primary['icc21_ci_lo'])} to {fmt(primary['icc21_ci_hi'])}; "
        f"{int(primary['n_versions_complete'])} complete versions, {int(primary['icc21_boot_ok'])} usable "
        f"resamples).\n"
        f"- ICC(1,1), all ratings: {fmt(primary['icc11_all_ratings'])}.\n"
        f"- Kendall's W across repeats: {fmt(primary['kendall_w'])} "
        f"(permutation p = {fmt(primary['kendall_w_perm_p'], 4)}).\n"
        f"- Spearman between repeats: mean {fmt(primary['spearman_mean'])}, "
        f"min {fmt(primary['spearman_min'])}, max {fmt(primary['spearman_max'])}.\n"
        f"- Pooled within-version SD: {fmt(primary['sd_within_pooled'])} points; SD of version means: "
        f"{fmt(primary['sd_between_version_means'])}; repeatability coefficient (2.77 x SD): "
        f"{fmt(primary['repeatability_coef_2_77_sd'])} points.\n"
        "- Benchmarks usually quoted (Koo and Li 2016): ICC below 0.5 poor, 0.5-0.75 moderate, 0.75-0.9 good, "
        "above 0.9 excellent. Judge the interval, not the point.\n")
    lines.append("### `overall` by version\n")
    lines.append(md_table(overall_table) + "\n")
    lines.append("## Agreement, every category (only `overall` is the pre-registered primary)\n")
    lines.append(md_table(agreement[agree_cols]) + "\n")
    lines.append("## Version means, every category\n")
    lines.append(md_table(grid) + "\n")
    lines.append("## Repeat means vs the original in-loop editor scores (descriptive)\n")
    if comparison.empty:
        lines.append("No original scores for the versions analysed.\n")
    else:
        lines.append(md_table(comparison) + "\n")
        for name, value in extra.items():
            lines.append(f"- {name}: {fmt(value)}\n")
    lines.append(caveat_text())
    (out_dir / "results_summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return {"agreement": agreement, "summary": summary, "status": status, "comparison": comparison,
            "counts": counts, "warnings": warnings}


# ---------------------------------------------------------------------------------------------- self-test
def selftest(key_path: Path, seed: int) -> int:
    """Synthetic end-to-end check in a temp folder that is deleted afterwards."""
    # 1. textbook ICCs: Shrout & Fleiss (1979) Table 2, 6 subjects x 4 judges
    sf = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]], float)
    icc = icc_balanced(sf)
    assert abs(icc["icc1"] - 0.17) < 0.005 and abs(icc["icc2"] - 0.29) < 0.005 and abs(icc["icc3"] - 0.71) < 0.005, icc
    # 2. Kendall's W: perfect concordance = 1, hand-checked tie-free value for a 3x3 case
    perfect = np.array([[1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4]], float)
    assert abs(kendall_w(perfect) - 1.0) < 1e-12
    three = np.array([[1, 1, 2], [2, 3, 1], [3, 2, 3]], float)       # rank sums 4, 6, 8 -> S=8, W=12*8/(9*24)
    assert abs(kendall_w(three) - 12 * 8 / (9 * 24)) < 1e-12
    print("unit checks passed: Shrout-Fleiss ICCs, Kendall W")

    # 3. synthetic results through the whole pipeline
    key = json.loads(key_path.read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed)
    truth = {1: 5.5, 2: 6.0, 4: 6.0, 6: 5.0, 8: 6.5, 10: 7.0, 11: 7.5, 13: 7.5}
    tmp = Path(tempfile.mkdtemp(prefix="s1_selftest_"))
    try:
        results = tmp / "results"
        results.mkdir()
        offsets = {c: o for c, o in zip(CATEGORIES, [0.0, -0.5, 0.0, 0.5, -0.5, 0.0, 0.5, 0.0, 0.0, 0.0])}
        ids = sorted(key)
        for eval_id in ids:
            meta = key[eval_id]
            scores = {c: float(np.clip(round((truth[meta["version"]] + offsets[c] + rng.normal(0, 0.5)) * 2) / 2,
                                       1, 10)) for c in CATEGORIES}
            body = {"scores": scores, "top_fixes": ["a", "b", "c"]}
            (results / f"{eval_id}.json").write_text(json.dumps(body), encoding="utf-8")
        # one fenced block with chatter, one wrapper object, one truncated file, one out-of-range, one missing
        chatty = json.loads((results / f"{ids[0]}.json").read_text(encoding="utf-8"))
        (results / f"{ids[0]}.json").write_text("Here is my read.\n```json\n" + json.dumps(chatty, indent=2)
                                                + "\n```\n", encoding="utf-8")
        wrapped = json.loads((results / f"{ids[1]}.json").read_text(encoding="utf-8"))
        (results / f"{ids[1]}.json").write_text(json.dumps({"result": "```json\n" + json.dumps(wrapped) + "\n```"}),
                                                encoding="utf-8")
        (results / f"{ids[2]}.json").write_text('{"scores": {"hook": 6.0, "pacing": 5.', encoding="utf-8")
        oob = json.loads((results / f"{ids[3]}.json").read_text(encoding="utf-8"))
        oob["scores"]["hook"] = 11
        (results / f"{ids[3]}.json").write_text(json.dumps(oob), encoding="utf-8")
        (results / f"{ids[4]}.json").unlink()
        (results / "stray.json").write_text("{}", encoding="utf-8")
        orig = tmp / "orig.csv"
        pd.DataFrame({"version": [1, 2, 4, 8, 10, 11] * 1, "critic": "editor", "category": "overall",
                      "score": [5.5, 6.5, 6.0, 6.5, 7.5, 7.5]}).to_csv(orig, index=False)
        out = tmp / "out"
        res = analyse(results, key_path, out, n_boot=800, n_perm=800, seed=seed, original_path=orig)
        counts = res["counts"]
        assert counts.get("ok") == len(ids) - 3 and counts.get("missing") == 1 and counts.get("malformed") == 2, counts
        assert counts.get("unknown_file") == 1, counts
        assert not res["status"].loc[res["status"]["eval_id"] == ids[0], "status"].ne("ok").any()
        assert not res["status"].loc[res["status"]["eval_id"] == ids[1], "status"].ne("ok").any()
        agreement = res["agreement"].set_index("category")
        row = agreement.loc[PRIMARY]
        print(f"synthetic overall: ICC(2,1)={row['icc21']:.2f} CI [{row['icc21_ci_lo']:.2f}, "
              f"{row['icc21_ci_hi']:.2f}], W={row['kendall_w']:.2f} (p={row['kendall_w_perm_p']:.3f}), "
              f"complete versions {int(row['n_versions_complete'])}/{int(row['n_versions_total'])}, "
              f"status {counts}")
        assert row["icc21"] > 0.5 and row["icc21_ci_lo"] < row["icc21"] < row["icc21_ci_hi"] + 1e-9, row
        for name in ("results_summary.csv", "results_agreement.csv", "results_status.csv", "results_summary.md"):
            assert (out / name).exists(), name
        assert not res["comparison"].empty
        print((out / "results_summary.md").read_text(encoding="utf-8")[:1200])
        # repair the three bad evaluations and rerun: the design is then complete (8 versions x 3 repeats)
        for eval_id in ids[2:5]:
            meta = key[eval_id]
            scores = {c: float(np.clip(round((truth[meta["version"]] + offsets[c] + rng.normal(0, 0.5)) * 2) / 2,
                                       1, 10)) for c in CATEGORIES}
            (results / f"{eval_id}.json").write_text(json.dumps({"scores": scores, "top_fixes": []}),
                                                     encoding="utf-8")
        (results / "stray.json").unlink()
        full = analyse(results, key_path, tmp / "out_full", n_boot=800, n_perm=800, seed=seed, original_path=orig)
        frow = full["agreement"].set_index("category").loc[PRIMARY]
        assert int(frow["n_versions_complete"]) == 8 and full["counts"] == {"ok": len(ids)}, full["counts"]
        print(f"complete synthetic design: ICC(2,1)={frow['icc21']:.2f} CI [{frow['icc21_ci_lo']:.2f}, "
              f"{frow['icc21_ci_hi']:.2f}], ICC(1,1)={frow['icc11_all_ratings']:.2f}, W={frow['kendall_w']:.2f}")
        print("selftest OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("synthetic data deleted:", not tmp.exists())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Study 1 analysis (editor critic repeatability)")
    parser.add_argument("--results-dir", type=Path, default=STUDY_DIR / "results")
    parser.add_argument("--key", type=Path, default=STUDY_DIR / "key.json")
    parser.add_argument("--out-dir", type=Path, default=STUDY_DIR)
    parser.add_argument("--n-boot", type=int, default=N_BOOT_DEFAULT)
    parser.add_argument("--n-perm", type=int, default=N_PERM_DEFAULT)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--selftest", action="store_true", help="run on synthetic data in a temp folder")
    args = parser.parse_args()
    if not args.key.exists():
        print(f"missing {args.key}; run s1_prepare.py first", file=sys.stderr)
        return 1
    if args.selftest:
        return selftest(args.key, args.seed)
    res = analyse(args.results_dir, args.key, args.out_dir, args.n_boot, args.n_perm, args.seed,
                  prompt_path=STUDY_DIR / "prompt.md", manifest_path=STUDY_DIR / "manifest.json")
    print(f"status {res['counts']}; wrote results_summary.csv, results_agreement.csv, results_status.csv, "
          f"results_summary.md to {args.out_dir}")
    for w in res["warnings"]:
        print("WARNING:", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
