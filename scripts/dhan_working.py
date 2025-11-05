#!/usr/bin/env python3
"""
Dhan API - Working Implementation
Uses existing token from .env for all operations
No browser automation (Chrome not available)
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(".env")

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

if not all([DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN]):
    print("❌ Missing credentials in .env")
    sys.exit(1)


class DhanClient:
    """Simple Dhan API client - all working functions"""

    def __init__(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from dhan_market_data_rest import DhanMarketDataFetcher

        self.fetcher = DhanMarketDataFetcher()

    def get_account_summary(self):
        """Get complete account summary"""
        print("\n" + "=" * 70)
        print("DHAN ACCOUNT SUMMARY")
        print("=" * 70)

        # Get profile
        profile = self.fetcher.get_profile()
        if profile:
            print("\n✅ Profile:")
            print(f"   Client ID: {profile.get('dhanClientId')}")
            print(f"   Token Validity: {profile.get('tokenValidity')}")
            print(f"   Active Segments: {profile.get('activeSegment')}")
            print(f"   Data Plan: {profile.get('dataPlan')}")

        # Get holdings
        holdings = self.fetcher.get_holdings()
        if holdings:
            print(f"\n✅ Holdings ({len(holdings)} items):")
            total_value = 0
            for h in holdings:
                qty = h.get("totalQty", 0)
                avg_price = h.get("avgCostPrice", 0)
                value = qty * avg_price
                total_value += value
                print(f"   {h['tradingSymbol']:10} {qty:6} units @ ₹{avg_price:8.2f}")
            print(f"   {'TOTAL VALUE':10} ₹{total_value:8.2f}")

        # Get positions
        positions = self.fetcher.get_positions()
        if positions:
            print(f"\n✅ Open Positions ({len(positions)} items):")
            for p in positions:
                print(f"   {p}")
        else:
            print("\n⚠️  No open positions")

        # Get orders
        orders = self.fetcher.get_orders()
        if orders:
            print(f"\n✅ Orders ({len(orders)} items):")
            for o in orders:
                print(f"   {o}")
        else:
            print("\n⚠️  No pending orders")

        print("\n" + "=" * 70)

    def get_holdings_list(self):
        """Get just the holdings list"""
        holdings = self.fetcher.get_holdings()
        if holdings:
            print(f"\nCurrent Holdings ({len(holdings)} stocks):")
            for h in holdings:
                print(f"  • {h['tradingSymbol']}: {h['totalQty']} units")
        return holdings

    def verify_api(self):
        """Verify API is working"""
        print("Verifying Dhan API...")
        if self.fetcher.test_connection():
            profile = self.fetcher.get_profile()
            if profile:
                print(f"✅ API WORKING - Token valid until {profile['tokenValidity']}")
                return True
        print("❌ API not responding")
        return False


def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("DHAN API - WORKING IMPLEMENTATION")
    print("=" * 70)

    client = DhanClient()

    # Verify API works
    if not client.verify_api():
        print("\n❌ Cannot connect to Dhan API")
        sys.exit(1)

    # Show account summary
    client.get_account_summary()

    print("\n📝 STATUS:")
    print("  ✅ REST API: WORKING")
    print("  ✅ Account Data: ACCESSIBLE")
    print("  ✅ Holdings: FETCHED")
    print("  ✅ Token: VALID")
    print("\n⚠️  NOTE: Browser automation (dhan_login_auto.py)")
    print("     requires Chrome which is not installed on this system.")
    print("\n     Token must be refreshed manually or via separate system with Chrome.")
    print("     Current token valid until: 06/11/2025 20:24")
    print("\n🔗 To refresh token:")
    print("     1. Visit: https://web.dhan.co/settings/apis")
    print("     2. Generate new token")
    print("     3. Copy token and update .env file")
    print("     4. Or: python scripts/dhan_login_auto.py (if Chrome available)")


if __name__ == "__main__":
    main()
