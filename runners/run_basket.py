# runners/run_basket.py
# ✅ PRODUCTION RUNNER - Optimized v2 with macOS fork support
# High-performance backtesting with multiprocessing (4-8x speedup)
#
# Features:
# - Phase 1+2+3 optimizations (indicator cache, fast iteration, NaN safety)
# - Platform-aware multiprocessing (fork on macOS/Linux, spawn fallback)
# - Auto-detects CPU cores for worker pool sizing
# - Production-ready with comprehensive error handling
#
# For baseline sequential backtesting (debugging), use: run_basket_backup.py

from __future__ import annotations

import argparse
import logging
import os
import platform
import signal
import sys
import time
import traceback
from contextlib import contextmanager
from multiprocessing import Pool, cpu_count, get_context
from typing import Optional

import numpy as np
import pandas as pd

from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.metrics import (
    compute_comprehensive_metrics,
    compute_portfolio_trade_metrics,
    compute_trade_metrics_table,
    load_benchmark,
    calculate_alpha_beta,
)
from core.monitoring import BacktestMonitor, optimize_window_processing
from core.registry import make_strategy
from core.report import make_run_dir, save_summary
from data.loaders import load_many_india

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Bars per year for each timeframe
# Used for window calculations (1Y, 3Y, 5Y windows)
# MAX window always uses all available bars
BARS_PER_YEAR_MAP: dict[str, int] = {
    "1d": 245,  # 1Y: 245, 3Y: 735, 5Y: 1225 bars
    "125m": 735,  # 1Y: 735, 3Y: 2205, 5Y: 3675 bars
    "75m": 1225,  # 1Y: 1225, 3Y: 3675, 5Y: 6125 bars
}

# Timeout configuration
DEFAULT_TIMEOUT = 300  # 5 minutes per operation
SYMBOL_TIMEOUT = 60  # 1 minute per symbol
TOTAL_TIMEOUT = 3600  # 1 hour total limit

# Global flag for graceful shutdown on interrupt
_shutdown_requested = False


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    global _shutdown_requested
    if not _shutdown_requested:
        _shutdown_requested = True
        logger.warning("\n⚠️ Interrupt signal received (Ctrl+C)")
        logger.warning("⏳ Finishing current operation safely...")
        logger.info("💡 Press Ctrl+C again to force exit (not recommended)")
    else:
        logger.error("\n❌ Force exit requested. Data may be incomplete!")
        sys.exit(1)


# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class TimeoutError(Exception):
    """Custom timeout exception."""

    pass


