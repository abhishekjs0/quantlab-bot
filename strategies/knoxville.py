"""
Knoxville Divergence Strategy with Reversal Tabs
=================================================

A trend-following strategy combining:
1. **Knoxville Divergence**: RSI + Momentum divergence detection using fractals
2. **Reversal Tabs**: MACD mean reversion signals (Bob Rooker style)

Original TradingView strategy adapted for QuantLab backtesting engine.

Key Features:
- Entry: Bullish Knoxville divergence OR MACD reversal signal
- Exit: Bearish signals (KD or Sell Reversal Tab)
- SL: 5x ATR stop loss
- Filter: SMA 20 < SMA 50 (uptrend filter)

Parameters (from TradingView script):
- Knox RSI: 21 period (Note: TV default was 17, user override to 21)
- Knox Momentum: 20 period
- Fractal lookback: 30 candles (user requirement: at least 30 candles back)
- MACD: 12/26/9
- Stochastic RSI: 70-period, 10K, 10D
- ATR: 14-period, 5x multiplier for stop loss
- SMA: 20-period and 50-period for trend filter

CRITICAL: All trading decisions use PREVIOUS bar data only.
This ensures no future leak and realistic trading simulation.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils import ATR, MACD, RSI, SMA, Momentum, StochasticRSI


def detect_fractals(momentum: np.ndarray, lookback: int = 2):
    """
    Detect fractal tops and bottoms in momentum.

    A fractal top is when momentum[t-2] > momentum[t] < momentum[t+2]
    A fractal bottom is when momentum[t-2] < momentum[t] > momentum[t+2]

    Returns:
    - fractal_tops: indices of fractal tops
    - fractal_bottoms: indices of fractal bottoms
    """
    mom_arr = np.asarray(momentum)
    n = len(mom_arr)

    fractal_tops = []
    fractal_bottoms = []

    for i in range(lookback, n - lookback):
        # Check for fractal top
        if (
            mom_arr[i - lookback] < mom_arr[i]
            and mom_arr[i - 1] < mom_arr[i]
            and mom_arr[i + 1] < mom_arr[i]
            and mom_arr[i + lookback] < mom_arr[i]
        ):
            fractal_tops.append(i)

        # Check for fractal bottom
        if (
            mom_arr[i - lookback] > mom_arr[i]
            and mom_arr[i - 1] > mom_arr[i]
            and mom_arr[i + 1] > mom_arr[i]
            and mom_arr[i + lookback] > mom_arr[i]
        ):
            fractal_bottoms.append(i)

    return fractal_tops, fractal_bottoms


class KnoxvilleStrategy(Strategy):
    """
    Knoxville Divergence Strategy with Reversal Tabs.

    Combines two complementary signals:
    1. Knoxville Divergence: Detects hidden divergences between price and momentum
    2. Reversal Tabs: MACD + Stochastic mean reversion on oversold/overbought

    NOTE ON INDICATORS:
    - Indicators return NaN for insufficient data period
    - Stochastic RSI requires 70-bar minimum
    - Strategy checks for NaN before trading to avoid premature signals
    """

    # ===== Knoxville Divergence Parameters =====
    knox_rsi_period = 21  # User override: 21 instead of 17
    knox_momentum_period = 20
    knox_fractal_lookback = 30  # At least 30 candles back
    knox_rsi_ob = 70.0  # RSI overbought
    knox_rsi_os = 30.0  # RSI oversold

    # ===== Reversal Tabs Parameters (Bob Rooker - MACD based) =====
    macd_fast = 12
    macd_slow = 26
    macd_signal = 9
    stoch_rsi_period = 70
    stoch_k_period = 10  # User override: 10 instead of 30
    stoch_d_period = 10  # User override: 10 instead of 30
    stoch_ob = 70.0
    stoch_os = 30.0

    # ===== Risk Management =====
    atr_period = 14
    atr_multiplier = 10.0  # 10 ATR for stop loss
    use_stop_loss = False  # Flag to enable/disable stop loss (set to False - NO SL)

    # ===== Trend Filter =====
    sma_fast_period = 20
    sma_slow_period = 50

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and initialize indicators."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""

        # ===== Knoxville Divergence Indicators =====
        self.knox_rsi = self.I(
            RSI,
            self.data.close,
            self.knox_rsi_period,
            name=f"Knox RSI({self.knox_rsi_period})",
            overlay=False,
        )

        self.knox_momentum = self.I(
            Momentum,
            self.data.close,
            self.knox_momentum_period,
            name=f"Knox Momentum({self.knox_momentum_period})",
            overlay=False,
        )

        # ===== Reversal Tabs Indicators =====
        # MACD returns a dictionary, call directly
        macd_result = MACD(
            np.asarray(self.data.close.values),
            self.macd_fast,
            self.macd_slow,
            self.macd_signal,
        )
        self.macd_line = macd_result.get("macd", np.zeros(len(self.data)))
        self.macd_signal = macd_result.get("signal", np.zeros(len(self.data)))
        self.macd_hist = macd_result.get("histogram", np.zeros(len(self.data)))

        # ===== Stochastic RSI Indicator =====
        # StochasticRSI returns a dictionary, call directly
        stoch_rsi_dict = StochasticRSI(
            self.data.close,
            self.stoch_rsi_period,
            self.stoch_k_period,
            self.stoch_d_period,
        )
        self.stoch_k = stoch_rsi_dict["k"]
        self.stoch_d = stoch_rsi_dict["d"]

        # ===== Risk Management Indicator =====
        self.atr = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_period,
            name=f"ATR({self.atr_period})",
            overlay=False,
        )

        # ===== Trend Filter Indicators =====
        self.sma_fast = self.I(
            SMA,
            self.data.close,
            self.sma_fast_period,
            name=f"SMA({self.sma_fast_period})",
            overlay=True,
        )

        self.sma_slow = self.I(
            SMA,
            self.data.close,
            self.sma_slow_period,
            name=f"SMA({self.sma_slow_period})",
            overlay=True,
        )

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate ATR-based stop loss when entering a trade.

        Stop loss is DISABLED by default (use_stop_loss = False).
        Can be enabled by setting use_stop_loss = True.
        Uses 5x ATR multiplier for stop loss.
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result

            if idx is not None and idx >= 0 and idx < len(self.atr):
                atr_value = self.atr[idx]
                if atr_value is not None and not np.isnan(atr_value) and atr_value > 0:
                    stop_loss = entry_price - (atr_value * self.atr_multiplier)
                    return {"stop": stop_loss}
        except Exception:
            pass

        return {}

    def on_bar(self, ts, row, state):
        """
        Execute trading logic on each bar.

        Uses PREVIOUS bar data only to prevent future leak.

        Entry: Bullish KD or Buy Reversal Tab
        Exit: Bearish KD or Sell Reversal Tab

        Args:
            ts: Timestamp
            row: Current bar data
            state: Trading state

        Returns:
            Dictionary with entry/exit signals
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
            self.knox_rsi_period,
            self.knox_momentum_period,
            self.macd_slow,
            self.stoch_rsi_period,
            self.knox_fractal_lookback + 2,
        )

        if idx is None or idx < min_bars:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Check core indicators for NaN (insufficient data)
        if (
            np.isnan(self.knox_rsi[idx])
            or np.isnan(self.knox_momentum[idx])
            or np.isnan(self.macd_line[idx])
            or np.isnan(self.stoch_k[idx])
            or np.isnan(self.sma_fast[idx])
            or np.isnan(self.sma_slow[idx])
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # ===== Knoxville Divergence Detection =====
        bullish_kd = False
        bearish_kd = False

        # Detect fractals in momentum looking back at least 30 bars
        if idx >= self.knox_fractal_lookback + 2:
            momentum_slice = self.knox_momentum[max(0, idx - 100) : idx + 1]
            fractal_tops, fractal_bottoms = detect_fractals(
                momentum_slice, lookback=self.knox_fractal_lookback
            )

            # Check for bullish divergence at latest fractal bottom
            if fractal_bottoms and len(fractal_bottoms) >= 2:
                current_frac_idx = idx - (len(momentum_slice) - 1 - fractal_bottoms[-1])
                prev_frac_idx = idx - (len(momentum_slice) - 1 - fractal_bottoms[-2])

                if current_frac_idx >= 0 and prev_frac_idx >= 0:
                    curr_low_price = self.data.low.iloc[current_frac_idx]
                    prev_low_price = self.data.low.iloc[prev_frac_idx]
                    curr_mom = self.knox_momentum[current_frac_idx]
                    prev_mom = self.knox_momentum[prev_frac_idx]
                    curr_rsi = self.knox_rsi[current_frac_idx]

                    bullish_kd = (
                        curr_low_price < prev_low_price
                        and curr_mom > prev_mom
                        and curr_rsi < self.knox_rsi_os
                    )

            # Check for bearish divergence at latest fractal top
            if fractal_tops and len(fractal_tops) >= 2:
                current_frac_idx = idx - (len(momentum_slice) - 1 - fractal_tops[-1])
                prev_frac_idx = idx - (len(momentum_slice) - 1 - fractal_tops[-2])

                if current_frac_idx >= 0 and prev_frac_idx >= 0:
                    curr_high_price = self.data.high.iloc[current_frac_idx]
                    prev_high_price = self.data.high.iloc[prev_frac_idx]
                    curr_mom = self.knox_momentum[current_frac_idx]
                    prev_mom = self.knox_momentum[prev_frac_idx]
                    curr_rsi = self.knox_rsi[current_frac_idx]

                    bearish_kd = (
                        curr_high_price > prev_high_price
                        and curr_mom < prev_mom
                        and curr_rsi > self.knox_rsi_ob
                    )

        # ===== Reversal Tabs Detection (Bob Rooker) =====
        macd_now = self.macd_line[idx]
        macd_prev = self.macd_line[idx - 1]
        stoch_k_now = self.stoch_k[idx]

        # Buy reversal: MACD crosses above 0 AND stoch < oversold
        buy_reversal = macd_prev <= 0 and macd_now > 0 and stoch_k_now < self.stoch_os

        # Sell reversal: MACD crosses below 0 AND stoch > overbought
        sell_reversal = macd_prev >= 0 and macd_now < 0 and stoch_k_now > self.stoch_ob

        # ===== Trend Filter (SMA 20 < SMA 50) =====
        sma_fast_now = self.sma_fast[idx]
        sma_slow_now = self.sma_slow[idx]
        is_uptrend = (
            sma_fast_now < sma_slow_now
        )  # SMA 20 below SMA 50 = uptrend/downtrend filter

        # ===== Entry Signal =====
        # Enter on: (Bullish KD OR Buy Reversal Tab) AND Trend Filter
        enter_long = (bullish_kd or buy_reversal) and is_uptrend
        signal_reason = ""
        if enter_long:
            if bullish_kd:
                signal_reason = "Knoxville Divergence"
            else:
                signal_reason = "Reversal Tab"

        # ===== Exit Signals =====
        # Exit logic with priorities:
        # Priority 1: Bearish KD or Sell Reversal Tab (signal-based)
        # Priority 2: Stop loss check (ATR-based at entry - FIXED)
        exit_long = False
        was_in_position = state.get("qty", 0) > 0
        close_now = self.data.close.values[idx]

        if was_in_position:
            # Priority 1: Check ATR-based stop loss FIRST (hard stop)
            # This should be checked before signals to enforce risk management
            if "entry_stop" in state:
                entry_stop = state["entry_stop"]
                if close_now <= entry_stop:
                    exit_long = True
                    signal_reason = "Stop Loss"

            # Priority 2: Bearish KD (higher pivot high + lower momentum + RSI overbought)
            if not exit_long and bearish_kd:
                exit_long = True
                signal_reason = "Knoxville Exit"

            # Priority 3: Sell reversal signal (MACD < 0 AND Stoch RSI > 70)
            if not exit_long and sell_reversal:
                exit_long = True
                signal_reason = "Reversal Exit"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
