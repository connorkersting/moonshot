"""Build the static, offline MOONSHOT analytics dashboard.

Reads the dbt + DuckDB warehouse read-only and writes two files into
``dashboard/site/``: ``index.html`` (a single page with anchored sections) and one shared
``plotly.min.js``. Nothing is fetched at view time: no CDN, no web fonts.

Run from the analytics folder:

    cd analytics
    export DO_NOT_TRACK=1 PYTHONUTF8=1
    uv run python dashboard/build_dashboard.py

The build is idempotent apart from the build timestamp in the footer.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs
from plotly.subplots import make_subplots

# ----------------------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
ANALYTICS = HERE.parent
WAREHOUSE = ANALYTICS / "warehouse"
DB_PATH = WAREHOUSE / "moonshot.duckdb"
RUN_RESULTS = WAREHOUSE / "target" / "run_results.json"
MANIFEST = WAREHOUSE / "target" / "manifest.json"
RAW_DIR = ANALYTICS / "data" / "raw"
RECONCILIATION = RAW_DIR / "_reconciliation.txt"
SEED_CSV = WAREHOUSE / "seeds" / "version_outcomes.csv"
SITE_DIR = HERE / "site"

# ----------------------------------------------------------------------------------------
# Design tokens (dark, neutral surface; one amber accent; colourblind-safe categorical set)
# ----------------------------------------------------------------------------------------

BG = "#0f1216"
SURFACE = "#171b21"
SURFACE_2 = "#1e232b"
BORDER = "#2a313b"
TEXT = "#e6e9ee"
MUTED = "#a2abb8"
GRID = "rgba(255,255,255,0.09)"
AXIS = "rgba(255,255,255,0.28)"

ACCENT = "#FFB040"  # amber: the headline series and the things to look at
BLUE = "#5BB5F0"
GREEN = "#3FC1A0"
PINK = "#D98BBF"
LAVENDER = "#B7A0F0"
ORANGE = "#E8743B"
GREY = "#98A2B0"
SLATE = "#7F93AA"

FONT_FAMILY = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"

PLOT_CONFIG: dict[str, Any] = {
    "displayModeBar": False,
    "responsive": True,
    "displaylogo": False,
    "scrollZoom": False,
}

CATEGORY_LABELS = {
    "hook": "Hook",
    "pacing": "Pacing",
    "variety": "Variety",
    "motion": "Motion",
    "type": "Type",
    "color": "Color",
    "sound": "Sound",
    "captions": "Captions",
    "story": "Story",
    "overall": "Overall",
}


# ----------------------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------------------


def query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    """Run a read-only query and return a DataFrame."""
    return con.execute(sql).df()


def fmt_tokens(n: float) -> str:
    """Human-readable token count: 396.6M, 74k, 812."""
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k"
    return f"{n:,.0f}"


def fmt_int(n: float) -> str:
    return f"{n:,.0f}"


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def lerp_hex(c0: str, c1: str, t: float) -> str:
    """Linear interpolation between two hex colours, t in [0, 1]."""
    t = min(1.0, max(0.0, t))
    a, b = hex_to_rgb(c0), hex_to_rgb(c1)
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * t):02x}" for i in range(3))


def luminance(color: str) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(v) for v in hex_to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def text_on(color: str) -> str:
    """Pick white or near-black text, whichever has the higher contrast on `color`."""
    lum = luminance(color)
    contrast_white = 1.05 / (lum + 0.05)
    contrast_dark = (lum + 0.05) / (luminance(BG) + 0.05)
    return "#ffffff" if contrast_white >= contrast_dark else BG


def style_figure(fig: go.Figure, height: int, *, margin: dict[str, int] | None = None) -> go.Figure:
    """Apply the shared look: transparent background, readable fonts, quiet grid."""
    fig.update_layout(
        height=height,
        autosize=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT_FAMILY, "size": 13, "color": TEXT},
        margin=margin or {"l": 64, "r": 24, "t": 36, "b": 56},
        hoverlabel={
            "bgcolor": SURFACE_2,
            "bordercolor": BORDER,
            "font": {"family": FONT_FAMILY, "size": 13, "color": TEXT},
        },
        legend={
            "orientation": "h",
            "x": 0,
            "y": 1.0,
            "yanchor": "bottom",
            "font": {"size": 12},
            "bgcolor": "rgba(0,0,0,0)",
        },
    )
    fig.update_xaxes(
        gridcolor=GRID,
        zeroline=False,
        linecolor=AXIS,
        tickfont={"size": 12, "color": TEXT},
        title_font={"size": 13, "color": MUTED},
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor=GRID,
        zeroline=False,
        linecolor=AXIS,
        tickfont={"size": 12, "color": TEXT},
        title_font={"size": 13, "color": MUTED},
        automargin=True,
    )
    return fig


def figure_html(fig: go.Figure, div_id: str) -> str:
    """Plotly figure as an HTML fragment. The plotly.js bundle is loaded once in <head>."""
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        div_id=div_id,
        config=PLOT_CONFIG,
        default_width="100%",
        default_height=f"{fig.layout.height}px",
    )


def html_table(df: pd.DataFrame, *, numeric_cols: set[str] | None = None) -> str:
    """Small accessible table; numeric columns right-aligned."""
    numeric_cols = numeric_cols or set()
    head = "".join(
        f'<th scope="col"{" class=num" if c in numeric_cols else ""}>{esc(c)}</th>' for c in df.columns
    )
    rows = []
    for _, row in df.iterrows():
        cells = "".join(
            f'<td{" class=num" if c in numeric_cols else ""}>{esc(row[c])}</td>' for c in df.columns
        )
        rows.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>'


# ----------------------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------------------


def load_data(con: duckdb.DuckDBPyConnection) -> dict[str, pd.DataFrame]:
    """Pull every table the dashboard needs, once."""
    data = {
        "scorecard": query(con, "SELECT * FROM marts.mart_version_scorecard ORDER BY version_number"),
        "tokens": query(con, "SELECT * FROM marts.mart_token_usage_by_role_session"),
        "timeline": query(con, "SELECT * FROM marts.mart_run_timeline ORDER BY bucket_start_utc"),
        "session_parts": query(con, "SELECT * FROM core.dim_session_part ORDER BY session_part"),
        "critic": query(
            con,
            """
            SELECT
                c.version_id,
                v.version_number,
                c.score_category,
                k.category_order,
                c.score,
            FROM core.fct_critic_scores AS c
            INNER JOIN core.dim_version AS v
                ON c.version_id = v.version_id
            INNER JOIN core.dim_score_category AS k
                ON c.score_category = k.score_category
            WHERE c.critic_id = 'fable_editor'
            ORDER BY v.version_number, k.category_order
            """,
        ),
        "ab": query(
            con,
            """
            SELECT
                a.*,
                v.version_number AS newer_version_number,
            FROM core.fct_ab_votes AS a
            INNER JOIN core.dim_version AS v
                ON a.newer_version_id = v.version_id
            ORDER BY v.version_number, a.section_no
            """,
        ),
        "dialogue": query(
            con,
            """
            SELECT
                d.*,
                v.version_number,
            FROM core.fct_dialogue_lines AS d
            INNER JOIN core.dim_version AS v
                ON d.version_id = v.version_id
            ORDER BY v.version_number, d.line_no
            """,
        ),
        "sections": query(
            con,
            """
            SELECT
                a.*,
                v.version_number,
            FROM core.fct_version_audio AS a
            INNER JOIN core.dim_version AS v
                ON a.version_id = v.version_id
            ORDER BY v.version_number, a.section_no
            """,
        ),
        "llm_by_model": query(
            con,
            """
            SELECT
                model_id,
                COUNT(*) AS requests,
                COUNT(*) FILTER (WHERE is_subagent) AS subagent_requests,
                COUNT(*) FILTER (WHERE NOT is_usage_final) AS requests_without_final_usage,
                SUM(input_tokens) AS input_tokens,
                SUM(cache_creation_tokens) AS cache_creation_tokens,
                SUM(cache_read_tokens) AS cache_read_tokens,
                SUM(output_tokens) AS output_tokens,
            FROM core.fct_llm_requests
            GROUP BY model_id
            ORDER BY requests DESC
            """,
        ),
        "llm_summary": query(
            con,
            """
            SELECT
                COUNT(*) AS requests,
                COUNT(*) FILTER (WHERE NOT is_usage_final) AS no_final_usage,
                COUNT(*) FILTER (WHERE is_subagent) AS subagent_requests,
                MAX(requested_at_local) AS last_request_local,
                MIN(requested_at_local) AS first_request_local,
            FROM core.fct_llm_requests
            """,
        ),
        "codex": query(
            con,
            """
            SELECT
                COUNT(*) AS requests,
                COUNT(DISTINCT codex_session_id) AS sessions,
                SUM(input_tokens) AS input_tokens,
                SUM(cached_input_tokens) AS cached_input_tokens,
                SUM(output_tokens) AS output_tokens,
                SUM(reasoning_output_tokens) AS reasoning_output_tokens,
                SUM(total_tokens) AS total_tokens,
                ANY_VALUE(model_id) AS model_id,
            FROM core.fct_codex_requests
            """,
        ),
        "agent_runs": query(con, "SELECT COUNT(*) AS runs FROM core.fct_agent_runs"),
        "plateau": query(
            con,
            """
            SELECT
                plateau_point_id,
                version_id,
                version_number,
                critic_id,
                score_category,
                score,
                outcome,
                is_promoted,
                has_director_input,
                loop_hours_at_export,
            FROM marts.mart_critic_plateau
            ORDER BY version_number, critic_id, score_category
            """,
        ),
        "plateau_versions": query(
            con,
            """
            SELECT
                version_id,
                version_number,
                outcome,
                is_promoted,
                decision_basis,
                decision_reason,
                has_director_input,
                loop_hours_at_export,
            FROM core.dim_version
            ORDER BY version_number
            """,
        ),
        "reliability": query(con, "SELECT * FROM marts.mart_critic_reliability ORDER BY critic_id"),
        "compactions": query(
            con,
            """
            SELECT
                event_at_local,
                context_tokens_before,
                context_tokens_after,
            FROM core.fct_session_events
            WHERE event_type = 'compaction'
            ORDER BY event_at_local
            """,
        ),
    }
    return data


# ----------------------------------------------------------------------------------------
# Freshness / staleness checks (read-only; report, never edit)
# ----------------------------------------------------------------------------------------


def freshness_notes(data: dict[str, pd.DataFrame]) -> tuple[list[str], list[str]]:
    """Return (ok_notes, stale_warnings) comparing warehouse, raw CSVs and the outcomes seed."""
    ok: list[str] = []
    warn: list[str] = []
    db_mtime = DB_PATH.stat().st_mtime
    raw_files = [p for p in RAW_DIR.glob("*.csv")]
    newest_raw = max((p.stat().st_mtime for p in raw_files), default=0.0)
    if newest_raw > db_mtime:
        warn.append("A raw CSV is newer than moonshot.duckdb: the warehouse needs a dbt build.")
    else:
        ok.append("Warehouse is newer than every raw CSV.")
    if SEED_CSV.exists() and SEED_CSV.stat().st_mtime > db_mtime:
        warn.append("The version_outcomes seed is newer than moonshot.duckdb: the marts need a rebuild.")
    sc = data["scorecard"]
    exported_undecided = sc[sc["exported_at_local"].notna() & (sc["outcome"] == "in_progress")]["version_id"].tolist()
    if exported_undecided:
        warn.append(
            "Exported versions with no keep/revert decision in the version_outcomes seed: "
            + ", ".join(exported_undecided)
        )
    else:
        n_decided = int(sc["exported_at_local"].notna().sum())
        ok.append(f"version_outcomes seed covers all {n_decided} exported versions.")
    in_progress = sc[sc["outcome"] == "in_progress"]["version_id"].tolist()
    if in_progress:
        ok.append(f"{', '.join(in_progress)} is in progress and not exported, so it is left out of the charts.")
    return ok, warn


# ----------------------------------------------------------------------------------------
# dbt test results and ingest reconciliation
# ----------------------------------------------------------------------------------------

LAYER_ORDER = ["Sources", "Seeds", "Staging", "Intermediate", "Dimensions", "Facts", "Marts", "Singular"]


def layer_of(file_key_name: str | None) -> str:
    """Map a dbt test node to the layer it guards, using the manifest's file_key_name."""
    if not file_key_name:
        return "Singular"
    kind, _, name = file_key_name.partition(".")
    if kind == "sources":
        return "Sources"
    if kind == "seeds":
        return "Seeds"
    for prefix, label in (
        ("stg_", "Staging"),
        ("int_", "Intermediate"),
        ("dim_", "Dimensions"),
        ("fct_", "Facts"),
        ("mart_", "Marts"),
    ):
        if name.startswith(prefix):
            return label
    return "Other"


def load_dbt_results() -> dict[str, Any] | None:
    """Parse run_results.json + manifest.json. Returns None when they are missing."""
    if not RUN_RESULTS.exists() or not MANIFEST.exists():
        return None
    rr = json.loads(RUN_RESULTS.read_text(encoding="utf-8"))
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    other: dict[str, dict[str, int]] = {"model": {}, "seed": {}, "snapshot": {}}
    for res in rr["results"]:
        uid = res["unique_id"]
        kind = uid.split(".")[0]
        if kind == "test":
            node = man["nodes"].get(uid, {})
            meta = node.get("test_metadata") or {}
            rows.append(
                {
                    "status": res["status"],
                    "type": meta.get("name", "singular"),
                    "layer": layer_of(node.get("file_key_name")),
                }
            )
        elif kind in other:
            other[kind][res["status"]] = other[kind].get(res["status"], 0) + 1
    tests = pd.DataFrame(rows)
    return {
        "tests": tests,
        "other": other,
        "generated_at": rr["metadata"]["generated_at"],
        "dbt_version": rr["metadata"]["dbt_version"],
        "elapsed": rr.get("elapsed_time"),
        "command": rr.get("args", {}).get("which", "build"),
    }


