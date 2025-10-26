# viz/tv_plot.py

import mplfinance as mpf
import numpy as np
import pandas as pd


def _donchian(df: pd.DataFrame, length: int, min_periods: int | None = None):
    mp = length if (min_periods is None) else int(min_periods)
    hi = df["high"].rolling(length, min_periods=mp).max()
    lo = df["low"].rolling(length, min_periods=mp).min()
    mid = (hi + lo) / 2.0
    return hi, lo, mid


def plot_tv_donchian(
    df: pd.DataFrame,
    trades_df: pd.DataFrame | None,
    length: int = 20,
    months: int | None = 12,
    title: str = "Donchian - TV style",
):
    # 1) Optional window
    if months is not None:
        end = df.index.max()
        start = end - pd.DateOffset(months=months)
        df = df.loc[start:end]
        if trades_df is not None and len(trades_df):
            trades_df = trades_df[
                (trades_df["entry_time"] >= df.index.min())
                | (trades_df["exit_time"].fillna(pd.Timestamp.min) >= df.index.min())
            ]

    # If nothing to plot, bail gracefully
    if df.empty:
        print("[plot_tv_donchian] Empty window after slicing; nothing to plot.")
        return

    # 2) Donchian with safe min_periods
    mp_safe = length if len(df) >= length else max(1, len(df) // 2)
    up, lo, mid = _donchian(df, length, min_periods=mp_safe)

    # 3) Entry/exit markers
    entry_y = pd.Series(np.nan, index=df.index)
    exit_y = pd.Series(np.nan, index=df.index)
    if trades_df is not None and len(trades_df):
        for _, tr in trades_df.iterrows():
            et = tr["entry_time"]
            xt = tr.get("exit_time", pd.NaT)
            if et in df.index:
                entry_y.loc[et] = df.loc[et, "low"] * 0.995
            if pd.notna(xt) and xt in df.index:
                exit_y.loc[xt] = df.loc[xt, "high"] * 1.005

    # 4) Build overlays only if they have finite data
    apds = []
    if np.isfinite(up.values).any():
        apds.append(mpf.make_addplot(up, color="#2F5EFF", width=1.2))
    if np.isfinite(lo.values).any():
        apds.append(mpf.make_addplot(lo, color="#2F5EFF", width=1.2))
    if np.isfinite(mid.values).any():
        apds.append(mpf.make_addplot(mid, color="#F39C12", width=1.2))
    if np.isfinite(entry_y.values).any():
        apds.append(
            mpf.make_addplot(
                entry_y, type="scatter", marker="^", markersize=120, color="#009944"
            )
        )
    if np.isfinite(exit_y.values).any():
        apds.append(
            mpf.make_addplot(
                exit_y, type="scatter", marker="v", markersize=120, color="#D81B60"
            )
        )

    # 5) Fill between band edges only if valid
    valid = np.isfinite(lo.values) & np.isfinite(up.values)
    fb = None
    if valid.any():
        fb = {
            "y1": lo.values,
            "y2": up.values,
            "where": valid,
            "alpha": 0.15,
            "color": "#2F5EFF",
        }

    # 6) Plot
    mpf.plot(
        df[["open", "high", "low", "close"]],
        type="candle",
        addplot=apds if apds else None,
        fill_between=fb,
        style="yahoo",
        title=title,
        tight_layout=True,
        volume=False,
        warn_too_much_data=len(df) + 1,
    )
