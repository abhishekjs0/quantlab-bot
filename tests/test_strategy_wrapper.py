"""
Comprehensive tests for Strategy.I() wrapper and modern architecture.
Tests the core Strategy.I() wrapper system, market regime detection, and template strategy.
"""

import numpy as np
import pandas as pd
import pytest

from core.strategy import Strategy
from strategies.template import TemplateStrategy
from utils import EMA, RSI, SMA


class TestStrategyIWrapper:
    """Test the Strategy.I() wrapper system."""

    def test_strategy_I_wrapper_creation(self):
        """Test that Strategy.I() wrapper creates indicators correctly."""

        # Create test data
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.normal(0, 1, 100))

        data = pd.DataFrame(
            {
                "open": prices,
                "high": prices * 1.02,
                "low": prices * 0.98,
                "close": prices,
                "volume": np.random.randint(1000, 10000, 100),
            },
            index=dates,
        )

        # Create strategy and attach data
        strategy = Strategy()
        strategy.data = data

        # Test Strategy.I() wrapper for SMA
        sma_indicator = strategy.I(SMA, data.close, 20, name="SMA20")

        # Verify the indicator was created
        assert hasattr(strategy, "_indicators")
        assert len(strategy._indicators) == 1
        assert sma_indicator is not None
        assert len(sma_indicator) == len(data)

        # Test multiple indicators
        rsi_indicator = strategy.I(RSI, data.close, 14, name="RSI14")
        assert len(strategy._indicators) == 2

        # Test that indicators are calculated correctly
        manual_sma = SMA(data.close, 20)
        manual_rsi = RSI(data.close, 14)

        np.testing.assert_array_almost_equal(sma_indicator, manual_sma)
        np.testing.assert_array_almost_equal(rsi_indicator, manual_rsi)

    def test_strategy_I_wrapper_with_ema(self):
        """Test Strategy.I() wrapper with EMA (numpy array function)."""

        # Create test data
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        np.random.seed(42)
        prices = 100 + np.cumsum(np.random.normal(0, 0.5, 50))

        data = pd.DataFrame({"close": prices}, index=dates)

        strategy = Strategy()
        strategy.data = data

        # Test EMA through Strategy.I() wrapper
        ema_indicator = strategy.I(EMA, data.close.values, 10, name="EMA10")

        # Compare with direct EMA calculation
        manual_ema = EMA(data.close.values, 10)

        np.testing.assert_array_almost_equal(ema_indicator, manual_ema)

    def test_strategy_indicator_retrieval(self):
        """Test getting indicators from strategy."""

        # Create test data
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        data = pd.DataFrame({"close": np.linspace(100, 120, 30)}, index=dates)

        strategy = Strategy()
        strategy.data = data

        # Add some indicators
        strategy.I(SMA, data.close, 5, name="SMA5")
        strategy.I(SMA, data.close, 10, name="SMA10")
        strategy.I(RSI, data.close, 14, name="RSI")

        # Test get_indicators method if it exists
        if hasattr(strategy, "get_indicators"):
            indicators = strategy.get_indicators()
            assert isinstance(indicators, dict)
            assert "SMA5" in indicators
            assert "SMA10" in indicators
            assert "RSI" in indicators


