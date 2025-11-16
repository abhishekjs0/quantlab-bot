#!/usr/bin/env python3
"""
fast_run_basket.py - Ultra-fast basket backtest runner with multi-window analysis
Creates BACKTEST_METRICS.csv with TOTAL rows for each window: 1Y, 3Y, 5Y, MAX
Returns portfolio-level metrics only (TOTAL rows), no per-symbol rows
Much faster than run_basket.py for quick strategy testing
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from multiprocessing import cpu_count, get_context

import numpy as np
import pandas as pd

from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.metrics import compute_portfolio_trade_metrics, compute_trade_metrics_table
from core.monitoring import optimize_window_processing
from core.registry import make_strategy
from data.loaders import load_many_india

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bars per year for each timeframe
BARS_PER_YEAR_MAP: dict[str, int] = {
    "1d": 245,
    "125m": 735,
    "75m": 1225,
}

# Window labels for output
WINDOW_LABELS = {1: "1Y", 3: "3Y", 5: "5Y", None: "MAX"}


def _process_symbol_for_backtest(args: tuple) -> dict:
    """Module-level function for multiprocessing - processes a single symbol."""
    symbol, df_full, strategy_name, cfg = args

    try:
        strat = make_strategy(strategy_name)
        engine = BacktestEngine(df_full, strat, cfg, symbol=symbol)
        trades_full, equity_full, _ = engine.run()

        return (
            symbol,
            {
                "trades": trades_full,
                "equity": equity_full,
                "data": df_full,
            },
            None,
        )
    except Exception as e:
        return (symbol, None, f"Error: {str(e)[:50]}")


def _build_portfolio_curve(trades_by_symbol: dict, dfs_by_symbol: dict, initial_capital: float) -> pd.DataFrame:
    """Build a daily portfolio curve starting at initial_capital and tracking cumulative realized+unrealized.

    Key principles:
      1. Start at initial_capital on day 0 with zero exposure/returns.
      2. Equity = initial_capital + (sum of closed trade P&L + sum of open trade MTM).
      3. Drawdown = max(0, prev_day_equity - current_equity) — daily drop only.
      4. max_drawdown_inr/pct = running maximum of daily drawdowns.
      5. Last row should match the final equity position, reflecting only settled trades/MTM.

    Output columns: equity, avg_exposure, avg_exposure_pct, realized_inr, realized_pct,
    unrealized_inr, unrealized_pct, total_return_inr, total_return_pct,
    drawdown_inr, drawdown_pct, max_drawdown_inr, max_drawdown_pct.
    """
    # Collect all trading dates from price data
    all_dates = set()
    for df in dfs_by_symbol.values():
        try:
            idx = pd.to_datetime(df.index)
            all_dates.update(idx)
        except Exception:
            continue

    if not all_dates:
        return pd.DataFrame(
            columns=[
                "equity",
                "avg_exposure",
                "avg_exposure_pct",
                "realized_inr",
                "realized_pct",
                "unrealized_inr",
                "unrealized_pct",
                "total_return_inr",
                "total_return_pct",
                "drawdown_inr",
                "drawdown_pct",
                "max_drawdown_inr",
                "max_drawdown_pct",
            ]
        )

    dates = sorted(all_dates)

    # Pre-compute trade events: for each symbol, collect entry/exit times and final P&L
    # Vectorized approach - much faster than nested iterrows()
    trade_events = (
        []
    )  # list of (date, sym, "ENTRY"/"EXIT", price, qty, pnl_if_exit)

    for sym, trades in trades_by_symbol.items():
        if trades is None or trades.empty:
            continue

        try:
            # Vectorized operations - process all trades at once
            trades_clean = trades.copy()
            trades_clean["entry_time"] = pd.to_datetime(
                trades_clean["entry_time"], errors="coerce"
            )
            trades_clean["entry_price"] = pd.to_numeric(
                trades_clean["entry_price"], errors="coerce"
            ).fillna(0.0)
            trades_clean["entry_qty"] = pd.to_numeric(
                trades_clean["entry_qty"], errors="coerce"
            ).fillna(0.0)
            trades_clean["net_pnl"] = pd.to_numeric(
                trades_clean["net_pnl"], errors="coerce"
            ).fillna(0.0)

            # Create entry events (vectorized)
            entry_events = list(
                zip(
                    trades_clean["entry_time"],
                    [sym] * len(trades_clean),
                    ["ENTRY"] * len(trades_clean),
                    trades_clean["entry_price"],
                    trades_clean["entry_qty"],
                    [0.0] * len(trades_clean),
                    [None] * len(trades_clean),
                )
            )
            trade_events.extend(entry_events)

            # Create exit events (only for valid exits)
            has_exit = trades_clean["exit_time"].notna()
            if has_exit.any():
                trades_with_exits = trades_clean[has_exit].copy()
                trades_with_exits["exit_time"] = pd.to_datetime(
                    trades_with_exits["exit_time"], errors="coerce"
                )

                exit_events = list(
                    zip(
                        trades_with_exits["exit_time"],
                        [sym] * len(trades_with_exits),
                        ["EXIT"] * len(trades_with_exits),
                        trades_with_exits["entry_price"],
                        trades_with_exits["entry_qty"],
                        trades_with_exits["net_pnl"],
                        [None] * len(trades_with_exits),
                    )
                )
                trade_events.extend(exit_events)

        except Exception:
            continue

    # For each date, compute: which trades are open, which are closed, and their values
    rows = []
    running_peak = float(
        initial_capital
    )  # Track running maximum equity for proper drawdown
    max_dd_inr = 0.0
    max_dd_pct = 0.0
    prev_equity = float(
        initial_capital
    )  # Track previous day's equity for period returns

    # Pre-calculate cumulative realized P&L timeline to avoid double-counting
    # For each date, calculate the cumulative P&L from all trades closed by that date
    realized_pnl_by_date = {}
    realized_entry_amounts_by_date = (
        {}
    )  # Track actual entry amounts for % calculation
    for sym, trades in trades_by_symbol.items():
        if trades is None or trades.empty:
            continue
        # Vectorized approach for realized P&L calculation
        trades_copy = trades.copy()
        trades_copy["exit_time"] = pd.to_datetime(
            trades_copy["exit_time"], errors="coerce"
        )
        trades_copy["net_pnl"] = pd.to_numeric(
            trades_copy["net_pnl"], errors="coerce"
        ).fillna(0.0)

        # Filter trades with valid exit times
        exited_trades = trades_copy[trades_copy["exit_time"].notna()]

        if not exited_trades.empty:
            # Calculate entry amounts (entry_price * quantity) for realized P&L %
            # Use the correct column names
            qty_col = (
                "Position size (qty)"
                if "Position size (qty)" in exited_trades.columns
                else "entry_qty"
            )
            price_col = (
                "entry_price"
                if "entry_price" in exited_trades.columns
                else "Price INR"
            )
            exited_trades = (
                exited_trades.copy()
            )  # Create explicit copy to avoid warning
            exited_trades.loc[:, "entry_amount"] = pd.to_numeric(
                exited_trades[price_col], errors="coerce"
            ).fillna(0.0) * pd.to_numeric(
                exited_trades[qty_col], errors="coerce"
            ).fillna(
                0.0
            )

            # Group by exit date and sum P&L and entry amounts
            pnl_by_date = exited_trades.groupby("exit_time")["net_pnl"].sum()
            amounts_by_date = exited_trades.groupby("exit_time")[
                "entry_amount"
            ].sum()

            for exit_dt, net_pnl in pnl_by_date.items():
                if exit_dt not in realized_pnl_by_date:
                    realized_pnl_by_date[exit_dt] = 0.0
                realized_pnl_by_date[exit_dt] += net_pnl

            for exit_dt, entry_amount in amounts_by_date.items():
                if exit_dt not in realized_entry_amounts_by_date:
                    realized_entry_amounts_by_date[exit_dt] = 0.0
                realized_entry_amounts_by_date[exit_dt] += entry_amount

    # Build cumulative realized P&L for each date
    realized_cum_total = 0.0
    prev_unrealized = 0.0

    for dt in dates:
        # Add any realized P&L that occurred on this date
        dt_obj = pd.to_datetime(dt)
        daily_realized = 0.0
        if dt_obj in realized_pnl_by_date:
            daily_realized = realized_pnl_by_date[dt_obj]
            realized_cum_total += daily_realized

        # Calculate daily unrealized P&L from open trades
        unrealized = 0.0
        exposure = 0.0

        for sym, trades in trades_by_symbol.items():
            if trades is None or trades.empty:
                continue
            df = dfs_by_symbol.get(sym)
            if df is None or df.empty:
                continue

            # Get price at or before this date
            try:
                dt_ts = pd.Timestamp(dt)
                df_idx = pd.to_datetime(df.index, errors="coerce")
                mask = df_idx <= dt_ts
                sel = df.loc[mask]
                if sel.empty:
                    continue
                price_at_dt = float(sel["close"].iloc[-1])
            except Exception:
                price_at_dt = None

            # Vectorized approach instead of iterrows() for better performance
            if not trades.empty:
                dt_obj = pd.to_datetime(dt)
                trades_copy = trades.copy()

                # Check if required columns exist
                required_cols = [
                    "entry_time",
                    "exit_time",
                    "entry_price",
                    "entry_qty",
                ]
                missing_cols = [
                    col
                    for col in required_cols
                    if col not in trades_copy.columns
                ]

                if missing_cols:
                    continue

                # Convert times to datetime with error handling
                try:
                    trades_copy["entry_time"] = pd.to_datetime(
                        trades_copy["entry_time"], errors="coerce"
                    )
                    trades_copy["exit_time"] = pd.to_datetime(
                        trades_copy["exit_time"], errors="coerce"
                    )

                    # Convert price and qty to numeric
                    trades_copy["entry_price"] = pd.to_numeric(
                        trades_copy["entry_price"], errors="coerce"
                    ).fillna(0.0)
                    trades_copy["entry_qty"] = pd.to_numeric(
                        trades_copy["entry_qty"], errors="coerce"
                    ).fillna(0.0)
                except Exception as e:
                    continue

                # Filter trades that have entered by this date with robust datetime handling
                try:
                    # Ensure dt_obj is timezone-naive if entry_time is timezone-naive
                    if (
                        hasattr(trades_copy["entry_time"].iloc[0], "tz")
                        and trades_copy["entry_time"].iloc[0].tz is not None
                    ):
                        if dt_obj.tz is None:
                            dt_obj = dt_obj.tz_localize("UTC")
                    else:
                        if hasattr(dt_obj, "tz") and dt_obj.tz is not None:
                            dt_obj = dt_obj.tz_localize(None)

                    # Remove any NaT values before comparison
                    valid_entry_mask = trades_copy["entry_time"].notna()
                    if not valid_entry_mask.any():
                        continue

                    # More efficient filtering to avoid memory issues
                    try:
                        # Apply both filters in one operation to reduce memory usage
                        time_mask = trades_copy["entry_time"] <= dt_obj
                        combined_mask = valid_entry_mask & time_mask
                        entered_trades = trades_copy.loc[combined_mask].copy()
                    except (MemoryError, KeyboardInterrupt):
                        # Fallback to simpler approach if memory issues
                        valid_trades = trades_copy.dropna(subset=["entry_time"])
                        time_filter = valid_trades["entry_time"] <= dt_obj
                        entered_trades = valid_trades[time_filter]
                except Exception as e:
                    continue

                if not entered_trades.empty:
                    # Identify open trades (no exit or exit after current date)
                    # Ensure both sides of comparison are tz-naive
                    exit_times = pd.to_datetime(
                        entered_trades["exit_time"], errors="coerce"
                    )
                    if exit_times.dt.tz is not None:
                        exit_times = exit_times.dt.tz_localize(None)

                    # Create mask separately to avoid tz mismatch
                    has_no_exit = entered_trades["exit_time"].isna()
                    exit_after_dt = exit_times > dt_obj
                    open_mask = has_no_exit | exit_after_dt
                    open_trades = entered_trades[open_mask]

                    if not open_trades.empty and price_at_dt is not None:
                        # Calculate MTM for all open trades with robust error handling
                        try:
                            entry_day_mask = open_trades["entry_time"] == dt_obj

                            # Entry day trades: MTM = 0, use entry price for exposure
                            entry_day_trades = open_trades[entry_day_mask]
                            if not entry_day_trades.empty:
                                # Ensure numeric types and handle NaN values
                                entry_prices = pd.to_numeric(
                                    entry_day_trades["entry_price"],
                                    errors="coerce",
                                ).fillna(0.0)
                                entry_qtys = pd.to_numeric(
                                    entry_day_trades["entry_qty"],
                                    errors="coerce",
                                ).fillna(0.0)
                                exposure_value = abs(
                                    entry_prices * entry_qtys
                                ).sum()
                                if not pd.isna(exposure_value):
                                    exposure += exposure_value

                            # Post-entry trades: MTM based on current price vs entry price
                            post_entry_trades = open_trades[~entry_day_mask]
                            if not post_entry_trades.empty:
                                # Ensure numeric types and handle NaN values
                                post_entry_prices = pd.to_numeric(
                                    post_entry_trades["entry_price"],
                                    errors="coerce",
                                ).fillna(0.0)
                                post_entry_qtys = pd.to_numeric(
                                    post_entry_trades["entry_qty"],
                                    errors="coerce",
                                ).fillna(0.0)

                                mtm_values = (
                                    price_at_dt - post_entry_prices
                                ) * post_entry_qtys
                                mtm_sum = mtm_values.sum()
                                if not pd.isna(mtm_sum):
                                    unrealized += mtm_sum

                                exposure_value = abs(
                                    price_at_dt * post_entry_qtys
                                ).sum()
                                if not pd.isna(exposure_value):
                                    exposure += exposure_value

                        except Exception as e:
                            continue

        # Equity is always initial_capital + (realized + unrealized)
        total_return = realized_cum_total + unrealized
        equity_val = float(initial_capital) + total_return

        # Update running peak (high watermark)
        if equity_val > running_peak:
            running_peak = equity_val

        # Proper drawdown calculation: distance from running peak, not daily drop
        draw_inr = max(0.0, running_peak - equity_val)
        draw_pct = (
            (draw_inr / running_peak * 100.0) if running_peak > 0 else 0.0
        )

        # Update running max drawdown
        if draw_inr > max_dd_inr:
            max_dd_inr = draw_inr
            max_dd_pct = draw_pct

        # Calculate incremental changes for this day/period
        daily_realized_increment = (
            daily_realized  # This is already the daily increment
        )
        daily_unrealized_increment = (
            unrealized - prev_unrealized
        )  # Change in unrealized MTM
        daily_total_increment = (
            daily_realized_increment + daily_unrealized_increment
        )

        # Calculate percentage based on current equity as denominator
        # Realized % based on current equity
        realized_pct = (
            (daily_realized_increment / equity_val * 100.0)
            if equity_val > 0
            else 0.0
        )

        # Unrealized % based on current equity
        unrealized_pct = (
            (daily_unrealized_increment / equity_val * 100.0)
            if equity_val > 0
            else 0.0
        )

        # Total Return % - period return (day-over-day change)
        # This shows the return for THIS day compared to the previous day
        total_pct = (
            ((equity_val / prev_equity) - 1) * 100.0 if prev_equity > 0 else 0.0
        )

        # Update avg_exposure_pct to be relative to current equity
        avg_exposure_pct = (
            (exposure / equity_val * 100.0) if equity_val > 0 else 0.0
        )

        rows.append(
            {
                "time": pd.to_datetime(dt),
                "equity": equity_val,
                "avg_exposure": exposure,
                "avg_exposure_pct": avg_exposure_pct,
                "realized_inr": daily_realized_increment,  # Daily incremental realized P&L
                "realized_pct": realized_pct,
                "unrealized_inr": daily_unrealized_increment,  # Daily incremental unrealized change
                "unrealized_pct": unrealized_pct,
                "total_return_inr": daily_total_increment,  # Daily incremental total
                "total_return_pct": total_pct,
                "drawdown_inr": draw_inr,
                "drawdown_pct": draw_pct,
                "max_drawdown_inr": max_dd_inr,
                "max_drawdown_pct": max_dd_pct,
            }
        )

        # Update previous values for next iteration
        prev_unrealized = unrealized
        prev_equity = (
            equity_val  # Update for next day's period return calculation
        )

    df_port = pd.DataFrame(rows).set_index("time").sort_index()

    # Prepend explicit initial-capital baseline on first date
    if not df_port.empty:
        first_dt = df_port.index[0]
        first_row_data = {
            "equity": float(initial_capital),
            "avg_exposure": 0.0,
            "avg_exposure_pct": 0.0,
            "realized_inr": 0.0,
            "realized_pct": 0.0,
            "unrealized_inr": 0.0,
            "unrealized_pct": 0.0,
            "total_return_inr": 0.0,
            "total_return_pct": 0.0,
            "drawdown_inr": 0.0,
            "drawdown_pct": 0.0,
            "max_drawdown_inr": 0.0,
            "max_drawdown_pct": 0.0,
        }
        first_baseline_df = pd.DataFrame([first_row_data], index=[first_dt])
        # Combine, keeping first occurrence if dates match
        df_port = pd.concat([first_baseline_df, df_port])
        df_port = df_port[~df_port.index.duplicated(keep="first")].sort_index()

    return df_port


def _slice_df_years(df, years):
    """Slice dataframe to last N years."""
    if years is None:
        return df
    if df.empty:
        return df

    try:
        idx = pd.to_datetime(df.index, errors="coerce")
        last = idx.max()
        first = last - pd.DateOffset(years=years)
        mask = idx >= first
        result = df.loc[mask]
        return result if not result.empty else df.iloc[-252 * years :] if len(df) >= 252 * years else df
    except Exception as e:
        logger.warning(f"Error slicing df by years: {e}, returning full df")
        return df


def backtest_symbol(args: tuple) -> dict:
    """Backtest a single symbol - returns trades and OHLC data."""
    symbol, df_full, strategy_name, cfg = args

    try:
        strat = make_strategy(strategy_name)
        engine = BacktestEngine(df_full, strat, cfg, symbol=symbol)
        trades_full, equity_full, _ = engine.run()

        return {
            "symbol": symbol,
            "status": "success",
            "trades": trades_full,
            "ohlc": df_full,
        }
    except Exception as e:
        logger.debug(f"Error for {symbol}: {str(e)[:50]}")
        return {
            "symbol": symbol,
            "status": "error",
        }


def run_fast_backtest(
    strategy_name: str,
    basket_file: str,
    interval: str = "1d",
    num_workers: int | None = None,
) -> None:
    """
    Run fast basket backtest with multi-window analysis.
    Outputs TOTAL rows only for windows: 1Y, 3Y, 5Y, MAX.
    Creates BACKTEST_METRICS.csv in timestamped folder.
    """
    start_time = time.time()

    logger.info(f"🚀 FAST BACKTEST: {strategy_name}")

    # Load symbols
    with open(basket_file) as f:
        symbols = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    logger.info(f"📊 {len(symbols)} symbols loaded")

    # Load strategy
    try:
        make_strategy(strategy_name)
    except Exception:
        logger.error(f"❌ Strategy not found: {strategy_name}")
        sys.exit(1)

    # Load all OHLCV data
    logger.info("📥 Loading OHLCV data...")
    ohlcv_map = load_many_india(symbols, interval=interval)

    # Filter to symbols with data
    valid_symbols = [s for s in symbols if s in ohlcv_map and len(ohlcv_map[s]) > 0]
    logger.info(f"🔄 Backtesting {len(valid_symbols)} symbols (1Y, 3Y, 5Y, MAX windows)...")

    # Prepare backtest tasks
    cfg = BrokerConfig()
    tasks = [(symbol, ohlcv_map[symbol], strategy_name, cfg) for symbol in valid_symbols]

    # Run backtests in parallel using module-level function
    num_workers = num_workers or max(2, cpu_count() - 1)
    logger.info(f"   Using {num_workers} workers")

    symbol_results = {}
    errors = 0

    try:
        ctx = get_context("spawn")
        with ctx.Pool(num_workers) as pool:
            for i, (symbol, result, error) in enumerate(pool.imap_unordered(_process_symbol_for_backtest, tasks), 1):
                if error:
                    logger.debug(f"Error for {symbol}: {error}")
                    errors += 1
                else:
                    symbol_results[symbol] = result
                    if i % max(1, len(valid_symbols) // 10) == 0 or i == len(valid_symbols):
                        logger.info(f"   ✅ {i}/{len(valid_symbols)}")
    except Exception as e:
        logger.warning(f"Parallel processing failed, falling back to sequential: {e}")
        # Fallback to sequential
        for symbol, df_full, strategy_name, cfg in tasks:
            try:
                strat = make_strategy(strategy_name)
                engine = BacktestEngine(df_full, strat, cfg, symbol=symbol)
                trades_full, equity_full, _ = engine.run()
                symbol_results[symbol] = {
                    "trades": trades_full,
                    "equity": equity_full,
                    "data": df_full,
                }
            except Exception as e:
                logger.debug(f"Error for {symbol}: {e}")
                errors += 1

    logger.info(f"✅ Parallel backtests complete: {len(symbol_results)} successful, {errors} errors")

    if not symbol_results:
        logger.info("⚠️  No symbols backtested successfully")
        return

    # Now compute metrics for each window
    bars_per_year = BARS_PER_YEAR_MAP.get(interval, 245)
    windows_years = (1, 3, 5, None)  # (1Y, 3Y, 5Y, MAX)

    # Optimize window processing
    window_results = optimize_window_processing(symbol_results, list(windows_years), bars_per_year)

    # Collect TOTAL rows for each window
    all_totals = []

    for Y in windows_years:
        label = WINDOW_LABELS[Y]
        logger.info(f"📊 Computing {label} window metrics...")

        window_data = window_results[label]
        trades_by_symbol = window_data["trades_by_symbol"]
        dfs_by_symbol = {}

        # Build price data for this window
        for sym in symbol_results.keys():
            df_full = symbol_results[sym]["data"]
            df = _slice_df_years(df_full, Y)
            if len(df) > 0:
                dfs_by_symbol[sym] = df

        # Filter trades to this window
        trades_by_window_filtered = {}
        for sym, trades in trades_by_symbol.items():
            trades_filtered = trades.copy() if trades is not None and not trades.empty else trades
            if trades_filtered is not None and not trades_filtered.empty:
                try:
                    df_for_sym = dfs_by_symbol.get(sym)
                    if df_for_sym is not None and not df_for_sym.empty:
                        window_start_date = pd.to_datetime(df_for_sym.index.min())
                        entry_times = pd.to_datetime(trades_filtered["entry_time"], errors="coerce")
                        mask = entry_times >= window_start_date
                        trades_filtered = trades_filtered.loc[mask].copy()
                except Exception as e:
                    logger.debug(f"Error filtering trades for {sym}: {e}")
            trades_by_window_filtered[sym] = trades_filtered

        # Compute TOTAL metrics using compute_portfolio_trade_metrics
        total_row = compute_portfolio_trade_metrics(
            dfs_by_symbol=dfs_by_symbol,
            trades_by_symbol=trades_by_window_filtered,
            bars_per_year=bars_per_year,
        )

        # Calculate NetPnLPct using same method as run_basket.py:
        # NetPnLPct = TotalNetPnL / initial_capital * 100 (not divided by deployed capital)
        total_net_pnl = total_row.get("TotalNetPnL", 0.0)
        net_pnl_pct = (total_net_pnl / cfg.initial_capital * 100.0) if cfg.initial_capital > 0 else 0.0

        # Get max drawdown from portfolio curve
        port_df = _build_portfolio_curve(trades_by_window_filtered, dfs_by_symbol, cfg.initial_capital)
        max_dd_pct = 0.0
        if not port_df.empty and "max_drawdown_pct" in port_df.columns:
            try:
                max_dd_pct = float(pd.to_numeric(port_df["max_drawdown_pct"], errors="coerce").max())
            except Exception:
                max_dd_pct = 0.0

        # Calculate Equity CAGR from net return
        equity_cagr = 0.0
        try:
            if Y is not None:
                n_years = Y
            else:
                # Calculate from actual dates for MAX window
                all_dates = []
                for df in dfs_by_symbol.values():
                    if df is not None and not df.empty:
                        all_dates.extend(pd.to_datetime(df.index, errors="coerce").tolist())
                if all_dates:
                    n_years = (max(all_dates) - min(all_dates)).days / 365.25
                    n_years = max(n_years, 1.0 / 365.25)
                else:
                    n_years = 1.0

            net_pnl_decimal = net_pnl_pct / 100.0
            equity_cagr = (
                ((1.0 + net_pnl_decimal) ** (1.0 / n_years) - 1.0) * 100.0
                if net_pnl_decimal > -1.0
                else 0.0
            )
        except Exception:
            equity_cagr = 0.0

        total_row["NetPnLPct"] = net_pnl_pct
        total_row["MaxDrawdownPct"] = max_dd_pct
        total_row["CAGR_pct"] = equity_cagr
        total_row["Window"] = label
        total_row["Symbol"] = "TOTAL"

        all_totals.append(total_row)

    # Create output dataframe with only TOTAL rows
    output_rows = []
    for total_row in all_totals:
        output_row = {
            "Window": total_row.get("Window"),
            "Symbol": "TOTAL",
            "Net P&L %": round(float(total_row.get("NetPnLPct", 0.0)), 2),
            "Max equity drawdown %": round(float(total_row.get("MaxDrawdownPct", 0.0)), 2),
            "Total trades": int(total_row.get("NumTrades", 0)),
            "Profitable trades %": round(float(total_row.get("WinRatePct", 0.0)), 2),
            "Profit factor": round(float(total_row.get("ProfitFactor", 0.0)), 2),
            "Avg P&L % per trade": round(float(total_row.get("AvgProfitPerTradePct", 0.0)), 2),
            "Avg bars per trade": int(total_row.get("AvgBarsPerTrade", 0)),
            "IRR %": round(float(total_row.get("IRR_pct", 0.0)), 2),
            "Equity CAGR %": round(float(total_row.get("CAGR_pct", 0.0)), 2),
        }
        output_rows.append(output_row)

    output_df = pd.DataFrame(output_rows)

    # Show results
    print("\n" + "=" * 100)
    print("RESULTS:")
    print("=" * 100)
    print(output_df.to_string(index=False))
    print("=" * 100 + "\n")

    # Save to timestamped folder
    _save_metrics(output_df, strategy_name, basket_file, interval)

    elapsed = time.time() - start_time
    logger.info(f"⏱️  Total time: {elapsed:.1f}s")


def _save_metrics(
    metrics_df: pd.DataFrame,
    strategy_name: str,
    basket_file: str,
    interval: str,
) -> None:
    """
    Save metrics to timestamped folder in format:
    reports/MMDD-HHMM-<strategy>-<basket>-<interval>/
        └── BACKTEST_METRICS.csv
    """
    try:
        # Extract basket name from path
        basket_name = os.path.basename(basket_file).replace("basket_", "").replace(".txt", "")

        # Create folder name with timestamp
        now = datetime.now()
        folder_name = f"{now.strftime('%m%d-%H%M')}-{strategy_name}-{basket_name}-{interval}"
        metrics_path = os.path.join("reports", folder_name)

        os.makedirs(metrics_path, exist_ok=True)

        # Save CSV
        csv_path = os.path.join(metrics_path, "BACKTEST_METRICS.csv")
        metrics_df.to_csv(csv_path, index=False)

        logger.info(f"✅ Saved metrics to: {csv_path}")

    except Exception as e:
        logger.warning(f"Failed to save metrics: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fast basket backtest runner - minimal output, maximum speed"
    )
    parser.add_argument(
        "--strategy",
        required=True,
        help="Strategy name (e.g., kama_13_55_filter)",
    )
    parser.add_argument(
        "--basket_file",
        required=True,
        help="Path to basket file",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Interval (1d, 125m, 75m)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of workers (default: cpu_count - 1)",
    )

    args = parser.parse_args()

    run_fast_backtest(
        strategy_name=args.strategy,
        basket_file=args.basket_file,
        interval=args.interval,
        num_workers=args.workers,
    )
