"""
EMA Color Filter Strategy
=========================

Exponential Moving Average Color Filter strategy with trend alignment detection.

Buy Signal: Price < EMA(20) < EMA(50) < EMA(200) (all EMAs in descending order)
Sell Signal: Price > EMA(20) > EMA(50) > EMA(200) (all EMAs in ascending order)

This represents the "Black < Green < Red" candle color pattern where:
- Black = EMA(20) (short-term trend)
- Green = EMA(50) (medium-term trend)
- Red = EMA(200) (long-term trend)

The strategy filters for strong aligned trends:
- Buy: Bullish alignment (price below all EMAs, all EMAs properly ordered)
- Sell: Bearish alignment (price above all EMAs, all EMAs properly ordered)

Parameters:
- EMA Fast: 20 period (Black line)
- EMA Medium: 50 period (Green line)
- EMA Slow: 200 period (Red line)
- ATR: 14-period, 2x multiplier for stop loss
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils import ATR, EMA


class EMAColorFilterStrategy(Strategy):
    """
    EMA Color Filter Strategy with trend alignment.

    Enters on strong trend alignments where all three EMAs are in proper order
    relative to current price, indicating a confirmed directional move.
    """

    # ===== EMA Parameters =====
    ema_fast_period = 20  # Black line
    ema_medium_period = 50  # Green line
    ema_slow_period = 200  # Red line

    # ===== Risk Management =====
    atr_period = 14
    atr_multiplier = 2.0  # 2 ATR for stop loss
    use_stop_loss = False  # Can be enabled if needed

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

        self.ema_medium = self.I(
            EMA,
            self.data.close,
            self.ema_medium_period,
            name=f"EMA({self.ema_medium_period})",
            overlay=True,
        )

        self.ema_slow = self.I(
            EMA,
            self.data.close,
            self.ema_slow_period,
            name=f"EMA({self.ema_slow_period})",
            overlay=True,
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

        Entry: Price < EMA(20) < EMA(50) < EMA(200) (bullish alignment)
        Exit: Price > EMA(20) > EMA(50) > EMA(200) (bearish alignment)

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
            self.ema_medium_period,
            self.ema_slow_period,
            self.atr_period,
        )

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== Get Current Values =====
        price = row.close
        ema_fast = self.ema_fast[idx]
        ema_medium = self.ema_medium[idx]
        ema_slow = self.ema_slow[idx]

        # ===== CHECK FOR NaN INDICATORS =====
        if (
            np.isnan(price)
            or np.isnan(ema_fast)
            or np.isnan(ema_medium)
            or np.isnan(ema_slow)
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== Alignment Detection =====
        # Bullish alignment: Price < EMA(20) < EMA(50) < EMA(200)
        bullish_aligned = (
            price < ema_fast and ema_fast < ema_medium and ema_medium < ema_slow
        )

        # Bearish alignment: Price > EMA(20) > EMA(50) > EMA(200)
        bearish_aligned = (
            price > ema_fast and ema_fast > ema_medium and ema_medium > ema_slow
        )

        # ===== Entry/Exit Signals =====
        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0

        # Entry: Bullish alignment
        if bullish_aligned and not was_in_position:
            enter_long = True
            signal_reason = f"Bullish EMA alignment: {price:.2f} < {ema_fast:.2f} < {ema_medium:.2f} < {ema_slow:.2f}"

        # Exit: Bearish alignment
        if was_in_position and bearish_aligned:
            exit_long = True
            signal_reason = f"Bearish EMA alignment: {price:.2f} > {ema_fast:.2f} > {ema_medium:.2f} > {ema_slow:.2f}"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