def parse_reconciliation() -> dict[str, Any] | None:
    """Parse the ingest's reconciliation report. Returns None when the file is missing."""
    if not RECONCILIATION.exists():
        return None
    text = RECONCILIATION.read_text(encoding="utf-8")
    first = text.splitlines()[0] if text else ""
    run_at = re.search(r"run (\S+)", first)
    passes = len(re.findall(r"^\[PASS\]", text, flags=re.M))
    fails = len(re.findall(r"^\[FAIL\]", text, flags=re.M))
    row_counts = {m.group(1): int(m.group(2)) for m in re.finditer(r"^\s+(\w+)\.csv\s+(\d+)\s*$", text, flags=re.M)}
    naive: dict[str, int] = {}
    deduped: dict[str, int] = {}
    for m in re.finditer(
        r"^\s+(input_tokens|output_tokens|cache_creation_tokens|cache_read_tokens)\s+naive\s+([\d,]+)\s+deduped\s+([\d,]+)",
        text,
        flags=re.M,
    ):
        key = m.group(1)
        naive[key] = naive.get(key, 0) + int(m.group(2).replace(",", ""))
        deduped[key] = deduped.get(key, 0) + int(m.group(3).replace(",", ""))
    cost_out = 0
    table_out = 0
    for m in re.finditer(r"(claude-[\w.-]+): .*?output_tokens cost-state ([\d,]+) / table ([\d,]+)", text):
        if "haiku" in m.group(1):
            continue
        cost_out += int(m.group(2).replace(",", ""))
        table_out += int(m.group(3).replace(",", ""))
    return {
        "run_at": run_at.group(1) if run_at else "unknown",
        "passes": passes,
        "fails": fails,
        "all_passed": "all checks passed" in text,
        "row_counts": row_counts,
        "naive": naive,
        "deduped": deduped,
        "cost_state_output": cost_out,
        "table_output_at_cost_state": table_out,
    }


# ----------------------------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------------------------

OUTCOME_STYLE = {
    "kept": {"color": BLUE, "symbol": "circle", "label": "kept"},
    "final": {"color": ACCENT, "symbol": "star", "label": "FINAL"},
    "reverted": {"color": ORANGE, "symbol": "x", "label": "reverted"},
    "not_best": {"color": ORANGE, "symbol": "diamond-open", "label": "lost"},
}


def version_ticks(versions: pd.DataFrame) -> tuple[list[int], list[str]]:
    return versions["version_number"].tolist(), versions["version_id"].tolist()


