"""
Pytest Configuration and Fixtures
==================================

Provides mock data fixtures for CI environments without live cache.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ============================================================================
# Mock Data Generators
# ============================================================================

def generate_ohlcv_data(
    n_days: int = 252,
    start_date: str = "2023-01-01",
    base_price: float = 1000.0,
    volatility: float = 0.02,
    trend: float = 0.0005,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic OHLCV data for testing.

    Args:
        n_days: Number of trading days
        start_date: Start date for the series
        base_price: Starting price
        volatility: Daily volatility (std of returns)
        trend: Daily drift (mean of returns)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: open, high, low, close, volume
    """
    np.random.seed(seed)

    # Generate dates (trading days only)
    dates = pd.date_range(start_date, periods=n_days, freq="B")

    # Generate log returns with trend and volatility
    returns = np.random.normal(trend, volatility, n_days)
    
    # Calculate close prices
    log_prices = np.log(base_price) + np.cumsum(returns)
    close = np.exp(log_prices)

    # Generate realistic OHLC from close
    intraday_range = np.random.uniform(0.005, 0.02, n_days)
    high = close * (1 + intraday_range * np.random.uniform(0.5, 1.0, n_days))
    low = close * (1 - intraday_range * np.random.uniform(0.5, 1.0, n_days))
    
    # Open is previous close with overnight gap
    overnight_gap = np.random.normal(0, 0.003, n_days)
    open_prices = np.roll(close, 1) * (1 + overnight_gap)
    open_prices[0] = base_price

    # Ensure OHLC consistency
    high = np.maximum(high, np.maximum(open_prices, close))
    low = np.minimum(low, np.minimum(open_prices, close))

    # Generate volume with some pattern
    base_volume = np.random.randint(500000, 2000000, n_days)
    volume = base_volume * (1 + np.abs(returns) * 10)  # Higher volume on big moves

    df = pd.DataFrame(
        {
            "open": open_prices,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume.astype(int),
        },
        index=dates,
    )
    df.index.name = "date"

    return df


def generate_weekly_data(daily_df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to weekly OHLCV."""
    weekly = daily_df.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return weekly.dropna()


def generate_vix_data(
    n_days: int = 252,
    start_date: str = "2023-01-01",
    base_vix: float = 15.0,
    seed: int = 43,
) -> pd.DataFrame:
    """Generate synthetic VIX data."""
    np.random.seed(seed)

    dates = pd.date_range(start_date, periods=n_days, freq="B")
    
    # VIX mean-reverts around base level
    vix = np.zeros(n_days)
    vix[0] = base_vix
    
    for i in range(1, n_days):
        # Mean reversion with some random walk
        mean_revert = 0.05 * (base_vix - vix[i - 1])
        shock = np.random.normal(0, 1.5)
        vix[i] = max(8, min(80, vix[i - 1] + mean_revert + shock))

    return pd.DataFrame({"vix": vix}, index=dates)


def generate_basket_symbols(n_symbols: int = 10) -> list[str]:
    """Generate a list of mock symbol names."""
    return [f"STOCK{i:03d}_NS" for i in range(1, n_symbols + 1)]


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Fixture: 1 year of daily OHLCV data."""
    return generate_ohlcv_data(n_days=252)


@pytest.fixture
def sample_ohlcv_short() -> pd.DataFrame:
    """Fixture: 60 days of daily OHLCV data for quick tests."""
    return generate_ohlcv_data(n_days=60)


@pytest.fixture
def sample_ohlcv_trending() -> pd.DataFrame:
    """Fixture: Trending market data (upward bias)."""
    return generate_ohlcv_data(n_days=252, trend=0.002, volatility=0.015)


@pytest.fixture
def sample_ohlcv_volatile() -> pd.DataFrame:
    """Fixture: High volatility market data."""
    return generate_ohlcv_data(n_days=252, trend=0.0, volatility=0.04)


@pytest.fixture
def sample_weekly() -> pd.DataFrame:
    """Fixture: Weekly OHLCV data."""
    daily = generate_ohlcv_data(n_days=252)
    return generate_weekly_data(daily)


@pytest.fixture
def sample_vix() -> pd.DataFrame:
    """Fixture: VIX data for the same period."""
    return generate_vix_data(n_days=252)


@pytest.fixture
def sample_basket() -> Dict[str, pd.DataFrame]:
    """Fixture: Multiple symbols for basket testing."""
    symbols = generate_basket_symbols(5)
    basket = {}
    for i, symbol in enumerate(symbols):
        basket[symbol] = generate_ohlcv_data(
            n_days=252,
            base_price=500 + i * 200,
            seed=42 + i,
        )
    return basket


@pytest.fixture
def temp_cache_dir(tmp_path) -> Path:
    """Fixture: Temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Fixture: Mock backtest configuration."""
    return {
        "initial_capital": 100000.0,
        "trading_days_per_year": 245,
        "risk_free_rate": 0.06,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
    }


# ============================================================================
# Test Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "requires_cache: marks tests that need live cache data"
    )


# ============================================================================
# Skip Conditions
# ============================================================================

HAS_CACHE = Path(ROOT / "cache").exists() and any(
    Path(ROOT / "cache").glob("*.parquet")
)

requires_cache = pytest.mark.skipif(
    not HAS_CACHE,
    reason="Requires cache data (run: python scripts/fetch_groww_daily_data.py)",
)
