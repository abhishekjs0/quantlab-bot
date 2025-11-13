"""
EMA 13/34 Crossover Strategy with SMA 200 Filter
=================================================

A momentum-based trend-following strategy that:
1. Enters on EMA 13/55 crossovers
2. Uses SMA 200 as a confirmation filter
3. Exits on crossunder signals

Key Features:
- Entry: EMA(13) crosses above EMA(55) for LONG (with SMA 200 confirmation)
- Exit: EMA(13) crosses below EMA(55)
- Filter: Only trade if price is above SMA(200)
- No stop loss or pyramiding - simple, clean logic

Parameters:
- EMA Fast: 13 period
- EMA Slow: 55 period
- SMA Filter: 200 period
- Filter Logic: Close > SMA(200) required for entry

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import EMA, SMA


class EMA1355Strategy(Strategy):
    """
    EMA 13/34 Crossover Strategy with SMA 200 Filter.

    Combines momentum (EMA crossover) with trend confirmation (SMA).

    NOTE ON INDICATORS:
    - Indicators return NaN for insufficient data period
    - EMA(34) returns NaN for bars 0-54
    - SMA(200) returns NaN for bars 0-199
    - Strategy checks for NaN before trading to avoid premature signals
    """

    # ===== EMA Parameters =====
    ema_fast_period = 55
    ema_slow_period = 144

    # ===== Filter Parameters =====
    sma_filter_period = 200

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

        # ===== SMA Filter Indicator =====
        self.sma_filter = self.I(
            SMA,
            self.data.close,
            self.sma_filter_period,
            name=f"SMA({self.sma_filter_period})",
            overlay=True,
        )

    def on_entry(self, entry_time, entry_price, state):
        """No stop loss for this strategy."""
        return {}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.
        Checks for NaN indicator values to avoid trading during insufficient data period.

        Entry: EMA(21) crosses above EMA(55) AND Close > SMA(200)
        Exit: EMA(21) crosses below EMA(55)

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

        # Need enough bars for all indicators (max is SMA 200)
        min_bars = max(
            self.ema_fast_period,
            self.ema_slow_period,
            self.sma_filter_period,
        )

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== CHECK FOR NaN INDICATORS =====
        # Indicators return NaN when insufficient data - don't trade on NaN
        ema_fast_now = self.ema_fast[idx]
        ema_fast_prev = self.ema_fast[idx - 1]
        ema_slow_now = self.ema_slow[idx]
        ema_slow_prev = self.ema_slow[idx - 1]
        sma_filter_now = self.sma_filter[idx]
        close_now = self.data.close[idx]

        # If any indicator is NaN, skip trading
        if (
            np.isnan(ema_fast_now)
            or np.isnan(ema_fast_prev)
            or np.isnan(ema_slow_now)
            or np.isnan(ema_slow_prev)
            or np.isnan(sma_filter_now)
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== EMA Crossover Detection =====
        # Bullish crossover: EMA21 crosses above EMA55
        bullish_crossover = (ema_fast_prev <= ema_slow_prev) and (
            ema_fast_now > ema_slow_now
        )

        # Bearish crossover: EMA21 crosses below EMA55
        bearish_crossover = (ema_fast_prev >= ema_slow_prev) and (
            ema_fast_now < ema_slow_now
        )

        # ===== SMA 200 Filter =====
        # Only trade when price is above SMA 200 (uptrend confirmation)
        above_sma_200 = close_now > sma_filter_now

        # ===== Entry Signals =====
        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0

        # Entry: Bullish crossover + Price above SMA 200
        if bullish_crossover and above_sma_200 and not was_in_position:
            enter_long = True
            signal_reason = "EMA 21/55 Crossover + SMA 200 Filter"

        # ===== Exit Signal =====
        if was_in_position and bearish_crossover:
            exit_long = True
            signal_reason = "EMA 21/55 Crossunder"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
