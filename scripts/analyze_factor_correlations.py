#!/usr/bin/env python3
import pandas as pd
import numpy as np
from itertools import combinations
import os

factor_etfs = ['ALPHAETF', 'ALPL30IETF', 'LOWVOLIETF', 'MOM30IETF', 'QUAL30IETF', 'SBIETFQLTY', 'VAL30IETF']

prices = {}
for symbol in factor_etfs:
    files = [f for f in os.listdir('data/cache/dhan/daily/') if symbol in f and '_1d.csv' in f]
    if files:
        df = pd.read_csv(f'data/cache/dhan/daily/{files[0]}')
        date_col = 'time' if 'time' in df.columns else 'date'
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).set_index(date_col)
        prices[symbol] = df['close']

# Calculate correlations using maximum overlap for each pair
corr_data = {}
for etf1 in factor_etfs:
    corr_data[etf1] = {}
    for etf2 in factor_etfs:
        if etf1 == etf2:
            corr_data[etf1][etf2] = 1.0
        else:
            combined = pd.DataFrame({'etf1': prices[etf1], 'etf2': prices[etf2]}).dropna()
            if len(combined) > 20:
                returns = combined.pct_change().dropna()
                corr_data[etf1][etf2] = returns['etf1'].corr(returns['etf2'])

corr_matrix = pd.DataFrame(corr_data)

print("📊 FACTOR ETF CORRELATION - MAXIMUM AVAILABLE DATA")
print("=" * 90)

# Best pairs
pairs = []
for etf1, etf2 in combinations(factor_etfs, 2):
    corr = corr_matrix.loc[etf1, etf2]
    combined = pd.DataFrame({'etf1': prices[etf1], 'etf2': prices[etf2]}).dropna()
    days = len(combined)
    years = days / 252
    pairs.append((corr, etf1, etf2, days, years))

pairs.sort()
print("\nTOP 10 LEAST CORRELATED PAIRS:")
print("-" * 90)
for i, (corr, etf1, etf2, days, years) in enumerate(pairs[:10], 1):
    print(f"{i:2d}. {etf1:12s} + {etf2:12s}  Correlation: {corr:.3f}  ({days:4d} days, {years:.1f} years)")

# Best trios  
trios = []
for etf1, etf2, etf3 in combinations(factor_etfs, 3):
    corr12 = corr_matrix.loc[etf1, etf2]
    corr13 = corr_matrix.loc[etf1, etf3]
    corr23 = corr_matrix.loc[etf2, etf3]
    avg_corr = (corr12 + corr13 + corr23) / 3
    combined = pd.DataFrame({'e1': prices[etf1], 'e2': prices[etf2], 'e3': prices[etf3]}).dropna()
    days = len(combined)
    years = days / 252
    trios.append((avg_corr, etf1, etf2, etf3, days, years))

trios.sort()
print("\nTOP 10 LEAST CORRELATED TRIOS:")
print("-" * 90)
for i, (avg, e1, e2, e3, days, years) in enumerate(trios[:10], 1):
    print(f"{i:2d}. {e1:10s} + {e2:10s} + {e3:10s}  Avg Corr: {avg:.3f}  ({days:4d} days, {years:.1f} years)")

# Performance analysis
def analyze(etf_list, label):
    price_dict = {etf: prices[etf] for etf in etf_list}
    df = pd.DataFrame(price_dict).dropna()
    if len(df) < 50:
        print(f"{label}: Insufficient data")
        return
    rets = df.pct_change().dropna()
    port_rets = rets.mean(axis=1)
    years = len(df) / 252
    tot_ret = (1 + port_rets).prod() - 1
    cagr = (1 + tot_ret) ** (1/years) - 1
    vol = port_rets.std() * np.sqrt(252)
    sharpe = cagr / vol if vol > 0 else 0
    cum = (1 + port_rets).cumprod()
    dd = (cum - cum.expanding().max()) / cum.expanding().max()
    max_dd = dd.min()
    print(f"\n{label}")
    print(f"  ETFs: {', '.join(etf_list)}")
    print(f"  Period: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')} ({len(df)} days, {years:.1f} years)")
    print(f"  CAGR: {cagr*100:6.2f}%  |  Volatility: {vol*100:5.2f}%  |  Sharpe: {sharpe:.2f}  |  Max DD: {max_dd*100:6.2f}%")
    return {'cagr': cagr, 'vol': vol, 'sharpe': sharpe, 'max_dd': max_dd}

print("\n" + "=" * 90)
print("PERFORMANCE ANALYSIS (Equal Weight Portfolios)")
print("=" * 90)

analyze([pairs[0][1], pairs[0][2]], f"✅ Best 2-ETF: {pairs[0][1]} + {pairs[0][2]} (Corr: {pairs[0][0]:.3f})")
analyze([pairs[1][1], pairs[1][2]], f"2nd Best 2-ETF: {pairs[1][1]} + {pairs[1][2]} (Corr: {pairs[1][0]:.3f})")
analyze([trios[0][1], trios[0][2], trios[0][3]], f"✅ Best 3-ETF: {trios[0][1]} + {trios[0][2]} + {trios[0][3]} (Avg Corr: {trios[0][0]:.3f})")
analyze([trios[1][1], trios[1][2], trios[1][3]], f"2nd Best 3-ETF: {trios[1][1]} + {trios[1][2]} + {trios[1][3]} (Avg Corr: {trios[1][0]:.3f})")
analyze(factor_etfs, "All 7 Factor ETFs Combined")

print("\n" + "-" * 90)
print("Individual ETF Performance (Full Period):")
print("-" * 90)
for etf in sorted(factor_etfs):
    p = prices[etf].dropna()
    r = p.pct_change().dropna()
    years = len(p) / 252
    cagr = ((p.iloc[-1] / p.iloc[0]) ** (1/years) - 1) if years > 0 else 0
    vol = r.std() * np.sqrt(252)
    cum = (1 + r).cumprod()
    dd = ((cum - cum.expanding().max()) / cum.expanding().max()).min()
    print(f"  {etf:12s}  CAGR: {cagr*100:6.2f}%  |  Vol: {vol*100:5.2f}%  |  Max DD: {dd*100:6.2f}%  ({years:.1f} years)")

print("\n" + "=" * 90)
print("✅ Analysis complete! Correlations calculated using maximum available overlap for each pair.")
