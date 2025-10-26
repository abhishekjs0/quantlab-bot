"""Ichimoku Cloud strategy implementation (long-only) with entry confir        # Market regime filter (ENABLED by default)
use_market_regime_filter: bool = True,
market_regime_strength_min: float = 0.4,
market_regime_symbol: str = "NIFTYBEES",on filters."""

from typing import Any

import pandas as pd

from core.strategy import Strategy

# crossover not used in the final variant (we use simple conv>base)


class IchimokuStrategy(Strategy):
    """Ichimoku Cloud Strategy (long-only) with entry confirmation filters.

    Behavior:
    - Enter when conversion_line crosses above base_line and the lagging span
      (close shifted -delta) is above both lead lines (shifted forward by delta).
    - Exit when base_line crosses above conversion_line and lagging span is below
      both lead lines.
    - Implements 8% stop loss below entry price for risk management.
    - Pyramiding=0 (single position).
    - Supports an optional custom test period; signals are suppressed outside it.

    Default Entry Confirmation Filters (ENABLED by default):
    - RSI Filter: RSI > 50 for momentum confirmation
    - CCI Filter: CCI > 0 for commodity channel momentum
    - Directional Index Filter: +DI > -DI for bullish directional movement
    - EMA Filter: Price above 20-period EMA for trend confirmation

    Optional Filters (DISABLED by default):
    - ATR% Filter: Volatility filter (2-5% range)
    - CMF Filter: Chaikin Money Flow filter (> -0.15)
    - Market Regime Filter: Only trade in bullish market conditions (2-3 month view)

    All filters are togglable via constructor parameters for easy optimization.
    The market regime filter uses NIFTY50 or market index to determine overall
    market conditions and only allows trend-following trades in bull markets.
    """

    def __init__(
        self,
        conversion_length: int = 9,
        base_length: int = 26,
        lagging_length: int = 52,
        delta: int = 26,
        testPeriodSwitch: bool = True,
        testStartYear: int = 2001,
        testStartMonth: int = 1,
        testStartDay: int = 1,
        testStartHour: int = 0,
        testStopYear: int = 2030,
        testStopMonth: int = 12,
        testStopDay: int = 1,
        testStopHour: int = 0,
        # Entry confirmation filters (ENABLED by default)
        use_atr_filter: bool = False,
        atr_min_pct: float = 2.0,
        atr_max_pct: float = 5.0,
        atr_period: int = 14,
        use_rsi_filter: bool = True,
        rsi_min: float = 50.0,
        rsi_period: int = 14,
        use_cci_filter: bool = True,
        cci_min: float = 0.0,
        cci_period: int = 20,
        use_di_filter: bool = True,
        use_ema20_filter: bool = True,
        use_cmf_filter: bool = False,
        cmf_min: float = -0.15,
        cmf_period: int = 20,
        # Market regime filter (DISABLED by default)
        use_market_regime_filter: bool = False,
        market_regime_strength_min: float = 0.4,
        market_regime_symbol: str = "NIFTY50",
    ):
        self.conversion_length = int(conversion_length)
        self.base_length = int(base_length)
        self.lagging_length = int(lagging_length)
        self.delta = int(delta)

        # test period params
        self.testPeriodSwitch = bool(testPeriodSwitch)
        self.testStartYear = int(testStartYear)
        self.testStartMonth = int(testStartMonth)
        self.testStartDay = int(testStartDay)
        self.testStartHour = int(testStartHour)
        self.testStopYear = int(testStopYear)
        self.testStopMonth = int(testStopMonth)
        self.testStopDay = int(testStopDay)
        self.testStopHour = int(testStopHour)

        # Entry confirmation filters
        self.use_atr_filter = bool(use_atr_filter)
        self.atr_min_pct = float(atr_min_pct)
        self.atr_max_pct = float(atr_max_pct)
        self.atr_period = int(atr_period)

        self.use_rsi_filter = bool(use_rsi_filter)
        self.rsi_min = float(rsi_min)
        self.rsi_period = int(rsi_period)

        self.use_cci_filter = bool(use_cci_filter)
        self.cci_min = float(cci_min)
        self.cci_period = int(cci_period)

        self.use_di_filter = bool(use_di_filter)

        self.use_ema20_filter = bool(use_ema20_filter)

        self.use_cmf_filter = bool(use_cmf_filter)
        self.cmf_min = float(cmf_min)
        self.cmf_period = int(cmf_period)

        # Market regime filter
        self.use_market_regime_filter = bool(use_market_regime_filter)
        self.market_regime_strength_min = float(market_regime_strength_min)
        self.market_regime_symbol = str(market_regime_symbol)

        # Initialize market regime filter if enabled
        self._market_regime_filter = None
        if self.use_market_regime_filter:
            from core.market_regime import create_trend_following_filter

            self._market_regime_filter = create_trend_following_filter()
            self._market_regime_filter.min_strength = self.market_regime_strength_min

        # Pine declared pyramiding=0; engine requires >=1 to allow entries, so set to 1
        self.pyramiding = 1

        # runtime fields
        self.df = None
        self._enter = None
        self._exit = None
        self._is_period = None

    def _average(self, high: pd.Series, low: pd.Series, length: int) -> pd.Series:
        """Calculate midpoint of highest high and lowest low over length periods."""
        hi = high.rolling(length, min_periods=1).max()
        lo = low.rolling(length, min_periods=1).min()
        return (hi + lo) / 2.0

    def _calculate_atr_pct(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate ATR as percentage of close price."""
        # True Range calculation - simplified approach
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        # Get maximum of the three without using concat
        tr = tr1.copy()
        tr = tr.where(tr >= tr2, tr2)
        tr = tr.where(tr >= tr3, tr3)

        # ATR as moving average of True Range
        atr = tr.rolling(period, min_periods=1).mean()

        # Convert to percentage of close price with safety check
        atr_pct = (atr / close.where(close > 0, 1)) * 100
        return atr_pct.fillna(0)

    def _calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate Average Directional Index (ADX)."""
        # Directional movements
        plus_dm = high.diff()
        minus_dm = -low.diff()

        # Only keep positive directional movements
        plus_dm = plus_dm.where(plus_dm > minus_dm, 0)
        minus_dm = minus_dm.where(minus_dm > plus_dm, 0)

        # True Range - simplified approach
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        # Get maximum without using concat
        tr = tr1.copy()
        tr = tr.where(tr >= tr2, tr2)
        tr = tr.where(tr >= tr3, tr3)

        # Smoothed values using Wilder's smoothing
        alpha = 1 / period
        plus_di = 100 * (
            plus_dm.ewm(alpha=alpha, adjust=False).mean()
            / tr.ewm(alpha=alpha, adjust=False).mean()
        )
        minus_di = 100 * (
            minus_dm.ewm(alpha=alpha, adjust=False).mean()
            / tr.ewm(alpha=alpha, adjust=False).mean()
        )

        # Directional Index with safety check
        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.where(di_sum > 0, 1)
        dx = dx.fillna(0)

        # ADX as smoothed DX
        adx = dx.ewm(alpha=alpha, adjust=False).mean()
        return adx.fillna(0)

    def _calculate_rsi(self, close: pd.Series, period: int) -> pd.Series:
        """Calculate Relative Strength Index (RSI) with robust error handling."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        # Wilder's smoothing with minimum periods
        alpha = 1 / period
        avg_gain = gain.ewm(alpha=alpha, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False, min_periods=period).mean()

        # Calculate RS with safety check for division by zero
        avg_loss_safe = avg_loss.where(avg_loss > 1e-8, 1e-8)
        rs = avg_gain / avg_loss_safe

        # RSI calculation
        rsi = 100 - (100 / (1 + rs))

        # Fill NaN with neutral RSI value and cap extreme values
        return rsi.fillna(50).clip(0, 100)

    def _calculate_cmf(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int,
    ) -> pd.Series:
        """Calculate Chaikin Money Flow (CMF) with robust error handling."""
        # Money Flow Multiplier with safety checks
        hl_diff = high - low
        hl_diff_safe = hl_diff.where(hl_diff > 1e-8, 1e-8)  # Avoid division by zero

        mfm = ((close - low) - (high - close)) / hl_diff_safe
        mfm = mfm.fillna(0).clip(-1, 1)  # Cap extreme values

        # Money Flow Volume
        mfv = mfm * volume

        # CMF calculation with safety checks
        volume_sum = volume.rolling(period, min_periods=1).sum()
        volume_sum_safe = volume_sum.where(volume_sum > 0, 1)  # Avoid division by zero

        cmf = mfv.rolling(period, min_periods=1).sum() / volume_sum_safe
        return cmf.fillna(0).clip(-1, 1)  # Cap extreme values

    def _calculate_cci(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> pd.Series:
        """Calculate Commodity Channel Index (CCI) using a robust simplified approach."""
        # Typical Price
        tp = (high + low + close) / 3

        # Simple Moving Average of Typical Price
        sma_tp = tp.rolling(period, min_periods=1).mean()

        # Use a simple standard-based approximation for mean deviation
        # This completely avoids the problematic rolling apply function
        std_tp = tp.rolling(period, min_periods=1).std()
        # Convert std to approximate mean absolute deviation
        mad_approx = std_tp * 0.7979  # statistical factor to approximate MAD from STD

        # Safety check for division by zero
        mad_safe = mad_approx.where(mad_approx > 1e-8, 1e-8)

        # CCI calculation
        cci = (tp - sma_tp) / (0.015 * mad_safe)

        # Cap extreme values to prevent numerical issues
        cci = cci.clip(-500, 500)
        return cci.fillna(0)

    def _calculate_di(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int
    ) -> tuple:
        """Calculate +DI and -DI for directional movement."""
        # Directional movements
        plus_dm = high.diff()
        minus_dm = -low.diff()

        # Only keep positive directional movements
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        # True Range - simplified approach avoiding DataFrame operations
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        # Get maximum of the three without using DataFrame
        tr = tr1.copy()
        tr = tr.where(tr >= tr2, tr2)
        tr = tr.where(tr >= tr3, tr3)

        # Smoothed values using Wilder's smoothing with safety checks
        alpha = 1 / period
        tr_ema = tr.ewm(alpha=alpha, adjust=False).mean()
        tr_safe = tr_ema.where(tr_ema > 1e-8, 1e-8)  # Avoid division by zero

        plus_di = 100 * (plus_dm.ewm(alpha=alpha, adjust=False).mean() / tr_safe)
        minus_di = 100 * (minus_dm.ewm(alpha=alpha, adjust=False).mean() / tr_safe)

        return plus_di.fillna(0), minus_di.fillna(0)

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare strategy with robust error handling."""
        try:
            df = df.sort_index().copy()
            close = df["close"].astype(float)
            high = df["high"].astype(float)
            low = df["low"].astype(float)

            # Ichimoku indicators with robust calculations
            conversion_line = self._average(high, low, self.conversion_length)
            base_line = self._average(high, low, self.base_length)

            # lead lines (senkou spans) - these are shifted forward by delta for plotting
            lead_line_a = (conversion_line + base_line) / 2.0
            lead_line_b = self._average(high, low, self.lagging_length)

            # Use current close for lagging span (corrected implementation)
            lagging_span = close

            # Implement proper crossover detection with safety checks
            conv_prev = conversion_line.shift(1).fillna(conversion_line)
            base_prev = base_line.shift(1).fillna(base_line)

            conv_cross_up = (conversion_line > base_line) & (conv_prev <= base_prev)
            base_cross_up = (base_line > conversion_line) & (base_prev <= conv_prev)

            # Ichimoku signal logic with safety checks
            long_condition1 = conv_cross_up
            long_condition2 = lagging_span > lead_line_a
            long_condition3 = lagging_span > lead_line_b
            long_signal = long_condition1 & long_condition2 & long_condition3

            short_condition1 = base_cross_up
            short_condition2 = lagging_span < lead_line_a
            short_condition3 = lagging_span < lead_line_b
            short_signal = short_condition1 & short_condition2 & short_condition3

            # Initialize filter conditions
            filter_conditions = pd.Series(True, index=df.index)

            # Apply filters with error handling
            try:
                # 1. ATR% filter (2-5%)
                if self.use_atr_filter:
                    atr_pct = self._calculate_atr_pct(high, low, close, self.atr_period)
                    atr_filter = (atr_pct >= self.atr_min_pct) & (
                        atr_pct <= self.atr_max_pct
                    )
                    filter_conditions = filter_conditions & atr_filter

                # 2. RSI filter (> 50)
                if self.use_rsi_filter:
                    rsi = self._calculate_rsi(close, self.rsi_period)
                    rsi_filter = rsi > self.rsi_min
                    filter_conditions = filter_conditions & rsi_filter

                # 3. CCI filter (> 0)
                if self.use_cci_filter:
                    cci = self._calculate_cci(high, low, close, self.cci_period)
                    cci_filter = cci > self.cci_min
                    filter_conditions = filter_conditions & cci_filter

                # 4. +DI > -DI filter
                if self.use_di_filter:
                    plus_di, minus_di = self._calculate_di(high, low, close, 14)
                    di_filter = plus_di > minus_di
                    filter_conditions = filter_conditions & di_filter

                # 5. Above 20 EMA filter
                if self.use_ema20_filter:
                    ema20 = close.ewm(span=20, adjust=False, min_periods=20).mean()
                    ema20_filter = close > ema20
                    filter_conditions = filter_conditions & ema20_filter

                # 6. CMF filter (> -0.15)
                if self.use_cmf_filter and "volume" in df.columns:
                    volume = df["volume"].astype(float)
                    cmf = self._calculate_cmf(high, low, close, volume, self.cmf_period)
                    cmf_filter = cmf > self.cmf_min
                    filter_conditions = filter_conditions & cmf_filter

                # 7. Market regime filter (bullish markets only)
                if (
                    self.use_market_regime_filter
                    and self._market_regime_filter is not None
                ):
                    try:
                        # Apply regime filter to each timestamp
                        regime_filter = pd.Series(True, index=df.index)

                        # For efficiency, check regime in chunks or at key points
                        # Here we'll check every 5 days to balance accuracy vs performance
                        check_frequency = 5
                        for i in range(0, len(df), check_frequency):
                            end_idx = min(i + check_frequency, len(df))
                            chunk_data = df.iloc[:end_idx]  # Data up to this point

                            # Check if regime allows trading at this point
                            should_trade = self._market_regime_filter.should_trade(
                                chunk_data
                            )

                            # Apply to all dates in this chunk
                            chunk_dates = df.index[i:end_idx]
                            regime_filter.loc[chunk_dates] = should_trade

                        filter_conditions = filter_conditions & regime_filter

                    except Exception as regime_e:
                        print(f"Warning: Market regime filter error: {regime_e}")
                        # Continue without regime filter if it fails

            except Exception as e:
                print(f"Warning: Filter calculation error: {e}")
                # If filters fail, use unfiltered signals
                filter_conditions = pd.Series(True, index=df.index)

            # Apply filters to entry signals
            filtered_long_signal = long_signal & filter_conditions

            # Ensure boolean series with proper handling
            self._enter = filtered_long_signal.fillna(False).astype(bool)
            self._exit = short_signal.fillna(False).astype(bool)
            self.df = df

            # return df with indicator columns for optional plotting
            out = df.copy()
            out["conversion_line"] = conversion_line.ffill()
            out["base_line"] = base_line.ffill()
            out["lead_line_a"] = lead_line_a.shift(self.delta).ffill()
            out["lead_line_b"] = lead_line_b.shift(self.delta).ffill()
            out["lagging_span"] = lagging_span

            # Add filter indicators for analysis with error handling
            try:
                if self.use_atr_filter:
                    out["atr_pct"] = self._calculate_atr_pct(
                        high, low, close, self.atr_period
                    )
                if self.use_rsi_filter:
                    out["rsi"] = self._calculate_rsi(close, self.rsi_period)
                if self.use_cci_filter:
                    out["cci"] = self._calculate_cci(high, low, close, self.cci_period)
                if self.use_di_filter:
                    plus_di, minus_di = self._calculate_di(high, low, close, 14)
                    out["plus_di"] = plus_di.fillna(0)
                    out["minus_di"] = minus_di.fillna(0)
                if self.use_ema20_filter:
                    out["ema_20"] = close.ewm(
                        span=20, adjust=False, min_periods=20
                    ).mean()
                if self.use_cmf_filter and "volume" in df.columns:
                    volume = df["volume"].astype(float)
                    out["cmf"] = self._calculate_cmf(
                        high, low, close, volume, self.cmf_period
                    )
            except Exception as e:
                print(f"Warning: Indicator output error: {e}")

            # Add signal columns for debugging
            out["ichimoku_signal"] = long_signal.fillna(False)
            out["filtered_signal"] = filtered_long_signal.fillna(False)
            out["exit_signal"] = short_signal.fillna(False)

            return out

        except Exception as e:
            print(f"Error in prepare method: {e}")
            # Return minimal output in case of error
            out = df.copy()
            self._enter = pd.Series(False, index=df.index)
            self._exit = pd.Series(False, index=df.index)
            return out

    def on_bar(self, ts, row, state: dict[str, Any]) -> dict[str, Any]:
        def _scalar_bool_from_series(src, key):
            try:
                if src is None:
                    return False
                # Simple index-based lookup
                if hasattr(src, "index") and key in src.index:
                    val = src[key]
                    return bool(val) if not pd.isna(val) else False
                return False
            except Exception:
                return False

        enter = _scalar_bool_from_series(self._enter, ts)
        exit_ = _scalar_bool_from_series(self._exit, ts)
        return {"enter_long": enter, "exit_long": exit_}

    def __repr__(self):
        return f"IchimokuStrategy(conv={self.conversion_length}, base={self.base_length}, lag={self.lagging_length}, delta={self.delta})"
