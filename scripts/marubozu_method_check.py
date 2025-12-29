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
