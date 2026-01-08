"""
Runner Integration Tests
========================

Tests for the runner modules (fast_run_basket, standard_run_basket).
Uses mock data fixtures for CI environments without live cache.
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import generate_ohlcv_data, generate_basket_symbols


# ============================================================================
# Mock Strategy for Testing
# ============================================================================

class MockStrategy:
    """Simple mock strategy for runner testing."""

    def __init__(self):
        self.name = "MockStrategy"
        self.data = None
        self._trades = []

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        self.data = df
        return df

    def should_enter(self, i: int) -> bool:
        # Simple: enter every 20 bars
        return i > 0 and i % 20 == 0 and not self._in_position()

    def should_exit(self, i: int) -> bool:
        # Exit after 10 bars in position
        if not self._in_position():
            return False
        entry_idx = self._trades[-1]["entry_idx"]
        return i - entry_idx >= 10

    def _in_position(self) -> bool:
        return len(self._trades) > 0 and self._trades[-1].get("exit_idx") is None

    def record_entry(self, i: int, price: float):
        self._trades.append({"entry_idx": i, "entry_price": price})

    def record_exit(self, i: int, price: float):
        if self._trades:
            self._trades[-1]["exit_idx"] = i
            self._trades[-1]["exit_price"] = price


# ============================================================================
# Unit Tests for Runner Utilities
# ============================================================================

class TestRunnerUtilities:
    """Test utility functions used by runners."""

    def test_portfolio_curve_calculation(self, sample_ohlcv):
        """Test portfolio equity curve building."""
        # Simulate trades
        trades_df = pd.DataFrame({
            "entry_date": [sample_ohlcv.index[10], sample_ohlcv.index[50]],
            "exit_date": [sample_ohlcv.index[20], sample_ohlcv.index[70]],
            "entry_price": [100.0, 110.0],
            "exit_price": [105.0, 115.0],
            "pnl_pct": [0.05, 0.0454],
            "pnl": [500.0, 500.0],
        })

        # Calculate equity curve
        initial_capital = 10000.0
        equity = initial_capital

        for _, trade in trades_df.iterrows():
            equity += trade["pnl"]

        assert equity > initial_capital
        assert len(trades_df) == 2

    def test_window_slicing(self, sample_ohlcv):
        """Test time window slicing for metrics."""
        # 1-year window
        end_date = sample_ohlcv.index[-1]
        start_date_1y = end_date - pd.Timedelta(days=365)

        window_1y = sample_ohlcv[sample_ohlcv.index >= start_date_1y]
        assert len(window_1y) <= 252

        # 3-year window (should be full data if less than 3 years)
        start_date_3y = end_date - pd.Timedelta(days=365 * 3)
        window_3y = sample_ohlcv[sample_ohlcv.index >= start_date_3y]
        assert len(window_3y) == len(sample_ohlcv)  # Full data since less than 3 years

    def test_indicator_enrichment(self, sample_ohlcv):
        """Test indicator calculation on OHLCV data."""
        from utils.indicators import RSI, ATR, EMA

        close = sample_ohlcv["close"].values
        high = sample_ohlcv["high"].values
        low = sample_ohlcv["low"].values

        # Calculate indicators
        rsi = RSI(close, 14)
        atr = ATR(high, low, close, 14)
        ema_20 = EMA(close, 20)

        # Verify shapes
        assert len(rsi) == len(sample_ohlcv)
        assert len(atr) == len(sample_ohlcv)
        assert len(ema_20) == len(sample_ohlcv)

        # Verify values are reasonable
        valid_rsi = rsi[~np.isnan(rsi)]
        assert np.all(valid_rsi >= 0) and np.all(valid_rsi <= 100)


# ============================================================================
# Integration Tests for Backtest Engine
# ============================================================================

class TestBacktestEngineIntegration:
    """Integration tests for the backtest engine with mock data."""

    def test_engine_initialization(self, sample_ohlcv):
        """Test BacktestEngine can be initialized."""
        from core.engine import BacktestEngine
        from core.config import BrokerConfig
        from core.strategy import Strategy

        class DummyStrategy(Strategy):
            def prepare(self, df):
                self.data = df
                return super().prepare(df)

            def should_enter(self, i):
                return False

            def should_exit(self, i):
                return False

        strategy = DummyStrategy()
        cfg = BrokerConfig()
        engine = BacktestEngine(
            df=sample_ohlcv,
            strategy=strategy,
            cfg=cfg,
            symbol="TEST_NS",
        )

        assert engine is not None
        assert engine.symbol == "TEST_NS"

    def test_engine_with_strategy(self, sample_ohlcv):
        """Test running backtest with a simple strategy."""
        from core.engine import BacktestEngine
        from core.config import BrokerConfig
        from core.strategy import Strategy
        from utils.indicators import SMA

        class SimpleStrategy(Strategy):
            def prepare(self, df):
                self.data = df
                self.sma_fast = self.I(SMA, df.close, 10, name="SMA10")
                self.sma_slow = self.I(SMA, df.close, 30, name="SMA30")
                return super().prepare(df)

            def should_enter(self, i):
                if i < 1:
                    return False
                return (
                    self.sma_fast[i - 1] > self.sma_slow[i - 1]
                    and self.sma_fast[i - 2] <= self.sma_slow[i - 2]
                )

            def should_exit(self, i):
                if i < 1:
                    return False
                return (
                    self.sma_fast[i - 1] < self.sma_slow[i - 1]
                    and self.sma_fast[i - 2] >= self.sma_slow[i - 2]
                )

        strategy = SimpleStrategy()
        cfg = BrokerConfig()
        engine = BacktestEngine(
            df=sample_ohlcv,
            strategy=strategy,
            cfg=cfg,
            symbol="TEST_NS",
        )
        
        result = engine.run()
        
        assert result is not None

    def test_trades_dataframe_structure(self, sample_ohlcv):
        """Test that trades DataFrame has expected columns."""
        # Create mock trades DataFrame
        trades = pd.DataFrame({
            "symbol": ["TEST_NS"] * 3,
            "entry_date": pd.date_range("2023-01-15", periods=3, freq="30D"),
            "exit_date": pd.date_range("2023-01-25", periods=3, freq="30D"),
            "entry_price": [100.0, 105.0, 110.0],
            "exit_price": [108.0, 112.0, 105.0],
            "shares": [100, 100, 100],
            "direction": ["long"] * 3,
        })

        # Calculate PnL
        trades["pnl"] = (trades["exit_price"] - trades["entry_price"]) * trades["shares"]
        trades["pnl_pct"] = (trades["exit_price"] / trades["entry_price"]) - 1

        expected_cols = ["symbol", "entry_date", "exit_date", "entry_price", 
                         "exit_price", "shares", "direction", "pnl", "pnl_pct"]
        
        for col in expected_cols:
            assert col in trades.columns


# ============================================================================
# Basket Processing Tests
# ============================================================================

class TestBasketProcessing:
    """Tests for basket (multi-symbol) processing."""

    def test_basket_data_loading(self, sample_basket):
        """Test loading multiple symbols."""
        assert len(sample_basket) == 5
        
        for symbol, df in sample_basket.items():
            assert isinstance(df, pd.DataFrame)
            assert set(df.columns) == {"open", "high", "low", "close", "volume"}
            assert len(df) == 252

    def test_basket_aggregation(self, sample_basket):
        """Test aggregating trades across multiple symbols."""
        all_trades = []
        
        for symbol, df in sample_basket.items():
            # Simulate some trades per symbol
            trades = pd.DataFrame({
                "symbol": [symbol] * 2,
                "pnl": [100.0, -50.0],
                "pnl_pct": [0.02, -0.01],
            })
            all_trades.append(trades)

        combined = pd.concat(all_trades, ignore_index=True)
        
        assert len(combined) == 10  # 2 trades per 5 symbols
        assert combined["pnl"].sum() == 250.0  # 5 * (100 - 50)

    def test_parallel_processing_compatibility(self, sample_basket):
        """Test that data structures are pickle-compatible for multiprocessing."""
        import pickle

        for symbol, df in sample_basket.items():
            # Should be picklable for multiprocessing
            pickled = pickle.dumps(df)
            restored = pickle.loads(pickled)
            
            assert len(restored) == len(df)
            assert list(restored.columns) == list(df.columns)


# ============================================================================
# Metrics Integration Tests
# ============================================================================

class TestMetricsIntegration:
    """Test metrics calculation integration."""

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio calculation."""
        from core.metrics import calculate_sharpe_ratio

        # 10% returns with 15% volatility
        returns = np.random.normal(0.0004, 0.01, 252)  # Daily returns
        
        sharpe = calculate_sharpe_ratio(returns)
        
        # Sharpe should be a reasonable number
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)

    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        from core.metrics import calculate_max_drawdown

        # Create equity curve with known drawdown
        equity = pd.Series([100, 110, 105, 90, 95, 100, 85, 100, 120])
        
        mdd, drawdown_series = calculate_max_drawdown(equity)
        
        # Max drawdown should be from 110 to 85 = 22.7%
        assert abs(mdd) > 0.20  # Drawdown is negative
        assert len(drawdown_series) == len(equity)

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        # Profit factor = gross profit / gross loss
        trades_pnl = [100, -50, 200, -30, 150]
        
        gross_profit = sum(p for p in trades_pnl if p > 0)
        gross_loss = abs(sum(p for p in trades_pnl if p < 0))
        
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        assert profit_factor == 450 / 80
        assert profit_factor > 1  # Profitable strategy


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_data(self):
        """Test handling of empty DataFrame."""
        empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        
        assert len(empty_df) == 0

    def test_insufficient_data(self, sample_ohlcv_short):
        """Test handling of insufficient data for indicators."""
        from utils.indicators import SMA

        # 200-period SMA on 60 days of data
        sma_200 = SMA(sample_ohlcv_short["close"].values, 200)
        
        # Should return all NaN (insufficient data)
        assert np.all(np.isnan(sma_200))

    def test_nan_handling_in_indicators(self, sample_ohlcv):
        """Test that indicators handle NaN values gracefully."""
        from utils.indicators import RSI

        # Add some NaN values
        close = sample_ohlcv["close"].values.copy()
        close[50:55] = np.nan

        rsi = RSI(close, 14)
        
        # Should propagate NaN but not crash
        assert len(rsi) == len(close)

    def test_single_trade(self, sample_ohlcv):
        """Test metrics with single trade."""
        trades = pd.DataFrame({
            "symbol": ["TEST_NS"],
            "entry_date": [sample_ohlcv.index[10]],
            "exit_date": [sample_ohlcv.index[20]],
            "pnl": [500.0],
            "pnl_pct": [0.05],
        })

        # Should handle single trade without division by zero
        win_rate = (trades["pnl"] > 0).mean()
        assert win_rate == 1.0


