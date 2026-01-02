#!/usr/bin/env python3
"""
ETF Analysis Script
===================
1. Extended TOTM Strategy (Entry: 25th open, Exit: 3rd close of next month)
2. Monthly Return Analysis
3. Day of Week Analysis
"""

import glob
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
OUTPUT_DIR = Path("reports/analysis/etf_analysis")
CHARGES = 0.0037  # 0.37% round-trip

# ETF symbols
ETF_SYMBOLS = [
    "NIFTYBETA", "NEXT50BETA", "ALPHA", "IT", "LOWVOL1", "MIDCAP", "GILT5BETA",
    "GILT10BETA", "MIDCAPBETA", "MNC", "CONS", "VAL30IETF", "MOMIDMTM", "ESG",
    "MID150CASE", "BSLNIFTY", "ELIQUID", "MULTICAP", "NEXT50IETF", "MOMNC",
    "SENSEXADD", "ESENSEX", "TECH", "MONQ50", "BANKADD", "LICNETFGSC",
    "MIDCAPIETF", "AUTOBEES", "TATAGOLD", "GOLDBEES", "GROWWNET", "AXSENSEX",
    "METALIETF", "MSCIADD", "TNIDETF", "ALPHAETF", "SBIETFQLTY", "AONENIFTY",
    "TOP10ADD", "NV20IETF", "METAL", "MOLOWVOL", "LOWVOLIETF", "MONIFTY500",
    "HEALTHIETF", "UNIONGOLD", "SETFNN50", "LIQUIDADD", "ALPL30IETF",
    "SILVERBEES", "MOSILVER", "HDFCQUAL", "GSEC10ABSL", "MAFANG", "GILT5YBEES",
    "MOINFRA", "HDFCNEXT50", "MONEXT50", "NIFTYCASE", "SBIETFCON", "GOLDBND",
    "ABSLLIQUID", "EVIETF", "LIQUIDETF", "SETFNIFBK", "TOP15IETF", "SILVERBND",
    "CONSUMIETF", "HDFCGROWTH", "CPSEETF", "SBINEQWETF", "GSEC10YEAR", "HDFCGOLD",
    "MOHEALTH", "BANKIETF", "MOMGF", "MOIPO", "ITETF", "SML100CASE", "GOLDIETF",
    "TOP100CASE", "QUAL30IETF", "GROWWNXT50", "GOLDADD", "HDFCPVTBAN",
    "MIDQ50ADD", "MOGOLD", "BANKPSU", "CONSUMER", "GSEC10IETF", "MOVALUE",
    "HDFCNIFTY", "AXISTECETF", "INTERNET", "SELECTIPO", "EBANKNIFTY",
    "SILVERCASE", "GROWWGOLD", "PSUBNKBEES", "LICNETFN50", "EMULTIMQ",
    "NIFTYQLITY", "GROWWPOWER", "GROWWLOVOL", "GSEC5IETF", "SNXT30BEES",
    "SBIETFPB", "GROWWMOM50", "ABSLNN50ET", "NIF100BEES", "SMALL250",
    "MIDSELIETF", "LOWVOL", "LIQUID", "FINIETF", "LICMFGOLD", "NIFTYADD",
    "LIQUIDSHRI", "FMCGIETF", "CONSUMBEES", "CHOICEGOLD", "LIQUIDPLUS",
    "HDFCVALUE", "SILVERADD", "INFRAIETF", "HNGSNGBEES", "MANUFGBEES",
    "ABSLBANETF", "QGOLDHALF", "GOLD360", "MOGSEC", "MOPSE", "GROWWLIQID",
    "INFRABEES"
]


def load_etf_data():
    """Load all ETF data from cache."""
    all_data = {}
    
    for symbol in ETF_SYMBOLS:
        pattern = CACHE_DIR / f"dhan_*_{symbol}_1d.csv"
        files = list(CACHE_DIR.glob(f"dhan_*_{symbol}_1d.csv"))
        
        if files:
            try:
                df = pd.read_csv(files[0], parse_dates=['time'], index_col='time')
                if len(df) >= 20:  # Minimum data requirement
                    all_data[symbol] = df
            except Exception as e:
                pass
    
    return all_data


