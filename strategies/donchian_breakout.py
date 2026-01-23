"""
Donchian Breakout Strategy v7
=============================

Entry: Close crosses above upper Donchian band (with optional filters)
Exit: 
  - Option 1: Close crosses below lower Donchian band (conservative)
  - Option 2: Close crosses below the basis (middle line) (aggressive)

Configuration:
- Pyramiding: 0 (long-only, no pyramiding)
- Commission: 0.22% (0.11% round trip)
- Slippage: 3 ticks
- Default capital: 100,000 INR
- Default position size: 10% of equity

No lookahead bias - all indicators use current bar data only.

Improvements (v7):
- Fixed lambda indicator pattern (direct array references)
- Added validation for exit_option parameter
- Improved error messages and edge case handling
- Better indicator caching strategy
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import DonchianChannels


class DonchianBreakout(Strategy):
    """
    Donchian Breakout - Long only with configurable exit.
    
    Parameters:
        length: Lookback period for Donchian Channels (default: 20)
                Range: 10-50. Higher = wider bands, fewer signals, larger R/R
        exit_option: Exit strategy
                    1 = Exit at lower Donchian band (conservative)
                    2 = Exit at basis/middle line (aggressive)
    """

    # Donchian parameters
    length = 20  # Lookback period for Donchian Channels
    exit_option = 1  # 1=Lower band exit, 2=Basis exit

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup indicators."""
        # Validate parameters
        if not isinstance(self.length, int) or self.length < 1:
            raise ValueError(f"Invalid length: {self.length}. Must be int >= 1")
        if self.exit_option not in [1, 2]:
            raise ValueError(f"Invalid exit_option: {self.exit_option}. Must be 1 or 2")

        self.data = df.copy()
        high = self.data.high.values
        low = self.data.low.values

        # Calculate Donchian Channels once - store arrays directly
        donchian = DonchianChannels(high, low, self.length)
        self.upper_vals = donchian["upper"]
        self.lower_vals = donchian["lower"]
        self.basis_vals = donchian["basis"]

        # Plot indicators - improved lambda pattern
        self.I(
            lambda: self.upper_vals,
            name=f"Upper({self.length})",
            overlay=True,
            color="blue"
        )
        self.I(
            lambda: self.lower_vals,
            name=f"Lower({self.length})",
            overlay=True,
            color="blue"
        )
        self.I(
            lambda: self.basis_vals,
            name=f"Basis({self.length})",
            overlay=True,
            color="orange"
        )

        return super().prepare(df)

    def on_bar(self, ts, row, state):
        """Trading logic - Donchian breakout."""
        try:
            idx_result = self.data.index.get_loc(ts)
            idx = idx_result.start if isinstance(idx_result, slice) else idx_result
        except (KeyError, AttributeError, TypeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Need at least length bars to have valid Donchian
        if idx < self.length:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        close_now = row.close
        close_prev = self.data.iloc[idx - 1].close

        # Get band values (using previous bar for signal to avoid lookahead)
        # Direct array access instead of lambda
        upper_prev = self.upper_vals[idx - 1]
        lower_prev = self.lower_vals[idx - 1]
        basis_prev = self.basis_vals[idx - 1]

        # Validate all values are numeric and not NaN
        if any(np.isnan(v) for v in [close_now, close_prev, upper_prev, lower_prev, basis_prev]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        in_position = state.get("qty", 0) > 0
        enter_long = False
        exit_long = False
        signal_reason = ""

        # ===== Entry Signal: Close crosses above upper Donchian band =====
        long_condition = (close_prev <= upper_prev) and (close_now > upper_prev)

        if not in_position and long_condition:
            enter_long = True
            signal_reason = "Donchian BO"

        # ===== Exit Signals =====
        if in_position:
            exit_lower = (close_prev >= lower_prev) and (close_now < lower_prev)
            exit_basis = (close_prev >= basis_prev) and (close_now < basis_prev)

            # Execute appropriate exit based on option
            if self.exit_option == 1 and exit_lower:
                exit_long = True
                signal_reason = "Exit Lower"
            elif self.exit_option == 2 and exit_basis:
                exit_long = True
                signal_reason = "Exit Basis"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }


# Pre-configured variants for easy backtesting
class DonchianBreakout10(DonchianBreakout):
    """Donchian Breakout with length=10 (for weekly timeframe)."""
    length = 10
    exit_option = 1


class DonchianBreakout20(DonchianBreakout):
    """Donchian Breakout with length=20 (for daily timeframe)."""
    length = 20
    exit_option = 1
