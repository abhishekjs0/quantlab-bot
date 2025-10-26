"""
Market regime detection system for identifying bullish/sideways/bearish conditions.

This module implements various methods to detect market regimes based on price action,
volatility, and trend analysis. The regime detection is designed for 2-3 month
timeframes and can be used as a filter for strategy entries.
"""

import logging
from enum import Enum

import numpy as np
import pandas as pd


class MarketRegime(Enum):
    """Market regime classifications."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class RegimeDetector:
    """
    Market regime detection using multiple technical indicators and methods.

    This class implements several regime detection algorithms:
    1. Trend-based using moving averages
    2. Volatility-based using ADX and volatility measures
    3. Momentum-based using RSI and rate of change
    4. Multiple timeframe analysis
    """

    def __init__(
        self,
        short_ma: int = 20,
        medium_ma: int = 50,
        long_ma: int = 200,
        lookback_days: int = 60,
        volatility_window: int = 20,
        trend_threshold: float = 0.02,
        sideways_threshold: float = 0.005,
    ):
        """
        Initialize regime detector with parameters.

        Args:
            short_ma: Short-term moving average period
            medium_ma: Medium-term moving average period
            long_ma: Long-term moving average period
            lookback_days: Days to look back for regime classification
            volatility_window: Window for volatility calculations
            trend_threshold: Minimum slope for trending regime (2% default)
            sideways_threshold: Maximum slope for sideways regime (0.5% default)
        """
        self.short_ma = short_ma
        self.medium_ma = medium_ma
        self.long_ma = long_ma
        self.lookback_days = lookback_days
        self.volatility_window = volatility_window
        self.trend_threshold = trend_threshold
        self.sideways_threshold = sideways_threshold

        self.logger = logging.getLogger(__name__)

    def detect_regime(self, data: pd.DataFrame) -> pd.Series:
        """
        Detect market regime for each date in the dataset.

        Args:
            data: OHLCV DataFrame with datetime index

        Returns:
            Series with MarketRegime values for each date
        """
        if not self._validate_data(data):
            return pd.Series([MarketRegime.UNKNOWN] * len(data), index=data.index)

        close = data["close"]

        # Calculate technical indicators
        indicators = self._calculate_indicators(data)

        # Apply multiple regime detection methods
        trend_regime = self._trend_based_regime(close, indicators)
        momentum_regime = self._momentum_based_regime(close, indicators)
        volatility_regime = self._volatility_based_regime(indicators)

        # Combine regimes using consensus approach
        combined_regime = self._combine_regimes(
            trend_regime, momentum_regime, volatility_regime
        )

        # Apply smoothing to reduce noise
        smoothed_regime = self._smooth_regime(combined_regime)

        return smoothed_regime

    def get_current_regime(self, data: pd.DataFrame) -> MarketRegime:
        """
        Get the current market regime based on latest data.

        Args:
            data: OHLCV DataFrame

        Returns:
            Current market regime
        """
        regimes = self.detect_regime(data)
        if len(regimes) == 0:
            return MarketRegime.UNKNOWN
        return regimes.iloc[-1]

    def get_regime_strength(self, data: pd.DataFrame) -> float:
        """
        Calculate the strength/confidence of the current regime.

        Args:
            data: OHLCV DataFrame

        Returns:
            Regime strength from 0.0 (weak) to 1.0 (strong)
        """
        if len(data) < self.lookback_days:
            return 0.0

        close = data["close"]
        indicators = self._calculate_indicators(data)

        # Calculate trend strength
        trend_strength = self._calculate_trend_strength(close, indicators)

        # Calculate momentum consistency
        momentum_strength = self._calculate_momentum_strength(indicators)

        # Calculate volatility regime clarity
        vol_strength = self._calculate_volatility_strength(indicators)

        # Combine strengths
        overall_strength = np.mean([trend_strength, momentum_strength, vol_strength])
        return np.clip(overall_strength, 0.0, 1.0)

    def _validate_data(self, data: pd.DataFrame) -> bool:
        """Validate input data has required columns and sufficient length."""
        required_cols = ["open", "high", "low", "close"]
        if not all(col in data.columns for col in required_cols):
            self.logger.error(f"Data missing required columns: {required_cols}")
            return False

        if len(data) < self.long_ma:
            self.logger.warning(f"Insufficient data: {len(data)} < {self.long_ma}")
            return False

        return True

    def _calculate_indicators(self, data: pd.DataFrame) -> dict:
        """Calculate technical indicators needed for regime detection."""
        close = data["close"]
        high = data["high"]
        low = data["low"]

        indicators = {}

        # Moving averages
        indicators["sma_short"] = close.rolling(self.short_ma).mean()
        indicators["sma_medium"] = close.rolling(self.medium_ma).mean()
        indicators["sma_long"] = close.rolling(self.long_ma).mean()

        # Exponential moving averages
        indicators["ema_short"] = close.ewm(span=self.short_ma).mean()
        indicators["ema_medium"] = close.ewm(span=self.medium_ma).mean()

        # Rate of change
        indicators["roc_short"] = close.pct_change(self.short_ma)
        indicators["roc_medium"] = close.pct_change(self.medium_ma)

        # RSI
        indicators["rsi"] = self._calculate_rsi(close, 14)

        # ADX for trend strength
        indicators["adx"] = self._calculate_adx(high, low, close, 14)

        # Volatility measures
        indicators["volatility"] = close.rolling(self.volatility_window).std()
        indicators["atr"] = self._calculate_atr(high, low, close, 14)

        # Price position relative to moving averages
        indicators["price_vs_sma_short"] = close / indicators["sma_short"] - 1
        indicators["price_vs_sma_medium"] = close / indicators["sma_medium"] - 1
        indicators["price_vs_sma_long"] = close / indicators["sma_long"] - 1

        return indicators

    def _trend_based_regime(self, close: pd.Series, indicators: dict) -> pd.Series:
        """Detect regime based on trend analysis with optimized calculations."""
        regime = pd.Series([MarketRegime.UNKNOWN] * len(close), index=close.index)

        # Optimized trend direction - use simple ratio instead of pct_change for speed
        sma_long = indicators["sma_long"]
        sma_medium = indicators["sma_medium"]

        # Fast slope calculation using shift instead of pct_change
        sma_long_slope = (sma_long / sma_long.shift(self.lookback_days)) - 1
        (sma_medium / sma_medium.shift(self.lookback_days // 2)) - 1

        # Price position relative to moving averages
        above_long_ma = close > sma_long
        above_medium_ma = close > sma_medium

        # Moving average alignment
        ma_bullish = (indicators["sma_short"] > sma_medium) & (sma_medium > sma_long)
        ma_bearish = (indicators["sma_short"] < sma_medium) & (sma_medium < sma_long)

        # Trend regime conditions
        bullish_trend = (
            (sma_long_slope > self.trend_threshold)
            & above_long_ma
            & above_medium_ma
            & ma_bullish
        )

        bearish_trend = (
            (sma_long_slope < -self.trend_threshold)
            & (~above_long_ma)
            & (~above_medium_ma)
            & ma_bearish
        )

        sideways_trend = (abs(sma_long_slope) <= self.sideways_threshold) | (
            ~ma_bullish & ~ma_bearish
        )

        regime.loc[bullish_trend] = MarketRegime.BULLISH
        regime.loc[bearish_trend] = MarketRegime.BEARISH
        regime.loc[sideways_trend] = MarketRegime.SIDEWAYS

        return regime

    def _momentum_based_regime(self, close: pd.Series, indicators: dict) -> pd.Series:
        """Detect regime based on momentum indicators."""
        regime = pd.Series([MarketRegime.UNKNOWN] * len(close), index=close.index)

        rsi = indicators["rsi"]
        roc_medium = indicators["roc_medium"]

        # Momentum conditions
        strong_bullish_momentum = (rsi > 60) & (roc_medium > 0.05)
        moderate_bullish_momentum = (rsi > 50) & (roc_medium > 0.02)

        strong_bearish_momentum = (rsi < 40) & (roc_medium < -0.05)
        moderate_bearish_momentum = (rsi < 50) & (roc_medium < -0.02)

        neutral_momentum = (rsi >= 40) & (rsi <= 60) & (abs(roc_medium) <= 0.02)

        # Assign regimes
        bullish_momentum = strong_bullish_momentum | moderate_bullish_momentum
        bearish_momentum = strong_bearish_momentum | moderate_bearish_momentum

        regime.loc[bullish_momentum] = MarketRegime.BULLISH
        regime.loc[bearish_momentum] = MarketRegime.BEARISH
        regime.loc[neutral_momentum] = MarketRegime.SIDEWAYS

        return regime

    def _volatility_based_regime(self, indicators: dict) -> pd.Series:
        """Detect regime based on volatility characteristics."""
        regime = pd.Series(
            [MarketRegime.UNKNOWN] * len(indicators["adx"]),
            index=indicators["adx"].index,
        )

        adx = indicators["adx"]
        volatility = indicators["volatility"]

        # Normalize volatility (z-score over longer period)
        vol_mean = volatility.rolling(self.lookback_days * 2).mean()
        vol_std = volatility.rolling(self.lookback_days * 2).std()
        (volatility - vol_mean) / vol_std

        # Trend strength conditions
        weak_trend = adx < 20

        # Volatility conditions

        # Trending markets (high ADX)
        non_trending = weak_trend

        # In trending markets, use other signals
        # In non-trending markets, likely sideways
        regime.loc[non_trending] = MarketRegime.SIDEWAYS

        return regime

    def _combine_regimes(self, *regime_series) -> pd.Series:
        """Combine multiple regime classifications using voting."""
        df = pd.DataFrame(
            {f"regime_{i}": series for i, series in enumerate(regime_series)}
        )

        # Count votes for each regime
        result = pd.Series([MarketRegime.UNKNOWN] * len(df), index=df.index)

        for i in range(len(df)):
            row = df.iloc[i]
            # Manual vote counting to completely avoid pandas enum sorting issues
            regime_counts = {}
            for regime in row:
                if regime in regime_counts:
                    regime_counts[regime] += 1
                else:
                    regime_counts[regime] = 1

            # Simple majority vote - get regime with highest count
            if regime_counts:
                winner = max(regime_counts, key=regime_counts.get)
                if winner != MarketRegime.UNKNOWN:
                    result.iloc[i] = winner

        return result

    def _smooth_regime(self, regime: pd.Series, window: int = 5) -> pd.Series:
        """Apply smoothing to reduce regime switching noise using efficient vectorized operations."""
        # Use pandas rolling operations for much better performance
        # Convert enum to numeric for efficient rolling operations
        regime_numeric = regime.map(
            {
                MarketRegime.BULLISH: 1,
                MarketRegime.BEARISH: -1,
                MarketRegime.SIDEWAYS: 0,
                MarketRegime.UNKNOWN: 999,
            }
        )

        # Use rolling mode - take most frequent value in window
        # For efficiency, use rolling mean and round to nearest valid value
        smoothed_numeric = regime_numeric.rolling(window=window, min_periods=1).apply(
            lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else x.iloc[-1], raw=False
        )

        # Convert back to enum
        numeric_to_regime = {
            1: MarketRegime.BULLISH,
            -1: MarketRegime.BEARISH,
            0: MarketRegime.SIDEWAYS,
            999: MarketRegime.UNKNOWN,
        }

        return smoothed_numeric.map(numeric_to_regime)

    def _calculate_trend_strength(self, close: pd.Series, indicators: dict) -> float:
        """Calculate trend strength score."""
        if len(close) < self.lookback_days:
            return 0.0

        # Recent slope of long MA
        recent_slope = (
            indicators["sma_long"].iloc[-1]
            / indicators["sma_long"].iloc[-self.lookback_days]
            - 1
        )
        trend_strength = min(abs(recent_slope) / self.trend_threshold, 1.0)

        return trend_strength

    def _calculate_momentum_strength(self, indicators: dict) -> float:
        """Calculate momentum consistency score."""
        if len(indicators["rsi"]) < self.lookback_days:
            return 0.0

        # RSI consistency (less volatility = higher strength)
        recent_rsi = indicators["rsi"].iloc[-self.lookback_days :]
        rsi_std = recent_rsi.std()
        momentum_strength = max(
            0.0, 1.0 - rsi_std / 20.0
        )  # Normalize by typical RSI std

        return momentum_strength

    def _calculate_volatility_strength(self, indicators: dict) -> float:
        """Calculate volatility regime clarity."""
        if len(indicators["adx"]) < self.lookback_days:
            return 0.0

        # ADX strength (higher ADX = clearer regime)
        recent_adx = indicators["adx"].iloc[-self.lookback_days :].mean()
        vol_strength = min(recent_adx / 40.0, 1.0)  # Normalize by strong ADX level

        return vol_strength

    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        alpha = 1 / period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss.where(avg_loss > 0, np.inf)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)

    def _calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate ADX (Average Directional Index)."""
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional movements
        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        # Smoothed values
        alpha = 1 / period
        atr = tr.ewm(alpha=alpha, adjust=False).mean()
        plus_di = 100 * plus_dm.ewm(alpha=alpha, adjust=False).mean() / atr
        minus_di = 100 * minus_dm.ewm(alpha=alpha, adjust=False).mean() / atr

        # ADX calculation
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=alpha, adjust=False).mean()

        return adx.fillna(0)

    def _calculate_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate Average True Range."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr = tr.rolling(period).mean()
        return atr.fillna(0)


