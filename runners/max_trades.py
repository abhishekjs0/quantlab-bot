#!/usr/bin/env python3
"""
fast_max_trades.py - Fast runner that ONLY generates consolidated_trades_MAX.csv

This runner is optimized for quick trade analysis on the MAX window.
It generates ONLY the consolidated_trades_MAX.csv file with all indicators,
skipping portfolio curves, metrics tables, and other report generation.

Usage:
    python3 -m runners.fast_max_trades --strategy <strategy_name> --basket_file <basket_path>
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# ============================================================================
# CRITICAL: Prevent Python bytecode cache (.pyc) files
# ============================================================================
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True

import shutil
import warnings
from pathlib import Path

# Suppress FutureWarnings to speed up execution
warnings.filterwarnings('ignore', category=FutureWarning)

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
from core.registry import make_strategy
from core.loaders import load_many_india, load_india_vix, load_nifty200, aggregate_to_weekly
from core.report import make_run_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global cache for weekly NIFTY50 indicators (loaded once, used for all symbols)
_WEEKLY_NIFTY50_CACHE = None
_WEEKLY_VIX_CACHE = None  # Cache for VIX data
_WEEKLY_DATA_DIR = Path(__file__).parent.parent / "data" / "cache" / "groww" / "weekly"


def _load_weekly_vix() -> pd.DataFrame | None:
    """Load India VIX from weekly cache file.
    
    Returns DataFrame with 'close' column (VIX value) indexed by week start date.
    Uses Groww weekly format which has week START as index.
    """
    global _WEEKLY_VIX_CACHE
    if _WEEKLY_VIX_CACHE is not None:
        return _WEEKLY_VIX_CACHE
    
    try:
        # Try Groww weekly VIX first
        vix_path = _WEEKLY_DATA_DIR / "groww_0_INDIAVIX_1w.csv"
        if not vix_path.exists():
            # Fallback to dhan weekly
            vix_path = Path(__file__).parent.parent / "data" / "cache" / "dhan" / "weekly" / "dhan_21_INDIA_VIX_1w.csv"
        
        if not vix_path.exists():
            logger.warning("India VIX weekly data not found")
            return None
        
        df = pd.read_csv(vix_path, parse_dates=['time'], index_col='time')
        df.index = pd.to_datetime(df.index).normalize()
        df = df.sort_index()
        df.columns = df.columns.str.lower()
        
        _WEEKLY_VIX_CACHE = df
        logger.info(f"✓ Loaded India VIX weekly data: {len(df)} weeks")
        return df
        
    except Exception as e:
        logger.warning(f"Failed to load India VIX weekly: {e}")
        return None


def _load_weekly_nifty50_indicators() -> pd.DataFrame | None:
    """Load NIFTY50 weekly data and calculate EMA indicators.
    
    Returns DataFrame with columns: weekly_nifty50_above_ema5, weekly_nifty50_above_ema20, weekly_nifty50_above_ema50,
    weekly_nifty50_above_ema200 indexed by week end date.
    """
    global _WEEKLY_NIFTY50_CACHE
    if _WEEKLY_NIFTY50_CACHE is not None:
        return _WEEKLY_NIFTY50_CACHE
    
    try:
        # Try loading from Groww weekly cache
        nifty50_weekly_path = _WEEKLY_DATA_DIR / "groww_0_NIFTY_50_1w.csv"
        if not nifty50_weekly_path.exists():
            logger.warning("NIFTY50 weekly data not found, weekly NIFTY50 indicators will be NaN")
            return None
        
        df = pd.read_csv(nifty50_weekly_path, parse_dates=['time'], index_col='time')
        df.index = pd.to_datetime(df.index).normalize()
        df = df.sort_index()
        
        from utils import EMA
        close_arr = df['close'].astype(float).values
        
        ema5 = EMA(close_arr, 5)
        ema20 = EMA(close_arr, 20)
        ema50 = EMA(close_arr, 50)
        ema200 = EMA(close_arr, 200)
        
        result = pd.DataFrame({
            'Weekly_NIFTY50_Above_EMA5': close_arr > ema5,
            'Weekly_NIFTY50_Above_EMA20': close_arr > ema20,
            'Weekly_NIFTY50_Above_EMA50': close_arr > ema50,
            'Weekly_NIFTY50_Above_EMA200': close_arr > ema200,
        }, index=df.index)
        
        _WEEKLY_NIFTY50_CACHE = result
        logger.info(f"✓ Loaded NIFTY50 weekly indicators: {len(result)} weeks")
        return result
        
    except Exception as e:
        logger.warning(f"Failed to load NIFTY50 weekly: {e}")
        return None


def _load_weekly_data_for_symbol(symbol: str, daily_df: pd.DataFrame) -> pd.DataFrame | None:
    """Load weekly data for a symbol from Groww cache or aggregate from daily.
    
    Args:
        symbol: Symbol name (e.g., 'RELIANCE')
        daily_df: Daily OHLC DataFrame to aggregate if weekly cache not found
        
    Returns:
        Weekly OHLC DataFrame or None if failed (excludes incomplete current week)
    """
    clean_symbol = symbol.replace("NSE:", "").replace(":", "_").replace("/", "_").strip()
    
    # Try Groww weekly cache first
    import glob
    pattern = str(_WEEKLY_DATA_DIR / f"groww_*_{clean_symbol}_1w.csv")
    matches = glob.glob(pattern)
    
    if matches:
        try:
            df = pd.read_csv(matches[0], parse_dates=['time'], index_col='time')
            df.index = pd.to_datetime(df.index).normalize()
            df = df.sort_index()
            # CRITICAL: Exclude incomplete current week to avoid lookahead bias
            # Keep only weeks that have ended before today
            today = pd.Timestamp.now().normalize()
            df = df[df.index < today]
            return df if not df.empty else None
        except Exception:
            pass  # Fall through to aggregation
    
    # Aggregate daily to weekly as fallback
    if daily_df is not None and not daily_df.empty:
        try:
            weekly_df = aggregate_to_weekly(daily_df)
            # CRITICAL: Exclude incomplete current week to avoid lookahead bias
            today = pd.Timestamp.now().normalize()
            weekly_df = weekly_df[weekly_df.index < today]
            return weekly_df if not weekly_df.empty else None
        except Exception:
            pass
    
    return None


def _calculate_weekly_indicators(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate weekly indicators for a symbol.
    
    Returns DataFrame indexed by week with weekly indicator columns.
    """
    if weekly_df is None or weekly_df.empty:
        return pd.DataFrame()
    
    import math
    from utils import EMA, RSI, SMA, MACD, BollingerBands, ATR
    from utils.indicators import ADX, CCI, MFI, CMF, Aroon, TrendClassification, kaufman_efficiency_ratio
    
    close_arr = weekly_df['close'].astype(float).values
    high_arr = weekly_df['high'].astype(float).values
    low_arr = weekly_df['low'].astype(float).values
    open_arr = weekly_df['open'].astype(float).values if 'open' in weekly_df.columns else close_arr
    volume_arr = weekly_df['volume'].astype(float).values if 'volume' in weekly_df.columns else np.ones(len(close_arr))
    
    # Volume
    vol_sma20 = SMA(volume_arr, 20)
    
    # RSI
    rsi_14 = RSI(close_arr, 14)
    
    # MACD
    macd_result = MACD(close_arr, 12, 26, 9)
    macd_line = macd_result.get('macd', np.full(len(close_arr), np.nan))
    signal_line = macd_result.get('signal', np.full(len(close_arr), np.nan))
    
    # ADX - extract 'adx' array from returned dict
    adx_result = ADX(high_arr, low_arr, close_arr, 14)
    adx_14 = adx_result.get('adx', np.full(len(close_arr), np.nan)) if isinstance(adx_result, dict) else adx_result
    
    # EMAs
    ema5 = EMA(close_arr, 5)
    ema20 = EMA(close_arr, 20)
    ema50 = EMA(close_arr, 50)
    ema200 = EMA(close_arr, 200)
    
    # Bollinger Bands
    bb_20 = BollingerBands(close_arr, 20, 2)
    
    # CCI (20)
    cci_20 = CCI(high_arr, low_arr, close_arr, 20)
    
    # MFI (20), CMF (20)
    mfi_20 = MFI(high_arr, low_arr, close_arr, volume_arr, 20)
    cmf_20 = CMF(high_arr, low_arr, close_arr, volume_arr, 20)
    
    # KER (10)
    ker_10 = kaufman_efficiency_ratio(close_arr, 10)
    
    # Candle Colour
    candle_colour = np.where(close_arr > open_arr, 'green', 
                            np.where(close_arr < open_arr, 'red', 'doji'))
    
    # Candlestick Patterns
    try:
        import talib
        
        bullish_patterns = ['cdl_hammer', 'cdl_inverted_hammer', 'cdl_engulfing_bullish', 
                           'cdl_morning_star', 'cdl_three_white_soldiers', 'cdl_piercing', 'cdl_dragonfly_doji']
        bearish_patterns = ['cdl_hanging_man', 'cdl_shooting_star', 'cdl_engulfing_bearish',
                           'cdl_evening_star', 'cdl_three_black_crows', 'cdl_dark_cloud', 'cdl_gravestone_doji']
        
        cdl_hammer = talib.CDLHAMMER(open_arr, high_arr, low_arr, close_arr)
        cdl_inverted_hammer = talib.CDLINVERTEDHAMMER(open_arr, high_arr, low_arr, close_arr)
        cdl_engulfing_bullish = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
        cdl_morning_star = talib.CDLMORNINGSTAR(open_arr, high_arr, low_arr, close_arr)
        cdl_three_white_soldiers = talib.CDL3WHITESOLDIERS(open_arr, high_arr, low_arr, close_arr)
        cdl_piercing = talib.CDLPIERCING(open_arr, high_arr, low_arr, close_arr)
        cdl_dragonfly_doji = talib.CDLDRAGONFLYDOJI(open_arr, high_arr, low_arr, close_arr)
        cdl_hanging_man = talib.CDLHANGINGMAN(open_arr, high_arr, low_arr, close_arr)
        cdl_shooting_star = talib.CDLSHOOTINGSTAR(open_arr, high_arr, low_arr, close_arr)
        cdl_engulfing_bearish = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) < 0, 100, 0)
        cdl_evening_star = talib.CDLEVENINGSTAR(open_arr, high_arr, low_arr, close_arr)
        cdl_three_black_crows = talib.CDL3BLACKCROWS(open_arr, high_arr, low_arr, close_arr)
        cdl_dark_cloud = talib.CDLDARKCLOUDCOVER(open_arr, high_arr, low_arr, close_arr)
        cdl_gravestone_doji = talib.CDLGRAVESTONEDOJI(open_arr, high_arr, low_arr, close_arr)
        
        def get_pattern_name(row_idx):
            if cdl_hammer[row_idx] != 0: return 'Hammer'
            if cdl_inverted_hammer[row_idx] != 0: return 'Inverted Hammer'
            if cdl_engulfing_bullish[row_idx] != 0: return 'Bullish Engulfing'
            if cdl_morning_star[row_idx] != 0: return 'Morning Star'
            if cdl_three_white_soldiers[row_idx] != 0: return 'Three White Soldiers'
            if cdl_piercing[row_idx] != 0: return 'Piercing'
            if cdl_dragonfly_doji[row_idx] != 0: return 'Dragonfly Doji'
            if cdl_hanging_man[row_idx] != 0: return 'Hanging Man'
            if cdl_shooting_star[row_idx] != 0: return 'Shooting Star'
            if cdl_engulfing_bearish[row_idx] != 0: return 'Bearish Engulfing'
            if cdl_evening_star[row_idx] != 0: return 'Evening Star'
            if cdl_three_black_crows[row_idx] != 0: return 'Three Black Crows'
            if cdl_dark_cloud[row_idx] != 0: return 'Dark Cloud Cover'
            if cdl_gravestone_doji[row_idx] != 0: return 'Gravestone Doji'
            return ''
        
        candlestick_pattern = [get_pattern_name(i) for i in range(len(close_arr))]
    except ImportError:
        candlestick_pattern = [''] * len(close_arr)
    except Exception:
        candlestick_pattern = [''] * len(close_arr)
    
    # Choppiness Index (20)
    def choppiness_index(high, low, close, length=14):
        n = len(close)
        chop = np.full(n, np.nan)
        
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        
        log_length = math.log10(length)
        
        for i in range(length, n):
            atr_sum = np.sum(tr[i-length+1:i+1])
            highest_high = np.max(high[i-length+1:i+1])
            lowest_low = np.min(low[i-length+1:i+1])
            range_val = highest_high - lowest_low
            
            if range_val > 0 and log_length > 0:
                chop[i] = 100 * math.log10(atr_sum / range_val) / log_length
        
        return chop
    
    def classify_chop(chop_values):
        return np.where(chop_values >= 61.8, 'Very Choppy',
               np.where(chop_values >= 50, 'Choppy',
               np.where(chop_values >= 38.2, 'Trending', 'Strong Trend')))
    
    chop_20 = choppiness_index(high_arr, low_arr, close_arr, 20)
    chop_20_class = classify_chop(chop_20)
    
    # Aroon Trend Classification (25, 50, 100)
    aroon_25 = Aroon(high_arr, low_arr, 25)
    aroon_50 = Aroon(high_arr, low_arr, 50)
    aroon_100 = Aroon(high_arr, low_arr, 100)
    
    short_trend = [
        TrendClassification(aroon_25['aroon_up'][i], aroon_25['aroon_down'][i], period=25)
        if i < len(aroon_25['aroon_up']) else 'Sideways'
        for i in range(len(close_arr))
    ]
    medium_trend = [
        TrendClassification(aroon_50['aroon_up'][i], aroon_50['aroon_down'][i], period=50)
        if i < len(aroon_50['aroon_up']) else 'Sideways'
        for i in range(len(close_arr))
    ]
    long_trend = [
        TrendClassification(aroon_100['aroon_up'][i], aroon_100['aroon_down'][i], period=100)
        if i < len(aroon_100['aroon_up']) else 'Sideways'
        for i in range(len(close_arr))
    ]
    
    result = pd.DataFrame({
        'Weekly_Volume_Above_MA20': volume_arr > vol_sma20,
        'Weekly_RSI (14)': np.round(rsi_14, 2),
        'Weekly_MACD_Bullish': macd_line > signal_line,
        'Weekly_ADX (14)': np.round(adx_14, 2),
        'Weekly_Above_EMA5': close_arr > ema5,
        'Weekly_Above_EMA20': close_arr > ema20,
        'Weekly_Above_EMA50': close_arr > ema50,
        'Weekly_Above_EMA200': close_arr > ema200,
        'Weekly_BB_Position (20;2)': np.where(close_arr > bb_20['upper'], 'Above', 
                                             np.where(close_arr < bb_20['lower'], 'Below', 'Middle')),
        'Daily_CCI (20)': np.round(cci_20, 2),
        'Daily_MFI (20)': np.round(mfi_20, 2),
        'Daily_CMF (20)': np.round(cmf_20, 2),
        'Weekly_KER (10)': np.round(ker_10, 3),
        'Weekly_Candle_Colour': candle_colour,
        'Weekly_Candlestick_Pattern': candlestick_pattern,
        'Weekly_CHOP (20) Class': chop_20_class,
        'Weekly_Short_Trend (Aroon 25)': short_trend,
        'Weekly_Medium_Trend (Aroon 50)': medium_trend,
        'Weekly_Long_Trend (Aroon 100)': long_trend,
    }, index=weekly_df.index)
    
    return result


