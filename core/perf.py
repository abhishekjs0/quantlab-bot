"""Performance analytics and metrics computation for backtesting results."""

# core/perf.py
from math import inf, sqrt

import numpy as np
import pandas as pd


# ---------- Core performance ----------
def _ann_factor(freq: str) -> int:
    f = str(freq).upper()
    return (
        252
        if f.startswith("D")
        else 52 if f.startswith("W") else 12 if f.startswith("M") else 252
    )


def _drawdown_stats(eq: pd.Series) -> tuple:
    cummax = eq.cummax()
    dd = eq / cummax - 1.0
    maxdd = float(dd.min())
    return dd, maxdd


def _trade_durations(trades: pd.DataFrame) -> pd.Series:
    if trades is None or trades.empty:
        return pd.Series(dtype=float)
    dur = (
        pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])
    ).dt.total_seconds() / 86400.0
    return dur.dropna()


def compute_perf(
    equity_df: pd.DataFrame, trades_df: pd.DataFrame, freq: str = "D"
) -> dict:
    """
    equity_df: expects 'equity' column; optional 'qty'
    trades_df: expects entry/exit and net_pnl
    """
    out = {}
    eq = equity_df["equity"].astype(float)
    ann = _ann_factor(freq)

    # Returns
    r = eq.pct_change().fillna(0.0)
    mu, sigma = r.mean(), r.std(ddof=0)
    sharpe = (mu / sigma * sqrt(ann)) if sigma > 0 else 0.0

    # Sortino
    dn = r[r < 0.0]
    dn_sigma = dn.std(ddof=0)
    sortino = (mu / dn_sigma * sqrt(ann)) if dn_sigma > 0 else 0.0

    # Drawdowns
    dd, maxdd = _drawdown_stats(eq)

    # CAGR-like (geometric start->end) - use actual date range when possible
    start, end = float(eq.iloc[0]), float(eq.iloc[-1])
    n_years = None
    try:
        idx = equity_df.index
        if hasattr(idx, "dtype") and "datetime" in str(idx.dtype).lower():
            days = (pd.to_datetime(idx[-1]) - pd.to_datetime(idx[0])).days
            n_years = max(days / 365.25, 1 / 365.25)
    except Exception:
        n_years = None
    if n_years is None:
        n_years = max(len(eq) / ann, 1e-9)
    cagr_like = (end / start) ** (1.0 / n_years) - 1.0 if start > 0 else 0.0

    # Calmar
    calmar = (cagr_like / abs(maxdd)) if maxdd < 0 else inf

    # Exposure
    exposure = (
        float((equity_df["qty"] > 0).mean()) if "qty" in equity_df.columns else np.nan
    )

    # Trade stats (basic)
    if trades_df is None or trades_df.empty:
        pf = winrate = avgtrade = 0.0
        num = 0
        dur = pd.Series(dtype=float)
        avg_profit_per_trade_frac = 0.0
        avg_bars = float("nan")
    else:
        pnl = trades_df["net_pnl"].astype(float)
        gross_win = pnl[pnl > 0].sum()
        gross_loss = -pnl[pnl < 0].sum()
        pf = (
            (gross_win / gross_loss)
            if gross_loss > 0
            else (inf if gross_win > 0 else 0.0)
        )
        num = int(len(pnl))
        winrate = float((pnl > 0).mean())
        avgtrade = float(pnl.mean())
        dur = _trade_durations(trades_df)

        # compute trade-based CAGR components
        try:
            denom = (trades_df["entry_price"] * trades_df["entry_qty"]).replace(
                0, np.nan
            )
            ret_frac = (
                (trades_df["net_pnl"] / denom)
                .replace([np.inf, -np.inf], np.nan)
                .fillna(0.0)
            )
            avg_profit_per_trade_frac = float(ret_frac.mean()) if len(ret_frac) else 0.0
        except Exception:
            avg_profit_per_trade_frac = 0.0

        # average bars per trade derived from durations (days) - works for daily data
        dur_days = _trade_durations(trades_df)
        avg_days = float(dur_days.mean()) if len(dur_days) else float("nan")
        avg_bars = avg_days

    # trade-based CAGR formula preference (avg_profit_per_trade_frac * bars_per_year / avg_bars)
    trade_based_cagr = None
    try:
        if not np.isnan(avg_bars) and avg_bars > 0:
            trade_based_cagr = avg_profit_per_trade_frac * (ann / avg_bars)
    except Exception:
        trade_based_cagr = None

    # Prefer trade-based CAGR when trades exist.
    # If trade-based CAGR is unavailable but trades exist, set CAGR to 0 (as requested).
    if num and num > 0:
        if trade_based_cagr is not None:
            cagr_like = float(trade_based_cagr)
        else:
            cagr_like = 0.0

    out.update(
        {
            "FinalEquity": end,
            "CAGR_like": cagr_like,
            "Sharpe": sharpe,
            "Sortino": sortino,
            "MaxDD": maxdd,
            "Calmar": calmar,
            "Exposure": exposure,
            "WinRate": winrate if trades_df is not None and len(trades_df) else 0.0,
            "ProfitFactor": pf,
            "NumTrades": num,
            "AvgTrade": avgtrade,
            "HoldDays_avg": float(dur.mean()) if len(dur) else 0.0,
            "HoldDays_p50": float(dur.median()) if len(dur) else 0.0,
            "HoldDays_p90": float(dur.quantile(0.90)) if len(dur) else 0.0,
            # additional trade-aware fields
            "AvgTradePct": (
                float(avg_profit_per_trade_frac * 100.0)
                if "avg_profit_per_trade_frac" in locals()
                else 0.0
            ),
            "AvgBarsPerTrade": (
                float(avg_bars) if "avg_bars" in locals() else float("nan")
            ),
        }
    )
    return out


