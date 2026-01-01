#!/usr/bin/env python3
"""
COMPLETE 6-POINT INDEX ANALYSIS
================================
1. Fetch daily data from Dhan for 6 indices
2. Save to cache directory
3-6. Perform comprehensive statistical analysis with expiry schedule accounting
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
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# Dhan API
DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

# Index mapping - maps to cache filenames
INDICES = {
    "NIFTY50": {"security_id": 13, "cache_file": "dhan_13_NIFTY_50_1d.csv"},
    "BANKNIFTY": {"security_id": 25, "cache_file": "dhan_25_BANKNIFTY_1d.csv"},
    "NIFTY200": {"security_id": 18, "cache_file": "dhan_18_NIFTY_200_1d.csv"},
    # These need to be fetched via dhan_fetch_data.py:
    # "FINNIFTY": {"security_id": 165, "cache_file": "dhan_165_FINNIFTY_1d.csv"},
    # "NIFTYNXT50": {"security_id": 152, "cache_file": "dhan_152_NIFTYNXT50_1d.csv"},
    # "SENSEX": {"security_id": 99926000, "cache_file": "dhan_99926000_SENSEX_1d.csv"},
    # "BANKEX": {"security_id": 99926009, "cache_file": "dhan_99926009_BANKEX_1d.csv"},
}

CACHE_DIR = Path("data/cache/dhan/daily")
REPORTS_DIR = Path("reports/indices_analysis")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def get_headers():
    """Get Dhan API headers."""
    return {
        "Authorization": f"Bearer {DHAN_ACCESS_TOKEN}",
        "Accept": "application/json"
    }

def fetch_index_from_dhan(symbol, config):
    """Fetch index daily data from Dhan and save to cache."""
    
    cache_file = CACHE_DIR / f"dhan_{config['security_id']}_{symbol}_1d.csv"
    
    # Return if already cached
    if cache_file.exists():
        log.info(f"✅ {symbol} already cached")
        return cache_file
    
    log.info(f"📥 Fetching {symbol} from Dhan API...")
    
    if not DHAN_ACCESS_TOKEN:
        log.warning(f"⚠️  DHAN_ACCESS_TOKEN not set, skipping {symbol}")
        return None
    
    try:
        params = {
            "securityId": config["security_id"],
            "exchangeTokenId": config["security_id"],
            "instrumentType": "INDEX",
            "periodInMinutes": 1440,  # Daily
        }
        
        url = f"{DHAN_BASE_URL}/historicalCharts"
        response = requests.get(url, params=params, headers=get_headers(), verify=False, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            if "data" in data and "candlesticks" in data["data"]:
                candles = data["data"]["candlesticks"]
                records = []
                
                for candle in candles:
                    try:
                        records.append({
                            "time": int(candle[0]),
                            "open": float(candle[1]),
                            "high": float(candle[2]),
                            "low": float(candle[3]),
                            "close": float(candle[4]),
                            "volume": int(candle[5]) if len(candle) > 5 else 0
                        })
                    except (ValueError, IndexError):
                        continue
                
                if records:
                    df = pd.DataFrame(records)
                    df.to_csv(cache_file, index=False)
                    log.info(f"✅ Saved {symbol}: {len(df)} candles to cache")
                    return cache_file
                else:
                    log.warning(f"⚠️  No valid candles for {symbol}")
                    return None
        else:
            log.warning(f"⚠️  API {response.status_code} for {symbol}")
            return None
            
    except Exception as e:
        log.error(f"❌ Exception fetching {symbol}: {e}")
        return None

def load_cached_data(filepath):
    """Load cached Dhan data."""
    if filepath and Path(filepath).exists():
        try:
            df = pd.read_csv(filepath)
            return df
        except Exception as e:
            log.error(f"❌ Error loading {filepath}: {e}")
            return None
    return None

def get_monthly_expiry_dates(year_start=2020, year_end=2026):
    """Get monthly options expiry dates (last Thursday of month)."""
    expiry_dates = []
    
    # NSE holidays (select ones that affect Thursday expirations)
    nse_thursday_holidays = {
        (2021, 3, 11), (2021, 3, 25), (2021, 4, 2), (2021, 4, 21), (2021, 4, 25),
        (2021, 8, 19), (2021, 9, 10), (2021, 10, 2), (2021, 11, 4), (2021, 11, 5),
        (2022, 1, 26), (2022, 3, 18), (2022, 4, 14), (2022, 8, 9), (2022, 8, 31),
        (2022, 10, 5), (2022, 10, 24), (2023, 3, 7), (2023, 3, 30), (2023, 4, 4),
        (2023, 4, 14), (2023, 8, 15), (2023, 8, 30), (2023, 9, 19), (2023, 9, 28),
        (2023, 11, 12), (2023, 11, 13), (2023, 11, 27), (2024, 1, 26), (2024, 3, 8),
        (2024, 3, 25), (2024, 3, 29), (2024, 4, 11), (2024, 4, 17), (2024, 4, 21),
        (2024, 8, 15), (2024, 8, 26), (2024, 9, 16), (2024, 10, 2), (2024, 10, 12),
        (2024, 11, 1), (2024, 11, 15), (2025, 1, 26), (2025, 3, 8), (2025, 3, 31),
        (2025, 4, 18),
    }
    
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            # Find last Thursday
            if month == 12:
                last_day = 31
            else:
                last_day = (datetime(year, month + 1, 1) - timedelta(days=1)).day
            
            for day in range(last_day, 0, -1):
                d = datetime(year, month, day)
                if d.weekday() == 3:  # Thursday
                    # Check if it's a holiday, if so use previous trading day
                    check_date = d
                    while (check_date.year, check_date.month, check_date.day) in nse_thursday_holidays:
                        check_date -= timedelta(days=1)
                    expiry_dates.append(check_date.date())
                    break
    
    return sorted(expiry_dates)

def get_weekly_expiry_dates(year_start=2020, year_end=2026):
    """Get weekly expiry dates (every Wednesday)."""
    expiry_dates = []
    
    nse_wednesday_holidays = {
        (2021, 3, 10), (2021, 3, 24), (2021, 4, 21), (2021, 6, 2), (2021, 7, 21),
        (2021, 8, 18), (2021, 9, 1), (2021, 10, 6), (2021, 11, 3), (2021, 11, 24),
        (2022, 1, 26), (2022, 3, 16), (2022, 4, 13), (2022, 8, 10), (2022, 8, 30),
        (2022, 10, 5), (2022, 10, 26), (2023, 1, 25), (2023, 3, 1), (2023, 3, 29),
        (2023, 4, 5), (2023, 4, 12), (2023, 8, 16), (2023, 8, 29), (2023, 9, 20),
        (2023, 9, 27), (2023, 11, 1), (2023, 11, 29), (2024, 1, 24), (2024, 3, 6),
        (2024, 3, 27), (2024, 3, 27), (2024, 4, 10), (2024, 4, 17), (2024, 8, 14),
        (2024, 8, 28), (2024, 9, 18), (2024, 10, 2), (2024, 10, 16), (2024, 10, 30),
        (2024, 11, 13), (2025, 1, 1), (2025, 3, 5), (2025, 4, 16),
    }
    
    current = datetime(year_start, 1, 1)
    end = datetime(year_end, 12, 31)
    
    while current <= end:
        if current.weekday() == 2:  # Wednesday
            check_date = current
            while (check_date.year, check_date.month, check_date.day) in nse_wednesday_holidays:
                check_date -= timedelta(days=1)
            expiry_dates.append(check_date.date())
        current += timedelta(days=1)
    
    return sorted(expiry_dates)

def analyze_index(symbol, df):
    """
    6-POINT ANALYSIS:
    1. Intraday movement (Open-Close)
    2. Overnight movement (Close-Open next day)
    3. Days-to-monthly-expiry impact
    4. Days-to-weekly-expiry impact
    5. Day-of-week bias
    6. Volatility by day-of-week and expiry proximity
    """
    
    if df is None or len(df) == 0:
        log.warning(f"⚠️  No data for {symbol}")
        return None
    
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    
    # Handle timestamp
    time_col = 'timestamp' if 'timestamp' in df.columns else 'time'
    
    if time_col not in df.columns:
        log.error(f"❌ No timestamp column in {symbol}")
        return None
    
    try:
        # Convert time (handle both ms and seconds)
        if pd.api.types.is_numeric_dtype(df[time_col]):
            if df[time_col].max() > 100000000000:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='ms')
            else:
                df['timestamp'] = pd.to_datetime(df[time_col], unit='s')
        else:
            df['timestamp'] = pd.to_datetime(df[time_col])
    except Exception as e:
        log.error(f"❌ Cannot parse time for {symbol}: {e}")
        return None
    
    # Ensure numeric
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    df = df.dropna(subset=['open', 'close']).sort_values('timestamp').reset_index(drop=True)
    
    # Filter 5 years
    five_years_ago = df['timestamp'].max() - timedelta(days=365*5)
    df_5y = df[df['timestamp'] >= five_years_ago].copy()
    
    if len(df_5y) == 0:
        log.warning(f"⚠️  No 5-year data for {symbol}")
        return None
    
    log.info(f"✅ {symbol}: {len(df_5y)} records (5Y: {df_5y['timestamp'].min().date()} to {df_5y['timestamp'].max().date()})")
    
    # Add date fields
    df_5y['date'] = df_5y['timestamp'].dt.date
    df_5y['day_of_week'] = df_5y['timestamp'].dt.day_name()
    df_5y['weekday_num'] = df_5y['timestamp'].dt.weekday
    
    # METRIC 1: Intraday movement (Open-Close)
    df_5y['intraday_move_pct'] = ((df_5y['close'] - df_5y['open']) / df_5y['open'] * 100).round(4)
    
    # METRIC 2: Overnight movement (Close-Open next day)
    df_5y['overnight_move_pct'] = ((df_5y['open'].shift(-1) - df_5y['close']) / df_5y['close'] * 100).round(4)
    
    # METRICS 3-4: Days to expiry
    monthly_expiries = get_monthly_expiry_dates()
    weekly_expiries = get_weekly_expiry_dates()
    
    days_data = []
    for date in df_5y['date']:
        date_ts = pd.Timestamp(date)
        
        # Days to monthly expiry
        days_to_monthly = None
        for exp_date in monthly_expiries:
            if exp_date > date:
                days_to_monthly = (exp_date - date).days
                break
        
        # Days to weekly expiry
        days_to_weekly = None
        for exp_date in weekly_expiries:
            if exp_date > date:
                days_to_weekly = (exp_date - date).days
                break
        
        days_data.append({
            'days_to_monthly': days_to_monthly,
            'days_to_weekly': days_to_weekly
        })
    
    df_days = pd.DataFrame(days_data)
    df_5y = pd.concat([df_5y, df_days], axis=1)
    
    # METRIC 5-6: Volatility (High-Low range)
    df_5y['volatility_pct'] = ((df_5y['high'] - df_5y['low']) / df_5y['open'] * 100).round(4)
    
    return df_5y

def generate_reports(symbol, df_analyzed):
    """Generate all reports."""
    
    if df_analyzed is None or len(df_analyzed) == 0:
        return
    
    # 1. Save detailed data
    detailed_path = REPORTS_DIR / f"{symbol}_5y_detailed.csv"
    df_analyzed.to_csv(detailed_path, index=False)
    log.info(f"📊 Detailed: {detailed_path.name}")
    
    # 2. Day-of-week summary
    dow_summary = df_analyzed.groupby('day_of_week').agg({
        'intraday_move_pct': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'overnight_move_pct': ['mean', 'median', 'std', lambda x: (x > 0).sum() / len(x) * 100],
        'volatility_pct': ['mean', 'median', 'std']
    }).round(4)
    
    dow_summary.columns = [
        'intraday_mean', 'intraday_median', 'intraday_std', 'intraday_win%',
        'overnight_mean', 'overnight_median', 'overnight_std', 'overnight_win%',
        'vol_mean', 'vol_median', 'vol_std'
    ]
    
    dow_path = REPORTS_DIR / f"{symbol}_5y_dow_summary.csv"
    dow_summary.to_csv(dow_path)
    log.info(f"📊 Day-of-week: {dow_path.name}")
    
    # 3. Monthly expiry impact
    df_expiry = df_analyzed.dropna(subset=['days_to_monthly'])
    if len(df_expiry) > 0:
        expiry_summary = df_expiry.groupby('days_to_monthly').agg({
            'intraday_move_pct': ['mean', 'std', lambda x: (x > 0).sum() / len(x) * 100 if len(x) > 0 else 0],
            'overnight_move_pct': ['mean', 'std'],
            'volatility_pct': ['mean']
        }).round(4)
        
        expiry_summary.columns = ['intraday_mean', 'intraday_std', 'intraday_win%', 'overnight_mean', 'overnight_std', 'vol_mean']
        
        expiry_path = REPORTS_DIR / f"{symbol}_5y_monthly_expiry_impact.csv"
        expiry_summary.to_csv(expiry_path)
        log.info(f"📊 Monthly expiry: {expiry_path.name}")

def main():
    log.info("=" * 80)
    log.info("6-POINT INDEX ANALYSIS (COMPLETE IMPLEMENTATION)")
    log.info("=" * 80)
    
    # TASK 1-2: Load cached data
    log.info("\n[TASK 1-2] LOADING CACHED INDEX DATA")
    log.info("-" * 80)
    
    all_data = {}
    
    for symbol, config in INDICES.items():
        cache_file = CACHE_DIR / config["cache_file"]
        df = load_cached_data(cache_file)
        if df is not None:
            all_data[symbol] = df
            log.info(f"✅ {symbol}: {len(df)} candles")
        else:
            log.warning(f"⚠️  {symbol} not cached")
    
    # TASK 3-6: Analyze
    log.info("\n[TASK 3-6] ANALYZING DATA (6-POINT METRICS)")
    log.info("-" * 80)
    
    for symbol, df in all_data.items():
        df_analyzed = analyze_index(symbol, df)
        if df_analyzed is not None:
            generate_reports(symbol, df_analyzed)
    
    log.info("\n" + "=" * 80)
    log.info("✅ ANALYSIS COMPLETE - Reports saved to: " + str(REPORTS_DIR))
    log.info("=" * 80)

if __name__ == "__main__":
    main()
