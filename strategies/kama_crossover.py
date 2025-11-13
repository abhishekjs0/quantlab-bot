# KAMA (Kaufman Adaptive Moving Average) Crossover Strategy with Trailing Stop
# KAMA(5) vs KAMA(200) crossover using Kaufman ends 2-30.
# Enhanced with 50 EMA trailing stop and 2*ATR fixed stop loss.

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, EMA


class KAMACrossover(Strategy):
    """
    KAMA Crossover Strategy with Fixed Stop Loss.

    Uses two KAMAs with different periods:
    - Fast KAMA (len_fast=5): Responds quickly to trend changes
    - Slow KAMA (len_slow=200): Provides baseline trend direction

    Entry: Fast KAMA crosses above Slow KAMA
    Exit: Fast KAMA crosses below Slow KAMA (crossunder signal)

    Stop Loss Management:
    - **Entry Stop**: 2 × ATR(14) fixed stop set at entry (hard floor)

    Both KAMAs use same fast_end/slow_end parameters (Kaufman 2-30).
    Only the lookback period (len_fast vs len_slow) differs.
    """

    # ===== KAMA Parameters =====
    len_fast = 5  # Fast KAMA period (efficiency lookback)
    len_slow = 200  # Slow KAMA period (trend baseline)
    fast_end = 0.666  # Fast smoothing endpoint (Kaufman 2-period)
    slow_end = 0.0645  # Slow smoothing endpoint (Kaufman 30-period)

    # ===== Stop Loss Parameters =====
    atr_period = 14  # ATR period for fixed stop
    atr_multiplier = 2.0  # 2 × ATR for fixed stop loss at entry

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""
        # Calculate KAMA lines
        self.kama_fast = self.I(
            self._compute_kama,
            self.data.close,
            self.len_fast,
            self.fast_end,
            self.slow_end,
            name=f"KAMA({self.len_fast})",
        )

        self.kama_slow = self.I(
            self._compute_kama,
            self.data.close,
            self.len_slow,
            self.fast_end,
            self.slow_end,
            name=f"KAMA({self.len_slow})",
        )

        # Stop Loss indicators
        self.atr_14 = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

    def _compute_kama(self, close, lookback, fast_end, slow_end):
        """
        Compute Kaufman Adaptive Moving Average.

        Matches Pine Script reference exactly.

        Args:
            close: Price series (pandas Series)
            lookback: Efficiency ratio lookback period
            fast_end: Fast smoothing endpoint
            slow_end: Slow smoothing endpoint

        Returns:
            pandas Series with KAMA values
        """
        close = close.astype(float)
        n = len(close)

        # Initialize KAMA array
        kama = np.full(n, np.nan)

        # Calculate components
        # xvnoise = abs(close[i] - close[i-1])
        xvnoise = (close - close.shift(1)).abs()

        # nsignal = abs(close[i] - close[i-lookback])
        nsignal = (close - close.shift(lookback)).abs()

        # nnoise = sum(xvnoise, lookback periods)
        # Use min_periods=lookback to match Pine Script
        nnoise = xvnoise.rolling(window=lookback, min_periods=lookback).sum()

        # Efficiency Ratio: er = nsignal / nnoise
        er = nsignal / nnoise
        er = er.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        # Smoothing Constant: sc = [er * (fastEnd - slowEnd) + slowEnd]^2
        sc = (er * (fast_end - slow_end) + slow_end) ** 2

        # KAMA calculation
        # k[0] = close[0] (initialization)
        kama[0] = close.iloc[0]

        # k[i] = k[i-1] + sc[i] * (close[i] - k[i-1])
        for i in range(1, n):
            prev_kama = kama[i - 1]
            current_close = close.iloc[i]
            current_sc = sc.iloc[i]

            # Handle NaN: use close as base if prev_kama is NaN
            if np.isnan(prev_kama):
                base = current_close
            else:
                base = prev_kama

            # Only update if we have valid SC
            if not np.isnan(current_sc):
                kama[i] = base + current_sc * (current_close - base)
            else:
                kama[i] = np.nan

        return pd.Series(kama, index=close.index)

    def _at(self, x, i):
        """Accessor: safely get element at index i from Series or array."""
        return x.iloc[i] if hasattr(x, "iloc") else x[i]

    def on_entry(self, entry_time, entry_price, state):
        """
        Configure entry parameters: set initial stop loss.

        Stop Loss Strategy:
        1. Fixed stop: entry_price - 2*ATR (hard floor)
        2. Trailing stop: Entry uses 50 EMA line (dynamic)

        Returns dict with stop loss levels to be applied by the engine.
        """
        # Get ATR value at entry to calculate fixed stop
        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            idx = None

        if idx is None or idx < 1 or np.isnan(self._at(self.atr_14, idx)):
            # Can't calculate ATR-based stop, use simple percentage
            return {}

        # Get ATR value at entry
        atr_value = self._at(self.atr_14, idx)

        if np.isnan(atr_value) or atr_value <= 0:
            return {}

        # Calculate fixed stop loss: entry_price - 2*ATR
        fixed_stop = entry_price - (self.atr_multiplier * atr_value)

        # Return stop loss configuration
        # The engine will use this as the hard floor
        return {"stop_loss": fixed_stop}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar with trailing stop.

        Entry: Fast KAMA crosses above Slow KAMA
        Exit:
          1. Fast KAMA crosses below Slow KAMA (crossunder signal), OR
          2. Price closes below 50 EMA (trailing stop breach)

        Trailing Stop Logic:
        - Once in position, continuously compare close to 50 EMA
        - If close < 50 EMA, exit the position (trailing stop triggered)
        - This provides dynamic profit protection while allowing upside
        """
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Need at least 2 bars for crossover detection
        if idx is None or idx < 1:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Get current and previous KAMA values (safely handle Series or array)
        kama_fast_now = self._at(self.kama_fast, idx)
        kama_fast_prev = self._at(self.kama_fast, idx - 1)
        kama_slow_now = self._at(self.kama_slow, idx)
        kama_slow_prev = self._at(self.kama_slow, idx - 1)

        # Check for valid data (no NaN)
        if (
            np.isnan(kama_fast_now)
            or np.isnan(kama_fast_prev)
            or np.isnan(kama_slow_now)
            or np.isnan(kama_slow_prev)
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Detect crossovers
        # Bullish: fast > slow AND fast[prev] <= slow[prev]
        bullish_crossover = (kama_fast_now > kama_slow_now) and (
            kama_fast_prev <= kama_slow_prev
        )

        # Bearish: fast < slow AND fast[prev] >= slow[prev]
        bearish_crossover = (kama_fast_now < kama_slow_now) and (
            kama_fast_prev >= kama_slow_prev
        )

        # Entry/Exit logic
        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0

        if bullish_crossover and not was_in_position:
            enter_long = True
            signal_reason = "KAMA Crossover"

        if was_in_position and bearish_crossover:
            exit_long = True
            signal_reason = "KAMA Crossunder"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
