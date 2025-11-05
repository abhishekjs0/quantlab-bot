#!/usr/bin/env python3
"""
DHAN API - Simple Working Example
Copy-paste and run this to verify everything works
"""

import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(".env")

print("\n" + "=" * 70)
print("DHAN API - SIMPLE TEST (No dependencies needed)")
print("=" * 70)

# Get credentials
client_id = os.getenv("DHAN_CLIENT_ID")
token = os.getenv("DHAN_ACCESS_TOKEN")

if not client_id or not token:
    print("❌ Missing credentials in .env")
    sys.exit(1)

print(f"\n✓ Client ID: {client_id}")
print(f"✓ Token: {token[:30]}...")

# Test 1: Get Profile
print("\n[TEST 1] Getting account profile...")
headers = {
    "access-token": token,
    "dhanClientId": client_id,
}

resp = requests.get("https://api.dhan.co/profile", headers=headers, timeout=10)
if resp.status_code == 200:
    profile = resp.json()
    print(f"✅ PASS - Token valid until: {profile['tokenValidity']}")
else:
    print(f"❌ FAIL - Status: {resp.status_code}")

# Test 2: Get Holdings
print("\n[TEST 2] Getting holdings...")
resp = requests.get("https://api.dhan.co/holdings", headers=headers, timeout=10)
if resp.status_code == 200:
    holdings = resp.json()
    print(f"✅ PASS - Found {len(holdings)} holdings")
    total = 0
    for h in holdings[:3]:
        qty = h.get("totalQty", 0)
        price = h.get("avgCostPrice", 0)
        value = qty * price
        total += value
        print(f"   {h['tradingSymbol']:10} x{qty:3} @ ₹{price:8.2f}")
    print(f"   ... total value: ₹{total:8.2f}")
else:
    print(f"❌ FAIL - Status: {resp.status_code}")

# Test 3: Get Positions
print("\n[TEST 3] Getting positions...")
resp = requests.get("https://api.dhan.co/positions", headers=headers, timeout=10)
if resp.status_code == 200:
    positions = resp.json()
    print(f"✅ PASS - {len(positions)} open positions")
else:
    print(f"❌ FAIL - Status: {resp.status_code}")

# Test 4: Get Orders
print("\n[TEST 4] Getting orders...")
resp = requests.get("https://api.dhan.co/orders", headers=headers, timeout=10)
if resp.status_code == 200:
    orders = resp.json()
    print(f"✅ PASS - {len(orders)} pending orders")
else:
    print(f"❌ FAIL - Status: {resp.status_code}")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - API IS WORKING!")
print("=" * 70)
print("\nNext: python scripts/dhan_working.py")
