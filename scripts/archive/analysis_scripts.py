# Analysis Scripts Archive
# Combined on 2026-01-08


# ========== FROM: overnight_intraday_analysis.py ==========

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
    "largecap_highbeta": "data/baskets/basket_largecap_highbeta.txt",
    "largecap_lowbeta": "data/baskets/basket_largecap_lowbeta.txt",
    "midcap_highbeta": "data/baskets/basket_midcap_highbeta.txt",
    "midcap_lowbeta": "data/baskets/basket_midcap_lowbeta.txt",
    "smallcap_highbeta": "data/baskets/basket_smallcap_highbeta.txt",
    "smallcap_lowbeta": "data/baskets/basket_smallcap_lowbeta.txt",
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


# ========== FROM: overnight_intraday_corrected.py ==========

#!/usr/bin/env python3
"""
Corrected Overnight vs Intraday Analysis
Using proper compounding methodology
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path

CACHE_DIR = Path('data/cache')

def load_basket(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def analyze_basket_correct(basket_name, basket_path):
    symbols = load_basket(basket_path)
    
    # Collect individual stock returns
    stock_results = []
    
    for symbol in symbols:
        file = find_file(symbol)
        if not file:
            continue
        
        df = pd.read_csv(file)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'])
        df = df.set_index('time').sort_index()
        
        # Calculate returns
        df['prev_close'] = df['close'].shift(1)
        df['overnight_mult'] = df['open'] / df['prev_close']
        df['intraday_mult'] = df['close'] / df['open']
        df['total_mult'] = df['close'] / df['prev_close']
        df = df.dropna()
        
        if len(df) > 100:
            # Compound returns for this stock
            cum_overnight = df['overnight_mult'].prod()
            cum_intraday = df['intraday_mult'].prod()
            cum_total = df['total_mult'].prod()
            
            stock_results.append({
                'symbol': symbol,
                'days': len(df),
                'start': df.index.min(),
                'end': df.index.max(),
                'overnight': (cum_overnight - 1) * 100,
                'intraday': (cum_intraday - 1) * 100,
                'total': (cum_total - 1) * 100,
                'log_overnight': np.log(cum_overnight) * 100,
                'log_intraday': np.log(cum_intraday) * 100,
                'log_total': np.log(cum_total) * 100,
            })
    
    if not stock_results:
        return
    
    results_df = pd.DataFrame(stock_results)
    
    # Simple average of log returns
    avg_log_overnight = results_df['log_overnight'].mean()
    avg_log_intraday = results_df['log_intraday'].mean()
    avg_log_total = results_df['log_total'].mean()
    
    print(f'\n{"="*60}')
    print(f'{basket_name.upper()}')
    print(f'{"="*60}')
    print(f'Symbols loaded: {len(results_df)}')
    print(f'Avg trading days per symbol: {results_df["days"].mean():.0f}')
    print(f'Date range: {results_df["start"].min().date()} to {results_df["end"].max().date()}')
    print()
    
    # Per-symbol stats
    print('PER-SYMBOL AVERAGES (log returns):')
    print(f'  Avg Overnight per symbol: {avg_log_overnight:>8.2f}%')
    print(f'  Avg Intraday per symbol:  {avg_log_intraday:>8.2f}%')
    print(f'  Avg Total per symbol:     {avg_log_total:>8.2f}%')
    
    print()
    print('CONTRIBUTION:')
    if avg_log_total != 0:
        print(f'  Overnight: {avg_log_overnight/avg_log_total * 100:>6.1f}%')
        print(f'  Intraday:  {avg_log_intraday/avg_log_total * 100:>6.1f}%')
    
    print()
    print('STOCK-LEVEL BREAKDOWN:')
    print(f'  Stocks with positive overnight: {(results_df["overnight"] > 0).sum()}/{len(results_df)}')
    print(f'  Stocks with negative intraday:  {(results_df["intraday"] < 0).sum()}/{len(results_df)}')
    print(f'  Stocks with negative total:     {(results_df["total"] < 0).sum()}/{len(results_df)}')
    
    # Show top/bottom
    print()
    print('Top 3 by Total Return:')
    for _, row in results_df.nlargest(3, 'total').iterrows():
        print(f'  {row["symbol"]}: Total={row["total"]:.1f}%, Overnight={row["overnight"]:.1f}%, Intraday={row["intraday"]:.1f}%')
    
    print()
    print('Bottom 3 by Total Return:')
    for _, row in results_df.nsmallest(3, 'total').iterrows():
        print(f'  {row["symbol"]}: Total={row["total"]:.1f}%, Overnight={row["overnight"]:.1f}%, Intraday={row["intraday"]:.1f}%')


if __name__ == '__main__':
    baskets = {
        'largecap_highbeta': 'data/baskets/basket_largecap_highbeta.txt',
        'largecap_lowbeta': 'data/baskets/basket_largecap_lowbeta.txt', 
        'midcap_highbeta': 'data/baskets/basket_midcap_highbeta.txt',
        'midcap_lowbeta': 'data/baskets/basket_midcap_lowbeta.txt',
        'smallcap_highbeta': 'data/baskets/basket_smallcap_highbeta.txt',
        'smallcap_lowbeta': 'data/baskets/basket_smallcap_lowbeta.txt',
    }

    print('CORRECTED OVERNIGHT VS INTRADAY ANALYSIS')
    print('Per-stock compounded returns, then averaged')

    for name, path in baskets.items():
        analyze_basket_correct(name, path)


# ========== FROM: overnight_intraday_monthly.py ==========

#!/usr/bin/env python3
"""
Monthly Overnight vs Intraday Analysis - Full Historical Data
Analyzes all available data for each basket with monthly aggregation
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from datetime import datetime

CACHE_DIR = Path('data/cache')

def load_basket(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def analyze_basket_monthly(basket_name, basket_path):
    """Analyze basket and return monthly summary with running totals."""
    symbols = load_basket(basket_path)
    
    all_daily_data = []
    loaded_count = 0
    
    for symbol in symbols:
        file = find_file(symbol)
        if not file:
            continue
        
        df = pd.read_csv(file)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'])
        df = df.set_index('time').sort_index()
        
        # Calculate returns as percentages
        df['prev_close'] = df['close'].shift(1)
        df['overnight_pct'] = (df['open'] - df['prev_close']) / df['prev_close'] * 100
        df['intraday_pct'] = (df['close'] - df['open']) / df['open'] * 100
        df['total_pct'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
        df = df.dropna()
        
        if len(df) > 50:
            all_daily_data.append(df[['overnight_pct', 'intraday_pct', 'total_pct']])
            loaded_count += 1
    
    if not all_daily_data:
        return None, 0
    
    # Combine all symbols - average across symbols for each day
    combined = pd.concat(all_daily_data, axis=1)
    
    # Get average for each day (equal weighted basket)
    overnight_cols = [i for i in range(0, len(combined.columns), 3)]
    intraday_cols = [i for i in range(1, len(combined.columns), 3)]
    total_cols = [i for i in range(2, len(combined.columns), 3)]
    
    daily_avg = pd.DataFrame(index=combined.index)
    daily_avg['overnight'] = combined.iloc[:, overnight_cols].mean(axis=1)
    daily_avg['intraday'] = combined.iloc[:, intraday_cols].mean(axis=1)
    daily_avg['total'] = combined.iloc[:, total_cols].mean(axis=1)
    daily_avg['num_stocks'] = combined.iloc[:, overnight_cols].notna().sum(axis=1)
    
    # Add month info
    daily_avg['year'] = daily_avg.index.year
    daily_avg['month'] = daily_avg.index.month
    daily_avg['year_month'] = daily_avg['year'].astype(str) + '-' + daily_avg['month'].astype(str).str.zfill(2)
    
    # Aggregate to monthly - sum of daily returns
    monthly = daily_avg.groupby('year_month').agg({
        'overnight': 'sum',
        'intraday': 'sum',
        'total': 'sum',
        'num_stocks': 'mean'
    }).reset_index()
    
    monthly.columns = ['Year-Month', 'Overnight', 'Intraday', 'Monthly Total', 'Avg Stocks']
    
    # Sort by month
    monthly = monthly.sort_values('Year-Month').reset_index(drop=True)
    
    # Calculate running totals
    monthly['Running Overnight'] = monthly['Overnight'].cumsum()
    monthly['Running Intraday'] = monthly['Intraday'].cumsum()
    monthly['Running Total'] = monthly['Monthly Total'].cumsum()
    
    return monthly, loaded_count


def print_monthly_summary(basket_name, monthly_df, symbol_count):
    """Print formatted monthly summary - last 24 months and yearly totals."""
    print(f"\n{'='*100}")
    print(f"{basket_name.upper()} - Monthly Overnight vs Intraday ({symbol_count} symbols)")
    print(f"{'='*100}")
    
    # Show data range
    print(f"Data Range: {monthly_df['Year-Month'].iloc[0]} to {monthly_df['Year-Month'].iloc[-1]}")
    print(f"Total Months: {len(monthly_df)}")
    
    # Yearly summary
    monthly_df['Year'] = monthly_df['Year-Month'].str[:4].astype(int)
    yearly = monthly_df.groupby('Year').agg({
        'Overnight': 'sum',
        'Intraday': 'sum',
        'Monthly Total': 'sum'
    }).reset_index()
    
    print(f"\n{'─'*100}")
    print("YEARLY SUMMARY")
    print(f"{'─'*100}")
    print(f"{'Year':<8} │ {'Overnight':>12} {'Intraday':>12} │ {'Annual Total':>14} │ {'O/I Split':>20}")
    print(f"{'─'*100}")
    
    for _, row in yearly.iterrows():
        total = row['Monthly Total']
        if total != 0:
            o_pct = row['Overnight'] / total * 100
            i_pct = row['Intraday'] / total * 100
            split = f"{o_pct:.0f}% / {i_pct:.0f}%"
        else:
            split = "N/A"
        print(f"{int(row['Year']):<8} │ {row['Overnight']:>11.2f}% {row['Intraday']:>11.2f}% │ {row['Monthly Total']:>13.2f}% │ {split:>20}")
    
    # Totals
    print(f"{'─'*100}")
    total_overnight = monthly_df['Overnight'].sum()
    total_intraday = monthly_df['Intraday'].sum()
    total_return = monthly_df['Monthly Total'].sum()
    if total_return != 0:
        split = f"{total_overnight/total_return*100:.0f}% / {total_intraday/total_return*100:.0f}%"
    else:
        split = "N/A"
    print(f"{'TOTAL':<8} │ {total_overnight:>11.2f}% {total_intraday:>11.2f}% │ {total_return:>13.2f}% │ {split:>20}")
    
    # Last 12 months detail
    print(f"\n{'─'*100}")
    print("LAST 12 MONTHS DETAIL")
    print(f"{'─'*100}")
    print(f"{'Year-Month':<12} │ {'Overnight':>10} {'Intraday':>10} │ {'Monthly':>10} │ {'Run.Over':>10} {'Run.Intra':>10} {'Run.Tot':>10}")
    print(f"{'─'*100}")
    
    last_12 = monthly_df.tail(12)
    for _, row in last_12.iterrows():
        print(f"{row['Year-Month']:<12} │ {row['Overnight']:>10.2f} {row['Intraday']:>10.2f} │ {row['Monthly Total']:>10.2f} │ {row['Running Overnight']:>10.2f} {row['Running Intraday']:>10.2f} {row['Running Total']:>10.2f}")
    
    return yearly


def main():
    baskets = {
        'largecap_highbeta': 'data/baskets/basket_largecap_highbeta.txt',
        'largecap_lowbeta': 'data/baskets/basket_largecap_lowbeta.txt', 
        'midcap_highbeta': 'data/baskets/basket_midcap_highbeta.txt',
        'midcap_lowbeta': 'data/baskets/basket_midcap_lowbeta.txt',
        'smallcap_highbeta': 'data/baskets/basket_smallcap_highbeta.txt',
        'smallcap_lowbeta': 'data/baskets/basket_smallcap_lowbeta.txt',
    }
    
    print("="*100)
    print("OVERNIGHT VS INTRADAY ANALYSIS - MONTHLY BREAKDOWN (ALL AVAILABLE DATA)")
    print("="*100)
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap)")
    print("  • Intraday:  Today's open → Today's close (session)")
    print("  • Running Totals: Cumulative sum from first month")
    
    all_results = {}
    all_yearly = {}
    
    for name, path in baskets.items():
        monthly, count = analyze_basket_monthly(name, path)
        if monthly is not None:
            all_results[name] = monthly
            yearly = print_monthly_summary(name, monthly, count)
            all_yearly[name] = yearly
            
            # Save to CSV
            output_file = f"reports/monthly_overnight_intraday_{name}_all.csv"
            monthly.to_csv(output_file, index=False)
    
    # Comparative summary across all years
    print("\n" + "="*100)
    print("COMPARATIVE SUMMARY - ALL AVAILABLE DATA")
    print("="*100)
    print(f"\n{'Basket':<25} {'Data Range':<20} {'Total Overnight':>15} {'Total Intraday':>15} {'Total Return':>14} {'O/I Split':>18}")
    print("-" * 110)
    
    for name, monthly in all_results.items():
        date_range = f"{monthly['Year-Month'].iloc[0]} to {monthly['Year-Month'].iloc[-1]}"
        total_overnight = monthly['Overnight'].sum()
        total_intraday = monthly['Intraday'].sum()
        total_return = monthly['Monthly Total'].sum()
        
        if total_return != 0:
            split = f"{total_overnight/total_return*100:.0f}% / {total_intraday/total_return*100:.0f}%"
        else:
            split = "N/A"
        
        print(f"{name:<25} {date_range:<20} {total_overnight:>14.2f}% {total_intraday:>14.2f}% {total_return:>13.2f}% {split:>18}")
    
    # Year-by-year comparison across baskets
    print("\n" + "="*100)
    print("YEAR-BY-YEAR COMPARISON (Annual Returns)")
    print("="*100)
    
    # Get all years
    all_years = set()
    for name, yearly in all_yearly.items():
        all_years.update(yearly['Year'].tolist())
    all_years = sorted(all_years)
    
    # Header
    print(f"\n{'Year':<8}", end="")
    for name in baskets.keys():
        short_name = name.replace('cap_', '').replace('beta', '')[:12]
        print(f" │ {short_name:>12}", end="")
    print()
    print("-" * (8 + 15 * len(baskets)))
    
    # Data rows
    for year in all_years:
        print(f"{year:<8}", end="")
        for name in baskets.keys():
            if name in all_yearly:
                yearly = all_yearly[name]
                row = yearly[yearly['Year'] == year]
                if not row.empty:
                    val = row['Monthly Total'].iloc[0]
                    print(f" │ {val:>11.2f}%", end="")
                else:
                    print(f" │ {'N/A':>12}", end="")
            else:
                print(f" │ {'N/A':>12}", end="")
        print()
    
    print("\n✅ CSV files saved to reports/ folder")


if __name__ == '__main__':
    main()


# ========== FROM: overnight_intraday_weekly.py ==========

#!/usr/bin/env python3
"""
Weekly Overnight vs Intraday Analysis with Running Totals
Matches the format shown in the user's screenshot
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from datetime import datetime

CACHE_DIR = Path('data/cache')

def load_basket(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def analyze_basket_weekly(basket_name, basket_path, year=2025):
    """Analyze basket and return weekly summary with running totals."""
    symbols = load_basket(basket_path)
    
    all_daily_data = []
    loaded_count = 0
    
    for symbol in symbols:
        file = find_file(symbol)
        if not file:
            continue
        
        df = pd.read_csv(file)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'])
        df = df.set_index('time').sort_index()
        
        # Calculate returns as percentages
        df['prev_close'] = df['close'].shift(1)
        df['overnight_pct'] = (df['open'] - df['prev_close']) / df['prev_close'] * 100
        df['intraday_pct'] = (df['close'] - df['open']) / df['open'] * 100
        df['total_pct'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
        df = df.dropna()
        
        # Filter to target year
        df_year = df[df.index.year == year]
        
        if len(df_year) > 0:
            all_daily_data.append(df_year[['overnight_pct', 'intraday_pct', 'total_pct']])
            loaded_count += 1
    
    if not all_daily_data:
        return None, 0
    
    # Combine all symbols - average across symbols for each day
    combined = pd.concat(all_daily_data, axis=1)
    
    # Get average for each day (equal weighted basket)
    overnight_cols = [i for i in range(0, len(combined.columns), 3)]
    intraday_cols = [i for i in range(1, len(combined.columns), 3)]
    total_cols = [i for i in range(2, len(combined.columns), 3)]
    
    daily_avg = pd.DataFrame(index=combined.index)
    daily_avg['overnight'] = combined.iloc[:, overnight_cols].mean(axis=1)
    daily_avg['intraday'] = combined.iloc[:, intraday_cols].mean(axis=1)
    daily_avg['total'] = combined.iloc[:, total_cols].mean(axis=1)
    
    # Add week info
    daily_avg['year'] = daily_avg.index.year
    daily_avg['week'] = daily_avg.index.isocalendar().week.values
    daily_avg['year_week'] = daily_avg['year'].astype(str) + '-W' + daily_avg['week'].astype(str).str.zfill(2)
    
    # Aggregate to weekly - sum of daily returns
    weekly = daily_avg.groupby('year_week').agg({
        'overnight': 'sum',
        'intraday': 'sum',
        'total': 'sum'
    }).reset_index()
    
    weekly.columns = ['Year-Wk', 'Overnight', 'Intraday', 'Weekly Total']
    
    # Sort by week
    weekly = weekly.sort_values('Year-Wk').reset_index(drop=True)
    
    # Calculate running totals
    weekly['Running Overnight'] = weekly['Overnight'].cumsum()
    weekly['Running Intraday'] = weekly['Intraday'].cumsum()
    weekly['Running Total'] = weekly['Weekly Total'].cumsum()
    
    return weekly, loaded_count


def print_weekly_table(basket_name, weekly_df, symbol_count):
    """Print formatted weekly table."""
    print(f"\n{'='*90}")
    print(f"{basket_name.upper()} - Weekly Overnight vs Intraday ({symbol_count} symbols)")
    print(f"{'='*90}")
    
    print(f"\n{'Year-Wk':<12} │ {'Grand Total':^25} │ {'Weekly':>8} │ {'Running Totals':^35}")
    print(f"{'':12} │ {'Overnight':>10} {'Intraday':>12} │ {'Total':>8} │ {'Overnight':>10} {'Intraday':>12} {'Total':>10}")
    print("-" * 90)
    
    for _, row in weekly_df.iterrows():
        overnight_color = "" 
        intraday_color = ""
        
        print(f"{row['Year-Wk']:<12} │ {row['Overnight']:>10.2f} {row['Intraday']:>12.2f} │ {row['Weekly Total']:>8.2f} │ {row['Running Overnight']:>10.2f} {row['Running Intraday']:>12.2f} {row['Running Total']:>10.2f}")
    
    # Summary
    print("-" * 90)
    print(f"{'TOTAL':<12} │ {weekly_df['Overnight'].sum():>10.2f} {weekly_df['Intraday'].sum():>12.2f} │ {weekly_df['Weekly Total'].sum():>8.2f} │")


def main():
    baskets = {
        'largecap_highbeta': 'data/baskets/basket_largecap_highbeta.txt',
        'largecap_lowbeta': 'data/baskets/basket_largecap_lowbeta.txt', 
        'midcap_highbeta': 'data/baskets/basket_midcap_highbeta.txt',
        'midcap_lowbeta': 'data/baskets/basket_midcap_lowbeta.txt',
        'smallcap_highbeta': 'data/baskets/basket_smallcap_highbeta.txt',
        'smallcap_lowbeta': 'data/baskets/basket_smallcap_lowbeta.txt',
    }
    
    print("="*90)
    print("OVERNIGHT VS INTRADAY ANALYSIS - WEEKLY BREAKDOWN WITH RUNNING TOTALS")
    print("Year: 2025")
    print("="*90)
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap)")
    print("  • Intraday:  Today's open → Today's close (session)")
    print("  • Running Totals: Cumulative sum from W01")
    
    all_results = {}
    
    for name, path in baskets.items():
        weekly, count = analyze_basket_weekly(name, path, year=2025)
        if weekly is not None:
            all_results[name] = weekly
            print_weekly_table(name, weekly, count)
            
            # Save to CSV
            output_file = f"reports/weekly_overnight_intraday_{name}_2025.csv"
            weekly.to_csv(output_file, index=False)
    
    # Comparative summary
    print("\n" + "="*90)
    print("COMPARATIVE SUMMARY - 2025 YTD")
    print("="*90)
    print(f"\n{'Basket':<25} {'Total Overnight':>15} {'Total Intraday':>15} {'YTD Return':>12} {'O/I Split':>15}")
    print("-" * 85)
    
    for name, weekly in all_results.items():
        total_overnight = weekly['Overnight'].sum()
        total_intraday = weekly['Intraday'].sum()
        ytd_return = weekly['Weekly Total'].sum()
        
        if ytd_return != 0:
            split = f"{total_overnight/ytd_return*100:.0f}% / {total_intraday/ytd_return*100:.0f}%"
        else:
            split = "N/A"
        
        print(f"{name:<25} {total_overnight:>14.2f}% {total_intraday:>14.2f}% {ytd_return:>11.2f}% {split:>15}")
    
    print("\n✅ CSV files saved to reports/ folder")


if __name__ == '__main__':
    main()


# ========== FROM: etf_analysis.py ==========

#!/usr/bin/env python3
"""
ETF Analysis Script
===================
1. Extended TOTM Strategy (Entry: 25th open, Exit: 3rd close of next month)
2. Monthly Return Analysis
3. Day of Week Analysis
"""

import glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
OUTPUT_DIR = Path("reports/analysis/etf_analysis")
CHARGES = 0.0037  # 0.37% round-trip

# ETF symbols
ETF_SYMBOLS = [
    "NIFTYBETA", "NEXT50BETA", "ALPHA", "IT", "LOWVOL1", "MIDCAP", "GILT5BETA",
    "GILT10BETA", "MIDCAPBETA", "MNC", "CONS", "VAL30IETF", "MOMIDMTM", "ESG",
    "MID150CASE", "BSLNIFTY", "ELIQUID", "MULTICAP", "NEXT50IETF", "MOMNC",
    "SENSEXADD", "ESENSEX", "TECH", "MONQ50", "BANKADD", "LICNETFGSC",
    "MIDCAPIETF", "AUTOBEES", "TATAGOLD", "GOLDBEES", "GROWWNET", "AXSENSEX",
    "METALIETF", "MSCIADD", "TNIDETF", "ALPHAETF", "SBIETFQLTY", "AONENIFTY",
    "TOP10ADD", "NV20IETF", "METAL", "MOLOWVOL", "LOWVOLIETF", "MONIFTY500",
    "HEALTHIETF", "UNIONGOLD", "SETFNN50", "LIQUIDADD", "ALPL30IETF",
    "SILVERBEES", "MOSILVER", "HDFCQUAL", "GSEC10ABSL", "MAFANG", "GILT5YBEES",
    "MOINFRA", "HDFCNEXT50", "MONEXT50", "NIFTYCASE", "SBIETFCON", "GOLDBND",
    "ABSLLIQUID", "EVIETF", "LIQUIDETF", "SETFNIFBK", "TOP15IETF", "SILVERBND",
    "CONSUMIETF", "HDFCGROWTH", "CPSEETF", "SBINEQWETF", "GSEC10YEAR", "HDFCGOLD",
    "MOHEALTH", "BANKIETF", "MOMGF", "MOIPO", "ITETF", "SML100CASE", "GOLDIETF",
    "TOP100CASE", "QUAL30IETF", "GROWWNXT50", "GOLDADD", "HDFCPVTBAN",
    "MIDQ50ADD", "MOGOLD", "BANKPSU", "CONSUMER", "GSEC10IETF", "MOVALUE",
    "HDFCNIFTY", "AXISTECETF", "INTERNET", "SELECTIPO", "EBANKNIFTY",
    "SILVERCASE", "GROWWGOLD", "PSUBNKBEES", "LICNETFN50", "EMULTIMQ",
    "NIFTYQLITY", "GROWWPOWER", "GROWWLOVOL", "GSEC5IETF", "SNXT30BEES",
    "SBIETFPB", "GROWWMOM50", "ABSLNN50ET", "NIF100BEES", "SMALL250",
    "MIDSELIETF", "LOWVOL", "LIQUID", "FINIETF", "LICMFGOLD", "NIFTYADD",
    "LIQUIDSHRI", "FMCGIETF", "CONSUMBEES", "CHOICEGOLD", "LIQUIDPLUS",
    "HDFCVALUE", "SILVERADD", "INFRAIETF", "HNGSNGBEES", "MANUFGBEES",
    "ABSLBANETF", "QGOLDHALF", "GOLD360", "MOGSEC", "MOPSE", "GROWWLIQID",
    "INFRABEES"
]


def load_etf_data():
    """Load all ETF data from cache."""
    all_data = {}
    
    for symbol in ETF_SYMBOLS:
        pattern = CACHE_DIR / f"dhan_*_{symbol}_1d.csv"
        files = list(CACHE_DIR.glob(f"dhan_*_{symbol}_1d.csv"))
        
        if files:
            try:
                df = pd.read_csv(files[0], parse_dates=['time'], index_col='time')
                if len(df) >= 20:  # Minimum data requirement
                    all_data[symbol] = df
            except Exception as e:
                pass
    
    return all_data


def run_extended_totm_strategy(all_data):
    """
    Extended TOTM Strategy:
    - Entry: Open of first trading day on/after 25th of month N
    - Exit: Close of first trading day on/after 3rd of month N+1
    """
    print("\n" + "=" * 70)
    print("EXTENDED TOTM STRATEGY ANALYSIS")
    print("Entry: 25th Open | Exit: 3rd Close (next month) | Charges: 0.37%")
    print("=" * 70)
    
    all_trades = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['date'] = df.index.date
        df['day'] = df.index.day
        df['month'] = df.index.month
        df['year'] = df.index.year
        
        # Find entry days (first trading day on/after 25th)
        df['is_entry_candidate'] = df['day'] >= 25
        
        # Group by year-month for entry
        for (year, month), group in df.groupby(['year', 'month']):
            entry_candidates = group[group['day'] >= 25]
            if entry_candidates.empty:
                continue
            
            entry_row = entry_candidates.iloc[0]
            entry_date = entry_row.name
            entry_price = entry_row['open']
            
            # Find exit in next month (first day on/after 3rd)
            if month == 12:
                next_year, next_month = year + 1, 1
            else:
                next_year, next_month = year, month + 1
            
            next_month_data = df[(df['year'] == next_year) & (df['month'] == next_month)]
            exit_candidates = next_month_data[next_month_data['day'] >= 3]
            
            if exit_candidates.empty:
                continue
            
            exit_row = exit_candidates.iloc[0]
            exit_date = exit_row.name
            exit_price = exit_row['close']
            
            # Calculate returns
            gross_return = (exit_price - entry_price) / entry_price
            net_return = gross_return - CHARGES
            holding_days = (exit_date - entry_date).days
            
            all_trades.append({
                'symbol': symbol,
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_return_pct': gross_return * 100,
                'net_return_pct': net_return * 100,
                'holding_days': holding_days,
                'year': entry_date.year
            })
    
    if not all_trades:
        print("No trades generated!")
        return None
    
    trades_df = pd.DataFrame(all_trades)
    
    # Overall stats
    total_trades = len(trades_df)
    total_net_return = trades_df['net_return_pct'].sum()
    avg_net_return = trades_df['net_return_pct'].mean()
    win_rate = (trades_df['net_return_pct'] > 0).mean() * 100
    winners = trades_df[trades_df['net_return_pct'] > 0]['net_return_pct']
    losers = trades_df[trades_df['net_return_pct'] <= 0]['net_return_pct']
    avg_winner = winners.mean() if len(winners) > 0 else 0
    avg_loser = losers.mean() if len(losers) > 0 else 0
    profit_factor = abs(winners.sum() / losers.sum()) if losers.sum() != 0 else float('inf')
    avg_holding = trades_df['holding_days'].mean()
    
    print(f"\n--- OVERALL RESULTS ---")
    print(f"Total Trades: {total_trades}")
    print(f"Total Net Return: {total_net_return:+,.2f}%")
    print(f"Avg Net P&L per Trade: {avg_net_return:+.3f}%")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Avg Winner: {avg_winner:+.2f}%")
    print(f"Avg Loser: {avg_loser:.2f}%")
    print(f"Avg Holding Period: {avg_holding:.1f} days")
    
    # Year-wise breakdown
    print(f"\n--- YEAR-WISE BREAKDOWN ---")
    year_stats = []
    for year, group in trades_df.groupby('year'):
        yr_total = group['net_return_pct'].sum()
        yr_avg = group['net_return_pct'].mean()
        yr_wr = (group['net_return_pct'] > 0).mean() * 100
        yr_winners = group[group['net_return_pct'] > 0]['net_return_pct']
        yr_losers = group[group['net_return_pct'] <= 0]['net_return_pct']
        yr_pf = abs(yr_winners.sum() / yr_losers.sum()) if yr_losers.sum() != 0 else float('inf')
        
        year_stats.append({
            'year': year,
            'trades': len(group),
            'total_return': yr_total,
            'avg_return': yr_avg,
            'win_rate': yr_wr,
            'profit_factor': yr_pf
        })
        print(f"{year}: {len(group):3d} trades | {yr_total:+8.1f}% total | {yr_avg:+.2f}% avg | {yr_wr:.1f}% WR | {yr_pf:.2f} PF")
    
    # Top performing ETFs
    print(f"\n--- TOP 15 ETFs BY AVG RETURN ---")
    etf_stats = trades_df.groupby('symbol').agg({
        'net_return_pct': ['count', 'sum', 'mean'],
    }).round(3)
    etf_stats.columns = ['trades', 'total_return', 'avg_return']
    etf_stats = etf_stats[etf_stats['trades'] >= 12]  # At least 1 year of data
    etf_stats = etf_stats.sort_values('avg_return', ascending=False)
    
    for i, (symbol, row) in enumerate(etf_stats.head(15).iterrows(), 1):
        print(f"{i:2d}. {symbol:15s} | {int(row['trades']):3d} trades | {row['total_return']:+8.1f}% total | {row['avg_return']:+.3f}% avg")
    
    # Worst performing ETFs
    print(f"\n--- BOTTOM 10 ETFs BY AVG RETURN ---")
    for i, (symbol, row) in enumerate(etf_stats.tail(10).iterrows(), 1):
        print(f"{i:2d}. {symbol:15s} | {int(row['trades']):3d} trades | {row['total_return']:+8.1f}% total | {row['avg_return']:+.3f}% avg")
    
    return trades_df


def run_monthly_analysis(all_data):
    """Analyze returns by month of year."""
    print("\n" + "=" * 70)
    print("MONTHLY RETURN ANALYSIS")
    print("=" * 70)
    
    all_monthly = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['month'] = df.index.month
        df['year'] = df.index.year
        df['daily_return'] = df['close'].pct_change() * 100
        
        # Monthly returns
        monthly = df.groupby(['year', 'month']).agg({
            'open': 'first',
            'close': 'last',
            'daily_return': 'sum'
        }).reset_index()
        
        monthly['symbol'] = symbol
        monthly['monthly_return'] = (monthly['close'] - monthly['open']) / monthly['open'] * 100
        all_monthly.append(monthly)
    
    if not all_monthly:
        print("No data!")
        return None
    
    monthly_df = pd.concat(all_monthly, ignore_index=True)
    
    # Average return by month
    print("\n--- AVERAGE RETURN BY MONTH (All ETFs) ---")
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    month_stats = monthly_df.groupby('month').agg({
        'monthly_return': ['count', 'mean', 'std', 'median']
    }).round(3)
    month_stats.columns = ['observations', 'mean_return', 'std', 'median_return']
    month_stats['win_rate'] = monthly_df.groupby('month').apply(
        lambda x: (x['monthly_return'] > 0).mean() * 100, include_groups=False
    )
    
    print(f"\n{'Month':<6} {'Obs':>6} {'Mean':>8} {'Median':>8} {'Std':>8} {'Win%':>7}")
    print("-" * 50)
    for month in range(1, 13):
        if month in month_stats.index:
            row = month_stats.loc[month]
            print(f"{month_names[month-1]:<6} {int(row['observations']):>6} {row['mean_return']:>+8.2f}% {row['median_return']:>+8.2f}% {row['std']:>8.2f} {row['win_rate']:>6.1f}%")
    
    # Best and worst months
    best_months = month_stats.nlargest(3, 'mean_return')
    worst_months = month_stats.nsmallest(3, 'mean_return')
    
    print(f"\n📈 Best Months: {', '.join([month_names[int(m)-1] for m in best_months.index])}")
    print(f"📉 Worst Months: {', '.join([month_names[int(m)-1] for m in worst_months.index])}")
    
    return monthly_df


def run_day_of_week_analysis(all_data):
    """Analyze returns by day of week."""
    print("\n" + "=" * 70)
    print("DAY OF WEEK ANALYSIS")
    print("=" * 70)
    
    all_daily = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['day_of_week'] = df.index.dayofweek  # 0=Monday, 4=Friday
        df['daily_return'] = df['close'].pct_change() * 100
        df['overnight_return'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1) * 100
        df['intraday_return'] = (df['close'] - df['open']) / df['open'] * 100
        df['symbol'] = symbol
        all_daily.append(df[['symbol', 'day_of_week', 'daily_return', 'overnight_return', 'intraday_return']].dropna())
    
    if not all_daily:
        print("No data!")
        return None
    
    daily_df = pd.concat(all_daily, ignore_index=True)
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Daily return by day of week
    print("\n--- DAILY RETURNS BY DAY OF WEEK ---")
    print(f"\n{'Day':<12} {'Obs':>8} {'Mean':>8} {'Median':>8} {'Std':>8} {'Win%':>7}")
    print("-" * 55)
    
    dow_stats = []
    for dow in range(5):
        subset = daily_df[daily_df['day_of_week'] == dow]
        if len(subset) > 0:
            mean_ret = subset['daily_return'].mean()
            median_ret = subset['daily_return'].median()
            std_ret = subset['daily_return'].std()
            win_rate = (subset['daily_return'] > 0).mean() * 100
            obs = len(subset)
            
            dow_stats.append({
                'day': day_names[dow],
                'dow': dow,
                'observations': obs,
                'mean_return': mean_ret,
                'median_return': median_ret,
                'std': std_ret,
                'win_rate': win_rate
            })
            
            print(f"{day_names[dow]:<12} {obs:>8} {mean_ret:>+8.3f}% {median_ret:>+8.3f}% {std_ret:>8.3f} {win_rate:>6.1f}%")
    
    # Overnight vs Intraday by day
    print("\n--- OVERNIGHT vs INTRADAY BY DAY ---")
    print(f"\n{'Day':<12} {'Overnight':>12} {'Intraday':>12} {'Total':>12}")
    print("-" * 50)
    
    for dow in range(5):
        subset = daily_df[daily_df['day_of_week'] == dow]
        if len(subset) > 0:
            overnight = subset['overnight_return'].mean()
            intraday = subset['intraday_return'].mean()
            total = subset['daily_return'].mean()
            print(f"{day_names[dow]:<12} {overnight:>+11.3f}% {intraday:>+11.3f}% {total:>+11.3f}%")
    
    # Best/worst day
    dow_df = pd.DataFrame(dow_stats)
    best_day = dow_df.loc[dow_df['mean_return'].idxmax(), 'day']
    worst_day = dow_df.loc[dow_df['mean_return'].idxmin(), 'day']
    
    print(f"\n📈 Best Day: {best_day}")
    print(f"📉 Worst Day: {worst_day}")
    
    return daily_df


def main():
    print("=" * 70)
    print("ETF COMPREHENSIVE ANALYSIS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # Load data
    print("\n📂 Loading ETF data...")
    all_data = load_etf_data()
    print(f"✅ Loaded {len(all_data)} ETFs with sufficient data")
    
    if not all_data:
        print("❌ No data loaded!")
        return
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Extended TOTM Strategy
    totm_trades = run_extended_totm_strategy(all_data)
    if totm_trades is not None:
        totm_trades.to_csv(OUTPUT_DIR / "etf_extended_totm_trades.csv", index=False)
        print(f"\n💾 Saved: {OUTPUT_DIR / 'etf_extended_totm_trades.csv'}")
    
    # 2. Monthly Analysis
    monthly_data = run_monthly_analysis(all_data)
    if monthly_data is not None:
        monthly_data.to_csv(OUTPUT_DIR / "etf_monthly_returns.csv", index=False)
        print(f"💾 Saved: {OUTPUT_DIR / 'etf_monthly_returns.csv'}")
    
    # 3. Day of Week Analysis
    dow_data = run_day_of_week_analysis(all_data)
    if dow_data is not None:
        dow_data.to_csv(OUTPUT_DIR / "etf_day_of_week.csv", index=False)
        print(f"💾 Saved: {OUTPUT_DIR / 'etf_day_of_week.csv'}")
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()


# ========== FROM: etf_monthly_analysis.py ==========

#!/usr/bin/env python3
"""
ETF Month-wise Returns Analysis
================================
Find which ETF performs best in which month.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CACHE_DIR = Path("data/cache/dhan/daily")
OUTPUT_DIR = Path("reports/analysis/etf_analysis")

def main():
    print("=" * 80)
    print("ETF MONTH-WISE RETURNS ANALYSIS")
    print("=" * 80)
    
    # Load all clean ETF data
    all_monthly = []
    etf_count = 0
    skipped = []
    
    for f in sorted(CACHE_DIR.glob("dhan_*_1d.csv")):
        symbol = f.stem.split("_")[2]
        
        try:
            df = pd.read_csv(f, parse_dates=["time"], index_col="time")
            
            # Skip if too little data
            if len(df) < 60:
                skipped.append((symbol, "too few rows"))
                continue
            
            # Check for bad data - skip if extreme moves
            df["daily_return"] = df["close"].pct_change() * 100
            max_move = df["daily_return"].abs().max()
            if max_move > 30:
                skipped.append((symbol, f"extreme move {max_move:.1f}%"))
                continue
            
            # Check for duplicates
            if df.index.duplicated().sum() > 0:
                skipped.append((symbol, "duplicates"))
                continue
            
            df["month"] = df.index.month
            df["year"] = df.index.year
            
            # Calculate monthly returns (open to close of month)
            for (year, month), group in df.groupby(["year", "month"]):
                if len(group) < 10:  # Skip incomplete months
                    continue
                
                open_price = group["open"].iloc[0]
                close_price = group["close"].iloc[-1]
                monthly_ret = (close_price - open_price) / open_price * 100
                
                all_monthly.append({
                    "symbol": symbol,
                    "year": year,
                    "month": month,
                    "monthly_return": monthly_ret
                })
            
            etf_count += 1
            
        except Exception as e:
            skipped.append((symbol, str(e)))
            continue
    
    print(f"\n✅ Analyzed {etf_count} ETFs with clean data")
    print(f"📊 Total monthly observations: {len(all_monthly)}")
    
    if skipped:
        print(f"⚠️ Skipped {len(skipped)} files (bad data)")
    
    df_monthly = pd.DataFrame(all_monthly)
    
    # Month names
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Average return by ETF and month
    etf_month_avg = df_monthly.groupby(["symbol", "month"])["monthly_return"].agg(
        ["mean", "count", "std"]
    ).reset_index()
    etf_month_avg.columns = ["symbol", "month", "avg_return", "observations", "std"]
    
    # Filter for sufficient observations (at least 3 years)
    etf_month_avg = etf_month_avg[etf_month_avg["observations"] >= 3]
    
    # =========================================================================
    # BEST PERFORMING ETF-MONTH COMBINATIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print("TOP 30 ETF-MONTH COMBINATIONS (By Avg Return)")
    print("=" * 80)
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
    print("-" * 50)
    
    top_combos = etf_month_avg.nlargest(30, "avg_return")
    for _, row in top_combos.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")
    
    # =========================================================================
    # WORST PERFORMING ETF-MONTH COMBINATIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print("BOTTOM 20 ETF-MONTH COMBINATIONS (By Avg Return)")
    print("=" * 80)
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
    print("-" * 50)
    
    worst_combos = etf_month_avg.nsmallest(20, "avg_return")
    for _, row in worst_combos.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")
    
    # =========================================================================
    # BEST MONTH FOR EACH ETF
    # =========================================================================
    print("\n" + "=" * 80)
    print("BEST MONTH FOR EACH ETF (Top 30)")
    print("=" * 80)
    
    best_months = etf_month_avg.loc[etf_month_avg.groupby("symbol")["avg_return"].idxmax()]
    best_months = best_months.sort_values("avg_return", ascending=False)
    
    print(f"\n{'Symbol':<15} {'Best Month':<10} {'Avg Ret%':>10} {'Obs':>5}")
    print("-" * 45)
    for _, row in best_months.head(30).iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<10} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")
    
    # =========================================================================
    # MONTH RANKING (OVERALL)
    # =========================================================================
    print("\n" + "=" * 80)
    print("MONTH RANKING (Average across all ETFs)")
    print("=" * 80)
    
    month_overall = df_monthly.groupby("month")["monthly_return"].agg(
        ["mean", "median", "std", "count"]
    ).reset_index()
    month_overall = month_overall.sort_values("mean", ascending=False)
    
    print(f"\n{'Month':<10} {'Mean%':>10} {'Median%':>10} {'Std':>8} {'Obs':>8}")
    print("-" * 50)
    for _, row in month_overall.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{m:<10} {row['mean']:>+10.2f} {row['median']:>+10.2f} {row['std']:>8.2f} {int(row['count']):>8}")
    
    # =========================================================================
    # EXCEPTIONAL COMBOS (Risk-Adjusted)
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXCEPTIONAL ETF-MONTH COMBOS (Risk-Adjusted Score)")
    print("Score = Avg Return / Std * sqrt(Obs) -- Higher is better")
    print("=" * 80)
    
    # Calculate Sharpe-like score
    etf_month_avg["score"] = (etf_month_avg["avg_return"] / etf_month_avg["std"]) * np.sqrt(etf_month_avg["observations"])
    etf_month_avg = etf_month_avg.replace([np.inf, -np.inf], np.nan).dropna()
    
    exceptional = etf_month_avg[etf_month_avg["avg_return"] > 1].nlargest(25, "score")
    
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg%':>8} {'Std':>8} {'Obs':>5} {'Score':>8}")
    print("-" * 55)
    for _, row in exceptional.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+8.2f} {row['std']:>8.2f} {int(row['observations']):>5} {row['score']:>8.2f}")
    
    # =========================================================================
    # WIN RATE BY ETF-MONTH
    # =========================================================================
    print("\n" + "=" * 80)
    print("HIGHEST WIN RATE ETF-MONTH COMBOS (Min 5 obs, Avg > 1%)")
    print("=" * 80)
    
    # Calculate win rate
    win_rate = df_monthly.groupby(["symbol", "month"]).apply(
        lambda x: pd.Series({
            "win_rate": (x["monthly_return"] > 0).mean() * 100,
            "avg_return": x["monthly_return"].mean(),
            "observations": len(x)
        }), include_groups=False
    ).reset_index()
    
    win_rate = win_rate[(win_rate["observations"] >= 5) & (win_rate["avg_return"] > 1)]
    win_rate = win_rate.sort_values("win_rate", ascending=False)
    
    print(f"\n{'Symbol':<15} {'Month':<6} {'WinRate%':>10} {'Avg%':>8} {'Obs':>5}")
    print("-" * 50)
    for _, row in win_rate.head(25).iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['win_rate']:>10.1f} {row['avg_return']:>+8.2f} {int(row['observations']):>5}")
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    etf_month_avg.to_csv(OUTPUT_DIR / "etf_monthly_performance.csv", index=False)
    print(f"\n💾 Saved: {OUTPUT_DIR / 'etf_monthly_performance.csv'}")