def _read_symbols_from_txt(txt_path: str) -> list[str]:
    """Read symbols from a basket text file."""
    with open(txt_path) as f:
        lines = [ln.strip() for ln in f.read().splitlines()]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("Empty symbols file")
    if lines[0].lower() == "symbol":
        lines = lines[1:]
    return lines


def _enrich_with_vix(df: pd.DataFrame) -> pd.DataFrame:
    """Add india_vix column to DataFrame for VIX filter in strategies.
    
    Uses weekly VIX data mapped to daily bars (daily VIX file may not exist).
    """
    try:
        vix_weekly_df = _load_weekly_vix()
        if vix_weekly_df is not None and not vix_weekly_df.empty:
            # Weekly VIX time is week START (Sunday 18:30 IST)
            # Add 7 days to get week END, then map daily bars to completed weeks
            daily_dates = pd.to_datetime(df.index).normalize()
            week_end_dates = (vix_weekly_df.index + pd.Timedelta(days=7)).normalize()
            vix_values = vix_weekly_df['close'].values
            
            # Map each daily date to the most recent completed weekly VIX
            week_indices = np.searchsorted(week_end_dates, daily_dates, side='right') - 1
            
            india_vix_mapped = np.full(len(df), np.nan)
            for i, week_idx in enumerate(week_indices):
                if 0 <= week_idx < len(vix_values):
                    india_vix_mapped[i] = vix_values[week_idx]
            
            df['india_vix'] = india_vix_mapped
            df['india_vix'] = df['india_vix'].ffill()  # Forward fill for holidays
        else:
            df['india_vix'] = np.nan
    except Exception:
        df['india_vix'] = np.nan
    return df


