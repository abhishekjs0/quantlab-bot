"""
Additional technical analysis indicators specifically for Indian equity markets.

Provides advanced indicators and market-specific calculations commonly used
in Indian stock market analysis.
"""

import numpy as np
import pandas as pd


def VWAP(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray
) -> np.ndarray:
    """
    Volume Weighted Average Price.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        volume: Volume data

    Returns:
        VWAP values
    """
    typical_price = (high + low + close) / 3
    cumulative_tpv = np.cumsum(typical_price * volume)
    cumulative_volume = np.cumsum(volume)

    return cumulative_tpv / cumulative_volume


def SuperTrend(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> dict:
    """
    SuperTrend indicator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period (default: 10)
        multiplier: ATR multiplier (default: 3.0)

    Returns:
        Dictionary with 'supertrend' values and 'trend' direction
    """
    from . import ATR

    hl2 = (high + low) / 2
    atr = ATR(high, low, close, period)

    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)

    # Initialize arrays
    final_upper = np.zeros_like(close)
    final_lower = np.zeros_like(close)
    supertrend = np.zeros_like(close)
    trend = np.ones_like(close)  # 1 for uptrend, -1 for downtrend

    for i in range(len(close)):
        if i == 0:
            final_upper[i] = upper_band[i]
            final_lower[i] = lower_band[i]
            supertrend[i] = close[i]
            continue

        # Calculate final bands
        final_upper[i] = (
            upper_band[i]
            if upper_band[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]
            else final_upper[i - 1]
        )
        final_lower[i] = (
            lower_band[i]
            if lower_band[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]
            else final_lower[i - 1]
        )

        # Determine trend
        if close[i] <= final_lower[i]:
            trend[i] = -1
        elif close[i] >= final_upper[i]:
            trend[i] = 1
        else:
            trend[i] = trend[i - 1]

        # Calculate SuperTrend
        supertrend[i] = final_lower[i] if trend[i] == 1 else final_upper[i]

    return {"supertrend": supertrend, "trend": trend}


def IchimokuKinkoHyo(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_span_b_period: int = 52,
) -> dict:
    """
    Ichimoku Kinko Hyo (Cloud) indicator.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        tenkan_period: Tenkan-sen period (default: 9)
        kijun_period: Kijun-sen period (default: 26)
        senkou_span_b_period: Senkou Span B period (default: 52)

    Returns:
        Dictionary with all Ichimoku components
    """

    def donchian_middle(h, l, period):
        high_roll = pd.Series(h).rolling(period).max().values
        low_roll = pd.Series(l).rolling(period).min().values
        return (high_roll + low_roll) / 2

    tenkan_sen = donchian_middle(high, low, tenkan_period)
    kijun_sen = donchian_middle(high, low, kijun_period)

    # Senkou Span A (Leading Span A)
    senkou_span_a = (tenkan_sen + kijun_sen) / 2

    # Senkou Span B (Leading Span B)
    senkou_span_b = donchian_middle(high, low, senkou_span_b_period)

    # Chikou Span (Lagging Span) - close displaced backwards
    chikou_span = np.roll(close, -kijun_period)

    return {
        "tenkan_sen": tenkan_sen,
        "kijun_sen": kijun_sen,
        "senkou_span_a": senkou_span_a,
        "senkou_span_b": senkou_span_b,
        "chikou_span": chikou_span,
    }


def ParabolicSAR(
    high: np.ndarray, low: np.ndarray, acceleration: float = 0.02, maximum: float = 0.2
) -> np.ndarray:
    """
    Parabolic SAR indicator.

    Args:
        high: High prices
        low: Low prices
        acceleration: Acceleration factor (default: 0.02)
        maximum: Maximum acceleration (default: 0.2)

    Returns:
        Parabolic SAR values
    """
    sar = np.zeros_like(high)
    trend = np.ones_like(high)  # 1 for uptrend, -1 for downtrend
    af = acceleration
    ep = high[0]  # Extreme point

    sar[0] = low[0]

    for i in range(1, len(high)):
        if trend[i - 1] == 1:  # Uptrend
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if high[i] > ep:
                ep = high[i]
                af = min(af + acceleration, maximum)

            if low[i] < sar[i]:
                trend[i] = -1
                sar[i] = ep
                ep = low[i]
                af = acceleration
            else:
                trend[i] = 1

        else:  # Downtrend
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])

            if low[i] < ep:
                ep = low[i]
                af = min(af + acceleration, maximum)

            if high[i] > sar[i]:
                trend[i] = 1
                sar[i] = ep
                ep = high[i]
                af = acceleration
            else:
                trend[i] = -1

    return sar


def KeltnerChannels(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 20,
    multiplier: float = 2.0,
) -> dict:
    """
    Keltner Channels.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: EMA period (default: 20)
        multiplier: ATR multiplier (default: 2.0)

    Returns:
        Dictionary with upper, middle, and lower channels
    """
    from . import ATR, EMA

    ema = EMA(close, period)
    atr = ATR(high, low, close, period)

    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)

    return {"upper": upper, "middle": ema, "lower": lower}


def CCI(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20
) -> np.ndarray:
    """
    Commodity Channel Index.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Period (default: 20)

    Returns:
        CCI values
    """
    typical_price = (high + low + close) / 3
    sma_tp = pd.Series(typical_price).rolling(period).mean().values

    mean_deviation = np.zeros_like(typical_price)
    for i in range(period - 1, len(typical_price)):
        window = typical_price[i - period + 1 : i + 1]
        mean_deviation[i] = np.mean(np.abs(window - sma_tp[i]))

    cci = (typical_price - sma_tp) / (0.015 * mean_deviation)
    return cci


