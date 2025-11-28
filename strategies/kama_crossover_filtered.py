# KAMA Crossover Strategy with New Filters
# Entry Filters: 
#   1. KAMA crossover (Fast > Slow)
#   2. Short Trend (Aroon 25): Bull or Sideways
#   3. Volatility (14): High or Med
#   4. DI_Bullish (14): True (+DI > -DI)
#   5. CCI (20): > 0
#   6. Price > EMA(20)

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import (
    ATR, ADX, Aroon, CCI, EMA, TrendClassification, VolatilityClassification
)


class KAMACrossoverFiltered(Strategy):
    """
    KAMA Crossover Strategy with New Filters.

    Entry Conditions (ALL must be true):
    1. Fast KAMA crosses above Slow KAMA
    2. Short Trend (Aroon 25): Bull or Sideways
    3. Volatility (14): High or Med
    4. DI_Bullish (14): True (+DI > -DI)
    5. CCI (20): > 0
    6. Price > EMA(20)

    Exit: Fast KAMA crosses below Slow KAMA

    Stop Loss: 2 × ATR(14) fixed stop at entry
    """

    # ===== KAMA Parameters =====
    len_fast = 55
    len_slow = 233
    fast_end = 0.666
    slow_end = 0.0645

    # ===== Stop Loss Parameters =====
    atr_period = 14
    atr_multiplier = 2.0

    # ===== Filter Parameters =====
    aroon_period = 25
    volatility_period = 14
    di_period = 14
    cci_period = 20
    ema_period = 20

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df.copy()
        
        # Pre-calculate all indicators
        self._calculate_indicators()

        self.initialize()
        return super().prepare(df)

    def _calculate_indicators(self):
        """Pre-calculate all indicators using utils.indicators."""
        # KAMA
        self.data["kama_fast"] = self._compute_kama(
            self.data["close"], self.len_fast, self.fast_end, self.slow_end
        )
        self.data["kama_slow"] = self._compute_kama(
            self.data["close"], self.len_slow, self.fast_end, self.slow_end
        )

        # ATR for stop loss and volatility classification
        self.data["atr"] = ATR(
            self.data["high"].values,
            self.data["low"].values,
            self.data["close"].values,
            self.atr_period
        )

        # EMA(20) for price filter
        self.data["ema_20"] = EMA(self.data["close"].values, self.ema_period)

        # Aroon Oscillator (Short Trend)
        aroon_result = Aroon(self.data["high"].values, self.data["low"].values, self.aroon_period)
        self.data["aroon_up"] = aroon_result["aroon_up"]
        self.data["aroon_down"] = aroon_result["aroon_down"]

        # Volatility Classification
        atr_pct = (self.data["atr"] / self.data["close"].values) * 100
        self.data["volatility"] = [
            VolatilityClassification(atr_pct.iloc[i] if hasattr(atr_pct, 'iloc') else atr_pct[i], self.volatility_period)
            for i in range(len(atr_pct))
        ]

        # ADX (includes DI+ and DI-)
        adx_result = ADX(
            self.data["high"].values,
            self.data["low"].values,
            self.data["close"].values,
            self.di_period
        )
        self.data["di_plus"] = adx_result["di_plus"]
        self.data["di_minus"] = adx_result["di_minus"]

        # CCI
        self.data["cci"] = CCI(
            self.data["high"].values,
            self.data["low"].values,
            self.data["close"].values,
            self.cci_period
        )

    def initialize(self):
        """Initialize (legacy method)."""
        pass

    def _compute_kama(self, close, lookback, fast_end, slow_end):
        """Compute Kaufman Adaptive Moving Average."""
        close = close.astype(float)
        n = len(close)
        kama = np.full(n, np.nan)

        xvnoise = (close - close.shift(1)).abs()
        nsignal = (close - close.shift(lookback)).abs()
        nnoise = xvnoise.rolling(window=lookback, min_periods=lookback).sum()

        er = nsignal / nnoise
        er = er.replace([np.inf, -np.inf], np.nan).fillna(0.0)

        sc = (er * (fast_end - slow_end) + slow_end) ** 2

        kama[0] = close.iloc[0]

        for i in range(1, n):
            prev_kama = kama[i - 1]
            current_close = close.iloc[i]
            current_sc = sc.iloc[i]

            if np.isnan(prev_kama):
                base = current_close
            else:
                base = prev_kama

            if not np.isnan(current_sc):
                kama[i] = base + current_sc * (current_close - base)
            else:
                kama[i] = np.nan

        return pd.Series(kama, index=close.index)

    def _at(self, x, i):
        """Safely get element at index i."""
        if isinstance(x, (pd.Series, np.ndarray)):
            if hasattr(x, 'iloc'):
                return x.iloc[i]
            else:
                return x[i]
        return x

    def on_entry(self, entry_time, entry_price, state):
        """Configure entry stop loss."""
        try:
            idx_result = self.data.index.get_loc(entry_time)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError):
            return {}

        if idx is None or idx < 1:
            return {}
            
        atr_value = self._at(self.data["atr"], idx)
        if np.isnan(atr_value) or atr_value <= 0:
            return {}

        fixed_stop = entry_price - (self.atr_multiplier * atr_value)
        return {"stop": fixed_stop}

    def on_bar(self, ts, row, state):
        """Execute trading logic on each bar."""
        try:
            idx_result = self.data.index.get_loc(ts)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        if idx is None or idx < 1:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Get KAMA values
        kama_fast_now = self._at(self.data["kama_fast"], idx)
        kama_fast_prev = self._at(self.data["kama_fast"], idx - 1)
        kama_slow_now = self._at(self.data["kama_slow"], idx)
        kama_slow_prev = self._at(self.data["kama_slow"], idx - 1)

        # Check for valid KAMA data
        if any(np.isnan(x) for x in [kama_fast_now, kama_fast_prev, kama_slow_now, kama_slow_prev]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Detect crossovers
        bullish_crossover = (kama_fast_now > kama_slow_now) and (kama_fast_prev <= kama_slow_prev)
        bearish_crossover = (kama_fast_now < kama_slow_now) and (kama_fast_prev >= kama_slow_prev)

        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0

        # Entry: ALL filters must pass
        if bullish_crossover and not was_in_position:
            # Filter 1: Short Trend (Aroon 25): Bull or Sideways
            aroon_up = self._at(self.data["aroon_up"], idx)
            aroon_down = self._at(self.data["aroon_down"], idx)
            trend = TrendClassification(aroon_up, aroon_down, self.aroon_period)
            trend_ok = trend in ["Bull", "Sideways"]
            
            if not trend_ok:
                signal_reason = f"KAMA crossover but trend is {trend}"
            
            # Filter 2: Volatility (14): High or Med
            elif self._at(self.data["volatility"], idx) == "Low":
                signal_reason = "KAMA crossover but volatility is Low"
            
            # Filter 3: DI_Bullish (14): True
            elif self._at(self.data["di_plus"], idx) <= self._at(self.data["di_minus"], idx):
                signal_reason = "KAMA crossover but DI not bullish"
            
            # Filter 4: CCI (20): > 0
            elif self._at(self.data["cci"], idx) <= 0:
                signal_reason = "KAMA crossover but CCI <= 0"
            
            # Filter 5: Price > EMA(20)
            elif row["close"] <= self._at(self.data["ema_20"], idx):
                signal_reason = "KAMA crossover but Price below EMA(20)"
            
            else:
                enter_long = True
                signal_reason = "KAMA Crossover + All Filters Pass"

        # Exit
        if was_in_position and bearish_crossover:
            exit_long = True
            signal_reason = "KAMA Crossunder"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used."""
        pass