class MarketRegimeFilter:
    """
    Filter for strategy entries based on market regime.

    This class can be used to enhance strategies by only taking trades
    when market conditions are favorable for the strategy type.
    """

    def __init__(
        self,
        detector: RegimeDetector,
        allowed_regimes: list[MarketRegime],
        min_strength: float = 0.5,
        regime_data_symbol: str = "NIFTY50",
    ):
        """
        Initialize regime filter.

        Args:
            detector: RegimeDetector instance
            allowed_regimes: List of regimes to allow trades
            min_strength: Minimum regime strength required
            regime_data_symbol: Symbol to use for regime detection
        """
        self.detector = detector
        self.allowed_regimes = allowed_regimes
        self.min_strength = min_strength
        self.regime_data_symbol = regime_data_symbol
        self.logger = logging.getLogger(__name__)

    def should_trade(
        self, market_data: pd.DataFrame, current_date: pd.Timestamp | None = None
    ) -> bool:
        """
        Determine if trading should be allowed based on market regime.

        Args:
            market_data: Market index data (e.g., NIFTY50)
            current_date: Date to check (uses latest if None)

        Returns:
            True if trading is allowed, False otherwise
        """
        try:
            # Get regime for current or latest date
            if current_date is not None:
                # Get data up to current date
                data_slice = market_data[market_data.index <= current_date]
            else:
                data_slice = market_data

            if len(data_slice) == 0:
                self.logger.warning("No market data available for regime check")
                return False

            # Detect current regime
            current_regime = self.detector.get_current_regime(data_slice)
            regime_strength = self.detector.get_regime_strength(data_slice)

            # Check if regime is allowed and strong enough
            regime_allowed = current_regime in self.allowed_regimes
            strength_sufficient = regime_strength >= self.min_strength

            self.logger.debug(
                f"Regime check: {current_regime.value} (strength: {regime_strength:.2f}) "
                f"- Trade allowed: {regime_allowed and strength_sufficient}"
            )

            return regime_allowed and strength_sufficient

        except Exception as e:
            self.logger.error(f"Error in regime check: {e}")
            return False  # Conservative approach - don't trade on errors


