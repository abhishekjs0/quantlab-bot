"""
Hypothesis Analysis: Candlestick Pattern Predictive Power

Analysis: For each trading day, detect candlestick patterns using TA-Lib
and measure if the pattern correctly predicts the next day's direction.

Patterns analyzed:
- Bullish: Hammer, Inverted Hammer, Bullish Engulfing, Morning Star, 
  Three White Soldiers, Piercing, Dragonfly Doji
- Bearish: Hanging Man, Shooting Star, Bearish Engulfing, Evening Star,
  Three Black Crows, Dark Cloud Cover, Gravestone Doji
- Neutral: Doji, Spinning Top
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

# TA-Lib for candlestick patterns
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("WARNING: TA-Lib not available. Please install with: pip install TA-Lib")


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


def detect_talib_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect candlestick patterns using TA-Lib.
    Returns dataframe with pattern columns (values are -100, 0, or 100).
    """
    if not TALIB_AVAILABLE:
        raise ImportError("TA-Lib is required for pattern detection")
    
    df = df.copy()
    
    open_arr = df['Open'].values.astype(float)
    high_arr = df['High'].values.astype(float)
    low_arr = df['Low'].values.astype(float)
    close_arr = df['Close'].values.astype(float)
    
    # Calculate daily return
    df['return_pct'] = df['Close'].pct_change() * 100
    df['next_return'] = df['return_pct'].shift(-1)
    df['next_positive'] = df['next_return'] > 0
    df['next_negative'] = df['next_return'] < 0
    
    # ========== BULLISH PATTERNS ==========
    df['CDL_HAMMER'] = talib.CDLHAMMER(open_arr, high_arr, low_arr, close_arr)
    df['CDL_INVERTEDHAMMER'] = talib.CDLINVERTEDHAMMER(open_arr, high_arr, low_arr, close_arr)
    df['CDL_ENGULFING_BULL'] = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
    df['CDL_MORNINGSTAR'] = talib.CDLMORNINGSTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_3WHITESOLDIERS'] = talib.CDL3WHITESOLDIERS(open_arr, high_arr, low_arr, close_arr)
    df['CDL_PIERCING'] = talib.CDLPIERCING(open_arr, high_arr, low_arr, close_arr)
    df['CDL_DRAGONFLYDOJI'] = talib.CDLDRAGONFLYDOJI(open_arr, high_arr, low_arr, close_arr)
    df['CDL_MORNINGDOJISTAR'] = talib.CDLMORNINGDOJISTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_ABANDONEDBABY_BULL'] = np.where(talib.CDLABANDONEDBABY(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
    df['CDL_HARAMI_BULL'] = np.where(talib.CDLHARAMI(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
    df['CDL_HARAMICROSS_BULL'] = np.where(talib.CDLHARAMICROSS(open_arr, high_arr, low_arr, close_arr) > 0, 100, 0)
    df['CDL_HOMINGPIGEON'] = talib.CDLHOMINGPIGEON(open_arr, high_arr, low_arr, close_arr)
    df['CDL_MATCHINGLOW'] = talib.CDLMATCHINGLOW(open_arr, high_arr, low_arr, close_arr)
    df['CDL_STICKSANDWICH'] = talib.CDLSTICKSANDWICH(open_arr, high_arr, low_arr, close_arr)
    df['CDL_TAKURI'] = talib.CDLTAKURI(open_arr, high_arr, low_arr, close_arr)
    
    # ========== BEARISH PATTERNS ==========
    df['CDL_HANGINGMAN'] = talib.CDLHANGINGMAN(open_arr, high_arr, low_arr, close_arr)
    df['CDL_SHOOTINGSTAR'] = talib.CDLSHOOTINGSTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_ENGULFING_BEAR'] = np.where(talib.CDLENGULFING(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    df['CDL_EVENINGSTAR'] = talib.CDLEVENINGSTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_3BLACKCROWS'] = talib.CDL3BLACKCROWS(open_arr, high_arr, low_arr, close_arr)
    df['CDL_DARKCLOUDCOVER'] = talib.CDLDARKCLOUDCOVER(open_arr, high_arr, low_arr, close_arr)
    df['CDL_GRAVESTONEDOJI'] = talib.CDLGRAVESTONEDOJI(open_arr, high_arr, low_arr, close_arr)
    df['CDL_EVENINGDOJISTAR'] = talib.CDLEVENINGDOJISTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_ABANDONEDBABY_BEAR'] = np.where(talib.CDLABANDONEDBABY(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    df['CDL_HARAMI_BEAR'] = np.where(talib.CDLHARAMI(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    df['CDL_HARAMICROSS_BEAR'] = np.where(talib.CDLHARAMICROSS(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    df['CDL_ADVANCEBLOCK'] = talib.CDLADVANCEBLOCK(open_arr, high_arr, low_arr, close_arr)
    df['CDL_BELTHOLD_BEAR'] = np.where(talib.CDLBELTHOLD(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    df['CDL_COUNTERATTACK_BEAR'] = np.where(talib.CDLCOUNTERATTACK(open_arr, high_arr, low_arr, close_arr) < 0, -100, 0)
    
    # ========== NEUTRAL/CONTINUATION PATTERNS ==========
    df['CDL_DOJI'] = talib.CDLDOJI(open_arr, high_arr, low_arr, close_arr)
    df['CDL_DOJISTAR'] = talib.CDLDOJISTAR(open_arr, high_arr, low_arr, close_arr)
    df['CDL_LONGLEGGEDDOJI'] = talib.CDLLONGLEGGEDDOJI(open_arr, high_arr, low_arr, close_arr)
    df['CDL_SPINNINGTOP'] = talib.CDLSPINNINGTOP(open_arr, high_arr, low_arr, close_arr)
    df['CDL_HIGHWAVE'] = talib.CDLHIGHWAVE(open_arr, high_arr, low_arr, close_arr)
    df['CDL_MARUBOZU'] = talib.CDLMARUBOZU(open_arr, high_arr, low_arr, close_arr)
    df['CDL_LONGLINE'] = talib.CDLLONGLINE(open_arr, high_arr, low_arr, close_arr)
    df['CDL_SHORTLINE'] = talib.CDLSHORTLINE(open_arr, high_arr, low_arr, close_arr)
    
    return df


def analyze_pattern_predictive_power(
    symbols: list[str],
    min_date: Optional[str] = None,
    max_date: Optional[str] = None,
) -> dict:
    """
    Analyze predictive power of each candlestick pattern.
    """
    if not TALIB_AVAILABLE:
        print("ERROR: TA-Lib required. Install with: pip install TA-Lib")
        return {}
    
    print(f"Loading data for {len(symbols)} symbols...")
    
    # Load all data with patterns
    all_results = []
    
    for sym in symbols:
        df = load_symbol_data(sym)
        if df is None or len(df) < 50:
            continue
        
        try:
            df = detect_talib_patterns(df)
            df['symbol'] = sym
            all_results.append(df)
        except Exception as e:
            continue
    
    if not all_results:
        print("No data loaded!")
        return {}
    
    combined_df = pd.concat(all_results, ignore_index=False)
    
    # Apply date filters
    if min_date:
        combined_df = combined_df[combined_df.index >= min_date]
    if max_date:
        combined_df = combined_df[combined_df.index <= max_date]
    
    # Remove rows without next day data
    combined_df = combined_df.dropna(subset=['next_return'])
    
    print(f"Loaded {len(symbols)} symbols, {len(combined_df)} total trading days")
    
    # Define pattern groups
    bullish_patterns = [
        ('CDL_HAMMER', 'Hammer'),
        ('CDL_INVERTEDHAMMER', 'Inverted Hammer'),
        ('CDL_ENGULFING_BULL', 'Bullish Engulfing'),
        ('CDL_MORNINGSTAR', 'Morning Star'),
        ('CDL_3WHITESOLDIERS', 'Three White Soldiers'),
        ('CDL_PIERCING', 'Piercing Line'),
        ('CDL_DRAGONFLYDOJI', 'Dragonfly Doji'),
        ('CDL_MORNINGDOJISTAR', 'Morning Doji Star'),
        ('CDL_ABANDONEDBABY_BULL', 'Abandoned Baby (Bull)'),
        ('CDL_HARAMI_BULL', 'Bullish Harami'),
        ('CDL_HARAMICROSS_BULL', 'Bullish Harami Cross'),
        ('CDL_HOMINGPIGEON', 'Homing Pigeon'),
        ('CDL_MATCHINGLOW', 'Matching Low'),
        ('CDL_STICKSANDWICH', 'Stick Sandwich'),
        ('CDL_TAKURI', 'Takuri (Dragonfly w/ long shadow)'),
    ]
    
    bearish_patterns = [
        ('CDL_HANGINGMAN', 'Hanging Man'),
        ('CDL_SHOOTINGSTAR', 'Shooting Star'),
        ('CDL_ENGULFING_BEAR', 'Bearish Engulfing'),
        ('CDL_EVENINGSTAR', 'Evening Star'),
        ('CDL_3BLACKCROWS', 'Three Black Crows'),
        ('CDL_DARKCLOUDCOVER', 'Dark Cloud Cover'),
        ('CDL_GRAVESTONEDOJI', 'Gravestone Doji'),
        ('CDL_EVENINGDOJISTAR', 'Evening Doji Star'),
        ('CDL_ABANDONEDBABY_BEAR', 'Abandoned Baby (Bear)'),
        ('CDL_HARAMI_BEAR', 'Bearish Harami'),
        ('CDL_HARAMICROSS_BEAR', 'Bearish Harami Cross'),
        ('CDL_ADVANCEBLOCK', 'Advance Block'),
        ('CDL_BELTHOLD_BEAR', 'Belt Hold (Bear)'),
        ('CDL_COUNTERATTACK_BEAR', 'Counterattack (Bear)'),
    ]
    
    neutral_patterns = [
        ('CDL_DOJI', 'Doji'),
        ('CDL_DOJISTAR', 'Doji Star'),
        ('CDL_LONGLEGGEDDOJI', 'Long-Legged Doji'),
        ('CDL_SPINNINGTOP', 'Spinning Top'),
        ('CDL_HIGHWAVE', 'High Wave'),
        ('CDL_MARUBOZU', 'Marubozu'),
        ('CDL_LONGLINE', 'Long Line'),
        ('CDL_SHORTLINE', 'Short Line'),
    ]
    
    # ========== ANALYSIS ==========
    
    print("\n" + "="*100)
    print("CANDLESTICK PATTERN PREDICTIVE POWER ANALYSIS (TA-Lib)")
    print("="*100)
    
    # Baseline stats
    baseline_positive_rate = combined_df['next_positive'].mean() * 100
    baseline_avg_return = combined_df['next_return'].mean()
    print(f"\n📊 BASELINE (Random day → Next day):")
    print(f"   Positive next day: {baseline_positive_rate:.1f}%")
    print(f"   Average next day return: {baseline_avg_return:.3f}%")
    
    # Analyze each pattern group
    results_list = []
    
    def analyze_pattern_group(patterns, group_name, expected_direction):
        print(f"\n" + "-"*100)
        print(f"{'🟢' if expected_direction == 'up' else '🔴' if expected_direction == 'down' else '⚪'} {group_name}")
        print("-"*100)
        
        if expected_direction == 'up':
            print(f"\n{'Pattern':<30} {'Count':>8} {'Next +':>10} {'Avg Ret':>10} {'vs Base':>10} {'Accuracy':>10}")
        else:
            print(f"\n{'Pattern':<30} {'Count':>8} {'Next -':>10} {'Avg Ret':>10} {'vs Base':>10} {'Accuracy':>10}")
        print("-"*90)
        
        for col, name in patterns:
            if col not in combined_df.columns:
                continue
            
            # Filter where pattern occurred (non-zero)
            if expected_direction in ['up', 'neutral']:
                subset = combined_df[combined_df[col] > 0]
            else:
                subset = combined_df[combined_df[col] < 0] if combined_df[col].min() < 0 else combined_df[combined_df[col] != 0]
            
            if len(subset) < 20:  # Min sample size
                continue
            
            count = len(subset)
            avg_return = subset['next_return'].mean()
            
            if expected_direction == 'up':
                hit_rate = subset['next_positive'].mean() * 100
                accuracy = hit_rate
                vs_base = hit_rate - baseline_positive_rate
            elif expected_direction == 'down':
                hit_rate = subset['next_negative'].mean() * 100
                accuracy = hit_rate
                vs_base = hit_rate - (100 - baseline_positive_rate)
            else:
                hit_rate = subset['next_positive'].mean() * 100
                accuracy = max(hit_rate, 100 - hit_rate)  # Direction doesn't matter
                vs_base = 0
            
            # Emoji based on performance
            if expected_direction == 'up':
                emoji = "✅" if hit_rate > 55 else "⚠️" if hit_rate > 50 else "❌"
            elif expected_direction == 'down':
                emoji = "✅" if hit_rate > 55 else "⚠️" if hit_rate > 50 else "❌"
            else:
                emoji = "➖"
            
            print(f"{emoji} {name:<28} {count:>8} {hit_rate:>9.1f}% {avg_return:>+9.3f}% {vs_base:>+9.1f}% {accuracy:>9.1f}%")
            
            results_list.append({
                'pattern': name,
                'column': col,
                'group': group_name,
                'expected': expected_direction,
                'count': count,
                'hit_rate': hit_rate,
                'avg_return': avg_return,
                'vs_baseline': vs_base,
                'accuracy': accuracy
            })
    
    analyze_pattern_group(bullish_patterns, "BULLISH PATTERNS (Expect: Next day UP)", "up")
    analyze_pattern_group(bearish_patterns, "BEARISH PATTERNS (Expect: Next day DOWN)", "down")
    analyze_pattern_group(neutral_patterns, "NEUTRAL/INDECISION PATTERNS", "neutral")
    
    results_df = pd.DataFrame(results_list)
    
    if len(results_df) == 0:
        print("\nNo patterns detected with sufficient sample size!")
        return {}
    
    # ========== SUMMARY ==========
    
    print("\n" + "="*100)
    print("📈 TOP PERFORMING BULLISH PATTERNS (Highest next-day positive rate)")
    print("="*100)
    
    bullish_results = results_df[results_df['expected'] == 'up'].sort_values('hit_rate', ascending=False)
    for _, row in bullish_results.head(10).iterrows():
        emoji = "🏆" if row['hit_rate'] > 55 else "⭐" if row['hit_rate'] > 52 else "📊"
        print(f"{emoji} {row['pattern']:<30}: {row['hit_rate']:.1f}% positive next day (n={row['count']}, avg={row['avg_return']:+.3f}%)")
    
    print("\n" + "="*100)
    print("📉 TOP PERFORMING BEARISH PATTERNS (Highest next-day negative rate)")
    print("="*100)
    
    bearish_results = results_df[results_df['expected'] == 'down'].sort_values('hit_rate', ascending=False)
    for _, row in bearish_results.head(10).iterrows():
        emoji = "🏆" if row['hit_rate'] > 55 else "⭐" if row['hit_rate'] > 52 else "📊"
        print(f"{emoji} {row['pattern']:<30}: {row['hit_rate']:.1f}% negative next day (n={row['count']}, avg={row['avg_return']:+.3f}%)")
    
    # Statistical significance
    print("\n" + "="*100)
    print("📊 STATISTICAL SIGNIFICANCE TEST (Chi-square vs baseline)")
    print("="*100)
    
    from scipy import stats
    
    significant_patterns = []
    
    for _, row in results_df.iterrows():
        if row['count'] >= 50:
            if row['expected'] == 'up':
                expected_rate = baseline_positive_rate / 100
            elif row['expected'] == 'down':
                expected_rate = (100 - baseline_positive_rate) / 100
            else:
                continue
            
            observed = row['count'] * (row['hit_rate'] / 100)
            expected = row['count'] * expected_rate
            
            # Chi-square test
            chi2 = ((observed - expected) ** 2) / expected
            chi2 += ((row['count'] - observed - (row['count'] - expected)) ** 2) / (row['count'] - expected)
            p_value = 1 - stats.chi2.cdf(chi2, df=1)
            
            if p_value < 0.05:
                direction = "BETTER" if row['hit_rate'] > (expected_rate * 100) else "WORSE"
                significant_patterns.append({
                    'pattern': row['pattern'],
                    'hit_rate': row['hit_rate'],
                    'baseline': expected_rate * 100,
                    'p_value': p_value,
                    'direction': direction,
                    'count': row['count']
                })
                print(f"✓ {row['pattern']:<30}: p={p_value:.4f} ({direction} than baseline)")
    
    if not significant_patterns:
        print("No patterns showed statistically significant difference from baseline at p<0.05")
    
    # Trading recommendations
    print("\n" + "="*100)
    print("💡 TRADING RECOMMENDATIONS")
    print("="*100)
    
    reliable_bullish = bullish_results[bullish_results['hit_rate'] >= 52]
    reliable_bearish = bearish_results[bearish_results['hit_rate'] >= 52]
    
    print("\n🟢 RELIABLE BULLISH SIGNALS (>52% next-day positive):")
    if len(reliable_bullish) > 0:
        for _, row in reliable_bullish.head(5).iterrows():
            print(f"   - {row['pattern']}: {row['hit_rate']:.1f}% accuracy, avg +{row['avg_return']:.3f}%")
    else:
        print("   - No reliable bullish patterns found")
    
    print("\n🔴 RELIABLE BEARISH SIGNALS (>52% next-day negative):")
    if len(reliable_bearish) > 0:
        for _, row in reliable_bearish.head(5).iterrows():
            print(f"   - {row['pattern']}: {row['hit_rate']:.1f}% accuracy, avg {row['avg_return']:+.3f}%")
    else:
        print("   - No reliable bearish patterns found")
    
    print("\n⚠️ PATTERNS TO AVOID (Poor predictive power):")
    poor_patterns = results_df[(results_df['accuracy'] < 48) & (results_df['count'] >= 50)]
    if len(poor_patterns) > 0:
        for _, row in poor_patterns.iterrows():
            print(f"   - {row['pattern']}: Only {row['accuracy']:.1f}% accuracy (worse than random)")
    else:
        print("   - All patterns perform at or above random baseline")
    
    return {
        'results_df': results_df,
        'combined_df': combined_df,
        'baseline_positive_rate': baseline_positive_rate,
        'baseline_avg_return': baseline_avg_return,
        'significant_patterns': significant_patterns
    }


def main():
    """Run the TA-Lib pattern analysis."""
    symbols = load_basket_symbols("basket_large.txt")
    print(f"Loaded {len(symbols)} symbols from basket_large.txt")
    
    if not TALIB_AVAILABLE:
        print("\n❌ ERROR: TA-Lib is required for this analysis.")
        print("Install with: pip install TA-Lib")
        print("Note: You may need to install the underlying C library first.")
        return
    
    results = analyze_pattern_predictive_power(symbols)
    
    if results and 'results_df' in results:
        # Additional analysis by market regime
        print("\n" + "="*100)
        print("📊 ADDITIONAL: PATTERN PERFORMANCE BY DAY OF WEEK")
        print("="*100)
        
        df = results['combined_df']
        df['day_of_week'] = df.index.dayofweek
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        # Check Hammer pattern by day of week
        for col, name in [('CDL_HAMMER', 'Hammer'), ('CDL_ENGULFING_BULL', 'Bullish Engulfing')]:
            if col in df.columns:
                print(f"\n{name} by Day of Week:")
                for day_num, day_name in enumerate(day_names):
                    subset = df[(df[col] > 0) & (df['day_of_week'] == day_num)]
                    if len(subset) >= 10:
                        hr = subset['next_positive'].mean() * 100
                        print(f"   {day_name}: {hr:.1f}% (n={len(subset)})")


if __name__ == "__main__":
    main()
