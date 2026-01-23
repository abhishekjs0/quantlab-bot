#!/usr/bin/env python3
"""
Fetch all NSE indices from Dhan (daily) and Groww (weekly) using master files
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

CACHE_DIR_DAILY = Path("data/cache/dhan/daily")
CACHE_DIR_WEEKLY = Path("data/cache/groww/weekly")

def load_dhan_indices():
    """Load all NSE indices from Dhan master file"""
    df = pd.read_csv('data/dhan-scrip-master-detailed.csv', low_memory=False)
    indices = df[(df['SEM_EXM_EXCH_ID'] == 'NSE') & (df['SEM_SEGMENT'] == 'I')]
    
    result = {}
    for _, row in indices.iterrows():
        secid = int(row['SEM_SMST_SECURITY_ID'])
        symbol = row['SEM_TRADING_SYMBOL']
        result[secid] = symbol
    
    return result

def load_groww_indices():
    """Load all indices from Groww master file"""
    df = pd.read_csv('data/groww-scrip-master-detailed.csv', low_memory=False)
    indices = df[df['instrument_type'] == 'IDX']
    
    result = {}
    for _, row in indices.iterrows():
        token = row['exchange_token']
        symbol = row['trading_symbol']
        desc = row['Description']
        result[token] = (symbol, desc)
    
    return result

def fetch_dhan_daily(secid, symbol, from_date, to_date):
    """Fetch daily data from Dhan"""
    payload = {
        "securityId": str(secid),
        "exchangeSegment": "IDX_I",
        "instrument": "INDEX",
        "expiryCode": 0,
        "oi": False,
        "fromDate": from_date.strftime("%Y-%m-%d"),
        "toDate": to_date.strftime("%Y-%m-%d"),
    }
    
    headers = {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
    }
    
    try:
        response = requests.post(
            f"{DHAN_BASE_URL}/charts/historical",
            json=payload,
            headers=headers,
            verify=False,
            timeout=10
        )
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if data and "timestamp" in data:
            df = pd.DataFrame({
                "time": data["timestamp"],
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
            })
            
            if not df.empty:
                df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
                df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
                return df.sort_values("time").reset_index(drop=True)
        
        return None
        
    except Exception as e:
        return None

def fetch_groww_weekly(token, symbol):
    """Fetch weekly data from Groww"""
    # Groww API seems to not support index historical data via public API
    # Keeping stub for future implementation
    return None

def main():
    print("=" * 70)
    print("🔄 FETCHING ALL NSE INDICES")
    print("=" * 70)
    
    # Create cache directories
    CACHE_DIR_DAILY.mkdir(parents=True, exist_ok=True)
    CACHE_DIR_WEEKLY.mkdir(parents=True, exist_ok=True)
    
    # Load indices from master files
    print("\n📊 Loading indices from master files...")
    dhan_indices = load_dhan_indices()
    groww_indices = load_groww_indices()
    
    print(f"   Dhan: {len(dhan_indices)} indices")
    print(f"   Groww: {len(groww_indices)} indices")
    
    # Fetch Dhan daily data
    print(f"\n{'=' * 70}")
    print("📥 FETCHING DHAN DAILY DATA")
    print(f"{'=' * 70}")
    
    to_date = datetime.now()
    from_date = to_date - timedelta(days=365*5)
    
    success = 0
    failed = []
    
    for secid, symbol in dhan_indices.items():
        # Check if already cached
        # Replace spaces, slashes and other invalid filename characters
        clean_symbol = symbol.replace(' ', '_').replace('/', '_').replace(':', '_')
        cache_file = CACHE_DIR_DAILY / f"dhan_{secid}_{clean_symbol}_1d.csv"
        if cache_file.exists():
            print(f"  [{success+1}/{len(dhan_indices)}] {symbol:30} ✓ cached")
            success += 1
            continue
        
        print(f"  [{success+1}/{len(dhan_indices)}] {symbol:30} ", end="", flush=True)
        
        df = fetch_dhan_daily(secid, symbol, from_date, to_date)
        
        if df is not None and not df.empty:
            df.to_csv(cache_file, index=False)
            print(f"✅ {len(df)} records")
            success += 1
        else:
            print(f"❌ Failed")
            failed.append((secid, symbol))
        
        time.sleep(0.5)
    
    print(f"\n{'=' * 70}")
    print(f"✅ Dhan daily: {success}/{len(dhan_indices)} successful")
    if failed:
        print(f"❌ Failed ({len(failed)}):")
        for secid, symbol in failed[:10]:
            print(f"   - {symbol} (SECID={secid})")
        if len(failed) > 10:
            print(f"   ... and {len(failed) - 10} more")
    
    print(f"\n{'=' * 70}")
    print("📊 FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Daily cache: {len(list(CACHE_DIR_DAILY.glob('dhan_*_1d.csv')))} files")
    print(f"   Weekly cache: {len(list(CACHE_DIR_WEEKLY.glob('groww_*_1w.csv')))} files")

if __name__ == "__main__":
    main()
