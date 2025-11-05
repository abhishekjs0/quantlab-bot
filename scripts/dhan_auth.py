#!/usr/bin/env python3
"""
Dhan API Authentication - End to End
Auto-fill form correctly in browser + capture tokenId
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

# Global to capture tokenId
captured_token_id = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Capture OAuth callback redirect"""

    def do_GET(self):
        global captured_token_id
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)

        if "tokenId" in params:
            captured_token_id = params["tokenId"][0]
            print(f"\n✅ TokenId captured from redirect: {captured_token_id[:40]}...")

            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            html = "<html><body><h1>Authentication Successful!</h1><p>Token captured. You can close this window.</p></body></html>"
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def start_callback_server():
    """Start HTTP server to capture callback"""
    def run_server():
        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), CallbackHandler)
        server.handle_request()

    thread = Thread(target=run_server, daemon=True)
    thread.start()
    print(f"🌐 Callback server listening on port {CALLBACK_PORT}")
    time.sleep(0.5)


print("\n" + "=" * 70)
print("DHAN API - END-TO-END AUTHENTICATION")
print("=" * 70)

# Step 1: Generate consent
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
    print(f"✅ Consent ID: {consent_app_id[:30]}...")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# Step 2: Generate TOTP
print("\n2️⃣  Generating TOTP...")
totp_code = pyotp.TOTP(TOTP_SECRET).now()
print(f"✅ TOTP Code: {totp_code}")

# Step 3: Start callback server
print("\n3️⃣  Starting callback server...")
start_callback_server()

# Step 4: Open login page
print("\n4️⃣  Opening login page in browser...")
login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
print(f"✅ Login URL: {login_url}")
webbrowser.open(login_url)
print(f"✅ Browser opened")
time.sleep(4)

# Step 5: Auto-fill form
print("\n5️⃣  Auto-filling login form...")
print("   IMPORTANT: Making sure to click in the form fields correctly")

try:
    # Click in the center of screen to ensure focus on browser
    pyautogui.click(640, 400)
    time.sleep(1)

    # Mobile field - type slowly and carefully
    print(f"   📝 Typing mobile: {USER_ID}")
    for digit in USER_ID:
        pyautogui.typewrite(digit, interval=0.08)
    time.sleep(1)

    # Press Tab to move to password field
    pyautogui.press("tab")
    time.sleep(1)

    # Password field
    print("   📝 Typing password")
    for char in PASSWORD:
        if char == "*":
            pyautogui.hotkey("shift", "8")
        elif char == "&":
            pyautogui.hotkey("shift", "7")
        elif char == "v":
            pyautogui.typewrite(char, interval=0.08)
        elif char == "L":
            pyautogui.hotkey("shift", "l")
        elif char == "b":
            pyautogui.typewrite(char, interval=0.08)
        elif char == "4":
            pyautogui.typewrite(char, interval=0.08)
        elif char == "n":
            pyautogui.typewrite(char, interval=0.08)
        else:
            pyautogui.typewrite(char, interval=0.08)
    time.sleep(1)

    # Press Tab to move to OTP field
    pyautogui.press("tab")
    time.sleep(1)

    # OTP field
    print(f"   📝 Typing TOTP: {totp_code}")
    for digit in totp_code:
        pyautogui.typewrite(digit, interval=0.08)
    time.sleep(1)

    # Submit form
    print("   ⏩ Pressing Enter to submit...")
    pyautogui.press("return")
    print("✅ Form submitted!")

except Exception as e:
    print(f"❌ Form fill error: {e}")
    sys.exit(1)

# Step 6: Wait for token callback
print("\n6️⃣  Waiting for token from browser redirect (30 seconds)...")
for i in range(30):
    if captured_token_id:
        break
    time.sleep(1)
    sys.stdout.write(f"\r   Waiting... {i+1}s")
    sys.stdout.flush()

if not captured_token_id:
    print("\n⚠️  Redirect not captured")
    print("   Checking browser for redirect URL...")
    print("\n   If browser shows a redirect URL with 'tokenId' parameter:")
    print("   1. Copy the tokenId value from the URL")
    print("   2. Paste it below\n")
    
    manual_token = input("Enter tokenId from browser (or press Enter to skip): ").strip()
    if manual_token:
        captured_token_id = manual_token
        print(f"✅ Token ID entered: {captured_token_id[:40]}...")
    else:
        print("❌ No token ID provided")
        sys.exit(1)
else:
    print("\n✅ Token received from redirect!")

# Step 7: Exchange tokenId for accessToken
print("\n7️⃣  Exchanging tokenId for access token...")
try:
    response = requests.post(
        f"{AUTH_BASE}/app/consumeApp-consent",
        headers={"app_id": API_KEY, "app_secret": API_SECRET},
        json={"tokenId": captured_token_id},
        timeout=10
    )
    response.raise_for_status()
    data = response.json()

    if "accessToken" not in data:
        print(f"❌ No access token in response: {data}")
        sys.exit(1)

    access_token = data["accessToken"]
    print(f"✅ Access Token: {access_token[:40]}...")

except Exception as e:
    print(f"❌ Exchange failed: {e}")
    sys.exit(1)

# Step 8: Save to .env
print("\n8️⃣  Saving to .env...")
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

print("✅ Token saved to .env")

print("\n" + "=" * 70)
print("✅ AUTHENTICATION COMPLETE")
print("=" * 70)
print(f"\n✓ Access Token: {access_token[:50]}...")
print("✓ Saved to: .env")
print("\nYou can now use:")
print("  python scripts/test_dhan.py")
print("  python scripts/fetch_data.py RELIANCE")
print("=" * 70)
