"""Unified Technical Analysis Indicators - Single Source of Truth.

Consolidated collection of all 22+ technical indicators matching PineScript.
NO REDUNDANCIES - single source for all indicators.

Categories:
- Moving Averages: SMA, EMA, WMA, HMA
- Momentum: RSI, MACD, Stochastic, StochasticRSI, Momentum, ChandeOscillator, UltimateOscillator
- Trend: ATR, ADX, Aroon, DonchianChannels, Supertrend, Ichimoku
- Volume: VWAP, MFI, CMF, OBV, VWMA
- Oscillators: WilliamsR, CCI, BullBearPower
- Volatility/Bands: BollingerBands, Envelope, KeltnerChannels
- Special: ParabolicSAR, HullMovingAverage
"""

from typing import Optional, Union

import numpy as np
import pandas as pd


# Moving Averages
def SMA(series: Union[pd.Series, np.ndarray], n: int) -> np.ndarray:
    """Simple Moving Average."""
    if isinstance(series, np.ndarray):
        series = pd.Series(series)
    return series.rolling(window=n).mean().values


def EMA(values: np.ndarray, n: int, alpha: Optional[float] = None) -> np.ndarray:
    """Exponential Moving Average. Uses alpha=2/(n+1) or 1/n for Wilder's smoothing."""
    values = values.values if hasattr(values, "values") else values
    if alpha is None:
        alpha = 2.0 / (n + 1)

    result = np.empty_like(values, dtype=float)
    result[0] = values[0]

    for i in range(1, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]

    return result


def WMA(values: np.ndarray, n: int) -> np.ndarray:
    """Weighted Moving Average - linearly weighted."""
    weights = np.arange(1, n + 1, dtype=float)
    result = np.full_like(values, np.nan, dtype=float)

    for i in range(n - 1, len(values)):
        result[i] = np.dot(values[i - n + 1 : i + 1], weights) / weights.sum()

    return result


def HullMovingAverage(close: np.ndarray, period: int = 9) -> np.ndarray:
    """Hull Moving Average - low-lag moving average."""
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = WMA(close, half_period)
    wma_full = WMA(close, period)
    combined = 2 * wma_half - wma_full

    hma = WMA(combined, sqrt_period)
    return np.nan_to_num(hma, nan=0)


# Momentum Indicators
def RSI(series: Union[pd.Series, np.ndarray], n: int = 14) -> np.ndarray:
    """RSI with Wilder's smoothing matching TradingView. Range: 0-100."""
    if isinstance(series, pd.Series):
        values = series.values
    else:
        values = np.asarray(series)

    delta = np.diff(values, prepend=values[0])
    gain = np.where(delta > 0, delta, 0)
    loss = np.where(delta < 0, -delta, 0)

    avg_gain = EMA(gain, n, alpha=1.0 / n)
    avg_loss = EMA(loss, n, alpha=1.0 / n)

    # Suppress division warnings - we handle zero loss with np.where
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = np.where(avg_loss != 0, avg_gain / avg_loss, 0)
    rsi = 100 - (100 / (1 + rs))

    return np.nan_to_num(rsi, nan=50)


def MACD(values: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """MACD - returns dict with macd, signal, histogram."""
    ema_fast = EMA(values, fast)
    ema_slow = EMA(values, slow)
    macd_line = ema_fast - ema_slow
    signal_line = EMA(macd_line, signal)
    histogram = macd_line - signal_line

    return {"macd": macd_line, "signal": signal_line, "histogram": histogram}


def Stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period_k: int = 14,
    smooth_k: int = 1,
    period_d: int = 3,
) -> dict:
    """Stochastic Oscillator - returns k and d lines. Range: 0-100."""
    highest_high = pd.Series(high).rolling(window=period_k).max().values
    lowest_low = pd.Series(low).rolling(window=period_k).min().values

    range_val = highest_high - lowest_low
    stoch_raw = np.where(range_val != 0, ((close - lowest_low) / range_val) * 100, 50)

    k = SMA(stoch_raw, smooth_k)
    d = SMA(k, period_d)

    return {"k": k, "d": d}


