"""
Utility functions library adapted from backtesting.py for QuantLab.

Provides technical analysis indicators, data resampling utilities, and composable
strategy helpers optimized for Indian equity markets.

Original implementation: https://github.com/kernc/backtesting.py
Adapted for QuantLab's architecture and requirements.
"""

import numpy as np
import pandas as pd
from typing import Union


def SMA(series: pd.Series, n: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=n).mean()


def WMA(values: np.ndarray, n: int) -> np.ndarray:
    """
    Weighted Moving Average.
    
    Args:
        values: Input array
        n: Period
    
    Returns:
        Weighted moving average array
    """
    weights = np.arange(1, n + 1)
    
    if isinstance(values, pd.Series):
        wma = values.rolling(n).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
        return wma.values
    else:
        result = np.full_like(values, np.nan, dtype=float)
        for i in range(n - 1, len(values)):
            result[i] = np.dot(values[i - n + 1:i + 1], weights) / weights.sum()
        return result


def EMA(values: np.ndarray, n: int, alpha: float = None) -> np.ndarray:
    """
    Exponential Moving Average.

    Args:
        values: Input array
        n: Period
        alpha: Smoothing factor (default: 2/(n+1))

    Returns:
        Exponential moving average array
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

    Args:
        series: Input price series
        n: Period (default: 14)

    Returns:
        RSI values as pandas Series
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

    Args:
        values: Input price array
        fast: Fast EMA period (default: 12)
        slow: Slow EMA period (default: 26)
        signal: Signal line EMA period (default: 9)

    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' arrays
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

    Args:
        values: Input price array
        n: Period (default: 20)
        std: Number of standard deviations (default: 2)

    Returns:
        Dictionary with 'upper', 'middle', and 'lower' bands
    """
    values_series = pd.Series(values)
    sma = SMA(values_series, n)
    rolling_std = values_series.rolling(n).std().values

    upper = sma.values + (rolling_std * std)
    lower = sma.values - (rolling_std * std)

    return {"upper": upper, "middle": sma.values, "lower": lower}


def ATR(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14
) -> np.ndarray:
    """
    Average True Range.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        n: Period (default: 14)

    Returns:
        ATR values array
    """
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))

    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0] if len(tr1) > 0 else 0  # First value doesn't have previous close

    return SMA(pd.Series(tr), n).values


def Stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> dict:
    """
    Stochastic Oscillator.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        k_period: %K period (default: 14)
        d_period: %D period (default: 3)

    Returns:
        Dictionary with 'k' and 'd' values
    """
    high_roll = pd.Series(high).rolling(k_period).max().values
    low_roll = pd.Series(low).rolling(k_period).min().values

    k_percent = 100 * (close - low_roll) / (high_roll - low_roll)
    d_percent = SMA(pd.Series(k_percent), d_period).values

    return {"k": k_percent, "d": d_percent}


def Williams_R(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14
) -> np.ndarray:
    """
    Williams %R.

    Args:
        high: High prices array
        low: Low prices array
        close: Close prices array
        n: Period (default: 14)

    Returns:
        Williams %R values array
    """
    high_roll = pd.Series(high).rolling(n).max().values
    low_roll = pd.Series(low).rolling(n).min().values

    return -100 * (high_roll - close) / (high_roll - low_roll)


def crossover(series1: np.ndarray, series2: Union[np.ndarray, float]) -> np.ndarray:
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


def crossunder(series1: np.ndarray, series2: Union[np.ndarray, float]) -> np.ndarray:
    """
    Return True where series1 crosses under series2.

    Args:
        series1: First series
        series2: Second series or scalar value

    Returns:
        Boolean array indicating crossunder points
    """
    return crossover(series2, series1)


def resample_apply(
    rule: str, data: pd.DataFrame, apply_func: callable = None
) -> pd.DataFrame:
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
    data: pd.DataFrame, brick_size: float = None, percentage: bool = False
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
        self, condition: np.ndarray, stop_loss: float = None, take_profit: float = None
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
        self, condition: np.ndarray, stop_loss: float = None, take_profit: float = None
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
