#!/usr/bin/env python3
"""
Weekly Overnight vs Intraday Analysis with Running Totals
Matches the format shown in the user's screenshot
"""

import pandas as pd
import numpy as np
import glob
from pathlib import Path
from datetime import datetime

CACHE_DIR = Path('data/cache')

def load_basket(path):
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]

def find_file(symbol):
    pattern = str(CACHE_DIR / f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    return matches[0] if matches else None

def analyze_basket_weekly(basket_name, basket_path, year=2025):
    """Analyze basket and return weekly summary with running totals."""
    symbols = load_basket(basket_path)
    
    all_daily_data = []
    loaded_count = 0
    
    for symbol in symbols:
        file = find_file(symbol)
        if not file:
            continue
        
        df = pd.read_csv(file)
        df['time'] = pd.to_datetime(df['time'])
        df = df.drop_duplicates(subset=['time'])
        df = df.set_index('time').sort_index()
        
        # Calculate returns as percentages
        df['prev_close'] = df['close'].shift(1)
        df['overnight_pct'] = (df['open'] - df['prev_close']) / df['prev_close'] * 100
        df['intraday_pct'] = (df['close'] - df['open']) / df['open'] * 100
        df['total_pct'] = (df['close'] - df['prev_close']) / df['prev_close'] * 100
        df = df.dropna()
        
        # Filter to target year
        df_year = df[df.index.year == year]
        
        if len(df_year) > 0:
            all_daily_data.append(df_year[['overnight_pct', 'intraday_pct', 'total_pct']])
            loaded_count += 1
    
    if not all_daily_data:
        return None, 0
    
    # Combine all symbols - average across symbols for each day
    combined = pd.concat(all_daily_data, axis=1)
    
    # Get average for each day (equal weighted basket)
    overnight_cols = [i for i in range(0, len(combined.columns), 3)]
    intraday_cols = [i for i in range(1, len(combined.columns), 3)]
    total_cols = [i for i in range(2, len(combined.columns), 3)]
    
    daily_avg = pd.DataFrame(index=combined.index)
    daily_avg['overnight'] = combined.iloc[:, overnight_cols].mean(axis=1)
    daily_avg['intraday'] = combined.iloc[:, intraday_cols].mean(axis=1)
    daily_avg['total'] = combined.iloc[:, total_cols].mean(axis=1)
    
    # Add week info
    daily_avg['year'] = daily_avg.index.year
    daily_avg['week'] = daily_avg.index.isocalendar().week.values
    daily_avg['year_week'] = daily_avg['year'].astype(str) + '-W' + daily_avg['week'].astype(str).str.zfill(2)
    
    # Aggregate to weekly - sum of daily returns
    weekly = daily_avg.groupby('year_week').agg({
        'overnight': 'sum',
        'intraday': 'sum',
        'total': 'sum'
    }).reset_index()
    
    weekly.columns = ['Year-Wk', 'Overnight', 'Intraday', 'Weekly Total']
    
    # Sort by week
    weekly = weekly.sort_values('Year-Wk').reset_index(drop=True)
    
    # Calculate running totals
    weekly['Running Overnight'] = weekly['Overnight'].cumsum()
    weekly['Running Intraday'] = weekly['Intraday'].cumsum()
    weekly['Running Total'] = weekly['Weekly Total'].cumsum()
    
    return weekly, loaded_count


def print_weekly_table(basket_name, weekly_df, symbol_count):
    """Print formatted weekly table."""
    print(f"\n{'='*90}")
    print(f"{basket_name.upper()} - Weekly Overnight vs Intraday ({symbol_count} symbols)")
    print(f"{'='*90}")
    
    print(f"\n{'Year-Wk':<12} │ {'Grand Total':^25} │ {'Weekly':>8} │ {'Running Totals':^35}")
    print(f"{'':12} │ {'Overnight':>10} {'Intraday':>12} │ {'Total':>8} │ {'Overnight':>10} {'Intraday':>12} {'Total':>10}")
    print("-" * 90)
    
    for _, row in weekly_df.iterrows():
        overnight_color = "" 
        intraday_color = ""
        
        print(f"{row['Year-Wk']:<12} │ {row['Overnight']:>10.2f} {row['Intraday']:>12.2f} │ {row['Weekly Total']:>8.2f} │ {row['Running Overnight']:>10.2f} {row['Running Intraday']:>12.2f} {row['Running Total']:>10.2f}")
    
    # Summary
    print("-" * 90)
    print(f"{'TOTAL':<12} │ {weekly_df['Overnight'].sum():>10.2f} {weekly_df['Intraday'].sum():>12.2f} │ {weekly_df['Weekly Total'].sum():>8.2f} │")


def main():
    baskets = {
        'largecap_highbeta': 'data/baskets/basket_largecap_highbeta.txt',
        'largecap_lowbeta': 'data/baskets/basket_largecap_lowbeta.txt', 
        'midcap_highbeta': 'data/baskets/basket_midcap_highbeta.txt',
        'midcap_lowbeta': 'data/baskets/basket_midcap_lowbeta.txt',
        'smallcap_highbeta': 'data/baskets/basket_smallcap_highbeta.txt',
        'smallcap_lowbeta': 'data/baskets/basket_smallcap_lowbeta.txt',
    }
    
    print("="*90)
    print("OVERNIGHT VS INTRADAY ANALYSIS - WEEKLY BREAKDOWN WITH RUNNING TOTALS")
    print("Year: 2025")
    print("="*90)
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap)")
    print("  • Intraday:  Today's open → Today's close (session)")
    print("  • Running Totals: Cumulative sum from W01")
    
    all_results = {}
    
    for name, path in baskets.items():
        weekly, count = analyze_basket_weekly(name, path, year=2025)
        if weekly is not None:
            all_results[name] = weekly
            print_weekly_table(name, weekly, count)
            
            # Save to CSV
            output_file = f"reports/weekly_overnight_intraday_{name}_2025.csv"
            weekly.to_csv(output_file, index=False)
    
    # Comparative summary
    print("\n" + "="*90)
    print("COMPARATIVE SUMMARY - 2025 YTD")
    print("="*90)
    print(f"\n{'Basket':<25} {'Total Overnight':>15} {'Total Intraday':>15} {'YTD Return':>12} {'O/I Split':>15}")
    print("-" * 85)
    
    for name, weekly in all_results.items():
        total_overnight = weekly['Overnight'].sum()
        total_intraday = weekly['Intraday'].sum()
        ytd_return = weekly['Weekly Total'].sum()
        
        if ytd_return != 0:
            split = f"{total_overnight/ytd_return*100:.0f}% / {total_intraday/ytd_return*100:.0f}%"
        else:
            split = "N/A"
        
        print(f"{name:<25} {total_overnight:>14.2f}% {total_intraday:>14.2f}% {ytd_return:>11.2f}% {split:>15}")
    
    print("\n✅ CSV files saved to reports/ folder")


if __name__ == '__main__':
    main()
