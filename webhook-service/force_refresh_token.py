#!/usr/bin/env python3
"""
Force Refresh Dhan Access Token

This script ALWAYS generates a new access token via OAuth flow,
regardless of current token validity or expiry time.

Usage:
    python3 force_refresh_token.py

What it does:
    1. Loads Dhan credentials from .env
    2. Triggers OAuth flow (browser automation)
    3. Generates new access token
    4. Saves to Google Secret Manager (if configured)
    5. Saves to .env file (as fallback)

Requirements:
    - All Dhan credentials in .env file
    - Playwright installed (for browser automation)
    - Google Cloud project configured (for Secret Manager)
"""

import os
import sys
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dhan_auth import DhanAuth

def print_separator():
    print("\n" + "="*70)

def main():
    """Main function to force refresh token"""
    print_separator()
    print("  🔄 FORCE REFRESH DHAN ACCESS TOKEN")
    print_separator()
    
    # Load environment variables
    load_dotenv()
    
    # Validate required environment variables
    required_vars = [
        "DHAN_CLIENT_ID",
        "DHAN_API_KEY",
        "DHAN_API_SECRET",
        "DHAN_TOTP_SECRET",
        "DHAN_USER_ID",
        "DHAN_PASSWORD",
        "DHAN_PIN"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"\n❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Add these to your .env file")
        sys.exit(1)
    
    print("\n✓ All required credentials found in .env")
    
    # Initialize DhanAuth
    try:
        auth = DhanAuth(
            client_id=os.getenv("DHAN_CLIENT_ID"),
            api_key=os.getenv("DHAN_API_KEY"),
            api_secret=os.getenv("DHAN_API_SECRET"),
            totp_secret=os.getenv("DHAN_TOTP_SECRET"),
            user_id=os.getenv("DHAN_USER_ID"),
            password=os.getenv("DHAN_PASSWORD"),
            gcp_project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            secret_name=os.getenv("SECRET_NAME", "dhan-access-token")
        )
        print(f"✓ DhanAuth initialized")
        print(f"  Client ID: {auth.client_id}")
        print(f"  GCP Project: {auth.gcp_project or 'Not configured'}")
        print(f"  Secret Name: {auth.secret_name}")
    except Exception as e:
        print(f"\n❌ Failed to initialize DhanAuth: {e}")
        sys.exit(1)
    
    # Check current token status
    print_separator()
    print("  📊 CURRENT TOKEN STATUS")
    print_separator()
    
    cached = auth._load_from_secret_manager()
    if cached:
        token, expiry = cached
        time_remaining = (expiry - datetime.now()).total_seconds() / 3600
        print(f"\n✓ Current token found in Secret Manager")
        print(f"  Expiry: {expiry}")
        print(f"  Time remaining: {time_remaining:.2f} hours")
        print(f"  Status: {'✅ Valid' if time_remaining > 0 else '❌ Expired'}")
    else:
        print("\n⚠️  No token in Secret Manager")
        if auth._access_token:
            print(f"  Token in memory: {auth._access_token[:20]}...")
            if auth._token_expiry:
                time_remaining = (auth._token_expiry - datetime.now()).total_seconds() / 3600
                print(f"  Expiry: {auth._token_expiry}")
                print(f"  Time remaining: {time_remaining:.2f} hours")
        else:
            print("  No token in memory either")
    
    # Force refresh - no confirmation needed
    print_separator()
    print("  🚀 STARTING FORCE REFRESH")
    print_separator()
    print("\nThis will:")
    print("  1. Trigger OAuth flow (browser automation ~60 seconds)")
    print("  2. Generate a BRAND NEW access token")
    print("  3. Invalidate the current token")
    print("  4. Save new token to Secret Manager (PRIMARY) + .env (BACKUP)")
    print("\nThe OAuth flow will:")
    print("  - Launch headless browser")
    print("  - Log in with your credentials (auto-filled)")
    print("  - Complete 2FA with TOTP (auto-generated)")
    print("  - Retrieve new token")
    
    # Start immediately
    print("\n⏳ Generating new token (this may take ~60 seconds)...")
    print("   Browser automation in progress...\n")
    
    try:
        # Run force refresh
        new_token = asyncio.run(auth.force_refresh_token())
        
        if new_token:
            print_separator()
            print("  ✅ SUCCESS - NEW TOKEN GENERATED")
            print_separator()
            print(f"\n✓ New access token: {new_token[:30]}...{new_token[-10:]}")
            print(f"✓ Expiry: {auth._token_expiry}")
            
            if auth._token_expiry:
                time_remaining = (auth._token_expiry - datetime.now()).total_seconds() / 3600
                print(f"✓ Valid for: {time_remaining:.2f} hours")
            
            print("\n✓ Token saved to:")
            if auth._secret_client:
                print(f"  • Google Secret Manager: {auth.secret_name} (PRIMARY - source of truth)")
            print("  • .env file (BACKUP - local fallback)")
            
            print_separator()
            print("  🎉 TOKEN REFRESH COMPLETE")
            print_separator()
            print("\n✅ SOURCE OF TRUTH: Google Secret Manager")
            print("   All future operations will use this new token from Secret Manager")
            print("\nIf running on Cloud Run, restart the service to load it:")
            print("\n  gcloud run services update tradingview-webhook \\")
            print('    --update-env-vars="TOKEN_LOADED=$(date +%s)" \\')
            print("    --region=asia-south1 \\")
            print("    --project=tradingview-webhook-prod")
            
        else:
            print_separator()
            print("  ❌ FORCE REFRESH FAILED")
            print_separator()
            print("\nOAuth flow did not complete successfully.")
            print("\nPossible issues:")
            print("  • Browser automation timed out")
            print("  • Incorrect credentials")
            print("  • Network connectivity issues")
            print("  • Dhan API issues")
            print("\nCheck the logs above for more details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n❌ Refresh cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print_separator()
        print("  ❌ ERROR DURING REFRESH")
        print_separator()
        print(f"\n{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