def StochasticRSI(
    close: np.ndarray,
    rsi_length: int = 14,
    stoch_length: int = 14,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> dict:
    """Stochastic RSI - Stochastic applied to RSI values."""
    rsi_vals = RSI(close, rsi_length)

    rsi_series = pd.Series(rsi_vals)
    highest_rsi = rsi_series.rolling(window=stoch_length).max().values
    lowest_rsi = rsi_series.rolling(window=stoch_length).min().values

    range_val = highest_rsi - lowest_rsi
    stoch_vals = np.where(
        range_val != 0, ((rsi_vals - lowest_rsi) / range_val) * 100, 50
    )

    k = SMA(stoch_vals, k_smooth)
    d = SMA(k, d_smooth)

    return {"k": k, "d": d}


def Momentum(close: np.ndarray, period: int = 10) -> np.ndarray:
    """Momentum - price change over period."""
    momentum = np.diff(close, n=1, prepend=np.nan)
    momentum[period:] = close[period:] - close[:-period]
    return momentum


def ChandeOscillator(close: np.ndarray, period: int = 9) -> np.ndarray:
    """Chande Momentum Oscillator. Range: -100 to +100."""
    momentum = np.diff(close, prepend=close[0])

    positive_mom = np.where(momentum >= 0, momentum, 0)
    negative_mom = np.where(momentum < 0, -momentum, 0)

    sum_positive = pd.Series(positive_mom).rolling(period).sum().values
    sum_negative = pd.Series(negative_mom).rolling(period).sum().values

    total_sum = sum_positive + sum_negative
    cmo = np.where(total_sum != 0, 100 * (sum_positive - sum_negative) / total_sum, 0)

    return np.nan_to_num(cmo, nan=0)


def UltimateOscillator(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    fast_length: int = 7,
    middle_length: int = 14,
    slow_length: int = 28,
) -> np.ndarray:
    """Ultimate Oscillator - multi-timeframe momentum. Range: 0-100."""
    close = close.values if hasattr(close, "values") else close
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr = np.maximum(high, prev_close) - np.minimum(low, prev_close)
    bp = close - np.minimum(low, prev_close)

    bp_fast = pd.Series(bp).rolling(fast_length).sum().values
    tr_fast = pd.Series(tr).rolling(fast_length).sum().values
    avg_fast = np.where(tr_fast != 0, bp_fast / tr_fast, 0)

    bp_middle = pd.Series(bp).rolling(middle_length).sum().values
    tr_middle = pd.Series(tr).rolling(middle_length).sum().values
    avg_middle = np.where(tr_middle != 0, bp_middle / tr_middle, 0)

    bp_slow = pd.Series(bp).rolling(slow_length).sum().values
    tr_slow = pd.Series(tr).rolling(slow_length).sum().values
    avg_slow = np.where(tr_slow != 0, bp_slow / tr_slow, 0)

    uo = 100 * (4 * avg_fast + 2 * avg_middle + avg_slow) / 7

    return np.nan_to_num(uo, nan=50)


# Trend Indicators
def ATR(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    """Average True Range - volatility measurement."""
    close = close.values if hasattr(close, "values") else close
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    atr = EMA(tr, period, alpha=1.0 / period)
    return np.nan_to_num(atr, nan=0)


def ADX(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> dict:
    """ADX - Average Directional Index. Returns adx, di_plus, di_minus."""
    close = close.values if hasattr(close, "values") else close
    high = high.values if hasattr(high, "values") else high
    low = low.values if hasattr(low, "values") else low
    prev_close = np.concatenate(([close[0]], close[:-1]))
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    tr = np.maximum(np.maximum(tr1, tr2), tr3)

    prev_high = np.concatenate(([high[0]], high[:-1]))
    prev_low = np.concatenate(([low[0]], low[:-1]))

    plus_dm = np.where(
        (high - prev_high > prev_low - low) & (high - prev_high > 0),
        high - prev_high,
        0,
    )
    minus_dm = np.where(
        (prev_low - low > high - prev_high) & (prev_low - low > 0), prev_low - low, 0
    )

    tr_smooth = EMA(tr, period, alpha=1.0 / period)
    plus_dm_smooth = EMA(plus_dm, period, alpha=1.0 / period)
    minus_dm_smooth = EMA(minus_dm, period, alpha=1.0 / period)

    di_plus = 100 * plus_dm_smooth / np.where(tr_smooth != 0, tr_smooth, 1)
    di_minus = 100 * minus_dm_smooth / np.where(tr_smooth != 0, tr_smooth, 1)

    dx = (
        100
        * np.abs(di_plus - di_minus)
        / np.where(di_plus + di_minus != 0, di_plus + di_minus, 1)
    )
    adx = EMA(dx, period, alpha=1.0 / period)

    return {
        "adx": np.nan_to_num(adx, nan=0),
        "di_plus": np.nan_to_num(di_plus, nan=0),
        "di_minus": np.nan_to_num(di_minus, nan=0),
    }


def Aroon(high: np.ndarray, low: np.ndarray, period: int = 14) -> dict:
    """Aroon - trend timing indicator. Returns aroon_up, aroon_down, and aroon_oscillator."""
    aroon_up = np.zeros(len(high))
    aroon_down = np.zeros(len(low))

    for i in range(period, len(high)):
        highest_idx = np.argmax(high[i - period : i])
        bars_since_high = i - (i - period + highest_idx)

        lowest_idx = np.argmin(low[i - period : i])
        bars_since_low = i - (i - period + lowest_idx)

        aroon_up[i] = 100 * (period - bars_since_high) / period
        aroon_down[i] = 100 * (period - bars_since_low) / period

    aroon_oscillator = aroon_up - aroon_down

    return {
        "aroon_up": aroon_up,
        "aroon_down": aroon_down,
        "aroon_oscillator": aroon_oscillator,
    }


def DonchianChannels(high: np.ndarray, low: np.ndarray, period: int = 20) -> dict:
    """Donchian Channels - highest/lowest levels. Returns upper, lower, basis."""
    upper = pd.Series(high).rolling(window=period).max().values
    lower = pd.Series(low).rolling(window=period).min().values
    basis = (upper + lower) / 2.0

    return {"upper": upper, "lower": lower, "basis": basis}


def Supertrend(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr_period: int = 10,
    factor: float = 3.0,
) -> dict:
    """Supertrend - ATR-based trend indicator. Returns supertrend and direction."""
    atr_vals = ATR(high, low, close, atr_period)

    hl_avg = (high + low) / 2.0
    basic_ub = hl_avg + factor * atr_vals
    basic_lb = hl_avg - factor * atr_vals

    final_ub = np.zeros(len(close))
    final_lb = np.zeros(len(close))
    supertrend = np.zeros(len(close))
    direction = np.zeros(len(close))

    final_ub[0] = basic_ub[0]
    final_lb[0] = basic_lb[0]
    supertrend[0] = basic_ub[0]
    direction[0] = 1

    for i in range(1, len(close)):
        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i - 1]

        if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i - 1]

        if supertrend[i - 1] == final_ub[i - 1]:
            if close[i] <= final_ub[i]:
                supertrend[i] = final_ub[i]
                direction[i] = 1
            else:
                supertrend[i] = final_lb[i]
                direction[i] = -1
        else:
            if close[i] >= final_lb[i]:
                supertrend[i] = final_lb[i]
                direction[i] = -1
            else:
                supertrend[i] = final_ub[i]
                direction[i] = 1

    return {"supertrend": supertrend, "direction": direction}


def IchimokuKinkoHyo(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_span_b_period: int = 52,
) -> dict:
    """Ichimoku Cloud - returns all 5 components."""

    def donchian_middle(h, l, period):
        high_roll = pd.Series(h).rolling(period).max().values
        low_roll = pd.Series(l).rolling(period).min().values
        return (high_roll + low_roll) / 2

    tenkan_sen = donchian_middle(high, low, tenkan_period)
    kijun_sen = donchian_middle(high, low, kijun_period)

    senkou_span_a = (tenkan_sen + kijun_sen) / 2
    senkou_span_b = donchian_middle(high, low, senkou_span_b_period)
    chikou_span = np.roll(close, -kijun_period)

    return {
        "tenkan_sen": tenkan_sen,
        "kijun_sen": kijun_sen,
        "senkou_span_a": senkou_span_a,
        "senkou_span_b": senkou_span_b,
        "chikou_span": chikou_span,
    }


# Volume Indicators
def VWAP(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray
) -> np.ndarray:
    """Volume Weighted Average Price."""
    typical_price = (high + low + close) / 3
    cumulative_tpv = np.cumsum(typical_price * volume)
    cumulative_volume = np.cumsum(volume)

    return cumulative_tpv / cumulative_volume


def MFI(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Money Flow Index - volume-weighted RSI. Range: 0-100."""
    typical_price = (high + low + close) / 3
    raw_money_flow = typical_price * volume

    tp_diff = np.diff(typical_price, prepend=typical_price[0])

    positive_flow = np.where(tp_diff > 0, raw_money_flow, 0)
    positive_mf = pd.Series(positive_flow).rolling(period).sum().values

    negative_flow = np.where(tp_diff < 0, raw_money_flow, 0)
    negative_mf = pd.Series(negative_flow).rolling(period).sum().values

    money_flow_ratio = positive_mf / np.where(negative_mf != 0, negative_mf, 1)

    mfi = 100 - (100 / (1 + money_flow_ratio))

    return np.nan_to_num(mfi, nan=50)


def CMF(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """Chaikin Money Flow - volume-weighted price momentum."""
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low)
    money_flow_multiplier = np.nan_to_num(money_flow_multiplier)

    money_flow_volume = money_flow_multiplier * volume

    cmf = (
        pd.Series(money_flow_volume).rolling(period).sum()
        / pd.Series(volume).rolling(period).sum()
    ).values

    return np.nan_to_num(cmf, nan=0)


def OBV(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """On Balance Volume - cumulative volume indicator."""
    price_change = np.diff(close, prepend=close[0])
    sign = np.sign(price_change)
    obv = np.cumsum(sign * volume)

    return obv


def VWMA(close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
    """Volume Weighted Moving Average."""
    pv = close * volume
    vwma = pd.Series(pv).rolling(period).sum() / pd.Series(volume).rolling(period).sum()
    return vwma.values


# Oscillators
def WilliamsR(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14
) -> np.ndarray:
    """Williams %R - overbought/oversold. Range: -100 to 0."""
    highest_high = pd.Series(high).rolling(window=period).max().values
    lowest_low = pd.Series(low).rolling(window=period).min().values

    range_val = highest_high - lowest_low

    williams_r = np.where(
        range_val != 0, -100 * (highest_high - close) / range_val, -50
    )

    return np.nan_to_num(williams_r, nan=-50)


def CCI(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20
) -> np.ndarray:
    """Commodity Channel Index - deviation-based momentum."""
    tp = (high + low + close) / 3
    tp_series = pd.Series(tp)

    sma_tp = tp_series.rolling(period).mean()
    mad = tp_series.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())

    cci = (tp_series - sma_tp) / (0.015 * mad)

    return np.nan_to_num(cci.fillna(0).values, nan=0)


def BullBearPower(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, length: int = 13
) -> dict:
    """Bull Bear Power - buying vs selling pressure vs EMA."""
    ema_val = EMA(close, length)

    bull_power = high - ema_val
    bear_power = low - ema_val
    bbp = bull_power + bear_power

    return {"bull_power": bull_power, "bear_power": bear_power, "bbp": bbp}


# Volatility/Bands
def BollingerBands(values: np.ndarray, n: int = 20, std: float = 2) -> dict:
    """Bollinger Bands - SMA with std dev bands."""
    values_series = pd.Series(values)
    sma = SMA(values_series, n)
    rolling_std = values_series.rolling(n).std().values

    upper = sma + (rolling_std * std)
    lower = sma - (rolling_std * std)

    return {"upper": upper, "middle": sma, "lower": lower}


def Envelope(
    close: np.ndarray, period: int = 20, percent: float = 10.0, use_ema: bool = False
) -> dict:
    """Envelope - MA with percentage bands."""
    if use_ema:
        basis = EMA(close, period)
    else:
        basis = SMA(pd.Series(close), period)

    basis = np.asarray(basis, dtype=np.float64)
    k = percent / 100.0
    upper = basis * (1.0 + k)
    lower = basis * (1.0 - k)

    return {"basis": basis, "upper": upper, "lower": lower}


def KeltnerChannels(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 20,
    multiplier: float = 2.0,
) -> dict:
    """Keltner Channels - EMA with ATR bands."""
    ema = EMA(close, period)
    atr = ATR(high, low, close, period)

    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)

    return {"upper": upper, "middle": ema, "lower": lower}


# Special/Advanced
def ParabolicSAR(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    start: float = 0.02,
    increment: float = 0.02,
    maximum: float = 0.2,
) -> np.ndarray:
    """Parabolic SAR - Stop and Reversal indicator."""
    sar = np.zeros_like(high)
    trend = np.ones_like(high)
    af = start
    ep = high[0]

    sar[0] = low[0]

    for i in range(1, len(high)):
        if trend[i - 1] == 1:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if high[i] > ep:
                ep = high[i]
                af = min(af + increment, maximum)

            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = start
            else:
                trend[i] = 1

        else:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if low[i] < ep:
                ep = low[i]
                af = min(af + increment, maximum)

            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = start
            else:
                trend[i] = -1

    return sar


# Utilities
def crossover(series1: np.ndarray, series2) -> np.ndarray:
    """Return True where series1 crosses over series2."""
    series1 = np.asarray(series1)
    series2 = np.asarray(series2)

    if series2.ndim == 0:
        return (series1[:-1] <= series2) & (series1[1:] > series2)
    else:
        return (series1[:-1] <= series2[:-1]) & (series1[1:] > series2[1:])


def crossunder(series1: np.ndarray, series2) -> np.ndarray:
    """Return True where series1 crosses under series2."""
    return crossover(series2, series1)


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Calculate True Range for ATR calculations."""
    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))

    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]

    return tr


