"""
QuantLab-compatible Ichimoku Wrapper Strategy
Super lean implementation using Strategy.I() wrapper for ALL indicators.
Following the wrapper guide exactly - NO manual calculations!
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import ADX, ATR, EMA, MACD, RSI, Aroon


def ichimoku_line(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    """Calculate Ichimoku line (conversion, base, or leading span B)."""
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    return (highest + lowest) / 2


class IchimokuSimple(Strategy):
    """
    SUPER LEAN Ichimoku wrapper using Strategy.I() for ALL indicators.
    This follows the wrapper guide exactly - NO manual calculations!

    NOTE ON INDICATORS:
    - Indicators return NaN for insufficient data period
    - Ichimoku leading span B requires 52-bar minimum
    - Strategy checks for NaN before trading to avoid premature signals
    """

    # Strategy parameters (easily optimizable!)
    conversion_length = 9
    base_length = 26
    lagging_length = 52

    # Filter parameters - ALL DISABLED
    # Trend = Bull OR Sideways: Aroon up>70, down<30 OR Aroon mixed (not pure Bear)
    # Volatility = High OR Med: ATR % >= 2.0 (not Low which is < 2.0)
    # DI_Bullish = TRUE: plus_di > minus_di
    # RSI > 60 (stricter)
    # Price > EMA5 AND Price > EMA20 AND Price > EMA50 (all three required)
    # MACD_Bullish = TRUE: DISABLED (too strict)

    use_trend_filter = False  # Trend filter DISABLED
    use_vol_filter = False  # Volatility filter DISABLED
    use_di_filter = False  # DI Bullish filter DISABLED
    use_rsi_filter = False  # RSI filter DISABLED
    rsi_min = 60.0  # (unused)
    rsi_period = 14
    use_macd_filter = False  # MACD_Bullish = DISABLED (too strict)
    use_ema_filter = False  # EMA filter DISABLED
    use_ema5_filter = False  # EMA5 filter DISABLED
    use_ema50_filter = False  # EMA50 filter DISABLED

    # Aroon parameters (for Trend filter)
    aroon_period = 25
    aroon_up_bull_threshold = 70  # Aroon Up > 70
    aroon_down_bull_threshold = 30  # Aroon Down < 30
    aroon_down_sideways_threshold = 70  # For Sideways: not pure down trend

    # ATR % thresholds for volatility
    atr_high_threshold = 2.0  # ATR % >= 2.0 = High or Med volatility (not Low)

    # DISABLED FILTERS:
    use_cci_filter = False
    cci_min = 0.0
    cci_period = 20
    use_ema5_filter = False
    use_atr_filter = False
    atr_min_pct = 2.0
    atr_max_pct = 5.0
    atr_period = 14
    use_vwma_filter = False
    vwma_period = 14
    use_hma_filter = False
    hma_period = 14
    use_bb_filter = False
    bb_period = 20
    bb_std = 2
    use_cmf_filter = False
    cmf_min = -0.15
    cmf_period = 20

    # Risk management
    atr_trailing_stop_mult = 3.0  # 3 ATR fixed stop at entry
    atr_trailing_stop_length = 14
    use_stop_loss = False  # Flag to enable/disable stop loss (set to False - NO SL)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Setup data and call initialize."""
        self.data = df
        self.initialize()
        return super().prepare(df)

    def initialize(self):
        """Initialize all indicators using Strategy.I() wrapper."""
        # Ichimoku core indicators
        self.conversion_line = self.I(
            ichimoku_line,
            self.data.high,
            self.data.low,
            self.conversion_length,
            name=f"Conversion({self.conversion_length})",
            color="blue",
        )

        self.base_line = self.I(
            ichimoku_line,
            self.data.high,
            self.data.low,
            self.base_length,
            name=f"Base({self.base_length})",
            color="red",
        )

        self.leading_span_b = self.I(
            ichimoku_line,
            self.data.high,
            self.data.low,
            self.lagging_length,
            name=f"Leading Span B({self.lagging_length})",
            color="green",
        )

        # Confirmation filters using Strategy.I()
        if self.use_rsi_filter:
            self.rsi = self.I(
                RSI,
                self.data.close,
                self.rsi_period,
                name=f"RSI({self.rsi_period})",
                overlay=False,
                color="purple",
            )

        if self.use_ema_filter or self.use_ema5_filter:
            self.ema5 = self.I(EMA, self.data.close, 5, name="EMA(5)", color="cyan")
            self.ema20 = self.I(
                EMA, self.data.close, 20, name="EMA(20)", color="orange"
            )
            if self.use_ema50_filter:
                self.ema50 = self.I(
                    EMA, self.data.close, 50, name="EMA(50)", color="brown"
                )

        if self.use_macd_filter:
            # MACD returns a dict, so calculate separately
            macd_result = MACD(self.data.close.values, 12, 26, 9)
            self.macd_line = macd_result.get("macd", np.zeros(len(self.data)))
            self.macd_signal = macd_result.get("signal", np.zeros(len(self.data)))

        if self.use_di_filter:
            # ADX returns a dict, so calculate separately
            adx_result = ADX(
                self.data.high.values, self.data.low.values, self.data.close.values, 14
            )
            self.adx_di_plus = adx_result.get("di_plus", np.zeros(len(self.data)))
            self.adx_di_minus = adx_result.get("di_minus", np.zeros(len(self.data)))

        if self.use_trend_filter:
            # Aroon for trend classification: Bull = aroon_up > 70 and aroon_down < 30
            aroon_result = Aroon(
                self.data.high.values, self.data.low.values, self.aroon_period
            )
            self.aroon_up = aroon_result.get("aroon_up", np.zeros(len(self.data)))
            self.aroon_down = aroon_result.get("aroon_down", np.zeros(len(self.data)))

        # ATR for volatility classification and stop loss
        self.atr_trailing = self.I(
            ATR,
            self.data.high,
            self.data.low,
            self.data.close,
            self.atr_trailing_stop_length,
            name=f"ATR({self.atr_trailing_stop_length})",
            overlay=False,
            color="darkgray",
        )

    def on_entry(self, entry_time, entry_price, state):
        """
        Calculate ATR-based stop loss when entering a trade.

        Stop loss is DISABLED by default (use_stop_loss = False).
        Can be enabled by setting use_stop_loss = True.
        """
        if not self.use_stop_loss:
            return {}

        try:
            idx_result = self.data.index.get_loc(entry_time)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result

            if idx is not None and idx >= 0 and idx < len(self.atr_trailing):
                atr_value = self.atr_trailing[idx]
                if atr_value is not None and not np.isnan(atr_value) and atr_value > 0:
                    stop_loss = entry_price - (atr_value * self.atr_trailing_stop_mult)
                    return {"stop": stop_loss}
        except Exception:
            pass

        return {}

    def on_bar(self, ts, row, state):
        """Strategy logic using declared indicators."""
        # Get current position in the data
        try:
            idx_result = self.data.index.get_loc(ts)
            # Handle case where get_loc returns a slice (duplicate index)
            if isinstance(idx_result, slice):
                idx = idx_result.start
            else:
                idx = idx_result
        except (KeyError, AttributeError):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        if idx is None or idx < 2 or len(self.conversion_line) < 2:
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Check core Ichimoku indicators for NaN (insufficient data)
        if (
            np.isnan(self.conversion_line[idx])
            or np.isnan(self.base_line[idx])
            or np.isnan(self.leading_span_b[idx])
        ):
            return {"enter_long": False, "exit_long": False, "signal_reason": ""}

        # Ichimoku signals using current and previous values
        conv_cross_up = (
            self.conversion_line[idx] > self.base_line[idx]
            and self.conversion_line[idx - 1] <= self.base_line[idx - 1]
        )

        # Leading span A (calculated dynamically)
        leading_span_a = (self.conversion_line[idx] + self.base_line[idx]) / 2

        # Cloud conditions
        above_cloud = (
            row.close > leading_span_a and row.close > self.leading_span_b[idx]
        )

        # Core ichimoku signal
        ichimoku_signal = conv_cross_up and above_cloud

        # Apply filters - NEW REQUIREMENTS
        all_filters_pass = True
        signal_reason = ""

        # Trend = Bull only: aroon_up > 70 and aroon_down < 30
        if (
            self.use_trend_filter
            and hasattr(self, "aroon_up")
            and hasattr(self, "aroon_down")
        ):
            # Check for NaN before using
            if not (np.isnan(self.aroon_up[idx]) or np.isnan(self.aroon_down[idx])):
                trend_is_bull = (
                    self.aroon_up[idx] > self.aroon_up_bull_threshold
                ) and (self.aroon_down[idx] < self.aroon_down_bull_threshold)
                all_filters_pass &= trend_is_bull
            else:
                all_filters_pass = False

        # Volatility = High or Med (ATR % >= 2.0, not Low which is < 2.0)
        if self.use_vol_filter and hasattr(self, "atr_trailing"):
            if not np.isnan(self.atr_trailing[idx]):
                atr_val = self.atr_trailing[idx]
                atr_pct = (atr_val / row.close * 100) if row.close > 0 else 0
                vol_is_high_or_med = atr_pct >= self.atr_high_threshold
                all_filters_pass &= vol_is_high_or_med
            else:
                all_filters_pass = False

        # RSI > 60 (stricter)
        if self.use_rsi_filter and hasattr(self, "rsi"):
            if not np.isnan(self.rsi[idx]):
                all_filters_pass &= self.rsi[idx] > self.rsi_min
            else:
                all_filters_pass = False

        # DI Bullish: +DI > -DI
        if self.use_di_filter and hasattr(self, "adx_di_plus"):
            if not (
                np.isnan(self.adx_di_plus[idx]) or np.isnan(self.adx_di_minus[idx])
            ):
                all_filters_pass &= self.adx_di_plus[idx] > self.adx_di_minus[idx]
            else:
                all_filters_pass = False

        # Price > EMA5, EMA5 > EMA20, Price > EMA20, Price > EMA50 (all required)
        if (
            self.use_ema_filter
            and hasattr(self, "ema5")
            and hasattr(self, "ema20")
            and hasattr(self, "ema50")
        ):
            if not (
                np.isnan(self.ema5[idx])
                or np.isnan(self.ema20[idx])
                or np.isnan(self.ema50[idx])
            ):
                all_filters_pass &= (
                    (row.close > self.ema5[idx])
                    and (self.ema5[idx] > self.ema20[idx])
                    and (row.close > self.ema20[idx])
                    and (row.close > self.ema50[idx])
                )
            else:
                all_filters_pass = False

        enter_long = ichimoku_signal and all_filters_pass
        if enter_long:
            signal_reason = "Ichimoku Crossover"

        # Exit signal
        base_cross_up = (
            self.base_line[idx] > self.conversion_line[idx]
            and self.base_line[idx - 1] <= self.conversion_line[idx - 1]
        )

        below_cloud = row.close < leading_span_a or row.close < self.leading_span_b[idx]

        exit_long = base_cross_up and below_cloud
        if exit_long:
            signal_reason = "Ichimoku Exit"

        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
            "signal_reason": signal_reason,
        }

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
