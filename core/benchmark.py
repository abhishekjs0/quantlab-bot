# core/benchmark.py
"""
Benchmark calculation module for alpha/beta analysis.
Uses Reliance Industries Limited as market benchmark for Indian stocks.
RELIANCE is th            # Calculate beta using linear regression
        # beta = covariance(portfolio, benchmark) / variance(benchmark)

        # Perform linear regression: y = alpha + beta * x + errora = covariance(portfolio, benchmark) / variance(benchmark)
        X = aligned_data["benchmark_returns"].values.reshape(-1, 1)
        y = aligned_data["portfolio_returns"].values

        # Add constant for alpha (intercept)
        X_with_const = np.column_stack([np.ones(len(X)), X])est stock by market cap and serves as a good market proxy.
"""

import logging
import os
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Default benchmark configuration
DEFAULT_BENCHMARK_FILE = "data/cache/dhan_historical_10576.csv"
BENCHMARK_SYMBOL = "NIFTYBEES"  # NIFTY 50 ETF - NSE ID 10576


class BenchmarkError(Exception):
    """Custom exception for benchmark calculation errors."""

    pass


def load_benchmark_data(
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
    start_date=None,
    end_date=None,
) -> pd.DataFrame:
    """
    Load and prepare benchmark data from cache.

    Args:
        benchmark_file: Path to benchmark CSV file
        start_date: Optional start date filter (YYYY-MM-DD)
        end_date: Optional end date filter (YYYY-MM-DD)

    Returns:
        DataFrame with date index and price data

    Raises:
        BenchmarkError: If benchmark data cannot be loaded
    """
    try:
        if not os.path.exists(benchmark_file):
            raise BenchmarkError(f"Benchmark file not found: {benchmark_file}")

        # Load benchmark data
        bench_df = pd.read_csv(benchmark_file)

        # Convert date column and set as index
        bench_df["date"] = pd.to_datetime(bench_df["date"])
        bench_df.set_index("date", inplace=True)

        # Apply date filtering if provided
        if start_date:
            bench_df = bench_df[bench_df.index >= pd.to_datetime(start_date)]
        if end_date:
            bench_df = bench_df[bench_df.index <= pd.to_datetime(end_date)]

        if len(bench_df) == 0:
            raise BenchmarkError(
                "No benchmark data available for the specified date range"
            )

        logger.info(
            f"Loaded benchmark data: {len(bench_df)} records from {bench_df.index.min()} to {bench_df.index.max()}"
        )
        return bench_df

    except Exception as e:
        raise BenchmarkError(f"Failed to load benchmark data: {e}")


def calculate_returns(price_series: pd.Series) -> pd.Series:
    """
    Calculate daily returns from price series.

    Args:
        price_series: Series of prices with datetime index

    Returns:
        Series of daily returns (excluding first NaN value)
    """
    returns = price_series.pct_change().dropna()
    return returns


