#!/usr/bin/env python3
"""
Dhan API - Automated Token Management Script

Production-ready implementation of Dhan's 3-step OAuth-like flow:
1. Generate consent (server-to-server)
2. Headless login with TOTP (automated Chrome)
3. Exchange tokenId for accessToken
4. Token rotation via RenewToken (no re-login)

Usage:
    python3 dhan_auth.py login          # Full login flow
    python3 dhan_auth.py renew          # Renew existing token
    python3 dhan_auth.py validate       # Check if token is valid
    python3 dhan_auth.py info           # Show token info

Docs: https://dhanhq.co/docs/v2/authentication
"""

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime

import pyotp
import requests
from flask import Flask
from flask import request as flask_request
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG = {
    "DHAN_CLIENT_ID": os.getenv("DHAN_CLIENT_ID", ""),
    "API_KEY": os.getenv("DHAN_API_KEY", ""),
    "API_SECRET": os.getenv("DHAN_API_SECRET", ""),
    "USER_ID": os.getenv("DHAN_USER_ID", ""),
    "USER_PASS": os.getenv("DHAN_PASSWORD", ""),
    "TOTP_SECRET": os.getenv("DHAN_TOTP_SECRET", ""),
    "REDIRECT_URL": os.getenv("DHAN_REDIRECT_URL", "http://127.0.0.1:5000/dhan/callback"),
    "AUTH_BASE": "https://auth.dhan.co",
    "API_BASE": "https://api.dhan.co/v2",
    "CALLBACK_PATH": "/dhan/callback",
    "PORT": 5000,
    "TOKEN_FILE": os.getenv("DHAN_TOKEN_FILE", ".dhan_token.json"),
}

# Global state
token_box = {"tokenId": None, "error": None}
flask_app = Flask(__name__)


# ============================================================================
# STEP 1: Generate Consent
# ============================================================================

