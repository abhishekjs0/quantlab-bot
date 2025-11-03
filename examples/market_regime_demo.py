#!/usr/bin/env python3
"""
Example script demonstrating market regime detection for NIFTY50 data.

This script shows how to use the market regime detection system to identify
bullish, bearish, and sideways market conditions.
"""

import logging
import sys

import matplotlib.pyplot as plt
import pandas as pd
from core.market_regime import (
    MarketRegime,
    RegimeDetector,
    analyze_regime_history,
    create_trend_following_filter,
)

from data.loaders import load_many_india


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("market_regime_demo.log"),
        ],
    )


def plot_regime_analysis(data: pd.DataFrame, regimes: pd.Series, save_path: str = None):
    """Plot price data with regime overlay."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)

    # Plot price data
    ax1.plot(data.index, data["close"], label="Close Price", color="black", linewidth=1)
    ax1.set_ylabel("Price")
    ax1.set_title("NIFTY50 Price with Market Regime Detection")
    ax1.grid(True, alpha=0.3)

    # Color background based on regime
    regime_colors = {
        MarketRegime.BULLISH: "green",
        MarketRegime.BEARISH: "red",
        MarketRegime.SIDEWAYS: "yellow",
        MarketRegime.UNKNOWN: "gray",
    }

    # Create regime background
    for regime in MarketRegime:
        regime_mask = regimes == regime
        if regime_mask.any():
            regime_dates = regimes[regime_mask].index
            for date in regime_dates:
                ax1.axvspan(
                    date,
                    date + pd.Timedelta(days=1),
                    color=regime_colors[regime],
                    alpha=0.2,
                )

    # Plot regime as categorical data
    regime_numeric = regimes.map(
        {
            MarketRegime.BULLISH: 1,
            MarketRegime.SIDEWAYS: 0,
            MarketRegime.BEARISH: -1,
            MarketRegime.UNKNOWN: -0.5,
        }
    )

    ax2.plot(
        regime_numeric.index,
        regime_numeric.values,
        color="blue",
        linewidth=2,
        marker="o",
        markersize=2,
    )
    ax2.set_ylabel("Regime")
    ax2.set_xlabel("Date")
    ax2.set_ylim(-1.2, 1.2)
    ax2.set_yticks([-1, -0.5, 0, 1])
    ax2.set_yticklabels(["Bearish", "Unknown", "Sideways", "Bullish"])
    ax2.grid(True, alpha=0.3)
    ax2.set_title("Market Regime Classification")

    # Add legend
    legend_elements = [
        plt.Rectangle(
            (0, 0),
            1,
            1,
            color=regime_colors[regime],
            alpha=0.3,
            label=regime.value.capitalize(),
        )
        for regime in MarketRegime
    ]
    ax1.legend(handles=legend_elements, loc="upper left")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to: {save_path}")

    plt.show()


def main():
    """Main function to demonstrate market regime detection."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting market regime detection demo")

    # Load NIFTY50 data (or substitute with available index data)
    symbols = ["NIFTY50"]  # Try to load NIFTY50, fallback to large cap
    try:
        all_data = load_many_india(symbols)
        if "NIFTY50" in all_data:
            data = all_data["NIFTY50"].copy()
        else:
            # Fallback to a large cap stock as proxy
            fallback_symbols = ["RELIANCE", "TCS", "INFY", "HINDUNILVR"]
            logger.warning("NIFTY50 not available, using fallback symbols")
            all_data = load_many_india(fallback_symbols)
            data = all_data[fallback_symbols[0]].copy()
            logger.info(f"Using {fallback_symbols[0]} as market proxy")
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        return

    logger.info(
        f"Loaded {len(data)} rows from {data.index.min()} to {data.index.max()}"
    )

    # Create regime detector
    detector = RegimeDetector(
        short_ma=20,
        medium_ma=50,
        long_ma=200,
        lookback_days=60,
        trend_threshold=0.02,
        sideways_threshold=0.005,
    )

    # Detect regimes
    logger.info("Detecting market regimes...")
    regimes = detector.detect_regime(data)

    # Analyze regime history
    analysis = analyze_regime_history(data, detector)

    # Print regime analysis
    print("\n" + "=" * 60)
    print("MARKET REGIME ANALYSIS")
    print("=" * 60)

    print(
        f"Analysis Period: {data.index.min().strftime('%Y-%m-%d')} to {data.index.max().strftime('%Y-%m-%d')}"
    )
    print(f"Total Days: {len(data)}")

    print("\nRegime Distribution:")
    for regime, count in analysis["regime_counts"].items():
        pct = analysis["regime_percentages"][regime]
        print(f"  {regime.capitalize():<10}: {count:>5} days ({pct:>5.1f}%)")

    print("\nAverage Regime Duration:")
    for regime, duration in analysis["average_durations"].items():
        print(f"  {regime.capitalize():<10}: {duration:>5.1f} days")

    print(f"\nTotal Regime Changes: {analysis['total_regime_changes']}")

    # Current regime analysis
    current_regime = detector.get_current_regime(data)
    regime_strength = detector.get_regime_strength(data)

    print(f"\nCurrent Market Regime: {current_regime.value.upper()}")
    print(f"Regime Strength: {regime_strength:.2f} (0.0 = weak, 1.0 = strong)")

    # Test regime filter for trend following
    trend_filter = create_trend_following_filter()
    should_trade = trend_filter.should_trade(data)
    print(f"Trend Following Trade Signal: {'ALLOW' if should_trade else 'BLOCK'}")

    # Recent regime changes
    print("\nRecent Regime Periods (Last 10):")
    recent_periods = analysis["regime_periods"].tail(10)
    print(f"{'Start':<12} {'End':<12} {'Regime':<10} {'Duration':<10}")
    print("-" * 50)
    for _, period in recent_periods.iterrows():
        print(
            f"{period['start'].strftime('%Y-%m-%d'):<12} "
            f"{period['end'].strftime('%Y-%m-%d'):<12} "
            f"{period['regime'].value.capitalize():<10} "
            f"{period['duration_days']:>8.0f} days"
        )

    # Performance by regime
    print("\nPrice Performance by Regime:")
    print(f"{'Regime':<10} {'Avg Return':<12} {'Volatility':<12} {'Sharpe':<10}")
    print("-" * 50)

    for regime in MarketRegime:
        if regime == MarketRegime.UNKNOWN:
            continue

        regime_mask = regimes == regime
        if regime_mask.sum() > 5:  # Need sufficient data
            regime_data = data[regime_mask]
            regime_returns = regime_data["close"].pct_change().dropna()

            avg_return = regime_returns.mean() * 252  # Annualized
            volatility = regime_returns.std() * (252**0.5)  # Annualized
            sharpe = avg_return / volatility if volatility > 0 else 0

            print(
                f"{regime.value.capitalize():<10} "
                f"{avg_return:>10.1%} "
                f"{volatility:>10.1%} "
                f"{sharpe:>9.2f}"
            )

    # Save detailed results
    results_file = "regime_analysis.csv"
    regime_df = pd.DataFrame(
        {
            "date": regimes.index,
            "regime": regimes.values,
            "close": data["close"],
            "regime_strength": [
                detector.get_regime_strength(data.iloc[: i + 60]) if i >= 60 else 0
                for i in range(len(data))
            ],
        }
    )
    regime_df.to_csv(results_file, index=False)
    logger.info(f"Detailed results saved to {results_file}")

    # Create visualization
    try:
        plot_regime_analysis(data, regimes, "regime_analysis.png")
    except Exception as e:
        logger.warning(f"Could not create plot: {e}")

    print(f"\nDetailed results saved to: {results_file}")
    print("Market regime detection demo complete!")


if __name__ == "__main__":
    main()
