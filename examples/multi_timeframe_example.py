"""Example: Loading and aggregating minute candles for multi-timeframe backtesting.

This demonstrates how to:
1. Load minute-wise candles from Dhan historical data
2. Aggregate them to different timeframes (75m, 125m, daily)
3. Prepare data for strategy backtesting
"""

import pandas as pd

from core.multi_timeframe import aggregate_to_timeframe
from data.loaders import load_minute_data


# Example 1: Load minute data for a symbol
# ==========================================

# Load minute candles for SBIN (SECURITY_ID: 1023)
minute_df = load_minute_data(1023)
print(f"Loaded {len(minute_df)} minute candles for SBIN")
print(f"Date range: {minute_df.index[0]} to {minute_df.index[-1]}")
print(f"Columns: {list(minute_df.columns)}")


# Example 2: Aggregate to different timeframes
# =============================================

# Aggregate 1-minute data to 75-minute candles
df_75m = aggregate_to_timeframe(minute_df, "75m")
print(f"\n75-min candles: {len(df_75m)} bars")

# Aggregate to 125-minute candles
df_125m = aggregate_to_timeframe(minute_df, "125m")
print(f"125-min candles: {len(df_125m)} bars")

# Aggregate to daily candles
df_1d = aggregate_to_timeframe(minute_df, "1d")
print(f"Daily candles: {len(df_1d)} bars")


# Example 3: Validate OHLCV data
# ===============================

def validate_ohlcv(df, name):
    """Validate OHLCV data integrity."""
    print(f"\n{name} OHLCV Validation:")
    print(f"  - Total bars: {len(df)}")
    print(f"  - Date range: {df.index[0]} to {df.index[-1]}")
    print(f"  - High >= Low: {(df['high'] >= df['low']).all()}")
    print(f"  - Close in [Low, High]: {((df['close'] >= df['low']) & (df['close'] <= df['high'])).all()}")
    print(f"  - No NaN values: {not df[['open', 'high', 'low', 'close', 'volume']].isnull().any().any()}")


validate_ohlcv(df_75m, "75-min")
validate_ohlcv(df_125m, "125-min")
validate_ohlcv(df_1d, "Daily")


# Example 4: Prepare for strategy backtesting
# ============================================

print("\n\nReady for strategy backtesting!")
print("Next steps:")
print("1. Create strategy instance: strategy = EMAcrossoverStrategy()")
print("2. Create engine: engine = BacktestEngine(df_75m, strategy, broker_config)")
print("3. Run backtest: trades_df, equity_df, signals_df = engine.run()")


# Example 5: Load data for multiple symbols
# ==========================================

print("\n\nMultiple symbols example:")
security_ids = [1023, 1038, 10397]  # SBIN, HDFC, LT

symbol_data = {}
for secid in security_ids:
    try:
        minute_data = load_minute_data(secid)
        df_75m = aggregate_to_timeframe(minute_data, "75m")
        symbol_data[secid] = df_75m
        print(f"Symbol {secid}: {len(df_75m)} 75-min candles loaded")
    except FileNotFoundError:
        print(f"Symbol {secid}: Data not found")

print(f"Successfully loaded data for {len(symbol_data)} symbols")


# Example 6: Timeframe aggregation statistics
# ============================================

print("\n\nTimeframe Aggregation Statistics:")
print("=" * 60)

def print_aggregation_stats(minute_df, timeframe, target_str):
    """Print aggregation statistics for a timeframe."""
    df_target = aggregate_to_timeframe(minute_df, target_str)
    reduction_pct = 100 * (1 - len(df_target) / len(minute_df))
    avg_vol = df_target["volume"].mean()

    print(f"\n{timeframe}:")
    print(f"  Minute bars: {len(minute_df):,}")
    print(f"  Aggregated bars: {len(df_target):,}")
    print(f"  Reduction: {reduction_pct:.1f}%")
    print(f"  Avg volume: {avg_vol:,.0f}")


print_aggregation_stats(minute_df, "75-minute", "75m")
print_aggregation_stats(minute_df, "125-minute", "125m")
print_aggregation_stats(minute_df, "1-day", "1d")