# Utility Functions (Performance & Support)


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


def extract_ichimoku_base_line(
    high: np.ndarray, low: np.ndarray, period: int = 26
) -> np.ndarray:
    """
    Extract Ichimoku Base Line (Kijun-sen).

    Args:
        high: High prices
        low: Low prices
        period: Period (default: 26)

    Returns:
        Ichimoku Base Line values
    """
    high_series = pd.Series(high)
    low_series = pd.Series(low)

    highest_high = high_series.rolling(period).max()
    lowest_low = low_series.rolling(period).min()

    base_line = (highest_high + lowest_low) / 2

    return base_line.values


def calculate_stochastic_slow(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int = 5,
    d_period: int = 3,
    smooth_k: int = 3,
) -> dict:
    """
    Calculate Stochastic Slow oscillator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        k_period: %K period (default: 5)
        d_period: %D period (default: 3)
        smooth_k: %K smoothing (default: 3)

    Returns:
        Dictionary with slow_k and slow_d values
    """
    # Calculate Fast %K (raw stochastic)
    high_series = pd.Series(high)
    low_series = pd.Series(low)
    close_series = pd.Series(close)

    lowest_low = low_series.rolling(k_period).min()
    highest_high = high_series.rolling(k_period).max()

    fast_k = 100 * (close_series - lowest_low) / (highest_high - lowest_low)

    # Slow %K is SMA of Fast %K
    slow_k = fast_k.rolling(smooth_k).mean()

    # Slow %D is SMA of Slow %K
    slow_d = slow_k.rolling(d_period).mean()

    return {"slow_k": slow_k.fillna(50).values, "slow_d": slow_d.fillna(50).values}


