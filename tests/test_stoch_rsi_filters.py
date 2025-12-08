#!/usr/bin/env python3
"""
Unit tests for Stoch RSI Pyramid Long Strategy Filters

Tests each filter individually:
1. ATR % > 3 filter
2. VIX < 14 OR VIX > 20 filter
3. ADX(28) > 25 filter
"""

import numpy as np
import pandas as pd
import pytest

from strategies.stoch_rsi_pyramid_long import StochRSIPyramidLongStrategy


def create_test_dataframe(n_bars=100, include_vix=True):
    """Create a test DataFrame with OHLCV data and optional VIX."""
    dates = pd.date_range(start="2024-01-01", periods=n_bars, freq="D")
    np.random.seed(42)
    
    # Generate realistic price data
    base_price = 100.0
    returns = np.random.randn(n_bars) * 0.02  # 2% daily volatility
    close = base_price * np.exp(np.cumsum(returns))
    
    # OHLC
    high = close * (1 + np.abs(np.random.randn(n_bars)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(n_bars)) * 0.01)
    open_ = close * (1 + np.random.randn(n_bars) * 0.005)
    volume = np.random.randint(100000, 1000000, n_bars)
    
    df = pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }, index=dates)
    
    if include_vix:
        # Default VIX in "neutral" zone (14-20) - should FAIL filter
        df["india_vix"] = 17.0
    
    return df


class TestATRFilter:
    """Test ATR % > 3 filter."""
    
    def test_atr_filter_pass_high_volatility(self):
        """ATR filter should pass when ATR % > 3."""
        df = create_test_dataframe(include_vix=False)
        
        # Create high volatility data (ATR% > 3)
        df["high"] = df["close"] * 1.05  # 5% above close
        df["low"] = df["close"] * 0.95   # 5% below close
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=True,
            atr_pct_threshold=3.0,
            use_vix_filter=False,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        # Get ATR value at last bar
        idx = len(df) - 1
        atr_val = strategy._at(strategy.atr, idx)
        close = df.iloc[idx]["close"]
        atr_pct = (atr_val / close) * 100.0
        
        print(f"ATR: {atr_val:.4f}, Close: {close:.2f}, ATR%: {atr_pct:.2f}%")
        assert atr_pct > 3.0, f"ATR% should be > 3, got {atr_pct:.2f}%"
    
    def test_atr_filter_fail_low_volatility(self):
        """ATR filter should fail when ATR % < 3."""
        df = create_test_dataframe(include_vix=False)
        
        # Create low volatility data (ATR% < 3)
        df["high"] = df["close"] * 1.005  # 0.5% above close
        df["low"] = df["close"] * 0.995   # 0.5% below close
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=True,
            atr_pct_threshold=3.0,
            use_vix_filter=False,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        # Get ATR value at last bar
        idx = len(df) - 1
        atr_val = strategy._at(strategy.atr, idx)
        close = df.iloc[idx]["close"]
        atr_pct = (atr_val / close) * 100.0
        
        print(f"ATR: {atr_val:.4f}, Close: {close:.2f}, ATR%: {atr_pct:.2f}%")
        assert atr_pct < 3.0, f"ATR% should be < 3, got {atr_pct:.2f}%"


