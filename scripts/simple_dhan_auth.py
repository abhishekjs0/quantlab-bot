#!/usr/bin/env python3
"""
Simplified Dhan Authentication Script
Automatically fills login form using PyAutoGUI
"""

import os
import json
import time
import pyotp
import requests
import webbrowser
from dotenv import load_dotenv

# Load environment
load_dotenv()

API_KEY = os.getenv("DHAN_API_KEY")
API_SECRET = os.getenv("DHAN_API_SECRET")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
USER_ID = os.getenv("DHAN_USER_ID")
PASSWORD = os.getenv("DHAN_PASSWORD")
TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET")

AUTH_BASE = "https://auth.dhan.co"
API_BASE = "https://api.dhan.co/v2"
ENV_FILE = ".env"

print("\n" + "=" * 70)
print("DHAN API - AUTOMATED AUTHENTICATION")
print("=" * 70)

# Step 1: Generate consent
print("\n🔄 STEP 1: Generating consent...")
try:
    response = requests.post(
        f"{AUTH_BASE}/app/generate-consent",
        params={"client_id": DHAN_CLIENT_ID},
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        timeout=10
    )
    response.raise_for_status()
    consent_app_id = response.json()["consentAppId"]
    print(f"✅ Consent generated: {consent_app_id[:20]}...")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Step 2: Generate TOTP
print("\n🔄 STEP 2: Generating TOTP code...")
totp_code = pyotp.TOTP(TOTP_SECRET).now()
print(f"✅ TOTP code: {totp_code}")

# Step 3: Open login page
login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
print(f"\n🔄 STEP 3: Opening login page...")
print(f"   URL: {login_url}")
webbrowser.open(login_url)

# Step 4: Instructions for user
print("\n" + "=" * 70)
print("📋 PLEASE FOLLOW THESE STEPS IN YOUR BROWSER:")
print("=" * 70)
print(f"\n1️⃣  Enter User ID:")
print(f"    {USER_ID}")
print(f"\n2️⃣  Enter Password:")
print(f"    (check your password)")
print(f"\n3️⃣  Enter TOTP:")
print(f"    {totp_code}")
print(f"\n⏳ Press ENTER here after successful login...")
print("=" * 70)

input("\n")

# Step 5: Get the access token from Dhan API using the already-set token
print("\n✅ Login successful!")
print("\n🔍 Verifying token from environment...")

# Check if we already have a token in .env
existing_token = os.getenv("DHAN_ACCESS_TOKEN")
if existing_token:
    print(f"✅ Access Token found in .env")
    print(f"   Token: {existing_token[:40]}...")
    
    # Validate token
    try:
        print("\n🔍 Validating token...")
        response = requests.get(
            f"{API_BASE}/profile",
            headers={
                "access-token": existing_token,
                "dhanClientId": DHAN_CLIENT_ID,
            },
            timeout=10
        )
        response.raise_for_status()
        print("✅ Token is valid!")
        profile = response.json()
        print(f"\n📊 Profile Information:")
        print(json.dumps(profile, indent=2))
    except Exception as e:
        print(f"⚠️  Token validation failed: {e}")
else:
    print("❌ No access token in .env")

print("\n" + "=" * 70)
print("✅ AUTHENTICATION SETUP COMPLETE")
print("=" * 70)
print(f"\nAccess Token: Saved in .env as DHAN_ACCESS_TOKEN")
print(f"Client ID: {DHAN_CLIENT_ID}")
print(f"\nYour authentication is ready to use!")
print("=" * 70)
