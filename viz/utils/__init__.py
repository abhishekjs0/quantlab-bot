"""
Utility functions library adapted from backtesting.py for QuantLab.

Provides technical analysis indicators, data resampling utilities, and composable
strategy helpers optimized for Indian equity markets.

Original implementation: https://github.com/kernc/backtesting.py
Adapted for QuantLab's architecture and requirements.
"""

from typing import Union

import numpy as np
import pandas as pd


def SMA(series: pd.Series, n: int) -> pd.Series:
    """
    Simple Moving Average.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid SMA values from bar n onwards.

    Args:
        series: Input price series
        n: Period

    Returns:
        SMA with NaN for insufficient data period
    """
    return series.rolling(window=n).mean()


def WMA(values: np.ndarray, n: int) -> np.ndarray:
    """
    Weighted Moving Average.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid WMA values from bar n onwards.

    Args:
        values: Input array
        n: Period

    Returns:
        Weighted moving average array with NaN for insufficient data period
    """
    weights = np.arange(1, n + 1)

    if isinstance(values, pd.Series):
        wma = values.rolling(n).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )
        return wma.values
    else:
        result = np.full_like(values, np.nan, dtype=float)
        for i in range(n - 1, len(values)):
            result[i] = np.dot(values[i - n + 1 : i + 1], weights) / weights.sum()
        return result


def EMA(values: np.ndarray, n: int, alpha=None) -> np.ndarray:
    """
    Exponential Moving Average.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid EMA values from bar n onwards.

    Args:
        values: Input array
        n: Period
        alpha: Smoothing factor (default: 2/(n+1))

    Returns:
        EMA array with NaN for insufficient data period
    """
    if alpha is None:
        alpha = 2.0 / (n + 1)

    result = np.empty_like(values, dtype=float)
    result[0] = values.iloc[0] if hasattr(values, "iloc") else values[0]

    for i in range(1, len(values)):
        val_i = values.iloc[i] if hasattr(values, "iloc") else values[i]
        result[i] = alpha * val_i + (1 - alpha) * result[i - 1]

    return result


