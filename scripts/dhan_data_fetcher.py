#!/usr/bin/env python3
"""
Dhan API - Live Market Data Fetcher
Fetch live quotes and historical minute candles from Dhan
"""

import json
import os
from datetime import datetime, timedelta

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


def fetch_live_quote(exchange_token: str):
    """
    Fetch live market quote for a security

    Args:
        exchange_token: Format "NSE_EQ|100" for RELIANCE

    Returns:
        Quote data or None
    """
    try:
        response = requests.get(
            f"{API_BASE}/market/quotes/",
            params={"mode": "LTP", "exchangeTokens": exchange_token},
            headers=get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching live quote: {e}")
        return None


def fetch_historical_candles(
    exchange_token: str,
    interval_minutes: int = 1,
    days_back: int = 1,
):
    """
    Fetch historical candles from Dhan API

    Args:
        exchange_token: Format "NSE_EQ|100" for RELIANCE
        interval_minutes: 1 for minute candles, 5, 15, 30, 60, etc.
        days_back: How many days back to fetch

    Returns:
        List of candle dictionaries with OHLCV data
    """
    try:
        to_date = datetime.now().date()
        from_date = to_date - timedelta(days=days_back)

        payload = {
            "exchangeTokens": exchange_token,
            "fromDate": from_date.strftime("%Y-%m-%d"),
            "toDate": to_date.strftime("%Y-%m-%d"),
            "interval": interval_minutes,
        }

        response = requests.get(
            f"{API_BASE}/charts/",
            params=payload,
            headers=get_headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print(f"❌ Error fetching historical candles: {e}")
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
            f"{API_BASE}/profile",
            headers=get_headers(),
            timeout=10
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

    # Test 2: Fetch live quote for RELIANCE (security ID 100)
    print("\n🔄 TEST 2: Fetching live quote for RELIANCE...")
    quote = fetch_live_quote("NSE_EQ|100")
    if quote:
        print("✅ Live quote received!")
        print(f"   {json.dumps(quote, indent=2)}")
    else:
        print("❌ Failed to fetch live quote")

    # Test 3: Fetch minute candles for RELIANCE
    print("\n🔄 TEST 3: Fetching minute candles for RELIANCE (last 1 day)...")
    candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=1, days_back=1)
    if candles:
        if isinstance(candles, list):
            print(f"✅ Received {len(candles)} minute candles")
            if candles:
                print("\n   Latest candle:")
                print(f"   {json.dumps(candles[-1], indent=2)}")
        else:
            print(f"✅ Response received: {json.dumps(candles, indent=2)}")
    else:
        print("❌ Failed to fetch historical candles")

    # Test 4: Fetch 5-minute candles
    print("\n🔄 TEST 4: Fetching 5-minute candles for INFY (security ID 10188)...")
    candles = fetch_historical_candles("NSE_EQ|10188", interval_minutes=5, days_back=1)
    if candles:
        if isinstance(candles, list):
            print(f"✅ Received {len(candles)} 5-minute candles")
        else:
            print(f"✅ Response received: {json.dumps(candles, indent=2)}")
    else:
        print("❌ Failed to fetch 5-minute candles")

    print("\n" + "=" * 70)
    print("✅ TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_dhan_integration()
