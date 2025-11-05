#!/usr/bin/env python3
"""
Dhan API - Integration Test
Verify token and fetch data
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

if not DHAN_ACCESS_TOKEN:
    print("\n❌ DHAN_ACCESS_TOKEN not in .env")
    print("   Run: python scripts/dhan_auth.py")
    sys.exit(1)

print("\n" + "=" * 70)
print("DHAN API - INTEGRATION TEST")
print("=" * 70)

print(f"\n✅ Token found: {DHAN_ACCESS_TOKEN[:40]}...")
print(f"✅ Client ID: {DHAN_CLIENT_ID}")

# Test data fetching
print("\n🔄 Testing data fetch...")
try:
    from scripts.dhan_data_fetcher import fetch_live_quote

    quote = fetch_live_quote("NSE_EQ|100")
    if quote:
        print("✅ Live quote fetch works!")
        print(f"   Response: {str(quote)[:100]}...")
    else:
        print("⚠️  Quote fetch returned empty")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("✅ TEST COMPLETE")
print("=" * 70)
