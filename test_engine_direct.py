#!/usr/bin/env python3
"""Test to directly inspect engine output"""

import sys

sys.path.insert(0, "/Users/abhishekshah/Desktop/quantlab-workspace")

import pandas as pd

from core.config import BrokerConfig
from core.engine import BacktestEngine
from data.loaders import load_many_dhan_multiframe
from strategies.kama_crossover import KAMACrossoverStrategy

# Load INFY data from cache
try:
    df = pd.read_csv("data/cache/dhan_INFY_1d.csv")
    if "Date" in df.columns:
        df.rename(columns={"Date": "date"}, inplace=True)
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

    print(f"Loaded {len(df)} bars of INFY 1d data")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Date range: {df.index[0]} to {df.index[-1]}")

    # Run backtest
    cfg = BrokerConfig(
        initial_capital=100000.0,
        commission_pct=0.11,
        execute_on_next_open=False,
    )

    strategy = KAMACrossoverStrategy(cfg)
    engine = BacktestEngine(df, strategy, cfg)

    trades_df, equity_df, signals_df = engine.run()

    print(f"\n✅ Backtest complete")
    print(f"Total trades: {len(trades_df)}")

    # Find the trade with exit price 1853
    print(f"\n=== LOOKING FOR TRADE WITH EXIT PRICE 1853 ===")
    matching_trades = trades_df[trades_df["exit_price"] == 1853]

    if matching_trades.empty:
        print("No exact match for exit price 1853")
        print(f"\nAll closed trades (exit_price not null):")
        closed_trades = trades_df[trades_df["exit_time"].notna()]
        print(
            closed_trades[
                [
                    "entry_price",
                    "entry_qty",
                    "exit_price",
                    "commission_entry",
                    "commission_exit",
                    "gross_pnl",
                    "net_pnl",
                ]
            ].tail(20)
        )
    else:
        row = matching_trades.iloc[0]
        print(f"Found trade with exit price 1853:")
        print(f"  entry_price: {row['entry_price']}")
        print(f"  exit_price: {row['exit_price']}")
        print(f"  entry_qty: {row['entry_qty']}")
        print(f"  entry_time: {row['entry_time']}")
        print(f"  exit_time: {row['exit_time']}")
        print(f"  commission_entry: {row['commission_entry']}")
        print(f"  commission_exit: {row['commission_exit']}")
        print(f"  gross_pnl: {row['gross_pnl']}")
        print(f"  net_pnl: {row['net_pnl']}")

        # Verify calculation
        expected_commission_total = row["commission_entry"] + row["commission_exit"]
        expected_net = row["gross_pnl"] - expected_commission_total

        print(f"\n  Expected calculation:")
        print(f"    Total commission: {expected_commission_total}")
        print(f"    Expected net P&L: {expected_net}")

except Exception as e:
    print(f"Error: {e}")
    import traceback

    traceback.print_exc()
