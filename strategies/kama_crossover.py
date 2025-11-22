# KAMA Crossover Strategy with Price > 200 KAMA Filter and Fixed Stop Loss
# KAMA(55) vs KAMA(233) crossover with price above 200-period KAMA trend filter
# Enhanced with 2*ATR fixed stop loss.

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR


class KAMACrossover(Strategy):
    """
    KAMA Crossover Strategy with Trend Filter and Fixed Stop Loss.

    Uses three KAMAs:
    - Fast KAMA (len_fast=55): Short to medium-term trend
    - Slow KAMA (len_slow=233): Baseline trend direction
    - Filter KAMA (len_filter=200): Trend confirmation filter

    Entry Conditions (ALL must be true):
    1. Fast KAMA crosses above Slow KAMA
    2. Price is above 200-period KAMA (uptrend filter)

    Exit: Fast KAMA crosses below Slow KAMA (crossunder signal)

    Stop Loss Management:
    - **Entry Stop**: 2 × ATR(14) fixed stop set at entry (hard floor)

    All KAMAs use same fast_end/slow_end parameters (Kaufman 3-30 slower).
    Only the lookback period differs (55, 233, 200).
    """

    # ===== KAMA Parameters =====
    len_fast = 55  # Fast KAMA period (short to medium-term trend)
    len_slow = 233  # Slow KAMA period (baseline trend)
    len_filter = 200  # Filter KAMA period (long-term trend confirmation)
    fast_end = 0.666  # Fast smoothing endpoint (togglable: 0.666 or 0.4)
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

        self.kama_filter = self.I(
            self._compute_kama,
            self.data.close,
            self.len_filter,
            self.fast_end,
            self.slow_end,
            name=f"KAMA({self.len_filter})",
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
        Configure entry parameters: set fixed stop loss.

        Stop Loss Strategy:
        1. Fixed stop: entry_price - 2*ATR (hard floor)

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

        # Return stop loss configuration to the engine
        # Engine expects "stop" key for stop price
        return {"stop": fixed_stop}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Entry: Fast KAMA crosses above Slow KAMA AND Price > 200 KAMA Filter
        Exit: Fast KAMA crosses below Slow KAMA (crossunder signal)
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
        kama_filter_now = self._at(self.kama_filter, idx)
        close_now = self._at(self.data.close, idx)

        # Check for valid data (no NaN)
        if (
            np.isnan(kama_fast_now)
            or np.isnan(kama_fast_prev)
            or np.isnan(kama_slow_now)
            or np.isnan(kama_slow_prev)
            or np.isnan(kama_filter_now)
            or np.isnan(close_now)
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

        # Entry: Crossover + Price > 200 KAMA Filter
        if bullish_crossover and not was_in_position:
            # Check trend filter: price must be above 200-period KAMA
            if close_now > kama_filter_now:
                enter_long = True
                signal_reason = "KAMA Crossover + Uptrend Filter"
            else:
                signal_reason = "Crossover but below 200 KAMA"

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
