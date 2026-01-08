# Mean Reversion Experiments Archive
# Combined on 2026-01-08


# ========== FROM: test_mean_reversion_ema_touch.py ==========

#!/usr/bin/env python3
"""
Mean Reversion Hypothesis - EMA Touch Exit Strategy
====================================================
Test: 30% drop from EMA20 with Take Profit at EMA20 line touch

Entry: Close is 30% below EMA(20)
Exit: 
  - TP: Price touches/crosses EMA(20) (uses the EMA value on that day)
  - SL: 30% loss from entry price

This differs from fixed % TP - we exit when price reverts TO the mean (EMA20).

Usage:
    python scripts/test_mean_reversion_ema_touch.py --basket large
    python scripts/test_mean_reversion_ema_touch.py --basket mid
    python scripts/test_mean_reversion_ema_touch.py --basket small
    python scripts/test_mean_reversion_ema_touch.py --basket all
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loaders import load_many_india


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

EMA_PERIOD = 20
ENTRY_DROP_PCT = 0.30      # 30% below EMA
STOP_LOSS_PCT = 0.30       # 30% SL from entry
POSITION_SIZE = 10000      # ₹10,000 per trade

BASKET_DIR = Path("data/baskets")


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTING
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_symbol(df: pd.DataFrame, symbol: str) -> List[Dict]:
    """
    Backtest single symbol with EMA touch exit.
    
    Entry: Close is 30% below EMA(20)
    Exit: Price touches EMA(20) OR 30% SL
    """
    if len(df) < EMA_PERIOD + 10:
        return []
    
    df = df.copy()
    df["ema"] = calculate_ema(df["close"], EMA_PERIOD)
    df = df.dropna()
    
    if len(df) < 10:
        return []
    
    trades = []
    in_position = False
    entry_price = 0.0
    entry_date = None
    entry_ema = 0.0
    
    for date, row in df.iterrows():
        ema_today = row["ema"]
        close = row["close"]
        high = row["high"]
        
        if not in_position:
            # Entry condition: Close is 30% or more below EMA
            deviation = (close - ema_today) / ema_today
            if deviation <= -ENTRY_DROP_PCT:
                entry_price = close
                entry_date = date
                entry_ema = ema_today
                in_position = True
        else:
            # Check exits using current day's EMA (moving target)
            current_ema = ema_today
            
            # TP: High touched or crossed EMA (price reverted to mean)
            if high >= current_ema:
                # Exit at EMA price (or close if it gapped above)
                exit_price = min(current_ema, close) if close > current_ema else current_ema
                pnl_pct = (exit_price - entry_price) / entry_price * 100
                pnl_amt = (exit_price - entry_price) * (POSITION_SIZE / entry_price)
                
                trades.append({
                    "symbol": symbol,
                    "entry_date": str(entry_date)[:10],
                    "exit_date": str(date)[:10],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "entry_ema": round(entry_ema, 2),
                    "exit_ema": round(current_ema, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amt": round(pnl_amt, 2),
                    "exit_reason": "TP_EMA_TOUCH",
                    "days_held": (date - entry_date).days if hasattr(date - entry_date, 'days') else 0,
                })
                in_position = False
                continue
            
            # SL: 30% loss from entry
            sl_price = entry_price * (1 - STOP_LOSS_PCT)
            if close <= sl_price:
                exit_price = sl_price
                pnl_pct = -STOP_LOSS_PCT * 100
                pnl_amt = -STOP_LOSS_PCT * POSITION_SIZE
                
                trades.append({
                    "symbol": symbol,
                    "entry_date": str(entry_date)[:10],
                    "exit_date": str(date)[:10],
                    "entry_price": round(entry_price, 2),
                    "exit_price": round(exit_price, 2),
                    "entry_ema": round(entry_ema, 2),
                    "exit_ema": round(current_ema, 2),
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_amt": round(pnl_amt, 2),
                    "exit_reason": "SL",
                    "days_held": (date - entry_date).days if hasattr(date - entry_date, 'days') else 0,
                })
                in_position = False
    
    return trades


def load_basket(basket_name: str) -> List[str]:
    """Load symbols from basket file."""
    basket_file = BASKET_DIR / f"basket_{basket_name}.txt"
    if not basket_file.exists():
        print(f"❌ Basket not found: {basket_file}")
        return []
    
    symbols = []
    with open(basket_file) as f:
        for line in f:
            symbol = line.strip().upper()
            if symbol and not symbol.startswith("#"):
                symbols.append(symbol)
    
    return symbols


def run_backtest(basket_name: str) -> pd.DataFrame:
    """Run backtest for a basket."""
    print(f"\n{'='*80}")
    print(f"MEAN REVERSION: 30% DROP FROM EMA(20), TP AT EMA TOUCH")
    print(f"{'='*80}")
    print(f"📊 Strategy: EMA({EMA_PERIOD}) Touch Exit")
    print(f"   Entry: Close {ENTRY_DROP_PCT*100:.0f}% below EMA({EMA_PERIOD})")
    print(f"   Exit TP: Price touches EMA({EMA_PERIOD}) line (moving target)")
    print(f"   Exit SL: {STOP_LOSS_PCT*100:.0f}% from entry")
    print(f"{'='*80}")
    
    # Load symbols
    symbols = load_basket(basket_name)
    if not symbols:
        return pd.DataFrame()
    
    print(f"\n📊 Basket: {basket_name.upper()} ({len(symbols)} symbols)")
    
    # Load data
    print("Loading data from cache...")
    data = load_many_india(symbols, interval="1d", use_cache_only=True)
    print(f"✅ Loaded data for {len(data)} symbols")
    
    # Run backtest
    all_trades = []
    symbols_with_trades = 0
    
    for symbol, df in data.items():
        trades = backtest_symbol(df, symbol)
        if trades:
            all_trades.extend(trades)
            symbols_with_trades += 1
    
    if not all_trades:
        print("❌ No trades found")
        return pd.DataFrame()
    
    # Create DataFrame
    df_trades = pd.DataFrame(all_trades)
    
    # Calculate stats
    total_trades = len(df_trades)
    wins = df_trades[df_trades["pnl_pct"] > 0]
    losses = df_trades[df_trades["pnl_pct"] <= 0]
    
    win_rate = len(wins) / total_trades * 100
    
    gross_profit = wins["pnl_amt"].sum() if len(wins) > 0 else 0
    gross_loss = abs(losses["pnl_amt"].sum()) if len(losses) > 0 else 0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    total_pnl = df_trades["pnl_amt"].sum()
    avg_win = wins["pnl_pct"].mean() if len(wins) > 0 else 0
    avg_loss = losses["pnl_pct"].mean() if len(losses) > 0 else 0
    
    tp_exits = len(df_trades[df_trades["exit_reason"] == "TP_EMA_TOUCH"])
    sl_exits = len(df_trades[df_trades["exit_reason"] == "SL"])
    
    avg_days = df_trades["days_held"].mean()
    
    # Print results
    print(f"\n{'='*80}")
    print(f"RESULTS: {basket_name.upper()}")
    print(f"{'='*80}")
    print(f"Total Trades:     {total_trades:,}")
    print(f"Symbols Traded:   {symbols_with_trades}")
    print(f"Win Rate:         {win_rate:.1f}%")
    print(f"Profit Factor:    {profit_factor:.2f}")
    print(f"")
    print(f"Avg Win:          +{avg_win:.1f}%")
    print(f"Avg Loss:         {avg_loss:.1f}%")
    print(f"Avg Days Held:    {avg_days:.1f} days")
    print(f"")
    print(f"Exit Distribution:")
    print(f"  TP (EMA Touch): {tp_exits} ({tp_exits/total_trades*100:.1f}%)")
    print(f"  SL (30% loss):  {sl_exits} ({sl_exits/total_trades*100:.1f}%)")
    print(f"")
    print(f"Total P&L:        ₹{total_pnl:,.2f}")
    print(f"Per Trade P&L:    ₹{total_pnl/total_trades:,.2f}")
    
    # Top performers
    print(f"\n📈 TOP 5 WINNING TRADES:")
    top_wins = df_trades.nlargest(5, "pnl_pct")
    for _, t in top_wins.iterrows():
        print(f"   {t['symbol']}: +{t['pnl_pct']:.1f}% "
              f"(₹{t['entry_price']:.0f} → ₹{t['exit_price']:.0f}, "
              f"{t['days_held']} days)")
    
    print(f"\n📉 TOP 5 LOSING TRADES:")
    top_losses = df_trades.nsmallest(5, "pnl_pct")
    for _, t in top_losses.iterrows():
        print(f"   {t['symbol']}: {t['pnl_pct']:.1f}% "
              f"(₹{t['entry_price']:.0f} → ₹{t['exit_price']:.0f}, "
              f"{t['days_held']} days)")
    
    # Save to CSV
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"reports/mean_reversion_ema_touch_{basket_name}_{timestamp}.csv"
    os.makedirs("reports", exist_ok=True)
    df_trades.to_csv(output_file, index=False)
    print(f"\n📁 Trades saved to: {output_file}")
    
    return df_trades


def main():
    parser = argparse.ArgumentParser(description="Mean Reversion - EMA Touch Exit Strategy")
    parser.add_argument("--basket", choices=["large", "mid", "small", "all"], 
                        required=True, help="Basket to test")
    
    args = parser.parse_args()
    
    all_results = []
    baskets = ["large", "mid", "small"] if args.basket == "all" else [args.basket]
    
    for basket in baskets:
        df = run_backtest(basket)
        if not df.empty:
            all_results.append((basket, df))
    
    # Summary comparison if testing all
    if args.basket == "all" and len(all_results) == 3:
        print(f"\n{'='*80}")
        print("COMPARISON SUMMARY: 30% DROP → EMA(20) TOUCH EXIT")
        print(f"{'='*80}")
        print(f"{'Basket':<10} {'Trades':<10} {'WR%':<10} {'PF':<10} {'TP%':<10} {'SL%':<10} {'Total P&L':<15}")
        print("-" * 80)
        
        for basket_name, df in all_results:
            total = len(df)
            wr = len(df[df["pnl_pct"] > 0]) / total * 100
            wins = df[df["pnl_pct"] > 0]["pnl_amt"].sum()
            losses = abs(df[df["pnl_pct"] <= 0]["pnl_amt"].sum())
            pf = wins / losses if losses > 0 else 0
            tp_pct = len(df[df["exit_reason"] == "TP_EMA_TOUCH"]) / total * 100
            sl_pct = len(df[df["exit_reason"] == "SL"]) / total * 100
            pnl = df["pnl_amt"].sum()
            
            print(f"{basket_name.upper():<10} {total:<10} {wr:<10.1f} {pf:<10.2f} "
                  f"{tp_pct:<10.1f} {sl_pct:<10.1f} ₹{pnl:>13,.0f}")


if __name__ == "__main__":
    main()


# ========== FROM: test_mean_reversion_sma.py ==========

#!/usr/bin/env python3
"""
Mean Reversion Hypothesis Test
==============================
Thesis: When price is 10% below the 50-day SMA, it will eventually revert to that mean.

