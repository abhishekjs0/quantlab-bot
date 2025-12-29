#!/usr/bin/env python3
"""
Overnight vs Intraday Analysis
==============================
Analyzes the contribution of overnight gaps vs intraday moves for stock baskets.

Definitions:
- Overnight: Previous day close -> Current day open (gap return)
- Intraday: Current day open -> Current day close (session return)

Output includes:
- Daily breakdown
- Weekly aggregates (Grand Total, Weekly Total, Running Totals)
"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import numpy as np

# Configuration
CACHE_DIR = Path("data/cache")
BASKETS = {
    "largecap_highbeta": "data/basket_largecap_highbeta.txt",
    "largecap_lowbeta": "data/basket_largecap_lowbeta.txt",
    "midcap_highbeta": "data/basket_midcap_highbeta.txt",
    "midcap_lowbeta": "data/basket_midcap_lowbeta.txt",
    "smallcap_highbeta": "data/basket_smallcap_highbeta.txt",
    "smallcap_lowbeta": "data/basket_smallcap_lowbeta.txt",
}


def load_basket(basket_path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(basket_path) as f:
        return [line.strip() for line in f if line.strip()]


def find_symbol_cache_file(symbol: str, cache_dir: Path) -> Optional[str]:
    """Find the cached CSV file for a symbol."""
    pattern = str(cache_dir / f"dhan_*_{symbol}_1d.csv")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def load_ohlc_data(symbol: str, cache_dir: Path) -> Optional[pd.DataFrame]:
    """Load OHLC data for a symbol from cache."""
    cache_file = find_symbol_cache_file(symbol, cache_dir)
    if not cache_file or not os.path.exists(cache_file):
        return None
    
    try:
        df = pd.read_csv(cache_file)
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        
        # Ensure required columns exist
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return None
        
        return df.sort_index()
    except Exception as e:
        print(f"Error loading {symbol}: {e}")
        return None


def calculate_overnight_intraday_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate overnight and intraday returns for each day.
    
    Overnight: (Open - Previous Close) / Previous Close * 100
    Intraday: (Close - Open) / Open * 100
    """
    df = df.copy()
    
    # Intraday return: open to close
    df["intraday_pct"] = (df["close"] - df["open"]) / df["open"] * 100
    
    # Overnight return: previous close to today's open
    df["prev_close"] = df["close"].shift(1)
    df["overnight_pct"] = (df["open"] - df["prev_close"]) / df["prev_close"] * 100
    
    # Total daily return
    df["total_pct"] = (df["close"] - df["prev_close"]) / df["prev_close"] * 100
    
    return df.dropna()


def calculate_basket_returns(symbols: List[str], cache_dir: Path) -> pd.DataFrame:
    """
    Calculate equal-weighted average returns for a basket of symbols.
    """
    all_returns = []
    loaded_symbols = []
    
    for symbol in symbols:
        df = load_ohlc_data(symbol, cache_dir)
        if df is not None and len(df) > 1:
            returns = calculate_overnight_intraday_returns(df)
            if not returns.empty:
                # Remove duplicates in index
                returns = returns[~returns.index.duplicated(keep='first')]
                returns = returns[["overnight_pct", "intraday_pct", "total_pct"]]
                returns.columns = [f"{symbol}_{col}" for col in returns.columns]
                all_returns.append(returns)
                loaded_symbols.append(symbol)
    
    if not all_returns:
        return pd.DataFrame()
    
    # Combine all symbols - use join to handle different date ranges
    combined = all_returns[0]
    for df in all_returns[1:]:
        combined = combined.join(df, how='outer')
    
    # Calculate equal-weighted basket returns
    overnight_cols = [col for col in combined.columns if "_overnight_pct" in col]
    intraday_cols = [col for col in combined.columns if "_intraday_pct" in col]
    total_cols = [col for col in combined.columns if "_total_pct" in col]
    
    result = pd.DataFrame(index=combined.index)
    result["overnight_pct"] = combined[overnight_cols].mean(axis=1)
    result["intraday_pct"] = combined[intraday_cols].mean(axis=1)
    result["total_pct"] = combined[total_cols].mean(axis=1)
    result["num_symbols"] = combined[overnight_cols].notna().sum(axis=1)
    
    # Remove any remaining duplicates
    result = result[~result.index.duplicated(keep='first')]
    result = result.sort_index()
    
    return result


