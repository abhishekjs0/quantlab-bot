#!/usr/bin/env python3
"""
Monthly Overnight vs Intraday Analysis - Full Historical Data
Analyzes all available data for each basket with monthly aggregation
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

def analyze_basket_monthly(basket_name, basket_path):
    """Analyze basket and return monthly summary with running totals."""
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
        
        if len(df) > 50:
            all_daily_data.append(df[['overnight_pct', 'intraday_pct', 'total_pct']])
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
    daily_avg['num_stocks'] = combined.iloc[:, overnight_cols].notna().sum(axis=1)
    
    # Add month info
    daily_avg['year'] = daily_avg.index.year
    daily_avg['month'] = daily_avg.index.month
    daily_avg['year_month'] = daily_avg['year'].astype(str) + '-' + daily_avg['month'].astype(str).str.zfill(2)
    
    # Aggregate to monthly - sum of daily returns
    monthly = daily_avg.groupby('year_month').agg({
        'overnight': 'sum',
        'intraday': 'sum',
        'total': 'sum',
        'num_stocks': 'mean'
    }).reset_index()
    
    monthly.columns = ['Year-Month', 'Overnight', 'Intraday', 'Monthly Total', 'Avg Stocks']
    
    # Sort by month
    monthly = monthly.sort_values('Year-Month').reset_index(drop=True)
    
    # Calculate running totals
    monthly['Running Overnight'] = monthly['Overnight'].cumsum()
    monthly['Running Intraday'] = monthly['Intraday'].cumsum()
    monthly['Running Total'] = monthly['Monthly Total'].cumsum()
    
    return monthly, loaded_count


def print_monthly_summary(basket_name, monthly_df, symbol_count):
    """Print formatted monthly summary - last 24 months and yearly totals."""
    print(f"\n{'='*100}")
    print(f"{basket_name.upper()} - Monthly Overnight vs Intraday ({symbol_count} symbols)")
    print(f"{'='*100}")
    
    # Show data range
    print(f"Data Range: {monthly_df['Year-Month'].iloc[0]} to {monthly_df['Year-Month'].iloc[-1]}")
    print(f"Total Months: {len(monthly_df)}")
    
    # Yearly summary
    monthly_df['Year'] = monthly_df['Year-Month'].str[:4].astype(int)
    yearly = monthly_df.groupby('Year').agg({
        'Overnight': 'sum',
        'Intraday': 'sum',
        'Monthly Total': 'sum'
    }).reset_index()
    
    print(f"\n{'─'*100}")
    print("YEARLY SUMMARY")
    print(f"{'─'*100}")
    print(f"{'Year':<8} │ {'Overnight':>12} {'Intraday':>12} │ {'Annual Total':>14} │ {'O/I Split':>20}")
    print(f"{'─'*100}")
    
    for _, row in yearly.iterrows():
        total = row['Monthly Total']
        if total != 0:
            o_pct = row['Overnight'] / total * 100
            i_pct = row['Intraday'] / total * 100
            split = f"{o_pct:.0f}% / {i_pct:.0f}%"
        else:
            split = "N/A"
        print(f"{int(row['Year']):<8} │ {row['Overnight']:>11.2f}% {row['Intraday']:>11.2f}% │ {row['Monthly Total']:>13.2f}% │ {split:>20}")
    
    # Totals
    print(f"{'─'*100}")
    total_overnight = monthly_df['Overnight'].sum()
    total_intraday = monthly_df['Intraday'].sum()
    total_return = monthly_df['Monthly Total'].sum()
    if total_return != 0:
        split = f"{total_overnight/total_return*100:.0f}% / {total_intraday/total_return*100:.0f}%"
    else:
        split = "N/A"
    print(f"{'TOTAL':<8} │ {total_overnight:>11.2f}% {total_intraday:>11.2f}% │ {total_return:>13.2f}% │ {split:>20}")
    
    # Last 12 months detail
    print(f"\n{'─'*100}")
    print("LAST 12 MONTHS DETAIL")
    print(f"{'─'*100}")
    print(f"{'Year-Month':<12} │ {'Overnight':>10} {'Intraday':>10} │ {'Monthly':>10} │ {'Run.Over':>10} {'Run.Intra':>10} {'Run.Tot':>10}")
    print(f"{'─'*100}")
    
    last_12 = monthly_df.tail(12)
    for _, row in last_12.iterrows():
        print(f"{row['Year-Month']:<12} │ {row['Overnight']:>10.2f} {row['Intraday']:>10.2f} │ {row['Monthly Total']:>10.2f} │ {row['Running Overnight']:>10.2f} {row['Running Intraday']:>10.2f} {row['Running Total']:>10.2f}")
    
    return yearly


def main():
    baskets = {
        'largecap_highbeta': 'data/baskets/basket_largecap_highbeta.txt',
        'largecap_lowbeta': 'data/baskets/basket_largecap_lowbeta.txt', 
        'midcap_highbeta': 'data/baskets/basket_midcap_highbeta.txt',
        'midcap_lowbeta': 'data/baskets/basket_midcap_lowbeta.txt',
        'smallcap_highbeta': 'data/baskets/basket_smallcap_highbeta.txt',
        'smallcap_lowbeta': 'data/baskets/basket_smallcap_lowbeta.txt',
    }
    
    print("="*100)
    print("OVERNIGHT VS INTRADAY ANALYSIS - MONTHLY BREAKDOWN (ALL AVAILABLE DATA)")
    print("="*100)
    print("\nDefinitions:")
    print("  • Overnight: Previous close → Today's open (gap)")
    print("  • Intraday:  Today's open → Today's close (session)")
    print("  • Running Totals: Cumulative sum from first month")
    
    all_results = {}
    all_yearly = {}
    
    for name, path in baskets.items():
        monthly, count = analyze_basket_monthly(name, path)
        if monthly is not None:
            all_results[name] = monthly
            yearly = print_monthly_summary(name, monthly, count)
            all_yearly[name] = yearly
            
            # Save to CSV
            output_file = f"reports/monthly_overnight_intraday_{name}_all.csv"
            monthly.to_csv(output_file, index=False)
    
    # Comparative summary across all years
    print("\n" + "="*100)
    print("COMPARATIVE SUMMARY - ALL AVAILABLE DATA")
    print("="*100)
    print(f"\n{'Basket':<25} {'Data Range':<20} {'Total Overnight':>15} {'Total Intraday':>15} {'Total Return':>14} {'O/I Split':>18}")
    print("-" * 110)
    
    for name, monthly in all_results.items():
        date_range = f"{monthly['Year-Month'].iloc[0]} to {monthly['Year-Month'].iloc[-1]}"
        total_overnight = monthly['Overnight'].sum()
        total_intraday = monthly['Intraday'].sum()
        total_return = monthly['Monthly Total'].sum()
        
        if total_return != 0:
            split = f"{total_overnight/total_return*100:.0f}% / {total_intraday/total_return*100:.0f}%"
        else:
            split = "N/A"
        
        print(f"{name:<25} {date_range:<20} {total_overnight:>14.2f}% {total_intraday:>14.2f}% {total_return:>13.2f}% {split:>18}")
    
    # Year-by-year comparison across baskets
    print("\n" + "="*100)
    print("YEAR-BY-YEAR COMPARISON (Annual Returns)")
    print("="*100)
    
    # Get all years
    all_years = set()
    for name, yearly in all_yearly.items():
        all_years.update(yearly['Year'].tolist())
    all_years = sorted(all_years)
    
    # Header
    print(f"\n{'Year':<8}", end="")
    for name in baskets.keys():
        short_name = name.replace('cap_', '').replace('beta', '')[:12]
        print(f" │ {short_name:>12}", end="")
    print()
    print("-" * (8 + 15 * len(baskets)))
    
    # Data rows
    for year in all_years:
        print(f"{year:<8}", end="")
        for name in baskets.keys():
            if name in all_yearly:
                yearly = all_yearly[name]
                row = yearly[yearly['Year'] == year]
                if not row.empty:
                    val = row['Monthly Total'].iloc[0]
                    print(f" │ {val:>11.2f}%", end="")
                else:
                    print(f" │ {'N/A':>12}", end="")
            else:
                print(f" │ {'N/A':>12}", end="")
        print()
    
    print("\n✅ CSV files saved to reports/ folder")


if __name__ == '__main__':
    main()