def CMF(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """
    Chaikin Money Flow.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        volume: Volume data
        period: Period (default: 20)

    Returns:
        CMF values
    """
    money_flow_multiplier = ((close - low) - (high - close)) / (high - low)
    money_flow_multiplier = np.nan_to_num(money_flow_multiplier)

    money_flow_volume = money_flow_multiplier * volume

    cmf = (
        pd.Series(money_flow_volume).rolling(period).sum()
        / pd.Series(volume).rolling(period).sum()
    ).values

    return cmf


def ADX(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> dict:
    """
    Average Directional Index.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Period (default: 14)

    Returns:
        Dictionary with ADX, +DI, and -DI values
    """
    from . import ATR

    # Calculate True Range and Directional Movement
    tr = ATR(high, low, close, 1)  # True Range for single period

    dm_plus = np.where(
        (high[1:] - high[:-1]) > (low[:-1] - low[1:]),
        np.maximum(high[1:] - high[:-1], 0),
        0,
    )
    dm_minus = np.where(
        (low[:-1] - low[1:]) > (high[1:] - high[:-1]),
        np.maximum(low[:-1] - low[1:], 0),
        0,
    )

    # Pad arrays to match original length
    dm_plus = np.concatenate([[0], dm_plus])
    dm_minus = np.concatenate([[0], dm_minus])

    # Smooth the values
    tr_smooth = pd.Series(tr).rolling(period).mean().values
    dm_plus_smooth = pd.Series(dm_plus).rolling(period).mean().values
    dm_minus_smooth = pd.Series(dm_minus).rolling(period).mean().values

    # Calculate Directional Indicators
    di_plus = 100 * dm_plus_smooth / tr_smooth
    di_minus = 100 * dm_minus_smooth / tr_smooth

    # Calculate ADX
    dx = 100 * np.abs(di_plus - di_minus) / (di_plus + di_minus)
    dx = np.nan_to_num(dx)
    adx = pd.Series(dx).rolling(period).mean().values

    return {"adx": adx, "di_plus": di_plus, "di_minus": di_minus}


def OBV(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """
    On-Balance Volume.

    Args:
        close: Close prices
        volume: Volume data

    Returns:
        OBV values
    """
    obv = np.zeros_like(volume, dtype=float)
    obv[0] = volume[0]

    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]

    return obv


def PivotPoints(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict:
    """
    Calculate pivot points and support/resistance levels.

    Args:
        high: High prices
        low: Low prices
        close: Close prices

    Returns:
        Dictionary with pivot point and S/R levels
    """
    # Use previous day's HLC for calculation
    prev_high = np.roll(high, 1)
    prev_low = np.roll(low, 1)
    prev_close = np.roll(close, 1)

    # Pivot Point
    pivot = (prev_high + prev_low + prev_close) / 3

    # Support and Resistance levels
    r1 = 2 * pivot - prev_low
    s1 = 2 * pivot - prev_high
    r2 = pivot + (prev_high - prev_low)
    s2 = pivot - (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)

    return {"pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


def FibonacciRetracements(high_price: float, low_price: float) -> dict:
    """
    Calculate Fibonacci retracement levels.

    Args:
        high_price: Swing high price
        low_price: Swing low price

    Returns:
        Dictionary with Fibonacci levels
    """
    diff = high_price - low_price

    levels = {
        "0%": high_price,
        "23.6%": high_price - 0.236 * diff,
        "38.2%": high_price - 0.382 * diff,
        "50%": high_price - 0.50 * diff,
        "61.8%": high_price - 0.618 * diff,
        "78.6%": high_price - 0.786 * diff,
        "100%": low_price,
    }

    return levels


# Indian market specific indicators
def NSEAdvanceDecline(advances: int, declines: int, unchanged: int = 0) -> dict:
    """
    Calculate NSE advance-decline indicators.

    Args:
        advances: Number of advancing stocks
        declines: Number of declining stocks
        unchanged: Number of unchanged stocks

    Returns:
        Dictionary with A/D ratio and breadth indicators
    """
    total = advances + declines + unchanged
    ad_ratio = advances / declines if declines > 0 else float("inf")
    breadth = (advances - declines) / total if total > 0 else 0

    return {
        "ad_ratio": ad_ratio,
        "breadth": breadth,
        "net_advances": advances - declines,
    }


def NIFTYPutCallRatio(put_oi: float, call_oi: float) -> float:
    """
    Calculate NIFTY Put-Call Ratio from options data.

    Args:
        put_oi: Put option open interest
        call_oi: Call option open interest

    Returns:
        Put-Call ratio
    """
    return put_oi / call_oi if call_oi > 0 else 0


def VIXAnalysis(vix_value: float) -> str:
    """
    Analyze VIX levels for market sentiment.

    Args:
        vix_value: Current VIX value

    Returns:
        Market sentiment string
    """
    if vix_value < 15:
        return "Low volatility - Complacent market"
    elif vix_value < 20:
        return "Normal volatility - Stable market"
    elif vix_value < 30:
        return "Elevated volatility - Cautious market"
    elif vix_value < 40:
        return "High volatility - Fearful market"
    else:
        return "Extreme volatility - Panic conditions"
