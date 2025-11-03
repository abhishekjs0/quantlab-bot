"""Walk-forward optimization framework for robust strategy testing.

This module implements walk-forward optimization where strategies are trained on
historical data and tested on out-of-sample periods. The framework uses a
4-year training window and 1-year validation period, rolling forward through
the dataset.
"""

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import BrokerConfig
from .engine import BacktestEngine


@dataclass
class WalkForwardPeriod:
    """Represents a single walk-forward period."""

    period_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_data: pd.DataFrame
    test_data: pd.DataFrame


@dataclass
class WalkForwardResult:
    """Results from a single walk-forward period."""

    period_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    # Training results (for parameter optimization)
    train_metrics: dict[str, float]

    # Out-of-sample test results
    test_metrics: dict[str, float]
    test_equity_curve: pd.Series
    test_trades: pd.DataFrame

    # Best parameters found during training
    best_params: dict[str, Any]


class WalkForwardOptimizer:
    """
    Walk-forward optimization framework.

    This class implements a rolling window approach where:
    1. A strategy is trained on N years of data to find optimal parameters
    2. The optimized strategy is tested on the next M months of data
    3. The window rolls forward and the process repeats

    Default configuration:
    - Training window: 4 years
    - Test window: 1 year
    - Step size: 1 year (non-overlapping test periods)
    """

    def __init__(
        self,
        strategy_class: type,
        data: pd.DataFrame,
        config: BrokerConfig,
        train_years: int = 4,
        test_years: int = 1,
        step_years: int = 1,
        min_train_days: int = 1000,
        min_test_days: int = 200,
    ):
        """
        Initialize walk-forward optimizer.

        Args:
            strategy_class: Strategy class to optimize
            data: Historical data with OHLCV columns
            config: Broker configuration
            train_years: Years of data for training window
            test_years: Years of data for test window
            step_years: Years to step forward between periods
            min_train_days: Minimum days required in training set
            min_test_days: Minimum days required in test set
        """
        self.strategy_class = strategy_class
        self.data = data.copy().sort_index()
        self.config = config
        self.train_years = train_years
        self.test_years = test_years
        self.step_years = step_years
        self.min_train_days = min_train_days
        self.min_test_days = min_test_days

        self.logger = logging.getLogger(__name__)

    def create_periods(self) -> list[WalkForwardPeriod]:
        """
        Create walk-forward periods based on available data.

        Returns:
            List of WalkForwardPeriod objects
        """
        periods = []
        data_start = self.data.index.min()
        data_end = self.data.index.max()

        # Start with first possible training window
        current_start = data_start
        period_id = 1

        while True:
            # Define training period
            train_start = current_start
            train_end = train_start + pd.DateOffset(years=self.train_years)

            # Define test period
            test_start = train_end + pd.DateOffset(days=1)
            test_end = test_start + pd.DateOffset(years=self.test_years)

            # Check if we have enough data
            if test_end > data_end:
                break

            # Extract data for this period
            train_mask = (self.data.index >= train_start) & (
                self.data.index <= train_end
            )
            test_mask = (self.data.index >= test_start) & (self.data.index <= test_end)

            train_data = self.data[train_mask].copy()
            test_data = self.data[test_mask].copy()

            # Validate minimum data requirements
            if len(train_data) < self.min_train_days:
                self.logger.warning(
                    f"Period {period_id}: Insufficient training data ({len(train_data)} days)"
                )
                break

            if len(test_data) < self.min_test_days:
                self.logger.warning(
                    f"Period {period_id}: Insufficient test data ({len(test_data)} days)"
                )
                break

            # Create period
            period = WalkForwardPeriod(
                period_id=period_id,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
                train_data=train_data,
                test_data=test_data,
            )
            periods.append(period)

            self.logger.info(
                f"Created period {period_id}: "
                f"Train {train_start.strftime('%Y-%m-%d')} to {train_end.strftime('%Y-%m-%d')} "
                f"({len(train_data)} days), "
                f"Test {test_start.strftime('%Y-%m-%d')} to {test_end.strftime('%Y-%m-%d')} "
                f"({len(test_data)} days)"
            )

            # Move to next period
            current_start += pd.DateOffset(years=self.step_years)
            period_id += 1

        return periods

    def optimize_parameters(
        self, train_data: pd.DataFrame, param_grid: dict[str, list[Any]]
    ) -> tuple[dict[str, Any], dict[str, float]]:
        """
        Optimize strategy parameters on training data.

        Args:
            train_data: Training dataset
            param_grid: Dictionary with parameter names and values to test

        Returns:
            Tuple of (best_parameters, best_metrics)
        """
        best_params = None
        best_metrics = None
        best_score = float("-inf")

        # Create parameter combinations
        param_combinations = self._create_param_combinations(param_grid)

        self.logger.info(f"Testing {len(param_combinations)} parameter combinations")

        for i, params in enumerate(param_combinations):
            try:
                # Create strategy with these parameters
                strategy = self.strategy_class(**params)

                # Run backtest on training data
                engine = BacktestEngine(train_data, strategy, self.config)
                result = engine.run()

                # Calculate optimization score (you can customize this)
                metrics = self._calculate_metrics(result)
                score = self._calculate_optimization_score(metrics)

                # Track best parameters
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    best_metrics = metrics.copy()

                if (i + 1) % 50 == 0:
                    self.logger.info(
                        f"Tested {i + 1}/{len(param_combinations)} combinations"
                    )

            except Exception as e:
                self.logger.warning(
                    f"Parameter combination failed: {params}, Error: {e}"
                )
                continue

        return best_params, best_metrics

    def run_walk_forward(
        self, param_grid: dict[str, list[Any]], optimize_params: bool = True
    ) -> list[WalkForwardResult]:
        """
        Run complete walk-forward optimization.

        Args:
            param_grid: Parameters to optimize during training
            optimize_params: Whether to optimize parameters or use defaults

        Returns:
            List of WalkForwardResult objects
        """
        periods = self.create_periods()
        results = []

        self.logger.info(
            f"Starting walk-forward optimization with {len(periods)} periods"
        )

        for period in periods:
            self.logger.info(f"Processing period {period.period_id}")

            # Optimize parameters on training data
            if optimize_params and param_grid:
                best_params, train_metrics = self.optimize_parameters(
                    period.train_data, param_grid
                )
            else:
                # Use default parameters
                best_params = {}
                strategy = self.strategy_class(**best_params)
                engine = BacktestEngine(period.train_data, strategy, self.config)
                train_result = engine.run()
                train_metrics = self._calculate_metrics(train_result)

            # Test optimized strategy on out-of-sample data
            test_strategy = self.strategy_class(**best_params)
            test_engine = BacktestEngine(period.test_data, test_strategy, self.config)
            test_result = test_engine.run()
            test_metrics = self._calculate_metrics(test_result)

            # Create result object
            result = WalkForwardResult(
                period_id=period.period_id,
                train_start=period.train_start,
                train_end=period.train_end,
                test_start=period.test_start,
                test_end=period.test_end,
                train_metrics=train_metrics,
                test_metrics=test_metrics,
                test_equity_curve=test_result["equity"],
                test_trades=test_result["trades"],
                best_params=best_params,
            )
            results.append(result)

            self.logger.info(
                f"Period {period.period_id} complete: "
                f"Test CAGR {test_metrics.get('cagr', 0):.2%}, "
                f"Sharpe {test_metrics.get('sharpe', 0):.2f}"
            )

        return results

    def _create_param_combinations(
        self, param_grid: dict[str, list[Any]]
    ) -> list[dict[str, Any]]:
        """Create all combinations of parameters."""
        import itertools

        keys = list(param_grid.keys())
        values = list(param_grid.values())

        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))

        return combinations

    def _calculate_metrics(self, backtest_result: dict[str, Any]) -> dict[str, float]:
        """Calculate performance metrics from backtest result."""
        equity = backtest_result["equity"]
        trades = backtest_result["trades"]

        # Basic performance metrics
        total_return = (equity.iloc[-1] / equity.iloc[0]) - 1

        # Calculate CAGR
        days = (equity.index[-1] - equity.index[0]).days
        years = days / 365.25
        cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0

        # Calculate volatility and Sharpe ratio
        returns = equity.pct_change().dropna()
        volatility = returns.std() * (252**0.5)  # Annualized
        sharpe = (cagr / volatility) if volatility > 0 else 0

        # Calculate max drawdown
        peak = equity.expanding().max()
        drawdown = (equity - peak) / peak
        max_drawdown = drawdown.min()

        # Trade statistics
        win_rate = (
            len(trades[trades["net_pnl"] > 0]) / len(trades) if len(trades) > 0 else 0
        )
        avg_win = (
            trades[trades["net_pnl"] > 0]["net_pnl"].mean() if len(trades) > 0 else 0
        )
        avg_loss = (
            trades[trades["net_pnl"] < 0]["net_pnl"].mean() if len(trades) > 0 else 0
        )
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

        return {
            "total_return": total_return,
            "cagr": cagr,
            "volatility": volatility,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "win_rate": win_rate,
            "num_trades": len(trades),
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
        }

    def _calculate_optimization_score(self, metrics: dict[str, float]) -> float:
        """
        Calculate optimization score for parameter selection.

        You can customize this function based on your optimization objectives.
        Default uses a combination of Sharpe ratio and drawdown.
        """
        sharpe = metrics.get("sharpe", 0)
        max_dd = abs(metrics.get("max_drawdown", 1))
        win_rate = metrics.get("win_rate", 0)

        # Penalize high drawdown and reward high Sharpe and win rate
        score = sharpe * (1 - max_dd) * (1 + win_rate)
        return score