def fig_score_trajectory(sc: pd.DataFrame) -> go.Figure:
    """Editor overall score per exported version, with a decision strip underneath."""
    exported = sc[sc["exported_at_local"].notna()].copy()
    scored = exported[exported["has_editor_score"]]
    kept = scored[scored["outcome"].isin(["kept", "final"])]
    not_kept = scored[~scored["outcome"].isin(["kept", "final"])]
    unscored = exported[~exported["has_editor_score"]]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.76, 0.24], vertical_spacing=0.05)
    fig.add_trace(
        go.Scatter(
            x=scored["version_number"],
            y=scored["editor_overall_score"],
            mode="lines",
            line={"color": ACCENT, "width": 2.5},
            connectgaps=True,
            hoverinfo="skip",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=kept["version_number"],
            y=kept["editor_overall_score"],
            mode="markers+text",
            name="Editor overall, version kept",
            marker={"color": ACCENT, "size": 11, "line": {"color": BG, "width": 1.5}},
            text=[f"{v:.1f}" for v in kept["editor_overall_score"]],
            textposition="top center",
            textfont={"size": 12, "color": TEXT},
            customdata=kept[["version_id", "outcome"]],
            hovertemplate="%{customdata[0]} (%{customdata[1]})<br>Editor overall: %{y:.1f} / 10<extra></extra>",
        ),
        row=1,
        col=1,
    )
    if not not_kept.empty:
        fig.add_trace(
            go.Scatter(
                x=not_kept["version_number"],
                y=not_kept["editor_overall_score"],
                mode="markers+text",
                name="Editor overall, version not kept",
                marker={"color": ORANGE, "size": 12, "symbol": "x", "line": {"color": ORANGE, "width": 2.5}},
                text=[f"{v:.1f}" for v in not_kept["editor_overall_score"]],
                textposition="top center",
                textfont={"size": 12, "color": TEXT},
                customdata=not_kept[["version_id", "outcome"]],
                hovertemplate="%{customdata[0]} (%{customdata[1]})<br>Editor overall: %{y:.1f} / 10<extra></extra>",
            ),
            row=1,
            col=1,
        )
    ymin = float(scored["editor_overall_score"].min())
    ymax = float(scored["editor_overall_score"].max())
    y_lo = float(int(ymin) - 1.5)
    if not unscored.empty:
        fig.add_trace(
            go.Scatter(
                x=unscored["version_number"],
                y=[y_lo + 0.4] * len(unscored),
                mode="text",
                text=["no editor<br>pass" for _ in range(len(unscored))],
                textfont={"size": 12, "color": MUTED},
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        for vn in unscored["version_number"]:
            fig.add_shape(
                type="line",
                x0=vn,
                x1=vn,
                y0=y_lo + 1.0,
                y1=ymax + 1.0,
                line={"color": AXIS, "width": 1, "dash": "dot"},
                row=1,
                col=1,
            )

    # Decision strip
    for outcome, style in OUTCOME_STYLE.items():
        sub = exported[exported["outcome"] == outcome]
        if sub.empty:
            continue
        labels = []
        for _, r in sub.iterrows():
            ab_only = (not r["has_editor_score"]) and pd.notna(r["ab_compared_with_version_id"])
            labels.append(f"{style['label']}<br>(A/B only)" if ab_only else style["label"])
        fig.add_trace(
            go.Scatter(
                x=sub["version_number"],
                y=[1.0] * len(sub),
                mode="markers+text",
                name=f"Decision: {style['label']}",
                marker={
                    "color": style["color"],
                    "symbol": style["symbol"],
                    "size": 13,
                    "line": {"color": style["color"], "width": 2},
                },
                text=labels,
                textposition="bottom center",
                textfont={"size": 12, "color": TEXT},
                customdata=sub[["version_id", "decision_basis"]],
                hovertemplate="%{customdata[0]}: " + style["label"] + "<br>Basis: %{customdata[1]}<extra></extra>",
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    ticks, labels_all = version_ticks(exported)
    style_figure(fig, 520, margin={"l": 72, "r": 24, "t": 36, "b": 48})
    fig.update_yaxes(
        range=[y_lo, ymax + 1.0],
        dtick=1,
        title_text="Editor overall score (1 to 10)",
        row=1,
        col=1,
    )
    fig.update_yaxes(
        range=[-0.1, 1.5],
        showticklabels=False,
        showgrid=False,
        title_text="Decision",
        row=2,
        col=1,
    )
    fig.update_xaxes(showgrid=False, tickvals=ticks, ticktext=labels_all, row=1, col=1)
    fig.update_xaxes(
        showgrid=False,
        tickvals=ticks,
        ticktext=labels_all,
        title_text="Trailer version, in export order",
        row=2,
        col=1,
    )
    fig.update_xaxes(range=[min(ticks) - 0.6, max(ticks) + 0.6])
    return fig


def fig_category_multiples(critic: pd.DataFrame) -> go.Figure:
    """Small multiples: one panel per editor category, same y scale."""
    cats = (
        critic[["score_category", "category_order"]].drop_duplicates().sort_values("category_order")["score_category"].tolist()
    )
    titles: list[str] = []
    for cat in cats:
        sub = critic[critic["score_category"] == cat].sort_values("version_number")
        first, last = float(sub["score"].iloc[0]), float(sub["score"].iloc[-1])
        titles.append(f"{CATEGORY_LABELS.get(cat, cat)}: {first:.1f} to {last:.1f}")
    rows, cols = 5, 2
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=titles,
        shared_xaxes=True,
        shared_yaxes=True,
        horizontal_spacing=0.07,
        vertical_spacing=0.07,
    )
    all_versions = sorted(critic["version_number"].unique().tolist())
    for i, cat in enumerate(cats):
        r, c = i // cols + 1, i % cols + 1
        sub = critic[critic["score_category"] == cat].sort_values("version_number")
        is_overall = cat == "overall"
        color = ACCENT if is_overall else BLUE
        fig.add_trace(
            go.Scatter(
                x=sub["version_number"],
                y=sub["score"],
                mode="lines+markers",
                line={"color": color, "width": 2},
                marker={"color": color, "size": 7, "line": {"color": BG, "width": 1}},
                customdata=sub["version_id"],
                hovertemplate="%{customdata}: %{y:.1f} / 10<extra>" + CATEGORY_LABELS.get(cat, cat) + "</extra>",
                showlegend=False,
            ),
            row=r,
            col=c,
        )
    style_figure(fig, 900, margin={"l": 56, "r": 16, "t": 36, "b": 56})
    fig.update_yaxes(range=[3.8, 9.2], tickvals=[4, 6, 8])
    fig.update_yaxes(title_text="Score (1 to 10)", row=3, col=1)
    tick_vals = [v for v in all_versions if v in (1, 4, 7, 10)] or all_versions[:: max(1, len(all_versions) // 4)]
    fig.update_xaxes(tickvals=tick_vals, ticktext=[f"v{v}" for v in tick_vals], showgrid=False)
    fig.update_xaxes(title_text="Trailer version", row=rows, col=1)
    fig.update_xaxes(title_text="Trailer version", row=rows, col=2)
    fig.update_annotations(font={"size": 13, "color": TEXT})
    return fig


def role_model_table(tokens: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the mart to role x model (session parts summed)."""
    t = tokens.copy()
    for col in (
        "input_tokens",
        "cache_creation_tokens",
        "cache_read_tokens",
        "output_tokens_final",
        "total_tokens_known",
        "request_count",
        "requests_usage_final",
    ):
        t[col] = t[col].astype(float)
    agg = (
        t.groupby(["agent_role", "model_family"], as_index=False)[
            [
                "request_count",
                "requests_usage_final",
                "input_tokens",
                "cache_creation_tokens",
                "cache_read_tokens",
                "output_tokens_final",
                "total_tokens_known",
            ]
        ]
        .sum()
        .sort_values("total_tokens_known")
        .reset_index(drop=True)
    )
    agg["label"] = agg["agent_role"] + " (" + agg["model_family"] + ")"
    agg["cache_read_share"] = agg["cache_read_tokens"] / agg["total_tokens_known"]
    return agg


def fig_tokens_stacked(rm: pd.DataFrame) -> go.Figure:
    """Stacked horizontal bars: where the (API-equivalent) tokens went, by role and model."""
    series = [
        ("cache_read_tokens", "Cache read", BLUE),
        ("cache_creation_tokens", "Cache creation", PINK),
        ("input_tokens", "Input (uncached)", GREEN),
        ("output_tokens_final", "Output (final counts only, a floor)", ACCENT),
    ]
    fig = go.Figure()
    for col, name, color in series:
        fig.add_trace(
            go.Bar(
                y=rm["label"],
                x=rm[col] / 1e6,
                name=name,
                orientation="h",
                marker={"color": color},
                customdata=rm[col],
                hovertemplate="%{y}<br>" + name + ": %{customdata:,.0f} tokens<extra></extra>",
            )
        )
    xmax = float(rm["total_tokens_known"].max() / 1e6)
    for _, r in rm.iterrows():
        fig.add_annotation(
            x=r["total_tokens_known"] / 1e6,
            y=r["label"],
            xanchor="left",
            yanchor="middle",
            xshift=6,
            showarrow=False,
            text=f"{fmt_tokens(r['total_tokens_known'])} ({r['cache_read_share'] * 100:.0f}% cache read)",
            font={"size": 12, "color": TEXT},
        )
    style_figure(fig, 400, margin={"l": 150, "r": 24, "t": 40, "b": 56})
    fig.update_layout(barmode="stack", legend={"traceorder": "normal"})
    fig.update_xaxes(
        range=[0, xmax * 1.5],
        title_text="Tokens (millions; API-equivalent counts, not billed)",
    )
    fig.update_yaxes(title_text=None)
    return fig


def fig_output_tokens(rm: pd.DataFrame) -> go.Figure:
    """Output tokens per role: counts with a final usage line only, so subagent bars are floors."""
    d = rm.sort_values("output_tokens_final").reset_index(drop=True)
    shares = d["requests_usage_final"] / d["request_count"]
    patterns = ["" if s >= 0.995 else "/" for s in shares]
    texts = []
    for _, r in d.iterrows():
        if r["requests_usage_final"] == 0:
            texts.append(f"unknown: 0 of {r['request_count']:.0f} requests finalised")
        elif r["requests_usage_final"] >= r["request_count"] - 0.5:
            texts.append(f"{fmt_tokens(r['output_tokens_final'])}: complete")
        else:
            texts.append(
                f"at least {fmt_tokens(r['output_tokens_final'])}: "
                f"{r['requests_usage_final']:.0f} of {r['request_count']:.0f} requests finalised"
            )
    fig = go.Figure(
        go.Bar(
            y=d["label"],
            x=d["output_tokens_final"] / 1e3,
            orientation="h",
            marker={
                "color": ACCENT,
                "pattern": {"shape": patterns, "fgcolor": BG, "size": 7, "solidity": 0.45},
            },
            text=texts,
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            customdata=d[["request_count", "requests_usage_final"]],
            hovertemplate="%{y}<br>%{x:,.1f}k output tokens (final counts)<extra></extra>",
            showlegend=False,
        )
    )
    xmax = float(d["output_tokens_final"].max() / 1e3)
    style_figure(fig, 380, margin={"l": 150, "r": 24, "t": 12, "b": 56})
    fig.update_xaxes(range=[0, xmax * 1.9], title_text="Output tokens with a final count (thousands)")
    return fig


def bucket_labels(starts: pd.Series) -> list[str]:
    return [f"{s:%H:%M} to {s + pd.Timedelta(minutes=15):%H:%M}" for s in starts]


def timeline_layout(tl: pd.DataFrame, parts: pd.DataFrame) -> list[dict[str, Any]]:
    """Columns of the timeline: one per session part, with a narrow idle-gap column between parts.

    Each entry: kind ('part' or 'gap'), the plot column (1-based), the buckets that belong to it
    and, for a part, the session-part row. Buckets are assigned by time so a second gap does not
    pick up the first gap's empty buckets.
    """
    parts = parts.sort_values("session_part").reset_index(drop=True)
    layout: list[dict[str, Any]] = []
    for i, part in parts.iterrows():
        layout.append({"kind": "part", "col": len(layout) + 1, "rows": tl[tl["session_part"] == part["session_part"]], "part": part})
        if i < len(parts) - 1:
            nxt = parts.iloc[i + 1]
            gap_rows = tl[
                tl["session_part"].isna()
                & (tl["bucket_start_local"] >= part["wall_end_at_local"].floor("15min"))
                & (tl["bucket_start_local"] < nxt["wall_start_at_local"])
            ]
            gap_h = (nxt["wall_start_at_local"] - part["wall_end_at_local"]).total_seconds() / 3600
            layout.append({"kind": "gap", "col": len(layout) + 1, "rows": gap_rows, "hours": gap_h})
    return layout


def fig_timeline(tl: pd.DataFrame, parts: pd.DataFrame) -> tuple[go.Figure, dict[str, Any]]:
    """Five aligned panels over 15-minute buckets: each session part, with the idle gaps between them."""
    tl = tl.copy()
    tl["centre"] = tl["bucket_start_local"] + pd.Timedelta(minutes=7.5)
    tl["main_requests"] = tl["llm_requests"].astype(float) - tl["subagent_llm_requests"].astype(float)
    layout = timeline_layout(tl, parts)
    ncols = len(layout)
    # Part columns are as wide as their buckets; gap columns are a narrow fixed block, not to scale
    n_buckets = [max(len(c["rows"]), 1) if c["kind"] == "part" else 0 for c in layout]
    part_total = sum(n_buckets)
    gap_share = 0.045
    n_gaps = sum(1 for c in layout if c["kind"] == "gap")
    widths = [
        (n / part_total) * (1 - gap_share * n_gaps) if c["kind"] == "part" else gap_share
        for c, n in zip(layout, n_buckets)
    ]
    row_defs = [
        ("Requests per 15 min", None),
        ("Tokens per 15 min (M)", None),
        ("Agents active", None),
        ("Codex requests", None),
        ("Human messages", None),
    ]
    fig = make_subplots(
        rows=5,
        cols=ncols,
        column_widths=widths,
        shared_xaxes="columns",
        shared_yaxes="rows",
        horizontal_spacing=0.008,
        vertical_spacing=0.045,
        row_heights=[0.26, 0.2, 0.18, 0.18, 0.18],
    )
    bar_w = 13.5 * 60 * 1000
    legend_done: set[str] = set()
    peaks = {
        1: float(tl["llm_requests"].max()),
        2: float(tl["llm_tokens_known"].astype(float).max() / 1e6),
        3: float(tl["active_agents"].max()),
        4: float(tl["codex_requests"].max()),
        5: float(tl["interventions"].astype(float).max()),
    }

    def add(col: int, row: int, trace: go.Bar, key: str) -> None:
        trace.showlegend = key not in legend_done and col == 1 and row == 1
        if trace.showlegend:
            legend_done.add(key)
        fig.add_trace(trace, row=row, col=col)

    for entry in layout:
        col, g = entry["col"], entry["rows"]
        if g.empty or entry["kind"] == "gap":
            continue
        labels = bucket_labels(g["bucket_start_local"])
        x = g["centre"]
        series = [
            (1, g["main_requests"], "Main agent requests", BLUE, "Main agent: %{y:.0f} requests", "main"),
            (1, g["subagent_llm_requests"], "Subagent requests", GREEN, "Subagents: %{y:.0f} requests", "sub"),
            (2, g["llm_tokens_known"].astype(float) / 1e6, None, SLATE, "%{y:.1f}M tokens (known)", "tok"),
            (3, g["active_agents"], None, LAVENDER, "%{y:.0f} agents with a request", "agents"),
            (4, g["codex_requests"], None, PINK, "%{y:.0f} Codex requests", "codex"),
            (5, g["interventions"].astype(float), None, ACCENT, "%{y:.0f} human messages", "human"),
        ]
        for row, y, name, color, tip, key in series:
            add(
                col,
                row,
                go.Bar(
                    x=x,
                    y=y,
                    width=bar_w,
                    name=name,
                    marker={"color": color},
                    customdata=labels,
                    hovertemplate="%{customdata} (local)<br>" + tip + "<extra></extra>",
                ),
                key,
            )
    style_figure(fig, 880, margin={"l": 78, "r": 16, "t": 48, "b": 64})
    fig.update_layout(barmode="stack", bargap=0.05, legend={"y": -0.07, "yanchor": "top", "traceorder": "normal"})
    for row, (title, _) in enumerate(row_defs, start=1):
        top = peaks[row] * 1.18 if peaks[row] > 0 else 1
        fig.update_yaxes(range=[0, top], title_text=title, row=row, col=1)
    fig.update_yaxes(rangemode="tozero")
    fig.update_yaxes(dtick=1, row=5, col=1)
    fig.update_yaxes(dtick=1, row=3, col=1)
    for entry in layout:
        col, g = entry["col"], entry["rows"]
        if g.empty or entry["kind"] == "gap":
            continue
        x0 = g["bucket_start_local"].min()
        x1 = g["bucket_end_utc"].max() - g["bucket_start_utc"].min() + x0
        fig.update_xaxes(range=[x0, x1], row=5, col=col)
        fig.update_xaxes(dtick=(3600 if len(g) > 40 else 1800) * 1000, row=5, col=col)
    fig.update_xaxes(tickformat="%H:%M", showgrid=False)
    for entry in layout:
        if entry["kind"] == "gap":
            for row in range(1, 6):
                fig.update_xaxes(visible=False, row=row, col=entry["col"])
    # Shade each idle-gap column and label it
    for entry in layout:
        if entry["kind"] != "gap":
            continue
        for row in range(1, 6):
            idx = (row - 1) * ncols + entry["col"]
            fig.add_shape(
                type="rect",
                xref=f"x{idx} domain",
                yref=f"y{idx} domain",
                x0=0,
                x1=1,
                y0=0,
                y1=1,
                fillcolor="rgba(255,255,255,0.06)",
                line={"width": 0},
                layer="below",
            )
        idx = entry["col"]
        fig.add_annotation(
            xref=f"x{idx} domain",
            yref=f"y{idx} domain",
            x=0.5,
            y=0.5,
            text=f"<b>{entry['hours']:.1f} h</b><br>idle",
            showarrow=False,
            font={"size": 12, "color": TEXT},
        )
    # Column headings from the real subplot domains
    part_labels = {1: "overnight run", 2: "24-hour extension", 3: "tool expansion and v22"}
    axis_of_col: dict[int, str] = {}
    for entry in layout:
        axis_name = "xaxis" if entry["col"] == 1 else f"xaxis{entry['col']}"
        axis_of_col[entry["col"]] = "x" if entry["col"] == 1 else f"x{entry['col']}"
        if entry["kind"] != "part":
            continue
        part = entry["part"]
        dom = fig.layout[axis_name].domain
        label = part_labels.get(int(part["session_part"]), "")
        fig.add_annotation(
            xref="paper",
            yref="paper",
            x=dom[0],
            y=1.0,
            xanchor="left",
            yanchor="bottom",
            text=f"<b>Part {int(part['session_part'])}: {label} ({part['wall_start_at_local']:%H:%M} to {part['wall_end_at_local']:%H:%M})</b>",
            showarrow=False,
            font={"size": 12, "color": TEXT},
        )
    gap_hours = [e["hours"] for e in layout if e["kind"] == "gap"]
    return fig, {"gap_hours": gap_hours, "peak_agents": peaks[3], "layout": layout, "axis_of_col": axis_of_col}


def add_compaction_marker(fig: go.Figure, when: pd.Timestamp, stats: dict[str, Any], label: str) -> None:
    """Dotted amber line through every panel of the part column that holds the compaction."""
    xref = None
    for entry in stats["layout"]:
        if entry["kind"] == "part" and not entry["rows"].empty:
            lo = entry["rows"]["bucket_start_local"].min()
            hi = lo + (entry["rows"]["bucket_end_utc"].max() - entry["rows"]["bucket_start_utc"].min())
            if lo <= when <= hi:
                xref = stats["axis_of_col"][entry["col"]]
    if xref is None:
        return
    fig.add_shape(
        type="line",
        xref=xref,
        yref="paper",
        x0=when.isoformat(),
        x1=when.isoformat(),
        y0=0,
        y1=1,
        line={"color": ACCENT, "width": 1.5, "dash": "dot"},
    )
    fig.add_annotation(
        xref=xref,
        yref="paper",
        x=when.isoformat(),
        y=0.995,
        xanchor="left",
        yanchor="top",
        xshift=4,
        text=label,
        showarrow=False,
        font={"size": 12, "color": ACCENT},
    )


AB_NEWER = "#2c6fa8"
AB_OLDER = "#b8541c"
AB_TIE = "#444c58"


def ab_matrix(ab: pd.DataFrame) -> tuple[list[str], list[str], list[list[int]], list[list[str]], pd.DataFrame]:
    """Comparison x section grid: 0 = newer preferred, 1 = older preferred, 2 = tie."""
    comps = ab[["comparison_label", "newer_version_id", "older_version_id", "newer_version_number"]].drop_duplicates()
    comps = comps.sort_values(["newer_version_number", "older_version_id"]).reset_index(drop=True)
    sections = (
        ab[["section_no", "section_name"]].drop_duplicates().sort_values("section_no")["section_name"].tolist()
    )
    sec_labels = [re.sub(r"^\d+_", "", s).replace("_", " ") for s in sections]
    sec_labels = [f"{i + 1} {s}" for i, s in enumerate(sec_labels)]
    z: list[list[int]] = []
    txt: list[list[str]] = []
    for _, c in comps.iterrows():
        sub = ab[ab["comparison_label"] == c["comparison_label"]].sort_values("section_no")
        zr: list[int] = []
        tr: list[str] = []
        for _, v in sub.iterrows():
            if v["is_tie"]:
                zr.append(2)
                tr.append("tie")
            else:
                zr.append(0 if v["newer_outcome"] == "win" else 1)
                tr.append(str(v["picked_version_id"]) + ("*" if v["is_marginal"] else ""))
        z.append(zr)
        txt.append(tr)
    y_labels = [f"{r.newer_version_id} vs {r.older_version_id}" for r in comps.itertuples()]
    return y_labels, sec_labels, z, txt, comps


def fig_ab_picks(ab: pd.DataFrame, kept_despite: list[str]) -> go.Figure:
    """Heatmap of section picks per comparison, with the two kept-despite-losing rows outlined."""
    y_labels, sec_labels, z, txt, comps = ab_matrix(ab)
    colors = [AB_NEWER, AB_OLDER, AB_TIE]
    colorscale = [
        [0.0, colors[0]],
        [1 / 3, colors[0]],
        [1 / 3, colors[1]],
        [2 / 3, colors[1]],
        [2 / 3, colors[2]],
        [1.0, colors[2]],
    ]
    meaning = ["newer version picked", "older version picked", "tie"]
    hover = [[f"{y_labels[i]}, section {sec_labels[j]}: {meaning[z[i][j]]} ({txt[i][j]})" for j in range(len(sec_labels))] for i in range(len(y_labels))]
    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=sec_labels,
            y=y_labels,
            zmin=0,
            zmax=2,
            colorscale=colorscale,
            showscale=False,
            xgap=3,
            ygap=3,
            text=hover,
            hovertemplate="%{text}<extra></extra>",
        )
    )
    for i, row in enumerate(txt):
        for j, cell in enumerate(row):
            fig.add_annotation(
                x=sec_labels[j],
                y=y_labels[i],
                text=cell,
                showarrow=False,
                font={"size": 12, "color": text_on(colors[z[i][j]])},
            )
    wins = [sum(1 for v in r if v == 0) for r in z]
    losses = [sum(1 for v in r if v == 1) for r in z]
    ties = [sum(1 for v in r if v == 2) for r in z]
    for i, c in comps.iterrows():
        kept_anyway = str(c["newer_version_id"]) in kept_despite
        label = f"{wins[i]}W {losses[i]}L {ties[i]}T"
        if kept_anyway:
            label = f"<b>{label}: kept anyway</b>"
            fig.add_shape(
                type="rect",
                xref="x",
                yref="y",
                x0=-0.5,
                x1=len(sec_labels) - 0.5,
                y0=i - 0.5,
                y1=i + 0.5,
                line={"color": ACCENT, "width": 3},
                fillcolor="rgba(0,0,0,0)",
            )
        fig.add_annotation(
            xref="x",
            yref="y",
            x=len(sec_labels) - 0.5,
            y=y_labels[i],
            xanchor="left",
            xshift=10,
            text=label,
            showarrow=False,
            font={"size": 12, "color": ACCENT if kept_anyway else TEXT},
        )
    style_figure(fig, 520, margin={"l": 92, "r": 190, "t": 70, "b": 24})
    fig.update_xaxes(side="top", showgrid=False, tickfont={"size": 12}, tickangle=0)
    fig.update_yaxes(autorange="reversed", showgrid=False, title_text=None)
    return fig


def fig_tie_rate(ab: pd.DataFrame) -> go.Figure:
    """Share of the 7 sections tied, per comparison."""
    y_labels, _, z, _, _ = ab_matrix(ab)
    rates = [sum(1 for v in r if v == 2) / len(r) * 100 for r in z]
    overall = sum(sum(1 for v in r if v == 2) for r in z) / sum(len(r) for r in z) * 100
    fig = go.Figure(
        go.Bar(
            x=y_labels,
            y=rates,
            marker={"color": GREY},
            text=[f"{r:.0f}%" for r in rates],
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            hovertemplate="%{x}<br>%{y:.0f}% of sections tied<extra></extra>",
        )
    )
    fig.add_hline(
        y=overall,
        line={"color": ACCENT, "width": 1.5, "dash": "dash"},
        annotation_text=f"all comparisons: {overall:.0f}%",
        annotation_position="top left",
        annotation_font={"size": 12, "color": ACCENT},
    )
    style_figure(fig, 340, margin={"l": 64, "r": 24, "t": 24, "b": 64})
    fig.update_yaxes(range=[0, 105], title_text="Sections tied (% of 7)")
    fig.update_xaxes(showgrid=False, title_text="Blind A/B comparison (newer vs older version)", tickangle=0)
    return fig


def fig_dialogue_strip(dlg: pd.DataFrame, sc: pd.DataFrame) -> go.Figure:
    """One square per dialogue line: position in the trailer on x, version on y, ratio as colour."""
    versions = dlg[["version_id", "version_number"]].drop_duplicates().sort_values("version_number")
    low = dlg.groupby("version_id")["meets_10db_target"].apply(lambda s: int((~s).sum()))
    total = dlg.groupby("version_id")["line_no"].count()
    ylab = {v: f"{v} ({low[v]} of {total[v]} below +10 dB)" for v in versions["version_id"]}
    d = dlg.copy()
    d["ylabel"] = d["version_id"].map(ylab)
    cmin, cmid, cmax = -4.0, 10.0, 24.0
    fig = go.Figure(
        go.Scatter(
            x=d["line_start_s"],
            y=d["ylabel"],
            mode="markers",
            marker={
                "symbol": "square",
                "size": 12,
                "color": d["dialogue_to_bed_db"],
                "cmin": cmin,
                "cmax": cmax,
                "cmid": cmid,
                "colorscale": [[0.0, "#D4501A"], [0.4999, "#F7BE96"], [0.5, "#2f6fa6"], [1.0, "#8DD0FA"]],
                "line": {"color": BG, "width": 1},
                "colorbar": {
                    "title": {"text": "dB over bed", "side": "top", "font": {"size": 12}},
                    "tickvals": [-4, 0, 10, 20],
                    "ticktext": ["-4", "0", "+10 target", "+20"],
                    "tickfont": {"size": 12},
                    "thickness": 14,
                    "len": 0.9,
                    "outlinewidth": 0,
                },
            },
            customdata=d[["version_id", "speaker", "dialogue_to_bed_db", "whisper_recall"]],
            hovertemplate=(
                "%{customdata[0]}, %{x:.1f} s<br>%{customdata[1]}<br>"
                "Dialogue over bed: %{customdata[2]:+.1f} dB<br>"
                "Whisper recall: %{customdata[3]:.0%}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    style_figure(fig, 420, margin={"l": 210, "r": 24, "t": 16, "b": 56})
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=[ylab[v] for v in versions["version_id"]][::-1],
        showgrid=True,
    )
    fig.update_xaxes(title_text="Position of the dialogue line in the trailer (seconds)", showgrid=False)
    return fig


def fig_section_loudness(sections: pd.DataFrame) -> go.Figure:
    """Heatmap: integrated loudness (LUFS) per section and version."""
    names = (
        sections.sort_values("version_number")
        .groupby("section_no")["section_name"]
        .last()
        .map(lambda s: s.split("/")[0])
    )
    versions = sections[["version_id", "version_number"]].drop_duplicates().sort_values("version_number")["version_id"].tolist()
    piv = sections.pivot(index="section_no", columns="version_id", values="section_lufs").reindex(columns=versions)
    sec_nos = piv.index.tolist()
    y_labels = [f"{n} {names[n]}" for n in sec_nos]
    zmin, zmax = -25.0, -10.0
    c_lo, c_hi = "#1d3f63", "#7cc0ee"
    fig = go.Figure(
        go.Heatmap(
            z=piv.values,
            x=versions,
            y=y_labels,
            zmin=zmin,
            zmax=zmax,
            colorscale=[[0.0, c_lo], [1.0, c_hi]],
            xgap=3,
            ygap=3,
            hovertemplate="%{x}, %{y}<br>%{z:.1f} LUFS<extra></extra>",
            colorbar={
                "title": {"text": "LUFS", "side": "top", "font": {"size": 12}},
                "tickfont": {"size": 12},
                "thickness": 14,
                "len": 0.9,
                "outlinewidth": 0,
            },
        )
    )
    for i, sec in enumerate(sec_nos):
        for j, v in enumerate(versions):
            val = piv.loc[sec, v]
            if pd.isna(val):
                continue
            col = lerp_hex(c_lo, c_hi, (val - zmin) / (zmax - zmin))
            fig.add_annotation(
                x=v,
                y=y_labels[i],
                text=f"{val:.1f}",
                showarrow=False,
                font={"size": 12, "color": text_on(col)},
            )
    style_figure(fig, 500, margin={"l": 150, "r": 24, "t": 16, "b": 48})
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(showgrid=False, title_text="Trailer version")
    return fig


def fig_dbt_tests(tests: pd.DataFrame) -> go.Figure:
    """Test counts by layer and by test type (all passing in the current run)."""
    by_layer = tests.groupby("layer").size().reindex([layer for layer in LAYER_ORDER if layer in set(tests["layer"])])
    by_type = tests.groupby("type").size().sort_values()
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Tests by layer", "Tests by type"), horizontal_spacing=0.2)
    fig.add_trace(
        go.Bar(
            y=by_layer.index,
            x=by_layer.values,
            orientation="h",
            marker={"color": GREEN},
            text=by_layer.values,
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            hovertemplate="%{y}: %{x} tests<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            y=by_type.index,
            x=by_type.values,
            orientation="h",
            marker={"color": BLUE},
            text=by_type.values,
            textposition="outside",
            textfont={"size": 12, "color": TEXT},
            cliponaxis=False,
            hovertemplate="%{y}: %{x} tests<extra></extra>",
        ),
        row=1,
        col=2,
    )
    style_figure(fig, 340, margin={"l": 110, "r": 40, "t": 36, "b": 48})
    fig.update_layout(showlegend=False)
    fig.update_yaxes(autorange="reversed", row=1, col=1, showgrid=False)
    fig.update_yaxes(showgrid=False, row=1, col=2)
    fig.update_xaxes(title_text="Tests", showgrid=False)
    fig.update_xaxes(range=[0, float(by_layer.max()) * 1.2], row=1, col=1)
    fig.update_xaxes(range=[0, float(by_type.max()) * 1.2], row=1, col=2)
    fig.update_annotations(font={"size": 13, "color": TEXT})
    return fig


# ----------------------------------------------------------------------------------------
# HTML assembly
# ----------------------------------------------------------------------------------------

CSS = f"""
:root {{
  --bg: {BG}; --surface: {SURFACE}; --surface-2: {SURFACE_2}; --border: {BORDER};
  --text: {TEXT}; --muted: {MUTED}; --accent: {ACCENT};
  --blue: {BLUE}; --green: {GREEN}; --pink: {PINK}; --orange: {ORANGE};
}}
* {{ box-sizing: border-box; }}
html {{ color-scheme: dark; scroll-behavior: smooth; scroll-padding-top: 64px; }}
body {{
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.55 {FONT_FAMILY}; -webkit-text-size-adjust: 100%;
}}
a {{ color: var(--blue); }}
a:focus-visible, summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
.wrap {{ max-width: 1120px; margin: 0 auto; padding: 0 16px; }}
header.top {{ padding: 40px 0 20px; }}
header.top h1 {{ margin: 0 0 8px; font-size: clamp(1.7rem, 4.5vw, 2.4rem); line-height: 1.15; letter-spacing: -0.01em; }}
header.top h1 span {{ color: var(--accent); }}
header.top p {{ margin: 0; color: var(--muted); max-width: 70ch; }}
nav.sections {{
  position: sticky; top: 0; z-index: 5; background: rgba(15,18,22,0.94);
  border-bottom: 1px solid var(--border); backdrop-filter: blur(6px);
}}
nav.sections ul {{ list-style: none; margin: 0; padding: 0; display: flex; gap: 4px; overflow-x: auto; white-space: nowrap; }}
nav.sections a {{ display: block; padding: 12px 12px; color: var(--muted); text-decoration: none; font-size: 0.9rem; }}
nav.sections a:hover {{ color: var(--text); }}
section {{ padding: 36px 0 8px; border-top: 1px solid var(--border); margin-top: 28px; }}
section:first-of-type {{ border-top: 0; margin-top: 0; }}
h2 {{ margin: 0 0 6px; font-size: 1.5rem; letter-spacing: -0.01em; }}
h2 .num {{ color: var(--accent); font-variant-numeric: tabular-nums; margin-right: 8px; }}
.lede {{ color: var(--muted); margin: 0 0 20px; max-width: 75ch; }}
.tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; margin-bottom: 16px; }}
.tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
.tile.wide {{ grid-column: span 2; }}
.tile .label {{ color: var(--muted); font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.04em; }}
.tile .value {{ font-size: 2rem; font-weight: 650; line-height: 1.2; margin: 4px 0 2px; font-variant-numeric: tabular-nums; }}
.tile .value small {{ font-size: 0.95rem; font-weight: 500; color: var(--muted); }}
.tile .value .acc {{ color: var(--accent); }}
.tile .sub {{ color: var(--muted); font-size: 0.88rem; }}
.hours .row {{ display: grid; grid-template-columns: 1fr; gap: 3px; margin-top: 10px; }}
.hours .row span {{ font-size: 0.88rem; }}
.hours .track {{ height: 10px; background: var(--surface-2); border-radius: 5px; overflow: hidden; border: 1px solid var(--border); }}
.hours .fill {{ height: 100%; background: var(--accent); }}
.note {{ background: var(--surface); border-left: 3px solid var(--accent); padding: 10px 14px; border-radius: 0 8px 8px 0; color: var(--text); font-size: 0.92rem; margin: 12px 0; }}
.table-wrap {{ overflow-x: auto; margin: 8px 0; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; font-variant-numeric: tabular-nums; }}
th, td {{ text-align: left; padding: 7px 10px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
th {{ color: var(--muted); font-weight: 600; font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.03em; }}
th.num, td.num {{ text-align: right; }}
figure.chart {{ margin: 28px 0 32px; }}
figure.chart h3 {{ margin: 0 0 4px; font-size: 1.12rem; line-height: 1.35; font-weight: 600; max-width: 85ch; }}
figure.chart .sub {{ margin: 0 0 10px; color: var(--muted); font-size: 0.92rem; max-width: 85ch; }}
.scroll {{ overflow-x: auto; background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 8px 8px 4px; }}
.plot {{ min-width: 640px; }}
figcaption.source {{ color: var(--muted); font-size: 0.82rem; margin-top: 6px; }}
details {{ margin-top: 8px; color: var(--muted); font-size: 0.9rem; }}
summary {{ cursor: pointer; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0 0 8px; font-size: 0.88rem; color: var(--text); }}
.legend i {{ display: inline-block; width: 14px; height: 14px; border-radius: 3px; vertical-align: -2px; margin-right: 6px; }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(420px, 100%), 1fr)); gap: 16px; }}
.card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
.card h4 {{ margin: 0 0 8px; font-size: 1rem; }}
.card ul {{ margin: 0; padding-left: 1.1em; font-size: 0.92rem; }}
.card li {{ margin: 4px 0; }}
.chips {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3px 16px; font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
.chips div {{ display: flex; justify-content: space-between; gap: 8px; border-bottom: 1px solid var(--border); padding: 2px 0; }}
.chips span {{ color: var(--muted); overflow: hidden; text-overflow: ellipsis; }}
.card th, .card td {{ padding: 6px 6px; }}
ul.notes {{ margin: 0 0 10px; padding-left: 1.2em; color: var(--muted); font-size: 0.9rem; max-width: 95ch; }}
ul.notes li {{ margin: 3px 0; }}
.status-ok {{ color: var(--green); font-weight: 600; }}
.status-warn {{ color: var(--accent); font-weight: 600; }}
footer {{ border-top: 1px solid var(--border); margin-top: 48px; padding: 24px 0 56px; color: var(--muted); font-size: 0.88rem; }}
footer h2 {{ font-size: 1.05rem; color: var(--text); }}
footer dt {{ color: var(--text); font-weight: 600; margin-top: 8px; }}
footer dd {{ margin: 2px 0 0; max-width: 85ch; }}
@media (max-width: 640px) {{
  .tile.wide {{ grid-column: span 1; }}
  header.top {{ padding-top: 24px; }}
}}
"""


def figure_block(
    *,
    fig_id: str,
    takeaway: str,
    fig: go.Figure,
    source: str,
    subtitle: str = "",
    alt: str = "",
    min_width: int = 640,
    extra_above: str = "",
    details: str = "",
) -> str:
    """One chart with a takeaway headline, optional subtitle, source line and data table."""
    sub = f'<p class="sub">{subtitle}</p>' if subtitle else ""
    det = f"<details><summary>Show the data behind this chart</summary>{details}</details>" if details else ""
    return (
        f'<figure class="chart" id="{fig_id}-block">'
        f'<h3 id="{fig_id}-title">{takeaway}</h3>{sub}{extra_above}'
        f'<div class="scroll"><div class="plot" style="min-width:{min_width}px" role="img" '
        f'aria-labelledby="{fig_id}-title" aria-describedby="{fig_id}-alt">'
        f"{figure_html(fig, fig_id)}</div></div>"
        f'<p id="{fig_id}-alt" hidden>{esc(alt or takeaway)}</p>'
        f'<figcaption class="source">Source: {esc(source)}</figcaption>{det}</figure>'
    )


def tile(label: str, value: str, sub: str = "", *, wide: bool = False) -> str:
    cls = "tile wide" if wide else "tile"
    return (
        f'<div class="{cls}"><div class="label">{label}</div><div class="value">{value}</div>'
        f'<div class="sub">{sub}</div></div>'
    )


# ----------------------------------------------------------------------------------------
# Plateau chart: every critic's score for every version, with the promotion record
# ----------------------------------------------------------------------------------------

CRITIC_STYLE: dict[str, dict[str, Any]] = {
    # critic_id: label, colour, line dash, marker symbol
    "fable_editor": {"label": "Fable editor (its own review)", "color": ACCENT, "dash": "solid", "symbol": "circle"},
    "fable_editor_rescored": {
        "label": "Fable editor re-scoring the same version in the next review",
        "color": ACCENT,
        "dash": "dot",
        "symbol": "circle-open",
    },
    "codex_critic": {"label": "Codex critic", "color": BLUE, "dash": "solid", "symbol": "square"},
    "gemini_flash": {"label": "Gemini Flash (non-discriminating)", "color": PINK, "dash": "dash", "symbol": "diamond"},
    "gemini_pro_web": {"label": "Gemini Pro app (one run)", "color": SLATE, "dash": "solid", "symbol": "diamond-open"},
    "twelvelabs": {"label": "TwelveLabs (non-discriminating)", "color": LAVENDER, "dash": "dash", "symbol": "triangle-up"},
}
CROWD_STYLE: dict[str, dict[str, Any]] = {
    "shareability": {"label": "Crowd: shareability", "color": GREEN, "dash": "solid", "symbol": "circle"},
    "would_watch_to_end": {"label": "First-time viewer: would watch to the end", "color": BLUE, "dash": "solid", "symbol": "square"},
    "ai_slop_perception": {"label": "Crowd: reads as AI slop (higher is worse)", "color": ORANGE, "dash": "dash", "symbol": "x"},
}
DIRECTOR_BANDS = [
    # (first version, last version, label)
    (17, 17, "Director's<br>v16 notes"),
    (19, 19, "Director:<br>recut call"),
    (20, 21, "Director: HUD<br>looks cheap"),
    (24, 27, "Director's calls: staging audio,<br>hero beat, quieter tags, slow-mo"),
]


def plateau_tick_text(ver: pd.DataFrame) -> tuple[list[int], list[str]]:
    """Version labels with the ledger loop hours spent when each version was exported."""
    nums = ver["version_number"].astype(int).tolist()
    text = [f"v{n}<br>{h:.1f} h" for n, h in zip(nums, ver["loop_hours_at_export"])]
    return nums, text


def _line_trace(
    sub: pd.DataFrame,
    style: dict[str, Any],
    *,
    name: str | None = None,
    legend_group: str | None = None,
    size: int = 8,
    width: float = 2.4,
    connect: bool = True,
    all_versions: list[int] | None = None,
) -> go.Scatter:
    """One critic's line. With connect=False the line breaks wherever the critic did not score."""
    sub = sub.sort_values("version_number")
    if not connect and all_versions:
        sub = sub.set_index("version_number").reindex(all_versions).rename_axis("version_number").reset_index()
        sub["is_promoted"] = sub["is_promoted"].fillna(False).astype(bool)
        sub["outcome"] = sub["outcome"].fillna("")
    hover = [
        f"<b>v{int(r.version_number)}</b> &middot; {esc(style['label'])}<br>score {r.score:g}"
        f"<br>{'PROMOTED' if r.is_promoted else 'not promoted'} ({esc(r.outcome)})"
        if pd.notna(r.score) else ""
        for r in sub.itertuples()
    ]
    return go.Scatter(
        x=sub["version_number"],
        y=sub["score"],
        mode="lines+markers",
        name=name or style["label"],
        legendgroup=legend_group,
        line={"color": style["color"], "dash": style["dash"], "width": width},
        marker={"symbol": style["symbol"], "size": size, "color": style["color"], "line": {"width": 1.6, "color": style["color"]}},
        connectgaps=connect,
        hovertext=hover,
        hoverinfo="text",
    )


def fig_plateau(plateau: pd.DataFrame, ver: pd.DataFrame, *, height: int = 880, for_png: bool = False) -> go.Figure:
    """Three stacked panels on one version axis: rubric critics, crowd personas, decision strip."""
    rubric = plateau[plateau["score_category"] == "overall"]
    crowd = plateau[plateau["critic_id"] == "crowd_ftv"]
    nums, ticktext = plateau_tick_text(ver)
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.56, 0.27, 0.17],
        vertical_spacing=0.05,
    )

    # --- panel 1: rubric critics, overall score
    for critic_id, style in CRITIC_STYLE.items():
        sub = rubric[rubric["critic_id"] == critic_id]
        if sub.empty:
            continue
        if critic_id == "fable_editor":
            fig.add_trace(_line_trace(sub, style, size=9, width=3.2), row=1, col=1)
        elif critic_id in ("gemini_flash", "twelvelabs", "gemini_pro_web"):
            fig.add_trace(_line_trace(sub, style, size=10, width=1.8), row=1, col=1)
        else:
            fig.add_trace(_line_trace(sub, style, connect=False, all_versions=nums), row=1, col=1)

    # --- panel 2: crowd personas
    for category, style in CROWD_STYLE.items():
        sub = crowd[crowd["score_category"] == category]
        if sub.empty:
            continue
        fig.add_trace(
            _line_trace(sub, style, legend_group="crowd", size=7, width=2.0, connect=False, all_versions=nums), row=2, col=1
        )

    # --- panel 3: decision strip (promoted = filled amber, not promoted = hollow grey)
    promoted = ver[ver["is_promoted"]]
    rejected = ver[~ver["is_promoted"]]
    fig.add_trace(
        go.Scatter(
            x=promoted["version_number"],
            y=[1] * len(promoted),
            mode="markers",
            name="Promoted to BEST",
            marker={"symbol": "star", "size": 15, "color": ACCENT, "line": {"width": 1, "color": BG}},
            hovertext=[
                f"<b>{esc(r.version_id)} promoted</b> ({esc(r.decision_basis)})<br>{esc(r.decision_reason)}"
                for r in promoted.itertuples()
            ],
            hoverinfo="text",
        ),
        row=3,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=rejected["version_number"],
            y=[1] * len(rejected),
            mode="markers",
            name="Not promoted (reverted or lost)",
            marker={"symbol": "x-thin-open", "size": 12, "color": GREY, "line": {"width": 2.2, "color": GREY}},
            hovertext=[
                f"<b>{esc(r.version_id)} not promoted</b> ({esc(r.decision_basis)})<br>{esc(r.decision_reason)}"
                for r in rejected.itertuples()
            ],
            hoverinfo="text",
        ),
        row=3,
        col=1,
    )

    # --- director's-note bands across all panels
    for first, last, label in DIRECTOR_BANDS:
        fig.add_vrect(
            x0=first - 0.5,
            x1=last + 0.5,
            fillcolor="rgba(255,176,64,0.10)",
            line={"width": 0},
            layer="below",
            row="all",
            col=1,
        )
        fig.add_annotation(
            x=(first + last) / 2,
            y=1.0,
            xref="x",
            yref="paper",
            yanchor="bottom",
            text=label,
            showarrow=False,
            align="center",
            font={"size": 12 if not for_png else 13, "color": ACCENT},
        )

    # --- honest labels on the unreliable critics
    tl = rubric[rubric["critic_id"] == "twelvelabs"]
    if len(tl) >= 2 and tl["score"].nunique() == 1:
        fig.add_annotation(
            x=float(tl["version_number"].max()) + 0.45,
            y=float(tl["score"].iloc[0]),
            xref="x",
            yref="y",
            xanchor="right",
            yanchor="bottom",
            yshift=10,
            text="Same 10 scores for v19 and v21<br>(also off the half-point scale)",
            showarrow=False,
            font={"size": 12, "color": LAVENDER},
        )
    gf = rubric[rubric["critic_id"] == "gemini_flash"].sort_values("version_number")
    if len(gf) >= 2:
        fig.add_annotation(
            x=float(gf["version_number"].max()) + 0.45,
            y=float(gf["score"].min()),
            xref="x",
            yref="y",
            xanchor="right",
            yanchor="top",
            yshift=-10,
            text="Gemini: v20 = the first v18 run; the retry that replaced it<br>differs by as much as v18 does from v20",
            showarrow=False,
            font={"size": 12, "color": PINK},
        )
    # the scale shift: v17 was 8.0 in its own review and 7.0 in the next
    fe = rubric[rubric["critic_id"] == "fable_editor"].set_index("version_number")["score"]
    fr = rubric[rubric["critic_id"] == "fable_editor_rescored"].set_index("version_number")["score"]
    if 17 in fe.index and 17 in fr.index:
        fig.add_annotation(
            x=17,
            y=float(fr.loc[17]),
            xref="x",
            yref="y",
            ax=-70,
            ay=40,
            axref="pixel",
            ayref="pixel",
            text=f"Same critic, same v17: {fe.loc[17]:.1f} in its own review,<br>{fr.loc[17]:.1f} when re-scoring it for v18",
            showarrow=True,
            arrowhead=2,
            arrowcolor=ACCENT,
            arrowwidth=1.2,
            font={"size": 12, "color": ACCENT},
            align="right",
        )

    style_figure(fig, height, margin={"l": 70, "r": 40, "t": 92 if for_png else 58, "b": 120})
    fig.update_xaxes(
        tickmode="array",
        tickvals=nums,
        ticktext=ticktext,
        range=[0.4, max(nums) + 0.6],
        showgrid=False,
    )
    fig.update_yaxes(title_text="Overall score (1 to 10)", range=[4.8, 9.6], dtick=0.5, row=1, col=1)
    fig.update_yaxes(title_text="Crowd score (1 to 10)", range=[2.5, 7.5], dtick=1, row=2, col=1)
    fig.update_yaxes(showticklabels=False, showgrid=False, title_text="Promoted?", range=[0.5, 1.5], row=3, col=1)
    fig.update_layout(
        legend={"orientation": "h", "x": 0, "y": -0.13, "yanchor": "top", "font": {"size": 12}, "tracegroupgap": 8},
        hovermode="closest",
    )
    if for_png:
        fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG, font={"size": 14, "color": TEXT}, width=1600)
    return fig


