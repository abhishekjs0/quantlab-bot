"""Tests for multi-timeframe data handling."""

import pandas as pd
import pytest

from core.multi_timeframe import (
    aggregate_to_timeframe,
    load_multi_timeframe,
    validate_timeframe_alignment,
)


@pytest.fixture
def sample_daily_df():
    """Create sample daily OHLCV data."""
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(10)],
            "high": [101.0 + i for i in range(10)],
            "low": [99.0 + i for i in range(10)],
            "close": [100.5 + i for i in range(10)],
            "volume": [1000000] * 10,
        },
        index=dates,
    )


def test_resample_to_daily(sample_daily_df):
    """Resample daily to daily should return same data."""
    result = aggregate_to_timeframe(sample_daily_df, "1d")
    assert len(result) == len(sample_daily_df)
    assert result.index[0] == sample_daily_df.index[0]


def test_resample_to_75min(sample_daily_df):
    """Resample daily to 75min candles."""
    result = aggregate_to_timeframe(sample_daily_df, "75m")

    # Should have same number of rows (daily data resampled at 75min intervals)
    # NOTE: With daily data as input, resample creates one candle per day
    # Real minute candles would need minute-level input data
    assert len(result) >= len(sample_daily_df) * 0.8  # Allow for gaps

    # Should have same columns
    assert set(result.columns) == {"open", "high", "low", "close", "volume"}

    # No NaN values
    assert not result.isnull().any().any()


def test_resample_invalid_interval(sample_daily_df):
    """Invalid interval format should raise ValueError."""
    with pytest.raises(ValueError):
        aggregate_to_timeframe(sample_daily_df, "invalid")


def test_load_multi_timeframe_no_minutes(sample_daily_df):
    """Load multi-timeframe with only daily data."""
    data = {"SBIN": sample_daily_df}
    result = load_multi_timeframe(data, minute_intervals=None)

    assert "SBIN" in result
    assert "1d" in result["SBIN"]
    assert len(result["SBIN"]) == 1  # Only daily


def test_load_multi_timeframe_with_minutes(sample_daily_df):
    """Load multi-timeframe with daily and minute intervals."""
    data = {"SBIN": sample_daily_df}
    result = load_multi_timeframe(data, minute_intervals=["75m", "15m"])

    assert "SBIN" in result
    assert "1d" in result["SBIN"]
    assert "75m" in result["SBIN"]
    assert "15m" in result["SBIN"]

    # With daily input data, minute resampling doesn't increase row count significantly
    # Real minute data would come from API
    assert len(result["SBIN"]["75m"]) >= len(result["SBIN"]["1d"]) * 0.8
    assert len(result["SBIN"]["15m"]) >= len(result["SBIN"]["1d"]) * 0.8


def test_load_multi_timeframe_multiple_symbols(sample_daily_df):
    """Load multi-timeframe for multiple symbols."""
    data = {"SBIN": sample_daily_df, "INFY": sample_daily_df.copy()}
    result = load_multi_timeframe(data, minute_intervals=["75m"])

    assert len(result) == 2
    assert "SBIN" in result
    assert "INFY" in result


def test_validate_timeframe_alignment(sample_daily_df):
    """Validate that timeframes are aligned."""
    timeframe_data = {
        "SBIN": {
            "1d": sample_daily_df,
            "75m": aggregate_to_timeframe(sample_daily_df, "75m"),
        }
    }

    # Should not raise
    assert validate_timeframe_alignment(timeframe_data) is True


def test_resample_preserves_hlc_properties(sample_daily_df):
    """Aggregated candles should maintain high >= low, close between high and low."""
    result = aggregate_to_timeframe(sample_daily_df, "75m")

    # High >= Low for all rows
    assert (result["high"] >= result["low"]).all()

    # Close between Low and High
    assert (result["close"] >= result["low"]).all()
    assert (result["close"] <= result["high"]).all()

    # Open between Low and High
    assert (result["open"] >= result["low"]).all()
    assert (result["open"] <= result["high"]).all()
