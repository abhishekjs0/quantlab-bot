import math
from pathlib import Path

import pandas as pd
import pytest

from config import REPORTS_DIR


def _get_latest_report_dir():
    """Get the latest generated report directory."""
    dirs = [
        d for d in REPORTS_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]
    if not dirs:
        pytest.skip("No reports directory found")
    # Sort by modification time, get latest
    latest = max(dirs, key=lambda p: p.stat().st_mtime)
    return latest


def test_total_net_pnl_equals_portfolio_change():
    """Test that total net P&L equals portfolio equity change."""
    rdir = _get_latest_report_dir()

    # Try to find files for all available periods
    for period in ["5Y", "3Y", "1Y"]:
        metrics = pd.read_csv(rdir / f"portfolio_key_metrics_{period}.csv")
        pec = pd.read_csv(rdir / f"portfolio_daily_equity_curve_{period}.csv")

        if metrics.empty or pec.empty:
            continue

        total_row = metrics[metrics["Symbol"] == "TOTAL"]
        if total_row.empty:
            continue

        # Try different column names for net P&L
        net_pct_num = None
        for col in ["Net P&L % (num)", "Net P&L %"]:
            if col in total_row.columns:
                val = total_row[col].iloc[0]
                net_pct_num = float(str(val).replace("%", "").replace(",", ""))
                break

        if net_pct_num is None:
            continue

        eq = pec["Equity"].astype(float)
        start, end = float(eq.iloc[0]), float(eq.iloc[-1])
        computed = (end / start - 1.0) * 100.0

        # Allow a small tolerance
        assert (
            abs(net_pct_num - computed) < 0.5
        ), f"Period {period}: total {net_pct_num}% != computed {computed}%"

        # If we got here, test passed for this period
        return

    # If no periods found, skip test
    pytest.skip("No valid report periods found")


def test_profit_factor_closed_trades():
    """Test profit factor calculation from closed trades."""
    rdir = _get_latest_report_dir()

    # Try to find files for all available periods
    for period in ["5Y", "3Y", "1Y"]:
        trades_path = rdir / f"consolidated_trades_{period}.csv"
        metrics_path = rdir / f"portfolio_key_metrics_{period}.csv"

        if not trades_path.exists() or not metrics_path.exists():
            continue

        trades = pd.read_csv(trades_path)
        metrics = pd.read_csv(metrics_path)

        total_row = metrics[metrics["Symbol"] == "TOTAL"]
        if total_row.empty:
            continue

        # Get reported profit factor (may have different column names)
        pf_reported = None
        for col in [
            "Profit factor (num)",
            "Profit Factor (num)",
            "Profit Factor",
            "Profit factor",
        ]:
            if col in total_row.columns:
                val = total_row[col].iloc[0]
                if pd.notna(val) and val != "":
                    pf_reported = (
                        float(val)
                        if not isinstance(val, str)
                        else float(val.replace(",", ""))
                    )
                    break

        if pf_reported is None:
            continue

        # Only consider Exit rows (these contain Net P&L INR)
        exits = trades[trades["Type"].str.contains("Exit", na=False)].copy()
        if exits.empty:
            continue

        # Ensure numeric - handle string format with commas
        exits["Net P&L INR"] = (
            exits["Net P&L INR"].astype(str).str.replace(",", "").astype(float)
        )

        gross_win = float(exits[exits["Net P&L INR"] > 0]["Net P&L INR"].sum())
        gross_loss = float(-exits[exits["Net P&L INR"] < 0]["Net P&L INR"].sum())

        if gross_loss > 0:
            pf_calc = gross_win / gross_loss
        else:
            pf_calc = math.inf if gross_win > 0 else 0.0

        # Compare reported PF with computed one
        if math.isinf(pf_calc):
            # Either both should be inf or pf_reported should be very large
            assert (
                math.isinf(pf_reported) or pf_reported > 1000
            ), f"Period {period}: Expected inf or very large, got {pf_reported}"
        else:
            # Allow tolerance for rounding differences
            assert (
                abs(float(pf_reported) - pf_calc) < 0.05
            ), f"Period {period}: reported {pf_reported} != calculated {pf_calc}"

        # If we got here, test passed for this period
        return

    # If no periods found, skip test
    pytest.skip("No valid report periods found")
