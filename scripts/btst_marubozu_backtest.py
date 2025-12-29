#!/usr/bin/env python3
"""BTST Marubozu Backtest"""

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
ROUND_TRIP_COST = 0.37

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

trades = []

for sym in SYMBOLS:
    file = find_file(sym)
    if not file:
        continue
    
    df = pd.read_csv(file)
    df['time'] = pd.to_datetime(df['time'])
    df = df.drop_duplicates(subset=['time'])
    df = df.sort_values('time').reset_index(drop=True)
    df = df[(df['time'] >= '2016-01-01') & (df['time'] < '2025-01-01')]
    
    if len(df) < 10:
        continue
    
    df['body'] = df['close'] - df['open']
    df['range'] = df['high'] - df['low']
    df['body_pct'] = (df['body'] / df['open']) * 100
    df['body_ratio'] = df['body'] / df['range'].replace(0, np.nan)
    df['is_marubozu'] = (df['body'] > 0) & (df['body_pct'] >= MIN_BODY_PCT) & (df['body_ratio'] >= MIN_BODY_RANGE)
    
    df['next_close'] = df['close'].shift(-1)
    df['ret_btst_gross'] = (df['next_close'] - df['close']) / df['close'] * 100
    df['ret_btst_net'] = df['ret_btst_gross'] - ROUND_TRIP_COST
    
    signals = df[df['is_marubozu'] & df['ret_btst_gross'].notna()].copy()
    
    for _, row in signals.iterrows():
        trades.append({
            'year': row['time'].year,
            'symbol': sym,
            'ret_gross': row['ret_btst_gross'],
            'ret_net': row['ret_btst_net'],
        })

df_trades = pd.DataFrame(trades)

print('='*80)
print('BTST MARUBOZU BACKTEST (Buy at 3:25 PM today, Sell at 3:25 PM tomorrow)')
print('='*80)
print(f'\nRound Trip Cost: {ROUND_TRIP_COST}% (delivery)\n')

print('GROSS RETURNS (before charges):')
print('-'*60)
print(f'Total Trades: {len(df_trades):,}')
print(f'Avg Return: {df_trades["ret_gross"].mean():.2f}%')
print(f'Win Rate: {(df_trades["ret_gross"] > 0).mean() * 100:.1f}%')

yearly_gross = df_trades.groupby('year')['ret_gross'].mean()
print(f'Years Positive: {(yearly_gross > 0).sum()}/{len(yearly_gross)}')
print()

print('NET RETURNS (after 0.37% charges):')
print('-'*60)
print(f'Total Trades: {len(df_trades):,}')
print(f'Avg Return: {df_trades["ret_net"].mean():.2f}%')
print(f'Win Rate: {(df_trades["ret_net"] > 0).mean() * 100:.1f}%')

yearly_net = df_trades.groupby('year')['ret_net'].mean()
print(f'Years Positive: {(yearly_net > 0).sum()}/{len(yearly_net)}')
print()

print('YEAR-BY-YEAR BREAKDOWN (Net):')
print('-'*60)
print(f'{"Year":<6} {"Trades":>8} {"Avg Ret":>10} {"Win%":>8} {"Total%":>10}')
print('-'*60)
for year in sorted(df_trades['year'].unique()):
    year_df = df_trades[df_trades['year'] == year]
    trades_n = len(year_df)
    avg_ret = year_df['ret_net'].mean()
    win_pct = (year_df['ret_net'] > 0).mean() * 100
    total_ret = year_df['ret_net'].sum()
    print(f'{year:<6} {trades_n:>8} {avg_ret:>+9.2f}% {win_pct:>7.1f}% {total_ret:>+9.1f}%')