def plateau_details(plateau: pd.DataFrame, ver: pd.DataFrame) -> str:
    """Compact table: one row per version, one column per critic headline score."""
    wide = (
        plateau[plateau["score_category"].isin(["overall", "shareability", "ai_slop_perception", "would_watch_to_end"])]
        .assign(col=lambda d: d["critic_id"].where(d["critic_id"] != "crowd_ftv", d["score_category"]))
        .pivot(index="version_number", columns="col", values="score")
    )
    order = [c for c in [
        "fable_editor", "fable_editor_rescored", "codex_critic", "gemini_flash", "gemini_pro_web", "twelvelabs",
        "shareability", "ai_slop_perception", "would_watch_to_end",
    ] if c in wide.columns]
    short = {
        "fable_editor": "Fable", "fable_editor_rescored": "Fable re-score", "codex_critic": "Codex",
        "gemini_flash": "Gemini Flash", "gemini_pro_web": "Gemini Pro app", "twelvelabs": "TwelveLabs",
        "shareability": "Share", "ai_slop_perception": "Slop", "would_watch_to_end": "Watch",
    }
    table = ver[["version_number", "version_id", "loop_hours_at_export", "is_promoted", "decision_basis"]].merge(
        wide[order].reset_index(), on="version_number", how="left"
    )
    out = pd.DataFrame({"Version": table["version_id"], "Loop h": table["loop_hours_at_export"].map(lambda x: f"{x:.1f}")})
    out["Promoted"] = table["is_promoted"].map({True: "yes", False: "no"})
    for c in order:
        out[short[c]] = table[c].map(lambda x: "" if pd.isna(x) else f"{x:g}")
    out["Basis"] = table["decision_basis"].fillna("")
    return html_table(out, numeric_cols=set(out.columns) - {"Version", "Promoted", "Basis"})


