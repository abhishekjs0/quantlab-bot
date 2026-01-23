#!/usr/bin/env python3
"""
Fetch all NSE indices data from Dhan (daily) and Groww (weekly)
"""

import argparse
import json
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
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

GROWW_BASE_URL = "https://api.groww.in"

CACHE_DIR_DAILY = Path("data/cache/dhan/daily")
CACHE_DIR_WEEKLY = Path("data/cache/groww/weekly")

# NSE Indices with their SECID
INDICES = {
    2: "NIFTY",
    13: "NIFTY",  # Use this one
    15: "NIFTY PVT BANK",
    17: "NIFTY 100",
    18: "NIFTY 200",
    19: "NIFTY 500",
    20: "NIFTYMCAP50",
    21: "INDIA VIX",
    22: "NIFTY SML100 FREE",
    25: "BANKNIFTY",
    27: "FINNIFTY",
    28: "NIFTY FMCG",
    29: "NIFTYIT",
    30: "NIFTY MEDIA",
    31: "NIFTY METAL",
    32: "NIFTY PHARMA",
    33: "NIFTY PSU BANK",
    34: "NIFTY REALTY",
    37: "NIFTY MID100 FREE",
    38: "NIFTYNXT50",
    443: "NIFTY TOTAL MKT",
    444: "NIFTY MICROCAP250",
}

def sanitize_symbol(symbol):
    """Sanitize symbol for filename"""
    return symbol.upper().replace(" ", "_").replace(",", "")

def fetch_dhan_index_data(secid, symbol, from_date, to_date):
    """Fetch index data from Dhan API"""
    payload = {
        "securityId": str(secid),
        "exchangeSegment": "NSE_INDEX",  # For indices
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
        response.raise_for_status()
        
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
        print(f"  ❌ Error fetching {symbol} (SECID={secid}): {e}")
        return None

def fetch_all_dhan_indices(from_date=None, to_date=None):
    """Fetch all indices from Dhan"""
    if to_date is None:
        to_date = datetime.now()
    if from_date is None:
        from_date = to_date - timedelta(days=365*5)  # 5 years
    
    CACHE_DIR_DAILY.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 70)
    print("🔄 Fetching NSE Indices from Dhan (Daily)")
    print("=" * 70)
    print(f"Date range: {from_date.date()} to {to_date.date()}")
    print(f"Total indices to fetch: {len(INDICES) - 1}\n")  # -1 for duplicate NIFTY
    
    success = 0
    failed = []
    
    # Remove duplicate NIFTY (SECID=2)
    indices_to_fetch = {k: v for k, v in INDICES.items() if k != 2}
    
    for secid, symbol in indices_to_fetch.items():
        print(f"  📥 Fetching {symbol} (SECID={secid})...", end="", flush=True)
        
        df = fetch_dhan_index_data(secid, symbol, from_date, to_date)
        
        if df is not None and not df.empty:
            sanitized = sanitize_symbol(symbol)
            cache_file = CACHE_DIR_DAILY / f"dhan_{secid}_{sanitized}_1d.csv"
            df.to_csv(cache_file, index=False)
            print(f" ✅ {len(df)} records")
            success += 1
        else:
            print(f" ⚠️  No data")
            failed.append((secid, symbol))
        
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n✅ Dhan daily: {success} ✅ / {len(failed)} ❌")
    if failed:
        print("  Failed indices:")
        for secid, symbol in failed:
            print(f"    - {symbol} (SECID={secid})")
    
    return success, failed

