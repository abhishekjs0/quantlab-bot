#!/usr/bin/env python3
"""
Dhan API - Token Management System
Provides automated and manual token refresh capabilities
"""

import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()


class DhanTokenManager:
    """Manages Dhan API tokens - refresh, validation, and storage"""

    def __init__(self):
        self.client_id = os.getenv("DHAN_CLIENT_ID")
        self.api_key = os.getenv("DHAN_API_KEY")
        self.access_token = os.getenv("DHAN_ACCESS_TOKEN")
        self.base_url = "https://api.dhan.co"

    def validate_token(self):
        """Check if current token is valid by calling API"""
        if not self.access_token:
            return False, "No token found"

        headers = {
            "access-token": self.access_token,
            "dhanClientId": self.client_id,
        }

        try:
            response = requests.get(
                f"{self.base_url}/profile", headers=headers, timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                token_validity = data.get("tokenValidity", "Unknown")
                return True, f"Token valid until {token_validity}"
            else:
                return False, f"API returned {response.status_code}"

        except Exception as e:
            return False, str(e)

    def get_token_expiry_unix(self):
        """Extract token expiry time from JWT"""
        if not self.access_token:
            return None

        try:
            # JWT format: header.payload.signature
            parts = self.access_token.split(".")
            if len(parts) != 3:
                return None

            # Decode payload (add padding if needed)
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding

            import base64

            decoded = base64.urlsafe_b64decode(payload)
            data = json.loads(decoded)

            exp_timestamp = data.get("exp")
            if exp_timestamp:
                exp_date = datetime.fromtimestamp(exp_timestamp)
                return exp_timestamp, exp_date
            return None

        except Exception as e:
            print(f"Error decoding token: {e}")
            return None

    def get_token_status(self):
        """Get comprehensive token status"""
        valid, msg = self.validate_token()

        expiry_info = self.get_token_expiry_unix()
        if expiry_info:
            _unix_ts, exp_date = expiry_info
            days_remaining = (exp_date - datetime.now()).days
        else:
            exp_date, days_remaining = None, None

        return {
            "valid": valid,
            "validation_message": msg,
            "expiry_datetime": exp_date.isoformat() if exp_date else None,
            "days_remaining": days_remaining,
            "token_preview": (
                self.access_token[:40] + "..." if self.access_token else None
            ),
        }

    def manual_token_refresh_instructions(self):
        """Provide instructions for manual token refresh"""
        instructions = """
╔════════════════════════════════════════════════════════════════════════════╗
║                    MANUAL TOKEN REFRESH INSTRUCTIONS                       ║
╚════════════════════════════════════════════════════════════════════════════╝

When your token expires, follow these steps:

1. NAVIGATE TO DHAN WEB PLATFORM
   └─ Go to: https://web.dhan.co/

2. LOGIN WITH YOUR CREDENTIALS
   └─ User ID: {user_id}
   └─ Password: (from .env DHAN_PASSWORD)
   └─ OTP: Use TOTP secret to generate from Google Authenticator

3. GO TO API SETTINGS
   └─ Settings → API Settings
   └─ Click "Generate" or "Regenerate" button

4. COPY THE NEW TOKEN
   └─ Look for a token starting with "eyJ"
   └─ Copy the entire token (it's long, typically 500+ characters)

5. UPDATE YOUR .env FILE
   └─ Replace DHAN_ACCESS_TOKEN with the new token
   └─ Save the file

6. RESTART YOUR APPLICATION
   └─ Run: python scripts/test_simple.py
   └─ Verify the new token works

ALTERNATIVELY, if you need automated refresh:
   └─ Use: python scripts/dhan_login_auto_fixed.py
   └─ This will automate the browser login and token extraction

╔════════════════════════════════════════════════════════════════════════════╗
""".format(
            user_id=os.getenv("DHAN_USER_ID", "N/A")
        )

        return instructions


def main():
    """Test token manager"""
    manager = DhanTokenManager()

    print("\n" + "=" * 80)
    print("DHAN TOKEN MANAGEMENT SYSTEM")
    print("=" * 80)

    print("\n📊 TOKEN STATUS:")
    status = manager.get_token_status()

    if status["valid"]:
        print("\n   ✅ Token Status: VALID")
        print(f"   📅 Valid Until: {status['expiry_datetime']}")
        print(f"   ⏳ Days Remaining: {status['days_remaining']}")
        print(f"   🔐 Token: {status['token_preview']}")
    else:
        print("\n   ❌ Token Status: INVALID")
        print(f"   ⚠️  Reason: {status['validation_message']}")
        print(manager.manual_token_refresh_instructions())

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("\n   1. Verify token is valid ✅ (just did this)")
    print("   2. Use REST API to fetch account data:")
    print("      └─ python scripts/dhan_working.py")
    print("   3. When token expires (in", status["days_remaining"], "days):")
    print("      └─ Option A: Manual refresh (see instructions above)")
    print("      └─ Option B: Automated refresh with browser:")
    print("         python scripts/dhan_login_auto_fixed.py")
    print("\n" + "=" * 80 + "\n")

    return 0 if status["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