def plateau_takeaway(plateau: pd.DataFrame, ver: pd.DataFrame) -> str:
    """The one-sentence finding, computed from the data so it cannot drift from the chart."""
    fable = plateau[(plateau["critic_id"] == "fable_editor") & (plateau["score_category"] == "overall")].sort_values("version_number")
    first, last = fable[fable["version_number"] == 14], fable[fable["version_number"] == fable["version_number"].max()]
    if first.empty or last.empty:
        return "Scores flatten after v14"
    hours = ver.set_index("version_number")["loop_hours_at_export"]
    h0, h1 = float(hours.loc[14]), float(hours.loc[int(last["version_number"].iloc[0])])
    return (
        f"The Fable editor went from {first['score'].iloc[0]:.1f} at v14 ({h0:.1f} loop hours) to {last['score'].iloc[0]:.1f} at "
        f"v{int(last['version_number'].iloc[0])} ({h1:.1f} hours): {h1 - h0:.1f} more hours for "
        f"{last['score'].iloc[0] - first['score'].iloc[0]:+.1f} points, "
        "on a scale that moved between reviews"
    )


def build_plateau(data: dict[str, pd.DataFrame]) -> str:
    plateau, ver = data["plateau"], data["plateau_versions"]
    fig = fig_plateau(plateau, ver)
    n = len(ver)
    takeaway = plateau_takeaway(plateau, ver)
    sub = (
        f"{n} versions, one line per critic. Stars in the bottom strip are the versions promoted to BEST; shaded bands are the "
        "versions that followed a note from the director. The tick labels give the loop hours spent when each version was exported "
        "(ledger segments only). Gemini and TwelveLabs are drawn, and labelled, as scorers that did not separate versions."
    )
    notes = (
        '<ul class="notes">'
        "<li>Each Fable score is on that review's own scale. The dotted line is the same critic re-scoring the version in the next "
        "review: v17 was 8.0, then 7.0.</li>"
        "<li>The Fable editor scored v1 to v11, v14 to v24 and v26; v3, v6, v12, v13, v25, v27 and v28 have no editor review of their "
        "own (v25 was re-scored 9.5 inside the v26 review; v27 and v28 had no fresh critic pass). Codex and the crowd were last run on v22; "
        "Codex was not run for v16 and v17.</li>"
        "<li>Gemini Flash and TwelveLabs are shown for transparency. TwelveLabs gave v19 and v21 the identical ten scores. The log says "
        "Gemini gave v20 exactly the first v18 run's scores; that file was overwritten by a retry, and the stored v18 differs by 0.5.</li>"
        "<li>The crowd lines come from personas looking at stills (integer scores); lower is better only for the slop line.</li>"
        "</ul>"
    )
    block = figure_block(
        fig_id="fig-plateau",
        takeaway=takeaway,
        subtitle=sub,
        fig=fig,
        source="mart_critic_plateau, dim_version, dim_critic",
        alt=(
            "Line chart of critic scores for versions 1 to 28 with promoted versions starred and the director's-note versions shaded. "
            "The Fable editor rises from 5.5 at v1 to 8.0 at v14, sits between 7.5 and 8.5 from v17 to v21, then reads 9.0 at v22 and 9.5 from v23 to v26."
        ),
        min_width=1100,
        extra_above=notes,
        details=plateau_details(plateau, ver),
    )
    return f'<section id="plateau"><h2>The plateau</h2>{block}</section>'