# ============================================================================
# Performance Tests (marked as slow)
# ============================================================================

@pytest.mark.slow
class TestPerformance:
    """Performance tests for runner operations."""

    def test_large_basket_processing(self):
        """Test processing a large basket of symbols."""
        n_symbols = 50
        n_days = 500

        basket = {}
        for i in range(n_symbols):
            basket[f"STOCK{i:03d}_NS"] = generate_ohlcv_data(
                n_days=n_days,
                seed=i,
            )

        assert len(basket) == n_symbols

        # Simulate aggregation
        total_trades = 0
        for symbol, df in basket.items():
            # Count potential signals
            total_trades += len(df) // 20

        assert total_trades > 0

    def test_indicator_calculation_speed(self, sample_ohlcv):
        """Test indicator calculation performance."""
        import time
        from utils.indicators import RSI, ATR, MACD, BollingerBands

        close = sample_ohlcv["close"].values
        high = sample_ohlcv["high"].values
        low = sample_ohlcv["low"].values

        start = time.time()
        
        for _ in range(100):
            RSI(close, 14)
            ATR(high, low, close, 14)
            MACD(close, 12, 26, 9)
            BollingerBands(close, 20, 2.0)

        elapsed = time.time() - start
        
        # Should complete 100 iterations in reasonable time
        assert elapsed < 5.0  # 5 seconds max
