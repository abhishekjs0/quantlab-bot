"""Multi-timeframe data handling for intraday trading.

Supports:
- Loading daily candles
- Generating minute-based candles (75min, 15min, etc.) from daily data via aggregation
- Loading pre-cached minute candles
- Synchronizing positions across timeframes

ARCHITECTURE:
- Daily strategy runs on daily candles (existing: EMA crossover, Ichimoku, Knoxville)
- Intraday strategy runs on 75-min candles (new: Phase A)
- Both share cash pool via T+1 manager
- Positions tracked separately, coordinated via engine
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class TimeframeData:
    """Holds OHLCV data for a specific timeframe."""

    symbol: str
    interval: str  # "1d", "75m", "15m", etc.
    df: pd.DataFrame  # DatetimeIndex, columns: open, high, low, close, volume


def resample_to_candles(
    daily_df: pd.DataFrame, target_interval: str
) -> pd.DataFrame:
    """Resample daily OHLCV to target minute interval.

    NOT RECOMMENDED for production - minute candles should be fetched from API.
    This is for backtesting only when minute data is unavailable.

    This naive aggregation will NOT produce accurate minute candles from daily data.
    Use only for testing/prototyping.

    Args:
        daily_df: DataFrame with daily OHLCV (DatetimeIndex, columns: open, high, low, close, volume)
        target_interval: Target interval like "75m", "15m", etc.

    Returns:
        Resampled DataFrame with minute candles
    """
    if target_interval == "1d":
        return daily_df.copy()

    # Parse interval
    import re

    match = re.match(r"(\d+)([mhd])", target_interval.lower())
    if not match:
        raise ValueError(f"Invalid interval format: {target_interval}")

    qty, unit = int(match.group(1)), match.group(2)

    # Convert to minutes
    if unit == "m":
        freq_minutes = qty
    elif unit == "h":
        freq_minutes = qty * 60
    elif unit == "d":
        freq_minutes = qty * 24 * 60
    else:
        raise ValueError(f"Unknown unit: {unit}")

    # CAVEAT: This creates artificial minute candles by repeating daily OHLCV
    # Real minute candles would have intrabar volatility
    # Only useful for testing strategy logic
    resampled = daily_df.resample(f"{freq_minutes}min").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )

    return resampled.dropna()


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
            result[symbol][interval] = resample_to_candles(daily_df, interval)

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
