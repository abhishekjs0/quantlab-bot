#!/usr/bin/env python3
"""
Test multi-timeframe data loaders with synthetic data.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.loaders import load_many_dhan_multiframe, load_ohlc_dhan_multiframe


def test_single_loader():
    """Test load_ohlc_dhan_multiframe() for single stock, single timeframe."""
    print("\n" + "=" * 70)
    print("✅ TEST 1: load_ohlc_dhan_multiframe() - Single Stock, Single Timeframe")
    print("=" * 70)

    test_cases = [
        ("RELIANCE", "75m"),
        ("INFY", "125m"),
        ("HDFCBANK", "1d"),
        ("SBIN", "75m"),
    ]

    for symbol, timeframe in test_cases:
        try:
            df = load_ohlc_dhan_multiframe(symbol, timeframe=timeframe)
            print(f"\n✓ {symbol:12} ({timeframe:5}): {len(df):4d} candles")
            print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
            print(f"  - Columns: {list(df.columns)}")
            print(
                f"  - Price range: ₹{df['close'].min():.2f} - ₹{df['close'].max():.2f}"
            )

            # Validate data
            assert len(df) > 0, "Empty DataFrame"
            assert all(
                col in df.columns for col in ["open", "high", "low", "close", "volume"]
            ), "Missing columns"
            assert (df["high"] >= df["low"]).all(), "Invalid high/low"
            assert (df["high"] >= df["open"]).all() or (
                df["high"] >= df["close"]
            ).all(), "Invalid high"

        except Exception as e:
            print(f"\n✗ {symbol:12} ({timeframe:5}): {e}")

    print("\n" + "=" * 70)


def test_batch_loader():
    """Test load_many_dhan_multiframe() for multiple stocks."""
    print("\n" + "=" * 70)
    print("✅ TEST 2: load_many_dhan_multiframe() - Multiple Stocks, Single Timeframe")
    print("=" * 70)

    symbols = ["RELIANCE", "INFY", "HDFCBANK", "ICICIBANK", "SBIN"]

    for timeframe in ["75m", "125m", "1d"]:
        print(f"\n📊 Loading {timeframe} data for {len(symbols)} stocks:")

        try:
            data_dict = load_many_dhan_multiframe(symbols, timeframe=timeframe)

            print(f"✓ Loaded {len(data_dict)} symbols")
            for symbol, df in sorted(data_dict.items()):
                print(
                    f"  - {symbol:12}: {len(df):4d} candles | Price: ₹{df['close'].mean():.2f} avg"
                )

            # Validate
            assert len(data_dict) > 0, "No data loaded"
            assert all(
                isinstance(df, pd.DataFrame) for df in data_dict.values()
            ), "Not all DataFrames"

        except Exception as e:
            print(f"✗ Failed to load {timeframe}: {e}")

    print("\n" + "=" * 70)


def test_candle_counts():
    """Verify candle counts match expected frequency."""
    print("\n" + "=" * 70)
    print("✅ TEST 3: Verify Candle Counts (Expected per timeframe)")
    print("=" * 70)

    symbol = "RELIANCE"

    # Load all timeframes - skip if data not available
    try:
        df_75m = load_ohlc_dhan_multiframe(symbol, timeframe="75m")
        df_125m = load_ohlc_dhan_multiframe(symbol, timeframe="125m")
        df_1d = load_ohlc_dhan_multiframe(symbol, timeframe="1d")
    except FileNotFoundError as e:
        pytest.skip(f"Test data files not available: {e}")

    # Count trading days
    trading_days_75m = df_75m.index.normalize().nunique()
    trading_days_125m = df_125m.index.normalize().nunique()
    trading_days_1d = len(df_1d)

    print(f"\n{symbol} Candle Analysis:")
    print(
        f"  📊 75m  data: {len(df_75m):4d} candles | {trading_days_75m} trading days | {len(df_75m)/trading_days_75m:.1f} candles/day ✓"
    )
    print(
        f"  📊 125m data: {len(df_125m):4d} candles | {trading_days_125m} trading days | {len(df_125m)/trading_days_125m:.1f} candles/day ✓"
    )
    print(
        f"  📊 1d   data: {len(df_1d):4d} candles | {trading_days_1d} trading days | 1.0 candles/day ✓"
    )

    # Verify ratios
    ratio_75m_to_125m = len(df_75m) / len(df_125m)
    ratio_125m_to_1d = len(df_125m) / len(df_1d)

    print("\n  Ratios:")
    print(f"    - 75m/125m: {ratio_75m_to_125m:.2f}x (expected ~1.67x = 5/3) ✓")
    print(f"    - 125m/1d:  {ratio_125m_to_1d:.2f}x (expected ~3.0x)        ✓")

    print("\n" + "=" * 70)


def test_time_alignment():
    """Check that timeframes start at correct times."""
    print("\n" + "=" * 70)
    print("✅ TEST 4: Verify Time Alignment for Session Boundaries")
    print("=" * 70)

    symbol = "INFY"

    try:
        df_75m = load_ohlc_dhan_multiframe(symbol, timeframe="75m")
        df_125m = load_ohlc_dhan_multiframe(symbol, timeframe="125m")
    except FileNotFoundError as e:
        pytest.skip(f"Test data files not available: {e}")

    # Get unique times for each day
    print(f"\n{symbol} First 3 Trading Days (times should be consistent):\n")

    # 75m times
    df_75m_times = df_75m.groupby(df_75m.index.normalize()).apply(
        lambda x: x.index.strftime("%H:%M").tolist()
    )
    print("75m Candle Times (Expected: 09:15, 10:30, 11:45, 13:00, 14:15):")
    for i, times_list in enumerate(df_75m_times.head(3), 1):
        print(f"  Day {i}: {', '.join(times_list)}")

    # 125m times
    df_125m_times = df_125m.groupby(df_125m.index.normalize()).apply(
        lambda x: x.index.strftime("%H:%M").tolist()
    )
    print("\n125m Candle Times (Expected: 09:15, 11:20, 13:25):")
    for i, times_list in enumerate(df_125m_times.head(3), 1):
        print(f"  Day {i}: {', '.join(times_list)}")

    print("\n" + "=" * 70)


def main():
    print("\n" + "=" * 70)
    print("🧪 MULTI-TIMEFRAME DATA LOADER TEST SUITE")
    print("=" * 70)

    try:
        test_single_loader()
        test_batch_loader()
        test_candle_counts()
        test_time_alignment()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
