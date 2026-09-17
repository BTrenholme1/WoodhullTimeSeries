#!/usr/bin/env python3
"""Plot BMS/BAS trend-log CSVs (Timestamp + point columns) as an interactive HTML chart.

Usage:
    python3 scripts/plot_trends.py data/FCU-5-303_Trends_2026-08-25_2026-09-14.csv
    python3 scripts/plot_trends.py path/to/other_trend.csv -o output/other.html
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Validated categorical palette (light mode) -- see dataviz skill references/palette.md
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"

UNIT_RE = re.compile(r"\(([^)]+)\)\s*$")
MAX_SERIES_PER_PANEL = 6


def load_trend_csv(path: Path) -> pd.DataFrame:
    """Read a BAS trend export. These files are commonly Windows-1252 encoded
    because point names embed a degree sign (e.g. '(°F)')."""
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="cp1252")

    ts_col = df.columns[0]
    # Strip trailing timezone abbreviations (EDT/EST/...) -- dateutil doesn't
    # resolve US abbreviations unambiguously, and these exports are always a
    # single local timezone, so we parse as naive local time.
    ts_stripped = df[ts_col].astype(str).str.replace(r"\s+[A-Z]{2,5}$", "", regex=True)
    df[ts_col] = pd.to_datetime(ts_stripped, format="mixed")
    df = df.rename(columns={ts_col: "timestamp"}).sort_values("timestamp")
    return df


def strip_unit(col: str) -> str:
    """'FCU-5-303/DA-T (°F)' -> 'FCU-5-303/DA-T'; strip the unit BEFORE
    splitting on a delimiter, since the unit itself can contain one
    (e.g. 'AC-5-33_RA-P (in/wc)')."""
    return UNIT_RE.sub("", col).strip()


def split_point(col: str) -> tuple[str, str]:
    """Split a column into (equipment_prefix, point_id), trying the '/' and
    '_' delimiters BAS exports commonly use between equipment tag and point."""
    name = strip_unit(col)
    for delim in ("/", "_"):
        if delim in name:
            prefix, point = name.split(delim, 1)
            return prefix, point
    return "", name


def point_label(col: str) -> str:
    """'FCU-5-303/DA-T (°F)' -> 'DA-T'"""
    return split_point(col)[1]


def point_unit(col: str) -> str:
    match = UNIT_RE.search(col)
    return match.group(1) if match else "status"


def group_columns_by_unit(columns) -> dict:
    groups: dict[str, list[str]] = {}
    for col in columns:
        groups.setdefault(point_unit(col), []).append(col)
    return groups


def chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def build_figure(df: pd.DataFrame, title: str) -> go.Figure:
    value_cols = [c for c in df.columns if c != "timestamp"]
    groups = group_columns_by_unit(value_cols)
    # Stable, readable panel order: temperature, then percent outputs, then anything else.
    units = sorted(groups, key=lambda u: (u != "°F", u != "%", u))

    # A palette has 8 slots and a shared line chart gets unreadable well before
    # that -- split any unit's columns into multiple panels rather than
    # cycling (repeating) colors within one panel.
    panels: list[tuple[str, list[str]]] = []
    for unit in units:
        parts = chunk(groups[unit], MAX_SERIES_PER_PANEL)
        for i, part in enumerate(parts):
            label = unit if unit != "status" else "Status"
            if len(parts) > 1:
                label = f"{label} ({i + 1}/{len(parts)})"
            panels.append((label, part))

    row_heights = [0.6 if unit == "Status" else 1.0 for unit, _ in panels]

    fig = make_subplots(
        rows=len(panels),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        subplot_titles=[label for label, _ in panels],
        row_heights=row_heights,
    )

    for row, (panel_label, cols) in enumerate(panels, start=1):
        for i, col in enumerate(cols):
            color = CATEGORICAL[i % len(CATEGORICAL)]
            label = point_label(col)
            fig.add_trace(
                go.Scatter(
                    x=df["timestamp"],
                    y=df[col],
                    name=label,
                    legendgroup=f"row{row}",
                    legend=f"legend{row}",
                    mode="lines",
                    line=dict(color=color, width=2, dash="dash" if "SP" in label else "solid"),
                    hovertemplate=f"{label}: %{{y}}<extra></extra>",
                ),
                row=row,
                col=1,
            )
        fig.update_yaxes(
            title_text=panel_label if panel_label != "Status" else "",
            gridcolor=GRIDLINE,
            zerolinecolor=BASELINE,
            linecolor=BASELINE,
            tickfont=dict(color=INK_MUTED),
            row=row,
            col=1,
        )

    fig.update_xaxes(
        gridcolor=GRIDLINE,
        linecolor=BASELINE,
        tickfont=dict(color=INK_MUTED),
    )
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.05), row=len(panels), col=1)

    total_weight = sum(row_heights)
    cumulative = 0.0
    legends = {}
    for row, weight in enumerate(row_heights, start=1):
        top = 1 - cumulative / total_weight
        legends[f"legend{row}"] = dict(
            y=top - 0.02,
            yanchor="top",
            x=1.02,
            xanchor="left",
            bgcolor="rgba(0,0,0,0)",
        )
        cumulative += weight

    fig.update_layout(
        title=dict(text=title, font=dict(color=INK_PRIMARY, size=18)),
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK_SECONDARY),
        hovermode="x unified",
        height=int(280 * total_weight + 120),
        margin=dict(t=90, r=170, b=40, l=60),
        **legends,
    )
    for i, ann in enumerate(fig.layout.annotations):
        ann.font = dict(color=INK_PRIMARY, size=13)
        ann.x = 0
        ann.xanchor = "left"

    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to a trend-log CSV export")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Output HTML path")
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Embed plotly.js in the HTML instead of loading it from a CDN "
        "(bigger file, but works with no internet connection when opened)",
    )
    args = parser.parse_args()

    df = load_trend_csv(args.csv_path)
    point_prefix = next(
        (split_point(c)[0] for c in df.columns if c != "timestamp" and split_point(c)[0]),
        args.csv_path.stem,
    )
    start = df["timestamp"].min().strftime("%d %b %Y")
    end = df["timestamp"].max().strftime("%d %b %Y")
    title = f"{point_prefix} Trends — {start} to {end}"

    fig = build_figure(df, title)

    out_path = args.output or Path("output") / (args.csv_path.stem + ".html")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(out_path, include_plotlyjs=True if args.inline else "cdn")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    sys.exit(main())