if __name__ == "__main__":
    main()


# ========== FROM: etf_only_monthly_analysis.py ==========

#!/usr/bin/env python3
"""
ETF-Only Monthly Analysis
Analyzes month-wise returns for only the ETFs from the attached file.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CACHE_DIR = Path('data/cache/dhan/daily')

# ETF symbols from the attached TradingView CSV
ETF_SYMBOLS = [
    'NIFTYBETA', 'NEXT50BETA', 'ALPHA', 'IT', 'LOWVOL1', 'MIDCAP', 'GILT5BETA',
    'GILT10BETA', 'MIDCAPBETA', 'MNC', 'CONS', 'VAL30IETF', 'MOMIDMTM', 'ESG',
    'MID150CASE', 'BSLNIFTY', 'ELIQUID', 'MULTICAP', 'NEXT50IETF', 'MOMNC',
    'SENSEXADD', 'ESENSEX', 'TECH', 'MONQ50', 'BANKADD', 'LICNETFGSC',
    'MIDCAPIETF', 'AUTOBEES', 'TATAGOLD', 'GOLDBEES', 'GROWWNET', 'AXSENSEX',
    'METALIETF', 'MSCIADD', 'TNIDETF', 'ALPHAETF', 'SBIETFQLTY', 'AONENIFTY',
    'TOP10ADD', 'NV20IETF', 'METAL', 'MOLOWVOL', 'LOWVOLIETF', 'MONIFTY500',
    'HEALTHIETF', 'UNIONGOLD', 'SETFNN50', 'LIQUIDADD', 'ALPL30IETF',
    'SILVERBEES', 'MOSILVER', 'HDFCQUAL', 'GSEC10ABSL', 'MAFANG', 'GILT5YBEES',
    'MOINFRA', 'HDFCNEXT50', 'MONEXT50', 'NIFTYCASE', 'SBIETFCON', 'GOLDBND',
    'ABSLLIQUID', 'EVIETF', 'LIQUIDETF', 'SETFNIFBK', 'LIQUIDADD', 'TOP15IETF', 'SILVERBND',
    'CONSUMIETF', 'HDFCGROWTH', 'CPSEETF', 'SBINEQWETF', 'GSEC10YEAR', 'HDFCGOLD',
    'MOHEALTH', 'BANKIETF', 'MOMGF', 'MOIPO', 'ITETF', 'SML100CASE', 'GOLDIETF',
    'TOP100CASE', 'QUAL30IETF', 'GROWWNXT50', 'GOLDADD', 'HDFCPVTBAN',
    'MIDQ50ADD', 'MOGOLD', 'BANKPSU', 'CONSUMER', 'GSEC10IETF', 'MOVALUE',
    'HDFCNIFTY', 'AXISTECETF', 'INTERNET', 'SELECTIPO', 'EBANKNIFTY',
    'SILVERCASE', 'GROWWGOLD', 'PSUBNKBEES', 'LICNETFN50', 'EMULTIMQ',
    'NIFTYQLITY', 'GROWWPOWER', 'GROWWLOVOL', 'GSEC5IETF', 'SNXT30BEES',
    'SBIETFPB', 'GROWWMOM50', 'ABSLNN50ET', 'NIF100BEES', 'SMALL250',
    'MIDSELIETF', 'LOWVOL', 'LIQUID', 'FINIETF', 'LICMFGOLD', 'NIFTYADD',
    'LIQUIDSHRI', 'FMCGIETF', 'CONSUMBEES', 'CHOICEGOLD', 'LIQUIDPLUS',
    'HDFCVALUE', 'SILVERADD', 'INFRAIETF', 'HNGSNGBEES', 'MANUFGBEES',
    'ABSLBANETF', 'QGOLDHALF', 'GOLD360', 'MOGSEC', 'MOPSE', 'GROWWLIQID',
    'INFRABEES'
]

print('=' * 80)
print('ETF-ONLY MONTH-WISE RETURNS ANALYSIS')
print('=' * 80)

# Find which ETFs we have data for
found_etfs = []
missing_etfs = []
for symbol in ETF_SYMBOLS:
    files = list(CACHE_DIR.glob(f'dhan_*_{symbol}_1d.csv'))
    if files:
        found_etfs.append(symbol)
    else:
        missing_etfs.append(symbol)

print(f"\n📁 ETFs in CSV: {len(ETF_SYMBOLS)}")
print(f"✅ Found data for: {len(found_etfs)} ETFs")
print(f"❌ Missing data for: {len(missing_etfs)} ETFs")

if missing_etfs[:20]:
    print(f"\n   Missing: {missing_etfs[:20]}...")

# Load only ETF data
all_monthly = []
etf_count = 0
skipped = []

for f in sorted(CACHE_DIR.glob('dhan_*_1d.csv')):
    symbol = f.stem.split('_')[2]
    
    # Only process ETFs
    if symbol not in ETF_SYMBOLS:
        continue
    
    try:
        df = pd.read_csv(f, parse_dates=['time'], index_col='time')
        
        if len(df) < 60:
            skipped.append((symbol, 'too few rows'))
            continue
        
        df['daily_return'] = df['close'].pct_change() * 100
        max_move = df['daily_return'].abs().max()
        if max_move > 30:
            skipped.append((symbol, f'extreme move {max_move:.1f}%'))
            continue
        
        if df.index.duplicated().sum() > 0:
            skipped.append((symbol, 'duplicates'))
            continue
        
        df['month'] = df.index.month
        df['year'] = df.index.year
        
        for (year, month), group in df.groupby(['year', 'month']):
            if len(group) < 10:
                continue
            
            open_price = group['open'].iloc[0]
            close_price = group['close'].iloc[-1]
            monthly_ret = (close_price - open_price) / open_price * 100
            
            all_monthly.append({
                'symbol': symbol,
                'year': year,
                'month': month,
                'monthly_return': monthly_ret
            })
        
        etf_count += 1
        
    except Exception as e:
        skipped.append((symbol, str(e)))

print(f'\n✅ Analyzed {etf_count} ETFs with clean data')
print(f'📊 Total monthly observations: {len(all_monthly)}')
if skipped:
    print(f'⚠️ Skipped {len(skipped)}: {[s[0] for s in skipped]}')

if len(all_monthly) == 0:
    print("\n❌ No data to analyze!")
    exit()

df_monthly = pd.DataFrame(all_monthly)
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Average return by ETF and month
etf_month_avg = df_monthly.groupby(['symbol', 'month'])['monthly_return'].agg(['mean', 'count', 'std']).reset_index()
etf_month_avg.columns = ['symbol', 'month', 'avg_return', 'observations', 'std']
etf_month_avg = etf_month_avg[etf_month_avg['observations'] >= 3]

# TOP ETF-MONTH COMBINATIONS
print('\n' + '=' * 80)
print('TOP 25 ETF-MONTH COMBINATIONS (By Avg Return)')
print('=' * 80)
print(f"{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
print('-' * 50)

top_combos = etf_month_avg.nlargest(25, 'avg_return')
for _, row in top_combos.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")

# WORST ETF-MONTH COMBINATIONS
print('\n' + '=' * 80)
print('BOTTOM 15 ETF-MONTH COMBINATIONS (By Avg Return)')
print('=' * 80)
print(f"{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
print('-' * 50)

worst_combos = etf_month_avg.nsmallest(15, 'avg_return')
for _, row in worst_combos.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")

# MONTH RANKING
print('\n' + '=' * 80)
print('MONTH RANKING (Average across all ETFs)')
print('=' * 80)

month_overall = df_monthly.groupby('month')['monthly_return'].agg(['mean', 'median', 'std', 'count']).reset_index()
month_overall = month_overall.sort_values('mean', ascending=False)

print(f"{'Month':<10} {'Mean%':>10} {'Median%':>10} {'Std':>8} {'Obs':>8}")
print('-' * 50)
for _, row in month_overall.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{m:<10} {row['mean']:>+10.2f} {row['median']:>+10.2f} {row['std']:>8.2f} {int(row['count']):>8}")

# BEST MONTH FOR EACH ETF
print('\n' + '=' * 80)
print('BEST MONTH FOR EACH ETF (All ETFs)')
print('=' * 80)

best_months = etf_month_avg.loc[etf_month_avg.groupby('symbol')['avg_return'].idxmax()]
best_months = best_months.sort_values('avg_return', ascending=False)

print(f"{'Symbol':<15} {'Best Month':<10} {'Avg Ret%':>10} {'Obs':>5}")
print('-' * 45)
for _, row in best_months.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<10} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")

# WIN RATE BY ETF-MONTH
print('\n' + '=' * 80)
print('HIGHEST WIN RATE ETF-MONTH COMBOS (Min 4 obs, Avg > 1%)')
print('=' * 80)

win_rate = df_monthly.groupby(['symbol', 'month']).apply(
    lambda x: pd.Series({
        'win_rate': (x['monthly_return'] > 0).mean() * 100,
        'avg_return': x['monthly_return'].mean(),
        'observations': len(x)
    }), include_groups=False
).reset_index()

win_rate = win_rate[(win_rate['observations'] >= 4) & (win_rate['avg_return'] > 1)]
win_rate = win_rate.sort_values('win_rate', ascending=False)

print(f"{'Symbol':<15} {'Month':<6} {'WinRate%':>10} {'Avg%':>8} {'Obs':>5}")
print('-' * 50)
for _, row in win_rate.head(25).iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['win_rate']:>10.1f} {row['avg_return']:>+8.2f} {int(row['observations']):>5}")

# 100% WIN RATE COMBOS
print('\n' + '=' * 80)
print('100% WIN RATE ETF-MONTH COMBOS (Min 4 obs)')
print('=' * 80)

perfect = win_rate[(win_rate['win_rate'] == 100) & (win_rate['observations'] >= 4)]
perfect = perfect.sort_values('avg_return', ascending=False)

if len(perfect) > 0:
    print(f"{'Symbol':<15} {'Month':<6} {'Avg%':>10} {'Obs':>5}")
    print('-' * 40)
    for _, row in perfect.iterrows():
        m = month_names[int(row['month']) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")
else:
    print("No 100% win rate combos with min 4 observations")

# Category analysis - Group by ETF type
print('\n' + '=' * 80)
print('ANALYSIS BY ETF CATEGORY')
print('=' * 80)

categories = {
    'Gold': ['GOLDBEES', 'TATAGOLD', 'HDFCGOLD', 'GOLDIETF', 'UNIONGOLD', 'MOGOLD', 'GROWWGOLD', 'GOLDADD', 'QGOLDHALF', 'LICMFGOLD', 'CHOICEGOLD', 'GOLDBND', 'GOLD360'],
    'Silver': ['SILVERBEES', 'MOSILVER', 'SILVERCASE', 'SILVERADD', 'SILVERBND'],
    'Nifty50': ['NIFTYBETA', 'HDFCNIFTY', 'LICNETFN50', 'BSLNIFTY', 'NIFTYADD', 'NIFTYCASE', 'AONENIFTY'],
    'NiftyNext50': ['NEXT50BETA', 'NEXT50IETF', 'HDFCNEXT50', 'SETFNN50', 'ABSLNN50ET', 'MONEXT50', 'GROWWNXT50'],
    'Bank': ['PSUBNKBEES', 'BANKIETF', 'SETFNIFBK', 'BANKPSU', 'EBANKNIFTY', 'ABSLBANETF', 'SBIETFPB', 'HDFCPVTBAN'],
    'IT': ['IT', 'TECH', 'ITETF', 'AXISTECETF', 'TNIDETF'],
    'Midcap': ['MIDCAP', 'MIDCAPBETA', 'MIDCAPIETF', 'MID150CASE', 'MIDSELIETF', 'MIDQ50ADD'],
    'Infra': ['INFRAIETF', 'INFRABEES', 'MOINFRA'],
    'CPSE/PSU': ['CPSEETF', 'MOPSE'],
    'Consumption': ['CONS', 'CONSUMIETF', 'CONSUMBEES', 'SBIETFCON', 'CONSUMER'],
    'Healthcare': ['HEALTHIETF', 'MOHEALTH'],
    'Metal': ['METALIETF', 'METAL'],
}

for cat, symbols in categories.items():
    cat_data = df_monthly[df_monthly['symbol'].isin(symbols)]
    if len(cat_data) < 20:
        continue
    
    print(f"\n{cat} ETFs:")
    cat_by_month = cat_data.groupby('month')['monthly_return'].agg(['mean', 'count']).reset_index()
    cat_by_month = cat_by_month.sort_values('mean', ascending=False)
    
    best_month = cat_by_month.iloc[0]
    worst_month = cat_by_month.iloc[-1]
    
    best_m = month_names[int(best_month['month']) - 1]
    worst_m = month_names[int(worst_month['month']) - 1]
    
    print(f"   Best:  {best_m} → {best_month['mean']:+.2f}% avg ({int(best_month['count'])} obs)")
    print(f"   Worst: {worst_m} → {worst_month['mean']:+.2f}% avg ({int(worst_month['count'])} obs)")

# Save to CSV
output_dir = Path('reports/analysis/etf_analysis')
output_dir.mkdir(parents=True, exist_ok=True)

etf_month_avg.to_csv(output_dir / 'etf_only_monthly_performance.csv', index=False)
print(f"\n💾 Saved: {output_dir / 'etf_only_monthly_performance.csv'}")


# ========== FROM: candlestick_pattern_returns.py ==========

#!/usr/bin/env python3
"""
Candlestick Pattern Analysis - Forward Returns
Identifies all TA-Lib candlestick patterns across 10 years of data
and measures 1D, 3D, 5D forward returns after each pattern.
"""

import pandas as pd
import numpy as np
import glob
import talib
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

CACHE_DIR = Path('data/cache')
BASKET_PATH = 'data/baskets/basket_main.txt'

# All TA-Lib candlestick pattern functions
CANDLESTICK_PATTERNS = {
    'CDL2CROWS': 'Two Crows',
    'CDL3BLACKCROWS': 'Three Black Crows',
    'CDL3INSIDE': 'Three Inside Up/Down',
    'CDL3LINESTRIKE': 'Three-Line Strike',
    'CDL3OUTSIDE': 'Three Outside Up/Down',
    'CDL3STARSINSOUTH': 'Three Stars In The South',
    'CDL3WHITESOLDIERS': 'Three Advancing White Soldiers',
    'CDLABANDONEDBABY': 'Abandoned Baby',
    'CDLADVANCEBLOCK': 'Advance Block',
    'CDLBELTHOLD': 'Belt-hold',
    'CDLBREAKAWAY': 'Breakaway',
    'CDLCLOSINGMARUBOZU': 'Closing Marubozu',
    'CDLCONCEALBABYSWALL': 'Concealing Baby Swallow',
    'CDLCOUNTERATTACK': 'Counterattack',
    'CDLDARKCLOUDCOVER': 'Dark Cloud Cover',
    'CDLDOJI': 'Doji',
    'CDLDOJISTAR': 'Doji Star',
    'CDLDRAGONFLYDOJI': 'Dragonfly Doji',
    'CDLENGULFING': 'Engulfing Pattern',
    'CDLEVENINGDOJISTAR': 'Evening Doji Star',
    'CDLEVENINGSTAR': 'Evening Star',
    'CDLGAPSIDESIDEWHITE': 'Up/Down-gap side-by-side white lines',
    'CDLGRAVESTONEDOJI': 'Gravestone Doji',
    'CDLHAMMER': 'Hammer',
    'CDLHANGINGMAN': 'Hanging Man',
    'CDLHARAMI': 'Harami Pattern',
    'CDLHARAMICROSS': 'Harami Cross Pattern',
    'CDLHIGHWAVE': 'High-Wave Candle',
    'CDLHIKKAKE': 'Hikkake Pattern',
    'CDLHIKKAKEMOD': 'Modified Hikkake Pattern',
    'CDLHOMINGPIGEON': 'Homing Pigeon',
    'CDLIDENTICAL3CROWS': 'Identical Three Crows',
    'CDLINNECK': 'In-Neck Pattern',
    'CDLINVERTEDHAMMER': 'Inverted Hammer',
    'CDLKICKING': 'Kicking',
    'CDLKICKINGBYLENGTH': 'Kicking - bull/bear determined by the longer marubozu',
    'CDLLADDERBOTTOM': 'Ladder Bottom',
    'CDLLONGLEGGEDDOJI': 'Long Legged Doji',
    'CDLLONGLINE': 'Long Line Candle',
    'CDLMARUBOZU': 'Marubozu',
    'CDLMATCHINGLOW': 'Matching Low',
    'CDLMATHOLD': 'Mat Hold',
    'CDLMORNINGDOJISTAR': 'Morning Doji Star',
    'CDLMORNINGSTAR': 'Morning Star',
    'CDLONNECK': 'On-Neck Pattern',
    'CDLPIERCING': 'Piercing Pattern',
    'CDLRICKSHAWMAN': 'Rickshaw Man',
    'CDLRISEFALL3METHODS': 'Rising/Falling Three Methods',
    'CDLSEPARATINGLINES': 'Separating Lines',
    'CDLSHOOTINGSTAR': 'Shooting Star',
    'CDLSHORTLINE': 'Short Line Candle',
    'CDLSPINNINGTOP': 'Spinning Top',
    'CDLSTALLEDPATTERN': 'Stalled Pattern',
    'CDLSTICKSANDWICH': 'Stick Sandwich',
    'CDLTAKURI': 'Takuri (Dragonfly Doji with very long lower shadow)',
    'CDLTASUKIGAP': 'Tasuki Gap',
    'CDLTHRUSTING': 'Thrusting Pattern',
    'CDLTRISTAR': 'Tristar Pattern',
    'CDLUNIQUE3RIVER': 'Unique 3 River',
    'CDLUPSIDEGAP2CROWS': 'Upside Gap Two Crows',
    'CDLXSIDEGAP3METHODS': 'Upside/Downside Gap Three Methods',
}


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def find_file(symbol: str) -> str:
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def detect_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detect all candlestick patterns and add as columns."""
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    
    for pattern_code in CANDLESTICK_PATTERNS.keys():
        try:
            func = getattr(talib, pattern_code)
            df[pattern_code] = func(o, h, l, c)
        except Exception as e:
            df[pattern_code] = 0
    
    return df


