import pandas as pd


def ref(s: pd.Series, n: int) -> pd.Series:
    return s.shift(n)


def crossover(a: pd.Series, b: pd.Series) -> pd.Series:
    ap, bp = a.shift(1), b.shift(1)
    return (a > b) & (ap <= bp)


def crossunder(a: pd.Series, b: pd.Series) -> pd.Series:
    ap, bp = a.shift(1), b.shift(1)
    return (a < b) & (ap >= bp)


def donchian(df: pd.DataFrame, length: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    hi = df["high"].rolling(length, min_periods=length).max()
    lo = df["low"].rolling(length, min_periods=length).min()
    mid = (hi + lo) / 2.0
    return hi, lo, mid
