#!/usr/bin/env python3
"""
Test Weekly Rotation Strategy - Multiple Combinations

Settings:
- No filters (ADX disabled)
- Trailing stop: False
- Commission: 0.185% per side (0.37% round trip)
- Logic: Bottom N% ranking FIRST, then filter by drop threshold
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from pathlib import Path
from core.loaders import load_many_india
from core.engine import BacktestEngine
from core.config import BrokerConfig

from strategies.weekly_rotation import (
    WeeklyMeanReversionStrategy,
    compute_weekly_returns,
    compute_ranking_cache,
)

# Test combinations: (min_drop_pct, select_pct, name)
COMBOS = [
    (5.0, 20.0, ">5% drop + Bottom 20%"),
    (10.0, 10.0, ">10% drop + Bottom 10%"),
    (5.0, 10.0, ">5% drop + Bottom 10%"),
]

# 0.37% round trip = 0.185% per side
COMMISSION_PCT = 0.185

print("=" * 80)
print("WEEKLY ROTATION BACKTEST - MULTI-COMBO TEST")
print("=" * 80)
print(f"Commission: {COMMISSION_PCT}% per side ({COMMISSION_PCT * 2}% round trip)")
print("Filters: DISABLED | Trailing Stop: FALSE")
print("Logic: Bottom N% ranking → Then filter by drop threshold")
print("=" * 80)

# Load basket
basket_file = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data/baskets/basket_main.txt"
symbols = [s.strip() for s in basket_file.read_text().splitlines() if s.strip() and not s.startswith("#")]
print(f"\n📂 Loading {len(symbols)} symbols from basket_main.txt...")

# Load data (cache only)
data = load_many_india(symbols, "1d", cache=True)
print(f"✅ Loaded {len(data)} symbols")

# Compute weekly returns once (shared across all combos)
print("\n📊 Computing weekly returns...")
weekly_returns = compute_weekly_returns(data)

# Broker config with 0.37% round trip
broker_config = BrokerConfig(
    commission_pct=COMMISSION_PCT,
)


def run_backtest(select_pct: float, min_drop_pct: float, name: str):
    """Run backtest for a single combination."""
    print(f"\n{'='*80}")
    print(f"📈 TESTING: {name}")
    print(f"   select_pct={select_pct}%, min_drop_pct={min_drop_pct}%")
    print(f"{'='*80}")
    
    # Compute ranking cache
    cache = compute_ranking_cache(
        weekly_returns,
        mode="mean_reversion",
        select_pct=select_pct,
        min_drop_pct=min_drop_pct,
    )
    
    # Set cache on strategy class (reset first)
    WeeklyMeanReversionStrategy._ranking_cache = cache
    WeeklyMeanReversionStrategy._weekly_returns = weekly_returns
    WeeklyMeanReversionStrategy._cache_loaded = True
    
    n_entries = sum(1 for v in cache.values() if v.get("should_enter", False))
    print(f"   Cache entries with should_enter=True: {n_entries}")
    
    results = []
    for symbol in symbols:
        if symbol not in data:
            continue
        
        df = data[symbol]
        strategy = WeeklyMeanReversionStrategy(
            select_pct=select_pct,
            use_adx_filter=False,  # No filters
            use_trailing_stop=False,  # Trailing stop disabled
        )
        
        engine = BacktestEngine(df, strategy, broker_config, symbol=symbol)
        trades_df, equity_df, signals_df = engine.run()
        
        if trades_df is not None and len(trades_df) > 0:
            results.append({
                "symbol": symbol,
                "trades_df": trades_df,
            })
    
    # Aggregate results
    all_trades = []
    for r in results:
        trades_df = r["trades_df"]
        symbol = r["symbol"]
        for _, t in trades_df.iterrows():
            # Skip open trades (no exit price)
            if pd.isna(t.get("exit_price")):
                continue
            return_pct = (t["exit_price"] / t["entry_price"] - 1) * 100
            all_trades.append({
                "symbol": symbol,
                "entry_date": t["entry_time"],
                "exit_date": t["exit_time"],
                "return_pct": return_pct,
                "entry_price": t["entry_price"],
                "exit_price": t["exit_price"],
            })
    
    if not all_trades:
        print(f"\n   ❌ No trades generated!")
        return None
    
    df_trades = pd.DataFrame(all_trades)
    df_trades["year"] = pd.to_datetime(df_trades["entry_date"]).dt.year
    
    # Summary
    print(f"\n   Total Trades: {len(df_trades)}")
    print(f"   Avg Return: {df_trades['return_pct'].mean():.2f}%")
    print(f"   Win Rate: {(df_trades['return_pct'] > 0).mean() * 100:.1f}%")
    print(f"   Median Return: {df_trades['return_pct'].median():.2f}%")
    
    # Yearly breakdown
    print(f"\n   📅 YEARLY BREAKDOWN:")
    print(f"   {'-'*50}")
    yearly = df_trades.groupby("year").agg({
        "return_pct": ["count", "mean", lambda x: (x > 0).mean() * 100]
    })
    yearly.columns = ["Trades", "Avg Return %", "Win Rate %"]
    
    positive_years = 0
    total_years = len(yearly)
    for year, row in yearly.iterrows():
        status = "✅" if row["Avg Return %"] > 0 else "❌"
        if row["Avg Return %"] > 0:
            positive_years += 1
        print(f"   {year}: {status} {row['Trades']:.0f} trades, {row['Avg Return %']:+.2f}% avg, {row['Win Rate %']:.1f}% WR")
    
    print(f"   {'-'*50}")
    print(f"   POSITIVE YEARS: {positive_years}/{total_years} ({positive_years/total_years*100:.1f}%)")
    
    return {
        "name": name,
        "select_pct": select_pct,
        "min_drop_pct": min_drop_pct,
        "total_trades": len(df_trades),
        "avg_return": df_trades['return_pct'].mean(),
        "win_rate": (df_trades['return_pct'] > 0).mean() * 100,
        "median_return": df_trades['return_pct'].median(),
        "positive_years": positive_years,
        "total_years": total_years,
    }


# Run all combinations
results_summary = []
for min_drop, select, name in COMBOS:
    result = run_backtest(select, min_drop, name)
    if result:
        results_summary.append(result)

# Final summary table
print("\n" + "=" * 80)
print("📊 FINAL SUMMARY - ALL COMBINATIONS")
print("=" * 80)
print(f"{'Combination':<30} {'Trades':>8} {'Avg Ret':>10} {'Win Rate':>10} {'+Years':>10}")
print("-" * 80)
for r in results_summary:
    print(f"{r['name']:<30} {r['total_trades']:>8} {r['avg_return']:>+9.2f}% {r['win_rate']:>9.1f}% {r['positive_years']:>4}/{r['total_years']:<4}")
print("=" * 80)
