"""
Performance analysis and risk metrics utilities for QuantLab.

Provides comprehensive performance measurement, risk analysis, and
portfolio statistics adapted from backtesting.py standards.
"""

import numpy as np
import pandas as pd


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate simple returns from price series.

    Args:
        prices: Price series

    Returns:
        Returns series
    """
    return prices.pct_change().dropna()


def calculate_log_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate logarithmic returns from price series.

    Args:
        prices: Price series

    Returns:
        Log returns series
    """
    return np.log(prices / prices.shift(1)).dropna()


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculate annualized return.

    Args:
        returns: Daily returns series
        periods_per_year: Trading periods per year (default: 252 for daily)

    Returns:
        Annualized return
    """
    total_return = (1 + returns).prod() - 1
    years = len(returns) / periods_per_year
    return (1 + total_return) ** (1 / years) - 1 if years > 0 else 0


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculate annualized volatility.

    Args:
        returns: Daily returns series
        periods_per_year: Trading periods per year

    Returns:
        Annualized volatility
    """
    return returns.std() * np.sqrt(periods_per_year)


def sharpe_ratio(
    returns: pd.Series, risk_free_rate: float = 0.05, periods_per_year: int = 252
) -> float:
    """
    Calculate Sharpe ratio.

    Args:
        returns: Returns series
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        Sharpe ratio
    """
    excess_returns = returns - risk_free_rate / periods_per_year
    return excess_returns.mean() / excess_returns.std() * np.sqrt(periods_per_year)


def sortino_ratio(
    returns: pd.Series, risk_free_rate: float = 0.05, periods_per_year: int = 252
) -> float:
    """
    Calculate Sortino ratio (downside deviation).

    Args:
        returns: Returns series
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        Sortino ratio
    """
    excess_returns = returns - risk_free_rate / periods_per_year
    downside_returns = excess_returns[excess_returns < 0]
    downside_std = downside_returns.std() if len(downside_returns) > 0 else 0

    if downside_std == 0:
        return float("inf") if excess_returns.mean() > 0 else 0

    return excess_returns.mean() / downside_std * np.sqrt(periods_per_year)


