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

# ============================================================================
# CRITICAL: Prevent Python bytecode cache (.pyc) files
# This ensures strategy changes take effect immediately without stale cache
# ============================================================================
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

# Clear any existing __pycache__ directories on startup
import shutil
from pathlib import Path
_workspace_root = Path(__file__).parent.parent
for _pycache_dir in _workspace_root.rglob('__pycache__'):
    try:
        shutil.rmtree(_pycache_dir)
    except Exception:
        pass
# ============================================================================

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
from core.loaders import load_many_india

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

    OPTIMIZED VERSION: Uses vectorized operations instead of nested loops.
    
    Key principles:
      1. Start at initial_capital on day 0 with zero exposure/returns.
      2. Equity = initial_capital + (sum of closed trade P&L + sum of open trade MTM).
      3. Drawdown = distance from running peak (high watermark).
      4. max_drawdown_inr/pct = running maximum of drawdowns.
      5. Last row should match the final equity position.

    Output columns: equity, avg_exposure, avg_exposure_pct, realized_inr, realized_pct,
    unrealized_inr, unrealized_pct, total_return_inr, total_return_pct,
    drawdown_inr, drawdown_pct, max_drawdown_inr, max_drawdown_pct.
    """
    import numpy as np
    
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
    n_dates = len(dates)
    date_to_idx = {d: i for i, d in enumerate(dates)}
    
    # Pre-build price lookup arrays for each symbol (vectorized price access)
    # prices_matrix[sym] = numpy array of prices aligned to dates index
    prices_by_sym = {}
    for sym, df in dfs_by_symbol.items():
        if df is None or df.empty:
            continue
        try:
            df_idx = pd.to_datetime(df.index, errors="coerce")
            close_prices = df["close"].values
            # Create aligned array - forward fill prices
            aligned = np.full(n_dates, np.nan)
            for i, dt in enumerate(dates):
                # Find latest price <= dt
                mask = df_idx <= dt
                if mask.any():
                    last_idx = np.where(mask)[0][-1]
                    aligned[i] = close_prices[last_idx]
            # Forward fill any remaining NaN
            for i in range(1, n_dates):
                if np.isnan(aligned[i]) and not np.isnan(aligned[i-1]):
                    aligned[i] = aligned[i-1]
            prices_by_sym[sym] = aligned
        except Exception:
            continue

    # Pre-compute realized P&L by date (vectorized)
    realized_by_date_idx = np.zeros(n_dates)
    
    # Collect all trades into a single structure for efficient processing
    all_trades_list = []
    for sym, trades in trades_by_symbol.items():
        if trades is None or trades.empty:
            continue
        try:
            t = trades.copy()
            t["_sym"] = sym
            t["entry_time"] = pd.to_datetime(t["entry_time"], errors="coerce")
            t["exit_time"] = pd.to_datetime(t["exit_time"], errors="coerce")
            t["entry_price"] = pd.to_numeric(t["entry_price"], errors="coerce").fillna(0.0)
            t["entry_qty"] = pd.to_numeric(t["entry_qty"], errors="coerce").fillna(0.0)
            t["net_pnl"] = pd.to_numeric(t["net_pnl"], errors="coerce").fillna(0.0)
            
            # Normalize timezone
            if t["entry_time"].dt.tz is not None:
                t["entry_time"] = t["entry_time"].dt.tz_localize(None)
            if t["exit_time"].dt.tz is not None:
                t["exit_time"] = t["exit_time"].dt.tz_localize(None)
            
            all_trades_list.append(t)
        except Exception:
            continue
    
    if not all_trades_list:
        # No trades - return flat equity curve
        rows = []
        for dt in dates:
            rows.append({
                "time": pd.to_datetime(dt),
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
            })
        return pd.DataFrame(rows).set_index("time").sort_index()
    
    all_trades = pd.concat(all_trades_list, ignore_index=True)
    
    # Build realized P&L by date
    exited = all_trades[all_trades["exit_time"].notna()].copy()
    if not exited.empty:
        for _, row in exited.iterrows():
            exit_dt = row["exit_time"]
            if exit_dt in date_to_idx:
                realized_by_date_idx[date_to_idx[exit_dt]] += row["net_pnl"]
    
    # Cumulative realized P&L
    cum_realized = np.cumsum(realized_by_date_idx)
    
    # Pre-compute trade entry/exit date indices for fast open trade detection
    all_trades["_entry_idx"] = all_trades["entry_time"].map(lambda x: date_to_idx.get(x, -1) if pd.notna(x) else -1)
    all_trades["_exit_idx"] = all_trades["exit_time"].map(lambda x: date_to_idx.get(x, n_dates) if pd.notna(x) else n_dates)
    
    # Convert to numpy for fast iteration
    entry_idxs = all_trades["_entry_idx"].values
    exit_idxs = all_trades["_exit_idx"].values
    entry_prices = all_trades["entry_price"].values
    entry_qtys = all_trades["entry_qty"].values
    syms = all_trades["_sym"].values
    
    # Build daily unrealized P&L and exposure (optimized single pass per date)
    unrealized_arr = np.zeros(n_dates)
    exposure_arr = np.zeros(n_dates)
    
    # Process each date
    for date_idx in range(n_dates):
        unrealized = 0.0
        exposure = 0.0
        
        # Find trades that are open on this date:
        # Open if: entry_idx <= date_idx AND exit_idx > date_idx
        open_mask = (entry_idxs <= date_idx) & (exit_idxs > date_idx) & (entry_idxs >= 0)
        
        if open_mask.any():
            open_indices = np.where(open_mask)[0]
            for ti in open_indices:
                sym = syms[ti]
                entry_price = entry_prices[ti]
                qty = entry_qtys[ti]
                entry_idx = entry_idxs[ti]
                
                # Get current price
                if sym in prices_by_sym:
                    price_arr = prices_by_sym[sym]
                    current_price = price_arr[date_idx]
                    if np.isnan(current_price):
                        continue
                else:
                    continue
                
                # Entry day: no MTM, just exposure at entry price
                if entry_idx == date_idx:
                    exposure += abs(entry_price * qty)
                else:
                    # Post-entry: MTM and exposure at current price
                    mtm = (current_price - entry_price) * qty
                    unrealized += mtm
                    exposure += abs(current_price * qty)
        
        unrealized_arr[date_idx] = unrealized
        exposure_arr[date_idx] = exposure
    
    # Build equity curve
    equity_arr = initial_capital + cum_realized + unrealized_arr
    
    # Compute drawdown from running peak
    running_peak = np.maximum.accumulate(equity_arr)
    drawdown_inr = np.maximum(0, running_peak - equity_arr)
    drawdown_pct = np.where(running_peak > 0, drawdown_inr / running_peak * 100, 0)
    max_dd_inr = np.maximum.accumulate(drawdown_inr)
    max_dd_pct = np.maximum.accumulate(drawdown_pct)
    
    # Build output dataframe
    rows = []
    prev_unrealized = 0.0
    prev_equity = float(initial_capital)
    
    for i, dt in enumerate(dates):
        equity_val = equity_arr[i]
        daily_realized = realized_by_date_idx[i]
        unrealized = unrealized_arr[i]
        exposure = exposure_arr[i]
        
        daily_unrealized_increment = unrealized - prev_unrealized
        daily_total_increment = daily_realized + daily_unrealized_increment
        
        realized_pct_val = (daily_realized / equity_val * 100.0) if equity_val > 0 else 0.0
        unrealized_pct_val = (daily_unrealized_increment / equity_val * 100.0) if equity_val > 0 else 0.0
        total_pct = ((equity_val / prev_equity) - 1) * 100.0 if prev_equity > 0 else 0.0
        avg_exposure_pct = (exposure / equity_val * 100.0) if equity_val > 0 else 0.0
        
        rows.append({
            "time": pd.to_datetime(dt),
            "equity": equity_val,
            "avg_exposure": exposure,
            "avg_exposure_pct": avg_exposure_pct,
            "realized_inr": daily_realized,
            "realized_pct": realized_pct_val,
            "unrealized_inr": daily_unrealized_increment,
            "unrealized_pct": unrealized_pct_val,
            "total_return_inr": daily_total_increment,
            "total_return_pct": total_pct,
            "drawdown_inr": drawdown_inr[i],
            "drawdown_pct": drawdown_pct[i],
            "max_drawdown_inr": max_dd_inr[i],
            "max_drawdown_pct": max_dd_pct[i],
        })
        
        prev_unrealized = unrealized
        prev_equity = equity_val
    
    df_port = pd.DataFrame(rows).set_index("time").sort_index()
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
            "Avg bars per trade": int(total_row.get("AvgBarsPerTrade", 0)) if not np.isnan(float(total_row.get("AvgBarsPerTrade", 0))) else 0,
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
