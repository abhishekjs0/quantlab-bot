#!/usr/bin/env python3
"""
Dhan API Authentication - Get Fresh Access Token
Complete OAuth flow with automatic form filling and token capture
"""

import json
import os
import re
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
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
CALLBACK_PORT = 8765

# Global storage for captured token
captured_token = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Capture OAuth callback with tokenId"""

    def do_GET(self):
        global captured_token
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        if "tokenId" in query_params:
            token_id = query_params["tokenId"][0]
            captured_token = token_id
            print(f"\n✅ TokenId captured: {token_id[:30]}...")

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            response = "<html><body style='font-family:Arial;text-align:center;margin-top:50px;'><h1>Success!</h1><p>Token captured. You can close this window.</p></body></html>"
            self.wfile.write(response.encode())
        else:
            self.send_response(400)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def start_callback_server():
    """Start callback server on background thread"""
    def run():
        server = HTTPServer(("127.0.0.1", CALLBACK_PORT), CallbackHandler)
        server.handle_request()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print(f"🌐 Callback server started on port {CALLBACK_PORT}")


def exchange_token_id_for_access_token(token_id):
    """Exchange tokenId for accessToken using Dhan API"""
    print("\n� Exchanging tokenId for access token...")
    try:
        response = requests.post(
            f"{AUTH_BASE}/app/consumeApp-consent",
            headers={"app_id": API_KEY, "app_secret": API_SECRET},
            json={"tokenId": token_id},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        if "accessToken" in data:
            access_token = data["accessToken"]
            print(f"✅ Access token received: {access_token[:40]}...")
            return access_token
        else:
            print(f"❌ No access token in response: {data}")
            return None
    except Exception as e:
        print(f"❌ Exchange failed: {e}")
        return None


def save_token_to_env(access_token):
    """Save token to .env file"""
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


def main():
    print("\n" + "=" * 70)
    print("DHAN API - AUTOMATIC AUTHENTICATION")
    print("=" * 70)

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1

    # Step 1: Generate consent
    print("\n� STEP 1: Generating consent...")
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

    # Step 2: Start callback server
    start_callback_server()
    time.sleep(1)

    # Step 3: Generate TOTP
    print("\n🔄 STEP 2: Generating TOTP...")
    totp_code = pyotp.TOTP(TOTP_SECRET).now()
    print(f"✅ TOTP: {totp_code}")

    # Step 4: Open login page
    print("\n🔄 STEP 3: Opening login page...")
    login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
    webbrowser.open(login_url)

    print("⏳ Waiting for browser to load (3 seconds)...")
    time.sleep(3)

    # Step 5: Automate form
    print("\n🔄 STEP 4: Auto-filling login form...")
    try:
        # Click browser
        pyautogui.click(500, 300)
        time.sleep(1)

        # Enter mobile (USER_ID)
        print(f"   📝 Mobile: {USER_ID}")
        pyautogui.typewrite(USER_ID, interval=0.05)
        time.sleep(0.5)
        pyautogui.press("return")
        time.sleep(2)

        # Enter password
        print("   📝 Password: ****")
        pyautogui.typewrite(PASSWORD, interval=0.05)
        time.sleep(0.5)
        pyautogui.press("return")
        time.sleep(2)

        # Enter TOTP
        print(f"   📝 TOTP: {totp_code}")
        pyautogui.typewrite(totp_code, interval=0.05)
        time.sleep(0.5)
        pyautogui.press("return")

        print("\n✅ Form submitted!")

    except Exception as e:
        print(f"❌ Form fill error: {e}")
        sys.exit(1)

    # Step 6: Wait for callback
    print("\n⏳ Waiting for token callback (30 seconds)...")
    for i in range(30):
        if captured_token:
            break
        time.sleep(1)
        sys.stdout.write(f"\r   Waiting... {i+1}s")
        sys.stdout.flush()

    if not captured_token:
        print("\n❌ Token not captured from browser redirect")
        sys.exit(1)

    print("\n✅ Token captured from redirect!")

    # Step 7: Exchange token ID for access token
    access_token = exchange_token_id_for_access_token(captured_token)
    if not access_token:
        sys.exit(1)

    # Step 8: Save to .env
    save_token_to_env(access_token)

    print("\n" + "=" * 70)
    print("✅ AUTHENTICATION COMPLETE")
    print("=" * 70)
    print(f"\nToken: {access_token[:50]}...")
    print("Saved to: .env (DHAN_ACCESS_TOKEN)")


if __name__ == "__main__":
    main()
