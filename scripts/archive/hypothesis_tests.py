# Hypothesis Tests Archive
# Combined from multiple test_hypothesis_*.py files on 2026-01-08
# Original files: test_hypothesis_20pct_sl.py, test_hypothesis_all_baskets.py, test_hypothesis_bb15sd.py,
# test_hypothesis_bb2sd.py, test_hypothesis_corrected.py, test_hypothesis_corrected_v2.py,
# test_hypothesis_final_3baskets.py, test_hypothesis_multi_variant.py, test_hypothesis_properly_corrected.py,
# test_hypothesis_top5_distribution.py, test_hypothesis_v2_refined.py, test_hypothesis_v3_unlimited.py



# ========== FROM: test_hypothesis_20pct_sl.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - 20% Fixed SL
=============================================
Entry: Next Monday at open

Exit Conditions (whichever hits first, checking WEEKLY candles):
1. STOP LOSS: Fixed at -20% from entry price
2. TAKE PROFIT: When any subsequent weekly candle's high >= 20 SMA (BB middle)

Signal Detection (Proper Indexing):
- Position i: Weekly candle is GREEN (close > open)
- Position i: Opens BELOW Bollinger Band 1 SD
- Position i: Body BIGGER than candle at position i-1
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0  # Fixed stop loss at -20%


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly (Mon-Fri)"""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify signals with proper indexing:
    - i: current green candle (signal)
    - i-1: previous candle (for body comparison)
    - i-2: candle BEFORE previous (not used for 20% SL)
    """
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    # START FROM INDEX 2 (consistent with previous logic)
    for i in range(2, len(weekly_df)):
        curr = weekly_df.iloc[i]        # Signal candle (green)
        prev = weekly_df.iloc[i - 1]    # Previous candle (for body comparison)
        
        # Condition 1: Current candle is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below 1 SD Bollinger Band
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous candle
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "bb_middle": weekly_df.iloc[i]["bb_middle"],  # TP: 20 SMA
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the Monday after the given date"""
    days_ahead = 0 - date.weekday()  # Monday is 0
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_20pct_sl(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Exit Logic (check WEEKLY candles only):
    1. SL: Fixed at -20% from entry price
    2. TP: When weekly high >= 20 SMA
    Exit at Friday close of that week
    """
    signal_date = signal_row["signal_date"]
    signal_index = signal_row["signal_index"]
    tp_level = signal_row["bb_middle"]      # 20 SMA
    
    # Entry: next Monday
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    # Calculate fixed SL price (20% below entry)
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    # Get subsequent weekly candles (after the signal)
    subsequent_weekly = weekly_df.iloc[signal_index+1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    # Check each subsequent weekly candle
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        
        # Check SL FIRST: if weekly low <= -20% price, hit SL
        if week["low"] <= sl_price:
            exit_price = sl_price
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        # Check TP: if weekly high >= TP level, hit TP
        if week["high"] >= tp_level:
            exit_price = tp_level
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            exit_reason = "TP_HIT"
            break
    
    # If neither hit, exit at end of data
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        friday_date = last_week["date"] + timedelta(days=(4 - last_week["date"].weekday()))
        exit_date = friday_date
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    # Ensure exit_date doesn't go beyond available data
    if exit_date > df["date"].max():
        exit_date = df["date"].max()
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_price,
        "take_profit": tp_level,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_20pct_sl(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - 20% FIXED SL")
    print(f"{'─'*130}")
    print(f"\nSignal Detection:")
    print(f"  • Position i: Weekly candle is GREEN (close > open)")
    print(f"  • Position i: Opens BELOW Bollinger Band 1 SD")
    print(f"  • Position i: Body BIGGER than candle at position i-1")
    print(f"\nEntry: Next Monday (after signal week) at open")
    print(f"\nExit (checking WEEKLY candles, starting from i+1):")
    print(f"  • STOP LOSS: Fixed at -20% from entry price")
    print(f"  • TAKE PROFIT: When weekly high >= 20 SMA (BB middle)")
    print(f"  • Exit at Friday close of the week that triggered exit")
    print(f"  • Transaction Cost: 0.37% total")
    
    # Test on 3 baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*130}\n")
    
    # Summary table
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r['median_return']:.2f}",
            "Best %": f"{r['best_trade']:.2f}",
            "Worst %": f"{r['worst_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Detailed analysis for each basket
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*130}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*130}\n")
            
            print(f"📊 Key Metrics:")
            print(f"  Total Return: {r['total_return']:.2f}%")
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Avg Return/Trade: {r['avg_return']:.2f}%")
            print(f"  Avg Holding Days: {r['avg_days']:.1f}")
            
            print(f"\n📋 Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\n📈 Top 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\n📉 Bottom 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            # Save detailed results
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_20pct_sl.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Overall verdict
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_all_baskets.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - Multi-Variant Testing (All Baskets)
===================================================================
Tests all combinations on LARGE, MID, and SMALL baskets
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import glob
from typing import Dict, List, Tuple, Optional
from itertools import product

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0

MA_TYPES = ["SMA", "EMA"]
MA_PERIODS = [10, 20, 50, 100]
SD_LEVELS = [1.0, 1.5, 2.0]

BASKETS = [
    ("large", "data/baskets/basket_large.txt"),
    ("mid", "data/baskets/basket_mid.txt"),
    ("small", "data/baskets/basket_small.txt"),
]


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].dt.strftime("%Y-%W")
    
    weekly = df.groupby("year_week", sort=False).agg({
        "date": ["first", "last"],
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    
    weekly.columns = ["week_start", "week_end", "open", "high", "low", "close", "volume"]
    weekly = weekly.reset_index()
    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_ma(prices: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type == "SMA":
        return prices.rolling(window=period).mean()
    else:
        return prices.ewm(span=period, adjust=False).mean()


def calculate_bb_lower(prices: pd.Series, period: int, std_dev: float) -> pd.Series:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    return sma - (std * std_dev)


def add_indicators(weekly_df: pd.DataFrame, ma_period: int, ma_type: str, sd_level: float) -> pd.DataFrame:
    weekly_df = weekly_df.copy()
    weekly_df["ma"] = calculate_ma(weekly_df["close"], ma_period, ma_type)
    weekly_df["bb_lower"] = calculate_bb_lower(weekly_df["close"], ma_period, sd_level)
    return weekly_df


def identify_signals(weekly_df: pd.DataFrame, ma_period: int) -> pd.DataFrame:
    min_periods = max(2, ma_period)
    if len(weekly_df) < min_periods + 5:
        return pd.DataFrame()
    
    signals = []
    
    for i in range(min_periods, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        if pd.isna(curr["bb_lower"]) or pd.isna(curr["ma"]):
            continue
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < curr["bb_lower"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["week_start"],
            "signal_week_end": curr["week_end"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    signal_index = signal_row["signal_index"]
    signal_week_end = signal_row["signal_week_end"]
    
    entry_candidates = df[df["date"] > signal_week_end].head(1)
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    entry_week_idx = None
    for idx in range(signal_index + 1, len(weekly_df)):
        week = weekly_df.iloc[idx]
        if week["week_start"] <= entry_date <= week["week_end"]:
            entry_week_idx = idx
            break
    
    if entry_week_idx is None:
        return None
    
    subsequent_weekly = weekly_df.iloc[entry_week_idx + 1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        tp_level = week["ma"]
        
        if pd.isna(tp_level):
            continue
        
        sl_hit = week["low"] <= sl_price
        tp_hit = week["high"] >= tp_level
        
        if sl_hit and tp_hit:
            dist_to_sl = abs(week["open"] - sl_price)
            dist_to_tp = abs(week["open"] - tp_level)
            
            if dist_to_sl < dist_to_tp:
                exit_price = sl_price
                exit_date = week["week_end"]
                hit_sl = True
                exit_reason = "SL_HIT"
            else:
                exit_price = tp_level
                exit_date = week["week_end"]
                exit_reason = "TP_HIT"
            break
        elif sl_hit:
            exit_price = sl_price
            exit_date = week["week_end"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        elif tp_hit:
            exit_price = tp_level
            exit_date = week["week_end"]
            exit_reason = "TP_HIT"
            break
    
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        exit_date = last_week["week_end"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_variant(symbols: List[str], symbol_data: Dict, ma_type: str, ma_period: int, sd_level: float) -> Dict:
    all_trades = []
    
    for symbol in symbols:
        if symbol not in symbol_data:
            continue
        
        df, weekly_df = symbol_data[symbol]
        weekly_with_indicators = add_indicators(weekly_df.copy(), ma_period, ma_type, sd_level)
        
        signals_df = identify_signals(weekly_with_indicators, ma_period)
        if len(signals_df) == 0:
            continue
        
        last_exit_date = None
        
        for _, signal_row in signals_df.iterrows():
            if last_exit_date is not None and signal_row["signal_date"] < last_exit_date:
                continue
            
            trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_with_indicators)
            if trade:
                all_trades.append(trade)
                last_exit_date = trade["exit_date"]  # FIXED: Use actual exit date
    
    if not all_trades:
        return {
            "ma_type": ma_type,
            "ma_period": ma_period,
            "sd_level": sd_level,
            "trades": 0,
            "win_rate": 0,
            "avg_days": 0,
            "avg_return": 0,
            "median_return": 0,
            "profit_factor": 0,
        }
    
    trades_df = pd.DataFrame(all_trades)
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    gross_profits = trades_df[trades_df["net_return_pct"] > 0]["net_return_pct"].sum()
    gross_losses = abs(trades_df[trades_df["net_return_pct"] < 0]["net_return_pct"].sum())
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else float('inf')
    
    return {
        "ma_type": ma_type,
        "ma_period": ma_period,
        "sd_level": sd_level,
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_days": trades_df["days_held"].mean(),
        "avg_return": trades_df["net_return_pct"].mean(),
        "median_return": trades_df["net_return_pct"].median(),
        "total_return": trades_df["net_return_pct"].sum(),
        "profit_factor": profit_factor,
    }


def analyze_basket(basket_name: str, basket_path: str) -> pd.DataFrame:
    """Analyze all variants for a single basket"""
    symbols = load_basket(basket_path)
    
    symbol_data = {}
    for symbol in symbols:
        df = load_ohlc_data(symbol)
        if df is not None and len(df) >= 100:
            weekly_df = get_weekly_candles(df)
            if len(weekly_df) >= 25:
                symbol_data[symbol] = (df, weekly_df)
    
    results = []
    
    for ma_type, ma_period, sd_level in product(MA_TYPES, MA_PERIODS, SD_LEVELS):
        result = analyze_variant(symbols, symbol_data, ma_type, ma_period, sd_level)
        result["basket"] = basket_name
        results.append(result)
    
    return pd.DataFrame(results)


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - ALL BASKETS MULTI-VARIANT TESTING")
    print(f"{'═'*120}")
    print(f"\nTesting: {len(MA_TYPES) * len(MA_PERIODS) * len(SD_LEVELS)} variants × 3 baskets = 72 total tests")
    
    all_results = []
    
    for basket_name, basket_path in BASKETS:
        print(f"\n📊 Analyzing {basket_name.upper()} basket...")
        results_df = analyze_basket(basket_name, basket_path)
        all_results.append(results_df)
        print(f"  ✅ Completed {len(results_df)} variants")
    
    combined_df = pd.concat(all_results, ignore_index=True)
    
    # Print results by basket
    for basket_name, _, in BASKETS:
        print(f"\n{'═'*120}")
        print(f"RESULTS: {basket_name.upper()} BASKET - SORTED BY PROFIT FACTOR")
        print(f"{'═'*120}\n")
        
        basket_df = combined_df[combined_df["basket"] == basket_name].sort_values("profit_factor", ascending=False)
        
        display_df = basket_df.copy()
        display_df["Variant"] = display_df["ma_type"] + " " + display_df["ma_period"].astype(str) + " / " + display_df["sd_level"].astype(str) + "SD"
        display_df["Win %"] = display_df["win_rate"].round(1)
        display_df["Days"] = display_df["avg_days"].round(1)
        display_df["Avg %"] = display_df["avg_return"].round(2)
        display_df["Med %"] = display_df["median_return"].round(2)
        display_df["Tot %"] = display_df["total_return"].round(0)
        display_df["PF"] = display_df["profit_factor"].apply(lambda x: f"{x:.2f}" if x < float('inf') else "∞")
        
        print(display_df[["Variant", "trades", "Win %", "Days", "Avg %", "Med %", "Tot %", "PF"]].to_string(index=False))
    
    # Cross-basket comparison for top variants
    print(f"\n{'═'*120}")
    print(f"CROSS-BASKET COMPARISON: TOP 5 VARIANTS BY AVERAGE PROFIT FACTOR")
    print(f"{'═'*120}\n")
    
    # Calculate average PF across baskets
    pivot = combined_df.pivot_table(
        index=["ma_type", "ma_period", "sd_level"],
        columns="basket",
        values=["profit_factor", "trades", "avg_return", "median_return"],
        aggfunc="first"
    )
    
    # Flatten column names
    pivot.columns = [f"{col[1]}_{col[0]}" for col in pivot.columns]
    pivot = pivot.reset_index()
    
    # Calculate average PF
    pivot["avg_pf"] = (pivot["large_profit_factor"] + pivot["mid_profit_factor"] + pivot["small_profit_factor"]) / 3
    pivot = pivot.sort_values("avg_pf", ascending=False)
    
    print(f"{'Variant':<20} | {'LARGE':^30} | {'MID':^30} | {'SMALL':^30} | {'Avg PF':>7}")
    print(f"{'':20} | {'Trades':>6} {'Med%':>7} {'PF':>7} {'':>8} | {'Trades':>6} {'Med%':>7} {'PF':>7} {'':>8} | {'Trades':>6} {'Med%':>7} {'PF':>7} {'':>8} |")
    print(f"{'-'*20}-+-{'-'*30}-+-{'-'*30}-+-{'-'*30}-+-{'-'*7}")
    
    for _, row in pivot.head(10).iterrows():
        variant = f"{row['ma_type']} {int(row['ma_period'])} / {row['sd_level']}SD"
        
        def fmt_pf(x):
            return f"{x:.2f}" if x < float('inf') else "∞"
        
        large_trades = int(row.get("large_trades", 0))
        large_med = row.get("large_median_return", 0)
        large_pf = row.get("large_profit_factor", 0)
        
        mid_trades = int(row.get("mid_trades", 0))
        mid_med = row.get("mid_median_return", 0)
        mid_pf = row.get("mid_profit_factor", 0)
        
        small_trades = int(row.get("small_trades", 0))
        small_med = row.get("small_median_return", 0)
        small_pf = row.get("small_profit_factor", 0)
        
        print(f"{variant:<20} | {large_trades:>6} {large_med:>+7.1f} {fmt_pf(large_pf):>7} {'':>8} | {mid_trades:>6} {mid_med:>+7.1f} {fmt_pf(mid_pf):>7} {'':>8} | {small_trades:>6} {small_med:>+7.1f} {fmt_pf(small_pf):>7} {'':>8} | {row['avg_pf']:>7.2f}")
    
    # Save results
    output_path = "reports/hypothesis_all_baskets_results.csv"
    Path("reports").mkdir(exist_ok=True)
    combined_df.to_csv(output_path, index=False)
    print(f"\n💾 Saved: {output_path}")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_bb15sd.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - BB 1.5 SD with 20% Fixed SL
===========================================================
Entry: Next Monday at open

Signal Conditions:
- Weekly candle is GREEN (close > open)
- Opens BELOW Bollinger Band 1.5 SD (instead of 1.0 SD)
- Body BIGGER than previous candle's body

Exit Conditions (whichever hits first, checking WEEKLY candles):
1. STOP LOSS: Fixed at -20% from entry price
2. TAKE PROFIT: When weekly high >= 20 SMA (BB middle)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0  # Fixed stop loss at -20%
BB_STD_DEV = 1.5  # Use 1.5 SD instead of 1.0


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly (Mon-Fri)"""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify signals with proper indexing:
    - i: current green candle (signal)
    - i-1: previous candle (for body comparison)
    
    Entry condition: Opens below BB 1.5 SD
    """
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    upper_bb_15, _, lower_bb_15 = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=BB_STD_DEV)
    
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_15sd_below"] = lower_bb_15
    
    signals = []
    
    # START FROM INDEX 2 (consistent with previous logic)
    for i in range(2, len(weekly_df)):
        curr = weekly_df.iloc[i]        # Signal candle (green)
        prev = weekly_df.iloc[i - 1]    # Previous candle (for body comparison)
        
        # Condition 1: Current candle is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below 1.5 SD Bollinger Band
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_15sd_below"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous candle
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "bb_middle": weekly_df.iloc[i]["bb_middle"],  # TP: 20 SMA
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the Monday after the given date"""
    days_ahead = 0 - date.weekday()  # Monday is 0
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_20pct_sl(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Exit Logic (check WEEKLY candles only):
    1. SL: Fixed at -20% from entry price
    2. TP: When weekly high >= 20 SMA
    Exit at Friday close of that week
    """
    signal_date = signal_row["signal_date"]
    signal_index = signal_row["signal_index"]
    tp_level = signal_row["bb_middle"]      # 20 SMA
    
    # Entry: next Monday
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    # Calculate fixed SL price (20% below entry)
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    # Get subsequent weekly candles (after the signal)
    subsequent_weekly = weekly_df.iloc[signal_index+1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    # Check each subsequent weekly candle
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        
        # Check SL FIRST: if weekly low <= -20% price, hit SL
        if week["low"] <= sl_price:
            exit_price = sl_price
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        # Check TP: if weekly high >= TP level, hit TP
        if week["high"] >= tp_level:
            exit_price = tp_level
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            exit_reason = "TP_HIT"
            break
    
    # If neither hit, exit at end of data
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        friday_date = last_week["date"] + timedelta(days=(4 - last_week["date"].weekday()))
        exit_date = friday_date
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    # Ensure exit_date doesn't go beyond available data
    if exit_date > df["date"].max():
        exit_date = df["date"].max()
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_price,
        "take_profit": tp_level,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_20pct_sl(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - BB 1.5 SD + 20% FIXED SL")
    print(f"{'─'*130}")
    print(f"\nSignal Detection:")
    print(f"  • Position i: Weekly candle is GREEN (close > open)")
    print(f"  • Position i: Opens BELOW Bollinger Band 1.5 SD (wider than 1.0 SD)")
    print(f"  • Position i: Body BIGGER than candle at position i-1")
    print(f"\nEntry: Next Monday (after signal week) at open")
    print(f"\nExit (checking WEEKLY candles, starting from i+1):")
    print(f"  • STOP LOSS: Fixed at -20% from entry price")
    print(f"  • TAKE PROFIT: When weekly high >= 20 SMA (BB middle)")
    print(f"  • Exit at Friday close of the week that triggered exit")
    print(f"  • Transaction Cost: 0.37% total")
    
    # Test on 3 baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*130}\n")
    
    # Summary table
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r['median_return']:.2f}",
            "Best %": f"{r['best_trade']:.2f}",
            "Worst %": f"{r['worst_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Detailed analysis for each basket
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*130}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*130}\n")
            
            print(f"📊 Key Metrics:")
            print(f"  Total Return: {r['total_return']:.2f}%")
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Avg Return/Trade: {r['avg_return']:.2f}%")
            print(f"  Avg Holding Days: {r['avg_days']:.1f}")
            
            print(f"\n📋 Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\n📈 Top 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\n📉 Bottom 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            # Save detailed results
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_bb15sd.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Overall verdict
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_bb2sd.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - BB 2.0 SD with 20% Fixed SL
===========================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0
BB_STD_DEV = 2.0  # Use 2.0 SD


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    _, middle_bb, _ = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    _, _, lower_bb_2sd = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=BB_STD_DEV)
    
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_2sd_below"] = lower_bb_2sd
    
    signals = []
    
    for i in range(2, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_2sd_below"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["date"],
            "bb_middle": weekly_df.iloc[i]["bb_middle"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    signal_date = signal_row["signal_date"]
    signal_index = signal_row["signal_index"]
    tp_level = signal_row["bb_middle"]
    
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    subsequent_weekly = weekly_df.iloc[signal_index+1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        
        if week["low"] <= sl_price:
            exit_price = sl_price
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        if week["high"] >= tp_level:
            exit_price = tp_level
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            exit_reason = "TP_HIT"
            break
    
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        friday_date = last_week["date"] + timedelta(days=(4 - last_week["date"].weekday()))
        exit_date = friday_date
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    if exit_date > df["date"].max():
        exit_date = df["date"].max()
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_price,
        "take_profit": tp_level,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {"basket": basket_name, "symbols": len(symbols), "trades": 0, "win_rate": 0, "avg_return": 0, "total_return": 0}
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - BB 2.0 SD + 20% FIXED SL")
    print(f"{'─'*130}")
    
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS (BB 2.0 SD)")
    print(f"{'='*130}\n")
    
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r.get('median_return', 0):.2f}",
            "SL Hit %": f"{r.get('sl_hit_pct', 0):.1f}",
            "Avg Days": f"{r.get('avg_days', 0):.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_bb2sd.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_corrected_v2.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - BB 1.5 SD with 20% Fixed SL (CORRECTED)
======================================================================
Entry: Next Monday at open

Signal Conditions:
- Weekly candle is GREEN (close > open)
- Opens BELOW Bollinger Band 1.5 SD
- Body BIGGER than previous candle's body

Exit Conditions (whichever hits first, checking WEEKLY candles):
1. STOP LOSS: Fixed at -20% from entry price
2. TAKE PROFIT: When weekly high >= DYNAMIC 20 SMA (recalculated each week)

FIXES APPLIED:
1. TP uses DYNAMIC 20 SMA (recalculated for each subsequent week)
2. Intraweek SL/TP ambiguity handled (compare which level is closer to open)
3. Exit checking starts from week AFTER entry (not signal week)
4. Friday calculation handles non-Monday week starts
5. No side effects on DataFrames (uses .copy())
6. Overlap protection (no new trade if previous still open)
7. Explicit NaN checks on BB values
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0
BB_STD_DEV = 1.5
BB_PERIOD = 20


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly (Mon-Fri) with proper year-week handling"""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    # Create a unique year-week identifier that handles year boundaries
    df["year_week"] = df["date"].dt.strftime("%Y-%W")
    
    weekly = df.groupby("year_week", sort=False).agg({
        "date": ["first", "last"],  # Get both first and last date
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    
    # Flatten column names
    weekly.columns = ["week_start", "week_end", "open", "high", "low", "close", "volume"]
    weekly = weekly.reset_index()
    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    # Calculate dynamic BB values for each week
    weekly["bb_middle"] = weekly["close"].rolling(window=BB_PERIOD).mean()
    std = weekly["close"].rolling(window=BB_PERIOD).std()
    weekly["bb_lower_15sd"] = weekly["bb_middle"] - (std * BB_STD_DEV)
    
    return weekly


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify signals with proper indexing and NaN checks:
    - i: current green candle (signal)
    - i-1: previous candle (for body comparison)
    """
    if len(weekly_df) < BB_PERIOD + 5:
        return pd.DataFrame()
    
    signals = []
    
    # Start from BB_PERIOD to ensure BB values are valid
    for i in range(max(2, BB_PERIOD), len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        # Skip if BB values are NaN
        if pd.isna(curr["bb_lower_15sd"]) or pd.isna(curr["bb_middle"]):
            continue
        
        # Condition 1: Current candle is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below 1.5 SD Bollinger Band
        opens_below_bb = curr["open"] < curr["bb_lower_15sd"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous candle
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["week_start"],
            "signal_week_end": curr["week_end"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def get_friday_of_week(week_end_date: pd.Timestamp) -> pd.Timestamp:
    """Get the Friday of the week (handles non-Friday week ends due to holidays)"""
    # week_end is the last trading day of the week, which should be Friday or earlier
    return week_end_date


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Exit Logic with DYNAMIC TP:
    1. SL: Fixed at -20% from entry price
    2. TP: When weekly high >= DYNAMIC 20 SMA (recalculated each week)
    3. Intraweek conflict: If both hit, use price distance from open to determine order
    """
    signal_index = signal_row["signal_index"]
    signal_week_end = signal_row["signal_week_end"]
    
    # Entry: first trading day AFTER signal week ends
    entry_candidates = df[df["date"] > signal_week_end].head(1)
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    # Calculate fixed SL price (20% below entry)
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    # Find which week the entry falls into
    entry_week_idx = None
    for idx in range(signal_index + 1, len(weekly_df)):
        week = weekly_df.iloc[idx]
        if week["week_start"] <= entry_date <= week["week_end"]:
            entry_week_idx = idx
            break
    
    if entry_week_idx is None:
        return None
    
    # Start checking from NEXT week after entry (not entry week)
    # Entry week is partially in, so we skip it
    subsequent_weekly = weekly_df.iloc[entry_week_idx + 1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    # Check each subsequent weekly candle
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        
        # Get DYNAMIC TP level (20 SMA at this week)
        tp_level = week["bb_middle"]
        if pd.isna(tp_level):
            continue
        
        sl_hit = week["low"] <= sl_price
        tp_hit = week["high"] >= tp_level
        
        if sl_hit and tp_hit:
            # Both hit in same week - determine order by price distance from week open
            # If open is closer to SL, likely SL hit first
            # If open is closer to TP, likely TP hit first
            dist_to_sl = abs(week["open"] - sl_price)
            dist_to_tp = abs(week["open"] - tp_level)
            
            if dist_to_sl < dist_to_tp:
                # SL was closer, assume it hit first
                exit_price = sl_price
                exit_date = get_friday_of_week(week["week_end"])
                hit_sl = True
                exit_reason = "SL_HIT"
            else:
                # TP was closer, assume it hit first
                exit_price = tp_level
                exit_date = get_friday_of_week(week["week_end"])
                exit_reason = "TP_HIT"
            break
        elif sl_hit:
            exit_price = sl_price
            exit_date = get_friday_of_week(week["week_end"])
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        elif tp_hit:
            exit_price = tp_level
            exit_date = get_friday_of_week(week["week_end"])
            exit_reason = "TP_HIT"
            break
    
    # If neither hit, exit at end of data
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        exit_date = get_friday_of_week(last_week["week_end"])
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    # Ensure exit_date doesn't go beyond available data
    if exit_date > df["date"].max():
        exit_date = df["date"].max()
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_row["signal_date"],
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_price,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < BB_PERIOD + 5:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    last_exit_date = None
    
    for _, signal_row in signals_df.iterrows():
        # Overlap protection: skip if previous trade hasn't exited yet
        if last_exit_date is not None and signal_row["signal_date"] < last_exit_date:
            continue
        
        trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
            last_exit_date = trade["exit_date"]
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - BB 1.5 SD + 20% FIXED SL (CORRECTED)")
    print(f"{'─'*130}")
    print(f"\nFIXES APPLIED:")
    print(f"  ✅ TP uses DYNAMIC 20 SMA (recalculated each week)")
    print(f"  ✅ Intraweek SL/TP conflict resolved by distance from open")
    print(f"  ✅ Exit checking starts from week AFTER entry")
    print(f"  ✅ Overlap protection (no new trade if previous still open)")
    print(f"  ✅ Explicit NaN checks on BB values")
    print(f"\nSignal Detection:")
    print(f"  • Weekly candle is GREEN (close > open)")
    print(f"  • Opens BELOW Bollinger Band 1.5 SD")
    print(f"  • Body BIGGER than previous candle")
    print(f"\nEntry: First trading day after signal week at open")
    print(f"\nExit:")
    print(f"  • STOP LOSS: Fixed at -20% from entry price")
    print(f"  • TAKE PROFIT: When weekly high >= DYNAMIC 20 SMA")
    print(f"  • Transaction Cost: 0.37% total")
    
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*130}\n")
    
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r['median_return']:.2f}",
            "Best %": f"{r['best_trade']:.2f}",
            "Worst %": f"{r['worst_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*130}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*130}\n")
            
            print(f"📊 Key Metrics:")
            print(f"  Total Return: {r['total_return']:.2f}%")
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Avg Return/Trade: {r['avg_return']:.2f}%")
            print(f"  Avg Holding Days: {r['avg_days']:.1f}")
            
            print(f"\n📋 Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\n📈 Top 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\n📉 Bottom 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_corrected_v2.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_corrected.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - Corrected Exit Logic
====================================================
Entry: Next Monday at open

Exit Conditions (whichever hits first):
1. STOP LOSS: When any subsequent candle's low breaches the low of the candle 
             PRIOR to the green signal candle
2. TAKE PROFIT: When any subsequent WEEK's high breaches 20 SMA (upside)

Test across 3 basket sizes: large, mid, small
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Identify signals and return prior candle's low for SL"""
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "prev_candle_low": prev["low"],  # SL level: low of candle PRIOR to signal
            "bb_middle": weekly_df.iloc[i]["bb_middle"],  # TP level: 20 SMA
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_corrected_exit(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Exit Logic:
    - SL: When any subsequent daily candle's low <= prev_candle_low
    - TP: When any subsequent weekly high >= 20 SMA
    - Whichever hits first
    """
    signal_date = signal_row["signal_date"]
    sl_level = signal_row["prev_candle_low"]  # Low of candle prior to signal
    tp_level = signal_row["bb_middle"]  # 20 SMA level
    
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    future_df = df[df["date"] >= entry_date].copy()
    if len(future_df) < 2:
        return None
    
    # Build weekly mapping for future dates
    future_weekly = weekly_df[weekly_df["date"] >= entry_date].copy()
    if len(future_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    # Check both daily (for SL) and weekly (for TP)
    for idx in future_df.index:
        row = df.loc[idx]
        
        # Check SL: daily candle low breaches SL level
        if row["low"] <= sl_level:
            exit_price = sl_level
            exit_date = row["date"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
    
    # If SL not hit, check TP (weekly high breaches 20 SMA)
    if exit_price is None:
        for idx in future_weekly.index:
            row = future_weekly.loc[idx]
            
            # Check TP: weekly high >= 20 SMA
            if row["high"] >= tp_level:
                # Exit at the SMA level (the TP)
                exit_price = tp_level
                # Use the Friday close date of this week
                exit_date = row["date"] + timedelta(days=(4 - row["date"].weekday()))
                exit_reason = "TP_HIT"
                break
    
    # If neither hit, exit at end of data
    if exit_price is None:
        exit_price = future_df.iloc[-1]["close"]
        exit_date = future_df.iloc[-1]["date"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_level,
        "take_profit": tp_level,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_corrected_exit(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket and return metrics"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - 3 BASKET COMPARISON (Corrected Exit Logic)")
    print(f"{'─'*130}")
    print(f"\nSignal Conditions:")
    print(f"  • Weekly candle is GREEN (close > open)")
    print(f"  • Opens BELOW Bollinger Band 1 SD")
    print(f"  • Body BIGGER than previous candle")
    print(f"\nEntry: Next Monday at open")
    print(f"Stop Loss: Breached when any subsequent daily candle's low <= low of candle PRIOR to signal")
    print(f"Take Profit: Breached when any subsequent weekly high >= 20 SMA (BB middle)")
    print(f"Transaction Cost: 0.37% total")
    
    # Test on 3 baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*130}\n")
    
    # Summary table
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r['median_return']:.2f}",
            "Best %": f"{r['best_trade']:.2f}",
            "Worst %": f"{r['worst_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Detailed analysis for each basket
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*130}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*130}\n")
            
            print(f"📊 Key Metrics:")
            print(f"  Total Return: {r['total_return']:.2f}%")
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Avg Return/Trade: {r['avg_return']:.2f}%")
            print(f"  Avg Holding Days: {r['avg_days']:.1f}")
            
            print(f"\n📋 Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\n📈 Top 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\n📉 Bottom 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            # Save detailed results
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_corrected.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Overall verdict
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_final_3baskets.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - Final Version
=============================================
Proper Exit Logic:
- Exit when price touches 20 SMA (daily low <= SMA)
- For weekly data assumption: exit at Friday close if that week's high > 20 SMA
- Stop Loss: Previous candle's low
- No arbitrary time limits

Test across 3 basket sizes
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_date": curr["date"],
            "prev_low": prev["low"],
            "bb_middle": weekly_df.iloc[i]["bb_middle"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def get_friday_of_week(date: pd.Timestamp) -> pd.Timestamp:
    """Get Friday (end of week) of the given date's week"""
    days_ahead = 4 - date.weekday()  # Friday is 4
    if days_ahead < 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_weekly_exit(signal_row: Dict, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """
    Exit Logic:
    1. Daily: Exit when low <= 20 SMA
    2. Weekly assumption: Exit at Friday close if that week's high > 20 SMA
    3. SL: Previous candle's low
    """
    signal_date = signal_row["signal_date"]
    entry_sl = signal_row["prev_low"]
    target_sma = signal_row["bb_middle"]
    
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    entry_week = entry_date.isocalendar().week
    entry_year = entry_date.isocalendar().year
    
    future_df = df[df["date"] >= entry_date].copy()
    if len(future_df) < 2:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    current_week = entry_week
    current_year = entry_year
    
    for idx in future_df.index:
        row = df.loc[idx]
        row_week = row["date"].isocalendar().week
        row_year = row["date"].isocalendar().year
        
        # Check if we moved to a new week
        if row_week != current_week or row_year != current_year:
            # Check previous week for weekly exit condition
            # Get the last day (Friday) of the previous week
            prev_week_df = future_df[
                (future_df["date"].dt.isocalendar().week == current_week) &
                (future_df["date"].dt.isocalendar().year == current_year)
            ]
            
            if len(prev_week_df) > 0:
                prev_week_high = prev_week_df["high"].max()
                prev_week_friday = prev_week_df.iloc[-1]
                
                # If that week's high > 20 SMA, exit at Friday close
                if prev_week_high >= target_sma:
                    exit_price = prev_week_friday["close"]
                    exit_date = prev_week_friday["date"]
                    exit_reason = "WEEKLY_HIGH_SMA"
                    break
            
            current_week = row_week
            current_year = row_year
        
        # Check daily condition: if low touches SMA, exit immediately
        if row["low"] <= target_sma:
            exit_price = target_sma
            exit_date = row["date"]
            exit_reason = "DAILY_TOUCH_SMA"
            break
        
        # Check SL on any day
        if row["low"] <= entry_sl:
            exit_price = entry_sl
            exit_date = row["date"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
    
    # If no exit found, exit at end of data
    if exit_price is None:
        exit_price = future_df.iloc[-1]["close"]
        exit_date = future_df.iloc[-1]["date"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": entry_sl,
        "target_sma": target_sma,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_weekly_exit(signal_row.to_dict(), df, symbol)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket and return metrics"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - 3 BASKET COMPARISON")
    print(f"{'─'*120}")
    print(f"\nEntry: Next Monday at open")
    print(f"Exit:")
    print(f"  • Daily: Exit when low touches 20 SMA")
    print(f"  • Weekly assumption: Exit Friday close if week's high > 20 SMA")
    print(f"Stop Loss: Previous candle's low")
    print(f"Transaction Cost: 0.37% total")
    
    # Test on 3 baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*120}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*120}\n")
    
    # Summary table
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Return %": f"{r['avg_return']:.2f}",
            "Total Return %": f"{r['total_return']:.2f}",
            "Best Trade %": f"{r['best_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Hold Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Detailed analysis for each basket
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*120}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*120}\n")
            
            print(f"Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\nTop 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\nWorst 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            # Save detailed results
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_results.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Overall verdict
    print(f"\n{'='*120}")
    print(f"SUMMARY")
    print(f"{'='*120}\n")
    
    for r in results:
        status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
        print(f"{r['basket'].upper():12} {r['symbols']:3} symbols: {r['trades']:5} trades → {status} {r['total_return']:+8.2f}%")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_multi_variant.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - Multi-Variant Testing
=====================================================
Tests all combinations of:
- MA Types: SMA, EMA
- MA Periods: 10, 20, 50, 100
- BB SD Levels: 1.0, 1.5, 2.0

Reports: Win Rate, Holding Days, Avg Return, Profit Factor
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import glob
from typing import Dict, List, Tuple, Optional
from itertools import product

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0
RSI_PERIOD = 14
RSI_MAX = 60  # Daily RSI on signal bar must be below this

# Variants to test
MA_TYPES = ["SMA", "EMA"]
MA_PERIODS = [10, 20, 50, 100]
SD_LEVELS = [1.0, 1.5, 2.0]


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly"""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].dt.strftime("%Y-%W")
    
    weekly = df.groupby("year_week", sort=False).agg({
        "date": ["first", "last"],
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    
    weekly.columns = ["week_start", "week_end", "open", "high", "low", "close", "volume"]
    weekly = weekly.reset_index()
    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_ma(prices: pd.Series, period: int, ma_type: str) -> pd.Series:
    """Calculate SMA or EMA"""
    if ma_type == "SMA":
        return prices.rolling(window=period).mean()
    else:  # EMA
        return prices.ewm(span=period, adjust=False).mean()


def calculate_bb_lower(prices: pd.Series, period: int, std_dev: float) -> pd.Series:
    """Calculate lower Bollinger Band using SMA for std calculation"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    return sma - (std * std_dev)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI for a price series."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_indicators(weekly_df: pd.DataFrame, ma_period: int, ma_type: str, sd_level: float) -> pd.DataFrame:
    """Add MA, BB, and Weekly RSI indicators to weekly dataframe"""
    weekly_df = weekly_df.copy()
    
    # Calculate the MA (for TP target)
    weekly_df["ma"] = calculate_ma(weekly_df["close"], ma_period, ma_type)
    
    # Calculate BB lower band (for entry signal)
    weekly_df["bb_lower"] = calculate_bb_lower(weekly_df["close"], ma_period, sd_level)
    
    # Calculate Weekly RSI for signal filtering
    weekly_df["weekly_rsi"] = calculate_rsi(weekly_df["close"], RSI_PERIOD)
    
    return weekly_df


def identify_signals(weekly_df: pd.DataFrame, ma_period: int) -> pd.DataFrame:
    """Identify signals with Weekly RSI filter."""
    min_periods = max(2, ma_period)
    if len(weekly_df) < min_periods + 5:
        return pd.DataFrame()
    
    signals = []
    
    for i in range(min_periods, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        if pd.isna(curr["bb_lower"]) or pd.isna(curr["ma"]):
            continue
        
        # Condition 1: Green candle
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below BB lower
        opens_below_bb = curr["open"] < curr["bb_lower"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        # Condition 4: Weekly RSI filter on signal bar
        weekly_rsi = curr.get("weekly_rsi", np.nan)
        if pd.isna(weekly_rsi) or weekly_rsi >= RSI_MAX:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["week_start"],
            "signal_week_end": curr["week_end"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """Calculate trade with dynamic TP"""
    signal_index = signal_row["signal_index"]
    signal_week_end = signal_row["signal_week_end"]
    
    # Entry: first trading day after signal week
    entry_candidates = df[df["date"] > signal_week_end].head(1)
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    # Find entry week index
    entry_week_idx = None
    for idx in range(signal_index + 1, len(weekly_df)):
        week = weekly_df.iloc[idx]
        if week["week_start"] <= entry_date <= week["week_end"]:
            entry_week_idx = idx
            break
    
    if entry_week_idx is None:
        return None
    
    subsequent_weekly = weekly_df.iloc[entry_week_idx + 1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        tp_level = week["ma"]
        
        if pd.isna(tp_level):
            continue
        
        sl_hit = week["low"] <= sl_price
        tp_hit = week["high"] >= tp_level
        
        if sl_hit and tp_hit:
            dist_to_sl = abs(week["open"] - sl_price)
            dist_to_tp = abs(week["open"] - tp_level)
            
            if dist_to_sl < dist_to_tp:
                exit_price = sl_price
                exit_date = week["week_end"]
                hit_sl = True
                exit_reason = "SL_HIT"
            else:
                exit_price = tp_level
                exit_date = week["week_end"]
                exit_reason = "TP_HIT"
            break
        elif sl_hit:
            exit_price = sl_price
            exit_date = week["week_end"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        elif tp_hit:
            exit_price = tp_level
            exit_date = week["week_end"]
            exit_reason = "TP_HIT"
            break
    
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        exit_date = last_week["week_end"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_variant(symbols: List[str], symbol_data: Dict, ma_type: str, ma_period: int, sd_level: float) -> Dict:
    """Analyze a single variant with Weekly RSI filter."""
    all_trades = []
    
    for symbol in symbols:
        if symbol not in symbol_data:
            continue
        
        df, weekly_df = symbol_data[symbol]
        
        # Add indicators for this variant (includes weekly RSI)
        weekly_with_indicators = add_indicators(weekly_df.copy(), ma_period, ma_type, sd_level)
        
        signals_df = identify_signals(weekly_with_indicators, ma_period)
        if len(signals_df) == 0:
            continue
        
        last_exit_date = None
        
        for _, signal_row in signals_df.iterrows():
            if last_exit_date is not None and signal_row["signal_date"] < last_exit_date:
                continue
            
            trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_with_indicators)
            if trade:
                all_trades.append(trade)
                last_exit_date = trade["exit_date"]
    
    if not all_trades:
        return {
            "ma_type": ma_type,
            "ma_period": ma_period,
            "sd_level": sd_level,
            "trades": 0,
            "win_rate": 0,
            "avg_days": 0,
            "avg_return": 0,
            "profit_factor": 0,
        }
    
    trades_df = pd.DataFrame(all_trades)
    total_trades = len(trades_df)
    winning_trades = len(trades_df[trades_df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    # Calculate profit factor
    gross_profits = trades_df[trades_df["net_return_pct"] > 0]["net_return_pct"].sum()
    gross_losses = abs(trades_df[trades_df["net_return_pct"] < 0]["net_return_pct"].sum())
    profit_factor = (gross_profits / gross_losses) if gross_losses > 0 else float('inf')
    
    return {
        "ma_type": ma_type,
        "ma_period": ma_period,
        "sd_level": sd_level,
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_days": trades_df["days_held"].mean(),
        "avg_return": trades_df["net_return_pct"].mean(),
        "total_return": trades_df["net_return_pct"].sum(),
        "profit_factor": profit_factor,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - MULTI-VARIANT TESTING")
    print(f"{'═'*100}")
    print(f"\nTesting combinations:")
    print(f"  • MA Types: {MA_TYPES}")
    print(f"  • MA Periods: {MA_PERIODS}")
    print(f"  • SD Levels: {SD_LEVELS}")
    print(f"  • Total variants: {len(MA_TYPES) * len(MA_PERIODS) * len(SD_LEVELS)}")
    print(f"\nFixed parameters:")
    print(f"  • Stop Loss: 20% fixed")
    print(f"  • Transaction Cost: 0.37%")
    print(f"  • RSI Filter: Weekly RSI({RSI_PERIOD}) < {RSI_MAX} on signal bar")
    print(f"  • Basket: LARGE")
    
    # Load symbols and preprocess data once
    print(f"\n📂 Loading data...")
    symbols = load_basket("data/baskets/basket_large.txt")
    
    symbol_data = {}
    for symbol in symbols:
        df = load_ohlc_data(symbol)
        if df is not None and len(df) >= 100:
            weekly_df = get_weekly_candles(df)
            if len(weekly_df) >= 25:
                symbol_data[symbol] = (df, weekly_df)
    
    print(f"  Loaded {len(symbol_data)} symbols with sufficient data")
    
    # Test all variants
    results = []
    total_variants = len(MA_TYPES) * len(MA_PERIODS) * len(SD_LEVELS)
    
    print(f"\n🧪 Testing {total_variants} variants...")
    
    variant_count = 0
    for ma_type, ma_period, sd_level in product(MA_TYPES, MA_PERIODS, SD_LEVELS):
        variant_count += 1
        result = analyze_variant(symbols, symbol_data, ma_type, ma_period, sd_level)
        results.append(result)
        
        if variant_count % 6 == 0:
            print(f"  [{variant_count}/{total_variants}] completed...")
    
    # Create results DataFrame
    results_df = pd.DataFrame(results)
    
    # Sort by profit factor
    results_df = results_df.sort_values("profit_factor", ascending=False)
    
    print(f"\n{'═'*100}")
    print(f"RESULTS SORTED BY PROFIT FACTOR")
    print(f"{'═'*100}\n")
    
    # Format for display
    display_df = results_df.copy()
    display_df["Variant"] = display_df["ma_type"] + " " + display_df["ma_period"].astype(str) + " / " + display_df["sd_level"].astype(str) + "SD"
    display_df["Win %"] = display_df["win_rate"].round(1)
    display_df["Days"] = display_df["avg_days"].round(1)
    display_df["Avg Ret %"] = display_df["avg_return"].round(2)
    display_df["Total Ret %"] = display_df["total_return"].round(1)
    display_df["PF"] = display_df["profit_factor"].apply(lambda x: f"{x:.2f}" if x < float('inf') else "∞")
    
    print(display_df[["Variant", "trades", "Win %", "Days", "Avg Ret %", "Total Ret %", "PF"]].to_string(index=False))
    
    # Group by SD level
    print(f"\n{'═'*100}")
    print(f"BREAKDOWN BY SD LEVEL")
    print(f"{'═'*100}")
    
    for sd in SD_LEVELS:
        print(f"\n📊 SD = {sd}")
        sd_df = results_df[results_df["sd_level"] == sd].sort_values("profit_factor", ascending=False)
        
        for _, row in sd_df.iterrows():
            pf_str = f"{row['profit_factor']:.2f}" if row['profit_factor'] < float('inf') else "∞"
            print(f"  {row['ma_type']:3} {row['ma_period']:3} | {row['trades']:4} trades | {row['win_rate']:5.1f}% win | {row['avg_days']:5.1f} days | {row['avg_return']:+6.2f}% avg | PF: {pf_str}")
    
    # Top 5 best variants
    print(f"\n{'═'*100}")
    print(f"🏆 TOP 5 VARIANTS BY PROFIT FACTOR")
    print(f"{'═'*100}\n")
    
    top5 = results_df.head(5)
    for i, (_, row) in enumerate(top5.iterrows(), 1):
        pf_str = f"{row['profit_factor']:.2f}" if row['profit_factor'] < float('inf') else "∞"
        print(f"#{i}: {row['ma_type']} {int(row['ma_period'])} / {row['sd_level']}SD")
        print(f"    Trades: {int(row['trades'])} | Win Rate: {row['win_rate']:.1f}% | Avg Days: {row['avg_days']:.1f}")
        print(f"    Avg Return: {row['avg_return']:.2f}% | Total Return: {row['total_return']:.1f}%")
        print(f"    Profit Factor: {pf_str}")
        print()
    
    # Save results
    output_path = "reports/hypothesis_multi_variant_results.csv"
    Path("reports").mkdir(exist_ok=True)
    results_df.to_csv(output_path, index=False)
    print(f"💾 Saved: {output_path}")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_properly_corrected.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Strategy - Properly Corrected
==================================================
Entry: Next Monday at open

Exit Conditions (whichever hits first, checking WEEKLY candles):
1. STOP LOSS: When any subsequent weekly candle's low <= 
               the low of the candle BEFORE the green signal candle (i-2)
2. TAKE PROFIT: When any subsequent weekly candle's high >= 20 SMA (BB middle)

Proper signal detection:
- Signal at index i (green candle)
- Compare body with i-1 (previous candle)
- SL level is i-2 (candle before previous)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily to weekly (Mon-Fri)"""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify signals with CORRECT indexing:
    - i: current green candle (signal)
    - i-1: previous candle (for body comparison)
    - i-2: candle BEFORE previous (for SL level)
    """
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    # START FROM INDEX 2 (need i-2 for SL)
    for i in range(2, len(weekly_df)):
        curr = weekly_df.iloc[i]        # Signal candle (green)
        prev = weekly_df.iloc[i - 1]    # Previous candle (for body comparison)
        prev_prev = weekly_df.iloc[i - 2]  # Candle BEFORE previous (for SL)
        
        # Condition 1: Current candle is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below 1 SD Bollinger Band
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous candle
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "prev_prev_low": prev_prev["low"],  # SL: low of candle i-2
            "bb_middle": weekly_df.iloc[i]["bb_middle"],  # TP: 20 SMA
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the Monday after the given date"""
    days_ahead = 0 - date.weekday()  # Monday is 0
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_weekly_sl_tp(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Exit Logic (check WEEKLY candles only):
    1. SL: When weekly low <= prev_prev_low (low of i-2)
    2. TP: When weekly high >= 20 SMA
    Exit at Friday close of that week
    """
    signal_date = signal_row["signal_date"]
    signal_index = signal_row["signal_index"]
    sl_level = signal_row["prev_prev_low"]  # Low of candle i-2
    tp_level = signal_row["bb_middle"]      # 20 SMA
    
    # Entry: next Monday
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    # Get subsequent weekly candles (after the signal)
    # Signal is at signal_index, so we check weeks from signal_index+1 onwards
    subsequent_weekly = weekly_df.iloc[signal_index+1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    # Check each subsequent weekly candle
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        
        # Check SL FIRST: if weekly low <= SL level, hit SL
        if week["low"] <= sl_level:
            exit_price = sl_level
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        # Check TP: if weekly high >= TP level, hit TP
        if week["high"] >= tp_level:
            exit_price = tp_level
            # Exit at Friday close of this week
            friday_date = week["date"] + timedelta(days=(4 - week["date"].weekday()))
            exit_date = friday_date
            exit_reason = "TP_HIT"
            break
    
    # If neither hit, exit at end of data
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        friday_date = last_week["date"] + timedelta(days=(4 - last_week["date"].weekday()))
        exit_date = friday_date
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    # Ensure exit_date doesn't go beyond available data
    if exit_date > df["date"].max():
        exit_date = df["date"].max()
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": sl_level,
        "take_profit": tp_level,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_weekly_sl_tp(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze a basket"""
    print(f"\n  📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    all_trades = []
    
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % max(1, len(symbols)//5) == 0:
            print(f"    [{i+1}/{len(symbols)}] processed...")
    
    if not all_trades:
        return {
            "basket": basket_name,
            "symbols": len(symbols),
            "trades": 0,
            "win_rate": 0,
            "avg_return": 0,
            "total_return": 0,
        }
    
    df = pd.DataFrame(all_trades)
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "basket": basket_name,
        "symbols": len(symbols),
        "trades": total_trades,
        "win_rate": win_rate,
        "avg_return": df["net_return_pct"].mean(),
        "total_return": df["net_return_pct"].sum(),
        "median_return": df["net_return_pct"].median(),
        "best_trade": df["net_return_pct"].max(),
        "worst_trade": df["net_return_pct"].min(),
        "sl_hit_pct": (len(df[df["hit_stop_loss"]]) / total_trades * 100),
        "avg_days": df["days_held"].mean(),
        "df": df,
    }


def main():
    print(f"\n🔬 WEEKLY GREEN CANDLE STRATEGY - PROPERLY CORRECTED")
    print(f"{'─'*130}")
    print(f"\nSignal Detection (Proper Indexing):")
    print(f"  • Position i: Weekly candle is GREEN (close > open)")
    print(f"  • Position i: Opens BELOW Bollinger Band 1 SD")
    print(f"  • Position i: Body BIGGER than candle at position i-1")
    print(f"\nEntry: Next Monday (after signal week) at open")
    print(f"\nExit (checking WEEKLY candles, starting from i+1):")
    print(f"  • STOP LOSS: When weekly low <= low of candle at position i-2")
    print(f"  • TAKE PROFIT: When weekly high >= 20 SMA (BB middle)")
    print(f"  • Exit at Friday close of the week that triggered exit")
    print(f"  • Transaction Cost: 0.37% total")
    
    # Test on 3 baskets
    baskets = [
        ("large", "data/baskets/basket_large.txt"),
        ("mid", "data/baskets/basket_mid.txt"),
        ("small", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    for basket_name, basket_path in baskets:
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
    
    print(f"\n{'='*130}")
    print(f"COMPARISON ACROSS BASKETS")
    print(f"{'='*130}\n")
    
    # Summary table
    summary_data = []
    for r in results:
        summary_data.append({
            "Basket": r["basket"].upper(),
            "Symbols": r["symbols"],
            "Trades": r["trades"],
            "Win Rate %": f"{r['win_rate']:.1f}",
            "Avg Ret %": f"{r['avg_return']:.2f}",
            "Total Ret %": f"{r['total_return']:.2f}",
            "Median %": f"{r['median_return']:.2f}",
            "Best %": f"{r['best_trade']:.2f}",
            "Worst %": f"{r['worst_trade']:.2f}",
            "SL Hit %": f"{r['sl_hit_pct']:.1f}",
            "Avg Days": f"{r['avg_days']:.1f}",
        })
    
    summary_df = pd.DataFrame(summary_data)
    print(summary_df.to_string(index=False))
    
    # Detailed analysis for each basket
    for r in results:
        if r["trades"] > 0:
            df = r["df"]
            print(f"\n{'='*130}")
            print(f"DETAILED ANALYSIS: {r['basket'].upper()} BASKET ({r['symbols']} symbols, {r['trades']} trades)")
            print(f"{'='*130}\n")
            
            print(f"📊 Key Metrics:")
            print(f"  Total Return: {r['total_return']:.2f}%")
            print(f"  Win Rate: {r['win_rate']:.1f}%")
            print(f"  Avg Return/Trade: {r['avg_return']:.2f}%")
            print(f"  Avg Holding Days: {r['avg_days']:.1f}")
            
            print(f"\n📋 Exit Reason Distribution:")
            print(df["exit_reason"].value_counts().to_string())
            
            print(f"\n📈 Top 5 Symbols:")
            top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
            top.columns = ['Trades', 'Avg %', 'Total %']
            print(top.sort_values("Total %", ascending=False).head(5).to_string())
            
            print(f"\n📉 Bottom 5 Symbols:")
            print(top.sort_values("Total %", ascending=True).head(5).to_string())
            
            # Save detailed results
            output_path = f"reports/hypothesis_weekly_green_{r['basket']}_final.csv"
            Path("reports").mkdir(exist_ok=True)
            df.to_csv(output_path, index=False)
            print(f"\n💾 Saved: {output_path}")
    
    # Overall verdict
    print(f"\n{'='*130}")
    print(f"FINAL SUMMARY")
    print(f"{'='*130}\n")
    
    for r in results:
        if r["trades"] > 0:
            status = "✅ PROFITABLE" if r["total_return"] > 0 else "❌ NOT PROFITABLE"
            print(f"{r['basket'].upper():10} | {r['symbols']:3} symbols | {r['trades']:5} trades | {status:17} | {r['total_return']:+8.2f}% return | {r['win_rate']:5.1f}% win rate")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_top5_distribution.py ==========

#!/usr/bin/env python3
"""
Top 5 Variants - Detailed Return Distribution Analysis
=======================================================
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
TRANSACTION_COST_PCT = 0.37
FIXED_SL_PCT = 20.0

# Top 5 variants to analyze in detail
TOP_VARIANTS = [
    ("SMA", 100, 2.0),
    ("EMA", 100, 2.0),
    ("EMA", 20, 2.0),
    ("SMA", 20, 2.0),
    ("SMA", 100, 1.0),
]


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year_week"] = df["date"].dt.strftime("%Y-%W")
    
    weekly = df.groupby("year_week", sort=False).agg({
        "date": ["first", "last"],
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    })
    
    weekly.columns = ["week_start", "week_end", "open", "high", "low", "close", "volume"]
    weekly = weekly.reset_index()
    weekly = weekly.sort_values("week_start").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_ma(prices: pd.Series, period: int, ma_type: str) -> pd.Series:
    if ma_type == "SMA":
        return prices.rolling(window=period).mean()
    else:
        return prices.ewm(span=period, adjust=False).mean()


def calculate_bb_lower(prices: pd.Series, period: int, std_dev: float) -> pd.Series:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    return sma - (std * std_dev)


def add_indicators(weekly_df: pd.DataFrame, ma_period: int, ma_type: str, sd_level: float) -> pd.DataFrame:
    weekly_df = weekly_df.copy()
    weekly_df["ma"] = calculate_ma(weekly_df["close"], ma_period, ma_type)
    weekly_df["bb_lower"] = calculate_bb_lower(weekly_df["close"], ma_period, sd_level)
    return weekly_df


def identify_signals(weekly_df: pd.DataFrame, ma_period: int) -> pd.DataFrame:
    min_periods = max(2, ma_period)
    if len(weekly_df) < min_periods + 5:
        return pd.DataFrame()
    
    signals = []
    
    for i in range(min_periods, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        if pd.isna(curr["bb_lower"]) or pd.isna(curr["ma"]):
            continue
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < curr["bb_lower"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_index": i,
            "signal_date": curr["week_start"],
            "signal_week_end": curr["week_end"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def calculate_trade(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    signal_index = signal_row["signal_index"]
    signal_week_end = signal_row["signal_week_end"]
    
    entry_candidates = df[df["date"] > signal_week_end].head(1)
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    sl_price = entry_price * (1 - FIXED_SL_PCT / 100)
    
    entry_week_idx = None
    for idx in range(signal_index + 1, len(weekly_df)):
        week = weekly_df.iloc[idx]
        if week["week_start"] <= entry_date <= week["week_end"]:
            entry_week_idx = idx
            break
    
    if entry_week_idx is None:
        return None
    
    subsequent_weekly = weekly_df.iloc[entry_week_idx + 1:].copy()
    if len(subsequent_weekly) == 0:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in subsequent_weekly.index:
        week = weekly_df.loc[idx]
        tp_level = week["ma"]
        
        if pd.isna(tp_level):
            continue
        
        sl_hit = week["low"] <= sl_price
        tp_hit = week["high"] >= tp_level
        
        if sl_hit and tp_hit:
            dist_to_sl = abs(week["open"] - sl_price)
            dist_to_tp = abs(week["open"] - tp_level)
            
            if dist_to_sl < dist_to_tp:
                exit_price = sl_price
                exit_date = week["week_end"]
                hit_sl = True
                exit_reason = "SL_HIT"
            else:
                exit_price = tp_level
                exit_date = week["week_end"]
                exit_reason = "TP_HIT"
            break
        elif sl_hit:
            exit_price = sl_price
            exit_date = week["week_end"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        elif tp_hit:
            exit_price = tp_level
            exit_date = week["week_end"]
            exit_reason = "TP_HIT"
            break
    
    if exit_price is None:
        last_week = subsequent_weekly.iloc[-1]
        exit_price = last_week["close"]
        exit_date = last_week["week_end"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_variant_detailed(symbols: List[str], symbol_data: Dict, ma_type: str, ma_period: int, sd_level: float) -> List[Dict]:
    """Return all trades for detailed analysis"""
    all_trades = []
    
    for symbol in symbols:
        if symbol not in symbol_data:
            continue
        
        df, weekly_df = symbol_data[symbol]
        weekly_with_indicators = add_indicators(weekly_df.copy(), ma_period, ma_type, sd_level)
        
        signals_df = identify_signals(weekly_with_indicators, ma_period)
        if len(signals_df) == 0:
            continue
        
        last_exit_date = None
        
        for _, signal_row in signals_df.iterrows():
            if last_exit_date is not None and signal_row["signal_date"] < last_exit_date:
                continue
            
            trade = calculate_trade(signal_row.to_dict(), df, symbol, weekly_with_indicators)
            if trade:
                all_trades.append(trade)
                last_exit_date = pd.Timestamp.now()  # Simplified
    
    return all_trades


def print_distribution_analysis(trades: List[Dict], variant_name: str):
    """Print detailed distribution analysis"""
    if not trades:
        print(f"  No trades for {variant_name}")
        return
    
    returns = pd.Series([t["net_return_pct"] for t in trades])
    
    print(f"\n{'─'*80}")
    print(f"📊 {variant_name}")
    print(f"{'─'*80}")
    
    print(f"\n  📈 Central Tendency:")
    print(f"      Mean:   {returns.mean():+.2f}%")
    print(f"      Median: {returns.median():+.2f}%")
    print(f"      Mode:   {returns.mode().iloc[0] if len(returns.mode()) > 0 else 'N/A':+.2f}%")
    
    print(f"\n  📉 Spread:")
    print(f"      Std Dev: {returns.std():.2f}%")
    print(f"      Min:     {returns.min():+.2f}%")
    print(f"      Max:     {returns.max():+.2f}%")
    print(f"      Range:   {returns.max() - returns.min():.2f}%")
    
    print(f"\n  📊 Percentiles:")
    percentiles = [5, 10, 25, 50, 75, 90, 95]
    for p in percentiles:
        val = np.percentile(returns, p)
        print(f"      P{p:2d}: {val:+7.2f}%")
    
    print(f"\n  📦 Distribution Buckets:")
    
    # Define buckets
    buckets = [
        (-100, -20, "Heavy Loss (< -20%)"),
        (-20, -10, "Moderate Loss (-20% to -10%)"),
        (-10, -5, "Small Loss (-10% to -5%)"),
        (-5, 0, "Minor Loss (-5% to 0%)"),
        (0, 5, "Minor Gain (0% to 5%)"),
        (5, 10, "Small Gain (5% to 10%)"),
        (10, 20, "Moderate Gain (10% to 20%)"),
        (20, 50, "Good Gain (20% to 50%)"),
        (50, 100, "Great Gain (50% to 100%)"),
        (100, 500, "Exceptional (> 100%)"),
    ]
    
    total = len(returns)
    for low, high, label in buckets:
        count = len(returns[(returns >= low) & (returns < high)])
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        if count > 0:
            print(f"      {label:30} | {count:4} ({pct:5.1f}%) {bar}")
    
    # Skewness interpretation
    skew = returns.skew()
    print(f"\n  📐 Shape:")
    print(f"      Skewness: {skew:.2f}", end="")
    if skew > 0.5:
        print(" (right-skewed: more big winners)")
    elif skew < -0.5:
        print(" (left-skewed: more big losers)")
    else:
        print(" (approximately symmetric)")
    
    kurtosis = returns.kurtosis()
    print(f"      Kurtosis: {kurtosis:.2f}", end="")
    if kurtosis > 1:
        print(" (fat tails: more extreme outcomes)")
    elif kurtosis < -1:
        print(" (thin tails: fewer extreme outcomes)")
    else:
        print(" (normal-like tails)")
    
    # Win/Loss Analysis
    winners = returns[returns > 0]
    losers = returns[returns <= 0]
    
    print(f"\n  🎯 Win/Loss Analysis:")
    print(f"      Winners: {len(winners)} ({len(winners)/total*100:.1f}%)")
    print(f"      Losers:  {len(losers)} ({len(losers)/total*100:.1f}%)")
    if len(winners) > 0:
        print(f"      Avg Win:  {winners.mean():+.2f}%")
    if len(losers) > 0:
        print(f"      Avg Loss: {losers.mean():+.2f}%")
    if len(winners) > 0 and len(losers) > 0:
        print(f"      Win/Loss Ratio: {abs(winners.mean() / losers.mean()):.2f}x")


def main():
    print(f"\n🔬 TOP 5 VARIANTS - DETAILED RETURN DISTRIBUTION ANALYSIS")
    print(f"{'═'*80}")
    
    # Load data
    print(f"\n📂 Loading data...")
    symbols = load_basket("data/baskets/basket_large.txt")
    
    symbol_data = {}
    for symbol in symbols:
        df = load_ohlc_data(symbol)
        if df is not None and len(df) >= 100:
            weekly_df = get_weekly_candles(df)
            if len(weekly_df) >= 25:
                symbol_data[symbol] = (df, weekly_df)
    
    print(f"  Loaded {len(symbol_data)} symbols")
    
    # Analyze each top variant
    print(f"\n🧪 Analyzing top 5 variants...")
    
    all_results = {}
    
    for ma_type, ma_period, sd_level in TOP_VARIANTS:
        variant_name = f"{ma_type} {ma_period} / {sd_level}SD"
        trades = analyze_variant_detailed(symbols, symbol_data, ma_type, ma_period, sd_level)
        all_results[variant_name] = trades
        print_distribution_analysis(trades, variant_name)
    
    # Summary comparison
    print(f"\n{'═'*80}")
    print(f"SUMMARY COMPARISON")
    print(f"{'═'*80}\n")
    
    print(f"{'Variant':<22} | {'Trades':>6} | {'Median':>8} | {'P25':>8} | {'P75':>8} | {'P5':>8} | {'P95':>8}")
    print(f"{'-'*22}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}")
    
    for variant_name, trades in all_results.items():
        if trades:
            returns = [t["net_return_pct"] for t in trades]
            print(f"{variant_name:<22} | {len(trades):>6} | {np.median(returns):>+7.2f}% | {np.percentile(returns, 25):>+7.2f}% | {np.percentile(returns, 75):>+7.2f}% | {np.percentile(returns, 5):>+7.2f}% | {np.percentile(returns, 95):>+7.2f}%")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_v2_refined.py ==========

#!/usr/bin/env python3
"""
Refined Weekly Green Candle Strategy - v2
==========================================
Hypothesis: When a completed weekly green candle forms with:
1. Opens below Bollinger Band 1 SD
2. Body bigger than previous candle's body
Then: Trade on next week's first trading day
Exit: When price touches 20 SMA (Bollinger Band middle)
Stop Loss: Previous candle's low

FIXES:
- Transaction cost: 0.37% TOTAL (not doubled to 0.74%)
- Exit on 20 SMA instead of calendar close
- SL protection with prior candle low
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
BASKET_FILE = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37  # 0.37% TOTAL (0.175% entry + 0.175% exit)


def load_basket(path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLC data for symbol from cache."""
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily data to weekly candles (Monday-Friday)."""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Identify trading signals based on STRICT criteria."""
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    # Calculate Bollinger Bands
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(
        weekly_df["close"], period=20, std_dev=1.0
    )
    
    weekly_df["bb_upper"] = upper_bb
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_lower"] = lower_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        # Condition 1: Current week is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Condition 2: Opens below 1 SD
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        # Condition 3: Body bigger than previous
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "signal_open": curr["open"],
            "signal_close": curr["close"],
            "signal_high": curr["high"],
            "signal_low": curr["low"],
            "signal_body": curr["body"],
            "prev_low": prev["low"],  # For stop loss
            "bb_middle": weekly_df.iloc[i]["bb_middle"],  # For exit
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the next Monday after given date."""
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_with_sma_exit(signal_row: Dict, df: pd.DataFrame, symbol: str, weekly_df: pd.DataFrame) -> Optional[Dict]:
    """
    Calculate returns with:
    - Entry: Next Monday open
    - Exit: When price touches 20 SMA (Bollinger Band middle)
    - Stop Loss: Previous candle's low
    """
    signal_date = signal_row["signal_date"]
    entry_sl = signal_row["prev_low"]  # Stop loss level
    target_sma = signal_row["bb_middle"]  # Exit target (20 SMA)
    
    # Find next Monday
    next_monday = find_next_monday(signal_date)
    
    # Find entry price on that Monday
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    # Find exit: search from entry date onwards for price that touches 20 SMA
    future_df = df[df["date"] >= entry_date].copy()
    if len(future_df) < 2:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in future_df.index:
        row = df.loc[idx]
        
        # Check if hit stop loss (any price below SL during the day)
        if row["low"] <= entry_sl:
            exit_price = entry_sl
            exit_date = row["date"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        # Check if hit target SMA (price touches or crosses 20 SMA)
        if row["low"] <= target_sma <= row["high"]:
            # Assume we exit at the SMA level
            exit_price = target_sma
            exit_date = row["date"]
            exit_reason = "TARGET_HIT"
            break
        
        # Safety: Don't hold more than 10 trading days
        days_held = (row["date"] - entry_date).days
        if days_held > 10:
            exit_price = row["close"]
            exit_date = row["date"]
            exit_reason = "TIME_EXIT_10D"
            break
    
    # If no exit found, exit at end of data
    if exit_price is None:
        exit_price = future_df.iloc[-1]["close"]
        exit_date = future_df.iloc[-1]["date"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    # Calculate returns (FIXED: no doubling of transaction cost)
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100  # 0.37% total, NOT doubled
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": entry_sl,
        "target_sma": target_sma,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    """Analyze a single symbol."""
    trades = []
    
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_with_sma_exit(signal_row.to_dict(), df, symbol, weekly_df)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def main():
    """Main execution."""
    print(f"\n🔬 REFINED HYPOTHESIS TEST - Weekly Green Candle v2")
    print(f"{'─'*120}")
    print(f"Basket: {BASKET_FILE}")
    print(f"\nSignal Conditions (STRICT):")
    print(f"  1. Weekly candle is GREEN (close > open)")
    print(f"  2. Opens BELOW Bollinger Band 1-SD")
    print(f"  3. Body BIGGER than previous week's body")
    print(f"\nEntry/Exit/SL:")
    print(f"  Entry: Next Monday at open")
    print(f"  Exit: When price touches 20 SMA (BB middle) OR max 10 days")
    print(f"  Stop Loss: Previous candle's low")
    print(f"  Transaction Cost: 0.37% total (CORRECTED)")
    print()
    
    # Load basket
    symbols = load_basket(BASKET_FILE)
    print(f"📋 Loaded {len(symbols)} symbols from basket")
    
    # Analyze each symbol
    all_trades = []
    symbol_with_signals = 0
    
    for i, symbol in enumerate(symbols):
        trades, signal_count = analyze_symbol(symbol)
        if signal_count > 0:
            symbol_with_signals += 1
            all_trades.extend(trades)
            if len(trades) > 5:
                print(f"  ✅ {symbol}: {len(trades)} trades from {signal_count} signals")
        
        if (i + 1) % 20 == 0:
            print(f"     [{i+1}/{len(symbols)}] analyzed...")
    
    print(f"\n📊 Analysis Complete")
    print(f"{'─'*120}")
    
    # Print summary
    if all_trades:
        df = pd.DataFrame(all_trades)
        
        print(f"\n✅ RESULTS - REFINED HYPOTHESIS (with SMA exit + SL)")
        print(f"{'─'*120}")
        
        total_trades = len(df)
        winning_trades = len(df[df["net_return_pct"] > 0])
        losing_trades = len(df[df["net_return_pct"] <= 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_return = df["net_return_pct"].mean()
        total_return = df["net_return_pct"].sum()
        median_return = df["net_return_pct"].median()
        std_return = df["net_return_pct"].std()
        
        best_trade = df["net_return_pct"].max()
        worst_trade = df["net_return_pct"].min()
        
        # Exit reason breakdown
        exit_reasons = df["exit_reason"].value_counts()
        sl_hit = len(df[df["hit_stop_loss"] == True])
        
        print(f"\n📈 OVERALL METRICS")
        print(f"{'─'*120}")
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
        print(f"Losing Trades: {losing_trades} ({100-win_rate:.1f}%)")
        print(f"SL Hit: {sl_hit} ({sl_hit/total_trades*100:.1f}%)")
        print(f"\nAverage Return/Trade: {avg_return:.2f}%")
        print(f"Median Return/Trade: {median_return:.2f}%")
        print(f"Total Return (Sum): {total_return:.2f}%")
        print(f"Std Dev: {std_return:.2f}%")
        print(f"Best Trade: {best_trade:.2f}%")
        print(f"Worst Trade: {worst_trade:.2f}%")
        
        print(f"\n📊 Exit Reason Distribution:")
        print(exit_reasons.to_string())
        
        # By symbol
        print(f"\n📈 TOP PERFORMERS (by symbol)")
        print(f"{'─'*120}")
        symbol_stats = df.groupby("symbol").agg({
            "net_return_pct": ["count", "mean", "sum"],
        }).round(2)
        symbol_stats.columns = ["Trades", "Avg Return %", "Total Return %"]
        symbol_stats = symbol_stats.sort_values("Total Return %", ascending=False).head(10)
        print(symbol_stats.to_string())
        
        # Bottom performers
        print(f"\n📉 WORST PERFORMERS (by symbol)")
        print(f"{'─'*120}")
        symbol_stats_worst = df.groupby("symbol").agg({
            "net_return_pct": ["count", "mean", "sum"],
        }).round(2)
        symbol_stats_worst.columns = ["Trades", "Avg Return %", "Total Return %"]
        symbol_stats_worst = symbol_stats_worst.sort_values("Total Return %", ascending=True).head(10)
        print(symbol_stats_worst.to_string())
        
        # Holding period analysis
        print(f"\n⏱️ HOLDING PERIOD ANALYSIS")
        print(f"{'─'*120}")
        print(f"Avg Holding Days: {df['days_held'].mean():.1f}")
        print(f"Median Holding Days: {df['days_held'].median():.0f}")
        print(f"Min Holding Days: {df['days_held'].min()}")
        print(f"Max Holding Days: {df['days_held'].max()}")
        
        print(f"\nAvg Return by Holding Period:")
        df['holding_bucket'] = pd.cut(df['days_held'], bins=[0, 1, 2, 3, 5, 10, 100], 
                                       labels=['1d', '2d', '3d', '4-5d', '6-10d', '10d+'])
        hold_stats = df.groupby('holding_bucket')['net_return_pct'].agg(['count', 'mean', 'sum']).round(2)
        hold_stats.columns = ['Trades', 'Avg %', 'Total %']
        print(hold_stats.to_string())
        
        # Save results
        output_path = "reports/hypothesis_weekly_green_v2_refined_results.csv"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False)
        print(f"\n💾 Results saved to: {output_path}")
        
        # Conclusion
        print(f"\n{'='*120}")
        if total_return > 0:
            print(f"✅ PROFITABLE: Total return {total_return:.2f}% across {total_trades} trades")
        else:
            print(f"❌ NOT PROFITABLE: Total return {total_return:.2f}% across {total_trades} trades")
            print(f"   → Avg return is still negative at {avg_return:.2f}% per trade")
            print(f"   → Win rate {win_rate:.1f}% needs to be > 50% to profitably cover costs")
    else:
        print("❌ No trades generated")


if __name__ == "__main__":
    main()


# ========== FROM: test_hypothesis_v3_unlimited.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Hypothesis - v3
===================================
CHANGES from v2:
- Remove 10-day maximum holding period cap
- Let SMA exit work naturally (no time limit)
- Keep SL protection as before
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

CACHE_DIR = Path("data/cache/dhan/daily")
BASKET_FILE = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    if len(weekly_df) < 25:
        return pd.DataFrame()
    
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(weekly_df["close"], period=20, std_dev=1.0)
    weekly_df["bb_upper"] = upper_bb
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_lower"] = lower_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
        if not opens_below_bb:
            continue
        
        bigger_body = curr["body"] > prev["body"]
        if not bigger_body:
            continue
        
        signals.append({
            "signal_date": curr["date"],
            "signal_low": curr["low"],
            "prev_low": prev["low"],
            "bb_middle": weekly_df.iloc[i]["bb_middle"],
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def calculate_trade_unlimited_sma_exit(signal_row: Dict, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """
    NO 10-day cap - let SMA exit work naturally
    Exit when price touches 20 SMA OR at data end
    """
    signal_date = signal_row["signal_date"]
    entry_sl = signal_row["prev_low"]
    target_sma = signal_row["bb_middle"]
    
    next_monday = find_next_monday(signal_date)
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price = entry_actual["open"]
    entry_date = entry_actual["date"]
    
    future_df = df[df["date"] >= entry_date].copy()
    if len(future_df) < 2:
        return None
    
    exit_price = None
    exit_date = None
    hit_sl = False
    exit_reason = "NOT_HIT"
    
    for idx in future_df.index:
        row = df.loc[idx]
        
        # Check SL
        if row["low"] <= entry_sl:
            exit_price = entry_sl
            exit_date = row["date"]
            hit_sl = True
            exit_reason = "SL_HIT"
            break
        
        # Check target (NO 10-day limit anymore!)
        if row["low"] <= target_sma <= row["high"]:
            exit_price = target_sma
            exit_date = row["date"]
            exit_reason = "TARGET_HIT"
            break
    
    # If no exit found, exit at end of data
    if exit_price is None:
        exit_price = future_df.iloc[-1]["close"]
        exit_date = future_df.iloc[-1]["date"]
        exit_reason = "DATA_END"
    
    if exit_date is None or exit_price is None:
        return None
    
    gross_return = (exit_price - entry_price) / entry_price
    transaction_costs = TRANSACTION_COST_PCT / 100
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": entry_date,
        "entry_price": entry_price,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "stop_loss": entry_sl,
        "target_sma": target_sma,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "exit_reason": exit_reason,
        "hit_stop_loss": hit_sl,
        "days_held": (exit_date - entry_date).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    trades = []
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_unlimited_sma_exit(signal_row.to_dict(), df, symbol)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def main():
    print(f"\n🔬 HYPOTHESIS TEST v3 - Unlimited SMA Exit (NO 10-day cap)")
    print(f"{'─'*120}")
    print(f"Changes from v2:")
    print(f"  ❌ Removed 10-day maximum holding period")
    print(f"  ✅ Let SMA exit work naturally (can hold indefinitely)")
    print(f"  ✅ Keep SL protection")
    print()
    
    symbols = load_basket(BASKET_FILE)
    print(f"📋 Loaded {len(symbols)} symbols")
    
    all_trades = []
    for i, symbol in enumerate(symbols):
        trades, _ = analyze_symbol(symbol)
        all_trades.extend(trades)
        
        if (i + 1) % 20 == 0:
            print(f"  [{i+1}/{len(symbols)}] processed...")
    
    print(f"\n📊 Analysis Complete")
    print(f"{'─'*120}\n")
    
    if all_trades:
        df = pd.DataFrame(all_trades)
        
        total_trades = len(df)
        winning_trades = len(df[df["net_return_pct"] > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_return = df["net_return_pct"].mean()
        total_return = df["net_return_pct"].sum()
        median_return = df["net_return_pct"].median()
        
        sl_hit = len(df[df["hit_stop_loss"] == True])
        
        print(f"✅ RESULTS - HYPOTHESIS v3 (Unlimited SMA Exit)")
        print(f"{'─'*120}\n")
        print(f"📈 OVERALL METRICS")
        print(f"Total Trades: {total_trades}")
        print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
        print(f"Losing Trades: {total_trades - winning_trades} ({100-win_rate:.1f}%)")
        print(f"SL Hit Rate: {sl_hit} ({sl_hit/total_trades*100:.1f}%)")
        print(f"\nAverage Return/Trade: {avg_return:.2f}%")
        print(f"Median Return/Trade: {median_return:.2f}%")
        print(f"Total Return: {total_return:.2f}%")
        print(f"Best Trade: {df['net_return_pct'].max():.2f}%")
        print(f"Worst Trade: {df['net_return_pct'].min():.2f}%")
        
        print(f"\n📊 Exit Reason Distribution:")
        print(df["exit_reason"].value_counts().to_string())
        
        print(f"\n⏱️ HOLDING PERIOD ANALYSIS")
        print(f"Avg Holding Days: {df['days_held'].mean():.1f}")
        print(f"Median Holding Days: {df['days_held'].median():.0f}")
        print(f"Max Holding Days: {df['days_held'].max()}")
        
        print(f"\n📈 TOP SYMBOLS")
        top = df.groupby("symbol")["net_return_pct"].agg(['count', 'mean', 'sum']).round(2)
        top.columns = ['Trades', 'Avg %', 'Total %']
        print(top.sort_values("Total %", ascending=False).head(10).to_string())
        
        # Save
        Path("reports").mkdir(exist_ok=True)
        df.to_csv("reports/hypothesis_weekly_green_v3_unlimited_results.csv", index=False)
        print(f"\n💾 Results saved to: reports/hypothesis_weekly_green_v3_unlimited_results.csv")
        
        # Verdict
        print(f"\n{'='*120}")
        if total_return > 0:
            print(f"✅ PROFITABLE: +{total_return:.2f}% total return")
        else:
            print(f"❌ NOT PROFITABLE: {total_return:.2f}% total return")
            improvement = ((total_return - (-449.62)) / (-449.62) * 100)
            print(f"   (Improved {improvement:.1f}% vs v2 with 10-day cap)")


if __name__ == "__main__":
    main()
