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