def run_extended_totm_strategy(all_data):
    """
    Extended TOTM Strategy:
    - Entry: Open of first trading day on/after 25th of month N
    - Exit: Close of first trading day on/after 3rd of month N+1
    """
    print("\n" + "=" * 70)
    print("EXTENDED TOTM STRATEGY ANALYSIS")
    print("Entry: 25th Open | Exit: 3rd Close (next month) | Charges: 0.37%")
    print("=" * 70)
    
    all_trades = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['date'] = df.index.date
        df['day'] = df.index.day
        df['month'] = df.index.month
        df['year'] = df.index.year
        
        # Find entry days (first trading day on/after 25th)
        df['is_entry_candidate'] = df['day'] >= 25
        
        # Group by year-month for entry
        for (year, month), group in df.groupby(['year', 'month']):
            entry_candidates = group[group['day'] >= 25]
            if entry_candidates.empty:
                continue
            
            entry_row = entry_candidates.iloc[0]
            entry_date = entry_row.name
            entry_price = entry_row['open']
            
            # Find exit in next month (first day on/after 3rd)
            if month == 12:
                next_year, next_month = year + 1, 1
            else:
                next_year, next_month = year, month + 1
            
            next_month_data = df[(df['year'] == next_year) & (df['month'] == next_month)]
            exit_candidates = next_month_data[next_month_data['day'] >= 3]
            
            if exit_candidates.empty:
                continue
            
            exit_row = exit_candidates.iloc[0]
            exit_date = exit_row.name
            exit_price = exit_row['close']
            
            # Calculate returns
            gross_return = (exit_price - entry_price) / entry_price
            net_return = gross_return - CHARGES
            holding_days = (exit_date - entry_date).days
            
            all_trades.append({
                'symbol': symbol,
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_return_pct': gross_return * 100,
                'net_return_pct': net_return * 100,
                'holding_days': holding_days,
                'year': entry_date.year
            })
    
    if not all_trades:
        print("No trades generated!")
        return None
    
    trades_df = pd.DataFrame(all_trades)
    
    # Overall stats
    total_trades = len(trades_df)
    total_net_return = trades_df['net_return_pct'].sum()
    avg_net_return = trades_df['net_return_pct'].mean()
    win_rate = (trades_df['net_return_pct'] > 0).mean() * 100
    winners = trades_df[trades_df['net_return_pct'] > 0]['net_return_pct']
    losers = trades_df[trades_df['net_return_pct'] <= 0]['net_return_pct']
    avg_winner = winners.mean() if len(winners) > 0 else 0
    avg_loser = losers.mean() if len(losers) > 0 else 0
    profit_factor = abs(winners.sum() / losers.sum()) if losers.sum() != 0 else float('inf')
    avg_holding = trades_df['holding_days'].mean()
    
    print(f"\n--- OVERALL RESULTS ---")
    print(f"Total Trades: {total_trades}")
    print(f"Total Net Return: {total_net_return:+,.2f}%")
    print(f"Avg Net P&L per Trade: {avg_net_return:+.3f}%")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Avg Winner: {avg_winner:+.2f}%")
    print(f"Avg Loser: {avg_loser:.2f}%")
    print(f"Avg Holding Period: {avg_holding:.1f} days")
    
    # Year-wise breakdown
    print(f"\n--- YEAR-WISE BREAKDOWN ---")
    year_stats = []
    for year, group in trades_df.groupby('year'):
        yr_total = group['net_return_pct'].sum()
        yr_avg = group['net_return_pct'].mean()
        yr_wr = (group['net_return_pct'] > 0).mean() * 100
        yr_winners = group[group['net_return_pct'] > 0]['net_return_pct']
        yr_losers = group[group['net_return_pct'] <= 0]['net_return_pct']
        yr_pf = abs(yr_winners.sum() / yr_losers.sum()) if yr_losers.sum() != 0 else float('inf')
        
        year_stats.append({
            'year': year,
            'trades': len(group),
            'total_return': yr_total,
            'avg_return': yr_avg,
            'win_rate': yr_wr,
            'profit_factor': yr_pf
        })
        print(f"{year}: {len(group):3d} trades | {yr_total:+8.1f}% total | {yr_avg:+.2f}% avg | {yr_wr:.1f}% WR | {yr_pf:.2f} PF")
    
    # Top performing ETFs
    print(f"\n--- TOP 15 ETFs BY AVG RETURN ---")
    etf_stats = trades_df.groupby('symbol').agg({
        'net_return_pct': ['count', 'sum', 'mean'],
    }).round(3)
    etf_stats.columns = ['trades', 'total_return', 'avg_return']
    etf_stats = etf_stats[etf_stats['trades'] >= 12]  # At least 1 year of data
    etf_stats = etf_stats.sort_values('avg_return', ascending=False)
    
    for i, (symbol, row) in enumerate(etf_stats.head(15).iterrows(), 1):
        print(f"{i:2d}. {symbol:15s} | {int(row['trades']):3d} trades | {row['total_return']:+8.1f}% total | {row['avg_return']:+.3f}% avg")
    
    # Worst performing ETFs
    print(f"\n--- BOTTOM 10 ETFs BY AVG RETURN ---")
    for i, (symbol, row) in enumerate(etf_stats.tail(10).iterrows(), 1):
        print(f"{i:2d}. {symbol:15s} | {int(row['trades']):3d} trades | {row['total_return']:+8.1f}% total | {row['avg_return']:+.3f}% avg")
    
    return trades_df