# ---------- Basket metrics you requested ----------
def _bars_between(df_index: pd.DatetimeIndex, t0, t1) -> int:
    """Count trading bars between entry_time and exit_time inclusive using df index."""
    if t0 not in df_index or t1 not in df_index:
        delta_days = (pd.to_datetime(t1) - pd.to_datetime(t0)).days
        return max(delta_days, 1)
    i0 = df_index.get_loc(t0)
    i1 = df_index.get_loc(t1)
    if isinstance(i0, slice):
        i0 = i0.start
    if isinstance(i1, slice):
        i1 = i1.start
    return int(abs(i1 - i0) + 1)


def compute_trade_metrics_table(
    df: pd.DataFrame, trades: pd.DataFrame, bars_per_year: int
) -> dict:
    """
    Per-symbol row:
      - AvgProfitPerTradePct
      - AvgBarsPerTrade
      - CAGR_pct = AvgProfitPerTradePct * (bars_per_year / AvgBarsPerTrade) * 100
      - NumTrades, WinRatePct, ProfitFactor
    """
    if trades is None or trades.empty:
        return {
            "AvgProfitPerTradePct": 0.0,
            "AvgBarsPerTrade": np.nan,
            "CAGR_pct": 0.0,
            "NumTrades": 0,
            "WinRatePct": 0.0,
            "ProfitFactor": 0.0,
        }

    t = trades.copy()

    # Filter to only closed trades (those with net_pnl values) for performance calculation
    # This avoids double-counting when trades dataframe contains both entry and exit rows
    closed_trades = t[t["net_pnl"].notna() & (t["net_pnl"] != "")].copy()

    if closed_trades.empty:
        return {
            "AvgProfitPerTradePct": 0.0,
            "AvgBarsPerTrade": np.nan,
            "CAGR_pct": 0.0,
            "IRR_pct": 0.0,
            "NumTrades": 0,
            "WinRatePct": 0.0,
            "ProfitFactor": 0.0,
        }

    # include open trades MTM when net_pnl is missing
    pnl_vals = []
    for _, tr in closed_trades.reset_index(drop=True).iterrows():
        _raw_net = tr.get("net_pnl")
        net_pnl = None
        try:
            if _raw_net is not None:
                net_pnl = float(_raw_net)
        except (ValueError, TypeError):
            net_pnl = None

        if net_pnl is None or pd.isna(net_pnl):
            # compute MTM using last available price in df
            try:
                entry_price_raw = tr.get("entry_price")
                qty_raw = tr.get("entry_qty", 0)
                if entry_price_raw is not None and qty_raw is not None:
                    entry_price = float(entry_price_raw)
                    qty = float(qty_raw)
                    if df is not None and not df.empty:
                        current_price = float(df["close"].iloc[-1])
                    else:
                        current_price = entry_price
                    net_pnl = (current_price - entry_price) * qty
                else:
                    net_pnl = 0.0
            except Exception:
                net_pnl = 0.0

        pnl_vals.append(float(net_pnl))

    # deployed denom for percent per trade
    denom = (
        (closed_trades["entry_price"] * closed_trades["entry_qty"])
        .abs()
        .replace(0, np.nan)
    )

    # ret_frac per trade - IMPORTANT: reset index to avoid pandas index misalignment
    try:
        pnl_series = pd.Series(pnl_vals)  # Has index [0, 1, 2, ...]
        denom_series = denom.reset_index(
            drop=True
        )  # Reset to [0, 1, 2, ...] to match pnl_series
        ret_frac = pnl_series / denom_series.replace([np.inf, -np.inf], np.nan)
        ret_frac = ret_frac.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        avg_profit_per_trade_frac = float(ret_frac.mean())
    except Exception as e:
        print(f"DEBUG: Exception in ret_frac calculation: {e}")
        avg_profit_per_trade_frac = 0.0

    bars = []
    for e0, e1 in zip(
        pd.to_datetime(closed_trades["entry_time"]),
        pd.to_datetime(closed_trades["exit_time"]),
    ):
        # Handle NaT exit times (open trades) by using current date or last available date
        try:
            if pd.isna(e1):
                if df is not None and not df.empty:
                    e1 = df.index[-1]  # Use last available date for open trades
                else:
                    e1 = e0  # Fallback to entry date (0 bars)
            df_index = df.index if (df is not None and not df.empty) else pd.DatetimeIndex([])
            if isinstance(df_index, pd.DatetimeIndex):
                n_bars = _bars_between(df_index, e0, e1)
            else:
                n_bars = 0
        except Exception:
            n_bars = 0
        bars.append(n_bars)

    avg_bars = float(np.mean(bars)) if len(bars) else np.nan

    # CAGR calculation: handle zero/NaN bars case properly
    if avg_bars and avg_bars > 0 and not pd.isna(avg_bars):
        cagr_frac = avg_profit_per_trade_frac * (bars_per_year / avg_bars)
    else:
        # For trades with 0 bars (same-day entry/exit), use the raw profit percentage
        cagr_frac = avg_profit_per_trade_frac

    # Profit factor should be computed over closed trades only (where net_pnl is present)
    if not closed_trades.empty:
        pnl = closed_trades["net_pnl"].astype(float)
        gross_win = float(pnl[pnl > 0].sum())
        gross_loss = float(-pnl[pnl < 0].sum())
        pf = (
            (gross_win / gross_loss)
            if gross_loss > 0
            else (inf if gross_win > 0 else 0.0)
        )
        winrate_pct = float((pnl > 0).mean() * 100.0)
    else:
        # no closed trades
        pf = 0.0
        winrate_pct = 0.0

    # Also compute IRR including all trades (open + closed)
    # This uses all trades from the original trades dataframe with MTM for open ones
    all_pnl_vals = []
    for idx, tr in t.reset_index(drop=True).iterrows():
        _raw_net = tr.get("net_pnl")
        net_pnl = None
        try:
            if _raw_net is not None:
                net_pnl = float(_raw_net)
        except (ValueError, TypeError):
            net_pnl = None

        if net_pnl is None or pd.isna(net_pnl):
            # compute MTM using last available price in df for open trades
            try:
                entry_price_raw = tr.get("entry_price")
                qty_raw = tr.get("entry_qty", 0)
                if entry_price_raw is not None and qty_raw is not None:
                    entry_price = float(entry_price_raw)
                    qty = float(qty_raw)
                    if df is not None and not df.empty:
                        current_price = float(df["close"].iloc[-1])
                    else:
                        current_price = entry_price
                    net_pnl = (current_price - entry_price) * qty
                else:
                    net_pnl = 0.0
            except (ValueError, TypeError, KeyError):
                net_pnl = 0.0

        all_pnl_vals.append(float(net_pnl))

    # Compute IRR for all trades (with MTM for open)
    try:
        all_denom = (t["entry_price"] * t["entry_qty"]).abs().replace(0, np.nan)
        all_pnl_series = pd.Series(all_pnl_vals)
        all_denom_series = all_denom.reset_index(drop=True)
        all_ret_frac = (
            all_pnl_series / all_denom_series.replace([np.inf, -np.inf], np.nan)
        )
        all_ret_frac = all_ret_frac.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        avg_profit_per_trade_frac_all = float(all_ret_frac.mean())
    except Exception:
        avg_profit_per_trade_frac_all = avg_profit_per_trade_frac

    # Calculate bars for all trades
    bars_all = []
    entry_times = pd.to_datetime(t["entry_time"]).tolist()
    exit_times = pd.to_datetime(t["exit_time"]).tolist()
    for e0, e1 in zip(entry_times, exit_times):
        try:
            if pd.isna(e1):
                if df is not None and not df.empty:
                    e1 = df.index[-1]
                else:
                    e1 = e0
            df_index = df.index if (df is not None and not df.empty) else pd.DatetimeIndex([])
            if isinstance(df_index, pd.DatetimeIndex):
                n_bars = _bars_between(df_index, e0, e1)
            else:
                n_bars = 0
        except Exception:
            n_bars = 0
        bars_all.append(n_bars)

    avg_bars_all = float(np.mean(bars_all)) if len(bars_all) else np.nan

    # Compute IRR for all trades (closed + open)
    if avg_bars_all and avg_bars_all > 0 and not pd.isna(avg_bars_all):
        irr_frac_all = avg_profit_per_trade_frac_all * (bars_per_year / avg_bars_all)
    else:
        irr_frac_all = avg_profit_per_trade_frac_all

    return {
        "AvgProfitPerTradePct": avg_profit_per_trade_frac * 100.0,
        "AvgBarsPerTrade": avg_bars,
        # Provide trade-based CAGR_pct (percent) here; equity-based CAGR remains 0 and
        # is computed in reporting layer when equity series is available.
        "CAGR_pct": float(cagr_frac * 100.0),
        # IRR_pct for closed trades only
        "IRR_pct": cagr_frac * 100.0,
        # IRR_pct_incl_open includes all trades at mark-to-market
        "IRR_pct_incl_open": irr_frac_all * 100.0,
        "NumTrades": int(len(closed_trades)),
        "WinRatePct": winrate_pct,
        "ProfitFactor": float(pf),
    }


