#!/usr/bin/env python3
"""
Dhan Authentication Module with Automatic Token Generation
===========================================================
Handles automatic access token generation and renewal using API Key + Secret + TOTP.

This module implements the 3-step OAuth flow:
1. Generate Consent (validate API key/secret)
2. Browser Login (automated with TOTP)
3. Consume Consent (get access token)

Token Details:
- Access Token: Valid for 24 hours
- Automatically generates new token when expired
- Uses TOTP for headless authentication (no manual OTP entry needed)
"""

import base64
import json
import logging
import os
import time
import asyncio
from datetime import datetime
from typing import Optional, Tuple

import pyotp
import requests

# Optional: Playwright for browser automation fallback
try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    PlaywrightTimeout = None

logger = logging.getLogger(__name__)


class DhanAuth:
    """
    Automatic Dhan authentication with TOTP-based token generation.
    
    Flow:
    1. Check if current token is valid (>1 hour remaining)
    2. If expired/expiring, generate new token automatically
    3. Uses API Key + Secret + TOTP (no browser needed)
    """
    
    AUTH_BASE_URL = "https://auth.dhan.co"
    API_BASE_URL = "https://api.dhan.co/v2"
    
    def __init__(
        self,
        client_id: str,
        api_key: str,
        api_secret: str,
        totp_secret: str,
        user_id: str,
        password: str,
        access_token: Optional[str] = None,
        redirect_uri: Optional[str] = None
    ):
        """
        Initialize Dhan authentication.
        
        Args:
            client_id: Dhan client ID
            api_key: API key from Dhan web
            api_secret: API secret from Dhan web
            totp_secret: TOTP secret for 2FA
            user_id: Dhan user ID (mobile/email)
            password: Dhan password
            access_token: Existing access token (optional)
            redirect_uri: OAuth redirect URI for callback (optional)
        """
        self.client_id = client_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.totp_secret = totp_secret
        self.user_id = user_id
        self.password = password
        self.redirect_uri = redirect_uri
        self._access_token = access_token
        self._token_expiry = None
        self._pending_token_id = None  # Store tokenId from OAuth callback
        
        if access_token:
            self._token_expiry = self._decode_token_expiry(access_token)
    
    def _decode_token_expiry(self, token: str) -> Optional[datetime]:
        """Decode JWT token and extract expiry timestamp."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None
            
            payload = parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            
            exp = decoded.get("exp")
            if exp:
                return datetime.fromtimestamp(exp)
            return None
        except Exception as e:
            logger.warning(f"Failed to decode token expiry: {e}")
            return None
    
    def _is_token_valid(self, min_hours_remaining: float = 1.0) -> bool:
        """
        Check if current access token is valid.
        
        Args:
            min_hours_remaining: Minimum hours remaining before considering token expired
            
        Returns:
            True if token is valid and has sufficient time remaining
        """
        if not self._access_token or not self._token_expiry:
            return False
        
        now = datetime.now()
        if now >= self._token_expiry:
            logger.info("Token expired")
            return False
        
        hours_left = (self._token_expiry - now).total_seconds() / 3600
        if hours_left < min_hours_remaining:
            logger.info(f"Token expiring soon ({hours_left:.1f} hours left)")
            return False
        
        logger.info(f"Token valid ({hours_left:.1f} hours remaining)")
        return True
    
    def _generate_totp(self) -> str:
        """Generate TOTP code from secret."""
        totp = pyotp.TOTP(self.totp_secret)
        code = totp.now()
        logger.debug(f"Generated TOTP code: {code}")
        return code
    
    def set_token_id_from_callback(self, token_id: str) -> None:
        """Store tokenId received from OAuth callback."""
        self._pending_token_id = token_id
        logger.info(f"✅ Stored tokenId from callback: {token_id[:20]}...")
    
    def _step1_generate_consent(self) -> Optional[str]:
        """
        Step 1: Generate consent to initiate login session.
        
        Returns:
            consentAppId if successful, None otherwise
        """
        try:
            url = f"{self.AUTH_BASE_URL}/app/generate-consent"
            headers = {
                "app_id": self.api_key,
                "app_secret": self.api_secret
            }
            params = {
                "client_id": self.client_id
            }
            
            logger.info("Step 1: Generating consent...")
            response = requests.post(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    consent_app_id = data.get("consentAppId")
                    logger.info(f"✅ Consent generated: {consent_app_id}")
                    return consent_app_id
                else:
                    logger.error(f"Consent generation failed: {data}")
                    return None
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception in step 1: {e}")
            return None
    
    async def _step2_browser_automation(self, consent_app_id: str) -> Optional[str]:
        """
        Step 2: Browser-based login (REQUIRED for Individual Traders).
        
        For Individual Traders, there is NO API endpoint for Step 2.
        The login MUST happen through a browser where the user enters:
        1. Mobile number (user_id) → Click "Proceed"
        2. TOTP (6 separate digit fields) → Click "Proceed"  
        3. PIN (6 separate digit fields) → Click "Proceed"
        
        Upon successful login, browser redirects to redirect_url with tokenId parameter.
        
        Args:
            consent_app_id: Consent ID from step 1
            
        Returns:
            tokenId if successful, None otherwise
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return None
        
        try:
            logger.info("🌐 Using browser automation (Playwright) for login...")
            
            # Validate we have PIN
            pin = os.getenv("DHAN_PIN")
            if not pin:
                logger.error("❌ DHAN_PIN not found in environment variables")
                return None
            
            async with async_playwright() as p:
                # Launch headless browser (required for Cloud Run)
                browser = await p.chromium.launch(
                    headless=True,  # Headless mode for serverless environments
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-gpu',
                        '--window-size=1920x1080',
                        '--disable-blink-features=AutomationControlled',
                        '--disable-features=IsolateOrigins,site-per-process,VizDisplayCompositor',
                        '--disable-web-security',
                        '--no-zygote',  # Important for Cloud Run
                        # Note: NOT using --single-process as it can break navigation
                    ],
                    slow_mo=300  # Slow down by 300ms between actions
                )
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    java_script_enabled=True,
                    ignore_https_errors=True,
                    bypass_csp=True,  # Bypass Content Security Policy
                    extra_http_headers={
                        'Accept-Language': 'en-IN,en;q=0.9',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    }
                )
                page = await context.new_page()
                
                # Hide automation indicators
                await page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    window.chrome = {
                        runtime: {}
                    };
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-IN', 'en-US', 'en']
                    });
                """)
                
                # Navigate to consent login page
                login_url = f"{self.AUTH_BASE_URL}/login/consentApp-login?consentAppId={consent_app_id}"
                logger.info(f"🌐 Navigating to: {login_url}")
                try:
                    # Set up network logging
                    page.on("response", lambda response: logger.info(f"📡 Response: {response.status} {response.url[:80]}..."))
                    page.on("pageerror", lambda error: logger.error(f"📄 Page error: {error}"))
                    page.on("crash", lambda: logger.error("💥 Page crashed!"))
                    
                    # Use domcontentloaded instead of networkidle - faster and more reliable
                    logger.info("⏳ Starting navigation...")
                    await page.goto(login_url, wait_until="domcontentloaded", timeout=90000)
                    logger.info(f"✅ Page DOM loaded, current URL: {page.url}")
                    
                    # Wait for page to settle after initial load
                    logger.info("⏳ Waiting for full page load...")
                    await page.wait_for_load_state("load", timeout=30000)
                    time.sleep(3)  # Additional wait for any dynamic content
                    logger.info(f"✅ Page fully loaded, final URL: {page.url}")
                    
                    # Check if page loaded successfully
                    if "chrome-error://" in page.url or "about:blank" in page.url:
                        logger.error(f"❌ Page failed to load properly: {page.url}")
                        logger.info(f"📄 Page title: {await page.title()}")
                        logger.info(f"📄 Page content preview: {(await page.content())[:200]}...")
                        await page.screenshot(path="/tmp/dhan_navigation_failed.png")
                        await browser.close()
                        return None
                except Exception as e:
                    logger.error(f"❌ Navigation failed with exception: {type(e).__name__}: {e}")
                    logger.info(f"Current URL at error: {page.url}")
                    try:
                        await page.screenshot(path="/tmp/dhan_navigation_error.png")
                        logger.info("📸 Screenshot saved: /tmp/dhan_navigation_error.png")
                    except:
                        pass
                    await browser.close()
                    return None
                
                # Step 1: Fill mobile number (user_id)
                try:
                    logger.info("📱 Step 1: Entering mobile number...")
                    mobile_input = page.locator('input[type="tel"]').first
                    await mobile_input.wait_for(state="visible", timeout=10000)
                    await mobile_input.fill(self.user_id)
                    logger.info("✅ Filled mobile number")
                    time.sleep(1)
                    
                    # Click Proceed button
                    proceed_btn = page.locator('button[type="submit"]:visible').first
                    await proceed_btn.click()
                    logger.info("✅ Clicked Proceed (Step 1)")
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"❌ Step 1 (mobile) failed: {e}")
                    try:
                        await page.screenshot(path="/tmp/dhan_step1_failed.png")
                        logger.info("📸 Screenshot saved: /tmp/dhan_step1_failed.png")
                    except:
                        pass
                    await browser.close()
                    return None
                
                # Step 2: Fill TOTP (6 separate digit fields)
                try:
                    logger.info("🔐 Step 2: Entering TOTP...")
                    totp_code = self._generate_totp()
                    logger.info(f"Generated TOTP: {totp_code}")
                    
                    # Wait for TOTP fields to appear (6 separate tel inputs)
                    time.sleep(1)
                    totp_inputs = await page.locator('input[type="tel"]:visible').all()
                    
                    if len(totp_inputs) >= 6:
                        # Fill each digit into separate fields
                        for i, digit in enumerate(totp_code[:6]):
                            await totp_inputs[i].fill(digit)
                            time.sleep(0.1)  # Small delay between fields
                        logger.info("✅ Filled TOTP in 6 separate fields")
                        
                        # Wait a bit for form validation
                        time.sleep(1)
                        
                        # Click the submit button (force=True to bypass enable check)
                        proceed_btn = page.locator('button[type="submit"]').first
                        await proceed_btn.click(force=True)
                        logger.info("✅ Clicked Proceed (Step 2)")
                        time.sleep(5)  # Wait longer for page transition
                    else:
                        # Fallback: try single field
                        logger.warning(f"Expected 6 fields, found {len(totp_inputs)}, trying single field")
                        otp_input = page.locator('input[type="tel"]:visible').first
                        await otp_input.fill(totp_code)
                        await otp_input.press("Enter")
                        logger.info("✅ Filled TOTP in single field")
                        time.sleep(3)
                except Exception as e:
                    logger.error(f"❌ Step 2 (TOTP) failed: {e}")
                    try:
                        page.screenshot(path="/tmp/dhan_step2_failed.png")
                        logger.info("📸 Screenshot saved: /tmp/dhan_step2_failed.png")
                    except:
                        pass
                    browser.close()
                    return None
                
                # Step 3: Fill PIN (6 separate digit fields)
                try:
                    logger.info("🔢 Step 3: Entering PIN...")
                    
                    # Wait for PIN fields to appear (6 separate tel inputs)
                    time.sleep(2)
                    pin_inputs = await page.locator('input[type="tel"]:visible').all()
                    
                    if len(pin_inputs) >= 6:
                        # Fill each digit into separate fields
                        for i, digit in enumerate(pin[:6]):
                            await pin_inputs[i].fill(digit)
                            time.sleep(0.2)
                        logger.info("✅ Filled PIN in 6 separate fields")
                        
                        # Wait for form validation and auto-submit to complete
                        # Dhan often auto-submits after all fields are filled
                        logger.info("⏳ Waiting for auto-submit or page transition...")
                        time.sleep(5)
                        
                        # Check if URL already changed (auto-submit)
                        if "tokenId=" in page.url:
                            logger.info("✅ Auto-submit successful!")
                        else:
                            # Manual submit attempt
                            logger.info("🔘 Attempting manual submit...")
                            try:
                                # Look for any submit button or Proceed button
                                submit_selectors = [
                                    'button[type="submit"]',
                                    'button:has-text("Proceed")',
                                    'button:has-text("Submit")',
                                    'button:has-text("Continue")',
                                ]
                                
                                for selector in submit_selectors:
                                    try:
                                        btn = page.locator(selector).first
                                        if await btn.is_visible(timeout=2000):
                                            await btn.click(force=True)
                                            logger.info(f"✅ Clicked button: {selector}")
                                            break
                                    except:
                                        continue
                            except Exception as e:
                                logger.warning(f"Manual submit attempt failed: {e}")
                                # Try keyboard submit as last resort
                                try:
                                    await page.keyboard.press("Enter")
                                    logger.info("✅ Pressed Enter key")
                                except:
                                    pass
                        
                        # Wait and capture tokenId
                        # The consentAppConsume API might return tokenId in response body
                        logger.info("⏳ Monitoring for tokenId in network responses...")
                        
                        captured_tokenid = None
                        
                        # Intercept the consentAppConsume response
                        async def capture_consent_response(response):
                            nonlocal captured_tokenid
                            if "consentAppConsume" in response.url and response.status == 200:
                                try:
                                    data = await response.json()
                                    logger.info(f"📡 consentAppConsume response: {data}")
                                    if "tokenId" in data:
                                        captured_tokenid = data["tokenId"]
                                        logger.info(f"✅ Captured tokenId from API response: {captured_tokenid[:20]}...")
                                    elif "token_id" in data:
                                        captured_tokenid = data["token_id"]
                                        logger.info(f"✅ Captured token_id from API response: {captured_tokenid[:20]}...")
                                except Exception as e:
                                    logger.warning(f"Could not parse consentAppConsume response: {e}")
                        
                        page.on("response", lambda r: asyncio.create_task(capture_consent_response(r)))
                        
                        # Wait up to 15 seconds
                        for attempt in range(30):  # 15 seconds
                            if captured_tokenid:
                                logger.info(f"🎉 TokenId captured from API response!")
                                await browser.close()
                                return captured_tokenid
                            
                            # Also check URL
                            current_url = page.url
                            if "tokenId=" in current_url:
                                captured_tokenid = current_url.split("tokenId=")[1].split("&")[0]
                                logger.info(f"✅ Found tokenId in URL: {captured_tokenid[:20]}...")
                                break
                            
                            if attempt % 5 == 0:
                                logger.info(f"🔍 Checking (attempt {attempt}/30): {current_url[:80]}...")
                            
                            await asyncio.sleep(0.5)
                        
                        if captured_tokenid:
                            logger.info(f"🎉 TokenId captured!")
                            await browser.close()
                            return captured_tokenid
                            
                    else:
                        # Fallback: try password field
                        logger.warning(f"Expected 6 fields, found {len(pin_inputs)}, trying password field")
                        pin_input = page.locator('input[type="password"]:visible').first
                        await pin_input.fill(pin)
                        await pin_input.press("Enter")
                        logger.info("✅ Filled PIN in password field")
                    
                    # Only reach here if tokenId wasn't found in loop above
                    # Wait for URL to change and contain tokenId
                    logger.info("⏳ Waiting for tokenId in URL...")
                    token_id = None
                    
                    # Strategy: Keep checking URL continuously, even if page shows error
                    # The tokenId appears in URL immediately after successful auth
                    max_attempts = 120  # 60 seconds (0.5s intervals)
                    
                    for attempt in range(max_attempts):
                        current_url = page.url
                        
                        # Log URL changes to debug
                        if attempt == 0 or attempt % 20 == 0:  # Log every 10 seconds
                            logger.info(f"Checking URL (attempt {attempt+1}/{max_attempts}): {current_url[:100]}...")
                        
                        # Check if tokenId is in URL (works even on error pages)
                        if "tokenId=" in current_url:
                            logger.info(f"✅ Found tokenId in URL: {current_url}")
                            try:
                                # Extract tokenId from URL
                                token_id = current_url.split("tokenId=")[1].split("&")[0].split("#")[0]
                                logger.info(f"✅ Extracted tokenId: {token_id}")
                                break
                            except Exception as e:
                                logger.warning(f"Failed to extract tokenId from URL: {e}")
                        
                        # Also check for common error patterns that might contain tokenId
                        if "callback" in current_url.lower() and "token" in current_url.lower():
                            logger.info(f"⚠️  Possible tokenId in callback URL: {current_url}")
                            # Try to extract any UUID-like pattern
                            import re
                            uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
                            matches = re.findall(uuid_pattern, current_url, re.IGNORECASE)
                            if matches:
                                token_id = matches[0]
                                logger.info(f"✅ Extracted tokenId via pattern matching: {token_id}")
                                break
                        
                        time.sleep(0.5)
                    
                    if not token_id:
                        logger.warning(f"❌ No tokenId found after {max_attempts * 0.5}s")
                        logger.info(f"Final URL: {page.url}")
                        # Take screenshot for debugging
                        try:
                            await page.screenshot(path="/tmp/dhan_no_tokenid.png")
                            logger.info("📸 Screenshot saved: /tmp/dhan_no_tokenid.png")
                        except:
                            pass
                    
                    current_url = page.url
                except Exception as e:
                    logger.error(f"❌ Step 3 (PIN) failed: {e}")
                    try:
                        await page.screenshot(path="/tmp/dhan_step3_failed.png")
                        logger.info("📸 Screenshot saved: /tmp/dhan_step3_failed.png")
                    except:
                        pass
                    await browser.close()
                    return None
                
                # Check if we got tokenId
                if token_id:
                    logger.info(f"🎉 Browser automation successful! TokenId: {token_id[:10]}...")
                    await browser.close()
                    return token_id
                
                # Fallback: Try extracting from current URL one more time
                logger.info(f"Final URL check: {current_url}")
                if "tokenId=" in current_url:
                    try:
                        token_id = current_url.split("tokenId=")[1].split("&")[0]
                        logger.info(f"🎉 Browser automation successful! TokenId: {token_id[:10]}...")
                        await browser.close()
                        return token_id
                    except Exception as e:
                        logger.error(f"Failed to extract tokenId from final URL: {e}")
                
                # No tokenId found
                logger.error("❌ No tokenId found in URL after login")
                try:
                    await page.screenshot(path="/tmp/dhan_login_failed.png")
                    logger.info("📸 Screenshot saved: /tmp/dhan_login_failed.png")
                except:
                    pass
                await browser.close()
                return None
                
        except Exception as e:
            logger.error(f"Browser automation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def _step3_consume_consent(self, token_id: str) -> Optional[Tuple[str, datetime]]:
        """
        Step 3: Consume consent to get access token.
        
        Args:
            token_id: Token ID from step 2
            
        Returns:
            Tuple of (access_token, expiry_datetime) if successful, None otherwise
        """
        try:
            url = f"{self.AUTH_BASE_URL}/app/consumeApp-consent"
            headers = {
                "app_id": self.api_key,
                "app_secret": self.api_secret
            }
            params = {
                "tokenId": token_id
            }
            
            logger.info("Step 3: Consuming consent to get access token...")
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                access_token = data.get("accessToken")
                expiry_str = data.get("expiryTime")
                
                if access_token:
                    # Parse expiry time (format: "2025-09-23T12:37:23")
                    try:
                        expiry = datetime.strptime(expiry_str, "%Y-%m-%dT%H:%M:%S")
                    except:
                        # Fallback: assume 24 hours from now
                        expiry = datetime.now() + timedelta(hours=24)
                    
                    logger.info(f"✅ Access token obtained, expires at {expiry}")
                    return access_token, expiry
                else:
                    logger.error(f"No access token in response: {data}")
                    return None
            else:
                logger.error(f"HTTP {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Exception in step 3: {e}")
            return None
    
    async def generate_new_token(self) -> Optional[str]:
        """
        Generate a new access token using the 3-step OAuth flow.
        
        For Individual Traders:
        - Step 1: Generate consent (API call)
        - Step 2: Browser login (MUST use browser - no API endpoint exists)
          OR use tokenId from OAuth callback if available
        - Step 3: Consume consent (API call)
        
        Returns:
            New access token if successful, None otherwise
        """
        logger.info("🔄 Starting automatic token generation...")
        
        # Check if we have a tokenId from OAuth callback
        if self._pending_token_id:
            logger.info("✅ Using tokenId from OAuth callback")
            token_id = self._pending_token_id
            self._pending_token_id = None  # Clear it after use
            
            # Step 3: Consume consent with the callback tokenId
            result = self._step3_consume_consent(token_id)
            if not result:
                logger.error("❌ Failed at step 3 (consume consent with callback tokenId)")
                return None
            
            access_token, expiry = result
            self._access_token = access_token
            self._token_expiry = expiry
            
            logger.info(f"✅ Token generation complete! Expires at {expiry}")
            
            # Update local .env file with new token
            self._update_env_file(access_token)
            
            return access_token
        
        # Otherwise, use full browser automation flow
        # Step 1: Generate consent
        consent_app_id = self._step1_generate_consent()
        if not consent_app_id:
            logger.error("❌ Failed at step 1 (generate consent)")
            return None
        
        # Wait a moment for consent to be processed
        time.sleep(2)
        
        # Step 2: Browser login (REQUIRED - no API alternative for Individual Traders)
        logger.info("Step 2: Browser login required...")
        token_id = await self._step2_browser_automation(consent_app_id)
            
        if not token_id:
            logger.error("❌ Failed at step 2 (browser login)")
            logger.info("💡 TIP: For Individual Traders, browser login is mandatory")
            logger.info("💡 Alternative: Generate access token manually from web.dhan.co")
            return None
        
        # Wait a moment for token to be processed
        time.sleep(2)
        
        # Step 3: Consume consent
        result = self._step3_consume_consent(token_id)
        if not result:
            logger.error("❌ Failed at step 3 (consume consent)")
            return None
        
        access_token, expiry = result
        self._access_token = access_token
        self._token_expiry = expiry
        
        logger.info(f"✅ Token generation complete! Expires at {expiry}")
        
        # Update local .env file with new token
        self._update_env_file(access_token)
        
        return access_token
    
    def _update_env_file(self, new_token: str) -> bool:
        """
        Update DHAN_ACCESS_TOKEN in local .env file
        
        Args:
            new_token: New access token to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            env_path = os.path.join(os.path.dirname(__file__), '.env')
            
            if not os.path.exists(env_path):
                logger.warning(f"⚠️  .env file not found at {env_path}, skipping update")
                return False
            
            # Read existing .env file
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            # Update DHAN_ACCESS_TOKEN line
            updated = False
            new_lines = []
            for line in lines:
                if line.startswith('DHAN_ACCESS_TOKEN='):
                    new_lines.append(f'DHAN_ACCESS_TOKEN={new_token}\n')
                    updated = True
                    logger.info("✅ Updated DHAN_ACCESS_TOKEN in .env file")
                else:
                    new_lines.append(line)
            
            # If token wasn't found, append it
            if not updated:
                new_lines.append(f'\nDHAN_ACCESS_TOKEN={new_token}\n')
                logger.info("✅ Added DHAN_ACCESS_TOKEN to .env file")
            
            # Write back to .env file
            with open(env_path, 'w') as f:
                f.writelines(new_lines)
            
            logger.info(f"📝 Local .env file updated with new token")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update .env file: {e}")
            return False
    
    async def get_valid_token(self, auto_refresh: bool = True) -> Optional[str]:
        """
        Get a valid access token, automatically generating new one if needed.
        
        Args:
            auto_refresh: If True, automatically generate new token when expired
            
        Returns:
            Valid access token or None if unable to get one
        """
        # Check if current token is valid
        if self._is_token_valid():
            return self._access_token
        
        # Token invalid or expiring soon
        if not auto_refresh:
            logger.warning("Token invalid and auto_refresh disabled")
            return None
        
        # Generate new token
        logger.info("Token expired or expiring soon, generating new token...")
        return await self.generate_new_token()
    
    def refresh_token(self) -> Optional[str]:
        """
        Refresh existing token using RenewToken endpoint.
        
        Note: This only works for tokens generated from Dhan Web.
        For API key-based tokens, use generate_new_token() instead.
        
        Returns:
            New access token if successful, None otherwise
        """
        if not self._access_token:
            logger.error("No existing token to refresh")
            return None
        
        try:
            url = f"{self.API_BASE_URL}/RenewToken"
            headers = {
                "access-token": self._access_token,
                "dhanClientId": self.client_id
            }
            
            logger.info("🔄 Attempting to refresh token...")
            response = requests.post(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("access_token") or data.get("accessToken")
                
                if new_token:
                    expiry = self._decode_token_expiry(new_token)
                    self._access_token = new_token
                    self._token_expiry = expiry
                    logger.info(f"✅ Token refreshed successfully, expires at {expiry}")
                    return new_token
                else:
                    logger.error(f"No token in refresh response: {data}")
                    return None
            else:
                logger.warning(f"Token refresh failed (HTTP {response.status_code}), will generate new token")
                # Fall back to generating new token
                return self.generate_new_token()
                
        except Exception as e:
            logger.error(f"Exception refreshing token: {e}")
            # Fall back to generating new token
            return self.generate_new_token()


def load_auth_from_env() -> Optional[DhanAuth]:
    """
    Load Dhan authentication from environment variables.
    
    Required env vars:
    - DHAN_CLIENT_ID
    - DHAN_API_KEY
    - DHAN_API_SECRET
    - DHAN_TOTP_SECRET
    - DHAN_USER_ID
    - DHAN_PASSWORD
    - DHAN_ACCESS_TOKEN (optional)
    
    Returns:
        DhanAuth instance or None if required vars missing
    """
    # Load .env file if it exists
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv("DHAN_CLIENT_ID")
    api_key = os.getenv("DHAN_API_KEY")
    api_secret = os.getenv("DHAN_API_SECRET")
    totp_secret = os.getenv("DHAN_TOTP_SECRET")
    user_id = os.getenv("DHAN_USER_ID")
    password = os.getenv("DHAN_PASSWORD")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    redirect_uri = os.getenv("DHAN_REDIRECT_URI")
    
    if not all([client_id, api_key, api_secret, totp_secret, user_id, password]):
        missing = []
        if not client_id: missing.append("DHAN_CLIENT_ID")
        if not api_key: missing.append("DHAN_API_KEY")
        if not api_secret: missing.append("DHAN_API_SECRET")
        if not totp_secret: missing.append("DHAN_TOTP_SECRET")
        if not user_id: missing.append("DHAN_USER_ID")
        if not password: missing.append("DHAN_PASSWORD")
        
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        return None
    
    return DhanAuth(
        client_id=client_id,
        api_key=api_key,
        api_secret=api_secret,
        totp_secret=totp_secret,
        user_id=user_id,
        password=password,
        access_token=access_token,
        redirect_uri=redirect_uri
    )


if __name__ == "__main__":
    # Test token generation
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    from dotenv import load_dotenv
    load_dotenv()
    
    auth = load_auth_from_env()
    if auth:
        token = auth.get_valid_token()
        if token:
            print(f"\n✅ Got valid token: {token[:50]}...")
            print(f"Expires: {auth._token_expiry}")
        else:
            print("\n❌ Failed to get valid token")
    else:
        print("\n❌ Failed to load authentication from environment")
