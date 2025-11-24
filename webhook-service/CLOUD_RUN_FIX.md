# Cloud Run Webhook Service Fix

## Problem Summary

**Date**: November 24, 2025
**Issue**: TradingView alerts sent to `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/webhook` are not placing Dhan orders or sending Telegram notifications.

### Root Causes Identified:

1. **Playwright Sync API Error** (CRITICAL)
   - Cloud Run service crashes during startup when trying to authenticate with Dhan
   - Error: `"It looks like you are using Playwright Sync API inside the asyncio loop. Please use the Async API instead."`
   - Location: `dhan_auth.py`, line 208: `with sync_playwright() as p:`
   - Impact: Authentication fails, service falls back to log-only mode

2. **Service Running in Log-Only Mode**
   - Without valid Dhan authentication, the service sets `ENABLE_DHAN=false`
   - Orders are logged to CSV but not executed
   - Telegram notifications are disabled

3. **Token Expired**
   - Last valid token expired on Nov 23, 2025 at 22:47
   - Auto-refresh failed due to Playwright error
   - Service has been in failed state since Nov 24, 03:53 AM

### Evidence from Logs:

```
2025-11-24T03:53:06.253956Z - ❌ Failed at step 2 (browser login)
2025-11-24T03:53:06.253946Z - playwright._impl._errors.Error: It looks like you are using Playwright Sync API inside the asyncio loop.
2025-11-24T03:53:06.254140Z - ❌ Failed to get valid access token
2025-11-24T03:53:06.254173Z - Orders will be logged only, not executed
```

---

## Solutions (Choose One)

### Option 1: Manual Token Generation (QUICK FIX - 5 minutes)

**Pros**: Works immediately, no code changes
**Cons**: Token expires every 24 hours, requires manual renewal

**Steps**:
1. Login to https://web.dhan.co
2. Open browser DevTools (F12) → Network tab
3. Look for API requests with `access_token` in headers
4. Copy the token value
5. Update Cloud Run environment variable:
   ```bash
   gcloud run services update tradingview-webhook \
     --region=asia-south1 \
     --set-env-vars="DHAN_ACCESS_TOKEN=<your_token_here>"
   ```
6. Service will restart and use the manual token

### Option 2: Fix Playwright to Use Async API (PROPER FIX - 30 minutes)

**Pros**: Permanent fix, auto-refresh works
**Cons**: Requires code changes and redeployment

**Required Changes**:

#### 1. Update `dhan_auth.py` imports:
```python
# Change from:
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# To:
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
```

#### 2. Convert `_step2_browser_automation()` to async:
```python
# Change from:
def _step2_browser_automation(self, consent_app_id: str) -> Optional[str]:
    ...
    with sync_playwright() as p:
        browser = p.chromium.launch(...)

# To:
async def _step2_browser_automation(self, consent_app_id: str) -> Optional[str]:
    ...
    async with async_playwright() as p:
        browser = await p.chromium.launch(...)
```

#### 3. Update all Playwright calls to await:
```python
# Examples:
browser = await p.chromium.launch(...)
context = await browser.new_context(...)
page = await context.new_page()
await page.goto(url)
await mobile_input.fill(value)
await button.click()
await browser.close()
```

#### 4. Update callers of `_step2_browser_automation()`:
```python
# In generate_token() method:
# Change from:
token_id = self._step2_browser_automation(consent_app_id)

# To:
token_id = await self._step2_browser_automation(consent_app_id)
```

#### 5. Make `generate_token()` async:
```python
async def generate_token(self, force_new: bool = False) -> Optional[str]:
    # ... existing code ...
```

#### 6. Redeploy to Cloud Run:
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
gcloud run deploy tradingview-webhook \
  --source . \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars-file .env.yaml
```

### Option 3: Run Playwright in Separate Thread (ALTERNATIVE FIX - 20 minutes)

**Pros**: Minimal code changes, sync Playwright still works
**Cons**: More complex, uses threading

**Required Changes**:

#### 1. Update `dhan_auth.py` to use thread executor:
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# In DhanAuth class:
def _sync_browser_automation(self, consent_app_id: str) -> Optional[str]:
    """Synchronous browser automation (runs in thread)"""
    with sync_playwright() as p:
        # ... existing code ...

async def _step2_browser_automation(self, consent_app_id: str) -> Optional[str]:
    """Async wrapper that runs sync code in thread"""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            self._sync_browser_automation,
            consent_app_id
        )
    return result
```

#### 2. Make generate_token() async and redeploy

---

## Recommended Approach

**For immediate fix**: Use **Option 1** (manual token) today to unblock TradingView alerts

**For permanent solution**: Implement **Option 2** (async Playwright) this week

---

## Verification Steps

After implementing any fix:

### 1. Check Cloud Run logs:
```bash
gcloud logging read \
  'resource.type="cloud_run_revision" AND resource.labels.service_name="tradingview-webhook"' \
  --limit 20 --format json --freshness=10m
```

### 2. Test /health endpoint:
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "dhan_authenticated": true,
  "telegram_enabled": true,
  "market_status": "...",
  "timestamp": "..."
}
```

### 3. Send test webhook:
```bash
curl -X POST https://tradingview-webhook-cgy4m5alfq-el.a.run.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "transactionType": "BUY",
        "quantity": 1,
        "orderType": "MARKET",
        "productType": "INTRADAY",
        "price": 0,
        "amoTime": "OPEN"
      }
    ]
  }'
```

### 4. Check Telegram for notification

### 5. Verify CSV log:
```bash
gcloud run services logs read tradingview-webhook --region=asia-south1 --limit=10
```

---

## Current Service Status

- **Local Service**: Running on localhost:8080 ✅
  - Last activity: Nov 20, 2025
  - Dhan authenticated (but token expired Nov 24)
  
- **Cloud Run Service**: Running but broken ❌
  - URL: https://tradingview-webhook-cgy4m5alfq-el.a.run.app
  - Status: Playwright error on startup
  - Mode: Log-only (orders not executed)
  - Last successful run: Nov 22, 2025

---

## Files to Modify

For Option 2 (Async Playwright):
- `webhook-service/dhan_auth.py` - Convert to async
- `webhook-service/app.py` - Update token generation calls
- `webhook-service/requirements.txt` - Verify playwright version

For deployment:
- `webhook-service/Dockerfile` - Already correct
- `.env.yaml` - Environment variables

---

## Prevention

To prevent this issue in future:

1. **Add Error Monitoring**: Set up Cloud Run alerting for startup failures
2. **Health Check Automation**: Monitor /health endpoint every 5 minutes
3. **Token Expiry Alerts**: Send Telegram notification when token < 2 hours remaining
4. **Testing**: Test Cloud Run deployments in staging before production
5. **Fallback**: Keep manual token generation as backup method

---

## Contact

If you need help implementing any of these fixes, let me know which option you prefer and I can guide you through the specific steps.
