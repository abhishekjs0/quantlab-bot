"""
CONSOLIDATED Metrics Module - Single Source of Truth for All Performance Calculations.

🎯 PURPOSE:
Consolidates ALL performance metrics calculation from previously scattered modules:
  - core/perf.py (portfolio/trade metrics)
  - utils/performance.py (performance ratios)
  - core/benchmark.py (alpha/beta calculations)
  - core/metrics.py (unified entry point)

⚠️ DEPRECATED MODULES (kept for backward compatibility):
  - utils/performance.py - Use functions from this module instead
  - core/benchmark.py - Use calculate_alpha_beta() from this module instead
  - core/perf.py - Use compute_perf() or trade functions from this module instead

✅ STANDARDIZATION:
- All metrics use 245 trading days per year (Indian market)
- Risk-free rate: 6% (0.06) annually
- CAGR uses trade-based approach with MTM for open positions
- Ratios (Sharpe, Sortino, Calmar) use trade-based returns
- Alpha/Beta calculated against NIFTYBEES benchmark
- Max drawdown from equity curve

🔧 MAIN ENTRY POINTS:
1. compute_comprehensive_metrics() - Full metric calculation (recommended)
2. compute_perf() - Portfolio performance metrics
3. compute_trade_metrics_table() - Per-trade analysis
4. compute_portfolio_trade_metrics() - Aggregated basket metrics

📊 FUNCTIONS CONSOLIDATED:
From utils/performance.py:
  - calculate_returns(), calculate_log_returns()
  - annualized_return(), annualized_volatility()
  - sharpe_ratio(), sortino_ratio()
  - calmar_ratio(), max_drawdown_from_returns()
  - value_at_risk(), conditional_value_at_risk()
  - beta(), alpha(), information_ratio()
  - tail_ratio(), skewness(), kurtosis()
  - win_rate(), profit_factor(), kelly_criterion()
  - comprehensive_performance_stats()

From core/perf.py:
  - compute_perf() - Core equity metrics
  - compute_trade_metrics_table() - Per-symbol trade analysis
  - compute_portfolio_trade_metrics() - Portfolio aggregation
  - combine_equal_weight() - Multi-symbol portfolio

From core/benchmark.py:
  - load_benchmark_data()
  - calculate_alpha_beta() - Proper alpha/beta vs benchmark
  - calculate_portfolio_alpha_beta()
"""

import logging
from math import inf, sqrt
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Constants
PERIODS_PER_YEAR = 245  # Indian market trading days
RISK_FREE_RATE = 0.06  # 6% annual
BENCHMARK_SYMBOL = "NIFTYBEES"  # Benchmark for alpha/beta
DEFAULT_BENCHMARK_FILE = "data/cache/dhan_10576_NIFTYBEES_1d.csv"


def load_benchmark(interval: str = "1d") -> Optional[pd.DataFrame]:
    """
    Load NIFTYBEES benchmark data for alpha/beta calculation.

    Args:
        interval: Time interval ('1d', '75m', '125m')

    Returns:
        DataFrame with 'equity' column and datetime index, or None if not found
    """
    import glob

    try:
        # Find the benchmark file
        cache_dir = Path("data/cache")
        pattern = f"dhan_10576_NIFTYBEES_{interval}.csv"
        benchmark_files = list(cache_dir.glob(pattern))

        if not benchmark_files:
            logger.debug(f"Benchmark file not found: {pattern}")
            return None

        benchmark_file = benchmark_files[0]
        df = pd.read_csv(benchmark_file)

        # Rename 'close' to 'equity' for consistency
        if "close" in df.columns:
            df = df.copy()
            df["equity"] = df["close"]

        # Parse date column
        if "tradingDate" in df.columns:
            df["date"] = pd.to_datetime(df["tradingDate"])
        elif "Date" in df.columns:
            df["date"] = pd.to_datetime(df["Date"])
        elif "time" in df.columns:
            df["date"] = pd.to_datetime(df["time"])
        else:
            # Try to find datetime column
            date_cols = [
                c for c in df.columns if "date" in c.lower() or "time" in c.lower()
            ]
            if date_cols:
                df["date"] = pd.to_datetime(df[date_cols[0]])
            else:
                logger.debug("No date column found in benchmark file")
                return None

        df.set_index("date", inplace=True)
        df.index = pd.to_datetime(df.index)

        # Normalize timezone - remove UTC offset if present
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        return df[["equity"]].sort_index()

    except Exception as e:
        logger.debug(f"Error loading benchmark: {e}")
        return None


def get_daily_returns_from_equity(equity_series: pd.Series) -> pd.Series:
    """Calculate daily returns from equity curve."""
    return equity_series.pct_change().fillna(0.0)


