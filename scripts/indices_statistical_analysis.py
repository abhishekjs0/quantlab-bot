#!/usr/bin/env python3
"""
Statistical Analysis of Index Options Expiry Patterns
=====================================================
Analyzes daily OHLC movements by day of week and days to expiry for multiple indices.
Uses cached Dhan data and Groww API for weekly data.
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Groww API Setup
GROWW_BASE_URL = "https://api.groww.in/v1/chart_feed"

# Available cached indices
CACHED_INDICES = {
    "NIFTY50": "dhan_13_NIFTY_50_1d.csv",
    "NIFTY200": "dhan_18_NIFTY_200_1d.csv",
}

CACHE_DIR = Path("data/cache/dhan/daily")

def load_cached_dhan_data(filename):
    """Load cached Dhan data."""
    filepath = CACHE_DIR / filename
    if filepath.exists():
        print(f"📂 Loading cached {filepath.name}...")
        df = pd.read_csv(filepath)
        return df
    return None

def analyze_ohlc_movements(symbol, df):
    """Analyze OHLC movements by day of week and days to expiry."""
    
    if df is None or len(df) == 0:
        print(f"⚠️  No data for {symbol}")
        return None
    
    # Standardize columns
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp - check for both 'timestamp' and 'time'
    time_col = None
    if 'timestamp' in df.columns:
        time_col = 'timestamp'
    elif 'time' in df.columns:
        time_col = 'time'
    else:
        print(f"⚠️  No timestamp/time column for {symbol}")
        return None
    
    try:
        # Try milliseconds first
        if df[time_col].dtype != 'datetime64[ns]':
            if df[time_col].max() > 100000000000:  # Milliseconds
                df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
        else:
            df['timestamp'] = df[time_col]
    except:
        df['timestamp'] = pd.to_datetime(df[time_col])
    
    # Ensure proper data types
    df['open'] = pd.to_numeric(df['open'], errors='coerce')
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df['high'] = pd.to_numeric(df['high'], errors='coerce')
    df['low'] = pd.to_numeric(df['low'], errors='coerce')
    
    df = df.dropna(subset=['open', 'close'])
    df = df.sort_values('timestamp').reset_index(drop=True)
    
    # Calculate movements
    df['open_close_movement'] = ((df['close'] - df['open']) / df['open'] * 100).round(4)
    df['close_open_movement_next'] = ((df['close'].shift(-1) - df['close']) / df['close'] * 100).round(4)
    
    # Day of week
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['weekday_num'] = df['timestamp'].dt.weekday
    df['date'] = df['timestamp'].dt.date
    
    # Filter for last 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df_5y = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df_5y) == 0:
        print(f"⚠️  No data in last 5 years for {symbol}")
        return None
    
    print(f"✅ Analyzing {len(df_5y)} records for {symbol} (5Y)")
    
    # Results container
    results = {
        'symbol': symbol,
        'total_records': len(df),
        'records_5y': len(df_5y),
        'date_range': f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}",
        'date_range_5y': f"{df_5y['timestamp'].min().date()} to {df_5y['timestamp'].max().date()}",
    }
    
    # Statistics by day of week
    results['open_close_stats'] = {}
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    for day in day_order:
        day_data = df_5y[df_5y['day_of_week'] == day]['open_close_movement']
        if len(day_data) > 0:
            results['open_close_stats'][day] = {
                'mean': round(day_data.mean(), 4),
                'median': round(day_data.median(), 4),
                'std': round(day_data.std(), 4),
                'min': round(day_data.min(), 4),
                'max': round(day_data.max(), 4),
                'positive_pct': round((day_data > 0).sum() / len(day_data) * 100, 2),
                'count': len(day_data)
            }
    
    # Close-Open movements
    results['close_open_by_dow'] = {}
    for day in day_order:
        day_data = df_5y[df_5y['day_of_week'] == day]['close_open_movement_next']
        if len(day_data) > 0:
            results['close_open_by_dow'][day] = {
                'mean': round(day_data.mean(), 4),
                'median': round(day_data.median(), 4),
                'count': len(day_data)
            }
    
    # Overall bias
    results['open_close_positive_pct'] = round((df_5y['open_close_movement'] > 0).sum() / len(df_5y) * 100, 2)
    results['close_open_positive_pct'] = round((df_5y['close_open_movement_next'] > 0).sum() / len(df_5y) * 100, 2)
    
    return results, df_5y

def print_report(results_dict):
    """Print comprehensive analysis report."""
    print("\n" + "="*100)
    print("INDEX STATISTICAL ANALYSIS - DAILY OHLC MOVEMENTS (Last 5 Years)")
    print("="*100)
    
    for symbol in sorted(results_dict.keys()):
        results = results_dict[symbol]
        
        if results is None:
            print(f"\n❌ {symbol}: No data available")
            continue
        
        print(f"\n{'='*100}")
        print(f"📊 {symbol}")
        print(f"{'='*100}")
        print(f"   Data Range: {results['date_range_5y']}")
        print(f"   Records: {results['records_5y']} (Total: {results['total_records']})")
        
        # Open-Close by DOW
        print(f"\n   🔵 OPEN-CLOSE MOVEMENT (%) BY DAY OF WEEK:")
        print(f"   {'Day':<12} {'Mean':>10} {'Median':>10} {'Std':>10} {'Count':>8} {'Positive %':>12}")
        print(f"   {'-'*65}")
        for day, stats in results['open_close_stats'].items():
            print(f"   {day:<12} {stats['mean']:>10.4f} {stats['median']:>10.4f} {stats['std']:>10.4f} {stats['count']:>8} {stats['positive_pct']:>11.2f}%")
        
        # Close-Open by DOW
        print(f"\n   🔵 CLOSE-OPEN GAP (%) BY DAY OF WEEK (next day opening):")
        print(f"   {'Day':<12} {'Mean':>10} {'Median':>10} {'Count':>8}")
        print(f"   {'-'*45}")
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']:
            if day in results['close_open_by_dow']:
                data = results['close_open_by_dow'][day]
                print(f"   {day:<12} {data['mean']:>10.4f} {data['median']:>10.4f} {int(data['count']):>8}")
        
        # Overall statistics
        print(f"\n   🔵 OVERALL STATISTICS:")
        print(f"      Open-Close Positive: {results['open_close_positive_pct']:.2f}%")
        print(f"      Close-Open Positive: {results['close_open_positive_pct']:.2f}%")

def main():
    print("\n🚀 INDEX STATISTICAL ANALYSIS - STARTING\n")
    
    results_dict = {}
    all_data = {}
    
    # Process cached Dhan data
    for symbol, filename in CACHED_INDICES.items():
        print(f"\n{'='*60}")
        print(f"Processing {symbol}")
        print(f"{'='*60}")
        
        df = load_cached_dhan_data(filename)
        if df is not None:
            result = analyze_ohlc_movements(symbol, df)
            if result is not None:
                results, df_5y = result
                results_dict[symbol] = results
                all_data[symbol] = df_5y
        else:
            results_dict[symbol] = None
    
    # Print report
    print_report(results_dict)
    
    # Save results
    print(f"\n{'='*100}")
    print("SAVING DETAILED ANALYSIS...")
    print(f"{'='*100}")
    
    output_dir = Path("reports/indices_analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for symbol, df in all_data.items():
        if df is not None:
            output_file = output_dir / f"{symbol}_5y_analysis.csv"
            df.to_csv(output_file, index=False)
            print(f"✅ Saved {symbol} detailed data to {output_file}")
    
    # Save summary as JSON
    summary_file = output_dir / "analysis_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(results_dict, f, indent=2, default=str)
    
    print(f"✅ Saved summary to {summary_file}")

if __name__ == "__main__":
    main()
