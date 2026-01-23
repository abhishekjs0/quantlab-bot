"""
Hypothesis Analysis: Worst Day Performers + Candlestick Patterns

Extended analysis that combines:
1. Worst performers by % drop
2. Candlestick patterns on the drop day
3. Next day performance prediction

Candlestick patterns analyzed:
- Bearish Engulfing, Bearish Marubozu, Shooting Star, Hanging Man
- Doji patterns, Long lower shadow (hammer-like)
- Gap down patterns
"""

import os
import sys
import glob
from pathlib import Path
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
import warnings
warnings.filterwarnings('ignore')

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
    
    pattern = os.path.join(cache_dir, f"dhan_*_{symbol}_1d.csv")
    matches = glob.glob(pattern)
    
    if not matches:
        return None
    
    df = pd.read_csv(matches[0])
    
    if 'start_time' in df.columns:
        df['Date'] = pd.to_datetime(df['start_time'])
    elif 'datetime' in df.columns:
        df['Date'] = pd.to_datetime(df['datetime'])
    elif 'date' in df.columns:
        df['Date'] = pd.to_datetime(df['date'])
    else:
        df['Date'] = pd.to_datetime(df.iloc[:, 0])
    
    df = df.set_index('Date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
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


# ============================================================================
# CANDLESTICK PATTERN DETECTION
# ============================================================================

def detect_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect various candlestick patterns and add pattern columns to dataframe.
    Returns dataframe with pattern detection columns.
    """
    df = df.copy()
    
    # Basic candlestick components
    df['body'] = df['Close'] - df['Open']
    df['body_abs'] = abs(df['body'])
    df['upper_shadow'] = df['High'] - df[['Open', 'Close']].max(axis=1)
    df['lower_shadow'] = df[['Open', 'Close']].min(axis=1) - df['Low']
    df['range'] = df['High'] - df['Low']
    df['is_bearish'] = df['Close'] < df['Open']
    df['is_bullish'] = df['Close'] > df['Open']
    
    # Previous day values
    df['prev_open'] = df['Open'].shift(1)
    df['prev_close'] = df['Close'].shift(1)
    df['prev_high'] = df['High'].shift(1)
    df['prev_low'] = df['Low'].shift(1)
    df['prev_body'] = df['body'].shift(1)
    df['prev_body_abs'] = df['body_abs'].shift(1)
    df['prev_is_bullish'] = df['is_bullish'].shift(1)
    
    # Average body size for relative comparisons
    df['avg_body'] = df['body_abs'].rolling(20).mean()
    df['avg_range'] = df['range'].rolling(20).mean()
    
    # Daily return
    df['return_pct'] = df['Close'].pct_change() * 100
    
    # ---- PATTERN DETECTION ----
    
    # 1. Bearish Marubozu - Large bearish body with minimal shadows
    df['bearish_marubozu'] = (
        df['is_bearish'] & 
        (df['body_abs'] > df['avg_body'] * 1.5) &
        (df['upper_shadow'] < df['body_abs'] * 0.1) &
        (df['lower_shadow'] < df['body_abs'] * 0.1)
    )
    
    # 2. Bearish Engulfing - Bearish candle engulfs previous bullish
    df['bearish_engulfing'] = (
        df['is_bearish'] & 
        df['prev_is_bullish'] &
        (df['Open'] > df['prev_close']) &
        (df['Close'] < df['prev_open']) &
        (df['body_abs'] > df['prev_body_abs'])
    )
    
    # 3. Shooting Star (at potential top) - Small body at top, long upper shadow
    df['shooting_star'] = (
        (df['upper_shadow'] > df['body_abs'] * 2) &
        (df['lower_shadow'] < df['body_abs'] * 0.5) &
        (df['body_abs'] > 0) &
        (df['Close'] < df['prev_close'])  # Down day
    )
    
    # 4. Hanging Man - Small body at top, long lower shadow (bearish signal)
    df['hanging_man'] = (
        (df['lower_shadow'] > df['body_abs'] * 2) &
        (df['upper_shadow'] < df['body_abs'] * 0.5) &
        (df['body_abs'] > 0) &
        (df['is_bearish'])
    )
    
    # 5. Doji - Very small body relative to range
    df['doji'] = (
        (df['body_abs'] < df['range'] * 0.1) &
        (df['range'] > 0)
    )
    
    # 6. Gap Down - Open significantly lower than previous close
    df['gap_down'] = (df['prev_close'] - df['Open']) / df['prev_close'] * 100 > 0.5
    
    # 7. Large Gap Down (>1%)
    df['large_gap_down'] = (df['prev_close'] - df['Open']) / df['prev_close'] * 100 > 1.0
    
    # 8. Filled Gap Down - Gap down but recovered during day (close > open)
    df['filled_gap_down'] = df['gap_down'] & df['is_bullish']
    
    # 9. Unfilled Gap Down - Gap down and continued selling
    df['unfilled_gap_down'] = df['gap_down'] & df['is_bearish']
    
    # 10. Hammer (potential reversal) - Long lower shadow, small body at top
    df['hammer'] = (
        (df['lower_shadow'] > df['body_abs'] * 2) &
        (df['upper_shadow'] < df['body_abs'] * 0.5) &
        (df['body_abs'] > 0) &
        (df['is_bullish'])  # Bullish variant
    )
    
    # 11. Long Red Candle - Significant bearish candle
    df['long_red_candle'] = (
        df['is_bearish'] & 
        (df['body_abs'] > df['avg_body'] * 1.5)
    )
    
    # 12. Very Long Red Candle (extreme)
    df['very_long_red'] = (
        df['is_bearish'] & 
        (df['body_abs'] > df['avg_body'] * 2.5)
    )
    
    # 13. Lower Close - Closed near the low of the day
    df['lower_close'] = (df['Close'] - df['Low']) / df['range'].replace(0, np.nan) < 0.2
    
    # 14. Upper Close - Closed near the high (potential recovery sign)
    df['upper_close'] = (df['High'] - df['Close']) / df['range'].replace(0, np.nan) < 0.2
    
    # 15. Dark Cloud Cover - Bearish reversal
    df['dark_cloud'] = (
        df['prev_is_bullish'] &
        df['is_bearish'] &
        (df['Open'] > df['prev_high']) &
        (df['Close'] < (df['prev_open'] + df['prev_close']) / 2) &
        (df['Close'] > df['prev_open'])
    )
    
    # 16. Evening Star setup (simplified) - Gap up then bearish
    df['evening_star'] = (
        df['is_bearish'] &
        (df['Open'] > df['prev_close']) &
        (df['Close'] < df['prev_open'])
    )
    
    return df


def get_pattern_name(row: pd.Series) -> list[str]:
    """Get list of pattern names detected for a row."""
    patterns = []
    pattern_cols = [
        'bearish_marubozu', 'bearish_engulfing', 'shooting_star', 
        'hanging_man', 'doji', 'gap_down', 'large_gap_down',
        'filled_gap_down', 'unfilled_gap_down', 'hammer',
        'long_red_candle', 'very_long_red', 'lower_close', 
        'upper_close', 'dark_cloud', 'evening_star'
    ]
    for col in pattern_cols:
        if col in row and row[col]:
            patterns.append(col)
    return patterns if patterns else ['no_pattern']


def analyze_with_candlestick_patterns(
    symbols: list[str],
    bottom_n: int = 10,
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> dict:
    """
    Analyze worst performers with candlestick pattern breakdown.
    """
    print(f"Loading data for {len(symbols)} symbols...")
    
    # Load all data and detect patterns
    all_data = {}
    for sym in symbols:
        df = load_symbol_data(sym)
        if df is not None and len(df) > 50:
            df = detect_candlestick_patterns(df)
            all_data[sym] = df
    
    print(f"Successfully loaded {len(all_data)} symbols with pattern detection")
    
    if len(all_data) < 10:
        print("Not enough symbols with data. Exiting.")
        return {}
    
    # Build returns dataframe
    returns_dict = {}
    for sym, df in all_data.items():
        returns_dict[sym] = df['return_pct']
    
    returns_df = pd.DataFrame(returns_dict)
    returns_df = returns_df.dropna(thresh=len(all_data) * 0.5)
    
    if min_date:
        returns_df = returns_df[returns_df.index >= min_date]
    if max_date:
        returns_df = returns_df[returns_df.index <= max_date]
    
    print(f"Analyzing {len(returns_df)} trading days from {returns_df.index[0].date()} to {returns_df.index[-1].date()}")
    
    # Track results with pattern info
    results = []
    
    for i in range(len(returns_df) - 1):
        current_date = returns_df.index[i]
        next_date = returns_df.index[i + 1]
        
        current_returns = returns_df.iloc[i].dropna()
        
        if len(current_returns) < bottom_n + 5:
            continue
        
        # Identify worst performers
        worst_performers = current_returns.nsmallest(bottom_n)
        next_day_returns = returns_df.iloc[i + 1]
        
        for sym in worst_performers.index:
            if sym not in all_data or current_date not in all_data[sym].index:
                continue
            if sym not in next_day_returns or pd.isna(next_day_returns[sym]):
                continue
                
            # Get pattern info for this candle
            row = all_data[sym].loc[current_date]
            patterns = get_pattern_name(row)
            
            result = {
                'date': current_date,
                'next_date': next_date,
                'symbol': sym,
                'day_t_return': worst_performers[sym],
                'day_t1_return': next_day_returns[sym],
                'was_negative_next_day': next_day_returns[sym] < 0,
                'rank': list(worst_performers.index).index(sym) + 1,
                'patterns': ','.join(patterns),
                'pattern_count': len([p for p in patterns if p != 'no_pattern']),
                # Individual pattern flags
                'has_bearish_marubozu': 'bearish_marubozu' in patterns,
                'has_bearish_engulfing': 'bearish_engulfing' in patterns,
                'has_shooting_star': 'shooting_star' in patterns,
                'has_doji': 'doji' in patterns,
                'has_gap_down': 'gap_down' in patterns,
                'has_large_gap_down': 'large_gap_down' in patterns,
                'has_hammer': 'hammer' in patterns,
                'has_long_red_candle': 'long_red_candle' in patterns,
                'has_very_long_red': 'very_long_red' in patterns,
                'has_lower_close': 'lower_close' in patterns,
                'has_upper_close': 'upper_close' in patterns,
                'has_filled_gap_down': 'filled_gap_down' in patterns,
                'has_unfilled_gap_down': 'unfilled_gap_down' in patterns,
            }
            results.append(result)
    
    results_df = pd.DataFrame(results)
    
    if len(results_df) == 0:
        print("No results found!")
        return {}
    
    # ============================================================================
    # ANALYSIS OUTPUT
    # ============================================================================
    
    print("\n" + "="*90)
    print("CANDLESTICK PATTERN ANALYSIS: WORST PERFORMERS")
    print("="*90)
    
    total_obs = len(results_df)
    baseline_hit_rate = results_df['was_negative_next_day'].mean() * 100
    baseline_avg_return = results_df['day_t1_return'].mean()
    
    print(f"\n📊 BASELINE (All worst performers, n={total_obs}):")
    print(f"   Negative next day rate: {baseline_hit_rate:.1f}%")
    print(f"   Average next day return: {baseline_avg_return:.3f}%")
    
    # Pattern-by-pattern analysis
    print("\n" + "-"*90)
    print("📈 PATTERN-BY-PATTERN BREAKDOWN")
    print("-"*90)
    
    pattern_columns = [
        ('has_bearish_marubozu', 'Bearish Marubozu'),
        ('has_bearish_engulfing', 'Bearish Engulfing'),
        ('has_shooting_star', 'Shooting Star'),
        ('has_doji', 'Doji'),
        ('has_gap_down', 'Gap Down'),
        ('has_large_gap_down', 'Large Gap Down (>1%)'),
        ('has_hammer', 'Hammer'),
        ('has_long_red_candle', 'Long Red Candle'),
        ('has_very_long_red', 'Very Long Red Candle'),
        ('has_lower_close', 'Closed Near Low'),
        ('has_upper_close', 'Closed Near High'),
        ('has_filled_gap_down', 'Filled Gap Down'),
        ('has_unfilled_gap_down', 'Unfilled Gap Down'),
    ]
    
    pattern_stats = []
    
    print(f"\n{'Pattern':<25} {'Count':>8} {'Hit Rate':>12} {'Avg T+1':>12} {'vs Base':>10}")
    print("-"*70)
    
    for col, name in pattern_columns:
        subset = results_df[results_df[col]]
        if len(subset) >= 30:  # Minimum sample size
            hit_rate = subset['was_negative_next_day'].mean() * 100
            avg_return = subset['day_t1_return'].mean()
            diff_vs_base = hit_rate - baseline_hit_rate
            
            # Emoji indicator
            if hit_rate > 55:
                indicator = "🔴"  # Strong bearish continuation
            elif hit_rate < 45:
                indicator = "🟢"  # Mean reversion
            else:
                indicator = "⚪"  # Neutral
            
            print(f"{indicator} {name:<23} {len(subset):>8} {hit_rate:>11.1f}% {avg_return:>11.3f}% {diff_vs_base:>+9.1f}%")
            
            pattern_stats.append({
                'pattern': name,
                'count': len(subset),
                'hit_rate': hit_rate,
                'avg_t1_return': avg_return,
                'diff_vs_baseline': diff_vs_base
            })
    
    pattern_stats_df = pd.DataFrame(pattern_stats)
    
    # Find best and worst patterns
    if len(pattern_stats_df) > 0:
        print("\n" + "-"*90)
        print("🏆 TOP PATTERNS FOR PREDICTING CONTINUED DECLINE (Highest hit rate)")
        print("-"*90)
        top_bearish = pattern_stats_df.nlargest(5, 'hit_rate')
        for _, row in top_bearish.iterrows():
            print(f"   {row['pattern']}: {row['hit_rate']:.1f}% negative next day (n={row['count']})")
        
        print("\n" + "-"*90)
        print("📈 TOP PATTERNS FOR MEAN REVERSION (Lowest hit rate / highest bounce)")
        print("-"*90)
        top_reversal = pattern_stats_df.nsmallest(5, 'hit_rate')
        for _, row in top_reversal.iterrows():
            print(f"   {row['pattern']}: {row['hit_rate']:.1f}% negative next day, avg +{row['avg_t1_return']:.3f}% (n={row['count']})")
    
    # Combination patterns analysis
    print("\n" + "-"*90)
    print("🔗 PATTERN COMBINATIONS")
    print("-"*90)
    
    # No pattern vs has pattern
    no_pattern = results_df[results_df['pattern_count'] == 0]
    has_pattern = results_df[results_df['pattern_count'] > 0]
    multi_pattern = results_df[results_df['pattern_count'] >= 2]
    
    print(f"\n{'Category':<30} {'Count':>8} {'Hit Rate':>12} {'Avg T+1':>12}")
    print("-"*65)
    if len(no_pattern) > 0:
        print(f"{'No clear pattern':<30} {len(no_pattern):>8} {no_pattern['was_negative_next_day'].mean()*100:>11.1f}% {no_pattern['day_t1_return'].mean():>11.3f}%")
    if len(has_pattern) > 0:
        print(f"{'Has pattern(s)':<30} {len(has_pattern):>8} {has_pattern['was_negative_next_day'].mean()*100:>11.1f}% {has_pattern['day_t1_return'].mean():>11.3f}%")
    if len(multi_pattern) > 0:
        print(f"{'Multiple patterns (2+)':<30} {len(multi_pattern):>8} {multi_pattern['was_negative_next_day'].mean()*100:>11.1f}% {multi_pattern['day_t1_return'].mean():>11.3f}%")
    
    # Gap down + other patterns
    gap_and_red = results_df[results_df['has_gap_down'] & results_df['has_long_red_candle']]
    gap_and_lower = results_df[results_df['has_gap_down'] & results_df['has_lower_close']]
    gap_and_upper = results_df[results_df['has_gap_down'] & results_df['has_upper_close']]
    
    print(f"\n{'Combination':<30} {'Count':>8} {'Hit Rate':>12} {'Avg T+1':>12}")
    print("-"*65)
    if len(gap_and_red) >= 20:
        print(f"{'Gap Down + Long Red':<30} {len(gap_and_red):>8} {gap_and_red['was_negative_next_day'].mean()*100:>11.1f}% {gap_and_red['day_t1_return'].mean():>11.3f}%")
    if len(gap_and_lower) >= 20:
        print(f"{'Gap Down + Closed Near Low':<30} {len(gap_and_lower):>8} {gap_and_lower['was_negative_next_day'].mean()*100:>11.1f}% {gap_and_lower['day_t1_return'].mean():>11.3f}%")
    if len(gap_and_upper) >= 20:
        print(f"{'Gap Down + Closed Near High':<30} {len(gap_and_upper):>8} {gap_and_upper['was_negative_next_day'].mean()*100:>11.1f}% {gap_and_upper['day_t1_return'].mean():>11.3f}%")
    
    # Statistical significance for top patterns
    print("\n" + "-"*90)
    print("📊 STATISTICAL SIGNIFICANCE (vs baseline)")
    print("-"*90)
    
    from scipy import stats
    
    for col, name in pattern_columns:
        subset = results_df[results_df[col]]
        if len(subset) >= 50:
            # Chi-square test vs baseline
            observed = subset['was_negative_next_day'].sum()
            expected = len(subset) * (baseline_hit_rate / 100)
            if expected > 0:
                chi2 = ((observed - expected) ** 2) / expected + ((len(subset) - observed - (len(subset) - expected)) ** 2) / (len(subset) - expected) if len(subset) > expected else 0
                p_value = 1 - stats.chi2.cdf(chi2, df=1) if chi2 > 0 else 1.0
                
                hit_rate = subset['was_negative_next_day'].mean() * 100
                sig = "✓ Significant" if p_value < 0.05 else "  Not significant"
                
                if p_value < 0.05:
                    direction = "MORE" if hit_rate > baseline_hit_rate else "LESS"
                    print(f"{sig} (p={p_value:.4f}): {name} → {direction} likely to drop ({hit_rate:.1f}% vs {baseline_hit_rate:.1f}%)")
    
    # Summary and trading insights
    print("\n" + "="*90)
    print("💡 TRADING INSIGHTS")
    print("="*90)
    
    print("\n🔴 BEARISH CONTINUATION signals (short candidates):")
    bearish_patterns = pattern_stats_df[pattern_stats_df['hit_rate'] > 52].sort_values('hit_rate', ascending=False)
    for _, row in bearish_patterns.head(3).iterrows():
        print(f"   - {row['pattern']}: {row['hit_rate']:.1f}% continue down")
    
    print("\n🟢 MEAN REVERSION signals (bounce candidates):")
    reversal_patterns = pattern_stats_df[pattern_stats_df['hit_rate'] < 48].sort_values('hit_rate')
    for _, row in reversal_patterns.head(3).iterrows():
        print(f"   - {row['pattern']}: Only {row['hit_rate']:.1f}% continue down, avg bounce +{row['avg_t1_return']:.2f}%")
    
    return {
        'results_df': results_df,
        'pattern_stats_df': pattern_stats_df,
        'baseline_hit_rate': baseline_hit_rate,
        'baseline_avg_return': baseline_avg_return
    }


def main():
    """Run the candlestick pattern analysis."""
    symbols = load_basket_symbols("basket_large.txt")
    print(f"Loaded {len(symbols)} symbols from basket_large.txt")
    
    print("\n" + "#"*90)
    print("# CANDLESTICK PATTERN ANALYSIS: BOTTOM 10 WORST PERFORMERS")
    print("#"*90)
    
    results = analyze_with_candlestick_patterns(symbols, bottom_n=10)
    
    if results and 'results_df' in results:
        # Additional deep dive: by severity quartile + pattern
        print("\n" + "="*90)
        print("📉 DEEP DIVE: PATTERN EFFECTIVENESS BY DROP SEVERITY")
        print("="*90)
        
        df = results['results_df']
        df['severity'] = pd.qcut(df['day_t_return'], q=4, labels=['Extreme', 'Severe', 'Moderate', 'Mild'])
        
        print(f"\n{'Severity':<12} {'Pattern':<25} {'Count':>8} {'Hit Rate':>12} {'Avg T+1':>12}")
        print("-"*75)
        
        for severity in ['Extreme', 'Severe']:
            sev_df = df[df['severity'] == severity]
            
            # Check key patterns
            for col, name in [('has_unfilled_gap_down', 'Unfilled Gap Down'), 
                              ('has_lower_close', 'Closed Near Low'),
                              ('has_upper_close', 'Closed Near High'),
                              ('has_hammer', 'Hammer')]:
                subset = sev_df[sev_df[col]]
                if len(subset) >= 20:
                    hr = subset['was_negative_next_day'].mean() * 100
                    avg = subset['day_t1_return'].mean()
                    print(f"{severity:<12} {name:<25} {len(subset):>8} {hr:>11.1f}% {avg:>11.3f}%")


if __name__ == "__main__":
    main()
