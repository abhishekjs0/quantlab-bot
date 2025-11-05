"""
Modern QuantLab Strategy Template
================================

Template showing how to build strategies using the modern Strategy.I() wrapper system.
This template reflects the current architecture used in the production ichimoku strategy.

Key Features:
- Uses Strategy.I() wrapper for clean indicator declarations
- Automatic plotting metadata and optimization support
- Market regime integration capability
- Professional parameter management
- Proper bar-close entry/exit logic (no future-leak)
- Integration with config.py defaults

IMPORTANT: All entry and exit decisions are based on PREVIOUS BAR CLOSE data only.
This ensures no future leak and realistic trading simulation.
"""

import pandas as pd

from config import config
from core.strategy import Strategy
from utils import ATR, EMA, RSI, SMA


class TemplateStrategy(Strategy):
    """
    Modern strategy template using Strategy.I() wrapper system.

    This template demonstrates:
    1. Clean indicator declaration with Strategy.I()
    2. Professional parameter management with config.py integration
    3. Market regime integration
    4. Proper initialization pattern
    5. Bar-close entry/exit logic (no future leak)

    CRITICAL: All trading decisions use PREVIOUS bar data only.
    Current bar data is never used for entry/exit decisions to prevent future leak.

    NOTE ON INDICATORS:
    - Indicators return NaN for the first N bars where data is insufficient
    - Example: SMA(200) returns NaN for bars 0-199, valid from bar 200 onwards
    - Strategy must check for NaN values in indicators before trading
    - This ensures accurate calculations and prevents premature trading

    Usage:
    - Define strategy parameters as class attributes
    - Use initialize() method to declare indicators with self.I()
    - Implement next() method for trading logic
    - Check for NaN values before making trading decisions
    - Optionally integrate market regime filtering
    """

    # Strategy parameters (easily optimizable!) - with config.py defaults
    fast_period = 10
    slow_period = 20
    rsi_period = 14
    atr_period = 14

    # Filter parameters
    use_rsi_filter = True
    rsi_min = 30.0
    rsi_max = 70.0

    use_atr_filter = False
    atr_min_pct = 1.0
    atr_max_pct = 5.0

    # Market regime filter (optional) - integrates with config system
    use_market_regime_filter = False
    market_regime_strength_min = 0.4

    def __init__(self, **kwargs):
        """Initialize strategy with config.py integration."""
        super().__init__()

        # Apply any passed parameters
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        # Log configuration source
        if hasattr(config, "logging") and config.logging.level == "DEBUG":
            print(f"Strategy initialized with config from: {config.project_root}")

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and call initialize."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """
        Initialize all indicators using Strategy.I() wrapper.

        This is the modern way to declare indicators in QuantLab.
        Each indicator gets automatic plotting metadata and optimization support.
        """
        # Moving averages with Strategy.I() wrapper
        self.fast_ma = self.I(
            SMA,
            self.data.close,
            self.fast_period,
            name=f"SMA({self.fast_period})",
            color="blue",
            overlay=True,
        )

        self.slow_ma = self.I(
            SMA,
            self.data.close,
            self.slow_period,
            name=f"SMA({self.slow_period})",
            color="red",
            overlay=True,
        )

        # Optional filters with Strategy.I()
        if self.use_rsi_filter:
            self.rsi = self.I(
                RSI,
                self.data.close,
                self.rsi_period,
                name=f"RSI({self.rsi_period})",
                overlay=False,
                color="purple",
            )

        if self.use_atr_filter:
            self.atr = self.I(
                ATR,
                self.data.high,
                self.data.low,
                self.data.close,
                self.atr_period,
                name=f"ATR({self.atr_period})",
                overlay=False,
                color="orange",
            )

    def next(self):
        """
        Main strategy logic called for each bar.

        CRITICAL: All trading decisions use PREVIOUS bar data only.
        This ensures no future leak and realistic trading simulation.

        This method implements the trading decisions using the indicators
        declared in initialize(). All entry/exit decisions are based on
        completed (closed) bars only.
        """
        # Ensure we have enough data for proper analysis
        if len(self.data) < max(self.fast_period, self.slow_period) + 2:
            return

        # Check if we have enough indicator data
        if len(self.fast_ma.dropna()) < 2 or len(self.slow_ma.dropna()) < 2:
            return

        # CRITICAL: Use PREVIOUS bar data for all decisions (no future leak)
        # Current index position in the data
        current_idx = len(self.data) - 1
        prev_idx = current_idx - 1

        # Ensure we have at least 2 bars for crossover detection
        if prev_idx < 1:
            return

        # Previous bar values (this is what we base decisions on)
        prev_price = self.data.close.iloc[prev_idx]
        fast_ma_prev = self.fast_ma.iloc[prev_idx]
        slow_ma_prev = self.slow_ma.iloc[prev_idx]

        # Two bars ago values (for crossover detection)
        fast_ma_prev2 = self.fast_ma.iloc[prev_idx - 1]
        slow_ma_prev2 = self.slow_ma.iloc[prev_idx - 1]

        # Crossover signals using PREVIOUS bar data only
        bullish_cross = fast_ma_prev > slow_ma_prev and fast_ma_prev2 <= slow_ma_prev2
        bearish_cross = fast_ma_prev < slow_ma_prev and fast_ma_prev2 >= slow_ma_prev2

        # Apply filters using PREVIOUS bar data only
        all_filters_pass = True

        # RSI filter (using previous bar)
        if self.use_rsi_filter and hasattr(self, "rsi"):
            if len(self.rsi.dropna()) > prev_idx:
                rsi_val = self.rsi.iloc[prev_idx]
                all_filters_pass &= self.rsi_min <= rsi_val <= self.rsi_max

        # ATR filter (using previous bar)
        if self.use_atr_filter and hasattr(self, "atr"):
            if len(self.atr.dropna()) > prev_idx:
                atr_val = self.atr.iloc[prev_idx]
                atr_pct = (atr_val / prev_price) * 100
                all_filters_pass &= self.atr_min_pct <= atr_pct <= self.atr_max_pct

        # Trading logic based on PREVIOUS bar signals
        if bullish_cross and all_filters_pass:
            if not self.position:
                # Entry will be executed at current bar's open (next day)
                # This simulates real-world execution after signal confirmation
                self.buy()
        elif bearish_cross:
            if self.position:
                # Exit will be executed at current bar's open (next day)
                self.sell()

    def __str__(self):
        """String representation for strategy identification."""
        return (
            f"TemplateStrategy(fast={self.fast_period}, slow={self.slow_period}, "
            f"rsi_filter={self.use_rsi_filter}, market_regime={self.use_market_regime_filter})"
        )


# Example of how to create strategy variants
class EMACrossStrategy(TemplateStrategy):
    """Example variant using EMA instead of SMA."""

    def initialize(self):
        """Override to use EMA instead of SMA."""
        # EMA cross with Strategy.I() wrapper
        self.fast_ma = self.I(
            EMA,
            self.data.close.values,
            self.fast_period,
            name=f"EMA({self.fast_period})",
            color="blue",
            overlay=True,
        )

        self.slow_ma = self.I(
            EMA,
            self.data.close.values,
            self.slow_period,
            name=f"EMA({self.slow_period})",
            color="red",
            overlay=True,
        )

        # Add RSI filter if enabled
        if self.use_rsi_filter:
            self.rsi = self.I(
                RSI,
                self.data.close,
                self.rsi_period,
                name=f"RSI({self.rsi_period})",
                overlay=False,
                color="purple",
            )


# Usage example:
"""
# Basic usage
strategy = TemplateStrategy()

# With custom parameters
strategy = TemplateStrategy()
strategy.fast_period = 12
strategy.slow_period = 26
strategy.use_rsi_filter = True
strategy.rsi_min = 40
strategy.rsi_max = 60

# EMA variant
ema_strategy = EMACrossStrategy()
ema_strategy.fast_period = 9
ema_strategy.slow_period = 21

# With market regime filter
regime_strategy = TemplateStrategy()
regime_strategy.use_market_regime_filter = True
regime_strategy.market_regime_strength_min = 0.5
"""
