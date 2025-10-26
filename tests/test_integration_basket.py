import os
import sys

import pandas as pd

# ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import REPORTS_DIR
from runners import run_basket as rb


def _run_quick_basket_and_return_paths():
    # Run run_basket for a single window (1Y) using cache-only to be fast
    rb.run_basket(
        "data/basket.txt",
        "ichimoku",
        "{}",
        "1d",
        "1y",
        windows_years=(1,),
        use_cache_only=True,
        use_portfolio_csv=True,
    )
    # find latest reports dir
    rep = sorted(REPORTS_DIR.iterdir(), key=lambda p: p.stat().st_mtime)[-1]
    return rep


def test_basket_total_parity():
    rep = _run_quick_basket_and_return_paths()
    basket_csv = rep / "basket_1Y.csv"
    port_csv = rep / "portfolio_equity_curve_1Y.csv"
    assert basket_csv.exists() and port_csv.exists()

    bdf = pd.read_csv(basket_csv)
    pdf = pd.read_csv(port_csv, comment="#")

    # parse portfolio percent (first and last equity)
    if "Equity" in pdf.columns and len(pdf) >= 2:
        start = float(pdf["Equity"].iloc[0])
        end = float(pdf["Equity"].iloc[-1])
        port_pct = round((end / start - 1.0) * 100.0, 2)
    else:
        port_pct = 0.0

    # parse basket TOTAL Net P&L % (strip % and convert)
    tot = bdf.loc[bdf["Symbol"] == "TOTAL", "Net P&L %"].iloc[0]
    if isinstance(tot, str) and tot.endswith("%"):
        tot_val = float(tot.strip("%"))
    else:
        tot_val = float(tot)

    assert abs(tot_val - port_pct) < 1e-6


def test_per_symbol_net_pnl_matches_trades_sum():
    rep = _run_quick_basket_and_return_paths()
    basket_csv = rep / "basket_1Y.csv"
    trades_csv = rep / "consolidated_trades_1Y.csv"
    assert basket_csv.exists() and trades_csv.exists()

    bdf = pd.read_csv(basket_csv)
    tdf = pd.read_csv(trades_csv)

    # For each symbol compute Net P&L % from consolidated trades: sum(net_pnl) / sum(deployed_notional) * 100
    for _, row in bdf.iterrows():
        sym = row["Symbol"]
        if sym == "TOTAL":
            continue
        # filter trades for symbol and exit rows (Exit long)
        sym_trades = tdf[(tdf["Symbol"] == sym) & (tdf["Type"].str.contains("Exit"))]
        if sym_trades.empty:
            continue
        # net pnl in INR
        net_sum = sym_trades["Net P&L INR"].replace("", 0).astype(float).sum()
        # approximate deployed: take Position size (value) at entry rows (Position size (value) where Type == 'Entry long')
        entry_rows = tdf[(tdf["Symbol"] == sym) & (tdf["Type"].str.contains("Entry"))]
        if not entry_rows.empty:
            deployed_sum = (
                entry_rows["Position size (value)"].replace("", 0).astype(float).sum()
            )
        else:
            deployed_sum = 0.0
        if deployed_sum == 0:
            continue
        computed_pct = (net_sum / deployed_sum) * 100.0

        # parse reported Net P&L % from basket (strip %)
        rep_val = row["Net P&L %"]
        if isinstance(rep_val, str) and rep_val.endswith("%"):
            rep_val = float(rep_val.strip("%"))
        else:
            rep_val = float(rep_val)

        # compare within reasonable tolerance
        assert abs(rep_val - computed_pct) < 1.0
