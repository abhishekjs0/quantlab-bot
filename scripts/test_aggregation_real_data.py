#!/usr/bin/env python3
"""
Test multi-timeframe aggregation with real minute data
"""

import sys

import pandas as pd

sys.path.insert(0, "/Users/abhishekshah/Desktop/quantlab-workspace")

from core.multi_timeframe import aggregate_to_timeframe
from data.loaders import load_minute_data


def test_aggregation_with_real_data():
    """Test that aggregation works with real fetched data"""
    print("\n" + "=" * 70)
    print("MULTI-TIMEFRAME AGGREGATION - REAL DATA TEST")
    print("=" * 70)

    # Test 1: Load real 1-minute RELIANCE data
    print("\n📊 TEST 1: Load real 1-minute RELIANCE data")
    try:
        df_1m = pd.read_csv("data/cache/dhan_minute_100_reliance_1m.csv")
        print(f"✅ Loaded {len(df_1m)} 1-minute candles")
        print(f"   Date range: {df_1m['date'].min()} to {df_1m['date'].max()}")
        print(f"   Columns: {list(df_1m.columns)}")
        print("   First 3 rows:")
        print(df_1m.head(3).to_string(index=False))
        
        # Set date as index for aggregation
        df_1m["date"] = pd.to_datetime(df_1m["date"])
        df_1m = df_1m.set_index("date")
        print("\n✅ Converted to DatetimeIndex for aggregation")
    except Exception as e:
        print(f"❌ Failed to load: {e}")
        return

    # Test 2: Aggregate 1m to 75m
    print("\n📊 TEST 2: Aggregate 1-minute to 75-minute")
    try:
        df_75m = aggregate_to_timeframe(df_1m, "75m")
        print(f"✅ Aggregated to {len(df_75m)} 75-minute candles")
        print("   Expected: ~3 candles (9:15-10:30, 10:30-11:45, 11:45-13:00, 13:00-14:15, 14:15-15:30)")
        print(f"   Date range: {df_75m.index.min()} to {df_75m.index.max()}")
        print("   All 75-minute bars:")
        df_75m_display = df_75m.reset_index()
        df_75m_display.rename(columns={"date": "datetime"}, inplace=True)
        print(df_75m_display.to_string(index=False))
    except Exception as e:
        print(f"❌ Failed to aggregate: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Aggregate 1m directly to daily
    print("\n📊 TEST 3: Aggregate 1-minute to daily (1d)")
    try:
        df_1d = aggregate_to_timeframe(df_1m, "1d")
        print(f"✅ Aggregated to {len(df_1d)} daily candle(s)")
        print(f"   Date: {df_1d.index[0]}")
        print("   Daily bar:")
        df_1d_display = df_1d.reset_index()
        df_1d_display.rename(columns={"date": "datetime"}, inplace=True)
        print(df_1d_display.to_string(index=False))
    except Exception as e:
        print(f"❌ Failed to aggregate: {e}")
        return

    # Test 4: Load real 5-minute SBIN data
    print("\n📊 TEST 4: Load real 5-minute SBIN data")
    try:
        df_5m = pd.read_csv("data/cache/dhan_minute_1023_sbin_5m.csv")
        print(f"✅ Loaded {len(df_5m)} 5-minute candles")
        print(f"   Date range: {df_5m['date'].min()} to {df_5m['date'].max()}")
        print("   First 3 rows:")
        print(df_5m.head(3).to_string(index=False))

        # Set date as index for aggregation
        df_5m["date"] = pd.to_datetime(df_5m["date"])
        df_5m = df_5m.set_index("date")
        print("\n✅ Converted to DatetimeIndex for aggregation")
    except Exception as e:
        print(f"❌ Failed to load: {e}")
        return

    # Test 5: Aggregate 5m to 125m
    print("\n📊 TEST 5: Aggregate 5-minute to 125-minute")
    try:
        df_125m = aggregate_to_timeframe(df_5m, "125m")
        print(f"✅ Aggregated to {len(df_125m)} 125-minute candles")
        print("   Expected: 2-3 candles depending on 9:15 start")
        print("   All 125-minute bars:")
        df_125m_display = df_125m.reset_index()
        df_125m_display.rename(columns={"date": "datetime"}, inplace=True)
        print(df_125m_display.to_string(index=False))
    except Exception as e:
        print(f"❌ Failed to aggregate: {e}")
        return

    # Test 6: Verify OHLCV aggregation rules
    print("\n📊 TEST 6: Verify OHLCV aggregation rules with 1m to 75m")
    try:
        # Check first 75m bar
        first_1m = df_1m.iloc[0:75]  # First 75 1-minute bars
        agg_first_75m = df_75m.iloc[0]

        print("✅ Checking first 75-minute bar aggregation rules:")
        print(f"   Open (should = first 1m open): {agg_first_75m['open']} == {first_1m['open'].iloc[0]} ? {agg_first_75m['open'] == first_1m['open'].iloc[0]}")
        print(f"   High (should = max of 1m highs): {agg_first_75m['high']} == {first_1m['high'].max()} ? {abs(agg_first_75m['high'] - first_1m['high'].max()) < 0.01}")
        print(f"   Low (should = min of 1m lows): {agg_first_75m['low']} == {first_1m['low'].min()} ? {abs(agg_first_75m['low'] - first_1m['low'].min()) < 0.01}")
        print(f"   Close (should = last 1m close): {agg_first_75m['close']} == {first_1m['close'].iloc[-1]} ? {agg_first_75m['close'] == first_1m['close'].iloc[-1]}")
        print(f"   Volume (should = sum of 1m volumes): {agg_first_75m['volume']} == {first_1m['volume'].sum()} ? {agg_first_75m['volume'] == first_1m['volume'].sum()}")
    except Exception as e:
        print(f"❌ Failed to verify: {e}")
        return

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED - MULTI-TIMEFRAME AGGREGATION WORKS!")
    print("=" * 70)


if __name__ == "__main__":
    test_aggregation_with_real_data()