def create_trend_following_filter() -> MarketRegimeFilter:
    """Create a regime filter optimized for trend-following strategies."""
    detector = RegimeDetector(
        short_ma=20,
        medium_ma=50,
        long_ma=200,
        lookback_days=60,
        trend_threshold=0.02,
        sideways_threshold=0.005,
    )

    return MarketRegimeFilter(
        detector=detector,
        allowed_regimes=[MarketRegime.BULLISH],  # Only trade in bull markets
        min_strength=0.4,  # Require decent confidence
        regime_data_symbol="NIFTY50",
    )


def create_mean_reversion_filter() -> MarketRegimeFilter:
    """Create a regime filter optimized for mean-reversion strategies."""
    detector = RegimeDetector(
        short_ma=10,
        medium_ma=20,
        long_ma=50,
        lookback_days=30,
        trend_threshold=0.015,
        sideways_threshold=0.008,
    )

    return MarketRegimeFilter(
        detector=detector,
        allowed_regimes=[MarketRegime.SIDEWAYS],  # Trade in sideways markets
        min_strength=0.5,
        regime_data_symbol="NIFTY50",
    )


def analyze_regime_history(data: pd.DataFrame, detector: RegimeDetector) -> dict:
    """
    Analyze historical regime patterns in the data.

    Args:
        data: OHLCV market data
        detector: RegimeDetector instance

    Returns:
        Dictionary with regime analysis results
    """
    regimes = detector.detect_regime(data)

    # Calculate regime statistics
    regime_counts = regimes.value_counts(sort=False)
    regime_pcts = regime_counts / len(regimes) * 100

    # Regime duration analysis
    regimes != regimes.shift(1)
    regime_periods = []
    current_regime = None
    current_start = None

    for date, regime in regimes.items():
        if regime != current_regime:
            if current_regime is not None:
                duration = (date - current_start).days
                regime_periods.append(
                    {
                        "regime": current_regime,
                        "start": current_start,
                        "end": date,
                        "duration_days": duration,
                    }
                )
            current_regime = regime
            current_start = date

    # Add final period
    if current_regime is not None:
        duration = (regimes.index[-1] - current_start).days
        regime_periods.append(
            {
                "regime": current_regime,
                "start": current_start,
                "end": regimes.index[-1],
                "duration_days": duration,
            }
        )

    periods_df = pd.DataFrame(regime_periods)

    # Calculate average duration by regime
    avg_durations = {}
    if len(periods_df) > 0:
        for regime in MarketRegime:
            regime_periods_filtered = periods_df[periods_df["regime"] == regime]
            if len(regime_periods_filtered) > 0:
                avg_durations[regime.value] = regime_periods_filtered[
                    "duration_days"
                ].mean()
            else:
                avg_durations[regime.value] = 0

    return {
        "regime_counts": regime_counts.to_dict(),
        "regime_percentages": regime_pcts.to_dict(),
        "average_durations": avg_durations,
        "regime_periods": periods_df,
        "total_regime_changes": len(periods_df),
        "regime_series": regimes,
    }
