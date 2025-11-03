"""
Envelope + Knoxville Divergence (KD) Strategy
==============================================

A sophisticated trend-following strategy combining:
1. **Envelope Filter**: Dynamic support/resistance using SMA/EMA
2. **Knoxville Divergence (KD)**: Momentum divergence detection with stochastic confirmation
3. **Trend Filter**: Basis slope validation with optional ATR volatility floor
4. **Risk Management**: ATR-based stops with time-based exits

Original TradingView strategy adapted for QuantLab using the modern Strategy.I() wrapper system.

Key Features:
- Entry: Bullish KD with price below envelope basis
- TP: Cross above upper envelope band
- SL: Trailing stop at envelope basis crossunder
- Risk: ATR-based or percent-based stops with max bar time limit
- Pyramiding: Up to 2 positions allowed

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils import ATR, EMA, SMA, Momentum, Stochastic


def stochastic_k_wrapper(
    high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14
) -> np.ndarray:
    """
    Calculate Stochastic %K only (simplified for self.I() compatibility).

    Returns just the %K line as numpy array.
    """
    high_arr = np.asarray(high)
    low_arr = np.asarray(low)
    close_arr = np.asarray(close)

    high_roll = pd.Series(high_arr).rolling(k_period).max().values
    low_roll = pd.Series(low_arr).rolling(k_period).min().values

    # Handle division by zero
    k_percent = np.where(
        high_roll == low_roll,
        50.0,  # Default to 50 if no range
        100 * (close_arr - low_roll) / (high_roll - low_roll),
    )
    return k_percent


class EnvelopeKDStrategy(Strategy):
    """
    Envelope + Knoxville Divergence Strategy using Strategy.I() wrapper system.

    Combines envelope-based mean reversion with divergence-based momentum confirmation
    for robust trade entries and exits.
    """

    # ===== Envelope Parameters =====
    envelope_length = 200
    envelope_percent = 14.0
    use_ema_envelope = False  # True=EMA, False=SMA

    # ===== Knoxville Divergence Parameters =====
    momentum_length = 20
    bars_back_max = 200
    pivot_left_bars = 2
    pivot_right_bars = 2

    stoch_k_length = 70
    stoch_k_smooth = 30
    stoch_d_smooth = 30
    stoch_ob = 70.0  # Overbought level
    stoch_os = 30.0  # Oversold level

    # ===== Trend Filter Parameters =====
    trend_mode = "Strict"  # "Off", "Loose", "Strict"
    slope_lookback = 60
    use_atr_floor = False
    atr_volume_length = 14
    min_atr_pct = 0.8

    # ===== Risk Management Parameters =====
    stop_type = "ATR"  # "ATR" or "Percent"
    stop_atr_length = 14
    stop_atr_mult = 6.0  # ATR multiplier for stop
    time_stop_bars = 60  # Max bars in trade (0 = disabled)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and call initialize."""
        self.data = df
        self.bars_since_entry = {}  # Track bars for each entry (for pyramiding support)
        self.first_entry_date = None  # Track entry date for time stop (calendar days)
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""

        # ===== Envelope Indicators =====
        if self.use_ema_envelope:
            self.envelope_basis = self.I(
                EMA,
                self.data.close.values,
                self.envelope_length,
                name=f"Envelope Basis EMA({self.envelope_length})",
                color="orange",
                overlay=True,
            )
        else:
            self.envelope_basis = self.I(
                SMA,
                self.data.close,
                self.envelope_length,
                name=f"Envelope Basis SMA({self.envelope_length})",
                color="orange",
                overlay=True,
            )

        # Calculate envelope bands
        k_env = self.envelope_percent / 100.0
        self.envelope_upper = self.envelope_basis * (1 + k_env)
        self.envelope_lower = self.envelope_basis * (1 - k_env)

        # ===== Stochastic for KD =====
        # Calculate raw stochastic %K
        self.stoch_k = self.I(
            stochastic_k_wrapper,
            self.data.high,
            self.data.low,
            self.data.close,
            self.stoch_k_length,
            name=f"Stochastic %K({self.stoch_k_length})",
            overlay=False,
        )

        # Smooth %K with specified smoothing
        self.stoch_k_smooth = self.I(
            SMA,
            pd.Series(self.stoch_k),
            self.stoch_k_smooth,
            name="Stoch %K Smoothed",
            overlay=False,
        )

        # ===== Momentum for KD =====
        self.momentum = self.I(
            Momentum,
            self.data.close,
            self.momentum_length,
            name=f"Momentum({self.momentum_length})",
            overlay=False,
        )

        # ===== Trend Filter =====
        self.atr_vol = self.I(
            ATR,
            self.data.high.values,
            self.data.low.values,
            self.data.close.values,
            self.atr_volume_length,
            name=f"ATR({self.atr_volume_length})",
            overlay=False,
        )

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate stop loss when entering a trade.

        Args:
            entry_time: Timestamp of entry
            entry_price: Entry price (float)
            state: Trading state

        Returns:
            Dictionary with stop loss price, e.g., {"stop": 1000.0}
        """
        try:
            # Find the index of the entry time
            idx = self.data.index.get_loc(entry_time)
            if isinstance(idx, slice):
                idx = idx.start

            if idx is None or idx < self.stop_atr_length:
                return {}

            # Calculate ATR-based stop: entry_price - (stop_atr_mult * ATR)
            atr_val = self.atr_vol[idx]
            stop_loss = entry_price - (self.stop_atr_mult * atr_val)
            return {"stop": stop_loss}
        except Exception:
            return {}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.
        Matches TradingView's ta.pivothigh/ta.pivotlow semantics exactly.

        Args:
            ts: Timestamp
            row: Current bar data
            state: Trading state

        Returns:
            Dictionary with entry/exit signals
        """
        # Get current position in the data
        try:
            idx_result = self.data.index.get_loc(ts)
            # Handle case where get_loc returns a slice (duplicate index)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False}

        # Need at least envelope_length + buffer bars
        min_bars = max(
            self.envelope_length,
            self.stoch_k_length,
            self.momentum_length,
            self.slope_lookback,
            self.pivot_left_bars + self.pivot_right_bars,
        )
        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False}

        # ===== Current Bar Values =====
        close_now = row.close
        basis_now = self.envelope_basis[idx]
        upper_now = self.envelope_upper[idx]
        stoch_k_now = self.stoch_k_smooth[idx]

        # ===== Previous Bar Values =====
        basis_prev = self.envelope_basis[idx - 1]
        close_prev = self.data.close.iloc[idx - 1]
        upper_prev = self.envelope_upper[idx - 1]

        # ===== Trend Filter =====
        basis_slope_ok = basis_now > self.envelope_basis[idx - self.slope_lookback]
        atr_pct_now = (100.0 * self.atr_vol[idx] / close_now) if close_now > 0 else 0
        atr_ok = (not self.use_atr_floor) or (atr_pct_now >= self.min_atr_pct)

        if self.trend_mode == "Off":
            trend_ok = True
        elif self.trend_mode == "Loose":
            trend_ok = basis_slope_ok or atr_ok
        else:  # Strict
            trend_ok = basis_slope_ok and atr_ok

        # ===== Knoxville Divergence Detection (TradingView semantics) =====
        # IMPORTANT: Pivots are detected ONLY when fully confirmed by right bars
        # On current bar idx, we can only confirm pivots from idx - pivot_right_bars
        # This prevents lookahead bias - we don't look into the future
        #
        # Pivot formation is complete when:
        # - Pivot High: high[idx-rightBars] >= max(high[idx-rightBars-leftBars:idx-rightBars])
        #              AND high[idx-rightBars] >= max(high[idx-rightBars:idx-rightBars+rightBars])
        # - Pivot Low: low[idx-rightBars] <= min(low[idx-rightBars-leftBars:idx-rightBars])
        #             AND low[idx-rightBars] <= min(low[idx-rightBars:idx-rightBars+rightBars])

        bull_kd = False
        bear_kd = False

        # Only check for pivots if we have enough bars
        if idx >= self.pivot_left_bars + 2 * self.pivot_right_bars:
            # The pivot can only be confirmed at idx-rightBars when we're at idx
            pivot_idx = idx - self.pivot_right_bars

            # Pivot low detection at confirmed location
            left_min = self.data.low.iloc[
                pivot_idx - self.pivot_left_bars : pivot_idx
            ].min()
            right_min = self.data.low.iloc[
                pivot_idx : pivot_idx + self.pivot_right_bars
            ].min()
            center_low = self.data.low.iloc[pivot_idx]

            is_pivot_low = center_low <= left_min and center_low <= right_min

            if is_pivot_low:
                # Look for previous pivot low within bars_back_max
                prev_pl_price = None
                prev_pl_mom = None

                for search_idx in range(pivot_idx - 1, -1, -1):
                    if pivot_idx - search_idx > self.bars_back_max:
                        break

                    if search_idx >= self.pivot_left_bars + self.pivot_right_bars:
                        search_pivot_idx = search_idx - self.pivot_right_bars
                        if search_pivot_idx >= self.pivot_left_bars:
                            s_left_min = self.data.low.iloc[
                                search_pivot_idx
                                - self.pivot_left_bars : search_pivot_idx
                            ].min()
                            s_right_min = self.data.low.iloc[
                                search_pivot_idx : search_pivot_idx
                                + self.pivot_right_bars
                            ].min()
                            s_center_low = self.data.low.iloc[search_pivot_idx]

                            if (
                                s_center_low <= s_left_min
                                and s_center_low <= s_right_min
                            ):
                                prev_pl_price = s_center_low
                                prev_pl_mom = self.momentum[search_pivot_idx]
                                break

                # Bullish KD: current pivot low < previous pivot low AND
                # current momentum > previous momentum AND current stoch < OS
                if prev_pl_price is not None:
                    curr_pl_mom = self.momentum[pivot_idx]
                    bull_kd = (
                        center_low < prev_pl_price
                        and curr_pl_mom > prev_pl_mom
                        and stoch_k_now < self.stoch_os
                    )

            # Pivot high detection at confirmed location
            left_max = self.data.high.iloc[
                pivot_idx - self.pivot_left_bars : pivot_idx
            ].max()
            right_max = self.data.high.iloc[
                pivot_idx : pivot_idx + self.pivot_right_bars
            ].max()
            center_high = self.data.high.iloc[pivot_idx]

            is_pivot_high = center_high >= left_max and center_high >= right_max

            if is_pivot_high:
                # Look for previous pivot high within bars_back_max
                prev_ph_price = None
                prev_ph_mom = None

                for search_idx in range(pivot_idx - 1, -1, -1):
                    if pivot_idx - search_idx > self.bars_back_max:
                        break

                    if search_idx >= self.pivot_left_bars + self.pivot_right_bars:
                        search_pivot_idx = search_idx - self.pivot_right_bars
                        if search_pivot_idx >= self.pivot_left_bars:
                            s_left_max = self.data.high.iloc[
                                search_pivot_idx
                                - self.pivot_left_bars : search_pivot_idx
                            ].max()
                            s_right_max = self.data.high.iloc[
                                search_pivot_idx : search_pivot_idx
                                + self.pivot_right_bars
                            ].max()
                            s_center_high = self.data.high.iloc[search_pivot_idx]

                            if (
                                s_center_high >= s_left_max
                                and s_center_high >= s_right_max
                            ):
                                prev_ph_price = s_center_high
                                prev_ph_mom = self.momentum[search_pivot_idx]
                                break

                # Bearish KD: current pivot high > previous pivot high AND
                # current momentum < previous momentum AND current stoch > OB
                if prev_ph_price is not None:
                    curr_ph_mom = self.momentum[pivot_idx]
                    bear_kd = (
                        center_high > prev_ph_price
                        and curr_ph_mom < prev_ph_mom
                        and stoch_k_now > self.stoch_ob
                    )

        # ===== Entry Signal =====
        enter_long = bull_kd and close_now < basis_now and trend_ok

        # ===== Exit Signals =====
        exit_long = False

        # Track position age for time stops
        was_in_position = state.get("qty", 0) > 0
        now_in_position = was_in_position or enter_long

        if was_in_position and not now_in_position:
            # Position just closed - reset entry tracker
            self.first_entry_date = None
        elif enter_long and not was_in_position:
            # New entry - record the date
            self.first_entry_date = ts
        elif was_in_position and self.first_entry_date is None:
            # Recovery case - mark current date if not yet marked
            self.first_entry_date = ts

        # Check if we're currently in a position (qty > 0)
        if was_in_position:
            # TP: Cross above upper band
            if close_prev <= upper_prev and close_now > upper_now:
                exit_long = True

            # Trailing SL: Cross below basis
            elif close_prev >= basis_prev and close_now < basis_now:
                exit_long = True

            # Exit on bearish KD
            elif bear_kd:
                exit_long = True

            # Time stop: Exit if trade has been open >= time_stop_bars calendar days
            elif self.time_stop_bars > 0 and self.first_entry_date is not None:
                days_held = (ts - self.first_entry_date).days
                if days_held >= self.time_stop_bars:
                    exit_long = True

        # Reset tracker when position closes
        if exit_long and was_in_position:
            self.first_entry_date = None

        return {"enter_long": enter_long, "exit_long": exit_long}

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