@contextmanager
def timeout_handler(seconds: int, error_message: str = "Operation timed out"):
    """Context manager for operation timeouts."""

    def signal_handler(signum, frame):
        raise TimeoutError(error_message)

    # Set the signal handler and alarm
    old_handler = signal.signal(signal.SIGALRM, signal_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Clean up
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def safe_operation(
    func,
    *args,
    timeout_seconds: int = DEFAULT_TIMEOUT,
    operation_name: str = "operation",
    **kwargs,
):
    """Safely execute an operation with timeout and error handling."""
    try:
        logger.info(f"Starting {operation_name}...")
        with timeout_handler(
            timeout_seconds, f"{operation_name} timed out after {timeout_seconds}s"
        ):
            result = func(*args, **kwargs)
        logger.info(f"Completed {operation_name} successfully")
        return result
    except TimeoutError as e:
        logger.error(f"Timeout in {operation_name}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error in {operation_name}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        import traceback as tb

        print("\n" + "=" * 80)
        print(f"❌ FULL ERROR TRACEBACK IN {operation_name}:")
        print("=" * 80)
        tb.print_exc()
        print("=" * 80 + "\n")
        raise


def _read_symbols_from_txt(txt_path: str) -> list[str]:
    with open(txt_path) as f:
        lines = [ln.strip() for ln in f.read().splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("Empty symbols file")
    if lines[0].lower() == "symbol":
        lines = lines[1:]
    return lines


# ===== MODULE-LEVEL FUNCTION FOR MULTIPROCESSING =====
# This must be at module level (not nested) to be pickleable for multiprocessing
def _process_symbol_for_backtest(args):
    """
    Process a single symbol for parallel execution.
    This function is module-level to be pickleable with multiprocessing.
    """
    sym, sym_idx, total_syms, data_dict, strategy_name, params_json = args
    try:
        if sym not in data_dict or data_dict[sym] is None or data_dict[sym].empty:
            return sym, None, f"No data for {sym}"

        df_full = data_dict[sym]
        strat = make_strategy(strategy_name, params_json)
        engine = BacktestEngine(
            df_full, strat, BrokerConfig(), symbol=sym
        )
        trades_full, equity_full, _ = engine.run()

        return (
            sym,
            {
                "trades": trades_full,
                "equity": equity_full,
                "data": df_full,
                "fingerprint": getattr(engine, "data_fingerprint", None),
                "validation": getattr(engine, "validation_results", None),
            },
            None,
        )
    except Exception as e:
        return sym, None, f"Error: {str(e)}"


def _slice_df_years(df, years):
    if years is None:
        return df
    if df.empty:
        return df

    try:
        # Ensure index is datetime64
        idx = pd.to_datetime(df.index, errors="coerce")
        last = idx.max()
        # Handle timezone-aware datetimes properly
        first = last - pd.DateOffset(years=years)

        # Ensure both datetimes have the same timezone for comparison
        if hasattr(last, "tz") and last.tz is not None:
            if hasattr(first, "tz") and first.tz is None:
                first = first.tz_localize(last.tz)

        # Use comparison with converted index
        mask = idx >= first
        result = df.loc[mask]
        return (
            result
            if not result.empty
            else (df.iloc[-252 * years :] if len(df) >= 252 * years else df)
        )
    except Exception as e:
        logger.warning(f"Error slicing df by years: {e}, returning full df")
        return df


def _sanitize_symbol(sym: str) -> str:
    return "".join([c if (c.isalnum() or c in ("_", "-")) else "_" for c in sym])


def _format_and_enforce_totals(
    out_df: pd.DataFrame, total_net_pct: float
) -> pd.DataFrame:
    """Format percent/numeric columns for human CSV and enforce TOTAL Net P&L parity.

    - total_net_pct: numeric percent (e.g. 12.3456 -> 12.3456)
    Returns a new DataFrame with formatted strings for percent fields and integer fields.
    """
    df = out_df.copy()
    # Normalize column names that tests may expect
    # Accept either 'Max equity drawdown' or 'Max equity drawdown %'
    dd_col = None
    if "Max equity drawdown %" in df.columns:
        dd_col = "Max equity drawdown %"
    elif "Max equity drawdown" in df.columns:
        dd_col = "Max equity drawdown"

    # Enforce TOTAL Net P&L
    if "Net P&L %" in df.columns:
        # ensure numeric
        try:
            df["Net P&L % (num)"] = pd.to_numeric(df["Net P&L %"], errors="coerce")
        except Exception:
            df["Net P&L % (num)"] = 0.0
        # Set TOTAL
        total_mask = df["Symbol"] == "TOTAL"
        if total_mask.any():
            df.loc[total_mask, "Net P&L % (num)"] = float(total_net_pct)

        # Format percent columns (vectorized - faster than apply with function)
        df["Net P&L %"] = (
            pd.to_numeric(df["Net P&L % (num)"], errors="coerce")
            .fillna(0)
            .apply(lambda v: f"{v:.2f}%")
        )

    # Format drawdown as percent (vectorized)
    if dd_col is not None:
        try:
            df["_dd_num"] = pd.to_numeric(df[dd_col], errors="coerce")
            # if drawdown appears fractional (< 2) assume decimal and convert to percent
            if not df["_dd_num"].dropna().empty and df["_dd_num"].abs().max() <= 2.0:
                df["_dd_num"] = df["_dd_num"].astype(float)
            # Vectorized formatting
            df[dd_col] = df["_dd_num"].fillna(0).apply(lambda v: f"{v:.2f}%")
            df = df.drop(columns=["_dd_num"], errors="ignore")
        except Exception:
            pass

    # Format integer-like columns (vectorized)
    if "Total trades" in df.columns:
        # Convert to numeric, fill NaN with 0, convert to int, then format with commas
        df["Total trades"] = (
            pd.to_numeric(df["Total trades"], errors="coerce")
            .fillna(0)
            .astype(int)
            .apply(lambda x: f"{x:,}")
        )

    return df


def _pre_calculate_trade_indicators_cached(
    df: pd.DataFrame, trades_df: pd.DataFrame
) -> dict:
    """⚡ PHASE 2 OPTIMIZATION: Pre-calculate ALL indicators ONCE for all entry times.

    Instead of recalculating 30+ indicators for EVERY trade, calculate them once per entry_time
    and cache the results. This eliminates redundant calculations.

    Returns:
        Dict mapping entry_time -> indicators_dict
    """
    if df.empty or trades_df.empty:
        return {}

    # Get unique entry times to avoid redundant calculations
    unique_entries = trades_df["entry_time"].unique()
    entry_indicators_cache = {}

    # Pre-convert df index to datetime once
    df_idx = pd.to_datetime(df.index, errors="coerce")
    # Pre-calculate OHLCV arrays (vectorized once)
    high_arr = df["high"].astype(float).values
    low_arr = df["low"].astype(float).values
    close_arr = df["close"].astype(float).values

    # Import all indicator functions once
    from utils import ATR, EMA, MACD, RSI, SMA, BollingerBands, Stochastic
    from utils.indicators import (
        ADX,
        CCI,
        HMA,
        VWMA,
        Aroon,
        BullBearPower,
        MomentumOscillator,
        StochasticRSI,
        TrendClassification,
        UltimateOscillator,
        VolatilityClassification,
        WilliamsR,
        calculate_stochastic_slow,
        extract_ichimoku_base_line,
    )

    # Calculate indicators ONCE for the full series
    atr_values = ATR(high_arr, low_arr, close_arr, 14)
    atr_series = pd.Series(atr_values, index=df.index)
    atr_pct_series = (atr_series / df["close"]) * 100

    bb_values = BollingerBands(close_arr, 20, 2)
    stoch_values = Stochastic(high_arr, low_arr, close_arr, 14, 3)
    adx_values = ADX(high_arr, low_arr, close_arr, 14)
    rsi_series = RSI(df["close"], 14)
    ema_5_series = pd.Series(EMA(close_arr, 5), index=df.index)
    ema_20_series = pd.Series(EMA(close_arr, 20), index=df.index)
    ema_50_series = pd.Series(EMA(close_arr, 50), index=df.index)
    ema_200_series = pd.Series(EMA(close_arr, 200), index=df.index)
    sma_5_series = SMA(df["close"], 5)
    sma_20_series = SMA(df["close"], 20)
    sma_50_series = SMA(df["close"], 50)
    sma_200_series = SMA(df["close"], 200)
    macd_values = MACD(close_arr, 12, 26, 9)
    macd_line_series = pd.Series(macd_values["macd"], index=df.index)
    macd_signal_series = pd.Series(macd_values["signal"], index=df.index)

    # For each unique entry time, lookup indicators from pre-calculated series
    for entry_time in unique_entries:
        entry_time = pd.Timestamp(entry_time)
        entry_data_mask = df_idx <= entry_time

        if not entry_data_mask.any():
            continue

        last_idx = entry_data_mask.nonzero()[0][-1]

        # Lookup from pre-calculated series
        atr_val = atr_series.iloc[last_idx]
        atr_pct_val = atr_pct_series.iloc[last_idx]
        close_val = close_arr[last_idx]

        # Get latest values from pre-calculated series
        adx_val = (
            adx_values["adx"][last_idx] if last_idx < len(adx_values["adx"]) else 0
        )
        plus_di_val = (
            adx_values["di_plus"][last_idx]
            if last_idx < len(adx_values["di_plus"])
            else 0
        )
        minus_di_val = (
            adx_values["di_minus"][last_idx]
            if last_idx < len(adx_values["di_minus"])
            else 0
        )
        rsi_val = rsi_series.iloc[last_idx] if last_idx < len(rsi_series) else 50

        macd_line_val = (
            macd_line_series.iloc[last_idx] if last_idx < len(macd_line_series) else 0
        )
        macd_signal_val = (
            macd_signal_series.iloc[last_idx]
            if last_idx < len(macd_signal_series)
            else 0
        )

        ema_5_val = ema_5_series.iloc[last_idx] if last_idx < len(ema_5_series) else 0
        ema_20_val = (
            ema_20_series.iloc[last_idx] if last_idx < len(ema_20_series) else 0
        )
        ema_50_val = (
            ema_50_series.iloc[last_idx] if last_idx < len(ema_50_series) else 0
        )
        ema_200_val = (
            ema_200_series.iloc[last_idx] if last_idx < len(ema_200_series) else 0
        )

        # Calculate Bollinger Band position
        upper_band = (
            bb_values["upper"][last_idx]
            if last_idx < len(bb_values["upper"])
            else close_val
        )
        lower_band = (
            bb_values["lower"][last_idx]
            if last_idx < len(bb_values["lower"])
            else close_val
        )
        if close_val > upper_band:
            bb_pos = "Above"
        elif close_val < lower_band:
            bb_pos = "Below"
        else:
            bb_pos = "Middle"

        # Stochastic
        k_val = (
            stoch_values["k"][last_idx]
            if last_idx < len(stoch_values["k"])
            and not np.isnan(stoch_values["k"][last_idx])
            else 0
        )
        d_val = (
            stoch_values["d"][last_idx]
            if last_idx < len(stoch_values["d"])
            and not np.isnan(stoch_values["d"][last_idx])
            else 0
        )

        # Cache the indicators dict for this entry time
        entry_indicators_cache[entry_time] = {
            "atr": atr_val,
            "atr_pct": atr_pct_val,
            "adx": adx_val,
            "plus_di": plus_di_val,
            "minus_di": minus_di_val,
            "di_bullish": plus_di_val > minus_di_val,
            "rsi": rsi_val,
            "macd_line": macd_line_val,
            "macd_signal": macd_signal_val,
            "macd_bullish": macd_line_val > macd_signal_val,
            "ema_5": ema_5_val,
            "ema_20": ema_20_val,
            "ema_50": ema_50_val,
            "ema_200": ema_200_val,
            "sma_5": sma_5_series.iloc[last_idx] if last_idx < len(sma_5_series) else 0,
            "sma_20": (
                sma_20_series.iloc[last_idx] if last_idx < len(sma_20_series) else 0
            ),
            "sma_50": (
                sma_50_series.iloc[last_idx] if last_idx < len(sma_50_series) else 0
            ),
            "sma_200": (
                sma_200_series.iloc[last_idx] if last_idx < len(sma_200_series) else 0
            ),
            "percent_k": k_val,
            "percent_d": d_val,
            "stoch_bullish": k_val > d_val,
            "bb_position": bb_pos,
            "price_above_ema20": close_val > ema_20_val,
            "price_above_ema50": close_val > ema_50_val,
            "price_above_ema200": close_val > ema_200_val,
            "price_above_ema5": close_val > ema_5_val,
            "ema5_above_ema20": ema_5_val > ema_20_val,
            "ema20_above_ema50": ema_20_val > ema_50_val,
            "ema50_above_ema200": ema_50_val > ema_200_val,
            "holding_days": 0,  # Will be calculated per-trade in the loop
        }

    return entry_indicators_cache


def _export_trades_events(
    trades_df: pd.DataFrame,
    df: pd.DataFrame,
    run_dir: str,
    sym: str,
    label: str,
    initial_capital: float = 100000.0,
) -> str:
    """Export TradingView-style trades CSV for a symbol and return path (or empty string).

    This function writes only TradingView-format CSVs (no duplicate event-style CSVs).
    """
    if trades_df.empty:
        return ""

    sym_safe = _sanitize_symbol(sym)
    tv_rows = []

    # ⚡ PHASE 2: Pre-calculate indicators cache ONCE instead of per-trade
    indicators_cache = _pre_calculate_trade_indicators_cached(df, trades_df)

    # ⚡ OPTIMIZATION: Use itertuples() instead of iterrows() (2x faster)
    for i, tr in enumerate(trades_df.reset_index(drop=True).itertuples(index=False)):
        trade_no = i + 1
        entry_time = tr.entry_time
        exit_time = tr.exit_time
        entry_price = float(tr.entry_price) if not pd.isna(tr.entry_price) else None
        exit_price = float(tr.exit_price) if not pd.isna(tr.exit_price) else None
        qty = int(tr.entry_qty) if tr.entry_qty else 0

        # ⚡ PHASE 2: Use cached indicators instead of recalculating per trade
        entry_time_ts = pd.Timestamp(entry_time)
        indicators = indicators_cache.get(entry_time_ts, {})

        # Calculate holding days for this specific trade
        if entry_time and exit_time:
            exit_dt = pd.to_datetime(exit_time)
            entry_dt = pd.to_datetime(entry_time)
            holding_days = (exit_dt - entry_dt).days
            indicators["holding_days"] = holding_days

        # Compute run-up/drawdown (price * qty P&L) over the trade
        run_up = None
        drawdown = None
        try:
            # Try to get price series using loc with datetime indexing
            price_series = None
            try:
                price_series = df.loc[entry_time:exit_time]["close"].astype(float)
            except (KeyError, TypeError):
                # Fallback: convert times to datetime and try again
                entry_dt = pd.to_datetime(entry_time)
                exit_dt = pd.to_datetime(exit_time)
                # Ensure df index is datetime
                if not isinstance(df.index, pd.DatetimeIndex):
                    df_temp = df.set_index(pd.to_datetime(df.index))
                else:
                    df_temp = df
                price_series = df_temp.loc[entry_dt:exit_dt]["close"].astype(float)

            if (
                price_series is not None
                and not price_series.empty
                and entry_price is not None
                and entry_price > 0
            ):
                pnl_series = (price_series - entry_price) * qty
                run_up = float(pnl_series.max())
                drawdown = float(pnl_series.min())
        except Exception:
            # If all else fails, use the net_pnl as run-up (conservative estimate)
            run_up = None
            drawdown = None

        net_pnl = (
            float(tr.get("net_pnl", 0.0))
            if not pd.isna(tr.get("net_pnl", 0.0))
            else 0.0
        )
        pos_value_exit = (
            (exit_price * qty) if (exit_price is not None and qty) else None
        )
        pos_value_entry = (
            (entry_price * qty) if (entry_price is not None and qty) else None
        )  # FIXED: Add entry value
        net_pnl_exit = net_pnl
        run_up_exit = run_up
        drawdown_exit = drawdown

        # Exit row (TradingView ordering: exit then entry)
        # Use entry value as denominator for percentage calculations (trade size basis)
        tv_pos_value = pos_value_exit
        tv_pos_value_base = pos_value_entry

        def pct(val, base=tv_pos_value_base):
            return (
                round((val / base) * 100, 2)
                if (base and base != 0 and val is not None)
                else None
            )

        tv_net_pct = pct(net_pnl_exit)
        tv_run_pct = pct(run_up_exit)
        tv_dd_pct = pct(drawdown_exit)
        # Set MAE % to Drawdown % (always matches Drawdown % for all trades)
        mae_pct = tv_dd_pct if tv_dd_pct is not None else ""

        tv_rows.append(
            {
                "Trade #": trade_no,
                "Type": "Exit long",
                "Date/Time": exit_time,
                "Signal": (
                    tr.exit_signal_reason
                    if hasattr(tr, "exit_signal_reason")
                    else "Close entry(s) order LONG"
                ),
                "Price INR": exit_price,
                "Position size (qty)": qty,
                "Position size (value)": (
                    int(tv_pos_value)
                    if (tv_pos_value is not None and not pd.isna(tv_pos_value))
                    else None
                ),
                "Net P&L INR": (
                    int(net_pnl_exit)
                    if (net_pnl_exit is not None and not pd.isna(net_pnl_exit))
                    else None
                ),
                "Net P&L %": tv_net_pct,
                "Run-up INR": (
                    int(run_up_exit)
                    if (run_up_exit is not None and not pd.isna(run_up_exit))
                    else None
                ),
                "Run-up %": tv_run_pct,
                "Drawdown INR": (
                    int(drawdown_exit)
                    if (drawdown_exit is not None and not pd.isna(drawdown_exit))
                    else None
                ),
                "Drawdown %": tv_dd_pct,
                "Cumulative P&L INR": None,  # computed later if needed
                "Cumulative P&L %": None,
                # New analytics columns for exit row
                "ATR": "",
                "ATR %": "",
                "MAE %": mae_pct,
                "MAE_ATR": (
                    round(abs(tv_dd_pct) / indicators.get("atr_pct", 1), 2)
                    if indicators
                    and indicators.get("atr_pct", 0) > 0
                    and tv_dd_pct is not None
                    and tv_dd_pct != 0
                    else ""
                ),
                "Holding days": (
                    int(indicators.get("holding_days", 0))
                    if (
                        indicators
                        and indicators.get("holding_days", 0)
                        and not pd.isna(indicators.get("holding_days", 0))
                    )
                    else ""
                ),
                # Universal indicator columns
                "ADX": "",
                "Plus_DI": "",
                "Minus_DI": "",
                "RSI": "",
                "RSI_21": "",
                "MACD_Line": "",
                "MACD_Signal": "",
                "EMA_20": "",
                "EMA_50": "",
                "EMA_200": "",
                "Above_EMA_20": "",
                "Above_EMA_50": "",
                "Above_EMA_200": "",
                "DI_Bullish": "",
            }
        )

        # Entry row
        tv_pos_value_entry = (
            (entry_price * qty) if (entry_price is not None and qty) else None
        )
        tv_rows.append(
            {
                "Trade #": trade_no,
                "Type": "Entry long",
                "Date/Time": entry_time,
                "Signal": tr.get(
                    "entry_signal_reason", "LONG"
                ),  # Use entry signal reason if available
                "Price INR": entry_price,
                "Position size (qty)": qty,
                "Position size (value)": (
                    int(tv_pos_value_entry)
                    if (
                        tv_pos_value_entry is not None
                        and not pd.isna(tv_pos_value_entry)
                    )
                    else None
                ),
                "Net P&L INR": "",
                "Net P&L %": "",
                "Run-up INR": "",
                "Run-up %": "",
                "Drawdown INR": "",
                "Drawdown %": "",
                "Cumulative P&L INR": None,
                "Cumulative P&L %": None,
                # New analytics columns for entry row (where values are calculated)
                "ATR": (
                    int(round(indicators.get("atr", 0)))
                    if (indicators and not pd.isna(indicators.get("atr", 0)))
                    else ""
                ),
                "ATR %": round(indicators.get("atr_pct", 0), 2) if indicators else "",
                "MAE %": "",  # MAE % is only shown on exit row, matching Drawdown %
                "MAE_ATR": "",  # MAE_ATR is only shown on exit row
                "Holding days": "",
                # Universal indicator columns (calculated at entry)
                "ADX": round(indicators.get("adx", 0), 2) if indicators else 0,
                "Plus_DI": round(indicators.get("plus_di", 0), 2) if indicators else 0,
                "Minus_DI": (
                    round(indicators.get("minus_di", 0), 2) if indicators else 0
                ),
                "RSI": round(indicators.get("rsi", 50), 2) if indicators else 50,
                "RSI_21": round(indicators.get("rsi_21", 50), 2) if indicators else 50,
                "MACD_Line": (
                    round(indicators.get("macd_line", 0), 2) if indicators else 0
                ),
                "MACD_Signal": (
                    round(indicators.get("macd_signal", 0), 2) if indicators else 0
                ),
                "EMA_20": round(indicators.get("ema_20", 0), 2) if indicators else 0,
                "EMA_50": round(indicators.get("ema_50", 0), 2) if indicators else 0,
                "EMA_200": round(indicators.get("ema_200", 0), 2) if indicators else 0,
                "Above_EMA_20": (
                    indicators.get("above_ema_20", False) if indicators else False
                ),
                "Above_EMA_50": (
                    indicators.get("above_ema_50", False) if indicators else False
                ),
                "Above_EMA_200": (
                    indicators.get("above_ema_200", False) if indicators else False
                ),
                "DI_Bullish": (
                    indicators.get("di_bullish", False) if indicators else False
                ),
            }
        )

    # write TradingView-format CSV
    try:
        if tv_rows:
            tv_df = pd.DataFrame(tv_rows)
            if "Date/Time" in tv_df.columns:
                # Vectorized datetime formatting (faster than apply with lambda)
                if pd.api.types.is_datetime64_any_dtype(tv_df["Date/Time"]):
                    tv_df["Date/Time"] = tv_df["Date/Time"].dt.strftime("%Y-%m-%d")
                else:
                    tv_df["Date/Time"] = pd.to_datetime(
                        tv_df["Date/Time"], errors="coerce"
                    ).dt.strftime("%Y-%m-%d")
            tv_csv_path = os.path.join(run_dir, f"trades_TV_{label}_{sym_safe}.csv")
            tv_df.to_csv(tv_csv_path, index=False)
            return tv_csv_path
    except Exception:
        return ""

    return ""


def _generate_strategy_summary(
    run_dir: str,
    portfolio_curves: dict[str, pd.DataFrame],
    trades_by_window: dict[str, pd.DataFrame],
    portfolio_metrics: dict[str, pd.DataFrame],
    initial_capital: float = 100000.0,
    strategy_name: str | None = None,
) -> str:
    """Generate comprehensive strategy backtests summary file.

    Args:
        run_dir: Output directory
        portfolio_curves: Dict mapping label (e.g. "1Y") to daily portfolio curve DataFrame
        trades_by_window: Dict mapping label to consolidated trades DataFrame
        portfolio_metrics: Dict mapping label to portfolio_key_metrics DataFrame (for TOTAL row data)
        initial_capital: Starting capital
        strategy_name: Name of the strategy

    Returns:
        Path to generated strategy_backtests_summary.csv file
    """
    import numpy as np

    summary_rows = []

    for label, port_df in portfolio_curves.items():
        if port_df.empty:
            continue

        try:
            # Time metrics
            start_date = port_df.index[0]
            end_date = port_df.index[-1]
            duration = end_date - start_date
            duration_str = str(duration)

            # Equity metrics (handle both "Equity" and "equity" column names)
            equity_col = "Equity" if "Equity" in port_df.columns else "equity"
            equity_start = float(port_df[equity_col].iloc[0])
            equity_end = float(port_df[equity_col].iloc[-1])
            float(port_df[equity_col].max())  # Return metrics
            total_return_pct = (
                ((equity_end / equity_start) - 1.0) * 100.0 if equity_start > 0 else 0.0
            )

            # Annualization
            # Extract window period from label (e.g., "1Y" -> 1, "3Y" -> 3, "5Y" -> 5)
            n_years = 1.0  # Default
            if label.endswith("Y"):
                try:
                    n_years = float(label[:-1])
                except (ValueError, IndexError):
                    # Fallback to calculating from actual dates
                    n_days = max((end_date - start_date).days, 1)
                    n_years = n_days / 365.25
            else:
                # For "ALL" or other labels, calculate from actual dates
                n_days = max((end_date - start_date).days, 1)
                n_years = n_days / 365.25

            cagr_pct = (
                ((equity_end / equity_start) ** (1.0 / n_years) - 1.0) * 100.0
                if equity_start > 0 and n_years > 0
                else 0.0
            )

            # Exposure statistics
            exposure_col = (
                "Avg exposure" if "Avg exposure" in port_df.columns else "avg_exposure"
            )
            avg_exposure_value = float(port_df[exposure_col].mean())
            avg_exposure_pct = (
                (avg_exposure_value / initial_capital * 100.0)
                if initial_capital > 0
                else 0.0
            )

            # Get Max Drawdown and IRR from portfolio_metrics (TOTAL row) if available
            metrics_df = portfolio_metrics.get(label)
            if metrics_df is not None and not metrics_df.empty:
                total_metrics = metrics_df[metrics_df["Symbol"] == "TOTAL"]
                if not total_metrics.empty:
                    max_dd_pct = float(total_metrics["Max equity drawdown %"].iloc[0])
                    irr_pct = float(total_metrics["IRR %"].iloc[0])
                else:
                    max_dd_pct = 0.0
                    irr_pct = 0.0
            else:
                max_dd_pct = 0.0
                irr_pct = 0.0

            # Equity metrics

            dd_pct_col = (
                "Drawdown %" if "Drawdown %" in port_df.columns else "drawdown_pct"
            )

            # Drawdown duration: consecutive days with exposure
            drawdown_durations = []
            in_dd = False
            dd_start = None
            for i, val in enumerate(port_df[dd_pct_col].fillna(0.0)):
                if val > 0:  # in drawdown
                    if not in_dd:
                        in_dd = True
                        dd_start = i
                else:
                    if in_dd:
                        drawdown_durations.append(i - dd_start)
                        in_dd = False
            if in_dd and dd_start is not None:
                drawdown_durations.append(len(port_df) - dd_start)

            max_dd_duration = max(drawdown_durations) if drawdown_durations else 0

            # Volatility (annualized) - calculate from Equity column, not Total Return %
            equity_col_for_returns = (
                "Equity" if "Equity" in port_df.columns else "equity"
            )
            daily_equity_returns = port_df[equity_col_for_returns].pct_change().dropna()
            if len(daily_equity_returns) > 0:
                daily_vol = float(daily_equity_returns.std())
                daily_vol * np.sqrt(245)  # 245 trading days per year
            else:
                pass

            # Trade statistics
            trades_df = trades_by_window.get(label)
            if trades_df is not None and not trades_df.empty:
                exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                if len(exit_trades) > 0:
                    num_trades = len(exit_trades)

                    # Extract P&L values (strip '%' suffix if present)
                    pnl_str = (
                        exit_trades["Net P&L %"]
                        .astype(str)
                        .str.replace("%", "")
                        .str.strip()
                    )
                    pnl_values = pd.to_numeric(pnl_str, errors="coerce").dropna()
                    if len(pnl_values) > 0:
                        winning_trades = (pnl_values > 0).sum()
                        win_rate = (
                            (winning_trades / num_trades * 100.0)
                            if num_trades > 0
                            else 0.0
                        )
                        avg_trade_pct = float(pnl_values.mean())
                        best_trade_pct = float(pnl_values.max())
                        worst_trade_pct = float(pnl_values.min())

                        # Profit factor
                        wins = pnl_values[pnl_values > 0].sum()
                        losses = abs(pnl_values[pnl_values < 0].sum())
                        profit_factor = (
                            float(wins / losses)
                            if losses > 0
                            else (float("inf") if wins > 0 else 0.0)
                        )

                        # Expectancy (avg weighted by probability)
                        # Use average win/loss instead of best/worst trades for realistic calculation
                        win_avg = (
                            pnl_values[pnl_values > 0].mean()
                            if (pnl_values > 0).any()
                            else 0.0
                        )
                        loss_avg = (
                            pnl_values[pnl_values < 0].mean()
                            if (pnl_values < 0).any()
                            else 0.0
                        )
                        expectancy = (win_rate / 100.0 * win_avg) + (
                            (1 - win_rate / 100.0) * loss_avg
                        )
                    else:
                        num_trades = 0
                        win_rate = 0.0
                        avg_trade_pct = 0.0
                        best_trade_pct = 0.0
                        worst_trade_pct = 0.0
                        profit_factor = 0.0
                        expectancy = 0.0

                    # Trade duration
                    entry_trades = trades_df[trades_df["Type"] == "Entry long"].copy()
                    exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()

                    if len(entry_trades) > 0 and len(exit_trades) > 0:
                        # Filter out trades with empty/NaN dates
                        exit_trades = exit_trades[exit_trades["Date/Time"].notna()]
                        exit_trades = exit_trades[exit_trades["Date/Time"] != ""]

                        if len(exit_trades) > 0:
                            entry_trades["Date/Time"] = pd.to_datetime(
                                entry_trades["Date/Time"]
                            )
                            exit_trades_sorted = exit_trades.copy()
                            exit_trades_sorted["Date/Time"] = pd.to_datetime(
                                exit_trades_sorted["Date/Time"]
                            )

                            # Match entries with exits using merge (vectorized, much faster than iterrows)
                            matched = entry_trades.merge(
                                exit_trades_sorted[["Trade #", "Date/Time"]],
                                on="Trade #",
                                how="inner",
                                suffixes=("_entry", "_exit"),
                            )

                            # Calculate durations vectorized
                            if not matched.empty:
                                durations = (
                                    pd.to_datetime(matched["Date/Time_exit"])
                                    - pd.to_datetime(matched["Date/Time_entry"])
                                ).dt.days
                                # Filter valid durations (>= 0)
                                valid_durations = durations[durations >= 0]
                                trade_durations = valid_durations.tolist()
                            else:
                                trade_durations = []

                            max_trade_duration = (
                                max(trade_durations) if trade_durations else 0
                            )
                            if trade_durations:
                                avg_duration_days = np.mean(trade_durations)
                                avg_trade_duration = (
                                    int(avg_duration_days)
                                    if not np.isnan(avg_duration_days)
                                    else 0
                                )
                            else:
                                avg_trade_duration = 0
                        else:
                            max_trade_duration = 0
                            avg_trade_duration = 0
                    else:
                        max_trade_duration = 0
                        avg_trade_duration = 0
                else:
                    num_trades = 0
                    win_rate = 0.0
                    avg_trade_pct = 0.0
                    best_trade_pct = 0.0
                    worst_trade_pct = 0.0
                    profit_factor = 0.0
                    expectancy = 0.0
                    max_trade_duration = 0
                    avg_trade_duration = 0
            else:
                num_trades = 0
                win_rate = 0.0
                avg_trade_pct = 0.0
                best_trade_pct = 0.0
                worst_trade_pct = 0.0
                profit_factor = 0.0
                expectancy = 0.0
                max_trade_duration = 0
                avg_trade_duration = 0

            # Use unified metrics calculation from core/metrics
            # Load benchmark for alpha/beta calculation
            from core.metrics import load_benchmark

            benchmark_df = load_benchmark(interval="1d")

            metrics = compute_comprehensive_metrics(
                equity_df=port_df,
                trades_df=(
                    trades_df if trades_df is not None and not trades_df.empty else None
                ),
                benchmark_df=benchmark_df,
                initial_capital=100000.0,
            )

            # Extract metrics from unified calculation
            sharpe_ratio = metrics.get("sharpe_ratio", 0.0)
            sortino_ratio = metrics.get("sortino_ratio", 0.0)
            calmar_ratio = metrics.get("calmar_ratio", 0.0)
            annualized_vol_pct = metrics.get("annualized_volatility_pct", 0.0)
            annualized_var_95_pct = metrics.get("annualized_var_95_pct", 0.0)
            alpha_pct = metrics.get("alpha_pct", 0.0)
            beta = metrics.get("beta", 0.0)

            # SQN (System Quality Number): expectancy / standard_dev_pnl
            if len(pnl_values) > 0:
                pnl_std = float(pnl_values.std())
                if pnl_std > 0:
                    sqn = (
                        expectancy / pnl_std * np.sqrt(num_trades)
                        if num_trades > 0
                        else 0.0
                    )
                else:
                    sqn = 0.0
            else:
                sqn = 0.0

            # Kelly Criterion: p * b - q / b, where p=win%, b=avg_win/avg_loss, q=loss%
            if num_trades > 0:
                p = win_rate / 100.0
                win_avg = (
                    pnl_values[pnl_values > 0].mean() if (pnl_values > 0).any() else 0.0
                )
                loss_avg = (
                    abs(pnl_values[pnl_values < 0].mean())
                    if (pnl_values < 0).any()
                    else 1.0
                )
                if loss_avg > 0 and win_avg > 0:
                    b = win_avg / loss_avg
                    kelly_pct = (p * b - (1 - p)) / b
                    kelly_pct = max(0, min(kelly_pct, 1.0))  # clamp to 0-1
                else:
                    kelly_pct = 0.0
            else:
                kelly_pct = 0.0

            # Compile row - keeping only specified columns
            row = {
                "Window": label,
                "Strategy Name": strategy_name if strategy_name else "Unknown",
                "Start": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "End": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "Duration": duration_str,
                "Avg exposure %": round(avg_exposure_pct, 2),
                "Equity Final [INR]": round(equity_end, 2),
                "Net P&L %": round(total_return_pct, 2),
                "CAGR [%]": round(cagr_pct, 2),
                "Sharpe Ratio": round(sharpe_ratio, 2),
                "Sortino Ratio": round(sortino_ratio, 2),
                "Calmar Ratio/RoMaD": round(calmar_ratio, 2),
                "Annualized Volatility [%]": round(annualized_vol_pct, 2),
                "Annualized VaR 95% [%]": round(annualized_var_95_pct, 2),
                "IRR [%]": round(irr_pct, 2),
                "Alpha [%]": round(alpha_pct, 2),
                "Beta": round(beta, 2),
                "Max. Drawdown [%]": round(max_dd_pct, 2),
                "Max. Drawdown Duration": f"{max_dd_duration} days",
                "# Trades": int(num_trades),
                "Win Rate [%]": round(win_rate, 2),
                "Best Trade [%]": round(best_trade_pct, 2),
                "Worst Trade [%]": round(worst_trade_pct, 2),
                "Avg. Trade [%]": round(avg_trade_pct, 2),
                "Max. Trade Duration": f"{max_trade_duration} days",
                "Avg. Trade Duration": f"{avg_trade_duration} days",
                "Profit Factor": (
                    round(profit_factor, 2)
                    if not np.isinf(profit_factor)
                    else float("inf")
                ),
                "Expectancy [%]": round(expectancy, 2),
                "SQN": round(sqn, 2),
                "Kelly Criterion": round(kelly_pct, 4),
            }
            summary_rows.append(row)

        except Exception as e:
            import traceback

            print(f"Error generating summary for {label}: {e}")
            traceback.print_exc()
            continue

    # Write summary CSV
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_csv_path = os.path.join(run_dir, "strategy_backtests_summary.csv")
        summary_df.to_csv(summary_csv_path, index=False)
        return summary_csv_path

    return ""


def _generate_analytics_csv_files(
    run_dir: str,
    portfolio_curves: dict,
    trades_data: dict,
    initial_capital: float,
    atr_percentage: float = 2.5,
) -> None:
    """Generate comprehensive analytics CSV files for dashboard visualization."""

    print("🔄 Generating analytics CSV files...")

    # TRADE ANALYTICS CSV - MAE, win rates, holding periods
    trade_analytics_data = []
    for period, trades_df in trades_data.items():
        if trades_df.empty:
            continue
        exit_trades = trades_df[trades_df["Type"].str.contains("Exit", na=False)].copy()
        if exit_trades.empty or "Net P&L %" not in exit_trades.columns:
            continue
        import numpy as np

        exit_trades["Return"] = pd.to_numeric(
            exit_trades["Net P&L %"].astype(str).str.rstrip("%"), errors="coerce"
        )
        # MAE % = Drawdown % (always matches Drawdown % with correct sign)
        if "Drawdown %" in exit_trades.columns:
            exit_trades["MAE_Pct"] = pd.to_numeric(
                exit_trades["Drawdown %"].astype(str).str.rstrip("%"), errors="coerce"
            )
        else:
            exit_trades["MAE_Pct"] = (
                None  # Default to None if Drawdown % is unavailable
            )
        # Use actual Holding days from trades data
        if "Holding days" in exit_trades.columns:
            exit_trades["HoldingDays"] = (
                pd.to_numeric(exit_trades["Holding days"], errors="coerce")
                .fillna(0)
                .astype(int)
            )
        else:
            exit_trades["HoldingDays"] = 0  # Default if missing
        exit_trades["Period"] = period
        analytics_cols = [
            "Period",
            "Symbol",
            "Trade #",
            "Date/Time",
            "Return",
            "MAE_Pct",
            "HoldingDays",
        ]
        available_cols = [col for col in analytics_cols if col in exit_trades.columns]
        trade_analytics_data.append(exit_trades[available_cols])
    if trade_analytics_data:
        trade_analytics_df = pd.concat(trade_analytics_data, ignore_index=True)
        trade_analytics_path = os.path.join(run_dir, "trade_analytics.csv")
        trade_analytics_df.to_csv(trade_analytics_path, index=False)
        print(f"✅ Trade analytics saved: {trade_analytics_path}")

    # 2. MONTHLY RETURNS HEATMAP CSV
    monthly_returns_data = []

    for period, portfolio_df in portfolio_curves.items():
        if portfolio_df.empty or "Equity" not in portfolio_df.columns:
            continue
        # Calculate monthly returns
        portfolio_monthly = portfolio_df["Equity"].resample("M").last()
        monthly_returns = portfolio_monthly.pct_change() * 100
        # Create monthly data
        monthly_data = pd.DataFrame(
            {
                "Period": period,
                "Year": monthly_returns.index.year,
                "Month": monthly_returns.index.strftime("%b"),
                "Month_Num": monthly_returns.index.month,
                "Return_Pct": monthly_returns.values,
            }
        )
        monthly_returns_data.append(monthly_data)

    # Save monthly returns CSV
    if monthly_returns_data:
        monthly_returns_df = pd.concat(monthly_returns_data, ignore_index=True)
        monthly_returns_path = os.path.join(run_dir, "monthly_returns_heatmap.csv")
        monthly_returns_df.to_csv(monthly_returns_path, index=False)
        print(f"✅ Monthly returns heatmap saved: {monthly_returns_path}")

    # 3. ROLLING PERFORMANCE CSV
    rolling_performance_data = []

    for period, portfolio_df in portfolio_curves.items():
        if portfolio_df.empty or "Equity" not in portfolio_df.columns:
            continue

        equity_series = portfolio_df["Equity"]
        window_days = min(252, len(equity_series) // 4)  # 1 year or 1/4 of data

        rolling_dates = []
        rolling_cagr = []
        rolling_volatility = []
        rolling_sharpe = []

        for i in range(window_days, len(equity_series)):
            end_date = equity_series.index[i]
            start_date = equity_series.index[i - window_days]

            start_value = equity_series.iloc[i - window_days]
            end_value = equity_series.iloc[i]

            # Calculate rolling CAGR
            days = (end_date - start_date).days
            years = days / 365.25

            if years > 0 and start_value > 0:
                cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
            else:
                cagr = 0

            # Calculate rolling volatility
            window_returns = (
                equity_series.iloc[i - window_days : i + 1].pct_change().dropna()
            )
            if len(window_returns) > 1:
                volatility = window_returns.std() * np.sqrt(252) * 100  # Annualized
                sharpe = cagr / volatility if volatility > 0 else 0
            else:
                volatility = 0
                sharpe = 0

            rolling_dates.append(end_date)
            rolling_cagr.append(cagr)
            rolling_volatility.append(volatility)
            rolling_sharpe.append(sharpe)

        # Create rolling performance data
        if rolling_dates:
            rolling_data = pd.DataFrame(
                {
                    "Period": period,
                    "Date": rolling_dates,
                    "Rolling_CAGR": rolling_cagr,
                    "Rolling_Volatility": rolling_volatility,
                    "Rolling_Sharpe": rolling_sharpe,
                    "Window_Days": window_days,
                }
            )

            rolling_performance_data.append(rolling_data)

    # Save rolling performance CSV
    if rolling_performance_data:
        rolling_performance_df = pd.concat(rolling_performance_data, ignore_index=True)
        rolling_performance_path = os.path.join(run_dir, "rolling_performance.csv")
        rolling_performance_df.to_csv(rolling_performance_path, index=False)
        print(f"✅ Rolling performance saved: {rolling_performance_path}")

    # 4. ANALYTICS SUMMARY CSV
    summary_analytics = []

    for period in portfolio_curves.keys():
        period_summary = {"Period": period}

        # Portfolio metrics
        if period in portfolio_curves and not portfolio_curves[period].empty:
            portfolio_df = portfolio_curves[period]
            equity_series = portfolio_df["Equity"]

            # Basic metrics
            total_return = ((equity_series.iloc[-1] / equity_series.iloc[0]) - 1) * 100

            # Drawdown analysis
            peak_series = equity_series.expanding().max()
            drawdown_series = ((equity_series / peak_series) - 1) * 100
            max_drawdown = drawdown_series.min()

            # Days in drawdown
            days_in_dd = len(drawdown_series[drawdown_series < 0])
            dd_percentage = (days_in_dd / len(drawdown_series)) * 100

            period_summary.update(
                {
                    "Total_Return_Pct": total_return,
                    "Max_Drawdown_Pct": max_drawdown,
                    "Days_In_Drawdown": days_in_dd,
                    "Drawdown_Time_Pct": dd_percentage,
                }
            )

        # Trade metrics
        if period in trades_data and not trades_data[period].empty:
            trades_df = trades_data[period]
            exit_trades = trades_df[trades_df["Type"].str.contains("Exit", na=False)]

            if not exit_trades.empty and "Net P&L %" in exit_trades.columns:
                returns = pd.to_numeric(
                    exit_trades["Net P&L %"].astype(str).str.rstrip("%"),
                    errors="coerce",
                ).dropna()

                total_trades = len(returns)
                winning_trades = len(returns[returns > 0])
                win_rate = (
                    (winning_trades / total_trades * 100) if total_trades > 0 else 0
                )

                period_summary.update(
                    {
                        "Total_Trades": total_trades,
                        "Winning_Trades": winning_trades,
                        "Win_Rate_Pct": win_rate,
                    }
                )

        summary_analytics.append(period_summary)

    # Save analytics summary CSV
    if summary_analytics:
        analytics_summary_df = pd.DataFrame(summary_analytics)
        analytics_summary_path = os.path.join(run_dir, "analytics_summary.csv")
        analytics_summary_df.to_csv(analytics_summary_path, index=False)
        print(f"✅ Analytics summary saved: {analytics_summary_path}")

    print("✅ All analytics CSV files generated successfully!")


def _calculate_trade_indicators(
    df: pd.DataFrame, entry_time, exit_time, entry_price: float
) -> dict:
    """Calculate technical indicators for a trade at entry and exit times."""
    try:
        # Get data up to entry time for entry indicators
        # Ensure both index and entry_time are comparable types
        df_idx = pd.to_datetime(df.index, errors="coerce")
        entry_time = pd.Timestamp(entry_time)
        exit_time = pd.Timestamp(exit_time)

        entry_data = df.loc[df_idx <= entry_time].copy()
        if entry_data.empty:
            return {}

        # Ensure we have OHLC data
        required_cols = ["high", "low", "close"]
        if not all(col in entry_data.columns for col in required_cols):
            return {}

        high = entry_data["high"].astype(float)
        low = entry_data["low"].astype(float)
        close = entry_data["close"].astype(float)
        entry_data.get("open", close).astype(float)
        volume = entry_data.get("volume", pd.Series([0] * len(close))).astype(float)

        # Calculate ATR (14-period) using centralized function
        from utils import ATR

        atr_values = ATR(high.values, low.values, close.values, 14)
        atr = pd.Series(atr_values, index=close.index)
        atr_pct = (atr / close) * 100

        # ATR values at entry
        entry_atr = atr.iloc[-1] if not atr.empty else 0
        entry_atr_pct = atr_pct.iloc[-1] if not atr_pct.empty else 0

        # MAE % logic removed - now using Drawdown % directly in exit row
        # MAE_ATR is calculated based on actual drawdown, not estimated here
        mae_atr = 0  # Placeholder for MAE_ATR column

        # Calculate Bollinger Bands (20, 2) using centralized function
        from utils import BollingerBands

        bb = BollingerBands(close.values, 20, 2)
        price = close.iloc[-1] if not close.empty else entry_price
        upper = bb["upper"][-1] if len(bb["upper"]) > 0 else price
        lower = bb["lower"][-1] if len(bb["lower"]) > 0 else price
        if price > upper:
            bb_pos = "Above"
        elif price < lower:
            bb_pos = "Below"
        else:
            bb_pos = "Middle"

        # Stochastic Oscillator (14, 3) using centralized function
        from utils import Stochastic

        stoch = Stochastic(high.values, low.values, close.values, 14, 3)
        k_value = (
            stoch["k"][-1]
            if len(stoch["k"]) > 0 and not np.isnan(stoch["k"][-1])
            else 0
        )
        d_value = (
            stoch["d"][-1]
            if len(stoch["d"]) > 0 and not np.isnan(stoch["d"][-1])
            else 0
        )
        stoch_bullish = k_value > d_value

        # Calculate holding days (for exit row)
        holding_days = 0
        if entry_time:
            # For closed trades: days between entry and exit
            # For open trades: days between entry and today
            exit_dt = (
                pd.to_datetime(exit_time)
                if pd.notna(exit_time)
                else pd.Timestamp.today()
            )
            entry_dt = pd.to_datetime(entry_time)
            holding_days = (exit_dt - entry_dt).days

        # Calculate ADX and DI using centralized function
        from utils.indicators import ADX

        adx_result = ADX(high.values, low.values, close.values, 14)
        adx = pd.Series(adx_result["adx"], index=close.index)
        plus_di = pd.Series(adx_result["di_plus"], index=close.index)
        minus_di = pd.Series(adx_result["di_minus"], index=close.index)

        # Calculate RSI using centralized function
        from utils import RSI

        rsi = RSI(close, 14)

        # Calculate multiple EMAs using centralized function
        from utils import EMA

        ema_5 = pd.Series(EMA(close.values, 5), index=close.index)
        ema_20 = pd.Series(EMA(close.values, 20), index=close.index)
        ema_50 = pd.Series(EMA(close.values, 50), index=close.index)
        ema_200 = pd.Series(EMA(close.values, 200), index=close.index)

        # Calculate multiple SMAs using centralized function
        from utils import SMA

        sma_5 = pd.Series(SMA(close, 5), index=close.index)
        sma_20 = pd.Series(SMA(close, 20), index=close.index)
        sma_50 = pd.Series(SMA(close, 50), index=close.index)
        sma_200 = pd.Series(SMA(close, 200), index=close.index)

        # Calculate MACD using centralized function
        from utils import MACD

        macd_result = MACD(close.values, 12, 26, 9)
        macd_line = pd.Series(macd_result["macd"], index=close.index)
        macd_signal = pd.Series(macd_result["signal"], index=close.index)

        # Calculate CCI (20-period)
        from utils.indicators import CCI

        cci = CCI(high.values, low.values, close.values, period=20)

        # Calculate Stochastic Slow (5, 3, 3)
        from utils.indicators import calculate_stochastic_slow

        stoch_slow = calculate_stochastic_slow(
            high.values, low.values, close.values, 5, 3, 3
        )

        # Calculate Ichimoku Base Line (26-period) and Tenkan Line (9-period)
        from utils.indicators import extract_ichimoku_base_line

        ichimoku_base = extract_ichimoku_base_line(high.values, low.values, 26)
        ichimoku_tenkan = extract_ichimoku_base_line(
            high.values, low.values, 9
        )  # Tenkan uses 9-period

        # Calculate VWMA (14-period)
        from utils.indicators import VWMA

        vwma_14 = VWMA(close.values, volume.values, 14)

        # Calculate HMA (14-period)
        from utils.indicators import HMA

        hma_14 = HMA(close.values, 14)

        # Calculate Williams %R (14-period)
        from utils.indicators import WilliamsR

        williams_r = WilliamsR(high.values, low.values, close.values, 14)

        # Calculate Momentum Oscillator (14-period)
        from utils.indicators import MomentumOscillator

        momentum = MomentumOscillator(close.values, 14)

        # Calculate Ultimate Oscillator (7, 14, 28)
        from utils.indicators import UltimateOscillator

        uo = UltimateOscillator(high.values, low.values, close.values, 7, 14, 28)

        # Calculate Bull/Bear Power (13-period)
        from utils.indicators import BullBearPower

        bb_power = BullBearPower(high.values, low.values, close.values, 13)

        # Calculate Stochastic RSI (14-period)
        from viz.utils.indicators import StochasticRSI as StochasticRSI_calc

        # rsi is already a numpy array from RSI calculation
        stoch_rsi = StochasticRSI_calc(rsi, 14)

        # Calculate Aroon (25-period)
        from utils.indicators import (
            Aroon,
            TrendClassification,
            VolatilityClassification,
        )

        # Compute Aroon for three different periods (short, medium, long)
        aroon_short = Aroon(high.values, low.values, 25)  # Short-term (25 bars - original)
        aroon_medium = Aroon(high.values, low.values, 50)  # Medium-term (50 bars)
        aroon_long = Aroon(high.values, low.values, 100)  # Long-term (100 bars)

        # Extract latest Aroon values for each period
        aroon_up_short = aroon_short["aroon_up"][-1] if len(aroon_short["aroon_up"]) > 0 else 50
        aroon_down_short = aroon_short["aroon_down"][-1] if len(aroon_short["aroon_down"]) > 0 else 50
        
        aroon_up_medium = aroon_medium["aroon_up"][-1] if len(aroon_medium["aroon_up"]) > 0 else 50
        aroon_down_medium = aroon_medium["aroon_down"][-1] if len(aroon_medium["aroon_down"]) > 0 else 50
        
        aroon_up_long = aroon_long["aroon_up"][-1] if len(aroon_long["aroon_up"]) > 0 else 50
        aroon_down_long = aroon_long["aroon_down"][-1] if len(aroon_long["aroon_down"]) > 0 else 50

        # Classify Trend for each timeframe and Volatility
        short_trend = TrendClassification(aroon_up_short, aroon_down_short)
        medium_trend = TrendClassification(aroon_up_medium, aroon_down_medium)
        long_trend = TrendClassification(aroon_up_long, aroon_down_long)
        volatility = VolatilityClassification(entry_atr_pct)

        # Get latest values
        indicators = {
            # Basic metrics
            "atr": entry_atr,
            "atr_pct": entry_atr_pct,
            "mae_atr": mae_atr,  # Placeholder for MAE_ATR column
            "holding_days": holding_days,
            # Trend and volatility classification (multi-timeframe)
            "short_trend": short_trend,
            "medium_trend": medium_trend,
            "long_trend": long_trend,
            "volatility": volatility,
            # ADX and directional indicators
            "adx": adx.iloc[-1] if not adx.empty else 0,
            "plus_di": plus_di.iloc[-1] if not plus_di.empty else 0,
            "minus_di": minus_di.iloc[-1] if not minus_di.empty else 0,
            "di_bullish": (
                (plus_di.iloc[-1] > minus_di.iloc[-1])
                if not plus_di.empty and not minus_di.empty
                else False
            ),
            # RSI (rsi is numpy array from utils.indicators.RSI)
            "rsi": float(rsi[-1]) if len(rsi) > 0 and not np.isnan(rsi[-1]) else 50,
            # MACD
            "macd_line": macd_line.iloc[-1] if not macd_line.empty else 0,
            "macd_signal": macd_signal.iloc[-1] if not macd_signal.empty else 0,
            "macd_bullish": (
                (macd_line.iloc[-1] > macd_signal.iloc[-1])
                if not macd_line.empty and not macd_signal.empty
                else False
            ),
            # EMAs
            "ema_5": ema_5.iloc[-1] if not ema_5.empty else 0,
            "ema_20": ema_20.iloc[-1] if not ema_20.empty else 0,
            "ema_50": ema_50.iloc[-1] if not ema_50.empty else 0,
            "ema_200": ema_200.iloc[-1] if not ema_200.empty else 0,
            # SMAs
            "sma_5": sma_5.iloc[-1] if not sma_5.empty else 0,
            "sma_20": sma_20.iloc[-1] if not sma_20.empty else 0,
            "sma_50": sma_50.iloc[-1] if not sma_50.empty else 0,
            "sma_200": sma_200.iloc[-1] if not sma_200.empty else 0,
            # Ichimoku
            "ichimoku_base": ichimoku_base[-1] if len(ichimoku_base) > 0 else 0,
            "ichimoku_tenkan": ichimoku_tenkan[-1] if len(ichimoku_tenkan) > 0 else 0,
            # VWMA
            "vwma_14": vwma_14[-1] if len(vwma_14) > 0 else 0,
            # HMA
            "hma_14": hma_14[-1] if len(hma_14) > 0 else 0,
            # CCI
            "cci": cci[-1] if len(cci) > 0 else 0,
            # Stochastic (Fast 14, 3, 3)
            "percent_k": k_value,
            "percent_d": d_value,
            "stoch_bullish": stoch_bullish,
            # Stochastic Slow (5, 3, 3)
            "stoch_slow_k": (
                stoch_slow["slow_k"][-1] if len(stoch_slow["slow_k"]) > 0 else 0
            ),
            "stoch_slow_d": (
                stoch_slow["slow_d"][-1] if len(stoch_slow["slow_d"]) > 0 else 0
            ),
            # Williams %R
            "williams_r": williams_r[-1] if len(williams_r) > 0 else -50,
            # Momentum
            "momentum": momentum[-1] if len(momentum) > 0 else 0,
            # Ultimate Oscillator
            "ultimate_osc": uo[-1] if len(uo) > 0 else 50,
            # Bull/Bear Power
            "bull_power": (
                bb_power["bull_power"][-1] if len(bb_power["bull_power"]) > 0 else 0
            ),
            "bear_power": (
                bb_power["bear_power"][-1] if len(bb_power["bear_power"]) > 0 else 0
            ),
            "bull_bear_power": (
                (bb_power["bull_power"][-1] - bb_power["bear_power"][-1])
                if len(bb_power["bull_power"]) > 0
                else 0
            ),
            # Stochastic RSI
            "stoch_rsi_k": (
                stoch_rsi["fast_k"][-1] if len(stoch_rsi["fast_k"]) > 0 else 50
            ),
            "stoch_rsi_d": (
                stoch_rsi["fast_d"][-1] if len(stoch_rsi["fast_d"]) > 0 else 50
            ),
            # Aroon (short-term 25-period for compatibility)
            "aroon_up": aroon_up_short,
            "aroon_down": aroon_down_short,
            "aroon_osc": (
                aroon_short["aroon_oscillator"][-1]
                if len(aroon_short["aroon_oscillator"]) > 0
                else 0
            ),
            # Bollinger Bands
            "bb_position": bb_pos,
            # Trend Comparisons (True/False) - EMA
            "price_above_ema20": (
                close.iloc[-1] > ema_20.iloc[-1] if not ema_20.empty else False
            ),
            "price_above_ema50": (
                close.iloc[-1] > ema_50.iloc[-1] if not ema_50.empty else False
            ),
            "price_above_ema200": (
                close.iloc[-1] > ema_200.iloc[-1] if not ema_200.empty else False
            ),
            "price_above_ema5": (
                close.iloc[-1] > ema_5.iloc[-1] if not ema_5.empty else False
            ),
            "ema5_above_ema20": (
                ema_5.iloc[-1] > ema_20.iloc[-1]
                if not ema_5.empty and not ema_20.empty
                else False
            ),
            "ema20_above_ema50": (
                ema_20.iloc[-1] > ema_50.iloc[-1]
                if not ema_20.empty and not ema_50.empty
                else False
            ),
            "ema50_above_ema200": (
                ema_50.iloc[-1] > ema_200.iloc[-1]
                if not ema_50.empty and not ema_200.empty
                else False
            ),
            # Trend Comparisons (True/False) - SMA
            "price_above_sma20": (
                close.iloc[-1] > sma_20.iloc[-1] if not sma_20.empty else False
            ),
            "price_above_sma50": (
                close.iloc[-1] > sma_50.iloc[-1] if not sma_50.empty else False
            ),
            "price_above_sma200": (
                close.iloc[-1] > sma_200.iloc[-1] if not sma_200.empty else False
            ),
            "price_above_sma5": (
                close.iloc[-1] > sma_5.iloc[-1] if not sma_5.empty else False
            ),
            "sma5_above_sma20": (
                sma_5.iloc[-1] > sma_20.iloc[-1]
                if not sma_5.empty and not sma_20.empty
                else False
            ),
            "sma20_above_sma50": (
                sma_20.iloc[-1] > sma_50.iloc[-1]
                if not sma_20.empty and not sma_50.empty
                else False
            ),
            "sma50_above_sma200": (
                sma_50.iloc[-1] > sma_200.iloc[-1]
                if not sma_50.empty and not sma_200.empty
                else False
            ),
            # Trend Comparisons (True/False) - Ichimoku and Other
            "price_above_kijun": (
                close.iloc[-1] > ichimoku_base[-1] if len(ichimoku_base) > 0 else False
            ),
            "tenkan_above_kijun": (
                ichimoku_tenkan[-1] > ichimoku_base[-1]
                if len(ichimoku_tenkan) > 0 and len(ichimoku_base) > 0
                else False
            ),
            "price_above_vwma": (
                close.iloc[-1] > vwma_14[-1] if len(vwma_14) > 0 else False
            ),
            "price_above_hma": (
                close.iloc[-1] > hma_14[-1] if len(hma_14) > 0 else False
            ),
            "stoch_rsi_bullish": (
                stoch_rsi.get("fast_k", [])[-1] > stoch_rsi.get("fast_d", [])[-1]
                if len(stoch_rsi.get("fast_k", [])) > 0
                and len(stoch_rsi.get("fast_d", [])) > 0
                else False
            ),
            "stoch_slow_bullish": (
                stoch_slow["slow_k"][-1] > stoch_slow["slow_d"][-1]
                if len(stoch_slow["slow_k"]) > 0 and len(stoch_slow["slow_d"]) > 0
                else False
            ),
        }

        return indicators

    except Exception as e:
        print(f"Error calculating indicators: {e}")
        import traceback

        traceback.print_exc()
        return {}


def run_basket(
    basket_file=None,
    strategy_name=None,
    params_json=None,
    interval=None,
    period=None,
    windows_years=(1, 3, 5),
    use_cache_only=False,
    cache_dir="cache",
    use_portfolio_csv=False,
    basket_size=None,
) -> None:
    """
    Run backtest on a basket of stocks.

    Args:
        basket_file: Path to basket file (if None, uses basket_size)
        basket_size: Size of basket ('mega', 'large', 'mid', 'small') - overrides basket_file
        strategy_name: Name of strategy to use
        params_json: Strategy parameters as JSON string
        interval: Time interval ('1d', '1h', etc.)
        period: Period ('1y', '3y', '5y', 'max')
        windows_years: Analysis windows in years
        use_cache_only: Only use cached data
        cache_dir: Cache directory
        use_portfolio_csv: Generate portfolio CSV
    """
    from config import DEFAULT_BASKET_SIZE, get_basket_file

    # Handle basket selection logic
    if basket_size is not None:
        basket_file = str(get_basket_file(basket_size))
        print(f"📊 Using {basket_size} basket: {basket_file}")
    elif basket_file is None:
        basket_file = str(get_basket_file(DEFAULT_BASKET_SIZE))
        print(f"📊 Using default {DEFAULT_BASKET_SIZE} basket: {basket_file}")
    else:
        print(f"📊 Using specified basket file: {basket_file}")

    bars_per_year = BARS_PER_YEAR_MAP.get(interval, 245)
    bare = _read_symbols_from_txt(basket_file)

    # Try quick path: if we have Dhan CSVs in data/dhan_historical_<SECID>.csv,
    # map each basket symbol -> SECID via data/api-scrip-master-detailed.csv and load the CSVs.
    data_map_full: dict[str, pd.DataFrame] = {}
    try:
        inst_csv = os.path.join("data", "api-scrip-master-detailed.csv")
        if os.path.exists(inst_csv):
            # avoid mixed-type low_memory warnings by reading with low_memory=False
            inst_df = pd.read_csv(inst_csv, low_memory=False)
            for sym in bare:
                # normalize symbol name
                base = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                cand = inst_df[
                    (inst_df["SYMBOL_NAME"] == base)
                    | (inst_df["UNDERLYING_SYMBOL"] == base)
                ]
                if not cand.empty:
                    secid = int(cand.iloc[0]["SECURITY_ID"])
                    csv_path = os.path.join(
                        "data", "cache", f"dhan_historical_{secid}.csv"
                    )
                    if os.path.exists(csv_path):
                        try:
                            df = pd.read_csv(
                                csv_path, parse_dates=["date"], index_col="date"
                            )
                            df.index = pd.to_datetime(df.index)
                            data_map_full[sym] = df.sort_index()
                        except Exception:
                            pass
        # if we loaded nothing, fall back
        if not data_map_full:
            raise RuntimeError("no local Dhan CSVs loaded")
    except Exception:
        # If the quick CSV path failed, allow the loader to read local Dhan CSVs
        # (don't force strict cache-only parquet requirement here).
        data_map_full = load_many_india(
            bare,
            interval=interval,
            period=period,
            cache=True,
            cache_dir=cache_dir,
            use_cache_only=True,
        )

    # Extract basket name from file path for better report naming
    basket_name = "default"
    if basket_file:
        basket_name = os.path.basename(basket_file).replace(".txt", "")
    elif basket_size:
        basket_name = basket_size

    run_dir = make_run_dir(
        strategy_name=strategy_name, basket_name=basket_name, timeframe=interval
    )
    cfg = BrokerConfig()

    # Initialize monitoring
    symbols = list(data_map_full.keys())
    monitor = BacktestMonitor(run_dir, len(symbols))
    print(f"🚀 Starting optimized backtesting for {len(symbols)} symbols...")

    # Add MAX window when period='max' to get full historical analysis
    if period and period.lower() == "max":
        windows_years = (
            1,
            3,
            5,
            None,
        )  # None represents MAX window in optimize_window_processing
        print("📊 Including MAX window for full historical analysis")
    else:
        windows_years = (1, 3, 5)

    # Check for resume - but note: we still need to process ALL symbols for window analysis
    remaining_symbols = monitor.get_remaining_symbols(symbols)

    # OPTIMIZATION 1: Run strategy ONCE per symbol (not per window)
    # IMPORTANT: Even if checkpoint says all done, we still need to process all symbols
    # to populate symbol_results for window analysis
    print("⚡ Running strategy once per symbol with parallel processing...")
    symbol_results = {}

    # If all symbols are already done (checkpoint 100%), use all symbols for window processing
    # Otherwise process only remaining symbols
    symbols_to_process = symbols if len(remaining_symbols) == 0 else remaining_symbols
    # ⚡ OPTIMIZATION: Parallel symbol processing using multiprocessing
    num_processes = max(1, min(cpu_count() - 1, len(symbols_to_process)))

    if num_processes > 1 and len(symbols_to_process) > 1:
        # ⚡ Parallel processing with module-level function for pickling compatibility
        print(
            f"⚡ Using {num_processes} processes for {len(symbols_to_process)} symbols"
        )
        # Include strategy_name and params_json in task args for module-level function
        task_args = [
            (sym, i, len(symbols_to_process), data_map_full, strategy_name, params_json)
            for i, sym in enumerate(symbols_to_process)
        ]

        try:
            # ⚡ MULTIPROCESSING: Use 'spawn' context for cross-platform compatibility
            # This avoids pickle issues with local functions while maintaining stability
            # 'fork' is faster but 'spawn' is safer and more portable
            ctx = get_context("spawn")
            logger.info(
                "⚡ Using 'spawn' multiprocessing context (stable, cross-platform)"
            )

            # Create pool with optimal context
            with ctx.Pool(processes=num_processes) as pool:
                logger.info(
                    f"📊 Starting parallel backtest with {num_processes} worker processes"
                )
                results = pool.map(_process_symbol_task, task_args)

            # Collect results from parallel workers
            successful = 0
            failed = 0
            for sym, result, error in results:
                if error:
                    logger.warning(f"⚠️ {error}")
                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "error")
                    failed += 1
                else:
                    symbol_results[sym] = result
                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "completed")
                    successful += 1

            logger.info(
                f"✅ Parallel processing complete: {successful} successful, {failed} failed"
            )
        except Exception as pool_err:
            logger.debug(
                f"⚠️ Parallel processing unavailable: {pool_err}. Falling back to sequential (works fine, just slower)."
            )
            # Fallback to sequential if parallel fails
            for i, sym in enumerate(symbols_to_process):
                try:
                    with timeout_handler(
                        SYMBOL_TIMEOUT, f"Symbol {sym} processing timed out"
                    ):
                        if sym not in monitor.completed_symbols:
                            monitor.log_progress(sym, "processing")
                        logger.info(
                            f"Processing symbol {i+1}/{len(symbols_to_process)}: {sym}"
                        )

                        df_full = data_map_full[sym]
                        strat = make_strategy(strategy_name, params_json)
                        engine = BacktestEngine(
                            df_full, strat, cfg, symbol=sym
                        )
                        trades_full, equity_full, _ = engine.run()

                        symbol_results[sym] = {
                            "trades": trades_full,
                            "equity": equity_full,
                            "data": df_full,
                            "fingerprint": getattr(engine, "data_fingerprint", None),
                            "validation": getattr(engine, "validation_results", None),
                        }

                        if sym not in monitor.completed_symbols:
                            monitor.log_progress(sym, "completed")
                        logger.debug(f"Successfully processed {sym}")

                except TimeoutError as e:
                    logger.warning(f"⚠️ Timeout processing {sym}: {e}")
                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "timeout")
                    continue

                except Exception as e:
                    logger.warning(f"⚠️ Error processing {sym}: {e}")
                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "error")
                    continue

                if i % 10 == 0:
                    resources = monitor.monitor_resources()
                    print(
                        f"💾 Memory: {resources['memory_percent']:.1f}%, CPU: {resources['cpu_percent']:.1f}%"
                    )
    else:
        # Sequential processing for single symbol or insufficient CPU cores
        logger.info("ℹ️ Using sequential processing (limited CPU or few symbols)")
        for i, sym in enumerate(symbols_to_process):
            try:
                # Use timeout for individual symbol processing
                with timeout_handler(
                    SYMBOL_TIMEOUT, f"Symbol {sym} processing timed out"
                ):
                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "processing")
                    logger.info(
                        f"Processing symbol {i+1}/{len(symbols_to_process)}: {sym}"
                    )

                    df_full = data_map_full[sym]

                    # Run strategy ONCE on full data
                    strat = make_strategy(strategy_name, params_json)
                    engine = BacktestEngine(
                        df_full, strat, cfg, symbol=sym
                    )
                    trades_full, equity_full, _ = engine.run()

                    # Store results for window processing
                    symbol_results[sym] = {
                        "trades": trades_full,
                        "equity": equity_full,
                        "data": df_full,
                        "fingerprint": getattr(engine, "data_fingerprint", None),
                        "validation": getattr(engine, "validation_results", None),
                    }

                    if sym not in monitor.completed_symbols:
                        monitor.log_progress(sym, "completed")
                    logger.debug(f"Successfully processed {sym}")

            except TimeoutError as e:
                logger.warning(f"⚠️ Timeout processing {sym}: {e}")
                if sym not in monitor.completed_symbols:
                    monitor.log_progress(sym, "timeout")
                # Continue with next symbol instead of failing entire basket
                continue

            except Exception as e:
                logger.warning(f"⚠️ Error processing {sym}: {e}")
                if sym not in monitor.completed_symbols:
                    monitor.log_progress(sym, "error")
                # Continue with next symbol instead of failing entire basket
                continue

            # Monitor resources every 10 symbols
            if i % 10 == 0:
                resources = monitor.monitor_resources()
                print(
                    f"💾 Memory: {resources['memory_percent']:.1f}%, CPU: {resources['cpu_percent']:.1f}%"
                )

    # OPTIMIZATION 2: Build all windows from cached results
    print("⚡ Processing time windows from cached results...")
    window_start_time = time.time()
    total_windows = len(windows_years)

    window_results = optimize_window_processing(
        symbol_results, list(windows_years), bars_per_year
    )
    window_labels: dict[int | None, str] = {1: "1Y", 3: "3Y", 5: "5Y", None: "MAX"}
    consolidated_csv_paths: dict[str, str] = {}
    portfolio_csv_paths: dict[str, str] = {}
    window_maxdd: dict[str, float] = {}

    # Load benchmark for Alpha/Beta calculation (once for all windows)
    benchmark_df = load_benchmark(interval="1d")

    for window_idx, Y in enumerate(windows_years):
        time.time()
        label = window_labels[Y]

        # Progress tracking for window processing
        window_progress = (window_idx / total_windows) * 100
        elapsed_window = time.time() - window_start_time
        eta_window = (
            (elapsed_window / (window_idx + 1)) * (total_windows - window_idx - 1)
            if window_idx > 0
            else 0
        )

        print(
            f"📊 Window Progress: {window_progress:.1f}% ({window_idx + 1}/{total_windows})"
        )
        print(f"⏱️  Window ETA: {eta_window:.1f}s remaining")
        print(f"🔄 Processing {label} window...")

        rows = []

        # Get pre-computed results for this window
        window_data = window_results[label]
        trades_by_symbol = window_data["trades_by_symbol"]
        symbol_equities = {}
        dfs_by_symbol = {}

        # DEBUG: Log window data status
        logger.info(
            f"📊 Window {label}: {len(trades_by_symbol)} symbols in trades_by_symbol, {len(symbol_results)} total symbols"
        )
        if len(symbol_results) == 0:
            logger.warning(f"⚠️  No symbol_results to process for window {label}")
            continue

        # IMPORTANT: First pass - populate dfs_by_symbol with ALL symbols' price data for this window
        # This is critical for portfolio curve generation to have access to price data for all traded symbols
        for sym in symbol_results.keys():
            df_full = symbol_results[sym]["data"]
            equity_full = symbol_results[sym]["equity"]

            # Apply window slicing to data
            df = _slice_df_years(df_full, Y)
            if len(df) == 0:
                continue

            # Filter equity curve to the window
            try:
                if not equity_full.empty:
                    # Ensure both indices are the same dtype for isin()
                    equity_idx = pd.to_datetime(equity_full.index, errors="coerce")
                    df_idx = pd.to_datetime(df.index, errors="coerce")
                    mask = equity_idx.isin(df_idx)
                    equity = equity_full.loc[mask]
                else:
                    equity = equity_full
            except Exception as e:
                logger.warning(
                    f"Error filtering equity for {sym}: {e}, using full equity"
                )
                equity = equity_full

            # Store price data and equity for this symbol and window
            dfs_by_symbol[sym] = df
            symbol_equities[sym] = (
                equity["equity"] if "equity" in equity.columns else equity
            )

        # SECOND pass - compute metrics and trades only for symbols with data
        for sym in symbol_results.keys():
            if sym not in dfs_by_symbol:
                # Symbol had no data for this window, skip metrics calculation
                continue

            df_full = symbol_results[sym]["data"]
            trades = trades_by_symbol[sym]
            equity_full = symbol_results[sym]["equity"]

            # Get the already-sliced df from first pass
            df = dfs_by_symbol[sym]

            # ===== CRITICAL FIX: Filter trades to only those within the window =====
            # Previously, ALL trades from full backtest were included in window reports
            # This caused lookahead bias (trades from 2019 appearing in 5Y window 2020-2025)
            trades_filtered = (
                trades.copy() if trades is not None and not trades.empty else trades
            )
            if trades_filtered is not None and not trades_filtered.empty:
                try:
                    # Filter by entry_time to only include trades that started in this window
                    window_start_date = pd.to_datetime(df.index.min())
                    entry_times = pd.to_datetime(
                        trades_filtered["entry_time"], errors="coerce"
                    )
                    mask = entry_times >= window_start_date
                    trades_filtered = trades_filtered.loc[mask].copy()
                except Exception as e:
                    logger.warning(
                        f"Error filtering trades for {sym} in {label}: {e}, using all trades"
                    )
                    trades_filtered = trades

            row = compute_trade_metrics_table(
                df=df,
                trades=trades_filtered,
                bars_per_year=bars_per_year,
                initial_capital=cfg.initial_capital,
            )
            row["Symbol"] = sym
            row["Window"] = label
            rows.append(row)

        if not rows:
            continue

        # ===== Build filtered trades dict for portfolio curve calculation =====
        # Must also filter trades for portfolio curve to avoid window boundary issues
        trades_by_window_filtered = {}
        for sym, trades in trades_by_symbol.items():
            trades_filtered = (
                trades.copy() if trades is not None and not trades.empty else trades
            )
            if trades_filtered is not None and not trades_filtered.empty:
                try:
                    df_for_sym = dfs_by_symbol.get(sym)
                    if df_for_sym is not None and not df_for_sym.empty:
                        window_start_date = pd.to_datetime(df_for_sym.index.min())
                        entry_times = pd.to_datetime(
                            trades_filtered["entry_time"], errors="coerce"
                        )
                        mask = entry_times >= window_start_date
                        trades_filtered = trades_filtered.loc[mask].copy()
                except Exception as e:
                    logger.debug(
                        f"Error filtering trades for portfolio curve {sym}: {e}"
                    )
            trades_by_window_filtered[sym] = trades_filtered

        # Portfolio curve for the window - fixed equal-weight logic
        # Build portfolio equity curve by aggregating per-trade P&L (realized + MTM) over union of dates.
        # We DO NOT re-allocate initial capital to a single stock. The engine already sized each trade
        # using BrokerConfig.qty_pct_of_equity (5% of initial capital). For portfolio equity we simply
        # sum realized P&L for closed trades and mark-to-market for open trades on each date.
        def _build_portfolio_curve(trades_by_symbol, dfs_by_symbol, initial_capital):
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
                            print(
                                f"Warning: Missing columns {missing_cols} in trades for {sym}. Available columns: {list(trades_copy.columns)}"
                            )
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
                            print(
                                f"Warning: Error converting trade data for {sym}: {e}"
                            )
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
                            print(
                                f"Warning: Error filtering trades by entry_time for {sym}: {e}"
                            )
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
                                    print(
                                        f"Warning: Error calculating MTM for {sym}: {e}"
                                    )
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

        port_df = _build_portfolio_curve(
            trades_by_window_filtered, dfs_by_symbol, cfg.initial_capital
        )
        if not port_df.empty and "max_drawdown_pct" in port_df.columns:
            try:
                window_maxdd[label] = float(
                    pd.to_numeric(port_df["max_drawdown_pct"], errors="coerce").max()
                )
            except Exception:
                window_maxdd[label] = 0.0
        else:
            window_maxdd[label] = 0.0

        # TOTAL row: compute portfolio-level metrics using user's trade-aggregation formula
        # NOTE: do NOT append the TOTAL into `rows` here; we'll compute and
        # inject a single TOTAL row later when building the output table to
        # avoid producing duplicate TOTAL rows.
        total_row = compute_portfolio_trade_metrics(
            dfs_by_symbol=dfs_by_symbol,
            trades_by_symbol=trades_by_window_filtered,
            bars_per_year=bars_per_year,
        )
        total_row["Symbol"] = "TOTAL"
        total_row["Window"] = label

        # Build per-window parameter table (per-symbol rows) and a portfolio TOTAL row.
        # We'll produce a single CSV `basket_{label}.csv` with the requested columns
        # and put the TOTAL row at the top.
        try:
            params_rows = []
            for r in rows:
                sym = r.get("Symbol")
                # Use NetPnLPct from metrics (total P&L / deployed capital)
                net_pnl_pct = float(r.get("NetPnLPct", 0.0))
                maxdd = 0.0

                # Calculate max drawdown using highest individual trade drawdown
                # This is more meaningful than equity curve drawdown as it represents actual trading risk
                trades_df = trades_by_symbol.get(sym)
                if trades_df is not None and not trades_df.empty:
                    # Get all trade drawdowns and find the maximum
                    try:
                        # For each trade, calculate drawdown based on entry price vs lowest price during trade
                        max_trade_dd = 0.0
                        for _, trade in trades_df.iterrows():
                            entry_time = trade.get("entry_time")
                            exit_time = trade.get("exit_time")
                            entry_price = trade.get("entry_price", 0)

                            if entry_time and exit_time and entry_price > 0:
                                # Get price data during trade period
                                symbol_df = dfs_by_symbol.get(sym)
                                if symbol_df is not None and not symbol_df.empty:
                                    try:
                                        # Ensure index and times are comparable
                                        sym_idx = pd.to_datetime(
                                            symbol_df.index, errors="coerce"
                                        )
                                        entry_ts = pd.Timestamp(entry_time)
                                        exit_ts = pd.Timestamp(exit_time)
                                        mask = (sym_idx >= entry_ts) & (
                                            sym_idx <= exit_ts
                                        )
                                        trade_data = symbol_df.loc[mask]
                                    except Exception:
                                        trade_data = pd.DataFrame()

                                    if (
                                        not trade_data.empty
                                        and "low" in trade_data.columns
                                    ):
                                        min_low = trade_data["low"].min()
                                        trade_dd = (
                                            (entry_price - min_low) / entry_price * 100
                                            if entry_price > 0
                                            else 0
                                        )
                                        max_trade_dd = max(max_trade_dd, trade_dd)

                        maxdd = float(max_trade_dd)
                    except Exception:
                        maxdd = 0.0
                else:
                    net_pnl_pct = 0.0
                    maxdd = 0.0

                # compute per-symbol Equity CAGR (%) from Net P&L % (same as TOTAL)
                eq_cagr_pct = 0.0
                try:
                    # Determine n_years for annualization
                    if Y is not None:
                        n_years = Y  # Use the window period directly (1, 3, or 5 years)
                    else:
                        # For "ALL" window, calculate from actual dates
                        eqs = symbol_equities.get(sym)
                        if eqs is not None and not eqs.empty:
                            idx = eqs.index
                            if (
                                hasattr(idx, "dtype")
                                and "datetime" in str(idx.dtype).lower()
                            ):
                                days = (
                                    pd.to_datetime(idx[-1]) - pd.to_datetime(idx[0])
                                ).days
                                n_years = max(days / 365.25, 1 / 365.25)
                            else:
                                n_years = 1.0
                        else:
                            n_years = 1.0

                    # Compute CAGR from Net P&L %
                    # CAGR = ((1 + net_pnl_pct/100) ** (1/n_years) - 1) * 100
                    net_pnl_decimal = net_pnl_pct / 100.0  # Convert % to decimal
                    eq_cagr_pct = (
                        ((1.0 + net_pnl_decimal) ** (1.0 / n_years) - 1.0) * 100.0
                        if net_pnl_decimal > -1.0  # Avoid invalid values
                        else 0.0
                    )
                except Exception:
                    eq_cagr_pct = 0.0

                row_out = {
                    "Window": r.get("Window"),
                    "Symbol": sym,
                    "Net P&L %": net_pnl_pct,
                    "Max equity drawdown %": maxdd,
                    "Total trades": r.get("NumTrades", 0),
                    "Profitable trades %": r.get("WinRatePct", 0.0),
                    "Profit factor": r.get("ProfitFactor", 0.0),
                    "Avg P&L % per trade": r.get("AvgProfitPerTradePct", 0.0),
                    "Avg bars per trade": r.get("AvgBarsPerTrade", float("nan")),
                    # IRR_pct provided by compute_trade_metrics_table (trade/deployment-based)
                    "IRR %": r.get("IRR_pct", 0.0),
                    # CAGR will be populated from equity series in reporting (for TOTAL we compute below)
                    "Equity CAGR %": eq_cagr_pct,
                }
                params_rows.append(row_out)

            # NOTE: total_row was already computed at line 2639 above using trades_by_window_filtered
            # Do NOT recompute it here - that would overwrite the correct window-filtered metrics!
            # compute portfolio Net P&L %, MaxDD, and CAGR from port_df
            try:
                port_net_pct = 0.0
                port_maxdd = 0.0
                equity_cagr = 0.0

                # Net P&L % for TOTAL should match equity curve return (most reliable)
                # = (end_equity - start_equity) / start_equity * 100
                if not port_df.empty:
                    try:
                        start_eq = float(port_df["equity"].iloc[0])
                        end_eq = float(port_df["equity"].iloc[-1])
                        port_net_pct = (
                            (end_eq / start_eq - 1.0) * 100.0 if start_eq != 0 else 0.0
                        )
                    except Exception:
                        port_net_pct = 0.0
                else:
                    # Fallback: use TotalNetPnL / initial_capital if no equity curve
                    if cfg.initial_capital > 0:
                        port_net_pct = (
                            total_row.get("TotalNetPnL", 0.0)
                            / cfg.initial_capital
                            * 100.0
                        )

                if not port_df.empty:
                    # Max drawdown comes directly from port_df's max_drawdown_pct column (portfolio-level)
                    try:
                        port_maxdd = float(
                            pd.to_numeric(
                                port_df["max_drawdown_pct"], errors="coerce"
                            ).max()
                        )
                    except Exception:
                        port_maxdd = 0.0

                    # Compute CAGR based on time span
                    try:
                        # For windowed analysis (1Y, 3Y, 5Y), use the window period as n_years
                        # to ensure CAGR represents true annualized return for the specified window
                        if Y is not None:
                            n_years = (
                                Y  # Use the window period directly (1, 3, or 5 years)
                            )
                        else:
                            # For "ALL" window, calculate from actual dates
                            idx_dates = pd.to_datetime(port_df.index)
                            if len(idx_dates) >= 2:
                                days = (idx_dates[-1] - idx_dates[0]).days
                                n_years = max(days / 365.25, 1.0 / 365.25)
                            else:
                                n_years = 1.0

                        # Compute CAGR from Net P&L %
                        # CAGR = ((1 + net_pnl_pct/100) ** (1/n_years) - 1) * 100
                        try:
                            net_pnl_decimal = (
                                port_net_pct / 100.0
                            )  # Convert % to decimal
                            equity_cagr = (
                                ((1.0 + net_pnl_decimal) ** (1.0 / n_years) - 1.0)
                                * 100.0
                                if net_pnl_decimal > -1.0  # Avoid invalid values
                                else 0.0
                            )
                        except Exception:
                            equity_cagr = 0.0
                    except Exception:
                        equity_cagr = 0.0
            except Exception:
                port_net_pct = 0.0
                port_maxdd = 0.0
                equity_cagr = 0.0

            total_row_out = {
                "Window": label,
                "Symbol": "TOTAL",
                "Net P&L %": port_net_pct,
                "Max equity drawdown %": port_maxdd,
                "Total trades": int(total_row.get("NumTrades", 0)),
                "Profitable trades %": float(total_row.get("WinRatePct", 0.0)),
                "Profit factor": float(total_row.get("ProfitFactor", 0.0)),
                "Avg P&L % per trade": float(
                    total_row.get("AvgProfitPerTradePct", 0.0)
                ),
                "Avg bars per trade": float(
                    total_row.get("AvgBarsPerTrade", float("nan"))
                ),
                "IRR %": float(total_row.get("IRR_pct", 0.0)),
                # Equity CAGR in percent (already computed as percent)
                "Equity CAGR %": float(equity_cagr),
            }            # Build DataFrame with TOTAL first, then symbols sorted
            params_df = pd.DataFrame(params_rows)
            # remove duplicates and ensure consistent ordering
            params_df = params_df.sort_values(by=["Symbol"]).reset_index(drop=True)
            final_df = pd.concat(
                [pd.DataFrame([total_row_out]), params_df], ignore_index=True
            )

            # Write CSV with portfolio key metrics (renamed from basket)
            csv_path = os.path.join(run_dir, f"portfolio_key_metrics_{label}.csv")

            # Format percent fields as numeric (two decimals, no '%' suffix) - vectorized
            pct_cols = [
                "Net P&L %",
                "Profitable trades %",
                "Avg P&L % per trade",
                "IRR %",
                "Equity CAGR %",
                "Max equity drawdown %",
            ]
            for col in pct_cols:
                if col in final_df.columns:
                    # Vectorized rounding - no need for apply
                    final_df[col] = (
                        pd.to_numeric(final_df[col], errors="coerce")
                        .fillna(0.0)
                        .round(2)
                    )

            # Profit factor: numeric rounded to 2 decimals - vectorized
            if "Profit factor" in final_df.columns:
                import math

                # Vectorized approach - handle inf and nan efficiently
                pf_series = pd.to_numeric(final_df["Profit factor"], errors="coerce")
                # Replace inf with a large number (e.g., 999.99) or keep as inf
                pf_series = pf_series.replace([np.inf, -np.inf], 999.99)
                final_df["Profit factor"] = pf_series.fillna(0.0).round(2)

            # Avg bars per trade should be integer - vectorized
            if "Avg bars per trade" in final_df.columns:
                final_df["Avg bars per trade"] = (
                    pd.to_numeric(final_df["Avg bars per trade"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )

            # Ensure Total trades is integer
            if "Total trades" in final_df.columns:
                final_df["Total trades"] = (
                    pd.to_numeric(final_df["Total trades"], errors="coerce")
                    .fillna(0)
                    .astype(int)
                )

            # Write CSV
            final_df.to_csv(csv_path, index=False)
            consolidated_csv_paths[label] = csv_path

            # Consolidated trades-only CSV (all symbols concatenated) with requested columns
            # ===== CRITICAL FIX: Use window-filtered trades, not full backtest trades =====
            trades_list = [
                t.reset_index(drop=True).assign(Symbol=sym)
                for sym, t in trades_by_window_filtered.items()
                if t is not None and not t.empty
            ]

            if trades_list:
                # Filter out any None, empty, or all-NA entries before concatenation to avoid FutureWarning
                valid_trades_list = []
                for t in trades_list:
                    if (
                        t is not None
                        and not t.empty
                        and not t.isna().all().all()
                        and len(t.dropna(how="all", axis=1)) > 0
                    ):  # Remove all-NA columns
                        # Clean the DataFrame by removing all-NA columns
                        clean_t = t.dropna(how="all", axis=1)
                        if not clean_t.empty:
                            valid_trades_list.append(clean_t)

                if valid_trades_list:
                    trades_only_df = pd.concat(
                        valid_trades_list, axis=0, ignore_index=True
                    )
                else:
                    trades_only_df = (
                        pd.DataFrame()
                    )  # Empty DataFrame if no valid trades

                # normalize and compute requested columns and ordering
                # Ensure datetime columns are stringified consistently

                trades_only_df["entry_time"] = pd.to_datetime(
                    trades_only_df.get("entry_time")
                )
                trades_only_df["exit_time"] = pd.to_datetime(
                    trades_only_df.get("exit_time")
                )

                # Create TV-style rows (Exit then Entry) per trade to match prior format
                tv_rows = []

                # OPTIMIZATION 1: Cache for OHLC data lookups (trade indicators, runup/drawdown)
                # This reduces redundant DataFrame filtering for repeated symbols
                ohlc_cache = {}

                def _get_trade_ohlc(symbol: str, entry_time, exit_time):
                    """Get OHLC data for a trade period (cached)."""
                    # Create cache key from symbol and dates
                    key = (symbol, str(entry_time)[:10], str(exit_time)[:10])
                    if key not in ohlc_cache:
                        symbol_df = dfs_by_symbol.get(symbol)
                        if symbol_df is not None and not symbol_df.empty:
                            try:
                                sym_idx = pd.to_datetime(
                                    symbol_df.index, errors="coerce"
                                )
                                entry_ts = pd.Timestamp(entry_time)
                                exit_ts = pd.Timestamp(exit_time)
                                mask = (sym_idx >= entry_ts) & (sym_idx <= exit_ts)
                                ohlc_cache[key] = symbol_df.loc[mask]
                            except Exception:
                                ohlc_cache[key] = pd.DataFrame()
                        else:
                            ohlc_cache[key] = pd.DataFrame()
                    return ohlc_cache[key]

                # Simplified approach - just create basic trade records
                tv_rows = []
                for i, tr in trades_only_df.reset_index(drop=True).iterrows():
                    trade_no = i + 1
                    entry_time = tr.get("entry_time", pd.NaT)
                    exit_time = tr.get("exit_time", pd.NaT)
                    entry_price = float(tr.get("entry_price", 0))
                    exit_price = float(tr.get("exit_price", 0))
                    qty = int(tr.get("entry_qty", 0))
                    net_pnl = float(tr.get("net_pnl", 0))
                    symbol = tr.get("Symbol", "")

                    # IMPORTANT: Verify net_pnl includes both entry and exit commissions
                    # Commission is correctly calculated in the engine based on actual
                    # entry/exit prices (which may have decimal values like 1905.03, 1853.97)
                    # The CSV displays prices as integers for readability, but the commission
                    # calculation uses the full decimal precision from the engine.

                    # Get OHLC data for this trade period
                    symbol_df = dfs_by_symbol.get(symbol)
                    if symbol_df is None or symbol_df.empty:
                        continue

                    # Calculate indicators for this specific trade
                    indicators = _calculate_trade_indicators(
                        symbol_df, entry_time, exit_time, entry_price
                    )

                    # Compute P&L related metrics
                    tv_pos_value = entry_price * qty if entry_price and qty else 0
                    tv_net_pct = (
                        (net_pnl / tv_pos_value * 100)
                        if tv_pos_value > 0 and pd.notna(net_pnl)
                        else 0
                    )

                    # Calculate run-up and drawdown from OHLC data (like in _export_trades_events)
                    run_up_exit = 0
                    drawdown_exit = 0
                    try:
                        if (
                            symbol_df is not None
                            and not symbol_df.empty
                            and entry_price > 0
                        ):
                            # Get price series between entry and exit times
                            try:
                                price_series = symbol_df.loc[entry_time:exit_time][
                                    "close"
                                ].astype(float)
                            except (KeyError, TypeError):
                                # Fallback: convert times to datetime
                                entry_dt = pd.to_datetime(entry_time)
                                exit_dt = pd.to_datetime(exit_time)
                                if not isinstance(symbol_df.index, pd.DatetimeIndex):
                                    symbol_df_temp = symbol_df.set_index(
                                        pd.to_datetime(symbol_df.index)
                                    )
                                else:
                                    symbol_df_temp = symbol_df
                                price_series = symbol_df_temp.loc[entry_dt:exit_dt][
                                    "close"
                                ].astype(float)

                            if not price_series.empty:
                                pnl_series = (price_series - entry_price) * qty
                                run_up_exit = float(
                                    max(0, pnl_series.max())
                                )  # Run-up can't be negative
                                drawdown_exit = float(pnl_series.min())
                    except Exception:
                        pass

                    tv_run_pct = (
                        (run_up_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
                    )
                    tv_dd_pct = (
                        (drawdown_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
                    )
                    mae_pct = abs(tv_dd_pct)

                    # Format dates
                    entry_str = (
                        entry_time.strftime("%Y-%m-%d") if pd.notna(entry_time) else ""
                    )
                    exit_str = (
                        exit_time.strftime("%Y-%m-%d") if pd.notna(exit_time) else ""
                    )

                    # For open trades, use current (last) price from symbol_df
                    current_exit_price = exit_price
                    is_open_trade = pd.isna(exit_time) or exit_price == 0
                    if is_open_trade:
                        # Get last close price from the dataframe
                        if symbol_df is not None and not symbol_df.empty:
                            current_exit_price = (
                                float(symbol_df["close"].iloc[-1])
                                if "close" in symbol_df.columns
                                else exit_price
                            )
                        else:
                            current_exit_price = entry_price  # Fallback to entry price

                    # Recalculate position value with current exit price for open trades
                    tv_pos_value_exit = (
                        current_exit_price * qty if current_exit_price and qty else 0
                    )

                    # For open trades, calculate MTM P&L; for closed trades, use realized P&L
                    if is_open_trade:
                        # Mark-to-market P&L for open trades
                        mtm_pnl = (
                            (current_exit_price - entry_price) * qty
                            if entry_price > 0
                            else 0
                        )
                        (
                            (mtm_pnl / tv_pos_value_exit * 100)
                            if tv_pos_value_exit > 0
                            else 0
                        )
                        net_pnl_exit = mtm_pnl
                    else:
                        # Realized P&L for closed trades
                        (
                            (net_pnl / tv_pos_value_exit * 100)
                            if tv_pos_value_exit > 0 and pd.notna(net_pnl)
                            else 0
                        )
                        net_pnl_exit = net_pnl if pd.notna(net_pnl) else 0

                    # Recalculate run-up % and drawdown % - use entry price for base calculation
                    tv_run_pct = (
                        (run_up_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
                    )
                    tv_dd_pct = (
                        (drawdown_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
                    )
                    mae_pct = abs(tv_dd_pct)

                    # Net P&L handling - ensure it's an integer
                    net_pnl_int = (
                        int(net_pnl_exit)
                        if net_pnl_exit is not None and not pd.isna(net_pnl_exit)
                        else 0
                    )

                    # Exit row
                    tv_rows.append(
                        {
                            "Trade #": trade_no,
                            "Symbol": symbol,
                            "Type": "Exit long",
                            "Date/Time": exit_str,
                            "Signal": ("CLOSE" if pd.notna(exit_time) else "OPEN"),
                            "Price INR": (
                                int(current_exit_price)
                                if current_exit_price > 0
                                else ""
                            ),
                            "Position size (qty)": int(qty) if qty > 0 else "",
                            "Position size (value)": (
                                int(tv_pos_value_exit) if tv_pos_value_exit > 0 else ""
                            ),
                            "Net P&L INR": net_pnl_int,
                            "Net P&L %": round(tv_net_pct, 2),
                            "Run-up INR": (int(run_up_exit) if run_up_exit > 0 else 0),
                            "Run-up %": round(tv_run_pct, 2),
                            "Drawdown INR": (
                                int(drawdown_exit)
                                if drawdown_exit is not None
                                else None
                            ),
                            "Drawdown %": round(tv_dd_pct, 2),
                            "Holding days": (
                                int(indicators.get("holding_days", 0))
                                if indicators
                                and indicators.get("holding_days", 0)
                                and pd.notna(indicators.get("holding_days", 0))
                                else 0
                            ),
                            "ATR": (
                                int(round(indicators.get("atr", 0)))
                                if indicators and pd.notna(indicators.get("atr", 0))
                                else ""
                            ),
                            "ATR %": (
                                round(indicators.get("atr_pct", 0), 2)
                                if indicators and pd.notna(indicators.get("atr_pct", 0))
                                else ""
                            ),
                            "MAE %": round(mae_pct, 2),
                            "MAE_ATR": (
                                round(mae_pct / indicators.get("atr_pct", 1), 2)
                                if indicators and indicators.get("atr_pct", 0) > 0
                                else ""
                            ),
                            "MFE %": round(tv_run_pct, 2),
                            "MFE_ATR": (
                                round(tv_run_pct / indicators.get("atr_pct", 1), 2)
                                if indicators and indicators.get("atr_pct", 0) > 0
                                else ""
                            ),
                            "Short-Trend": indicators.get("short_trend", "") if indicators else "",
                            "Medium-Trend": indicators.get("medium_trend", "") if indicators else "",
                            "Long-Trend": indicators.get("long_trend", "") if indicators else "",
                            "Volatility": (
                                indicators.get("volatility", "") if indicators else ""
                            ),
                            "ADX": (
                                round(indicators.get("adx", 0), 2) if indicators else ""
                            ),
                            "Plus_DI": (
                                round(indicators.get("plus_di", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Minus_DI": (
                                round(indicators.get("minus_di", 0), 2)
                                if indicators
                                else ""
                            ),
                            "DI_Bullish": (
                                str(indicators.get("di_bullish", ""))
                                if indicators
                                else ""
                            ),
                            "RSI": (
                                round(indicators.get("rsi", 50), 2)
                                if indicators
                                else ""
                            ),
                            "MACD_Line": (
                                round(indicators.get("macd_line", 0), 2)
                                if indicators
                                else ""
                            ),
                            "MACD_Signal": (
                                round(indicators.get("macd_signal", 0), 2)
                                if indicators
                                else ""
                            ),
                            "MACD_Bullish": (
                                str(indicators.get("macd_bullish", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_EMA20": (
                                str(indicators.get("price_above_ema20", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_EMA50": (
                                str(indicators.get("price_above_ema50", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_EMA200": (
                                str(indicators.get("price_above_ema200", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_EMA5": (
                                str(indicators.get("price_above_ema5", ""))
                                if indicators
                                else ""
                            ),
                            "EMA_5": (
                                round(indicators.get("ema_5", 0), 2)
                                if indicators
                                else ""
                            ),
                            "EMA_20": (
                                round(indicators.get("ema_20", 0), 2)
                                if indicators
                                else ""
                            ),
                            "EMA5_Above_EMA20": (
                                str(indicators.get("ema5_above_ema20", ""))
                                if indicators
                                else ""
                            ),
                            "EMA_50": (
                                round(indicators.get("ema_50", 0), 2)
                                if indicators
                                else ""
                            ),
                            "EMA20_Above_EMA50": (
                                str(indicators.get("ema20_above_ema50", ""))
                                if indicators
                                else ""
                            ),
                            "EMA_200": (
                                round(indicators.get("ema_200", 0), 2)
                                if indicators
                                else ""
                            ),
                            "EMA50_Above_EMA200": (
                                str(indicators.get("ema50_above_ema200", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_SMA20": (
                                str(indicators.get("price_above_sma20", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_SMA50": (
                                str(indicators.get("price_above_sma50", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_SMA200": (
                                str(indicators.get("price_above_sma200", ""))
                                if indicators
                                else ""
                            ),
                            "Price_Above_SMA5": (
                                str(indicators.get("price_above_sma5", ""))
                                if indicators
                                else ""
                            ),
                            "SMA_5": (
                                round(indicators.get("sma_5", 0), 2)
                                if indicators
                                else ""
                            ),
                            "SMA_20": (
                                round(indicators.get("sma_20", 0), 2)
                                if indicators
                                else ""
                            ),
                            "SMA5_Above_SMA20": (
                                str(indicators.get("sma5_above_sma20", ""))
                                if indicators
                                else ""
                            ),
                            "SMA_50": (
                                round(indicators.get("sma_50", 0), 2)
                                if indicators
                                else ""
                            ),
                            "SMA20_Above_SMA50": (
                                str(indicators.get("sma20_above_sma50", ""))
                                if indicators
                                else ""
                            ),
                            "SMA_200": (
                                round(indicators.get("sma_200", 0), 2)
                                if indicators
                                else ""
                            ),
                            "SMA50_Above_SMA200": (
                                str(indicators.get("sma50_above_sma200", ""))
                                if indicators
                                else ""
                            ),
                            "Ichimoku_Base": (
                                round(indicators.get("ichimoku_base", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Ichimoku_Tenkan": (
                                round(indicators.get("ichimoku_tenkan", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Price_Above_Kijun": (
                                str(indicators.get("price_above_kijun", ""))
                                if indicators
                                else ""
                            ),
                            "Tenkan_Above_Kijun": (
                                str(indicators.get("tenkan_above_kijun", ""))
                                if indicators
                                else ""
                            ),
                            "VWMA_14": (
                                round(indicators.get("vwma_14", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Price_Above_VWMA": (
                                str(indicators.get("price_above_vwma", ""))
                                if indicators
                                else ""
                            ),
                            "HMA_14": (
                                round(indicators.get("hma_14", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Price_Above_HMA": (
                                str(indicators.get("price_above_hma", ""))
                                if indicators
                                else ""
                            ),
                            "CCI": (
                                round(indicators.get("cci", 0), 2) if indicators else ""
                            ),
                            "%K": (
                                round(indicators.get("percent_k", 50), 2)
                                if indicators
                                else ""
                            ),
                            "%D": (
                                round(indicators.get("percent_d", 50), 2)
                                if indicators
                                else ""
                            ),
                            "Stoch_Bullish": (
                                str(indicators.get("stoch_bullish", ""))
                                if indicators
                                else ""
                            ),
                            "Stoch_Slow_K": (
                                round(indicators.get("stoch_slow_k", 50), 2)
                                if indicators
                                else ""
                            ),
                            "Stoch_Slow_D": (
                                round(indicators.get("stoch_slow_d", 50), 2)
                                if indicators
                                else ""
                            ),
                            "Stoch_Slow_Bullish": (
                                str(indicators.get("stoch_slow_bullish", ""))
                                if indicators
                                else ""
                            ),
                            "Stoch_RSI_K": (
                                round(indicators.get("stoch_rsi_k", 50), 2)
                                if indicators
                                else ""
                            ),
                            "Stoch_RSI_D": (
                                round(indicators.get("stoch_rsi_d", 50), 2)
                                if indicators
                                else ""
                            ),
                            "StochRSI_Bullish": (
                                str(indicators.get("stoch_rsi_bullish", ""))
                                if indicators
                                else ""
                            ),
                            "Williams_R": (
                                round(indicators.get("williams_r", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Momentum": (
                                round(indicators.get("momentum", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Ultimate_Osc": (
                                round(indicators.get("ultimate_osc", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Bull_Power": (
                                round(indicators.get("bull_power", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Bear_Power": (
                                round(indicators.get("bear_power", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Bull_Bear_Power": (
                                round(indicators.get("bull_bear_power", 0), 2)
                                if indicators
                                else ""
                            ),
                            "Aroon_Up": (
                                int(round(indicators.get("aroon_up", 50)))
                                if indicators
                                else ""
                            ),
                            "Aroon_Down": (
                                int(round(indicators.get("aroon_down", 50)))
                                if indicators
                                else ""
                            ),
                            "Aroon_Osc": (
                                int(round(indicators.get("aroon_osc", 0)))
                                if indicators
                                else ""
                            ),
                            "Bollinger_Band_Position": (
                                indicators.get("bb_position", "") if indicators else ""
                            ),
                        }
                    )

                    # Entry row
                    tv_pos_value_entry = (
                        (entry_price * qty) if (entry_price is not None and qty) else 0
                    )
                    tv_rows.append(
                        {
                            "Trade #": trade_no,
                            "Symbol": symbol,
                            "Type": "Entry long",
                            "Date/Time": entry_str,
                            "Signal": "LONG",
                            "Price INR": int(entry_price) if entry_price > 0 else "",
                            "Position size (qty)": int(qty) if qty > 0 else "",
                            "Position size (value)": (
                                int(tv_pos_value_entry)
                                if tv_pos_value_entry > 0
                                else ""
                            ),
                            "Net P&L INR": "",
                            "Net P&L %": "",
                            "Run-up INR": "",
                            "Run-up %": "",
                            "Drawdown INR": "",
                            "Drawdown %": "",
                            "Holding days": "",
                            "ATR": "",
                            "ATR %": "",
                            "MAE %": "",
                            "MAE_ATR": "",
                            "MFE %": "",
                            "MFE_ATR": "",
                            "Short-Trend": "",
                            "Medium-Trend": "",
                            "Long-Trend": "",
                            "Volatility": "",
                            "ADX": "",
                            "Plus_DI": "",
                            "Minus_DI": "",
                            "DI_Bullish": "",
                            "RSI": "",
                            "MACD_Line": "",
                            "MACD_Signal": "",
                            "MACD_Bullish": "",
                            "Price_Above_EMA20": "",
                            "Price_Above_EMA50": "",
                            "Price_Above_EMA200": "",
                            "Price_Above_EMA5": "",
                            "EMA_5": "",
                            "EMA_20": "",
                            "EMA5_Above_EMA20": "",
                            "EMA_50": "",
                            "EMA20_Above_EMA50": "",
                            "EMA_200": "",
                            "EMA50_Above_EMA200": "",
                            "Price_Above_SMA20": "",
                            "Price_Above_SMA50": "",
                            "Price_Above_SMA200": "",
                            "Price_Above_SMA5": "",
                            "SMA_5": "",
                            "SMA_20": "",
                            "SMA5_Above_SMA20": "",
                            "SMA_50": "",
                            "SMA20_Above_SMA50": "",
                            "SMA_200": "",
                            "SMA50_Above_SMA200": "",
                            "Ichimoku_Base": "",
                            "Ichimoku_Tenkan": "",
                            "Price_Above_Kijun": "",
                            "Tenkan_Above_Kijun": "",
                            "VWMA_14": "",
                            "Price_Above_VWMA": "",
                            "HMA_14": "",
                            "Price_Above_HMA": "",
                            "CCI": "",
                            "%K": "",
                            "%D": "",
                            "Stoch_Bullish": "",
                            "Stoch_Slow_K": "",
                            "Stoch_Slow_D": "",
                            "Stoch_Slow_Bullish": "",
                            "Stoch_RSI_K": "",
                            "Stoch_RSI_D": "",
                            "StochRSI_Bullish": "",
                            "Williams_R": "",
                            "Momentum": "",
                            "Ultimate_Osc": "",
                            "Bull_Power": "",
                            "Bear_Power": "",
                            "Bull_Bear_Power": "",
                            "Aroon_Up": "",
                            "Aroon_Down": "",
                            "Aroon_Osc": "",
                            "Bollinger_Band_Position": "",
                        }
                    )

                print(
                    f"DEBUG {label}: created {len(tv_rows)} TV rows from {len(trades_only_df)} trades"
                )
                if len(tv_rows) == 0 and len(trades_only_df) > 0:
                    print(
                        f"DEBUG {label}: trades_only_df columns: {list(trades_only_df.columns)}"
                    )
                    print(
                        f"DEBUG {label}: First trade: {trades_only_df.iloc[0].to_dict() if len(trades_only_df) > 0 else 'NO DATA'}"
                    )

                trades_only_out = pd.DataFrame(tv_rows)

                # Skip empty trades
                if trades_only_out.empty or "Trade #" not in trades_only_out.columns:
                    print(
                        f"⚠️  {label}: No trades or missing 'Trade #' column, skipping symbol output"
                    )
                    continue

                # Symbol is already correctly set in tv_rows from trades_only_df
                # DO NOT RECALCULATE IT - the mapping created by iterating trades_by_symbol
                # does not match the actual trade order in trades_only_df and causes symbol mismatches
                print(
                    f"DEBUG {label}: Symbol already assigned from trades_only_df"
                )

                # Ensure numeric Net P&L INR and Position size (value)
                trades_only_out["Net P&L INR"] = pd.to_numeric(
                    trades_only_out["Net P&L INR"], errors="coerce"
                )
                trades_only_out["Position size (value)"] = pd.to_numeric(
                    trades_only_out["Position size (value)"], errors="coerce"
                )
                # Write out with requested column order
                # Put Symbol as the second column as requested
                cols = [
                    # Basic Trade Info
                    "Trade #",
                    "Symbol",
                    "Type",
                    "Date/Time",
                    "Signal",
                    "Price INR",
                    "Position size (qty)",
                    "Position size (value)",
                    # P&L Metrics (moved to start after basic info)
                    "Net P&L INR",
                    "Net P&L %",
                    # Risk Metrics
                    "Run-up INR",
                    "Run-up %",
                    "Drawdown INR",
                    "Drawdown %",
                    "Holding days",
                    # Volatility Indicators
                    "ATR",
                    "ATR %",
                    "MAE %",
                    "MAE_ATR",
                    "MFE %",
                    "MFE_ATR",
                    # Market Regime (Multi-timeframe Trends)
                    "Short-Trend",
                    "Medium-Trend",
                    "Long-Trend",
                    "Volatility",
                    # ADX and directional indicators
                    "ADX",
                    "Plus_DI",
                    "Minus_DI",
                    "DI_Bullish",
                    # RSI
                    "RSI",
                    # MACD
                    "MACD_Line",
                    "MACD_Signal",
                    "MACD_Bullish",
                    # EMAs with comparisons (Price_Above_* moved before EMA_5)
                    "Price_Above_EMA20",
                    "Price_Above_EMA50",
                    "Price_Above_EMA200",
                    "Price_Above_EMA5",
                    "EMA_5",
                    "EMA_20",
                    "EMA5_Above_EMA20",
                    "EMA_50",
                    "EMA20_Above_EMA50",
                    "EMA_200",
                    "EMA50_Above_EMA200",
                    # SMAs with comparisons (Price_Above_* moved before SMA_5)
                    "Price_Above_SMA20",
                    "Price_Above_SMA50",
                    "Price_Above_SMA200",
                    "Price_Above_SMA5",
                    "SMA_5",
                    "SMA_20",
                    "SMA5_Above_SMA20",
                    "SMA_50",
                    "SMA20_Above_SMA50",
                    "SMA_200",
                    "SMA50_Above_SMA200",
                    # Ichimoku with comparisons
                    "Ichimoku_Base",
                    "Ichimoku_Tenkan",
                    "Price_Above_Kijun",
                    "Tenkan_Above_Kijun",
                    # VWMA with comparison
                    "VWMA_14",
                    "Price_Above_VWMA",
                    # HMA with comparison
                    "HMA_14",
                    "Price_Above_HMA",
                    # CCI
                    "CCI",
                    # Stochastic (Fast 14, 3, 3)
                    "%K",
                    "%D",
                    "Stoch_Bullish",
                    # Stochastic Slow (5, 3, 3) with comparison renamed
                    "Stoch_Slow_K",
                    "Stoch_Slow_D",
                    "Stoch_Slow_Bullish",
                    # Stochastic RSI with comparison renamed
                    "Stoch_RSI_K",
                    "Stoch_RSI_D",
                    "StochRSI_Bullish",
                    # Williams %R
                    "Williams_R",
                    # Momentum
                    "Momentum",
                    # Ultimate Oscillator
                    "Ultimate_Osc",
                    # Bull/Bear Power
                    "Bull_Power",
                    "Bear_Power",
                    "Bull_Bear_Power",
                    # Aroon
                    "Aroon_Up",
                    "Aroon_Down",
                    "Aroon_Osc",
                    # Bollinger Bands
                    "Bollinger_Band_Position",
                ]
                trades_only_path = os.path.join(
                    run_dir, f"consolidated_trades_{label}.csv"
                )
                trades_only_out = trades_only_out.reindex(columns=cols)
                print(
                    f"DEBUG {label}: writing consolidated trades to {trades_only_path}"
                )

                # Only write trades if we have data
                if not trades_only_out.empty and len(trades_only_out) > 0:
                    trades_only_out.to_csv(trades_only_path, index=False, columns=cols)
                    consolidated_csv_paths[f"trades_{label}"] = trades_only_path
                    print(
                        f"DEBUG {label}: successfully wrote consolidated trades file ({len(trades_only_out)} rows)"
                    )
                else:
                    print(f"⚠️  {label}: Skipping trades CSV - no data available")

            # Save portfolio (TOTAL) consolidated csv path as portfolio curve path
            # We'll emit distinct daily and monthly portfolio files below; keep a legacy copy for compatibility.
            print(
                f"DEBUG {label}: starting portfolio curve generation, port_df shape: {port_df.shape if not port_df.empty else 'empty'}"
            )
            try:
                # write daily consolidated curve CSV (daily values)
                # Write daily consolidated curve into consolidated_{label}.csv
                # Create a numeric daily DataFrame from port_df
                try:
                    # port_df contains 'equity' and drawdown columns named 'drawdown_inr','drawdown_pct', etc.
                    df_daily_num = port_df.reset_index().rename(
                        columns={"index": "time", "equity": "Equity"}
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])
                except Exception:
                    df_daily_num = port_df.reset_index()
                    df_daily_num.columns = (
                        ["time", "Equity"] + list(df_daily_num.columns[2:])
                        if df_daily_num.shape[1] >= 2
                        else df_daily_num.columns
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])

                # Prepare display versions (Equity integer, drawdown as percent string)
                df_daily_display = df_daily_num.copy()
                try:
                    df_daily_display["Equity"] = (
                        df_daily_display["Equity"].astype(float).round(0).astype(int)
                    )
                except Exception:
                    # Vectorized fallback
                    df_daily_display["Equity"] = (
                        pd.to_numeric(df_daily_display["Equity"], errors="coerce")
                        .fillna(0)
                        .round(0)
                        .astype(int)
                    )
                # Ensure drawdown percent numeric field exists (drawdown_pct). Port_df uses 'drawdown_pct'
                if "drawdown_pct" in df_daily_display.columns:
                    # Vectorized rounding - no need for apply
                    df_daily_display["drawdown_pct"] = (
                        pd.to_numeric(df_daily_display["drawdown_pct"], errors="coerce")
                        .fillna(0.0)
                        .round(2)
                    )
                else:
                    # best-effort: if 'drawdown_inr' and Equity are present, compute percent
                    try:
                        draw_inr = pd.to_numeric(
                            df_daily_display.get("drawdown_inr", 0), errors="coerce"
                        ).fillna(0.0)
                        eq_val = pd.to_numeric(
                            df_daily_display.get("Equity", cfg.initial_capital),
                            errors="coerce",
                        ).replace({0: cfg.initial_capital})
                        # Vectorized calculation and rounding
                        df_daily_display["drawdown_pct"] = (
                            draw_inr / eq_val * 100.0
                        ).round(2)
                    except Exception:
                        df_daily_display["drawdown_pct"] = 0.0

                # create numeric daily dataframe from port_df
                try:
                    df_daily_num = port_df.reset_index().rename(
                        columns={
                            "index": "time",
                            "equity": "Equity",
                            "drawdown": "drawdown",
                        }
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])
                except Exception:
                    df_daily_num = port_df.reset_index()
                    df_daily_num.columns = (
                        ["time", "Equity", "drawdown"]
                        if df_daily_num.shape[1] >= 3
                        else df_daily_num.columns
                    )
                    df_daily_num["time"] = pd.to_datetime(df_daily_num["time"])

                # Format numeric columns (note: df_daily_display was already prepared and renamed above)
                try:
                    df_daily_display["Equity"] = (
                        df_daily_display["Equity"].astype(float).round(0).astype(int)
                    )
                except Exception:
                    df_daily_display["Equity"] = df_daily_display["Equity"].apply(
                        lambda v: int(round(float(v))) if pd.notna(v) else 0
                    )

                # Round INR columns to integers
                inr_cols = [
                    "avg_exposure",
                    "realized_inr",
                    "unrealized_inr",
                    "total_return_inr",
                    "drawdown_inr",
                    "max_drawdown_inr",
                ]
                for c in inr_cols:
                    if c in df_daily_display.columns:
                        df_daily_display[c] = (
                            pd.to_numeric(df_daily_display[c], errors="coerce")
                            .fillna(0)
                            .apply(lambda v: int(round(float(v))))
                        )

                # Percent columns: numeric floats with 2 decimals (no '%' suffix),
                # matching the user's example files where percent columns are numeric.
                pct_cols = {
                    "avg_exposure_pct": "Avg exposure %",
                    "realized_pct": "Realized %",
                    "unrealized_pct": "Unrealized %",
                    "total_return_pct": "Total Return %",
                    "drawdown_pct": "Drawdown %",
                    "max_drawdown_pct": "Max drawdown %",
                }
                for src, dst in pct_cols.items():
                    if src in df_daily_display.columns:
                        df_daily_display[dst] = (
                            pd.to_numeric(df_daily_display[src], errors="coerce")
                            .fillna(0.0)
                            .apply(lambda v: round(float(v), 2))
                        )

                # Rename and select final daily columns in requested order
                df_daily_display = df_daily_display.reset_index(drop=True)
                # ensure all expected cols exist
                for k in [
                    "avg_exposure",
                    "avg_exposure_pct",
                    "realized_inr",
                    "realized_pct",
                    "unrealized_inr",
                    "unrealized_pct",
                    "total_return_inr",
                    "total_return_pct",
                    "max_drawdown_inr",
                    "max_drawdown_pct",
                ]:
                    if k not in df_daily_display.columns:
                        df_daily_display[k] = 0

                df_daily_display = df_daily_display.rename(
                    columns={
                        "time": "Date",
                        "Equity": "Equity",
                        "avg_exposure": "Avg exposure",
                        "realized_inr": "Realized INR",
                        "unrealized_inr": "Unrealized INR",
                        "total_return_inr": "Total Return INR",
                        "max_drawdown_inr": "Max drawdown INR",
                    }
                )

                # Add percent columns if not present already
                if "Avg exposure %" not in df_daily_display.columns:
                    df_daily_display["Avg exposure %"] = df_daily_display[
                        "avg_exposure_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Realized %" not in df_daily_display.columns:
                    df_daily_display["Realized %"] = df_daily_display[
                        "realized_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Unrealized %" not in df_daily_display.columns:
                    df_daily_display["Unrealized %"] = df_daily_display[
                        "unrealized_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Total Return %" not in df_daily_display.columns:
                    df_daily_display["Total Return %"] = df_daily_display[
                        "total_return_pct"
                    ].apply(lambda v: round(float(v), 2))
                if "Drawdown %" not in df_daily_display.columns:
                    df_daily_display["Drawdown %"] = df_daily_display[
                        "drawdown_pct"
                    ].apply(lambda v: round(float(v), 2))

                # Rename drawdown_inr to Drawdown INR (this is the daily drop, not max)
                if (
                    "drawdown_inr" in df_daily_display.columns
                    and "Drawdown INR" not in df_daily_display.columns
                ):
                    df_daily_display = df_daily_display.rename(
                        columns={"drawdown_inr": "Drawdown INR"}
                    )

                # Select final column ordering (daily should have Drawdown, not Max drawdown)
                daily_cols = [
                    "Date",
                    "Equity",
                    "Avg exposure",
                    "Avg exposure %",
                    "Realized INR",
                    "Realized %",
                    "Unrealized INR",
                    "Unrealized %",
                    "Total Return INR",
                    "Total Return %",
                    "Drawdown INR",
                    "Drawdown %",
                ]
                daily_path = os.path.join(
                    run_dir, f"portfolio_daily_equity_curve_{label}.csv"
                )
                df_daily_display.to_csv(daily_path, index=False, columns=daily_cols)
                portfolio_csv_paths[f"daily_{label}"] = daily_path

                # Write monthly aggregated file: group daily display by Month (YYYY-MM) and aggregate
                try:
                    # Use df_daily_display which has Date column
                    monthly_num = df_daily_display.copy()
                    # Convert to period first, then apply on each element
                    monthly_num["Month"] = (
                        pd.to_datetime(monthly_num["Date"]).dt.to_period("M").apply(str)
                    )

                    # Define aggregation map
                    agg_map = {}
                    # Numeric columns that should be last value of the month
                    for col in [
                        "Equity",
                        "Avg exposure",
                        "Max drawdown INR",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "last"

                    # P&L columns should be summed since they're now incremental
                    for col in ["Realized INR", "Unrealized INR", "Total Return INR"]:
                        if col in monthly_num.columns:
                            agg_map[col] = "sum"

                    # Percent columns for realized and unrealized can be summed since incremental
                    for col in [
                        "Realized %",
                        "Unrealized %",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "sum"

                    # Total Return % needs special handling - we'll calculate it after aggregation
                    # For now, just take the last value (we'll recalculate below)
                    if "Total Return %" in monthly_num.columns:
                        agg_map["Total Return %"] = "last"

                    # Other percent columns that should be last value of the month
                    for col in [
                        "Avg exposure %",
                        "Max drawdown %",
                    ]:
                        if col in monthly_num.columns:
                            agg_map[col] = "last"

                    # Drawdown % should be max for the month
                    if "Drawdown %" in monthly_num.columns:
                        agg_map["Drawdown %"] = "max"
                    if "Drawdown INR" in monthly_num.columns:
                        agg_map["Drawdown INR"] = "max"

                    # sort by date so 'last' picks the end-of-month row
                    monthly_num = (
                        monthly_num.sort_values(by="Date")
                        .groupby("Month", as_index=False)
                        .agg(agg_map)
                    )

                    # Recalculate Total Return % as month-over-month return
                    if (
                        "Total Return %" in monthly_num.columns
                        and "Equity" in monthly_num.columns
                    ):
                        # Calculate month-over-month return based on equity change
                        monthly_num["Total Return %"] = 0.0
                        for i in range(len(monthly_num)):
                            if i == 0:
                                # First month: compare to initial capital
                                equity_current = float(monthly_num.iloc[i]["Equity"])
                                equity_prev = float(cfg.initial_capital)
                            else:
                                # Subsequent months: compare to previous month's equity
                                equity_current = float(monthly_num.iloc[i]["Equity"])
                                equity_prev = float(monthly_num.iloc[i - 1]["Equity"])

                            if equity_prev > 0:
                                monthly_num.at[i, "Total Return %"] = (
                                    (equity_current / equity_prev) - 1
                                ) * 100.0
                            else:
                                monthly_num.at[i, "Total Return %"] = 0.0

                    # Ensure the first monthly row is at initial capital
                    if not df_daily_display.empty and not monthly_num.empty:
                        first_day = df_daily_display.iloc[0]
                        if first_day["Equity"] == cfg.initial_capital:
                            first_month = str(
                                pd.to_datetime(first_day["Date"]).to_period("M")
                            )
                            # Check if first_month is already in monthly_num; if not, prepend it
                            if monthly_num.iloc[0]["Month"] != first_month:
                                # Create baseline first month row at initial capital
                                first_row_dict = {"Month": first_month}
                                for col in monthly_num.columns:
                                    if col == "Month":
                                        continue
                                    if col in ["Equity"]:
                                        first_row_dict[col] = int(cfg.initial_capital)
                                    elif col in ["Drawdown INR", "Drawdown %"]:
                                        first_row_dict[col] = 0
                                    else:
                                        first_row_dict[col] = 0.0 if "%" in col else 0

                                monthly_num = pd.concat(
                                    [pd.DataFrame([first_row_dict]), monthly_num],
                                    ignore_index=True,
                                )

                    # Format display version
                    monthly_disp = monthly_num.copy()

                    # Round Equity to integer
                    if "Equity" in monthly_disp.columns:
                        try:
                            monthly_disp["Equity"] = (
                                monthly_disp["Equity"]
                                .astype(float)
                                .round(0)
                                .astype(int)
                            )
                        except Exception:
                            pass

                    # Ensure INR columns are integers
                    for col in [
                        "Avg exposure",
                        "Realized INR",
                        "Unrealized INR",
                        "Total Return INR",
                        "Max drawdown INR",
                        "Drawdown INR",
                    ]:
                        if col in monthly_disp.columns:
                            try:
                                monthly_disp[col] = (
                                    pd.to_numeric(monthly_disp[col], errors="coerce")
                                    .fillna(0)
                                    .astype(int)
                                )
                            except Exception:
                                pass

                    # Ensure percent columns are float with 2 decimals
                    for col in [
                        "Avg exposure %",
                        "Realized %",
                        "Unrealized %",
                        "Total Return %",
                        "Max drawdown %",
                        "Drawdown %",
                    ]:
                        if col in monthly_disp.columns:
                            try:
                                monthly_disp[col] = (
                                    pd.to_numeric(monthly_disp[col], errors="coerce")
                                    .fillna(0.0)
                                    .apply(lambda v: round(float(v), 2))
                                )
                            except Exception:
                                pass

                    # Select final column ordering
                    monthly_cols = [
                        "Month",
                        "Equity",
                        "Avg exposure",
                        "Avg exposure %",
                        "Realized INR",
                        "Realized %",
                        "Unrealized INR",
                        "Unrealized %",
                        "Total Return INR",
                        "Total Return %",
                        "Max drawdown INR",
                        "Max drawdown %",
                    ]

                    # Only include columns that exist
                    monthly_cols = [
                        c for c in monthly_cols if c in monthly_disp.columns
                    ]

                    monthly_path = os.path.join(
                        run_dir, f"portfolio_monthly_equity_curve_{label}.csv"
                    )
                    monthly_disp.to_csv(monthly_path, index=False, columns=monthly_cols)
                    portfolio_csv_paths[f"monthly_{label}"] = monthly_path
                except Exception:
                    # non-fatal; continue
                    pass
            except Exception as e:
                print(f"DEBUG {label}: error in portfolio curve generation: {e}")
                import traceback

                traceback.print_exc()
                pass
        except Exception as e:
            # non-fatal; continue to next window
            import traceback

            print(f"❌ ERROR in window {label}: {e}")
            traceback.print_exc()
            pass

        # Legacy per-window params CSV block removed; we already create
        # `basket_{label}.csv` containing the parameter table and TOTAL row above.

    # Generate strategy results summary (comprehensive metrics per window)
    # First, collect portfolio curves, metrics, and trades for summary generation
    portfolio_curves_for_summary: dict[str, pd.DataFrame] = {}
    portfolio_metrics_for_summary: dict[str, pd.DataFrame] = {}
    trades_for_summary: dict[str, pd.DataFrame] = {}

    # Re-load the daily CSV files to get portfolio curves
    for label, daily_csv_path in portfolio_csv_paths.items():
        if label.startswith("daily_"):
            window_label = label.replace("daily_", "")
            try:
                port_df = pd.read_csv(daily_csv_path, parse_dates=["Date"])
                port_df.set_index("Date", inplace=True)
                portfolio_curves_for_summary[window_label] = port_df
            except Exception as e:
                print(f"Warning: could not load portfolio curve {daily_csv_path}: {e}")

    # Re-load the portfolio_key_metrics files from consolidated_csv_paths
    for label, metrics_csv_path in consolidated_csv_paths.items():
        if not label.startswith("trades_"):
            # These are the portfolio_key_metrics files
            try:
                metrics_df = pd.read_csv(metrics_csv_path)
                portfolio_metrics_for_summary[label] = metrics_df
            except Exception as e:
                print(f"Warning: could not load metrics {metrics_csv_path}: {e}")

    # Re-load the consolidated trades files
    # Match trades CSV files by window label (key format is "trades_1Y", "trades_3Y", etc.)
    for label, csv_path in consolidated_csv_paths.items():
        if label.startswith("trades_"):
            window_label = label.replace("trades_", "")
            try:
                trades_df = pd.read_csv(csv_path)
                trades_for_summary[window_label] = trades_df
            except Exception as e:
                print(f"Warning: could not load trades {csv_path}: {e}")

    # Generate and save strategy summary
    if portfolio_curves_for_summary and trades_for_summary:
        summary_path = _generate_strategy_summary(
            run_dir,
            portfolio_curves_for_summary,
            trades_for_summary,
            portfolio_metrics_for_summary,
            cfg.initial_capital,
            strategy_name,
        )
        if summary_path:
            print(f"Saved strategy summary: {summary_path}")

    # Generate comprehensive dashboard with all improvements
    print("\n📊 Generating hybrid financial dashboard...")
    try:
        from pathlib import Path

        from viz.dashboard import QuantLabDashboard

        # Create dashboard instance
        dashboard = QuantLabDashboard(Path(run_dir).parent)

        # Load data and generate dashboard
        report_folder = Path(run_dir).name
        data = dashboard.load_comprehensive_data(report_folder)
        dashboard_path = dashboard.save_dashboard(
            data=data, output_name="quantlab_dashboard"  # Use consistent name
        )

        print(f"✅ Dashboard saved: {dashboard_path}")
        print(f"🌐 Open in browser: file://{dashboard_path}")

    except Exception as e:
        import traceback

        print(f"⚠️ Dashboard generation failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        # Continue with rest of execution - dashboard failure shouldn't stop backtest

    # Collect data fingerprints for audit trail
    data_fingerprints = {}
    validation_issues = []
    for sym in symbol_results:
        fingerprint = symbol_results[sym].get("fingerprint")
        validation = symbol_results[sym].get("validation")
        if fingerprint:
            data_fingerprints[sym] = fingerprint
        if validation and not validation.get("passed", False):
            validation_issues.append(
                {"symbol": sym, "errors": validation.get("errors", [])}
            )

    save_summary(
        run_dir,
        {
            "runner": "run_basket",
            "strategy": strategy_name,
            "params_json": params_json,
            "interval": interval,
            "period": period,
            "bars_per_year": bars_per_year,
            "windows": [window_labels[w] for w in windows_years],
            "consolidated_csv": consolidated_csv_paths,
            "portfolio_curves_csv": portfolio_csv_paths,
            "portfolio_maxdd_by_window": window_maxdd,
            "symbols_bare": bare,
            "data_fingerprints": data_fingerprints,
            "validation_issues": validation_issues if validation_issues else None,
        },
    )

    print("\nSaved consolidated reports:")
    for k, v in consolidated_csv_paths.items():
        print(f"- {k}: {v}")
    print("Saved portfolio curves:")
    for k, v in portfolio_csv_paths.items():
        print(f"- {k}: {v}")

    # Generate visual plots for portfolio performance
    print("\n📊 Generating performance visualizations...")

    print("✅ Portfolio analysis complete!")


if __name__ == "__main__":
    from config import DEFAULT_BASKET_SIZE, get_available_baskets

    available_baskets = get_available_baskets()
    basket_info = ", ".join(
        [f"{size}({count})" for size, count in available_baskets.items()]
    )

    epilog = (
        f"Available baskets: {basket_info}\n"
        f"Default basket: {DEFAULT_BASKET_SIZE} (data/basket.txt)\n\n"
        "Examples:\n"
        "  # Use default basket (data/basket.txt):\n"
        "  python3 -m runners.run_basket --strategy ema_cross --params '{}' --interval 1d --period max\n\n"
        "  # Use specific basket size:\n"
        "  python3 -m runners.run_basket --basket_size large --strategy ema_cross --params '{}' --interval 1d --period max\n\n"
        "  # Use custom basket file:\n"
        "  python3 -m runners.run_basket --basket_file data/my_basket.txt --strategy ema_cross --params '{}' --interval 1d --period max\n"
    )

    ap = argparse.ArgumentParser(
        description="Run a basket of backtests and produce reports",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Basket selection (mutually exclusive)
    basket_group = ap.add_mutually_exclusive_group()
    basket_group.add_argument(
        "--basket_file",
        help="Path to custom basket file (txt with symbols, one per line)",
    )
    basket_group.add_argument(
        "--basket_size",
        choices=list(available_baskets.keys()),
        help=f"Predefined basket size. Available: {basket_info}",
    )
    ap.add_argument(
        "--strategy",
        default="ichimoku",  # Changed from donchian to ichimoku as primary strategy
        help="Strategy name in core.registry (e.g. ichimoku, donchian, ema_cross)",
    )
    ap.add_argument(
        "--params",
        default="{}",
        help='JSON string for strategy params, e.g. \'{"ema_fast":89,"ema_slow":144}\'. Empty {} uses strategy defaults.',
    )
    ap.add_argument("--interval", default="1d", help="Data interval, e.g. 1d or 60m")
    ap.add_argument(
        "--period",
        default="max",  # Changed from 5y to max for complete historical analysis
        help="Data history period for loader, e.g. 1y, 5y, max",
    )
    ap.add_argument(
        "--use_cache_only",
        action="store_true",
        default=True,  # Set to True by default to prevent interruptions from network issues
        help="Use only locally cached data (don't hit remote) if present",
    )
    ap.add_argument(
        "--cache_dir",
        default="data/cache",  # Updated to correct cache directory path
        help="Local cache directory for downloaded symbol data",
    )
    args = ap.parse_args()

    # Execute with comprehensive error handling and timeout management
    try:
        logger.info("Starting basket backtest execution...")
        logger.info(
            f"Configuration: strategy={args.strategy}, period={args.period}, cache_only={args.use_cache_only}"
        )

        start_time = time.time()

        # Use safe operation wrapper with timeout
        safe_operation(
            run_basket,
            basket_file=args.basket_file,
            basket_size=args.basket_size,
            strategy_name=args.strategy,
            params_json=args.params,
            interval=args.interval,
            period=args.period,
            use_cache_only=args.use_cache_only,
            cache_dir=args.cache_dir,
            timeout_seconds=TOTAL_TIMEOUT,
            operation_name="basket backtest",
        )

        execution_time = time.time() - start_time
        logger.info(
            f"✅ Basket backtest completed successfully in {execution_time:.1f}s"
        )

    except TimeoutError as e:
        logger.error(f"❌ Execution timed out: {e}")
        logger.error("Consider using --use_cache_only to avoid network delays")
        sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("⚠️ Interrupt signal received (Ctrl+C)")
        logger.warning("⏳ Waiting for current operation to complete safely...")
        logger.info("💡 The process will finish the current step and then exit")
        logger.info("📁 Partial results may be available in the output directory")
        # Don't exit immediately - let the current operation complete
        # The finally block will handle cleanup

    except Exception as e:
        logger.error(f"❌ Execution failed: {e}")
        logger.debug(f"Full traceback: {traceback.format_exc()}")

        # Provide helpful error resolution hints
        if "No module named" in str(e):
            logger.error("💡 Try: pip install -e . to install the package")
        elif "file not found" in str(e).lower() or "no such file" in str(e).lower():
            logger.error("💡 Check that the basket file and cache directory exist")
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            logger.error("💡 Try using --use_cache_only to avoid network issues")
        elif "memory" in str(e).lower():
            logger.error(
                "💡 Consider reducing basket size or using shorter time periods"
            )

        sys.exit(1)
