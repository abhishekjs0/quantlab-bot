#!/usr/bin/env python3
"""
Dhan API - Complete Authentication Flow
Guides user through login and captures token
"""

import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from urllib.parse import parse_qs, urlparse

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
CALLBACK_PORT = 9000

captured_token_id = None


class TokenHandler(BaseHTTPRequestHandler):
    """Capture redirect with tokenId"""

    def do_GET(self):
        global captured_token_id
        params = parse_qs(urlparse(self.path).query)

        if "tokenId" in params:
            captured_token_id = params["tokenId"][0]

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"Success! Token captured.")
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def start_server():
    """Start callback server"""
    def run():
        HTTPServer(("127.0.0.1", CALLBACK_PORT), TokenHandler).handle_request()

    Thread(target=run, daemon=True).start()


print("\n" + "=" * 70)
print("DHAN API - AUTHENTICATION")
print("=" * 70)

# Step 1: Generate consent
print("\n1. Generating consent...")
try:
    r = requests.post(
        f"{AUTH_BASE}/app/generate-consent",
        params={"client_id": DHAN_CLIENT_ID},
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        timeout=10
    )
    r.raise_for_status()
    consent_id = r.json()["consentAppId"]
    print(f"   ✅ Consent: {consent_id[:30]}...")
except Exception as e:
    print(f"   ❌ {e}")
    sys.exit(1)

# Step 2: Generate TOTP
print("\n2. Generating TOTP...")
totp_code = pyotp.TOTP(TOTP_SECRET).now()
print(f"   ✅ Code: {totp_code}")

# Step 3: Start server
print("\n3. Starting token capture server...")
start_server()
print(f"   ✅ Listening on port {CALLBACK_PORT}")

# Step 4: Open browser
print("\n4. Opening login page...")
login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_id}"
webbrowser.open(login_url)
print("   ✅ Browser opened - allow 5 seconds to load")
time.sleep(5)

# Step 5: Auto-fill form
print("\n5. Auto-filling form...")
try:
    pyautogui.click(640, 400)
    time.sleep(1)

    print(f"   📝 Mobile: {USER_ID}")
    pyautogui.typewrite(USER_ID)
    time.sleep(0.5)
    pyautogui.press("tab")
    time.sleep(1)

    print(f"   📝 Password")
    pyautogui.typewrite(PASSWORD)
    time.sleep(0.5)
    pyautogui.press("tab")
    time.sleep(1)

    print(f"   📝 TOTP: {totp_code}")
    pyautogui.typewrite(totp_code)
    time.sleep(0.5)

    print("   ⏩ Submitting...")
    pyautogui.press("return")
    print("   ✅ Form submitted")

except Exception as e:
    print(f"   ❌ {e}")
    sys.exit(1)

# Step 6: Wait for redirect
print("\n6. Waiting for token (30 seconds)...")
for i in range(30):
    if captured_token_id:
        print(f"\n   ✅ Token captured: {captured_token_id[:40]}...")
        break
    time.sleep(1)
    print(f"   {i+1}s", end="\r")

if not captured_token_id:
    print("\n   ⚠️  Auto-capture failed")
    print("   Enter tokenId from browser URL manually:")
    token_id = input("   tokenId: ").strip()
    if not token_id:
        print("   ❌ No token provided")
        sys.exit(1)
    captured_token_id = token_id

# Step 7: Exchange token
print("\n7. Exchanging tokenId for access token...")
try:
    r = requests.post(
        f"{AUTH_BASE}/app/consumeApp-consent",
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        json={"tokenId": captured_token_id},
        timeout=10
    )
    r.raise_for_status()
    data = r.json()

    if "accessToken" not in data:
        print(f"   ❌ {data}")
        sys.exit(1)

    access_token = data["accessToken"]
    print(f"   ✅ Access token: {access_token[:40]}...")

except Exception as e:
    print(f"   ❌ {e}")
    sys.exit(1)

# Step 8: Save token
print("\n8. Saving to .env...")
env_vars = {}
env_file = ".env"

if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key] = val

env_vars["DHAN_ACCESS_TOKEN"] = access_token

with open(env_file, "w") as f:
    for key, val in env_vars.items():
        f.write(f"{key}={val}\n")

print("   ✅ Saved")

print("\n" + "=" * 70)
print("✅ AUTHENTICATION COMPLETE")
print("=" * 70)
print(f"\nToken: {access_token[:60]}...")
print("\nTest with: python scripts/test_dhan.py")
print("=" * 70)
