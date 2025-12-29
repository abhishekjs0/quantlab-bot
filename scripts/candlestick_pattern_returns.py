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
BASKET_PATH = 'data/basket_main.txt'

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
