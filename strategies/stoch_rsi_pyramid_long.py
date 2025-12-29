#!/usr/bin/env python3
"""
Stochastic RSI OB/OS Long with Pyramiding Strategy (v5 EXACT Pine Script Replica)

Exact replica of TradingView Pine Script v6 "Stoch RSI OB/OS Long v5 (CORRECTED)":
- Entry on Turn-In-Zone signals in Oversold (OS) region (K <= 10)
- Pyramid up to 2 positions when K exits and re-enters OS zone (1 original + 1 re-entry)
- Exit on Turn-In-Zone signals in Overbought (OB) region (K >= 70)
- ATR-based stop loss (2.0x ATR) - DISABLED by default

FILTERS:
1. ATR % > 3 - Entry only when ATR% above threshold (volatility filter)
2. VIX < 14 OR VIX > 20 - Entry only in fear/greed zones, not neutral
3. ADX(28) > 25 - Entry only when strong trend (directional movement)

All logic replicated exactly from Pine Script.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ADX, ATR, EMA, SMA, RSI


class StochRSIPyramidLongStrategy(Strategy):
    """
    Stochastic RSI with Pyramiding Long-Only Strategy v5 EXACT

    ENTRY: Turn-In-Zone signals in Oversold (OS) region
    - Turn UP: (K <= OS or K_prev <= OS) and (K > K_prev)
    - One-bar dip recovery: K_prev <= OS and K > OS and K_prev < K_prev2 and K_prev2 > OS

    PYRAMID: Up to 2 total entries (1 original + 1 re-entry)
    - K must exit OS (go > 10)
    - Then re-enter OS (come back <= 10)
    - State: canPyramidAgain, entriesThisCycle, hasExitedOS

    EXIT: Turn-In-Zone signals in Overbought (OB) region
    - Turn DOWN: (K >= OB or K_prev >= OB) and (K < K_prev)
    - One-bar spike decline: K_prev >= OB and K < OB and K_prev > K_prev2 and K_prev2 < OB

    FILTERS:
    1. ATR % > 3 - Entry only when ATR% above threshold (volatility)
    2. VIX < 14 OR VIX > 20 - Entry only in fear/greed zones
    3. ADX(28) > 25 - Entry only when strong trend exists

    STOP LOSS (DISABLED by default):
    - 2 ATR below entry
    """

    # ===== STOCH RSI PARAMETERS (from Pine Script inputs) =====
    rsi_len = 14  # RSI Length
    stoch_len = 5  # Stoch Length (RSI lookback)
    smooth_len = 3  # Smooth Length %K
    smooth_d_len = 3  # Smooth Length %D
    ob_level = 70.0  # Overbought Level
    os_level = 10.0  # Oversold Level

    # ===== ATR STOP =====
    use_atr_stop = False  # Use ATR Stop - DISABLED
    atr_len_stop = 14  # ATR Length
    atr_mult_stop = 3.0  # ATR Multiple (not used when disabled)

    # ===== FILTERS =====
    # Filter 1: ATR % > 3 (volatility filter)
    use_atr_filter = True  # ENABLED
    atr_pct_threshold = 3.0  # ATR % must be > this
    
    # Filter 2: VIX < 14 OR VIX > 20 (regime filter)
    use_vix_filter = True  # ENABLED
    vix_low_threshold = 14.0  # VIX below this = fear zone (good)
    vix_high_threshold = 20.0  # VIX above this = greed zone (good)
    
    # Filter 3: ADX(28) > 25 (trend strength filter)
    use_adx_filter = True  # ENABLED
    adx_len = 28  # ADX Length
    adx_threshold = 25.0  # ADX must be > this

    # ===== PYRAMIDING =====
    max_pyramid_entries = 2  # Max entries per cycle (1 original + 1 re-entry)

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides."""
        super().__init__()

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

        self.name = "Stochastic RSI Pyramid Long v5"
        self.description = (
            f"Pine Script v6 exact replica. "
            f"Stoch RSI({self.rsi_len}, {self.stoch_len}, "
            f"{self.smooth_len}/{self.smooth_d_len}). "
            f"Filters: Price>EMA20, ATR%>3, RSI>60. "
            f"Stop: {self.atr_mult_stop}x ATR"
        )

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""
        # Stochastic RSI - exact Pine Script calculation
        self.stoch_k, self.stoch_d = self.I(
            self._compute_stoch_rsi,
            self.data.close,
            self.rsi_len,
            self.stoch_len,
            self.smooth_len,
            self.smooth_d_len,
            name="StochRSI_Pyramid",
        )

        # ATR for stop loss and ATR% filter
        self.atr = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_len_stop,
            name=f"ATR({self.atr_len_stop})",
            overlay=False,
        )
        
        # ADX for trend strength filter (ADX > 25)
        if self.use_adx_filter:
            adx_result = ADX(
                self.data.high,
                self.data.low,
                self.data.close,
                self.adx_len,
            )
            self.adx_values = adx_result["adx"]

    def _at(self, x, i):
        """Accessor: safely get element at index i from Series or array."""
        return x.iloc[i] if hasattr(x, "iloc") else x[i]

    def on_bar(self, ts, row, state):
        """Generate signals on each bar using exact Pine Script v6 logic.
        
        EXACT REPLICA of Pine Script logic - follows sections 2-6 from the script.
        """
        # Get index of current bar
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Need at least 4 bars for proper lookback (decision made on idx-1)
        if idx is None or idx < 3:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ========== GET K VALUES ==========
        # Signal bar = idx (current bar where decision is made)
        # Entry happens at idx+1 open
        # K values at signal bar for crossover detection
        k_now = self._at(self.stoch_k, idx)
        k_prev = self._at(self.stoch_k, idx - 1)
        k_prev2 = self._at(self.stoch_k, idx - 2)

        # haveK = not na(k_now) and not na(k_prev) and not na(k_prev2)
        have_k = not np.isnan(k_now) and not np.isnan(k_prev) and not np.isnan(k_prev2)
        if not have_k:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ATR for stop loss and filters (use signal bar idx)
        atr_val = self._at(self.atr, idx)
        
        # Validate ATR value
        if np.isnan(atr_val):
            atr_val = 0.0

        # ========== FILTERS (Ichimoku-style: all_filters_pass pattern) ==========
        all_filters_pass = True

        # Filter 1: ATR % > 3 (volatility filter)
        if all_filters_pass and self.use_atr_filter:
            if row["close"] > 0 and not np.isnan(atr_val):
                atr_pct = (atr_val / row["close"]) * 100.0
                if atr_pct <= self.atr_pct_threshold:
                    all_filters_pass = False
            else:
                all_filters_pass = False

        # Filter 2: VIX < 14 OR VIX > 20 (regime filter - avoid neutral zone)
        if all_filters_pass and self.use_vix_filter:
            # VIX comes from the row (loaded by standard_run_basket.py)
            vix_val = row.get("india_vix", np.nan) if hasattr(row, 'get') else (
                row["india_vix"] if "india_vix" in row.index else np.nan
            )
            if np.isnan(vix_val):
                # FIXED: Fail filter if VIX data is missing (don't trade blind)
                all_filters_pass = False
            elif not (vix_val < self.vix_low_threshold or vix_val > self.vix_high_threshold):
                # Fail if 14 <= VIX <= 20 (neutral zone)
                all_filters_pass = False

        # Filter 3: ADX(28) > 25 (trend strength filter)
        if all_filters_pass and self.use_adx_filter and hasattr(self, 'adx_values'):
            adx_val = self._at(self.adx_values, idx)
            if np.isnan(adx_val):
                # FIXED: Fail filter if ADX data is missing (don't trade blind)
                all_filters_pass = False
            elif adx_val <= self.adx_threshold:
                all_filters_pass = False

        # ========== TURN-IN-ZONE SIGNALS (ENTRY) ==========
        # turnUpInOS = haveK and (k_now <= osLevel or k_prev <= osLevel) and (k_now > k_prev)
        turn_up_in_os = (
            have_k
            and (k_now <= self.os_level or k_prev <= self.os_level)
            and (k_now > k_prev)
        )

        # oneBarDipRecovery = haveK and (k_prev <= osLevel) and (k_now > osLevel) and
        #                    (k_prev < k_prev2) and (k_prev2 > osLevel)
        one_bar_dip_recovery = (
            have_k
            and (k_prev <= self.os_level)
            and (k_now > self.os_level)
            and (k_prev < k_prev2)
            and (k_prev2 > self.os_level)
        )

        # turnInOSZone = turnUpInOS or oneBarDipRecovery
        turn_in_os_zone = turn_up_in_os or one_bar_dip_recovery

        # ========== TURN-IN-ZONE SIGNALS (EXIT) ==========
        # turnDownInOB = haveK and (k_now >= obLevel or k_prev >= obLevel) and (k_now < k_prev)
        turn_down_in_ob = (
            have_k
            and (k_now >= self.ob_level or k_prev >= self.ob_level)
            and (k_now < k_prev)
        )

        # oneBarSpikeDecline = haveK and (k_prev >= obLevel) and (k_now < obLevel) and
        #                     (k_prev > k_prev2) and (k_prev2 < obLevel)
        one_bar_spike_decline = (
            have_k
            and (k_prev >= self.ob_level)
            and (k_now < self.ob_level)
            and (k_prev > k_prev2)
            and (k_prev2 < self.ob_level)
        )

        # turnInOBZone = turnDownInOB or oneBarSpikeDecline
        turn_in_ob_zone = turn_down_in_ob or one_bar_spike_decline

        # ========== POSITION & PYRAMID STATE TRACKING ==========
        # inPos = strategy.position_size > 0
        qty = state.get("qty", 0)
        in_pos = qty > 0

        # Initialize state variables (var in Pine Script)
        if "can_pyramid_again" not in state:
            state["can_pyramid_again"] = False
        if "entries_this_cycle" not in state:
            state["entries_this_cycle"] = 0
        if "has_exited_os" not in state:
            state["has_exited_os"] = False

        # EXACT Pine Script logic:
        # if not inPos
        #     canPyramidAgain := false
        #     entriesThisCycle := 0
        #     hasExitedOS := false
        # else if inPos
        #     if k_now > osLevel
        #         hasExitedOS := true
        #     if hasExitedOS and k_now <= osLevel
        #         canPyramidAgain := true

        if not in_pos:
            state["can_pyramid_again"] = False
            state["entries_this_cycle"] = 0
            state["has_exited_os"] = False
        elif in_pos:
            # Step 1: Track if K has exited OS zone
            if k_now > self.os_level:
                state["has_exited_os"] = True

            # Step 2: Update canPyramidAgain
            if state["has_exited_os"] and k_now <= self.os_level:
                state["can_pyramid_again"] = True

        # ========== ENTRY CONDITIONS ==========
        # initialEntrySignal = turnInOSZone and filterPass and not inPos
        initial_entry_signal = turn_in_os_zone and all_filters_pass and not in_pos

        # pyramidEntrySignal = turnInOSZone and filterPass and inPos and
        #                     canPyramidAgain and entriesThisCycle < 3
        pyramid_entry_signal = (
            turn_in_os_zone
            and all_filters_pass
            and in_pos
            and state["can_pyramid_again"]
            and state["entries_this_cycle"] < self.max_pyramid_entries
        )

        # When an entry is taken, reset tracking
        # if initialEntrySignal
        #     entriesThisCycle += 1
        #     hasExitedOS := false
        #     canPyramidAgain := false
        if initial_entry_signal:
            state["entries_this_cycle"] += 1
            state["has_exited_os"] = False
            state["can_pyramid_again"] = False

        # if pyramidEntrySignal
        #     entriesThisCycle += 1
        #     hasExitedOS := false
        #     canPyramidAgain := false
        if pyramid_entry_signal:
            state["entries_this_cycle"] += 1
            state["has_exited_os"] = False
            state["can_pyramid_again"] = False

        # ========== EXIT CONDITION ==========
        # exitSignal = turnInOBZone and inPos
        exit_signal = turn_in_ob_zone and in_pos

        # ========== STOP LOSS ==========
        # var float stopPrice = na
        if "stop_price" not in state:
            state["stop_price"] = None

        stop_price = None
        if (initial_entry_signal or pyramid_entry_signal) and self.use_atr_stop:
            stop_price = row["close"] - atr_val * self.atr_mult_stop
            state["stop_price"] = stop_price

        if exit_signal:
            state["stop_price"] = None

        # ========== RETURN ACTION ==========
        enter_long = initial_entry_signal or pyramid_entry_signal
        entry_type = "LONG"
        
        if pyramid_entry_signal:
            entry_type = f"PYRAMID_{state['entries_this_cycle']}"
        elif initial_entry_signal:
            entry_type = "ENTRY_LONG"

        return {
            "enter_long": enter_long,
            "exit_long": exit_signal,
            "signal_reason": (
                f"{entry_type} K={k_now:.1f}" if enter_long
                else f"EXIT K={k_now:.1f}" if exit_signal
                else ""
            ),
            "stop": stop_price,  # Engine expects "stop" not "stop_price"
            "entry_type": entry_type if enter_long else None,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass

    @staticmethod
    def _compute_stoch_rsi(
        close_series, rsi_len, stoch_len, k_smooth, d_smooth
    ):
        """Compute Stochastic RSI indicator.
        
        Exact Pine Script replication:
        1. RSI = ta.rsi(close, rsi_len)
        2. rsi_highest = ta.highest(rsi, stoch_len)
        3. rsi_lowest = ta.lowest(rsi, stoch_len)
        4. denom = rsi_highest - rsi_lowest
        5. stoch_raw = denom != 0 ? (rsi - rsi_lowest) / denom * 100.0 : 0.0
        6. k = ta.sma(stoch_raw, smooth_len)
        7. d = ta.sma(k, smooth_d_len)
        """
        from utils.indicators import RSI

        # Step 1: Calculate RSI
        rsi_vals = RSI(close_series, rsi_len)

        # Step 2-3: Get RSI highest/lowest over stoch_len period
        rsi_series = pd.Series(rsi_vals)
        highest_rsi = rsi_series.rolling(window=stoch_len).max().values
        lowest_rsi = rsi_series.rolling(window=stoch_len).min().values

        # Step 4-5: Calculate Stochastic RSI with zero handling
        range_val = highest_rsi - lowest_rsi
        with np.errstate(divide='ignore', invalid='ignore'):
            stoch_vals = np.where(
                range_val != 0, ((rsi_vals - lowest_rsi) / range_val) * 100, 0
            )

        # Step 6-7: Smooth K and D
        k = SMA(stoch_vals, k_smooth)
        d = SMA(k, d_smooth)

        return k, d
