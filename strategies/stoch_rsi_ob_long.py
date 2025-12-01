#!/usr/bin/env python3
"""
Stochastic RSI Overbought/Oversold Long-Only Strategy with KAMA Filter

Based on Stochastic RSI indicator with configurable entry/exit modes:
- Entry on oversold conditions (Turn In Zone)
- Exit on overbought conditions (Turn In Zone)
- KAMA(55) > KAMA(233) momentum filter
- Risk management via ATR-based stop loss

Strategy uses the Strategy wrapper pattern for indicators.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, ADX, Aroon, EMA, TrendClassification, VolatilityClassification


class StochRSIOBLongStrategy(Strategy):
    """
    Stochastic RSI Overbought/Oversold Long-Only Strategy with KAMA Filter
    
    Generates long entry signals based on Stochastic RSI oversold conditions
    and exits on overbought conditions with KAMA momentum filter.
    """
    
    # Core Stoch RSI parameters
    rsi_length = 5
    stoch_length = 3
    smooth_length = 3  # %K smoothing
    smooth_d_length = 3  # %D smoothing
    ob_level = 70.0
    os_level = 10.0
    rsi_source = 'close'
    
    # Entry/Exit modes
    entry_mode = 'Enter Turn In Zone'
    exit_mode = 'Exit Turn In Zone'
    
    # Risk management
    use_atr_stop = True
    atr_length_stop = 14
    atr_multiple_stop = 4.0
    
    # ADX filter parameters
    use_adx_filter = True
    adx_threshold = 25
    
    # Aroon 100 Trend filter (Bull = Uptrend)
    use_aroon_trend_filter = True
    aroon_trend_target = 'Bull'  # 'Bull', 'Bear', or 'Sideways'
    
    # EMA5 > EMA20 trend confirmation
    use_ema_trend_filter = False
    
    # Volatility filter (High volatility preferred)
    use_volatility_filter = False
    volatility_target = "High"  # "Low", "Med", or "High"

    def __init__(self, **kwargs):
        """Initialize strategy with optional parameter overrides."""
        super().__init__()
        
        # Apply any parameter overrides
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        self.name = "Stochastic RSI OB/OS Long with Multi-Filter"
        self.description = (
            f"Long-only strategy using Stochastic RSI({self.rsi_length}, "
            f"{self.stoch_length}, {self.smooth_length}/{self.smooth_d_length}) with "
            f"ADX({self.adx_threshold}), Aroon Trend, EMA Trend, and Volatility filters"
        )

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""
        # Calculate Stochastic RSI
        self.stoch_k, self.stoch_d = self.I(
            self._compute_stoch_rsi,
            self.data.close,
            self.rsi_length,
            self.stoch_length,
            self.smooth_length,
            self.smooth_d_length,
            name="StochRSI",
        )

        # ADX filter
        if self.use_adx_filter:
            adx_result = self.I(
                self._compute_adx,
                self.data.high,
                self.data.low,
                self.data.close,
                14,
                name="ADX(14)",
            )
            # ADX returns (adx_series, pos_di, neg_di) from utils
            self.adx = adx_result[0] if isinstance(adx_result, tuple) else adx_result

        # Stop Loss ATR
        if self.use_atr_stop:
            self.atr_14 = self.I(
                ATR,
                self.data.high,
                self.data.low,
                self.data.close,
                self.atr_length_stop,
                name=f"ATR({self.atr_length_stop})",
                overlay=False,
            )

        # Aroon 100 Trend filter
        if self.use_aroon_trend_filter:
            # Aroon returns dict, so we compute it directly instead of using self.I()
            high_arr = self.data.high.astype(float).values
            low_arr = self.data.low.astype(float).values
            self.aroon_100 = Aroon(high_arr, low_arr, 100)

        # EMA5 and EMA20 for trend confirmation
        if self.use_ema_trend_filter:
            self.ema_5 = self.I(
                EMA,
                self.data.close,
                5,
                name="EMA(5)",
            )
            self.ema_20 = self.I(
                EMA,
                self.data.close,
                20,
                name="EMA(20)",
            )

        # Volatility filter
        if self.use_volatility_filter:
            self.atr_28 = self.I(
                ATR,
                self.data.high,
                self.data.low,
                self.data.close,
                28,
                name="ATR(28)",
                overlay=False,
            )

    def _compute_adx(self, high, low, close, period):
        """
        Compute Average Directional Index (ADX) using utils.indicators.ADX.
        
        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ADX period (typically 14)
        
        Returns:
            pandas Series with ADX values
        """
        # Convert to numpy arrays for utils.ADX function
        high_arr = high.astype(float).values
        low_arr = low.astype(float).values
        close_arr = close.astype(float).values
        
        # Call utils ADX which returns dict with 'adx', 'di_plus', 'di_minus'
        adx_dict = ADX(high_arr, low_arr, close_arr, period)
        
        # Extract ADX values and convert back to Series
        adx_values = adx_dict['adx']
        return pd.Series(adx_values, index=close.index)

    def _compute_stoch_rsi(self, close, rsi_len, stoch_len, smooth_len, smooth_d_len):
        """
        Compute Stochastic RSI with %K and %D lines.
        Pine Script ta.rsi uses Wilder's smoothing (RMA/EMA with alpha=1/n).
        
        Returns:
            tuple: (k_series, d_series)
        """
        close = close.astype(float)
        
        # Calculate RSI using Wilder's smoothing (RMA)
        # Pine Script's ta.rsi() uses RMA which is EMA with alpha=1/n
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        # Use alpha=1/rsi_len for Wilder's smoothing, adjust=True for proper initialization
        avg_gain = gain.ewm(alpha=1/rsi_len, min_periods=1, adjust=True).mean()
        avg_loss = loss.ewm(alpha=1/rsi_len, min_periods=1, adjust=True).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))
        
        # Calculate Stochastic of RSI
        rsi_lowest = rsi.rolling(window=stoch_len, min_periods=stoch_len).min()
        rsi_highest = rsi.rolling(window=stoch_len, min_periods=stoch_len).max()
        
        denominator = rsi_highest - rsi_lowest
        stoch_raw = np.where(
            denominator != 0.0,
            (rsi - rsi_lowest) / denominator * 100.0,
            0.0
        )
        
        # Smooth to get %K
        k = pd.Series(stoch_raw, index=close.index).rolling(
            window=smooth_len, 
            min_periods=smooth_len
        ).mean()
        
        # Smooth %K to get %D
        d = k.rolling(
            window=smooth_d_len,
            min_periods=smooth_d_len
        ).mean()
        
        return k, d

    def _at(self, x, i):
        """Accessor: safely get element at index i from Series or array."""
        return x.iloc[i] if hasattr(x, "iloc") else x[i]

    def on_entry(self, entry_time, entry_price, state):
        """Configure entry parameters: set fixed stop loss based on ATR."""
        if not self.use_atr_stop:
            return {}
        
        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            idx = None

        if idx is None or idx < 1 or np.isnan(self._at(self.atr_14, idx)):
            return {}

        atr_value = self._at(self.atr_14, idx)

        if np.isnan(atr_value) or atr_value <= 0:
            return {}

        # Calculate fixed stop loss
        fixed_stop = entry_price - (self.atr_multiple_stop * atr_value)
        return {"stop": fixed_stop}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.
        
        Entry: Stoch RSI Turn In Zone with support for 1-bar dip
            - Classic: K <= OS, K_prev <= OS, K > K_prev (turn up inside zone)
            - 1-bar dip: K > OS (exiting), K_prev <= OS (was inside), K_prev < K_prev2 (dipped), K_prev2 > OS (started above)
            AND KAMA(55) > KAMA(233) if filter enabled
        
        Exit: Stoch RSI Turn In Zone with support for 1-bar spike
            - Classic: K >= OB, K_prev >= OB, K < K_prev (turn down inside zone)
            - 1-bar spike: K < OB (exiting), K_prev >= OB (was inside), K_prev > K_prev2 (spiked), K_prev2 < OB (started below)
        """
        try:
            idx_result = self.data.index.get_loc(ts)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Need at least 3 bars for full detection (k, k_prev, k_prev2)
        if idx is None or idx < 2:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Get Stochastic RSI values
        k_now = self._at(self.stoch_k, idx)
        k_prev = self._at(self.stoch_k, idx - 1)
        k_prev2 = self._at(self.stoch_k, idx - 2)

        # Check for valid Stoch RSI data
        if np.isnan(k_now) or np.isnan(k_prev) or np.isnan(k_prev2):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        was_in_position = state.get("qty", 0) > 0
        enter_long = False
        exit_long = False
        signal_reason = ""

        if not was_in_position:
            # Check entry: Turn In Zone with 1-bar dip support
            # Classic turn entirely inside OS zone
            classic_turn = (
                (k_now <= self.os_level) and 
                (k_prev <= self.os_level) and 
                (k_now > k_prev)
            )
            
            # 1-bar dip below OS: bar[1] inside, bar[2] above, current bar exits up
            one_bar_dip = (
                (k_prev <= self.os_level) and 
                (k_now > self.os_level) and 
                (k_prev < k_prev2) and 
                (k_prev2 > self.os_level)
            )

            turn_in_zone = classic_turn or one_bar_dip

            if turn_in_zone:
                # Check ADX filter if enabled
                if self.use_adx_filter:
                    adx_val = self._at(self.adx, idx)
                    
                    if np.isnan(adx_val):
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                    
                    if adx_val < self.adx_threshold:
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                
                # Check Aroon Trend filter if enabled
                if self.use_aroon_trend_filter:
                    # Aroon returns dict with numpy arrays from Strategy.I()
                    aroon_up_arr = self.aroon_100['aroon_up']
                    aroon_down_arr = self.aroon_100['aroon_down']
                    
                    if idx >= len(aroon_up_arr) or idx >= len(aroon_down_arr):
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                    
                    # Access numpy arrays directly
                    aroon_up_val = aroon_up_arr[idx] if hasattr(aroon_up_arr, '__getitem__') else self._at(aroon_up_arr, idx)
                    aroon_down_val = aroon_down_arr[idx] if hasattr(aroon_down_arr, '__getitem__') else self._at(aroon_down_arr, idx)
                    
                    if np.isnan(aroon_up_val) or np.isnan(aroon_down_val):
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                    
                    aroon_trend = TrendClassification(aroon_up_val, aroon_down_val, period=100)
                    
                    if aroon_trend != self.aroon_trend_target:
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                
                # Check EMA Trend filter if enabled
                if self.use_ema_trend_filter:
                    ema5_val = float(self._at(self.ema_5, idx))
                    ema20_val = float(self._at(self.ema_20, idx))
                    
                    if np.isnan(ema5_val) or np.isnan(ema20_val):
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                    
                    if ema5_val <= ema20_val:
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                
                # Check Volatility filter if enabled
                if self.use_volatility_filter:
                    atr_val = float(self._at(self.atr_28, idx))
                    close_val = float(self._at(self.data["close"], idx))
                    
                    if np.isnan(atr_val) or np.isnan(close_val) or close_val <= 0:
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                    
                    atr_pct = (atr_val / close_val) * 100.0
                    volatility = VolatilityClassification(atr_pct, period=28)
                    
                    if volatility != self.volatility_target:
                        return {"enter_long": False, "exit_long": False, "signal_reason": ""}
                
                enter_long = True
                signal_reason = "Stoch RSI Turn In Zone + Multi-Filter"

        else:
            # Check exit: Turn In Zone with 1-bar spike support
            # Classic turn entirely inside OB zone
            classic_turn = (
                (k_now >= self.ob_level) and 
                (k_prev >= self.ob_level) and 
                (k_now < k_prev)
            )
            
            # 1-bar spike above OB: bar[1] inside, bar[2] below, current bar exits down
            one_bar_spike = (
                (k_prev >= self.ob_level) and 
                (k_now < self.ob_level) and 
                (k_prev > k_prev2) and 
                (k_prev2 < self.ob_level)
            )

            turn_in_zone = classic_turn or one_bar_spike

            if turn_in_zone:
                exit_long = True
                signal_reason = "Stoch RSI Turn In Overbought"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass

