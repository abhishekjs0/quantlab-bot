#!/usr/bin/env python3
"""
Dhan API - Browser-Based Token Refresh Helper
Opens Dhan web platform and guides you through manual token extraction
More reliable than full automation in constrained environments
"""

import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()


def get_browser_instructions():
    """Generate manual browser instructions for token refresh"""
    user_id = os.getenv("DHAN_USER_ID", "UNKNOWN")
    password_hint = os.getenv("DHAN_PASSWORD", "")[:2]

    instructions = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   DHAN TOKEN REFRESH - MANUAL BROWSER METHOD                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

⏰ YOUR TOKEN EXPIRES IN LESS THAN 24 HOURS!
   Token valid until: 2025-11-06 20:24:48 UTC

📋 STEP-BY-STEP INSTRUCTIONS:

1️⃣  OPEN BROWSER AND LOGIN
   └─ Go to: https://web.dhan.co/
   └─ User ID: {user_id}
   └─ Password: [Use your password from .env - starts with: {password_hint}*]
   └─ OTP: Use your TOTP app to generate a 6-digit code

2️⃣  NAVIGATE TO API SETTINGS
   └─ Click "Settings" in the menu (usually in profile/account area)
   └─ Select "API Settings" or "Developer Settings"

3️⃣  GENERATE/REGENERATE TOKEN
   └─ Click the "Generate" or "Regenerate" button
   └─ If a token already exists, you may need to click "Revoke" first, then "Generate"

4️⃣  COPY THE TOKEN
   └─ Look for a long string starting with "eyJ"
   └─ It will look something like: eyJ0eXAiOiJKV1QiLCJhbGci...
   └─ Copy the ENTIRE token (it's usually 500+ characters)

5️⃣  PASTE BELOW
   └─ Come back here and paste the token when prompted

╔══════════════════════════════════════════════════════════════════════════════╗
"""
    return instructions


def prompt_for_token():
    """Interactively get token from user"""
    print(get_browser_instructions())

    print("\n🔐 PASTE YOUR TOKEN HERE:")
    print("   (Right-click and paste, then press Enter)")
    print("   Token: ", end="")

    token = input("").strip()

    if not token:
        print("\n❌ No token provided")
        return None

    if not token.startswith("eyJ"):
        print(f"\n⚠️  WARNING: Token doesn't look valid (starts with '{token[:10]}')")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != "y":
            return None

    return token


def validate_and_save_token(token):
    """Validate token with API and save to .env"""
    print("\n⏳ Validating token with API...")

    client_id = os.getenv("DHAN_CLIENT_ID")
    headers = {"access-token": token, "dhanClientId": client_id}

    try:
        response = requests.get(
            "https://api.dhan.co/profile", headers=headers, timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            token_validity = data.get("tokenValidity", "Unknown")

            print("\n✅ TOKEN VALIDATED!")
            print(f"   Valid until: {token_validity}")

            # Save to .env
            print("\n💾 Saving to .env...")
            env_file = ".env"
            env_vars = {}

            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            env_vars[key] = val

            env_vars["DHAN_ACCESS_TOKEN"] = token

            with open(env_file, "w") as f:
                for key, val in env_vars.items():
                    f.write(f"{key}={val}\n")

            print("   ✅ Token saved successfully!")
            return True

        else:
            print(f"\n❌ API validation failed (HTTP {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"\n❌ Error validating token: {e}")
        return False


def main():
    print("\n" + "=" * 80)
    print("DHAN API - TOKEN REFRESH HELPER")
    print("=" * 80)

    token = prompt_for_token()

    if not token:
        print("\n❌ Token refresh cancelled")
        return 1

    success = validate_and_save_token(token)

    if success:
        print("\n" + "=" * 80)
        print("✅ TOKEN REFRESH COMPLETE!")
        print("=" * 80)
        print("\nYour new token is ready to use!")
        print("Next: python scripts/test_simple.py")
        return 0
    else:
        print("\n" + "=" * 80)
        print("❌ TOKEN REFRESH FAILED")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