def write_plateau_page(data: dict[str, pd.DataFrame], build_time: str) -> Path:
    """Standalone page: just the plateau section, same look and the shared plotly.min.js."""
    page = render_page([build_plateau(data)], "", "MOONSHOT plateau chart", n_versions=len(data["plateau_versions"]), nav=False)
    out = SITE_DIR / "plateau.html"
    out.write_text(page, encoding="utf-8", newline="\n")
    return out


def export_plateau_png(data: dict[str, pd.DataFrame], png_path: Path) -> bool:
    """Render the chart to a PNG with headless Chrome (kaleido is not installed). False if no browser."""
    import shutil
    import subprocess
    import tempfile

    browser = next(
        (p for p in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            shutil.which("chrome") or "",
            shutil.which("msedge") or "",
        ) if p and Path(p).exists()),
        None,
    )
    if browser is None:
        print("warning: no Chrome or Edge found; PNG not written")
        return False
    fig = fig_plateau(data["plateau"], data["plateau_versions"], height=980, for_png=True)
    width, height = 1600, 1060
    work = Path(tempfile.mkdtemp(prefix="plateau_png_"))
    try:
        fig_div = fig.to_html(full_html=False, include_plotlyjs=False, config={"staticPlot": True, "displayModeBar": False},
                              default_width=f"{width}px", default_height="980px")
        title = "MOONSHOT: every critic's score per version, v1 to v" + str(int(data["plateau_versions"]["version_number"].max()))
        foot = (plateau_takeaway(data["plateau"], data["plateau_versions"]) + ". Source: warehouse model mart_critic_plateau. "
                "Gemini Flash and TwelveLabs did not separate versions.")
        html_page = (
            f"<!doctype html><html><head><meta charset='utf-8'><script src='{(SITE_DIR / 'plotly.min.js').as_uri()}'></script>"
            f"<style>html,body{{margin:0;background:{BG};color:{TEXT};font-family:{FONT_FAMILY}}}"
            f"h1{{font-size:24px;margin:16px 24px 0 70px}}p{{margin:4px 24px 0 70px;color:{MUTED};font-size:13px}}</style></head>"
            f"<body><h1>{html.escape(title)}</h1><p>{html.escape(foot)}</p>{fig_div}</body></html>"
        )
        page = work / "plateau_png.html"
        page.write_text(html_page, encoding="utf-8")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={work / 'profile'}",
             f"--window-size={width},{height}", "--virtual-time-budget=6000", f"--screenshot={png_path}", page.as_uri()],
            check=True, capture_output=True, timeout=120,
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"wrote {png_path}")
    return True


def build_headline(data: dict[str, pd.DataFrame]) -> tuple[str, dict[str, Any]]:
    """Section 1: stat tiles and the tokens-by-model table. Returns (html, headline numbers)."""
    sc = data["scorecard"]
    exported = sc[sc["exported_at_local"].notna()]
    n_exported = len(exported)
    kept = exported[exported["is_promoted"]]
    reverted = exported[exported["outcome"] == "reverted"]["version_id"].tolist()
    not_best = exported[exported["outcome"] == "not_best"]["version_id"].tolist()
    final_v = exported[exported["is_final"]]["version_id"].tolist()
    scored = exported[exported["has_editor_score"]]
    first_v, last_v = scored.iloc[0], scored.iloc[-1]
    parts = data["session_parts"].sort_values("session_part").reset_index(drop=True)
    active_total = float(parts["active_hours"].sum())
    wall_total = float(parts["wall_hours"].sum())
    idle_h = sum(
        (parts.iloc[i + 1]["wall_start_at_local"] - parts.iloc[i]["wall_end_at_local"]).total_seconds() / 3600
        for i in range(len(parts) - 1)
    )
    by_model = data["llm_by_model"].copy()
    for col in ("input_tokens", "cache_creation_tokens", "cache_read_tokens", "output_tokens"):
        by_model[col] = by_model[col].astype(float)
    by_model["total"] = by_model[["input_tokens", "cache_creation_tokens", "cache_read_tokens", "output_tokens"]].sum(axis=1)
    total_requests = int(by_model["requests"].sum())
    total_tokens = float(by_model["total"].sum())
    cache_read_share = float(by_model["cache_read_tokens"].sum()) / total_tokens
    codex = data["codex"].iloc[0]
    n_runs = int(data["agent_runs"].iloc[0]["runs"])
    split = ", ".join(
        f"{int(r.requests):,} {r.model_id.replace('claude-', '').split('-')[0].title()}" for r in by_model.itertuples()
    )

    tiles = [
        tile(
            "Versions exported",
            f"{n_exported}",
            f"{exported.iloc[0]['version_id']} to {exported.iloc[-1]['version_id']}"
            + ("; " + ", ".join(sc[sc["outcome"] == "in_progress"]["version_id"]) + " in progress" if (sc["outcome"] == "in_progress").any() else ""),
        ),
        tile(
            "Kept vs reverted",
            f'<span class="acc">{len(kept)}</span> kept <small>/ {len(reverted)} reverted</small>',
            f"Reverted: {', '.join(reverted) or 'none'}. Not best: {', '.join(not_best) or 'none'}. FINAL: {', '.join(final_v)}.",
        ),
        tile(
            "Editor score, first to latest",
            f'{first_v["editor_overall_score"]:.1f} <small>to</small> <span class="acc">{last_v["editor_overall_score"]:.1f}</span>',
            f"Overall, 1 to 10 scale, {first_v['version_id']} to {last_v['version_id']} (latest editor-scored version; {len(scored)} scored).",
        ),
        tile(
            "Claude requests",
            f"{total_requests:,}",
            f"{split}. {n_runs} subagent runs.",
        ),
        tile(
            "Claude tokens",
            f"{fmt_tokens(total_tokens)}",
            f"{cache_read_share * 100:.0f}% cache reads. API-equivalent token counts, not billed; output counts are floors.",
        ),
        tile(
            "Codex requests",
            f"{int(codex['requests']):,}",
            f"{int(codex['sessions'])} sessions; {fmt_tokens(float(codex['input_tokens']))} input tokens "
            f"({float(codex['cached_input_tokens']) / float(codex['input_tokens']) * 100:.0f}% cached), "
            f"{fmt_tokens(float(codex['output_tokens']))} output.",
        ),
    ]

    def hours_row(label: str, r: pd.Series) -> str:
        share = float(r["active_hours"]) / float(r["wall_hours"])
        return (
            f'<div class="row"><span>{label}: <b>{r["active_hours"]:.1f} h</b> active of '
            f'{r["wall_hours"]:.1f} h wall-clock ({share * 100:.0f}%)</span>'
            f'<div class="track" aria-hidden="true"><div class="fill" style="width:{share * 100:.1f}%"></div></div></div>'
        )

    part_names = {1: "overnight run", 2: "24-hour extension", 3: "tool expansion and v22"}
    hours_rows = "".join(
        hours_row(f"Part {int(r.session_part)} ({part_names.get(int(r.session_part), '')})", parts.iloc[i])
        for i, r in enumerate(parts.itertuples())
    )
    hours_tile = (
        '<div class="tile wide hours"><div class="label">Active hours vs wall-clock hours, per session part</div>'
        f"{hours_rows}"
        f'<div class="sub" style="margin-top:10px">Total {active_total:.1f} h active of {wall_total:.1f} h wall-clock, '
        f"with {idle_h:.1f} h of idle gaps between the parts that count as neither. Part 3 is still open.</div></div>"
    )

    table = pd.DataFrame(
        {
            "Model": by_model["model_id"],
            "Requests": by_model["requests"].map(fmt_int),
            "Input (uncached)": by_model["input_tokens"].map(fmt_int),
            "Cache creation": by_model["cache_creation_tokens"].map(fmt_int),
            "Cache read": by_model["cache_read_tokens"].map(fmt_int),
            "Output (floor)": by_model["output_tokens"].map(fmt_int),
            "Total known": by_model["total"].map(fmt_int),
            "No final output count": by_model["requests_without_final_usage"].map(fmt_int),
        }
    )
    codex_row = pd.DataFrame(
        [
            {
                "Model": f"{codex['model_id']} (Codex)",
                "Requests": fmt_int(float(codex["requests"])),
                "Input (uncached)": fmt_int(float(codex["input_tokens"]) - float(codex["cached_input_tokens"])),
                "Cache creation": "n/a",
                "Cache read": fmt_int(float(codex["cached_input_tokens"])),
                "Output (floor)": fmt_int(float(codex["output_tokens"])),
                "Total known": fmt_int(float(codex["total_tokens"])),
                "No final output count": "n/a",
            }
        ]
    )
    table = pd.concat([table, codex_row], ignore_index=True)
    num_cols = set(table.columns) - {"Model"}
    headline = {
        "versions_exported": n_exported,
        "kept": len(kept),
        "reverted": reverted,
        "not_best": not_best,
        "score_first": float(first_v["editor_overall_score"]),
        "score_last": float(last_v["editor_overall_score"]),
        "score_first_v": first_v["version_id"],
        "score_last_v": last_v["version_id"],
        "active_hours": [float(h) for h in parts["active_hours"]],
        "wall_hours": [float(h) for h in parts["wall_hours"]],
        "requests": total_requests,
        "tokens": total_tokens,
        "cache_read_share": cache_read_share,
        "codex_requests": int(codex["requests"]),
    }
    body = (
        '<section id="headline"><h2><span class="num">1</span>Headline numbers</h2>'
        f'<p class="lede">MOONSHOT was one Claude Code agent loop that cut {n_exported} versions of an Apollo 11 trailer, '
        "using critic subagents, blind A/B judges and Codex reviews. Everything below is read from a dbt + DuckDB "
        "warehouse built on the loop's own logs.</p>"
        f'<div class="tiles">{"".join(tiles[:3])}{tiles[5]}{hours_tile}{tiles[3]}{tiles[4]}</div>'
        '<div class="note"><b>API-equivalent token counts, not billed; output counts are floors.</b> '
        "The warehouse holds no dollar prices, and about a third of requests never logged a closing usage line "
        "(see the data-quality section).</div>"
        '<h3 style="font-size:1.05rem;margin:20px 0 4px">Requests and tokens by model</h3>'
        f"{html_table(table, numeric_cols=num_cols)}"
        '<p class="source" style="color:var(--muted);font-size:0.82rem;margin:4px 0 0">'
        "Source: fct_llm_requests, fct_codex_requests, fct_agent_runs, dim_session_part. "
        "Codex counts follow the OpenAI convention: input includes cached input, shown here split into uncached and cached.</p>"
        "</section>"
    )
    return body, headline


