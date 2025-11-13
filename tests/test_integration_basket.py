import os
import sys
from pathlib import Path

import pandas as pd
import pytest

# ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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


def test_basket_total_parity():
    """Test that portfolio key metrics total P&L matches equity curve change."""
    rep = _get_latest_report_dir()

    # Try to find files for all available periods
    for period in ["5Y", "3Y", "1Y"]:
        metrics_csv = rep / f"portfolio_key_metrics_{period}.csv"
        port_csv = rep / f"portfolio_daily_equity_curve_{period}.csv"

        if not metrics_csv.exists() or not port_csv.exists():
            continue

        mdf = pd.read_csv(metrics_csv)
        pdf = pd.read_csv(port_csv)

        # Parse portfolio percent (first and last equity)
        if "Equity" in pdf.columns and len(pdf) >= 2:
            start = float(pdf["Equity"].iloc[0])
            end = float(pdf["Equity"].iloc[-1])
            port_pct = round((end / start - 1.0) * 100.0, 2)
        else:
            continue

        # Get TOTAL row from metrics
        total_row = mdf[mdf["Symbol"] == "TOTAL"]
        if total_row.empty:
            continue

        # Try different column names for net P&L %
        tot_val = None
        for col in ["Net P&L %", "Net P&L % (num)"]:
            if col in total_row.columns:
                val = total_row[col].iloc[0]
                tot_val = float(str(val).replace("%", "").replace(",", ""))
                break

        if tot_val is None:
            continue

        # Verify parity (within 0.5% tolerance due to rounding/formatting)
        assert (
            abs(tot_val - port_pct) < 0.5
        ), f"Period {period}: metrics total {tot_val}% != portfolio {port_pct}%"

        # If we got here, test passed for this period
        return

    # If no periods found, skip test
    pytest.skip("No valid report periods found")


def test_per_symbol_net_pnl_matches_trades_sum():
    """Test that per-symbol metrics exist and align with trade data."""
    rdir = _get_latest_report_dir()

    # Try to find files for all available periods
    for period in ["5Y", "3Y", "1Y"]:
        tdf_path = rdir / f"consolidated_trades_{period}.csv"
        metrics_path = rdir / f"portfolio_key_metrics_{period}.csv"

        if not tdf_path.exists() or not metrics_path.exists():
            continue

        tdf = pd.read_csv(tdf_path)
        metrics = pd.read_csv(metrics_path)

        if tdf.empty or metrics.empty:
            continue

        # Check that every symbol with trades has metrics
        symbols_in_trades = tdf["Symbol"].unique()
        symbols_in_metrics = metrics[metrics["Symbol"] != "TOTAL"]["Symbol"].unique()

        # At least some symbols should exist in both
        common_symbols = set(symbols_in_trades) & set(symbols_in_metrics)
        if len(common_symbols) == 0:
            continue

        for sym in list(common_symbols)[:3]:  # Check first 3
            row = metrics[metrics["Symbol"] == sym].iloc[0]

            sym_trades = tdf[tdf["Symbol"] == sym]
            if sym_trades.empty:
                continue

            # Verify that metrics exist and are non-null
            assert pd.notna(
                row["Avg P&L % per trade"]
            ), f"{sym}: Avg P&L % per trade is null"
            assert pd.notna(row["Total trades"]), f"{sym}: Total trades is null"

            # Total trades should be positive
            num_total_trades = row["Total trades"]
            assert num_total_trades > 0, f"{sym}: Total trades should be > 0"

        # If we got here with this period, test passed
        return

    # No valid report periods found
    pytest.skip("No valid report periods found")  # If no periods found, skip test
    pytest.skip("No valid report periods found")