def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculate Calmar ratio (annual return / max drawdown).

    Args:
        returns: Returns series
        periods_per_year: Trading periods per year

    Returns:
        Calmar ratio
    """
    annual_return = annualized_return(returns, periods_per_year)
    max_dd = max_drawdown_from_returns(returns)["max_drawdown"]

    return annual_return / abs(max_dd) if max_dd != 0 else float("inf")


def max_drawdown_from_returns(returns: pd.Series) -> dict:
    """
    Calculate maximum drawdown from returns series.

    Args:
        returns: Returns series

    Returns:
        Dictionary with drawdown statistics
    """
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max

    max_dd = drawdown.min()
    max_dd_end = drawdown.idxmin()

    # Find start of max drawdown period
    max_dd_start = running_max[:max_dd_end].idxmax()

    # Calculate recovery date
    recovery_date = None
    if max_dd_end < len(cumulative) - 1:
        recovery_series = cumulative[max_dd_end:]
        recovery_level = running_max.loc[max_dd_end]
        recovered = recovery_series >= recovery_level
        if recovered.any():
            recovery_date = recovered.idxmax()

    duration = (max_dd_end - max_dd_start).days if hasattr(max_dd_start, "days") else 0

    return {
        "max_drawdown": max_dd,
        "start_date": max_dd_start,
        "end_date": max_dd_end,
        "recovery_date": recovery_date,
        "duration_days": duration,
    }


def value_at_risk(returns: pd.Series, confidence_level: float = 0.05) -> float:
    """
    Calculate Value at Risk (VaR).

    Args:
        returns: Returns series
        confidence_level: Confidence level (default: 5%)

    Returns:
        VaR value
    """
    return returns.quantile(confidence_level)


def conditional_value_at_risk(
    returns: pd.Series, confidence_level: float = 0.05
) -> float:
    """
    Calculate Conditional Value at Risk (CVaR/Expected Shortfall).

    Args:
        returns: Returns series
        confidence_level: Confidence level

    Returns:
        CVaR value
    """
    var = value_at_risk(returns, confidence_level)
    return returns[returns <= var].mean()


def beta(returns: pd.Series, market_returns: pd.Series) -> float:
    """
    Calculate beta relative to market.

    Args:
        returns: Asset returns
        market_returns: Market returns (e.g., NIFTY)

    Returns:
        Beta coefficient
    """
    aligned_returns = pd.concat([returns, market_returns], axis=1).dropna()
    if len(aligned_returns) < 2:
        return 0

    covariance = aligned_returns.cov().iloc[0, 1]
    market_variance = aligned_returns.iloc[:, 1].var()

    return covariance / market_variance if market_variance != 0 else 0


def alpha(
    returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> float:
    """
    Calculate alpha (Jensen's alpha).

    Args:
        returns: Asset returns
        market_returns: Market returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        Alpha value
    """
    asset_return = annualized_return(returns, periods_per_year)
    market_return = annualized_return(market_returns, periods_per_year)
    asset_beta = beta(returns, market_returns)

    expected_return = risk_free_rate + asset_beta * (market_return - risk_free_rate)
    return asset_return - expected_return


def information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Calculate Information Ratio.

    Args:
        returns: Portfolio returns
        benchmark_returns: Benchmark returns

    Returns:
        Information ratio
    """
    active_returns = returns - benchmark_returns
    aligned_returns = active_returns.dropna()

    if len(aligned_returns) == 0 or aligned_returns.std() == 0:
        return 0

    return aligned_returns.mean() / aligned_returns.std()


def tracking_error(
    returns: pd.Series, benchmark_returns: pd.Series, periods_per_year: int = 252
) -> float:
    """
    Calculate tracking error.

    Args:
        returns: Portfolio returns
        benchmark_returns: Benchmark returns
        periods_per_year: Trading periods per year

    Returns:
        Annualized tracking error
    """
    active_returns = returns - benchmark_returns
    return active_returns.std() * np.sqrt(periods_per_year)


def tail_ratio(returns: pd.Series) -> float:
    """
    Calculate tail ratio (95th percentile / 5th percentile).

    Args:
        returns: Returns series

    Returns:
        Tail ratio
    """
    p95 = returns.quantile(0.95)
    p5 = returns.quantile(0.05)

    return abs(p95 / p5) if p5 != 0 else float("inf")


def skewness(returns: pd.Series) -> float:
    """
    Calculate skewness of returns.

    Args:
        returns: Returns series

    Returns:
        Skewness value
    """
    return returns.skew()


def kurtosis(returns: pd.Series) -> float:
    """
    Calculate excess kurtosis of returns.

    Args:
        returns: Returns series

    Returns:
        Excess kurtosis value
    """
    return returns.kurtosis()


def win_rate(returns: pd.Series) -> float:
    """
    Calculate win rate (percentage of positive returns).

    Args:
        returns: Returns series

    Returns:
        Win rate as percentage
    """
    positive_returns = (returns > 0).sum()
    total_returns = len(returns)

    return positive_returns / total_returns * 100 if total_returns > 0 else 0


def profit_factor(returns: pd.Series) -> float:
    """
    Calculate profit factor (gross profit / gross loss).

    Args:
        returns: Returns series

    Returns:
        Profit factor
    """
    gross_profit = returns[returns > 0].sum()
    gross_loss = abs(returns[returns < 0].sum())

    return gross_profit / gross_loss if gross_loss != 0 else float("inf")


def kelly_criterion(returns: pd.Series) -> float:
    """
    Calculate Kelly Criterion for optimal position sizing.

    Args:
        returns: Returns series

    Returns:
        Kelly percentage
    """
    win_rate_pct = win_rate(returns) / 100
    avg_win = returns[returns > 0].mean()
    avg_loss = abs(returns[returns < 0].mean())

    if avg_loss == 0 or win_rate_pct == 1:
        return 0

    win_loss_ratio = avg_win / avg_loss
    kelly = win_rate_pct - (1 - win_rate_pct) / win_loss_ratio

    return max(0, kelly)  # Don't allow negative Kelly


def ulcer_index(returns: pd.Series) -> float:
    """
    Calculate Ulcer Index (downside risk measure).

    Args:
        returns: Returns series

    Returns:
        Ulcer Index value
    """
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max * 100

    return np.sqrt((drawdown**2).mean())


def comprehensive_performance_stats(
    returns: pd.Series,
    benchmark_returns: pd.Series = None,
    risk_free_rate: float = 0.05,
    periods_per_year: int = 252,
) -> dict:
    """
    Calculate comprehensive performance statistics.

    Args:
        returns: Returns series
        benchmark_returns: Optional benchmark returns
        risk_free_rate: Annual risk-free rate
        periods_per_year: Trading periods per year

    Returns:
        Dictionary with all performance metrics
    """
    stats = {
        # Return metrics
        "total_return": (1 + returns).prod() - 1,
        "annualized_return": annualized_return(returns, periods_per_year),
        "annualized_volatility": annualized_volatility(returns, periods_per_year),
        # Risk-adjusted metrics
        "sharpe_ratio": sharpe_ratio(returns, risk_free_rate, periods_per_year),
        "sortino_ratio": sortino_ratio(returns, risk_free_rate, periods_per_year),
        "calmar_ratio": calmar_ratio(returns, periods_per_year),
        # Drawdown metrics
        "max_drawdown": max_drawdown_from_returns(returns)["max_drawdown"],
        "ulcer_index": ulcer_index(returns),
        # Distribution metrics
        "skewness": skewness(returns),
        "kurtosis": kurtosis(returns),
        "var_5pct": value_at_risk(returns, 0.05),
        "cvar_5pct": conditional_value_at_risk(returns, 0.05),
        "tail_ratio": tail_ratio(returns),
        # Trade metrics
        "win_rate": win_rate(returns),
        "profit_factor": profit_factor(returns),
        "kelly_criterion": kelly_criterion(returns),
        # Count metrics
        "total_trades": len(returns),
        "winning_trades": (returns > 0).sum(),
        "losing_trades": (returns < 0).sum(),
    }

    # Add benchmark comparison metrics if provided
    if benchmark_returns is not None:
        stats.update(
            {
                "beta": beta(returns, benchmark_returns),
                "alpha": alpha(
                    returns, benchmark_returns, risk_free_rate, periods_per_year
                ),
                "information_ratio": information_ratio(returns, benchmark_returns),
                "tracking_error": tracking_error(
                    returns, benchmark_returns, periods_per_year
                ),
            }
        )

    return stats


def rolling_performance(
    returns: pd.Series, window: int = 252, metric: str = "sharpe_ratio"
) -> pd.Series:
    """
    Calculate rolling performance metric.

    Args:
        returns: Returns series
        window: Rolling window size
        metric: Performance metric to calculate

    Returns:
        Rolling performance series
    """
    rolling_stats = []

    for i in range(window, len(returns) + 1):
        window_returns = returns.iloc[i - window : i]

        if metric == "sharpe_ratio":
            value = sharpe_ratio(window_returns)
        elif metric == "volatility":
            value = annualized_volatility(window_returns)
        elif metric == "max_drawdown":
            value = max_drawdown_from_returns(window_returns)["max_drawdown"]
        else:
            value = window_returns.mean()  # Default to mean return

        rolling_stats.append(value)

    return pd.Series(rolling_stats, index=returns.index[window - 1 :])


def performance_attribution(returns: pd.Series, weights: pd.DataFrame) -> dict:
    """
    Simple performance attribution analysis.

    Args:
        returns: Portfolio returns
        weights: Asset weights over time

    Returns:
        Attribution statistics
    """
    # This is a simplified version - full attribution would need asset returns
    portfolio_return = returns.sum()
    volatility = returns.std()

    return {
        "portfolio_return": portfolio_return,
        "volatility_contribution": volatility,
        "average_weight": weights.mean().to_dict() if not weights.empty else {},
    }
