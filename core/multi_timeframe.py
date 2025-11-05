"""Multi-timeframe data handling for strategy backtesting.

Supports:
- Running strategies on different timeframes (daily, 75min, 125min, etc.)
- Aggregating minute candles from Dhan API to desired timeframe
- Single strategy togglable to run on any timeframe

ARCHITECTURE:
- Dhan API provides minute-wise candles
- Aggregate minute data to target timeframe (75min, 125min, etc.)
- Single strategy runs on selected timeframe
- Strategy logic remains unchanged, only input timeframe changes

USAGE:
    # Load minute candles from Dhan
    minute_df = load_minute_data(symbol, start_date, end_date)

    # Aggregate to 75-min candles
    df_75m = aggregate_to_timeframe(minute_df, "75m")

    # Run strategy on 75-min bars
    engine = BacktestEngine(df_75m, strategy, config)
    trades_df, equity_df, signals_df = engine.run()
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TimeframeData:
    """Holds OHLCV data for a specific timeframe."""

    symbol: str
    interval: str  # "1m", "75m", "125m", "1d", etc.
    df: pd.DataFrame  # DatetimeIndex, columns: open, high, low, close, volume


def aggregate_to_timeframe(df: pd.DataFrame, target_interval: str) -> pd.DataFrame:
    """Aggregate minute candles to target timeframe.

    Dhan API provides minute-wise candles. This function aggregates them
    to desired timeframes (75m, 125m, etc.) for strategy testing.

    OHLCV aggregation rules:
    - Open: First candle's open
    - High: Maximum high across all candles
    - Low: Minimum low across all candles
    - Close: Last candle's close
    - Volume: Sum of all volumes

    Args:
        df: DataFrame with minute OHLCV (DatetimeIndex, columns: open, high, low, close, volume)
        target_interval: Target interval like "75m", "125m", "1h", "1d", etc.

    Returns:
        Aggregated DataFrame with target timeframe candles

    Example:
        >>> minute_df = load_from_dhan(symbol)  # Minute candles
        >>> df_75m = aggregate_to_timeframe(minute_df, "75m")
        >>> df_125m = aggregate_to_timeframe(minute_df, "125m")
    """
    if target_interval == "1m":
        return df.copy()

    # Parse interval (e.g., "75m" -> 75, "1h" -> 60, "1d" -> 1440)
    import re

    match = re.match(r"(\d+)([mhd])", target_interval.lower())
    if not match:
        raise ValueError(
            f"Invalid interval format: {target_interval}. Use like '75m', '1h', '1d'"
        )

    qty, unit = int(match.group(1)), match.group(2)

    # Convert to minutes
    if unit == "m":
        freq_minutes = qty
    elif unit == "h":
        freq_minutes = qty * 60
    elif unit == "d":
        freq_minutes = qty * 24 * 60
    else:
        raise ValueError(
            f"Unknown unit: {unit}. Use m (minutes), h (hours), or d (days)"
        )

    # Aggregate using pandas resample
    aggregated = df.resample(f"{freq_minutes}min").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    # Remove rows with NaN (gaps in trading, e.g., overnight)
    return aggregated.dropna()


def load_multi_timeframe(
    daily_data: dict[str, pd.DataFrame],
    minute_intervals: list[str] | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Load or generate multiple timeframes for backtesting.

    Args:
        daily_data: Dict mapping symbols to daily DataFrames
        minute_intervals: List of minute intervals to generate (e.g., ["75m", "15m"])
                         If None, returns only daily data

    Returns:
        Dict mapping symbols to dict of timeframes:
        {
            "SBIN": {
                "1d": df_daily,
                "75m": df_75m,
                "15m": df_15m
            },
            ...
        }
    """
    result = {}

    if minute_intervals is None:
        minute_intervals = []

    for symbol, daily_df in daily_data.items():
        result[symbol] = {"1d": daily_df.copy()}

        for interval in minute_intervals:
            result[symbol][interval] = aggregate_to_timeframe(daily_df, interval)

    return result


def validate_timeframe_alignment(
    timeframe_data: dict[str, dict[str, pd.DataFrame]],
) -> bool:
    """Validate that all timeframes for a symbol have aligned timestamps.

    For backtesting, minute candles should align with daily boundaries.

    Returns:
        True if valid, raises ValueError if not
    """
    for symbol, timeframes in timeframe_data.items():
        daily_dates = set(pd.to_datetime(timeframes["1d"].index).normalize())

        for interval, df in timeframes.items():
            if interval == "1d":
                continue

            minute_dates = set(pd.to_datetime(df.index).normalize())
            if not minute_dates.issubset(daily_dates):
                raise ValueError(
                    f"Symbol {symbol}: {interval} dates not subset of daily dates"
                )

    return True