def build_scores(data: dict[str, pd.DataFrame]) -> str:
    sc = data["scorecard"]
    critic = data["critic"]
    exported = sc[sc["exported_at_local"].notna()]
    scored = exported[exported["has_editor_score"]]
    max_score = float(scored["editor_overall_score"].max())
    first_max = scored[scored["editor_overall_score"] == max_score].iloc[0]
    first, last = scored.iloc[0], scored.iloc[-1]
    held = scored[scored["version_number"] >= first_max["version_number"]]
    held_txt = (
        f", reached {max_score:.1f} at {first_max['version_id']}"
        + (f" and held at {held.iloc[-1]['version_id']}" if len(held) > 1 and (held["editor_overall_score"] == max_score).all() else "")
    )
    title1 = (
        f"Editor score rose from {first['editor_overall_score']:.1f} ({first['version_id']}) to "
        f"{last['editor_overall_score']:.1f} ({last['version_id']}) across {len(scored)} scored versions{held_txt}"
    )
    unscored = exported[~exported["has_editor_score"]]["version_id"].tolist()
    sub1 = (
        f"Not every step was an improvement: v4 and v5 dipped to 6.0 before recovering. "
        f"{', '.join(unscored)} have no editor score because they were judged by blind A/B only. "
        "Each score is one critic pass per version."
    )
    table1 = exported[
        ["version_id", "outcome", "decision_basis", "editor_overall_score", "ab_result", "ab_compared_with_version_id"]
    ].copy()
    table1.columns = ["Version", "Outcome", "Decision basis", "Editor overall", "A/B result (newer)", "A/B compared with"]
    table1 = table1.fillna("n/a")
    fig1 = fig_score_trajectory(sc)

    # Category multiples
    first_scores = critic.sort_values("version_number").groupby("score_category").first()["score"]
    last_scores = critic.sort_values("version_number").groupby("score_category").last()["score"]
    delta = (last_scores - first_scores).drop("overall", errors="ignore").sort_values(ascending=False)
    top = delta.index[:2].tolist()
    lowest_val = float(delta.min())
    lowest = [CATEGORY_LABELS[c].lower() for c in delta[delta == lowest_val].index]
    if (delta >= 0).all():
        title2 = (
            f"All nine categories ended higher than they started; {CATEGORY_LABELS[top[0]].lower()} "
            f"(+{delta[top[0]]:.1f}) and {CATEGORY_LABELS[top[1]].lower()} (+{delta[top[1]]:.1f}) gained most, "
            f"{' / '.join(lowest)} least (+{lowest_val:.1f})"
        )
    else:
        worst = delta.index[-1]
        title2 = f"{CATEGORY_LABELS[top[0]]} gained most (+{delta[top[0]]:.1f}); {CATEGORY_LABELS[worst]} fell ({delta[worst]:+.1f})"
    fig2 = fig_category_multiples(critic)
    pivot = critic.pivot(index="version_number", columns="score_category", values="score")
    pivot.index = [f"v{n}" for n in pivot.index]
    pivot = pivot[[c for c in CATEGORY_LABELS if c in pivot.columns]].reset_index()
    pivot.columns = ["Version"] + [CATEGORY_LABELS[c] for c in pivot.columns[1:]]
    return (
        '<section id="scores"><h2><span class="num">2</span>Score trajectory</h2>'
        '<p class="lede">An editor critic (a separate model instance) scored each version from 1 to 10 on nine craft '
        "categories plus an overall score.</p>"
        + figure_block(
            fig_id="fig-score",
            takeaway=title1,
            subtitle=sub1,
            fig=fig1,
            source="mart_version_scorecard (editor_overall_score, outcome, decision_basis)",
            alt="Line chart of the editor overall score per version, with a strip below showing each version's keep or revert decision.",
            details=html_table(table1, numeric_cols={"Editor overall"}),
        )
        + figure_block(
            fig_id="fig-categories",
            takeaway=title2,
            subtitle="Same 4 to 9 scale in every panel. Panel titles give first and latest scored value. The overall score is amber.",
            fig=fig2,
            source="fct_critic_scores, dim_score_category",
            alt="Ten small line charts, one per editor category, showing scores by version.",
            min_width=560,
            details=html_table(pivot, numeric_cols=set(pivot.columns) - {"Version"}),
        )
        + "</section>"
    )


def build_tokens(data: dict[str, pd.DataFrame]) -> str:
    rm = role_model_table(data["tokens"])
    total = float(rm["total_tokens_known"].sum())
    cache_read = float(rm["cache_read_tokens"].sum())
    top = rm.sort_values("total_tokens_known", ascending=False).iloc[0]
    title1 = (
        f"Cache reads were {cache_read / total * 100:.0f}% of the {fmt_tokens(total)} tokens, "
        f"and the {top['agent_role']} agent alone used {top['total_tokens_known'] / total * 100:.0f}%"
    )
    fig1 = fig_tokens_stacked(rm)
    summary = data["llm_summary"].iloc[0]
    no_final = int(summary["no_final_usage"])
    n_req = int(summary["requests"])
    out_total = float(rm["output_tokens_final"].sum())
    title2 = (
        f"Output is under 1% of the tokens, and {no_final / n_req * 100:.0f}% of requests ({no_final} of {n_req:,}) "
        "have no final output count, so subagent bars are floors"
    )
    fig2 = fig_output_tokens(rm)
    tbl = rm.sort_values("total_tokens_known", ascending=False)[
        [
            "label",
            "request_count",
            "requests_usage_final",
            "input_tokens",
            "cache_creation_tokens",
            "cache_read_tokens",
            "output_tokens_final",
            "total_tokens_known",
        ]
    ].copy()
    tbl.columns = ["Role (model)", "Requests", "With final usage", "Input", "Cache creation", "Cache read", "Output (floor)", "Total known"]
    for col in tbl.columns[1:]:
        tbl[col] = tbl[col].map(fmt_int)
    return (
        '<section id="tokens"><h2><span class="num">3</span>Where the tokens went</h2>'
        '<p class="lede">Each agent request reports four separate counts. A long-running agent re-reads its whole context '
        "on every turn, and those re-reads come back as cache reads, so they dwarf everything else. "
        "<b>API-equivalent token counts, not billed; output counts are floors.</b></p>"
        + figure_block(
            fig_id="fig-tokens",
            takeaway=title1,
            subtitle="Agent role (model family), all session parts. Input and output are on the chart but too small to see at this scale; "
            "the second chart shows output on its own.",
            fig=fig1,
            source="mart_token_usage_by_role_session",
            alt="Horizontal stacked bars of cache read, cache creation, input and output tokens for each agent role and model.",
            min_width=640,
            details=html_table(tbl, numeric_cols=set(tbl.columns) - {"Role (model)"}),
        )
        + figure_block(
            fig_id="fig-output",
            takeaway=title2,
            subtitle=f"Solid bars have a final count on every request; hatched bars are floors. All roles together: at least {fmt_tokens(out_total)} output tokens.",
            fig=fig2,
            source="mart_token_usage_by_role_session (output_tokens_final, requests_usage_final)",
            alt="Horizontal bars of output tokens per agent role, hatched where counts are incomplete.",
            min_width=640,
        )
        + "</section>"
    )


def build_timeline(data: dict[str, pd.DataFrame], compactions: pd.DataFrame) -> str:
    """Section 4: five aligned panels, every session part and the idle gaps between them."""
    parts = data["session_parts"].sort_values("session_part").reset_index(drop=True)
    fig, stats = fig_timeline(data["timeline"], parts)
    peak = int(stats["peak_agents"])
    walls = ", ".join(f"{h:.1f} h" for h in parts["wall_hours"])
    gaps = " and ".join(f"{h:.1f} h" for h in stats["gap_hours"])
    title = (
        f"{len(parts)} session parts of {walls} wall-clock, with idle gaps of {gaps} between them; "
        f"up to {peak} agents ran at once"
    )
    comp_note = ""
    for _, c in compactions.iterrows():
        when = pd.Timestamp(c["event_at_local"])
        add_compaction_marker(fig, when, stats, f"compaction {when:%H:%M}")
        comp_note += (
            f" Dotted amber line at {when:%H:%M}: a compaction (context cut from about "
            f"{fmt_tokens(float(c['context_tokens_before']))} to {fmt_tokens(float(c['context_tokens_after']))} tokens)."
        )
    block = figure_block(
        fig_id="fig-timeline",
        takeaway=title,
        subtitle="Parts share one y scale per panel; each idle gap is drawn as a narrow fixed-width block, not to scale. "
        "Tokens are known totals, mostly cache reads." + comp_note,
        fig=fig,
        source="mart_run_timeline, dim_session_part, fct_session_events",
        alt=(
            "Five aligned bar panels over 15-minute buckets: requests, tokens, active agents, Codex requests and human messages, "
            "for each session part with the idle gaps between them."
        ),
        min_width=900,
    )
    return (
        '<section id="timeline"><h2><span class="num">4</span>Run timeline</h2>'
        '<p class="lede">Activity in 15-minute buckets, local time (America/New_York, EDT). The loop ran overnight, '
        "went quiet for most of the day, was extended for 24 hours, paused, and resumed for tool expansion and v22.</p>"
        f"{block}</section>"
    )


def build_ab(data: dict[str, pd.DataFrame]) -> str:
    ab = data["ab"]
    sc = data["scorecard"]
    kept_despite = sc[(sc["ab_agrees_with_decision"] == False) & sc["is_promoted"]]["version_id"].tolist()  # noqa: E712
    y_labels, sec_labels, z, txt, comps = ab_matrix(ab)
    n_votes = sum(len(r) for r in z)
    n_tie = sum(sum(1 for v in r if v == 2) for r in z)
    n_newer = sum(sum(1 for v in r if v == 0) for r in z)
    n_older = sum(sum(1 for v in r if v == 1) for r in z)
    kd = " and ".join(kept_despite)
    title1 = (
        f"Of {n_newer + n_older} decisive section picks, {n_newer} favoured the newer version and {n_older} the older; "
        f"{kd} were kept despite losing their A/B 0-2"
    )
    sub1 = (
        "Each row is one blind comparison (side A or B was randomised per section). The cell shows which version the judge picked. "
        "Amber outlines mark the two keep decisions that disagree with the A/B tally; the override came after the picks were reviewed. "
        "* = marginal pick."
    )
    legend = (
        '<div class="legend" aria-hidden="false">'
        f'<span><i style="background:{AB_NEWER}"></i>newer version picked</span>'
        f'<span><i style="background:{AB_OLDER}"></i>older version picked</span>'
        f'<span><i style="background:{AB_TIE}"></i>tie</span>'
        f'<span><i style="background:transparent;border:2px solid {ACCENT}"></i>kept despite losing</span></div>'
    )
    fig1 = fig_ab_picks(ab, kept_despite)
    rates = [sum(1 for v in r if v == 2) / len(r) * 100 for r in z]
    title2 = (
        f"Judges tied on {n_tie} of {n_votes} section votes ({n_tie / n_votes * 100:.0f}%); per comparison the tie rate "
        f"ran from {min(rates):.0f}% to {max(rates):.0f}% (first {rates[0]:.0f}%, latest {rates[-1]:.0f}%)"
    )
    fig2 = fig_tie_rate(ab)
    tbl = pd.DataFrame(
        {
            "Comparison": y_labels,
            "Newer picked": [sum(1 for v in r if v == 0) for r in z],
            "Older picked": [sum(1 for v in r if v == 1) for r in z],
            "Tie": [sum(1 for v in r if v == 2) for r in z],
            "Tie rate": [f"{r:.0f}%" for r in rates],
        }
    )
    return (
        '<section id="ab"><h2><span class="num">5</span>Blind A/B</h2>'
        '<p class="lede">Before keeping a new version, a judge subagent watched it and the previous best in random order and '
        "picked a winner for each of seven sections, or called a tie. Every comparison ran once (no repeats).</p>"
        + figure_block(
            fig_id="fig-ab",
            takeaway=title1,
            subtitle=sub1,
            extra_above=legend,
            fig=fig1,
            source="fct_ab_votes, mart_version_scorecard (ab_agrees_with_decision)",
            alt="Grid of ten blind comparisons by seven sections showing which version the judge picked or a tie.",
            min_width=760,
            details=html_table(tbl, numeric_cols={"Newer picked", "Older picked", "Tie", "Tie rate"}),
        )
        + figure_block(
            fig_id="fig-tie",
            takeaway=title2,
            subtitle="Tie rate is a descriptive count, not a test: with one run per comparison and 7 sections each, single-comparison rates are noisy.",
            fig=fig2,
            source="fct_ab_votes",
            alt="Bar chart of the share of sections tied in each comparison.",
            min_width=640,
        )
        + "</section>"
    )


def build_audio(data: dict[str, pd.DataFrame]) -> str:
    sc = data["scorecard"]
    aud = sc[sc["lines_below_10db"].notna()].copy()
    first = aud.iloc[0]
    n_lines = data["dialogue"].groupby("version_id")["line_no"].count()
    # last unbroken run of zero lines below target, ending at the final audio version
    zero_run: list[str] = []
    for _, r in aud.iloc[::-1].iterrows():
        if int(r["lines_below_10db"]) == 0:
            zero_run.append(r["version_id"])
        else:
            break
    zero_run = zero_run[::-1]
    if zero_run:
        run_txt = f"{zero_run[0]} to {zero_run[-1]} have none" if len(zero_run) > 1 else f"{zero_run[0]} has none"
    else:
        run_txt = "the latest version still has some"
    title1 = (
        f"{int(first['lines_below_10db'])} of {n_lines[first['version_id']]} dialogue lines sat below the +10 dB "
        f"dialogue-over-bed target in {first['version_id']}; {run_txt}"
    )
    fig1 = fig_dialogue_strip(data["dialogue"], sc)
    with_ls = sc[sc["landing_vs_cold_open_lu"].notna()]
    a, b = with_ls.iloc[0], with_ls.iloc[-1]

    def rel(val: float) -> str:
        return f"{abs(val):.1f} LU {'louder' if val > 0 else 'quieter'} than"

    title2 = (
        f"The landing section went from {rel(float(a['landing_vs_cold_open_lu']))} the cold open in {a['version_id']} "
        f"to {rel(float(b['landing_vs_cold_open_lu']))} it by {b['version_id']}"
    )
    fig2 = fig_section_loudness(data["sections"])
    tbl = aud[["version_id", "lines_below_10db", "min_dialogue_to_bed_db", "mean_whisper_recall", "integrated_lufs", "loudness_range_lu", "true_peak_dbtp"]].copy()
    tbl.columns = ["Version", "Lines below +10 dB", "Min ratio (dB)", "Mean Whisper recall", "Integrated (LUFS)", "Loudness range (LU)", "True peak (dBTP)"]
    tbl["Lines below +10 dB"] = tbl["Lines below +10 dB"].astype(int)
    tbl["Mean Whisper recall"] = tbl["Mean Whisper recall"].map(lambda v: f"{v:.0%}")
    return (
        '<section id="audio"><h2><span class="num">6</span>Audio QC</h2>'
        '<p class="lede">An audio check measured, for each version, how far dialogue sits above the music and effects bed, '
        "and the loudness of each section. Audio QC files exist from v4 on. v5 and v6 measure identically, as do v11 and v12 "
        "(picture-only changes; the audio files themselves were not re-checked).</p>"
        + figure_block(
            fig_id="fig-dialogue",
            takeaway=title1,
            subtitle="One square per dialogue line. Orange is below the +10 dB target, blue above. Lines are placed by their position in each cut, "
            "so columns are not the same line across versions.",
            fig=fig1,
            source="fct_dialogue_lines, mart_version_scorecard (lines_below_10db)",
            alt="Strip chart with one square per dialogue line for each version, coloured by dialogue-to-bed ratio.",
            min_width=700,
            details=html_table(tbl, numeric_cols=set(tbl.columns) - {"Version"}),
        )
        + figure_block(
            fig_id="fig-loudness",
            takeaway=title2,
            subtitle="Integrated loudness per section in LUFS (higher is louder). Colour is clipped at -25 LUFS so the near-silent "
            "silence and credits sections do not wash out the rest; the printed values are exact.",
            fig=fig2,
            source="fct_version_audio, mart_version_scorecard (landing_vs_cold_open_lu)",
            alt="Heatmap of section loudness in LUFS by version.",
            min_width=640,
        )
        + "</section>"
    )


