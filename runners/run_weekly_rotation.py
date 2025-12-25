#!/usr/bin/env python3
"""
Weekly Rotation Runner - Uses standard_run_basket with pre-computed rankings

This script:
1. Loads all symbols' daily data
2. Computes weekly returns and rankings
3. Populates the strategy's ranking cache
4. Runs standard_run_basket.py with the weekly_rotation strategy

Usage:
    python runners/run_weekly_rotation.py --basket_file data/basket_main.txt --mode mean_reversion
    python runners/run_weekly_rotation.py --basket_size main --mode momentum --select_pct 15
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import get_basket_file, BASKET_FILES
from core.loaders import load_many_india
from strategies.weekly_rotation import (
    WeeklyRotationStrategy,
    compute_weekly_returns,
    compute_ranking_cache,
)


def load_basket(basket_file: str) -> list[str]:
    """Load symbols from basket file."""
    path = Path(basket_file)
    if not path.exists():
        from config import DATA_DIR
        path = DATA_DIR / basket_file
    
    symbols = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and line.lower() != "symbol":
                symbols.append(line)
    return symbols


def main():
    parser = argparse.ArgumentParser(description="Weekly Rotation Strategy Runner")
    
    basket_group = parser.add_mutually_exclusive_group()
    basket_group.add_argument("--basket_file", help="Path to basket file")
    basket_group.add_argument("--basket_size", choices=list(BASKET_FILES.keys()), help="Predefined basket")
    
    parser.add_argument("--mode", choices=["momentum", "mean_reversion"], default="mean_reversion",
                        help="Selection mode: momentum (top performers) or mean_reversion (bottom performers)")
    parser.add_argument("--select_pct", type=float, default=10.0,
                        help="Percentage of stocks to select (default: 10)")
    parser.add_argument("--use_adx_filter", action="store_true",
                        help="Enable ADX filter (ADX > threshold)")
    parser.add_argument("--adx_threshold", type=float, default=25.0,
                        help="ADX threshold for filter (default: 25)")
    parser.add_argument("--cache_dir", default="data/cache",
                        help="Cache directory for data")
    parser.add_argument("--period", default="max",
                        help="Backtest period ('1y', '3y', '5y', 'max') - default: max")
    
    args = parser.parse_args()
    
    # Get basket file
    basket_file = args.basket_file or str(get_basket_file(args.basket_size or "main"))
    
    print(f"📊 Weekly Rotation Strategy Runner")
    print(f"   Mode: {args.mode}")
    print(f"   Select: {args.select_pct}%")
    print(f"   Basket: {basket_file}")
    print()
    
    # Load symbols
    symbols = load_basket(basket_file)
    print(f"📥 Loading data for {len(symbols)} symbols...")
    
    # Load daily data
    daily_data = load_many_india(
        symbols, 
        interval="1d", 
        cache=True, 
        cache_dir=args.cache_dir,
        use_cache_only=True
    )
    
    # Compute weekly returns
    print("📈 Computing weekly returns...")
    weekly_returns = compute_weekly_returns(daily_data)
    print(f"   {len(weekly_returns)} symbols with weekly data")
    
    # Compute ranking cache
    print(f"📊 Computing rankings ({args.mode}, top/bottom {args.select_pct}%)...")
    ranking_cache = compute_ranking_cache(
        weekly_returns,
        mode=args.mode,
        select_pct=args.select_pct
    )
    print(f"   {len(ranking_cache)} ranking entries")
    
    # Count entry signals
    entry_count = sum(1 for v in ranking_cache.values() if v.get("should_enter", False))
    print(f"   {entry_count} entry signals")
    
    # Populate strategy cache
    WeeklyRotationStrategy.set_ranking_cache(ranking_cache)
    WeeklyRotationStrategy.set_weekly_returns(weekly_returns)
    
    # Build strategy name and params
    strategy_name = f"weekly_{args.mode}"
    params = {
        "mode": args.mode,
        "select_pct": args.select_pct,
        "use_adx_filter": args.use_adx_filter,
        "adx_threshold": args.adx_threshold,
    }
    
    import json
    params_json = json.dumps(params)
    
    print()
    print(f"🚀 Running standard_run_basket.py with {strategy_name}...")
    print(f"   Params: {params_json}")
    print()
    
    # Import and run standard_run_basket
    from runners.standard_run_basket import run_basket
    
    run_basket(
        basket_file=basket_file,
        strategy_name=strategy_name,
        params_json=params_json,
        interval="1d",  # Daily data for the strategy
        period=args.period,  # Include MAX window for full analysis
        use_cache_only=True,
        cache_dir=args.cache_dir,
    )
    
    # Clear cache after run
    WeeklyRotationStrategy.clear_cache()


if __name__ == "__main__":
    main()
