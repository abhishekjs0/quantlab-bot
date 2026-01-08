"""Utility functions for backtesting framework.

This module re-exports all indicators from utils.indicators for backward compatibility.
New code should import directly from utils.indicators.
"""

# Re-export all indicators from indicators.py for backward compatibility
from utils.indicators import (  # Core indicators; Momentum indicators; Trend indicators; Volume indicators; Oscillators; Bands; Utility functions
    ADX,
    ATR,
    CCI,
    CMF,
    DEMA,
    EMA,
    LSMA,
    MACD,
    MFI,
    OBV,
    RSI,
    SMA,
    TEMA,
    VWAP,
    VWMA,
    WMA,
    Aroon,
    BollingerBands,
    BullBearPower,
    ChandeOscillator,
    DonchianChannels,
    Envelope,
    HullMovingAverage,
    IchimokuKinkoHyo,
    KeltnerChannels,
    Momentum,
    ParabolicSAR,
    Stochastic,
    StochasticRSI,
    Supertrend,
    UltimateOscillator,
    WilliamsR,
    apply_indicators,
    crossover,
    crossunder,
    max_drawdown,
    percent_rank,
    renko_bars,
    resample_apply,
    rolling_window,
    sharpe_ratio,
    true_range,
    volatility_adjusted_returns,
)

# Backward compatibility aliases
donchian_channel = DonchianChannels
Williams_R = WilliamsR

__all__ = [
    # Core indicators
    "SMA",
    "EMA",
    "WMA",
    "DEMA",
    "TEMA",
    "LSMA",
    "HullMovingAverage",
    "RSI",
    "MACD",
    "Stochastic",
    "StochasticRSI",
    "Momentum",
    # Momentum indicators
    "ChandeOscillator",
    "UltimateOscillator",
    # Trend indicators
    "ATR",
    "ADX",
    "Aroon",
    "DonchianChannels",
    "Supertrend",
    "IchimokuKinkoHyo",
    # Volume indicators
    "VWAP",
    "MFI",
    "CMF",
    "OBV",
    "VWMA",
    # Oscillators
    "WilliamsR",
    "CCI",
    "BullBearPower",
    # Bands
    "BollingerBands",
    "Envelope",
    "KeltnerChannels",
    "ParabolicSAR",
    # Utility functions
    "crossover",
    "crossunder",
    "true_range",
    "max_drawdown",
    "percent_rank",
    "renko_bars",
    "resample_apply",
    "rolling_window",
    "sharpe_ratio",
    "volatility_adjusted_returns",
    "apply_indicators",
    # Backward compatibility aliases
    "donchian_channel",
    "Williams_R",
]
