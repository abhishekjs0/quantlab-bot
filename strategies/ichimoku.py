"""
QuantLab-compatible Ichimoku Wrapper Strategy
Super lean implementation using Strategy.I() wrapper for ALL indicators.
Following the wrapper guide exactly - NO manual calculations!
"""

import pandas as pd

from core.strategy import Strategy
from utils import ATR, EMA, RSI
from utils.indicators import ADX, CCI, CMF


def ichimoku_line(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
    """Calculate Ichimoku line (conversion, base, or leading span B)."""
    highest = high.rolling(window=period, min_periods=period).max()
    lowest = low.rolling(window=period, min_periods=period).min()
    return (highest + lowest) / 2


class IchimokuQuantLabWrapper(Strategy):
    """
    SUPER LEAN Ichimoku wrapper using Strategy.I() for ALL indicators.
    This follows the wrapper guide exactly - NO manual calculations!
    """

    # Strategy parameters (easily optimizable!)
    conversion_length = 9
    base_length = 26
    lagging_length = 52

    # Filter parameters
    use_rsi_filter = True
    rsi_min = 50.0
    rsi_period = 14

    use_cci_filter = True
    cci_min = 0.0
    cci_period = 20

    use_di_filter = False  # Disable due to ADX shape mismatch
    use_ema20_filter = True

    use_atr_filter = False
    atr_min_pct = 2.0
    atr_max_pct = 5.0
    atr_period = 14

    use_cmf_filter = False  # Disable if no volume data
    cmf_min = -0.15
    cmf_period = 20

    # Market regime filter - fixed enum sorting issues
    use_market_regime_filter = False

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

        if self.use_ema20_filter:
            self.ema20 = self.I(
                EMA, self.data.close, 20, name="EMA(20)", color="orange"
            )

        if self.use_cci_filter:
            self.cci = self.I(
                CCI,
                self.data.high,
                self.data.low,
                self.data.close,
                self.cci_period,
                name=f"CCI({self.cci_period})",
                overlay=False,
                color="cyan",
            )

        if self.use_di_filter:
            self.adx_data = self.I(
                ADX,
                self.data.high,
                self.data.low,
                self.data.close,
                14,
                name="ADX(14)",
                overlay=False,
                color="brown",
            )

        if self.use_atr_filter:
            self.atr = self.I(
                ATR,
                self.data.high,
                self.data.low,
                self.data.close,
                self.atr_period,
                name=f"ATR({self.atr_period})",
                overlay=False,
                color="gray",
            )

        if self.use_cmf_filter and hasattr(self.data, "volume"):
            self.cmf = self.I(
                CMF,
                self.data.high,
                self.data.low,
                self.data.close,
                self.data.volume,
                self.cmf_period,
                name=f"CMF({self.cmf_period})",
                overlay=False,
                color="pink",
            )

        print("✅ Ichimoku strategy initialized successfully")

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
            return {"enter_long": False, "exit_long": False}

        if idx is None or idx < 2 or len(self.conversion_line) < 2:
            return {"enter_long": False, "exit_long": False}

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

        # Apply filters
        all_filters_pass = True

        if self.use_rsi_filter and hasattr(self, "rsi"):
            all_filters_pass &= self.rsi[idx] > self.rsi_min

        if self.use_ema20_filter and hasattr(self, "ema20"):
            all_filters_pass &= row.close > self.ema20[idx]

        if self.use_cci_filter and hasattr(self, "cci"):
            all_filters_pass &= self.cci[idx] > self.cci_min

        enter_long = ichimoku_signal and all_filters_pass

        # Exit signal
        base_cross_up = (
            self.base_line[idx] > self.conversion_line[idx]
            and self.base_line[idx - 1] <= self.conversion_line[idx - 1]
        )

        below_cloud = row.close < leading_span_a or row.close < self.leading_span_b[idx]

        exit_long = base_cross_up and below_cloud

        return {"enter_long": enter_long, "exit_long": exit_long}

    def next(self):
        """Legacy method - not used by QuantLab engine."""
        pass