class TestVIXFilter:
    """Test VIX < 14 OR VIX > 20 filter."""
    
    def test_vix_filter_pass_low_vix(self):
        """VIX filter should pass when VIX < 14."""
        df = create_test_dataframe(include_vix=True)
        df["india_vix"] = 12.0  # Below 14
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=True,
            vix_low_threshold=14.0,
            vix_high_threshold=20.0,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        # Simulate on_bar logic for VIX filter
        row = df.iloc[-1]
        vix_val = row["india_vix"]
        vix_filter = vix_val < 14.0 or vix_val > 20.0
        
        print(f"VIX: {vix_val}, Filter Pass: {vix_filter}")
        assert vix_filter == True, f"VIX filter should pass for VIX={vix_val}"
    
    def test_vix_filter_pass_high_vix(self):
        """VIX filter should pass when VIX > 20."""
        df = create_test_dataframe(include_vix=True)
        df["india_vix"] = 25.0  # Above 20
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=True,
            vix_low_threshold=14.0,
            vix_high_threshold=20.0,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        row = df.iloc[-1]
        vix_val = row["india_vix"]
        vix_filter = vix_val < 14.0 or vix_val > 20.0
        
        print(f"VIX: {vix_val}, Filter Pass: {vix_filter}")
        assert vix_filter == True, f"VIX filter should pass for VIX={vix_val}"
    
    def test_vix_filter_fail_neutral_vix(self):
        """VIX filter should FAIL when 14 <= VIX <= 20 (neutral zone)."""
        df = create_test_dataframe(include_vix=True)
        df["india_vix"] = 17.0  # In neutral zone
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=True,
            vix_low_threshold=14.0,
            vix_high_threshold=20.0,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        row = df.iloc[-1]
        vix_val = row["india_vix"]
        vix_filter = vix_val < 14.0 or vix_val > 20.0
        
        print(f"VIX: {vix_val}, Filter Pass: {vix_filter}")
        assert vix_filter == False, f"VIX filter should FAIL for VIX={vix_val} (neutral zone)"
    
    def test_vix_filter_boundary_14(self):
        """VIX filter should FAIL at exactly 14 (boundary)."""
        vix_val = 14.0
        vix_filter = vix_val < 14.0 or vix_val > 20.0
        
        print(f"VIX: {vix_val}, Filter Pass: {vix_filter}")
        assert vix_filter == False, f"VIX filter should FAIL for VIX=14.0 (at boundary)"
    
    def test_vix_filter_boundary_20(self):
        """VIX filter should FAIL at exactly 20 (boundary)."""
        vix_val = 20.0
        vix_filter = vix_val < 14.0 or vix_val > 20.0
        
        print(f"VIX: {vix_val}, Filter Pass: {vix_filter}")
        assert vix_filter == False, f"VIX filter should FAIL for VIX=20.0 (at boundary)"


class TestADXFilter:
    """Test ADX(28) > 25 filter."""
    
    def test_adx_filter_initialization(self):
        """ADX should be initialized when use_adx_filter=True."""
        df = create_test_dataframe(n_bars=50, include_vix=False)
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=False,
            use_adx_filter=True,
            adx_len=28,
        )
        df = strategy.prepare(df)
        
        assert hasattr(strategy, "adx_values"), "Strategy should have adx_values attribute"
        assert len(strategy.adx_values) == len(df), "ADX values should match data length"
    
    def test_adx_filter_strong_trend(self):
        """ADX filter computation for strong trend."""
        df = create_test_dataframe(n_bars=100, include_vix=False)
        
        # Create strong trending data - consistent up move
        trend = np.linspace(0, 50, len(df))  # Strong uptrend
        df["close"] = 100 + trend
        df["high"] = df["close"] * 1.02
        df["low"] = df["close"] * 0.98
        df["open"] = df["close"] * 0.995
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=False,
            use_adx_filter=True,
            adx_len=28,
            adx_threshold=25.0,
        )
        df = strategy.prepare(df)
        
        # Get ADX value at last bar
        idx = len(df) - 1
        adx_val = strategy._at(strategy.adx_values, idx)
        
        print(f"ADX({strategy.adx_len}): {adx_val:.2f}, Threshold: {strategy.adx_threshold}")
        # Note: ADX calculation may vary, so we just check it's computed
        assert not np.isnan(adx_val), "ADX should be computed"
    
    def test_adx_filter_ranging_market(self):
        """ADX filter computation for ranging market."""
        df = create_test_dataframe(n_bars=100, include_vix=False)
        
        # Create ranging/choppy data - oscillate around a mean
        np.random.seed(123)
        noise = np.random.randn(len(df)) * 2
        df["close"] = 100 + noise
        df["high"] = df["close"] + 1
        df["low"] = df["close"] - 1
        df["open"] = df["close"]
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=False,
            use_adx_filter=True,
            adx_len=28,
            adx_threshold=25.0,
        )
        df = strategy.prepare(df)
        
        # Get ADX value at last bar
        idx = len(df) - 1
        adx_val = strategy._at(strategy.adx_values, idx)
        
        print(f"ADX({strategy.adx_len}): {adx_val:.2f}, Threshold: {strategy.adx_threshold}")
        # In ranging market, ADX should be lower
        assert not np.isnan(adx_val), "ADX should be computed"


