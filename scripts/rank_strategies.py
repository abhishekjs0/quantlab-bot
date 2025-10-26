"""
Rank strategies by ALL-window Net P&L % and CAGR.
Writes reports/strategy_rankings.csv and prints top candidates.
"""

import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
REPORTS_DIR = os.path.join(ROOT, "reports")
SUMMARY_CSV = os.path.join(REPORTS_DIR, "basket_totals_summary.csv")
OUT_RANK = os.path.join(REPORTS_DIR, "strategy_rankings.csv")

if not os.path.exists(SUMMARY_CSV):
    print("summary csv missing")
    raise SystemExit(1)

df = pd.read_csv(SUMMARY_CSV)
# load mapping run_dir -> strategy from summary.json inside each run dir
run_dirs = sorted(set(df["run_dir"]))
run_to_strategy = {}
for rd in run_dirs:
    summary_path = os.path.join(ROOT, rd, "summary.json")
    strategy = None
    try:
        with open(summary_path) as fh:
            meta = json.load(fh)
            strategy = meta.get("strategy")
    except Exception:
        strategy = None
    run_to_strategy[rd] = strategy or "unknown"

# focus on ALL window and non-zero Net P&L rows
df_all = df[df["window"] == "ALL"].copy()
# convert Net P&L % to numeric
df_all["Net P&L %"] = pd.to_numeric(df_all["Net P&L %"], errors="coerce").fillna(0.0)
# attach strategy
df_all["strategy"] = df_all["run_dir"].map(run_to_strategy)

# remove zero rows (where Net P&L % == 0 and Total trades==0 may be empty runs)
df_nonzero = df_all[
    (df_all["Net P&L %"] != 0.0)
    & (pd.to_numeric(df_all.get("Total trades", 0)).fillna(0) > 0)
]

if df_nonzero.empty:
    print("No non-empty ALL-window runs to rank")
    df_all.to_csv(OUT_RANK, index=False)
    raise SystemExit(0)

# ranking by Net P&L % desc, tiebreaker CAGR desc
for col in ["CAGR", "Avg P&L % per trade"]:
    if col in df_nonzero.columns:
        df_nonzero[col] = pd.to_numeric(df_nonzero[col], errors="coerce").fillna(0.0)

ranked = df_nonzero.sort_values(by=["Net P&L %", "CAGR"], ascending=[False, False])
ranked = ranked[
    [
        "strategy",
        "run_dir",
        "basket_csv",
        "Net P&L %",
        "CAGR",
        "Total trades",
        "Profitable trades %",
        "Profit factor",
    ]
]
ranked.to_csv(OUT_RANK, index=False)
print("Wrote rankings to", OUT_RANK)
print("Top candidates:")
print(ranked.head(10).to_string(index=False))
