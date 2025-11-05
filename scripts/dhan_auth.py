#!/usr/bin/env python3
"""
Dhan API - Automated Authentication Script
3-Step OAuth-like flow with TOTP support & Callback Server

Usage:
    python3 dhan_auth.py       # Full login flow
"""

import http.server
import json
import os
import pickle
import socketserver
import threading
import time
import urllib.parse
import webbrowser
from datetime import datetime

import pyotp
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# ====================================================================================
# CONFIGURATION - Load from .env
# ====================================================================================

API_KEY = os.getenv("DHAN_API_KEY", "")
API_SECRET = os.getenv("DHAN_API_SECRET", "")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
USER_ID = os.getenv("DHAN_USER_ID", "")
PASSWORD = os.getenv("DHAN_PASSWORD", "")
TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET", "")

# Dhan API endpoints
AUTH_BASE = "https://auth.dhan.co"
API_BASE = "https://api.dhan.co/v2"

# Local callback server
PORT = 8000
REDIRECT_URL = f"http://127.0.0.1:{PORT}/callback"

# Global state
request_token = None
env_file_path = ".env"
token_box = {"tokenId": None, "error": None}


# ====================================================================================
# STEP 1: Generate Consent (Server-to-Server)
# ====================================================================================

def generate_consent():
    """Generate consent app ID for this session."""
    try:
        print("\n🔄 STEP 1: Generating consent...")

        url = f"{AUTH_BASE}/app/generate-consent"
        params = {"client_id": DHAN_CLIENT_ID}
        headers = {
            "app_id": API_KEY,
            "app_secret": API_SECRET,
        }

        response = requests.post(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        consent_app_id = data.get("consentAppId")

        print(f"✅ Consent generated: {consent_app_id[:15]}...")
        return consent_app_id

    except Exception as e:
        print(f"❌ ERROR generating consent: {e}")
        raise


# ====================================================================================
# STEP 2: Create HTTP Callback Handler to Capture tokenId from Redirect
# ====================================================================================

class RedirectHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler to capture tokenId from Dhan's redirect."""

    def do_GET(self):
        """Handle GET request with tokenId in query parameters."""
        global request_token

        # Parse the URL to get query parameters
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # Check for tokenId in query parameters
        if "tokenId" in query_params:
            request_token = query_params["tokenId"][0]  # Extract tokenId

            # Send success response to browser
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>[OK] Login successful. You may now close this tab.</h2>")

            print(f"✅ Received tokenId: {request_token[:15]}...")

            # Stop the server
            raise KeyboardInterrupt

        else:
            # Send error response
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>[ERROR] tokenId not found in URL.</h2>")

    def log_message(self, format_str, *args):
        """Suppress default logging."""
        pass


# ====================================================================================
# STEP 3: Start Local HTTP Callback Server
# ====================================================================================

def start_callback_server():
    """Start HTTP server to listen for redirect from Dhan."""
    print(f"🔄 STEP 2: Starting callback server on http://127.0.0.1:{PORT}")
    print(f"   Waiting for redirect from Dhan login page...")

    try:
        with socketserver.TCPServer(("127.0.0.1", PORT), RedirectHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("   ✅ Callback server stopped (token received)")
        httpd.server_close()


# ====================================================================================
# STEP 4: Generate TOTP Code
# ====================================================================================

def generate_totp():
    """Generate TOTP code from secret."""
    totp = pyotp.TOTP(TOTP_SECRET).now()
    print(f"   📱 TOTP code: {totp}")
    return totp


# ====================================================================================
# STEP 3: Open Browser and Wait for Manual Login (Simple Approach)
# ====================================================================================

def open_browser_for_login(login_url, timeout=300):
    """Open Dhan login page and wait for user to login or for token callback."""
    print("\n🔄 STEP 3: Opening browser for login...")
    print(f"   URL: {login_url}")

    totp_code = generate_totp()
    print(f"\n   📱 Your TOTP code: {totp_code}")
    print(f"   ⏱️  (Valid for 30 seconds)")

    # Open in default browser
    print("\n   Opening Dhan login page in your default browser...")
    webbrowser.open(login_url)

    print(f"\n   ⏳ Please complete the login in your browser:")
    print(f"      1. Enter User ID: {USER_ID}")
    print(f"      2. Enter Password: (your password)")
    print(f"      3. Enter TOTP code: {totp_code}")
    print(f"\n   ⏳ Waiting up to {timeout}s for token...")

    start_time = time.time()
    while time.time() - start_time < timeout:
        if token_box["tokenId"]:
            print("✅ Login successful!")
            return token_box["tokenId"]
        if token_box["error"]:
            raise Exception(f"Login error: {token_box['error']}")
        time.sleep(1)

    raise TimeoutError(f"Timeout: Token not received within {timeout}s")


# ====================================================================================
# STEP 7: Exchange tokenId for accessToken (Server-to-Server)
# ====================================================================================

def consume_consent(token_id):
    """Exchange tokenId for accessToken."""
    print(f"\n🔄 STEP 4: Exchanging tokenId for accessToken...")

    try:
        url = f"{AUTH_BASE}/app/consumeApp-consent"
        params = {"tokenId": token_id}
        headers = {
            "app_id": API_KEY,
            "app_secret": API_SECRET,
        }

        response = requests.post(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        print("✅ Access token obtained!")
        print(f"   Dhan Client ID: {data.get('dhanClientId')}")
        print(f"   Access Token: {data.get('accessToken', '')[:30]}...")
        print(f"   Expiry Time: {data.get('expiryTime')}")

        return data

    except Exception as e:
        print(f"❌ ERROR consuming consent: {e}")
        raise


# ====================================================================================
# STEP 8: Save Token to .env File
# ====================================================================================

def save_token(auth_data):
    """Save token to .env file."""
    # Read current .env
    env_vars = {}
    try:
        with open(env_file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    except FileNotFoundError:
        pass
    
    # Update with new token
    env_vars["DHAN_ACCESS_TOKEN"] = auth_data.get("accessToken", "")
    env_vars["DHAN_CLIENT_ID"] = auth_data.get("dhanClientId", "")
    env_vars["DHAN_TOKEN_EXPIRY"] = auth_data.get("expiryTime", "")
    
    # Write back to .env
    with open(env_file_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    
    print(f"✅ Token saved to {env_file_path}")
    print(f"   DHAN_ACCESS_TOKEN: {auth_data.get('accessToken', '')[:30]}...")
    print(f"   DHAN_CLIENT_ID: {auth_data.get('dhanClientId')}")
    print(f"   DHAN_TOKEN_EXPIRY: {auth_data.get('expiryTime')}")


# ====================================================================================
# STEP 9: Validate Token Works
# ====================================================================================

def validate_token(access_token, dhan_client_id):
    """Validate token by calling /v2/profile endpoint."""
    print(f"\n🔍 Validating token...")

    try:
        url = f"{API_BASE}/profile"
        headers = {
            "access-token": access_token,
            "dhanClientId": dhan_client_id,
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        profile = response.json()
        print(f"✅ Token is valid!")
        print(f"   Profile: {json.dumps(profile, indent=3)}")
        return True

    except Exception as e:
        print(f"❌ Token validation failed: {e}")
        return False


# ====================================================================================
# OPTIONAL: Token Rotation (RenewToken)
# ====================================================================================

def renew_token_api(access_token, dhan_client_id):
    """Rotate the accessToken to get a fresh 24-hour token (no re-login needed)."""
    print(f"\n🔄 Renewing token...")

    try:
        url = f"{API_BASE}/RenewToken"
        headers = {
            "access-token": access_token,
            "dhanClientId": dhan_client_id,
        }

        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        print("✅ Token renewed successfully!")
        print(f"   New Access Token: {data.get('accessToken', '')[:30]}...")
        print(f"   New Expiry Time: {data.get('expiryTime')}")

        return data

    except Exception as e:
        print(f"❌ ERROR renewing token: {e}")
        raise


# ====================================================================================
# MAIN: Complete Automated 3-Step Login Flow
# ====================================================================================

def main():
    """Complete automated 3-step OAuth-like login flow."""
    print("\n" + "=" * 70)
    print("DHAN API: COMPLETE AUTOMATED LOGIN FLOW")
    print("=" * 70)

    # Validate configuration
    print("\n📋 Checking configuration...")
    required = ["DHAN_CLIENT_ID", "API_KEY", "API_SECRET", "USER_ID", "PASSWORD", "TOTP_SECRET"]
    for key in required:
        value = globals()[key]
        if not value:
            print(f"❌ Missing: {key}")
            return False
        print(f"✅ {key}: {'*' * (len(value) // 2) if len(value) > 5 else value}")

    try:
        # Step 1: Generate Consent
        consent_app_id = generate_consent()

        # Step 2: Start callback server in background
        server_thread = threading.Thread(target=start_callback_server, daemon=True)
        server_thread.start()
        time.sleep(1)  # Give server time to start

        # Step 3: Open browser and wait for login
        login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
        token_id = open_browser_for_login(login_url)

        # Step 4: Exchange tokenId for accessToken
        auth_data = consume_consent(token_id)

        # Step 5: Save token
        save_token(auth_data)

        # Step 6: Validate token
        access_token = auth_data.get("accessToken")
        dhan_client_id = auth_data.get("dhanClientId")
        validate_token(access_token, dhan_client_id)

        print("\n" + "=" * 70)
        print("✅ LOGIN SUCCESSFUL!")
        print("=" * 70)
        print(f"Access Token: {access_token[:30]}...")
        print(f"Dhan Client ID: {dhan_client_id}")
        print(f"Expiry Time: {auth_data.get('expiryTime')}")
        print(f"Token saved to: {env_file_path}")
        print("=" * 70)

        return True

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return False

    except Exception as e:
        print("\n" + "=" * 70)
        print(f"❌ LOGIN FAILED: {e}")
        print("=" * 70)
        print("\nTroubleshooting:")
        print("1. Verify env vars in .env file:")
        print("   - DHAN_CLIENT_ID")
        print("   - DHAN_API_KEY")
        print("   - DHAN_API_SECRET")
        print("2. Check credentials in .env:")
        print("   - DHAN_USER_ID")
        print("   - DHAN_PASSWORD")
        print("3. Verify TOTP secret (base32 format):")
        print(f"   - DHAN_TOTP_SECRET = {TOTP_SECRET}")
        print("4. Ensure port 8000 is available for callback server")
        print("=" * 70)
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
