"""
Bollinger Band with RSI Strategy
=================================

Mean reversion strategy combining:
1. Bollinger Bands for volatility-based entry/exit
2. RSI for overbought/oversold confirmation (Wilder's smoothing - matches TradingView)

Entry: RSI < 30 (oversold) AND price < lower Bollinger Band
Exit: RSI > 70 (overbought) OR Fixed 25% stop loss (checked every bar)

Parameters:
- RSI Period: 14 (uses Wilder's smoothing with alpha=1/n)
- RSI Oversold Threshold: 30
- RSI Overbought Threshold: 70
- Bollinger Band Length: 20
- Bollinger Band Multiplier: 2.0
- Max Pyramiding: 3 levels on continued oversold signals
- Take Profit: 10%
- Stop Loss: 25% (fixed, checked every bar)

⚠️ IMPORTANT NOTE:
This strategy is optimized for INTRADAY TRADING on 125m and 75m timeframes.
Performance on daily (1d) data may be suboptimal. For best results:
- Use 125m interval for swing trading (2-8 hour holds)
- Use 75m interval for active intraday trading (1-4 hour holds)
- Daily (1d) interval is not recommended for this mean reversion strategy

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import RSI, BollingerBands


class BollingerRSIStrategy(Strategy):
    """
    Bollinger Band with RSI mean reversion strategy.

    Entry: RSI < 30 (oversold) AND price < lower BB
    Exit: RSI > 70 (overbought)

    Pyramiding: Up to 3 levels on continued oversold conditions
    Risk Management: 10% TP, 25% SL
    """

    # ===== RSI Parameters =====
    rsi_period = 14
    rsi_oversold = 30  # Entry threshold (RSI < 30)
    rsi_overbought = 70  # Exit threshold (RSI > 70)

    # ===== Bollinger Band Parameters =====
    bb_length = 20  # SMA period
    bb_mult = 2.0  # Standard deviation multiplier

    # ===== Risk Management =====
    long_tp_pct = 0.10  # 10% take profit (from entry price)
    long_sl_pct = 0.25  # 25% stop loss (from entry price)
    pyramiding_max = 3  # Maximum number of pyramid entries on oversold signals

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""

        # ===== RSI Indicator =====
        self.rsi = self.I(
            RSI,
            self.data.close,
            self.rsi_period,
            name=f"RSI({self.rsi_period})",
            overlay=False,
            color="purple",
        )

        # ===== Bollinger Bands Indicator =====
        # BollingerBands returns dict with 'upper', 'middle', 'lower' keys
        bb_dict = BollingerBands(
            self.data.close.values,
            self.bb_length,
            self.bb_mult,
        )

        # Store the individual bands
        self.bb_upper = bb_dict["upper"]
        self.bb_middle = bb_dict["middle"]
        self.bb_lower = bb_dict["lower"]

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate take profit and stop loss when entering a trade.

        Take Profit: entry_price * (1 + long_tp_pct)
        Stop Loss: entry_price * (1 - long_sl_pct)

        Args:
            entry_time: Entry timestamp
            entry_price: Entry price
            state: Trading state dict

        Returns:
            Dictionary with 'limit' (TP) and 'stop' (SL)
        """
        tp_level = entry_price * (1 + self.long_tp_pct)
        sl_level = entry_price * (1 - self.long_sl_pct)

        return {"limit": tp_level, "stop": sl_level}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.
        Checks for NaN indicator values to avoid trading during insufficient data period.

        Entry: RSI < 30 AND Price < Lower Bollinger Band
        Exit: RSI > 70

        Args:
            ts: Timestamp
            row: Current bar data (high, low, close, open, volume, etc.)
            state: Trading state dict

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

        # Need enough bars for all indicators
        min_bars = max(self.rsi_period, self.bb_length)

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== CHECK FOR NaN INDICATORS =====
        # RSI requires rsi_period bars
        if np.isnan(self.rsi[idx]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Bollinger Band requires bb_length bars
        if np.isnan(self.bb_middle[idx]):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== GET INDICATOR VALUES (Current Bar) =====
        rsi_now = self.rsi[idx]
        close_now = row.close
        bb_lower_now = self.bb_lower[idx]

        # ===== ENTRY CONDITIONS =====
        # Long entry: RSI < 30 (oversold) AND Price < Lower Bollinger Band
        entry_signal = rsi_now < self.rsi_oversold and close_now < bb_lower_now

        # ===== EXIT CONDITIONS =====
        # Exit: RSI > 70 (overbought) OR Fixed stop loss (25% loss)
        exit_signal = rsi_now > self.rsi_overbought

        # ===== ENTRY LOGIC =====
        enter_long = False
        exit_long = False
        signal_reason = ""
        was_in_position = state.get("qty", 0) > 0
        pyramid_count = state.get("pyramid_count", 0)

        # Entry: On oversold + lower band condition (with pyramiding up to 3 levels)
        if entry_signal:
            if not was_in_position:
                # First entry
                enter_long = True
                signal_reason = "RSI Oversold + Lower Band"
                state["pyramid_count"] = 1
            elif pyramid_count < self.pyramiding_max:
                # Pyramid entry (add to position)
                enter_long = True
                signal_reason = f"Pyramid #{pyramid_count + 1}"
                state["pyramid_count"] = pyramid_count + 1

        # ===== EXIT LOGIC =====
        # Exit 1: RSI overbought
        if exit_signal and was_in_position:
            exit_long = True
            signal_reason = "RSI Overbought"
            state["pyramid_count"] = 0  # Reset pyramid counter on exit

        # Exit 2: Fixed 25% stop loss (checked every bar)
        if was_in_position and not exit_long:
            entry_price = state.get("entry_price", close_now)
            fixed_sl = entry_price * (1 - self.long_sl_pct)
            if close_now < fixed_sl:
                exit_long = True
                signal_reason = "Fixed SL (25% Loss)"
                state["pyramid_count"] = 0  # Reset pyramid counter on exit

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
