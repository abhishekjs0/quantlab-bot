#!/usr/bin/env python3
"""
Dhan API - Simplified Authentication Flow
Complete OAuth flow with browser automation
"""

import json
import os
import time
import webbrowser

import pyautogui
import pyotp
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

API_KEY = os.getenv("DHAN_API_KEY")
API_SECRET = os.getenv("DHAN_API_SECRET")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
USER_ID = os.getenv("DHAN_USER_ID", "")
PASSWORD = os.getenv("DHAN_PASSWORD", "")
TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET", "")

AUTH_BASE = "https://auth.dhan.co"
API_BASE = "https://api.dhan.co/v2"

# PyAutoGUI settings
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1

print("\n" + "=" * 70)
print("DHAN API - SIMPLIFIED AUTHENTICATION FLOW")
print("=" * 70)


def generate_consent():
    """Step 1: Generate consent"""
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
        return consent_app_id
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def generate_totp():
    """Step 2: Generate TOTP code"""
    print("\n🔄 STEP 2: Generating TOTP code...")
    totp_code = pyotp.TOTP(TOTP_SECRET).now()
    print(f"✅ TOTP code: {totp_code}")
    return totp_code


def automate_login(consent_app_id, totp_code):
    """Step 3: Automate multi-step login form"""
    print("\n🔄 STEP 3: Opening login page and automating form...")

    login_url = f"{AUTH_BASE}/login/consentApp-login?consentAppId={consent_app_id}"
    webbrowser.open(login_url)

    print("⏳ Waiting for browser to load (5 seconds)...")
    time.sleep(5)

    try:
        # Focus on browser
        print("   📍 Ensuring browser is focused...")
        pyautogui.click(500, 300)
        time.sleep(2)

        # STEP 1: Enter Mobile Number (this is the USER_ID/phone)
        print(f"   📝 STEP 1 - Entering Mobile Number: {USER_ID}")
        pyautogui.typewrite(USER_ID, interval=0.05)
        time.sleep(1)

        # Press Enter to go to next step (password field)
        print("   ⏩ Pressing ENTER to proceed to password...")
        pyautogui.press("return")
        time.sleep(2)

        # STEP 2: Enter Password
        print("   📝 STEP 2 - Entering Password...")
        pyautogui.typewrite(PASSWORD, interval=0.05)
        time.sleep(1)

        # Press Enter to go to next step (OTP field)
        print("   ⏩ Pressing ENTER to proceed to OTP...")
        pyautogui.press("return")
        time.sleep(2)

        # STEP 3: Enter TOTP
        print(f"   📝 STEP 3 - Entering TOTP: {totp_code}")
        pyautogui.typewrite(totp_code, interval=0.05)
        time.sleep(1)

        # Press Enter to submit
        print("   ✅ Submitting form...")
        pyautogui.press("return")

        print("\n✅ Form submitted successfully!")
        print("   Waiting for token redirect...")
        time.sleep(3)

        return True

    except Exception as e:
        print(f"❌ Automation error: {e}")
        return False


def save_token(access_token, expiry_time=""):
    """Save token to .env file"""
    env_file = ".env"

    # Read current .env
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value

    # Update tokens
    env_vars["DHAN_ACCESS_TOKEN"] = access_token
    if expiry_time:
        env_vars["DHAN_TOKEN_EXPIRY"] = expiry_time

    # Write back
    with open(env_file, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    print("✅ Token saved to .env")


def validate_token(access_token):
    """Validate token by fetching profile"""
    print("\n🔍 Validating token...")
    try:
        response = requests.get(
            f"{API_BASE}/profile",
            headers={
                "access-token": access_token,
                "dhanClientId": DHAN_CLIENT_ID,
            },
            timeout=10
        )
        response.raise_for_status()
        profile = response.json()
        print("✅ Token is VALID!")
        print(f"   User: {profile.get('name', 'Unknown')}")
        return True
    except Exception as e:
        print(f"⚠️  Token validation: {e}")
        return False


def main():
    """Main authentication flow"""
    # Generate consent
    consent_app_id = generate_consent()
    if not consent_app_id:
        return

    # Generate TOTP
    totp_code = generate_totp()

    # Automate login
    if not automate_login(consent_app_id, totp_code):
        print("\n❌ Login automation failed")
        return

    # Wait for manual confirmation or token capture
    print("\n⏳ Waiting for authentication (60 seconds)...")
    print("   If using callback, ensure your browser receives the token")
    print("   Press Ctrl+C to cancel\n")

    try:
        for i in range(60):
            time.sleep(1)
            # Try to fetch profile with any existing token
            existing_token = os.getenv("DHAN_ACCESS_TOKEN")
            if existing_token:
                # Reload env to get latest
                from dotenv import load_dotenv
                load_dotenv(override=True)
                existing_token = os.getenv("DHAN_ACCESS_TOKEN")

                if validate_token(existing_token):
                    print("\n" + "=" * 70)
                    print("✅ AUTHENTICATION SUCCESSFUL")
                    print("=" * 70)
                    if existing_token:
                        print(f"\nToken: {existing_token[:50]}...")
                    print("Saved to: .env (DHAN_ACCESS_TOKEN)")
                    return
    except KeyboardInterrupt:
        print("\n\n⛔ Cancelled")

    print("\n⚠️  Timeout: No valid token found")
    print("   Please check browser and try again")


if __name__ == "__main__":
    main()