def compute_portfolio_trade_metrics(
    dfs_by_symbol: dict[str, pd.DataFrame],
    trades_by_symbol: dict[str, pd.DataFrame],
    bars_per_year: int,
) -> dict:
    """
    Aggregate ALL trades across symbols into a portfolio-level row using your formulas.
    """
    # Following user's specification:
    # Avg profit % = Sum(net_pnl across all trades, including open trades MTM) / Sum(capital deployed in each trade)
    # Avg bars in trade = Sum(number of bars across all trades) / NumTrades
    total_net_pnl = 0.0
    total_deployed = 0.0
    total_bars = 0
    pnl_all = []
    closed_flags = (
        []
    )  # track which pnl entries are from closed trades (original net_pnl present)

    for sym, trades in trades_by_symbol.items():
        if trades is None or trades.empty:
            continue
        df = dfs_by_symbol.get(sym)
        # deployed capital per trade = entry_price * abs(entry_qty)
        deployed = (
            (trades["entry_price"] * trades["entry_qty"]).abs().replace(0, np.nan)
        )
        # sum deployed where available
        try:
            deployed_sum = float(
                deployed.replace([np.inf, -np.inf], np.nan).fillna(0.0).sum()
            )
        except Exception:
            deployed_sum = 0.0
        total_deployed += deployed_sum

        # sum net pnl. Include unrealized (MTM) for open trades where net_pnl is missing
        pnl_vals = []
        for _, tr in trades.reset_index(drop=True).iterrows():
            _raw_net = tr.get("net_pnl")
            # detect whether this trade was closed (original net_pnl present)
            closed = False
            net_pnl = None
            try:
                if _raw_net is not None:
                    net_pnl = float(_raw_net)
                    if not pd.isna(net_pnl):
                        closed = True
            except (ValueError, TypeError):
                net_pnl = None

            # if net_pnl is not available or NaN, compute MTM using latest price in df
            if net_pnl is None or pd.isna(net_pnl):
                try:
                    entry_price_raw = tr.get("entry_price")
                    qty_raw = tr.get("entry_qty", 0)
                    if entry_price_raw is not None and qty_raw is not None:
                        entry_price = float(entry_price_raw)
                        qty = float(qty_raw)
                        # determine valuation time: exit_time if present else last available price
                        exit_time = tr.get("exit_time")
                        if pd.notna(exit_time) and df is not None and exit_time in df.index:
                            current_price = float(df.loc[exit_time]["close"])
                        elif df is not None and not df.empty:
                            # use last available close
                            current_price = float(df["close"].iloc[-1])
                        else:
                            current_price = entry_price
                        net_pnl = (current_price - entry_price) * qty
                    else:
                        net_pnl = 0.0
                except Exception:
                    net_pnl = 0.0

            pnl_vals.append(float(net_pnl))
            closed_flags.append(bool(closed))

        pnl_series = pd.Series(pnl_vals, dtype=float)
        total_net_pnl += float(pnl_series.sum())
        pnl_all.extend(pnl_series.tolist())

        # bars per trade (for open trades, use last index as exit)
        for _, tr in trades.reset_index(drop=True).iterrows():
            try:
                entry_time_raw = tr.get("entry_time")
                if entry_time_raw is not None:
                    e0 = pd.to_datetime(entry_time_raw)
                else:
                    continue
                e1 = tr.get("exit_time")
                if pd.isna(e1) or e1 is None:
                    # fallback to last available date in df
                    if df is not None and not df.empty:
                        e1 = df.index[-1]
                    else:
                        e1 = e0
                else:
                    e1 = pd.to_datetime(e1)
                df_index = df.index if (df is not None and not df.empty) else pd.DatetimeIndex([])
                if isinstance(df_index, pd.DatetimeIndex):
                    n = _bars_between(df_index, e0, e1)
                else:
                    n = 0
            except Exception:
                n = 0
            total_bars += int(n)

    num_trades = int(len(pnl_all))
    if num_trades == 0 or total_deployed == 0:
        return {
            "AvgProfitPerTradePct": 0.0,
            "AvgBarsPerTrade": np.nan,
            "CAGR_pct": 0.0,
            "IRR_pct": 0.0,
            "NumTrades": 0,
            "WinRatePct": 0.0,
            "ProfitFactor": 0.0,
        }

    avg_profit_frac = total_net_pnl / total_deployed  # fraction (e.g., 0.02 for 2%)
    avg_bars = float(total_bars) / float(num_trades) if num_trades > 0 else float("nan")

    # IRR (deployment-based) using trade aggregation: avg_profit_frac annualized
    # This includes open trades at mark-to-market value, which is appropriate for IRR calculation
    if avg_bars and avg_bars > 0 and not pd.isna(avg_bars):
        irr_frac = avg_profit_frac * (bars_per_year / avg_bars)
    else:
        # For trades with 0 bars (same-day entry/exit), use the raw profit percentage
        irr_frac = avg_profit_frac

    pnl_series_all = pd.Series(pnl_all, dtype=float)
    closed_flags_series = (
        pd.Series(closed_flags, dtype=bool) if closed_flags else pd.Series(dtype=bool)
    )
    # Profit factor should be computed over closed trades only (where original net_pnl was present)
    if not closed_flags_series.empty and closed_flags_series.any():
        closed_pnl = pnl_series_all[closed_flags_series]
        closed_pnl = closed_pnl.dropna()
        if not closed_pnl.empty:
            gross_win = float(closed_pnl[closed_pnl > 0].sum())
            gross_loss = float(-closed_pnl[closed_pnl < 0].sum())
            pf = (
                (gross_win / gross_loss)
                if gross_loss > 0
                else (inf if gross_win > 0 else 0.0)
            )
            winrate_pct = float((closed_pnl > 0).mean() * 100.0)
        else:
            pf = 0.0
            winrate_pct = 0.0
    else:
        # No truly closed trades available
        pf = 0.0
        winrate_pct = 0.0

    # portfolio exposure: average per-symbol exposure fraction (if qty column present)
    exposures = []
    for sym, df in dfs_by_symbol.items():
        try:
            if "qty" in df.columns:
                exposures.append(float((df["qty"] > 0).mean()))
        except Exception:
            continue
    exposure_portfolio = float(np.mean(exposures)) if exposures else float("nan")

    return {
        "AvgProfitPerTradePct": avg_profit_frac * 100.0,
        "AvgBarsPerTrade": avg_bars,
        "CAGR_pct": 0.0,  # equity-based CAGR is computed in reporting layer from equity curve
        "IRR_pct": irr_frac
        * 100.0,  # trade-based IRR including open positions at mark-to-market
        "NumTrades": num_trades,
        "WinRatePct": winrate_pct,
        "ProfitFactor": pf,
        "Exposure": exposure_portfolio,
    }


