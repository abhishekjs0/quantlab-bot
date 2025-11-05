#!/usr/bin/env python3
"""
Quick Start: Dhan API Integration
==================================

This script demonstrates basic usage of Dhan API with QuantLab
"""

import os
from datetime import datetime

from dotenv import load_dotenv

# Load environment
load_dotenv()

print("\n" + "=" * 70)
print("DHAN API - QUICK START GUIDE")
print("=" * 70)

# Check token
access_token = os.getenv("DHAN_ACCESS_TOKEN")
if not access_token:
    print("\n❌ No access token found in .env")
    print("\n📋 STEP 1: Initial Authentication")
    print("   Run: python scripts/dhan_simple_auth.py")
    print("   This will open your browser and save the token to .env")
else:
    print(f"\n✅ Access token found: {access_token[:40]}...")

# Show available commands
print("\n" + "=" * 70)
print("📚 AVAILABLE COMMANDS")
print("=" * 70)

commands = {
    "Initial Setup": [
        ("python scripts/dhan_simple_auth.py", "Authenticate and get access token"),
    ],
    "Token Management": [
        ("python scripts/dhan_token_scheduler.py", "Auto-refresh token (9 AM & 4 PM)"),
    ],
    "Data Fetching": [
        ("python scripts/dhan_data_fetcher.py", "Test live quotes and candles"),
        ("python scripts/fetch_data.py RELIANCE", "Fetch RELIANCE historical data"),
        ("python scripts/fetch_data.py", "Fetch all basket symbols"),
    ],
}

for category, cmds in commands.items():
    print(f"\n{category}:")
    for cmd, desc in cmds:
        print(f"  ✦ {cmd}")
        print(f"    → {desc}")

# Show integration example
print("\n" + "=" * 70)
print("💻 PYTHON INTEGRATION EXAMPLE")
print("=" * 70)

example_code = """
from scripts.dhan_data_fetcher import fetch_historical_candles

# Fetch 1-minute candles for RELIANCE (last day)
candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=1, days_back=1)

# Use in your strategy
from core.engine import BacktestEngine
engine = BacktestEngine(candles)
results = engine.run()
"""

print(example_code)

print("\n" + "=" * 70)
print("📖 DOCUMENTATION")
print("=" * 70)
print("\nFor detailed guide, see: docs/DHAN_INTEGRATION.md")
print("For API reference, visit: https://dhanhq.co/docs/v2/")

print("\n" + "=" * 70)
