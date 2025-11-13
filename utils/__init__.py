"""Utility functions for backtesting framework.

This module re-exports all indicators from utils.indicators for backward compatibility.
New code should import directly from utils.indicators.
"""

import warnings
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# Re-export all indicators from indicators.py for backward compatibility
from utils.indicators import (  # Core indicators; Momentum indicators; Trend indicators; Volume indicators; Oscillators; Bands; Utility functions
    ADX,
    ATR,
    CCI,
    CMF,
    EMA,
    MACD,
    MFI,
    OBV,
    RSI,
    SMA,
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

__all__ = [
    # Core indicators
    "SMA",
    "EMA",
    "WMA",
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
    # Strategy utilities
    "StrategyMixin",
    "COMMON_INDICATORS",
]
