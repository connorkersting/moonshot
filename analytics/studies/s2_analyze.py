"""Study 2 analysis: A/B judge position bias.

Reads studies/s2/results/<call_id>.json (one per judge call) and studies/s2/key.json, and writes
  studies/s2/results_decisions.csv   one row per usable decision, joined to the key
  studies/s2/results_items.csv       one row per item (12): picks, ties, consistency class
  studies/s2/results_stats.csv       every headline number, one per row
  studies/s2/results_status.csv      per call: ok / missing / malformed (with the reason)
  studies/s2/results_summary.md      the same, readable

Run (from C:\\dev\\moonshot-repo\\analytics):
    set PYTHONUTF8=1 && py studies\\s2_analyze.py
    set PYTHONUTF8=1 && py studies\\s2_analyze.py --selftest     (synthetic data in a temp folder, deleted after)

numpy + pandas + the standard library only. The exact binomial test, Clopper-Pearson and Wilson intervals are
implemented here; the randomization test is Monte Carlo.

"Top" and "A" are the same thing in this study (A is always the top row), so a preference for the A label and a
preference for the top row cannot be told apart.
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

STUDY_DIR = Path(__file__).resolve().parent / "s2"
SHEETS_PER_CALL = 6
N_PERM_DEFAULT = 20000
SEED_DEFAULT = 20261010
WINNERS = {"A", "B", "TIE"}


# ---------------------------------------------------------------------------------------------- statistics
def binom_pmf(k: int, n: int, p: float) -> float:
    """P(X = k) for X ~ Binomial(n, p)."""
    return math.comb(n, k) * p ** k * (1 - p) ** (n - k)


def binom_two_sided_p(k: int, n: int, p: float = 0.5) -> float:
    """Exact two-sided p: total probability of outcomes no more likely than the observed one (R's binom.test)."""
    if n == 0:
        return float("nan")
    observed = binom_pmf(k, n, p)
    total = sum(binom_pmf(i, n, p) for i in range(n + 1) if binom_pmf(i, n, p) <= observed * (1 + 1e-7))
    return min(1.0, total)


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k)."""
    return sum(binom_pmf(i, n, p) for i in range(k, n + 1))


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k)."""
    return sum(binom_pmf(i, n, p) for i in range(0, k + 1))


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Clopper-Pearson) two-sided confidence interval for a proportion, by bisection."""
    if n == 0:
        return float("nan"), float("nan")

    def bisect(func, target: float, increasing: bool) -> float:   # type: ignore[no-untyped-def]
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2
            if (func(mid) < target) == increasing:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else bisect(lambda p: binom_sf(k, n, p), alpha / 2, increasing=True)
    upper = 1.0 if k == n else bisect(lambda p: binom_cdf(k, n, p), alpha / 2, increasing=False)
    return lower, upper


def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for a proportion."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def block_randomization_test(blocks: list[tuple[np.ndarray, np.ndarray]], n_perm: int,
                             rng: np.random.Generator) -> dict[str, float]:
    """Randomization test for 'the judge prefers the A (top) position', respecting item blocks.

    Each block is one item: (picked_newer, newer_on_top) over that item's non-tie decisions. A decision picks A
    exactly when picked_newer == newer_on_top. Null: which version a judge picks does not depend on where it is
    shown, so the order labels are exchangeable within an item. We shuffle newer_on_top inside each block, keeping
    the version picks fixed, and recompute the number of A picks. The statistic is centred on its exact null
    mean (an item whose picks are all one version contributes exactly its balanced share, whatever the shuffle).
    """
    observed = float(sum(int(((pn == ot)).sum()) for pn, ot in blocks))
    expected = 0.0
    for pn, ot in blocks:
        q = float(ot.mean()) if len(ot) else 0.0
        expected += float(np.where(pn, q, 1 - q).sum())
    hits = 0
    for _ in range(n_perm):
        total = 0
        for pn, ot in blocks:
            total += int((pn == rng.permutation(ot)).sum())
        if abs(total - expected) >= abs(observed - expected) - 1e-9:
            hits += 1
    return {"observed_A_picks": observed, "null_mean_A_picks": expected, "p_two_sided": (hits + 1) / (n_perm + 1)}


# ---------------------------------------------------------------------------------------------- parsing
def extract_json_object(text: str, required_key: str) -> dict | None:
    """Last JSON object containing `required_key` (handles fenced blocks, chatter and string wrappers)."""
    decoder = json.JSONDecoder()
    found: dict | None = None
    for match in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and required_key in obj:
            found = obj
    if found is not None:
        return found
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(whole, dict):
        for value in whole.values():
            if isinstance(value, str) and required_key in value:
                inner = extract_json_object(value, required_key)
                if inner is not None:
                    return inner
    return None


def confidence_rank(text: str) -> int:
    """1 low, 2 medium, 3 high (loose match: 'med-high' counts as 3? no: the first word decides)."""
    lowered = text.strip().lower()
    if lowered.startswith("high"):
        return 3
    if lowered.startswith("low"):
        return 1
    return 2


def parse_call(path: Path) -> tuple[dict[str, dict[str, object]], list[str]]:
    """{sheet name: parsed decision} for a call file, or raise ValueError (the whole call is then excluded)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"unreadable: {exc}") from exc
    obj = extract_json_object(text, "decisions")
    if obj is None:
        raise ValueError("no JSON object with a 'decisions' key")
    entries = obj["decisions"]
    if not isinstance(entries, list):
        raise ValueError("'decisions' is not a list")
    parsed: dict[str, dict[str, object]] = {}
    warnings: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("a decision entry is not an object")
        sheet = re.sub(r"\.jpg$", "", str(entry.get("sheet", "")).strip().lower())
        if not re.fullmatch(rf"sheet_[1-{SHEETS_PER_CALL}]", sheet):
            raise ValueError(f"unknown sheet name {entry.get('sheet')!r}")
        if sheet in parsed:
            raise ValueError(f"{sheet} decided twice")
        winner = str(entry.get("winner", "")).strip().upper()
        if winner not in WINNERS:
            raise ValueError(f"{sheet}: winner {entry.get('winner')!r} is not A, B or TIE")
        a_total, b_total = entry.get("a_total"), entry.get("b_total")
        if isinstance(a_total, (int, float)) and isinstance(b_total, (int, float)):
            implied = "A" if a_total > b_total else "B" if b_total > a_total else "TIE"
            if implied != winner:
                warnings.append(f"{sheet}: winner {winner} disagrees with totals {a_total} vs {b_total}")
        parsed[sheet] = {"winner": winner, "confidence": str(entry.get("confidence", "")),
                         "a_total": a_total, "b_total": b_total, "reason": str(entry.get("reason", ""))}
    if len(parsed) != SHEETS_PER_CALL:
        raise ValueError(f"expected {SHEETS_PER_CALL} sheets, found {sorted(parsed)}")
    return parsed, warnings


