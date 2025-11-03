"""Report generation and data persistence utilities."""

import json
import os
import time
from pathlib import Path

import pandas as pd

from config import REPORTS_DIR


def make_run_dir(base=None, strategy_name=None, basket_name=None):
    if base is None:
        base = REPORTS_DIR

    # Generate timestamp prefix as requested: MMDD-HHMM format
    timestamp_prefix = time.strftime("%m%d-%H%M")

    # Build descriptive directory name with timestamp prefix
    dir_parts = [timestamp_prefix]

    if strategy_name:
        # Clean strategy name for filesystem
        clean_strategy = strategy_name.replace("_", "-").lower()
        dir_parts.append(clean_strategy)

    if basket_name:
        # Clean basket name for filesystem
        clean_basket = basket_name.replace("_", "-").lower()
        if not clean_basket.endswith(".txt"):
            clean_basket = clean_basket.replace(".txt", "")
        dir_parts.append(clean_basket)

    # Create descriptive directory name: MMDD-HHMM-strategy-basket
    dir_name = "-".join(dir_parts)

    path = base / dir_name
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def save_trades(trades: pd.DataFrame, symbol: str, run_dir: str):
    p = os.path.join(run_dir, f"{symbol}_trades.csv")
    # round numeric columns to 2 decimals
    try:
        trades = trades.copy()
        for c in trades.select_dtypes(include=["number"]).columns:
            trades[c] = trades[c].round(2)
    except Exception:
        pass
    trades.to_csv(p, index=False)
    return p


def save_equity(equity: pd.DataFrame, symbol: str, run_dir: str):
    p = os.path.join(run_dir, f"{symbol}_equity.csv")
    try:
        e = equity.copy()
        for c in e.select_dtypes(include=["number"]).columns:
            e[c] = e[c].round(2)
        e.to_csv(p)
    except Exception:
        equity.to_csv(p)
    return p


def save_leaderboard(df: pd.DataFrame, run_dir: str, name="leaderboard.csv"):
    p = os.path.join(run_dir, name)
    try:
        d = df.copy()
        for c in d.select_dtypes(include=["number"]).columns:
            d[c] = d[c].round(2)
        d.to_csv(p, index=False)
    except Exception:
        df.to_csv(p, index=False)
    return p


def save_summary(run_dir: str, meta: dict):
    p = os.path.join(run_dir, "summary.json")
    with open(p, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    return p


def auto_generate_dashboard(
    run_dir: str,
    data: dict,
    strategy_name: str = "Strategy",
    basket_name: str = "Portfolio",
):
    """Automatically generate dashboard for backtest reports.

    Args:
        run_dir: Report directory path
        data: Dictionary with time period keys (e.g., '1Y', '3Y', '5Y') containing:
            - equity_curve: Portfolio equity DataFrame
            - trades: Consolidated trades DataFrame
            - monthly_equity: Monthly equity breakdown (optional)
        strategy_name: Name of the strategy for dashboard title
        basket_name: Name of the basket for dashboard title

    Returns:
        Path to generated dashboard HTML file or None if failed
    """
    try:
        from viz.dashboard import QuantLabDashboard

        print(f"📊 Auto-generating dashboard for {strategy_name} - {basket_name}...")

        # Create dashboard instance
        dashboard = QuantLabDashboard(Path(run_dir))

        # Load data and generate dashboard
        report_folder = Path(run_dir).name
        data = dashboard.load_comprehensive_data(report_folder)
        dashboard_path = dashboard.save_dashboard(
            data=data,
            output_name="portfolio_dashboard"
        )

        print(f"✅ Dashboard auto-generated: {dashboard_path}")
        print(f"🌐 Open in browser: file://{dashboard_path}")

        return dashboard_path

    except Exception as e:
        import traceback

        print(f"⚠️ Dashboard auto-generation failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None
