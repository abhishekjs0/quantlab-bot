"""
Hypothesis Analysis: Worst Day Performers Continue to Drop Next Day

Hypothesis: Stocks that are the worst performers (largest % drop) on a particular day 
will also close negative on the next trading day.

Analysis approach:
1. Load daily data for all symbols in basket_large.txt
2. For each trading day, identify the bottom N worst performers
3. Check if these stocks close negative on the next trading day
4. Calculate hit rate, average next-day return, and statistical significance
"""

import os
import sys
import glob
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import DATA_DIR, CACHE_DIR


def load_basket_symbols(basket_name: str = "basket_large.txt") -> list[str]:
    """Load symbols from a basket file."""
    basket_path = os.path.join(DATA_DIR, "baskets", basket_name)
    with open(basket_path, "r") as f:
        symbols = [line.strip() for line in f if line.strip()]
    return symbols


def load_symbol_data(symbol: str, cache_dir: Optional[str] = None) -> Optional[pd.DataFrame]:
    """Load daily OHLC data for a symbol from cache."""
    if cache_dir is None:
        cache_dir = os.path.join(DATA_DIR, "cache", "dhan", "daily")
    
    # Find matching file
    pattern = os.path.join(cache_dir, f"dhan_*_{symbol}_1d.csv")
    matches = glob.glob(pattern)
    
    if not matches:
        return None
    
    # Load the first match
    df = pd.read_csv(matches[0])
    
    # Parse datetime
    if 'start_time' in df.columns:
        df['Date'] = pd.to_datetime(df['start_time'])
    elif 'datetime' in df.columns:
        df['Date'] = pd.to_datetime(df['datetime'])
    elif 'date' in df.columns:
        df['Date'] = pd.to_datetime(df['date'])
    else:
        # Try first column
        df['Date'] = pd.to_datetime(df.iloc[:, 0])
    
    df = df.set_index('Date').sort_index()
    
    # Standardize column names
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'open' in col_lower:
            col_map[col] = 'Open'
        elif 'high' in col_lower:
            col_map[col] = 'High'
        elif 'low' in col_lower:
            col_map[col] = 'Low'
        elif 'close' in col_lower:
            col_map[col] = 'Close'
        elif 'volume' in col_lower:
            col_map[col] = 'Volume'
    
    df = df.rename(columns=col_map)
    
    return df[['Open', 'High', 'Low', 'Close', 'Volume']] if 'Volume' in df.columns else df[['Open', 'High', 'Low', 'Close']]


def calculate_daily_returns(df: pd.DataFrame) -> pd.Series:
    """Calculate daily percentage returns (close to close)."""
    # Remove duplicate indices by keeping the last entry
    df = df[~df.index.duplicated(keep='last')]
    return df['Close'].pct_change() * 100


