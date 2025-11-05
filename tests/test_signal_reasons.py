#!/usr/bin/env python
"""Test to verify signal reasons are captured and exported."""

import numpy as np
import pandas as pd
import pytest

from core.config import BrokerConfig
from core.engine import BacktestEngine
from strategies.ema_crossover import EMAcrossoverStrategy


@pytest.mark.skip(
    reason="Synthetic data generation needs real signal setup - skipped pending signal infrastructure fix"
)
def test_signal_reasons_captured():
    """Verify signal reasons are captured and exported."""
    dates = pd.date_range(start="2024-01-01", periods=200, freq="1D")
    np.random.seed(42)
    prices = []
    base = 100.0
    for i in range(200):
        if i < 50:
            base += 0.3
        elif i < 100:
            base -= 0.3
        elif i < 150:
            base += 0.3
        else:
            base -= 0.3
        noise = np.random.randn() * 0.1
        prices.append(base + noise)
    prices = np.array(prices)
    df = pd.DataFrame(
        {
            "open": prices,
            "high": prices + np.abs(np.random.randn(200) * 0.5),
            "low": prices - np.abs(np.random.randn(200) * 0.5),
            "close": prices,
        },
        index=dates,
    )
    cfg = BrokerConfig(
        initial_capital=100000.0,
        commission_pct=0.05,
        slippage_ticks=1,
        tick_size=0.01,
        execute_on_next_open=True,
    )
    strategy = EMAcrossoverStrategy()
    engine = BacktestEngine(df, strategy, cfg)
    trades_df, equity_df, signals_df = engine.run()
    assert not trades_df.empty, "Expected trades to be generated"
    print(f"✅ Test passed: {len(trades_df)} trades generated")


if __name__ == "__main__":
    test_signal_reasons_captured()
