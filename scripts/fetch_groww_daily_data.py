#!/usr/bin/env python3
"""
Groww Historical Daily Data Fetcher - Production Ready
=======================================================
Fetches daily OHLCV data from Groww API and caches locally.
Format: groww_{EXCHANGE_TOKEN}_{SYMBOL}_1d.csv
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set, Dict

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_DIR = Path("data/cache/groww/daily")
GROWW_MASTER_FILE = Path("data/groww-scrip-master-detailed.csv")

# Groww API credentials from .env
GROWW_API_KEY = os.getenv("GROWW_API_KEY", "")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "")

BASKETS = {
    "main": "data/baskets/basket_main.txt",
    "large": "data/baskets/basket_large.txt",
    "mid": "data/baskets/basket_mid.txt",
    "small": "data/baskets/basket_small.txt",
    "test": "data/baskets/basket_test.txt",
    "debug": "data/baskets/basket_debug.txt",
    "midcap_highbeta": "data/baskets/basket_midcap_highbeta.txt",
    "largecap_highbeta": "data/baskets/basket_largecap_highbeta.txt",
    "smallcap_highbeta": "data/baskets/basket_smallcap_highbeta.txt",
    "largecap_lowbeta": "data/baskets/basket_largecap_lowbeta.txt",
    "midcap_lowbeta": "data/baskets/basket_midcap_lowbeta.txt",
    "smallcap_lowbeta": "data/baskets/basket_smallcap_lowbeta.txt",
}

DAILY_DATA_CUTOFF = datetime(2015, 11, 9)  # Historical data available from this date


def check_credentials():
    """Check if Groww API credentials are set."""
    if not GROWW_API_KEY:
        print("❌ GROWW_API_KEY not found in .env")
        return False
    if not GROWW_API_SECRET:
        print("❌ GROWW_API_SECRET not found in .env")
        return False
    return True


def generate_checksum(secret: str, timestamp: str) -> str:
    """Generate SHA256 checksum for Groww API authentication."""
    input_str = secret + timestamp
    return hashlib.sha256(input_str.encode('utf-8')).hexdigest()


def get_access_token() -> Optional[str]:
    """Get a fresh access token using the checksum/approval flow.
    
    This uses the Groww API Key + Secret to generate a temporary access token
    with back_test (historical data) permissions.
    
    Returns:
        Access token string or None if authentication fails
    """
    try:
        print("🔐 Getting access token via checksum flow...")
        
        # Generate timestamp and checksum
        timestamp = str(int(time.time()))
        checksum = generate_checksum(GROWW_API_SECRET, timestamp)
        
        # Request new access token
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
            print(f"❌ Token generation failed: {response.status_code}")
            return None
        
        data = response.json()
        
        # Handle both response formats: with or without status field
        if data.get('status') == 'FAILURE':
            error_msg = data.get('error', {}).get('message', 'Unknown error')
            print(f"❌ Token generation failed: {error_msg}")
            return None
        
        # If we have a 'token' field, the request was successful
        access_token = data.get('token')
        if not access_token:
            print(f"❌ Token generation failed: No token in response")
            print(f"   Response: {data}")
            return None
        
        expiry = data.get('expiry')
        print(f"✅ Got access token (expires: {expiry})")
        
        return access_token
        
    except Exception as e:
        print(f"❌ Token generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def load_basket_symbols(basket_name: str) -> Set[str]:
    """Load symbol list from basket file."""
    basket_file = BASKETS.get(basket_name)
    if not basket_file or not Path(basket_file).exists():
        print(f"❌ Basket file not found: {basket_file}")
        return set()
    
    symbols = set()
    try:
        with open(basket_file, 'r') as f:
            for line in f:
                symbol = line.strip().upper()
                if symbol:
                    symbols.add(symbol)
    except Exception as e:
        print(f"❌ Error reading basket {basket_name}: {e}")
        return set()
    
    return symbols


def get_symbol_info(symbol: str) -> Optional[Dict]:
    """Get symbol information from Groww master file.
    
    Returns dict with: exchange_token, groww_symbol, segment
    """
    try:
        if not GROWW_MASTER_FILE.exists():
            print(f"⚠️  Master file not found: {GROWW_MASTER_FILE}")
            return None
        
        df = pd.read_csv(GROWW_MASTER_FILE, low_memory=False)
        
        # Normalize column names to lowercase for consistency
        df.columns = df.columns.str.lower()
        
        # Filter for CASH segment (stocks) with matching trading symbol
        # trading_symbol is what we use (e.g., "RELIANCE")
        matches = df[
            (df['trading_symbol'] == symbol) & 
            (df['segment'] == 'CASH') &
            (df['exchange'] == 'NSE')
        ]
        
        if matches.empty:
            return None
        
        row = matches.iloc[0]
        return {
            'exchange_token': str(int(row['exchange_token'])),
            'groww_symbol': row['groww_symbol'],
            'segment': row['segment'],
            'exchange': row['exchange'],
        }
        
    except Exception as e:
        print(f"⚠️  Error looking up {symbol}: {e}")
        return None


def fetch_daily_data(
    symbol: str,
    exchange_token: str,
    access_token: str,
    days_back: int = 3650  # ~10 years
) -> Optional[pd.DataFrame]:
    """Fetch daily OHLCV data from Groww API.
    
    Args:
        symbol: Trading symbol (e.g., "RELIANCE")
        exchange_token: Groww exchange token
        access_token: Valid Groww access token for API requests
        days_back: Days of historical data to fetch
    
    Returns:
        DataFrame with daily OHLC data or None if fetch fails
    """
    try:
        end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        start_time = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"  📡 Fetching {symbol}...", end=" ", flush=True)
        
        # Prepare API request
        url = "https://api.groww.in/v1/historical/candle/range"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'X-API-VERSION': '1.0',
        }
        
        params = {
            'exchange': 'NSE',
            'segment': 'CASH',
            'trading_symbol': symbol,
            'start_time': start_time,
            'end_time': end_time,
            'interval_in_minutes': '1440'  # 1 day = 1440 minutes
        }
        
        # Fetch daily candles
        response = requests.get(url, headers=headers, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ {response.status_code}")
            return None
        
        data = response.json()
        if data.get('status') != 'SUCCESS':
            error_msg = data.get('error', {}).get('message', 'Unknown error')
            print(f"❌ {error_msg}")
            return None
        
        candles = data.get('payload', {}).get('candles', [])
        if not candles:
            print("⚠️  No data")
            return None
        
        # Parse candles: [timestamp (epoch seconds), open, high, low, close, volume, ...]
        data = []
        for c in candles:
            if len(c) >= 5:
                try:
                    ts = int(c[0])
                    dt = pd.Timestamp.fromtimestamp(ts, tz='UTC').tz_localize(None)
                    data.append({
                        'time': dt,
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': int(c[5]) if len(c) > 5 else 0,
                    })
                except (ValueError, IndexError, TypeError):
                    continue
        
        if not data:
            print("⚠️  Parse error")
            return None
        
        df = pd.DataFrame(data)
        df = df.sort_values('time').reset_index(drop=True)
        
        print(f"✅ {len(df)} days")
        return df
        
    except Exception as e:
        error_str = str(e)
        
        # Provide helpful error messages for common issues
        if "403" in error_str or "forbidden" in error_str.lower():
            print(f"❌ Access Denied (403)")
            print("\n⚠️  PERMISSION ISSUE DETECTED:")
            print("   Your Groww API key doesn't have permission to access historical data.")
            print("   Fix: https://groww.in/trade-api/api-keys")
            print("   1. Check your API key has 'Historical Data' or 'Backtesting' permissions")
            print("   2. If not, enable it or create a new key with those permissions")
            print("   3. Generate a new access token after enabling permissions")
            return None
        
        print(f"❌ {e}")
        return None


def save_daily_data(df: pd.DataFrame, exchange_token: str, symbol: str) -> bool:
    """Save daily data to cache.
    
    Format: groww_{EXCHANGE_TOKEN}_{SYMBOL}_1d.csv
    """
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        output_file = CACHE_DIR / f"groww_{exchange_token}_{symbol}_1d.csv"
        
        # Prepare data for save
        df_save = df[['time', 'open', 'high', 'low', 'close', 'volume']].copy()
        df_save['time'] = pd.to_datetime(df_save['time'])
        
        # Remove timezone info if present
        if df_save['time'].dt.tz is not None:
            df_save['time'] = df_save['time'].dt.tz_localize(None)
        
        # Save with time as index
        df_save.set_index('time').to_csv(output_file)
        
        return True
        
    except Exception as e:
        print(f"    ❌ Save error: {e}")
        return False


def fetch_basket_daily_data(basket_name: str, access_token: str) -> Dict[str, int]:
    """Fetch daily data for all symbols in a basket.
    
    Args:
        basket_name: Name of the basket to fetch
        access_token: Valid Groww access token
    
    Returns: dict with success/error counts
    """
    symbols = load_basket_symbols(basket_name)
    if not symbols:
        print(f"❌ No symbols found in basket: {basket_name}")
        return {'success': 0, 'error': 0}
    
    print(f"\n📊 Fetching {len(symbols)} symbols from basket '{basket_name}'...\n")
    
    success_count = 0
    error_count = 0
    
    for symbol in sorted(symbols):
        # Get symbol info from master file
        info = get_symbol_info(symbol)
        if not info:
            print(f"  ⚠️  {symbol}: Not found in master file")
            error_count += 1
            continue
        
        # Fetch daily data
        df = fetch_daily_data(
            symbol=symbol,
            exchange_token=info['exchange_token'],
            access_token=access_token,
        )
        
        if df is not None:
            # Save to cache
            if save_daily_data(df, info['exchange_token'], symbol):
                success_count += 1
            else:
                error_count += 1
        else:
            error_count += 1
    
    return {'success': success_count, 'error': error_count}


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(
        description="Fetch daily OHLCV data from Groww API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch specific basket
  python3 fetch_groww_daily_data.py --basket main
  
  # Fetch specific symbols
  python3 fetch_groww_daily_data.py --symbols RELIANCE,INFY,TCS
  
  # Fetch all baskets
  python3 fetch_groww_daily_data.py --all-baskets
        """,
    )
    
    parser.add_argument("--basket", choices=list(BASKETS.keys()), 
                       help="Basket name to fetch")
    parser.add_argument("--symbols", help="Comma-separated symbols (e.g., RELIANCE,INFY)")
    parser.add_argument("--all-baskets", action="store_true", 
                       help="Fetch all baskets")
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("GROWW DAILY DATA FETCHER")
    print("="*70)
    
    # Check credentials
    if not check_credentials():
        return 1
    
    # Get access token
    access_token = get_access_token()
    if not access_token:
        return 1
    
    # Fetch data based on arguments
    results = {}
    
    if args.all_baskets:
        for basket_name in BASKETS.keys():
            results[basket_name] = fetch_basket_daily_data(basket_name, access_token)
    elif args.basket:
        results[args.basket] = fetch_basket_daily_data(args.basket, access_token)
    elif args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
        print(f"\n📊 Fetching {len(symbols)} symbols...\n")
        success_count = 0
        error_count = 0
        for symbol in symbols:
            info = get_symbol_info(symbol)
            if info:
                df = fetch_daily_data(symbol, info['exchange_token'], access_token)
                if df is not None and save_daily_data(df, info['exchange_token'], symbol):
                    success_count += 1
                else:
                    error_count += 1
            else:
                error_count += 1
        results['manual'] = {'success': success_count, 'error': error_count}
    else:
        parser.print_help()
        return 1
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    total_success = sum(r.get('success', 0) for r in results.values())
    total_error = sum(r.get('error', 0) for r in results.values())
    
    for basket_name, result in results.items():
        print(f"  {basket_name:20} ✅ {result['success']:4d}  ❌ {result['error']:4d}")
    
    print(f"\n  {'TOTAL':20} ✅ {total_success:4d}  ❌ {total_error:4d}")
    print("\n📁 Daily data stored in data/cache/groww/daily/ as groww_{EXCHANGE_TOKEN}_{SYMBOL}_1d.csv")
    print("="*70 + "\n")
    
    return 0 if total_error == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
