#!/usr/bin/env python3
"""Test weekly rotation: Bottom 20% + >10% drop"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from pathlib import Path
from core.loaders import load_many_india
from core.engine import BacktestEngine
from core.config import BrokerConfig

# Import strategy and helper functions
from strategies.weekly_rotation import (
    WeeklyMeanReversionStrategy,
    compute_weekly_returns,
    compute_ranking_cache,
)

# Parameters to test
SELECT_PCT = 20.0  # Bottom 20%
MIN_DROP_PCT = 10.0  # >10% drop required

print("=" * 70)
print(f"WEEKLY ROTATION BACKTEST")
print(f"Settings: Bottom {SELECT_PCT}% + >{MIN_DROP_PCT}% drop")
print("=" * 70)

# Load basket
basket_file = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data/basket_main.txt"
symbols = [s.strip() for s in basket_file.read_text().splitlines() if s.strip() and not s.startswith("#")]
print(f"\n📂 Loading {len(symbols)} symbols from basket_main.txt...")

# Load data (cache only)
data = load_many_india(symbols, "1d", cache=True)
print(f"✅ Loaded {len(data)} symbols")

# Compute weekly returns
print("\n📊 Computing weekly returns...")
weekly_returns = compute_weekly_returns(data)

# Compute ranking cache with our parameters
print(f"🔢 Computing ranking cache (B{SELECT_PCT}% + >{MIN_DROP_PCT}% drop)...")
cache = compute_ranking_cache(
    weekly_returns,
    mode="mean_reversion",
    select_pct=SELECT_PCT,
    min_drop_pct=MIN_DROP_PCT,
)

# Set cache on strategy class
WeeklyMeanReversionStrategy._ranking_cache = cache
WeeklyMeanReversionStrategy._weekly_returns = weekly_returns
WeeklyMeanReversionStrategy._cache_loaded = True
WeeklyMeanReversionStrategy._save_cache_to_file()

# Count how many entries we have
n_entries = sum(1 for v in cache.values() if v.get("should_enter", False))
print(f"✅ Cache ready: {n_entries} potential entries across all symbols/weeks")

# Run backtest
print("\n🚀 Running backtest...")
broker_config = BrokerConfig(
    commission_pct=0.10,  # 0.1% per side
)

results = []
for symbol in symbols:
    if symbol not in data:
        continue
    
    df = data[symbol]
    strategy = WeeklyMeanReversionStrategy(
        select_pct=SELECT_PCT,
    )
    
    # Correct order: df, strategy, cfg
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
    print("\n❌ No trades generated!")
    sys.exit(0)

df_trades = pd.DataFrame(all_trades)
df_trades["year"] = pd.to_datetime(df_trades["entry_date"]).dt.year

print("\n" + "=" * 70)
print("📊 RESULTS: Bottom 20% + >10% Drop Weekly Rotation")
print("=" * 70)

print(f"\nTotal Trades: {len(df_trades)}")
print(f"Avg Return: {df_trades['return_pct'].mean():.2f}%")
print(f"Win Rate: {(df_trades['return_pct'] > 0).mean() * 100:.1f}%")
print(f"Median Return: {df_trades['return_pct'].median():.2f}%")

# Yearly breakdown
print("\n📅 YEARLY BREAKDOWN:")
print("-" * 50)
yearly = df_trades.groupby("year").agg({
    "return_pct": ["count", "mean", lambda x: (x > 0).mean() * 100]
})
yearly.columns = ["Trades", "Avg Return %", "Win Rate %"]

positive_years = 0
for year, row in yearly.iterrows():
    status = "✅" if row["Avg Return %"] > 0 else "❌"
    if row["Avg Return %"] > 0:
        positive_years += 1
    print(f"{year}: {status} {row['Trades']:.0f} trades, {row['Avg Return %']:+.2f}% avg, {row['Win Rate %']:.1f}% WR")

print("-" * 50)
print(f"POSITIVE YEARS: {positive_years}/{len(yearly)} ({positive_years/len(yearly)*100:.1f}%)")
