#!/usr/bin/env python3
"""
Fetch all NSE indices weekly data from Groww API
"""

import hashlib
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR_WEEKLY = Path("data/cache/groww/weekly")
GROWW_MASTER_FILE = Path("data/groww-scrip-master-detailed.csv")

GROWW_API_KEY = os.getenv("GROWW_API_KEY", "")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "")

def generate_checksum(secret: str, timestamp: str) -> str:
    """Generate SHA256 checksum for Groww API authentication."""
    input_str = secret + timestamp
    return hashlib.sha256(input_str.encode('utf-8')).hexdigest()

def get_access_token():
    """Get a fresh access token from Groww API."""
    try:
        print("🔐 Getting access token...", end=" ", flush=True)
        
        timestamp = str(int(time.time()))
        checksum = generate_checksum(GROWW_API_SECRET, timestamp)
        
        token_url = "https://api.groww.in/v1/token/api/access"
        headers = {
            'Authorization': f'Bearer {GROWW_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        body = {
            'key_type': 'approval',
            'checksum': checksum,
            'timestamp': timestamp
        }
        
        response = requests.post(token_url, json=body, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"❌ {response.status_code}")
            return None
        
        data = response.json()
        access_token = data.get('token')
        
        if not access_token:
            print("❌ No token in response")
            return None
        
        print("✅")
        return access_token
        
    except Exception as e:
        print(f"❌ {e}")
        return None

def load_groww_indices():
    """Load all indices from Groww master file"""
    df = pd.read_csv(GROWW_MASTER_FILE, low_memory=False)
    indices = df[df['instrument_type'] == 'IDX']
    
    result = {}
    for _, row in indices.iterrows():
        token = row['exchange_token']
        symbol = row['trading_symbol']
        result[token] = symbol
    
    return result

def fetch_weekly_index_data(symbol, token, access_token, days_back=3650):
    """Fetch weekly data for an index from Groww API"""
    try:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        
        url = "https://api.groww.in/v1/historical/candle/range"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'X-API-VERSION': '1.0',
        }
        
        params = {
            'exchange': 'NSE',
            'segment': 'INDEX',  # Use INDEX segment for indices
            'trading_symbol': symbol,
            'start_time': start_time,
            'end_time': end_time,
            'interval_in_minutes': '10080'  # 1 week
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        if data.get('status') != 'SUCCESS':
            return None
        
        candles = data.get('payload', {}).get('candles', [])
        if not candles:
            return None
        
        # Parse candles: [timestamp, open, high, low, close, volume]
        parsed_data = []
        for c in candles:
            if len(c) >= 5:
                try:
                    ts = int(c[0])
                    dt = pd.Timestamp.fromtimestamp(ts, tz='UTC').tz_localize(None)
                    parsed_data.append({
                        'time': dt,
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': int(c[5]) if len(c) > 5 else 0,
                    })
                except (ValueError, IndexError, TypeError):
                    continue
        
        if not parsed_data:
            return None
        
        df = pd.DataFrame(parsed_data)
        df = df.sort_values('time').reset_index(drop=True)
        return df
        
    except Exception:
        return None

def main():
    print("=" * 70)
    print("🔄 FETCHING GROWW WEEKLY INDICES")
    print("=" * 70)
    
    # Check credentials
    if not GROWW_API_KEY or not GROWW_API_SECRET:
        print("❌ GROWW_API_KEY or GROWW_API_SECRET not set in .env")
        return
    
    # Create cache directory
    CACHE_DIR_WEEKLY.mkdir(parents=True, exist_ok=True)
    
    # Get access token
    access_token = get_access_token()
    if not access_token:
        print("❌ Failed to get access token")
        return
    
    # Load indices from master
    print("\n📊 Loading indices from Groww master file...")
    groww_indices = load_groww_indices()
    print(f"   Found: {len(groww_indices)} indices")
    
    # Fetch weekly data
    print(f"\n{'=' * 70}")
    print("📥 FETCHING GROWW WEEKLY DATA")
    print(f"{'=' * 70}")
    
    success = 0
    failed = []
    
    for token, symbol in groww_indices.items():
        # Check if already cached
        cache_file = CACHE_DIR_WEEKLY / f"groww_{token}_{symbol}_1w.csv"
        if cache_file.exists():
            print(f"  [{success+1}/{len(groww_indices)}] {symbol:30} ✓ cached")
            success += 1
            continue
        
        print(f"  [{success+1}/{len(groww_indices)}] {symbol:30} ", end="", flush=True)
        
        df = fetch_weekly_index_data(symbol, token, access_token)
        
        if df is not None and not df.empty:
            df.to_csv(cache_file, index=False)
            print(f"✅ {len(df)} weeks")
            success += 1
        else:
            print(f"❌ Failed")
            failed.append((token, symbol))
        
        time.sleep(0.5)
    
    print(f"\n{'=' * 70}")
    print(f"✅ Groww weekly: {success}/{len(groww_indices)} successful")
    if failed:
        print(f"❌ Failed ({len(failed)}):")
        for token, symbol in failed[:10]:
            print(f"   - {symbol} (token={token})")
        if len(failed) > 10:
            print(f"   ... and {len(failed) - 10} more")
    
    print(f"\n{'=' * 70}")
    print("📊 FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"   Weekly cache: {len(list(CACHE_DIR_WEEKLY.glob('groww_*_1w.csv')))} files")

if __name__ == "__main__":
    main()