def fetch_groww_index_data(symbol_id):
    """Fetch weekly index data from Groww"""
    url = f"{GROWW_BASE_URL}/v1/charts/getChartData"
    
    params = {
        "token": symbol_id,
        "resolution": "weekly",
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get("status") == 200 and data.get("data"):
            candles = data["data"]["candles"]
            
            df = pd.DataFrame(candles)
            if not df.empty:
                df.columns = ["time", "open", "high", "low", "close", "volume"]
                df["time"] = pd.to_datetime(df["time"], unit='s')
                df = df.sort_values("time").reset_index(drop=True)
                
                return df
        
        return None
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

def fetch_all_groww_indices():
    """Fetch all indices from Groww"""
    CACHE_DIR_WEEKLY.mkdir(parents=True, exist_ok=True)
    
    # Groww symbol IDs for indices
    GROWW_INDICES = {
        "0_nifty": "NIFTY_50",
        "0_niftynxt50": "NIFTY_NEXT_50",
        "0_nifty100": "NIFTY_100",
        "0_nifty200": "NIFTY_200",
        "0_nifty500": "NIFTY_500",
        "0_niftymidcap50": "NIFTY_MIDCAP_50",
        "0_niftymidcap100": "NIFTY_MIDCAP_100",
        "0_niftysmallcap50": "NIFTY_SMALLCAP_50",
        "0_niftysmallcap100": "NIFTY_SMALLCAP_100",
        "0_banknifty": "NIFTY_BANK",
        "0_finnifty": "FINNIFTY",
        "0_niftypharma": "NIFTY_PHARMA",
        "0_niftyit": "NIFTY_IT",
        "0_niftymetal": "NIFTY_METAL",
        "0_niftyfmcg": "NIFTY_FMCG",
        "0_niftyrealty": "NIFTY_REALTY",
        "0_indiavix": "INDIA_VIX",
    }
    
    print("\n" + "=" * 70)
    print("🔄 Fetching NSE Indices from Groww (Weekly)")
    print("=" * 70)
    print(f"Total indices to fetch: {len(GROWW_INDICES)}\n")
    
    success = 0
    failed = []
    
    for symbol_id, display_name in GROWW_INDICES.items():
        print(f"  📥 Fetching {display_name}...", end="", flush=True)
        
        df = fetch_groww_index_data(symbol_id)
        
        if df is not None and not df.empty:
            sanitized = display_name.replace(" ", "_")
            cache_file = CACHE_DIR_WEEKLY / f"groww_{symbol_id}_{sanitized}_1w.csv"
            df.to_csv(cache_file, index=False)
            print(f" ✅ {len(df)} records")
            success += 1
        else:
            print(f" ⚠️  No data")
            failed.append((symbol_id, display_name))
        
        time.sleep(0.5)  # Rate limiting
    
    print(f"\n✅ Groww weekly: {success} ✅ / {len(failed)} ❌")
    if failed:
        print("  Failed indices:")
        for symbol_id, display_name in failed:
            print(f"    - {display_name}")
    
    return success, failed

def main():
    parser = argparse.ArgumentParser(description="Fetch NSE indices data from Dhan and Groww")
    parser.add_argument("--dhan-only", action="store_true", help="Fetch only from Dhan (daily)")
    parser.add_argument("--groww-only", action="store_true", help="Fetch only from Groww (weekly)")
    parser.add_argument("--from-date", help="From date (YYYY-MM-DD)")
    parser.add_argument("--to-date", help="To date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    from_date = None
    to_date = None
    
    if args.from_date:
        from_date = datetime.strptime(args.from_date, "%Y-%m-%d")
    if args.to_date:
        to_date = datetime.strptime(args.to_date, "%Y-%m-%d")
    
    dhan_success = dhan_failed = 0
    groww_success = groww_failed = 0
    
    if not args.groww_only:
        dhan_success, dhan_failed = fetch_all_dhan_indices(from_date, to_date)
    
    if not args.dhan_only:
        groww_success, groww_failed = fetch_all_groww_indices()
    
    print("\n" + "=" * 70)
    print(f"📊 Summary: Dhan {dhan_success} ✅ / {len(dhan_failed)} ❌, Groww {groww_success} ✅ / {len(groww_failed)} ❌")
    print("=" * 70)

if __name__ == "__main__":
    main()
