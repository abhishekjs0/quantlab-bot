# runners/run_basket.py
# ✅ PRODUCTION RUNNER - Optimized v2 with macOS fork support
# High-performance backtesting with multiprocessing (4-8x speedup)
#
# Features:
# - Phase 1+2+3 optimizations (indicator cache, fast iteration, NaN safety)
# - Platform-aware multiprocessing (fork on macOS/Linux, spawn fallback)
# - Auto-detects CPU cores for worker pool sizing
# - Production-ready with comprehensive error handling

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

# Also clear any .pyc files that might exist outside __pycache__
for _pyc_file in _workspace_root.rglob('*.pyc'):
    try:
        _pyc_file.unlink()
    except Exception:
        pass
# ============================================================================

import platform
import signal
import time
import traceback
import warnings
from contextlib import contextmanager
from multiprocessing import Pool, cpu_count, get_context

import numpy as np
import pandas as pd

# Suppress misleading FutureWarning for infer_objects + ffill/fillna
warnings.filterwarnings("ignore", message=".*Downcasting object dtype arrays.*")

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
from core.loaders import load_many_india

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Timer for performance monitoring
# ============================================================================
class Timer:
    """Simple timer for performance monitoring"""
    def __init__(self):
        self.timings = {}
    
    @contextmanager
    def measure(self, phase_name):
        """Context manager to measure execution time"""
        start = time.time()
        yield
        elapsed = time.time() - start
        self.timings[phase_name] = self.timings.get(phase_name, 0) + elapsed
    
    def report(self):
        """Print timing report"""
        print("\n" + "=" * 80)
        print("⏱️  EXECUTION TIME REPORT")
        print("=" * 80)
        total = sum(self.timings.values())
        for phase, duration in sorted(self.timings.items(), key=lambda x: x[1], reverse=True):
            pct = (duration / total * 100) if total > 0 else 0
            print(f"  {phase:40s} {duration:8.2f}s ({pct:5.1f}%)")
        print("-" * 80)
        print(f"  {'TOTAL':40s} {total:8.2f}s (100.0%)")
        print("=" * 80)

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
TOTAL_TIMEOUT = 7200  # 2 hours total limit (increased for large baskets with MAX window)

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