# ---------- Portfolio equity curve (fixed for union of dates) ----------
def equity_to_drawdown(equity: pd.Series) -> pd.Series:
    equity = pd.Series(equity).astype(float)
    peak = equity.cummax()
    return equity / peak - 1.0


def combine_equal_weight(
    equity_map: dict, initial_capital: float = 100000.0
) -> pd.DataFrame:
    """
    Equal-weight portfolio curve from multiple equity series.

    Fixes:
      - Outer-join on dates (union), not intersection.
      - Missing returns treated as 0 (cash) to keep fixed 1/N weighting.
      - Average by N_total every day.

    Returns DataFrame with columns: ['equity','drawdown'] indexed by date.
    """
    if not equity_map:
        return pd.DataFrame(columns=["equity", "drawdown"])

    N_total = len(equity_map)
    if N_total == 0:
        return pd.DataFrame(columns=["equity", "drawdown"])

    rets = []
    for sym, eq in equity_map.items():
        s = pd.Series(eq).sort_index().astype(float)
        # remove duplicate index labels (keep last) to avoid reindexing errors
        if s.index.duplicated().any():
            s = s[~s.index.duplicated(keep="last")]
        r = s.pct_change()
        # set first valid return to 0.0
        if not r.empty:
            r.iloc[0] = 0.0
        rets.append(r.rename(sym))

    R = pd.concat(rets, axis=1, join="outer").sort_index().fillna(0.0)
    port_ret = R.sum(axis=1) / float(N_total)

    equity = (1.0 + port_ret).cumprod() * float(initial_capital)
    drawdown = equity_to_drawdown(equity)
    return pd.DataFrame({"equity": equity, "drawdown": drawdown})