def calculate_annualized_return(returns: pd.Series) -> float:
    """
    Calculate annualized return from daily returns series.

    Formula: (1 + total_return) ^ (periods_per_year / len(returns)) - 1
    """
    total_return = (1 + returns).prod() - 1
    periods_traded = len(returns)
    if periods_traded == 0:
        return 0.0
    annualized = (1 + total_return) ** (PERIODS_PER_YEAR / periods_traded) - 1
    return float(annualized)


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
    annualized_return: float = None,
    annualized_volatility: float = None,
) -> float:
    """
    Calculate Sharpe ratio.

    Formula: (annualized_return - risk_free_rate) / annualized_volatility

    Args:
        returns: Daily returns series
        risk_free_rate: Annual risk-free rate (default 6%)
        annualized_return: Pre-calculated annualized return (e.g., IRR). If None, calculated from returns.
        annualized_volatility: Pre-calculated annualized volatility. If None, calculated from returns.

    Returns:
        Sharpe ratio
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0

    if annualized_return is None:
        annualized_ret = calculate_annualized_return(returns)
    else:
        annualized_ret = annualized_return

    if annualized_volatility is None:
        annualized_vol = returns.std() * sqrt(PERIODS_PER_YEAR)
    else:
        annualized_vol = annualized_volatility

    if annualized_vol == 0:
        return 0.0

    sharpe = (annualized_ret - risk_free_rate) / annualized_vol
    return float(sharpe)


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
    annualized_return: float = None,
    annualized_volatility: float = None,
) -> float:
    """
    Calculate Sortino ratio (uses only downside volatility).

    Formula: (annualized_return - risk_free_rate) / annualized_downside_volatility

    Args:
        returns: Daily returns series
        risk_free_rate: Annual risk-free rate (default 6%)
        annualized_return: Pre-calculated annualized return (e.g., IRR). If None, calculated from returns.
        annualized_volatility: Pre-calculated downside volatility. If None, calculated from returns.

    Returns:
        Sortino ratio
    """
    if len(returns) == 0:
        return 0.0

    if annualized_return is None:
        annualized_ret = calculate_annualized_return(returns)
    else:
        annualized_ret = annualized_return

    # Downside returns (only negative returns)
    downside_returns = returns[returns < 0]
    if len(downside_returns) == 0:
        # No downside returns - perfect strategy or flat performance
        return float("inf") if annualized_ret > 0 else 0.0

    if annualized_volatility is None:
        downside_vol = downside_returns.std() * sqrt(PERIODS_PER_YEAR)
    else:
        # Use pre-calculated downside volatility
        downside_vol = annualized_volatility

    if downside_vol == 0:
        return float("inf") if annualized_ret > 0 else 0.0

    sortino = (annualized_ret - risk_free_rate) / downside_vol
    return float(sortino)


def calculate_max_drawdown(equity_series: pd.Series) -> tuple:
    """
    Calculate maximum drawdown and drawdown series.

    Formula:
        Drawdown_t = (Equity_t / Peak_up_to_t) - 1
        Max Drawdown = min(all drawdowns)

    Args:
        equity_series: Equity curve series

    Returns:
        (max_drawdown as decimal, drawdown_series)
    """
    equity_series = pd.Series(equity_series).astype(float)
    peak = equity_series.cummax()
    drawdown = (equity_series / peak) - 1.0
    max_dd = float(drawdown.min())
    return max_dd, drawdown


def calculate_calmar_ratio(
    equity_series: pd.Series, annualized_return: float = None
) -> float:
    """
    Calculate Calmar Ratio (Return over Maximum Drawdown).

    Formula: annualized_return / max_drawdown

    Args:
        equity_series: Equity curve series
        annualized_return: Pre-calculated annualized return (e.g., IRR). If None, calculated from equity curve.

    Returns:
        Calmar ratio
    """
    equity_series = pd.Series(equity_series).astype(float)

    # Calculate max drawdown
    peak = equity_series.cummax()
    drawdown = (equity_series / peak) - 1.0
    max_dd = float(drawdown.min())

    if max_dd == 0:  # No drawdown
        return 0.0

    if annualized_return is None:
        # Calculate from equity curve
        annualized_ret = calculate_equity_based_cagr(equity_series)
    else:
        annualized_ret = annualized_return

    calmar = annualized_ret / abs(max_dd)
    return float(calmar)


def calculate_trade_based_cagr(
    trades_df: pd.DataFrame, df: pd.DataFrame = None, include_open: bool = True
) -> tuple:
    """
    Calculate CAGR based on trade performance, including open positions at MTM.

    Formula:
        1. Avg profit per trade (fraction) = sum(net_pnl_with_mtm) / sum(deployed_capital)
        2. Avg bars per trade = sum(bars) / num_trades
        3. CAGR = avg_profit_fraction * (periods_per_year / avg_bars)
        4. Return as percentage

    Args:
        trades_df: Trades dataframe with entry_price, entry_qty, net_pnl, entry_time, exit_time
                   OR consolidated format from run_basket with: Price INR, Position size (qty),
                   Net P&L %, Date/Time, Holding days
        df: Price data (needed for MTM of open trades)
        include_open: Whether to include open trades at MTM (default True)

    Returns:
        (cagr_percent, num_trades, avg_profit_percent, avg_bars_per_trade)
    """
    if trades_df is None or trades_df.empty:
        return 0.0, 0, 0.0, 0.0

    trades = trades_df.copy()
    total_pnl = 0.0
    total_deployed = 0.0
    total_bars = 0
    num_trades = 0

    # Detect format: check if this is consolidated format from run_basket (has "Net P&L %" column)
    is_consolidated_format = "Net P&L %" in trades.columns

    # For consolidated format, we use an entry/exit based approach
    # Each row represents a closed trade (Entry + Exit pair) with summary stats
    if is_consolidated_format:
        # Consolidated format from run_basket:
        # - "Price INR": Entry price
        # - "Position size (qty)": Entry quantity
        # - "Net P&L %": Profit/loss percentage
        # - "Holding days": Trade duration in days
        # - "Type": "Entry long" vs "Exit long"

        # Filter for exits only (each exit row represents a complete trade)
        exit_trades = (
            trades[trades.get("Type", "Exit long") == "Exit long"].copy()
            if "Type" in trades.columns
            else trades.copy()
        )

        for _, trade in exit_trades.iterrows():
            # For consolidated trades, we need entry price and qty from the trade row
            try:
                # In consolidated format, Price INR is usually the entry price of the position
                entry_price = float(trade.get("Price INR", 0))
                entry_qty = float(trade.get("Position size (qty)", 0))

                # Alternative column names
                if entry_price == 0 or pd.isna(entry_price):
                    entry_price = float(
                        trade.get("Entry Price", trade.get("entry_price", 0))
                    )
                if entry_qty == 0 or pd.isna(entry_qty):
                    entry_qty = float(trade.get("Qty", trade.get("entry_qty", 0)))

                deployed = abs(entry_price * entry_qty)
            except (ValueError, TypeError, KeyError):
                continue

            if deployed == 0:
                continue

            total_deployed += deployed

            # Net P&L: Try "Net P&L %" first (consolidated), then "Net P&L INR"
            try:
                if "Net P&L %" in trade:
                    pnl_pct = float(str(trade["Net P&L %"]).replace("%", "").strip())
                    net_pnl = deployed * (pnl_pct / 100.0)
                elif "Net P&L INR" in trade:
                    net_pnl = float(trade["Net P&L INR"])
                elif "net_pnl" in trade:
                    net_pnl = float(trade["net_pnl"])
                else:
                    net_pnl = 0.0
            except (ValueError, TypeError):
                net_pnl = 0.0

            total_pnl += net_pnl

            # Holding days (from consolidated format)
            try:
                holding_days = float(trade.get("Holding days", 1))
                total_bars += max(
                    holding_days, 1
                )  # Use days as bars for daily timeframe
            except (ValueError, TypeError):
                total_bars += 1

            num_trades += 1

    else:
        # Original internal format: entry_price, entry_qty, net_pnl, entry_time, exit_time
        for _, trade in trades.iterrows():
            # Deployed capital
            try:
                entry_price = float(trade["entry_price"])
                entry_qty = float(trade["entry_qty"])
                deployed = abs(entry_price * entry_qty)
            except (ValueError, TypeError, KeyError):
                continue

            if deployed == 0:
                continue

            total_deployed += deployed

            # Net P&L (with MTM for open trades)
            try:
                net_pnl = (
                    float(trade["net_pnl"]) if pd.notna(trade["net_pnl"]) else None
                )
            except (ValueError, TypeError):
                net_pnl = None

            # If no net_pnl and include_open, calculate MTM
            if (
                (net_pnl is None or pd.isna(net_pnl))
                and include_open
                and df is not None
                and not df.empty
            ):
                try:
                    current_price = float(df["close"].iloc[-1])
                    net_pnl = (current_price - entry_price) * entry_qty
                except Exception:
                    net_pnl = 0.0
            elif net_pnl is None or pd.isna(net_pnl):
                net_pnl = 0.0

            total_pnl += net_pnl

            # Bars per trade
            try:
                entry_time = pd.to_datetime(trade["entry_time"])
                exit_time = (
                    pd.to_datetime(trade["exit_time"])
                    if pd.notna(trade["exit_time"])
                    else None
                )

                if exit_time is None and df is not None and not df.empty:
                    exit_time = df.index[-1]
                elif exit_time is None:
                    exit_time = entry_time

                if (
                    df is not None
                    and not df.empty
                    and isinstance(df.index, pd.DatetimeIndex)
                ):
                    try:
                        idx_entry = df.index.get_loc(entry_time)
                        idx_exit = df.index.get_loc(exit_time)
                        if isinstance(idx_entry, slice):
                            idx_entry = idx_entry.start
                        if isinstance(idx_exit, slice):
                            idx_exit = idx_exit.start
                        bars = max(abs(idx_exit - idx_entry) + 1, 1)
                    except Exception:
                        bars = 1
                else:
                    # Estimate from days
                    days = (exit_time - entry_time).days
                    bars = max(days, 1)

                total_bars += bars

            except Exception:
                total_bars += 1

            num_trades += 1

    if num_trades == 0 or total_deployed == 0:
        return 0.0, 0, 0.0, 0.0

    avg_profit_fraction = total_pnl / total_deployed
    avg_bars = total_bars / num_trades

    # Annualize
    if avg_bars > 0:
        cagr_fraction = avg_profit_fraction * (PERIODS_PER_YEAR / avg_bars)
    else:
        cagr_fraction = avg_profit_fraction

    cagr_percent = cagr_fraction * 100.0
    avg_profit_percent = avg_profit_fraction * 100.0

    return (
        float(cagr_percent),
        int(num_trades),
        float(avg_profit_percent),
        float(avg_bars),
    )


def calculate_equity_based_cagr(
    equity_series: pd.Series, days_traded: int = None
) -> float:
    """
    Calculate CAGR from equity curve.

    Formula: (end_equity / start_equity) ^ (1 / years) - 1

    Args:
        equity_series: Equity curve
        days_traded: Optional number of days (if not in index)

    Returns:
        CAGR as decimal
    """
    equity_series = pd.Series(equity_series).astype(float)
    if len(equity_series) < 2:
        return 0.0

    start_eq = float(equity_series.iloc[0])
    end_eq = float(equity_series.iloc[-1])

    if start_eq <= 0:
        return 0.0

    # Determine years
    try:
        if isinstance(equity_series.index, pd.DatetimeIndex):
            days = (equity_series.index[-1] - equity_series.index[0]).days
            years = max(days / 365.25, 1 / 365.25)
        else:
            years = len(equity_series) / PERIODS_PER_YEAR
    except Exception:
        years = len(equity_series) / PERIODS_PER_YEAR

    if years == 0:
        return 0.0

    cagr = (end_eq / start_eq) ** (1.0 / years) - 1.0
    return float(cagr)


def calculate_win_rate(trades_df: pd.DataFrame) -> float:
    """
    Calculate win rate (percentage of profitable trades).

    Formula: (# trades with net_pnl > 0) / total_trades * 100

    Args:
        trades_df: Trades dataframe with net_pnl column

    Returns:
        Win rate as percentage
    """
    if trades_df is None or trades_df.empty:
        return 0.0

    try:
        pnl = trades_df["net_pnl"].astype(float)
        pnl = pnl[pnl.notna()]
        if len(pnl) == 0:
            return 0.0
        win_rate = (pnl > 0).sum() / len(pnl) * 100.0
        return float(win_rate)
    except Exception:
        return 0.0


def calculate_profit_factor(trades_df: pd.DataFrame) -> float:
    """
    Calculate profit factor.

    Formula: sum(winning_trades) / sum(|losing_trades|)

    Args:
        trades_df: Trades dataframe with net_pnl column

    Returns:
        Profit factor
    """
    if trades_df is None or trades_df.empty:
        return 0.0

    try:
        pnl = trades_df["net_pnl"].astype(float)
        pnl = pnl[pnl.notna()]

        gross_win = float(pnl[pnl > 0].sum())
        gross_loss = float(-pnl[pnl < 0].sum())

        if gross_loss > 0:
            pf = gross_win / gross_loss
        elif gross_win > 0:
            pf = inf
        else:
            pf = 0.0

        return float(pf)
    except Exception:
        return 0.0


def calculate_alpha_beta(
    equity_returns: pd.Series, benchmark_returns: pd.Series
) -> tuple:
    """
    Calculate alpha and beta against a benchmark.

    Beta = Covariance(returns, benchmark) / Variance(benchmark)
    Alpha = annualized_return - (risk_free_rate + beta * (benchmark_return - risk_free_rate))

    Args:
        equity_returns: Daily equity returns series
        benchmark_returns: Daily benchmark returns series

    Returns:
        (alpha, beta)
    """
    if len(equity_returns) == 0 or len(benchmark_returns) == 0:
        return 0.0, 0.0

    # Align indices
    aligned = pd.DataFrame(
        {"equity": equity_returns, "benchmark": benchmark_returns}
    ).dropna()

    if len(aligned) < 2:
        return 0.0, 0.0

    # Calculate beta
    covariance = aligned["equity"].cov(aligned["benchmark"])
    variance = aligned["benchmark"].var()

    if variance == 0:
        beta = 0.0
    else:
        beta = covariance / variance

    # Calculate alpha
    equity_annual_return = calculate_annualized_return(aligned["equity"])
    benchmark_annual_return = calculate_annualized_return(aligned["benchmark"])

    alpha = equity_annual_return - (
        RISK_FREE_RATE + beta * (benchmark_annual_return - RISK_FREE_RATE)
    )

    return float(alpha), float(beta)


def calculate_returns_from_trades(
    trades_df: pd.DataFrame, df: pd.DataFrame = None, include_open: bool = True
) -> pd.Series:
    """
    Create a returns series from trades (daily returns aligned with trade dates).

    Args:
        trades_df: Trades dataframe
        df: Price data for MTM
        include_open: Include open trades at MTM

    Returns:
        Series of daily returns
    """
    if trades_df is None or trades_df.empty:
        return pd.Series(dtype=float)

    # Calculate daily P&L from trades
    trade_returns = {}

    for _, trade in trades_df.iterrows():
        try:
            entry_date = pd.to_datetime(trade["entry_time"]).date()
            exit_date = (
                pd.to_datetime(trade["exit_time"]).date()
                if pd.notna(trade["exit_time"])
                else None
            )

            entry_price = float(trade["entry_price"])
            entry_qty = float(trade["entry_qty"])
            net_pnl = float(trade["net_pnl"]) if pd.notna(trade["net_pnl"]) else None

            # MTM for open trades
            if (
                (net_pnl is None or pd.isna(net_pnl))
                and include_open
                and df is not None
            ):
                try:
                    current_price = float(df["close"].iloc[-1])
                    net_pnl = (current_price - entry_price) * entry_qty
                except Exception:
                    net_pnl = 0.0
            elif net_pnl is None or pd.isna(net_pnl):
                net_pnl = 0.0

            deployed = abs(entry_price * entry_qty)
            if deployed > 0:
                ret = net_pnl / deployed

                # Assign to exit date or entry date
                date_key = exit_date if exit_date else entry_date
                if date_key in trade_returns:
                    trade_returns[date_key] += ret
                else:
                    trade_returns[date_key] = ret

        except Exception:
            continue

    if not trade_returns:
        return pd.Series(dtype=float)

    return pd.Series(trade_returns, dtype=float)


def calculate_deployment_volatility_and_var(
    equity_df: pd.DataFrame, trades_df: pd.DataFrame = None
) -> tuple:
    """
    Calculate volatility and VaR from all daily returns.

    Uses all returns including idle days (0% returns) to get true portfolio volatility.

    Args:
        equity_df: Equity curve dataframe with 'Equity' column
        trades_df: Trades dataframe (optional, unused)

    Returns:
        (annualized_volatility_pct, annualized_var_95_pct)
    """
    if equity_df is None or equity_df.empty:
        return 0.0, 0.0

    try:
        equity_col = "Equity" if "Equity" in equity_df.columns else "equity"
        equity_series = equity_df[equity_col].astype(float)
        daily_returns = equity_series.pct_change().fillna(0.0)

        if len(daily_returns) == 0:
            return 0.0, 0.0

        # Annualized volatility from all daily returns (including idle days)
        daily_vol = daily_returns.std()
        annualized_vol = daily_vol * sqrt(PERIODS_PER_YEAR) * 100.0

        # VaR 95% from all returns (5th percentile)
        var_95_daily = np.percentile(daily_returns, 5)
        annualized_var = var_95_daily * sqrt(PERIODS_PER_YEAR) * 100.0

        return float(annualized_vol), float(annualized_var)

    except Exception:
        return 0.0, 0.0


def create_irr_based_synthetic_returns(
    daily_returns: pd.Series, irr_decimal: float
) -> pd.Series:
    """
    Create synthetic daily returns based on IRR for deployed days.

    This represents: "If capital was deployed every day at this IRR level,
    what would the daily returns be?"

    Rationale: Measure strategy efficiency independent of deployment frequency.
    Each deployed day earns: IRR% / 365

    Args:
        daily_returns: Original daily returns (to identify deployed vs idle days)
        irr_decimal: IRR as decimal (e.g., 0.1958 for 19.58%)

    Returns:
        pd.Series with synthetic returns:
        - Deployed days: IRR% / 365
        - Idle days: 0%
    """
    if irr_decimal == 0:
        return pd.Series(0.0, index=daily_returns.index)

    # Daily IRR (divide annual IRR by 365 days)
    daily_irr = irr_decimal / 365.0

    # Create synthetic returns: deployed days get IRR/365, idle days get 0
    synthetic_returns = daily_returns.copy()

    # Deployed days: replace with constant daily IRR
    deployed_mask = daily_returns != 0.0
    synthetic_returns[deployed_mask] = daily_irr

    # Idle days: keep as 0
    synthetic_returns[~deployed_mask] = 0.0

    return synthetic_returns


def compute_comprehensive_metrics(
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    benchmark_df: pd.DataFrame = None,
    initial_capital: float = 100000.0,
) -> dict:
    """
    Compute all metrics in one place.

    Args:
        equity_df: Equity curve with 'equity' column and datetime index
        trades_df: Trades dataframe with columns: entry_price, entry_qty, net_pnl, entry_time, exit_time
        benchmark_df: Benchmark equity curve (optional, for alpha/beta)
        initial_capital: Starting capital

    Returns:
        Dictionary with all metrics
    """
    results = {}

    # Extract equity series (handle both "equity" and "Equity" column names)
    try:
        if "equity" in equity_df.columns:
            equity_series = equity_df["equity"].astype(float)
        elif "Equity" in equity_df.columns:
            equity_series = equity_df["Equity"].astype(float)
        else:
            equity_series = pd.Series(dtype=float)
    except Exception:
        equity_series = pd.Series(dtype=float)

    # Daily returns
    daily_returns = get_daily_returns_from_equity(equity_series)

    # Equity-based metrics
    results["equity_start"] = (
        float(equity_series.iloc[0]) if len(equity_series) > 0 else initial_capital
    )
    results["equity_end"] = (
        float(equity_series.iloc[-1]) if len(equity_series) > 0 else initial_capital
    )
    results["total_return_pct"] = (
        results["equity_end"] / results["equity_start"] - 1.0
    ) * 100.0
    results["cagr_equity_pct"] = calculate_equity_based_cagr(equity_series) * 100.0

    # Note: Trade-based metrics (IRR, avg_profit_per_trade, etc) are calculated separately in:
    # - compute_trade_metrics_table() - for per-symbol metrics
    # - compute_portfolio_trade_metrics() - for portfolio-level metrics
    # These functions have access to raw trade data and OHLC bars needed for accurate calculations.
    # This function uses equity curve only, which is insufficient for accurate trade-based metrics.

    # Use equity CAGR as return for metrics (equity-based perspective)
    cagr_equity_decimal = results["cagr_equity_pct"] / 100.0

    # Drawdown metrics
    max_dd, _ = calculate_max_drawdown(equity_series)
    results["max_drawdown_pct"] = max_dd * 100.0

    # Volatility and VaR (use all daily returns, not deployment-based)
    annualized_vol_pct, annualized_var_95_pct = calculate_deployment_volatility_and_var(
        equity_df, trades_df
    )
    results["annualized_volatility_pct"] = annualized_vol_pct
    results["annualized_var_95_pct"] = annualized_var_95_pct

    # Calculate downside volatility for Sortino (only negative returns)
    downside_returns = daily_returns[daily_returns < 0]
    if len(downside_returns) > 0:
        annualized_downside_vol = (
            downside_returns.std() * sqrt(PERIODS_PER_YEAR) * 100.0
        )
    else:
        # If no negative returns, use all returns std or small value
        if len(daily_returns) > 0:
            annualized_downside_vol = (
                daily_returns.std() * sqrt(PERIODS_PER_YEAR) * 100.0
            )
        else:
            annualized_downside_vol = 0.01

    annualized_vol_decimal = annualized_vol_pct / 100.0
    annualized_downside_vol_decimal = annualized_downside_vol / 100.0

    results["sharpe_ratio"] = calculate_sharpe_ratio(
        daily_returns,
        annualized_return=cagr_equity_decimal,
        annualized_volatility=annualized_vol_decimal,
    )
    results["sortino_ratio"] = calculate_sortino_ratio(
        daily_returns,
        annualized_return=cagr_equity_decimal,
        annualized_volatility=annualized_downside_vol_decimal,
    )
    results["calmar_ratio"] = calculate_calmar_ratio(
        equity_series, annualized_return=cagr_equity_decimal
    )

    # Trade stats
    results["win_rate_pct"] = calculate_win_rate(trades_df)
    results["profit_factor"] = calculate_profit_factor(trades_df)

    # Alpha/Beta (if benchmark provided)
    if benchmark_df is not None:
        try:
            benchmark_equity = benchmark_df["equity"].astype(float)
            benchmark_returns = get_daily_returns_from_equity(benchmark_equity)

            # Align returns
            aligned_dates = daily_returns.index.intersection(benchmark_returns.index)
            if len(aligned_dates) > 10:
                alpha, beta = calculate_alpha_beta(
                    daily_returns[aligned_dates], benchmark_returns[aligned_dates]
                )
                results["alpha_pct"] = alpha * 100.0
                results["beta"] = beta
            else:
                results["alpha_pct"] = 0.0
                results["beta"] = 0.0
        except Exception:
            results["alpha_pct"] = 0.0
            results["beta"] = 0.0
    else:
        results["alpha_pct"] = 0.0
        results["beta"] = 0.0

    # Exposure (average holding days)
    try:
        if "qty" in equity_df.columns:
            results["avg_exposure_pct"] = (equity_df["qty"] > 0).mean() * 100.0
        else:
            results["avg_exposure_pct"] = 0.0
    except Exception:
        results["avg_exposure_pct"] = 0.0

    return results


# ==================== CONSOLIDATED FROM core/perf.py ====================
# These functions were previously in core/perf.py and are now consolidated here


def _ann_factor(freq: str) -> int:
    """Annualization factor based on frequency."""
    f = str(freq).upper()
    return (
        252
        if f.startswith("D")
        else 52 if f.startswith("W") else 12 if f.startswith("M") else 252
    )


def _drawdown_stats(eq: pd.Series) -> tuple:
    """Calculate drawdown series and max drawdown."""
    cummax = eq.cummax()
    dd = eq / cummax - 1.0
    maxdd = float(dd.min())
    return dd, maxdd


def _trade_durations(trades: pd.DataFrame) -> pd.Series:
    """Calculate duration of trades in days."""
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
    Compute core portfolio performance metrics.

    Combines equity curve analysis with trade analysis to provide comprehensive
    performance statistics.

    Args:
        equity_df: DataFrame with 'equity' column; optional 'qty' for exposure
        trades_df: DataFrame with entry/exit and net_pnl
        freq: Frequency for annualization (D=daily, W=weekly, M=monthly)

    Returns:
        Dictionary with performance metrics
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

    # CAGR-like (geometric start->end)
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

    # Trade stats
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

        # Trade-based CAGR components
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

        dur_days = _trade_durations(trades_df)
        avg_days = float(dur_days.mean()) if len(dur_days) else float("nan")
        avg_bars = avg_days

    # Trade-based CAGR
    trade_based_cagr = None
    try:
        if not np.isnan(avg_bars) and avg_bars > 0:
            trade_based_cagr = avg_profit_per_trade_frac * (ann / avg_bars)
    except Exception:
        trade_based_cagr = None

    # Prefer trade-based CAGR when trades exist
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


def _bars_between(df_index: pd.DatetimeIndex, t0, t1) -> int:
    """Count trading bars between two times using dataframe index."""
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
    df: pd.DataFrame,
    trades: pd.DataFrame,
    bars_per_year: int,
    initial_capital: float = 100000.0,
) -> dict:
    """
    Compute per-symbol trade metrics, including OPEN trades at MTM.

    **CRITICAL**: This function must return the SAME metrics as compute_portfolio_trade_metrics()
    when aggregating a single symbol's trades. This ensures per-symbol rows match the TOTAL row
    when the portfolio contains only that symbol.

    Calculates metrics including average profit per trade, bars held, CAGR,
    and other trade statistics. **ALL trades (closed + open at MTM) are included in main metrics.**

    Args:
        df: OHLC data with datetime index
        trades: Trades dataframe (includes both closed and open trades)
        bars_per_year: Trading bars per year (e.g., 245 for daily)

    Returns:
        Dictionary with trade metrics:
        - IRR_pct: Internal rate of return (includes open trades at MTM)
        - AvgProfitPerTradePct: Average profit per trade % (includes open trades at MTM)
        - AvgBarsPerTrade: Average bars/days per trade
        - NumTrades: Total number of trades (closed + open)
        - WinRatePct: % of trades with P&L > 0 (includes open trades at MTM)
        - ProfitFactor: Sum(Wins) / Sum(Losses)
    """

    if trades is None or trades.empty:
        return {
            "AvgProfitPerTradePct": 0.0,
            "AvgBarsPerTrade": np.nan,
            "CAGR_pct": 0.0,
            "IRR_pct": 0.0,
            "NumTrades": 0,
            "WinRatePct": 0.0,
            "ProfitFactor": 0.0,
        }

    t = trades.copy()  # Calculate P&L for ALL trades (both closed and open at MTM)
    # This matches compute_portfolio_trade_metrics() logic
    total_net_pnl = 0.0
    total_deployed = 0.0
    total_bars = 0
    pnl_all = []

    for _, tr in t.reset_index(drop=True).iterrows():
        # Get entry price and qty
        try:
            entry_price = float(tr.get("entry_price", 0))
            entry_qty = float(tr.get("entry_qty", 0))
            deployed = abs(entry_price * entry_qty)
        except (ValueError, TypeError):
            continue

        if deployed == 0:
            continue

        total_deployed += deployed

        # Get net_pnl (closed) or calculate MTM (open)
        _raw_net = tr.get("net_pnl")
        net_pnl = None
        try:
            if _raw_net is not None and _raw_net != "":
                net_pnl = float(_raw_net)
        except (ValueError, TypeError):
            net_pnl = None

        # If no net_pnl (open trade), calculate MTM
        if net_pnl is None or pd.isna(net_pnl):
            try:
                if df is not None and not df.empty:
                    current_price = float(df["close"].iloc[-1])
                else:
                    current_price = entry_price
                net_pnl = (current_price - entry_price) * entry_qty
            except Exception:
                net_pnl = 0.0

        total_net_pnl += net_pnl
        pnl_all.append(float(net_pnl))

        # Calculate bars
        try:
            entry_time_raw = tr.get("entry_time")
            if entry_time_raw is not None:
                e0 = pd.to_datetime(entry_time_raw)
            else:
                e0 = None

            e1 = tr.get("exit_time")
            if pd.isna(e1) or e1 is None:
                # Open trade - use last bar
                if df is not None and not df.empty:
                    e1 = df.index[-1]
                else:
                    e1 = e0
            else:
                e1 = pd.to_datetime(e1)

            if e0 is not None and e1 is not None:
                df_index = (
                    df.index
                    if (df is not None and not df.empty)
                    else pd.DatetimeIndex([])
                )
                if isinstance(df_index, pd.DatetimeIndex):
                    n_bars = _bars_between(df_index, e0, e1)
                else:
                    n_bars = 0
            else:
                n_bars = 0
        except Exception:
            n_bars = 0

        total_bars += int(n_bars)

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

    # Calculate metrics using ALL trades (same as portfolio)
    # Net P&L % defined as: (sum of all trade P&L) / (initial capital) * 100
    net_pnl_frac = (
        (total_net_pnl / initial_capital)
        if initial_capital and initial_capital > 0
        else 0.0
    )
    net_pnl_pct = net_pnl_frac * 100.0

    # Avg P&L % per trade as requested: (sum P&L / total_deployed) * 100
    # This is the average return per trade expressed as a percentage of deployed capital
    avg_pnl_per_trade_pct = (
        (total_net_pnl / total_deployed * 100.0) if total_deployed > 0 else 0.0
    )
    avg_profit_frac = (total_net_pnl / total_deployed) if total_deployed > 0 else 0.0

    # Keep avg_bars (bars per trade)
    avg_bars = float(total_bars) / float(num_trades) if num_trades > 0 else float("nan")

    # IRR: annualized return based on avg P&L % (matches TOTAL row calculation)
    # Use avg_profit_frac (P&L / deployed) not net_pnl_frac (P&L / initial_capital)
    if avg_bars and avg_bars > 0 and not pd.isna(avg_bars):
        irr_frac = avg_profit_frac * (bars_per_year / avg_bars)
    else:
        irr_frac = avg_profit_frac

    # Win rate and profit factor from ALL trades (closed + open at MTM)
    pnl_series_all = pd.Series(pnl_all, dtype=float)
    pnl_series_clean = pnl_series_all.dropna()

    if not pnl_series_clean.empty:
        gross_win = float(pnl_series_clean[pnl_series_clean > 0].sum())
        gross_loss = float(-pnl_series_clean[pnl_series_clean < 0].sum())
        pf = (
            (gross_win / gross_loss)
            if gross_loss > 0
            else (inf if gross_win > 0 else 0.0)
        )
        winrate_pct = float((pnl_series_clean > 0).mean() * 100.0)
    else:
        pf = 0.0
        winrate_pct = 0.0

    # DEBUG
    import os

    if os.environ.get("DEBUG_METRICS"):
        print(f"  -> RETURNING: AvgProfitPerTradePct={avg_pnl_per_trade_pct:.4f}%")

    return {
        "NetPnLPct": float(net_pnl_pct),
        # Avg P&L % per trade = (sum P&L / total_deployed) * 100
        "AvgProfitPerTradePct": float(avg_pnl_per_trade_pct),
        "AvgBarsPerTrade": avg_bars,
        "CAGR_pct": float(irr_frac * 100.0),
        "IRR_pct": irr_frac * 100.0,
        "NumTrades": num_trades,
        "WinRatePct": winrate_pct,
        "ProfitFactor": float(pf),
        # totals for debugging/consumers
        "TotalNetPnL": total_net_pnl,
        "TotalDeployed": total_deployed,
    }


def compute_portfolio_trade_metrics(
    dfs_by_symbol: dict[str, pd.DataFrame],
    trades_by_symbol: dict[str, pd.DataFrame],
    bars_per_year: int,
) -> dict:
    """
    Compute portfolio-level trade metrics aggregated across all symbols.

    Args:
        dfs_by_symbol: Dictionary of symbol -> OHLC DataFrame
        trades_by_symbol: Dictionary of symbol -> trades DataFrame
        bars_per_year: Trading bars per year

    Returns:
        Portfolio-level metrics dictionary
    """
    total_net_pnl = 0.0
    total_deployed = 0.0
    total_bars = 0
    pnl_all = []
    closed_flags = []

    for sym, trades in trades_by_symbol.items():
        if trades is None or trades.empty:
            continue
        df = dfs_by_symbol.get(sym)
        deployed = (
            (trades["entry_price"] * trades["entry_qty"]).abs().replace(0, np.nan)
        )
        try:
            deployed_sum = float(
                deployed.replace([np.inf, -np.inf], np.nan).fillna(0.0).sum()
            )
        except Exception:
            deployed_sum = 0.0
        total_deployed += deployed_sum

        pnl_vals = []
        for _, tr in trades.reset_index(drop=True).iterrows():
            _raw_net = tr.get("net_pnl")
            closed = False
            net_pnl = None
            try:
                if _raw_net is not None:
                    net_pnl = float(_raw_net)
                    if not pd.isna(net_pnl):
                        closed = True
            except (ValueError, TypeError):
                net_pnl = None

            if net_pnl is None or pd.isna(net_pnl):
                try:
                    entry_price_raw = tr.get("entry_price")
                    qty_raw = tr.get("entry_qty", 0)
                    if entry_price_raw is not None and qty_raw is not None:
                        entry_price = float(entry_price_raw)
                        qty = float(qty_raw)
                        exit_time = tr.get("exit_time")
                        if (
                            pd.notna(exit_time)
                            and df is not None
                            and exit_time in df.index
                        ):
                            current_price = float(df.loc[exit_time]["close"])
                        elif df is not None and not df.empty:
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

        for _, tr in trades.reset_index(drop=True).iterrows():
            try:
                entry_time_raw = tr.get("entry_time")
                if entry_time_raw is not None:
                    e0 = pd.to_datetime(entry_time_raw)
                else:
                    continue
                e1 = tr.get("exit_time")
                if pd.isna(e1) or e1 is None:
                    if df is not None and not df.empty:
                        e1 = df.index[-1]
                    else:
                        e1 = e0
                else:
                    e1 = pd.to_datetime(e1)
                df_index = (
                    df.index
                    if (df is not None and not df.empty)
                    else pd.DatetimeIndex([])
                )
                if isinstance(df_index, pd.DatetimeIndex):
                    n = _bars_between(df_index, e0, e1)
                else:
                    n = 0
            except Exception:
                n = 0
            total_bars += int(n)

    num_trades = int(len(pnl_all))

    # DEBUG: Detailed trade count analysis
    actual_trade_count = 0
    sym_trade_counts = {}
    for sym, trades in trades_by_symbol.items():
        if trades is not None and not trades.empty:
            count = len(trades)
            actual_trade_count += count
            sym_trade_counts[sym] = count

    import sys

    if actual_trade_count > 20:  # Only log for portfolio (many trades)
        print(
            f"DEBUG: pnl_all len={len(pnl_all)}, trades_by_symbol total rows={actual_trade_count}, per-sym={sym_trade_counts}",
            file=sys.stderr,
        )

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

    avg_profit_frac = total_net_pnl / total_deployed
    avg_bars = float(total_bars) / float(num_trades) if num_trades > 0 else float("nan")

    if avg_bars and avg_bars > 0 and not pd.isna(avg_bars):
        irr_frac = avg_profit_frac * (bars_per_year / avg_bars)
    else:
        irr_frac = avg_profit_frac

    pnl_series_all = pd.Series(pnl_all, dtype=float)

    # Calculate metrics from ALL trades (closed + open at MTM)
    # This ensures consistency: if total_net_pnl includes open trades at MTM,
    # then win_rate should also be calculated from ALL trades (both closed and open)
    pnl_series_clean = pnl_series_all.dropna()
    if not pnl_series_clean.empty:
        # Win rate from ALL trades (including open positions at MTM)
        gross_win = float(pnl_series_clean[pnl_series_clean > 0].sum())
        gross_loss = float(-pnl_series_clean[pnl_series_clean < 0].sum())
        pf = (
            (gross_win / gross_loss)
            if gross_loss > 0
            else (inf if gross_win > 0 else 0.0)
        )
        # Win rate includes both closed trades and open positions at MTM
        winrate_pct = float((pnl_series_clean > 0).mean() * 100.0)
    else:
        pf = 0.0
        winrate_pct = 0.0

    exposures = []
    for sym, df in dfs_by_symbol.items():
        try:
            if "qty" in df.columns:
                exposures.append(float((df["qty"] > 0).mean()))
        except Exception:
            continue
    exposure_portfolio = float(np.mean(exposures)) if exposures else float("nan")

    # DEBUG: Print metrics for large portfolio
    if num_trades > 1000:
        import sys
        print(f"DEBUG compute_portfolio_trade_metrics: num_trades={num_trades}, total_net_pnl={total_net_pnl:,.0f}, total_deployed={total_deployed:,.0f}, avg_profit_frac={avg_profit_frac:.6f}, AvgProfitPerTradePct={avg_profit_frac * 100.0:.2f}%", file=sys.stderr)
    
    return {
        "AvgProfitPerTradePct": avg_profit_frac * 100.0,
        "AvgBarsPerTrade": avg_bars,
        "CAGR_pct": 0.0,
        "IRR_pct": irr_frac * 100.0,
        "NumTrades": num_trades,
        "WinRatePct": winrate_pct,
        "ProfitFactor": pf,
        "Exposure": exposure_portfolio,
        "TotalNetPnL": total_net_pnl,
        "TotalDeployed": total_deployed,
    }


def equity_to_drawdown(equity: pd.Series) -> pd.Series:
    """Convert equity curve to drawdown series."""
    equity = pd.Series(equity).astype(float)
    peak = equity.cummax()
    return equity / peak - 1.0


def combine_equal_weight(
    equity_map: dict, initial_capital: float = 100000.0
) -> pd.DataFrame:
    """
    Create equal-weight portfolio from multiple equity curves.

    Args:
        equity_map: Dictionary of symbol -> equity series
        initial_capital: Starting capital

    Returns:
        DataFrame with 'equity' and 'drawdown' columns
    """
    if not equity_map:
        return pd.DataFrame(columns=["equity", "drawdown"])

    N_total = len(equity_map)
    if N_total == 0:
        return pd.DataFrame(columns=["equity", "drawdown"])

    rets = []
    for sym, eq in equity_map.items():
        s = pd.Series(eq).sort_index().astype(float)
        if s.index.duplicated().any():
            s = s[~s.index.duplicated(keep="last")]
        r = s.pct_change()
        if not r.empty:
            r.iloc[0] = 0.0
        rets.append(r.rename(sym))

    R = pd.concat(rets, axis=1, join="outer").sort_index().fillna(0.0)
    port_ret = R.sum(axis=1) / float(N_total)

    equity = (1.0 + port_ret).cumprod() * float(initial_capital)
    drawdown = equity_to_drawdown(equity)
    return pd.DataFrame({"equity": equity, "drawdown": drawdown})
