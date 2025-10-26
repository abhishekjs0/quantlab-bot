import math
from pathlib import Path

import pandas as pd

from config import REPORTS_DIR


def _latest_reports_dir() -> Path:
    dirs = [d for d in REPORTS_DIR.iterdir() if d.is_dir()]
    if not dirs:
        raise RuntimeError("No reports directory found")
    # sort by name (timestamp-like) and pick last
    dirs_sorted = sorted(dirs)
    return dirs_sorted[-1]


def test_total_net_pnl_equals_portfolio_change():
    rdir = _latest_reports_dir()
    basket = pd.read_csv(rdir / "basket_1Y.csv")
    pec = pd.read_csv(rdir / "portfolio_equity_curve_1Y.csv")

    total_row = basket[basket["Symbol"] == "TOTAL"].iloc[0]
    net_pct_num = float(total_row.get("Net P&L % (num)", 0.0))

    eq = pec["Equity"].astype(float)
    start, end = float(eq.iloc[0]), float(eq.iloc[-1])
    computed = (end / start - 1.0) * 100.0

    # allow a tiny tolerance
    assert abs(net_pct_num - computed) < 1e-9


def test_profit_factor_closed_trades():
    rdir = _latest_reports_dir()
    trades = pd.read_csv(rdir / "consolidated_trades_1Y.csv")
    basket = pd.read_csv(rdir / "basket_1Y.csv")
    total_row = basket[basket["Symbol"] == "TOTAL"].iloc[0]
    pf_reported = total_row.get("Profit factor (num)")

    # Only consider Exit rows (these contain Net P&L INR)
    exits = trades[trades["Type"] == "Exit long"].copy()
    # ensure numeric
    exits["Net P&L INR"] = pd.to_numeric(exits["Net P&L INR"], errors="coerce")
    closed = exits[exits["Net P&L INR"].notna()]

    gross_win = float(closed[closed["Net P&L INR"] > 0]["Net P&L INR"].sum())
    gross_loss = float(-closed[closed["Net P&L INR"] < 0]["Net P&L INR"].sum())

    if gross_loss > 0:
        pf_calc = gross_win / gross_loss
    else:
        pf_calc = math.inf if gross_win > 0 else 0.0

    # Compare reported numeric PF with computed one. If either is NaN, fail.
    if pf_reported is None or (
        isinstance(pf_reported, float) and math.isnan(pf_reported)
    ):
        raise AssertionError("Reported Profit factor (num) missing in basket CSV")

    if math.isinf(pf_calc):
        assert str(pf_reported).lower() in ("inf", "infinity") or math.isinf(
            float(pf_reported)
        )
    else:
        # allow a small numeric tolerance due to rounding differences when
        # exporting/rounding trade P&L values in CSVs
        assert abs(float(pf_reported) - pf_calc) < 1e-4
