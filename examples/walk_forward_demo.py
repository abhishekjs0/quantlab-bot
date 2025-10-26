#!/usr/bin/env python3
"""
Example script demonstrating walk-forward optimization for strategy validation.

This script shows how to use the walk-forward optimization framework to test
a strategy's robustness using rolling windows of training and testing data.
"""

import logging
import sys

import pandas as pd

from core.config import BrokerConfig
from core.walk_forward import WalkForwardOptimizer, analyze_walk_forward_results
from data.loaders import load_many_india
from strategies.ichimoku import IchimokuQuantLabWrapper


def setup_logging():
    """Configure logging for the walk-forward optimization."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("walk_forward_optimization.log"),
        ],
    )


def main():
    """Main function to run walk-forward optimization example."""
    setup_logging()
    logger = logging.getLogger(__name__)

    # Configuration
    symbols = ["RELIANCE", "TCS", "INFY"]  # Use a few symbols for demo
    config = BrokerConfig(
        commission_pct=0.1, initial_capital=100000, qty_pct_of_equity=0.95
    )

    logger.info("Starting walk-forward optimization example")

    # Load data
    logger.info("Loading data...")
    all_data = load_many_india(symbols)

    # For demonstration, use one symbol
    symbol = symbols[0]
    if symbol not in all_data:
        logger.error(f"Symbol {symbol} not found in data")
        return

    data = all_data[symbol].copy()
    logger.info(
        f"Loaded {len(data)} rows for {symbol} from {data.index.min()} to {data.index.max()}"
    )

    # Define parameter grid for optimization
    param_grid = {
        "conversion_length": [7, 9, 12],
        "base_length": [20, 26, 30],
        "use_rsi_filter": [True, False],
        "rsi_min": [45.0, 50.0, 55.0],
        "use_cci_filter": [True, False],
        "cci_min": [-10.0, 0.0, 10.0],
    }

    logger.info(f"Parameter grid has {len(param_grid)} parameters")

    # Create walk-forward optimizer
    optimizer = WalkForwardOptimizer(
        strategy_class=IchimokuQuantLabWrapper,
        data=data,
        config=config,
        train_years=3,  # Shorter for demo
        test_years=1,
        step_years=1,
    )

    # Run walk-forward optimization
    logger.info("Running walk-forward optimization...")
    results = optimizer.run_walk_forward(param_grid=param_grid, optimize_params=True)

    if not results:
        logger.error("No results generated")
        return

    logger.info(f"Generated {len(results)} walk-forward periods")

    # Analyze results
    analysis = analyze_walk_forward_results(results)

    # Print summary
    print("\n" + "=" * 60)
    print("WALK-FORWARD OPTIMIZATION RESULTS")
    print("=" * 60)

    test_perf = analysis["test_performance"]
    print(f"Number of periods: {analysis['num_periods']}")
    print(f"Mean CAGR: {test_perf['mean_cagr']:.2%} ± {test_perf['std_cagr']:.2%}")
    print(
        f"Mean Sharpe: {test_perf['mean_sharpe']:.2f} ± {test_perf['std_sharpe']:.2f}"
    )
    print(f"Mean Max Drawdown: {test_perf['mean_max_drawdown']:.2%}")
    print(f"Worst Drawdown: {test_perf['worst_drawdown']:.2%}")
    print(f"Win Rate: {test_perf['win_rate']:.2%}")
    print(
        f"Profitable Periods: {test_perf['profitable_periods']}/{analysis['num_periods']} ({test_perf['profit_periods_pct']:.1%})"
    )
    print(f"Total Trades: {test_perf['total_trades']}")

    # Stability metrics
    stability = analysis["stability_metrics"]
    print("\\nStability Metrics:")
    print(f"CAGR Stability: {stability['cagr_stability']:.2f}")
    print(f"Sharpe Stability: {stability['sharpe_stability']:.2f}")

    # Period-by-period results
    print("\\nPeriod-by-Period Results:")
    print(
        f"{'Period':<8} {'Train Start':<12} {'Test Start':<12} {'CAGR':<8} {'Sharpe':<8} {'MaxDD':<8} {'Trades':<8}"
    )
    print("-" * 80)

    for result in results:
        print(
            f"{result.period_id:<8} "
            f"{result.train_start.strftime('%Y-%m-%d'):<12} "
            f"{result.test_start.strftime('%Y-%m-%d'):<12} "
            f"{result.test_metrics['cagr']:>7.1%} "
            f"{result.test_metrics['sharpe']:>7.2f} "
            f"{result.test_metrics['max_drawdown']:>7.1%} "
            f"{result.test_metrics['num_trades']:>7.0f}"
        )

    # Best performing period
    best_period = max(results, key=lambda x: x.test_metrics["sharpe"])
    print(f"\\nBest Period (by Sharpe): {best_period.period_id}")
    print(f"Parameters: {best_period.best_params}")
    print(
        f"Test Metrics: CAGR {best_period.test_metrics['cagr']:.2%}, "
        f"Sharpe {best_period.test_metrics['sharpe']:.2f}"
    )

    # Save detailed results
    results_file = "walk_forward_results.csv"

    # Create results DataFrame
    results_data = []
    for result in results:
        row = {
            "period_id": result.period_id,
            "train_start": result.train_start,
            "train_end": result.train_end,
            "test_start": result.test_start,
            "test_end": result.test_end,
        }

        # Add test metrics
        for key, value in result.test_metrics.items():
            row[f"test_{key}"] = value

        # Add train metrics
        for key, value in result.train_metrics.items():
            row[f"train_{key}"] = value

        # Add best parameters
        for key, value in result.best_params.items():
            row[f"param_{key}"] = value

        results_data.append(row)

    results_df = pd.DataFrame(results_data)
    results_df.to_csv(results_file, index=False)
    logger.info(f"Detailed results saved to {results_file}")

    print(f"\\nDetailed results saved to: {results_file}")
    print("Walk-forward optimization complete!")


if __name__ == "__main__":
    main()
