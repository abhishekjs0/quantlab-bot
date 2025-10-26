#!/usr/bin/env python3
"""
Mega Basket Backtest with Automatic Dashboard Generation

This script runs a comprehensive backtest on the mega basket (70+ stocks)
and automatically generates the improved dashboard with all enhancements:
- Monthly P&L with realized/unrealized breakdown
- Comprehensive key metrics panel with 1Y/3Y/5Y toggles
- Enhanced chart styling and visualizations
- Professional financial analytics

Usage:
    python run_mega_basket_backtest.py

Or with custom parameters:
    python run_mega_basket_backtest.py --strategy ichimoku --interval 1d --period max
"""

import argparse
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from runners.run_basket import run_basket


def main():
    """Run mega basket backtest with automatic dashboard generation."""

    parser = argparse.ArgumentParser(
        description="Run mega basket backtest with automatic dashboard generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_mega_basket_backtest.py
  python run_mega_basket_backtest.py --strategy donchian --interval 1d
  python run_mega_basket_backtest.py --strategy ichimoku --period 5y
        """,
    )

    parser.add_argument(
        "--strategy", default="ichimoku", help="Strategy to use (default: ichimoku)"
    )

    parser.add_argument(
        "--params",
        default='{"conversion_line": 9, "base_line": 26, "leading_span_b": 52, "displacement": 26}',
        help="Strategy parameters as JSON string",
    )

    parser.add_argument("--interval", default="1d", help="Time interval (default: 1d)")

    parser.add_argument(
        "--period", default="max", help="Historical period (default: max)"
    )

    parser.add_argument(
        "--windows",
        nargs="*",
        type=int,
        default=[1, 3, 5],
        help="Analysis windows in years (default: 1 3 5)",
    )

    parser.add_argument(
        "--cache-only", action="store_true", help="Use only cached data"
    )

    args = parser.parse_args()

    # Convert windows list to tuple
    windows_years = tuple(args.windows)

    print("🚀 Starting Mega Basket Backtest with Dashboard Generation")
    print("=" * 60)
    print("📊 Basket: Mega (70+ stocks)")
    print(f"🔧 Strategy: {args.strategy}")
    print(f"📈 Parameters: {args.params}")
    print(f"⏰ Interval: {args.interval}")
    print(f"📅 Period: {args.period}")
    print(f"🔍 Analysis Windows: {list(windows_years)} years")
    print(f"💾 Cache Only: {args.cache_only}")
    print("=" * 60)

    try:
        # Run the backtest with mega basket
        run_basket(
            basket_size="mega",  # Use mega basket
            strategy_name=args.strategy,
            params_json=args.params,
            interval=args.interval,
            period=args.period,
            windows_years=windows_years,
            use_cache_only=args.cache_only,
            use_portfolio_csv=True,  # Generate portfolio CSVs for dashboard
        )

        print("\n🎉 Mega Basket Backtest Completed Successfully!")
        print("📊 Dashboard with all improvements has been automatically generated")
        print("🌐 Check the reports directory for the HTML dashboard file")

    except KeyboardInterrupt:
        print("\n⚠️ Backtest interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Backtest failed: {e}")
        import traceback

        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
