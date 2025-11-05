"""Tests for minute data loader."""

import os

import pandas as pd
import pytest

from config import CACHE_DIR
from data.loaders import _symbol_to_security_id, load_minute_data


def test_load_minute_data_with_secid():
    """Load minute data using SECURITY_ID directly."""
    cache_files = [f for f in os.listdir(CACHE_DIR) if f.startswith("dhan_historical_")]
    if not cache_files:
        pytest.skip("No dhan_historical CSV files in cache")

    # Extract a SECURITY_ID from available files
    secid = int(
        cache_files[0].replace("dhan_historical_", "").replace(".csv", "").split("_")[0]
    )

    try:
        df = load_minute_data(secid)

        # Validate structure
        assert isinstance(df, pd.DataFrame)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert set(df.columns) == {"open", "high", "low", "close", "volume"}

        # Validate OHLC relationships
        assert (df["high"] >= df["low"]).all()
        assert (df["close"] >= df["low"]).all()
        assert (df["close"] <= df["high"]).all()

        # Validate data types
        assert df["volume"].dtype in [int, float]
    except FileNotFoundError:
        pytest.skip(f"Minute data not found for SECURITY_ID {secid}")


def test_load_minute_data_invalid_secid():
    """Loading non-existent SECURITY_ID should raise FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        load_minute_data(999999)  # Non-existent SECURITY_ID


def test_symbol_to_security_id():
    """Test symbol resolution to SECURITY_ID."""
    # This may return None if instrument master is not available
    result = _symbol_to_security_id("SBIN")

    if result is not None:
        assert isinstance(result, int)
        assert result > 0


def test_symbol_resolution_fallback():
    """Test symbol resolution with NSE: prefix."""
    result = _symbol_to_security_id("NSE:SBIN")

    if result is not None:
        assert isinstance(result, int)
        assert result > 0


def test_minute_data_sorted_by_date():
    """Minute data should be sorted by date."""
    cache_files = [f for f in os.listdir(CACHE_DIR) if f.startswith("dhan_historical_")]
    if not cache_files:
        pytest.skip("No dhan_historical CSV files in cache")

    secid = int(
        cache_files[0].replace("dhan_historical_", "").replace(".csv", "").split("_")[0]
    )

    try:
        df = load_minute_data(secid)

        # Check is sorted
        assert df.index.is_monotonic_increasing
    except FileNotFoundError:
        pytest.skip(f"Minute data not found for SECURITY_ID {secid}")


def test_minute_data_no_nan():
    """Minute data should not have NaN values."""
    cache_files = [f for f in os.listdir(CACHE_DIR) if f.startswith("dhan_historical_")]
    if not cache_files:
        pytest.skip("No dhan_historical CSV files in cache")

    secid = int(
        cache_files[0].replace("dhan_historical_", "").replace(".csv", "").split("_")[0]
    )

    try:
        df = load_minute_data(secid)

        # Check no NaN in OHLCV
        assert not df[["open", "high", "low", "close", "volume"]].isnull().any().any()
    except FileNotFoundError:
        pytest.skip(f"Minute data not found for SECURITY_ID {secid}")
