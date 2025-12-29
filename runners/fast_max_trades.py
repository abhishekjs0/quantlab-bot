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
from core.registry import make_strategy
from core.loaders import load_many_india, load_india_vix, load_nifty200
from core.report import make_run_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


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
    """Add india_vix column to DataFrame for VIX filter in strategies."""
    try:
        vix_df = load_india_vix()
        df = df.join(vix_df[['close']].rename(columns={'close': 'india_vix'}), how='left')
        df['india_vix'] = df['india_vix'].ffill().bfill()
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


def _calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate ALL indicators for consolidated file export."""
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
    
    # India VIX
    try:
        vix_df = load_india_vix()
        result_df = result_df.join(vix_df[['close']].rename(columns={'close': 'vix_value'}), how='left')
        result_df['vix_value'] = result_df['vix_value'].ffill().bfill()
        result_df['india_vix'] = result_df['vix_value']
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
            result_df[col] = True
    
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
    
    result_df['cci_20'] = CCI(high_arr, low_arr, close_arr, 20)
    
    # StochRSI variants
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
    
    # ========== VOLUME ==========
    result_df['mfi_20'] = MFI(high_arr, low_arr, close_arr, volume_arr, 20)
    result_df['cmf_20'] = CMF(high_arr, low_arr, close_arr, volume_arr, 20)
    
    # ========== KER ==========
    result_df['ker_10'] = kaufman_efficiency_ratio(close_arr, 10)
    
    # ========== CANDLE COLOUR ==========
    open_arr = df["open"].astype(float).values
    result_df['candle_colour'] = np.where(close_arr > open_arr, 'green', 
                                          np.where(close_arr < open_arr, 'red', 'doji'))
    
    # ========== CANDLESTICK PATTERNS ==========
    try:
        import talib
        
        bullish_patterns = ['cdl_hammer', 'cdl_inverted_hammer', 'cdl_engulfing_bullish', 
                           'cdl_morning_star', 'cdl_three_white_soldiers', 'cdl_piercing', 'cdl_dragonfly_doji']
        bearish_patterns = ['cdl_hanging_man', 'cdl_shooting_star', 'cdl_engulfing_bearish',
                           'cdl_evening_star', 'cdl_three_black_crows', 'cdl_dark_cloud', 'cdl_gravestone_doji']
        
        result_df['cdl_hammer'] = talib.CDLHAMMER(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_inverted_hammer'] = talib.CDLINVERTEDHAMMER(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_engulfing_bullish'] = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
        result_df['cdl_morning_star'] = talib.CDLMORNINGSTAR(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_three_white_soldiers'] = talib.CDL3WHITESOLDIERS(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_piercing'] = talib.CDLPIERCING(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_dragonfly_doji'] = talib.CDLDRAGONFLYDOJI(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_hanging_man'] = talib.CDLHANGINGMAN(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_shooting_star'] = talib.CDLSHOOTINGSTAR(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_engulfing_bearish'] = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
        result_df['cdl_evening_star'] = talib.CDLEVENINGSTAR(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_three_black_crows'] = talib.CDL3BLACKCROWS(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_dark_cloud'] = talib.CDLDARKCLOUDCOVER(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_gravestone_doji'] = talib.CDLGRAVESTONEDOJI(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_doji'] = talib.CDLDOJI(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_harami'] = talib.CDLHARAMI(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_spinning_top'] = talib.CDLSPINNINGTOP(open_arr, high_arr, low_arr, close_arr)
        result_df['cdl_marubozu'] = talib.CDLMARUBOZU(open_arr, high_arr, low_arr, close_arr)
        
        def get_pattern_name(row):
            for pat in bullish_patterns + bearish_patterns + ['cdl_doji', 'cdl_harami', 'cdl_spinning_top', 'cdl_marubozu']:
                if row.get(pat, 0) != 0:
                    return pat.replace('cdl_', '').upper()
            return ''
        
        result_df['candlestick_pattern'] = result_df.apply(get_pattern_name, axis=1)
    except ImportError:
        result_df['candlestick_pattern'] = ''
    except Exception:
        result_df['candlestick_pattern'] = ''
    
    # ========== CHOPPINESS INDEX ==========
    def choppiness_index(high, low, close, length):
        import math
        n = len(close)
        chop = np.full(n, np.nan)
        
        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        tr[0] = high[0] - low[0]
        
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
    chop_50 = choppiness_index(high_arr, low_arr, close_arr, 50)
    
    result_df['chop_20_class'] = classify_chop(chop_20)
    result_df['chop_50_class'] = classify_chop(chop_50)
    
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
        inst_csv = os.path.join("data", "api-scrip-master-detailed.csv")
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
    
    trades_list = []
    for sym, result in symbol_results.items():
        trades = result.get("trades")
        if trades is not None and not trades.empty:
            t = trades.copy()
            t["Symbol"] = sym
            trades_list.append(t)
    
    if not trades_list:
        logger.warning("⚠️ No trades to process")
        return ""
    
    all_trades = pd.concat(trades_list, ignore_index=True)
    logger.info(f"   {len(all_trades)} total trades")
    
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
        
        # Calculate indicators at entry time
        try:
            df_idx = pd.to_datetime(symbol_df.index, errors="coerce")
            entry_ts = pd.Timestamp(entry_time)
            
            # Get data UP TO BUT NOT INCLUDING entry (decision point)
            entry_data = symbol_df.loc[df_idx < entry_ts].copy()
            
            if not entry_data.empty:
                df_with_indicators = _calculate_all_indicators(entry_data)
                indicators = df_with_indicators.iloc[-1].to_dict()
            else:
                indicators = {}
            
            # Calculate indicators at exit time
            indicators_exit = {}
            if pd.notna(exit_time):
                exit_ts = pd.Timestamp(exit_time)
                exit_data = symbol_df.loc[df_idx < exit_ts].copy()
                if not exit_data.empty:
                    df_with_indicators_exit = _calculate_all_indicators(exit_data)
                    indicators_exit = df_with_indicators_exit.iloc[-1].to_dict()
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
        
        # ATR metrics
        from utils import ATR
        try:
            high = entry_data["high"].astype(float).values if not entry_data.empty else np.array([])
            low = entry_data["low"].astype(float).values if not entry_data.empty else np.array([])
            close = entry_data["close"].astype(float).values if not entry_data.empty else np.array([])
            
            if len(close) > 14:
                atr_values = ATR(high, low, close, 14)
                atr_val = int(round(atr_values[-1])) if len(atr_values) > 0 else ""
                atr_pct_val = round((atr_values[-1] / close[-1]) * 100, 2) if len(atr_values) > 0 and close[-1] > 0 else ""
            else:
                atr_val = ""
                atr_pct_val = ""
        except Exception:
            atr_val = ""
            atr_pct_val = ""
        
        # MAE_ATR and MFE_ATR
        mae_atr_val = round(mae_pct / atr_pct_val, 2) if atr_pct_val and isinstance(atr_pct_val, (int, float)) and atr_pct_val > 0 else ""
        mfe_atr_val = round(tv_run_pct / atr_pct_val, 2) if atr_pct_val and isinstance(atr_pct_val, (int, float)) and atr_pct_val > 0 else ""
        
        # Exit signal
        if pd.isna(exit_time):
            exit_signal = "OPEN"
        elif exit_reason == "stop":
            exit_signal = "STOP"
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
            "ATR": atr_val,
            "ATR %": atr_pct_val,
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
            "CCI (20)": round(indicators_exit.get("cci_20", indicators.get("cci_20", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (14;5;3;3)": round(indicators_exit.get("stoch_rsi_k_14_5_3_3", indicators.get("stoch_rsi_k_14_5_3_3", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (14;10;5;5)": round(indicators_exit.get("stoch_rsi_k_14_10_5_5", indicators.get("stoch_rsi_k_14_10_5_5", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (14;14;3;3)": round(indicators_exit.get("stoch_rsi_k_14_14_3_3", indicators.get("stoch_rsi_k_14_14_3_3", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (28;20;10;10)": round(indicators_exit.get("stoch_rsi_k_28_20_10_10", indicators.get("stoch_rsi_k_28_20_10_10", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (28;28;3;3)": round(indicators_exit.get("stoch_rsi_k_28_28_3_3", indicators.get("stoch_rsi_k_28_28_3_3", 0)), 2) if indicators_exit or indicators else "",
            "StochRSI_K (28;5;3;3)": round(indicators_exit.get("stoch_rsi_k_28_5_3_3", indicators.get("stoch_rsi_k_28_5_3_3", 0)), 2) if indicators_exit or indicators else "",
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
            "MFI (20)": round(indicators_exit.get("mfi_20", indicators.get("mfi_20", 50)), 2) if indicators_exit or indicators else "",
            "CMF (20)": round(indicators_exit.get("cmf_20", indicators.get("cmf_20", 0)), 2) if indicators_exit or indicators else "",
            "KER (10)": round(indicators_exit.get("ker_10", indicators.get("ker_10", 0)), 3) if indicators_exit or indicators else "",
            "Candle Colour": indicators_exit.get("candle_colour", indicators.get("candle_colour", "")) if indicators_exit or indicators else "",
            "Candlestick Pattern": indicators_exit.get("candlestick_pattern", indicators.get("candlestick_pattern", "")) if indicators_exit or indicators else "",
            "CHOP (20) Class": indicators_exit.get("chop_20_class", indicators.get("chop_20_class", "")) if indicators_exit or indicators else "",
            "CHOP (50) Class": indicators_exit.get("chop_50_class", indicators.get("chop_50_class", "")) if indicators_exit or indicators else "",
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
            "ATR": atr_val,
            "ATR %": atr_pct_val,
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
            "CCI (20)": round(indicators.get("cci_20", 0), 2) if indicators else "",
            "StochRSI_K (14;5;3;3)": round(indicators.get("stoch_rsi_k_14_5_3_3", 0), 2) if indicators else "",
            "StochRSI_K (14;10;5;5)": round(indicators.get("stoch_rsi_k_14_10_5_5", 0), 2) if indicators else "",
            "StochRSI_K (14;14;3;3)": round(indicators.get("stoch_rsi_k_14_14_3_3", 0), 2) if indicators else "",
            "StochRSI_K (28;20;10;10)": round(indicators.get("stoch_rsi_k_28_20_10_10", 0), 2) if indicators else "",
            "StochRSI_K (28;28;3;3)": round(indicators.get("stoch_rsi_k_28_28_3_3", 0), 2) if indicators else "",
            "StochRSI_K (28;5;3;3)": round(indicators.get("stoch_rsi_k_28_5_3_3", 0), 2) if indicators else "",
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
            "MFI (20)": round(indicators.get("mfi_20", 50), 2) if indicators else "",
            "CMF (20)": round(indicators.get("cmf_20", 0), 2) if indicators else "",
            "KER (10)": round(indicators.get("ker_10", 0), 3) if indicators else "",
            "Candle Colour": indicators.get("candle_colour", "") if indicators else "",
            "Candlestick Pattern": indicators.get("candlestick_pattern", "") if indicators else "",
            "CHOP (20) Class": indicators.get("chop_20_class", "") if indicators else "",
            "CHOP (50) Class": indicators.get("chop_50_class", "") if indicators else "",
        })
    
    # Build output DataFrame
    trades_df = pd.DataFrame(tv_rows)
    
    # Renumber trades sequentially
    trades_df = trades_df.reset_index(drop=True)
    trades_df["Trade #"] = (trades_df.index // 2) + 1
    
    # Define column order (exact match to standard_run_basket.py)
    cols = [
        "Trade #", "Symbol", "Type", "Date/Time", "Signal", "Price INR",
        "Position size (qty)", "Position size (value)", "Net P&L INR", "Net P&L %", "Profitable",
        "Run-up INR", "Run-up %", "Drawdown INR", "Drawdown %", "Holding days",
        "ATR", "ATR %", "MAE %", "MAE_ATR", "MFE %", "MFE_ATR",
        "India VIX", "NIFTY200 > EMA 5", "NIFTY200 > EMA 20", "NIFTY200 > EMA 50",
        "NIFTY200 > EMA 100", "NIFTY200 > EMA 200",
        "Short-Trend (Aroon 25)", "Medium-Trend (Aroon 50)", "Long-Trend (Aroon 100)",
        "Volatility (14)", "Volatility (28)",
        "ADX (14)", "ADX (28)", "DI_Bullish (14)", "DI_Bullish (28)",
        "RSI (14)", "RSI (28)", "MACD_Bullish (12;26;9)", "MACD_Bullish (24;52;18)", "CCI (20)",
        "StochRSI_K (14;5;3;3)", "StochRSI_K (14;10;5;5)", "StochRSI_K (14;14;3;3)",
        "StochRSI_K (28;20;10;10)", "StochRSI_K (28;28;3;3)", "StochRSI_K (28;5;3;3)",
        "Price_Above_EMA5", "Price_Above_EMA20", "Price_Above_EMA50", "Price_Above_EMA100", "Price_Above_EMA200",
        "EMA5_Above_EMA20", "EMA20_Above_EMA50", "EMA50_Above_EMA100", "EMA50_Above_EMA200", "EMA100_Above_EMA200",
        "Bollinger_Band_Position (20;2)", "Bollinger_Band_Position (40;2)",
        "MFI (20)", "CMF (20)", "KER (10)",
        "Candle Colour", "Candlestick Pattern", "CHOP (20) Class", "CHOP (50) Class",
    ]
    
    trades_df = trades_df.reindex(columns=cols)
    
    # Write output
    output_path = os.path.join(run_dir, "consolidated_trades_MAX.csv")
    trades_df.to_csv(output_path, index=False)
    
    elapsed = time.time() - start_time
    logger.info(f"✅ Saved: {output_path}")
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
