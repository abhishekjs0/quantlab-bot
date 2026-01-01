#!/usr/bin/env python3
"""
Comprehensive Index Analysis with Expiry Schedule
==================================================
1. Fetch daily data from Dhan for 6 indices
2. Perform 6 metrics analysis by day of week and days-to-expiry
3. Filter for last 5 years
4. Account for options expiry schedule rules (monthly & weekly)
5. Generate detailed reports
6. Compare across indices
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
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Dhan API
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
DHAN_BASE_URL = "https://api.dhan.co/v2"

# Index mapping to security IDs and exchanges
INDEX_CONFIG = {
    "NIFTY50": {
        "security_id": 13,
        "exchange": "NSE",
        "file": "dhan_13_NIFTY_50_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "BANKNIFTY": {
        "security_id": 14,
        "exchange": "NSE",
        "file": "dhan_14_BANKNIFTY_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "FINNIFTY": {
        "security_id": 15,
        "exchange": "NSE",
        "file": "dhan_15_FINNIFTY_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "NIFTY_MIDCAP_SELECT": {
        "security_id": 152,  # Approximate - may need adjustment
        "exchange": "NSE",
        "file": "dhan_152_NIFTY_MIDCAP_SELECT_1d.csv",
        "expiry_type": "monthly"
    },
    "SENSEX": {
        "security_id": 99926000,
        "exchange": "BSE",
        "file": "dhan_99926000_SENSEX_1d.csv",
        "expiry_type": "monthly_weekly"
    },
    "BANKEX": {
        "security_id": 99926009,
        "exchange": "BSE",
        "file": "dhan_99926009_BANKEX_1d.csv",
        "expiry_type": "monthly"
    }
}

CACHE_DIR = Path("data/cache/dhan/daily")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = Path("reports/indices_analysis")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def fetch_index_data_from_dhan(symbol, config):
    """Fetch index data from Dhan API and cache it."""
    filepath = CACHE_DIR / config["file"]
    
    # Return if already cached
    if filepath.exists():
        print(f"✅ {symbol} already cached")
        return filepath
    
    print(f"📥 Fetching {symbol} from Dhan API...")
    
    try:
        # Build Dhan API request for daily data
        # Endpoint: /historicalCharts
        params = {
            "securityId": config["security_id"],
            "exchangeTokenId": config["security_id"],
            "instrumentType": "INDEX",
            "expiryDate": "",
            "strikePrice": "",
            "optionType": "",
            "periodInMinutes": 1440,  # Daily
        }
        
        headers = {
            "Authorization": f"Bearer {DHAN_API_KEY}",
            "Accept": "application/json"
        }
        
        url = f"{DHAN_BASE_URL}/historicalCharts"
        response = requests.get(url, params=params, headers=headers, verify=False, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Parse candlestick data
            if "data" in data and "candlesticks" in data["data"]:
                candles = data["data"]["candlesticks"]
                records = []
                
                for candle in candles:
                    records.append({
                        "time": candle[0],  # timestamp in milliseconds
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": int(candle[5]) if len(candle) > 5 else 0
                    })
                
                df = pd.DataFrame(records)
                df.to_csv(filepath, index=False)
                print(f"✅ Saved {symbol}: {len(df)} candles to {filepath}")
                return filepath
        else:
            print(f"⚠️  API Error for {symbol}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"⚠️  Exception fetching {symbol}: {e}")
        return None

def load_cached_data(filepath):
    """Load cached Dhan data."""
    if filepath and filepath.exists():
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception as e:
            print(f"⚠️  Error loading {filepath}: {e}")
            return None
    return None

def get_monthly_expiry_dates(year_start=2020, year_end=2025):
    """
    Get monthly options expiry dates (last Thursday of month).
    Account for holiday shifts (if last Thursday is a holiday, move to previous trading day).
    """
    expiry_dates = []
    
    # NSE holidays (Thursdays that affect expiry)
    nse_holidays = {
        datetime(2021, 3, 11),   # Maha Shivaratri
        datetime(2021, 3, 29),   # Holi
        datetime(2021, 4, 2),    # Good Friday
        datetime(2021, 4, 21),   # Mahavir Jayanti
        datetime(2021, 4, 25),   # Ramzan Id
        datetime(2021, 8, 15),   # Independence Day (Thu)
        datetime(2021, 9, 10),   # Janmashtami
        datetime(2021, 10, 2),   # Gandhi Jayanti
        datetime(2021, 11, 5),   # Diwali
        datetime(2022, 1, 26),   # Republic Day
        datetime(2022, 3, 18),   # Holi
        datetime(2022, 4, 14),   # Ambedkar Jayanti
        datetime(2022, 8, 9),    # Janmashtami
        datetime(2022, 8, 31),   # Janmashtami (alternate)
        datetime(2022, 10, 5),   # Dussehra
        datetime(2022, 10, 24),  # Diwali
        datetime(2023, 3, 7),    # Maha Shivaratri
        datetime(2023, 3, 30),   # Holi
        datetime(2023, 4, 4),    # Eid ul-Fitr
        datetime(2023, 4, 14),   # Ambedkar Jayanti
        datetime(2023, 8, 15),   # Independence Day
        datetime(2023, 8, 30),   # Janmashtami
        datetime(2023, 9, 19),   # Milad-un-Nabi
        datetime(2023, 9, 28),   # Dussehra
        datetime(2023, 11, 12),  # Diwali
        datetime(2023, 11, 13),  # Diwali (alternate)
        datetime(2023, 11, 27),  # Guru Nanak Jayanti
        datetime(2024, 1, 26),   # Republic Day
        datetime(2024, 3, 8),    # Maha Shivaratri
        datetime(2024, 3, 25),   # Holi
        datetime(2024, 3, 29),   # Good Friday
        datetime(2024, 4, 11),   # Eid ul-Fitr
        datetime(2024, 4, 17),   # Ram Navami
        datetime(2024, 4, 21),   # Mahavir Jayanti
        datetime(2024, 8, 15),   # Independence Day
        datetime(2024, 8, 26),   # Janmashtami
        datetime(2024, 9, 16),   # Milad-un-Nabi
        datetime(2024, 10, 2),   # Gandhi Jayanti
        datetime(2024, 10, 12),  # Dussehra
        datetime(2024, 11, 1),   # Diwali
        datetime(2024, 11, 15),  # Guru Nanak Jayanti
        datetime(2025, 1, 26),   # Republic Day
        datetime(2025, 3, 8),    # Maha Shivaratri
        datetime(2025, 3, 31),   # Holi
        datetime(2025, 4, 18),   # Good Friday
    }
    
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            # Find last Thursday of month
            if month == 12:
                last_day = datetime(year, month, 31)
                next_month_first = datetime(year + 1, 1, 1)
            else:
                next_month_first = datetime(year, month + 1, 1)
                last_day = next_month_first - timedelta(days=1)
            
            # Find last Thursday
            last_thursday = None
            for day in range(last_day.day, 0, -1):
                d = datetime(year, month, day)
                if d.weekday() == 3:  # Thursday
                    last_thursday = d
                    break
            
            if last_thursday:
                # Check if it's a holiday, if so go back one trading day
                check_date = last_thursday
                while check_date in nse_holidays:
                    check_date -= timedelta(days=1)
                
                expiry_dates.append(check_date.date())
    
    return sorted(expiry_dates)

def get_weekly_expiry_dates(year_start=2020, year_end=2025):
    """
    Get weekly options expiry dates (every Wednesday for most indices).
    Account for holidays.
    """
    expiry_dates = []
    current = datetime(year_start, 1, 1)
    end = datetime(year_end, 12, 31)
    
    nse_holidays = get_nse_holidays_simple()
    
    while current <= end:
        # Find every Wednesday
        if current.weekday() == 2:  # Wednesday
            check_date = current
            # If holiday, move to previous trading day
            while check_date.date() in nse_holidays:
                check_date -= timedelta(days=1)
            expiry_dates.append(check_date.date())
        
        current += timedelta(days=1)
    
    return sorted(expiry_dates)

def get_nse_holidays_simple():
    """Return set of NSE holiday dates."""
    holidays = {
        datetime(2021, 3, 11).date(),
        datetime(2021, 3, 29).date(),
        datetime(2021, 4, 2).date(),
        datetime(2021, 4, 21).date(),
        datetime(2021, 4, 25).date(),
        datetime(2021, 8, 15).date(),
        datetime(2021, 9, 10).date(),
        datetime(2021, 10, 2).date(),
        datetime(2021, 11, 5).date(),
        datetime(2022, 1, 26).date(),
        datetime(2022, 3, 18).date(),
        datetime(2022, 4, 14).date(),
        datetime(2022, 8, 9).date(),
        datetime(2022, 8, 31).date(),
        datetime(2022, 10, 5).date(),
        datetime(2022, 10, 24).date(),
        datetime(2023, 3, 7).date(),
        datetime(2023, 3, 30).date(),
        datetime(2023, 4, 4).date(),
        datetime(2023, 4, 14).date(),
        datetime(2023, 8, 15).date(),
        datetime(2023, 8, 30).date(),
        datetime(2023, 9, 19).date(),
        datetime(2023, 9, 28).date(),
        datetime(2023, 11, 12).date(),
        datetime(2023, 11, 13).date(),
        datetime(2023, 11, 27).date(),
        datetime(2024, 1, 26).date(),
        datetime(2024, 3, 8).date(),
        datetime(2024, 3, 25).date(),
        datetime(2024, 3, 29).date(),
        datetime(2024, 4, 11).date(),
        datetime(2024, 4, 17).date(),
        datetime(2024, 4, 21).date(),
        datetime(2024, 8, 15).date(),
        datetime(2024, 8, 26).date(),
        datetime(2024, 9, 16).date(),
        datetime(2024, 10, 2).date(),
        datetime(2024, 10, 12).date(),
        datetime(2024, 11, 1).date(),
        datetime(2024, 11, 15).date(),
        datetime(2025, 1, 26).date(),
        datetime(2025, 3, 8).date(),
        datetime(2025, 3, 31).date(),
        datetime(2025, 4, 18).date(),
    }
    return holidays

def calculate_days_to_expiry(date, monthly_expiries, weekly_expiries):
    """Calculate days to next monthly and weekly expiry."""
    date = pd.Timestamp(date).date()
    
    # Find next monthly expiry
    days_to_monthly = None
    for expiry in monthly_expiries:
        if expiry > date:
            days_to_monthly = (expiry - date).days
            break
    
    # Find next weekly expiry
    days_to_weekly = None
    for expiry in weekly_expiries:
        if expiry > date:
            days_to_weekly = (expiry - date).days
            break
    
    return days_to_monthly, days_to_weekly

def analyze_index_ohlc(symbol, df):
    """
    6-Point Analysis:
    1. Intraday movement (Open-Close)
    2. Overnight movement (Close-Open next day)
    3. Days-to-expiry impact (monthly)
    4. Days-to-expiry impact (weekly)
    5. Day-of-week bias
    6. Volatility by day-of-week and expiry proximity
    """
    
    if df is None or len(df) == 0:
        print(f"⚠️  No data for {symbol}")
        return None
    
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp
    time_col = 'timestamp' if 'timestamp' in df.columns else ('time' if 'time' in df.columns else None)
    if not time_col:
        print(f"⚠️  No timestamp/time column for {symbol}")
        return None
    
    # Convert to datetime
    if df[time_col].dtype != 'datetime64[ns]':
        if df[time_col].max() > 100000000000:
            df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
        else:
            df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
    else:
        df['timestamp'] = df[time_col]
    
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['open', 'close']).sort_values('timestamp').reset_index(drop=True)
    
    # Filter 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df) == 0:
        print(f"⚠️  No 5-year data for {symbol}")
        return None
    
    print(f"✅ {symbol}: {len(df)} records for 5Y analysis")
    
    # Add metrics
    df['date'] = df['timestamp'].dt.date
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['weekday_num'] = df['timestamp'].dt.weekday
    
    # 1. Intraday movement (Open-Close)
    df['intraday_move'] = ((df['close'] - df['open']) / df['open'] * 100).round(4)
    
    # 2. Overnight movement (Close-Open next day)
    df['overnight_move'] = ((df['open'].shift(-1) - df['close']) / df['close'] * 100).round(4)
    
    # 3-4. Days to expiry
    monthly_expiries = get_monthly_expiry_dates()
    weekly_expiries = get_weekly_expiry_dates()
    
    days_to_expiry = []
    for date in df['date']:
        d_monthly, d_weekly = calculate_days_to_expiry(date, monthly_expiries, weekly_expiries)
        days_to_expiry.append({'days_to_monthly_expiry': d_monthly, 'days_to_weekly_expiry': d_weekly})
    
    df_expiry = pd.DataFrame(days_to_expiry)
    df = pd.concat([df, df_expiry], axis=1)
    
    # 5. High-Low range (volatility proxy)
    df['volatility'] = ((df['high'] - df['low']) / df['open'] * 100).round(4)
    
    return df

def generate_reports(symbol, df_analyzed):
    """Generate comprehensive reports."""
    
    if df_analyzed is None or len(df_analyzed) == 0:
        return
    
    # Save detailed CSV
    csv_path = REPORTS_DIR / f"{symbol}_5y_detailed.csv"
    df_analyzed.to_csv(csv_path, index=False)
    print(f"📊 Saved detailed analysis: {csv_path.name}")
    
    # Summary statistics by day of week
    summary_by_dow = df_analyzed.groupby('day_of_week').agg({
        'intraday_move': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'overnight_move': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'volatility': ['mean', 'median', 'std']
    }).round(4)
    
    summary_by_dow.columns = ['intraday_mean', 'intraday_median', 'intraday_std', 'intraday_win%',
                               'overnight_mean', 'overnight_median', 'overnight_std', 'overnight_win%',
                               'vol_mean', 'vol_median', 'vol_std']
    
    summary_path = REPORTS_DIR / f"{symbol}_5y_by_dow.csv"
    summary_by_dow.to_csv(summary_path)
    print(f"📊 Saved day-of-week summary: {summary_path.name}")
    
    # Summary by days to expiry
    df_with_expiry = df_analyzed.dropna(subset=['days_to_monthly_expiry'])
    if len(df_with_expiry) > 0:
        summary_by_expiry = df_with_expiry.groupby('days_to_monthly_expiry').agg({
            'intraday_move': ['mean', 'std', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0],
            'overnight_move': ['mean', 'std'],
            'volatility': ['mean']
        }).round(4)
        
        summary_by_expiry.columns = ['intraday_mean', 'intraday_std', 'intraday_win%',
                                      'overnight_mean', 'overnight_std', 'vol_mean']
        
        expiry_path = REPORTS_DIR / f"{symbol}_5y_by_expiry.csv"
        summary_by_expiry.to_csv(expiry_path)
        print(f"📊 Saved expiry summary: {expiry_path.name}")
    
    return summary_by_dow, df_analyzed

def main():
    print("=" * 80)
    print("6-POINT INDEX ANALYSIS: Fetching & Analyzing Daily Data")
    print("=" * 80)
    
    # Step 1: Fetch all indices from Dhan
    print("\n[1/3] FETCHING INDEX DATA FROM DHAN")
    print("-" * 80)
    
    fetched_files = {}
    
    # Try to fetch missing indices
    missing_indices = {k: v for k, v in INDEX_CONFIG.items() if k not in ["NIFTY50", "NIFTY200"]}
    
    if DHAN_API_KEY:
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_index_data_from_dhan, symbol, config): symbol 
                      for symbol, config in missing_indices.items()}
            
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    result = future.result()
                    if result:
                        fetched_files[symbol] = result
                except Exception as e:
                    print(f"⚠️  Error fetching {symbol}: {e}")
    else:
        print("⚠️  DHAN_API_KEY not set, skipping API fetches")
    
    # Load all available indices
    print("\n[2/3] LOADING CACHED DATA")
    print("-" * 80)
    
    all_data = {}
    for symbol, config in INDEX_CONFIG.items():
        filepath = CACHE_DIR / config["file"]
        df = load_cached_data(filepath)
        if df is not None:
            all_data[symbol] = df
            print(f"✅ Loaded {symbol}: {len(df)} candles")
        else:
            print(f"⚠️  Could not load {symbol}")
    
    # Step 2: Analyze
    print("\n[3/3] ANALYZING DATA (6-POINT METRICS)")
    print("-" * 80)
    
    all_analyzed = {}
    for symbol, df in all_data.items():
        df_analyzed = analyze_index_ohlc(symbol, df)
        if df_analyzed is not None:
            all_analyzed[symbol] = df_analyzed
            generate_reports(symbol, df_analyzed)
    
    # Create comparison summary
    print("\n" + "=" * 80)
    print("SUMMARY: All Indices Analysis Complete")
    print("=" * 80)
    print(f"✅ Analyzed {len(all_analyzed)} indices")
    print(f"✅ Reports saved to: {REPORTS_DIR}")
    print("=" * 80)

if __name__ == "__main__":
    main()