def run_monthly_analysis(all_data):
    """Analyze returns by month of year."""
    print("\n" + "=" * 70)
    print("MONTHLY RETURN ANALYSIS")
    print("=" * 70)
    
    all_monthly = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['month'] = df.index.month
        df['year'] = df.index.year
        df['daily_return'] = df['close'].pct_change() * 100
        
        # Monthly returns
        monthly = df.groupby(['year', 'month']).agg({
            'open': 'first',
            'close': 'last',
            'daily_return': 'sum'
        }).reset_index()
        
        monthly['symbol'] = symbol
        monthly['monthly_return'] = (monthly['close'] - monthly['open']) / monthly['open'] * 100
        all_monthly.append(monthly)
    
    if not all_monthly:
        print("No data!")
        return None
    
    monthly_df = pd.concat(all_monthly, ignore_index=True)
    
    # Average return by month
    print("\n--- AVERAGE RETURN BY MONTH (All ETFs) ---")
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    
    month_stats = monthly_df.groupby('month').agg({
        'monthly_return': ['count', 'mean', 'std', 'median']
    }).round(3)
    month_stats.columns = ['observations', 'mean_return', 'std', 'median_return']
    month_stats['win_rate'] = monthly_df.groupby('month').apply(
        lambda x: (x['monthly_return'] > 0).mean() * 100, include_groups=False
    )
    
    print(f"\n{'Month':<6} {'Obs':>6} {'Mean':>8} {'Median':>8} {'Std':>8} {'Win%':>7}")
    print("-" * 50)
    for month in range(1, 13):
        if month in month_stats.index:
            row = month_stats.loc[month]
            print(f"{month_names[month-1]:<6} {int(row['observations']):>6} {row['mean_return']:>+8.2f}% {row['median_return']:>+8.2f}% {row['std']:>8.2f} {row['win_rate']:>6.1f}%")
    
    # Best and worst months
    best_months = month_stats.nlargest(3, 'mean_return')
    worst_months = month_stats.nsmallest(3, 'mean_return')
    
    print(f"\n📈 Best Months: {', '.join([month_names[int(m)-1] for m in best_months.index])}")
    print(f"📉 Worst Months: {', '.join([month_names[int(m)-1] for m in worst_months.index])}")
    
    return monthly_df


