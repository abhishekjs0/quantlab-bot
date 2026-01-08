# Weekly Rotation Experiments Archive
# Combined on 2026-01-08


# ========== FROM: test_weekly_rotation_combos.py ==========

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


# ========== FROM: test_weekly_rotation_nifty.py ==========

#!/usr/bin/env python3
"""
Test Weekly Rotation Strategy - With NIFTY Filter Conditions

Tests all 3 combos with:
- NIFTY UP week condition
- NIFTY DOWN week condition

Settings:
- 10% Fixed Stop Loss
- No filters (ADX disabled)
- Trailing stop: False
- Commission: 0.185% per side (0.37% round trip)
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
    (5.0, 20.0, ">5% drop + B20%"),
    (10.0, 10.0, ">10% drop + B10%"),
    (5.0, 10.0, ">5% drop + B10%"),
]

# NIFTY conditions
NIFTY_CONDITIONS = [
    ("NIFTY UP", True, False),   # (name, require_nifty_up, require_nifty_down)
    ("NIFTY DOWN", False, True),
]

COMMISSION_PCT = 0.185  # 0.37% round trip

print("=" * 90)
print("WEEKLY ROTATION BACKTEST - NIFTY FILTER CONDITIONS")
print("=" * 90)
print(f"Commission: {COMMISSION_PCT}% per side ({COMMISSION_PCT * 2}% round trip)")
print("10% Fixed Stop Loss | No Filters | Trailing Stop: FALSE")
print("=" * 90)

# Load basket
basket_file = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data/baskets/basket_main.txt"
symbols = [s.strip() for s in basket_file.read_text().splitlines() if s.strip() and not s.startswith("#")]
print(f"\n📂 Loading {len(symbols)} symbols from basket_main.txt...")

# Load data (cache only)
data = load_many_india(symbols, "1d", cache=True)
print(f"✅ Loaded {len(data)} symbols")

# Load NIFTY data
print("\n📈 Loading NIFTY 50 data...")
try:
    nifty_data = load_many_india(["NIFTY50"], "1d", cache=True)
    if nifty_data:
        nifty_symbol = list(nifty_data.keys())[0]
        nifty_df = nifty_data[nifty_symbol]
        print(f"✅ Loaded NIFTY data: {nifty_symbol} ({len(nifty_df)} bars)")
    else:
        nifty_df = None
except FileNotFoundError:
    print("❌ NIFTY50 cache not found")
    nifty_df = None

# Compute weekly returns for all symbols
print("\n📊 Computing weekly returns...")
weekly_returns = compute_weekly_returns(data)

# Compute NIFTY weekly returns
nifty_weekly = None
if nifty_df is not None:
    nifty_weekly_dict = compute_weekly_returns({"NIFTY": nifty_df})
    if "NIFTY" in nifty_weekly_dict:
        nifty_weekly = nifty_weekly_dict["NIFTY"]
        print(f"✅ NIFTY weekly returns: {len(nifty_weekly)} weeks")
        
        # Show NIFTY up/down week stats
        up_weeks = (nifty_weekly["pct_return"] >= 0).sum()
        down_weeks = (nifty_weekly["pct_return"] < 0).sum()
        print(f"   NIFTY UP weeks: {up_weeks} | NIFTY DOWN weeks: {down_weeks}")

if nifty_weekly is None:
    print("❌ Could not compute NIFTY weekly returns - skipping NIFTY filter tests")
    sys.exit(1)

# Broker config
broker_config = BrokerConfig(commission_pct=COMMISSION_PCT)


def run_backtest(select_pct: float, min_drop_pct: float, combo_name: str,
                 nifty_condition: str, require_nifty_up: bool, require_nifty_down: bool):
    """Run backtest for a single combination."""
    
    # Compute ranking cache with NIFTY filter
    cache = compute_ranking_cache(
        weekly_returns,
        mode="mean_reversion",
        select_pct=select_pct,
        min_drop_pct=min_drop_pct,
        nifty_weekly=nifty_weekly,
        require_nifty_up=require_nifty_up,
        require_nifty_down=require_nifty_down,
    )
    
    # Set cache on strategy class
    WeeklyMeanReversionStrategy._ranking_cache = cache
    WeeklyMeanReversionStrategy._weekly_returns = weekly_returns
    WeeklyMeanReversionStrategy._cache_loaded = True
    
    n_entries = sum(1 for v in cache.values() if v.get("should_enter", False))
    
    results = []
    for symbol in symbols:
        if symbol not in data:
            continue
        
        df = data[symbol]
        strategy = WeeklyMeanReversionStrategy(
            select_pct=select_pct,
            use_adx_filter=False,
            use_trailing_stop=False,
            fixed_stop_pct=0.10,  # 10% stop loss
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
            if pd.isna(t.get("exit_price")):
                continue
            return_pct = (t["exit_price"] / t["entry_price"] - 1) * 100
            all_trades.append({
                "symbol": symbol,
                "entry_date": t["entry_time"],
                "exit_date": t["exit_time"],
                "return_pct": return_pct,
            })
    
    if not all_trades:
        return None
    
    df_trades = pd.DataFrame(all_trades)
    df_trades["year"] = pd.to_datetime(df_trades["entry_date"]).dt.year
    
    # Yearly breakdown
    yearly = df_trades.groupby("year").agg({
        "return_pct": ["count", "mean", lambda x: (x > 0).mean() * 100]
    })
    yearly.columns = ["Trades", "Avg Return %", "Win Rate %"]
    
    positive_years = sum(1 for _, row in yearly.iterrows() if row["Avg Return %"] > 0)
    total_years = len(yearly)
    
    return {
        "combo_name": combo_name,
        "nifty_condition": nifty_condition,
        "total_trades": len(df_trades),
        "avg_return": df_trades['return_pct'].mean(),
        "win_rate": (df_trades['return_pct'] > 0).mean() * 100,
        "median_return": df_trades['return_pct'].median(),
        "positive_years": positive_years,
        "total_years": total_years,
        "yearly": yearly,
    }


# Run all combinations
all_results = []

for nifty_name, require_up, require_down in NIFTY_CONDITIONS:
    print(f"\n{'='*90}")
    print(f"🔍 TESTING WITH {nifty_name} WEEK CONDITION")
    print(f"{'='*90}")
    
    for min_drop, select, combo_name in COMBOS:
        result = run_backtest(select, min_drop, combo_name, nifty_name, require_up, require_down)
        if result:
            all_results.append(result)
            print(f"\n   {combo_name} + {nifty_name}:")
            print(f"   Trades: {result['total_trades']} | Avg: {result['avg_return']:+.2f}% | WR: {result['win_rate']:.1f}% | +Years: {result['positive_years']}/{result['total_years']}")
        else:
            print(f"\n   {combo_name} + {nifty_name}: ❌ No trades")

# Final summary table
print("\n" + "=" * 90)
print("📊 FINAL SUMMARY - ALL COMBINATIONS WITH NIFTY FILTERS")
print("=" * 90)
print(f"{'Combination':<25} {'NIFTY':<12} {'Trades':>8} {'Avg Ret':>10} {'Win Rate':>10} {'+Years':>10}")
print("-" * 90)

for r in all_results:
    print(f"{r['combo_name']:<25} {r['nifty_condition']:<12} {r['total_trades']:>8} {r['avg_return']:>+9.2f}% {r['win_rate']:>9.1f}% {r['positive_years']:>4}/{r['total_years']:<4}")

print("=" * 90)

# Show detailed yearly breakdown for best performers
print("\n" + "=" * 90)
print("📅 DETAILED YEARLY BREAKDOWN FOR EACH VARIANT")
print("=" * 90)

for r in all_results:
    print(f"\n{r['combo_name']} + {r['nifty_condition']}:")
    print("-" * 60)
    yearly = r["yearly"]
    for year, row in yearly.iterrows():
        status = "✅" if row["Avg Return %"] > 0 else "❌"
        print(f"   {year}: {status} {row['Trades']:.0f} trades, {row['Avg Return %']:+.2f}% avg, {row['Win Rate %']:.1f}% WR")
    print(f"   POSITIVE YEARS: {r['positive_years']}/{r['total_years']}")


# ========== FROM: test_weekly_rotation.py ==========

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
basket_file = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data/baskets/basket_main.txt"
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