def calculate_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate 1D, 3D, 5D forward returns from close."""
    df['ret_1d'] = df['close'].shift(-1) / df['close'] - 1
    df['ret_3d'] = df['close'].shift(-3) / df['close'] - 1
    df['ret_5d'] = df['close'].shift(-5) / df['close'] - 1
    return df


def analyze_stock(symbol: str) -> Dict:
    """Analyze a single stock for all patterns."""
    file = find_file(symbol)
    if not file:
        return None
    
    df = pd.read_csv(file)
    df['time'] = pd.to_datetime(df['time'])
    df = df.drop_duplicates(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    if len(df) < 50:
        return None
    
    # Detect patterns and calculate returns
    df = detect_patterns(df)
    df = calculate_forward_returns(df)
    
    # Collect pattern occurrences
    results = {}
    
    for pattern_code in CANDLESTICK_PATTERNS.keys():
        # Bullish signals (positive values, typically 100)
        bullish_mask = df[pattern_code] > 0
        bearish_mask = df[pattern_code] < 0
        
        if bullish_mask.sum() > 0:
            bullish_df = df[bullish_mask & df['ret_1d'].notna() & df['ret_3d'].notna() & df['ret_5d'].notna()]
            if len(bullish_df) > 0:
                results[f'{pattern_code}_BULL'] = {
                    'count': len(bullish_df),
                    'ret_1d': bullish_df['ret_1d'].tolist(),
                    'ret_3d': bullish_df['ret_3d'].tolist(),
                    'ret_5d': bullish_df['ret_5d'].tolist(),
                }
        
        if bearish_mask.sum() > 0:
            bearish_df = df[bearish_mask & df['ret_1d'].notna() & df['ret_3d'].notna() & df['ret_5d'].notna()]
            if len(bearish_df) > 0:
                results[f'{pattern_code}_BEAR'] = {
                    'count': len(bearish_df),
                    'ret_1d': bearish_df['ret_1d'].tolist(),
                    'ret_3d': bearish_df['ret_3d'].tolist(),
                    'ret_5d': bearish_df['ret_5d'].tolist(),
                }
    
    return results


def main():
    print('=' * 120)
    print('CANDLESTICK PATTERN ANALYSIS - FORWARD RETURNS (1D, 3D, 5D)')
    print('=' * 120)
    print()
    print('Basket: basket_main.txt')
    print('Data: ~10 years of daily OHLC')
    print('Patterns: All TA-Lib candlestick patterns')
    print()
    
    symbols = load_basket(BASKET_PATH)
    print(f'Analyzing {len(symbols)} symbols...')
    print()
    
    # Aggregate results across all stocks
    all_patterns = defaultdict(lambda: {'count': 0, 'ret_1d': [], 'ret_3d': [], 'ret_5d': []})
    
    loaded = 0
    for i, symbol in enumerate(symbols):
        results = analyze_stock(symbol)
        if results:
            loaded += 1
            for pattern_key, data in results.items():
                all_patterns[pattern_key]['count'] += data['count']
                all_patterns[pattern_key]['ret_1d'].extend(data['ret_1d'])
                all_patterns[pattern_key]['ret_3d'].extend(data['ret_3d'])
                all_patterns[pattern_key]['ret_5d'].extend(data['ret_5d'])
        
        if (i + 1) % 20 == 0:
            print(f'  Processed {i + 1}/{len(symbols)} symbols...')
    
    print(f'\nLoaded {loaded} stocks successfully.')
    print()
    
    # Convert to summary stats
    summary = []
    for pattern_key, data in all_patterns.items():
        if data['count'] < 10:  # Skip patterns with very few occurrences
            continue
        
        # Parse pattern name
        parts = pattern_key.rsplit('_', 1)
        pattern_code = parts[0]
        direction = parts[1]
        pattern_name = CANDLESTICK_PATTERNS.get(pattern_code, pattern_code)
        
        ret_1d = np.array(data['ret_1d']) * 100
        ret_3d = np.array(data['ret_3d']) * 100
        ret_5d = np.array(data['ret_5d']) * 100
        
        summary.append({
            'Pattern': pattern_name,
            'Direction': direction,
            'Count': data['count'],
            'Avg_1D': np.mean(ret_1d),
            'Avg_3D': np.mean(ret_3d),
            'Avg_5D': np.mean(ret_5d),
            'Median_1D': np.median(ret_1d),
            'Median_3D': np.median(ret_3d),
            'Median_5D': np.median(ret_5d),
            'Win%_1D': (ret_1d > 0).mean() * 100,
            'Win%_3D': (ret_3d > 0).mean() * 100,
            'Win%_5D': (ret_5d > 0).mean() * 100,
            'Std_1D': np.std(ret_1d),
        })
    
    df_summary = pd.DataFrame(summary)
    
    # Sort by count
    df_summary = df_summary.sort_values('Count', ascending=False)
    
    # Print BULLISH patterns
    print('=' * 120)
    print('BULLISH PATTERNS - Sorted by Average 5D Return')
    print('=' * 120)
    bullish = df_summary[df_summary['Direction'] == 'BULL'].sort_values('Avg_5D', ascending=False)
    
    print(f"\n{'Pattern':<45} {'Count':>8} │ {'Avg 1D':>8} {'Avg 3D':>8} {'Avg 5D':>8} │ {'Win% 1D':>8} {'Win% 3D':>8} {'Win% 5D':>8}")
    print('─' * 120)
    
    for _, row in bullish.iterrows():
        print(f"{row['Pattern']:<45} {row['Count']:>8,} │ {row['Avg_1D']:>+7.2f}% {row['Avg_3D']:>+7.2f}% {row['Avg_5D']:>+7.2f}% │ {row['Win%_1D']:>7.1f}% {row['Win%_3D']:>7.1f}% {row['Win%_5D']:>7.1f}%")
    
    # Print BEARISH patterns
    print()
    print('=' * 120)
    print('BEARISH PATTERNS - Sorted by Average 5D Return (ascending - most bearish first)')
    print('=' * 120)
    bearish = df_summary[df_summary['Direction'] == 'BEAR'].sort_values('Avg_5D', ascending=True)
    
    print(f"\n{'Pattern':<45} {'Count':>8} │ {'Avg 1D':>8} {'Avg 3D':>8} {'Avg 5D':>8} │ {'Win% 1D':>8} {'Win% 3D':>8} {'Win% 5D':>8}")
    print('─' * 120)
    
    for _, row in bearish.iterrows():
        print(f"{row['Pattern']:<45} {row['Count']:>8,} │ {row['Avg_1D']:>+7.2f}% {row['Avg_3D']:>+7.2f}% {row['Avg_5D']:>+7.2f}% │ {row['Win%_1D']:>7.1f}% {row['Win%_3D']:>7.1f}% {row['Win%_5D']:>7.1f}%")
    
    # Top 10 most predictive patterns (by absolute 5D return)
    print()
    print('=' * 120)
    print('TOP 20 MOST PREDICTIVE PATTERNS (by absolute Avg 5D Return)')
    print('=' * 120)
    
    df_summary['Abs_5D'] = df_summary['Avg_5D'].abs()
    top20 = df_summary.sort_values('Abs_5D', ascending=False).head(20)
    
    print(f"\n{'Pattern':<45} {'Dir':<5} {'Count':>8} │ {'Avg 1D':>8} {'Avg 3D':>8} {'Avg 5D':>8} │ {'Win% 5D':>8}")
    print('─' * 120)
    
    for _, row in top20.iterrows():
        print(f"{row['Pattern']:<45} {row['Direction']:<5} {row['Count']:>8,} │ {row['Avg_1D']:>+7.2f}% {row['Avg_3D']:>+7.2f}% {row['Avg_5D']:>+7.2f}% │ {row['Win%_5D']:>7.1f}%")
    
    # Patterns with high statistical significance (high count + consistent returns)
    print()
    print('=' * 120)
    print('HIGH CONFIDENCE PATTERNS (Count > 500, sorted by Avg 5D)')
    print('=' * 120)
    
    high_count = df_summary[df_summary['Count'] >= 500].sort_values('Avg_5D', ascending=False)
    
    print(f"\n{'Pattern':<45} {'Dir':<5} {'Count':>8} │ {'Avg 1D':>8} {'Avg 3D':>8} {'Avg 5D':>8} │ {'Win% 5D':>8}")
    print('─' * 120)
    
    for _, row in high_count.iterrows():
        print(f"{row['Pattern']:<45} {row['Direction']:<5} {row['Count']:>8,} │ {row['Avg_1D']:>+7.2f}% {row['Avg_3D']:>+7.2f}% {row['Avg_5D']:>+7.2f}% │ {row['Win%_5D']:>7.1f}%")
    
    # Save to CSV
    df_summary.to_csv('reports/candlestick_pattern_returns.csv', index=False)
    print()
    print('✅ Full results saved to reports/candlestick_pattern_returns.csv')


if __name__ == '__main__':
    main()


# ========== FROM: candlestick_short_analysis.py ==========

#!/usr/bin/env python3
"""
Candlestick Pattern Analysis for INTRADAY SHORT TRADES
After a bearish pattern forms, evaluate shorting at next day's open.

Metrics:
- Short P&L = (Open - Close) / Open  (positive = profit for short)
- Max Gain = (Open - Low) / Open (best exit for short)
- Max Loss = (High - Open) / Open (worst case for short)
"""

import pandas as pd
import numpy as np
import glob
import talib
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

CACHE_DIR = Path('data/cache')
BASKET_PATH = 'data/baskets/basket_main.txt'

# Focus on traditionally BEARISH patterns only
BEARISH_PATTERNS = {
    'CDL2CROWS': 'Two Crows',
    'CDL3BLACKCROWS': 'Three Black Crows',
    'CDLADVANCEBLOCK': 'Advance Block',
    'CDLDARKCLOUDCOVER': 'Dark Cloud Cover',
    'CDLEVENINGDOJISTAR': 'Evening Doji Star',
    'CDLEVENINGSTAR': 'Evening Star',
    'CDLHANGINGMAN': 'Hanging Man',
    'CDLIDENTICAL3CROWS': 'Identical Three Crows',
    'CDLSHOOTINGSTAR': 'Shooting Star',
    'CDLUPSIDEGAP2CROWS': 'Upside Gap Two Crows',
    'CDLENGULFING': 'Engulfing (Bearish)',
    'CDLHARAMI': 'Harami (Bearish)',
    'CDLHARAMICROSS': 'Harami Cross (Bearish)',
    'CDL3INSIDE': 'Three Inside Down',
    'CDL3OUTSIDE': 'Three Outside Down',
    'CDLGRAVESTONEDOJI': 'Gravestone Doji',
    'CDLDOJISTAR': 'Doji Star (Bearish)',
    'CDLCOUNTERATTACK': 'Counterattack (Bearish)',
    'CDLBELTHOLD': 'Belt-hold (Bearish)',
    'CDLMARUBOZU': 'Marubozu (Bearish)',
    'CDLCLOSINGMARUBOZU': 'Closing Marubozu (Bearish)',
    'CDLLONGLINE': 'Long Line (Bearish)',
    'CDLSTALLEDPATTERN': 'Stalled Pattern',
    'CDLTRISTAR': 'Tristar (Bearish)',
    'CDLKICKING': 'Kicking (Bearish)',
    'CDLTHRUSTING': 'Thrusting Pattern',
    'CDLINNECK': 'In-Neck Pattern',
    'CDLONNECK': 'On-Neck Pattern',
    'CDL3LINESTRIKE': 'Three-Line Strike (Bearish)',
    'CDLRISEFALL3METHODS': 'Falling Three Methods',
}


def load_basket(path: str) -> List[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def find_file(symbol: str) -> str:
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None


def detect_bearish_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Detect bearish candlestick patterns. Returns -100 for bearish signals."""
    o = df['open'].values
    h = df['high'].values
    l = df['low'].values
    c = df['close'].values
    
    for pattern_code in BEARISH_PATTERNS.keys():
        try:
            func = getattr(talib, pattern_code)
            result = func(o, h, l, c)
            # Only keep bearish signals (negative values)
            df[pattern_code] = np.where(result < 0, result, 0)
        except Exception as e:
            df[pattern_code] = 0
    
    return df


def calculate_short_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate returns for SHORT trades entered at next day's open.
    
    Short at Open, cover at Close:
    - short_1d = (Open_t+1 - Close_t+1) / Open_t+1  (1 day hold)
    - short_3d = (Open_t+1 - Close_t+3) / Open_t+1  (3 day hold)
    - short_5d = (Open_t+1 - Close_t+5) / Open_t+1  (5 day hold)
    
    Also calculate max gain/loss during the trade:
    - max_gain_1d = (Open_t+1 - Low_t+1) / Open_t+1  (best exit point)
    - max_loss_1d = (High_t+1 - Open_t+1) / Open_t+1  (worst drawdown)
    """
    # Entry price: next day's open
    df['entry_open'] = df['open'].shift(-1)
    
    # 1D Short: entry at t+1 open, exit at t+1 close
    df['short_1d'] = (df['open'].shift(-1) - df['close'].shift(-1)) / df['open'].shift(-1)
    
    # 3D Short: entry at t+1 open, exit at t+3 close
    df['short_3d'] = (df['open'].shift(-1) - df['close'].shift(-3)) / df['open'].shift(-1)
    
    # 5D Short: entry at t+1 open, exit at t+5 close
    df['short_5d'] = (df['open'].shift(-1) - df['close'].shift(-5)) / df['open'].shift(-1)
    
    # Max gain on 1D short (if you sold at low)
    df['max_gain_1d'] = (df['open'].shift(-1) - df['low'].shift(-1)) / df['open'].shift(-1)
    
    # Max loss on 1D short (if stock went to high before you could exit)
    df['max_loss_1d'] = (df['high'].shift(-1) - df['open'].shift(-1)) / df['open'].shift(-1)
    
    return df


def analyze_stock(symbol: str) -> Dict:
    """Analyze a single stock for bearish patterns."""
    file = find_file(symbol)
    if not file:
        return None
    
    df = pd.read_csv(file)
    df['time'] = pd.to_datetime(df['time'])
    df = df.drop_duplicates(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    if len(df) < 50:
        return None
    
    # Detect patterns and calculate returns
    df = detect_bearish_patterns(df)
    df = calculate_short_returns(df)
    
    # Collect pattern occurrences
    results = {}
    
    for pattern_code in BEARISH_PATTERNS.keys():
        # Bearish signals are negative values (typically -100)
        bearish_mask = df[pattern_code] < 0
        
        if bearish_mask.sum() > 0:
            valid_mask = (bearish_mask & 
                         df['short_1d'].notna() & 
                         df['short_3d'].notna() & 
                         df['short_5d'].notna())
            bearish_df = df[valid_mask]
            
            if len(bearish_df) > 0:
                results[pattern_code] = {
                    'count': len(bearish_df),
                    'short_1d': bearish_df['short_1d'].tolist(),
                    'short_3d': bearish_df['short_3d'].tolist(),
                    'short_5d': bearish_df['short_5d'].tolist(),
                    'max_gain_1d': bearish_df['max_gain_1d'].tolist(),
                    'max_loss_1d': bearish_df['max_loss_1d'].tolist(),
                }
    
    return results


def main():
    print('=' * 130)
    print('BEARISH CANDLESTICK PATTERNS - INTRADAY SHORT TRADE ANALYSIS')
    print('=' * 130)
    print()
    print('Trade Setup:')
    print('  • Pattern forms on Day 0')
    print('  • SHORT at Day 1 Open')
    print('  • Cover at Day 1/3/5 Close')
    print()
    print('Metrics:')
    print('  • Short P&L = (Entry - Exit) / Entry  [positive = profit]')
    print('  • Max Gain = (Open - Low) / Open     [best possible exit on Day 1]')
    print('  • Max Loss = (High - Open) / Open    [worst drawdown on Day 1]')
    print()
    
    symbols = load_basket(BASKET_PATH)
    print(f'Analyzing {len(symbols)} symbols from basket_main.txt...')
    print()
    
    # Aggregate results
    all_patterns = defaultdict(lambda: {
        'count': 0, 
        'short_1d': [], 'short_3d': [], 'short_5d': [],
        'max_gain_1d': [], 'max_loss_1d': []
    })
    
    loaded = 0
    for i, symbol in enumerate(symbols):
        results = analyze_stock(symbol)
        if results:
            loaded += 1
            for pattern_code, data in results.items():
                all_patterns[pattern_code]['count'] += data['count']
                all_patterns[pattern_code]['short_1d'].extend(data['short_1d'])
                all_patterns[pattern_code]['short_3d'].extend(data['short_3d'])
                all_patterns[pattern_code]['short_5d'].extend(data['short_5d'])
                all_patterns[pattern_code]['max_gain_1d'].extend(data['max_gain_1d'])
                all_patterns[pattern_code]['max_loss_1d'].extend(data['max_loss_1d'])
        
        if (i + 1) % 25 == 0:
            print(f'  Processed {i + 1}/{len(symbols)} symbols...')
    
    print(f'\nLoaded {loaded} stocks successfully.')
    print()
    
    # Build summary
    summary = []
    for pattern_code, data in all_patterns.items():
        if data['count'] < 10:
            continue
        
        pattern_name = BEARISH_PATTERNS.get(pattern_code, pattern_code)
        
        s1 = np.array(data['short_1d']) * 100
        s3 = np.array(data['short_3d']) * 100
        s5 = np.array(data['short_5d']) * 100
        mg = np.array(data['max_gain_1d']) * 100
        ml = np.array(data['max_loss_1d']) * 100
        
        summary.append({
            'Pattern': pattern_name,
            'Count': data['count'],
            'Short_1D_Avg': np.mean(s1),
            'Short_3D_Avg': np.mean(s3),
            'Short_5D_Avg': np.mean(s5),
            'Short_1D_Median': np.median(s1),
            'Win%_1D': (s1 > 0).mean() * 100,
            'Win%_3D': (s3 > 0).mean() * 100,
            'Win%_5D': (s5 > 0).mean() * 100,
            'MaxGain_1D_Avg': np.mean(mg),
            'MaxLoss_1D_Avg': np.mean(ml),
            'RiskReward': np.mean(mg) / np.mean(ml) if np.mean(ml) > 0 else 0,
        })
    
    df_summary = pd.DataFrame(summary)
    
    # Sort by Win% 1D (best short trades)
    df_summary = df_summary.sort_values('Win%_1D', ascending=False)
    
    print('=' * 130)
    print('BEARISH PATTERNS - SORTED BY 1-DAY SHORT WIN RATE')
    print('=' * 130)
    print()
    print('Positive values = SHORT is profitable')
    print()
    
    print(f"{'Pattern':<35} {'Count':>7} │ {'Avg 1D':>8} {'Avg 3D':>8} {'Avg 5D':>8} │ {'Win% 1D':>8} {'Win% 3D':>8} {'Win% 5D':>8} │ {'MaxGain':>8} {'MaxLoss':>8} {'R:R':>6}")
    print('─' * 130)
    
    for _, row in df_summary.iterrows():
        print(f"{row['Pattern']:<35} {row['Count']:>7,} │ {row['Short_1D_Avg']:>+7.2f}% {row['Short_3D_Avg']:>+7.2f}% {row['Short_5D_Avg']:>+7.2f}% │ {row['Win%_1D']:>7.1f}% {row['Win%_3D']:>7.1f}% {row['Win%_5D']:>7.1f}% │ {row['MaxGain_1D_Avg']:>+7.2f}% {row['MaxLoss_1D_Avg']:>+7.2f}% {row['RiskReward']:>5.2f}x")
    
    # Comparison with baseline
    print()
    print('=' * 130)
    print('BASELINE COMPARISON: Random Day Intraday Returns')
    print('=' * 130)
    
    # Calculate baseline (all days)
    all_intraday = []
    all_max_gain = []
    all_max_loss = []
    
    for symbol in symbols:
        file = find_file(symbol)
        if not file:
            continue
        df = pd.read_csv(file)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'])
        df = df.sort_values('time')
        
        # Intraday return for long = (close - open) / open
        # For short = -1 * intraday = (open - close) / open
        df['intraday_short'] = (df['open'] - df['close']) / df['open'] * 100
        df['max_gain'] = (df['open'] - df['low']) / df['open'] * 100
        df['max_loss'] = (df['high'] - df['open']) / df['open'] * 100
        
        all_intraday.extend(df['intraday_short'].dropna().tolist())
        all_max_gain.extend(df['max_gain'].dropna().tolist())
        all_max_loss.extend(df['max_loss'].dropna().tolist())
    
    baseline_avg = np.mean(all_intraday)
    baseline_win = (np.array(all_intraday) > 0).mean() * 100
    baseline_mg = np.mean(all_max_gain)
    baseline_ml = np.mean(all_max_loss)
    
    print()
    print(f"Baseline (any random day):")
    print(f"  • Avg Short Return: {baseline_avg:+.3f}%")
    print(f"  • Win Rate (Short): {baseline_win:.1f}%")
    print(f"  • Avg Max Gain: {baseline_mg:+.2f}%")
    print(f"  • Avg Max Loss: {baseline_ml:+.2f}%")
    print(f"  • Risk/Reward: {baseline_mg/baseline_ml:.2f}x")
    
    # Patterns that beat baseline
    print()
    print('=' * 130)
    print('PATTERNS THAT BEAT BASELINE (Win% > {:.1f}%)'.format(baseline_win))
    print('=' * 130)
    
    better = df_summary[df_summary['Win%_1D'] > baseline_win].sort_values('Win%_1D', ascending=False)
    
    if len(better) > 0:
        print(f"\n{'Pattern':<35} {'Count':>7} │ {'Avg 1D':>8} │ {'Win% 1D':>8} │ {'Edge vs Base':>12}")
        print('─' * 80)
        
        for _, row in better.iterrows():
            edge = row['Win%_1D'] - baseline_win
            print(f"{row['Pattern']:<35} {row['Count']:>7,} │ {row['Short_1D_Avg']:>+7.2f}% │ {row['Win%_1D']:>7.1f}% │ {edge:>+11.1f}%")
    else:
        print("\nNo bearish patterns beat the baseline for shorting!")
    
    # Patterns worse than baseline (these actually favor longs!)
    print()
    print('=' * 130)
    print('PATTERNS WORSE THAN BASELINE (favor LONG not SHORT)')
    print('=' * 130)
    
    worse = df_summary[df_summary['Win%_1D'] < baseline_win].sort_values('Win%_1D', ascending=True)
    
    if len(worse) > 0:
        print(f"\n{'Pattern':<35} {'Count':>7} │ {'Avg 1D':>8} │ {'Win% 1D':>8} │ {'Long Win%':>10}")
        print('─' * 80)
        
        for _, row in worse.head(15).iterrows():
            long_win = 100 - row['Win%_1D']
            print(f"{row['Pattern']:<35} {row['Count']:>7,} │ {row['Short_1D_Avg']:>+7.2f}% │ {row['Win%_1D']:>7.1f}% │ {long_win:>9.1f}%")
    
    # Save results
    df_summary.to_csv('reports/bearish_pattern_short_analysis.csv', index=False)
    print()
    print('✅ Results saved to reports/bearish_pattern_short_analysis.csv')


if __name__ == '__main__':
    main()


# ========== FROM: indices_statistical_analysis.py ==========

#!/usr/bin/env python3
"""
Statistical Analysis of Index Options Expiry Patterns
=====================================================
Analyzes daily OHLC movements by day of week and days to expiry for multiple indices.
Uses cached Dhan data and Groww API for weekly data.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Groww API Setup
GROWW_BASE_URL = "https://api.groww.in/v1/chart_feed"

# Available cached indices
CACHED_INDICES = {
    "NIFTY50": "dhan_13_NIFTY_50_1d.csv",
    "NIFTY200": "dhan_18_NIFTY_200_1d.csv",
}

CACHE_DIR = Path("data/cache/dhan/daily")

def load_cached_dhan_data(filename):
    """Load cached Dhan data."""
    filepath = CACHE_DIR / filename
    if filepath.exists():
        print(f"📂 Loading cached {filepath.name}...")
        df = pd.read_csv(filepath)
        return df
    return None