def run_day_of_week_analysis(all_data):
    """Analyze returns by day of week."""
    print("\n" + "=" * 70)
    print("DAY OF WEEK ANALYSIS")
    print("=" * 70)
    
    all_daily = []
    
    for symbol, df in all_data.items():
        df = df.copy()
        df['day_of_week'] = df.index.dayofweek  # 0=Monday, 4=Friday
        df['daily_return'] = df['close'].pct_change() * 100
        df['overnight_return'] = (df['open'] - df['close'].shift(1)) / df['close'].shift(1) * 100
        df['intraday_return'] = (df['close'] - df['open']) / df['open'] * 100
        df['symbol'] = symbol
        all_daily.append(df[['symbol', 'day_of_week', 'daily_return', 'overnight_return', 'intraday_return']].dropna())
    
    if not all_daily:
        print("No data!")
        return None
    
    daily_df = pd.concat(all_daily, ignore_index=True)
    
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    # Daily return by day of week
    print("\n--- DAILY RETURNS BY DAY OF WEEK ---")
    print(f"\n{'Day':<12} {'Obs':>8} {'Mean':>8} {'Median':>8} {'Std':>8} {'Win%':>7}")
    print("-" * 55)
    
    dow_stats = []
    for dow in range(5):
        subset = daily_df[daily_df['day_of_week'] == dow]
        if len(subset) > 0:
            mean_ret = subset['daily_return'].mean()
            median_ret = subset['daily_return'].median()
            std_ret = subset['daily_return'].std()
            win_rate = (subset['daily_return'] > 0).mean() * 100
            obs = len(subset)
            
            dow_stats.append({
                'day': day_names[dow],
                'dow': dow,
                'observations': obs,
                'mean_return': mean_ret,
                'median_return': median_ret,
                'std': std_ret,
                'win_rate': win_rate
            })
            
            print(f"{day_names[dow]:<12} {obs:>8} {mean_ret:>+8.3f}% {median_ret:>+8.3f}% {std_ret:>8.3f} {win_rate:>6.1f}%")
    
    # Overnight vs Intraday by day
    print("\n--- OVERNIGHT vs INTRADAY BY DAY ---")
    print(f"\n{'Day':<12} {'Overnight':>12} {'Intraday':>12} {'Total':>12}")
    print("-" * 50)
    
    for dow in range(5):
        subset = daily_df[daily_df['day_of_week'] == dow]
        if len(subset) > 0:
            overnight = subset['overnight_return'].mean()
            intraday = subset['intraday_return'].mean()
            total = subset['daily_return'].mean()
            print(f"{day_names[dow]:<12} {overnight:>+11.3f}% {intraday:>+11.3f}% {total:>+11.3f}%")
    
    # Best/worst day
    dow_df = pd.DataFrame(dow_stats)
    best_day = dow_df.loc[dow_df['mean_return'].idxmax(), 'day']
    worst_day = dow_df.loc[dow_df['mean_return'].idxmin(), 'day']
    
    print(f"\n📈 Best Day: {best_day}")
    print(f"📉 Worst Day: {worst_day}")
    
    return daily_df


def main():
    print("=" * 70)
    print("ETF COMPREHENSIVE ANALYSIS")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)
    
    # Load data
    print("\n📂 Loading ETF data...")
    all_data = load_etf_data()
    print(f"✅ Loaded {len(all_data)} ETFs with sufficient data")
    
    if not all_data:
        print("❌ No data loaded!")
        return
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Extended TOTM Strategy
    totm_trades = run_extended_totm_strategy(all_data)
    if totm_trades is not None:
        totm_trades.to_csv(OUTPUT_DIR / "etf_extended_totm_trades.csv", index=False)
        print(f"\n💾 Saved: {OUTPUT_DIR / 'etf_extended_totm_trades.csv'}")
    
    # 2. Monthly Analysis
    monthly_data = run_monthly_analysis(all_data)
    if monthly_data is not None:
        monthly_data.to_csv(OUTPUT_DIR / "etf_monthly_returns.csv", index=False)
        print(f"💾 Saved: {OUTPUT_DIR / 'etf_monthly_returns.csv'}")
    
    # 3. Day of Week Analysis
    dow_data = run_day_of_week_analysis(all_data)
    if dow_data is not None:
        dow_data.to_csv(OUTPUT_DIR / "etf_day_of_week.csv", index=False)
        print(f"💾 Saved: {OUTPUT_DIR / 'etf_day_of_week.csv'}")
    
    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
