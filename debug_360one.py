#!/usr/bin/env python3
"""Debug script to trace 360ONE trades through metrics calculation."""

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/abhishekshah/Desktop/quantlab-workspace")

from core.engine import BacktestEngine
from data.loaders import CSVDataLoader
from strategies.kama_crossover import KAMACrossover

# Load 360ONE data
try:
    loader = CSVDataLoader("data/cache")
    df = loader.load_symbol("360ONE", years=1, interval="1d")
    print(f"✅ Loaded 360ONE: {len(df)} bars ({df.index.min()} to {df.index.max()})")
except Exception as e:
    print(f"❌ Error loading 360ONE: {e}")
    sys.exit(1)

# Run backtest
engine = BacktestEngine(initial_capital=100000, position_limit=1, max_pyramiding=1)
strategy = KAMACrossover()
engine.set_strategy(strategy)

print("\n▶️  Running backtest on 360ONE...")
trades_df, equity_df, signals_df = engine.run(df)

print(f"\n📊 Engine output:")
print(f"  Trades: {len(trades_df)} rows")
print(f"  Columns: {list(trades_df.columns)}")

# Check for open trades
if "net_pnl" in trades_df.columns:
    open_trades = trades_df[trades_df["net_pnl"].isna()]
    closed_trades = trades_df[trades_df["net_pnl"].notna()]
    print(f"\n🔍 Trade breakdown:")
    print(f"  Open trades: {len(open_trades)}")
    print(f"  Closed trades: {len(closed_trades)}")
    print(f"  Total: {len(trades_df)}")

print(f"\n📋 All trades:")
print(
    trades_df[
        ["entry_time", "exit_time", "entry_price", "exit_price", "entry_qty", "net_pnl"]
    ].to_string()
)

# Now test the metrics calculation
print(f"\n▶️  Calling compute_trade_metrics_table()...")
from core.metrics import compute_trade_metrics_table

metrics = compute_trade_metrics_table(df, trades_df, bars_per_year=252)
print(f"\n✅ Metrics calculated:")
for key, val in metrics.items():
    print(f"  {key}: {val}")

# Compare with expected
print(f"\n📊 Expected vs Actual:")
print(f"  Expected Profit Factor: 0.0 (all 3 closed trades are losers)")
print(f"  Actual Profit Factor: {metrics.get('ProfitFactor', 'N/A')}")
print(f"  Expected Avg P&L: Around -6.5% (average of -7.45%, -5.29%, -6.98%)")
print(f"  Actual Avg P&L: {metrics.get('AvgProfitPerTradePct', 'N/A'):.2f}%")
print(f"  Expected NumTrades: 4 (1 open + 3 closed)")
print(f"  Actual NumTrades: {metrics.get('NumTrades', 'N/A')}")
