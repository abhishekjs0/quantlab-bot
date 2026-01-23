"""
RSI Extreme Analysis: Does RSI > 90 predict next day bullish?

Tests the hypothesis that extremely overbought RSI (>90) leads to 
bullish continuation on the next trading day.
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


def main():
    # Load symbols
    basket_path = os.path.join(DATA_DIR, 'baskets', 'basket_large.txt')
    with open(basket_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]

    print(f'Analyzing RSI extremes for {len(symbols)} symbols...')

    all_results = []

    for sym in symbols:
        cache_dir = os.path.join(DATA_DIR, 'cache', 'dhan', 'daily')
        pattern = os.path.join(cache_dir, f'dhan_*_{sym}_1d.csv')
        matches = glob.glob(pattern)
        
        if not matches:
            continue
        
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
        
        # Rename columns
        col_map = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'close' in col_lower:
                col_map[col] = 'Close'
        df = df.rename(columns=col_map)
        
        if 'Close' not in df.columns or len(df) < 50:
            continue
        
        # Calculate RSI
        close = df['Close'].values.astype(float)
        rsi = talib.RSI(close, timeperiod=14)
        
        df['RSI'] = rsi
        df['return_pct'] = df['Close'].pct_change() * 100
        df['next_return'] = df['return_pct'].shift(-1)
        df['next_positive'] = df['next_return'] > 0
        df['symbol'] = sym
        
        all_results.append(df[['RSI', 'return_pct', 'next_return', 'next_positive', 'symbol']].dropna())

    combined = pd.concat(all_results)
    combined = combined.dropna(subset=['next_return'])

    print(f'Total observations: {len(combined)}')

    # Baseline
    baseline = combined['next_positive'].mean() * 100
    baseline_ret = combined['next_return'].mean()
    print(f'\n📊 BASELINE: {baseline:.1f}% positive next day, avg {baseline_ret:.3f}%')

    # RSI Analysis
    print('\n' + '='*80)
    print('RSI LEVEL ANALYSIS: Does extreme RSI predict next day direction?')
    print('='*80)

    thresholds = [
        ('RSI > 90 (Extreme Overbought)', combined['RSI'] > 90),
        ('RSI > 85', combined['RSI'] > 85),
        ('RSI > 80', combined['RSI'] > 80),
        ('RSI > 70 (Overbought)', combined['RSI'] > 70),
        ('RSI 50-70 (Neutral-Bullish)', (combined['RSI'] >= 50) & (combined['RSI'] <= 70)),
        ('RSI 30-50 (Neutral-Bearish)', (combined['RSI'] >= 30) & (combined['RSI'] < 50)),
        ('RSI < 30 (Oversold)', combined['RSI'] < 30),
        ('RSI < 20', combined['RSI'] < 20),
        ('RSI < 15', combined['RSI'] < 15),
        ('RSI < 10 (Extreme Oversold)', combined['RSI'] < 10),
    ]

    print(f'\n{"RSI Level":<35} {"Count":>8} {"Next Day +":>12} {"Avg Return":>12} {"vs Base":>10}')
    print('-'*80)

    for name, mask in thresholds:
        subset = combined[mask]
        if len(subset) >= 20:
            hit = subset['next_positive'].mean() * 100
            avg_ret = subset['next_return'].mean()
            vs_base = hit - baseline
            
            if hit > 55:
                emoji = '🟢'
            elif hit < 45:
                emoji = '🔴'
            else:
                emoji = '⚪'
            
            print(f'{emoji} {name:<33} {len(subset):>8} {hit:>11.1f}% {avg_ret:>+11.3f}% {vs_base:>+9.1f}%')

    # Focus on RSI > 90
    print('\n' + '='*80)
    print('🔥 DEEP DIVE: RSI > 90 (Your hypothesis)')
    print('='*80)

    extreme_ob = combined[combined['RSI'] > 90]
    print(f'\nTotal observations with RSI > 90: {len(extreme_ob)}')
    print(f'Next day positive rate: {extreme_ob["next_positive"].mean()*100:.1f}%')
    print(f'Average next day return: {extreme_ob["next_return"].mean():+.3f}%')

    # By current day return
    print('\nBreakdown by current day performance:')
    extreme_ob_up = extreme_ob[extreme_ob['return_pct'] > 0]
    extreme_ob_down = extreme_ob[extreme_ob['return_pct'] < 0]

    if len(extreme_ob_up) >= 10:
        print(f'  RSI>90 + Current day UP: {extreme_ob_up["next_positive"].mean()*100:.1f}% next day positive (n={len(extreme_ob_up)})')
    if len(extreme_ob_down) >= 10:
        print(f'  RSI>90 + Current day DOWN: {extreme_ob_down["next_positive"].mean()*100:.1f}% next day positive (n={len(extreme_ob_down)})')

    # Statistical significance
    observed = extreme_ob['next_positive'].sum()
    expected = len(extreme_ob) * (baseline/100)
    chi2 = ((observed - expected)**2) / expected + ((len(extreme_ob) - observed - (len(extreme_ob) - expected))**2) / (len(extreme_ob) - expected)
    p_val = 1 - stats.chi2.cdf(chi2, df=1)
    print(f'\nStatistical significance: p-value = {p_val:.4f}')
    if p_val < 0.05:
        if extreme_ob['next_positive'].mean()*100 > baseline:
            print('✓ SIGNIFICANT: RSI>90 leads to MORE bullish days than baseline')
        else:
            print('✓ SIGNIFICANT: RSI>90 leads to FEWER bullish days than baseline')
    else:
        print('⚡ Not statistically significant at p<0.05')

    # Consecutive RSI > 70 days
    print('\n' + '='*80)
    print('📈 MOMENTUM ANALYSIS: Consecutive high RSI days')
    print('='*80)

    # Check 2+ consecutive RSI > 70 days
    combined['prev_rsi'] = combined.groupby('symbol')['RSI'].shift(1)
    momentum_2 = combined[(combined['RSI'] > 70) & (combined['prev_rsi'] > 70)]
    if len(momentum_2) >= 30:
        print(f'2+ days RSI>70: {momentum_2["next_positive"].mean()*100:.1f}% next day + (n={len(momentum_2)})')

    # RSI > 80 after being > 80 yesterday
    momentum_80 = combined[(combined['RSI'] > 80) & (combined['prev_rsi'] > 80)]
    if len(momentum_80) >= 30:
        print(f'2+ days RSI>80: {momentum_80["next_positive"].mean()*100:.1f}% next day + (n={len(momentum_80)})')

    # RSI > 90 after being > 80 yesterday
    momentum_90 = combined[(combined['RSI'] > 90) & (combined['prev_rsi'] > 80)]
    if len(momentum_90) >= 30:
        print(f'RSI>90 after RSI>80: {momentum_90["next_positive"].mean()*100:.1f}% next day + (n={len(momentum_90)})')

    # Check for mean reversion vs momentum
    print('\n' + '='*80)
    print('📊 TRADING IMPLICATIONS')
    print('='*80)
    
    rsi_90 = combined[combined['RSI'] > 90]
    rsi_10 = combined[combined['RSI'] < 10]
    
    print(f'\nRSI > 90 (Extreme Overbought):')
    print(f'  Next day positive: {rsi_90["next_positive"].mean()*100:.1f}%')
    print(f'  Avg next day return: {rsi_90["next_return"].mean():+.3f}%')
    if rsi_90["next_positive"].mean()*100 > 50:
        print(f'  → MOMENTUM: Strong stocks tend to stay strong')
    else:
        print(f'  → MEAN REVERSION: Overbought leads to pullback')
    
    if len(rsi_10) >= 20:
        print(f'\nRSI < 10 (Extreme Oversold):')
        print(f'  Next day positive: {rsi_10["next_positive"].mean()*100:.1f}%')
        print(f'  Avg next day return: {rsi_10["next_return"].mean():+.3f}%')
        if rsi_10["next_positive"].mean()*100 > 50:
            print(f'  → MEAN REVERSION: Oversold bounces')
        else:
            print(f'  → MOMENTUM: Weak stocks stay weak')


if __name__ == "__main__":
    main()
