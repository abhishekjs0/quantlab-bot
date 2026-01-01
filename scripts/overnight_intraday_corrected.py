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
