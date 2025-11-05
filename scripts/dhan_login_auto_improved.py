#!/usr/bin/env python3
"""
Dhan API - Improved Automated Login with Fallback to Manual Entry
More robust handling of Dhan's complex login page
"""

import json
import os
import sys
import time
from datetime import datetime

import pyotp
import requests
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.support.ui import WebDriverWait

load_dotenv()

DHAN_USER = os.getenv("DHAN_USER_ID", "")
DHAN_PASS = os.getenv("DHAN_PASSWORD", "")
TOTP_SECRET = os.getenv("DHAN_TOTP_SECRET", "")

if not all([DHAN_USER, DHAN_PASS, TOTP_SECRET]):
    print("❌ Missing .env credentials:")
    print("   - DHAN_USER_ID")
    print("   - DHAN_PASSWORD")
    print("   - DHAN_TOTP_SECRET")
    sys.exit(1)


def find_chrome():
    """Find Chrome executable on macOS"""
    possible_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/local/bin/google-chrome",
        "/usr/bin/google-chrome",
        "/opt/homebrew/bin/google-chrome",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"   ✅ Found Chrome at: {path}")
            return path

    raise RuntimeError("Chrome not found. Install with: brew install google-chrome")


def login_and_get_token():
    """
    Improved automated Dhan login with better error handling
    """

    print("\n" + "=" * 70)
    print("DHAN - AUTOMATED LOGIN & TOKEN GENERATION (IMPROVED)")
    print("=" * 70)

    # Verify Chrome exists
    print("\n1. Locating Chrome browser...")
    _chrome_path = find_chrome()

    # Configure Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1400,900")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    driver = None
    token = None

    try:
        print("\n2. Launching Chrome browser...")
        driver = webdriver.Chrome(options=chrome_options)
        print("   ✅ Browser launched")

        print("\n3. Navigating to Dhan login page...")
        driver.get("https://login.dhan.co/")
        time.sleep(3)  # Let page load
        print("   ✅ Page loaded")

        # Try to find input fields with longer timeout
        print("\n4. Waiting for login form to load...")
        try:
            # Wait for ANY input fields to appear
            WebDriverWait(driver, 20).until(
                ec.presence_of_all_elements_located((By.TAG_NAME, "input"))
            )
            print("   ✅ Login form detected")
        except Exception as e:
            print(f"   ⚠️  Login form not found within timeout: {e}")
            print("   📋 Falling back to manual token entry...")
            return prompt_for_manual_token()

        time.sleep(2)

        # Try to find and fill User ID
        print("\n5. Entering user ID...")
        try:
            user_inputs = driver.find_elements(
                By.CSS_SELECTOR, 'input[type="text"], input[type="email"]'
            )
            if user_inputs:
                user_inputs[0].clear()
                user_inputs[0].send_keys(DHAN_USER)
                print(f"   ✅ User ID entered: {DHAN_USER}")
                time.sleep(1)
            else:
                print("   ⚠️  Could not find user input field")
        except Exception as e:
            print(f"   ⚠️  Error entering user ID: {e}")

        # Try to find and fill Password
        print("\n6. Entering password...")
        try:
            pass_inputs = driver.find_elements(
                By.CSS_SELECTOR, 'input[type="password"]'
            )
            if pass_inputs:
                pass_inputs[0].clear()
                pass_inputs[0].send_keys(DHAN_PASS)
                print("   ✅ Password entered")
                time.sleep(1)
            else:
                print("   ⚠️  Could not find password input field")
        except Exception as e:
            print(f"   ⚠️  Error entering password: {e}")

        # Click submit button
        print("\n7. Submitting login form...")
        try:
            buttons = driver.find_elements(By.TAG_NAME, "button")
            if buttons:
                buttons[0].click()  # Click first button (likely submit)
                print("   ✅ Form submitted")
                time.sleep(3)
            else:
                print("   ⚠️  No submit button found")
        except Exception as e:
            print(f"   ⚠️  Error submitting form: {e}")

        # Generate and enter OTP
        print("\n8. Generating OTP...")
        totp_code = pyotp.TOTP(TOTP_SECRET).now()
        print(f"   🔐 Generated OTP: {totp_code}")

        try:
            otp_inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="text"]')
            if len(otp_inputs) > 0:
                # Find the OTP input (usually the last one)
                otp_input = otp_inputs[-1] if len(otp_inputs) > 1 else otp_inputs[0]
                otp_input.clear()
                otp_input.send_keys(totp_code)
                print("   ✅ OTP entered")
                time.sleep(1)

                # Try to find and click submit
                buttons = driver.find_elements(By.TAG_NAME, "button")
                if buttons:
                    buttons[-1].click()  # Click last button
                    print("   ✅ OTP submitted")
                    time.sleep(3)
        except Exception as e:
            print(f"   ⚠️  Error with OTP: {e}")

        # Wait for navigation
        print("\n9. Waiting for redirect to API settings...")
        try:
            driver.get("https://web.dhan.co/settings/apis")
            time.sleep(3)
            print("   ✅ Navigated to API settings")
        except Exception as e:
            print(f"   ⚠️  Could not navigate to API settings: {e}")

        # Extract token from page
        print("\n10. Extracting access token...")
        token = extract_token_from_page(driver)

        if token:
            print(f"   ✅ Token extracted: {token[:60]}...")
            return token
        else:
            print("   ⚠️  Token not extracted, falling back to manual entry...")
            return prompt_for_manual_token()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        print("\n📋 Falling back to manual token entry...")
        return prompt_for_manual_token()

    finally:
        if driver:
            print("\n🔌 Closing browser...")
            driver.quit()