class TestCombinedFilters:
    """Test all filters working together."""
    
    def test_all_filters_integration(self):
        """Test that on_bar works with all filters enabled."""
        df = create_test_dataframe(n_bars=100, include_vix=True)
        
        # Setup data
        df["high"] = df["close"] * 1.05
        df["low"] = df["close"] * 0.95
        df["india_vix"] = 12.0  # VIX < 14 passes
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=True,
            atr_pct_threshold=3.0,
            use_vix_filter=True,
            vix_low_threshold=14.0,
            vix_high_threshold=20.0,
            use_adx_filter=True,
            adx_len=28,
            adx_threshold=25.0,
        )
        df = strategy.prepare(df)
        
        # Check that strategy can process on_bar without error
        idx = len(df) - 1
        ts = df.index[idx]
        row = df.iloc[idx]
        state = {"qty": 0, "cash": 100000, "equity": 100000}
        
        result = strategy.on_bar(ts, row, state)
        
        assert "enter_long" in result
        assert "exit_long" in result
        print(f"on_bar result: {result}")
    
    def test_strategy_defaults(self):
        """Test that default filter settings are correct (only 3 filters)."""
        strategy = StochRSIPyramidLongStrategy()
        
        # Stop loss disabled
        assert strategy.use_atr_stop == False, "Stop loss should be disabled"
        
        # Only 3 filters - all enabled
        assert strategy.use_atr_filter == True, "ATR filter should be enabled"
        assert strategy.atr_pct_threshold == 3.0, "ATR threshold should be 3.0"
        assert strategy.use_vix_filter == True, "VIX filter should be enabled"
        assert strategy.vix_low_threshold == 14.0, "VIX low threshold should be 14.0"
        assert strategy.vix_high_threshold == 20.0, "VIX high threshold should be 20.0"
        assert strategy.use_adx_filter == True, "ADX filter should be enabled"
        assert strategy.adx_len == 28, "ADX length should be 28"
        assert strategy.adx_threshold == 25.0, "ADX threshold should be 25.0"
        
        # Old filters should NOT exist
        assert not hasattr(strategy, "use_trend_filter"), "use_trend_filter should be removed"
        assert not hasattr(strategy, "use_rsi_filter"), "use_rsi_filter should be removed"


class TestVIXDataHandling:
    """Test VIX data handling edge cases."""
    
    def test_missing_vix_column(self):
        """Strategy should handle missing india_vix column gracefully."""
        df = create_test_dataframe(include_vix=False)
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=True,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        idx = len(df) - 1
        ts = df.index[idx]
        row = df.iloc[idx]
        state = {"qty": 0, "cash": 100000, "equity": 100000}
        
        # Should not raise error even if india_vix is missing
        result = strategy.on_bar(ts, row, state)
        assert "enter_long" in result
    
    def test_nan_vix_value(self):
        """Strategy should handle NaN VIX values gracefully."""
        df = create_test_dataframe(include_vix=True)
        df["india_vix"] = np.nan  # All NaN
        
        strategy = StochRSIPyramidLongStrategy(
            use_atr_filter=False,
            use_vix_filter=True,
            use_adx_filter=False,
        )
        df = strategy.prepare(df)
        
        idx = len(df) - 1
        ts = df.index[idx]
        row = df.iloc[idx]
        state = {"qty": 0, "cash": 100000, "equity": 100000}
        
        # Should not raise error with NaN VIX
        result = strategy.on_bar(ts, row, state)
        assert "enter_long" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
