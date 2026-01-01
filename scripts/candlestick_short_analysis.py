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
