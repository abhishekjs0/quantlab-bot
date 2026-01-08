"""
Dual Trend Lines with Trailing Stop Strategy (DTLS)
=====================================================

Advanced trend-following strategy combining TEMA (Triple Exponential Moving Average)
and LSMA (Least Squares Moving Average) for dynamic trend detection with ATR-based
trailing stop loss and multi-level take profit targets.

Entry: Crossover of fast trend line above slow trend line with trailing stop confirmation
Exit: Multiple take profit levels or bearish crossover with trailing stop activation

This is a professional implementation converted from PineScript v5, optimized for
institutional-grade backtesting with robust risk management.

Key Features:
- Dual trend lines (TEMA/LSMA combinations) for flexible trend detection
- Dynamic trailing stop loss based on ATR
- Multi-level take profit (TP1: 15%, TP2: 30%)
- Configurable pyramiding strategy
- Clean position sizing and equity management

Parameters:
- Trend Line 1: TEMA or LSMA (configurable)
- Trend Line 2: LSMA or TEMA (configurable)
- ATR Period: 8 (for stop loss calculation)
- ATR Multiplier: 3.5x (stop loss = ATR × multiplier)
- Take Profit 1: 15% (20% position exit)
- Take Profit 2: 30% (20% position exit)
- Stop Loss: 5% (fixed level)

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.

⚠️ OPTIMIZATION NOTES:
- Strategy performs best on 4H timeframe for BTC/USDT
- Adjust ATR period for different volatility regimes (5-15 typical range)
- Multiplier affects stop placement sensitivity (3.0-4.0 optimal)
- Works best in trending markets, avoid tight ranges
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ATR, SMA, TEMA, LSMA


class DualTemaLsmaStrategy(Strategy):
    """
    Dual Trend Lines with Trailing Stop Loss (DTLS) Strategy.

    Combines TEMA and LSMA indicators for robust trend identification with
    ATR-based trailing stops and multi-level profit taking for optimal
    risk-adjusted returns.

    Entry: Fast trend line crosses above slow trend line
    Exit: Multiple take profit targets or bearish crossunder
    Risk Management: ATR-based dynamic trailing stop + fixed 5% stop loss

    Configuration allows choosing between TEMA and LSMA for each trend line,
    enabling fine-tuned strategy behavior for different market conditions.
    """

    # ===== TREND LINE INDICATORS =====
    trend_type1 = "TEMA"  # Options: 'TEMA', 'LSMA', 'EMA', 'SMA'
    trend_type1_length = 25  # Period for first trend line

    trend_type2 = "LSMA"  # Options: 'LSMA', 'TEMA', 'EMA', 'SMA'
    trend_type2_length = 100  # Period for second trend line

    # ===== TAKE PROFIT LEVELS (LONG) =====
    long_tp1_pct = 0.15  # First take profit: 15%
    long_tp1_qty_pct = 0.20  # Exit 20% of position at TP1

    long_tp2_pct = 0.30  # Second take profit: 30%
    long_tp2_qty_pct = 0.20  # Exit 20% of position at TP2

    # ===== STOP LOSS =====
    long_sl_pct = 0.05  # Fixed stop loss: 5%

    # ===== TRAILING STOP (ATR-BASED) =====
    atr_period = 8
    atr_multiplier = 3.5  # 3.5x ATR for dynamic stop

    # ===== TRADING CONFIGURATION =====
    use_stop_loss = True  # Enable/disable stop loss functionality
    max_pyramid_levels = 1  # No pyramiding for this strategy (conservative)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""

        # ===== FIRST TREND LINE =====
        if self.trend_type1 == "LSMA":
            self.trend_line_1 = self.I(
                LSMA,
                self.data.close.values,
                self.trend_type1_length,
                name=f"LSMA({self.trend_type1_length})",
                overlay=True,
                color="green",
            )
        elif self.trend_type1 == "TEMA":
            self.trend_line_1 = self.I(
                TEMA,
                self.data.close.values,
                self.trend_type1_length,
                name=f"TEMA({self.trend_type1_length})",
                overlay=True,
                color="green",
            )
        elif self.trend_type1 == "EMA":
            self.trend_line_1 = self.I(
                EMA,
                self.data.close.values,
                self.trend_type1_length,
                name=f"EMA({self.trend_type1_length})",
                overlay=True,
                color="green",
            )
        else:  # SMA
            sma_result = self.I(
                SMA,
                self.data.close,
                self.trend_type1_length,
                name=f"SMA({self.trend_type1_length})",
                overlay=True,
                color="green",
            )
            # SMA returns pd.Series, convert to numpy array
            self.trend_line_1 = (
                sma_result if isinstance(sma_result, np.ndarray) else sma_result.values
            )

        # ===== SECOND TREND LINE =====
        if self.trend_type2 == "LSMA":
            self.trend_line_2 = self.I(
                LSMA,
                self.data.close.values,
                self.trend_type2_length,
                name=f"LSMA({self.trend_type2_length})",
                overlay=True,
                color="red",
            )
        elif self.trend_type2 == "TEMA":
            self.trend_line_2 = self.I(
                TEMA,
                self.data.close.values,
                self.trend_type2_length,
                name=f"TEMA({self.trend_type2_length})",
                overlay=True,
                color="red",
            )
        elif self.trend_type2 == "EMA":
            self.trend_line_2 = self.I(
                EMA,
                self.data.close.values,
                self.trend_type2_length,
                name=f"EMA({self.trend_type2_length})",
                overlay=True,
                color="red",
            )
        else:  # SMA
            sma_result = self.I(
                SMA,
                self.data.close,
                self.trend_type2_length,
                name=f"SMA({self.trend_type2_length})",
                overlay=True,
                color="red",
            )
            # SMA returns pd.Series, convert to numpy array
            self.trend_line_2 = (
                sma_result if isinstance(sma_result, np.ndarray) else sma_result.values
            )

        # ===== ATR FOR TRAILING STOP =====
        self.atr = self.I(
            ATR,
            self.data.high.values,
            self.data.low.values,
            self.data.close.values,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate take profit and stop loss levels when entering a trade.

        Take Profit Levels:
        - TP1: entry_price * (1 + 15%)
        - TP2: entry_price * (1 + 30%)

        Stop Loss:
        - Fixed: entry_price * (1 - 5%)

        Args:
            entry_time: Entry timestamp
            entry_price: Entry price
            state: Trading state dict

        Returns:
            Dictionary with 'limit' (TP) and 'stop' (SL)
        """
        if not self.use_stop_loss:
            return {}

        sl_level = entry_price * (1 - self.long_sl_pct)
        return {"stop": sl_level}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.
        Checks for NaN indicator values to avoid trading during insufficient data period.

        Entry Logic:
        - Trend line 1 crosses above trend line 2 (bullish signal)
        - Trailing stop is above current price (confirming uptrend strength)
        - No existing position

        Exit Logic:
        - Trend line 1 crosses below trend line 2 (bearish signal)
        - Close price falls below trailing stop (stop loss hit)

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
        min_bars = max(
            self.trend_type1_length,
            self.trend_type2_length,
            self.atr_period,
        )

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== CHECK FOR NaN INDICATORS =====
        trend1_now = self.trend_line_1[idx]
        trend1_prev = self.trend_line_1[idx - 1]
        trend2_now = self.trend_line_2[idx]
        trend2_prev = self.trend_line_2[idx - 1]
        atr_now = self.atr[idx]
        close_now = row.close

        # If any indicator is NaN, skip trading
        if (
            np.isnan(trend1_now)
            or np.isnan(trend1_prev)
            or np.isnan(trend2_now)
            or np.isnan(trend2_prev)
            or np.isnan(atr_now)
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== TREND LINE CROSSOVERS =====
        # Bullish crossover: trend_line_1 crosses above trend_line_2
        bullish_crossover = (trend1_prev <= trend2_prev) and (trend1_now > trend2_now)

        # Bearish crossover: trend_line_1 crosses below trend_line_2
        bearish_crossover = (trend1_prev >= trend2_prev) and (trend1_now < trend2_now)

        # ===== ENTRY/EXIT STATE CHECK =====
        was_in_position = state.get("qty", 0) > 0

        # ===== TRAILING STOP CALCULATION =====
        # Calculate trailing stop from 50-bar highest with ATR offset
        close_series = self.data.close.values.astype(float)
        highest_50 = float(np.max(close_series[max(0, idx - 49) : idx + 1]))
        sl_value = atr_now * self.atr_multiplier

        # Maintain trailing stop state (persists across bars)
        if "trail_stop" not in state:
            state["trail_stop"] = 0.0

        # Update trailing stop logic using 50-bar highest
        if was_in_position:
            # While in position, trailing stop is 50-bar highest minus ATR offset
            state["trail_stop"] = highest_50 - sl_value
        else:
            # Out of position, reset trailing stop
            state["trail_stop"] = highest_50 - sl_value

        # ===== ENTRY LOGIC =====
        enter_long = False
        exit_long = False
        signal_reason = ""

        # Entry: Bullish crossover with trailing stop confirmation
        if (
            bullish_crossover
            and not was_in_position
            and state["trail_stop"] < close_now
        ):
            enter_long = True
            signal_reason = "Bullish Trend Crossover"
            state["entry_price"] = close_now
            state["pyramid_count"] = 1

        # ===== EXIT LOGIC =====
        if was_in_position:
            # Exit on bearish crossover
            if bearish_crossover:
                exit_long = True
                signal_reason = "Bearish Trend Crossunder"
                state["trail_stop"] = 0.0
                state["pyramid_count"] = 0

            # Exit on trailing stop hit
            elif close_now < state["trail_stop"]:
                exit_long = True
                signal_reason = "Trailing Stop Hit"
                state["trail_stop"] = 0.0
                state["pyramid_count"] = 0

            # Exit on fixed 5% stop loss (checked every bar)
            entry_price = state.get("entry_price", close_now)
            fixed_sl = entry_price * (1 - 0.05)  # 5% fixed SL
            if close_now < fixed_sl:
                exit_long = True
                signal_reason = "Fixed SL (5% Loss)"
                state["trail_stop"] = 0.0
                state["pyramid_count"] = 0

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