def HMA(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Hull Moving Average - provides reduced lag compared to traditional MAs.

    Args:
        close: Close prices
        period: Period (default: 14)

    Returns:
        HMA values
    """
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))

    wma_half = WMA(close, half_period)
    wma_full = WMA(close, period)

    raw_hma = 2 * wma_half - wma_full
    hma = WMA(raw_hma, sqrt_period)

    return hma


def MomentumOscillator(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Momentum Oscillator - rate of change indicator.

    Args:
        close: Close prices
        period: Period (default: 14)

    Returns:
        Momentum values
    """
    momentum = close - np.roll(close, period)
    momentum[:period] = 0  # Set initial values to 0
    return momentum


def TrendClassification(aroon_up: float, aroon_down: float, period: int = 25) -> str:
    """
    Classify trend using Aroon indicator with period-adaptive thresholds.
    
    Longer periods need more relaxed thresholds (slower to change classification).
    Shorter periods use stricter thresholds (quicker to identify trends).

    Args:
        aroon_up: Aroon Up value (0-100)
        aroon_down: Aroon Down value (0-100)
        period: Aroon period length (default: 25)

    Returns:
        Trend classification: "Bull", "Bear", or "Sideways"
    """
    # Period-adaptive thresholds
    if period <= 25:
        # Short-term: Strict thresholds (quick reaction)
        bull_threshold = 70
        bear_threshold = 70
        neutral_gap = 30
    elif period <= 50:
        # Medium-term: Moderate thresholds
        bull_threshold = 65
        bear_threshold = 65
        neutral_gap = 25
    else:
        # Long-term: Relaxed thresholds (slow to classify)
        bull_threshold = 60
        bear_threshold = 60
        neutral_gap = 20
    
    # Bull: Aroon Up dominates
    if aroon_up > bull_threshold and aroon_down < neutral_gap:
        return "Bull"
    
    # Bear: Aroon Down dominates
    elif aroon_down > bear_threshold and aroon_up < neutral_gap:
        return "Bear"
    
    # Sideways: Neither dominates clearly
    else:
        return "Sideways"


def VolatilityClassification(atr_pct: float, period: int = 14) -> str:
    """
    Classify volatility using ATR percentage with period-adaptive thresholds.
    
    Calibrated for Indian market volatility (higher than US markets).
    Longer periods show smoother/lower ATR, so need lower thresholds.

    Args:
        atr_pct: ATR as percentage of price
        period: ATR period length (default: 14)

    Returns:
        Volatility classification: "Low", "Med", or "High"
    """
    # Period-adaptive thresholds
    if period <= 14:
        # Short-term ATR: Higher thresholds
        low_threshold = 2.5    # Increased from 1.5 for Indian markets
        high_threshold = 4.5   # Increased from 3.0
    elif period <= 21:
        # Medium-term ATR
        low_threshold = 2.2
        high_threshold = 4.0
    else:
        # Long-term ATR: Lower thresholds (smoother values)
        low_threshold = 2.0
        high_threshold = 3.5
    
    if atr_pct < low_threshold:
        return "Low"
    elif atr_pct < high_threshold:
        return "Med"
    else:
        return "High"


def kaufman_efficiency_ratio(close: np.ndarray, length: int) -> np.ndarray:
    """
    Kaufman Efficiency Ratio (KER) - measures trend strength vs noise.

    Identifies whether price is in a trending state (high KER) or noisy (low KER).

    Formula per Kaufman (as attached):
        ER = |Close[t] - Close[t-n]| / Σ|Close[i] - Close[i-1]|  for i = t-n+1 to t
    
    Where:
        - Direction (numerator): absolute price change over n periods
        - Volatility (denominator): sum of all bar-to-bar absolute changes over n periods
        - ER range: 0 to 1 (1=perfect trending, 0=choppy/noisy)

    Args:
        close: Close prices array
        length: Lookback period (commonly 10). Uses exactly `length` bars of history.

    Returns:
        KER array (range 0.0 to 1.0). 
        - Values < 0.3: High noise (mean-reverting)
        - Values > 0.7: Low noise (trending)

    Returns NaN for first `length` bars (insufficient data).
    """
    close = np.asarray(close, dtype=float)
    n = len(close)
    ker = np.full(n, np.nan, dtype=float)

    for i in range(length, n):
        # Direction: absolute change from length bars ago to current
        # Window: [i-length, i] = exactly length+1 points, length bars of change
        direction = abs(close[i] - close[i - length])

        # Volatility (noise): sum of ALL bar-to-bar absolute changes in window
        # Sum from bar i-length+1 to bar i (exactly length changes)
        volatility = 0.0
        for j in range(i - length + 1, i + 1):
            volatility += abs(close[j] - close[j - 1])

        # Calculate KER
        if volatility > 0:
            ker[i] = direction / volatility
        else:
            ker[i] = 0.0

    return ker
