# core/pine_adapter.py
"""Pine Script adapter functions for technical analysis.

Provides cross-compatibility functions that mimic TradingView Pine Script operations
using pandas Series operations.
"""

import pandas as pd


# Series refs
def ref(s: pd.Series, n: int) -> pd.Series:
    return s.shift(n)


# Crosses
def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    ap, bp = a.shift(1), b.shift(1)
    return (a > b) & (ap <= bp)


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    ap, bp = a.shift(1), b.shift(1)
    return (a < b) & (ap >= bp)


# Moving averages
def sma(s: pd.Series, length: int) -> pd.Series:
    return s.rolling(length, min_periods=length).mean()


def ema(s: pd.Series, length: int) -> pd.Series:
    return s.ewm(span=length, adjust=False, min_periods=length).mean()


# Donchian
def donchian(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    hi = df["high"].rolling(length, min_periods=length).max()
    lo = df["low"].rolling(length, min_periods=length).min()
    mid = (hi + lo) / 2.0
    return hi, lo, mid
