"""
EMA Crossover Strategy with Pyramiding on RSI Dips
===================================================

A trend-following strategy that:
1. Enters on EMA 89/144 crossovers
2. Pyramids into positions when RSI < 40 (buying dips)
3. Exits on crossunder signals

Reference: EMA Cross Strategy (kirilov)
Adapted for QuantLab backtesting engine.

Key Features:
- Entry: EMA(89) crosses above EMA(144) for LONG
- Pyramiding: Add to position when RSI < 30 (strong oversold, up to 3 entries max)
- Exit: EMA(89) crosses below EMA(144)
- SL: ATR-based stop loss

Parameters:
- EMA Fast: 89 period
- EMA Slow: 144 period
- RSI Period: 14
- RSI Threshold: 30 (for dip entries - more selective than 40)
- Max Pyramids: 3 levels
- ATR: 14-period, 2x multiplier for stop loss

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils import ATR, EMA, RSI


class EMAcrossoverStrategy(Strategy):
    """
    EMA Crossover Strategy with RSI-based pyramiding.

    Combines trend-following (EMA crossover) with mean reversion (RSI pyramiding).

    NOTE ON INDICATORS:
    - Indicators return NaN for insufficient data period
    - EMA(144) returns NaN for bars 0-143
    - Strategy checks for NaN before trading to avoid premature signals
    """

    # ===== EMA Parameters =====
    ema_fast_period = 89
    ema_slow_period = 144

    # ===== RSI Pyramiding Parameters =====
    rsi_period = 14
    rsi_pyramid_threshold = 30  # Buy dips when RSI < 30 (more aggressive than 40)
    max_pyramid_levels = 3  # Maximum number of pyramid entries

    # ===== Risk Management =====
    atr_period = 14
    atr_multiplier = 2.0  # 2x ATR for stop loss
    use_stop_loss = False  # Flag to enable/disable stop loss (set to False by default)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""

        # ===== EMA Indicators =====
        self.ema_fast = self.I(
            EMA,
            self.data.close,
            self.ema_fast_period,
            name=f"EMA({self.ema_fast_period})",
            overlay=True,
        )

        self.ema_slow = self.I(
            EMA,
            self.data.close,
            self.ema_slow_period,
            name=f"EMA({self.ema_slow_period})",
            overlay=True,
        )

        # ===== RSI Indicator =====
        self.rsi = self.I(
            RSI,
            self.data.close,
            self.rsi_period,
            name=f"RSI({self.rsi_period})",
            overlay=False,
        )

        # ===== Risk Management Indicator =====
        self.atr = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate ATR-based stop loss when entering a trade.

        Stop loss is DISABLED by default (use_stop_loss = False).
        Can be enabled by setting use_stop_loss = True.
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result

            if idx is not None and idx >= 0 and idx < len(self.atr):
                atr_value = self.atr[idx]
                if atr_value is not None and not np.isnan(atr_value) and atr_value > 0:
                    stop_loss = entry_price - (atr_value * self.atr_multiplier)
                    return {"stop": stop_loss}
        except Exception:
            pass

        return {}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.
        Checks for NaN indicator values to avoid trading during insufficient data period.

        Entry: EMA(89) crosses above EMA(144) OR RSI < 30 (pyramiding)
        Exit: EMA(89) crosses below EMA(144)

        Args:
            ts: Timestamp
            row: Current bar data
            state: Trading state

        Returns:
            Dictionary with entry/exit signals and reasons
        """
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Need enough bars for all indicators
        min_bars = max(
            self.ema_fast_period,
            self.ema_slow_period,
            self.rsi_period,
            self.atr_period,
        )

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== CHECK FOR NaN INDICATORS =====
        # Indicators return NaN when insufficient data - don't trade on NaN
        ema_fast_now = self.ema_fast[idx]
        ema_fast_prev = self.ema_fast[idx - 1]
        ema_slow_now = self.ema_slow[idx]
        ema_slow_prev = self.ema_slow[idx - 1]
        rsi_now = self.rsi[idx]

        # If any indicator is NaN, skip trading
        if (
            np.isnan(ema_fast_now)
            or np.isnan(ema_fast_prev)
            or np.isnan(ema_slow_now)
            or np.isnan(ema_slow_prev)
            or np.isnan(rsi_now)
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== EMA Crossover Detection =====
        # Bullish crossover: EMA89 crosses above EMA144
        bullish_crossover = (ema_fast_prev <= ema_slow_prev) and (
            ema_fast_now > ema_slow_now
        )

        # Bearish crossover: EMA89 crosses below EMA144
        bearish_crossover = (ema_fast_prev >= ema_slow_prev) and (
            ema_fast_now < ema_slow_now
        )

        # ===== RSI Pyramiding Detection =====
        # Buy dip when RSI < 30 and in uptrend (EMA89 > EMA144)
        in_uptrend = ema_fast_now > ema_slow_now
        rsi_dip = rsi_now < self.rsi_pyramid_threshold
        buy_dip = in_uptrend and rsi_dip

        # ===== Entry Signals =====
        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0
        pyramid_count = state.get("pyramid_count", 0)

        # Primary entry: Bullish crossover
        if bullish_crossover and not was_in_position:
            enter_long = True
            signal_reason = "EMA Crossover"
            # Initialize pyramid count on new entry
            state["pyramid_count"] = 1

        # Pyramiding entry: RSI dip while in position and not at max pyramid level
        elif buy_dip and was_in_position and pyramid_count < self.max_pyramid_levels:
            enter_long = True
            signal_reason = f"RSI Dip #{pyramid_count + 1}"
            state["pyramid_count"] = pyramid_count + 1

        # ===== Exit Signal =====
        if was_in_position and bearish_crossover:
            exit_long = True
            signal_reason = "EMA Crossunder"
            state["pyramid_count"] = 0  # Reset pyramid counter on exit

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
