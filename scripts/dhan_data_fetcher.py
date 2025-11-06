#!/usr/bin/env python3
"""
Dhan API - Live Market Data Fetcher
Fetch live quotes and historical minute candles from Dhan
"""

import csv
import json
import os
from datetime import datetime, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
API_BASE = "https://api.dhan.co/v2"

if not DHAN_ACCESS_TOKEN or not DHAN_CLIENT_ID:
    print("❌ Missing DHAN_ACCESS_TOKEN or DHAN_CLIENT_ID in .env")
    exit(1)


def get_headers():
    """Get common headers for Dhan API requests"""
    return {
        "access-token": DHAN_ACCESS_TOKEN,
        "dhanClientId": DHAN_CLIENT_ID,
        "Content-Type": "application/json",
    }


def fetch_ohlc_data(securities_dict: dict):
    """
    Fetch live OHLC data (quote mode) for securities

    Args:
        securities_dict: Format {"NSE_EQ": [1333, 100]}

    Returns:
        Quote data or None
    """
    try:
        payload = securities_dict
        response = requests.post(
            f"{API_BASE}/marketfeed/ohlc",
            json=payload,
            headers=get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching OHLC quote: {e}")
        return None


def fetch_intraday_minute_data(
    security_id: str,
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQUITY",
    interval: int = 1,
    days_back: int = 1,
):
    """
    Fetch intraday minute candles from Dhan API

    Args:
        security_id: Security ID (e.g., "100" for RELIANCE, "1023" for SBIN)
        exchange_segment: "NSE_EQ" for equity
        instrument_type: "EQUITY", "FUTCOM", etc.
        interval: 1, 5, 15, 25, or 60 minutes
        days_back: How many days back to fetch (max 5 trading days)

    Returns:
        Dict with status and data or None
    """
    if interval not in [1, 5, 15, 25, 60]:
        print(f"❌ Invalid interval: {interval}. Must be one of [1, 5, 15, 25, 60]")
        return None

    try:
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=days_back)

        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument_type,
            "interval": interval,
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d"),
        }

        response = requests.post(
            f"{API_BASE}/charts/intraday",
            json=payload,
            headers=get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"❌ Error fetching intraday minute data: {e}")
        return None


def fetch_historical_daily_data(
    security_id: str,
    exchange_segment: str = "NSE_EQ",
    instrument_type: str = "EQUITY",
    days_back: int = 365,
):
    """
    Fetch historical daily candles from Dhan API

    Args:
        security_id: Security ID (e.g., "100" for RELIANCE, "1023" for SBIN)
        exchange_segment: "NSE_EQ" for equity
        instrument_type: "EQUITY", "FUTCOM", etc.
        days_back: How many days back to fetch

    Returns:
        Dict with status and data or None
    """
    try:
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=days_back)

        payload = {
            "securityId": security_id,
            "exchangeSegment": exchange_segment,
            "instrument": instrument_type,
            "expiryCode": 0,
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d"),
        }

        response = requests.post(
            f"{API_BASE}/charts/historical",
            json=payload,
            headers=get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"❌ Error fetching historical daily data: {e}")
        return None


def save_minute_data_to_csv(response_data, security_id, interval, output_dir="data/cache"):
    """
    Save minute candle data to CSV format for backtesting

    Args:
        response_data: Response dict with open, high, low, close, volume, timestamp
        security_id: Security ID for filename
        interval: Minute interval (1, 5, 15, etc.) or "daily"
        output_dir: Directory to save CSV

    Returns:
        Path to saved CSV file or None
    """
    try:
        if not response_data or "open" not in response_data:
            print(f"❌ Invalid response data for security {security_id}")
            return None

        # Convert timestamps to datetime
        timestamps = pd.to_datetime(response_data["timestamp"], unit="s", utc=True)
        # Convert to Asia/Kolkata timezone
        timestamps = timestamps.tz_convert("Asia/Kolkata")
        # Format as strings
        dates = timestamps.strftime("%Y-%m-%d %H:%M:%S")

        # Create DataFrame
        df = pd.DataFrame(
            {
                "date": dates,
                "open": response_data["open"],
                "high": response_data["high"],
                "low": response_data["low"],
                "close": response_data["close"],
                "volume": response_data["volume"],
            }
        )

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        # Save to CSV
        filename = f"dhan_minute_{security_id}_{interval}m.csv"
        filepath = os.path.join(output_dir, filename)

        df.to_csv(filepath, index=False)
        print(f"✅ Saved {len(df)} {interval}-minute candles to {filepath}")
        print(f"   Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
        return filepath

    except Exception as e:
        print(f"❌ Error saving CSV: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_dhan_integration():
    """Test Dhan API integration"""
    print("\n" + "=" * 70)
    print("DHAN API - TEST DATA FETCHING")
    print("=" * 70)

    # Test 1: Validate connection
    print("\n🔍 TEST 1: Validating API connection...")
    try:
        response = requests.get(
            f"{API_BASE}/profile", headers=get_headers(), timeout=10
        )
        if response.status_code == 200:
            profile = response.json()
            print("✅ Connection successful!")
            print(f"   User: {profile.get('name', 'N/A')}")
            print(f"   DP ID: {profile.get('dpId', 'N/A')}")
        else:
            print(f"❌ Connection failed: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error: {e}")
        return

    # Test 2: Fetch live OHLC data for RELIANCE (security ID 100) and SBIN (security ID 1023)
    print("\n🔄 TEST 2: Fetching OHLC quote data...")
    quote = fetch_ohlc_data({"NSE_EQ": ["100", "1023"]})
    if quote:
        print("✅ OHLC data received!")
        print(f"   {json.dumps(quote, indent=2)}")
    else:
        print("❌ Failed to fetch OHLC data")

    # Test 3: Fetch minute candles for RELIANCE (security ID 100)
    print("\n🔄 TEST 3: Fetching 1-minute candles for RELIANCE (last 1 day)...")
    candles = fetch_intraday_minute_data("100", interval=1, days_back=1)
    if candles:
        print("✅ Response received!")
        csv_path = save_minute_data_to_csv(candles, "100_reliance", 1)
        print(f"   File: {csv_path}")
    else:
        print("❌ Failed to fetch minute candles")

    # Test 4: Fetch 5-minute candles for SBIN
    print("\n🔄 TEST 4: Fetching 5-minute candles for SBIN (security ID 1023)...")
    candles = fetch_intraday_minute_data("1023", interval=5, days_back=1)
    if candles:
        print("✅ Response received!")
        csv_path = save_minute_data_to_csv(candles, "1023_sbin", 5)
        print(f"   File: {csv_path}")
    else:
        print("❌ Failed to fetch 5-minute candles")

    # Test 5: Fetch historical daily data for INFY
    print("\n🔄 TEST 5: Fetching historical daily data for INFY (security ID 10188)...")
    candles = fetch_historical_daily_data("10188", days_back=30)
    if candles:
        print("✅ Response received!")
        csv_path = save_minute_data_to_csv(candles, "10188_infy", "daily")
        print(f"   File: {csv_path}")
    else:
        print("❌ Failed to fetch historical daily data")

    print("\n" + "=" * 70)
    print("✅ TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_dhan_integration()
