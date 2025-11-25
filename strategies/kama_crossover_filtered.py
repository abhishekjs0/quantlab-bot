# KAMA Crossover Strategy with Enhanced Filters
# Entry Filters: (1) KAMA crossover (2) NIFTY200 > EMA20 (3) Stoch_Bullish(14,3)

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, Stochastic
from data.loaders import load_ohlc_yf


class KAMACrossoverFiltered(Strategy):
    """
    KAMA Crossover Strategy with Multiple Trend Filters.

    Entry Conditions (ALL must be true):
    1. Fast KAMA crosses above Slow KAMA
    2. NIFTY200 > EMA(20) - Market regime filter
    3. Stochastic(14,3) is bullish (K > D) - Momentum filter

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
    nifty_ema_period = 20
    stoch_k_period = 14
    stoch_d_period = 3

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        
        # Load NIFTY data for market regime filter (from Dhan cache)
        try:
            from data.loaders import load_many_india
            # NIFTY 50 index: SECURITY_ID = 13
            nifty_dict = load_many_india(['NIFTY50'], interval='1d', cache=True, use_cache_only=True)
            self.nifty_data = nifty_dict['NIFTY50']
            # Calculate EMA(20) on NIFTY
            self.nifty_data['ema_20'] = self.nifty_data['close'].ewm(span=self.nifty_ema_period, adjust=False).mean()
        except Exception as e:
            print(f"⚠️  Could not load NIFTY data: {e}")
            self.nifty_data = None

        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators."""
        # KAMA lines
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

        # Stop Loss indicator
        self.atr_14 = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

        # Stochastic Oscillator - Call directly (returns dict)
        stoch_result = Stochastic(
            self.data.high,
            self.data.low,
            self.data.close,
            self.stoch_k_period,
            1,  # smooth_k
            self.stoch_d_period,
        )
        self.stoch_k = stoch_result["k"]
        self.stoch_d = stoch_result["d"]

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
        return x.iloc[i] if hasattr(x, "iloc") else x[i]

    def _check_nifty_filter(self, ts):
        """Check if NIFTY is above EMA(20)."""
        if self.nifty_data is None:
            return True  # Skip filter if data not available

        try:
            # Find closest date in NIFTY data
            if ts not in self.nifty_data.index:
                # Get closest previous date
                mask = self.nifty_data.index <= ts
                if not mask.any():
                    return True
                nifty_idx = self.nifty_data.index[mask][-1]
            else:
                nifty_idx = ts

            nifty_close = self.nifty_data.loc[nifty_idx, 'close']
            nifty_ema = self.nifty_data.loc[nifty_idx, 'ema_20']

            return nifty_close > nifty_ema
        except Exception:
            return True  # Skip filter on error

    def on_entry(self, entry_time, entry_price, state):
        """Configure entry stop loss."""
        try:
            idx_result = self.data.index.get_loc(entry_time)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError):
            return {}

        if idx is None or idx < 1 or np.isnan(self._at(self.atr_14, idx)):
            return {}

        atr_value = self._at(self.atr_14, idx)
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

        # Get indicator values
        kama_fast_now = self._at(self.kama_fast, idx)
        kama_fast_prev = self._at(self.kama_fast, idx - 1)
        kama_slow_now = self._at(self.kama_slow, idx)
        kama_slow_prev = self._at(self.kama_slow, idx - 1)
        stoch_k_now = self._at(self.stoch_k, idx)
        stoch_d_now = self._at(self.stoch_d, idx)

        # Check for valid data (no NaN)
        if any(np.isnan(x) for x in [kama_fast_now, kama_fast_prev, kama_slow_now,
                                       kama_slow_prev, stoch_k_now, stoch_d_now]):
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
            # Filter 1: NIFTY > EMA(20)
            if not self._check_nifty_filter(ts):
                signal_reason = "KAMA crossover but NIFTY below EMA(20)"
            # Filter 3: Stochastic Bullish (K > D)
            elif stoch_k_now <= stoch_d_now:
                signal_reason = "KAMA crossover but Stoch not bullish"
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
