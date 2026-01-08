"""
TEMA-LSMA Crossover Strategy
============================

Entry: TEMA(25) crosses above LSMA(100) when:
  - ATR(14)% > 3.5% (volatility filter)
  - ADX(28) > 25 (trend strength filter)

Exit: Bearish crossunder OR ATR-based stop loss

No lookahead bias - all indicators use current bar data only.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, ADX, TEMA, LSMA


class TemaLsmaCrossover(Strategy):
    """TEMA-LSMA Crossover with ATR% and ADX filters."""

    # MA parameters
    fast_length = 25
    slow_length = 100

    # Entry filters
    atr_14_min = 3.5      # ATR(14)% > 3.5%
    adx_28_min = 25.0     # ADX(28) > 25

    # ATR Stop Loss
    use_atr_stop = False
    atr_stop_multiplier = 5.0  # Stop at entry_price - N*ATR(14)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup indicators."""
        self.data = df.copy()
        close = self.data.close.values
        high = self.data.high.values
        low = self.data.low.values

        # Entry/Exit signals
        self.fast_line = self.I(
            TEMA, close, self.fast_length,
            name=f"TEMA({self.fast_length})", overlay=True, color="green"
        )
        self.slow_line = self.I(
            LSMA, close, self.slow_length,
            name=f"LSMA({self.slow_length})", overlay=True, color="red"
        )

        # ATR(14) for volatility filter and stop loss
        atr_vals = ATR(high, low, close, 14)
        self.atr = self.I(lambda: atr_vals, name="ATR(14)", overlay=False)

        # ADX(28) for trend strength filter
        adx_result = ADX(high, low, close, 28)
        self.adx_28 = self.I(lambda: adx_result['adx'], name="ADX(28)", overlay=False)

        return super().prepare(df)

    def on_entry(self, entry_time, entry_price, state):
        """Calculate ATR-based stop loss at entry."""
        if not self.use_atr_stop:
            return {}
        
        try:
            idx = self.data.index.get_loc(entry_time)
            if isinstance(idx, slice):
                idx = idx.start
            
            if idx is not None and idx >= 0 and self.atr is not None:
                atr_val = self.atr[idx]
                if atr_val is not None and not np.isnan(atr_val) and atr_val > 0:
                    stop_loss = entry_price - (atr_val * self.atr_stop_multiplier)
                    return {"stop": stop_loss}
        except Exception:
            pass
        
        return {}

    def on_bar(self, ts, row, state):
        """Trading logic."""
        try:
            idx_result = self.data.index.get_loc(ts)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        if idx < self.slow_length:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Indicator values
        fast_now, fast_prev = self.fast_line[idx], self.fast_line[idx - 1]
        slow_now, slow_prev = self.slow_line[idx], self.slow_line[idx - 1]

        if any(np.isnan(v) for v in [fast_now, fast_prev, slow_now, slow_prev]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Crossover detection
        bull_cross = (fast_prev <= slow_prev) and (fast_now > slow_now)
        bear_cross = (fast_prev >= slow_prev) and (fast_now < slow_now)

        in_position = state.get("qty", 0) > 0
        enter_long = False
        exit_long = False
        signal_reason = ""

        # Entry logic with filters
        if not in_position and bull_cross:
            close_price = row.close
            if close_price <= 0:
                return {"enter_long": False, "exit_long": False, "signal_reason": ""}
            
            atr_val = self.atr[idx]
            adx_val = self.adx_28[idx]
            
            # ATR(14)% > 3.5%
            atr_pct = 0.0 if np.isnan(atr_val) else (atr_val / close_price) * 100
            atr_ok = atr_pct >= self.atr_14_min
            
            # ADX(28) > 25
            adx_ok = not np.isnan(adx_val) and adx_val >= self.adx_28_min
            
            if atr_ok and adx_ok:
                enter_long = True
                signal_reason = "Bull Cross"

        # Exit on bearish crossunder
        if in_position and bear_cross:
            exit_long = True
            signal_reason = "XDN"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }
