# Woodhull Time Series

Plots BAS/BMS trend-log CSV exports (the "Timestamp + one column per point"
format used by Woodhull's building automation system) as an interactive,
multi-panel HTML chart.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python3 scripts/plot_trends.py data/FCU-5-303_Trends_2026-08-25_2026-09-14.csv
```

This writes an HTML chart to `output/<csv-name>.html` — open it in a browser.
It groups points into one panel per unit (e.g. °F, %) so temperatures and
percentage outputs never share an axis, keeps a synced crosshair across
panels, and includes a range slider for zooming into a date window.

Options:

```bash
python3 scripts/plot_trends.py <csv_path> -o output/custom_name.html
python3 scripts/plot_trends.py <csv_path> --inline   # embed plotly.js for offline viewing
```

## Data format

The script expects a CSV shaped like the sample in `data/`: a `Timestamp`
column followed by one column per trended point, with the point's unit in
parentheses in the header (e.g. `FCU-5-303/DA-T (°F)`). Point names with no
unit suffix are grouped into a "Status" panel.