Entry: Close is >= 10% below 50-day SMA
Exit:  Close touches or exceeds 50-day SMA (TP) OR 20% stop loss (SL)

Usage:
    python scripts/test_mean_reversion_sma.py --basket large
    python scripts/test_mean_reversion_sma.py --basket mid
    python scripts/test_mean_reversion_sma.py --basket small
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loaders import load_many_india


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

SMA_PERIOD = 50
ENTRY_THRESHOLD = -0.10  # Entry when price is 10% below SMA
STOP_LOSS_PCT = 0.20     # 20% stop loss from entry
POSITION_SIZE = 10000    # ₹10,000 per trade

BASKET_DIR = Path("data/baskets")


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATOR CALCULATION
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def calculate_deviation_pct(close: pd.Series, sma: pd.Series) -> pd.Series:
    """Calculate percentage deviation from SMA."""
    return (close - sma) / sma


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTING
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_symbol(df: pd.DataFrame, symbol: str) -> Dict:
    """
    Backtest mean reversion strategy on a single symbol.
    
    Entry: Close >= 10% below 50-day SMA
    Exit: Close touches SMA (TP) or 20% stop loss (SL)
    """
    if len(df) < SMA_PERIOD + 10:
        return {"symbol": symbol, "trades": [], "error": "Insufficient data"}
    
    df = df.copy()
    
    # Calculate indicators
    df["sma"] = calculate_sma(df["close"], SMA_PERIOD)
    df["deviation"] = calculate_deviation_pct(df["close"], df["sma"])
    
    # Drop NaN rows
    df = df.dropna()
    
    if len(df) < 10:
        return {"symbol": symbol, "trades": [], "error": "Not enough data after SMA calculation"}
    
    # Simulate trades
    trades = []
    in_position = False
    entry_price = 0.0
    entry_date = None
    stop_price = 0.0
    
    for i, (date, row) in enumerate(df.iterrows()):
        if not in_position:
            # Entry condition: Close is 10% or more below SMA
            if row["deviation"] <= ENTRY_THRESHOLD:
                entry_price = row["close"]
                entry_date = date
                stop_price = entry_price * (1 - STOP_LOSS_PCT)
                in_position = True
        else:
            # Check exit conditions
            exit_triggered = False
            exit_price = 0.0
            exit_reason = ""
            
            # TP: Price touches or exceeds SMA
            if row["close"] >= row["sma"]:
                exit_triggered = True
                exit_price = row["sma"]  # Exit at SMA level
                exit_reason = "TP"
            
            # SL: Price drops 20% from entry
            elif row["low"] <= stop_price:
                exit_triggered = True
                exit_price = stop_price
                exit_reason = "SL"
            
            if exit_triggered:
                pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                qty = POSITION_SIZE / entry_price
                pnl_abs = qty * (exit_price - entry_price)
                
                # Calculate holding period
                holding_days = (date - entry_date).days if hasattr(date, 'days') else 0
                try:
                    holding_days = (pd.Timestamp(date) - pd.Timestamp(entry_date)).days
                except:
                    holding_days = 0
                
                trades.append({
                    "entry_date": str(entry_date)[:10],
                    "entry_price": round(entry_price, 2),
                    "exit_date": str(date)[:10],
                    "exit_price": round(exit_price, 2),
                    "exit_reason": exit_reason,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_abs": round(pnl_abs, 2),
                    "holding_days": holding_days,
                    "deviation_at_entry": round(row["deviation"] * 100 if "deviation" in row else 0, 2),
                })
                
                in_position = False
    
    # Calculate summary stats
    if trades:
        total_pnl = sum(t["pnl_abs"] for t in trades)
        total_pnl_pct = sum(t["pnl_pct"] for t in trades)
        win_trades = [t for t in trades if t["pnl_pct"] > 0]
        win_rate = len(win_trades) / len(trades) * 100
        avg_holding = np.mean([t["holding_days"] for t in trades])
        
        # Profit factor
        gross_profit = sum(t["pnl_abs"] for t in trades if t["pnl_abs"] > 0)
        gross_loss = abs(sum(t["pnl_abs"] for t in trades if t["pnl_abs"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        return {
            "symbol": symbol,
            "total_trades": len(trades),
            "win_rate": round(win_rate, 1),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "total_pnl_abs": round(total_pnl, 2),
            "avg_holding_days": round(avg_holding, 1),
            "profit_factor": round(profit_factor, 2),
            "tp_exits": len([t for t in trades if t["exit_reason"] == "TP"]),
            "sl_exits": len([t for t in trades if t["exit_reason"] == "SL"]),
            "trades": trades,
        }
    else:
        return {
            "symbol": symbol,
            "total_trades": 0,
            "win_rate": 0,
            "total_pnl_pct": 0,
            "total_pnl_abs": 0,
            "trades": [],
        }


def load_basket(basket_name: str) -> List[str]:
    """Load symbols from basket file."""
    basket_file = BASKET_DIR / f"basket_{basket_name}.txt"
    if not basket_file.exists():
        print(f"❌ Basket not found: {basket_file}")
        return []
    
    symbols = []
    with open(basket_file) as f:
        for line in f:
            symbol = line.strip().upper()
            if symbol and not symbol.startswith("#"):
                symbols.append(symbol)
    
    return symbols


def run_backtest(basket_name: str) -> None:
    """Run backtest on a basket."""
    print("=" * 70)
    print(f"MEAN REVERSION HYPOTHESIS TEST")
    print(f"Entry: Close 10% below 50-day SMA | Exit: SMA touch or 20% SL")
    print("=" * 70)
    print()
    
    # Load symbols
    symbols = load_basket(basket_name)
    if not symbols:
        return
    
    print(f"📊 Basket: {basket_name} ({len(symbols)} symbols)")
    print(f"📅 Testing with MAX available data")
    print()
    
    # Load data
    print("Loading data from cache...")
    data = load_many_india(symbols, interval="1d", use_cache_only=True)
    print(f"✅ Loaded data for {len(data)} symbols")
    print()
    
    # Run backtests
    results = []
    errors = []
    
    for i, symbol in enumerate(symbols, 1):
        if symbol not in data or data[symbol].empty:
            errors.append(symbol)
            continue
        
        df = data[symbol]
        result = backtest_symbol(df, symbol)
        
        if "error" in result:
            errors.append(symbol)
        else:
            results.append(result)
        
        # Progress indicator
        if i % 50 == 0:
            print(f"  Processed {i}/{len(symbols)} symbols...")
    
    print()
    
    # Filter symbols with trades
    symbols_with_trades = [r for r in results if r.get("total_trades", 0) > 0]
    
    # Calculate aggregate stats
    total_trades = sum(r.get("total_trades", 0) for r in symbols_with_trades)
    total_pnl = sum(r.get("total_pnl_abs", 0) for r in symbols_with_trades)
    
    all_trades = []
    for r in symbols_with_trades:
        for t in r.get("trades", []):
            t["symbol"] = r["symbol"]
            all_trades.append(t)
    
    if all_trades:
        win_trades = [t for t in all_trades if t["pnl_pct"] > 0]
        overall_win_rate = len(win_trades) / len(all_trades) * 100
        avg_win = np.mean([t["pnl_pct"] for t in win_trades]) if win_trades else 0
        avg_loss = np.mean([t["pnl_pct"] for t in all_trades if t["pnl_pct"] <= 0]) if any(t["pnl_pct"] <= 0 for t in all_trades) else 0
        avg_holding = np.mean([t["holding_days"] for t in all_trades])
        
        tp_count = len([t for t in all_trades if t["exit_reason"] == "TP"])
        sl_count = len([t for t in all_trades if t["exit_reason"] == "SL"])
        
        gross_profit = sum(t["pnl_abs"] for t in all_trades if t["pnl_abs"] > 0)
        gross_loss = abs(sum(t["pnl_abs"] for t in all_trades if t["pnl_abs"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    else:
        overall_win_rate = 0
        avg_win = 0
        avg_loss = 0
        avg_holding = 0
        tp_count = 0
        sl_count = 0
        profit_factor = 0
    
    # Print results
    print("=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print()
    print(f"Basket:              {basket_name.upper()}")
    print(f"Symbols Tested:      {len(results)}")
    print(f"Symbols with Trades: {len(symbols_with_trades)}")
    print(f"Symbols Skipped:     {len(errors)} (no data or insufficient history)")
    print()
    print("-" * 70)
    print("TRADE STATISTICS")
    print("-" * 70)
    print(f"Total Trades:        {total_trades}")
    print(f"Win Rate:            {overall_win_rate:.1f}%")
    print(f"Avg Win:             {avg_win:+.2f}%")
    print(f"Avg Loss:            {avg_loss:+.2f}%")
    print(f"Profit Factor:       {profit_factor:.2f}")
    print(f"Avg Holding Days:    {avg_holding:.1f}")
    print()
    print(f"TP Exits (SMA touch): {tp_count} ({tp_count/total_trades*100:.1f}%)" if total_trades > 0 else "TP Exits: 0")
    print(f"SL Exits (20% loss):  {sl_count} ({sl_count/total_trades*100:.1f}%)" if total_trades > 0 else "SL Exits: 0")
    print()
    print("-" * 70)
    print("P&L SUMMARY")
    print("-" * 70)
    print(f"Total P&L:           ₹{total_pnl:,.2f}")
    print(f"Total P&L %:         {sum(r.get('total_pnl_pct', 0) for r in symbols_with_trades):.2f}%")
    print()
    
    # Top performers
    sorted_results = sorted(symbols_with_trades, key=lambda x: x.get("total_pnl_pct", 0), reverse=True)
    
    print("-" * 70)
    print("TOP 10 PERFORMERS")
    print("-" * 70)
    for r in sorted_results[:10]:
        print(f"  {r['symbol']:<15} {r.get('total_trades', 0):>3} trades  {r.get('win_rate', 0):>5.1f}% WR  {r.get('total_pnl_pct', 0):>+8.2f}%  PF {r.get('profit_factor', 0):.2f}")
    
    print()
    print("-" * 70)
    print("WORST 10 PERFORMERS")
    print("-" * 70)
    for r in sorted_results[-10:]:
        print(f"  {r['symbol']:<15} {r.get('total_trades', 0):>3} trades  {r.get('win_rate', 0):>5.1f}% WR  {r.get('total_pnl_pct', 0):>+8.2f}%  PF {r.get('profit_factor', 0):.2f}")
    
    print()
    print("=" * 70)
    print()
    
    # Save detailed results to CSV
    output_file = f"reports/mean_reversion_sma_{basket_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    os.makedirs("reports", exist_ok=True)
    
    if all_trades:
        trades_df = pd.DataFrame(all_trades)
        trades_df.to_csv(output_file, index=False)
        print(f"📁 Detailed trades saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Mean Reversion SMA Hypothesis Test")
    parser.add_argument("--basket", choices=["large", "mid", "small", "main", "test"], 
                        required=True, help="Basket to test")
    
    args = parser.parse_args()
    run_backtest(args.basket)


if __name__ == "__main__":
    main()


# ========== FROM: test_mean_reversion_variations.py ==========

#!/usr/bin/env python3
"""
Mean Reversion Hypothesis - Multi-Variation Tester
===================================================
Tests multiple combinations of:
- MA Type: SMA, EMA
- MA Period: 20, 50, 200
- Entry Drop: 5%, 10%, 20%, 30% below MA
- Take Profit: 5%, 10%, 20%, 30% gain from entry

Usage:
    python scripts/test_mean_reversion_variations.py --basket large
    python scripts/test_mean_reversion_variations.py --basket mid
    python scripts/test_mean_reversion_variations.py --basket small
    python scripts/test_mean_reversion_variations.py --basket all
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from itertools import product

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loaders import load_many_india


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MA_TYPES = ["SMA", "EMA"]
MA_PERIODS = [20, 50, 200]
ENTRY_DROPS = [0.05, 0.10, 0.20, 0.30]  # 5%, 10%, 20%, 30%
TP_TARGETS = [0.05, 0.10, 0.20, 0.30]   # 5%, 10%, 20%, 30%
STOP_LOSS_PCT = 0.30  # Fixed 30% stop loss

POSITION_SIZE = 10000  # ₹10,000 per trade
BASKET_DIR = Path("data/baskets")


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATORS
# ═══════════════════════════════════════════════════════════════════════════════

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_ma(series: pd.Series, period: int, ma_type: str) -> pd.Series:
    """Calculate moving average based on type."""
    if ma_type == "SMA":
        return calculate_sma(series, period)
    else:
        return calculate_ema(series, period)


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTESTING
# ═══════════════════════════════════════════════════════════════════════════════

def backtest_variation(
    data: Dict[str, pd.DataFrame],
    ma_type: str,
    ma_period: int,
    entry_drop: float,
    tp_target: float,
) -> Dict:
    """
    Backtest a single variation across all symbols.
    
    Entry: Close is entry_drop% below MA
    Exit: TP at tp_target% gain OR SL at 30% loss
    """
    all_trades = []
    symbols_with_trades = 0
    
    for symbol, df in data.items():
        if len(df) < ma_period + 10:
            continue
        
        df = df.copy()
        
        # Calculate MA
        df["ma"] = calculate_ma(df["close"], ma_period, ma_type)
        df["deviation"] = (df["close"] - df["ma"]) / df["ma"]
        
        # Drop NaN
        df = df.dropna()
        if len(df) < 10:
            continue
        
        # Simulate trades
        in_position = False
        entry_price = 0.0
        entry_date = None
        
        for date, row in df.iterrows():
            if not in_position:
                # Entry: Close is entry_drop% or more below MA
                if row["deviation"] <= -entry_drop:
                    entry_price = row["close"]
                    entry_date = date
                    in_position = True
            else:
                # Check exits
                pnl_pct = (row["close"] - entry_price) / entry_price
                
                # TP hit
                if pnl_pct >= tp_target:
                    exit_price = entry_price * (1 + tp_target)
                    all_trades.append({
                        "symbol": symbol,
                        "entry_date": str(entry_date)[:10],
                        "exit_date": str(date)[:10],
                        "pnl_pct": tp_target * 100,
                        "exit_reason": "TP",
                    })
                    in_position = False
                
                # SL hit
                elif pnl_pct <= -STOP_LOSS_PCT:
                    all_trades.append({
                        "symbol": symbol,
                        "entry_date": str(entry_date)[:10],
                        "exit_date": str(date)[:10],
                        "pnl_pct": -STOP_LOSS_PCT * 100,
                        "exit_reason": "SL",
                    })
                    in_position = False
        
        if any(t["symbol"] == symbol for t in all_trades):
            symbols_with_trades += 1
    
    # Calculate summary
    if not all_trades:
        return {
            "ma_type": ma_type,
            "ma_period": ma_period,
            "entry_drop": entry_drop * 100,
            "tp_target": tp_target * 100,
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "total_pnl_pct": 0,
            "avg_trade_pnl": 0,
            "tp_pct": 0,
            "sl_pct": 0,
        }
    
    total_trades = len(all_trades)
    wins = [t for t in all_trades if t["pnl_pct"] > 0]
    losses = [t for t in all_trades if t["pnl_pct"] < 0]
    
    win_rate = len(wins) / total_trades * 100
    
    gross_profit = sum(t["pnl_pct"] for t in wins)
    gross_loss = abs(sum(t["pnl_pct"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    total_pnl = sum(t["pnl_pct"] for t in all_trades)
    avg_trade = total_pnl / total_trades
    
    tp_exits = len([t for t in all_trades if t["exit_reason"] == "TP"])
    sl_exits = len([t for t in all_trades if t["exit_reason"] == "SL"])
    
    return {
        "ma_type": ma_type,
        "ma_period": ma_period,
        "entry_drop": entry_drop * 100,
        "tp_target": tp_target * 100,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_pnl_pct": round(total_pnl, 1),
        "avg_trade_pnl": round(avg_trade, 2),
        "tp_pct": round(tp_exits / total_trades * 100, 1),
        "sl_pct": round(sl_exits / total_trades * 100, 1),
        "symbols_with_trades": symbols_with_trades,
    }


def load_basket(basket_name: str) -> List[str]:
    """Load symbols from basket file."""
    basket_file = BASKET_DIR / f"basket_{basket_name}.txt"
    if not basket_file.exists():
        print(f"❌ Basket not found: {basket_file}")
        return []
    
    symbols = []
    with open(basket_file) as f:
        for line in f:
            symbol = line.strip().upper()
            if symbol and not symbol.startswith("#"):
                symbols.append(symbol)
    
    return symbols


def run_all_variations(basket_name: str) -> pd.DataFrame:
    """Run all variations for a basket."""
    print(f"\n{'='*80}")
    print(f"MEAN REVERSION VARIATIONS - {basket_name.upper()} BASKET")
    print(f"{'='*80}")
    
    # Load symbols
    symbols = load_basket(basket_name)
    if not symbols:
        return pd.DataFrame()
    
    print(f"📊 Basket: {basket_name} ({len(symbols)} symbols)")
    
    # Load data
    print("Loading data from cache...")
    data = load_many_india(symbols, interval="1d", use_cache_only=True)
    print(f"✅ Loaded data for {len(data)} symbols")
    
    # Generate all combinations
    combinations = list(product(MA_TYPES, MA_PERIODS, ENTRY_DROPS, TP_TARGETS))
    total_combos = len(combinations)
    print(f"🔄 Testing {total_combos} variations...")
    print()
    
    results = []
    
    for i, (ma_type, ma_period, entry_drop, tp_target) in enumerate(combinations, 1):
        if i % 24 == 0 or i == 1:
            print(f"  Progress: {i}/{total_combos} ({i/total_combos*100:.0f}%)")
        
        result = backtest_variation(data, ma_type, ma_period, entry_drop, tp_target)
        result["basket"] = basket_name
        results.append(result)
    
    print(f"  Progress: {total_combos}/{total_combos} (100%)")
    
    return pd.DataFrame(results)


def print_top_results(df: pd.DataFrame, basket_name: str, n: int = 20):
    """Print top N results sorted by profit factor."""
    print(f"\n{'='*100}")
    print(f"TOP {n} VARIATIONS BY PROFIT FACTOR - {basket_name.upper()}")
    print(f"{'='*100}")
    
    # Filter valid results
    valid = df[df["total_trades"] >= 50].copy()
    
    if valid.empty:
        print("No variations with >= 50 trades")
        return
    
    # Sort by profit factor
    top = valid.nlargest(n, "profit_factor")
    
    print(f"\n{'MA':<8} {'Period':<8} {'Drop%':<8} {'TP%':<8} {'Trades':<8} {'WR%':<8} {'PF':<8} {'P&L%':<10} {'TP%':<8} {'SL%':<8}")
    print("-" * 100)
    
    for _, row in top.iterrows():
        print(f"{row['ma_type']:<8} {int(row['ma_period']):<8} {row['entry_drop']:.0f}%{'':<5} {row['tp_target']:.0f}%{'':<5} "
              f"{int(row['total_trades']):<8} {row['win_rate']:<8.1f} {row['profit_factor']:<8.2f} "
              f"{row['total_pnl_pct']:<10.1f} {row['tp_pct']:<8.1f} {row['sl_pct']:<8.1f}")


def print_summary_matrix(df: pd.DataFrame, basket_name: str):
    """Print summary matrix by MA type and period."""
    print(f"\n{'='*80}")
    print(f"SUMMARY BY MA TYPE & PERIOD - {basket_name.upper()}")
    print(f"{'='*80}")
    
    for ma_type in MA_TYPES:
        for ma_period in MA_PERIODS:
            subset = df[(df["ma_type"] == ma_type) & (df["ma_period"] == ma_period)]
            if subset.empty:
                continue
            
            avg_wr = subset["win_rate"].mean()
            avg_pf = subset[subset["profit_factor"] < 100]["profit_factor"].mean()  # Exclude inf
            avg_pnl = subset["total_pnl_pct"].mean()
            total_trades = subset["total_trades"].sum()
            
            best = subset.loc[subset["profit_factor"].idxmax()]
            
            print(f"\n{ma_type}({ma_period}):")
            print(f"  Avg WR: {avg_wr:.1f}% | Avg PF: {avg_pf:.2f} | Avg P&L: {avg_pnl:.1f}%")
            print(f"  Best: Drop {best['entry_drop']:.0f}% / TP {best['tp_target']:.0f}% → PF {best['profit_factor']:.2f}, WR {best['win_rate']:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Mean Reversion Multi-Variation Tester")
    parser.add_argument("--basket", choices=["large", "mid", "small", "all"], 
                        required=True, help="Basket to test")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("MEAN REVERSION HYPOTHESIS - VARIATION TESTING")
    print("=" * 80)
    print(f"MA Types: {MA_TYPES}")
    print(f"MA Periods: {MA_PERIODS}")
    print(f"Entry Drops: {[f'{d*100:.0f}%' for d in ENTRY_DROPS]}")
    print(f"TP Targets: {[f'{t*100:.0f}%' for t in TP_TARGETS]}")
    print(f"Stop Loss: {STOP_LOSS_PCT*100:.0f}% (fixed)")
    print(f"Total Variations: {len(MA_TYPES) * len(MA_PERIODS) * len(ENTRY_DROPS) * len(TP_TARGETS)}")
    
    all_results = []
    
    baskets = ["large", "mid", "small"] if args.basket == "all" else [args.basket]
    
    for basket in baskets:
        df = run_all_variations(basket)
        if not df.empty:
            all_results.append(df)
            print_top_results(df, basket)
            print_summary_matrix(df, basket)
    
    # Combine and save
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        
        # Save to CSV
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"reports/mean_reversion_variations_{args.basket}_{timestamp}.csv"
        os.makedirs("reports", exist_ok=True)
        combined.to_csv(output_file, index=False)
        
        print(f"\n{'='*80}")
        print(f"📁 Results saved to: {output_file}")
        print(f"{'='*80}")
        
        # Print overall best if testing all baskets
        if args.basket == "all":
            print(f"\n{'='*80}")
            print("OVERALL BEST VARIATIONS ACROSS ALL BASKETS")
            print(f"{'='*80}")
            
            valid = combined[combined["total_trades"] >= 50]
            
            # Best by profit factor
            print("\n🏆 TOP 10 BY PROFIT FACTOR (min 50 trades):")
            top_pf = valid.nlargest(10, "profit_factor")
            for _, row in top_pf.iterrows():
                print(f"  {row['basket'].upper():<6} {row['ma_type']}({int(row['ma_period'])}) "
                      f"Drop {row['entry_drop']:.0f}% TP {row['tp_target']:.0f}% → "
                      f"PF {row['profit_factor']:.2f}, WR {row['win_rate']:.1f}%, {int(row['total_trades'])} trades")
            
            # Best by total P&L
            print("\n💰 TOP 10 BY TOTAL P&L%:")
            top_pnl = valid.nlargest(10, "total_pnl_pct")
            for _, row in top_pnl.iterrows():
                print(f"  {row['basket'].upper():<6} {row['ma_type']}({int(row['ma_period'])}) "
                      f"Drop {row['entry_drop']:.0f}% TP {row['tp_target']:.0f}% → "
                      f"P&L {row['total_pnl_pct']:.1f}%, WR {row['win_rate']:.1f}%, {int(row['total_trades'])} trades")


if __name__ == "__main__":
    main()