def extract_token_from_page(driver):
    """Try to extract token from page"""
    try:
        # Try code elements
        code_elements = driver.find_elements(By.TAG_NAME, "code")
        for code_el in code_elements:
            text = code_el.text.strip()
            if text.startswith("eyJ"):
                return text
    except Exception:
        pass

    try:
        # Try input fields
        inputs = driver.find_elements(By.TAG_NAME, "input")
        for inp in inputs:
            value = inp.get_attribute("value") or ""
            if value.startswith("eyJ"):
                return value
    except Exception:
        pass

    try:
        # Try page text
        page_text = driver.find_element(By.TAG_NAME, "body").text
        lines = page_text.split("\n")
        for line in lines:
            if line.startswith("eyJ"):
                return line.strip()
    except Exception:
        pass

    return None


def prompt_for_manual_token():
    """Prompt user to manually enter token"""
    print("\n" + "=" * 70)
    print("MANUAL TOKEN ENTRY")
    print("=" * 70)

    print("\n📋 INSTRUCTIONS:")
    print("1. Go to https://web.dhan.co/settings/apis in your browser")
    print("2. Login with your credentials")
    print("3. Find the 'Generate' or 'Access Token' section")
    print("4. Copy the token (starts with 'eyJ')")
    print("5. Paste it below:")

    token = input("\nToken: ").strip()

    if not token:
        print("❌ No token provided")
        return None

    if not token.startswith("eyJ"):
        print(f"⚠️  Warning: Token looks unusual (starts with '{token[:10]}')")
        confirm = input("Continue anyway? (y/n): ").strip().lower()
        if confirm != "y":
            return None

    return token


def validate_and_save_token(token):
    """Validate token and save to .env"""
    print("\n" + "=" * 70)
    print("VALIDATING AND SAVING TOKEN")
    print("=" * 70)

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

            print("✅ TOKEN VALIDATED!")
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
            print(f"❌ API validation failed (HTTP {response.status_code})")
            print(f"   Response: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return False


def main():
    print("\n🔐 Starting Dhan automated login and token generation...\n")

    token = login_and_get_token()

    if token:
        success = validate_and_save_token(token)

        if success:
            print("\n" + "=" * 70)
            print("✅ AUTHENTICATION SUCCESSFUL")
            print("=" * 70)
            print("\nYour new token is ready!")
            print("Next: python scripts/test_simple.py")
            return 0
        else:
            print("\n" + "=" * 70)
            print("⚠️  TOKEN VALIDATION FAILED")
            print("=" * 70)
            return 1
    else:
        print("\n" + "=" * 70)
        print("❌ NO TOKEN OBTAINED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