def _enrich_with_nifty200_ema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add nifty200_above_ema50 indicator to DataFrame for strategy filters.
    
    This is needed because some strategies (like ichimoku_cloud) use market regime
    filters that check if NIFTY200 > EMA 50.
    NIFTY200 is a broader market representation than NIFTY50.
    """
    import numpy as np
    from utils import EMA
    from core.loaders import load_nifty200
    
    try:
        nifty200_df = load_nifty200()
        nifty200_close = nifty200_df['close'].values
        nifty200_ema50 = EMA(nifty200_close, 50)
        
        # Create series aligned with nifty200 index
        nifty200_above_50 = pd.Series(nifty200_close > nifty200_ema50, index=nifty200_df.index)
        
        # Join with stock data
        df = df.join(nifty200_above_50.rename('nifty200_above_ema50'), how='left')
        
        # Forward fill for alignment, fill missing with True (graceful degradation)
        df['nifty200_above_ema50'] = df['nifty200_above_ema50'].infer_objects(copy=False).ffill().fillna(True).astype(bool)
    except Exception:
        # If NIFTY200 data not available, default to True (allow trades)
        df['nifty200_above_ema50'] = True
    
    return df


# Backward compatibility alias
_enrich_with_nifty50_ema = _enrich_with_nifty200_ema


# ===== MODULE-LEVEL FUNCTION FOR MULTIPROCESSING =====
# This must be at module level (not nested) to be pickleable for multiprocessing
def _process_symbol_for_backtest(args):
    """
    Process a single symbol for parallel execution.
    This function is module-level to be pickleable with multiprocessing.
    To avoid pickling large dataframes, we only pass symbol info and rebuild data in worker.
    """
    sym, sym_idx, total_syms, strategy_name, params_json, cache_dir, interval, period, compounding = args
    try:
        import sys
        print(f"[WORKER {sym_idx}/{total_syms}] Processing {sym}...", flush=True)
        sys.stdout.flush()
        
        # Set defaults if not provided
        if interval is None:
            interval = "1d"
        if period is None:
            period = "max"
            
        # Load data in worker process (avoid pickling large dicts with spawn)
        print(f"[WORKER {sym_idx}/{total_syms}] Loading data for {sym} from {cache_dir}...", flush=True)
        sys.stdout.flush()
        
        data_map = load_many_india(
            [sym],
            interval=interval,
            period=period,
            cache=True,
            cache_dir=cache_dir,
            use_cache_only=True,
        )
        
        if sym not in data_map or data_map[sym] is None or data_map[sym].empty:
            print(f"[WORKER {sym_idx}/{total_syms}] No data for {sym}", flush=True)
            sys.stdout.flush()
            return sym, None, f"No data for {sym}"

        df_full = data_map[sym]
        
        # Enrich with NIFTY200 EMA indicator for market regime filter
        df_full = _enrich_with_nifty200_ema(df_full)
        
        print(f"[WORKER {sym_idx}/{total_syms}] Running backtest for {sym}...", flush=True)
        sys.stdout.flush()
        
        strat = make_strategy(strategy_name, params_json)
        engine = BacktestEngine(
            df_full, strat, BrokerConfig(compounding=compounding), symbol=sym
        )
        trades_full, equity_full, _ = engine.run()

        print(f"[WORKER {sym_idx}/{total_syms}] ✅ Completed {sym}", flush=True)
        sys.stdout.flush()
        
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
        import traceback
        print(f"[WORKER {sym_idx}/{total_syms}] ❌ Error for {sym}: {e}", flush=True)
        traceback.print_exc()
        import sys
        sys.stdout.flush()
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


def _calculate_all_indicators_for_consolidated(df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
    """Calculate ALL indicators for consolidated file export.
    
    This function calculates all 56+ indicators needed for the consolidated files.
    Includes regime filters, trend strength, momentum, trend structure, volume indicators,
    and weekly multi-timeframe indicators (RSI, MACD, ADX, EMA).
    
    Args:
        df: OHLCV DataFrame with DatetimeIndex (daily)
        symbol: Stock symbol for loading weekly data (optional)
        
    Returns:
        DataFrame with all OHLCV data + all indicator columns
    """
    if df.empty:
        return df
    
    result_df = df.copy()
    
    # Pre-calculate OHLCV arrays (vectorized once)
    high_arr = df["high"].astype(float).values
    low_arr = df["low"].astype(float).values
    close_arr = df["close"].astype(float).values
    volume_arr = df["volume"].astype(float).values
    
    # Import all indicator functions
    from utils import ATR, EMA, MACD, RSI, SMA, BollingerBands, Stochastic
    from utils.indicators import (
        ADX, CCI, MFI, CMF, Aroon, BullBearPower, StochasticRSI,
        TrendClassification, VolatilityClassification,
        calculate_stochastic_slow, extract_ichimoku_base_line,
        kaufman_efficiency_ratio,
    )
    from core.loaders import load_india_vix, load_nifty200
    
    # ========== REGIME FILTERS ==========
    
    # India VIX
    try:
        vix_df = load_india_vix()
        # Align VIX with stock data
        result_df = result_df.join(vix_df[['close']].rename(columns={'close': 'vix_value'}), how='left')
        result_df['vix_value'] = result_df['vix_value'].ffill().bfill()
        
        # Use current VIX value as-is (no classification)
        result_df['india_vix'] = result_df['vix_value']
    except Exception:
        result_df['india_vix'] = np.nan
    
    # NIFTY200 EMA comparisons (broader market representation than NIFTY50)
    try:
        nifty200_df = load_nifty200()
        nifty200_close = nifty200_df['close'].values
        nifty200_ema5 = EMA(nifty200_close, 5)
        nifty200_ema20 = EMA(nifty200_close, 20)
        nifty200_ema50 = EMA(nifty200_close, 50)
        nifty200_ema100 = EMA(nifty200_close, 100)
        nifty200_ema200 = EMA(nifty200_close, 200)
        
        # Normalize NIFTY200 index to date-only (remove time component)
        nifty200_dates = pd.to_datetime(nifty200_df.index).normalize()
        
        # Create series aligned with normalized nifty200 dates
        nifty200_above_5 = pd.Series(nifty200_close > nifty200_ema5, index=nifty200_dates)
        nifty200_above_20 = pd.Series(nifty200_close > nifty200_ema20, index=nifty200_dates)
        nifty200_above_50 = pd.Series(nifty200_close > nifty200_ema50, index=nifty200_dates)
        nifty200_above_100 = pd.Series(nifty200_close > nifty200_ema100, index=nifty200_dates)
        nifty200_above_200 = pd.Series(nifty200_close > nifty200_ema200, index=nifty200_dates)
        
        # DROP any existing NIFTY200 columns to avoid join suffix issues
        for col in ['nifty200_above_ema5', 'nifty200_above_ema20', 'nifty200_above_ema50', 'nifty200_above_ema100', 'nifty200_above_ema200']:
            if col in result_df.columns:
                result_df = result_df.drop(columns=[col])
        
        # Normalize result_df index to date-only for proper alignment
        result_dates = pd.to_datetime(result_df.index).normalize()
        
        # Map NIFTY200 values to result_df using normalized dates
        result_df['nifty200_above_ema5'] = result_dates.map(lambda d: nifty200_above_5.get(d, pd.NA))
        result_df['nifty200_above_ema20'] = result_dates.map(lambda d: nifty200_above_20.get(d, pd.NA))
        result_df['nifty200_above_ema50'] = result_dates.map(lambda d: nifty200_above_50.get(d, pd.NA))
        result_df['nifty200_above_ema100'] = result_dates.map(lambda d: nifty200_above_100.get(d, pd.NA))
        result_df['nifty200_above_ema200'] = result_dates.map(lambda d: nifty200_above_200.get(d, pd.NA))
        
        # Forward fill for alignment, then fill remaining NaN with True (skip filter on missing data)
        result_df['nifty200_above_ema5'] = result_df['nifty200_above_ema5'].ffill().fillna(True).astype(bool)
        result_df['nifty200_above_ema20'] = result_df['nifty200_above_ema20'].ffill().fillna(True).astype(bool)
        result_df['nifty200_above_ema50'] = result_df['nifty200_above_ema50'].ffill().fillna(True).astype(bool)
        result_df['nifty200_above_ema100'] = result_df['nifty200_above_ema100'].ffill().fillna(True).astype(bool)
        result_df['nifty200_above_ema200'] = result_df['nifty200_above_ema200'].ffill().fillna(True).astype(bool)
    except Exception:
        # Match strategy behavior: skip filter on error (return True)
        result_df['nifty200_above_ema5'] = True
        result_df['nifty200_above_ema20'] = True
        result_df['nifty200_above_ema50'] = True
        result_df['nifty200_above_ema100'] = True
        result_df['nifty200_above_ema200'] = True
    
    # Aroon Trend Classification (25, 50, 100)
    aroon_25 = Aroon(high_arr, low_arr, 25)
    aroon_50 = Aroon(high_arr, low_arr, 50)
    aroon_100 = Aroon(high_arr, low_arr, 100)
    
    result_df['short_trend_aroon25'] = [
        TrendClassification(aroon_25['aroon_up'][i], aroon_25['aroon_down'][i], period=25)
        if i < len(aroon_25['aroon_up']) else 'Sideways'
        for i in range(len(df))
    ]
    result_df['medium_trend_aroon50'] = [
        TrendClassification(aroon_50['aroon_up'][i], aroon_50['aroon_down'][i], period=50)
        if i < len(aroon_50['aroon_up']) else 'Sideways'
        for i in range(len(df))
    ]
    result_df['long_trend_aroon100'] = [
        TrendClassification(aroon_100['aroon_up'][i], aroon_100['aroon_down'][i], period=100)
        if i < len(aroon_100['aroon_up']) else 'Sideways'
        for i in range(len(df))
    ]
    
    # Volatility (14, 28)
    atr_14 = ATR(high_arr, low_arr, close_arr, 14)
    atr_28 = ATR(high_arr, low_arr, close_arr, 28)
    atr_pct_14 = (atr_14 / close_arr) * 100
    atr_pct_28 = (atr_28 / close_arr) * 100
    
    result_df['volatility_14'] = [VolatilityClassification(atr_pct_14[i], period=14) for i in range(len(df))]
    result_df['volatility_28'] = [VolatilityClassification(atr_pct_28[i], period=28) for i in range(len(df))]
    
    # ========== TREND STRENGTH FILTERS ==========
    
    # ADX (14, 28)
    adx_14 = ADX(high_arr, low_arr, close_arr, 14)
    adx_28 = ADX(high_arr, low_arr, close_arr, 28)
    
    result_df['adx_14'] = adx_14['adx']
    result_df['adx_28'] = adx_28['adx']
    result_df['di_bullish_14'] = adx_14['di_plus'] > adx_14['di_minus']
    result_df['di_bullish_28'] = adx_28['di_plus'] > adx_28['di_minus']
    
    # Bull/Bear Power (13, 26)
    bbp_13 = BullBearPower(high_arr, low_arr, close_arr, 13)
    bbp_26 = BullBearPower(high_arr, low_arr, close_arr, 26)
    

    
    # ========== MOMENTUM FILTERS ==========
    
    # RSI (14, 28)
    result_df['rsi_14'] = RSI(close_arr, 14)
    result_df['rsi_28'] = RSI(close_arr, 28)
    
    # MACD (12,26,9 and 24,52,18)
    macd_12_26_9 = MACD(close_arr, 12, 26, 9)
    macd_24_52_18 = MACD(close_arr, 24, 52, 18)
    
    result_df['macd_bullish_12_26_9'] = macd_12_26_9['macd'] > macd_12_26_9['signal']
    result_df['macd_bullish_24_52_18'] = macd_24_52_18['macd'] > macd_24_52_18['signal']
    
    # Stochastic (14,3 and 28,3)
    stoch_14_3 = Stochastic(high_arr, low_arr, close_arr, 14, 1, 3)
    stoch_28_3 = Stochastic(high_arr, low_arr, close_arr, 28, 1, 3)
    
    result_df['stoch_bullish_14_3'] = stoch_14_3['k'] > stoch_14_3['d']
    result_df['stoch_bullish_28_3'] = stoch_28_3['k'] > stoch_28_3['d']
    
    # Stochastic Slow (5,3,3 and 10,3,3)
    stoch_slow_5 = calculate_stochastic_slow(high_arr, low_arr, close_arr, 5, 3, 3)
    stoch_slow_10 = calculate_stochastic_slow(high_arr, low_arr, close_arr, 10, 3, 3)
    
    result_df['stoch_slow_bullish_5_3_3'] = stoch_slow_5['slow_k'] > stoch_slow_5['slow_d']
    result_df['stoch_slow_bullish_10_3_3'] = stoch_slow_10['slow_k'] > stoch_slow_10['slow_d']
    
    # StochRSI - Four variants (RSI; Stoch; K_Smooth; D_Smooth)
    stoch_rsi_14_5_3_3 = StochasticRSI(close_arr, 14, 5, 3, 3)
    stoch_rsi_14_10_5_5 = StochasticRSI(close_arr, 14, 10, 5, 5)
    stoch_rsi_14_14_3_3 = StochasticRSI(close_arr, 14, 14, 3, 3)
    stoch_rsi_28_20_10_10 = StochasticRSI(close_arr, 28, 20, 10, 10)
    stoch_rsi_28_28_3_3 = StochasticRSI(close_arr, 28, 28, 3, 3)
    stoch_rsi_28_5_3_3 = StochasticRSI(close_arr, 28, 5, 3, 3)
    
    result_df['stoch_rsi_k_14_5_3_3'] = np.round(stoch_rsi_14_5_3_3['k'], 2)
    result_df['stoch_rsi_k_14_10_5_5'] = np.round(stoch_rsi_14_10_5_5['k'], 2)
    result_df['stoch_rsi_k_14_14_3_3'] = np.round(stoch_rsi_14_14_3_3['k'], 2)
    result_df['stoch_rsi_k_28_20_10_10'] = np.round(stoch_rsi_28_20_10_10['k'], 2)
    result_df['stoch_rsi_k_28_28_3_3'] = np.round(stoch_rsi_28_28_3_3['k'], 2)
    result_df['stoch_rsi_k_28_5_3_3'] = np.round(stoch_rsi_28_5_3_3['k'], 2)
    
    # ========== TREND STRUCTURE FILTERS ==========
    
    # EMAs (5, 20, 50, 100, 200)
    ema_5 = EMA(close_arr, 5)
    ema_20 = EMA(close_arr, 20)
    ema_50 = EMA(close_arr, 50)
    ema_100 = EMA(close_arr, 100)
    ema_200 = EMA(close_arr, 200)
    
    result_df['price_above_ema5'] = close_arr > ema_5
    result_df['price_above_ema20'] = close_arr > ema_20
    result_df['price_above_ema50'] = close_arr > ema_50
    result_df['price_above_ema100'] = close_arr > ema_100
    result_df['price_above_ema200'] = close_arr > ema_200
    result_df['ema5_above_ema20'] = ema_5 > ema_20
    result_df['ema20_above_ema50'] = ema_20 > ema_50
    result_df['ema50_above_ema100'] = ema_50 > ema_100
    result_df['ema50_above_ema200'] = ema_50 > ema_200
    
    # Ichimoku Kijun (26, 52)
    kijun_26 = extract_ichimoku_base_line(high_arr, low_arr, 26)
    kijun_52 = extract_ichimoku_base_line(high_arr, low_arr, 52)
    

    
    # Tenkan/Kijun (9,26 and 18,52)
    tenkan_9 = extract_ichimoku_base_line(high_arr, low_arr, 9)
    tenkan_18 = extract_ichimoku_base_line(high_arr, low_arr, 18)
    
    result_df['tenkan_above_kijun_9_26'] = tenkan_9 > kijun_26
    result_df['tenkan_above_kijun_18_52'] = tenkan_18 > kijun_52
    
    # Bollinger Bands Position (20,2 and 40,2)
    bb_20 = BollingerBands(close_arr, 20, 2)
    bb_40 = BollingerBands(close_arr, 40, 2)
    
    def bb_position(close, upper, lower):
        return np.where(close > upper, 'Above', np.where(close < lower, 'Below', 'Middle'))
    
    result_df['bb_position_20_2'] = bb_position(close_arr, bb_20['upper'], bb_20['lower'])
    result_df['bb_position_40_2'] = bb_position(close_arr, bb_40['upper'], bb_40['lower'])
    
    # ========== CHOPPINESS INDEX (20) ==========
    def choppiness_index_daily(high, low, close, length=14):
        """Calculate Choppiness Index."""
        import math
        n = len(close)
        chop = np.full(n, np.nan)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for j in range(1, n):
            tr[j] = max(high[j] - low[j], abs(high[j] - close[j-1]), abs(low[j] - close[j-1]))
        log_length = math.log10(length)
        for j in range(length, n):
            atr_sum = np.sum(tr[j-length+1:j+1])
            highest_high = np.max(high[j-length+1:j+1])
            lowest_low = np.min(low[j-length+1:j+1])
            range_val = highest_high - lowest_low
            if range_val > 0 and log_length > 0:
                chop[j] = 100 * math.log10(atr_sum / range_val) / log_length
        return chop
    
    def classify_chop_daily(chop_values):
        """Classify CHOP into 4 ranges based on Fibonacci levels."""
        return np.where(chop_values >= 61.8, 'Very Choppy',
               np.where(chop_values >= 50, 'Choppy',
               np.where(chop_values >= 38.2, 'Trending', 'Strong Trend')))
    
    chop_20 = choppiness_index_daily(high_arr, low_arr, close_arr, 20)
    result_df['chop_20_class'] = classify_chop_daily(chop_20)
    
    # ========== CHOPPINESS INDEX (50) ==========
    chop_50 = choppiness_index_daily(high_arr, low_arr, close_arr, 50)
    result_df['chop_50_class'] = classify_chop_daily(chop_50)
    
    # ========== EMA100 ABOVE EMA200 ==========
    ema100 = EMA(close_arr, 100)
    ema200 = EMA(close_arr, 200)
    result_df['ema100_above_ema200'] = ema100 > ema200
    
    # ========== DAILY VOLUME INDICATOR ==========
    # Volume > 20-period SMA of volume
    if 'volume' in df.columns:
        volume = df['volume'].values
        volume_sma20 = SMA(volume, 20)
        result_df['daily_volume_above_ma20'] = volume > volume_sma20
    else:
        result_df['daily_volume_above_ma20'] = False
    
    # ========== DAILY CCI, MFI, CMF (20-period) ==========
    result_df['Daily_CCI (20)'] = CCI(high_arr, low_arr, close_arr, 20)
    result_df['Daily_MFI (20)'] = MFI(high_arr, low_arr, close_arr, volume_arr, 20)
    result_df['Daily_CMF (20)'] = CMF(high_arr, low_arr, close_arr, volume_arr, 20)
    
    # ========== WEEKLY MULTI-TIMEFRAME INDICATORS ==========
    # Load weekly data and calculate RSI, MACD, ADX, EMA, Volume on weekly timeframe
    
    # Initialize weekly indicators with defaults
    result_df['Weekly_RSI (14)'] = np.nan
    result_df['Weekly_MACD_Bullish'] = False
    result_df['Weekly_ADX (14)'] = np.nan
    result_df['Weekly_Above_EMA5'] = False
    result_df['Weekly_Above_EMA20'] = False
    result_df['Weekly_Above_EMA50'] = False
    result_df['Weekly_Above_EMA200'] = False
    result_df['Weekly_Volume_Above_MA20'] = False
    result_df['Weekly_India_VIX'] = np.nan
    result_df['Weekly_BB_Position (20;2)'] = ''
    result_df['Weekly_KER (10)'] = np.nan
    result_df['Weekly_Candle_Colour'] = ''
    result_df['Weekly_Candlestick_Pattern'] = ''
    result_df['Weekly_CHOP (20) Class'] = ''
    result_df['Weekly_Short_Trend (Aroon 25)'] = ''
    result_df['Weekly_Medium_Trend (Aroon 50)'] = ''
    result_df['Weekly_Long_Trend (Aroon 100)'] = ''
    
    # Load weekly INDIA VIX data for all symbols
    weekly_vix_df = None
    try:
        from pathlib import Path as PathLib
        project_root = PathLib(__file__).parent.parent
        # Try to load weekly VIX - resample daily VIX to weekly if weekly not available
        daily_vix_path = project_root / 'data' / 'cache' / 'dhan' / 'daily' / 'dhan_21_INDIA_VIX_1d.csv'
        if daily_vix_path.exists():
            vix_df = pd.read_csv(daily_vix_path)
            vix_df['time'] = pd.to_datetime(vix_df['time'])
            vix_df = vix_df.set_index('time').sort_index()
            # Resample to weekly (last value of week)
            weekly_vix_df = vix_df['close'].resample('W').last().dropna()
    except Exception:
        pass
    
    if symbol:
        try:
            # Try to load weekly data from cache using absolute path
            import glob
            from pathlib import Path
            project_root = Path(__file__).parent.parent
            weekly_pattern = project_root / 'data' / 'cache' / 'groww' / 'weekly' / f'groww_*_{symbol}_1w.csv'
            weekly_files = glob.glob(str(weekly_pattern))
            
            if weekly_files:
                weekly_df = pd.read_csv(weekly_files[0])
                # Parse time - handle both string datetime and Unix timestamp
                if weekly_df['time'].dtype == 'int64':
                    weekly_df['time'] = pd.to_datetime(weekly_df['time'], unit='s')
                else:
                    weekly_df['time'] = pd.to_datetime(weekly_df['time'])
                weekly_df = weekly_df.set_index('time').sort_index()
                
                if not weekly_df.empty:
                    weekly_close = weekly_df['close'].values
                    weekly_high = weekly_df['high'].values
                    weekly_low = weekly_df['low'].values
                    weekly_open = weekly_df['open'].values if 'open' in weekly_df.columns else weekly_close
                    weekly_volume = weekly_df['volume'].values if 'volume' in weekly_df.columns else None
                    
                    # Import additional indicators for weekly calculations
                    from utils.indicators import CCI, MFI, CMF, Aroon, TrendClassification, kaufman_efficiency_ratio
                    
                    # Weekly RSI (14-period on weekly close)
                    weekly_rsi_14 = RSI(weekly_close, 14)
                    
                    # Weekly MACD (12,26,9 on weekly close)
                    weekly_macd = MACD(weekly_close, 12, 26, 9)
                    
                    # Weekly ADX (14 on weekly OHLC)
                    weekly_adx = ADX(weekly_high, weekly_low, weekly_close, 14)
                    
                    # Weekly EMAs (5, 20, 50, 200)
                    weekly_ema5 = EMA(weekly_close, 5)
                    weekly_ema20 = EMA(weekly_close, 20)
                    weekly_ema50 = EMA(weekly_close, 50)
                    weekly_ema200 = EMA(weekly_close, 200)
                    
                    # Weekly volume SMA (20-period)
                    weekly_volume_sma20 = SMA(weekly_volume, 20) if weekly_volume is not None else None
                    
                    # Weekly Bollinger Bands Position (20,2)
                    weekly_bb_20 = BollingerBands(weekly_close, 20, 2)
                    weekly_bb_position = np.where(weekly_close > weekly_bb_20['upper'], 'Above', 
                                                  np.where(weekly_close < weekly_bb_20['lower'], 'Below', 'Middle'))
                    
                    # Daily CCI, MFI, CMF (changed from weekly to daily)
                    # KER is still weekly (as intended)
                    weekly_ker_10 = kaufman_efficiency_ratio(weekly_close, 10)
                    
                    # Weekly candle colour
                    weekly_candle_colour = np.where(weekly_close > weekly_open, 'green', 
                                                    np.where(weekly_close < weekly_open, 'red', 'doji'))
                    
                    # Weekly candlestick patterns
                    try:
                        import talib
                        cdl_hammer = talib.CDLHAMMER(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_inverted_hammer = talib.CDLINVERTEDHAMMER(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_engulfing = talib.CDLENGULFING(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_morning_star = talib.CDLMORNINGSTAR(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_evening_star = talib.CDLEVENINGSTAR(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_shooting_star = talib.CDLSHOOTINGSTAR(weekly_open, weekly_high, weekly_low, weekly_close)
                        cdl_hanging_man = talib.CDLHANGINGMAN(weekly_open, weekly_high, weekly_low, weekly_close)
                        
                        def get_weekly_pattern(idx):
                            if cdl_hammer[idx] != 0: return 'Hammer'
                            if cdl_inverted_hammer[idx] != 0: return 'Inverted Hammer'
                            if cdl_engulfing[idx] > 0: return 'Bullish Engulfing'
                            if cdl_engulfing[idx] < 0: return 'Bearish Engulfing'
                            if cdl_morning_star[idx] != 0: return 'Morning Star'
                            if cdl_evening_star[idx] != 0: return 'Evening Star'
                            if cdl_shooting_star[idx] != 0: return 'Shooting Star'
                            if cdl_hanging_man[idx] != 0: return 'Hanging Man'
                            return ''
                        weekly_candlestick_pattern = [get_weekly_pattern(i) for i in range(len(weekly_close))]
                    except ImportError:
                        weekly_candlestick_pattern = [''] * len(weekly_close)
                    except Exception:
                        weekly_candlestick_pattern = [''] * len(weekly_close)
                    
                    # Weekly Choppiness Index (20)
                    import math
                    def choppiness_index(high, low, close, length=14):
                        n = len(close)
                        chop = np.full(n, np.nan)
                        tr = np.zeros(n)
                        tr[0] = high[0] - low[0]
                        for j in range(1, n):
                            tr[j] = max(high[j] - low[j], abs(high[j] - close[j-1]), abs(low[j] - close[j-1]))
                        log_length = math.log10(length)
                        for j in range(length, n):
                            atr_sum = np.sum(tr[j-length+1:j+1])
                            highest_high = np.max(high[j-length+1:j+1])
                            lowest_low = np.min(low[j-length+1:j+1])
                            range_val = highest_high - lowest_low
                            if range_val > 0 and log_length > 0:
                                chop[j] = 100 * math.log10(atr_sum / range_val) / log_length
                        return chop
                    
                    def classify_chop(chop_values):
                        return np.where(chop_values >= 61.8, 'Very Choppy',
                               np.where(chop_values >= 50, 'Choppy',
                               np.where(chop_values >= 38.2, 'Trending', 'Strong Trend')))
                    
                    weekly_chop_20 = choppiness_index(weekly_high, weekly_low, weekly_close, 20)
                    weekly_chop_20_class = classify_chop(weekly_chop_20)
                    
                    # Weekly Aroon Trend Classification
                    weekly_aroon_25 = Aroon(weekly_high, weekly_low, 25)
                    weekly_aroon_50 = Aroon(weekly_high, weekly_low, 50)
                    weekly_aroon_100 = Aroon(weekly_high, weekly_low, 100)
                    
                    weekly_short_trend = [
                        TrendClassification(weekly_aroon_25['aroon_up'][j], weekly_aroon_25['aroon_down'][j], period=25)
                        if j < len(weekly_aroon_25['aroon_up']) else 'Sideways'
                        for j in range(len(weekly_close))
                    ]
                    weekly_medium_trend = [
                        TrendClassification(weekly_aroon_50['aroon_up'][j], weekly_aroon_50['aroon_down'][j], period=50)
                        if j < len(weekly_aroon_50['aroon_up']) else 'Sideways'
                        for j in range(len(weekly_close))
                    ]
                    weekly_long_trend = [
                        TrendClassification(weekly_aroon_100['aroon_up'][j], weekly_aroon_100['aroon_down'][j], period=100)
                        if j < len(weekly_aroon_100['aroon_up']) else 'Sideways'
                        for j in range(len(weekly_close))
                    ]
                    
                    # Map weekly values to daily dataframe using date alignment
                    # CRITICAL: Use strict < to avoid lookahead bias
                    # Only use COMPLETED weekly candles (from BEFORE current date)
                    result_dates = pd.to_datetime(result_df.index).normalize()
                    weekly_dates = weekly_df.index.normalize()
                    
                    for i, daily_date in enumerate(result_dates):
                        # Find the most recent COMPLETED weekly bar BEFORE this daily date
                        # Use strict < to avoid lookahead bias (don't use current week's data)
                        matching_weeks = weekly_dates[weekly_dates < daily_date]
                        if len(matching_weeks) > 0:
                            week_idx = len(matching_weeks) - 1
                            if week_idx < len(weekly_rsi_14):
                                result_df['Weekly_RSI (14)'].iloc[i] = np.round(weekly_rsi_14[week_idx], 2)
                            if week_idx < len(weekly_macd['macd']):
                                result_df['Weekly_MACD_Bullish'].iloc[i] = weekly_macd['macd'][week_idx] > weekly_macd['signal'][week_idx]
                            if week_idx < len(weekly_adx['adx']):
                                result_df['Weekly_ADX (14)'].iloc[i] = np.round(weekly_adx['adx'][week_idx], 2)
                            if week_idx < len(weekly_ema5):
                                result_df['Weekly_Above_EMA5'].iloc[i] = weekly_close[week_idx] > weekly_ema5[week_idx]
                            if week_idx < len(weekly_ema20):
                                result_df['Weekly_Above_EMA20'].iloc[i] = weekly_close[week_idx] > weekly_ema20[week_idx]
                            if week_idx < len(weekly_ema50):
                                result_df['Weekly_Above_EMA50'].iloc[i] = weekly_close[week_idx] > weekly_ema50[week_idx]
                            if week_idx < len(weekly_ema200):
                                result_df['Weekly_Above_EMA200'].iloc[i] = weekly_close[week_idx] > weekly_ema200[week_idx]
                            if weekly_volume_sma20 is not None and week_idx < len(weekly_volume_sma20):
                                result_df['Weekly_Volume_Above_MA20'].iloc[i] = weekly_volume[week_idx] > weekly_volume_sma20[week_idx]
                            if week_idx < len(weekly_bb_position):
                                result_df['Weekly_BB_Position (20;2)'].iloc[i] = weekly_bb_position[week_idx]
                            if week_idx < len(weekly_ker_10):
                                result_df['Weekly_KER (10)'].iloc[i] = np.round(weekly_ker_10[week_idx], 3)
                            if week_idx < len(weekly_candle_colour):
                                result_df['Weekly_Candle_Colour'].iloc[i] = weekly_candle_colour[week_idx]
                            if week_idx < len(weekly_candlestick_pattern):
                                result_df['Weekly_Candlestick_Pattern'].iloc[i] = weekly_candlestick_pattern[week_idx]
                            if week_idx < len(weekly_chop_20_class):
                                result_df['Weekly_CHOP (20) Class'].iloc[i] = weekly_chop_20_class[week_idx]
                            if week_idx < len(weekly_short_trend):
                                result_df['Weekly_Short_Trend (Aroon 25)'].iloc[i] = weekly_short_trend[week_idx]
                            if week_idx < len(weekly_medium_trend):
                                result_df['Weekly_Medium_Trend (Aroon 50)'].iloc[i] = weekly_medium_trend[week_idx]
                            if week_idx < len(weekly_long_trend):
                                result_df['Weekly_Long_Trend (Aroon 100)'].iloc[i] = weekly_long_trend[week_idx]
                    
                    # Forward fill weekly indicators to cover days without weekly data
                    result_df['Weekly_RSI (14)'] = result_df['Weekly_RSI (14)'].ffill()
                    result_df['Weekly_MACD_Bullish'] = result_df['Weekly_MACD_Bullish'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_ADX (14)'] = result_df['Weekly_ADX (14)'].ffill()
                    result_df['Weekly_Above_EMA5'] = result_df['Weekly_Above_EMA5'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_Above_EMA20'] = result_df['Weekly_Above_EMA20'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_Above_EMA50'] = result_df['Weekly_Above_EMA50'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_Above_EMA200'] = result_df['Weekly_Above_EMA200'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_Volume_Above_MA20'] = result_df['Weekly_Volume_Above_MA20'].ffill().fillna(False).astype(bool)
                    result_df['Weekly_BB_Position (20;2)'] = result_df['Weekly_BB_Position (20;2)'].ffill().fillna('')
                    result_df['Weekly_KER (10)'] = result_df['Weekly_KER (10)'].ffill()
                    result_df['Weekly_Candle_Colour'] = result_df['Weekly_Candle_Colour'].ffill().fillna('')
                    result_df['Weekly_Candlestick_Pattern'] = result_df['Weekly_Candlestick_Pattern'].ffill().fillna('')
                    result_df['Weekly_CHOP (20) Class'] = result_df['Weekly_CHOP (20) Class'].ffill().fillna('')
                    result_df['Weekly_Short_Trend (Aroon 25)'] = result_df['Weekly_Short_Trend (Aroon 25)'].ffill().fillna('')
                    result_df['Weekly_Medium_Trend (Aroon 50)'] = result_df['Weekly_Medium_Trend (Aroon 50)'].ffill().fillna('')
                    result_df['Weekly_Long_Trend (Aroon 100)'] = result_df['Weekly_Long_Trend (Aroon 100)'].ffill().fillna('')
        except Exception:
            # Weekly data unavailable - defaults already set above
            pass
    
    # Map weekly VIX to daily dates
    if weekly_vix_df is not None and not weekly_vix_df.empty:
        result_dates = pd.to_datetime(result_df.index).normalize()
        vix_dates = pd.to_datetime(weekly_vix_df.index).normalize()
        for i, daily_date in enumerate(result_dates):
            matching_weeks = vix_dates[vix_dates <= daily_date]
            if len(matching_weeks) > 0:
                week_date = matching_weeks[-1]
                result_df['Weekly_India_VIX'].iloc[i] = np.round(weekly_vix_df.loc[week_date], 2)
        result_df['Weekly_India_VIX'] = result_df['Weekly_India_VIX'].ffill()
    
    # Weekly NIFTY50 indicators (using Groww weekly data - no resampling)
    result_df['Weekly_NIFTY50_Above_EMA5'] = True  # Default to True (allow trades if data missing)
    result_df['Weekly_NIFTY50_Above_EMA20'] = True
    result_df['Weekly_NIFTY50_Above_EMA50'] = True
    result_df['Weekly_NIFTY50_Above_EMA200'] = True
    
    try:
        from pathlib import Path as PathLib
        import glob
        project_root = PathLib(__file__).parent.parent
        
        # Load NIFTY50 weekly from Groww (no resampling)
        nifty50_weekly_path = project_root / 'data' / 'cache' / 'groww' / 'weekly' / 'groww_0_NIFTY_50_1w.csv'
        if nifty50_weekly_path.exists():
            nifty50_weekly_df = pd.read_csv(nifty50_weekly_path)
            # Parse time - handle both string datetime and Unix timestamp
            if nifty50_weekly_df['time'].dtype == 'int64':
                nifty50_weekly_df['time'] = pd.to_datetime(nifty50_weekly_df['time'], unit='s')
            else:
                nifty50_weekly_df['time'] = pd.to_datetime(nifty50_weekly_df['time'])
            nifty50_weekly_df = nifty50_weekly_df.set_index('time').sort_index()
            
            if not nifty50_weekly_df.empty:
                nifty50_close = nifty50_weekly_df['close'].values
                
                # Calculate EMAs on weekly NIFTY50
                nifty50_ema5 = EMA(nifty50_close, 5)
                nifty50_ema20 = EMA(nifty50_close, 20)
                nifty50_ema50 = EMA(nifty50_close, 50)
                nifty50_ema200 = EMA(nifty50_close, 200)
                
                # Create series aligned with weekly dates
                weekly_dates = nifty50_weekly_df.index.normalize()
                nifty50_above_5 = pd.Series(nifty50_close > nifty50_ema5, index=weekly_dates)
                nifty50_above_20 = pd.Series(nifty50_close > nifty50_ema20, index=weekly_dates)
                nifty50_above_50 = pd.Series(nifty50_close > nifty50_ema50, index=weekly_dates)
                nifty50_above_200 = pd.Series(nifty50_close > nifty50_ema200, index=weekly_dates)
                nifty50_close_series = pd.Series(nifty50_close, index=weekly_dates)
                
                # Map weekly values to daily dataframe
                result_dates = pd.to_datetime(result_df.index).normalize()
                for i, daily_date in enumerate(result_dates):
                    matching_weeks = weekly_dates[weekly_dates <= daily_date]
                    if len(matching_weeks) > 0:
                        week_idx = len(matching_weeks) - 1
                        if week_idx < len(nifty50_above_5):
                            result_df['Weekly_NIFTY50_Above_EMA5'].iloc[i] = nifty50_above_5.iloc[week_idx]
                        if week_idx < len(nifty50_above_20):
                            result_df['Weekly_NIFTY50_Above_EMA20'].iloc[i] = nifty50_above_20.iloc[week_idx]
                        if week_idx < len(nifty50_above_50):
                            result_df['Weekly_NIFTY50_Above_EMA50'].iloc[i] = nifty50_above_50.iloc[week_idx]
                        if week_idx < len(nifty50_above_200):
                            result_df['Weekly_NIFTY50_Above_EMA200'].iloc[i] = nifty50_above_200.iloc[week_idx]
                
                # Forward fill
                result_df['Weekly_NIFTY50_Above_EMA5'] = result_df['Weekly_NIFTY50_Above_EMA5'].ffill().fillna(True).astype(bool)
                result_df['Weekly_NIFTY50_Above_EMA20'] = result_df['Weekly_NIFTY50_Above_EMA20'].ffill().fillna(True).astype(bool)
                result_df['Weekly_NIFTY50_Above_EMA50'] = result_df['Weekly_NIFTY50_Above_EMA50'].ffill().fillna(True).astype(bool)
                result_df['Weekly_NIFTY50_Above_EMA200'] = result_df['Weekly_NIFTY50_Above_EMA200'].ffill().fillna(True).astype(bool)
    except Exception:
        # Keep defaults (True for above_ema columns)
        pass
    
    return result_df


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
    stoch_14_3_values = Stochastic(high_arr, low_arr, close_arr, 14, 1, 3)
    stoch_28_3_values = Stochastic(high_arr, low_arr, close_arr, 28, 1, 3)
    stoch_slow_5_3_3_values = calculate_stochastic_slow(high_arr, low_arr, close_arr, 5, 3, 3)
    stoch_slow_10_3_3_values = calculate_stochastic_slow(high_arr, low_arr, close_arr, 10, 3, 3)
    stoch_rsi_14_5_3_3_values = StochasticRSI(close_arr, 14, 5, 3, 3)
    stoch_rsi_14_10_5_5_values = StochasticRSI(close_arr, 14, 10, 5, 5)
    stoch_rsi_14_14_3_3_values = StochasticRSI(close_arr, 14, 14, 3, 3)
    stoch_rsi_28_20_10_10_values = StochasticRSI(close_arr, 28, 20, 10, 10)
    stoch_rsi_28_28_3_3_values = StochasticRSI(close_arr, 28, 28, 3, 3)
    stoch_rsi_28_5_3_3_values = StochasticRSI(close_arr, 28, 5, 3, 3)
    adx_14_values = ADX(high_arr, low_arr, close_arr, 14)
    adx_28_values = ADX(high_arr, low_arr, close_arr, 28)
    aroon_50_values = Aroon(high_arr, low_arr, 50)
    aroon_100_values = Aroon(high_arr, low_arr, 100)
    macd_12_26_9_values = MACD(close_arr, 12, 26, 9)
    macd_24_52_18_values = MACD(close_arr, 24, 52, 18)
    rsi_14_series = RSI(df["close"], 14)
    rsi_28_series = RSI(df["close"], 28)
    ema_5_series = pd.Series(EMA(close_arr, 5), index=df.index)
    ema_20_series = pd.Series(EMA(close_arr, 20), index=df.index)
    ema_50_series = pd.Series(EMA(close_arr, 50), index=df.index)
    ema_100_series = pd.Series(EMA(close_arr, 100), index=df.index)
    ema_200_series = pd.Series(EMA(close_arr, 200), index=df.index)
    sma_5_series = SMA(df["close"], 5)
    sma_20_series = SMA(df["close"], 20)
    sma_50_series = SMA(df["close"], 50)
    sma_200_series = SMA(df["close"], 200)
    cci_20_series = pd.Series(CCI(high_arr, low_arr, close_arr, 20), index=df.index)
    cci_40_series = pd.Series(CCI(high_arr, low_arr, close_arr, 40), index=df.index)
    adx_14_series = pd.Series(adx_14_values["adx"], index=df.index)
    adx_28_series = pd.Series(adx_28_values["adx"], index=df.index)
    bbp_13_values = BullBearPower(high_arr, low_arr, close_arr, 13)
    bbp_26_values = BullBearPower(high_arr, low_arr, close_arr, 26)
    mfi_20_series = pd.Series(VWMA(close_arr, df.get("volume", pd.Series([1]*len(close_arr))).astype(float).values, 20) if "volume" in df.columns else [50]*len(close_arr), index=df.index)
    mfi_40_series = pd.Series(VWMA(close_arr, df.get("volume", pd.Series([1]*len(close_arr))).astype(float).values, 40) if "volume" in df.columns else [50]*len(close_arr), index=df.index)
    bb_40_values = BollingerBands(close_arr, 40, 2)

    # For each unique entry time, lookup indicators from pre-calculated series
    # IMPORTANT: Use t-1 bar (decision time) not entry bar
    for entry_time in unique_entries:
        entry_time = pd.Timestamp(entry_time)
        entry_data_mask = df_idx <= entry_time

        if not entry_data_mask.any():
            continue

        bar_idx = entry_data_mask.nonzero()[0][-1]  # Entry bar index
        last_idx = max(0, bar_idx - 1)  # t-1 bar (decision time)

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
        rsi_14_val = rsi_14_series.iloc[last_idx] if last_idx < len(rsi_14_series) else 50
        rsi_28_val = rsi_28_series.iloc[last_idx] if last_idx < len(rsi_28_series) else 50

        macd_12_26_9_line = (
            macd_12_26_9_values["macd"][last_idx] if last_idx < len(macd_12_26_9_values["macd"]) else 0
        )
        macd_12_26_9_signal = (
            macd_12_26_9_values["signal"][last_idx]
            if last_idx < len(macd_12_26_9_values["signal"])
            else 0
        )
        macd_24_52_18_line = (
            macd_24_52_18_values["macd"][last_idx] if last_idx < len(macd_24_52_18_values["macd"]) else 0
        )
        macd_24_52_18_signal = (
            macd_24_52_18_values["signal"][last_idx]
            if last_idx < len(macd_24_52_18_values["signal"])
            else 0
        )

        ema_5_val = ema_5_series.iloc[last_idx] if last_idx < len(ema_5_series) else 0
        ema_20_val = (
            ema_20_series.iloc[last_idx] if last_idx < len(ema_20_series) else 0
        )
        ema_50_val = (
            ema_50_series.iloc[last_idx] if last_idx < len(ema_50_series) else 0
        )
        ema_100_val = (
            ema_100_series.iloc[last_idx] if last_idx < len(ema_100_series) else 0
        )
        ema_200_val = (
            ema_200_series.iloc[last_idx] if last_idx < len(ema_200_series) else 0
        )

        adx_14_val = adx_14_series.iloc[last_idx] if last_idx < len(adx_14_series) else 0
        adx_28_val = adx_28_series.iloc[last_idx] if last_idx < len(adx_28_series) else 0
        di_plus_14_val = (
            adx_14_values["di_plus"][last_idx]
            if last_idx < len(adx_14_values["di_plus"])
            else 0
        )
        di_minus_14_val = (
            adx_14_values["di_minus"][last_idx]
            if last_idx < len(adx_14_values["di_minus"])
            else 0
        )
        di_plus_28_val = (
            adx_28_values["di_plus"][last_idx]
            if last_idx < len(adx_28_values["di_plus"])
            else 0
        )
        di_minus_28_val = (
            adx_28_values["di_minus"][last_idx]
            if last_idx < len(adx_28_values["di_minus"])
            else 0
        )
        bbp_13_val = bbp_13_values["bbp"][last_idx] if last_idx < len(bbp_13_values["bbp"]) else 0
        bbp_26_val = bbp_26_values["bbp"][last_idx] if last_idx < len(bbp_26_values["bbp"]) else 0

        # Calculate Bollinger Band positions
        upper_band_20 = (
            bb_values["upper"][last_idx]
            if last_idx < len(bb_values["upper"])
            else close_val
        )
        lower_band_20 = (
            bb_values["lower"][last_idx]
            if last_idx < len(bb_values["lower"])
            else close_val
        )
        if close_val > upper_band_20:
            bb_pos_20 = "Above"
        elif close_val < lower_band_20:
            bb_pos_20 = "Below"
        else:
            bb_pos_20 = "Middle"

        upper_band_40 = (
            bb_40_values["upper"][last_idx]
            if last_idx < len(bb_40_values["upper"])
            else close_val
        )
        lower_band_40 = (
            bb_40_values["lower"][last_idx]
            if last_idx < len(bb_40_values["lower"])
            else close_val
        )
        if close_val > upper_band_40:
            bb_pos_40 = "Above"
        elif close_val < lower_band_40:
            bb_pos_40 = "Below"
        else:
            bb_pos_40 = "Middle"

        # Stochastic (14,3)
        k_14_3_val = (
            stoch_14_3_values["k"][last_idx]
            if last_idx < len(stoch_14_3_values["k"])
            and not np.isnan(stoch_14_3_values["k"][last_idx])
            else 0
        )
        d_14_3_val = (
            stoch_14_3_values["d"][last_idx]
            if last_idx < len(stoch_14_3_values["d"])
            and not np.isnan(stoch_14_3_values["d"][last_idx])
            else 0
        )

        # Stochastic (28,3)
        k_28_3_val = (
            stoch_28_3_values["k"][last_idx]
            if last_idx < len(stoch_28_3_values["k"])
            and not np.isnan(stoch_28_3_values["k"][last_idx])
            else 0
        )
        d_28_3_val = (
            stoch_28_3_values["d"][last_idx]
            if last_idx < len(stoch_28_3_values["d"])
            and not np.isnan(stoch_28_3_values["d"][last_idx])
            else 0
        )

        # Stochastic Slow (5,3,3)
        slow_k_5_3_3_val = (
            stoch_slow_5_3_3_values["slow_k"][last_idx]
            if last_idx < len(stoch_slow_5_3_3_values["slow_k"])
            and not np.isnan(stoch_slow_5_3_3_values["slow_k"][last_idx])
            else 0
        )
        slow_d_5_3_3_val = (
            stoch_slow_5_3_3_values["slow_d"][last_idx]
            if last_idx < len(stoch_slow_5_3_3_values["slow_d"])
            and not np.isnan(stoch_slow_5_3_3_values["slow_d"][last_idx])
            else 0
        )

        # Stochastic Slow (10,3,3)
        slow_k_10_3_3_val = (
            stoch_slow_10_3_3_values["slow_k"][last_idx]
            if last_idx < len(stoch_slow_10_3_3_values["slow_k"])
            and not np.isnan(stoch_slow_10_3_3_values["slow_k"][last_idx])
            else 0
        )
        slow_d_10_3_3_val = (
            stoch_slow_10_3_3_values["slow_d"][last_idx]
            if last_idx < len(stoch_slow_10_3_3_values["slow_d"])
            and not np.isnan(stoch_slow_10_3_3_values["slow_d"][last_idx])
            else 0
        )

        # StochRSI (14;5;3;3)
        stoch_rsi_k_14_5_3_3_val = (
            stoch_rsi_14_5_3_3_values["k"][last_idx]
            if last_idx < len(stoch_rsi_14_5_3_3_values["k"])
            and not np.isnan(stoch_rsi_14_5_3_3_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_14_5_3_3_val = (
            stoch_rsi_14_5_3_3_values["d"][last_idx]
            if last_idx < len(stoch_rsi_14_5_3_3_values["d"])
            and not np.isnan(stoch_rsi_14_5_3_3_values["d"][last_idx])
            else 50
        )

        # StochRSI (14;10;5;5)
        stoch_rsi_k_14_10_5_5_val = (
            stoch_rsi_14_10_5_5_values["k"][last_idx]
            if last_idx < len(stoch_rsi_14_10_5_5_values["k"])
            and not np.isnan(stoch_rsi_14_10_5_5_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_14_10_5_5_val = (
            stoch_rsi_14_10_5_5_values["d"][last_idx]
            if last_idx < len(stoch_rsi_14_10_5_5_values["d"])
            and not np.isnan(stoch_rsi_14_10_5_5_values["d"][last_idx])
            else 50
        )

        # StochRSI (14;14;3;3)
        stoch_rsi_k_14_14_3_3_val = (
            stoch_rsi_14_14_3_3_values["k"][last_idx]
            if last_idx < len(stoch_rsi_14_14_3_3_values["k"])
            and not np.isnan(stoch_rsi_14_14_3_3_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_14_14_3_3_val = (
            stoch_rsi_14_14_3_3_values["d"][last_idx]
            if last_idx < len(stoch_rsi_14_14_3_3_values["d"])
            and not np.isnan(stoch_rsi_14_14_3_3_values["d"][last_idx])
            else 50
        )

        # StochRSI (28;20;10;10)
        stoch_rsi_k_28_20_10_10_val = (
            stoch_rsi_28_20_10_10_values["k"][last_idx]
            if last_idx < len(stoch_rsi_28_20_10_10_values["k"])
            and not np.isnan(stoch_rsi_28_20_10_10_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_28_20_10_10_val = (
            stoch_rsi_28_20_10_10_values["d"][last_idx]
            if last_idx < len(stoch_rsi_28_20_10_10_values["d"])
            and not np.isnan(stoch_rsi_28_20_10_10_values["d"][last_idx])
            else 50
        )

        # StochRSI (28;28;3;3)
        stoch_rsi_k_28_28_3_3_val = (
            stoch_rsi_28_28_3_3_values["k"][last_idx]
            if last_idx < len(stoch_rsi_28_28_3_3_values["k"])
            and not np.isnan(stoch_rsi_28_28_3_3_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_28_28_3_3_val = (
            stoch_rsi_28_28_3_3_values["d"][last_idx]
            if last_idx < len(stoch_rsi_28_28_3_3_values["d"])
            and not np.isnan(stoch_rsi_28_28_3_3_values["d"][last_idx])
            else 50
        )

        # StochRSI (28;5;3;3)
        stoch_rsi_k_28_5_3_3_val = (
            stoch_rsi_28_5_3_3_values["k"][last_idx]
            if last_idx < len(stoch_rsi_28_5_3_3_values["k"])
            and not np.isnan(stoch_rsi_28_5_3_3_values["k"][last_idx])
            else 50
        )
        stoch_rsi_d_28_5_3_3_val = (
            stoch_rsi_28_5_3_3_values["d"][last_idx]
            if last_idx < len(stoch_rsi_28_5_3_3_values["d"])
            and not np.isnan(stoch_rsi_28_5_3_3_values["d"][last_idx])
            else 50
        )

        # CCI
        cci_20_val = cci_20_series.iloc[last_idx] if last_idx < len(cci_20_series) else 0
        cci_40_val = cci_40_series.iloc[last_idx] if last_idx < len(cci_40_series) else 0

        # Cache the indicators dict for this entry time with ALL consolidated file indicators
        entry_indicators_cache[entry_time] = {
            "atr_14": atr_val,
            "atr_pct": atr_pct_val,
            # ADX and DI (14 and 28)
            "adx_14": adx_14_val,
            "adx_28": adx_28_val,
            "di_plus_14": di_plus_14_val,
            "di_minus_14": di_minus_14_val,
            "di_plus_28": di_plus_28_val,
            "di_minus_28": di_minus_28_val,
            "di_bullish_14": di_plus_14_val > di_minus_14_val,
            "di_bullish_28": di_plus_28_val > di_minus_28_val,
            # RSI (14 and 28)
            "rsi_14": rsi_14_val,
            "rsi_28": rsi_28_val,
            # MACD (12,26,9 and 24,52,18)
            "macd_bullish_12_26_9": macd_12_26_9_line > macd_12_26_9_signal,
            "macd_bullish_24_52_18": macd_24_52_18_line > macd_24_52_18_signal,
            # EMAs
            "ema_5": ema_5_val,
            "ema_20": ema_20_val,
            "ema_50": ema_50_val,
            "ema_200": ema_200_val,
            # SMA
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
            # CCI (20 and 40)
            "cci_20": cci_20_val,
            "cci_40": cci_40_val,
            # Stochastic (14,3) - PRIMARY for entry filter
            "stoch_bullish_14_3": k_14_3_val > d_14_3_val,
            "percent_k_14_3": k_14_3_val,
            "percent_d_14_3": d_14_3_val,
            # Stochastic (28,3)
            "stoch_bullish_28_3": k_28_3_val > d_28_3_val,
            "percent_k_28_3": k_28_3_val,
            "percent_d_28_3": d_28_3_val,
            # Stochastic Slow (5,3,3)
            "stoch_slow_bullish_5_3_3": slow_k_5_3_3_val > slow_d_5_3_3_val,
            # Stochastic Slow (10,3,3)
            "stoch_slow_bullish_10_3_3": slow_k_10_3_3_val > slow_d_10_3_3_val,
            # StochRSI K values (14;5;3;3)
            "stoch_rsi_k_14_5_3_3": round(stoch_rsi_k_14_5_3_3_val, 2),
            # StochRSI K values (14;10;5;5)
            "stoch_rsi_k_14_10_5_5": round(stoch_rsi_k_14_10_5_5_val, 2),
            # StochRSI K values (14;14;3;3)
            "stoch_rsi_k_14_14_3_3": round(stoch_rsi_k_14_14_3_3_val, 2),
            # StochRSI K values (28;20;10;10)
            "stoch_rsi_k_28_20_10_10": round(stoch_rsi_k_28_20_10_10_val, 2),
            # StochRSI K values (28;28;3;3)
            "stoch_rsi_k_28_28_3_3": round(stoch_rsi_k_28_28_3_3_val, 2),
            # StochRSI K values (28;5;3;3)
            "stoch_rsi_k_28_5_3_3": round(stoch_rsi_k_28_5_3_3_val, 2),
            # Bull/Bear Power

            # Bollinger Bands position
            "bb_position_20_2": bb_pos_20,
            "bb_position_40_2": bb_pos_40,
            # Price vs EMA
            "price_above_ema5": close_val > ema_5_val,
            "price_above_ema20": close_val > ema_20_val,
            "price_above_ema50": close_val > ema_50_val,
            "price_above_ema100": close_val > ema_100_val if last_idx < len(ema_100_series) else False,
            "price_above_ema200": close_val > ema_200_val,
            # EMA vs EMA
            "ema5_above_ema20": ema_5_val > ema_20_val,
            "ema20_above_ema50": ema_20_val > ema_50_val,
            "ema50_above_ema100": ema_50_val > ema_100_val if last_idx < len(ema_100_series) else False,
            "ema50_above_ema200": ema_50_val > ema_200_val,
            "holding_days": 0,  # Will be calculated per-trade in the loop
        }

    return entry_indicators_cache


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
                        pnl_values = pd.Series(dtype=float)  # Empty series

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
                    pnl_values = pd.Series(dtype=float)  # Empty series
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
                pnl_values = pd.Series(dtype=float)  # Empty series

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

            # Kelly Criterion with Method A: Adjusted for multi-asset trading
            # Full Kelly: kelly_full = p - (q / b), where p=win%, q=1-p, b=avg_win/avg_loss
            # Method A adjustment: kelly_adjusted = kelly_full / sqrt(N), where N = avg concurrent positions
            
            # Get position size from config for accurate N calculation
            position_size_pct = BrokerConfig().qty_pct_of_equity * 100  # Convert to percentage (e.g., 0.05 -> 5%)
            
            if num_trades > 0:
                p = win_rate / 100.0
                q = 1.0 - p
                win_avg = (
                    pnl_values[pnl_values > 0].mean() if (pnl_values > 0).any() else 0.0
                )
                loss_avg = (
                    abs(pnl_values[pnl_values < 0].mean())
                    if (pnl_values < 0).any()
                    else 1.0
                )
                if loss_avg > 0 and win_avg > 0:
                    b = win_avg / loss_avg  # Payoff ratio
                    kelly_full = p - (q / b)  # Full Kelly fraction
                    kelly_full = max(0.0, kelly_full)  # Floor at 0
                    
                    # Compute average concurrent positions (N) from avg exposure %
                    # avg_exposure_pct represents total deployed capital as % of equity
                    # N = avg_exposure_pct / qty_pct_of_equity (position size from config)
                    if avg_exposure_pct > 0 and position_size_pct > 0:
                        # Estimate N from exposure: N = total exposure / position size
                        avg_concurrent_positions = max(1.0, avg_exposure_pct / position_size_pct)
                    else:
                        avg_concurrent_positions = 1.0
                    
                    # Apply Method A adjustment for multi-asset correlation
                    kelly_pct = kelly_full / np.sqrt(avg_concurrent_positions)
                    kelly_pct = max(0.0, min(kelly_pct, 1.0))  # Clamp to 0-1
                else:
                    kelly_full = 0.0
                    avg_concurrent_positions = 1.0
                    kelly_pct = 0.0
            else:
                kelly_full = 0.0
                avg_concurrent_positions = 1.0
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
                "Full Kelly": round(kelly_full * 100, 2),  # As percentage
                "Avg Concurrent Positions": round(avg_concurrent_positions, 2),
                "Kelly Criterion": round(kelly_pct * 100, 2),  # As percentage
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


def _calculate_trade_indicators(
    df: pd.DataFrame, entry_time, exit_time, entry_price: float
) -> dict:
    """Calculate technical indicators for a trade at entry and exit times.
    
    IMPORTANT: Uses t-1 bar data (the bar BEFORE entry) for indicator values.
    This represents the decision point - indicators that were known when deciding to enter.
    """
    try:
        # Get data UP TO BUT NOT INCLUDING entry time for entry indicators (t-1 bar)
        # This matches the strategy's decision point - we evaluate at close[i-1] before entering at bar i
        df_idx = pd.to_datetime(df.index, errors="coerce")
        entry_time = pd.Timestamp(entry_time)
        exit_time = pd.Timestamp(exit_time)

        entry_data = df.loc[df_idx < entry_time].copy()  # Changed from <= to < for t-1 bar
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

        # Calculate Stochastic RSI (14-period) from pre-computed RSI
        from utils.indicators import StochasticRSI_from_RSI

        # rsi is already a numpy array from RSI calculation
        stoch_rsi = StochasticRSI_from_RSI(rsi, stoch_length=14, k_smooth=3, d_smooth=3)

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

            # Stochastic RSI
            "stoch_rsi_k": (
                stoch_rsi["k"][-1] if len(stoch_rsi["k"]) > 0 else 50
            ),
            "stoch_rsi_d": (
                stoch_rsi["d"][-1] if len(stoch_rsi["d"]) > 0 else 50
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
    compounding=False,
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
        compounding: Use compounding position sizing (% of current equity vs initial capital)
    """
    from config import DEFAULT_BASKET_SIZE, get_basket_file

    # Initialize performance timer
    timer = Timer()

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
    # map each basket symbol -> SECID via data/dhan-scrip-master-detailed.csv and load the CSVs.
    data_map_full: dict[str, pd.DataFrame] = {}
    
    with timer.measure("Data Loading"):
        try:
            inst_csv = os.path.join("data", "dhan-scrip-master-detailed.csv")
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
    cfg = BrokerConfig(compounding=compounding)

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

    # Start timing for strategy processing
    strategy_start = time.time()
    
    if num_processes > 1 and len(symbols_to_process) > 1:
        # ⚡ Parallel processing with module-level function for pickling compatibility
        print(
            f"⚡ Using {num_processes} processes for {len(symbols_to_process)} symbols"
        )
        # Pass symbol metadata only, not data (to avoid pickling huge dataframes with spawn)
        task_args = [
            (sym, i, len(symbols_to_process), strategy_name, params_json, cache_dir, interval, period, compounding)
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
                results = pool.map(_process_symbol_for_backtest, task_args, chunksize=1)

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
    
    # Record strategy processing time
    strategy_elapsed = time.time() - strategy_start
    timer.timings["Strategy Initialization & Trade Generation"] = strategy_elapsed

    # OPTIMIZATION 2: Build all windows from cached results
    print("⚡ Processing time windows from cached results...")
    window_start_time = time.time()
    total_windows = len(windows_years)

    with timer.measure("Window Processing"):
        window_results = optimize_window_processing(
            symbol_results, list(windows_years), bars_per_year
        )
    window_labels: dict[int | None, str] = {1: "1Y", 3: "3Y", 5: "5Y", None: "MAX"}
    consolidated_csv_paths: dict[str, str] = {}
    portfolio_csv_paths: dict[str, str] = {}
    window_maxdd: dict[str, float] = {}
    
    # Track column order for trades files
    trades_column_order = None

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
        dfs_full_by_symbol = {}  # NEW: Store full unsliced data for indicator calculations

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

            # NEW: Store full unsliced data for consolidated indicator calculations
            # Indicators like Stochastic(14,3) need lookback bars before the window starts
            dfs_full_by_symbol[sym] = df_full

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
                curve_rows = []
                for dt in dates:
                    curve_rows.append({
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
                return pd.DataFrame(curve_rows).set_index("time").sort_index()
            
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
            curve_rows = []
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
                
                curve_rows.append({
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
            
            df_port = pd.DataFrame(curve_rows).set_index("time").sort_index()
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
                    exit_reason = tr.get("exit_reason", "")  # Get exit reason (stop, signal, etc.)

                    # IMPORTANT: Verify net_pnl includes both entry and exit commissions
                    # Commission is correctly calculated in the engine based on actual
                    # entry/exit prices (which may have decimal values like 1905.03, 1853.97)
                    # The CSV displays prices as integers for readability, but the commission
                    # calculation uses the full decimal precision from the engine.

                    # Get OHLC data for this trade period - use FULL unsliced data for indicator calculations
                    # This ensures indicators like Stochastic(14,3) have enough lookback bars
                    symbol_df_full = dfs_full_by_symbol.get(symbol)
                    if symbol_df_full is None or symbol_df_full.empty:
                        continue

                    # Calculate indicators for this specific trade using comprehensive indicator function
                    try:
                        # Get data up to entry time using FULL data, not window-sliced data
                        df_idx = pd.to_datetime(symbol_df_full.index, errors="coerce")
                        entry_ts = pd.Timestamp(entry_time)
                        
                        # IMPORTANT: Get data UP TO BUT NOT INCLUDING entry timestamp
                        # This matches the strategy's decision point - it evaluates at close[i] using data[0:i]
                        # Entry bar itself is not included in the calculation (that would be look-ahead bias)
                        entry_data = symbol_df_full.loc[df_idx < entry_ts].copy()  # Changed from <= to <
                        
                        if not entry_data.empty:
                            # Calculate all indicators AT ENTRY TIME (using data before entry)
                            df_with_indicators = _calculate_all_indicators_for_consolidated(entry_data, symbol)
                            # Get indicators at entry time (last row)
                            indicators_entry = df_with_indicators.iloc[-1].to_dict()
                            
                            # Calculate all indicators AT EXIT TIME (if trade is closed)
                            indicators_exit = {}
                            if pd.notna(exit_time):
                                try:
                                    exit_ts = pd.Timestamp(exit_time)
                                    # Same logic: data up to but not including exit bar
                                    exit_data = symbol_df_full.loc[df_idx < exit_ts].copy()  # Changed from <= to <
                                    if not exit_data.empty:
                                        df_with_indicators_exit = _calculate_all_indicators_for_consolidated(exit_data, symbol)
                                        indicators_exit = df_with_indicators_exit.iloc[-1].to_dict()
                                except Exception:
                                    pass
                            
                            # Use entry indicators for entry row
                            indicators = indicators_entry.copy()
                            
                            # Add holding days
                            # For open trades, use last date in cache data instead of today's date
                            holding_days = 0
                            # Check both exit_time and exit_price to determine if trade is open
                            is_open_for_holding = pd.isna(exit_time) or exit_price == 0 or exit_price is None
                            if entry_time:
                                if not is_open_for_holding:
                                    exit_dt = pd.to_datetime(exit_time)
                                else:
                                    # Open trade: use last date in symbol's cache data
                                    symbol_df_for_days = dfs_by_symbol.get(symbol)
                                    if symbol_df_for_days is not None and not symbol_df_for_days.empty:
                                        exit_dt = pd.to_datetime(symbol_df_for_days.index[-1])
                                    else:
                                        # Fallback: use any available symbol's last date
                                        for any_df in dfs_by_symbol.values():
                                            if any_df is not None and not any_df.empty:
                                                exit_dt = pd.to_datetime(any_df.index[-1])
                                                break
                                        else:
                                            exit_dt = pd.Timestamp.today()  # Last resort
                                entry_dt = pd.to_datetime(entry_time)
                                holding_days = (exit_dt - entry_dt).days
                            indicators["holding_days"] = holding_days
                            
                            # Add ATR metrics for compatibility
                            from utils import ATR
                            high = symbol_df["high"].astype(float)
                            low = symbol_df["low"].astype(float)
                            close = symbol_df["close"].astype(float)
                            atr_values = ATR(high.values, low.values, close.values, 14)
                            atr = atr_values[-1] if len(atr_values) > 0 else 0
                            atr_pct = (atr / close.iloc[-1]) * 100 if close.iloc[-1] > 0 else 0
                            indicators["atr"] = atr
                            indicators["atr_pct"] = atr_pct
                            indicators["mae_atr"] = 0  # Placeholder
                        else:
                            indicators = {}
                            indicators_exit = {}
                    except Exception as e:
                        logger.warning(f"Error calculating indicators for {symbol}: {e}")
                        indicators = {}

                    # Compute P&L related metrics
                    tv_pos_value = entry_price * qty if entry_price and qty else 0
                    tv_net_pct = (
                        (net_pnl / tv_pos_value * 100)
                        if tv_pos_value > 0 and pd.notna(net_pnl)
                        else 0
                    )

                    # === RESET TRADE METRICS FOR THIS TRADE ===
                    run_up_exit = 0.0
                    drawdown_exit = 0.0
                    
                    # Get symbol-specific data for run-up/drawdown calculation
                    symbol_df = dfs_by_symbol.get(symbol)
                    
                    # Determine if this is an open trade (no exit yet)
                    # Check both exit_time and exit_price to be safe
                    is_open_for_calc = pd.isna(exit_time) or exit_price == 0 or exit_price is None
                    
                    # For open trades, use current (last) price; for closed trades, use exit price
                    if is_open_for_calc and symbol_df is not None and not symbol_df.empty:
                        current_price = float(symbol_df["close"].iloc[-1])
                    else:
                        current_price = exit_price if exit_price > 0 else entry_price
                    
                    # Calculate run-up and drawdown from entry price to current/exit price
                    # For open trades, also look at historical highs/lows during trade period
                    try:
                        if symbol_df is not None and not symbol_df.empty and entry_price > 0:
                            try:
                                # Get price data for the trade period
                                df_idx = pd.to_datetime(symbol_df.index, errors="coerce")
                                entry_ts = pd.Timestamp(entry_time)
                                
                                # For open trades, use last date in cache data
                                if not is_open_for_calc:
                                    exit_ts = pd.Timestamp(exit_time)
                                else:
                                    exit_ts = df_idx[-1] if len(df_idx) > 0 else pd.Timestamp.today()
                                
                                # Get close prices from entry through exit
                                mask = (df_idx >= entry_ts) & (df_idx <= exit_ts)
                                close_prices = symbol_df.loc[mask, "close"].astype(float)
                                
                                if not close_prices.empty:
                                    # Calculate P&L series from entry price
                                    pnl_series = (close_prices - entry_price) * qty
                                    
                                    # Run-up is max profit reached during trade
                                    run_up_exit = float(max(0.0, pnl_series.max()))
                                    
                                    # Drawdown is max loss experienced during trade
                                    # For losses, it's the minimum value (most negative)
                                    min_pnl = pnl_series.min()
                                    drawdown_exit = float(min(0.0, min_pnl))  # Keep it negative or zero
                            except Exception as e:
                                logger.debug(f"Error calculating run-up/drawdown for {symbol}: {e}")
                                # Fallback: calculate from entry to current price
                                current_pnl = (current_price - entry_price) * qty
                                run_up_exit = float(max(0.0, current_pnl))
                                drawdown_exit = float(min(0.0, current_pnl))
                    except Exception as e:
                        logger.debug(f"Exception in run-up/drawdown calculation for {symbol}: {e}")
                        current_pnl = (current_price - entry_price) * qty
                        run_up_exit = float(max(0.0, current_pnl))
                        drawdown_exit = float(min(0.0, current_pnl))

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
                        net_pnl_exit = (
                            (current_exit_price - entry_price) * qty
                            if entry_price > 0
                            else 0
                        )
                        # Recalculate Net P&L % for open trades using MTM value
                        tv_net_pct = (
                            (net_pnl_exit / tv_pos_value * 100)
                            if tv_pos_value > 0
                            else 0
                        )
                    else:
                        # Realized P&L for closed trades
                        net_pnl_exit = net_pnl if pd.notna(net_pnl) else 0

                    # Net P&L handling - ensure it's an integer
                    net_pnl_int = (
                        int(net_pnl_exit)
                        if net_pnl_exit is not None and not pd.isna(net_pnl_exit)
                        else 0
                    )

                    # Extract holding days for both rows - RECALCULATE for consolidated trades
                    # Use last cache date for open trades instead of today
                    holding_days_val = 0
                    if entry_time and pd.notna(entry_time):
                        if is_open_for_calc:
                            # Open trade: use last date in symbol's cache data
                            symbol_df_for_days = dfs_by_symbol.get(symbol)
                            if symbol_df_for_days is not None and not symbol_df_for_days.empty:
                                exit_dt_for_days = pd.to_datetime(symbol_df_for_days.index[-1])
                            else:
                                # Fallback: use any available symbol's last date
                                exit_dt_for_days = None
                                for any_df in dfs_by_symbol.values():
                                    if any_df is not None and not any_df.empty:
                                        exit_dt_for_days = pd.to_datetime(any_df.index[-1])
                                        break
                                if exit_dt_for_days is None:
                                    exit_dt_for_days = pd.Timestamp.today()
                        else:
                            # Closed trade: use actual exit time
                            exit_dt_for_days = pd.to_datetime(exit_time) if pd.notna(exit_time) else pd.Timestamp.today()
                        
                        entry_dt_for_days = pd.to_datetime(entry_time)
                        holding_days_val = int((exit_dt_for_days - entry_dt_for_days).days)

                    # Extract ATR for both rows
                    atr_val = (
                        int(round(indicators.get("atr", 0)))
                        if indicators and pd.notna(indicators.get("atr", 0))
                        else ""
                    )
                    atr_pct_val = (
                        round(indicators.get("atr_pct", 0), 2)
                        if indicators and pd.notna(indicators.get("atr_pct", 0))
                        else ""
                    )

                    # Calculate MAE_ATR and MFE_ATR (only if ATR is available)
                    mae_atr_val = (
                        round(mae_pct / atr_pct_val, 2)
                        if atr_pct_val and isinstance(atr_pct_val, (int, float)) and atr_pct_val > 0
                        else ""
                    )
                    mfe_atr_val = (
                        round(tv_run_pct / atr_pct_val, 2)
                        if atr_pct_val and isinstance(atr_pct_val, (int, float)) and atr_pct_val > 0
                        else ""
                    )

                    # Exit row - First row for each trade
                    # Determine exit signal: STOP if stopped out, CLOSE otherwise, OPEN if still in trade
                    if pd.isna(exit_time):
                        exit_signal = "OPEN"
                    elif exit_reason == "stop":
                        exit_signal = "STOP"
                    else:
                        exit_signal = "CLOSE"
                    
                    tv_rows.append(
                        {
                            "Trade #": trade_no,
                            "Symbol": symbol,
                            "Type": "Exit long",
                            "Date/Time": exit_str,
                            "Signal": exit_signal,
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
                            "Profitable": "Yes" if round(tv_net_pct, 2) > 0 else "No",

                            "Run-up INR": (int(run_up_exit) if run_up_exit > 0 else 0),
                            "Run-up %": round(tv_run_pct, 2),
                            "Drawdown INR": (
                                int(drawdown_exit)
                                if drawdown_exit is not None
                                else None
                            ),
                            "Drawdown %": round(tv_dd_pct, 2),
                            "Holding days": holding_days_val,
                            "ATR": atr_val,
                            "ATR %": atr_pct_val,
                            "MAE %": round(mae_pct, 2),
                            "MAE_ATR": mae_atr_val,
                            "MFE %": round(tv_run_pct, 2),
                            "MFE_ATR": mfe_atr_val,
                            # === REGIME FILTERS (9 indicators) ===
                            "India VIX": indicators_exit.get("india_vix", indicators.get("india_vix", "")) if indicators_exit or indicators else "",
                            "NIFTY200 > EMA 5": str(indicators_exit.get("nifty200_above_ema5", indicators.get("nifty200_above_ema5", ""))) if indicators_exit or indicators else "",
                            "NIFTY200 > EMA 20": str(indicators_exit.get("nifty200_above_ema20", indicators.get("nifty200_above_ema20", ""))) if indicators_exit or indicators else "",
                            "NIFTY200 > EMA 50": str(indicators_exit.get("nifty200_above_ema50", indicators.get("nifty200_above_ema50", ""))) if indicators_exit or indicators else "",
                            "NIFTY200 > EMA 100": str(indicators_exit.get("nifty200_above_ema100", indicators.get("nifty200_above_ema100", ""))) if indicators_exit or indicators else "",
                            "NIFTY200 > EMA 200": str(indicators_exit.get("nifty200_above_ema200", indicators.get("nifty200_above_ema200", ""))) if indicators_exit or indicators else "",
                            "Short-Trend (Aroon 25)": indicators_exit.get("short_trend_aroon25", indicators.get("short_trend_aroon25", "")) if indicators_exit or indicators else "",
                            "Medium-Trend (Aroon 50)": indicators_exit.get("medium_trend_aroon50", indicators.get("medium_trend_aroon50", "")) if indicators_exit or indicators else "",
                            "Long-Trend (Aroon 100)": indicators_exit.get("long_trend_aroon100", indicators.get("long_trend_aroon100", "")) if indicators_exit or indicators else "",
                            "Volatility (14)": indicators_exit.get("volatility_14", indicators.get("volatility_14", "")) if indicators_exit or indicators else "",
                            "Volatility (28)": indicators_exit.get("volatility_28", indicators.get("volatility_28", "")) if indicators_exit or indicators else "",
                            # === TREND STRENGTH (6 indicators) ===
                            "ADX (14)": round(indicators_exit.get("adx_14", indicators.get("adx_14", 0)), 2) if indicators_exit or indicators else "",
                            "ADX (28)": round(indicators_exit.get("adx_28", indicators.get("adx_28", 0)), 2) if indicators_exit or indicators else "",
                            "DI_Bullish (14)": str(indicators_exit.get("di_bullish_14", indicators.get("di_bullish_14", ""))) if indicators_exit or indicators else "",
                            "DI_Bullish (28)": str(indicators_exit.get("di_bullish_28", indicators.get("di_bullish_28", ""))) if indicators_exit or indicators else "",
                                                                                    # === MOMENTUM (14 indicators) ===
                            "RSI (14)": round(indicators_exit.get("rsi_14", indicators.get("rsi_14", 50)), 2) if indicators_exit or indicators else "",
                            "RSI (28)": round(indicators_exit.get("rsi_28", indicators.get("rsi_28", 50)), 2) if indicators_exit or indicators else "",
                            "MACD_Bullish (12;26;9)": str(indicators_exit.get("macd_bullish_12_26_9", indicators.get("macd_bullish_12_26_9", ""))) if indicators_exit or indicators else "",
                            "MACD_Bullish (24;52;18)": str(indicators_exit.get("macd_bullish_24_52_18", indicators.get("macd_bullish_24_52_18", ""))) if indicators_exit or indicators else "",
                            # === TREND STRUCTURE (13 indicators) ===
                            "Price_Above_EMA5": str(indicators_exit.get("price_above_ema5", indicators.get("price_above_ema5", ""))) if indicators_exit or indicators else "",
                            "Price_Above_EMA20": str(indicators_exit.get("price_above_ema20", indicators.get("price_above_ema20", ""))) if indicators_exit or indicators else "",
                            "Price_Above_EMA50": str(indicators_exit.get("price_above_ema50", indicators.get("price_above_ema50", ""))) if indicators_exit or indicators else "",
                            "Price_Above_EMA100": str(indicators_exit.get("price_above_ema100", indicators.get("price_above_ema100", ""))) if indicators_exit or indicators else "",
                            "Price_Above_EMA200": str(indicators_exit.get("price_above_ema200", indicators.get("price_above_ema200", ""))) if indicators_exit or indicators else "",
                            "EMA5_Above_EMA20": str(indicators_exit.get("ema5_above_ema20", indicators.get("ema5_above_ema20", ""))) if indicators_exit or indicators else "",
                            "EMA20_Above_EMA50": str(indicators_exit.get("ema20_above_ema50", indicators.get("ema20_above_ema50", ""))) if indicators_exit or indicators else "",
                            "EMA50_Above_EMA100": str(indicators_exit.get("ema50_above_ema100", indicators.get("ema50_above_ema100", ""))) if indicators_exit or indicators else "",
                            "EMA50_Above_EMA200": str(indicators_exit.get("ema50_above_ema200", indicators.get("ema50_above_ema200", ""))) if indicators_exit or indicators else "",
                            "EMA100_Above_EMA200": str(indicators_exit.get("ema100_above_ema200", indicators.get("ema100_above_ema200", ""))) if indicators_exit or indicators else "",
                            "Bollinger_Band_Position (20;2)": indicators_exit.get("bb_position_20_2", indicators.get("bb_position_20_2", "")) if indicators_exit or indicators else "",
                            "Weekly_BB_Position (20;2)": indicators_exit.get("Weekly_BB_Position (20;2)", indicators.get("Weekly_BB_Position (20;2)", "")) if indicators_exit or indicators else "",
                            "Bollinger_Band_Position (40;2)": indicators_exit.get("bb_position_40_2", indicators.get("bb_position_40_2", "")) if indicators_exit or indicators else "",
                            # === CHOPPINESS INDEX ===
                            "CHOP (20) Class": indicators_exit.get("chop_20_class", indicators.get("chop_20_class", "")) if indicators_exit or indicators else "",
                            "CHOP (50) Class": indicators_exit.get("chop_50_class", indicators.get("chop_50_class", "")) if indicators_exit or indicators else "",
                            # === VOLUME INDICATORS ===
                            "Daily_Volume_Above_MA20": indicators_exit.get("daily_volume_above_ma20", indicators.get("daily_volume_above_ma20", False)) if indicators_exit or indicators else False,
                            "Weekly_Volume_Above_MA20": indicators_exit.get("Weekly_Volume_Above_MA20", indicators.get("Weekly_Volume_Above_MA20", False)) if indicators_exit or indicators else False,
                            # === WEEKLY MULTI-TIMEFRAME ===
                            "Weekly_RSI (14)": indicators_exit.get("Weekly_RSI (14)", indicators.get("Weekly_RSI (14)", "")) if indicators_exit or indicators else "",
                            "Weekly_MACD_Bullish": indicators_exit.get("Weekly_MACD_Bullish", indicators.get("Weekly_MACD_Bullish", False)) if indicators_exit or indicators else False,
                            "Weekly_ADX (14)": indicators_exit.get("Weekly_ADX (14)", indicators.get("Weekly_ADX (14)", "")) if indicators_exit or indicators else "",
                            "Weekly_Above_EMA5": indicators_exit.get("Weekly_Above_EMA5", indicators.get("Weekly_Above_EMA5", False)) if indicators_exit or indicators else False,
                            "Weekly_Above_EMA20": indicators_exit.get("Weekly_Above_EMA20", indicators.get("Weekly_Above_EMA20", False)) if indicators_exit or indicators else False,
                            "Weekly_Above_EMA50": indicators_exit.get("Weekly_Above_EMA50", indicators.get("Weekly_Above_EMA50", False)) if indicators_exit or indicators else False,
                            "Weekly_Above_EMA200": indicators_exit.get("Weekly_Above_EMA200", indicators.get("Weekly_Above_EMA200", False)) if indicators_exit or indicators else False,
                            "Weekly_India_VIX": indicators_exit.get("Weekly_India_VIX", indicators.get("Weekly_India_VIX", "")) if indicators_exit or indicators else "",
                            "Weekly_CCI (20)": round(indicators_exit.get("Weekly_CCI (20)", indicators.get("Weekly_CCI (20)", 0)), 2) if indicators_exit or indicators else "",
                            "Weekly_MFI (20)": round(indicators_exit.get("Weekly_MFI (20)", indicators.get("Weekly_MFI (20)", 50)), 2) if indicators_exit or indicators else "",
                            "Weekly_CMF (20)": round(indicators_exit.get("Weekly_CMF (20)", indicators.get("Weekly_CMF (20)", 0)), 2) if indicators_exit or indicators else "",
                            "Weekly_KER (10)": round(indicators_exit.get("Weekly_KER (10)", indicators.get("Weekly_KER (10)", 0)), 3) if indicators_exit or indicators else "",
                            "Weekly_Candle_Colour": indicators_exit.get("Weekly_Candle_Colour", indicators.get("Weekly_Candle_Colour", "")) if indicators_exit or indicators else "",
                            "Weekly_Candlestick_Pattern": indicators_exit.get("Weekly_Candlestick_Pattern", indicators.get("Weekly_Candlestick_Pattern", "")) if indicators_exit or indicators else "",
                            "Weekly_CHOP (20) Class": indicators_exit.get("Weekly_CHOP (20) Class", indicators.get("Weekly_CHOP (20) Class", "")) if indicators_exit or indicators else "",
                            "Weekly_Short_Trend (Aroon 25)": indicators_exit.get("Weekly_Short_Trend (Aroon 25)", indicators.get("Weekly_Short_Trend (Aroon 25)", "")) if indicators_exit or indicators else "",
                            "Weekly_Medium_Trend (Aroon 50)": indicators_exit.get("Weekly_Medium_Trend (Aroon 50)", indicators.get("Weekly_Medium_Trend (Aroon 50)", "")) if indicators_exit or indicators else "",
                            "Weekly_Long_Trend (Aroon 100)": indicators_exit.get("Weekly_Long_Trend (Aroon 100)", indicators.get("Weekly_Long_Trend (Aroon 100)", "")) if indicators_exit or indicators else "",
                            # === WEEKLY NIFTY50 (from Groww weekly - no resampling) ===
                            "Weekly_NIFTY50_Above_EMA5": indicators_exit.get("Weekly_NIFTY50_Above_EMA5", indicators.get("Weekly_NIFTY50_Above_EMA5", True)) if indicators_exit or indicators else True,
                            "Weekly_NIFTY50_Above_EMA20": indicators_exit.get("Weekly_NIFTY50_Above_EMA20", indicators.get("Weekly_NIFTY50_Above_EMA20", True)) if indicators_exit or indicators else True,
                            "Weekly_NIFTY50_Above_EMA50": indicators_exit.get("Weekly_NIFTY50_Above_EMA50", indicators.get("Weekly_NIFTY50_Above_EMA50", True)) if indicators_exit or indicators else True,
                            "Weekly_NIFTY50_Above_EMA200": indicators_exit.get("Weekly_NIFTY50_Above_EMA200", indicators.get("Weekly_NIFTY50_Above_EMA200", True)) if indicators_exit or indicators else True,
                        }
                    )

                    # Entry row - POPULATE WITH ENTRY-TIME INDICATORS to validate filters
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
                            "Net P&L INR": net_pnl_int,
                            "Net P&L %": round(tv_net_pct, 2),
                            "Profitable": "Yes" if round(tv_net_pct, 2) > 0 else "No",

                            "Run-up INR": (int(run_up_exit) if run_up_exit > 0 else 0),
                            "Run-up %": round(tv_run_pct, 2),
                            "Drawdown INR": (
                                int(drawdown_exit)
                                if drawdown_exit is not None
                                else None
                            ),
                            "Drawdown %": round(tv_dd_pct, 2),
                            "Holding days": holding_days_val,
                            "ATR": atr_val,
                            "ATR %": atr_pct_val,
                            "MAE %": round(mae_pct, 2),
                            "MAE_ATR": mae_atr_val,
                            "MFE %": round(tv_run_pct, 2),
                            "MFE_ATR": mfe_atr_val,
                            # ===== ENTRY-TIME INDICATORS (show what filters were at entry) =====
                            "India VIX": indicators.get("india_vix", "") if indicators else "",
                            "NIFTY200 > EMA 5": str(indicators.get("nifty200_above_ema5", "")) if indicators else "",
                            "NIFTY200 > EMA 20": str(indicators.get("nifty200_above_ema20", "")) if indicators else "",
                            "NIFTY200 > EMA 50": str(indicators.get("nifty200_above_ema50", "")) if indicators else "",
                            "NIFTY200 > EMA 100": str(indicators.get("nifty200_above_ema100", "")) if indicators else "",
                            "NIFTY200 > EMA 200": str(indicators.get("nifty200_above_ema200", "")) if indicators else "",
                            "Short-Trend (Aroon 25)": indicators.get("short_trend_aroon25", "") if indicators else "",
                            "Medium-Trend (Aroon 50)": indicators.get("medium_trend_aroon50", "") if indicators else "",
                            "Long-Trend (Aroon 100)": indicators.get("long_trend_aroon100", "") if indicators else "",
                            "Volatility (14)": indicators.get("volatility_14", "") if indicators else "",
                            "Volatility (28)": indicators.get("volatility_28", "") if indicators else "",
                            "ADX (14)": round(indicators.get("adx_14", 0), 2) if indicators else "",
                            "ADX (28)": round(indicators.get("adx_28", 0), 2) if indicators else "",
                            "DI_Bullish (14)": str(indicators.get("di_bullish_14", "")) if indicators else "",
                            "DI_Bullish (28)": str(indicators.get("di_bullish_28", "")) if indicators else "",
                                                                                    "RSI (14)": round(indicators.get("rsi_14", 50), 2) if indicators else "",
                            "RSI (28)": round(indicators.get("rsi_28", 50), 2) if indicators else "",
                            "MACD_Bullish (12;26;9)": str(indicators.get("macd_bullish_12_26_9", "")) if indicators else "",
                            "MACD_Bullish (24;52;18)": str(indicators.get("macd_bullish_24_52_18", "")) if indicators else "",
                            "Price_Above_EMA5": str(indicators.get("price_above_ema5", "")) if indicators else "",
                            "Price_Above_EMA20": str(indicators.get("price_above_ema20", "")) if indicators else "",
                            "Price_Above_EMA50": str(indicators.get("price_above_ema50", "")) if indicators else "",
                            "Price_Above_EMA100": str(indicators.get("price_above_ema100", "")) if indicators else "",
                            "Price_Above_EMA200": str(indicators.get("price_above_ema200", "")) if indicators else "",
                            "EMA5_Above_EMA20": str(indicators.get("ema5_above_ema20", "")) if indicators else "",
                            "EMA20_Above_EMA50": str(indicators.get("ema20_above_ema50", "")) if indicators else "",
                            "EMA50_Above_EMA100": str(indicators.get("ema50_above_ema100", "")) if indicators else "",
                            "EMA50_Above_EMA200": str(indicators.get("ema50_above_ema200", "")) if indicators else "",
                            "EMA100_Above_EMA200": str(indicators.get("ema100_above_ema200", "")) if indicators else "",
                            "Bollinger_Band_Position (20;2)": indicators.get("bb_position_20_2", "") if indicators else "",
                            "Weekly_BB_Position (20;2)": indicators.get("Weekly_BB_Position (20;2)", "") if indicators else "",
                            "Bollinger_Band_Position (40;2)": indicators.get("bb_position_40_2", "") if indicators else "",
                            # === CHOPPINESS INDEX ===
                            "CHOP (20) Class": indicators.get("chop_20_class", "") if indicators else "",
                            "CHOP (50) Class": indicators.get("chop_50_class", "") if indicators else "",
                            # === VOLUME INDICATORS ===
                            "Daily_Volume_Above_MA20": indicators.get("daily_volume_above_ma20", False) if indicators else False,
                            "Weekly_Volume_Above_MA20": indicators.get("Weekly_Volume_Above_MA20", False) if indicators else False,
                            # === WEEKLY MULTI-TIMEFRAME ===
                            "Weekly_RSI (14)": indicators.get("Weekly_RSI (14)", "") if indicators else "",
                            "Weekly_MACD_Bullish": indicators.get("Weekly_MACD_Bullish", False) if indicators else False,
                            "Weekly_ADX (14)": indicators.get("Weekly_ADX (14)", "") if indicators else "",
                            "Weekly_Above_EMA5": indicators.get("Weekly_Above_EMA5", False) if indicators else False,
                            "Weekly_Above_EMA20": indicators.get("Weekly_Above_EMA20", False) if indicators else False,
                            "Weekly_Above_EMA50": indicators.get("Weekly_Above_EMA50", False) if indicators else False,
                            "Weekly_Above_EMA200": indicators.get("Weekly_Above_EMA200", False) if indicators else False,
                            "Weekly_India_VIX": indicators.get("Weekly_India_VIX", "") if indicators else "",
                            "Weekly_CCI (20)": round(indicators.get("Weekly_CCI (20)", 0), 2) if indicators else "",
                            "Weekly_MFI (20)": round(indicators.get("Weekly_MFI (20)", 50), 2) if indicators else "",
                            "Weekly_CMF (20)": round(indicators.get("Weekly_CMF (20)", 0), 2) if indicators else "",
                            "Weekly_KER (10)": round(indicators.get("Weekly_KER (10)", 0), 3) if indicators else "",
                            "Weekly_Candle_Colour": indicators.get("Weekly_Candle_Colour", "") if indicators else "",
                            "Weekly_Candlestick_Pattern": indicators.get("Weekly_Candlestick_Pattern", "") if indicators else "",
                            "Weekly_CHOP (20) Class": indicators.get("Weekly_CHOP (20) Class", "") if indicators else "",
                            "Weekly_Short_Trend (Aroon 25)": indicators.get("Weekly_Short_Trend (Aroon 25)", "") if indicators else "",
                            "Weekly_Medium_Trend (Aroon 50)": indicators.get("Weekly_Medium_Trend (Aroon 50)", "") if indicators else "",
                            "Weekly_Long_Trend (Aroon 100)": indicators.get("Weekly_Long_Trend (Aroon 100)", "") if indicators else "",
                            # === WEEKLY NIFTY50 (from Groww weekly - no resampling) ===
                            "Weekly_NIFTY50_Above_EMA5": indicators.get("Weekly_NIFTY50_Above_EMA5", True) if indicators else True,
                            "Weekly_NIFTY50_Above_EMA20": indicators.get("Weekly_NIFTY50_Above_EMA20", True) if indicators else True,
                            "Weekly_NIFTY50_Above_EMA50": indicators.get("Weekly_NIFTY50_Above_EMA50", True) if indicators else True,
                            "Weekly_NIFTY50_Above_EMA200": indicators.get("Weekly_NIFTY50_Above_EMA200", True) if indicators else True,
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
                    "Profitable",
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
                    # === VIX (Daily + Weekly) ===
                    "India VIX",
                    "Weekly_India_VIX",
                    # === NIFTY INDEX ===
                    "NIFTY200 > EMA 5",
                    "NIFTY200 > EMA 20",
                    "NIFTY200 > EMA 50",
                    "NIFTY200 > EMA 100",
                    "NIFTY200 > EMA 200",
                    "Weekly_NIFTY50_Above_EMA5",
                    "Weekly_NIFTY50_Above_EMA20",
                    "Weekly_NIFTY50_Above_EMA50",
                    "Weekly_NIFTY50_Above_EMA200",
                    # === TREND (Daily + Weekly side by side) ===
                    "Short-Trend (Aroon 25)",
                    "Weekly_Short_Trend (Aroon 25)",
                    "Medium-Trend (Aroon 50)",
                    "Weekly_Medium_Trend (Aroon 50)",
                    "Long-Trend (Aroon 100)",
                    "Weekly_Long_Trend (Aroon 100)",
                    # === VOLATILITY ===
                    "Volatility (14)",
                    "Volatility (28)",
                    # === ADX (Daily + Weekly side by side) ===
                    "ADX (14)",
                    "Weekly_ADX (14)",
                    "ADX (28)",
                    "DI_Bullish (14)",
                    "DI_Bullish (28)",
                    # === RSI (Daily + Weekly side by side) ===
                    "RSI (14)",
                    "Weekly_RSI (14)",
                    "RSI (28)",
                    # === MACD (Daily + Weekly side by side) ===
                    "MACD_Bullish (12;26;9)",
                    "Weekly_MACD_Bullish",
                    "MACD_Bullish (24;52;18)",
                    # === CCI (Weekly only) ===
                    "Weekly_CCI (20)",
                    # === PRICE VS EMAs (Daily + Weekly side by side) ===
                    "Price_Above_EMA5",
                    "Weekly_Above_EMA5",
                    "Price_Above_EMA20",
                    "Weekly_Above_EMA20",
                    "Price_Above_EMA50",
                    "Weekly_Above_EMA50",
                    "Price_Above_EMA100",
                    "Price_Above_EMA200",
                    "Weekly_Above_EMA200",
                    # === EMA CROSSOVERS ===
                    "EMA5_Above_EMA20",
                    "EMA20_Above_EMA50",
                    "EMA50_Above_EMA100",
                    "EMA50_Above_EMA200",
                    "EMA100_Above_EMA200",
                    # === BOLLINGER BANDS (Daily + Weekly side by side) ===
                    "Bollinger_Band_Position (20;2)",
                    "Weekly_BB_Position (20;2)",
                    "Bollinger_Band_Position (40;2)",
                    # === CHOPPINESS INDEX ===
                    "CHOP (20) Class",
                    "CHOP (50) Class",
                    # === VOLUME (Daily + Weekly side by side) ===
                    "Daily_Volume_Above_MA20",
                    "Weekly_Volume_Above_MA20",
                    # === MFI (Weekly only) ===
                    "Weekly_MFI (20)",
                    # === CMF (Weekly only) ===
                    "Weekly_CMF (20)",
                    # === KER (Weekly only) ===
                    "Weekly_KER (10)",
                    # === CANDLE (Weekly only) ===
                    "Weekly_Candle_Colour",
                    "Weekly_Candlestick_Pattern",
                    # === CHOP (Weekly only) ===
                    "Weekly_CHOP (20) Class",
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
                    # Write window-specific trades to file (NO accumulation - each window's trades are independent)
                    # Store column order on first pass
                    if trades_column_order is None:
                        trades_column_order = cols
                    
                    # Reassign Trade # to be sequential for this window's trades
                    # Each trade has 2 rows (Exit, Entry pairs)
                    # Row 0,1 = Trade 1; Row 2,3 = Trade 2; etc.
                    if "Trade #" in trades_only_out.columns:
                        trades_only_out = trades_only_out.reset_index(drop=True)
                        trades_only_out["Trade #"] = (trades_only_out.index // 2) + 1
                    
                    # Write this window's trades to file
                    trades_only_out.to_csv(trades_only_path, index=False, columns=cols)
                    consolidated_csv_paths[f"trades_{label}"] = trades_only_path
                    print(
                        f"DEBUG {label}: wrote consolidated trades file ({len(trades_only_out)} rows)"
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
    with timer.measure("Metrics Calculation & Report Generation"):
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

    # Consolidated indicator files are now included in consolidated_trades_*.csv files

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
    
    # Print timing report
    timer.report()


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
        "  python3 -m runners.run_basket --strategy ema_crossover --params '{}' --interval 1d --period max\n\n"
        "  # Use specific basket size:\n"
        "  python3 -m runners.run_basket --basket_size large --strategy ichimoku --params '{}' --interval 1d --period max\n\n"
        "  # Use custom basket file:\n"
        "  python3 -m runners.run_basket --basket_file data/my_basket.txt --strategy stoch_rsi_ob_long --params '{}' --interval 1d --period max\n"
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
        default="ichimoku_cloud",
        help="Strategy name in core.registry (e.g. ichimoku_cloud, ema_crossover, kama_crossover_filtered, stoch_rsi_ob_long)",
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
    ap.add_argument(
        "--compounding",
        action="store_true",
        default=True,
        help="Use compounding position sizing (% of current equity vs initial capital) - enabled by default",
    )
    ap.add_argument(
        "--no-compounding",
        action="store_true",
        default=False,
        help="Disable compounding (use fixed % of initial capital)",
    )
    args = ap.parse_args()

    # Resolve compounding: --no-compounding overrides --compounding
    compounding_enabled = args.compounding and not getattr(args, 'no_compounding', False)

    # Execute with comprehensive error handling and timeout management
    try:
        logger.info("Starting basket backtest execution...")
        logger.info(
            f"Configuration: strategy={args.strategy}, period={args.period}, cache_only={args.use_cache_only}, compounding={compounding_enabled}"
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
            compounding=compounding_enabled,
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
