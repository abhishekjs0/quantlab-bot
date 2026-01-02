#!/usr/bin/env python3
"""
ETF-Only Monthly Analysis
Analyzes month-wise returns for only the ETFs from the attached file.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CACHE_DIR = Path('data/cache/dhan/daily')

# ETF symbols from the attached TradingView CSV
ETF_SYMBOLS = [
    'NIFTYBETA', 'NEXT50BETA', 'ALPHA', 'IT', 'LOWVOL1', 'MIDCAP', 'GILT5BETA',
    'GILT10BETA', 'MIDCAPBETA', 'MNC', 'CONS', 'VAL30IETF', 'MOMIDMTM', 'ESG',
    'MID150CASE', 'BSLNIFTY', 'ELIQUID', 'MULTICAP', 'NEXT50IETF', 'MOMNC',
    'SENSEXADD', 'ESENSEX', 'TECH', 'MONQ50', 'BANKADD', 'LICNETFGSC',
    'MIDCAPIETF', 'AUTOBEES', 'TATAGOLD', 'GOLDBEES', 'GROWWNET', 'AXSENSEX',
    'METALIETF', 'MSCIADD', 'TNIDETF', 'ALPHAETF', 'SBIETFQLTY', 'AONENIFTY',
    'TOP10ADD', 'NV20IETF', 'METAL', 'MOLOWVOL', 'LOWVOLIETF', 'MONIFTY500',
    'HEALTHIETF', 'UNIONGOLD', 'SETFNN50', 'LIQUIDADD', 'ALPL30IETF',
    'SILVERBEES', 'MOSILVER', 'HDFCQUAL', 'GSEC10ABSL', 'MAFANG', 'GILT5YBEES',
    'MOINFRA', 'HDFCNEXT50', 'MONEXT50', 'NIFTYCASE', 'SBIETFCON', 'GOLDBND',
    'ABSLLIQUID', 'EVIETF', 'LIQUIDETF', 'SETFNIFBK', 'LIQUIDADD', 'TOP15IETF', 'SILVERBND',
    'CONSUMIETF', 'HDFCGROWTH', 'CPSEETF', 'SBINEQWETF', 'GSEC10YEAR', 'HDFCGOLD',
    'MOHEALTH', 'BANKIETF', 'MOMGF', 'MOIPO', 'ITETF', 'SML100CASE', 'GOLDIETF',
    'TOP100CASE', 'QUAL30IETF', 'GROWWNXT50', 'GOLDADD', 'HDFCPVTBAN',
    'MIDQ50ADD', 'MOGOLD', 'BANKPSU', 'CONSUMER', 'GSEC10IETF', 'MOVALUE',
    'HDFCNIFTY', 'AXISTECETF', 'INTERNET', 'SELECTIPO', 'EBANKNIFTY',
    'SILVERCASE', 'GROWWGOLD', 'PSUBNKBEES', 'LICNETFN50', 'EMULTIMQ',
    'NIFTYQLITY', 'GROWWPOWER', 'GROWWLOVOL', 'GSEC5IETF', 'SNXT30BEES',
    'SBIETFPB', 'GROWWMOM50', 'ABSLNN50ET', 'NIF100BEES', 'SMALL250',
    'MIDSELIETF', 'LOWVOL', 'LIQUID', 'FINIETF', 'LICMFGOLD', 'NIFTYADD',
    'LIQUIDSHRI', 'FMCGIETF', 'CONSUMBEES', 'CHOICEGOLD', 'LIQUIDPLUS',
    'HDFCVALUE', 'SILVERADD', 'INFRAIETF', 'HNGSNGBEES', 'MANUFGBEES',
    'ABSLBANETF', 'QGOLDHALF', 'GOLD360', 'MOGSEC', 'MOPSE', 'GROWWLIQID',
    'INFRABEES'
]

print('=' * 80)
print('ETF-ONLY MONTH-WISE RETURNS ANALYSIS')
print('=' * 80)

# Find which ETFs we have data for
found_etfs = []
missing_etfs = []
for symbol in ETF_SYMBOLS:
    files = list(CACHE_DIR.glob(f'dhan_*_{symbol}_1d.csv'))
    if files:
        found_etfs.append(symbol)
    else:
        missing_etfs.append(symbol)

print(f"\n📁 ETFs in CSV: {len(ETF_SYMBOLS)}")
print(f"✅ Found data for: {len(found_etfs)} ETFs")
print(f"❌ Missing data for: {len(missing_etfs)} ETFs")

if missing_etfs[:20]:
    print(f"\n   Missing: {missing_etfs[:20]}...")

# Load only ETF data
all_monthly = []
etf_count = 0
skipped = []

for f in sorted(CACHE_DIR.glob('dhan_*_1d.csv')):
    symbol = f.stem.split('_')[2]
    
    # Only process ETFs
    if symbol not in ETF_SYMBOLS:
        continue
    
    try:
        df = pd.read_csv(f, parse_dates=['time'], index_col='time')
        
        if len(df) < 60:
            skipped.append((symbol, 'too few rows'))
            continue
        
        df['daily_return'] = df['close'].pct_change() * 100
        max_move = df['daily_return'].abs().max()
        if max_move > 30:
            skipped.append((symbol, f'extreme move {max_move:.1f}%'))
            continue
        
        if df.index.duplicated().sum() > 0:
            skipped.append((symbol, 'duplicates'))
            continue
        
        df['month'] = df.index.month
        df['year'] = df.index.year
        
        for (year, month), group in df.groupby(['year', 'month']):
            if len(group) < 10:
                continue
            
            open_price = group['open'].iloc[0]
            close_price = group['close'].iloc[-1]
            monthly_ret = (close_price - open_price) / open_price * 100
            
            all_monthly.append({
                'symbol': symbol,
                'year': year,
                'month': month,
                'monthly_return': monthly_ret
            })
        
        etf_count += 1
        
    except Exception as e:
        skipped.append((symbol, str(e)))

print(f'\n✅ Analyzed {etf_count} ETFs with clean data')
print(f'📊 Total monthly observations: {len(all_monthly)}')
if skipped:
    print(f'⚠️ Skipped {len(skipped)}: {[s[0] for s in skipped]}')

if len(all_monthly) == 0:
    print("\n❌ No data to analyze!")
    exit()

df_monthly = pd.DataFrame(all_monthly)
month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

# Average return by ETF and month
etf_month_avg = df_monthly.groupby(['symbol', 'month'])['monthly_return'].agg(['mean', 'count', 'std']).reset_index()
etf_month_avg.columns = ['symbol', 'month', 'avg_return', 'observations', 'std']
etf_month_avg = etf_month_avg[etf_month_avg['observations'] >= 3]

# TOP ETF-MONTH COMBINATIONS
print('\n' + '=' * 80)
print('TOP 25 ETF-MONTH COMBINATIONS (By Avg Return)')
print('=' * 80)
print(f"{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
print('-' * 50)

top_combos = etf_month_avg.nlargest(25, 'avg_return')
for _, row in top_combos.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")

# WORST ETF-MONTH COMBINATIONS
print('\n' + '=' * 80)
print('BOTTOM 15 ETF-MONTH COMBINATIONS (By Avg Return)')
print('=' * 80)
print(f"{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
print('-' * 50)

worst_combos = etf_month_avg.nsmallest(15, 'avg_return')
for _, row in worst_combos.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")

# MONTH RANKING
print('\n' + '=' * 80)
print('MONTH RANKING (Average across all ETFs)')
print('=' * 80)

month_overall = df_monthly.groupby('month')['monthly_return'].agg(['mean', 'median', 'std', 'count']).reset_index()
month_overall = month_overall.sort_values('mean', ascending=False)

print(f"{'Month':<10} {'Mean%':>10} {'Median%':>10} {'Std':>8} {'Obs':>8}")
print('-' * 50)
for _, row in month_overall.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{m:<10} {row['mean']:>+10.2f} {row['median']:>+10.2f} {row['std']:>8.2f} {int(row['count']):>8}")

# BEST MONTH FOR EACH ETF
print('\n' + '=' * 80)
print('BEST MONTH FOR EACH ETF (All ETFs)')
print('=' * 80)

best_months = etf_month_avg.loc[etf_month_avg.groupby('symbol')['avg_return'].idxmax()]
best_months = best_months.sort_values('avg_return', ascending=False)

print(f"{'Symbol':<15} {'Best Month':<10} {'Avg Ret%':>10} {'Obs':>5}")
print('-' * 45)
for _, row in best_months.iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<10} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")

# WIN RATE BY ETF-MONTH
print('\n' + '=' * 80)
print('HIGHEST WIN RATE ETF-MONTH COMBOS (Min 4 obs, Avg > 1%)')
print('=' * 80)

win_rate = df_monthly.groupby(['symbol', 'month']).apply(
    lambda x: pd.Series({
        'win_rate': (x['monthly_return'] > 0).mean() * 100,
        'avg_return': x['monthly_return'].mean(),
        'observations': len(x)
    }), include_groups=False
).reset_index()

win_rate = win_rate[(win_rate['observations'] >= 4) & (win_rate['avg_return'] > 1)]
win_rate = win_rate.sort_values('win_rate', ascending=False)

print(f"{'Symbol':<15} {'Month':<6} {'WinRate%':>10} {'Avg%':>8} {'Obs':>5}")
print('-' * 50)
for _, row in win_rate.head(25).iterrows():
    m = month_names[int(row['month']) - 1]
    print(f"{row['symbol']:<15} {m:<6} {row['win_rate']:>10.1f} {row['avg_return']:>+8.2f} {int(row['observations']):>5}")

# 100% WIN RATE COMBOS
print('\n' + '=' * 80)
print('100% WIN RATE ETF-MONTH COMBOS (Min 4 obs)')
print('=' * 80)

perfect = win_rate[(win_rate['win_rate'] == 100) & (win_rate['observations'] >= 4)]
perfect = perfect.sort_values('avg_return', ascending=False)

if len(perfect) > 0:
    print(f"{'Symbol':<15} {'Month':<6} {'Avg%':>10} {'Obs':>5}")
    print('-' * 40)
    for _, row in perfect.iterrows():
        m = month_names[int(row['month']) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")
else:
    print("No 100% win rate combos with min 4 observations")

# Category analysis - Group by ETF type
print('\n' + '=' * 80)
print('ANALYSIS BY ETF CATEGORY')
print('=' * 80)

categories = {
    'Gold': ['GOLDBEES', 'TATAGOLD', 'HDFCGOLD', 'GOLDIETF', 'UNIONGOLD', 'MOGOLD', 'GROWWGOLD', 'GOLDADD', 'QGOLDHALF', 'LICMFGOLD', 'CHOICEGOLD', 'GOLDBND', 'GOLD360'],
    'Silver': ['SILVERBEES', 'MOSILVER', 'SILVERCASE', 'SILVERADD', 'SILVERBND'],
    'Nifty50': ['NIFTYBETA', 'HDFCNIFTY', 'LICNETFN50', 'BSLNIFTY', 'NIFTYADD', 'NIFTYCASE', 'AONENIFTY'],
    'NiftyNext50': ['NEXT50BETA', 'NEXT50IETF', 'HDFCNEXT50', 'SETFNN50', 'ABSLNN50ET', 'MONEXT50', 'GROWWNXT50'],
    'Bank': ['PSUBNKBEES', 'BANKIETF', 'SETFNIFBK', 'BANKPSU', 'EBANKNIFTY', 'ABSLBANETF', 'SBIETFPB', 'HDFCPVTBAN'],
    'IT': ['IT', 'TECH', 'ITETF', 'AXISTECETF', 'TNIDETF'],
    'Midcap': ['MIDCAP', 'MIDCAPBETA', 'MIDCAPIETF', 'MID150CASE', 'MIDSELIETF', 'MIDQ50ADD'],
    'Infra': ['INFRAIETF', 'INFRABEES', 'MOINFRA'],
    'CPSE/PSU': ['CPSEETF', 'MOPSE'],
    'Consumption': ['CONS', 'CONSUMIETF', 'CONSUMBEES', 'SBIETFCON', 'CONSUMER'],
    'Healthcare': ['HEALTHIETF', 'MOHEALTH'],
    'Metal': ['METALIETF', 'METAL'],
}

for cat, symbols in categories.items():
    cat_data = df_monthly[df_monthly['symbol'].isin(symbols)]
    if len(cat_data) < 20:
        continue
    
    print(f"\n{cat} ETFs:")
    cat_by_month = cat_data.groupby('month')['monthly_return'].agg(['mean', 'count']).reset_index()
    cat_by_month = cat_by_month.sort_values('mean', ascending=False)
    
    best_month = cat_by_month.iloc[0]
    worst_month = cat_by_month.iloc[-1]
    
    best_m = month_names[int(best_month['month']) - 1]
    worst_m = month_names[int(worst_month['month']) - 1]
    
    print(f"   Best:  {best_m} → {best_month['mean']:+.2f}% avg ({int(best_month['count'])} obs)")
    print(f"   Worst: {worst_m} → {worst_month['mean']:+.2f}% avg ({int(worst_month['count'])} obs)")

# Save to CSV
output_dir = Path('reports/analysis/etf_analysis')
output_dir.mkdir(parents=True, exist_ok=True)

etf_month_avg.to_csv(output_dir / 'etf_only_monthly_performance.csv', index=False)
print(f"\n💾 Saved: {output_dir / 'etf_only_monthly_performance.csv'}")
