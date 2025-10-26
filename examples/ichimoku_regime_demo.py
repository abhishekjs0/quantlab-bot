#!/usr/bin/env python3
"""
Example script demonstrating Ichimoku strategy with market regime filter.

This script shows how the market regime filter enhances the Ichimoku strategy
by only taking trades during bullish market conditions.
"""

import logging
import sys

import pandas as pd

from core.config import BrokerConfig
from core.engine import BacktestEngine
from data.loaders import load_many_india
from strategies.ichimoku import IchimokuStrategy


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("ichimoku_regime_demo.log"),
        ],
    )


def compare_strategies(
    symbol_data: pd.DataFrame, market_data: pd.DataFrame, config: BrokerConfig
):
    """Compare Ichimoku strategy with and without market regime filter."""

    # Strategy without market regime filter
    basic_strategy = IchimokuStrategy(
        conversion_length=9,
        base_length=26,
        lagging_length=52,
        use_rsi_filter=True,
        use_cci_filter=True,
        use_di_filter=True,
        use_ema20_filter=True,
        use_market_regime_filter=False,  # Disabled
    )

    # Strategy with market regime filter
    regime_strategy = IchimokuStrategy(
        conversion_length=9,
        base_length=26,
        lagging_length=52,
        use_rsi_filter=True,
        use_cci_filter=True,
        use_di_filter=True,
        use_ema20_filter=True,
        use_market_regime_filter=True,  # Enabled
        market_regime_strength_min=0.4,
        market_regime_symbol="NIFTY50",
    )

    # Run backtests
    basic_engine = BacktestEngine(symbol_data, basic_strategy, config)
    basic_result = basic_engine.run()

    regime_engine = BacktestEngine(symbol_data, regime_strategy, config)
    regime_result = regime_engine.run()

    return basic_result, regime_result


def calculate_metrics(result: dict) -> dict:
    """Calculate performance metrics from backtest result."""
    equity = result["equity"]
    trades = result["trades"]

    if len(equity) == 0:
        return {"error": "No equity data"}

    if len(trades) == 0:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "max_drawdown": 0.0,
            "num_trades": 0,
            "win_rate": 0.0,
            "avg_trade": 0.0,
        }

    # Calculate performance metrics
    total_return = (equity.iloc[-1] / equity.iloc[0]) - 1

    # CAGR
    days = (equity.index[-1] - equity.index[0]).days
    years = days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0

    # Max drawdown
    peak = equity.expanding().max()
    drawdown = (equity - peak) / peak
    max_drawdown = drawdown.min()

    # Trade statistics
    win_rate = (
        len(trades[trades["net_pnl"] > 0]) / len(trades) if len(trades) > 0 else 0
    )
    avg_trade = trades["net_pnl"].mean() if len(trades) > 0 else 0

    return {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "num_trades": len(trades),
        "win_rate": win_rate,
        "avg_trade": avg_trade,
    }


