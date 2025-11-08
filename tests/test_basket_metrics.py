import os
import sys

import pandas as pd

# Ensure project root is on sys.path for imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.metrics import compute_portfolio_trade_metrics
from runners.run_basket import _format_and_enforce_totals


def test_format_and_enforce_totals_parity(tmp_path):
    # create a simple out_df with TOTAL and one symbol
    out_df = pd.DataFrame(
        [
            {
                "Window": "1Y",
                "Symbol": "TOTAL",
                "Net P&L %": 10.0,
                "Max equity drawdown": 2.0,
                "Total trades": 5,
            },
            {
                "Window": "1Y",
                "Symbol": "AAA",
                "Net P&L %": 3.0,
                "Max equity drawdown": 1.0,
                "Total trades": 2,
            },
        ]
    )

    formatted = _format_and_enforce_totals(out_df.copy(), 12.3456)
    # TOTAL should be forced to 12.35% (rounded) and include '%' suffix
    total_row = formatted.loc[formatted["Symbol"] == "TOTAL"].iloc[0]
    assert total_row["Net P&L %"] == "12.35%"
    assert total_row["Max equity drawdown"] == "2.00%"


def test_percent_suffix_and_other_numeric_formatting():
    out_df = pd.DataFrame(
        [
            {
                "Window": "1Y",
                "Symbol": "TOTAL",
                "Net P&L %": 1.23456,
                "Max equity drawdown": 0.3,
                "Total trades": 42,
            },
        ]
    )
    formatted = _format_and_enforce_totals(out_df.copy(), 1.23456)
    r = formatted.iloc[0]
    assert r["Net P&L %"].endswith("%")
    assert r["Max equity drawdown"].endswith("%")
    assert r["Total trades"] == "42"


def test_compute_portfolio_trade_metrics_includes_open_trades():
    # Construct fake df and trades for a single symbol with one open trade
    dates = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame({"close": [100.0, 110.0, 120.0]}, index=dates)
    trades = pd.DataFrame(
        [
            {
                "entry_time": dates[0],
                "exit_time": pd.NaT,
                "entry_price": 100.0,
                "entry_qty": 1,
                "net_pnl": pd.NA,
            }
        ]
    )
    res = compute_portfolio_trade_metrics(
        {"SYM": df}, {"SYM": trades}, bars_per_year=252
    )
    # Since the open trade MTM = (last_price - entry_price) * qty = 20, deployed capital = 100
    # AvgProfitPerTradePct should be approx 20/100 * 100 = 20.0
    assert abs(res["AvgProfitPerTradePct"] - 20.0) < 1e-6