def load_decisions(results_dir: Path, key: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(usable decisions joined to the key, one status row per call)."""
    rows: list[dict[str, object]] = []
    status: list[dict[str, object]] = []
    for call_id, sheets in sorted(key["calls"].items()):
        path = results_dir / f"{call_id}.json"
        if not path.exists():
            status.append({"call_id": call_id, "status": "missing", "detail": "no results file"})
            continue
        try:
            parsed, warnings = parse_call(path)
        except ValueError as exc:
            status.append({"call_id": call_id, "status": "malformed", "detail": str(exc)})
            continue
        status.append({"call_id": call_id, "status": "ok", "detail": "; ".join(warnings)})
        for sheet, decision_id in sheets.items():
            meta = key["decisions"][decision_id]
            got = parsed[sheet]
            winner = str(got["winner"])
            tie = winner == "TIE"
            picked_top: bool | None = None if tie else winner == "A"
            picked_newer: bool | None = None if tie else (picked_top == bool(meta["newer_on_top"]))
            rows.append({
                "decision_id": decision_id, "item_id": meta["item_id"], "comparison": meta["comparison"],
                "section": meta["section"], "repeat": meta["repeat"], "call_id": call_id, "sheet": sheet,
                "newer_on_top": bool(meta["newer_on_top"]), "top_version": meta["top_version"],
                "winner": winner, "tie": tie, "picked_top": picked_top, "picked_newer": picked_newer,
                "picked_version": (None if tie else meta["top_version"] if picked_top else meta["bottom_version"]),
                "confidence": got["confidence"], "confidence_rank": confidence_rank(str(got["confidence"])),
                "a_total": got["a_total"], "b_total": got["b_total"], "reason": got["reason"],
            })
    if results_dir.exists():
        for path in sorted(results_dir.glob("*.json")):
            if path.stem not in key["calls"]:
                status.append({"call_id": path.stem, "status": "unknown_file", "detail": "not a call_id in key.json"})
    return pd.DataFrame(rows), pd.DataFrame(status)


# ---------------------------------------------------------------------------------------------- analysis
def flip_consistency(decisions: pd.DataFrame) -> pd.DataFrame:
    """One row per (item, repeat) pair of decisions made on the two orders of the same item."""
    rows: list[dict[str, object]] = []
    for (item_id, repeat), group in decisions.groupby(["item_id", "repeat"]):
        top_newer = group[group["newer_on_top"]]
        top_older = group[~group["newer_on_top"]]
        if len(top_newer) != 1 or len(top_older) != 1:
            continue                       # one of the two orders is missing (a call was excluded)
        a, b = top_newer.iloc[0], top_older.iloc[0]
        if a["tie"] or b["tie"]:
            kind = "tie_involved"
        elif a["picked_version"] == b["picked_version"]:
            kind = "same_version"          # content-driven: the same cut won in both orders
        else:
            kind = "same_position_A" if a["winner"] == "A" else "same_position_B"
        rows.append({"item_id": item_id, "repeat": repeat, "kind": kind})
    return pd.DataFrame(rows, columns=["item_id", "repeat", "kind"])


def retest_agreement(decisions: pd.DataFrame) -> tuple[int, int]:
    """(agreeing, comparable) pairs: the same item shown in the same order in both repeats, same verdict."""
    agree = comparable = 0
    for (_, _), group in decisions.groupby(["item_id", "newer_on_top"]):
        if len(group) == 2:
            comparable += 1
            agree += int(group["winner"].iloc[0] == group["winner"].iloc[1])
    return agree, comparable


def item_table(decisions: pd.DataFrame) -> pd.DataFrame:
    """Per item: how many decisions, ties, which version was picked how often, and a consistency label."""
    rows: list[dict[str, object]] = []
    for item_id, group in decisions.groupby("item_id"):
        decisive = group[~group["tie"]]
        newer_picks = int(decisive["picked_newer"].sum()) if len(decisive) else 0
        a_picks = int(decisive["picked_top"].sum()) if len(decisive) else 0
        n = len(decisive)
        if n == 0:
            label = "all ties"
        elif newer_picks in (0, n):
            label = "same version every time" if n >= 2 else "one decisive pick"
        elif a_picks in (0, n):
            label = "same position every time"
        else:
            label = "mixed"
        rows.append({"item_id": item_id, "comparison": group["comparison"].iloc[0], "section": group["section"].iloc[0],
                     "n_decisions": len(group), "n_ties": int(group["tie"].sum()), "n_decisive": n,
                     "newer_picked": newer_picks, "older_picked": n - newer_picks, "A_picked": a_picks,
                     "B_picked": n - a_picks, "pattern": label})
    return pd.DataFrame(rows)


def compute_stats(decisions: pd.DataFrame, n_perm: int, rng: np.random.Generator) -> list[tuple[str, object, str]]:
    """Headline statistics as (name, value, note)."""
    stats: list[tuple[str, object, str]] = []
    n = len(decisions)
    n_tie = int(decisions["tie"].sum())
    decisive = decisions[~decisions["tie"]]
    nd = len(decisive)
    lo, hi = wilson(n_tie, n)
    stats += [("n_decisions_usable", n, "of 48 planned"),
              ("n_ties", n_tie, ""), ("tie_rate", n_tie / n if n else float("nan"), "ties / usable decisions"),
              ("tie_rate_wilson_lo", lo, "95% Wilson"), ("tie_rate_wilson_hi", hi, "95% Wilson")]
    for flag, name in ((True, "newer_on_top"), (False, "older_on_top")):
        sub = decisions[decisions["newer_on_top"] == flag]
        stats.append((f"tie_rate_{name}", float(sub["tie"].mean()) if len(sub) else float("nan"), f"n={len(sub)}"))
    stats.append(("n_decisive", nd, "non-tie decisions"))
    if nd:
        k_a = int(decisive["picked_top"].sum())
        cp_lo, cp_hi = clopper_pearson(k_a, nd)
        stats += [("A_picks", k_a, "decisions where the top/A row won"),
                  ("P_pick_A_given_decisive", k_a / nd, "0.5 = no position preference"),
                  ("P_pick_A_clopper_pearson_lo", cp_lo, "95% exact"), ("P_pick_A_clopper_pearson_hi", cp_hi, "95% exact"),
                  ("binomial_exact_p_two_sided", binom_two_sided_p(k_a, nd, 0.5),
                   "H0: P(A)=0.5; treats the decisive decisions as independent, which they are not")]
        blocks = [(g["picked_newer"].to_numpy(dtype=bool), g["newer_on_top"].to_numpy(dtype=bool))
                  for _, g in decisive.groupby("item_id")]
        perm = block_randomization_test(blocks, n_perm, rng)
        informative = sum(1 for pn, _ in blocks if 0 < pn.sum() < len(pn))
        stats += [("randomization_observed_A_picks", perm["observed_A_picks"], "same as A_picks"),
                  ("randomization_null_mean_A_picks", perm["null_mean_A_picks"], "exact mean under the item-block null"),
                  ("randomization_p_two_sided", perm["p_two_sided"], f"{n_perm} shuffles of order labels within items"),
                  ("items_with_a_version_flip", informative, "items where not every decisive pick chose the same cut")]
        k_new = int(decisive["picked_newer"].sum())
        nlo, nhi = clopper_pearson(k_new, nd)
        stats += [("P_pick_newer_given_decisive", k_new / nd, "descriptive; orders are balanced so position cancels"),
                  ("P_pick_newer_clopper_pearson_lo", nlo, "95% exact"), ("P_pick_newer_clopper_pearson_hi", nhi, "95% exact")]
    flips = flip_consistency(decisions)
    stats.append(("n_item_repeat_pairs", len(flips), "both orders of an item present in a repeat (24 planned)"))
    if len(flips):
        counts = flips["kind"].value_counts()
        for kind in ("same_version", "same_position_A", "same_position_B", "tie_involved"):
            stats.append((f"flip_pairs_{kind}", int(counts.get(kind, 0)), ""))
        both = int(counts.get("same_version", 0) + counts.get("same_position_A", 0) + counts.get("same_position_B", 0))
        if both:
            same = int(counts.get("same_version", 0))
            flo, fhi = wilson(same, both)
            stats += [("flip_consistency_same_version_rate", same / both,
                       "among pairs with no tie: same cut picked in both orders; 1 = content-driven, 0 = position-driven"),
                      ("flip_consistency_wilson_lo", flo, "95% Wilson"), ("flip_consistency_wilson_hi", fhi, "95% Wilson")]
    agree, comparable = retest_agreement(decisions)
    stats += [("retest_pairs_same_item_same_order", comparable, "item+order shown in both repeats"),
              ("retest_agreement_rate", agree / comparable if comparable else float("nan"),
               "same verdict (A/B/TIE) in both repeats")]
    return stats


def fmt(value: object, digits: int = 3) -> str:
    """Compact number formatting."""
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{digits}f}"
    return str(value)


def md_table(frame: pd.DataFrame) -> str:
    """Markdown pipe table without needing `tabulate`."""
    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def analyse(results_dir: Path, key_path: Path, out_dir: Path, n_perm: int = N_PERM_DEFAULT,
            seed: int = SEED_DEFAULT, prompt_path: Path | None = None,
            manifest_path: Path | None = None) -> dict[str, object]:
    """Run the full Study 2 analysis and write the output files to out_dir."""
    key = json.loads(key_path.read_text(encoding="utf-8"))
    decisions, status = load_decisions(results_dir, key)
    out_dir.mkdir(parents=True, exist_ok=True)
    status.to_csv(out_dir / "results_status.csv", index=False, encoding="utf-8")
    if decisions.empty:
        raise SystemExit("no usable decisions; nothing to analyse")
    rng = np.random.default_rng(seed)
    stats = compute_stats(decisions, n_perm, rng)
    stat_frame = pd.DataFrame(stats, columns=["statistic", "value", "note"])
    stat_frame.to_csv(out_dir / "results_stats.csv", index=False, encoding="utf-8")
    items = item_table(decisions)
    items.to_csv(out_dir / "results_items.csv", index=False, encoding="utf-8")
    decisions.to_csv(out_dir / "results_decisions.csv", index=False, encoding="utf-8")
    s = {name: value for name, value, _ in stats}
    counts = status["status"].value_counts().to_dict()

    lines = ["# Study 2: A/B judge position bias, results\n"]
    if prompt_path is not None and manifest_path is not None and prompt_path.exists() and manifest_path.exists():
        recorded = json.loads(manifest_path.read_text(encoding="utf-8")).get("prompt_sha256")
        if recorded != hashlib.sha256(prompt_path.read_bytes()).hexdigest():
            lines.append("**WARNING:** prompt.md differs from the hash recorded at prepare time: "
                         "the prompt was not frozen.\n")
            print("WARNING: prompt.md changed since prepare")
    lines.append(f"Calls expected {len(key['calls'])}; usable {counts.get('ok', 0)}; missing {counts.get('missing', 0)}; "
                 f"malformed {counts.get('malformed', 0)}. Usable decisions {s['n_decisions_usable']} of "
                 f"{len(key['decisions'])}.\n")
    problems = status[status["status"] != "ok"]
    if not problems.empty:
        lines.append(md_table(problems) + "\n")
    lines.append("## Primary: does the judge favour the A (top) position?\n")
    lines.append(f"- Ties: {s['n_ties']} of {s['n_decisions_usable']} = {fmt(s['tie_rate'])} "
                 f"(95% Wilson {fmt(s['tie_rate_wilson_lo'])} to {fmt(s['tie_rate_wilson_hi'])}). "
                 f"Tie rate with the newer cut on top {fmt(s['tie_rate_newer_on_top'])}, with the older on top "
                 f"{fmt(s['tie_rate_older_on_top'])}.\n")
    if "A_picks" in s:
        lines.append(
            f"- Among {s['n_decisive']} decisive decisions, A won {s['A_picks']}: P(A) = "
            f"**{fmt(s['P_pick_A_given_decisive'])}** (95% exact {fmt(s['P_pick_A_clopper_pearson_lo'])} to "
            f"{fmt(s['P_pick_A_clopper_pearson_hi'])}).\n"
            f"- Exact binomial test against 0.5, two-sided: p = {fmt(s['binomial_exact_p_two_sided'], 4)} "
            f"(assumes independent decisions; they are not).\n"
            f"- Item-block randomization test: p = {fmt(s['randomization_p_two_sided'], 4)} "
            f"(observed {fmt(s['randomization_observed_A_picks'])} A picks vs null mean "
            f"{fmt(s['randomization_null_mean_A_picks'])}; {s['items_with_a_version_flip']} items had a version "
            f"flip and so carry the information).\n"
            f"- Descriptive: the newer cut won {fmt(s['P_pick_newer_given_decisive'])} of decisive decisions "
            f"(95% exact {fmt(s['P_pick_newer_clopper_pearson_lo'])} to {fmt(s['P_pick_newer_clopper_pearson_hi'])}). "
            f"Orders are balanced, so this is not contaminated by position bias.\n")
    lines.append("## Order-flip consistency\n")
    lines.append(f"{s['n_item_repeat_pairs']} item x repeat pairs had both orders usable: "
                 f"{s.get('flip_pairs_same_version', 0)} picked the same cut in both orders, "
                 f"{s.get('flip_pairs_same_position_A', 0)} picked A both times, "
                 f"{s.get('flip_pairs_same_position_B', 0)} picked B both times, "
                 f"{s.get('flip_pairs_tie_involved', 0)} involved a tie.\n")
    if "flip_consistency_same_version_rate" in s:
        lines.append(f"Same-cut rate among pairs without a tie: **{fmt(s['flip_consistency_same_version_rate'])}** "
                     f"(95% Wilson {fmt(s['flip_consistency_wilson_lo'])} to {fmt(s['flip_consistency_wilson_hi'])}). "
                     "1 means the verdict follows the content; 0 means it follows the position; a judge guessing "
                     "at random would sit near 0.5.\n")
    lines.append(f"Test-retest: the same item in the same order got the same verdict in both repeats in "
                 f"{fmt(s['retest_agreement_rate'])} of {s['retest_pairs_same_item_same_order']} pairs.\n")
    lines.append("## Items\n")
    lines.append(md_table(items) + "\n")
    lines.append(
        "## Reading this honestly\n\n"
        "- n = 48 planned decisions on 12 items. The decisions are not independent: each item appears 4 times "
        "(2 orders x 2 repeats), and the two repeats are the same model re-asked. The exact binomial p-value is "
        "therefore optimistic; the item-block randomization test is the fairer one, and with 12 items even it has "
        "little power.\n"
        "- Items where the judge is firmly content-driven carry no information about position bias, by "
        "construction of the balanced design. Only items where the verdict flips across orders do.\n"
        "- A is always the top row: label bias and top-row bias cannot be separated.\n"
        "- The judge cannot hear audio and sees eight frames per cut, so 'correct' is not defined here. This "
        "measures whether the verdict depends on presentation order, not whether it is right.\n"
        "- Items were chosen because the cuts visibly differ (and not at random), so results describe sheets of "
        "that kind, not every comparison in the run.\n")
    (out_dir / "results_summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return {"stats": s, "items": items, "decisions": decisions, "status": status, "counts": counts}


# ---------------------------------------------------------------------------------------------- self-test
def simulate_call_files(key: dict, results_dir: Path, rng: np.random.Generator, bias: float, tie_p: float,
                        mode: str = "latent") -> None:
    """Write fake judge JSONs. mode 'latent': pick by item preference plus a position bias in logit units;
    'always_A': always A; 'content': always the item's preferred cut (no position effect at all)."""
    item_ids = sorted(key["items"])
    pref = {item: (2.5 if i % 2 == 0 else -2.5) if i < 8 else (0.4 if i % 2 == 0 else -0.4)
            for i, item in enumerate(item_ids)}                      # logit of preferring the newer cut
    for call_id, sheets in key["calls"].items():
        entries = []
        for sheet, decision_id in sheets.items():
            meta = key["decisions"][decision_id]
            if mode == "always_A":
                winner = "A"
            else:
                if rng.random() < tie_p:
                    winner = "TIE"
                else:
                    sign = 1.0 if meta["newer_on_top"] else -1.0
                    if mode == "content":
                        p_a = 1.0 if pref[meta["item_id"]] * sign > 0 else 0.0
                    else:
                        p_a = 1 / (1 + math.exp(-(pref[meta["item_id"]] * sign + bias)))
                    winner = "A" if rng.random() < p_a else "B"
            a, b = (3, 2) if winner == "A" else (2, 3) if winner == "B" else (2, 2)
            entries.append({"sheet": sheet, "a_total": a, "b_total": b, "winner": winner,
                            "confidence": str(rng.choice(["high", "med", "low"])), "reason": "synthetic"})
        (results_dir / f"{call_id}.json").write_text(json.dumps({"decisions": entries}), encoding="utf-8")


def selftest(key_path: Path, seed: int) -> int:
    """Synthetic end-to-end check in a temp folder that is deleted afterwards."""
    # exact-test unit checks against known values
    assert abs(binom_two_sided_p(7, 10) - 0.34375) < 1e-9
    assert abs(binom_two_sided_p(0, 10) - 2 * 0.5 ** 10) < 1e-12
    cp = clopper_pearson(7, 10)
    assert abs(cp[0] - 0.3475) < 5e-4 and abs(cp[1] - 0.9333) < 5e-4, cp
    w = wilson(7, 10)
    assert abs(w[0] - 0.397) < 2e-3 and abs(w[1] - 0.892) < 2e-3, w
    print("unit checks passed: exact binomial, Clopper-Pearson, Wilson")

    key = json.loads(key_path.read_text(encoding="utf-8"))
    rng = np.random.default_rng(seed)
    tmp = Path(tempfile.mkdtemp(prefix="s2_selftest_"))
    try:
        # scenario 1: purely content-driven judge -> P(A)=0.5 exactly, randomization p = 1, flip consistency 1
        results = tmp / "r_content"
        results.mkdir()
        simulate_call_files(key, results, rng, 0.0, 0.0, mode="content")
        res = analyse(results, key_path, tmp / "o_content", n_perm=500, seed=seed)["stats"]
        assert res["n_decisions_usable"] == 48 and abs(res["P_pick_A_given_decisive"] - 0.5) < 1e-9, res
        assert res["randomization_p_two_sided"] > 0.99 and res["flip_consistency_same_version_rate"] == 1.0, res
        print(f"content-only judge: P(A)={res['P_pick_A_given_decisive']:.2f}, randomization p="
              f"{res['randomization_p_two_sided']:.3f}, same-cut rate {res['flip_consistency_same_version_rate']:.2f}")

        # scenario 2: judge that always says A -> P(A)=1, tiny p, same-cut rate 0
        results = tmp / "r_always"
        results.mkdir()
        simulate_call_files(key, results, rng, 0.0, 0.0, mode="always_A")
        res = analyse(results, key_path, tmp / "o_always", n_perm=500, seed=seed)["stats"]
        assert res["P_pick_A_given_decisive"] == 1.0 and res["binomial_exact_p_two_sided"] < 1e-12, res
        assert res["randomization_p_two_sided"] < 0.01 and res["flip_consistency_same_version_rate"] == 0.0, res
        print(f"always-A judge: P(A)={res['P_pick_A_given_decisive']:.2f}, binomial p="
              f"{res['binomial_exact_p_two_sided']:.1e}, randomization p={res['randomization_p_two_sided']:.4f}")

        # scenario 3: noisy judge with an A bias of +1.2 logits, 15% ties; plus damaged files
        results = tmp / "r_biased"
        results.mkdir()
        simulate_call_files(key, results, rng, 1.2, 0.15)
        call_ids = sorted(key["calls"])
        (results / f"{call_ids[0]}.json").unlink()                                              # missing call
        (results / f"{call_ids[1]}.json").write_text('{"decisions": [{"sheet": "sheet_1", "win', encoding="utf-8")
        good = json.loads((results / f"{call_ids[2]}.json").read_text(encoding="utf-8"))
        (results / f"{call_ids[2]}.json").write_text("My verdicts:\n```json\n" + json.dumps(good, indent=1)
                                                     + "\n```", encoding="utf-8")               # fenced, still valid
        bad = json.loads((results / f"{call_ids[3]}.json").read_text(encoding="utf-8"))
        bad["decisions"][0]["winner"] = "C"
        (results / f"{call_ids[3]}.json").write_text(json.dumps(bad), encoding="utf-8")         # invalid winner
        short = json.loads((results / f"{call_ids[4]}.json").read_text(encoding="utf-8"))
        short["decisions"] = short["decisions"][:5]
        (results / f"{call_ids[4]}.json").write_text(json.dumps(short), encoding="utf-8")       # 5 of 6 sheets
        out = analyse(results, key_path, tmp / "o_biased", n_perm=2000, seed=seed)
        counts = out["counts"]
        assert counts == {"ok": 4, "malformed": 3, "missing": 1}, counts
        res = out["stats"]
        assert res["n_decisions_usable"] == 24, res["n_decisions_usable"]
        print(f"biased judge, damaged files {counts}: usable {res['n_decisions_usable']}, tie rate "
              f"{res['tie_rate']:.2f}, P(A)={res['P_pick_A_given_decisive']:.2f}, binomial p="
              f"{res['binomial_exact_p_two_sided']:.3f}, randomization p={res['randomization_p_two_sided']:.3f}, "
              f"same-cut rate {res.get('flip_consistency_same_version_rate', float('nan')):.2f}, "
              f"pairs {res['n_item_repeat_pairs']}")
        for name in ("results_decisions.csv", "results_items.csv", "results_stats.csv", "results_status.csv",
                     "results_summary.md"):
            assert (tmp / "o_biased" / name).exists(), name
        print("selftest OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("synthetic data deleted:", not tmp.exists())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Study 2 analysis (A/B judge position bias)")
    parser.add_argument("--results-dir", type=Path, default=STUDY_DIR / "results")
    parser.add_argument("--key", type=Path, default=STUDY_DIR / "key.json")
    parser.add_argument("--out-dir", type=Path, default=STUDY_DIR)
    parser.add_argument("--n-perm", type=int, default=N_PERM_DEFAULT)
    parser.add_argument("--seed", type=int, default=SEED_DEFAULT)
    parser.add_argument("--selftest", action="store_true", help="run on synthetic data in a temp folder")
    args = parser.parse_args()
    if not args.key.exists():
        print(f"missing {args.key}; run s2_prepare.py first", file=sys.stderr)
        return 1
    if args.selftest:
        return selftest(args.key, args.seed)
    out = analyse(args.results_dir, args.key, args.out_dir, args.n_perm, args.seed,
                  prompt_path=STUDY_DIR / "prompt.md", manifest_path=STUDY_DIR / "manifest.json")
    print(f"status {out['counts']}; wrote results_*.csv and results_summary.md to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