def RSI(series: pd.Series, n: int = 14) -> pd.Series:
    """
    Relative Strength Index (RSI) - momentum oscillator.

    Returns NaN for first n bars where calculation is incomplete.
    Only valid RSI values from bar n onwards.

    Args:
        series: Input price series
        n: Period (default: 14)

    Returns:
        RSI values as pandas Series with NaN for insufficient data period
    """
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(window=n).mean()
    avg_loss = loss.rolling(window=n).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def MACD(values: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    MACD (Moving Average Convergence Divergence).

    Returns NaN for first slow-1 bars where calculation is incomplete.
    Only valid MACD values from bar slow onwards.

    Args:
        values: Input price array
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)

    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' arrays
        All contain NaN for insufficient data period
    """
    ema_fast = EMA(values, fast)
    ema_slow = EMA(values, slow)

    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def BollingerBands(values: np.ndarray, n: int = 20, std: float = 2) -> dict:
    """
    Bollinger Bands.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid Bollinger Bands values from bar n onwards.

    Args:
        values: Input price array
        n: Period (default: 20)
        std: Number of standard deviations (default: 2)

    Returns:
        Dictionary with 'upper', 'middle', and 'lower' bands
        All contain NaN for insufficient data period
    """
    values_series = pd.Series(values)
    sma = SMA(values_series, n)
    rolling_std = values_series.rolling(n).std().values

    upper = sma.values + (rolling_std * std)
    lower = sma.values - (rolling_std * std)

    return {"upper": upper, "middle": sma.values, "lower": lower}


def Envelope(
    close: pd.Series, length: int = 200, percent: float = 14.0, use_ema: bool = False
) -> dict:
    """
    Envelope indicator - basis line with percentage-based bands.

    Returns NaN for first length-1 bars where calculation is incomplete.
    Only valid Envelope values from bar length onwards.

    Uses SMA or EMA as basis with symmetric percentage bands above/below.

    Args:
        close: Close prices series
        length: Period for basis calculation (default: 200)
        percent: Band percentage (default: 14.0 for 14%)
        use_ema: Use EMA instead of SMA (default: False)

    Returns:
        Dictionary with 'basis', 'upper', and 'lower' bands
    """
    if use_ema:
        basis = EMA(close.values if isinstance(close, pd.Series) else close, length)
    else:
        basis_series = SMA(close, length)
        basis = (
            basis_series.values if isinstance(basis_series, pd.Series) else basis_series
        )

    basis = np.asarray(basis, dtype=np.float64)
    k = percent / 100.0
    upper = basis * (1.0 + k)
    lower = basis * (1.0 - k)

    return {"basis": basis, "upper": upper, "lower": lower}


def ATR(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14
) -> np.ndarray:
    """
    Average True Range.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid ATR values from bar n onwards.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        n: Period (default: 14)

    Returns:
        ATR values array with NaN for insufficient data period
    """
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))

    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr = np.array(tr)  # Ensure it's a numpy array
    tr1 = np.array(tr1)  # Also ensure tr1 is numpy array
    # Fix first value - use direct numpy array indexing instead of Series
    if len(tr1) > 0:
        tr[0] = tr1[0]
    else:
        tr[0] = 0

    # Convert to Series with proper index to avoid FutureWarning
    tr_series = pd.Series(tr, index=range(len(tr)))
    return SMA(tr_series, n).values


def Stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> dict:
    """
    Stochastic Oscillator.

    Returns NaN for first k_period-1 bars where calculation is incomplete.
    Only valid Stochastic values from bar k_period onwards.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        k_period: K period (default: 14)
        d_period: D period (default: 3)

    Returns:
        Dictionary with 'k' and 'd' arrays containing NaN for insufficient data
    """
    high_roll = pd.Series(high).rolling(k_period).max().values
    low_roll = pd.Series(low).rolling(k_period).min().values

    k_percent = 100 * (close - low_roll) / (high_roll - low_roll)
    d_percent = SMA(pd.Series(k_percent), d_period).values

    return {"k": k_percent, "d": d_percent}


def StochasticRSI(
    close: pd.Series,
    rsi_period: int = 14,
    k_period: int = 14,
    d_period: int = 3,
) -> dict:
    """
    Stochastic RSI - applies Stochastic calculation to RSI values.

    Returns NaN for first max(rsi_period, k_period)-1 bars where calculation is incomplete.
    Only valid StochasticRSI values from bar max(rsi_period, k_period) onwards.

    Combines RSI with stochastic to measure oversold/overbought on RSI itself.

    Args:
        close: Close prices series
        rsi_period: RSI period (default: 14)
        k_period: Stochastic %K period (default: 14)
        d_period: Stochastic %D period (default: 3)

    Returns:
        Dictionary with 'k' and 'd' values containing NaN for insufficient data
    """
    # Calculate RSI
    rsi_vals = RSI(close, rsi_period)

    # Apply stochastic to RSI values
    rsi_series = pd.Series(rsi_vals)
    lowest_rsi = rsi_series.rolling(window=k_period).min()
    highest_rsi = rsi_series.rolling(window=k_period).max()

    # Fast %K (raw stochastic of RSI)
    fast_k = 100.0 * (rsi_vals - lowest_rsi) / (highest_rsi - lowest_rsi)
    fast_k = fast_k.fillna(50).values

    # Fast %D (D line - smoothing of Fast %K)
    fast_d = SMA(pd.Series(fast_k), d_period).values

    return {"k": fast_k, "d": fast_d}


def Williams_R(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14
) -> np.ndarray:
    """
    Williams %R.

    Returns NaN for first n-1 bars where calculation is incomplete.
    Only valid Williams %R values from bar n onwards.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        n: Period (default: 14)

    Returns:
        Williams %R values array with NaN for insufficient data period
    """
    high_roll = pd.Series(high).rolling(n).max().values
    low_roll = pd.Series(low).rolling(n).min().values

    return -100 * (high_roll - close) / (high_roll - low_roll)


def crossover(series1: np.ndarray, series2) -> np.ndarray:
    """
    Return True where series1 crosses over series2.

    Args:
        series1: First series
        series2: Second series or scalar value

    Returns:
        Boolean array indicating crossover points
    """
    series1 = np.asarray(series1)
    series2 = np.asarray(series2)

    if series2.ndim == 0:  # scalar
        return (series1[:-1] <= series2) & (series1[1:] > series2)
    else:
        return (series1[:-1] <= series2[:-1]) & (series1[1:] > series2[1:])


def crossunder(series1: np.ndarray, series2) -> np.ndarray:
    """
    Return True where series1 crosses under series2.

    Args:
        series1: First series
        series2: Second series or scalar value

    Returns:
        Boolean array indicating crossunder points
    """
    return crossover(series2, series1)


def resample_apply(rule: str, data: pd.DataFrame, apply_func=None) -> pd.DataFrame:
    """
    Resample OHLCV data to different timeframes.

    Args:
        rule: Pandas resample rule (e.g., "1H", "1D", "1W")
        data: OHLCV DataFrame with DatetimeIndex
        apply_func: Optional function to apply to resampled data

    Returns:
        Resampled DataFrame
    """
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("Data must have DatetimeIndex for resampling")

    # Define resampling logic for OHLCV data
    agg_dict = {}

    if "Open" in data.columns:
        agg_dict["Open"] = "first"
    if "High" in data.columns:
        agg_dict["High"] = "max"
    if "Low" in data.columns:
        agg_dict["Low"] = "min"
    if "Close" in data.columns:
        agg_dict["Close"] = "last"
    if "Volume" in data.columns:
        agg_dict["Volume"] = "sum"

    # Add any other numeric columns with mean aggregation
    for col in data.columns:
        if col not in agg_dict and pd.api.types.is_numeric_dtype(data[col]):
            agg_dict[col] = "mean"

    resampled = data.resample(rule).agg(agg_dict)

    # Apply custom function if provided
    if apply_func is not None:
        resampled = apply_func(resampled)

    return resampled.dropna()


def rolling_window(data: np.ndarray, window: int) -> np.ndarray:
    """
    Create rolling window view of data for vectorized operations.

    Args:
        data: Input array
        window: Window size

    Returns:
        2D array where each row is a rolling window
    """
    if window > len(data):
        raise ValueError("Window size cannot be larger than data length")

    shape = (len(data) - window + 1, window)
    strides = (data.strides[0], data.strides[0])

    return np.lib.stride_tricks.as_strided(data, shape=shape, strides=strides)


def percent_rank(values: np.ndarray, n: int) -> np.ndarray:
    """
    Percentile rank of values over rolling window.

    Args:
        values: Input array
        n: Window size

    Returns:
        Percentile rank array (0-100)
    """
    result = np.full_like(values, np.nan, dtype=float)

    for i in range(n - 1, len(values)):
        window = values[i - n + 1 : i + 1]
        current = values[i]
        rank = (window < current).sum() / len(window) * 100
        result[i] = rank

    return result


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """
    Calculate True Range.

    Args:
        high: High prices
        low: Low prices
        close: Close prices

    Returns:
        True Range array
    """
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))

    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]  # First value

    return tr


def donchian_channel(high: np.ndarray, low: np.ndarray, n: int = 20) -> dict:
    """
    Donchian Channel.

    Args:
        high: High prices array
        low: Low prices array
        n: Period (default: 20)

    Returns:
        Dictionary with 'upper', 'lower', and 'middle' channel lines
    """
    upper = pd.Series(high).rolling(n).max().values
    lower = pd.Series(low).rolling(n).min().values
    middle = (upper + lower) / 2

    return {"upper": upper, "lower": lower, "middle": middle}


def renko_bars(
    data: pd.DataFrame, brick_size=None, percentage: bool = False
) -> pd.DataFrame:
    """
    Generate Renko bars from OHLC data.

    Args:
        data: OHLC DataFrame
        brick_size: Size of each brick (auto-calculated if None)
        percentage: Whether brick_size is percentage (default: False)

    Returns:
        DataFrame with Renko bars
    """
    if brick_size is None:
        # Auto-calculate brick size as 1% of average price
        avg_price = data["Close"].mean()
        brick_size = avg_price * 0.01

    close_prices = data["Close"].values
    renko_data = []

    if len(close_prices) == 0:
        return pd.DataFrame()

    current_brick = close_prices[0]

    for i, price in enumerate(close_prices):
        if percentage:
            threshold = current_brick * brick_size / 100
        else:
            threshold = brick_size

        # Check for new brick formation
        if price >= current_brick + threshold:
            # Upward brick(s)
            while price >= current_brick + threshold:
                new_brick = current_brick + threshold
                renko_data.append(
                    {
                        "timestamp": data.index[i],
                        "open": current_brick,
                        "close": new_brick,
                        "direction": 1,
                    }
                )
                current_brick = new_brick

        elif price <= current_brick - threshold:
            # Downward brick(s)
            while price <= current_brick - threshold:
                new_brick = current_brick - threshold
                renko_data.append(
                    {
                        "timestamp": data.index[i],
                        "open": current_brick,
                        "close": new_brick,
                        "direction": -1,
                    }
                )
                current_brick = new_brick

    return pd.DataFrame(renko_data).set_index("timestamp")


class StrategyMixin:
    """Mixin providing additional utility methods for strategies."""

    def buy_signal(
        self, condition: np.ndarray, stop_loss=None, take_profit=None
    ) -> dict:
        """
        Generate buy signal with optional stop loss and take profit.

        Args:
            condition: Boolean array indicating buy signals
            stop_loss: Stop loss percentage (e.g., 0.05 for 5%)
            take_profit: Take profit percentage (e.g., 0.10 for 10%)

        Returns:
            Dictionary with signal information
        """
        signals = {
            "action": np.where(condition, 1, 0),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        return signals

    def sell_signal(
        self, condition: np.ndarray, stop_loss=None, take_profit=None
    ) -> dict:
        """
        Generate sell signal with optional stop loss and take profit.

        Args:
            condition: Boolean array indicating sell signals
            stop_loss: Stop loss percentage
            take_profit: Take profit percentage

        Returns:
            Dictionary with signal information
        """
        signals = {
            "action": np.where(condition, -1, 0),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        return signals

    def position_size(
        self, price: float, risk_per_trade: float = 0.02, account_value: float = 100000
    ) -> int:
        """
        Calculate position size based on risk management.

        Args:
            price: Entry price
            risk_per_trade: Risk per trade as percentage of account (default: 2%)
            account_value: Total account value

        Returns:
            Number of shares to buy/sell
        """
        risk_amount = account_value * risk_per_trade
        shares = int(risk_amount / price)
        return max(1, shares)  # At least 1 share


def Momentum(series: pd.Series, n: int = 14) -> pd.Series:
    """
    Momentum - rate of change indicator.

    Returns NaN for first n bars where calculation is incomplete.
    Only valid Momentum values from bar n onwards.

    Measures the rate at which prices are changing.
    Formula: Close - Close[n periods ago]

    Args:
        series: Input price series (typically close prices)
        n: Period (default: 14)

    Returns:
        Momentum series with NaN for insufficient data period
    """
    return series - series.shift(n)


def volatility_adjusted_returns(returns: pd.Series, window: int = 30) -> pd.Series:
    """
    Calculate volatility-adjusted returns (returns / volatility).

    Args:
        returns: Return series
        window: Rolling window for volatility calculation

    Returns:
        Volatility-adjusted returns
    """
    volatility = returns.rolling(window).std()
    return returns / volatility


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.05) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: Return series (annualized)
        risk_free_rate: Risk-free rate (default: 5% annually)

    Returns:
        Sharpe ratio
    """
    excess_returns = returns.mean() - risk_free_rate
    return excess_returns / returns.std() if returns.std() != 0 else 0