def analyze_walk_forward_results(results: list[WalkForwardResult]) -> dict[str, Any]:
    """
    Analyze walk-forward optimization results and generate summary statistics.

    Args:
        results: List of WalkForwardResult objects

    Returns:
        Dictionary with summary statistics and analysis
    """
    if not results:
        return {"error": "No results to analyze"}

    # Aggregate metrics across all periods
    test_metrics = []
    train_metrics = []

    for result in results:
        test_metrics.append(result.test_metrics)
        train_metrics.append(result.train_metrics)

    # Convert to DataFrame for easier analysis
    test_df = pd.DataFrame(test_metrics)
    train_df = pd.DataFrame(train_metrics)

    # Calculate summary statistics
    summary = {
        "num_periods": len(results),
        "test_performance": {
            "mean_cagr": test_df["cagr"].mean(),
            "std_cagr": test_df["cagr"].std(),
            "mean_sharpe": test_df["sharpe"].mean(),
            "std_sharpe": test_df["sharpe"].std(),
            "mean_max_drawdown": test_df["max_drawdown"].mean(),
            "worst_drawdown": test_df["max_drawdown"].min(),
            "win_rate": test_df["win_rate"].mean(),
            "total_trades": test_df["num_trades"].sum(),
            "profitable_periods": (test_df["cagr"] > 0).sum(),
            "profit_periods_pct": (test_df["cagr"] > 0).mean(),
        },
        "train_performance": {
            "mean_cagr": train_df["cagr"].mean(),
            "mean_sharpe": train_df["sharpe"].mean(),
            "mean_max_drawdown": train_df["max_drawdown"].mean(),
        },
        "stability_metrics": {
            "cagr_stability": (
                1 - (test_df["cagr"].std() / abs(test_df["cagr"].mean()))
                if test_df["cagr"].mean() != 0
                else 0
            ),
            "sharpe_stability": (
                1 - (test_df["sharpe"].std() / abs(test_df["sharpe"].mean()))
                if test_df["sharpe"].mean() != 0
                else 0
            ),
        },
    }

    # Combine equity curves
    combined_equity = pd.Series(dtype=float)
    for result in results:
        combined_equity = pd.concat([combined_equity, result.test_equity_curve])

    summary["combined_equity_curve"] = combined_equity
    summary["period_results"] = results

    return summary