def build_quality(
    data: dict[str, pd.DataFrame],
    dbt: dict[str, Any] | None,
    recon: dict[str, Any] | None,
    ok_notes: list[str],
    warn_notes: list[str],
) -> str:
    parts: list[str] = ['<section id="quality"><h2><span class="num">7</span>Data quality</h2>']
    parts.append(
        '<p class="lede">The metric here is whether bad data gets caught before someone builds a decision on it. '
        "Raw files are checked on the way in, the warehouse is tested on the way through, and the known gaps are listed rather than hidden.</p>"
    )
    if dbt is not None:
        tests = dbt["tests"]
        n = len(tests)
        n_pass = int((tests["status"] == "pass").sum())
        other = dbt["other"]
        n_models = sum(other["model"].values())
        n_seeds = sum(other["seed"].values())
        ok_nodes = other["model"].get("success", 0) + other["seed"].get("success", 0)
        title = (
            f"{n_pass} of {n} dbt tests passed, and all {ok_nodes} of {n_models + n_seeds} models and seeds built "
            f"(dbt {dbt['dbt_version']}, {dbt['command']}, {dbt['elapsed']:.0f} s)"
        )
        fig = fig_dbt_tests(tests)
        parts.append(
            figure_block(
                fig_id="fig-dbt",
                takeaway=title,
                subtitle="Sources carry a primary-key test and a schema contract per CSV; facts and dimensions carry grain, relationship and "
                "enum tests; singular tests reconcile row counts and token sums across layers. Failures would be listed by status.",
                fig=fig,
                source="warehouse/target/run_results.json and manifest.json "
                f"(generated {dbt['generated_at'][:19].replace('T', ' ')} UTC)",
                alt="Two bar charts: dbt test counts by layer and by test type.",
                min_width=640,
            )
        )
    else:
        parts.append('<div class="note">target/run_results.json was not found, so dbt test counts are not shown.</div>')

    cards: list[str] = []
    if recon is not None:
        rc = recon["row_counts"]
        chips = "".join(f"<div><span>{esc(k)}</span><b>{v:,}</b></div>" for k, v in rc.items())
        run_at = esc(re.sub(r"T(\d\d:\d\d).*", r" \1 EDT", recon["run_at"]))
        naive, dedup = recon["naive"], recon["deduped"]
        infl_rows = []
        for key, label in (
            ("cache_read_tokens", "Cache read"),
            ("cache_creation_tokens", "Cache creation"),
            ("output_tokens", "Output"),
            ("input_tokens", "Input"),
        ):
            if key in naive and dedup.get(key):
                infl_rows.append(
                    {
                        "Tokens": label,
                        "Naive sum": fmt_tokens(naive[key]),
                        "Deduped": fmt_tokens(dedup[key]),
                        "Inflation": f"{naive[key] / dedup[key]:.1f}x",
                    }
                )
        infl = pd.DataFrame(infl_rows)
        status = "all checks passed" if recon["all_passed"] and recon["fails"] == 0 else f"{recon['fails']} checks FAILED"
        cards.append(
            '<div class="card"><h4>Ingest reconciliation</h4>'
            f'<p style="margin:0 0 8px"><span class="{"status-ok" if recon["fails"] == 0 else "status-warn"}">'
            f'{recon["passes"]} PASS, {recon["fails"]} FAIL</span> ({esc(status)}), run {run_at}. '
            "The parsers ran twice over the same snapshot and produced byte-identical output; token sums were recounted by separate code; "
            "every CSV was scanned for paths and e-mail addresses.</p>"
            f'<p style="margin:0 0 6px;color:var(--muted);font-size:0.85rem">Rows per raw table</p><div class="chips">{chips}</div></div>'
        )
        cards.append(
            '<div class="card"><h4>Why requests are deduplicated</h4>'
            "<p style=\"margin:0 0 8px\">One response is logged as several lines. Summing lines instead of unique message ids would have "
            "overstated tokens:</p>"
            f"{html_table(infl, numeric_cols={'Naive sum', 'Deduped', 'Inflation'})}</div>"
        )
    else:
        cards.append('<div class="card"><h4>Ingest reconciliation</h4><p>_reconciliation.txt was not found.</p></div>')

    summary = data["llm_summary"].iloc[0]
    no_final = int(summary["no_final_usage"])
    n_req = int(summary["requests"])
    last_req = pd.Timestamp(summary["last_request_local"])
    cost_txt = ""
    if recon is not None and recon["cost_state_output"]:
        cost_txt = (
            f" Against the client's own end-of-session-1 cost record, the table's output tokens are "
            f"{recon['table_output_at_cost_state'] / recon['cost_state_output'] * 100:.0f}% "
            f"({fmt_tokens(recon['table_output_at_cost_state'])} vs {fmt_tokens(recon['cost_state_output'])}); input and cache counts match for two of three models."
        )
    caveats = [
        f"<b>{no_final / n_req * 100:.0f}% of requests ({no_final} of {n_req:,}) lack a final output-token count.</b> "
        f"The main agent is almost complete; builders, researchers and the ingest agent are not, so subagent output totals are floors.{cost_txt}",
        "<b>No dollar prices.</b> The data has none for these model ids, so everything is in tokens. Haiku web-fetch summaries and the "
        "compaction call appear only in the client's cost record, not the transcripts.",
        "<b>Scores are model judgments from a single pass.</b> One editor critique per version and one A/B run per comparison; no repeats or human raters.",
        "<b>Keep decisions that disagree with the A/B tally are surfaced, not hidden.</b> v10 and v11 lost 0-2 and were kept after the picks were reviewed.",
        "<b>Identical audio QC for v5/v6 and v11/v12.</b> Plausible (picture-only changes) but not checked against the audio files. "
        "Section 3 is labelled 'act 2 stats/chart' to v7 and 'act 2 stats/ascent' from v8, so models key on the section number.",
        "<b>Technical-QC click detector is noisy</b> (thousands of candidates per version, every version reads FAIL), so it is not charted.",
    ]
    fresh_items = "".join(f'<li><span class="status-ok">OK</span> {esc(t)}</li>' for t in ok_notes)
    fresh_items += "".join(f'<li><span class="status-warn">STALE</span> {esc(t)}</li>' for t in warn_notes)
    fresh_items += (
        f"<li>Data runs through {last_req:%d %b %Y %H:%M} EDT. Session 2 was still running at the snapshot, "
        "so a later build will include more rows.</li>"
    )
    cards.append(
        '<div class="card"><h4>Freshness</h4><ul>' + fresh_items + "</ul></div>"
    )
    parts.append(f'<div class="grid2">{"".join(cards)}</div>')
    parts.append(
        '<div class="card" style="margin-top:16px"><h4>Known caveats</h4><ul>'
        + "".join(f"<li>{c}</li>" for c in caveats)
        + "</ul></div>"
    )
    parts.append("</section>")
    return "".join(parts)


def build_footer(build_time: str, recon: dict[str, Any] | None, data: dict[str, pd.DataFrame]) -> str:
    infl = ""
    if recon and recon["naive"].get("cache_read_tokens"):
        infl = f" (summing lines would have inflated cache reads {recon['naive']['cache_read_tokens'] / recon['deduped']['cache_read_tokens']:.1f}x)"
    db_built = datetime.fromtimestamp(DB_PATH.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"""
<footer><div class="wrap"><h2>Methods</h2><dl>
<dt>Grain</dt><dd>Claude requests: one row per provider message id. Agent runs: one per subagent. Versions: one per exported trailer
version (v1 to the latest; an in-progress version is left out of the charts). Critic scores: one per version x critic x category. Loop phases: one per ledger segment or gap between segments.
Blind A/B: one per judge pick for one section of one comparison. Audio: one per version x loudness section, and per version x dialogue line.
Timeline: one per 15-minute bucket.</dd>
<dt>Deduplication rule</dt><dd>Responses are logged as several JSONL lines; rows are deduplicated on the provider message id and cross-checked
against the request id{infl}. Output tokens are taken only from a response's closing usage line; where it is missing the value is NULL
(unknown), never zero, and the streamed placeholder is kept separately as a lower bound.</dd>
<dt>Active-time rule</dt><dd>Take every request start time from the main agent and all subagents together, sort them, and merge neighbours no more
than 5 minutes apart into one interval. Active time is the summed interval length. Parallel subagents count once and an isolated request adds zero.
Wall-clock is first to last event of a session part.</dd>
<dt>Tokens</dt><dd>Input (uncached), cache creation, cache read and output are kept as separate counts and never merged into each other. "Total known" adds the four.
Counts are API-equivalent, not billed, and carry no dollar prices.</dd>
<dt>Times</dt><dd>Local time is America/New_York (EDT). Timeline buckets are 15 minutes.</dd>
<dt>Stack</dt><dd>Raw CSVs, then dbt (DuckDB adapter) staging, intermediate, core and mart models, then this script
(<code>dashboard/build_dashboard.py</code>), which queries the warehouse read-only and writes this page and one local plotly.min.js. No network access is needed to view it.</dd>
<dt>Build</dt><dd>Page generated {esc(build_time)} from moonshot.duckdb (built {esc(db_built)} local time).</dd>
</dl></div></footer>"""


def build_nav() -> str:
    items = [
        ("headline", "Headline"),
        ("scores", "Scores"),
        ("plateau", "Plateau"),
        ("tokens", "Tokens"),
        ("timeline", "Timeline"),
        ("ab", "Blind A/B"),
        ("audio", "Audio QC"),
        ("quality", "Data quality"),
    ]
    links = "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in items)
    return f'<nav class="sections" aria-label="Sections"><div class="wrap"><ul>{links}</ul></div></nav>'


def render_page(body_sections: list[str], footer: str, title: str, *, n_versions: int, nav: bool = True) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title>"
        '<meta name="description" content="Static analytics dashboard for the MOONSHOT agent run, built from a dbt and DuckDB warehouse.">'
        f"<style>{CSS}</style>"
        '<script src="plotly.min.js"></script></head><body>'
        f'<header class="top"><div class="wrap"><h1>MOONSHOT run analytics: <span>one AI agent loop</span>, {n_versions} trailer versions</h1>'
        "<p>An analytics-engineering view of one autonomous Claude Code run that cut an Apollo 11 trailer: versions, scores, tokens, "
        "timing, blind A/B judging, audio QC and data quality. Modelled in dbt, stored in DuckDB, rendered offline.</p></div></header>"
        f"{build_nav() if nav else ''}"
        f'<main class="wrap">{"".join(body_sections)}</main>{footer}</body></html>\n'
    )


# ----------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------


def png_target() -> Path | None:
    """Where to write the plateau PNG: --plateau-png PATH, else <MOONSHOT_EXPORTS>/evidence/plateau_chart.png.

    MOONSHOT_EXPORTS comes from the shell or from the untracked analytics/.env, the same
    way the ingest finds it, so no personal path is written in this file.
    """
    if "--plateau-png" in sys.argv:
        return Path(sys.argv[sys.argv.index("--plateau-png") + 1])
    sys.path.insert(0, str(ANALYTICS / "ingest"))
    from common import load_dotenv

    load_dotenv()
    import os

    root = os.environ.get("MOONSHOT_EXPORTS", "").strip()
    return Path(root) / "evidence" / "plateau_chart.png" if root and Path(root).is_dir() else None


def main() -> int:
    if not DB_PATH.exists():
        print(f"error: {DB_PATH} not found; run dbt build first", file=sys.stderr)
        return 1
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        data = load_data(con)
    finally:
        con.close()

    ok_notes, warn_notes = freshness_notes(data)
    for w in warn_notes:
        print(f"warning: {w}")

    dbt = load_dbt_results()
    recon = parse_reconciliation()

    headline_html, headline = build_headline(data)
    scores_html = build_scores(data)
    plateau_html = build_plateau(data)
    tokens_html = build_tokens(data)

    timeline_html = build_timeline(data, data["compactions"])
    ab_html = build_ab(data)
    audio_html = build_audio(data)
    quality_html = build_quality(data, dbt, recon, ok_notes, warn_notes)

    build_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = render_page(
        [headline_html, scores_html, plateau_html, tokens_html, timeline_html, ab_html, audio_html, quality_html],
        build_footer(build_time, recon, data),
        "MOONSHOT run analytics dashboard",
        n_versions=len(data["plateau_versions"]),
    )

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(page, encoding="utf-8", newline="\n")
    (SITE_DIR / "plotly.min.js").write_text(get_plotlyjs(), encoding="utf-8", newline="\n")

    print(f"wrote {SITE_DIR / 'index.html'} ({(SITE_DIR / 'index.html').stat().st_size / 1024:.0f} KiB)")
    print(f"wrote {SITE_DIR / 'plotly.min.js'} ({(SITE_DIR / 'plotly.min.js').stat().st_size / 1024:.0f} KiB)")
    print(f"wrote {write_plateau_page(data, build_time)}")
    png = png_target()
    if png is not None:
        export_plateau_png(data, png)
    print("headline:", json.dumps(headline, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