def calculate_alpha_beta(
    portfolio_equity: pd.DataFrame,
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
    risk_free_rate: float = 0.06,  # 6% annual risk-free rate
) -> tuple[float, float, float, dict]:
    """
    Calculate alpha and beta for portfolio against benchmark.

    Args:
        portfolio_equity: DataFrame with equity curve (should have 'equity' column or similar)
        benchmark_file: Path to benchmark data file
        risk_free_rate: Annual risk-free rate for alpha calculation (default 6%)

    Returns:
        Tuple of (alpha_annual, beta, r_squared, stats_dict)
        - alpha_annual: Annualized alpha (excess return over benchmark)
        - beta: Portfolio beta (sensitivity to market moves)
        - r_squared: R-squared of the regression
        - stats_dict: Additional statistics (correlation, tracking_error, etc.)

    Raises:
        BenchmarkError: If calculation fails
    """
    try:
        # Prepare portfolio data
        if isinstance(portfolio_equity.index, pd.DatetimeIndex):
            portfolio_df = portfolio_equity.copy()
        else:
            # Try to convert index to datetime
            portfolio_df = portfolio_equity.copy()
            portfolio_df.index = pd.to_datetime(portfolio_df.index)

        # Find equity column (could be 'equity', 'Equity', or similar)
        equity_col = None
        for col in ["equity", "Equity", "portfolio_value", "total_value"]:
            if col in portfolio_df.columns:
                equity_col = col
                break

        if equity_col is None:
            # Try to use the first numeric column
            numeric_cols = portfolio_df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                equity_col = numeric_cols[0]
            else:
                raise BenchmarkError(
                    "No suitable equity column found in portfolio data"
                )

        # Load benchmark data for the same period
        start_date = portfolio_df.index.min().strftime("%Y-%m-%d")
        end_date = portfolio_df.index.max().strftime("%Y-%m-%d")

        bench_df = load_benchmark_data(benchmark_file, start_date, end_date)

        # Calculate daily returns
        portfolio_returns = calculate_returns(portfolio_df[equity_col])
        benchmark_returns = calculate_returns(bench_df["close"])

        # Align dates (inner join to get common dates only)
        aligned_data = pd.concat(
            [portfolio_returns, benchmark_returns], axis=1, join="inner"
        )
        aligned_data.columns = ["portfolio_returns", "benchmark_returns"]
        aligned_data = aligned_data.dropna()

        if len(aligned_data) < 10:
            raise BenchmarkError(
                f"Insufficient overlapping data points: {len(aligned_data)}"
            )

        # Calculate beta using linear regression
        # beta = covariance(portfolio, benchmark) / variance(benchmark)

        # Perform linear regression: y = alpha + beta * x + error
        regression_result = stats.linregress(
            aligned_data["benchmark_returns"], aligned_data["portfolio_returns"]
        )

        beta = regression_result.slope
        r_squared = regression_result.rvalue**2

        # Convert daily alpha to annual
        trading_days_per_year = 252
        daily_rf_rate = risk_free_rate / trading_days_per_year

        # Alpha = (portfolio return - risk free rate) - beta * (benchmark return - risk free rate)
        # Since we calculated daily alpha from regression, we need to adjust it
        portfolio_mean_return = aligned_data["portfolio_returns"].mean()
        benchmark_mean_return = aligned_data["benchmark_returns"].mean()

        # Calculate excess returns
        portfolio_excess_return = portfolio_mean_return - daily_rf_rate
        benchmark_excess_return = benchmark_mean_return - daily_rf_rate

        # Jensen's Alpha: actual excess return - (beta * benchmark excess return)
        alpha_daily_jensen = portfolio_excess_return - (beta * benchmark_excess_return)
        alpha_annual = alpha_daily_jensen * trading_days_per_year

        # Calculate additional statistics
        correlation = aligned_data["portfolio_returns"].corr(
            aligned_data["benchmark_returns"]
        )

        # Tracking error (standard deviation of excess returns)
        excess_returns = (
            aligned_data["portfolio_returns"] - aligned_data["benchmark_returns"]
        )
        tracking_error_daily = excess_returns.std()
        tracking_error_annual = tracking_error_daily * np.sqrt(trading_days_per_year)

        # Information ratio (alpha / tracking error)
        information_ratio = (
            alpha_annual / tracking_error_annual if tracking_error_annual != 0 else 0.0
        )

        stats_dict = {
            "correlation": correlation,
            "tracking_error_annual": tracking_error_annual,
            "information_ratio": information_ratio,
            "data_points": len(aligned_data),
            "start_date": aligned_data.index.min(),
            "end_date": aligned_data.index.max(),
            "portfolio_mean_return_daily": portfolio_mean_return,
            "benchmark_mean_return_daily": benchmark_mean_return,
            "risk_free_rate_annual": risk_free_rate,
        }

        logger.info(
            f"Alpha/Beta calculation completed: α={alpha_annual:.4f}, β={beta:.4f}, R²={r_squared:.4f}"
        )

        return alpha_annual, beta, r_squared, stats_dict

    except Exception as e:
        logger.error(f"Alpha/beta calculation failed: {e}")
        raise BenchmarkError(f"Alpha/beta calculation failed: {e}")


def calculate_portfolio_alpha_beta(
    portfolio_curves: dict,
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
    risk_free_rate: float = 0.06,
) -> pd.DataFrame:
    """
    Calculate alpha and beta for multiple portfolio time windows.

    Args:
        portfolio_curves: dict of {window_label: portfolio_equity_df}
        benchmark_file: Path to benchmark data file
        risk_free_rate: Annual risk-free rate

    Returns:
        DataFrame with alpha/beta results by window
    """
    results = []

    for window_label, portfolio_equity in portfolio_curves.items():
        try:
            alpha, beta, r_squared, stats = calculate_alpha_beta(
                portfolio_equity, benchmark_file, risk_free_rate
            )

            result = {
                "Window": window_label,
                "Alpha": alpha,
                "Beta": beta,
                "R_Squared": r_squared,
                "Correlation": stats["correlation"],
                "Tracking_Error": stats["tracking_error_annual"],
                "Information_Ratio": stats["information_ratio"],
                "Data_Points": stats["data_points"],
            }
            results.append(result)

        except BenchmarkError as e:
            logger.warning(f"Failed to calculate alpha/beta for {window_label}: {e}")
            # Add row with zeros for failed calculations
            results.append(
                {
                    "Window": window_label,
                    "Alpha": 0.0,
                    "Beta": 0.0,
                    "R_Squared": 0.0,
                    "Correlation": 0.0,
                    "Tracking_Error": 0.0,
                    "Information_Ratio": 0.0,
                    "Data_Points": 0,
                }
            )

    return pd.DataFrame(results)


# Convenience function for testing
def test_benchmark_calculations():
    """Test function to verify benchmark calculations are working."""
    try:
        # Load benchmark data
        bench_df = load_benchmark_data()
        print(f"✅ Loaded benchmark data: {len(bench_df)} records")
        print(f"   Date range: {bench_df.index.min()} to {bench_df.index.max()}")

        # Calculate sample returns
        returns = calculate_returns(bench_df["close"])
        print(
            f"✅ Calculated returns: {len(returns)} records, mean={returns.mean():.6f}"
        )

        return True

    except Exception as e:
        print(f"❌ Benchmark test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the benchmark functionality
    test_benchmark_calculations()
