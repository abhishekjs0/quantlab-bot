#!/usr/bin/env python3
"""Debug script to verify BacktestEngine trade generation for IRCTC."""

import pandas as pd

from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.registry import make_strategy
from data.loaders import load_many_india

# Load IRCTC data
print("Loading IRCTC data...")
data = load_many_india(["IRCTC"], interval="1d")

if "IRCTC" not in data:
    print("ERROR: IRCTC not found in loaded data")
    exit(1)

irctc_data = data["IRCTC"]
print(f"IRCTC data shape: {irctc_data.shape}")
print(f"Date range: {irctc_data.index.min()} to {irctc_data.index.max()}")

# Filter to May 2025 for investigation
may_2025_idx = (irctc_data.index.year == 2025) & (irctc_data.index.month == 5)
may_2025 = irctc_data[may_2025_idx]
print(f"May 2025 data ({len(may_2025)} bars):")
print(may_2025[["open", "high", "low", "close"]])

# Run strategy on IRCTC
print("\n" + "=" * 80)
print("Running KAMA Crossover strategy on IRCTC...")
print("=" * 80)

strategy = make_strategy("kama_crossover", "{}")
broker_config = BrokerConfig()
engine = BacktestEngine(irctc_data, strategy, broker_config)

trades, equity, _ = engine.run()

print(f"Total trades generated: {len(trades)}")
print("Trade columns:", trades.columns.tolist())
print("Trade details:")
print(trades.to_string())

# Check for May 18 trades specifically
print("\n" + "=" * 80)
print("Looking for May 18, 2025 entry date...")
print("=" * 80)

may_18_trades = trades[trades["entry_date"] == "2025-05-18"]
if len(may_18_trades) > 0:
    print(f"Found {len(may_18_trades)} trade(s) entered on May 18:")
    print(
        may_18_trades[
            [
                "entry_price",
                "entry_signal",
                "exit_date",
                "exit_price",
                "exit_signal",
                "net_pnl",
            ]
        ].to_string()
    )
else:
    print("No trades entered on May 18")

# Check KAMA indicators on May 18
print("\n" + "=" * 80)
print("Checking KAMA indicator values around May 18...")
print("=" * 80)

# Get the bars around May 18
around_may_18 = irctc_data.loc["2025-05-10":"2025-05-25"]
print("Bars from May 10-25 (Close prices):")
print(around_may_18[["close"]])
