"""
Triple EMA Aligned Strategy
============================

Trend alignment strategy using three exponential moving averages (20/50/200).
Detects strong directional moves by filtering for proper EMA stack alignment.

Buy Signal: Price < EMA(20) < EMA(50) < EMA(200) (bullish stack)
Sell Signal: Price > EMA(20) > EMA(50) > EMA(200) (bearish stack)

Core Logic:
- EMA(20): Fast trend detection (short-term)
- EMA(50): Medium trend confirmation (medium-term)
- EMA(200): Slow trend bias (long-term)

Entry Requirements:
- Price must be aligned below/above all three EMAs
- All EMAs must be in proper stacking order (no crossing)
- This filters for strong directional bias only

Parameters:
- EMA Fast: 20 period
- EMA Medium: 50 period
- EMA Slow: 200 period
- ATR: 14-period for stop loss calculation
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils import ATR, EMA


class TripleEMAAlignedStrategy(Strategy):
    """
    Triple EMA Aligned Strategy - Strong directional trend filter.

    Enters only on strong EMA stack alignments where all three EMAs are
    properly ordered relative to price, indicating confirmed trend direction.
    Results in high win rate with low frequency but high-quality signals.
    """

    # ===== EMA Parameters =====
    ema_fast_period = 20  # Short-term trend
    ema_medium_period = 50  # Medium-term trend
    ema_slow_period = 200  # Long-term trend

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