def _enrich_with_nifty200_ema(df: pd.DataFrame) -> pd.DataFrame:
    """Add nifty200_above_ema50 indicator to DataFrame for market regime filter."""
    from utils import EMA
    try:
        nifty200_df = load_nifty200()
        nifty200_close = nifty200_df['close'].values
        nifty200_ema50 = EMA(nifty200_close, 50)
        nifty200_above_50 = pd.Series(nifty200_close > nifty200_ema50, index=nifty200_df.index)
        df = df.join(nifty200_above_50.rename('nifty200_above_ema50'), how='left')
        df['nifty200_above_ema50'] = df['nifty200_above_ema50'].infer_objects(copy=False).ffill().fillna(True).astype(bool)
    except Exception:
        df['nifty200_above_ema50'] = True
    return df


def _process_symbol(args: tuple) -> tuple:
    """Process a single symbol for backtesting (module-level for multiprocessing)."""
    symbol, df_full, strategy_name, cfg = args
    try:
        strat = make_strategy(strategy_name)
        engine = BacktestEngine(df_full, strat, cfg, symbol=symbol)
        trades_full, equity_full, _ = engine.run()
        return (symbol, {"trades": trades_full, "data": df_full}, None)
    except Exception as e:
        return (symbol, None, f"Error: {str(e)[:50]}")


