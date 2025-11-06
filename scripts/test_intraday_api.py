#!/usr/bin/env python3
"""
Test Dhan Intraday API - Fetch Real 1-Minute Candles

This script tests if we can fetch actual minute-level OHLCV data from Dhan API.
This is required for the multi-timeframe infrastructure to actually work.

The endpoint is: https://api.dhan.co/v2/charts/intraday

Run: python3 scripts/test_intraday_api.py
"""

import os
import sys
import json
from pathlib import Path

# Load .env manually to avoid dotenv issues
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

import requests

DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

print("\n" + "="*80)
print("DHAN INTRADAY API TEST - Real Minute Candles")
print("="*80)

if not DHAN_TOKEN or not DHAN_CLIENT_ID:
    print("❌ Missing credentials in .env")
    sys.exit(1)

print(f"✅ Token: {DHAN_TOKEN[:40]}...")
print(f"✅ Client ID: {DHAN_CLIENT_ID}")

headers = {
    "access-token": DHAN_TOKEN,
    "dhanClientId": DHAN_CLIENT_ID
}

print("\n" + "-"*80)
print("ATTEMPT 1: Historical Endpoint (v2 API)")
print("-"*80)

# Try /v2/charts/historical with minimal params
response = requests.get(
    "https://api.dhan.co/v2/charts/historical",
    headers=headers,
    params={
        "securityId": 1023,
        "fromDate": "2025-10-01",
        "toDate": "2025-11-05",
        "interval": "1d"
    },
    timeout=10
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Response type: {type(data)}")
    if isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        if "data" in data and isinstance(data["data"], list):
            candles = data["data"]
            print(f"✅ Got {len(candles)} candles!")
            if len(candles) > 0:
                print(f"\nFirst candle: {json.dumps(candles[0], indent=2)}")
        else:
            print(f"Full response: {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"Response: {data}")
else:
    print(f"❌ Error: {response.text[:300]}")

print("\n" + "-"*80)
print("ATTEMPT 2: Intraday Endpoint (v2 API)")
print("-"*80)

# Try /v2/charts/intraday
response = requests.get(
    "https://api.dhan.co/v2/charts/intraday",
    headers=headers,
    params={
        "securityId": 1023,
        "interval": 1,
        "fromDate": "2025-11-05",
        "toDate": "2025-11-05"
    },
    timeout=10
)

print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"✅ Got response!")
    print(f"Response type: {type(data)}")
    if isinstance(data, dict):
        if "data" in data:
            candles = data["data"]
            print(f"✅ Got {len(candles)} minute candles!")
            if len(candles) > 0:
                print(f"\nFirst candle: {json.dumps(candles[0], indent=2)}")
        else:
            print(f"Response: {json.dumps(data, indent=2)[:500]}")
    else:
        print(f"Response: {data}")
else:
    print(f"❌ Error: {response.text[:300]}")

print("\n" + "-"*80)
print("SUMMARY")
print("-"*80)
print("""
The multi-timeframe infrastructure requires:

1. ✅ DONE: Aggregation logic (core/multi_timeframe.py)
2. ✅ DONE: Test framework (tests/test_multi_timeframe.py)
3. ❌ TODO: Real minute data from Dhan API intraday endpoint

Current data in data/cache/ is DAILY OHLCV, not minute data.

To make multi-timeframe work:
- Need to fetch from /v2/charts/intraday endpoint
- Parse real 1-minute candles
- Cache them locally
- Test aggregation with real minute data
""")

print("="*80 + "\n")