def analyze_worst_performer_hypothesis(
    symbols: list[str],
    bottom_n: int = 5,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> dict:
    """
    Analyze the hypothesis that worst performers on day T will also drop on day T+1.
    
    Args:
        symbols: List of stock symbols to analyze
        bottom_n: Number of worst performers to select each day
        min_date: Optional minimum date for analysis (YYYY-MM-DD)
        max_date: Optional maximum date for analysis (YYYY-MM-DD)
    
    Returns:
        Dictionary with analysis results
    """
    print(f"Loading data for {len(symbols)} symbols...")
    
    # Load all data
    all_data = {}
    for sym in symbols:
        df = load_symbol_data(sym)
        if df is not None and len(df) > 50:  # Require at least 50 data points
            all_data[sym] = df
    
    print(f"Successfully loaded {len(all_data)} symbols with sufficient data")
    
    if len(all_data) < 10:
        print("Not enough symbols with data. Exiting.")
        return {}
    
    # Calculate daily returns for all symbols
    returns_df = pd.DataFrame()
    for sym, df in all_data.items():
        returns_df[sym] = calculate_daily_returns(df)
    
    # Drop rows with too many NaN values
    returns_df = returns_df.dropna(thresh=len(all_data) * 0.5)
    
    # Apply date filters
    if min_date:
        returns_df = returns_df[returns_df.index >= min_date]
    if max_date:
        returns_df = returns_df[returns_df.index <= max_date]
    
    print(f"Analyzing {len(returns_df)} trading days from {returns_df.index[0].date()} to {returns_df.index[-1].date()}")
    
    # Track results
    results = []
    
    # For each trading day (except the last one)
    for i in range(len(returns_df) - 1):
        current_date = returns_df.index[i]
        next_date = returns_df.index[i + 1]
        
        # Get returns for current day
        current_returns = returns_df.iloc[i].dropna()
        
        if len(current_returns) < bottom_n + 5:
            continue
        
        # Identify worst performers (most negative returns)
        worst_performers = current_returns.nsmallest(bottom_n)
        
        # Get next day returns for these worst performers
        next_day_returns = returns_df.iloc[i + 1]
        
        for sym in worst_performers.index:
            if sym in next_day_returns and not pd.isna(next_day_returns[sym]):
                results.append({
                    'date': current_date,
                    'next_date': next_date,
                    'symbol': sym,
                    'day_t_return': worst_performers[sym],
                    'day_t1_return': next_day_returns[sym],
                    'was_negative_next_day': next_day_returns[sym] < 0,
                    'rank': list(worst_performers.index).index(sym) + 1
                })
    
    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
        print("No results found!")
        return {}
    
    # Calculate statistics
    total_observations = len(results_df)
    negative_next_day = results_df['was_negative_next_day'].sum()
    hit_rate = negative_next_day / total_observations * 100
    
    avg_day_t_return = results_df['day_t_return'].mean()
    avg_day_t1_return = results_df['day_t1_return'].mean()
    
    # Calculate by rank (worst, 2nd worst, etc.)
    rank_stats = results_df.groupby('rank').agg({
        'day_t_return': 'mean',
        'day_t1_return': 'mean',
        'was_negative_next_day': ['sum', 'count']
    })
    rank_stats.columns = ['avg_day_t_return', 'avg_day_t1_return', 'negative_count', 'total_count']
    rank_stats['hit_rate'] = rank_stats['negative_count'] / rank_stats['total_count'] * 100
    
    # Calculate by severity of drop
    results_df['drop_severity'] = pd.qcut(results_df['day_t_return'], q=4, labels=['Extreme', 'Severe', 'Moderate', 'Mild'])
    severity_stats = results_df.groupby('drop_severity', observed=True).agg({
        'day_t_return': 'mean',
        'day_t1_return': 'mean',
        'was_negative_next_day': ['sum', 'count']
    })
    severity_stats.columns = ['avg_day_t_return', 'avg_day_t1_return', 'negative_count', 'total_count']
    severity_stats['hit_rate'] = severity_stats['negative_count'] / severity_stats['total_count'] * 100
    
    # Statistical significance test
    from scipy import stats
    # Null hypothesis: 50% chance of negative next day (random)
    # Alternative: different from 50%
    observed = negative_next_day
    expected = total_observations * 0.5
    chi2_stat = ((observed - expected) ** 2) / expected + ((total_observations - observed - expected) ** 2) / expected
    p_value = 1 - stats.chi2.cdf(chi2_stat, df=1)
    
    # One-sample t-test on next day returns (H0: mean = 0)
    t_stat, t_pvalue = stats.ttest_1samp(results_df['day_t1_return'].dropna(), 0)
    
    # Print results
    print("\n" + "="*80)
    print("HYPOTHESIS ANALYSIS: WORST PERFORMERS CONTINUE TO DROP")
    print("="*80)
    print(f"\nConfiguration:")
    print(f"  - Symbols analyzed: {len(all_data)}")
    print(f"  - Trading days analyzed: {len(returns_df)}")
    print(f"  - Bottom N worst performers per day: {bottom_n}")
    print(f"  - Total observations: {total_observations}")
    
    print(f"\n--- MAIN RESULTS ---")
    print(f"Average Day T return (worst performers): {avg_day_t_return:.2f}%")
    print(f"Average Day T+1 return: {avg_day_t1_return:.2f}%")
    print(f"Day T+1 Negative Close Rate: {hit_rate:.1f}% ({negative_next_day}/{total_observations})")
    
    print(f"\n--- STATISTICAL SIGNIFICANCE ---")
    print(f"Chi-square test (vs 50% baseline): p-value = {p_value:.4f}")
    print(f"T-test on Day T+1 returns (H0: mean=0): t={t_stat:.2f}, p={t_pvalue:.4f}")
    if p_value < 0.05:
        if hit_rate > 50:
            print("✓ Hypothesis SUPPORTED: Worst performers are significantly more likely to drop next day")
        else:
            print("✗ Hypothesis REJECTED: Worst performers are actually LESS likely to drop next day")
    else:
        print("⚡ Inconclusive: No statistically significant difference from random (50%)")
    
    print(f"\n--- BY RANK (1 = Worst) ---")
    print(rank_stats.to_string())
    
    print(f"\n--- BY DROP SEVERITY (Extreme = Largest drops) ---")
    print(severity_stats.to_string())
    
    # Monthly breakdown
    results_df['month'] = results_df['date'].dt.to_period('M')
    monthly_stats = results_df.groupby('month').agg({
        'day_t1_return': 'mean',
        'was_negative_next_day': ['sum', 'count']
    })
    monthly_stats.columns = ['avg_t1_return', 'negative_count', 'total']
    monthly_stats['hit_rate'] = monthly_stats['negative_count'] / monthly_stats['total'] * 100
    
    print(f"\n--- MONTHLY BREAKDOWN (Last 12 months) ---")
    print(monthly_stats.tail(12).to_string())
    
    # Check for mean reversion vs continuation
    print(f"\n--- MEAN REVERSION vs MOMENTUM ---")
    if avg_day_t1_return > 0:
        print(f"📈 MEAN REVERSION detected: Worst performers tend to recover (+{avg_day_t1_return:.2f}%)")
    elif avg_day_t1_return < 0:
        print(f"📉 MOMENTUM detected: Worst performers continue to drop ({avg_day_t1_return:.2f}%)")
    else:
        print("➡️ NEUTRAL: No clear direction on next day")
    
    return {
        'results_df': results_df,
        'rank_stats': rank_stats,
        'severity_stats': severity_stats,
        'monthly_stats': monthly_stats,
        'summary': {
            'total_observations': total_observations,
            'hit_rate': hit_rate,
            'avg_day_t_return': avg_day_t_return,
            'avg_day_t1_return': avg_day_t1_return,
            'p_value': p_value,
            't_pvalue': t_pvalue
        }
    }


def main():
    """Run the analysis."""
    # Load symbols from basket_large
    symbols = load_basket_symbols("basket_large.txt")
    print(f"Loaded {len(symbols)} symbols from basket_large.txt")
    
    # Run analysis with different configurations
    print("\n" + "#"*80)
    print("# ANALYSIS 1: Bottom 5 Worst Performers")
    print("#"*80)
    results_5 = analyze_worst_performer_hypothesis(symbols, bottom_n=5)
    
    print("\n" + "#"*80)
    print("# ANALYSIS 2: Bottom 10 Worst Performers")
    print("#"*80)
    results_10 = analyze_worst_performer_hypothesis(symbols, bottom_n=10)
    
    print("\n" + "#"*80)
    print("# ANALYSIS 3: Bottom 3 Worst Performers (Extreme losers only)")
    print("#"*80)
    results_3 = analyze_worst_performer_hypothesis(symbols, bottom_n=3)
    
    # Summary comparison
    print("\n" + "="*80)
    print("SUMMARY COMPARISON")
    print("="*80)
    for name, results in [("Bottom 5", results_5), ("Bottom 10", results_10), ("Bottom 3", results_3)]:
        if results and 'summary' in results:
            s = results['summary']
            print(f"\n{name}:")
            print(f"  Hit Rate (negative next day): {s['hit_rate']:.1f}%")
            print(f"  Avg Day T+1 Return: {s['avg_day_t1_return']:.2f}%")
            print(f"  P-value: {s['p_value']:.4f}")


if __name__ == "__main__":
    main()
