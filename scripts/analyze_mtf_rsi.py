"""
Multi-Timeframe RSI Analysis

Hypothesis: When BOTH weekly RSI > 80 AND daily RSI > 80, 
what happens on the next trading day?

This tests confluence of overbought conditions across timeframes.
"""

import os
import sys
import glob
import pandas as pd
import numpy as np
import talib
from pathlib import Path
from scipy import stats

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import DATA_DIR


def load_symbol_data(symbol: str) -> pd.DataFrame | None:
    """Load daily OHLC data for a symbol."""
    cache_dir = os.path.join(DATA_DIR, 'cache', 'dhan', 'daily')
    pattern = os.path.join(cache_dir, f'dhan_*_{symbol}_1d.csv')
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
    
    if 'Close' not in df.columns:
        return None
    
    return df


def calculate_weekly_data(df: pd.DataFrame) -> pd.DataFrame:
    """Resample daily data to weekly OHLC."""
    weekly = df.resample('W').agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
    }).dropna()
    return weekly


def main():
    # Load symbols
    basket_path = os.path.join(DATA_DIR, 'baskets', 'basket_large.txt')
    with open(basket_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]

    print(f'Multi-Timeframe RSI Analysis for {len(symbols)} symbols...')
    print('='*90)

    all_results = []

    for sym in symbols:
        df = load_symbol_data(sym)
        if df is None or len(df) < 100:
            continue
        
        try:
            # Calculate Daily RSI
            daily_close = df['Close'].values.astype(float)
            daily_rsi = talib.RSI(daily_close, timeperiod=14)
            df['daily_rsi'] = daily_rsi
            
            # Calculate Weekly data and RSI
            weekly = calculate_weekly_data(df)
            if len(weekly) < 20:
                continue
            
            weekly_close = weekly['Close'].values.astype(float)
            weekly_rsi = talib.RSI(weekly_close, timeperiod=14)
            weekly['weekly_rsi'] = weekly_rsi
            
            # Map weekly RSI to daily (use previous week's RSI for each day)
            # Each day gets the RSI from the week that ended before it
            df['week_end'] = df.index.to_period('W').to_timestamp('W')
            weekly['week_end'] = weekly.index
            
            # Shift weekly RSI by 1 to get "previous week's RSI"
            weekly['prev_weekly_rsi'] = weekly['weekly_rsi'].shift(1)
            
            # Merge weekly RSI to daily
            df = df.merge(
                weekly[['week_end', 'prev_weekly_rsi']], 
                on='week_end', 
                how='left'
            )
            
            # Calculate next day return
            df['return_pct'] = df['Close'].pct_change() * 100
            df['next_return'] = df['return_pct'].shift(-1)
            df['next_positive'] = df['next_return'] > 0
            
            # Previous day's daily RSI
            df['prev_daily_rsi'] = df['daily_rsi'].shift(1)
            
            df['symbol'] = sym
            
            # Keep relevant columns
            result_cols = ['symbol', 'prev_daily_rsi', 'prev_weekly_rsi', 
                          'return_pct', 'next_return', 'next_positive']
            all_results.append(df[result_cols].dropna())
            
        except Exception as e:
            continue

    if not all_results:
        print("No data loaded!")
        return

    combined = pd.concat(all_results)
    combined = combined.dropna(subset=['next_return', 'prev_daily_rsi', 'prev_weekly_rsi'])

    print(f'Total observations: {len(combined)}')

    # Baseline
    baseline = combined['next_positive'].mean() * 100
    baseline_ret = combined['next_return'].mean()
    print(f'\n📊 BASELINE: {baseline:.1f}% positive next day, avg {baseline_ret:.3f}%')

    # ========== SINGLE TIMEFRAME ANALYSIS ==========
    print('\n' + '='*90)
    print('SINGLE TIMEFRAME RSI ANALYSIS')
    print('='*90)

    print(f'\n{"Condition":<45} {"Count":>8} {"Next +":>10} {"Avg Ret":>10} {"vs Base":>10}')
    print('-'*90)

    conditions = [
        ('Daily RSI > 80 (prev day)', combined['prev_daily_rsi'] > 80),
        ('Daily RSI > 70 (prev day)', combined['prev_daily_rsi'] > 70),
        ('Weekly RSI > 80 (prev week)', combined['prev_weekly_rsi'] > 80),
        ('Weekly RSI > 70 (prev week)', combined['prev_weekly_rsi'] > 70),
    ]

    for name, mask in conditions:
        subset = combined[mask]
        if len(subset) >= 30:
            hit = subset['next_positive'].mean() * 100
            avg_ret = subset['next_return'].mean()
            vs_base = hit - baseline
            emoji = '🟢' if hit > 55 else '🔴' if hit < 45 else '⚪'
            print(f'{emoji} {name:<43} {len(subset):>8} {hit:>9.1f}% {avg_ret:>+9.3f}% {vs_base:>+9.1f}%')

    # ========== MULTI-TIMEFRAME ANALYSIS ==========
    print('\n' + '='*90)
    print('🔥 MULTI-TIMEFRAME RSI ANALYSIS (Your Hypothesis)')
    print('='*90)

    print(f'\n{"Condition":<50} {"Count":>8} {"Next +":>10} {"Avg Ret":>10} {"vs Base":>10}')
    print('-'*90)

    mtf_conditions = [
        # Core hypothesis
        ('Weekly RSI>80 + Daily RSI>80', 
         (combined['prev_weekly_rsi'] > 80) & (combined['prev_daily_rsi'] > 80)),
        
        ('Weekly RSI>70 + Daily RSI>80', 
         (combined['prev_weekly_rsi'] > 70) & (combined['prev_daily_rsi'] > 80)),
        
        ('Weekly RSI>80 + Daily RSI>70', 
         (combined['prev_weekly_rsi'] > 80) & (combined['prev_daily_rsi'] > 70)),
        
        ('Weekly RSI>70 + Daily RSI>70', 
         (combined['prev_weekly_rsi'] > 70) & (combined['prev_daily_rsi'] > 70)),
        
        # Extreme conditions
        ('Weekly RSI>85 + Daily RSI>85', 
         (combined['prev_weekly_rsi'] > 85) & (combined['prev_daily_rsi'] > 85)),
        
        ('Weekly RSI>90 + Daily RSI>80', 
         (combined['prev_weekly_rsi'] > 90) & (combined['prev_daily_rsi'] > 80)),
        
        # Oversold
        ('Weekly RSI<30 + Daily RSI<30', 
         (combined['prev_weekly_rsi'] < 30) & (combined['prev_daily_rsi'] < 30)),
        
        ('Weekly RSI<20 + Daily RSI<30', 
         (combined['prev_weekly_rsi'] < 20) & (combined['prev_daily_rsi'] < 30)),
    ]

    for name, mask in mtf_conditions:
        subset = combined[mask]
        if len(subset) >= 20:
            hit = subset['next_positive'].mean() * 100
            avg_ret = subset['next_return'].mean()
            vs_base = hit - baseline
            emoji = '🟢' if hit > 55 else '🔴' if hit < 45 else '⚪'
            print(f'{emoji} {name:<48} {len(subset):>8} {hit:>9.1f}% {avg_ret:>+9.3f}% {vs_base:>+9.1f}%')
        else:
            print(f'⚠️ {name:<48} {len(subset):>8} (insufficient data)')

    # ========== DEEP DIVE: Weekly RSI>80 + Daily RSI>80 ==========
    print('\n' + '='*90)
    print('📈 DEEP DIVE: Weekly RSI > 80 + Daily RSI > 80')
    print('='*90)

    mtf_overbought = combined[
        (combined['prev_weekly_rsi'] > 80) & 
        (combined['prev_daily_rsi'] > 80)
    ]

    if len(mtf_overbought) >= 20:
        print(f'\nTotal observations: {len(mtf_overbought)}')
        print(f'Next day positive rate: {mtf_overbought["next_positive"].mean()*100:.1f}%')
        print(f'Average next day return: {mtf_overbought["next_return"].mean():+.3f}%')
        
        # Statistical test
        observed = mtf_overbought['next_positive'].sum()
        expected = len(mtf_overbought) * (baseline/100)
        chi2 = ((observed - expected)**2) / expected
        chi2 += ((len(mtf_overbought) - observed - (len(mtf_overbought) - expected))**2) / (len(mtf_overbought) - expected)
        p_val = 1 - stats.chi2.cdf(chi2, df=1)
        
        print(f'\nStatistical significance: p-value = {p_val:.4f}')
        if p_val < 0.05:
            if mtf_overbought['next_positive'].mean()*100 > baseline:
                print('✓ SIGNIFICANT: Multi-TF overbought leads to MORE bullish days')
            else:
                print('✓ SIGNIFICANT: Multi-TF overbought leads to FEWER bullish days')
        else:
            print('⚡ Not statistically significant at p<0.05')
        
        # Breakdown by current day performance
        mtf_up_day = mtf_overbought[mtf_overbought['return_pct'] > 0]
        mtf_down_day = mtf_overbought[mtf_overbought['return_pct'] < 0]
        
        print('\nBreakdown by current day:')
        if len(mtf_up_day) >= 10:
            print(f'  After UP day: {mtf_up_day["next_positive"].mean()*100:.1f}% next day + (n={len(mtf_up_day)})')
        if len(mtf_down_day) >= 10:
            print(f'  After DOWN day: {mtf_down_day["next_positive"].mean()*100:.1f}% next day + (n={len(mtf_down_day)})')
        
        # Top symbols
        print('\nTop symbols with this condition:')
        symbol_counts = mtf_overbought.groupby('symbol').agg({
            'next_positive': ['count', 'mean'],
            'next_return': 'mean'
        })
        symbol_counts.columns = ['count', 'hit_rate', 'avg_return']
        symbol_counts = symbol_counts[symbol_counts['count'] >= 5].sort_values('count', ascending=False)
        
        for sym, row in symbol_counts.head(10).iterrows():
            print(f'  {sym}: {row["count"]:.0f} occurrences, {row["hit_rate"]*100:.1f}% hit rate, avg {row["avg_return"]:+.2f}%')

    # ========== DIVERGENCE ANALYSIS ==========
    print('\n' + '='*90)
    print('📊 DIVERGENCE: Weekly vs Daily RSI')
    print('='*90)

    divergence_conditions = [
        ('Weekly RSI>70 but Daily RSI<50 (Weekly strong, Daily weak)', 
         (combined['prev_weekly_rsi'] > 70) & (combined['prev_daily_rsi'] < 50)),
        
        ('Weekly RSI<30 but Daily RSI>50 (Weekly weak, Daily strong)', 
         (combined['prev_weekly_rsi'] < 30) & (combined['prev_daily_rsi'] > 50)),
        
        ('Weekly RSI>80 but Daily RSI<60 (Pullback in uptrend)', 
         (combined['prev_weekly_rsi'] > 80) & (combined['prev_daily_rsi'] < 60)),
    ]

    print(f'\n{"Condition":<55} {"Count":>8} {"Next +":>10} {"Avg Ret":>10}')
    print('-'*90)

    for name, mask in divergence_conditions:
        subset = combined[mask]
        if len(subset) >= 30:
            hit = subset['next_positive'].mean() * 100
            avg_ret = subset['next_return'].mean()
            emoji = '🟢' if hit > 55 else '🔴' if hit < 45 else '⚪'
            print(f'{emoji} {name:<53} {len(subset):>8} {hit:>9.1f}% {avg_ret:>+9.3f}%')

    # ========== TRADING IMPLICATIONS ==========
    print('\n' + '='*90)
    print('💡 TRADING IMPLICATIONS')
    print('='*90)

    # Find best and worst conditions
    all_conds = mtf_conditions + divergence_conditions
    results = []
    for name, mask in all_conds:
        subset = combined[mask]
        if len(subset) >= 30:
            results.append({
                'name': name,
                'count': len(subset),
                'hit_rate': subset['next_positive'].mean() * 100,
                'avg_return': subset['next_return'].mean()
            })
    
    if results:
        results_df = pd.DataFrame(results).sort_values('hit_rate', ascending=False)
        
        print('\n🟢 BEST CONDITIONS (Highest next-day bullish rate):')
        for _, row in results_df.head(3).iterrows():
            print(f'   {row["name"]}: {row["hit_rate"]:.1f}% (n={row["count"]}, avg {row["avg_return"]:+.3f}%)')
        
        print('\n🔴 WORST CONDITIONS (Lowest next-day bullish rate):')
        for _, row in results_df.tail(3).iterrows():
            print(f'   {row["name"]}: {row["hit_rate"]:.1f}% (n={row["count"]}, avg {row["avg_return"]:+.3f}%)')


if __name__ == "__main__":
    main()
