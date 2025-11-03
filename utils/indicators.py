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


def VWMA(close: np.ndarray, volume: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Volume Weighted Moving Average.
    
    Args:
        close: Close prices
        volume: Volume data
        period: Period (default: 14)
    
    Returns:
        VWMA values
    """
    pv = close * volume
    vwma = pd.Series(pv).rolling(period).sum() / pd.Series(volume).rolling(period).sum()
    return vwma.values


def HMA(close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Hull Moving Average - provides reduced lag compared to traditional MAs.
    
    Args:
        close: Close prices
        period: Period (default: 14)
    
    Returns:
        HMA values
    """
    from . import WMA
    
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    
    wma_half = WMA(close, half_period)
    wma_full = WMA(close, period)
    
    raw_hma = 2 * wma_half - wma_full
    hma = WMA(raw_hma, sqrt_period)
    
    return hma


def WilliamsR(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Williams %R - momentum indicator measuring overbought/oversold levels.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Period (default: 14)
    
    Returns:
        Williams %R values (range: -100 to 0)
    """
    highest_high = pd.Series(high).rolling(period).max().values
    lowest_low = pd.Series(low).rolling(period).min().values
    
    williams_r = -100 * (highest_high - close) / (highest_high - lowest_low)
    williams_r = np.nan_to_num(williams_r, nan=-50.0)
    
    return williams_r


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


def UltimateOscillator(
    high: np.ndarray, 
    low: np.ndarray, 
    close: np.ndarray,
    period1: int = 7,
    period2: int = 14,
    period3: int = 28
) -> np.ndarray:
    """
    Ultimate Oscillator - combines short, intermediate, and long-term market momentum.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period1: Short period (default: 7)
        period2: Intermediate period (default: 14)
        period3: Long period (default: 28)
    
    Returns:
        Ultimate Oscillator values (range: 0 to 100)
    """
    # Buying pressure
    bp = close - np.minimum(low, np.roll(close, 1))
    bp[0] = 0
    
    # True range
    tr = np.maximum(high, np.roll(close, 1)) - np.minimum(low, np.roll(close, 1))
    tr[0] = high[0] - low[0]
    
    # Calculate averages for each period
    avg1 = pd.Series(bp).rolling(period1).sum() / pd.Series(tr).rolling(period1).sum()
    avg2 = pd.Series(bp).rolling(period2).sum() / pd.Series(tr).rolling(period2).sum()
    avg3 = pd.Series(bp).rolling(period3).sum() / pd.Series(tr).rolling(period3).sum()
    
    # Ultimate Oscillator formula
    uo = 100 * ((4 * avg1 + 2 * avg2 + avg3) / (4 + 2 + 1))
    
    return uo.values


def BullBearPower(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 13) -> dict:
    """
    Bull and Bear Power - measures buying and selling pressure.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: EMA period (default: 13)
    
    Returns:
        Dictionary with bull_power, bear_power, and combined power
    """
    from . import EMA
    
    ema = EMA(close, period)
    
    bull_power = high - ema
    bear_power = low - ema
    
    return {
        "bull_power": bull_power,
        "bear_power": bear_power,
        "total_power": bull_power + bear_power
    }


def StochasticRSI(rsi: np.ndarray, period: int = 14) -> dict:
    """
    Stochastic RSI - applies Stochastic calculation to RSI values.
    
    Args:
        rsi: RSI values
        period: Period (default: 14)
    
    Returns:
        Dictionary with fast_k and fast_d values
    """
    rsi_series = pd.Series(rsi)
    
    lowest_rsi = rsi_series.rolling(period).min()
    highest_rsi = rsi_series.rolling(period).max()
    
    # Fast %K
    fast_k = 100 * (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
    fast_k = fast_k.fillna(50).values
    
    # Fast %D (3-period SMA of Fast %K)
    fast_d = pd.Series(fast_k).rolling(3).mean().fillna(50).values
    
    return {
        "fast_k": fast_k,
        "fast_d": fast_d
    }


def Aroon(high: np.ndarray, low: np.ndarray, period: int = 25) -> dict:
    """
    Aroon Indicator - identifies trend changes and strength.
    
    Args:
        high: High prices
        low: Low prices
        period: Period (default: 25)
    
    Returns:
        Dictionary with aroon_up, aroon_down, and aroon_oscillator
    """
    aroon_up = np.zeros_like(high)
    aroon_down = np.zeros_like(low)
    
    for i in range(period, len(high)):
        # Days since highest high
        high_window = high[i-period+1:i+1]
        days_since_high = period - 1 - np.argmax(high_window)
        aroon_up[i] = ((period - days_since_high) / period) * 100
        
        # Days since lowest low
        low_window = low[i-period+1:i+1]
        days_since_low = period - 1 - np.argmin(low_window)
        aroon_down[i] = ((period - days_since_low) / period) * 100
    
    aroon_oscillator = aroon_up - aroon_down
    
    return {
        "aroon_up": aroon_up,
        "aroon_down": aroon_down,
        "aroon_oscillator": aroon_oscillator
    }


def TrendClassification(aroon_up: float, aroon_down: float) -> str:
    """
    Classify trend using Aroon indicator values.
    
    Args:
        aroon_up: Aroon Up value
        aroon_down: Aroon Down value
    
    Returns:
        Trend classification: "Bull", "Bear", or "Sideways"
    """
    if aroon_up > 70 and aroon_down < 30:
        return "Bull"
    elif aroon_down > 70 and aroon_up < 30:
        return "Bear"
    else:
        return "Sideways"


def VolatilityClassification(atr_pct: float) -> str:
    """
    Classify volatility using ATR percentage.
    
    Args:
        atr_pct: ATR as percentage of price
    
    Returns:
        Volatility classification: "Low", "Med", or "High"
    """
    if atr_pct < 1.5:
        return "Low"
    elif atr_pct < 3.0:
        return "Med"
    else:
        return "High"


def calculate_max_favorable_excursion(
    df: pd.DataFrame,
    entry_time,
    exit_time,
    entry_price: float,
    qty: float
) -> tuple:
    """
    Calculate Maximum Favorable Excursion (MFE) for a trade.
    
    Args:
        df: DataFrame with OHLC data
        entry_time: Trade entry timestamp
        exit_time: Trade exit timestamp  
        entry_price: Entry price
        qty: Position quantity
    
    Returns:
        Tuple of (mfe_value, mfe_pct)
    """
    try:
        price_series = df.loc[entry_time:exit_time]["high"].astype(float)
        pnl_series = (price_series - entry_price) * qty
        
        if not pnl_series.empty:
            mfe = float(pnl_series.max())
            mfe_pct = (mfe / (abs(entry_price * qty))) * 100 if entry_price * qty != 0 else 0
            return mfe, mfe_pct
    except Exception:
        pass
    
    return 0.0, 0.0


def calculate_multiple_emas(close: pd.Series, periods: list[int]) -> dict:
    """
    Calculate multiple EMAs at once.
    
    Args:
        close: Close prices
        periods: List of EMA periods to calculate
    
    Returns:
        Dictionary with EMA values for each period
    """
    from . import EMA
    
    result = {}
    for period in periods:
        if period > 0:
            result[f"ema_{period}"] = EMA(close.values, period)
        else:
            result[f"ema_{period}"] = close.values  # EMA_0 = close price
    
    return result


def calculate_multiple_smas(close: pd.Series, periods: list[int]) -> dict:
    """
    Calculate multiple SMAs at once.
    
    Args:
        close: Close prices
        periods: List of SMA periods to calculate
    
    Returns:
        Dictionary with SMA values for each period
    """
    from . import SMA
    
    result = {}
    for period in periods:
        if period > 0:
            result[f"sma_{period}"] = SMA(close, period).values
        else:
            result[f"sma_{period}"] = close.values  # SMA_0 = close price
    
    return result


def extract_ichimoku_base_line(high: np.ndarray, low: np.ndarray, period: int = 26) -> np.ndarray:
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
    smooth_k: int = 3
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
    
    return {
        "slow_k": slow_k.fillna(50).values,
        "slow_d": slow_d.fillna(50).values
    }


def CCI(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 20) -> np.ndarray:
    """
    Commodity Channel Index (CCI) - momentum indicator.
    
    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: Period (default: 20)
    
    Returns:
        CCI values
    """
    # Typical Price
    tp = (high + low + close) / 3
    tp_series = pd.Series(tp)
    
    # SMA of Typical Price
    sma_tp = tp_series.rolling(period).mean()
    
    # Mean Deviation
    mad = tp_series.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
    
    # CCI calculation
    cci = (tp_series - sma_tp) / (0.015 * mad)
    
    return cci.fillna(0).values