def analyze_ohlc_movements(symbol, df):
    """Analyze OHLC movements by day of week and days to expiry."""
    
    if df is None or len(df) == 0:
        print(f"⚠️  No data for {symbol}")
        return None
    
    # Standardize columns
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp - check for both 'timestamp' and 'time'
    time_col = None
    if 'timestamp' in df.columns:
        time_col = 'timestamp'
    elif 'time' in df.columns:
        time_col = 'time'
    else:
        print(f"⚠️  No timestamp/time column for {symbol}")
        return None
    
    try:
        # Try milliseconds first
        if df[time_col].dtype != 'datetime64[ns]':
            if df[time_col].max() > 100000000000:  # Milliseconds
                df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
        else:
            df['timestamp'] = df[time_col]
    except:
        df['timestamp'] = pd.to_datetime(df[time_col])
    
    # Ensure proper data types
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    
    df = df.dropna(subset=['open', 'close'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Calculate movements
    df['open_close_movement'] = ((df['close'] - df['open']) / df['open'] * 100).round(4)
    df['close_open_movement_next'] = ((df['close'].shift(-1) - df['close']) / df['close'] * 100).round(4)
    
    # Day of week
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['weekday_num'] = df['timestamp'].dt.weekday
    df['date'] = df['timestamp'].dt.date
    
    # Filter for last 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df_5y = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df_5y) == 0:
        print(f"⚠️  No data in last 5 years for {symbol}")
        return None
    
    print(f"✅ Analyzing {len(df_5y)} records for {symbol} (5Y)")
    
    # Results container
    results = {
        'symbol': symbol,
        'total_records': len(df),
        'records_5y': len(df_5y),
        'date_range': f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}",
        'date_range_5y': f"{df_5y['timestamp'].min().date()} to {df_5y['timestamp'].max().date()}",
    }
    
    # Statistics by day of week
    results['open_close_stats'] = {}
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    for day in day_order:
        day_data = df_5y[df_5y['day_of_week'] == day]['open_close_movement']
        if len(day_data) > 0:
            results['open_close_stats'][day] = {
                'mean': round(day_data.mean(), 4),
                'median': round(day_data.median(), 4),
                'std': round(day_data.std(), 4),
                'min': round(day_data.min(), 4),
                'max': round(day_data.max(), 4),
                'positive_pct': round((day_data > 0).sum() / len(day_data) * 100, 2),
                'count': len(day_data)
            }
    
    # Close-Open movements
    results['close_open_by_dow'] = {}
    for day in day_order:
        day_data = df_5y[df_5y['day_of_week'] == day]['close_open_movement_next']
        if len(day_data) > 0:
            results['close_open_by_dow'][day] = {
                'mean': round(day_data.mean(), 4),
                'median': round(day_data.median(), 4),
                'count': len(day_data)
            }
    
    # Overall bias
    results['open_close_positive_pct'] = round((df_5y['open_close_movement'] > 0).sum() / len(df_5y) * 100, 2)
    results['close_open_positive_pct'] = round((df_5y['close_open_movement_next'] > 0).sum() / len(df_5y) * 100, 2)
    
    return results, df_5y

def print_report(results_dict):
    """Print comprehensive analysis report."""
    print("\n" + "="*100)
    print("INDEX STATISTICAL ANALYSIS - DAILY OHLC MOVEMENTS (Last 5 Years)")
    print("="*100)
    
    for symbol in sorted(results_dict.keys()):
        results = results_dict[symbol]
        
        if results is None:
            print(f"\n❌ {symbol}: No data available")
            continue
        
        print(f"\n{'='*100}")
        print(f"📊 {symbol}")
        print(f"{'='*100}")
        print(f"   Data Range: {results['date_range_5y']}")
        print(f"   Records: {results['records_5y']} (Total: {results['total_records']})")
        
        # Open-Close by DOW
        print(f"\n   🔵 OPEN-CLOSE MOVEMENT (%) BY DAY OF WEEK:")
        print(f"   {'Day':<12} {'Mean':>10} {'Median':>10} {'Std':>10} {'Count':>8} {'Positive %':>12}")
        print(f"   {'-'*65}")
        for day, stats in results['open_close_stats'].items():
            print(f"   {day:<12} {stats['mean']:>10.4f} {stats['median']:>10.4f} {stats['std']:>10.4f} {stats['count']:>8} {stats['positive_pct']:>11.2f}%")
        
        # Close-Open by DOW
        print(f"\n   🔵 CLOSE-OPEN GAP (%) BY DAY OF WEEK (next day opening):")
        print(f"   {'Day':<12} {'Mean':>10} {'Median':>10} {'Count':>8}")
        print(f"   {'-'*45}")
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            if day in results['close_open_by_dow']:
                data = results['close_open_by_dow'][day]
                print(f"   {day:<12} {data['mean']:>10.4f} {data['median']:>10.4f} {int(data['count']):>8}")
        
        # Overall statistics
        print(f"\n   🔵 OVERALL STATISTICS:")
        print(f"      Open-Close Positive: {results['open_close_positive_pct']:.2f}%")
        print(f"      Close-Open Positive: {results['close_open_positive_pct']:.2f}%")

def main():
    print("\n🚀 INDEX STATISTICAL ANALYSIS - STARTING\n")
    
    results_dict = {}
    all_data = {}
    
    # Process cached Dhan data
    for symbol, filename in CACHED_INDICES.items():
        print(f"\n{'='*60}")
        print(f"Processing {symbol}")
        print(f"{'='*60}")
        
        df = load_cached_dhan_data(filename)
        if df is not None:
            result = analyze_ohlc_movements(symbol, df)
            if result is not None:
                results, df_5y = result
                results_dict[symbol] = results
                all_data[symbol] = df_5y
        else:
            results_dict[symbol] = None
    
    # Print report
    print_report(results_dict)
    
    # Save results
    print(f"\n{'='*100}")
    print("SAVING DETAILED ANALYSIS...")
    print(f"{'='*100}")
    
    output_dir = Path("reports/indices_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for symbol, df in all_data.items():
        if df is not None:
            output_file = output_dir / f"{symbol}_5y_analysis.csv"
            df.to_csv(output_file, index=False)
            print(f"✅ Saved {symbol} detailed data to {output_file}")
    
    # Save summary as JSON
    summary_file = output_dir / "analysis_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)
    
    print(f"✅ Saved summary to {summary_file}")

if __name__ == "__main__":
    main()


# ========== FROM: weekend_effect_analysis.py ==========

#!/usr/bin/env python3
"""
Weekend Effect Analysis
=======================
Analyzes the return from buying at Friday close and selling at Monday open
across Large, Mid, and Small cap stocks for the last 10 years.

No commissions or charges are accounted for.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import glob
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict

CACHE_DIR = Path("data/cache/dhan/daily")
START_DATE = datetime(2016, 1, 1)  # ~10 years back from Jan 2026


def load_basket(path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLC data for a symbol."""
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    # Filter to last 10 years
                    df = df[df["date"] >= START_DATE]
                    return df
            except Exception:
                continue
    return None


def calculate_weekend_returns(df: pd.DataFrame) -> List[Dict]:
    """Calculate weekend returns (Friday close -> Monday open)."""
    if len(df) < 10:
        return []
    
    df = df.copy()
    df["weekday"] = df["date"].dt.weekday  # Monday=0, Friday=4
    
    weekend_returns = []
    
    # Find Fridays
    fridays = df[df["weekday"] == 4].copy()
    
    for _, friday_row in fridays.iterrows():
        friday_date = friday_row["date"]
        friday_close = friday_row["close"]
        
        # Look for next Monday (could be 3 days later normally, or more if holiday)
        for days_ahead in range(3, 8):  # Check up to 7 days ahead
            next_date = friday_date + timedelta(days=days_ahead)
            monday_rows = df[df["date"] == next_date]
            
            if len(monday_rows) > 0:
                monday_row = monday_rows.iloc[0]
                if monday_row["weekday"] == 0:  # Confirm it's Monday
                    monday_open = monday_row["open"]
                    
                    # Calculate return
                    ret = (monday_open / friday_close - 1) * 100
                    
                    weekend_returns.append({
                        "friday_date": friday_date,
                        "monday_date": next_date,
                        "friday_close": friday_close,
                        "monday_open": monday_open,
                        "return_pct": ret,
                        "year": friday_date.year,
                    })
                break
    
    return weekend_returns


def analyze_basket(basket_name: str, basket_path: str) -> Dict:
    """Analyze weekend effect for a basket."""
    symbols = load_basket(basket_path)
    
    all_returns = []
    symbols_processed = 0
    
    for symbol in symbols:
        df = load_ohlc_data(symbol)
        if df is None or len(df) < 100:
            continue
        
        returns = calculate_weekend_returns(df)
        for r in returns:
            r["symbol"] = symbol
        all_returns.extend(returns)
        symbols_processed += 1
    
    if not all_returns:
        return {"basket": basket_name, "symbols": 0, "trades": 0}
    
    returns_df = pd.DataFrame(all_returns)
    
    # Overall statistics
    total_trades = len(returns_df)
    avg_return = returns_df["return_pct"].mean()
    median_return = returns_df["return_pct"].median()
    std_return = returns_df["return_pct"].std()
    positive_pct = (returns_df["return_pct"] > 0).mean() * 100
    
    # Yearly breakdown
    yearly_stats = returns_df.groupby("year").agg({
        "return_pct": ["count", "mean", "median", "std"],
    }).round(4)
    yearly_stats.columns = ["trades", "avg_return", "median_return", "std"]
    yearly_stats["positive_pct"] = returns_df.groupby("year").apply(
        lambda x: (x["return_pct"] > 0).mean() * 100
    )
    
    return {
        "basket": basket_name,
        "symbols": symbols_processed,
        "total_trades": total_trades,
        "avg_return_pct": avg_return,
        "median_return_pct": median_return,
        "std_return_pct": std_return,
        "positive_pct": positive_pct,
        "yearly_stats": yearly_stats,
        "returns_df": returns_df,
    }


def main():
    print(f"\n{'═'*80}")
    print(f"WEEKEND EFFECT ANALYSIS")
    print(f"Buy Friday Close → Sell Monday Open")
    print(f"Period: {START_DATE.strftime('%Y-%m-%d')} to Present (~10 Years)")
    print(f"{'═'*80}")
    
    baskets = [
        ("LARGE CAP", "data/baskets/basket_large.txt"),
        ("MID CAP", "data/baskets/basket_mid.txt"),
        ("SMALL CAP", "data/baskets/basket_small.txt"),
    ]
    
    results = []
    
    for basket_name, basket_path in baskets:
        print(f"\n📊 Analyzing {basket_name}...")
        result = analyze_basket(basket_name, basket_path)
        results.append(result)
        
        if result.get("total_trades", 0) == 0:
            print(f"   No data available")
            continue
        
        print(f"   Symbols: {result['symbols']}")
        print(f"   Total Weekend Trades: {result['total_trades']:,}")
        print(f"   Average Return: {result['avg_return_pct']:+.4f}%")
        print(f"   Median Return: {result['median_return_pct']:+.4f}%")
        print(f"   Std Dev: {result['std_return_pct']:.4f}%")
        print(f"   Positive Weekends: {result['positive_pct']:.2f}%")
    
    # Print detailed yearly comparison
    print(f"\n{'═'*80}")
    print(f"YEARLY BREAKDOWN BY MARKET CAP")
    print(f"{'═'*80}")
    
    for result in results:
        if "yearly_stats" not in result:
            continue
        
        print(f"\n📈 {result['basket']}")
        print(f"{'─'*70}")
        print(f"{'Year':<6} {'Trades':>8} {'Avg Ret %':>12} {'Median %':>12} {'Positive %':>12}")
        print(f"{'─'*70}")
        
        yearly = result["yearly_stats"]
        for year in sorted(yearly.index):
            row = yearly.loc[year]
            print(f"{year:<6} {int(row['trades']):>8} {row['avg_return']:>+12.4f} {row['median_return']:>+12.4f} {row['positive_pct']:>12.2f}")
        
        # Total row
        print(f"{'─'*70}")
        print(f"{'TOTAL':<6} {result['total_trades']:>8} {result['avg_return_pct']:>+12.4f} {result['median_return_pct']:>+12.4f} {result['positive_pct']:>12.2f}")
    
    # Summary comparison
    print(f"\n{'═'*80}")
    print(f"SUMMARY COMPARISON")
    print(f"{'═'*80}")
    print(f"\n{'Basket':<12} {'Trades':>10} {'Avg Ret %':>12} {'Median %':>12} {'Win Rate':>12} {'Sharpe*':>10}")
    print(f"{'─'*70}")
    
    for result in results:
        if result.get("total_trades", 0) == 0:
            continue
        
        # Annualized Sharpe approximation (assuming ~52 weekends/year)
        sharpe = (result['avg_return_pct'] / result['std_return_pct']) * np.sqrt(52) if result['std_return_pct'] > 0 else 0
        
        print(f"{result['basket']:<12} {result['total_trades']:>10,} {result['avg_return_pct']:>+12.4f} {result['median_return_pct']:>+12.4f} {result['positive_pct']:>11.2f}% {sharpe:>10.2f}")
    
    print(f"\n* Sharpe ratio annualized assuming 52 trading weekends per year")
    
    # Calculate cumulative returns
    print(f"\n{'═'*80}")
    print(f"CUMULATIVE WEEKEND EFFECT (Compounded)")
    print(f"{'═'*80}")
    
    for result in results:
        if "returns_df" not in result:
            continue
        
        returns_df = result["returns_df"].sort_values("friday_date")
        
        # Calculate compounded return
        cumulative = (1 + returns_df["return_pct"] / 100).prod() - 1
        cumulative_pct = cumulative * 100
        
        # Calculate CAGR
        years = (returns_df["friday_date"].max() - returns_df["friday_date"].min()).days / 365.25
        if years > 0 and cumulative > -1:
            cagr = ((1 + cumulative) ** (1 / years) - 1) * 100
        else:
            cagr = 0
        
        print(f"\n{result['basket']}:")
        print(f"   Total Compounded Return: {cumulative_pct:+.2f}%")
        print(f"   CAGR: {cagr:+.2f}%")
        print(f"   Period: {years:.1f} years")
    
    # Save detailed results
    output_path = Path("reports/weekend_effect_analysis.csv")
    output_path.parent.mkdir(exist_ok=True)
    
    all_data = []
    for result in results:
        if "returns_df" in result:
            df = result["returns_df"].copy()
            df["basket"] = result["basket"]
            all_data.append(df)
    
    if all_data:
        combined = pd.concat(all_data, ignore_index=True)
        combined.to_csv(output_path, index=False)
        print(f"\n💾 Saved detailed data to: {output_path}")


if __name__ == "__main__":
    main()


# ========== FROM: month_end_strategy_analysis.py ==========

#!/usr/bin/env python3
"""
Month-End to Month-Start Trading Strategy Analysis
===================================================
Strategy: Buy at open of 3rd last trading day of month N,
          Sell at close of 3rd trading day of month N+1

Analyzes returns by:
- Overall basket
- Market cap (Large/Mid/Small)
- Sector
- Individual stock performance
"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from calendar import monthrange

import pandas as pd
import numpy as np

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
DATA_DIR = Path("data")

# Baskets
BASKETS = {
    "large": "data/baskets/basket_large.txt",
    "mid": "data/baskets/basket_mid.txt",
    "small": "data/baskets/basket_small.txt",
}

# Transaction costs (both legs combined)
TRANSACTION_COST_PCT = 0.37


def load_basket(basket_path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(basket_path) as f:
        return [line.strip() for line in f if line.strip()]


def load_sector_mapping() -> Dict[str, Dict[str, str]]:
    """Load sector mapping from scrip master files."""
    sector_map = {}
    
    # Try dhan scrip master first
    dhan_file = DATA_DIR / "dhan-scrip-master-detailed.csv"
    if dhan_file.exists():
        try:
            df = pd.read_csv(dhan_file, low_memory=False)
            if "SEM_TRADING_SYMBOL" in df.columns and "SECTOR" in df.columns:
                for _, row in df.iterrows():
                    symbol = str(row.get("SEM_TRADING_SYMBOL", "")).strip()
                    sector = str(row.get("SECTOR", "")).strip()
                    cap_type = str(row.get("CAP_TYPE", "")).strip()
                    
                    if symbol and sector and sector != "" and sector != "nan":
                        # Clean symbol
                        clean_symbol = symbol.split("-")[0]
                        if clean_symbol not in sector_map:
                            sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
        except Exception as e:
            print(f"Error loading dhan scrip master: {e}")
    
    # Also load from cap files directly for more accurate mapping
    cap_files = [
        ("Large Cap_NSE_2026-01-02.csv", "Large Cap"),
        ("Mid Cap_NSE_2026-01-02.csv", "Mid Cap"),
        ("Small Cap_NSE_2026-01-02.csv", "Small Cap"),
    ]
    
    for filename, cap_type in cap_files:
        filepath = DATA_DIR / filename
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                for _, row in df.iterrows():
                    symbol = str(row.get("Symbol", "")).strip()
                    sector = str(row.get("Sector", "")).strip()
                    if symbol and sector and sector != "nan":
                        clean_symbol = symbol.split(".")[0]
                        sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return sector_map


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
        
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return None
        
        df = df[~df.index.duplicated(keep='first')]
        return df.sort_index()
    except Exception as e:
        print(f"Error loading {symbol}: {e}")
        return None


def identify_trading_days_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Add month position information to dataframe."""
    df = df.copy()
    df["year"] = df.index.year
    df["month"] = df.index.month
    df["year_month"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    
    # Calculate trading day position within month
    df["trading_day_in_month"] = df.groupby("year_month").cumcount() + 1
    
    # Calculate trading days from end of month
    df["trading_days_from_end"] = df.groupby("year_month")["trading_day_in_month"].transform("max") - df["trading_day_in_month"] + 1
    
    return df


def calculate_strategy_returns(symbol: str, df: pd.DataFrame) -> List[Dict]:
    """
    Calculate returns for the strategy:
    - Entry: Open of 3rd last trading day of month N
    - Exit: Close of 3rd trading day of month N+1
    """
    df = identify_trading_days_by_month(df)
    
    trades = []
    
    # Get unique year-months
    year_months = sorted(df["year_month"].unique())
    
    for i, ym in enumerate(year_months[:-1]):  # Skip last month (no exit)
        next_ym = year_months[i + 1] if i + 1 < len(year_months) else None
        if not next_ym:
            continue
        
        # Find 3rd last trading day of current month (entry)
        month_data = df[df["year_month"] == ym]
        entry_days = month_data[month_data["trading_days_from_end"] == 3]
        
        if entry_days.empty:
            continue
        
        entry_date = entry_days.index[0]
        entry_price = entry_days.iloc[0]["open"]
        
        # Find 3rd trading day of next month (exit)
        next_month_data = df[df["year_month"] == next_ym]
        exit_days = next_month_data[next_month_data["trading_day_in_month"] == 3]
        
        if exit_days.empty:
            continue
        
        exit_date = exit_days.index[0]
        exit_price = exit_days.iloc[0]["close"]
        
        # Calculate returns
        gross_return_pct = ((exit_price - entry_price) / entry_price) * 100
        net_return_pct = gross_return_pct - TRANSACTION_COST_PCT
        
        trades.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_return_pct": gross_return_pct,
            "net_return_pct": net_return_pct,
            "holding_days": (exit_date - entry_date).days,
            "entry_month": ym,
            "exit_month": next_ym,
        })
    
    return trades


def analyze_basket(basket_name: str, basket_path: str, sector_map: Dict) -> pd.DataFrame:
    """Analyze all symbols in a basket."""
    print(f"\n📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    symbols = list(dict.fromkeys(symbols))  # Remove duplicates
    print(f"   Loaded {len(symbols)} symbols")
    
    all_trades = []
    symbols_with_data = 0
    
    for symbol in symbols:
        df = load_ohlc_data(symbol, CACHE_DIR)
        if df is not None and len(df) > 30:
            trades = calculate_strategy_returns(symbol, df)
            if trades:
                # Add sector info
                sector_info = sector_map.get(symbol, {"sector": "Unknown", "cap_type": basket_name.capitalize()})
                for trade in trades:
                    trade["sector"] = sector_info.get("sector", "Unknown")
                    trade["cap_type"] = basket_name.capitalize()
                all_trades.extend(trades)
                symbols_with_data += 1
    
    print(f"   Found data for {symbols_with_data} symbols")
    print(f"   Generated {len(all_trades)} trades")
    
    return pd.DataFrame(all_trades)


def analyze_results(trades_df: pd.DataFrame, group_by: str, title: str):
    """Analyze and print results grouped by a column."""
    if trades_df.empty:
        print(f"\nNo trades to analyze for {title}")
        return pd.DataFrame()
    
    grouped = trades_df.groupby(group_by).agg({
        "gross_return_pct": ["mean", "sum", "std", "count"],
        "net_return_pct": ["mean", "sum"],
    })
    
    grouped.columns = ["_".join(col) for col in grouped.columns]
    grouped = grouped.reset_index()
    
    # Calculate win rate
    win_rates = trades_df.groupby(group_by).apply(
        lambda x: pd.Series({
            "win_rate": (x["net_return_pct"] > 0).mean() * 100,
            "avg_winner": x[x["net_return_pct"] > 0]["net_return_pct"].mean() if (x["net_return_pct"] > 0).any() else 0,
            "avg_loser": x[x["net_return_pct"] <= 0]["net_return_pct"].mean() if (x["net_return_pct"] <= 0).any() else 0,
        }),
        include_groups=False
    ).reset_index()
    
    grouped = grouped.merge(win_rates, on=group_by)
    grouped = grouped.sort_values("net_return_pct_sum", ascending=False)
    
    print(f"\n{'='*80}")
    print(f"{title}")
    print("="*80)
    print(f"{'Category':<25} {'Trades':>8} {'Gross%':>10} {'Net%':>10} {'Win%':>8} {'Avg Win':>10} {'Avg Loss':>10}")
    print("-"*80)
    
    for _, row in grouped.iterrows():
        print(f"{str(row[group_by])[:24]:<25} {int(row['gross_return_pct_count']):>8} "
              f"{row['gross_return_pct_sum']:>10.2f} {row['net_return_pct_sum']:>10.2f} "
              f"{row['win_rate']:>8.1f} {row['avg_winner']:>10.2f} {row['avg_loser']:>10.2f}")
    
    return grouped


def analyze_by_symbol(trades_df: pd.DataFrame, top_n: int = 20):
    """Analyze top and bottom performing symbols."""
    if trades_df.empty:
        return pd.DataFrame()
    
    by_symbol = trades_df.groupby("symbol").agg({
        "gross_return_pct": ["mean", "sum", "count"],
        "net_return_pct": ["mean", "sum"],
        "sector": "first",
        "cap_type": "first",
    })
    
    by_symbol.columns = ["_".join(col) for col in by_symbol.columns]
    by_symbol = by_symbol.reset_index()
    
    # Win rate
    win_rates = trades_df.groupby("symbol").apply(
        lambda x: (x["net_return_pct"] > 0).mean() * 100,
        include_groups=False
    ).reset_index()
    win_rates.columns = ["symbol", "win_rate"]
    
    by_symbol = by_symbol.merge(win_rates, on="symbol")
    
    print(f"\n{'='*80}")
    print(f"TOP {top_n} PERFORMING SYMBOLS (by total net return)")
    print("="*80)
    print(f"{'Symbol':<15} {'Sector':<20} {'Cap':<10} {'Trades':>7} {'Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    top_symbols = by_symbol.nlargest(top_n, "net_return_pct_sum")
    for _, row in top_symbols.iterrows():
        print(f"{row['symbol']:<15} {str(row['sector_first'])[:19]:<20} {str(row['cap_type_first']):<10} "
              f"{int(row['gross_return_pct_count']):>7} {row['net_return_pct_sum']:>10.2f} {row['win_rate']:>8.1f}")
    
    print(f"\n{'='*80}")
    print(f"BOTTOM {top_n} PERFORMING SYMBOLS (by total net return)")
    print("="*80)
    print(f"{'Symbol':<15} {'Sector':<20} {'Cap':<10} {'Trades':>7} {'Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    bottom_symbols = by_symbol.nsmallest(top_n, "net_return_pct_sum")
    for _, row in bottom_symbols.iterrows():
        print(f"{row['symbol']:<15} {str(row['sector_first'])[:19]:<20} {str(row['cap_type_first']):<10} "
              f"{int(row['gross_return_pct_count']):>7} {row['net_return_pct_sum']:>10.2f} {row['win_rate']:>8.1f}")
    
    return by_symbol


def analyze_by_month(trades_df: pd.DataFrame):
    """Analyze performance by entry month (which month you enter)."""
    if trades_df.empty:
        return pd.DataFrame()
    
    # Extract month from entry_month
    trades_df = trades_df.copy()
    trades_df["entry_month_num"] = trades_df["entry_month"].str[-2:].astype(int)
    
    month_names = {1: "January", 2: "February", 3: "March", 4: "April", 
                   5: "May", 6: "June", 7: "July", 8: "August",
                   9: "September", 10: "October", 11: "November", 12: "December"}
    
    trades_df["entry_month_name"] = trades_df["entry_month_num"].map(month_names)
    
    by_month = trades_df.groupby("entry_month_name").agg({
        "gross_return_pct": ["mean", "sum", "count"],
        "net_return_pct": ["mean", "sum"],
    })
    
    by_month.columns = ["_".join(col) for col in by_month.columns]
    by_month = by_month.reset_index()
    
    # Win rate
    win_rates = trades_df.groupby("entry_month_name").apply(
        lambda x: (x["net_return_pct"] > 0).mean() * 100,
        include_groups=False
    ).reset_index()
    win_rates.columns = ["entry_month_name", "win_rate"]
    
    by_month = by_month.merge(win_rates, on="entry_month_name")
    
    # Sort by calendar order
    month_order = list(month_names.values())
    by_month["sort_order"] = by_month["entry_month_name"].map({m: i for i, m in enumerate(month_order)})
    by_month = by_month.sort_values("sort_order")
    
    print(f"\n{'='*80}")
    print("PERFORMANCE BY ENTRY MONTH")
    print("(Which month you enter the trade)")
    print("="*80)
    print(f"{'Month':<15} {'Trades':>8} {'Gross%':>10} {'Net%':>10} {'Avg Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    for _, row in by_month.iterrows():
        print(f"{row['entry_month_name']:<15} {int(row['gross_return_pct_count']):>8} "
              f"{row['gross_return_pct_sum']:>10.2f} {row['net_return_pct_sum']:>10.2f} "
              f"{row['net_return_pct_mean']:>10.2f} {row['win_rate']:>8.1f}")
    
    return by_month


def print_overall_summary(trades_df: pd.DataFrame):
    """Print overall strategy summary."""
    if trades_df.empty:
        print("\nNo trades to summarize")
        return
    
    total_trades = len(trades_df)
    total_gross = trades_df["gross_return_pct"].sum()
    total_net = trades_df["net_return_pct"].sum()
    avg_gross = trades_df["gross_return_pct"].mean()
    avg_net = trades_df["net_return_pct"].mean()
    win_rate = (trades_df["net_return_pct"] > 0).mean() * 100
    avg_holding = trades_df["holding_days"].mean()
    
    # Winners vs Losers
    winners = trades_df[trades_df["net_return_pct"] > 0]
    losers = trades_df[trades_df["net_return_pct"] <= 0]
    
    print("\n" + "="*80)
    print("OVERALL STRATEGY SUMMARY")
    print("="*80)
    print(f"\nStrategy: Buy at OPEN of 3rd last trading day of month")
    print(f"          Sell at CLOSE of 3rd trading day of next month")
    print(f"Transaction Cost: {TRANSACTION_COST_PCT}% (both legs)")
    print(f"\nDate Range: {trades_df['entry_date'].min().date()} to {trades_df['exit_date'].max().date()}")
    print(f"Total Trades: {total_trades}")
    print(f"Average Holding Period: {avg_holding:.1f} days")
    
    print(f"\n--- RETURNS ---")
    print(f"Total Gross Return: {total_gross:.2f}%")
    print(f"Total Net Return:   {total_net:.2f}%")
    print(f"Avg Gross per Trade: {avg_gross:.3f}%")
    print(f"Avg Net per Trade:   {avg_net:.3f}%")
    
    print(f"\n--- WIN/LOSS ANALYSIS ---")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Winners: {len(winners)} trades, avg gain: {winners['net_return_pct'].mean():.2f}%")
    print(f"Losers:  {len(losers)} trades, avg loss: {losers['net_return_pct'].mean():.2f}%")
    
    if len(losers) > 0 and len(winners) > 0:
        profit_factor = abs(winners["net_return_pct"].sum() / losers["net_return_pct"].sum())
        print(f"Profit Factor: {profit_factor:.2f}")


def main():
    print("="*80)
    print("MONTH-END TO MONTH-START TRADING STRATEGY ANALYSIS")
    print("="*80)
    print("\nStrategy Definition:")
    print("  Entry: Open of 3rd last trading day of month N")
    print("  Exit:  Close of 3rd trading day of month N+1")
    print(f"  Transaction Cost: {TRANSACTION_COST_PCT}% (combined for both legs)")
    print("="*80)
    
    # Load sector mapping
    print("\n📂 Loading sector mapping...")
    sector_map = load_sector_mapping()
    print(f"   Loaded sector data for {len(sector_map)} symbols")
    
    # Analyze all baskets
    all_trades = []
    
    for basket_name, basket_path in BASKETS.items():
        if os.path.exists(basket_path):
            trades_df = analyze_basket(basket_name, basket_path, sector_map)
            if not trades_df.empty:
                all_trades.append(trades_df)
    
    if not all_trades:
        print("\n❌ No trades generated. Exiting.")
        return
    
    # Combine all trades
    combined_trades = pd.concat(all_trades, ignore_index=True)
    print(f"\n📈 Total trades across all baskets: {len(combined_trades)}")
    
    # Overall summary
    print_overall_summary(combined_trades)
    
    # Analysis by cap type
    cap_analysis = analyze_results(combined_trades, "cap_type", "PERFORMANCE BY MARKET CAP")
    
    # Analysis by sector
    sector_analysis = analyze_results(combined_trades, "sector", "PERFORMANCE BY SECTOR")
    
    # Analysis by entry month
    month_analysis = analyze_by_month(combined_trades)
    
    # Top/Bottom symbols
    symbol_analysis = analyze_by_symbol(combined_trades, top_n=15)
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = f"reports/analysis/month_end_strategy_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n💾 Saving results to: {output_dir}")
    
    combined_trades.to_csv(f"{output_dir}/all_trades.csv", index=False)
    if not cap_analysis.empty:
        cap_analysis.to_csv(f"{output_dir}/by_cap_type.csv", index=False)
    if not sector_analysis.empty:
        sector_analysis.to_csv(f"{output_dir}/by_sector.csv", index=False)
    if not month_analysis.empty:
        month_analysis.to_csv(f"{output_dir}/by_month.csv", index=False)
    if not symbol_analysis.empty:
        symbol_analysis.to_csv(f"{output_dir}/by_symbol.csv", index=False)
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()


# ========== FROM: extended_totm_analysis.py ==========

#!/usr/bin/env python3
"""
Extended TOTM (Turn of the Month) Strategy Analysis
====================================================
Strategy: Entry on 25th of month (open), Exit on 3rd of next month (close)
Universe: Large Cap stocks only
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path

CACHE_DIR = Path("data/cache/dhan/daily")
BASKET_PATH = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37


def load_basket(path):
    with open(path) as f:
        return list(dict.fromkeys([line.strip() for line in f if line.strip()]))


def find_cache_file(symbol):
    matches = glob.glob(str(CACHE_DIR / f"dhan_*_{symbol}_1d.csv"))
    return matches[0] if matches else None


def load_ohlc(symbol):
    cache_file = find_cache_file(symbol)
    if not cache_file:
        return None
    df = pd.read_csv(cache_file)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df = df[~df.index.duplicated(keep="first")]
    return df.sort_index()


def calculate_totm_trades(symbol, df):
    """Extended TOTM: Entry on 25th open, Exit on 3rd close of next month"""
    trades = []
    df = df.copy()
    df["day"] = df.index.day
    df["month"] = df.index.month
    df["year"] = df.index.year
    df["year_month"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    
    year_months = sorted(df["year_month"].unique())
    
    for i, ym in enumerate(year_months[:-1]):
        next_ym = year_months[i + 1]
        
        # Find entry: first trading day on or after 25th of current month
        month_data = df[df["year_month"] == ym]
        entry_candidates = month_data[month_data["day"] >= 25]
        
        if entry_candidates.empty:
            continue
        
        entry_date = entry_candidates.index[0]
        entry_price = entry_candidates.iloc[0]["open"]
        
        # Find exit: first trading day on or after 3rd of next month
        next_month_data = df[df["year_month"] == next_ym]
        exit_candidates = next_month_data[next_month_data["day"] >= 3]
        
        if exit_candidates.empty:
            continue
        
        exit_date = exit_candidates.index[0]
        exit_price = exit_candidates.iloc[0]["close"]
        
        gross_ret = ((exit_price - entry_price) / entry_price) * 100
        net_ret = gross_ret - TRANSACTION_COST_PCT
        
        trades.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_return_pct": gross_ret,
            "net_return_pct": net_ret,
            "holding_days": (exit_date - entry_date).days,
            "entry_year": entry_date.year,
            "entry_month": ym,
        })
    
    return trades


def main():
    # Load symbols
    symbols = load_basket(BASKET_PATH)
    print(f"Loaded {len(symbols)} symbols from large cap basket")
    
    # Generate all trades
    all_trades = []
    for symbol in symbols:
        df = load_ohlc(symbol)
        if df is not None and len(df) > 30:
            trades = calculate_totm_trades(symbol, df)
            all_trades.extend(trades)
    
    trades_df = pd.DataFrame(all_trades)
    print(f"Generated {len(trades_df)} trades")
    print(f"Date Range: {trades_df['entry_date'].min().date()} to {trades_df['exit_date'].max().date()}")
    print(f"Avg Holding Period: {trades_df['holding_days'].mean():.1f} days")
    
    # Overall Summary
    print("\n" + "="*80)
    print("EXTENDED TOTM STRATEGY - LARGE CAP ONLY")
    print("Entry: Open on/after 25th | Exit: Close on/after 3rd of next month")
    print(f"Transaction Cost: {TRANSACTION_COST_PCT}%")
    print("="*80)
    
    total_trades = len(trades_df)
    winners = trades_df[trades_df["net_return_pct"] > 0]
    losers = trades_df[trades_df["net_return_pct"] <= 0]
    win_rate = len(winners) / total_trades * 100
    pf = abs(winners["net_return_pct"].sum() / losers["net_return_pct"].sum()) if len(losers) > 0 else float("inf")
    
    print(f"\n--- OVERALL ---")
    print(f"Total Trades: {total_trades}")
    print(f"Total Net Return: {trades_df['net_return_pct'].sum():.2f}%")
    print(f"Avg Net P&L per Trade: {trades_df['net_return_pct'].mean():.3f}%")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Avg Winner: {winners['net_return_pct'].mean():.2f}%")
    print(f"Avg Loser: {losers['net_return_pct'].mean():.2f}%")
    
    # Year-wise breakdown
    print("\n" + "="*80)
    print("YEAR-WISE BREAKDOWN")
    print("="*80)
    print(f"{'Year':<8} {'Trades':>8} {'Net Ret%':>12} {'Avg Net%':>12} {'Win Rate':>10} {'PF':>8}")
    print("-"*60)
    
    for year in sorted(trades_df["entry_year"].unique()):
        year_trades = trades_df[trades_df["entry_year"] == year]
        yr_winners = year_trades[year_trades["net_return_pct"] > 0]
        yr_losers = year_trades[year_trades["net_return_pct"] <= 0]
        yr_wr = len(yr_winners) / len(year_trades) * 100
        yr_pf = abs(yr_winners["net_return_pct"].sum() / yr_losers["net_return_pct"].sum()) if len(yr_losers) > 0 and yr_losers["net_return_pct"].sum() != 0 else float("inf")
        
        print(f"{year:<8} {len(year_trades):>8} {year_trades['net_return_pct'].sum():>12.2f} {year_trades['net_return_pct'].mean():>12.3f} {yr_wr:>10.1f}% {yr_pf:>8.2f}")
    
    # Save trades
    os.makedirs("reports/analysis", exist_ok=True)
    trades_df.to_csv("reports/analysis/extended_totm_large_cap.csv", index=False)
    print(f"\n✅ Saved trades to reports/analysis/extended_totm_large_cap.csv")


if __name__ == "__main__":
    main()


# ========== FROM: returns_time_patterns_analysis.py ==========

#!/usr/bin/env python3
"""
Returns Time Pattern Analysis
=============================
Comprehensive analysis of overnight, intraday, and total returns by various time patterns.

Patterns Analyzed:
- Day of the week (Monday-Friday)
- Day of the month (1-31)
- First/Last N days of month (3, 5, 10 days)
- Month of the year (January-December)
- Week of the year
- Quarter of the year
- Beginning/End of year patterns
- Pre/Post holiday effects (around weekends)
- Expiry week patterns (monthly F&O expiry)
"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from calendar import monthrange

import pandas as pd
import numpy as np

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
DEFAULT_BASKET = "data/baskets/basket_large.txt"


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
    """Calculate equal-weighted average returns for a basket of symbols."""
    all_returns = []
    loaded_symbols = []
    
    for symbol in symbols:
        df = load_ohlc_data(symbol, cache_dir)
        if df is not None and len(df) > 1:
            returns = calculate_overnight_intraday_returns(df)
            if not returns.empty:
                returns = returns[~returns.index.duplicated(keep='first')]
                returns = returns[["overnight_pct", "intraday_pct", "total_pct"]]
                returns.columns = [f"{symbol}_{col}" for col in returns.columns]
                all_returns.append(returns)
                loaded_symbols.append(symbol)
    
    if not all_returns:
        return pd.DataFrame()
    
    # Combine all symbols
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
    
    result = result[~result.index.duplicated(keep='first')]
    result = result.sort_index()
    
    print(f"   Loaded {len(loaded_symbols)} symbols with data")
    
    return result


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add all time-based features for pattern analysis."""
    df = df.copy()
    
    # Basic time features
    df["day_of_week"] = df.index.dayofweek  # 0=Monday, 4=Friday
    df["day_name"] = df.index.day_name()
    df["day_of_month"] = df.index.day
    df["month"] = df.index.month
    df["month_name"] = df.index.month_name()
    df["year"] = df.index.year
    df["week_of_year"] = df.index.isocalendar().week.values
    df["quarter"] = df.index.quarter
    
    # Days from month start/end
    df["days_in_month"] = df.index.to_series().apply(lambda x: monthrange(x.year, x.month)[1]).values
    df["days_from_start"] = df["day_of_month"]
    df["days_from_end"] = df["days_in_month"] - df["day_of_month"] + 1
    
    # First/Last N days flags
    for n in [3, 5, 10]:
        df[f"first_{n}_days"] = df["day_of_month"] <= n
        df[f"last_{n}_days"] = df["days_from_end"] <= n
    
    # Middle of month
    df["middle_of_month"] = (~df["first_10_days"]) & (~df["last_10_days"])
    
    # Beginning/End of year
    df["first_week_of_year"] = df["week_of_year"] == 1
    df["last_week_of_year"] = df["week_of_year"] >= 52
    df["january"] = df["month"] == 1
    df["december"] = df["month"] == 12
    
    # Pre/Post weekend (Friday/Monday)
    df["is_friday"] = df["day_of_week"] == 4
    df["is_monday"] = df["day_of_week"] == 0
    
    # F&O Expiry week (last Thursday of month - approximate as last 7 days containing Thursday)
    # More accurate: find if this week contains the last Thursday
    df["expiry_week"] = False
    for idx in df.index:
        # Get last day of month
        last_day = monthrange(idx.year, idx.month)[1]
        # Find last Thursday (weekday 3)
        for d in range(last_day, last_day - 7, -1):
            try:
                check_date = idx.replace(day=d)
                if check_date.weekday() == 3:  # Thursday
                    last_thursday = d
                    break
            except:
                continue
        # Check if current day is in expiry week (last Thursday ± 3 days)
        df.loc[idx, "expiry_week"] = abs(idx.day - last_thursday) <= 3
    
    return df


def aggregate_stats(df: pd.DataFrame, group_col: str, sort_col: Optional[str] = None) -> pd.DataFrame:
    """Aggregate return statistics by a grouping column."""
    agg_dict = {
        "overnight_pct": ["mean", "sum", "std", "count"],
        "intraday_pct": ["mean", "sum", "std"],
        "total_pct": ["mean", "sum", "std"]
    }
    
    result = df.groupby(group_col).agg(agg_dict)
    result.columns = ["_".join(col).strip() for col in result.columns.values]
    result = result.reset_index()
    
    # Calculate win rates
    win_rates = df.groupby(group_col).apply(
        lambda x: pd.Series({
            "overnight_win_rate": (x["overnight_pct"] > 0).mean() * 100,
            "intraday_win_rate": (x["intraday_pct"] > 0).mean() * 100,
            "total_win_rate": (x["total_pct"] > 0).mean() * 100
        }),
        include_groups=False
    ).reset_index()
    
    result = result.merge(win_rates, on=group_col)
    
    if sort_col:
        result = result.sort_values(sort_col)
    
    return result


def analyze_by_day_of_week(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by day of the week."""
    result = aggregate_stats(df, "day_name")
    # Sort by weekday order
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    result["sort_order"] = result["day_name"].map({d: i for i, d in enumerate(day_order)})
    result = result.sort_values("sort_order").drop("sort_order", axis=1)
    return result


def analyze_by_day_of_month(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by day of the month (1-31)."""
    result = aggregate_stats(df, "day_of_month", "day_of_month")
    return result


def analyze_first_last_days(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns for first/last N days of month."""
    results = []
    
    for n in [3, 5, 10]:
        # First N days
        first_n = df[df[f"first_{n}_days"]]
        first_stats = {
            "period": f"First {n} days",
            "overnight_mean": first_n["overnight_pct"].mean(),
            "overnight_sum": first_n["overnight_pct"].sum(),
            "intraday_mean": first_n["intraday_pct"].mean(),
            "intraday_sum": first_n["intraday_pct"].sum(),
            "total_mean": first_n["total_pct"].mean(),
            "total_sum": first_n["total_pct"].sum(),
            "trading_days": len(first_n),
            "overnight_win_rate": (first_n["overnight_pct"] > 0).mean() * 100,
            "intraday_win_rate": (first_n["intraday_pct"] > 0).mean() * 100,
            "total_win_rate": (first_n["total_pct"] > 0).mean() * 100
        }
        results.append(first_stats)
        
        # Last N days
        last_n = df[df[f"last_{n}_days"]]
        last_stats = {
            "period": f"Last {n} days",
            "overnight_mean": last_n["overnight_pct"].mean(),
            "overnight_sum": last_n["overnight_pct"].sum(),
            "intraday_mean": last_n["intraday_pct"].mean(),
            "intraday_sum": last_n["intraday_pct"].sum(),
            "total_mean": last_n["total_pct"].mean(),
            "total_sum": last_n["total_pct"].sum(),
            "trading_days": len(last_n),
            "overnight_win_rate": (last_n["overnight_pct"] > 0).mean() * 100,
            "intraday_win_rate": (last_n["intraday_pct"] > 0).mean() * 100,
            "total_win_rate": (last_n["total_pct"] > 0).mean() * 100
        }
        results.append(last_stats)
    
    # Middle of month
    middle = df[df["middle_of_month"]]
    middle_stats = {
        "period": "Middle (11th-21st)",
        "overnight_mean": middle["overnight_pct"].mean(),
        "overnight_sum": middle["overnight_pct"].sum(),
        "intraday_mean": middle["intraday_pct"].mean(),
        "intraday_sum": middle["intraday_pct"].sum(),
        "total_mean": middle["total_pct"].mean(),
        "total_sum": middle["total_pct"].sum(),
        "trading_days": len(middle),
        "overnight_win_rate": (middle["overnight_pct"] > 0).mean() * 100,
        "intraday_win_rate": (middle["intraday_pct"] > 0).mean() * 100,
        "total_win_rate": (middle["total_pct"] > 0).mean() * 100
    }
    results.append(middle_stats)
    
    return pd.DataFrame(results)


def analyze_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by calendar month."""
    result = aggregate_stats(df, "month_name")
    # Sort by month order
    month_order = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    result["sort_order"] = result["month_name"].map({m: i for i, m in enumerate(month_order)})
    result = result.sort_values("sort_order").drop("sort_order", axis=1)
    return result


def analyze_by_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by quarter."""
    result = aggregate_stats(df, "quarter", "quarter")
    result["quarter"] = result["quarter"].map({1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"})
    return result


def analyze_by_week_of_year(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by week of year."""
    result = aggregate_stats(df, "week_of_year", "week_of_year")
    return result


def analyze_special_periods(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze special periods (Mondays, Fridays, expiry week, etc.)."""
    results = []
    
    # Monday vs Rest
    monday = df[df["is_monday"]]
    results.append({
        "period": "Mondays",
        "overnight_mean": monday["overnight_pct"].mean(),
        "intraday_mean": monday["intraday_pct"].mean(),
        "total_mean": monday["total_pct"].mean(),
        "trading_days": len(monday),
        "overnight_win_rate": (monday["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (monday["total_pct"] > 0).mean() * 100
    })
    
    # Friday vs Rest
    friday = df[df["is_friday"]]
    results.append({
        "period": "Fridays",
        "overnight_mean": friday["overnight_pct"].mean(),
        "intraday_mean": friday["intraday_pct"].mean(),
        "total_mean": friday["total_pct"].mean(),
        "trading_days": len(friday),
        "overnight_win_rate": (friday["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (friday["total_pct"] > 0).mean() * 100
    })
    
    # Expiry week
    expiry = df[df["expiry_week"]]
    non_expiry = df[~df["expiry_week"]]
    results.append({
        "period": "Expiry Week",
        "overnight_mean": expiry["overnight_pct"].mean(),
        "intraday_mean": expiry["intraday_pct"].mean(),
        "total_mean": expiry["total_pct"].mean(),
        "trading_days": len(expiry),
        "overnight_win_rate": (expiry["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (expiry["total_pct"] > 0).mean() * 100
    })
    
    results.append({
        "period": "Non-Expiry Week",
        "overnight_mean": non_expiry["overnight_pct"].mean(),
        "intraday_mean": non_expiry["intraday_pct"].mean(),
        "total_mean": non_expiry["total_pct"].mean(),
        "trading_days": len(non_expiry),
        "overnight_win_rate": (non_expiry["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (non_expiry["total_pct"] > 0).mean() * 100
    })
    
    # January effect
    january = df[df["january"]]
    results.append({
        "period": "January",
        "overnight_mean": january["overnight_pct"].mean(),
        "intraday_mean": january["intraday_pct"].mean(),
        "total_mean": january["total_pct"].mean(),
        "trading_days": len(january),
        "overnight_win_rate": (january["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (january["total_pct"] > 0).mean() * 100
    })
    
    # December
    december = df[df["december"]]
    results.append({
        "period": "December",
        "overnight_mean": december["overnight_pct"].mean(),
        "intraday_mean": december["intraday_pct"].mean(),
        "total_mean": december["total_pct"].mean(),
        "trading_days": len(december),
        "overnight_win_rate": (december["overnight_pct"] > 0).mean() * 100,
        "total_win_rate": (december["total_pct"] > 0).mean() * 100
    })
    
    return pd.DataFrame(results)


def analyze_year_by_year(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze returns by year."""
    result = aggregate_stats(df, "year", "year")
    return result


def print_section(title: str, df: pd.DataFrame, cols_to_show: List[str]):
    """Print a formatted section of results."""
    print(f"\n{'='*80}")
    print(f"{title}")
    print("="*80)
    
    if df.empty:
        print("No data available.")
        return
    
    # Format and print
    display_df = df[cols_to_show].copy()
    for col in display_df.columns:
        if "mean" in col or "pct" in col or "rate" in col:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}%" if pd.notna(x) else "N/A")
        elif "sum" in col:
            display_df[col] = display_df[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "N/A")
        elif "count" in col or "days" in col:
            display_df[col] = display_df[col].apply(lambda x: f"{int(x)}" if pd.notna(x) else "N/A")
    
    print(display_df.to_string(index=False))


def df_to_markdown_simple(df: pd.DataFrame, float_fmt: str = ".3f") -> str:
    """Convert DataFrame to markdown table without tabulate dependency."""
    cols = df.columns.tolist()
    
    # Format numeric columns
    formatted_df = df.copy()
    for col in formatted_df.columns:
        if formatted_df[col].dtype in ['float64', 'float32']:
            formatted_df[col] = formatted_df[col].apply(lambda x: f"{x:{float_fmt}}" if pd.notna(x) else "N/A")
    
    # Header
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    separator = "|" + "|".join(["---"] * len(cols)) + "|"
    
    # Rows
    rows = []
    for _, row in formatted_df.iterrows():
        row_str = "| " + " | ".join(str(row[c]) for c in cols) + " |"
        rows.append(row_str)
    
    return "\n".join([header, separator] + rows)


def generate_report(results: Dict[str, pd.DataFrame], output_dir: str):
    """Generate comprehensive markdown report."""
    report_lines = [
        "# Returns Time Pattern Analysis Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n**Basket:** basket_large.txt",
        "",
        "## Summary",
        "",
        "This report analyzes overnight, intraday, and total returns across various time patterns.",
        "",
        "### Definitions",
        "- **Overnight Return**: (Open - Previous Close) / Previous Close × 100%",
        "- **Intraday Return**: (Close - Open) / Open × 100%",
        "- **Total Return**: (Close - Previous Close) / Previous Close × 100%",
        "",
    ]
    
    # Day of Week
    if "day_of_week" in results:
        report_lines.extend([
            "## 1. Returns by Day of the Week",
            "",
            df_to_markdown_simple(results["day_of_week"]),
            "",
        ])
    
    # Day of Month
    if "day_of_month" in results:
        report_lines.extend([
            "## 2. Returns by Day of the Month",
            "",
            df_to_markdown_simple(results["day_of_month"]),
            "",
        ])
    
    # First/Last Days
    if "first_last_days" in results:
        report_lines.extend([
            "## 3. First/Last Days of Month Analysis",
            "",
            df_to_markdown_simple(results["first_last_days"]),
            "",
        ])
    
    # Month of Year
    if "by_month" in results:
        report_lines.extend([
            "## 4. Returns by Month of the Year",
            "",
            df_to_markdown_simple(results["by_month"]),
            "",
        ])
    
    # Quarter
    if "by_quarter" in results:
        report_lines.extend([
            "## 5. Returns by Quarter",
            "",
            df_to_markdown_simple(results["by_quarter"]),
            "",
        ])
    
    # Week of Year
    if "week_of_year" in results:
        report_lines.extend([
            "## 6. Returns by Week of the Year",
            "",
            df_to_markdown_simple(results["week_of_year"]),
            "",
        ])
    
    # Special Periods
    if "special_periods" in results:
        report_lines.extend([
            "## 7. Special Period Analysis",
            "",
            "Comparison of specific trading patterns:",
            "",
            df_to_markdown_simple(results["special_periods"]),
            "",
        ])
    
    # Year by Year
    if "by_year" in results:
        report_lines.extend([
            "## 8. Year-by-Year Analysis",
            "",
            df_to_markdown_simple(results["by_year"]),
            "",
        ])
    
    report_content = "\n".join(report_lines)
    report_path = os.path.join(output_dir, "returns_patterns_report.md")
    with open(report_path, "w") as f:
        f.write(report_content)
    
    print(f"\n✅ Report saved to: {report_path}")


def export_to_csv(results: Dict[str, pd.DataFrame], output_dir: str):
    """Export all results to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    
    for name, df in results.items():
        if df is not None and not df.empty:
            csv_path = os.path.join(output_dir, f"{name}.csv")
            df.to_csv(csv_path, index=False)
            print(f"   Saved: {csv_path}")


def main():
    """Main entry point."""
    print("="*80)
    print("RETURNS TIME PATTERN ANALYSIS")
    print("="*80)
    print("\nAnalyzing overnight, intraday, and total returns by time patterns...")
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap return)")
    print("  • Intraday:  Today's open → Today's close (session return)")
    print("  • Total:     Previous close → Today's close (full day return)")
    print("="*80)
    
    # Load basket
    print(f"\n📂 Loading basket: {DEFAULT_BASKET}")
    symbols = load_basket(DEFAULT_BASKET)
    # Remove duplicates
    symbols = list(dict.fromkeys(symbols))
    print(f"   Found {len(symbols)} unique symbols")
    
    # Calculate returns
    print(f"\n📊 Loading data from: {CACHE_DIR}")
    daily_returns = calculate_basket_returns(symbols, CACHE_DIR)
    
    if daily_returns.empty:
        print("❌ No data available!")
        return
    
    print(f"\n📅 Date Range: {daily_returns.index.min().date()} to {daily_returns.index.max().date()}")
    print(f"📈 Total Trading Days: {len(daily_returns)}")
    
    # Add time features
    print("\n⏰ Adding time features...")
    df = add_time_features(daily_returns)
    
    # Run all analyses
    print("\n🔍 Running analyses...")
    results = {}
    
    # 1. Day of Week
    print("   - Day of Week analysis...")
    results["day_of_week"] = analyze_by_day_of_week(df)
    
    # 2. Day of Month
    print("   - Day of Month analysis...")
    results["day_of_month"] = analyze_by_day_of_month(df)
    
    # 3. First/Last Days
    print("   - First/Last days analysis...")
    results["first_last_days"] = analyze_first_last_days(df)
    
    # 4. Month of Year
    print("   - Month of Year analysis...")
    results["by_month"] = analyze_by_month(df)
    
    # 5. Quarter
    print("   - Quarter analysis...")
    results["by_quarter"] = analyze_by_quarter(df)
    
    # 6. Week of Year
    print("   - Week of Year analysis...")
    results["week_of_year"] = analyze_by_week_of_year(df)
    
    # 7. Special Periods
    print("   - Special periods analysis...")
    results["special_periods"] = analyze_special_periods(df)
    
    # 8. Year by Year
    print("   - Year-by-Year analysis...")
    results["by_year"] = analyze_year_by_year(df)
    
    # Print results
    print_section(
        "DAY OF WEEK ANALYSIS",
        results["day_of_week"],
        ["day_name", "overnight_pct_mean", "intraday_pct_mean", "total_pct_mean", 
         "overnight_pct_count", "total_win_rate"]
    )
    
    print_section(
        "FIRST/LAST DAYS OF MONTH",
        results["first_last_days"],
        ["period", "overnight_mean", "intraday_mean", "total_mean", 
         "trading_days", "total_win_rate"]
    )
    
    print_section(
        "MONTH OF YEAR ANALYSIS",
        results["by_month"],
        ["month_name", "overnight_pct_mean", "intraday_pct_mean", "total_pct_mean",
         "overnight_pct_count", "total_win_rate"]
    )
    
    print_section(
        "QUARTER ANALYSIS",
        results["by_quarter"],
        ["quarter", "overnight_pct_mean", "intraday_pct_mean", "total_pct_mean",
         "overnight_pct_count", "total_win_rate"]
    )
    
    print_section(
        "SPECIAL PERIODS",
        results["special_periods"],
        ["period", "overnight_mean", "intraday_mean", "total_mean",
         "trading_days", "total_win_rate"]
    )
    
    print_section(
        "YEAR-BY-YEAR ANALYSIS",
        results["by_year"],
        ["year", "overnight_pct_sum", "intraday_pct_sum", "total_pct_sum",
         "overnight_pct_count", "total_win_rate"]
    )
    
    # Create output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = f"reports/analysis/returns_patterns_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Export to CSV
    print(f"\n💾 Exporting results to: {output_dir}")
    export_to_csv(results, output_dir)
    
    # Generate markdown report
    generate_report(results, output_dir)
    
    # Print top insights
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    
    # Best/Worst day of week
    dow = results["day_of_week"]
    best_dow = dow.loc[dow["total_pct_mean"].idxmax()]
    worst_dow = dow.loc[dow["total_pct_mean"].idxmin()]
    print(f"\n📅 Day of Week:")
    print(f"   Best:  {best_dow['day_name']} (avg {best_dow['total_pct_mean']:.3f}%)")
    print(f"   Worst: {worst_dow['day_name']} (avg {worst_dow['total_pct_mean']:.3f}%)")
    
    # Best/Worst month
    month = results["by_month"]
    best_month = month.loc[month["total_pct_mean"].idxmax()]
    worst_month = month.loc[month["total_pct_mean"].idxmin()]
    print(f"\n📆 Month of Year:")
    print(f"   Best:  {best_month['month_name']} (avg {best_month['total_pct_mean']:.3f}%)")
    print(f"   Worst: {worst_month['month_name']} (avg {worst_month['total_pct_mean']:.3f}%)")
    
    # First vs Last days
    fl = results["first_last_days"]
    print(f"\n📌 Month Position:")
    for _, row in fl.iterrows():
        print(f"   {row['period']}: avg {row['total_mean']:.3f}% (win rate: {row['total_win_rate']:.1f}%)")
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()


# ========== FROM: marubozu_method_check.py ==========

#!/usr/bin/env python3
"""Compare backtest methodologies for Marubozu strategy."""

import pandas as pd
import numpy as np
import glob
from pathlib import Path

CACHE_DIR = Path('data/cache')

SYMBOLS = [
    'RELIANCE', 'BHARTIARTL', 'ICICIBANK', 'SBIN', 'BAJFINANCE', 'LICI', 'LT',
    'HCLTECH', 'AXISBANK', 'ULTRACEMCO', 'TITAN', 'BAJAJFINSV', 'ADANIPORTS',
    'NTPC', 'HAL', 'BEL', 'ADANIENT', 'ASIANPAINT', 'ADANIPOWER', 'DMART',
    'COALINDIA', 'IOC', 'INDIGO', 'TATASTEEL', 'VEDL', 'SBILIFE', 'JIOFIN',
    'GRASIM', 'LTIM', 'HINDALCO', 'DLF', 'ADANIGREEN', 'BPCL', 'TECHM',
    'PIDILITIND', 'IRFC', 'TRENT', 'BANKBARODA', 'CHOLAFIN', 'PNB',
    'TATAPOWER', 'SIEMENS', 'UNIONBANK', 'PFC', 'TATACONSUM', 'BSE', 'GAIL',
    'HDFCAMC', 'ABB', 'GMRAIRPORT', 'MAZDOCK', 'INDUSTOWER', 'IDBI', 'CGPOWER',
    'PERSISTENT', 'HDFCBANK', 'TCS', 'INFY', 'HINDUNILVR', 'ITC', 'MARUTI',
    'SUNPHARMA', 'KOTAKBANK', 'ONGC', 'JSWSTEEL', 'WIPRO', 'POWERGRID',
    'NESTLEIND', 'HINDZINC', 'EICHERMOT', 'TVSMOTOR', 'DIVISLAB', 'HDFCLIFE',
    'VBL', 'SHRIRAMFIN', 'MUTHOOTFIN', 'BRITANNIA', 'AMBUJACEM', 'TORNTPHARM',
    'HEROMOTOCO', 'CUMMINSIND', 'CIPLA', 'GODREJCP', 'POLYCAB', 'BOSCHLTD',
    'DRREDDY', 'MAXHEALTH', 'INDHOTEL', 'APOLLOHOSP', 'JINDALSTEL',
]

MIN_BODY_PCT = 5.0
MIN_BODY_RANGE = 0.80

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

trades_otc = []  # Open-to-Close
trades_ctc = []  # Close-to-Close

for sym in SYMBOLS:
    file = find_file(sym)
    if not file:
        continue
    
    df = pd.read_csv(file)
    df['time'] = pd.to_datetime(df['time'])
    df = df.drop_duplicates(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    
    # Only 2016-2024
    df = df[(df['time'] >= '2016-01-01') & (df['time'] < '2025-01-01')]
    
    if len(df) < 10:
        continue
    
    # Vectorized approach
    df['body'] = df['close'] - df['open']
    df['range'] = df['high'] - df['low']
    df['body_pct'] = (df['body'] / df['open']) * 100
    df['body_ratio'] = df['body'] / df['range'].replace(0, np.nan)
    
    # Marubozu condition
    df['is_marubozu'] = (df['body'] > 0) & (df['body_pct'] >= MIN_BODY_PCT) & (df['body_ratio'] >= MIN_BODY_RANGE)
    
    # Next day returns
    df['next_open'] = df['open'].shift(-1)
    df['next_close'] = df['close'].shift(-1)
    df['ret_otc'] = (df['next_close'] - df['next_open']) / df['next_open'] * 100
    df['ret_ctc'] = (df['next_close'] - df['close']) / df['close'] * 100
    
    # Filter marubozu signals
    signals = df[df['is_marubozu'] & df['ret_otc'].notna()].copy()
    
    for _, row in signals.iterrows():
        year = row['time'].year
        trades_otc.append({'year': year, 'ret': row['ret_otc']})
        trades_ctc.append({'year': year, 'ret': row['ret_ctc']})

print('='*80)
print('MARUBOZU BACKTEST METHODOLOGY COMPARISON')
print('='*80)
print()

print('METHOD 1: OPEN-TO-CLOSE (Pure Intraday)')
print('-'*60)
df1 = pd.DataFrame(trades_otc)
total1 = len(df1)
avg1 = df1['ret'].mean()
win1 = (df1['ret'] > 0).mean() * 100
yearly1 = df1.groupby('year')['ret'].mean()
print(f'Total Trades: {total1:,}')
print(f'Avg Return: {avg1:.2f}%')
print(f'Win Rate: {win1:.1f}%')
print(f'Years Positive: {(yearly1 > 0).sum()}/{len(yearly1)}')
print()

print('METHOD 2: CLOSE-TO-CLOSE (Includes Overnight)')
print('-'*60)
df2 = pd.DataFrame(trades_ctc)
total2 = len(df2)
avg2 = df2['ret'].mean()
win2 = (df2['ret'] > 0).mean() * 100
yearly2 = df2.groupby('year')['ret'].mean()
print(f'Total Trades: {total2:,}')
print(f'Avg Return: {avg2:.2f}%')
print(f'Win Rate: {win2:.1f}%')
print(f'Years Positive: {(yearly2 > 0).sum()}/{len(yearly2)}')
print()

print('='*80)
print('DOCUMENTED STATS: 1,130 trades, +0.64%/trade, 52.7% WR, 9/9 years')
print('='*80)
print()
print('MATCH ANALYSIS:')
print(f'  Method 1 (O2C): {total1} trades, {avg1:.2f}%, {win1:.1f}% WR')
print(f'  Method 2 (C2C): {total2} trades, {avg2:.2f}%, {win2:.1f}% WR')
print()

# Which matches better?
diff1_trades = abs(total1 - 1130)
diff2_trades = abs(total2 - 1130)
diff1_avg = abs(avg1 - 0.64)
diff2_avg = abs(avg2 - 0.64)
diff1_wr = abs(win1 - 52.7)
diff2_wr = abs(win2 - 52.7)

score1 = diff1_trades + diff1_avg * 100 + diff1_wr
score2 = diff2_trades + diff2_avg * 100 + diff2_wr

if score1 < score2:
    print('✅ METHOD 1 (Open-to-Close / Pure Intraday) matches the documented stats!')
else:
    print('✅ METHOD 2 (Close-to-Close / Includes Overnight) matches the documented stats!')


# ========== FROM: analyze_mfe_tp.py ==========

#!/usr/bin/env python3
"""
Analyze MFE (Maximum Favorable Excursion) to find optimal TP combination.

Uses actual realized max profit potential from trades to recommend:
- TP1% (first take profit level)
- TP1_qty% (qty to exit at TP1)
- TP2% (second take profit level)
- TP2_qty% (qty to exit at TP2)
- Remaining qty exits at CLOSE
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

WORKSPACE = Path(__file__).parent

# Grid search parameters
TP1_RANGE = [5, 8, 10, 12, 15, 20]  # TP1 percentage
TP1_QTY_RANGE = [0.15, 0.20, 0.30, 0.40]  # qty % to exit at TP1
TP2_RANGE = [15, 20, 25, 30, 40]  # TP2 percentage
TP2_QTY_RANGE = [0.30, 0.40, 0.50, 0.60]  # qty % to exit at TP2

def load_trades():
    """Load consolidated trades."""
    trades_file = WORKSPACE / "reports/0102-0144-tema-lsma-crossover-main-1d/consolidated_trades_MAX.csv"
    
    if not trades_file.exists():
        logger.error(f"❌ File not found: {trades_file}")
        return None
    
    df = pd.read_csv(trades_file)
    logger.info(f"✅ Loaded {len(df)} records")
    
    # Keep only entry trades (skip exit records)
    entry_trades = df[df['Type'] == 'Entry long'].copy()
    logger.info(f"✅ Found {len(entry_trades)} entry trades")
    
    return entry_trades

def simulate_tp_exit(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct):
    """
    Simulate exiting with TP levels based on MFE.
    
    Logic:
    - If MFE >= TP1%, exit tp1_qty_pct at TP1%
    - If remaining qty MFE >= TP2%, exit tp2_qty_pct at TP2%
    - Rest exits at actual close (using Net P&L %)
    """
    
    results = []
    
    for idx, trade in trades_df.iterrows():
        mfe_pct = trade['MFE %']
        entry_price = trade['Price INR']
        actual_pnl_pct = trade['Net P&L %']
        actual_pnl = trade['Net P&L INR']
        qty = trade['Position size (qty)']
        
        if pd.isna(mfe_pct) or pd.isna(entry_price):
            continue
        
        # Remaining qty to exit
        remaining_qty = qty
        total_pnl = 0
        
        # TP1 exit
        if mfe_pct >= tp1_pct:
            exit_qty = qty * tp1_qty_pct
            exit_pnl = exit_qty * entry_price * (tp1_pct / 100)
            total_pnl += exit_pnl
            remaining_qty -= exit_qty
        
        # TP2 exit
        if mfe_pct >= tp2_pct:
            exit_qty = remaining_qty * tp2_qty_pct
            exit_pnl = exit_qty * entry_price * (tp2_pct / 100)
            total_pnl += exit_pnl
            remaining_qty -= exit_qty
        
        # Rest exits at close (actual PnL)
        if remaining_qty > 0:
            # Scale remaining qty's share of actual PnL proportionally
            close_pnl = remaining_qty * entry_price * (actual_pnl_pct / 100)
            total_pnl += close_pnl
        
        # Calculate final metrics
        total_pnl_pct = (total_pnl / (qty * entry_price)) * 100 if qty > 0 else 0
        is_profitable = total_pnl > 0
        
        results.append({
            'trade_num': trade['Trade #'],
            'symbol': trade['Symbol'],
            'entry_price': entry_price,
            'mfe_pct': mfe_pct,
            'simulated_pnl': total_pnl,
            'simulated_pnl_pct': total_pnl_pct,
            'profitable': is_profitable,
            'original_pnl': actual_pnl
        })
    
    return results

def evaluate_combination(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct):
    """Evaluate a single TP combination."""
    
    results = simulate_tp_exit(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct)
    
    if not results:
        return None
    
    df_results = pd.DataFrame(results)
    
    total_trades = len(df_results)
    winning_trades = df_results[df_results['profitable'] == True]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    # Profit factor
    winning_pnl = df_results[df_results['simulated_pnl'] > 0]['simulated_pnl'].sum()
    losing_pnl = abs(df_results[df_results['simulated_pnl'] <= 0]['simulated_pnl'].sum())
    profit_factor = (winning_pnl / losing_pnl) if losing_pnl > 0 else (winning_pnl / 0.01 if winning_pnl > 0 else 0)
    
    # Total P&L
    net_pnl = df_results['simulated_pnl'].sum()
    avg_pnl = net_pnl / total_trades if total_trades > 0 else 0
    
    return {
        'tp1_pct': tp1_pct,
        'tp1_qty_pct': tp1_qty_pct,
        'tp2_pct': tp2_pct,
        'tp2_qty_pct': tp2_qty_pct,
        'total_trades': total_trades,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'net_pnl': net_pnl,
        'avg_pnl': avg_pnl
    }

def run_analysis():
    """Run MFE-based analysis."""
    
    logger.info("\n" + "="*90)
    logger.info("📊 MFE-BASED TP OPTIMIZATION ANALYSIS")
    logger.info("="*90)
    
    # Load trades
    trades_df = load_trades()
    if trades_df is None:
        return
    
    logger.info("\n" + "="*90)
    logger.info("⚡ Testing all 480 TP combinations using MFE data")
    logger.info("="*90)
    
    all_results = []
    total = len(TP1_RANGE) * len(TP1_QTY_RANGE) * len(TP2_RANGE) * len(TP2_QTY_RANGE)
    current = 0
    
    for tp1_pct in TP1_RANGE:
        for tp1_qty_pct in TP1_QTY_RANGE:
            for tp2_pct in TP2_RANGE:
                for tp2_qty_pct in TP2_QTY_RANGE:
                    current += 1
                    
                    result = evaluate_combination(trades_df, tp1_pct, tp1_qty_pct, tp2_pct, tp2_qty_pct)
                    
                    if result:
                        all_results.append(result)
                        
                        if current % 120 == 0:  # Log every 120 combinations
                            pct = (current / total) * 100
                            logger.info(f"[{current:3d}/{total}] ({pct:5.1f}%) - TP1={tp1_pct}% WR={result['win_rate']:.1f}% PF={result['profit_factor']:.2f}")
    
    # Sort by profit factor, then win rate
    df_results = pd.DataFrame(all_results)
    df_results = df_results.sort_values(by=['profit_factor', 'win_rate'], ascending=[False, False])
    
    # Save results
    timestamp = datetime.now().strftime("%m%d-%H%M")
    csv_file = WORKSPACE / f"mfe_analysis_results_{timestamp}.csv"
    df_results.to_csv(csv_file, index=False)
    
    logger.info("\n" + "="*110)
    logger.info("TOP 15 BEST COMBINATIONS (ranked by Profit Factor, then Win Rate)")
    logger.info("="*110 + "\n")
    
    for rank, (idx, row) in enumerate(df_results.head(15).iterrows(), 1):
        logger.info(
            f"Rank {rank:2d} | TP1={row['tp1_pct']:5.0f}% (qty={row['tp1_qty_pct']:.0%}) | "
            f"TP2={row['tp2_pct']:5.0f}% (qty={row['tp2_qty_pct']:.0%}) | "
            f"WR={row['win_rate']:6.1f}% | PF={row['profit_factor']:6.2f} | "
            f"Trades={row['total_trades']:5.0f} | P&L=₹{row['net_pnl']:12,.0f}"
        )
    
    logger.info("\n" + "="*110)
    logger.info(f"📊 Results saved to: {csv_file}")
    logger.info("="*110 + "\n")
    
    # Recommend best
    best = df_results.iloc[0]
    remaining_qty_pct = 1.0 - best['tp1_qty_pct'] - best['tp2_qty_pct']
    
    logger.info(f"✅ RECOMMENDED COMBINATION (based on MFE analysis):")
    logger.info(f"   TP1: {best['tp1_pct']:.0f}% (exit {best['tp1_qty_pct']:.0%} of position)")
    logger.info(f"   TP2: {best['tp2_pct']:.0f}% (exit {best['tp2_qty_pct']:.0%} of position)")
    logger.info(f"   CLOSE: Exit remaining {remaining_qty_pct:.0%} of position at signal")
    logger.info(f"   ")
    logger.info(f"   Win Rate: {best['win_rate']:.1f}%")
    logger.info(f"   Profit Factor: {best['profit_factor']:.2f}")
    logger.info(f"   Total Trades: {best['total_trades']:.0f}")
    logger.info(f"   Net P&L: ₹{best['net_pnl']:,.0f}")
    logger.info(f"   Avg P&L per trade: ₹{best['avg_pnl']:,.0f}\n")

if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


# ========== FROM: analyze_hypothesis_results.py ==========

#!/usr/bin/env python3
"""
Deep Hypothesis Analysis - Why is it failing?
==============================================
Investigate: 
1. Are we entering/exiting at good prices?
2. Does the strategy favor certain market conditions?
3. What % of green candles reverse?
"""

import pandas as pd
import numpy as np
from pathlib import Path
import glob
from datetime import datetime

# Load results
results_df = pd.read_csv("reports/hypothesis_weekly_green_strict_results.csv")

print("="*100)
print("HYPOTHESIS PERFORMANCE ANALYSIS - STRICT VARIANT")
print("="*100)

# Basic stats
print(f"\n📊 BASIC STATISTICS:")
print(f"  Total Trades: {len(results_df)}")
print(f"  Winning: {len(results_df[results_df['net_return_pct'] > 0])}")
print(f"  Losing: {len(results_df[results_df['net_return_pct'] <= 0])}")
print(f"  Win Rate: {(len(results_df[results_df['net_return_pct'] > 0])/len(results_df)*100):.1f}%")
print(f"  Total Return: {results_df['net_return_pct'].sum():.2f}%")
print(f"  Avg Return: {results_df['net_return_pct'].mean():.2f}%")
print(f"  Median Return: {results_df['net_return_pct'].median():.2f}%")

# Problem analysis
print(f"\n🔍 PROBLEM ANALYSIS:")
results_df['entry_price_num'] = pd.to_numeric(results_df['entry_price'], errors='coerce')
results_df['exit_price_num'] = pd.to_numeric(results_df['exit_price'], errors='coerce')
results_df['price_move'] = ((results_df['exit_price_num'] - results_df['entry_price_num']) / results_df['entry_price_num'] * 100)

print(f"\n  Price Action:")
print(f"    Avg price move (gross): {results_df['price_move'].mean():.2f}%")
print(f"    Avg transaction costs: {results_df['transaction_cost_pct'].mean():.2f}%")
print(f"    Med gross return: {results_df['gross_return_pct'].median():.2f}%")
print(f"    Med net return: {results_df['net_return_pct'].median():.2f}%")

print(f"\n  Entry/Exit Timing Issue?")
win_avg_move = results_df[results_df['net_return_pct'] > 0]['price_move'].mean()
lose_avg_move = results_df[results_df['net_return_pct'] <= 0]['price_move'].mean()
print(f"    Avg move on winners: {win_avg_move:.2f}%")
print(f"    Avg move on losers: {lose_avg_move:.2f}%")
print(f"    Difference: {win_avg_move - lose_avg_move:.2f}%")

# Distribution
print(f"\n  Return Distribution:")
bins = [-100, -10, -5, -2, -1, -0.5, 0, 0.5, 1, 2, 5, 10, 100]
labels = ["<-10%", "-10--5%", "-5--2%", "-2--1%", "-1--0.5%", "-0.5-0%", "0-0.5%", "0.5-1%", "1-2%", "2-5%", "5-10%", ">10%"]
dist = pd.cut(results_df['net_return_pct'], bins=bins, labels=labels).value_counts().sort_index()
print(dist)

# Profitability by year
print(f"\n  Performance by Year:")
results_df['entry_year'] = pd.to_datetime(results_df['entry_date']).dt.year
yearly = results_df.groupby('entry_year').agg({
    'net_return_pct': ['count', 'mean', 'sum']
}).round(2)
yearly.columns = ['Trades', 'Avg %', 'Total %']
print(yearly)

# By month
print(f"\n  Performance by Month:")
results_df['entry_month'] = pd.to_datetime(results_df['entry_date']).dt.month
monthly = results_df.groupby('entry_month').agg({
    'net_return_pct': ['count', 'mean', 'sum']
}).round(2)
monthly.columns = ['Trades', 'Avg %', 'Total %']
print(monthly)

# Key insight
print(f"\n💡 KEY INSIGHT:")
print(f"  Hypothesis flaw: 'Green candle + [filters] = continuation'")
print(f"  Reality: Green candle closing ≠ next week up")
print(f"  ")
print(f"  The strategy assumes completing a green week = momentum")
print(f"  But entering on MONDAY (after closing signal) is too late")
print(f"  By then, the move has already completed its reversal risk")
print(f"  ")
print(f"  Observations:")
print(f"  - Average move gross: {results_df['price_move'].mean():.2f}% (BELOW transaction costs!)")
print(f"  - Win rate: 41.7% (need 50%+ to profit)")
print(f"  - Winners: {win_avg_move:.2f}% avg move")
print(f"  - Losers: {lose_avg_move:.2f}% avg move")
print(f"  ")
print(f"  RECOMMENDATION:")
print(f"  ❌ This hypothesis is NOT profitable")
print(f"  ✅ Try REVERSE: Fade green candles with BB oversold")
print(f"  OR")
print(f"  ✅ Enter SAME WEEK (not next Monday)")
print(f"  OR")
print(f"  ✅ Use different timeframe (daily, not weekly hold)")


# ========== FROM: calculate_basket_ker.py ==========

#!/usr/bin/env python3
"""
Calculate KER (Kaufman Efficiency Ratio) for all symbols in all baskets.

KER measures the efficiency of price movement:
- KER = (Net Price Change) / (Sum of Absolute Price Changes)
- Range: 0 to 1
- Higher KER = More efficient trending (better for trend-following strategies)
- Lower KER = More choppy/noisy movement

This script calculates KER for the last 5 years (1225 bars) for each symbol
across all basket files to help with asset filtering for trend-following strategies.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.loaders import load_many_india

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_ker(prices: pd.Series, period: int = 10) -> float:
    """
    Calculate Kaufman Efficiency Ratio (KER) for a price series.
    
    Args:
        prices: Series of closing prices
        period: Number of periods to calculate KER over (default: 10)
    
    Returns:
        KER value between 0 and 1
    """
    if len(prices) < period + 1:
        return np.nan
    
    # Use the last 'period' prices
    price_data = prices.iloc[-period-1:]
    
    # Net change (absolute difference between first and last)
    net_change = abs(price_data.iloc[-1] - price_data.iloc[0])
    
    # Sum of absolute changes
    price_changes = price_data.diff().abs()
    volatility = price_changes.sum()
    
    # Avoid division by zero
    if volatility == 0:
        return 0.0
    
    ker = net_change / volatility
    return ker


def load_basket_symbols(basket_file: str) -> List[str]:
    """Load symbols from a basket file."""
    basket_path = project_root / "data" / basket_file
    
    if not basket_path.exists():
        logger.warning(f"Basket file not found: {basket_file}")
        return []
    
    with open(basket_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    return symbols


def calculate_symbol_ker(symbol: str, bars: int = 1225, ker_period: int = 10) -> Tuple[float, int]:
    """
    Calculate KER for a single symbol.
    
    Args:
        symbol: Stock symbol
        bars: Number of bars to fetch (default: 1225 for 5 years)
        ker_period: Period for KER calculation (default: 10)
    
    Returns:
        Tuple of (KER value, actual bars available)
    """
    try:
        # Fetch data using the same loader as the backtesting system
        data_dict = load_many_india(
            symbols=[symbol],
            interval='1d',
            period='max',
            use_cache_only=True
        )
        
        if not data_dict or symbol not in data_dict:
            logger.warning(f"No data available for {symbol}")
            return np.nan, 0
        
        df = data_dict[symbol]
        
        if df is None or df.empty:
            logger.warning(f"No data available for {symbol}")
            return np.nan, 0
        
        # Use only the last 'bars' rows
        if len(df) > bars:
            df = df.iloc[-bars:]
        
        actual_bars = len(df)
        
        if actual_bars < ker_period + 1:
            logger.warning(f"Insufficient data for {symbol}: {actual_bars} bars")
            return np.nan, actual_bars
        
        # Calculate KER using the full available period
        ker = calculate_ker(df['close'], period=actual_bars - 1)
        
        return ker, actual_bars
        
    except Exception as e:
        logger.error(f"Error calculating KER for {symbol}: {e}")
        return np.nan, 0


def main():
    """Main function to calculate KER for all baskets."""
    
    # Define all basket files
    basket_files = [
        'basket_largecap_highbeta.txt',
        'basket_largecap_lowbeta.txt',
        'basket_midcap_highbeta.txt',
        'basket_midcap_lowbeta.txt',
        'basket_smallcap_highbeta.txt',
        'basket_smallcap_lowbeta.txt',
    ]
    
    # Results storage
    all_results = []
    
    logger.info("=" * 80)
    logger.info("Starting KER Calculation for All Baskets")
    logger.info(f"Period: 5 years (1225 bars)")
    logger.info("=" * 80)
    
    # Process each basket
    for basket_file in basket_files:
        basket_name = basket_file.replace('basket_', '').replace('.txt', '')
        logger.info(f"\n📊 Processing basket: {basket_name}")
        
        # Load symbols
        symbols = load_basket_symbols(basket_file)
        logger.info(f"   Symbols to process: {len(symbols)}")
        
        if not symbols:
            continue
        
        # Calculate KER for each symbol
        for i, symbol in enumerate(symbols, 1):
            logger.info(f"   [{i}/{len(symbols)}] Calculating KER for {symbol}...")
            
            ker, bars = calculate_symbol_ker(symbol, bars=1225)
            
            all_results.append({
                'Basket': basket_name,
                'Symbol': symbol,
                'KER_5Y': round(ker, 4) if not np.isnan(ker) else np.nan,
                'Bars_Available': bars,
                'Data_Quality': 'Good' if bars >= 1225 else 'Limited' if bars >= 500 else 'Poor'
            })
            
            if not np.isnan(ker):
                logger.info(f"   ✅ {symbol}: KER = {ker:.4f} ({bars} bars)")
            else:
                logger.info(f"   ❌ {symbol}: No KER calculated ({bars} bars)")
    
    # Create DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Sort by KER descending (best trending assets first)
    results_df = results_df.sort_values('KER_5Y', ascending=False, na_position='last')
    
    # Save to CSV
    output_file = project_root / 'reports' / 'basket_ker_analysis_5y.csv'
    results_df.to_csv(output_file, index=False)
    
    logger.info("\n" + "=" * 80)
    logger.info("KER Calculation Complete!")
    logger.info("=" * 80)
    logger.info(f"📁 Results saved to: {output_file}")
    
    # Print summary statistics
    logger.info("\n📊 Summary Statistics by Basket:")
    logger.info("-" * 80)
    
    for basket in results_df['Basket'].unique():
        basket_data = results_df[results_df['Basket'] == basket]
        valid_ker = basket_data['KER_5Y'].dropna()
        
        if len(valid_ker) > 0:
            logger.info(f"\n{basket.upper()}:")
            logger.info(f"  Total Symbols: {len(basket_data)}")
            logger.info(f"  Valid KER: {len(valid_ker)}")
            logger.info(f"  Average KER: {valid_ker.mean():.4f}")
            logger.info(f"  Median KER: {valid_ker.median():.4f}")
            logger.info(f"  Max KER: {valid_ker.max():.4f} ({basket_data.loc[basket_data['KER_5Y'].idxmax(), 'Symbol']})")
            logger.info(f"  Min KER: {valid_ker.min():.4f} ({basket_data.loc[basket_data['KER_5Y'].idxmin(), 'Symbol']})")
    
    # Overall statistics
    logger.info("\n" + "=" * 80)
    logger.info("📊 OVERALL STATISTICS:")
    logger.info("=" * 80)
    valid_all = results_df['KER_5Y'].dropna()
    logger.info(f"Total Symbols Analyzed: {len(results_df)}")
    logger.info(f"Valid KER Values: {len(valid_all)}")
    logger.info(f"Overall Average KER: {valid_all.mean():.4f}")
    logger.info(f"Overall Median KER: {valid_all.median():.4f}")
    
    # Top 10 trending assets
    logger.info("\n" + "=" * 80)
    logger.info("🏆 TOP 10 TRENDING ASSETS (Highest KER):")
    logger.info("=" * 80)
    top_10 = results_df.head(10)
    for idx, row in top_10.iterrows():
        logger.info(f"{row['Symbol']:15s} ({row['Basket']:25s}): KER = {row['KER_5Y']:.4f}")
    
    # Bottom 10 (most choppy)
    logger.info("\n" + "=" * 80)
    logger.info("⚠️  BOTTOM 10 ASSETS (Lowest KER - Most Choppy):")
    logger.info("=" * 80)
    bottom_10 = results_df[results_df['KER_5Y'].notna()].tail(10)
    for idx, row in bottom_10.iterrows():
        logger.info(f"{row['Symbol']:15s} ({row['Basket']:25s}): KER = {row['KER_5Y']:.4f}")
    
    logger.info("\n" + "=" * 80)
    logger.info("✅ Analysis Complete!")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()


# ========== FROM: generate_comparison_report.py ==========

#!/usr/bin/env python3
"""
Generate comprehensive comparison reports across all indices.
Shows all 6 metrics in easy-to-read tables.
"""

import pandas as pd
from pathlib import Path

REPORTS_DIR = Path("reports/indices_analysis")

# Load all DOW summaries
indices = ["NIFTY50", "BANKNIFTY", "NIFTY200"]
all_dow_data = {}

print("=" * 120)
print("COMPREHENSIVE 6-POINT INDEX ANALYSIS REPORT")
print("=" * 120)
print("\nAnalysis Period: Last 5 Years (2020-2025)")
print("Metrics: Intraday Move | Overnight Move | Volatility by Day-of-Week & Expiry Impact\n")

for idx in indices:
    dow_file = REPORTS_DIR / f"{idx}_5y_dow_summary.csv"
    if dow_file.exists():
        all_dow_data[idx] = pd.read_csv(dow_file)

# Print 1: Day-of-Week Analysis (All Indices)
print("\n" + "=" * 120)
print("METRIC 5: DAY-OF-WEEK BIAS ANALYSIS")
print("=" * 120)

dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

for day in dow_order:
    print(f"\n{day.upper()}")
    print("-" * 120)
    
    for idx in indices:
        if idx in all_dow_data:
            df = all_dow_data[idx]
            row = df[df['day_of_week'] == day]
            
            if not row.empty:
                row = row.iloc[0]
                print(f"\n  {idx}:")
                print(f"    INTRADAY (Open-Close):      Mean: {row['intraday_mean']:+.4f}% | Median: {row['intraday_median']:+.4f}% | Win%: {row['intraday_win%']:.1f}% | Vol: {row['intraday_std']:.4f}%")
                print(f"    OVERNIGHT (Close-Open):     Mean: {row['overnight_mean']:+.4f}% | Median: {row['overnight_median']:+.4f}% | Win%: {row['overnight_win%']:.1f}% | Vol: {row['overnight_std']:.4f}%")
                print(f"    VOLATILITY (High-Low range): Mean: {row['vol_mean']:.4f}% | Median: {row['vol_median']:.4f}% | Std: {row['vol_std']:.4f}%")

# Print 2: Monthly Expiry Impact
print("\n\n" + "=" * 120)
print("METRIC 3: DAYS-TO-MONTHLY-EXPIRY IMPACT")
print("=" * 120)

expiry_files = {}
for idx in indices:
    expiry_file = REPORTS_DIR / f"{idx}_5y_monthly_expiry_impact.csv"
    if expiry_file.exists():
        expiry_files[idx] = pd.read_csv(expiry_file)

for idx in indices:
    if idx in expiry_files:
        df = expiry_files[idx]
        print(f"\n{idx}:")
        print("-" * 120)
        print(f"{'Days to Expiry':>20} | {'Intraday Mean %':>18} | {'Intraday Win%':>15} | {'Overnight Mean %':>18} | {'Volatility %':>18}")
        print("-" * 120)
        
        for _, row in df.iterrows():
            day_to_exp = int(row.name) if isinstance(row.name, (int, float)) else row.name
            print(f"{day_to_exp:>20} | {row['intraday_mean']:>18.4f} | {row['intraday_win%']:>15.1f} | {row['overnight_mean']:>18.4f} | {row['vol_mean']:>18.4f}")

# Print 3: Summary Statistics
print("\n\n" + "=" * 120)
print("SUMMARY STATISTICS (All 5 Years)")
print("=" * 120)

for idx in indices:
    detailed_file = REPORTS_DIR / f"{idx}_5y_detailed.csv"
    if detailed_file.exists():
        df = pd.read_csv(detailed_file)
        
        intraday_positive = (df['intraday_move_pct'] > 0).sum() / len(df) * 100
        overnight_positive = (df['overnight_move_pct'] > 0).sum() / len(df) * 100
        
        print(f"\n{idx}:")
        print(f"  Total records: {len(df)}")
        print(f"  Intraday positive days: {intraday_positive:.1f}%")
        print(f"  Overnight positive days: {overnight_positive:.1f}%")
        print(f"  Avg daily volatility: {df['volatility_pct'].mean():.4f}%")
        print(f"  Avg intraday move: {df['intraday_move_pct'].mean():+.4f}%")
        print(f"  Avg overnight move: {df['overnight_move_pct'].mean():+.4f}%")

# Print 4: Key Insights
print("\n\n" + "=" * 120)
print("KEY INSIGHTS & FINDINGS")
print("=" * 120)

insights = {
    "Overnight Bias": "All indices show positive overnight bias (>50% positive days), indicating market strength after market close",
    "Intraday Bias": "Slight intraday negative bias (~48% positive days), suggesting profit-taking during trading hours",
    "Best Days": "Monday & Sunday show highest overnight positive rates (65-72%), suggesting weekend/monday gap-ups",
    "Volatility": "Volatility consistent across days (~1% range), slightly higher on Sundays due to low sample size",
    "Expiry Impact": "Days closer to expiry may show elevated volatility - analyze expiry_impact files for T-0, T-1, T-2 patterns",
    "Index Comparison": "BANKNIFTY shows slightly different characteristics from broad indices (NIFTY50/NIFTY200)",
}

for insight, finding in insights.items():
    print(f"\n{insight}:")
    print(f"  → {finding}")

print("\n\n" + "=" * 120)
print("FILES GENERATED")
print("=" * 120)

print("\nDetailed Analysis Files:")
for idx in indices:
    detailed = REPORTS_DIR / f"{idx}_5y_detailed.csv"
    dow = REPORTS_DIR / f"{idx}_5y_dow_summary.csv"
    expiry = REPORTS_DIR / f"{idx}_5y_monthly_expiry_impact.csv"
    
    if detailed.exists():
        print(f"  ✅ {idx}_5y_detailed.csv - Full daily data with all 6 metrics")
    if dow.exists():
        print(f"  ✅ {idx}_5y_dow_summary.csv - Day-of-week aggregated statistics")
    if expiry.exists():
        print(f"  ✅ {idx}_5y_monthly_expiry_impact.csv - Expiry proximity impact analysis")

print("\n" + "=" * 120)
print("REPORT GENERATION COMPLETE")
print("=" * 120)


# ========== FROM: complete_indices_analysis.py ==========

#!/usr/bin/env python3
"""
COMPLETE 6-POINT INDEX ANALYSIS
================================
1. Fetch daily data from Dhan for 6 indices
2. Save to cache directory
3-6. Perform comprehensive statistical analysis with expiry schedule accounting
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests
import urllib3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# Dhan API
DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

# Index mapping - maps to cache filenames
INDICES = {
    "NIFTY50": {"security_id": 13, "cache_file": "dhan_13_NIFTY_50_1d.csv"},
    "BANKNIFTY": {"security_id": 25, "cache_file": "dhan_25_BANKNIFTY_1d.csv"},
    "NIFTY200": {"security_id": 18, "cache_file": "dhan_18_NIFTY_200_1d.csv"},
    # These need to be fetched via dhan_fetch_data.py:
    # "FINNIFTY": {"security_id": 165, "cache_file": "dhan_165_FINNIFTY_1d.csv"},
    # "NIFTYNXT50": {"security_id": 152, "cache_file": "dhan_152_NIFTYNXT50_1d.csv"},
    # "SENSEX": {"security_id": 99926000, "cache_file": "dhan_99926000_SENSEX_1d.csv"},
    # "BANKEX": {"security_id": 99926009, "cache_file": "dhan_99926009_BANKEX_1d.csv"},
}

CACHE_DIR = Path("data/cache/dhan/daily")
REPORTS_DIR = Path("reports/indices_analysis")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def get_headers():
    """Get Dhan API headers."""
    return {
        "Authorization": f"Bearer {DHAN_ACCESS_TOKEN}",
        "Accept": "application/json"
    }

def fetch_index_from_dhan(symbol, config):
    """Fetch index daily data from Dhan and save to cache."""
    
    cache_file = CACHE_DIR / f"dhan_{config['security_id']}_{symbol}_1d.csv"
    
    # Return if already cached
    if cache_file.exists():
        log.info(f"✅ {symbol} already cached")
        return cache_file
    
    log.info(f"📥 Fetching {symbol} from Dhan API...")
    
    if not DHAN_ACCESS_TOKEN:
        log.warning(f"⚠️  DHAN_ACCESS_TOKEN not set, skipping {symbol}")
        return None
    
    try:
        params = {
            "securityId": config["security_id"],
            "exchangeTokenId": config["security_id"],
            "instrumentType": "INDEX",
            "periodInMinutes": 1440,  # Daily
        }
        
        url = f"{DHAN_BASE_URL}/historicalCharts"
        response = requests.get(url, params=params, headers=get_headers(), verify=False, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if "data" in data and "candlesticks" in data["data"]:
                candles = data["data"]["candlesticks"]
                records = []
                
                for candle in candles:
                    try:
                        records.append({
                            "time": int(candle[0]),
                            "open": float(candle[1]),
                            "high": float(candle[2]),
                            "low": float(candle[3]),
                            "close": float(candle[4]),
                            "volume": int(candle[5]) if len(candle) > 5 else 0
                        })
                    except (ValueError, IndexError):
                        continue
                
                if records:
                    df = pd.DataFrame(records)
                    df.to_csv(cache_file, index=False)
                    log.info(f"✅ Saved {symbol}: {len(df)} candles to cache")
                    return cache_file
                else:
                    log.warning(f"⚠️  No valid candles for {symbol}")
                    return None
        else:
            log.warning(f"⚠️  API {response.status_code} for {symbol}")
            return None
            
    except Exception as e:
        log.error(f"❌ Exception fetching {symbol}: {e}")
        return None

def load_cached_data(filepath):
    """Load cached Dhan data."""
    if filepath and Path(filepath).exists():
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception as e:
            log.error(f"❌ Error loading {filepath}: {e}")
            return None
    return None

def get_monthly_expiry_dates(year_start=2020, year_end=2026):
    """Get monthly options expiry dates (last Thursday of month)."""
    expiry_dates = []
    
    # NSE holidays (select ones that affect Thursday expirations)
    nse_thursday_holidays = {
        (2021, 3, 11), (2021, 3, 25), (2021, 4, 2), (2021, 4, 21), (2021, 4, 25),
        (2021, 8, 19), (2021, 9, 10), (2021, 10, 2), (2021, 11, 4), (2021, 11, 5),
        (2022, 1, 26), (2022, 3, 18), (2022, 4, 14), (2022, 8, 9), (2022, 8, 31),
        (2022, 10, 5), (2022, 10, 24), (2023, 3, 7), (2023, 3, 30), (2023, 4, 4),
        (2023, 4, 14), (2023, 8, 15), (2023, 8, 30), (2023, 9, 19), (2023, 9, 28),
        (2023, 11, 12), (2023, 11, 13), (2023, 11, 27), (2024, 1, 26), (2024, 3, 8),
        (2024, 3, 25), (2024, 3, 29), (2024, 4, 11), (2024, 4, 17), (2024, 4, 21),
        (2024, 8, 15), (2024, 8, 26), (2024, 9, 16), (2024, 10, 2), (2024, 10, 12),
        (2024, 11, 1), (2024, 11, 15), (2025, 1, 26), (2025, 3, 8), (2025, 3, 31),
        (2025, 4, 18),
    }
    
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            # Find last Thursday
            if month == 12:
                last_day = 31
            else:
                last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
            
            for day in range(last_day, 0, -1):
                d = datetime(year, month, day)
                if d.weekday() == 3:  # Thursday
                    # Check if it's a holiday, if so use previous trading day
                    check_date = d
                    while (check_date.year, check_date.month, check_date.day) in nse_thursday_holidays:
                        check_date -= timedelta(days=1)
                    expiry_dates.append(check_date.date())
                    break
    
    return sorted(expiry_dates)

def get_weekly_expiry_dates(year_start=2020, year_end=2026):
    """Get weekly expiry dates (every Wednesday)."""
    expiry_dates = []
    
    nse_wednesday_holidays = {
        (2021, 3, 10), (2021, 3, 24), (2021, 4, 21), (2021, 6, 2), (2021, 7, 21),
        (2021, 8, 18), (2021, 9, 1), (2021, 10, 6), (2021, 11, 3), (2021, 11, 24),
        (2022, 1, 26), (2022, 3, 16), (2022, 4, 13), (2022, 8, 10), (2022, 8, 30),
        (2022, 10, 5), (2022, 10, 26), (2023, 1, 25), (2023, 3, 1), (2023, 3, 29),
        (2023, 4, 5), (2023, 4, 12), (2023, 8, 16), (2023, 8, 29), (2023, 9, 20),
        (2023, 9, 27), (2023, 11, 1), (2023, 11, 29), (2024, 1, 24), (2024, 3, 6),
        (2024, 3, 27), (2024, 3, 27), (2024, 4, 10), (2024, 4, 17), (2024, 8, 14),
        (2024, 8, 28), (2024, 9, 18), (2024, 10, 2), (2024, 10, 16), (2024, 10, 30),
        (2024, 11, 13), (2025, 1, 1), (2025, 3, 5), (2025, 4, 16),
    }
    
    current = datetime(year_start, 1, 1)
    end = datetime(year_end, 12, 31)
    
    while current <= end:
        if current.weekday() == 2:  # Wednesday
            check_date = current
            while (check_date.year, check_date.month, check_date.day) in nse_wednesday_holidays:
                check_date -= timedelta(days=1)
            expiry_dates.append(check_date.date())
        current += timedelta(days=1)
    
    return sorted(expiry_dates)

def analyze_index(symbol, df):
    """
    6-POINT ANALYSIS:
    1. Intraday movement (Open-Close)
    2. Overnight movement (Close-Open next day)
    3. Days-to-monthly-expiry impact
    4. Days-to-weekly-expiry impact
    5. Day-of-week bias
    6. Volatility by day-of-week and expiry proximity
    """
    
    if df is None or len(df) == 0:
        log.warning(f"⚠️  No data for {symbol}")
        return None
    
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp
    time_col = 'timestamp' if 'timestamp' in df.columns else 'time'
    
    if time_col not in df.columns:
        log.error(f"❌ No timestamp column in {symbol}")
        return None
    
    try:
        # Convert time (handle both ms and seconds)
        if pd.api.types.is_numeric_dtype(df[time_col]):
            if df[time_col].max() > 100000000000:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
        else:
            df['timestamp'] = pd.to_datetime(df[time_col])
    except Exception as e:
        log.error(f"❌ Cannot parse time for {symbol}: {e}")
        return None
    
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['open', 'close']).sort_values('timestamp').reset_index(drop=True)
    
    # Filter 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df_5y = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df_5y) == 0:
        log.warning(f"⚠️  No 5-year data for {symbol}")
        return None
    
    log.info(f"✅ {symbol}: {len(df_5y)} records (5Y: {df_5y['timestamp'].min().date()} to {df_5y['timestamp'].max().date()})")
    
    # Add date fields
    df_5y['date'] = df_5y['timestamp'].dt.date
    df_5y['day_of_week'] = df_5y['timestamp'].dt.day_name()
    df_5y['weekday_num'] = df_5y['timestamp'].dt.weekday
    
    # METRIC 1: Intraday movement (Open-Close)
    df_5y['intraday_move_pct'] = ((df_5y['close'] - df_5y['open']) / df_5y['open'] * 100).round(4)
    
    # METRIC 2: Overnight movement (Close-Open next day)
    df_5y['overnight_move_pct'] = ((df_5y['open'].shift(-1) - df_5y['close']) / df_5y['close'] * 100).round(4)
    
    # METRICS 3-4: Days to expiry
    monthly_expiries = get_monthly_expiry_dates()
    weekly_expiries = get_weekly_expiry_dates()
    
    days_data = []
    for date in df_5y['date']:
        date_ts = pd.Timestamp(date)
        
        # Days to monthly expiry
        days_to_monthly = None
        for exp_date in monthly_expiries:
            if exp_date > date:
                days_to_monthly = (exp_date - date).days
                break
        
        # Days to weekly expiry
        days_to_weekly = None
        for exp_date in weekly_expiries:
            if exp_date > date:
                days_to_weekly = (exp_date - date).days
                break
        
        days_data.append({
            'days_to_monthly': days_to_monthly,
            'days_to_weekly': days_to_weekly
        })
    
    df_days = pd.DataFrame(days_data)
    df_5y = pd.concat([df_5y, df_days], axis=1)
    
    # METRIC 5-6: Volatility (High-Low range)
    df_5y['volatility_pct'] = ((df_5y['high'] - df_5y['low']) / df_5y['open'] * 100).round(4)
    
    return df_5y

def generate_reports(symbol, df_analyzed):
    """Generate all reports."""
    
    if df_analyzed is None or len(df_analyzed) == 0:
        return
    
    # 1. Save detailed data
    detailed_path = REPORTS_DIR / f"{symbol}_5y_detailed.csv"
    df_analyzed.to_csv(detailed_path, index=False)
    log.info(f"📊 Detailed: {detailed_path.name}")
    
    # 2. Day-of-week summary
    dow_summary = df_analyzed.groupby('day_of_week').agg({
        'intraday_move_pct': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'overnight_move_pct': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'volatility_pct': ['mean', 'median', 'std']
    }).round(4)
    
    dow_summary.columns = [
        'intraday_mean', 'intraday_median', 'intraday_std', 'intraday_win%',
        'overnight_mean', 'overnight_median', 'overnight_std', 'overnight_win%',
        'vol_mean', 'vol_median', 'vol_std'
    ]
    
    dow_path = REPORTS_DIR / f"{symbol}_5y_dow_summary.csv"
    dow_summary.to_csv(dow_path)
    log.info(f"📊 Day-of-week: {dow_path.name}")
    
    # 3. Monthly expiry impact
    df_expiry = df_analyzed.dropna(subset=['days_to_monthly'])
    if len(df_expiry) > 0:
        expiry_summary = df_expiry.groupby('days_to_monthly').agg({
            'intraday_move_pct': ['mean', 'std', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0],
            'overnight_move_pct': ['mean', 'std'],
            'volatility_pct': ['mean']
        }).round(4)
        
        expiry_summary.columns = ['intraday_mean', 'intraday_std', 'intraday_win%', 'overnight_mean', 'overnight_std', 'vol_mean']
        
        expiry_path = REPORTS_DIR / f"{symbol}_5y_monthly_expiry_impact.csv"
        expiry_summary.to_csv(expiry_path)
        log.info(f"📊 Monthly expiry: {expiry_path.name}")

def main():
    log.info("=" * 80)
    log.info("6-POINT INDEX ANALYSIS (COMPLETE IMPLEMENTATION)")
    log.info("=" * 80)
    
    # TASK 1-2: Load cached data
    log.info("\n[TASK 1-2] LOADING CACHED INDEX DATA")
    log.info("-" * 80)
    
    all_data = {}
    
    for symbol, config in INDICES.items():
        cache_file = CACHE_DIR / config["cache_file"]
        df = load_cached_data(cache_file)
        if df is not None:
            all_data[symbol] = df
            log.info(f"✅ {symbol}: {len(df)} candles")
        else:
            log.warning(f"⚠️  {symbol} not cached")
    
    # TASK 3-6: Analyze
    log.info("\n[TASK 3-6] ANALYZING DATA (6-POINT METRICS)")
    log.info("-" * 80)
    
    for symbol, df in all_data.items():
        df_analyzed = analyze_index(symbol, df)
        if df_analyzed is not None:
            generate_reports(symbol, df_analyzed)
    
    log.info("\n" + "=" * 80)
    log.info("✅ ANALYSIS COMPLETE - Reports saved to: " + str(REPORTS_DIR))
    log.info("=" * 80)

if __name__ == "__main__":
    main()


# ========== FROM: fetch_and_analyze_indices.py ==========

#!/usr/bin/env python3
"""
Comprehensive Index Analysis with Expiry Schedule
==================================================
1. Fetch daily data from Dhan for 6 indices
2. Perform 6 metrics analysis by day of week and days-to-expiry
3. Filter for last 5 years
4. Account for options expiry schedule rules (monthly & weekly)
5. Generate detailed reports
6. Compare across indices
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests
import urllib3
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Dhan API
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
DHAN_BASE_URL = "https://api.dhan.co/v2"

# Index mapping to security IDs and exchanges
INDEX_CONFIG = {
    "NIFTY50": {
        "security_id": 13,
        "exchange": "NSE",
        "file": "dhan_13_NIFTY_50_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "BANKNIFTY": {
        "security_id": 14,
        "exchange": "NSE",
        "file": "dhan_14_BANKNIFTY_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "FINNIFTY": {
        "security_id": 15,
        "exchange": "NSE",
        "file": "dhan_15_FINNIFTY_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "NIFTY_MIDCAP_SELECT": {
        "security_id": 152,  # Approximate - may need adjustment
        "exchange": "NSE",
        "file": "dhan_152_NIFTY_MIDCAP_SELECT_1d.csv",
        "expiry_type": "monthly"
    },
    "SENSEX": {
        "security_id": 99926000,
        "exchange": "BSE",
        "file": "dhan_99926000_SENSEX_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "BANKEX": {
        "security_id": 99926009,
        "exchange": "BSE",
        "file": "dhan_99926009_BANKEX_1d.csv",
        "expiry_type": "monthly"
    }
}

CACHE_DIR = Path("data/cache/dhan/daily")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = Path("reports/indices_analysis")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def fetch_index_data_from_dhan(symbol, config):
    """Fetch index data from Dhan API and cache it."""
    filepath = CACHE_DIR / config["file"]
    
    # Return if already cached
    if filepath.exists():
        print(f"✅ {symbol} already cached")
        return filepath
    
    print(f"📥 Fetching {symbol} from Dhan API...")
    
    try:
        # Build Dhan API request for daily data
        # Endpoint: /historicalCharts
        params = {
            "securityId": config["security_id"],
            "exchangeTokenId": config["security_id"],
            "instrumentType": "INDEX",
            "expiryDate": "",
            "strikePrice": "",
            "optionType": "",
            "periodInMinutes": 1440,  # Daily
        }
        
        headers = {
            "Authorization": f"Bearer {DHAN_API_KEY}",
            "Accept": "application/json"
        }
        
        url = f"{DHAN_BASE_URL}/historicalCharts"
        response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse candlestick data
            if "data" in data and "candlesticks" in data["data"]:
                candles = data["data"]["candlesticks"]
                records = []
                
                for candle in candles:
                    records.append({
                        "time": candle[0],  # timestamp in milliseconds
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": int(candle[5]) if len(candle) > 5 else 0
                    })
                
                df = pd.DataFrame(records)
                df.to_csv(filepath, index=False)
                print(f"✅ Saved {symbol}: {len(df)} candles to {filepath}")
                return filepath
        else:
            print(f"⚠️  API Error for {symbol}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️  Exception fetching {symbol}: {e}")
        return None

def load_cached_data(filepath):
    """Load cached Dhan data."""
    if filepath and filepath.exists():
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception as e:
            print(f"⚠️  Error loading {filepath}: {e}")
            return None
    return None

def get_monthly_expiry_dates(year_start=2020, year_end=2025):
    """
    Get monthly options expiry dates (last Thursday of month).
    Account for holiday shifts (if last Thursday is a holiday, move to previous trading day).
    """
    expiry_dates = []
    
    # NSE holidays (Thursdays that affect expiry)
    nse_holidays = {
        datetime(2021, 3, 11),   # Maha Shivaratri
        datetime(2021, 3, 29),   # Holi
        datetime(2021, 4, 2),    # Good Friday
        datetime(2021, 4, 21),   # Mahavir Jayanti
        datetime(2021, 4, 25),   # Ramzan Id
        datetime(2021, 8, 15),   # Independence Day (Thu)
        datetime(2021, 9, 10),   # Janmashtami
        datetime(2021, 10, 2),   # Gandhi Jayanti
        datetime(2021, 11, 5),   # Diwali
        datetime(2022, 1, 26),   # Republic Day
        datetime(2022, 3, 18),   # Holi
        datetime(2022, 4, 14),   # Ambedkar Jayanti
        datetime(2022, 8, 9),    # Janmashtami
        datetime(2022, 8, 31),   # Janmashtami (alternate)
        datetime(2022, 10, 5),   # Dussehra
        datetime(2022, 10, 24),  # Diwali
        datetime(2023, 3, 7),    # Maha Shivaratri
        datetime(2023, 3, 30),   # Holi
        datetime(2023, 4, 4),    # Eid ul-Fitr
        datetime(2023, 4, 14),   # Ambedkar Jayanti
        datetime(2023, 8, 15),   # Independence Day
        datetime(2023, 8, 30),   # Janmashtami
        datetime(2023, 9, 19),   # Milad-un-Nabi
        datetime(2023, 9, 28),   # Dussehra
        datetime(2023, 11, 12),  # Diwali
        datetime(2023, 11, 13),  # Diwali (alternate)
        datetime(2023, 11, 27),  # Guru Nanak Jayanti
        datetime(2024, 1, 26),   # Republic Day
        datetime(2024, 3, 8),    # Maha Shivaratri
        datetime(2024, 3, 25),   # Holi
        datetime(2024, 3, 29),   # Good Friday
        datetime(2024, 4, 11),   # Eid ul-Fitr
        datetime(2024, 4, 17),   # Ram Navami
        datetime(2024, 4, 21),   # Mahavir Jayanti
        datetime(2024, 8, 15),   # Independence Day
        datetime(2024, 8, 26),   # Janmashtami
        datetime(2024, 9, 16),   # Milad-un-Nabi
        datetime(2024, 10, 2),   # Gandhi Jayanti
        datetime(2024, 10, 12),  # Dussehra
        datetime(2024, 11, 1),   # Diwali
        datetime(2024, 11, 15),  # Guru Nanak Jayanti
        datetime(2025, 1, 26),   # Republic Day
        datetime(2025, 3, 8),    # Maha Shivaratri
        datetime(2025, 3, 31),   # Holi
        datetime(2025, 4, 18),   # Good Friday
    }
    
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            # Find last Thursday of month
            if month == 12:
                last_day = datetime(year, month, 31)
                next_month_first = datetime(year + 1, 1, 1)
            else:
                next_month_first = datetime(year, month + 1, 1)
                last_day = next_month_first - timedelta(days=1)
            
            # Find last Thursday
            last_thursday = None
            for day in range(last_day.day, 0, -1):
                d = datetime(year, month, day)
                if d.weekday() == 3:  # Thursday
                    last_thursday = d
                    break
            
            if last_thursday:
                # Check if it's a holiday, if so go back one trading day
                check_date = last_thursday
                while check_date in nse_holidays:
                    check_date -= timedelta(days=1)
                
                expiry_dates.append(check_date.date())
    
    return sorted(expiry_dates)

def get_weekly_expiry_dates(year_start=2020, year_end=2025):
    """
    Get weekly options expiry dates (every Wednesday for most indices).
    Account for holidays.
    """
    expiry_dates = []
    current = datetime(year_start, 1, 1)
    end = datetime(year_end, 12, 31)
    
    nse_holidays = get_nse_holidays_simple()
    
    while current <= end:
        # Find every Wednesday
        if current.weekday() == 2:  # Wednesday
            check_date = current
            # If holiday, move to previous trading day
            while check_date.date() in nse_holidays:
                check_date -= timedelta(days=1)
            expiry_dates.append(check_date.date())
        
        current += timedelta(days=1)
    
    return sorted(expiry_dates)

def get_nse_holidays_simple():
    """Return set of NSE holiday dates."""
    holidays = {
        datetime(2021, 3, 11).date(),
        datetime(2021, 3, 29).date(),
        datetime(2021, 4, 2).date(),
        datetime(2021, 4, 21).date(),
        datetime(2021, 4, 25).date(),
        datetime(2021, 8, 15).date(),
        datetime(2021, 9, 10).date(),
        datetime(2021, 10, 2).date(),
        datetime(2021, 11, 5).date(),
        datetime(2022, 1, 26).date(),
        datetime(2022, 3, 18).date(),
        datetime(2022, 4, 14).date(),
        datetime(2022, 8, 9).date(),
        datetime(2022, 8, 31).date(),
        datetime(2022, 10, 5).date(),
        datetime(2022, 10, 24).date(),
        datetime(2023, 3, 7).date(),
        datetime(2023, 3, 30).date(),
        datetime(2023, 4, 4).date(),
        datetime(2023, 4, 14).date(),
        datetime(2023, 8, 15).date(),
        datetime(2023, 8, 30).date(),
        datetime(2023, 9, 19).date(),
        datetime(2023, 9, 28).date(),
        datetime(2023, 11, 12).date(),
        datetime(2023, 11, 13).date(),
        datetime(2023, 11, 27).date(),
        datetime(2024, 1, 26).date(),
        datetime(2024, 3, 8).date(),
        datetime(2024, 3, 25).date(),
        datetime(2024, 3, 29).date(),
        datetime(2024, 4, 11).date(),
        datetime(2024, 4, 17).date(),
        datetime(2024, 4, 21).date(),
        datetime(2024, 8, 15).date(),
        datetime(2024, 8, 26).date(),
        datetime(2024, 9, 16).date(),
        datetime(2024, 10, 2).date(),
        datetime(2024, 10, 12).date(),
        datetime(2024, 11, 1).date(),
        datetime(2024, 11, 15).date(),
        datetime(2025, 1, 26).date(),
        datetime(2025, 3, 8).date(),
        datetime(2025, 3, 31).date(),
        datetime(2025, 4, 18).date(),
    }
    return holidays

def calculate_days_to_expiry(date, monthly_expiries, weekly_expiries):
    """Calculate days to next monthly and weekly expiry."""
    date = pd.Timestamp(date).date()
    
    # Find next monthly expiry
    days_to_monthly = None
    for expiry in monthly_expiries:
        if expiry > date:
            days_to_monthly = (expiry - date).days
            break
    
    # Find next weekly expiry
    days_to_weekly = None
    for expiry in weekly_expiries:
        if expiry > date:
            days_to_weekly = (expiry - date).days
            break
    
    return days_to_monthly, days_to_weekly

def analyze_index_ohlc(symbol, df):
    """
    6-Point Analysis:
    1. Intraday movement (Open-Close)
    2. Overnight movement (Close-Open next day)
    3. Days-to-expiry impact (monthly)
    4. Days-to-expiry impact (weekly)
    5. Day-of-week bias
    6. Volatility by day-of-week and expiry proximity
    """
    
    if df is None or len(df) == 0:
        print(f"⚠️  No data for {symbol}")
        return None
    
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp
    time_col = 'timestamp' if 'timestamp' in df.columns else ('time' if 'time' in df.columns else None)
    if not time_col:
        print(f"⚠️  No timestamp/time column for {symbol}")
        return None
    
    # Convert to datetime
    if df[time_col].dtype != 'datetime64[ns]':
        if df[time_col].max() > 100000000000:
            df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
        else:
            df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
    else:
        df['timestamp'] = df[time_col]
    
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['open', 'close']).sort_values('timestamp').reset_index(drop=True)
    
    # Filter 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df) == 0:
        print(f"⚠️  No 5-year data for {symbol}")
        return None
    
    print(f"✅ {symbol}: {len(df)} records for 5Y analysis")
    
    # Add metrics
    df['date'] = df['timestamp'].dt.date
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['weekday_num'] = df['timestamp'].dt.weekday
    
    # 1. Intraday movement (Open-Close)
    df['intraday_move'] = ((df['close'] - df['open']) / df['open'] * 100).round(4)
    
    # 2. Overnight movement (Close-Open next day)
    df['overnight_move'] = ((df['open'].shift(-1) - df['close']) / df['close'] * 100).round(4)
    
    # 3-4. Days to expiry
    monthly_expiries = get_monthly_expiry_dates()
    weekly_expiries = get_weekly_expiry_dates()
    
    days_to_expiry = []
    for date in df['date']:
        d_monthly, d_weekly = calculate_days_to_expiry(date, monthly_expiries, weekly_expiries)
        days_to_expiry.append({'days_to_monthly_expiry': d_monthly, 'days_to_weekly_expiry': d_weekly})
    
    df_expiry = pd.DataFrame(days_to_expiry)
    df = pd.concat([df, df_expiry], axis=1)
    
    # 5. High-Low range (volatility proxy)
    df['volatility'] = ((df['high'] - df['low']) / df['open'] * 100).round(4)
    
    return df

def generate_reports(symbol, df_analyzed):
    """Generate comprehensive reports."""
    
    if df_analyzed is None or len(df_analyzed) == 0:
        return
    
    # Save detailed CSV
    csv_path = REPORTS_DIR / f"{symbol}_5y_detailed.csv"
    df_analyzed.to_csv(csv_path, index=False)
    print(f"📊 Saved detailed analysis: {csv_path.name}")
    
    # Summary statistics by day of week
    summary_by_dow = df_analyzed.groupby('day_of_week').agg({
        'intraday_move': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'overnight_move': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'volatility': ['mean', 'median', 'std']
    }).round(4)
    
    summary_by_dow.columns = ['intraday_mean', 'intraday_median', 'intraday_std', 'intraday_win%',
                               'overnight_mean', 'overnight_median', 'overnight_std', 'overnight_win%',
                               'vol_mean', 'vol_median', 'vol_std']
    
    summary_path = REPORTS_DIR / f"{symbol}_5y_by_dow.csv"
    summary_by_dow.to_csv(summary_path)
    print(f"📊 Saved day-of-week summary: {summary_path.name}")
    
    # Summary by days to expiry
    df_with_expiry = df_analyzed.dropna(subset=['days_to_monthly_expiry'])
    if len(df_with_expiry) > 0:
        summary_by_expiry = df_with_expiry.groupby('days_to_monthly_expiry').agg({
            'intraday_move': ['mean', 'std', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0],
            'overnight_move': ['mean', 'std'],
            'volatility': ['mean']
        }).round(4)
        
        summary_by_expiry.columns = ['intraday_mean', 'intraday_std', 'intraday_win%',
                                      'overnight_mean', 'overnight_std', 'vol_mean']
        
        expiry_path = REPORTS_DIR / f"{symbol}_5y_by_expiry.csv"
        summary_by_expiry.to_csv(expiry_path)
        print(f"📊 Saved expiry summary: {expiry_path.name}")
    
    return summary_by_dow, df_analyzed

def main():
    print("=" * 80)
    print("6-POINT INDEX ANALYSIS: Fetching & Analyzing Daily Data")
    print("=" * 80)
    
    # Step 1: Fetch all indices from Dhan
    print("\n[1/3] FETCHING INDEX DATA FROM DHAN")
    print("-" * 80)
    
    fetched_files = {}
    
    # Try to fetch missing indices
    missing_indices = {k: v for k, v in INDEX_CONFIG.items() if k not in ["NIFTY50", "NIFTY200"]}
    
    if DHAN_API_KEY:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_index_data_from_dhan, symbol, config): symbol 
                      for symbol, config in missing_indices.items()}
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    result = future.result()
                    if result:
                        fetched_files[symbol] = result
                except Exception as e:
                    print(f"⚠️  Error fetching {symbol}: {e}")
    else:
        print("⚠️  DHAN_API_KEY not set, skipping API fetches")
    
    # Load all available indices
    print("\n[2/3] LOADING CACHED DATA")
    print("-" * 80)
    
    all_data = {}
    for symbol, config in INDEX_CONFIG.items():
        filepath = CACHE_DIR / config["file"]
        df = load_cached_data(filepath)
        if df is not None:
            all_data[symbol] = df
            print(f"✅ Loaded {symbol}: {len(df)} candles")
        else:
            print(f"⚠️  Could not load {symbol}")
    
    # Step 2: Analyze
    print("\n[3/3] ANALYZING DATA (6-POINT METRICS)")
    print("-" * 80)
    
    all_analyzed = {}
    for symbol, df in all_data.items():
        df_analyzed = analyze_index_ohlc(symbol, df)
        if df_analyzed is not None:
            all_analyzed[symbol] = df_analyzed
            generate_reports(symbol, df_analyzed)
    
    # Create comparison summary
    print("\n" + "=" * 80)
    print("SUMMARY: All Indices Analysis Complete")
    print("=" * 80)
    print(f"✅ Analyzed {len(all_analyzed)} indices")
    print(f"✅ Reports saved to: {REPORTS_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()


# ========== FROM: add_sector_to_scrip_master.py ==========

#!/usr/bin/env python3
"""
Add Sector Column to Scrip Master Files
========================================
Enriches dhan-scrip-master-detailed.csv and groww-scrip-master-detailed.csv
with sector information from Large Cap, Mid Cap, and Small Cap CSV files.
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

def load_sector_data():
    """Load and combine sector data from all cap files."""
    sector_map = {}
    
    files = [
        ("Large Cap_NSE_2026-01-02.csv", "Large Cap"),
        ("Mid Cap_NSE_2026-01-02.csv", "Mid Cap"),
        ("Small Cap_NSE_2026-01-02.csv", "Small Cap"),
    ]
    
    for filename, cap_type in files:
        filepath = DATA_DIR / filename
        if filepath.exists():
            print(f"Loading {filename}...")
            df = pd.read_csv(filepath)
            print(f"   Found {len(df)} rows")
            
            for _, row in df.iterrows():
                symbol = str(row.get("Symbol", "")).strip()
                sector = str(row.get("Sector", "")).strip()
                
                if symbol and sector and sector != "nan":
                    # Clean symbol - remove any suffixes like .E1
                    clean_symbol = symbol.split(".")[0]
                    
                    # Store both the original and cleaned symbol
                    if symbol not in sector_map:
                        sector_map[symbol] = {"sector": sector, "cap_type": cap_type}
                    if clean_symbol not in sector_map:
                        sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
        else:
            print(f"   Warning: {filename} not found")
    
    print(f"\nTotal unique symbols with sector data: {len(sector_map)}")
    return sector_map


def update_dhan_scrip_master(sector_map):
    """Update dhan-scrip-master-detailed.csv with sector information."""
    filepath = DATA_DIR / "dhan-scrip-master-detailed.csv"
    
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return
    
    print(f"\nUpdating {filepath}...")
    df = pd.read_csv(filepath)
    print(f"   Original rows: {len(df)}")
    
    # Add new columns
    df["SECTOR"] = ""
    df["CAP_TYPE"] = ""
    
    # Match count
    matched = 0
    
    # Try to match by SEM_TRADING_SYMBOL (column 6) and SM_SYMBOL_NAME (column 16)
    for idx, row in df.iterrows():
        trading_symbol = str(row.get("SEM_TRADING_SYMBOL", "")).strip()
        symbol_name = str(row.get("SM_SYMBOL_NAME", "")).strip()
        
        # Clean trading symbol - take first part before any dash
        clean_trading = trading_symbol.split("-")[0] if trading_symbol else ""
        
        # Try different matching strategies
        sector_info = None
        
        # 1. Try exact trading symbol match
        if trading_symbol in sector_map:
            sector_info = sector_map[trading_symbol]
        # 2. Try cleaned trading symbol
        elif clean_trading in sector_map:
            sector_info = sector_map[clean_trading]
        # 3. Try symbol name (typically first word)
        elif symbol_name:
            first_word = symbol_name.split()[0] if symbol_name else ""
            if first_word in sector_map:
                sector_info = sector_map[first_word]
        
        if sector_info:
            df.at[idx, "SECTOR"] = sector_info["sector"]
            df.at[idx, "CAP_TYPE"] = sector_info["cap_type"]
            matched += 1
    
    print(f"   Matched {matched} rows with sector data")
    
    # Save updated file
    df.to_csv(filepath, index=False)
    print(f"   Saved updated file: {filepath}")
    
    # Show sample of matched rows
    matched_df = df[df["SECTOR"] != ""].head(10)
    print(f"\n   Sample matched rows:")
    if "SEM_TRADING_SYMBOL" in df.columns:
        print(matched_df[["SEM_TRADING_SYMBOL", "SECTOR", "CAP_TYPE"]].to_string())


def update_groww_scrip_master(sector_map):
    """Update groww-scrip-master-detailed.csv with sector information."""
    filepath = DATA_DIR / "groww-scrip-master-detailed.csv"
    
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return
    
    print(f"\nUpdating {filepath}...")
    df = pd.read_csv(filepath)
    print(f"   Original rows: {len(df)}")
    
    # Add new columns
    df["SECTOR"] = ""
    df["CAP_TYPE"] = ""
    
    # Match count
    matched = 0
    
    # Try to match by trading_symbol, underlying_symbol, or groww_symbol
    for idx, row in df.iterrows():
        trading_symbol = str(row.get("trading_symbol", "")).strip()
        underlying_symbol = str(row.get("underlying_symbol", "")).strip()
        groww_symbol = str(row.get("groww_symbol", "")).strip()
        
        # Clean symbols
        clean_trading = trading_symbol.split("-")[0] if trading_symbol else ""
        
        # Try different matching strategies
        sector_info = None
        
        # 1. Try exact trading symbol match
        if trading_symbol in sector_map:
            sector_info = sector_map[trading_symbol]
        # 2. Try underlying symbol
        elif underlying_symbol in sector_map:
            sector_info = sector_map[underlying_symbol]
        # 3. Try cleaned trading symbol  
        elif clean_trading in sector_map:
            sector_info = sector_map[clean_trading]
        # 4. Try extracting from groww_symbol (format: NSE-SYMBOL-...)
        elif groww_symbol:
            parts = groww_symbol.split("-")
            if len(parts) >= 2:
                extracted = parts[1]
                if extracted in sector_map:
                    sector_info = sector_map[extracted]
        
        if sector_info:
            df.at[idx, "SECTOR"] = sector_info["sector"]
            df.at[idx, "CAP_TYPE"] = sector_info["cap_type"]
            matched += 1
    
    print(f"   Matched {matched} rows with sector data")
    
    # Save updated file
    df.to_csv(filepath, index=False)
    print(f"   Saved updated file: {filepath}")
    
    # Show sample of matched rows
    matched_df = df[df["SECTOR"] != ""].head(10)
    print(f"\n   Sample matched rows:")
    cols_to_show = ["trading_symbol", "SECTOR", "CAP_TYPE"]
    cols_available = [c for c in cols_to_show if c in df.columns]
    if cols_available:
        print(matched_df[cols_available].to_string())


def print_sector_summary(sector_map):
    """Print summary of sectors found."""
    sectors = {}
    for symbol, info in sector_map.items():
        sector = info["sector"]
        if sector not in sectors:
            sectors[sector] = 0
        sectors[sector] += 1
    
    print("\n" + "="*50)
    print("SECTOR SUMMARY")
    print("="*50)
    for sector, count in sorted(sectors.items(), key=lambda x: -x[1]):
        print(f"   {sector}: {count} symbols")


def main():
    print("="*60)
    print("ADDING SECTOR DATA TO SCRIP MASTER FILES")
    print("="*60)
    
    # Load sector data
    sector_map = load_sector_data()
    
    if not sector_map:
        print("No sector data loaded. Exiting.")
        return
    
    # Print sector summary
    print_sector_summary(sector_map)
    
    # Update scrip master files
    update_dhan_scrip_master(sector_map)
    update_groww_scrip_master(sector_map)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()


# ========== FROM: recalculate_alpha_beta.py ==========

#!/usr/bin/env python3
"""
Recalculate alpha/beta for the completed backtest using real NIFTY50 benchmark.

This script regenerates the summary metrics with proper alpha/beta calculations
now that we have the NIFTYBEES (NIFTY50) benchmark file.
"""

import sys
from pathlib import Path
import pandas as pd

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

def recalculate_alpha_beta():
    """Recalculate alpha/beta for the backtest."""
    
    print("\n" + "="*80)
    print("🔄 RECALCULATING ALPHA/BETA WITH REAL NIFTY50 BENCHMARK")
    print("="*80)
    
    from core.metrics import compute_comprehensive_metrics, load_benchmark
    
    # Report directory
    report_dir = Path("reports/0103-2036-weekly-green-bb-basket-large-mid-1d")
    summary_file = report_dir / "strategy_backtests_summary.csv"
    
    if not report_dir.exists():
        print(f"❌ Report directory not found: {report_dir}")
        return False
    
    print(f"\n📂 Report directory: {report_dir}")
    
    # Load benchmark
    print("\n📊 Loading NIFTY50 benchmark...")
    benchmark_df = load_benchmark(interval="1d")
    
    if benchmark_df is None:
        print("❌ Benchmark still not loaded!")
        return False
    
    print(f"✅ Loaded benchmark: {len(benchmark_df)} rows")
    
    # Process each period
    periods = ["1Y", "3Y", "5Y", "MAX"]
    results_by_period = {}
    
    for period in periods:
        equity_file = report_dir / f"portfolio_daily_equity_curve_{period}.csv"
        trades_file = report_dir / f"consolidated_trades_{period}.csv"
        
        if not equity_file.exists():
            print(f"⚠️  Skipping {period} - equity file not found")
            continue
        
        print(f"\n📈 Processing {period}...")
        
        # Load equity curve
        equity_df = pd.read_csv(equity_file)
        equity_df['Date'] = pd.to_datetime(equity_df['Date']).dt.normalize()  # Normalize to date only
        equity_df['Equity'] = equity_df['Equity'].astype(float)
        
        # Load trades
        trades_df = None
        if trades_file.exists():
            trades_df = pd.read_csv(trades_file)
        
        # Create a copy of benchmark with normalized dates
        benchmark_aligned = benchmark_df.copy()
        benchmark_aligned.index = pd.to_datetime(benchmark_aligned.index).normalize()
        
        # Calculate metrics with benchmark
        try:
            # Use daily returns alignment approach
            from core.metrics import get_daily_returns_from_equity, calculate_alpha_beta
            
            # Get equity series with normalized date index
            equity_series = pd.Series(
                equity_df['Equity'].values,
                index=equity_df['Date'].values
            )
            equity_daily_returns = get_daily_returns_from_equity(equity_series)
            
            # Get benchmark returns
            benchmark_equity = benchmark_aligned['equity'].astype(float)
            benchmark_returns = get_daily_returns_from_equity(benchmark_equity)
            
            # Align to common dates
            common_dates = equity_daily_returns.index.intersection(benchmark_returns.index)
            
            print(f"  Equity dates: {equity_series.index.min()} to {equity_series.index.max()} ({len(equity_series)})")
            print(f"  Benchmark dates: {benchmark_equity.index.min()} to {benchmark_equity.index.max()} ({len(benchmark_equity)})")
            print(f"  Aligned dates: {len(common_dates)} common trading days")
            
            if len(common_dates) > 10:
                # Calculate alpha and beta
                alpha_pct, beta = calculate_alpha_beta(
                    equity_daily_returns.loc[common_dates],
                    benchmark_returns.loc[common_dates]
                )
                
                print(f"  ✅ Alpha: {alpha_pct*100:.2f}%")
                print(f"     Beta:  {beta:.4f}")
                
                results_by_period[period] = {
                    "alpha": alpha_pct * 100,
                    "beta": beta,
                }
            else:
                print(f"  ⚠️  Not enough overlapping dates, using fallback")
                results_by_period[period] = {"alpha": 0.0, "beta": 0.0}
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            results_by_period[period] = {"alpha": 0.0, "beta": 0.0}

    
    # Update summary file
    if summary_file.exists():
        print(f"\n📝 Updating summary file: {summary_file}")
        
        summary_df = pd.read_csv(summary_file)
        
        # Update Alpha and Beta columns
        for idx, row in summary_df.iterrows():
            period = row["Window"]
            if period in results_by_period:
                summary_df.at[idx, "Alpha [%]"] = results_by_period[period]["alpha"]
                summary_df.at[idx, "Beta"] = results_by_period[period]["beta"]
        
        # Save updated summary
        summary_df.to_csv(summary_file, index=False)
        
        print(f"✅ Updated summary file:")
        print("\nUpdated metrics:")
        print(summary_df[["Window", "Alpha [%]", "Beta"]].to_string(index=False))
        
        return True
    else:
        print(f"❌ Summary file not found: {summary_file}")
        return False


if __name__ == "__main__":
    try:
        success = recalculate_alpha_beta()
        if success:
            print(f"\n✅ Alpha/Beta recalculation complete!")
            print(f"   Summary file updated with real NIFTY50 benchmark values")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ========== FROM: create_benchmark_data.py ==========

#!/usr/bin/env python3
"""
Create benchmark data for alpha/beta calculations using real NIFTY50 data.

This script uses real NIFTY50 daily price history from the cache directory.
NIFTY50 is India's primary stock market index (CNX NIFTY).
"""

import sys
from pathlib import Path
import pandas as pd

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

def create_nifty_benchmark():
    """Create NIFTYBEES benchmark data from real NIFTY50."""
    
    print("\n" + "="*80)
    print("📊 CREATING NIFTYBEES BENCHMARK FROM REAL NIFTY50 DATA")
    print("="*80)
    
    # Source files
    nifty50_file = Path("data/cache/dhan/daily/dhan_13_NIFTY_50_1d.csv")
    nifty200_file = Path("data/cache/dhan/daily/dhan_18_NIFTY_200_1d.csv")
    
    # Use NIFTY50 (primary index)
    if not nifty50_file.exists():
        print(f"❌ NIFTY50 file not found: {nifty50_file}")
        return None
    
    print(f"\n📂 Loading NIFTY50 data from: {nifty50_file}")
    
    # Read NIFTY50 data
    df = pd.read_csv(nifty50_file)
    
    # Rename columns to match expected format
    df = df.rename(columns={
        'time': 'tradingDate',
        'close': 'close',
    })
    
    # Ensure tradingDate is datetime
    df['tradingDate'] = pd.to_datetime(df['tradingDate'])
    df['date'] = df['tradingDate']
    
    # Add 'equity' column (same as close price for benchmark)
    df['equity'] = df['close']
    
    # Reorder and select columns
    df = df[[
        'tradingDate', 'date', 'open', 'high', 'low', 'close', 'volume', 'equity'
    ]].copy()
    
    # Sort by date
    df = df.sort_values('date').reset_index(drop=True)
    
    print(f"\n✅ Loaded NIFTY50 data:")
    print(f"   Rows: {len(df)}")
    print(f"   Date range: {df['tradingDate'].min().date()} to {df['tradingDate'].max().date()}")
    print(f"   Price range: {df['close'].min():.0f} - {df['close'].max():.0f}")
    print(f"   Total return: {((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100:.1f}%")
    
    # Save as NIFTYBEES benchmark
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = cache_dir / "dhan_10576_NIFTYBEES_1d.csv"
    df.to_csv(output_file, index=False)
    
    print(f"\n✅ Created NIFTYBEES benchmark file:")
    print(f"   Location: {output_file}")
    print(f"   Source: NIFTY50 (dhan_13_NIFTY_50_1d.csv)")
    
    # Show sample
    print(f"\n📋 Sample data (first 5 rows):")
    print(df.head(5)[['date', 'open', 'high', 'low', 'close', 'volume']].to_string())
    
    print(f"\n📋 Sample data (last 5 rows):")
    print(df.tail(5)[['date', 'open', 'high', 'low', 'close', 'volume']].to_string())
    
    return output_file


if __name__ == "__main__":
    try:
        output = create_nifty_benchmark()
        if output:
            print(f"\n✅ Benchmark data created successfully!")
            print(f"   Ready for alpha/beta calculations against NIFTY50")
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error creating benchmark: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


# ========== FROM: btst_marubozu_backtest.py ==========

#!/usr/bin/env python3
"""BTST Marubozu Backtest"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path

CACHE_DIR = Path('data/cache')

SYMBOLS = [
    'RELIANCE', 'BHARTIARTL', 'ICICIBANK', 'SBIN', 'BAJFINANCE', 'LICI', 'LT',
    'HCLTECH', 'AXISBANK', 'ULTRACEMCO', 'TITAN', 'BAJAJFINSV', 'ADANIPORTS',
    'NTPC', 'HAL', 'BEL', 'ADANIENT', 'ASIANPAINT', 'ADANIPOWER', 'DMART',
    'COALINDIA', 'IOC', 'INDIGO', 'TATASTEEL', 'VEDL', 'SBILIFE', 'JIOFIN',
    'GRASIM', 'LTIM', 'HINDALCO', 'DLF', 'ADANIGREEN', 'BPCL', 'TECHM',
    'PIDILITIND', 'IRFC', 'TRENT', 'BANKBARODA', 'CHOLAFIN', 'PNB',
    'TATAPOWER', 'SIEMENS', 'UNIONBANK', 'PFC', 'TATACONSUM', 'BSE', 'GAIL',
    'HDFCAMC', 'ABB', 'GMRAIRPORT', 'MAZDOCK', 'INDUSTOWER', 'IDBI', 'CGPOWER',
    'PERSISTENT', 'HDFCBANK', 'TCS', 'INFY', 'HINDUNILVR', 'ITC', 'MARUTI',
    'SUNPHARMA', 'KOTAKBANK', 'ONGC', 'JSWSTEEL', 'WIPRO', 'POWERGRID',
    'NESTLEIND', 'HINDZINC', 'EICHERMOT', 'TVSMOTOR', 'DIVISLAB', 'HDFCLIFE',
    'VBL', 'SHRIRAMFIN', 'MUTHOOTFIN', 'BRITANNIA', 'AMBUJACEM', 'TORNTPHARM',
    'HEROMOTOCO', 'CUMMINSIND', 'CIPLA', 'GODREJCP', 'POLYCAB', 'BOSCHLTD',
    'DRREDDY', 'MAXHEALTH', 'INDHOTEL', 'APOLLOHOSP', 'JINDALSTEL',
]

MIN_BODY_PCT = 5.0
MIN_BODY_RANGE = 0.80
ROUND_TRIP_COST = 0.37

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

trades = []

for sym in SYMBOLS:
    file = find_file(sym)
    if not file:
        continue
    
    df = pd.read_csv(file)
    df['time'] = pd.to_datetime(df['time'])
    df = df.drop_duplicates(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    df = df[(df['time'] >= '2016-01-01') & (df['time'] < '2025-01-01')]
    
    if len(df) < 10:
        continue
    
    df['body'] = df['close'] - df['open']
    df['range'] = df['high'] - df['low']
    df['body_pct'] = (df['body'] / df['open']) * 100
    df['body_ratio'] = df['body'] / df['range'].replace(0, np.nan)
    df['is_marubozu'] = (df['body'] > 0) & (df['body_pct'] >= MIN_BODY_PCT) & (df['body_ratio'] >= MIN_BODY_RANGE)
    
    df['next_close'] = df['close'].shift(-1)
    df['ret_btst_gross'] = (df['next_close'] - df['close']) / df['close'] * 100
    df['ret_btst_net'] = df['ret_btst_gross'] - ROUND_TRIP_COST
    
    signals = df[df['is_marubozu'] & df['ret_btst_gross'].notna()].copy()
    
    for _, row in signals.iterrows():
        trades.append({
            'year': row['time'].year,
            'symbol': sym,
            'ret_gross': row['ret_btst_gross'],
            'ret_net': row['ret_btst_net'],
        })

df_trades = pd.DataFrame(trades)

print('='*80)
print('BTST MARUBOZU BACKTEST (Buy at 3:25 PM today, Sell at 3:25 PM tomorrow)')
print('='*80)
print(f'\nRound Trip Cost: {ROUND_TRIP_COST}% (delivery)\n')

print('GROSS RETURNS (before charges):')
print('-'*60)
print(f'Total Trades: {len(df_trades):,}')
print(f'Avg Return: {df_trades["ret_gross"].mean():.2f}%')
print(f'Win Rate: {(df_trades["ret_gross"] > 0).mean() * 100:.1f}%')

yearly_gross = df_trades.groupby('year')['ret_gross'].mean()
print(f'Years Positive: {(yearly_gross > 0).sum()}/{len(yearly_gross)}')
print()

print('NET RETURNS (after 0.37% charges):')
print('-'*60)
print(f'Total Trades: {len(df_trades):,}')
print(f'Avg Return: {df_trades["ret_net"].mean():.2f}%')
print(f'Win Rate: {(df_trades["ret_net"] > 0).mean() * 100:.1f}%')

yearly_net = df_trades.groupby('year')['ret_net'].mean()
print(f'Years Positive: {(yearly_net > 0).sum()}/{len(yearly_net)}')
print()

print('YEAR-BY-YEAR BREAKDOWN (Net):')
print('-'*60)
print(f'{"Year":<6} {"Trades":>8} {"Avg Ret":>10} {"Win%":>8} {"Total%":>10}')
print('-'*60)
for year in sorted(df_trades['year'].unique()):
    year_df = df_trades[df_trades['year'] == year]
    trades_n = len(year_df)
    avg_ret = year_df['ret_net'].mean()
    win_pct = (year_df['ret_net'] > 0).mean() * 100
    total_ret = year_df['ret_net'].sum()
    print(f'{year:<6} {trades_n:>8} {avg_ret:>+9.2f}% {win_pct:>7.1f}% {total_ret:>+9.1f}%')


# ========== FROM: fetch_etf_data.py ==========

#!/usr/bin/env python3
"""
Fetch Daily OHLCV data for ETFs from Dhan API
=============================================
Fetches historical daily data for all ETFs listed in input CSV.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY3NDI0NTgyLCJpYXQiOjE3NjczMzgxODIsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA4MzUxNjQ4In0.ONvXG5h3E1ka12NAOGEyoP7UInZww3Z5gFyctSqWaDPdtvbfGYpg04GfcBrKdnzVPA8WvBpgAc8RcKxG34n6gA"

CACHE_DIR = Path("data/cache/dhan/daily")
MASTER_FILE = Path("data/dhan-scrip-master-detailed.csv")

# ETF symbols from the user's file
ETF_SYMBOLS = [
    "NIFTYBETA", "NEXT50BETA", "ALPHA", "IT", "LOWVOL1", "MIDCAP", "GILT5BETA",
    "GILT10BETA", "MIDCAPBETA", "MNC", "CONS", "VAL30IETF", "MOMIDMTM", "ESG",
    "MID150CASE", "BSLNIFTY", "ELIQUID", "MULTICAP", "NEXT50IETF", "MOMNC",
    "SENSEXADD", "ESENSEX", "TECH", "MONQ50", "BANKADD", "LICNETFGSC",
    "MIDCAPIETF", "AUTOBEES", "TATAGOLD", "GOLDBEES", "GROWWNET", "AXSENSEX",
    "METALIETF", "MSCIADD", "TNIDETF", "ALPHAETF", "SBIETFQLTY", "AONENIFTY",
    "TOP10ADD", "NV20IETF", "METAL", "MOLOWVOL", "LOWVOLIETF", "MONIFTY500",
    "HEALTHIETF", "UNIONGOLD", "SETFNN50", "LIQUIDADD", "ALPL30IETF",
    "SILVERBEES", "MOSILVER", "HDFCQUAL", "GSEC10ABSL", "MAFANG", "GILT5YBEES",
    "MOINFRA", "HDFCNEXT50", "MONEXT50", "NIFTYCASE", "SBIETFCON", "GOLDBND",
    "ABSLLIQUID", "EVIETF", "LIQUIDETF", "SETFNIFBK", "TOP15IETF", "SILVERBND",
    "CONSUMIETF", "HDFCGROWTH", "CPSEETF", "SBINEQWETF", "GSEC10YEAR", "HDFCGOLD",
    "MOHEALTH", "BANKIETF", "MOMGF", "MOIPO", "ITETF", "SML100CASE", "GOLDIETF",
    "TOP100CASE", "QUAL30IETF", "GROWWNXT50", "GOLDADD", "HDFCPVTBAN",
    "MIDQ50ADD", "MOGOLD", "BANKPSU", "CONSUMER", "GSEC10IETF", "MOVALUE",
    "HDFCNIFTY", "AXISTECETF", "INTERNET", "SELECTIPO", "EBANKNIFTY",
    "SILVERCASE", "GROWWGOLD", "PSUBNKBEES", "LICNETFN50", "EMULTIMQ",
    "NIFTYQLITY", "GROWWPOWER", "GROWWLOVOL", "GSEC5IETF", "SNXT30BEES",
    "SBIETFPB", "GROWWMOM50", "ABSLNN50ET", "NIF100BEES", "SMALL250",
    "MIDSELIETF", "LOWVOL", "LIQUID", "FINIETF", "LICMFGOLD", "NIFTYADD",
    "LIQUIDSHRI", "FMCGIETF", "CONSUMBEES", "CHOICEGOLD", "LIQUIDPLUS",
    "HDFCVALUE", "SILVERADD", "INFRAIETF", "HNGSNGBEES", "MANUFGBEES",
    "ABSLBANETF", "QGOLDHALF", "GOLD360", "MOGSEC", "MOPSE", "GROWWLIQID",
    "INFRABEES"
]

MAX_RETRIES = 3
BASE_WAIT_TIME = 0.5
DAILY_DATA_CUTOFF = datetime(2015, 11, 9)


def get_headers():
    """Get request headers."""
    return {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
    }


def load_etf_mapping():
    """Load ETF security IDs from master file."""
    if not MASTER_FILE.exists():
        print(f"❌ Master file not found: {MASTER_FILE}")
        return {}

    try:
        df = pd.read_csv(MASTER_FILE, low_memory=False)
        # Filter for NSE equity (ETFs are under NSE equity segment)
        nse_eq = df[(df['SEM_EXM_EXCH_ID'] == 'NSE') & (df['SEM_SEGMENT'] == 'E')]
        
        mapping = {}
        for _, row in nse_eq.iterrows():
            symbol = row["SEM_TRADING_SYMBOL"]
            if symbol in ETF_SYMBOLS:
                secid = int(row["SEM_SMST_SECURITY_ID"])
                mapping[symbol] = secid
        
        print(f"📊 Found {len(mapping)} ETFs in master file out of {len(ETF_SYMBOLS)} requested")
        return mapping
    except Exception as e:
        print(f"❌ Failed to load master data: {e}")
        return {}


def fetch_with_retry(endpoint, payload, description):
    """Make API request with exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=get_headers(),
                timeout=15,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 401:
                print(f"❌ Unauthorized - check token")
                return None

            if response.status_code == 429:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                print(f"⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                time.sleep(wait)

        except (requests.Timeout, Exception) as e:
            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                time.sleep(wait)

    return None


def fetch_daily_data(sec_id, symbol, start_date, end_date):
    """Fetch daily candles for an ETF."""
    payload = {
        "securityId": str(sec_id),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",  # ETFs use EQUITY instrument type in Dhan
        "expiryCode": 0,
        "oi": False,
        "fromDate": start_date.strftime("%Y-%m-%d"),
        "toDate": end_date.strftime("%Y-%m-%d"),
    }

    data = fetch_with_retry(
        f"{DHAN_BASE_URL}/charts/historical",
        payload,
        f"daily {symbol}",
    )

    if not data or "timestamp" not in data:
        return None

    try:
        df = pd.DataFrame({
            "time": data["timestamp"],
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
        })

        if df.empty:
            return None

        # Convert Unix epoch to IST
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
        return df.sort_values("time").reset_index(drop=True)

    except Exception as e:
        print(f"❌ Error parsing {symbol}: {e}")
        return None


def save_candles(df, sec_id, symbol):
    """Save candles to CSV."""
    if df is None or df.empty:
        return False

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        output_file = CACHE_DIR / f"dhan_{sec_id}_{symbol}_1d.csv"

        df_save = df[["time", "open", "high", "low", "close", "volume"]].copy()
        df_save["time"] = pd.to_datetime(df_save["time"])

        # Convert IST to tz-naive for storage
        if df_save["time"].dt.tz is not None:
            df_save["time"] = df_save["time"].dt.tz_localize(None)

        df_save.set_index("time").to_csv(output_file)
        return True

    except Exception as e:
        print(f"❌ Error saving {symbol}: {e}")
        return False


def main():
    print("=" * 60)
    print("ETF Daily Data Fetcher - Dhan API")
    print("=" * 60)
    
    # Load ETF mapping
    etf_mapping = load_etf_mapping()
    
    if not etf_mapping:
        print("❌ No ETF mappings found. Check master file.")
        return
    
    # Find missing symbols
    missing = set(ETF_SYMBOLS) - set(etf_mapping.keys())
    if missing:
        print(f"\n⚠️ {len(missing)} symbols not found in master:")
        for s in sorted(missing):
            print(f"   - {s}")
    
    # Set date range
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    start_date = DAILY_DATA_CUTOFF
    
    print(f"\n📅 Date range: {start_date.date()} to {end_date.date()}")
    print(f"📂 Cache directory: {CACHE_DIR}")
    
    # Fetch data for each ETF
    success_count = 0
    fail_count = 0
    
    print(f"\n🚀 Fetching {len(etf_mapping)} ETFs...\n")
    
    for i, (symbol, sec_id) in enumerate(sorted(etf_mapping.items()), 1):
        print(f"[{i}/{len(etf_mapping)}] {symbol} (ID: {sec_id})...", end=" ")
        
        df = fetch_daily_data(sec_id, symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            if save_candles(df, sec_id, symbol):
                print(f"✅ {len(df)} candles")
                success_count += 1
            else:
                print("❌ Save failed")
                fail_count += 1
        else:
            print("❌ No data")
            fail_count += 1
        
        # Rate limiting
        time.sleep(0.3)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully fetched: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"⚠️ Not in master: {len(missing)}")
    print(f"\n📂 Data saved to: {CACHE_DIR}")


if __name__ == "__main__":
    main()