def main():
    """Main function to demonstrate ichimoku with market regime filter."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Ichimoku + Market Regime Filter demo")

    # Configuration
    config = BrokerConfig(
        commission_pct=0.1, initial_capital=100000, qty_pct_of_equity=0.95
    )

    # Load data
    symbols = ["RELIANCE", "TCS", "INFY"]  # Test symbols
    market_symbols = ["NIFTY50"]  # Market index

    try:
        # Load symbol data
        symbol_data_dict = load_many_india(symbols)
        market_data_dict = load_many_india(market_symbols)

        # Use first available symbol
        symbol = (
            symbols[0]
            if symbols[0] in symbol_data_dict
            else list(symbol_data_dict.keys())[0]
        )
        symbol_data = symbol_data_dict[symbol].copy()

        # Use market data (fallback to symbol data if needed)
        if "NIFTY50" in market_data_dict:
            market_data = market_data_dict["NIFTY50"].copy()
        else:
            logger.warning("NIFTY50 not available, using symbol data as market proxy")
            market_data = symbol_data.copy()

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return

    logger.info(
        f"Testing on {symbol}: {len(symbol_data)} rows from {symbol_data.index.min()} to {symbol_data.index.max()}"
    )

    # Compare strategies
    logger.info("Running backtests...")
    basic_result, regime_result = compare_strategies(symbol_data, market_data, config)

    # Calculate metrics
    basic_metrics = calculate_metrics(basic_result)
    regime_metrics = calculate_metrics(regime_result)

    # Print comparison
    print("\n" + "=" * 80)
    print("ICHIMOKU STRATEGY: MARKET REGIME FILTER COMPARISON")
    print("=" * 80)

    print(f"Symbol: {symbol}")
    print(
        f"Period: {symbol_data.index.min().strftime('%Y-%m-%d')} to {symbol_data.index.max().strftime('%Y-%m-%d')}"
    )
    print(f"Initial Capital: ${config.initial_capital:,.0f}")

    print("\n" + "-" * 80)
    print(
        f"{'Metric':<25} {'Basic Strategy':<20} {'With Regime Filter':<20} {'Improvement':<15}"
    )
    print("-" * 80)

    # Performance comparison
    metrics_to_compare = [
        ("Total Return", "total_return", "%"),
        ("CAGR", "cagr", "%"),
        ("Max Drawdown", "max_drawdown", "%"),
        ("Number of Trades", "num_trades", ""),
        ("Win Rate", "win_rate", "%"),
        ("Avg Trade P&L", "avg_trade", "$"),
    ]

    for metric_name, metric_key, unit in metrics_to_compare:
        basic_val = basic_metrics.get(metric_key, 0)
        regime_val = regime_metrics.get(metric_key, 0)

        if unit == "%":
            basic_str = f"{basic_val:>18.1%}"
            regime_str = f"{regime_val:>18.1%}"
            if basic_val != 0:
                improvement = ((regime_val - basic_val) / abs(basic_val)) * 100
                improvement_str = f"{improvement:>+13.1f}%"
            else:
                improvement_str = "N/A"
        elif unit == "$":
            basic_str = f"${basic_val:>17,.0f}"
            regime_str = f"${regime_val:>17,.0f}"
            if basic_val != 0:
                improvement = ((regime_val - basic_val) / abs(basic_val)) * 100
                improvement_str = f"{improvement:>+13.1f}%"
            else:
                improvement_str = "N/A"
        else:
            basic_str = f"{basic_val:>18.0f}"
            regime_str = f"{regime_val:>18.0f}"
            if basic_val != 0:
                improvement = ((regime_val - basic_val) / basic_val) * 100
                improvement_str = f"{improvement:>+13.1f}%"
            else:
                improvement_str = "N/A"

        print(f"{metric_name:<25} {basic_str} {regime_str} {improvement_str}")

    # Risk-adjusted metrics
    print("\n" + "-" * 80)
    print("RISK-ADJUSTED ANALYSIS")
    print("-" * 80)

    # Sharpe ratio approximation
    if basic_metrics.get("cagr", 0) != 0 and basic_metrics.get("max_drawdown", 0) != 0:
        basic_sharpe = basic_metrics["cagr"] / abs(basic_metrics["max_drawdown"])
        regime_sharpe = (
            regime_metrics["cagr"] / abs(regime_metrics["max_drawdown"])
            if regime_metrics.get("max_drawdown", 0) != 0
            else 0
        )

        print(
            f"{'Return/Drawdown Ratio':<25} {basic_sharpe:>18.2f} {regime_sharpe:>18.2f} {'':>15}"
        )

    # Trade efficiency
    if basic_metrics.get("num_trades", 0) > 0:
        basic_efficiency = basic_metrics["total_return"] / basic_metrics["num_trades"]
        regime_efficiency = (
            regime_metrics["total_return"] / regime_metrics["num_trades"]
            if regime_metrics.get("num_trades", 0) > 0
            else 0
        )

        print(
            f"{'Return per Trade':<25} {basic_efficiency:>17.1%} {regime_efficiency:>17.1%} {'':>15}"
        )

    # Key insights
    print("\n" + "-" * 80)
    print("KEY INSIGHTS")
    print("-" * 80)

    trade_reduction = basic_metrics.get("num_trades", 0) - regime_metrics.get(
        "num_trades", 0
    )
    trade_reduction_pct = (trade_reduction / basic_metrics.get("num_trades", 1)) * 100

    print(
        f"• Market regime filter reduced trades by {trade_reduction} ({trade_reduction_pct:.1f}%)"
    )

    if regime_metrics.get("win_rate", 0) > basic_metrics.get("win_rate", 0):
        print(
            f"• Win rate improved by {(regime_metrics['win_rate'] - basic_metrics['win_rate']) * 100:.1f} percentage points"
        )

    if regime_metrics.get("max_drawdown", 0) > basic_metrics.get("max_drawdown", 0):
        print(
            f"• Maximum drawdown reduced from {basic_metrics['max_drawdown']:.1%} to {regime_metrics['max_drawdown']:.1%}"
        )

    # Usage recommendations
    print("\n" + "-" * 80)
    print("USAGE RECOMMENDATIONS")
    print("-" * 80)

    if regime_metrics.get("cagr", 0) > basic_metrics.get("cagr", 0):
        print("✓ Market regime filter improved risk-adjusted returns")
        print("✓ Recommended for trend-following in this market")
    else:
        print("⚠ Market regime filter reduced returns in this test period")
        print("⚠ Consider adjusting regime parameters or testing longer periods")

    print("\nOptimal parameters for regime filter:")
    print("  use_market_regime_filter=True")
    print("  market_regime_strength_min=0.4 (adjust based on preference)")
    print("  market_regime_symbol='NIFTY50' (or appropriate market index)")

    # Save results
    results_file = "ichimoku_regime_comparison.csv"
    comparison_df = pd.DataFrame(
        {
            "Strategy": ["Basic Ichimoku", "Ichimoku + Regime Filter"],
            "Total_Return": [
                basic_metrics.get("total_return", 0),
                regime_metrics.get("total_return", 0),
            ],
            "CAGR": [basic_metrics.get("cagr", 0), regime_metrics.get("cagr", 0)],
            "Max_Drawdown": [
                basic_metrics.get("max_drawdown", 0),
                regime_metrics.get("max_drawdown", 0),
            ],
            "Num_Trades": [
                basic_metrics.get("num_trades", 0),
                regime_metrics.get("num_trades", 0),
            ],
            "Win_Rate": [
                basic_metrics.get("win_rate", 0),
                regime_metrics.get("win_rate", 0),
            ],
            "Avg_Trade": [
                basic_metrics.get("avg_trade", 0),
                regime_metrics.get("avg_trade", 0),
            ],
        }
    )
    comparison_df.to_csv(results_file, index=False)

    print(f"\nDetailed results saved to: {results_file}")
    print("Demo complete!")


if __name__ == "__main__":
    main()