def _calculate_all_indicators(
    df: pd.DataFrame,
    weekly_df: pd.DataFrame | None = None,
    weekly_nifty50_df: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Calculate ALL indicators for consolidated file export.
    
    Args:
        df: Daily OHLCV DataFrame
        weekly_df: Optional weekly OHLCV DataFrame for this symbol
        weekly_nifty50_df: Optional preloaded NIFTY50 weekly indicators
    """
    if df.empty:
        return df
    
    result_df = df.copy()
    
    # Pre-calculate OHLCV arrays
    high_arr = df["high"].astype(float).values
    low_arr = df["low"].astype(float).values
    close_arr = df["close"].astype(float).values
    volume_arr = df["volume"].astype(float).values if "volume" in df.columns else np.ones(len(close_arr))
    
    # Import indicator functions
    from utils import ATR, EMA, MACD, RSI, SMA, BollingerBands, Stochastic
    from utils.indicators import (
        ADX, CCI, MFI, CMF, Aroon, StochasticRSI,
        TrendClassification, VolatilityClassification,
        kaufman_efficiency_ratio,
    )
    
    # ========== REGIME FILTERS ==========
    
    # Store daily dates as normalized timestamps for joining
    daily_dates = pd.to_datetime(result_df.index).normalize()
    
    # India VIX - use weekly VIX and map to daily (daily VIX file may not exist)
    try:
        vix_weekly_df = _load_weekly_vix()
        if vix_weekly_df is not None and not vix_weekly_df.empty:
            # Weekly VIX time is week START (Sunday 18:30 IST)
            # Add 7 days to get week END, then map daily bars to completed weeks
            week_end_dates = (vix_weekly_df.index + pd.Timedelta(days=7)).normalize()
            vix_values = vix_weekly_df['close'].values
            
            # Map each daily date to the most recent completed weekly VIX
            # searchsorted gives index where daily_date would be inserted
            # -1 gives the last completed week
            week_indices = np.searchsorted(week_end_dates, daily_dates, side='right') - 1
            
            india_vix_mapped = np.full(len(result_df), np.nan)
            for i, week_idx in enumerate(week_indices):
                if 0 <= week_idx < len(vix_values):
                    india_vix_mapped[i] = vix_values[week_idx]
            
            result_df['india_vix'] = india_vix_mapped
            result_df['india_vix'] = result_df['india_vix'].ffill()  # Forward fill for holidays
        else:
            result_df['india_vix'] = np.nan
    except Exception:
        result_df['india_vix'] = np.nan
    
    # NIFTY200 EMA comparisons
    try:
        nifty200_df = load_nifty200()
        nifty200_close = nifty200_df['close'].values
        nifty200_ema5 = EMA(nifty200_close, 5)
        nifty200_ema20 = EMA(nifty200_close, 20)
        nifty200_ema50 = EMA(nifty200_close, 50)
        nifty200_ema100 = EMA(nifty200_close, 100)
        nifty200_ema200 = EMA(nifty200_close, 200)
        
        nifty200_dates = pd.to_datetime(nifty200_df.index).normalize()
        
        nifty200_above_5 = pd.Series(nifty200_close > nifty200_ema5, index=nifty200_dates)
        nifty200_above_20 = pd.Series(nifty200_close > nifty200_ema20, index=nifty200_dates)
        nifty200_above_50 = pd.Series(nifty200_close > nifty200_ema50, index=nifty200_dates)
        nifty200_above_100 = pd.Series(nifty200_close > nifty200_ema100, index=nifty200_dates)
        nifty200_above_200 = pd.Series(nifty200_close > nifty200_ema200, index=nifty200_dates)
        
        result_dates = pd.to_datetime(result_df.index).normalize()
        
        result_df['nifty200_above_ema5'] = result_dates.map(lambda d: nifty200_above_5.get(d, pd.NA))
        result_df['nifty200_above_ema20'] = result_dates.map(lambda d: nifty200_above_20.get(d, pd.NA))
        result_df['nifty200_above_ema50'] = result_dates.map(lambda d: nifty200_above_50.get(d, pd.NA))
        result_df['nifty200_above_ema100'] = result_dates.map(lambda d: nifty200_above_100.get(d, pd.NA))
        result_df['nifty200_above_ema200'] = result_dates.map(lambda d: nifty200_above_200.get(d, pd.NA))
        
        for col in ['nifty200_above_ema5', 'nifty200_above_ema20', 'nifty200_above_ema50', 
                    'nifty200_above_ema100', 'nifty200_above_ema200']:
            result_df[col] = result_df[col].ffill().fillna(True).astype(bool)
    except Exception:
        for col in ['nifty200_above_ema5', 'nifty200_above_ema20', 'nifty200_above_ema50',
                    'nifty200_above_ema100', 'nifty200_above_ema200']:
            result_df[col] = np.nan  # Return NaN instead of defaulting to True
    
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
    
    result_df['atr_14'] = atr_14  # Raw ATR value
    result_df['atr_pct_14'] = atr_pct_14  # Raw ATR % for consistent usage
    result_df['volatility_14'] = [VolatilityClassification(atr_pct_14[i], period=14) for i in range(len(df))]
    result_df['volatility_28'] = [VolatilityClassification(atr_pct_28[i], period=28) for i in range(len(df))]
    
    # ========== TREND STRENGTH ==========
    adx_14 = ADX(high_arr, low_arr, close_arr, 14)
    adx_28 = ADX(high_arr, low_arr, close_arr, 28)
    
    result_df['adx_14'] = adx_14['adx']
    result_df['adx_28'] = adx_28['adx']
    result_df['di_bullish_14'] = adx_14['di_plus'] > adx_14['di_minus']
    result_df['di_bullish_28'] = adx_28['di_plus'] > adx_28['di_minus']
    
    # ========== MOMENTUM ==========
    result_df['rsi_14'] = RSI(close_arr, 14)
    result_df['rsi_28'] = RSI(close_arr, 28)
    
    macd_12_26_9 = MACD(close_arr, 12, 26, 9)
    macd_24_52_18 = MACD(close_arr, 24, 52, 18)
    result_df['macd_bullish_12_26_9'] = macd_12_26_9['macd'] > macd_12_26_9['signal']
    result_df['macd_bullish_24_52_18'] = macd_24_52_18['macd'] > macd_24_52_18['signal']
    
    # ========== TREND STRUCTURE ==========
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
    result_df['ema100_above_ema200'] = ema_100 > ema_200
    
    # Bollinger Bands Position
    bb_20 = BollingerBands(close_arr, 20, 2)
    bb_40 = BollingerBands(close_arr, 40, 2)
    
    result_df['bb_position_20_2'] = np.where(close_arr > bb_20['upper'], 'Above', 
                                              np.where(close_arr < bb_20['lower'], 'Below', 'Middle'))
    result_df['bb_position_40_2'] = np.where(close_arr > bb_40['upper'], 'Above', 
                                              np.where(close_arr < bb_40['lower'], 'Below', 'Middle'))
    
    # ========== CHOPPINESS INDEX (Daily) ==========
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
    
    chop_20_daily = choppiness_index_daily(high_arr, low_arr, close_arr, 20)
    chop_50_daily = choppiness_index_daily(high_arr, low_arr, close_arr, 50)
    result_df['chop_20_class'] = classify_chop_daily(chop_20_daily)
    result_df['chop_50_class'] = classify_chop_daily(chop_50_daily)
    
    # ========== VOLUME INDICATORS ==========
    volume_sma20 = SMA(volume_arr, 20)
    result_df['daily_volume_above_ma20'] = volume_arr > volume_sma20
    
    # ========== WEEKLY INDICATORS ==========
    # Map daily dates to weeks for joining weekly data
    daily_dates = pd.to_datetime(result_df.index).normalize()
    
    # Symbol-specific weekly indicators (from weekly_df parameter)
    weekly_cols = ['Weekly_Volume_Above_MA20', 'Weekly_RSI (14)', 'Weekly_MACD_Bullish',
                   'Weekly_ADX (14)', 'Weekly_Above_EMA5', 'Weekly_Above_EMA20', 'Weekly_Above_EMA50', 'Weekly_Above_EMA200',
                   'Weekly_BB_Position (20;2)', 'Daily_CCI (20)', 'Daily_MFI (20)', 'Daily_CMF (20)',
                   'Weekly_KER (10)', 'Weekly_Candle_Colour', 'Weekly_Candlestick_Pattern', 'Weekly_CHOP (20) Class',
                   'Weekly_Short_Trend (Aroon 25)', 'Weekly_Medium_Trend (Aroon 50)', 'Weekly_Long_Trend (Aroon 100)']
    
    if weekly_df is not None and not weekly_df.empty:
        try:
            weekly_indicators = _calculate_weekly_indicators(weekly_df)
            if not weekly_indicators.empty:
                weekly_indicators.index = pd.to_datetime(weekly_indicators.index).normalize()
                
                # LOOKAHEAD FIX: The weekly CSV 'time' is the week START (Sunday).
                # A weekly bar is only complete after that week ends (Friday close).
                # Shift index by +7 days so that a bar dated Sunday Jan 3 (containing Jan 4-8 data)
                # becomes Jan 10, and will only be available via forward-fill starting Monday Jan 11.
                weekly_indicators.index = weekly_indicators.index + pd.Timedelta(days=7)
                
                # For each daily row, find the most recent weekly data point - use simple forward fill
                for col in weekly_cols:
                    if col in weekly_indicators.columns:
                        # Reindex weekly data to daily dates and forward fill
                        daily_dates_df = pd.DataFrame(index=daily_dates)
                        weekly_col_data = pd.DataFrame({col: weekly_indicators[col]})
                        merged = daily_dates_df.join(weekly_col_data, how='left')
                        result_df[col] = merged[col].fillna(method='ffill').values
                    else:
                        result_df[col] = np.nan
            else:
                for col in weekly_cols:
                    result_df[col] = np.nan
        except Exception:
            for col in weekly_cols:
                result_df[col] = np.nan
    else:
        for col in weekly_cols:
            result_df[col] = np.nan
    
    # Weekly VIX (from weekly VIX cache, same as india_vix but for output column)
    try:
        vix_weekly_df = _load_weekly_vix()
        if vix_weekly_df is not None and not vix_weekly_df.empty:
            # Weekly VIX time is week START (Sunday 18:30 IST)
            # Add 7 days to get week END, then map daily bars to completed weeks
            week_end_dates = (vix_weekly_df.index + pd.Timedelta(days=7)).normalize()
            vix_values = vix_weekly_df['close'].values
            
            # Map each daily date to the most recent completed weekly VIX
            week_indices = np.searchsorted(week_end_dates, daily_dates, side='right') - 1
            
            weekly_vix_mapped = np.full(len(result_df), np.nan)
            for i, week_idx in enumerate(week_indices):
                if 0 <= week_idx < len(vix_values):
                    weekly_vix_mapped[i] = vix_values[week_idx]
            
            result_df['Weekly_India_VIX'] = weekly_vix_mapped
            result_df['Weekly_India_VIX'] = result_df['Weekly_India_VIX'].ffill()  # Forward fill for holidays
        else:
            result_df['Weekly_India_VIX'] = np.nan
    except Exception:
        result_df['Weekly_India_VIX'] = np.nan
    
    # Weekly NIFTY50 indicators (from preloaded global cache)
    nifty50_weekly_cols = ['Weekly_NIFTY50_Above_EMA5', 'Weekly_NIFTY50_Above_EMA20', 'Weekly_NIFTY50_Above_EMA50',
                           'Weekly_NIFTY50_Above_EMA200']
    
    if weekly_nifty50_df is not None and not weekly_nifty50_df.empty:
        try:
            # LOOKAHEAD FIX: Shift NIFTY50 weekly index by +7 days (same as symbol weekly)
            nifty50_shifted = weekly_nifty50_df.copy()
            nifty50_shifted.index = nifty50_shifted.index + pd.Timedelta(days=7)
            
            for col in nifty50_weekly_cols:
                if col in nifty50_shifted.columns:
                    # Reindex weekly data to daily dates and forward fill
                    daily_dates_df = pd.DataFrame(index=daily_dates)
                    weekly_col_data = pd.DataFrame({col: nifty50_shifted[col]})
                    merged = daily_dates_df.join(weekly_col_data, how='left')
                    result_df[col] = merged[col].fillna(method='ffill').values
                else:
                    result_df[col] = np.nan
        except Exception:
            for col in nifty50_weekly_cols:
                result_df[col] = np.nan
    else:
        for col in nifty50_weekly_cols:
            result_df[col] = np.nan
    
    return result_df


def run_fast_max_trades(
    basket_file: str,
    strategy_name: str,
    interval: str = "1d",
    workers: int = None,
) -> str:
    """
    Run backtest and generate ONLY consolidated_trades_MAX.csv.
    
    Args:
        basket_file: Path to basket file with symbols
        strategy_name: Strategy name to run
        interval: Timeframe interval (default: 1d)
        workers: Number of parallel workers (default: cpu_count - 1)
        
    Returns:
        Path to the generated consolidated_trades_MAX.csv file
    """
    start_time = time.time()
    
    # Load symbols
    symbols = _read_symbols_from_txt(basket_file)
    logger.info(f"🚀 FAST MAX TRADES: {strategy_name}")
    logger.info(f"📊 {len(symbols)} symbols loaded")
    
    # Extract basket name
    basket_name = os.path.basename(basket_file).replace(".txt", "").replace("basket_", "")
    
    # Create output directory
    run_dir = make_run_dir(strategy_name=strategy_name, basket_name=basket_name, timeframe=interval)
    
    # Load OHLCV data
    logger.info("📥 Loading OHLCV data...")
    
    # Try local Dhan CSVs first
    data_map = {}
    try:
        inst_csv = os.path.join("data", "dhan-scrip-master-detailed.csv")
        if os.path.exists(inst_csv):
            inst_df = pd.read_csv(inst_csv, low_memory=False)
            for sym in symbols:
                base = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                cand = inst_df[(inst_df["SYMBOL_NAME"] == base) | (inst_df["UNDERLYING_SYMBOL"] == base)]
                if not cand.empty:
                    secid = int(cand.iloc[0]["SECURITY_ID"])
                    csv_path = os.path.join("data", "cache", f"dhan_historical_{secid}.csv")
                    if os.path.exists(csv_path):
                        try:
                            df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
                            df.index = pd.to_datetime(df.index)
                            data_map[sym] = df.sort_index()
                        except Exception:
                            pass
        if not data_map:
            raise RuntimeError("No local Dhan CSVs")
    except Exception:
        data_map = load_many_india(symbols, interval=interval, period="max", cache=True, use_cache_only=True)
    
    # Filter symbols with data
    valid_symbols = [s for s in symbols if s in data_map and data_map[s] is not None and not data_map[s].empty]
    logger.info(f"📈 {len(valid_symbols)} symbols with data")
    
    # Enrich data with VIX and NIFTY200 EMA for strategy filters
    logger.info("📊 Enriching data with VIX and NIFTY200 EMA...")
    for sym in valid_symbols:
        df = data_map[sym]
        df = _enrich_with_vix(df)
        df = _enrich_with_nifty200_ema(df)
        data_map[sym] = df
    
    # Setup config
    cfg = BrokerConfig()
    
    # Prepare for parallel processing
    num_workers = workers if workers else max(1, cpu_count() - 1)
    logger.info(f"🔄 Running backtests ({num_workers} workers)...")
    
    # Process symbols
    symbol_results = {}
    
    if num_workers > 1 and len(valid_symbols) > 1:
        ctx = get_context("spawn")
        task_args = [(sym, data_map[sym], strategy_name, cfg) for sym in valid_symbols]
        
        with ctx.Pool(processes=num_workers) as pool:
            results = pool.map(_process_symbol, task_args, chunksize=1)
        
        for sym, result, error in results:
            if error:
                logger.debug(f"⚠️ {sym}: {error}")
            else:
                symbol_results[sym] = result
    else:
        for i, sym in enumerate(valid_symbols):
            if (i + 1) % 50 == 0:
                logger.info(f"   ✅ {i+1}/{len(valid_symbols)}")
            try:
                strat = make_strategy(strategy_name)
                engine = BacktestEngine(data_map[sym], strat, cfg, symbol=sym)
                trades_full, _, _ = engine.run()
                symbol_results[sym] = {"trades": trades_full, "data": data_map[sym]}
            except Exception as e:
                logger.debug(f"⚠️ {sym}: {e}")
    
    logger.info(f"✅ {len(symbol_results)} symbols processed")
    
    # Build consolidated trades for MAX window (all data)
    logger.info("📝 Building consolidated_trades_MAX.csv...")
    
    # Pre-load weekly NIFTY50 indicators (used for all trades)
    weekly_nifty50_indicators = _load_weekly_nifty50_indicators()
    
    # Pre-load weekly data for all symbols with trades
    weekly_data_cache = {}
    symbols_with_trades = set()
    
    trades_list = []
    for sym, result in symbol_results.items():
        trades = result.get("trades")
        if trades is not None and not trades.empty:
            t = trades.copy()
            t["Symbol"] = sym
            trades_list.append(t)
            symbols_with_trades.add(sym)
    
    # Load weekly data for symbols that have trades
    logger.info(f"📊 Loading weekly data for {len(symbols_with_trades)} symbols...")
    for sym in symbols_with_trades:
        daily_df = symbol_results.get(sym, {}).get("data")
        weekly_df = _load_weekly_data_for_symbol(sym, daily_df)
        if weekly_df is not None:
            weekly_data_cache[sym] = weekly_df
    logger.info(f"   ✓ Loaded weekly data for {len(weekly_data_cache)} symbols")
    
    if not trades_list:
        logger.warning("⚠️ No trades to process")
        return ""
    
    all_trades = pd.concat(trades_list, ignore_index=True)
    logger.info(f"   {len(all_trades)} total trades")
    
    # PRE-CALCULATE indicators for all symbols to avoid recalculating per trade
    logger.info("📈 Pre-calculating indicators for all symbols...")
    indicators_cache = {}  # Cache[symbol] = {timestamp: indicators_dict}
    
    for sym in symbols_with_trades:
        symbol_df = symbol_results.get(sym, {}).get("data")
        weekly_df = weekly_data_cache.get(sym)
        
        if symbol_df is None or symbol_df.empty:
            continue
            
        try:
            # Calculate indicators for ALL rows of this symbol
            df_with_indicators = _calculate_all_indicators(
                symbol_df.copy(),
                weekly_df=weekly_df,
                weekly_nifty50_df=weekly_nifty50_indicators
            )
            
            # Store as dict keyed by timestamp for fast lookup
            sym_indicators = {}
            for idx in df_with_indicators.index:
                sym_indicators[pd.Timestamp(idx)] = df_with_indicators.loc[idx].to_dict()
            
            indicators_cache[sym] = sym_indicators
        except Exception:
            indicators_cache[sym] = {}
    
    logger.info(f"   ✓ Pre-calculated indicators for {len(indicators_cache)} symbols")
    
    # Build TV-style rows (Exit then Entry) with full indicators
    tv_rows = []
    
    for i, tr in all_trades.iterrows():
        trade_no = (i // 1) + 1  # Will be renumbered later
        symbol = tr.get("Symbol", "")
        entry_time = tr.get("entry_time", pd.NaT)
        exit_time = tr.get("exit_time", pd.NaT)
        entry_price = float(tr.get("entry_price", 0))
        exit_price = float(tr.get("exit_price", 0))
        qty = int(tr.get("entry_qty", 0))
        net_pnl = float(tr.get("net_pnl", 0))
        exit_reason = tr.get("exit_reason", "")
        
        # Get symbol data
        symbol_df = symbol_results.get(symbol, {}).get("data")
        if symbol_df is None or symbol_df.empty:
            continue
        
        # Lookup indicators from cache (fast)
        indicators = {}
        indicators_exit = {}
        
        try:
            df_idx = pd.to_datetime(symbol_df.index, errors="coerce")
            entry_ts = pd.Timestamp(entry_time)
            
            # Find closest timestamp <= entry_time in cached indicators
            sym_indicators = indicators_cache.get(symbol, {})
            valid_timestamps = [ts for ts in sym_indicators.keys() if ts < entry_ts]
            if valid_timestamps:
                closest_ts = max(valid_timestamps)
                indicators = sym_indicators.get(closest_ts, {})
            
            # Get indicators at exit time
            if pd.notna(exit_time):
                exit_ts = pd.Timestamp(exit_time)
                valid_timestamps_exit = [ts for ts in sym_indicators.keys() if ts < exit_ts]
                if valid_timestamps_exit:
                    closest_ts_exit = max(valid_timestamps_exit)
                    indicators_exit = sym_indicators.get(closest_ts_exit, {})
        except Exception:
            indicators = {}
            indicators_exit = {}
        
        # Calculate trade metrics
        is_open = pd.isna(exit_time) or exit_price == 0
        tv_pos_value = entry_price * qty if entry_price and qty else 0
        
        # Current price for open trades
        if is_open and not symbol_df.empty:
            current_price = float(symbol_df["close"].iloc[-1])
            net_pnl = (current_price - entry_price) * qty
        else:
            current_price = exit_price
        
        tv_net_pct = (net_pnl / tv_pos_value * 100) if tv_pos_value > 0 else 0
        
        # Run-up and Drawdown
        run_up_exit = 0.0
        drawdown_exit = 0.0
        
        try:
            if not symbol_df.empty and entry_price > 0:
                df_idx = pd.to_datetime(symbol_df.index, errors="coerce")
                entry_ts = pd.Timestamp(entry_time)
                exit_ts = pd.Timestamp(exit_time) if not is_open else df_idx[-1]
                
                mask = (df_idx >= entry_ts) & (df_idx <= exit_ts)
                close_prices = symbol_df.loc[mask, "close"].astype(float)
                
                if not close_prices.empty:
                    pnl_series = (close_prices - entry_price) * qty
                    run_up_exit = float(max(0.0, pnl_series.max()))
                    drawdown_exit = float(min(0.0, pnl_series.min()))
        except Exception:
            pass
        
        tv_run_pct = (run_up_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
        tv_dd_pct = (drawdown_exit / tv_pos_value * 100) if tv_pos_value > 0 else 0
        mae_pct = abs(tv_dd_pct)
        
        # Holding days
        holding_days = 0
        if pd.notna(entry_time):
            if is_open:
                exit_dt = pd.to_datetime(symbol_df.index[-1])
            else:
                exit_dt = pd.to_datetime(exit_time)
            entry_dt = pd.to_datetime(entry_time)
            holding_days = int((exit_dt - entry_dt).days)
        
        # Format dates
        entry_str = entry_time.strftime("%Y-%m-%d") if pd.notna(entry_time) else ""
        exit_str = exit_time.strftime("%Y-%m-%d") if pd.notna(exit_time) else ""
        
        # ATR metrics - use pre-calculated values from indicators cache at signal bar
        # Entry uses indicators (signal bar before entry), Exit uses indicators_exit (signal bar before exit)
        # This ensures ATR% matches Volatility(14) classification for each row
        atr_val_entry = ""
        atr_pct_val_entry = ""
        atr_val_exit = ""
        atr_pct_val_exit = ""
        
        if indicators:
            atr_val_raw = indicators.get("atr_14", "")
            atr_pct_raw = indicators.get("atr_pct_14", "")
            if atr_val_raw and not pd.isna(atr_val_raw):
                atr_val_entry = int(round(atr_val_raw))
            if atr_pct_raw and not pd.isna(atr_pct_raw):
                atr_pct_val_entry = round(atr_pct_raw, 2)
        
        if indicators_exit:
            atr_val_raw_exit = indicators_exit.get("atr_14", "")
            atr_pct_raw_exit = indicators_exit.get("atr_pct_14", "")
            if atr_val_raw_exit and not pd.isna(atr_val_raw_exit):
                atr_val_exit = int(round(atr_val_raw_exit))
            if atr_pct_raw_exit and not pd.isna(atr_pct_raw_exit):
                atr_pct_val_exit = round(atr_pct_raw_exit, 2)
        else:
            # Fallback to entry values if exit indicators not available
            atr_val_exit = atr_val_entry
            atr_pct_val_exit = atr_pct_val_entry
        
        # MAE_ATR and MFE_ATR - use entry ATR since these are trade metrics relative to entry
        mae_atr_val = round(mae_pct / atr_pct_val_entry, 2) if atr_pct_val_entry and isinstance(atr_pct_val_entry, (int, float)) and atr_pct_val_entry > 0 else ""
        mfe_atr_val = round(tv_run_pct / atr_pct_val_entry, 2) if atr_pct_val_entry and isinstance(atr_pct_val_entry, (int, float)) and atr_pct_val_entry > 0 else ""
        
        # Exit signal - handle consolidated exit reasons (e.g., "TP1+TP2+signal")
        if pd.isna(exit_time):
            exit_signal = "OPEN"
        elif exit_reason == "stop":
            exit_signal = "STOP"
        elif exit_reason in ("TP1", "TP2", "TP3"):
            exit_signal = exit_reason
        elif "+" in str(exit_reason):
            # Consolidated exit (e.g., "TP1+TP2+signal") - show as combined
            exit_signal = str(exit_reason).upper().replace("SIGNAL", "CLOSE")
        else:
            exit_signal = "CLOSE"
        
        net_pnl_int = int(net_pnl) if not pd.isna(net_pnl) else 0
        tv_pos_value_exit = current_price * qty if current_price and qty else 0
        
        # Exit row
        tv_rows.append({
            "Trade #": trade_no,
            "Symbol": symbol,
            "Type": "Exit long",
            "Date/Time": exit_str,
            "Signal": exit_signal,
            "Price INR": int(current_price) if current_price > 0 else "",
            "Position size (qty)": int(qty) if qty > 0 else "",
            "Position size (value)": int(tv_pos_value_exit) if tv_pos_value_exit > 0 else "",
            "Net P&L INR": net_pnl_int,
            "Net P&L %": round(tv_net_pct, 2),
            "Profitable": "Yes" if round(tv_net_pct, 2) > 0 else "No",
            "Run-up INR": int(run_up_exit) if run_up_exit > 0 else 0,
            "Run-up %": round(tv_run_pct, 2),
            "Drawdown INR": int(drawdown_exit) if drawdown_exit else None,
            "Drawdown %": round(tv_dd_pct, 2),
            "Holding days": holding_days,
            "ATR": atr_val_exit,
            "ATR %": atr_pct_val_exit,
            "MAE %": round(mae_pct, 2),
            "MAE_ATR": mae_atr_val,
            "MFE %": round(tv_run_pct, 2),
            "MFE_ATR": mfe_atr_val,
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
            "ADX (14)": round(indicators_exit.get("adx_14", indicators.get("adx_14", 0)), 2) if indicators_exit or indicators else "",
            "ADX (28)": round(indicators_exit.get("adx_28", indicators.get("adx_28", 0)), 2) if indicators_exit or indicators else "",
            "DI_Bullish (14)": str(indicators_exit.get("di_bullish_14", indicators.get("di_bullish_14", ""))) if indicators_exit or indicators else "",
            "DI_Bullish (28)": str(indicators_exit.get("di_bullish_28", indicators.get("di_bullish_28", ""))) if indicators_exit or indicators else "",
            "RSI (14)": round(indicators_exit.get("rsi_14", indicators.get("rsi_14", 50)), 2) if indicators_exit or indicators else "",
            "RSI (28)": round(indicators_exit.get("rsi_28", indicators.get("rsi_28", 50)), 2) if indicators_exit or indicators else "",
            "MACD_Bullish (12;26;9)": str(indicators_exit.get("macd_bullish_12_26_9", indicators.get("macd_bullish_12_26_9", ""))) if indicators_exit or indicators else "",
            "MACD_Bullish (24;52;18)": str(indicators_exit.get("macd_bullish_24_52_18", indicators.get("macd_bullish_24_52_18", ""))) if indicators_exit or indicators else "",
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
            "Bollinger_Band_Position (40;2)": indicators_exit.get("bb_position_40_2", indicators.get("bb_position_40_2", "")) if indicators_exit or indicators else "",
            "Weekly_BB_Position (20;2)": indicators_exit.get("Weekly_BB_Position (20;2)", indicators.get("Weekly_BB_Position (20;2)", "")) if indicators_exit or indicators else "",
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
            "Daily_CCI (20)": round(indicators_exit.get("Daily_CCI (20)", indicators.get("Daily_CCI (20)", 0)), 2) if indicators_exit or indicators else "",
            "Daily_MFI (20)": round(indicators_exit.get("Daily_MFI (20)", indicators.get("Daily_MFI (20)", 50)), 2) if indicators_exit or indicators else "",
            "Daily_CMF (20)": round(indicators_exit.get("Daily_CMF (20)", indicators.get("Daily_CMF (20)", 0)), 2) if indicators_exit or indicators else "",
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
        })
        
        # Entry row
        tv_rows.append({
            "Trade #": trade_no,
            "Symbol": symbol,
            "Type": "Entry long",
            "Date/Time": entry_str,
            "Signal": "LONG",
            "Price INR": int(entry_price) if entry_price > 0 else "",
            "Position size (qty)": int(qty) if qty > 0 else "",
            "Position size (value)": int(tv_pos_value) if tv_pos_value > 0 else "",
            "Net P&L INR": net_pnl_int,
            "Net P&L %": round(tv_net_pct, 2),
            "Profitable": "Yes" if round(tv_net_pct, 2) > 0 else "No",
            "Run-up INR": int(run_up_exit) if run_up_exit > 0 else 0,
            "Run-up %": round(tv_run_pct, 2),
            "Drawdown INR": int(drawdown_exit) if drawdown_exit else None,
            "Drawdown %": round(tv_dd_pct, 2),
            "Holding days": holding_days,
            "ATR": atr_val_entry,
            "ATR %": atr_pct_val_entry,
            "MAE %": round(mae_pct, 2),
            "MAE_ATR": mae_atr_val,
            "MFE %": round(tv_run_pct, 2),
            "MFE_ATR": mfe_atr_val,
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
            "Bollinger_Band_Position (40;2)": indicators.get("bb_position_40_2", "") if indicators else "",
            "Weekly_BB_Position (20;2)": indicators.get("Weekly_BB_Position (20;2)", "") if indicators else "",
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
            "Daily_CCI (20)": round(indicators.get("Daily_CCI (20)", 0), 2) if indicators else "",
            "Daily_MFI (20)": round(indicators.get("Daily_MFI (20)", 50), 2) if indicators else "",
            "Daily_CMF (20)": round(indicators.get("Daily_CMF (20)", 0), 2) if indicators else "",
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
        })
    
    # Build output DataFrame
    trades_df = pd.DataFrame(tv_rows)
    
    # Renumber trades sequentially
    trades_df = trades_df.reset_index(drop=True)
    trades_df["Trade #"] = (trades_df.index // 2) + 1
    
    # Define column order - grouped logically with daily and weekly side by side
    cols = [
        # === TRADE INFO ===
        "Trade #", "Symbol", "Type", "Date/Time", "Signal", "Price INR",
        "Position size (qty)", "Position size (value)", "Net P&L INR", "Net P&L %", "Profitable",
        "Run-up INR", "Run-up %", "Drawdown INR", "Drawdown %", "Holding days",
        # === RISK METRICS ===
        "ATR", "ATR %", "MAE %", "MAE_ATR", "MFE %", "MFE_ATR",
        # === VIX (Daily + Weekly) ===
        "India VIX", "Weekly_India_VIX",
        # === NIFTY INDEX ===
        "NIFTY200 > EMA 5", "NIFTY200 > EMA 20", "NIFTY200 > EMA 50", "NIFTY200 > EMA 100", "NIFTY200 > EMA 200",
        "Weekly_NIFTY50_Above_EMA5", "Weekly_NIFTY50_Above_EMA20", "Weekly_NIFTY50_Above_EMA50", "Weekly_NIFTY50_Above_EMA200",
        # === TREND (Daily + Weekly side by side) ===
        "Short-Trend (Aroon 25)", "Weekly_Short_Trend (Aroon 25)",
        "Medium-Trend (Aroon 50)", "Weekly_Medium_Trend (Aroon 50)",
        "Long-Trend (Aroon 100)", "Weekly_Long_Trend (Aroon 100)",
        # === VOLATILITY ===
        "Volatility (14)", "Volatility (28)",
        # === ADX (Daily + Weekly side by side) ===
        "ADX (14)", "Weekly_ADX (14)", "ADX (28)",
        "DI_Bullish (14)", "DI_Bullish (28)",
        # === RSI (Daily + Weekly side by side) ===
        "RSI (14)", "Weekly_RSI (14)", "RSI (28)",
        # === MACD (Daily + Weekly side by side) ===
        "MACD_Bullish (12;26;9)", "Weekly_MACD_Bullish", "MACD_Bullish (24;52;18)",
        # === CCI, MFI, CMF (Daily) ===
        "Daily_CCI (20)",
        "Daily_MFI (20)",
        "Daily_CMF (20)",
        # === PRICE VS EMAs (Daily + Weekly side by side) ===
        "Price_Above_EMA5", "Weekly_Above_EMA5",
        "Price_Above_EMA20", "Weekly_Above_EMA20",
        "Price_Above_EMA50", "Weekly_Above_EMA50",
        "Price_Above_EMA100",
        "Price_Above_EMA200", "Weekly_Above_EMA200",
        # === EMA CROSSOVERS ===
        "EMA5_Above_EMA20", "EMA20_Above_EMA50", "EMA50_Above_EMA100", "EMA50_Above_EMA200", "EMA100_Above_EMA200",
        # === BOLLINGER BANDS (Daily + Weekly side by side) ===
        "Bollinger_Band_Position (20;2)", "Weekly_BB_Position (20;2)", "Bollinger_Band_Position (40;2)",
        # === CHOPPINESS INDEX (Daily) ===
        "CHOP (20) Class", "CHOP (50) Class",
        # === VOLUME (Daily + Weekly side by side) ===
        "Daily_Volume_Above_MA20", "Weekly_Volume_Above_MA20",
        # === MFI, CMF (Daily) ===
        # Note: MFI and CMF have been moved to Daily from Weekly
        # === KER (Weekly only) ===
        "Weekly_KER (10)",
        # === CANDLE (Weekly only) ===
        "Weekly_Candle_Colour",
        "Weekly_Candlestick_Pattern",
        # === CHOP (Weekly only) ===
        "Weekly_CHOP (20) Class",
    ]
    
    trades_df = trades_df.reindex(columns=cols)
    
    # Clean up invalid weekly data where all True (missing data fallback)
    # These should be empty when data is unavailable, not all True
    weekly_bool_cols = ["Weekly_RSI (14)", "Weekly_MACD_Bullish", "Weekly_ADX (14)",
                        "Weekly_Above_EMA20", "Weekly_Above_EMA50", "Weekly_Above_EMA200",
                        "Weekly_NIFTY50_Above_EMA5", "Weekly_NIFTY50_Above_EMA20", "Weekly_NIFTY50_Above_EMA50", "Weekly_NIFTY50_Above_EMA200"]
    for col in weekly_bool_cols:
        if col in trades_df.columns:
            # If all non-empty values are 'True', likely default fallback - set to empty
            non_empty = trades_df[trades_df[col].notna()]
            if len(non_empty) > 0:
                true_count = (non_empty[col].astype(str) == 'True').sum()
                if true_count == len(non_empty):
                    trades_df[col] = ""
    
    # Write output
    output_path = os.path.join(run_dir, "consolidated_trades_MAX.csv")
    trades_df.to_csv(output_path, index=False)
    
    # Calculate and log portfolio-level summary metrics (consistent with fast_run_basket)
    # This uses weighted average for Avg P&L % to match fast_run and standard_run
    # NOTE: Uses all_trades directly for precise calculation, NOT truncated CSV values
    try:
        num_trades = len(all_trades)
        
        # Calculate from raw trades for precision (CSV has int-truncated Position size)
        total_pnl = float(all_trades['net_pnl'].sum())
        total_deployed = float((all_trades['entry_price'] * all_trades['entry_qty']).sum())
        
        if total_deployed > 0:
            weighted_avg_pnl_pct = (total_pnl / total_deployed) * 100
        else:
            weighted_avg_pnl_pct = 0.0
        
        # Win rate
        winning_trades = (all_trades['net_pnl'] > 0).sum()
        win_rate_pct = (winning_trades / num_trades * 100) if num_trades > 0 else 0.0
        
        # Profit factor
        gross_profit = all_trades[all_trades['net_pnl'] > 0]['net_pnl'].sum()
        gross_loss = abs(all_trades[all_trades['net_pnl'] < 0]['net_pnl'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
        
        logger.info(f"\n📊 Portfolio Summary (weighted metrics - consistent with fast_run_basket):")
        logger.info(f"   Total Trades: {num_trades}")
        logger.info(f"   Total Net P&L: {total_pnl:,.0f} INR")
        logger.info(f"   Total Deployed: {total_deployed:,.0f} INR")
        logger.info(f"   Avg P&L % per trade (weighted): {weighted_avg_pnl_pct:.2f}%")
        logger.info(f"   Win Rate: {win_rate_pct:.1f}%")
        logger.info(f"   Profit Factor: {profit_factor:.2f}")
    except Exception as e:
        logger.warning(f"   Could not compute portfolio summary: {e}")
    
    elapsed = time.time() - start_time
    logger.info(f"\n✅ Saved: {output_path}")
    logger.info(f"   {len(trades_df)} rows ({len(trades_df)//2} trades)")
    logger.info(f"⏱️  Total time: {elapsed:.1f}s")
    
    return output_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Fast runner that ONLY generates consolidated_trades_MAX.csv"
    )
    ap.add_argument("--strategy", required=True, help="Strategy name")
    ap.add_argument("--basket_file", required=True, help="Path to basket file")
    ap.add_argument("--interval", default="1d", help="Timeframe interval (default: 1d)")
    ap.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    
    args = ap.parse_args()
    
    run_fast_max_trades(
        basket_file=args.basket_file,
        strategy_name=args.strategy,
        interval=args.interval,
        workers=args.workers,
    )
