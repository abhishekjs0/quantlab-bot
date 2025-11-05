#!/usr/bin/env python3
"""
Dhan API Authentication
Auto-fill form + copy tokenId from browser
"""

import os
import sys
import time
import webbrowser

import pyautogui
import pyotp
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DHAN_API_KEY")
API_SECRET = os.getenv("DHAN_API_SECRET")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
USER_ID = os.getenv("DHAN_USER_ID", "")
PASSWORD = os.getenv("DHAN_PASSWORD", "")
TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET", "")

AUTH_BASE = "https://auth.dhan.co"

print("\n" + "=" * 70)
print("DHAN API - AUTHENTICATION")
print("=" * 70)

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

# Generate consent
print("\n1️⃣  Generating consent...")
try:
    response = requests.post(
        f"{AUTH_BASE}/app/generate-consent",
        params={"client_id": DHAN_CLIENT_ID},
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        timeout=10
    )
    response.raise_for_status()
    consent_app_id = response.json()["consentAppId"]
    print(f"✅ Consent: {consent_app_id[:30]}...")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Generate TOTP
print("2️⃣  Generating TOTP...")
totp_code = pyotp.TOTP(TOTP_SECRET).now()
print(f"✅ Code: {totp_code}")

# Open login page
print("3️⃣  Opening login page...")
login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
webbrowser.open(login_url)
time.sleep(3)

# Auto-fill form
print("4️⃣  Auto-filling form...")
try:
    pyautogui.click(500, 300)
    time.sleep(1)

    print(f"   Mobile: {USER_ID}")
    pyautogui.typewrite(USER_ID, interval=0.05)
    time.sleep(0.5)
    pyautogui.press("return")
    time.sleep(2)

    print("   Password: ****")
    pyautogui.typewrite(PASSWORD, interval=0.05)
    time.sleep(0.5)
    pyautogui.press("return")
    time.sleep(2)

    print(f"   TOTP: {totp_code}")
    pyautogui.typewrite(totp_code, interval=0.05)
    time.sleep(0.5)
    pyautogui.press("return")

    print("✅ Form submitted")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Get token ID
print("\n5️⃣  Getting tokenId...")
print("   After login, browser redirects to page with URL containing 'tokenId'")
print("   Copy the tokenId value from the URL\n")

token_id = input("Paste tokenId here: ").strip()
if not token_id:
    print("❌ No tokenId provided")
    sys.exit(1)

# Exchange for access token
print("\n6️⃣  Exchanging for access token...")
try:
    response = requests.post(
        f"{AUTH_BASE}/app/consumeApp-consent",
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        json={"tokenId": token_id},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    if "accessToken" not in data:
        print(f"❌ Response: {data}")
        sys.exit(1)

    access_token = data["accessToken"]
    print(f"✅ Token: {access_token[:40]}...")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Save to .env
print("\n7️⃣  Saving to .env...")
env_file = ".env"
env_vars = {}

if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value

env_vars["DHAN_ACCESS_TOKEN"] = access_token

with open(env_file, "w") as f:
    for key, value in env_vars.items():
        f.write(f"{key}={value}\n")

print("✅ Token saved")

print("\n" + "=" * 70)
print("✅ COMPLETE")
print("=" * 70)
