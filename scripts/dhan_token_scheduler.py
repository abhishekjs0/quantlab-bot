#!/usr/bin/env python3
"""
Dhan API - Token Refresh Scheduler
Automatically refreshes token at 9:00 AM and 4:00 PM daily
"""

import os
import sys
import time
from datetime import datetime, timedelta

import schedule
from dotenv import load_dotenv

# Import the simple auth functions
sys.path.insert(0, os.path.dirname(__file__))
from dhan_simple_auth import (
    generate_consent,
    generate_totp,
    automate_login,
    save_token,
    validate_token,
)

# Load environment
load_dotenv()


def refresh_token():
    """Refresh the access token"""
    print("\n" + "=" * 70)
    print(f"🔄 TOKEN REFRESH STARTED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Step 1: Generate consent
    consent_app_id = generate_consent()
    if not consent_app_id:
        print("❌ Failed to generate consent")
        return False

    # Step 2: Generate TOTP
    totp_code = generate_totp()

    # Step 3: Automate login
    if not automate_login(consent_app_id, totp_code):
        print("❌ Failed to automate login")
        return False

    # Step 4: Wait for token to be saved
    print("\n⏳ Waiting for token to be saved (30 seconds)...")
    for i in range(30):
        time.sleep(1)
        # Reload .env
        load_dotenv(override=True)
        access_token = os.getenv("DHAN_ACCESS_TOKEN")

        if access_token and validate_token(access_token):
            print("\n" + "=" * 70)
            print("✅ TOKEN REFRESH SUCCESSFUL")
            print("=" * 70)
            print(f"   New token: {access_token[:50]}...")
            print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return True

    print("❌ Token refresh timed out")
    return False


def schedule_refreshes():
    """Schedule token refreshes at 9 AM and 4 PM"""
    schedule.every().day.at("09:00").do(refresh_token)
    schedule.every().day.at("16:00").do(refresh_token)

    print("\n" + "=" * 70)
    print("📅 DHAN TOKEN REFRESH SCHEDULER")
    print("=" * 70)
    print("\n✅ Token refresh scheduled for:")
    print("   • 09:00 (9:00 AM)")
    print("   • 16:00 (4:00 PM)")
    print("\nScheduler is running. Press Ctrl+C to stop.")
    print("=" * 70 + "\n")

    # Run the scheduler
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n\n⛔ Scheduler stopped")
            sys.exit(0)


if __name__ == "__main__":
    schedule_refreshes()