def generate_consent():
    """Generate consent app ID for this session."""
    try:
        print("\n🔄 STEP 1: Generating consent...")

        url = f"{CONFIG['AUTH_BASE']}/app/generate-consent"
        params = {"client_id": CONFIG["DHAN_CLIENT_ID"]}
        headers = {
            "app_id": CONFIG["API_KEY"],
            "app_secret": CONFIG["API_SECRET"],
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


# ============================================================================
# STEP 2: Callback Server
# ============================================================================

@flask_app.route(CONFIG["CALLBACK_PATH"], methods=["GET"])
def callback():
    """Capture tokenId from Dhan's redirect."""
    token_id = flask_request.args.get("tokenId")
    error = flask_request.args.get("error")

    if token_id:
        token_box["tokenId"] = token_id
        print(f"✅ Received tokenId: {token_id[:15]}...")
        return "✅ Received tokenId. You can close this tab."
    elif error:
        token_box["error"] = error
        print(f"❌ Received error: {error}")
        return f"❌ Error: {error}"
    else:
        return "❌ No tokenId or error in request"


def start_callback_server():
    """Start Flask server in background."""
    import logging
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    flask_app.run(
        host="127.0.0.1",
        port=CONFIG["PORT"],
        debug=False,
        use_reloader=False,
        threaded=True,
    )


# ============================================================================
# STEP 3: Headless Login with TOTP
# ============================================================================

def headless_login(consent_app_id, timeout=60):
    """Automated login flow using headless Chrome."""
    print("\n🔄 STEP 2: Automated headless login...")

    login_url = f"{CONFIG['AUTH_BASE']}/login/consentApp-login?consentAppId={consent_app_id}"

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = None
    try:
        print("   Starting Chrome...")
        driver = webdriver.Chrome(
            ChromeDriverManager().install(),
            options=chrome_options,
        )
        driver.set_page_load_timeout(timeout)

        print(f"   Opening login URL...")
        driver.get(login_url)

        # Step 1: Enter User ID
        print("   Submitting User ID...")
        time.sleep(1)
        user_id_field = driver.find_element(By.NAME, "userId")
        user_id_field.clear()
        user_id_field.send_keys(CONFIG["USER_ID"])
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Step 2: Enter Password/PIN
        print("   Submitting Password...")
        time.sleep(2)
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(CONFIG["USER_PASS"])
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Step 3: Enter TOTP
        print("   Generating and submitting TOTP...")
        time.sleep(2)
        totp_code = pyotp.TOTP(CONFIG["TOTP_SECRET"]).now()
        print(f"   TOTP code: {totp_code}")
        otp_field = driver.find_element(By.NAME, "otp")
        otp_field.clear()
        otp_field.send_keys(totp_code)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

        # Wait for redirect
        print("   Waiting for redirect...")
        deadline = time.time() + timeout
        while time.time() < deadline:
            if token_box["tokenId"]:
                print(f"✅ Login successful")
                return token_box["tokenId"]
            if token_box["error"]:
                raise Exception(f"Login error: {token_box['error']}")
            time.sleep(0.5)

        raise TimeoutError(f"Did not receive tokenId within {timeout}s")

    except Exception as e:
        print(f"❌ Login failed: {e}")
        raise
    finally:
        if driver:
            driver.quit()


# ============================================================================
# STEP 4: Exchange tokenId for accessToken
# ============================================================================

def consume_consent(token_id):
    """Exchange tokenId for accessToken."""
    print("\n🔄 STEP 3: Consuming consent for accessToken...")

    try:
        url = f"{CONFIG['AUTH_BASE']}/app/consumeApp-consent"
        params = {"tokenId": token_id}
        headers = {
            "app_id": CONFIG["API_KEY"],
            "app_secret": CONFIG["API_SECRET"],
        }

        response = requests.post(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        print("✅ Access token obtained!")
        print(f"   Dhan Client ID: {data.get('dhanClientId')}")
        print(f"   Access Token: {data.get('accessToken', '')[:20]}...")
        print(f"   Expiry Time (IST): {data.get('expiryTime')}")

        return data

    except Exception as e:
        print(f"❌ ERROR consuming consent: {e}")
        raise


# ============================================================================
# STEP 5: Token Rotation (RenewToken)
# ============================================================================

def renew_token(access_token, dhan_client_id):
    """Rotate the accessToken to get a fresh 24-hour token."""
    print("\n🔄 Renewing token (no re-login needed)...")

    try:
        url = f"{CONFIG['API_BASE']}/RenewToken"
        headers = {
            "access-token": access_token,
            "dhanClientId": dhan_client_id,
        }

        response = requests.post(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        print("✅ Token renewed successfully!")
        print(f"   New Access Token: {data.get('accessToken', '')[:20]}...")
        print(f"   New Expiry Time: {data.get('expiryTime')}")

        return data

    except Exception as e:
        print(f"❌ ERROR renewing token: {e}")
        raise


# ============================================================================
# COMPLETE FLOW
# ============================================================================

def full_login_flow():
    """Complete automated 3-step login flow."""
    print("=" * 60)
    print("DHAN API: COMPLETE AUTOMATED LOGIN FLOW")
    print("=" * 60)

    # Reset token box
    token_box["tokenId"] = None
    token_box["error"] = None

    try:
        # Validate config
        required = ["DHAN_CLIENT_ID", "API_KEY", "API_SECRET", "USER_ID", "USER_PASS", "TOTP_SECRET"]
        for key in required:
            if not CONFIG[key]:
                raise ValueError(f"Missing config: {key}")

        # Step 1: Generate consent
        consent_app_id = generate_consent()

        # Step 2: Headless login
        token_id = headless_login(consent_app_id)

        # Step 3: Consume token
        auth_data = consume_consent(token_id)

        print("\n" + "=" * 60)
        print("✅ LOGIN SUCCESSFUL!")
        print("=" * 60)
        print(f"Access Token: {auth_data.get('accessToken', '')[:30]}...")
        print(f"Expiry Time: {auth_data.get('expiryTime')}")
        print(f"Client ID: {auth_data.get('dhanClientId')}")

        return auth_data

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ LOGIN FAILED: {e}")
        print("=" * 60)
        print("\nTroubleshooting:")
        print("1. Verify env vars: DHAN_CLIENT_ID, DHAN_API_KEY, DHAN_API_SECRET")
        print("2. Check credentials: DHAN_USER_ID, DHAN_PASSWORD")
        print("3. Verify TOTP secret: DHAN_TOTP_SECRET (base32 format)")
        print("4. Check redirect URL: " + CONFIG['REDIRECT_URL'])
        return None


# ============================================================================
# TOKEN MANAGER
# ============================================================================

class DhanTokenManager:
    """Manage Dhan tokens with automatic renewal."""

    def __init__(self, token_file=None):
        self.token_file = token_file or CONFIG["TOKEN_FILE"]
        self.token_data = None
        self.load_token()

    def save_token(self, token_data):
        """Save token to disk."""
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        self.token_data = token_data
        print(f"✅ Token saved to {self.token_file}")

    def load_token(self):
        """Load token from disk."""
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                self.token_data = json.load(f)
            print(f"✅ Token loaded from {self.token_file}")
        else:
            print(f"ℹ️  No token file found at {self.token_file}")

    def is_expired(self):
        """Check if token is expired."""
        if not self.token_data:
            return True

        expiry_str = self.token_data.get("expiryTime", "")
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            is_exp = now >= expiry_dt
            if is_exp:
                print(f"⚠️  Token expired at {expiry_str}")
            return is_exp
        except:
            return True

    def get_token(self):
        """Get valid token, renew if needed."""
        if not self.token_data:
            print("❌ No token available. Run login first.")
            return None

        if self.is_expired():
            print("🔄 Token expired, renewing...")
            new_data = renew_token(
                self.token_data.get("accessToken"),
                self.token_data.get("dhanClientId"),
            )
            if new_data:
                self.save_token(new_data)
                return new_data.get("accessToken")
            return None

        return self.token_data.get("accessToken")

    def validate_token(self):
        """Test token with /profile endpoint."""
        token = self.get_token()
        if not token:
            return False

        try:
            print("🔍 Validating token...")
            url = f"{CONFIG['API_BASE']}/profile"
            headers = {
                "access-token": token,
                "dhanClientId": self.token_data.get("dhanClientId"),
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            print("✅ Token is valid!")
            print(json.dumps(response.json(), indent=2))
            return True
        except Exception as e:
            print(f"❌ Token validation failed: {e}")
            return False

    def info(self):
        """Show token information."""
        if not self.token_data:
            print("❌ No token loaded")
            return

        print("\n📋 Token Information:")
        print(f"   Client ID: {self.token_data.get('dhanClientId')}")
        print(f"   Access Token: {self.token_data.get('accessToken', '')[:30]}...")
        print(f"   Expiry Time: {self.token_data.get('expiryTime')}")
        print(f"   Expires in: {self._time_to_expiry()}")

    def _time_to_expiry(self):
        """Calculate time until expiry."""
        if not self.token_data:
            return "N/A"

        expiry_str = self.token_data.get("expiryTime", "")
        try:
            expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            delta = expiry_dt - now
            if delta.total_seconds() < 0:
                return "EXPIRED"
            hours = int(delta.total_seconds() / 3600)
            minutes = int((delta.total_seconds() % 3600) / 60)
            return f"{hours}h {minutes}m"
        except:
            return "Unknown"


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Dhan API - Automated Token Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s login                    # Full login flow (3-step OAuth)
  %(prog)s renew                    # Renew existing token (no re-login)
  %(prog)s validate                 # Validate token works
  %(prog)s info                     # Show token information

Environment Variables (required for login):
  DHAN_CLIENT_ID        - Your Dhan client ID
  DHAN_API_KEY          - App ID from Dhan API key tab
  DHAN_API_SECRET       - App secret
  DHAN_USER_ID          - Your Dhan login user ID
  DHAN_PASSWORD         - Your Dhan password or PIN
  DHAN_TOTP_SECRET      - Base32 TOTP secret (from 2FA QR code)

Optional:
  DHAN_REDIRECT_URL     - Redirect URL (default: http://127.0.0.1:5000/dhan/callback)
  DHAN_TOKEN_FILE       - Token file location (default: .dhan_token.json)

Documentation: https://dhanhq.co/docs/v2/authentication
        """,
    )

    parser.add_argument(
        "action",
        choices=["login", "renew", "validate", "info"],
        help="Action to perform",
    )

    args = parser.parse_args()

    # Initialize token manager
    token_mgr = DhanTokenManager()

    try:
        if args.action == "login":
            # Start callback server
            server_thread = threading.Thread(target=start_callback_server, daemon=True)
            server_thread.start()
            time.sleep(2)

            # Full login
            auth_data = full_login_flow()
            if auth_data:
                token_mgr.save_token(auth_data)
                print(f"\n✅ Token saved to {token_mgr.token_file}")

        elif args.action == "renew":
            if not token_mgr.token_data:
                print("❌ No token file found. Run 'login' first.")
                sys.exit(1)

            new_data = renew_token(
                token_mgr.token_data.get("accessToken"),
                token_mgr.token_data.get("dhanClientId"),
            )
            if new_data:
                token_mgr.save_token(new_data)

        elif args.action == "validate":
            if not token_mgr.token_data:
                print("❌ No token file found. Run 'login' first.")
                sys.exit(1)

            if token_mgr.validate_token():
                print("\n✅ Token is working!")
            else:
                print("\n❌ Token validation failed!")
                sys.exit(1)

        elif args.action == "info":
            token_mgr.info()

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