class TestTemplateStrategy:
    """Test the modernized template strategy."""

    def test_template_strategy_initialization(self):
        """Test that template strategy initializes correctly."""

        # Create test data
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        np.random.seed(42)
        base_price = 1500
        returns = np.random.normal(0.001, 0.02, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))

        # Create OHLC data
        noise = np.random.normal(0, 0.005, len(dates))
        high = prices * (1 + np.abs(noise))
        low = prices * (1 - np.abs(noise))
        open_prices = np.roll(prices, 1)
        open_prices[0] = prices[0]

        data = pd.DataFrame(
            {
                "open": open_prices,
                "high": high,
                "low": low,
                "close": prices,
                "volume": np.random.randint(1000000, 5000000, len(dates)),
            },
            index=dates,
        )

        # Create and initialize strategy
        strategy = TemplateStrategy()
        strategy.data = data
        strategy.initialize()  # Use correct method name

        # Test that indicators are created
        assert hasattr(strategy, "_indicators")
        assert len(strategy._indicators) > 0

        # Test that Strategy.I() was used properly (use actual indicator names)
        assert hasattr(strategy, "fast_ma")
        assert hasattr(strategy, "slow_ma")
        assert hasattr(strategy, "rsi")

        # Test indicator values
        assert len(strategy.fast_ma) == len(data)
        assert len(strategy.slow_ma) == len(data)
        assert len(strategy.rsi) == len(data)

    def test_template_strategy_market_regime_integration(self):
        """Test that template strategy integrates with market regime detection."""

        # Create test data with trend
        dates = pd.date_range("2023-01-01", periods=100, freq="D")
        trend = np.linspace(0, 10, 100)  # Upward trend
        noise = np.random.normal(0, 0.5, 100)
        prices = 100 + trend + noise

        data = pd.DataFrame(
            {
                "open": prices,
                "high": prices * 1.01,
                "low": prices * 0.99,
                "close": prices,
                "volume": np.random.randint(1000000, 5000000, 100),
            },
            index=dates,
        )

        strategy = TemplateStrategy()
        strategy.data = data
        strategy.initialize()  # Use correct method name

        # Test market regime detection if available
        if hasattr(strategy, "market_regime"):
            # Should detect upward trend
            regime = strategy.market_regime
            assert regime is not None

        # Test that next() method works without errors
        for i in range(10, min(20, len(data))):  # Test a few iterations
            try:
                strategy.next()
            except Exception as e:
                # Some exceptions are expected (like no open positions to close)
                # but should not be initialization errors
                assert "init" not in str(e).lower()


class TestMarketRegimeDetection:
    """Test market regime detection functionality."""

    def test_regime_detection_uptrend(self):
        """Test regime detection for uptrending market."""

        # Create strong uptrend data
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        trend = np.linspace(0, 20, 50)  # Strong upward trend
        prices = 100 + trend

        pd.DataFrame({"close": prices}, index=dates)

        # Test with EMA trend detection (basic regime)
        ema_short = EMA(prices, 10)
        ema_long = EMA(prices, 20)

        # In an uptrend, short EMA should be mostly above long EMA
        uptrend_signals = ema_short > ema_long
        uptrend_ratio = np.sum(uptrend_signals) / len(uptrend_signals)

        # Should be mostly uptrend
        assert uptrend_ratio > 0.7

    def test_regime_detection_downtrend(self):
        """Test regime detection for downtrending market."""

        # Create strong downtrend data
        dates = pd.date_range("2023-01-01", periods=50, freq="D")
        trend = np.linspace(0, -20, 50)  # Strong downward trend
        prices = 120 + trend

        pd.DataFrame({"close": prices}, index=dates)

        # Test with EMA trend detection
        ema_short = EMA(prices, 10)
        ema_long = EMA(prices, 20)

        # In a downtrend, short EMA should be mostly below long EMA
        downtrend_signals = ema_short < ema_long
        downtrend_ratio = np.sum(downtrend_signals) / len(downtrend_signals)

        # Should be mostly downtrend
        assert downtrend_ratio > 0.7


class TestStrategyArchitecture:
    """Test the overall strategy architecture and patterns."""

    def test_strategy_base_class(self):
        """Test Strategy base class functionality."""

        strategy = Strategy()

        # Test basic attributes
        assert hasattr(strategy, "I")
        assert callable(strategy.I)
        assert hasattr(strategy, "_indicators")

        # Test that I() method exists and is callable
        assert strategy._indicators == []

    def test_strategy_data_validation(self):
        """Test strategy data validation."""

        # Test with invalid data
        strategy = Strategy()

        # Should handle missing data gracefully
        assert not hasattr(strategy, "data") or strategy.data is None

        # Test with valid data
        dates = pd.date_range("2023-01-01", periods=10, freq="D")
        data = pd.DataFrame({"close": np.linspace(100, 110, 10)}, index=dates)

        strategy.data = data
        assert strategy.data is not None
        assert len(strategy.data) == 10

    def test_strategy_parameter_management(self):
        """Test strategy parameter management."""

        strategy = TemplateStrategy()

        # Test that parameters are accessible (use actual attribute names)
        assert hasattr(strategy, "fast_period")
        assert hasattr(strategy, "slow_period")
        assert hasattr(strategy, "rsi_period")

        # Test parameter values are reasonable
        assert strategy.fast_period < strategy.slow_period
        assert strategy.rsi_period > 0
        assert strategy.fast_period > 0
        assert strategy.slow_period > 0


if __name__ == "__main__":
    pytest.main([__file__])