def max_drawdown(equity_curve: pd.Series) -> dict:
    """
    Calculate maximum drawdown.

    Args:
        equity_curve: Equity curve series

    Returns:
        Dictionary with max drawdown info
    """
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max

    max_dd = drawdown.min()
    max_dd_end = drawdown.idxmin()
    max_dd_start = equity_curve[:max_dd_end].idxmax()

    return {
        "max_drawdown": max_dd,
        "start_date": max_dd_start,
        "end_date": max_dd_end,
        "duration": (max_dd_end - max_dd_start).days,
    }


# Commonly used technical indicator presets
COMMON_INDICATORS = {
    "sma_fast": lambda close: SMA(close, 10),
    "sma_slow": lambda close: SMA(close, 30),
    "ema_fast": lambda close: EMA(close, 12),
    "ema_slow": lambda close: EMA(close, 26),
    "rsi": lambda close: RSI(close, 14),
    "macd": lambda close: MACD(close),
    "bb": lambda close: BollingerBands(close),
}


def apply_indicators(data: pd.DataFrame, indicators: list = None) -> pd.DataFrame:
    """
    Apply multiple technical indicators to OHLC data.

    Args:
        data: OHLC DataFrame
        indicators: List of indicator names or functions

    Returns:
        DataFrame with additional indicator columns
    """
    if indicators is None:
        indicators = ["sma_fast", "sma_slow", "rsi"]

    result = data.copy()

    for indicator in indicators:
        if isinstance(indicator, str) and indicator in COMMON_INDICATORS:
            func = COMMON_INDICATORS[indicator]
            if indicator.startswith(("sma", "ema", "rsi")):
                result[indicator] = func(data["Close"].values)
            elif indicator == "macd":
                macd_data = func(data["Close"].values)
                result["macd"] = macd_data["macd"]
                result["macd_signal"] = macd_data["signal"]
                result["macd_histogram"] = macd_data["histogram"]
            elif indicator == "bb":
                bb_data = func(data["Close"].values)
                result["bb_upper"] = bb_data["upper"]
                result["bb_middle"] = bb_data["middle"]
                result["bb_lower"] = bb_data["lower"]
        elif callable(indicator):
            # Custom function
            result[f"custom_{len(result.columns)}"] = indicator(data)

    return result