def aggregate_to_weekly(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate daily returns to weekly summary.
    """
    df = daily_returns.copy()
    df["year"] = df.index.year
    df["week"] = df.index.isocalendar().week.values
    df["year_week"] = df["year"].astype(str) + "-W" + df["week"].astype(str).str.zfill(2)
    
    # Weekly aggregation - sum of daily returns
    weekly = df.groupby("year_week").agg({
        "overnight_pct": "sum",  # Grand Total Overnight
        "intraday_pct": "sum",   # Grand Total Intraday
        "total_pct": "sum",      # Weekly Total
        "num_symbols": "mean"    # Avg symbols
    }).reset_index()
    
    weekly.columns = ["year_week", "grand_overnight", "grand_intraday", "weekly_total", "avg_symbols"]
    
    # Calculate running totals
    weekly["running_overnight"] = weekly["grand_overnight"].cumsum()
    weekly["running_intraday"] = weekly["grand_intraday"].cumsum()
    weekly["running_total"] = weekly["weekly_total"].cumsum()
    
    return weekly


def aggregate_by_day_of_week(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate returns by day of week.
    """
    df = daily_returns.copy()
    df["day_of_week"] = df.index.day_name()
    df["day_num"] = df.index.dayofweek
    
    # Aggregate by day
    by_day = df.groupby(["day_num", "day_of_week"]).agg({
        "overnight_pct": ["mean", "sum", "std", "count"],
        "intraday_pct": ["mean", "sum", "std"],
        "total_pct": ["mean", "sum", "std"]
    })
    
    by_day.columns = ["_".join(col).strip() for col in by_day.columns.values]
    by_day = by_day.reset_index().sort_values("day_num")
    
    return by_day


def aggregate_by_month(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate returns by month.
    """
    df = daily_returns.copy()
    df["year_month"] = df.index.to_period("M").astype(str)
    
    monthly = df.groupby("year_month").agg({
        "overnight_pct": ["sum", "mean", "std"],
        "intraday_pct": ["sum", "mean", "std"],
        "total_pct": ["sum", "mean", "std"],
        "num_symbols": "mean"
    })
    
    monthly.columns = ["_".join(col).strip() for col in monthly.columns.values]
    monthly = monthly.reset_index()
    
    return monthly


def aggregate_by_year(daily_returns: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate returns by year.
    """
    df = daily_returns.copy()
    df["year"] = df.index.year
    
    yearly = df.groupby("year").agg({
        "overnight_pct": ["sum", "mean", "std", "count"],
        "intraday_pct": ["sum", "mean", "std"],
        "total_pct": ["sum", "mean", "std"]
    })
    
    yearly.columns = ["_".join(col).strip() for col in yearly.columns.values]
    yearly = yearly.reset_index()
    
    return yearly


def generate_summary_stats(daily_returns: pd.DataFrame) -> Dict[str, Any]:
    """
    Generate summary statistics for the analysis.
    """
    stats = {
        "date_range": f"{daily_returns.index.min().date()} to {daily_returns.index.max().date()}",
        "total_days": len(daily_returns),
        
        # Overnight stats
        "overnight_total": daily_returns["overnight_pct"].sum(),
        "overnight_mean": daily_returns["overnight_pct"].mean(),
        "overnight_std": daily_returns["overnight_pct"].std(),
        "overnight_positive_days": (daily_returns["overnight_pct"] > 0).sum(),
        "overnight_negative_days": (daily_returns["overnight_pct"] < 0).sum(),
        
        # Intraday stats
        "intraday_total": daily_returns["intraday_pct"].sum(),
        "intraday_mean": daily_returns["intraday_pct"].mean(),
        "intraday_std": daily_returns["intraday_pct"].std(),
        "intraday_positive_days": (daily_returns["intraday_pct"] > 0).sum(),
        "intraday_negative_days": (daily_returns["intraday_pct"] < 0).sum(),
        
        # Total stats
        "total_return": daily_returns["total_pct"].sum(),
        "total_mean": daily_returns["total_pct"].mean(),
        "total_std": daily_returns["total_pct"].std(),
    }
    
    # Contribution analysis
    if stats["total_return"] != 0:
        stats["overnight_contribution"] = (stats["overnight_total"] / stats["total_return"]) * 100
        stats["intraday_contribution"] = (stats["intraday_total"] / stats["total_return"]) * 100
    else:
        stats["overnight_contribution"] = 0
        stats["intraday_contribution"] = 0
    
    return stats


def print_summary(basket_name: str, stats: dict, weekly: pd.DataFrame):
    """Print formatted summary."""
    print("\n" + "=" * 80)
    print(f"BASKET: {basket_name.upper()}")
    print("=" * 80)
    
    print(f"\n📅 Date Range: {stats['date_range']}")
    print(f"📊 Total Trading Days: {stats['total_days']}")
    
    print("\n--- OVERALL PERFORMANCE ---")
    print(f"Total Return:           {stats['total_return']:>10.2f}%")
    print(f"  └─ Overnight (Gaps):  {stats['overnight_total']:>10.2f}% ({stats['overnight_contribution']:.1f}% contribution)")
    print(f"  └─ Intraday (Session):{stats['intraday_total']:>10.2f}% ({stats['intraday_contribution']:.1f}% contribution)")
    
    print("\n--- DAILY AVERAGES ---")
    print(f"Avg Daily Return:       {stats['total_mean']:>10.4f}% (std: {stats['total_std']:.4f}%)")
    print(f"Avg Overnight:          {stats['overnight_mean']:>10.4f}% (std: {stats['overnight_std']:.4f}%)")
    print(f"Avg Intraday:           {stats['intraday_mean']:>10.4f}% (std: {stats['intraday_std']:.4f}%)")
    
    print("\n--- WIN/LOSS DAYS ---")
    print(f"Overnight: {stats['overnight_positive_days']} positive / {stats['overnight_negative_days']} negative days")
    print(f"Intraday:  {stats['intraday_positive_days']} positive / {stats['intraday_negative_days']} negative days")
    
    # Show last 10 weeks
    if len(weekly) > 0:
        print("\n--- RECENT WEEKLY SUMMARY (Last 10 Weeks) ---")
        recent = weekly.tail(10)
        print(f"{'Week':<12} {'Overnight':>10} {'Intraday':>10} {'Weekly':>10} │ {'Run.Over':>10} {'Run.Intra':>10} {'Run.Tot':>10}")
        print("-" * 80)
        for _, row in recent.iterrows():
            print(f"{row['year_week']:<12} {row['grand_overnight']:>10.2f} {row['grand_intraday']:>10.2f} {row['weekly_total']:>10.2f} │ {row['running_overnight']:>10.2f} {row['running_intraday']:>10.2f} {row['running_total']:>10.2f}")


def analyze_basket(basket_name: str, basket_path: str, cache_dir: Path) -> Dict[str, Any]:
    """Run full analysis for a basket."""
    print(f"\n🔄 Analyzing {basket_name}...")
    
    # Load basket symbols
    symbols = load_basket(basket_path)
    print(f"   Loaded {len(symbols)} symbols from basket")
    
    # Calculate basket returns
    daily_returns = calculate_basket_returns(symbols, cache_dir)
    if daily_returns.empty:
        print(f"   ❌ No data available for {basket_name}")
        return {}
    
    print(f"   Found data for {int(daily_returns['num_symbols'].mean())} symbols on average")
    
    # Generate aggregations
    weekly = aggregate_to_weekly(daily_returns)
    by_day = aggregate_by_day_of_week(daily_returns)
    monthly = aggregate_by_month(daily_returns)
    yearly = aggregate_by_year(daily_returns)
    stats = generate_summary_stats(daily_returns)
    
    # Print summary
    print_summary(basket_name, stats, weekly)
    
    return {
        "basket_name": basket_name,
        "daily": daily_returns,
        "weekly": weekly,
        "by_day": by_day,
        "monthly": monthly,
        "yearly": yearly,
        "stats": stats
    }


def export_to_csv(results: dict, output_dir: str):
    """Export all results to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Summary CSV
    summary_data = []
    for basket_name, data in results.items():
        if "stats" in data:
            row = {"basket": basket_name, **data["stats"]}
            summary_data.append(row)
    
    if summary_data:
        pd.DataFrame(summary_data).to_csv(f"{output_dir}/summary.csv", index=False)
    
    # Weekly CSVs for each basket
    for basket_name, data in results.items():
        if "weekly" in data and not data["weekly"].empty:
            data["weekly"].to_csv(f"{output_dir}/{basket_name}_weekly.csv", index=False)
    
    # Yearly comparison
    yearly_comparison = []
    for basket_name, data in results.items():
        if "yearly" in data:
            for _, row in data["yearly"].iterrows():
                yearly_comparison.append({
                    "basket": basket_name,
                    "year": row["year"],
                    "overnight_sum": row["overnight_pct_sum"],
                    "intraday_sum": row["intraday_pct_sum"],
                    "total_sum": row["total_pct_sum"]
                })
    
    if yearly_comparison:
        pd.DataFrame(yearly_comparison).to_csv(f"{output_dir}/yearly_comparison.csv", index=False)
    
    # Day of week analysis
    dow_comparison = []
    for basket_name, data in results.items():
        if "by_day" in data:
            for _, row in data["by_day"].iterrows():
                dow_comparison.append({
                    "basket": basket_name,
                    "day": row["day_of_week"],
                    "overnight_mean": row["overnight_pct_mean"],
                    "overnight_sum": row["overnight_pct_sum"],
                    "intraday_mean": row["intraday_pct_mean"],
                    "intraday_sum": row["intraday_pct_sum"],
                    "total_mean": row["total_pct_mean"],
                    "total_sum": row["total_pct_sum"],
                    "trading_days": row["overnight_pct_count"]
                })
    
    if dow_comparison:
        pd.DataFrame(dow_comparison).to_csv(f"{output_dir}/day_of_week.csv", index=False)
    
    print(f"\n✅ Results exported to: {output_dir}")


def main():
    """Main entry point."""
    print("=" * 80)
    print("OVERNIGHT VS INTRADAY ANALYSIS")
    print("=" * 80)
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap return)")
    print("  • Intraday:  Today's open → Today's close (session return)")
    print("=" * 80)
    
    results = {}
    
    for basket_name, basket_path in BASKETS.items():
        if os.path.exists(basket_path):
            result = analyze_basket(basket_name, basket_path, CACHE_DIR)
            if result:
                results[basket_name] = result
        else:
            print(f"❌ Basket file not found: {basket_path}")
    
    # Export to CSV
    if results:
        output_dir = f"reports/overnight_intraday_analysis_{datetime.now().strftime('%Y%m%d_%H%M')}"
        os.makedirs("reports", exist_ok=True)
        export_to_csv(results, output_dir)
    
    # Print comparative summary
    print("\n" + "=" * 80)
    print("COMPARATIVE SUMMARY")
    print("=" * 80)
    print(f"\n{'Basket':<25} {'Total Return':>12} {'Overnight':>12} {'Intraday':>12} {'Over %':>10} {'Intra %':>10}")
    print("-" * 95)
    
    for basket_name, data in results.items():
        if "stats" in data:
            s = data["stats"]
            print(f"{basket_name:<25} {s['total_return']:>12.2f}% {s['overnight_total']:>11.2f}% {s['intraday_total']:>11.2f}% {s['overnight_contribution']:>9.1f}% {s['intraday_contribution']:>9.1f}%")
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
