# Dhan Live Trading System - Complete Deployment Guide

> **All-in-One Guide**: OAuth Setup, Architecture, Live Trading, and Production Operations

**Last Updated**: 26-Nov-2025 03:00 IST  
**Status**: ✅ Production Ready  
**Service URL**: https://dhan-webhook-service-86335712552.asia-south1.run.app

---

## 📑 Table of Contents

1. [System Overview](#system-overview)
2. [Quick Start (15 Minutes)](#quick-start-15-minutes)
3. [Architecture & Components](#architecture--components)
4. [OAuth Authentication](#oauth-authentication)
5. [Configuration Management](#configuration-management)
6. [Live Trading Operations](#live-trading-operations)
7. [Order Types & Execution](#order-types--execution)
8. [Monitoring & Maintenance](#monitoring--maintenance)
9. [Troubleshooting](#troubleshooting)
10. [Security Best Practices](#security-best-practices)
11. [Advanced Features](#advanced-features)

---

## System Overview

### What This Does

Automatically executes trading orders on Dhan when TradingView alerts trigger:

```
TradingView Alert → Cloud Webhook → OAuth Token → Dhan API → Order Placed
```

### Current Deployment

| Component | Status | Details |
|-----------|--------|---------|
| **Service** | ✅ Running | Cloud Run (Mumbai region) |
| **OAuth** | ✅ Active | Auto-refresh daily at 8 AM IST |
| **Token** | ✅ Valid | Expires: 27-Nov-2025 02:07 IST |
| **Cron Job** | ✅ Enabled | Daily health check + refresh |
| **Telegram** | ⚠️ Configure | Notifications (optional) |

### New Architecture (Nov 2025)

Three production-ready modules created:

1. **`config_manager.py`** - Centralized configuration (ENV → Secret Manager → .env)
2. **`oauth_service.py`** - OAuth interface for webhook & backtesting
3. **`utils/production_utils.py`** - Retry logic, circuit breaker, security

---

## Quick Start (15 Minutes)

### Prerequisites

- Google Cloud account
- Dhan trading account
- TradingView account (Pro for webhooks)

### Step 1: Get Dhan Credentials (5 min)

1. Login to https://web.dhan.co
2. Settings → API Management
3. Copy:
   - **Client ID**: `1108351648`
   - **API Key**: `fdbe282b...`
   - **API Secret**: `457c0207-2d9c...`

### Step 2: OAuth Setup (5 min)

**OAuth Flow** (Browser-based, one-time per day):

```
Visit Dhan API Management
    ↓
Click "Authorize"
    ↓
Complete 2FA (Mobile OTP + TOTP + PIN)
    ↓
Redirect to callback URL with tokenId
    ↓
Service generates access token (valid ~30 hours)
```

**Automated Daily Refresh**:
- Cron job runs at 8:00 AM IST
- Checks token validity
- Triggers OAuth if expiring (<1 hour)
- Updates Secret Manager + both .env files

### Step 3: Test Service (2 min)

```bash
# Health check
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/health

# Token status
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready

# Expected:
# {"ready": true, "checks": {"dhan_client": "initialized", "access_token": "valid"}}
```

### Step 4: Configure TradingView (3 min)

1. Create alert on TradingView
2. Add webhook URL: `https://dhan-webhook-service-86335712552.asia-south1.run.app/webhook`
3. Alert message:

```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [{
    "transactionType": "B",
    "orderType": "MKT",
    "quantity": "1",
    "exchange": "NSE",
    "symbol": "{{ticker}}",
    "instrument": "EQ",
    "productType": "C",
    "sort_order": "1",
    "price": "0"
  }]
}
```

4. Test alert manually
5. Check order in Dhan app

---

## Architecture & Components

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    TradingView Alert                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│            Webhook Service (Cloud Run)                  │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │   app.py    │→│ oauth_service│→│ dhan_client.py│ │
│  │  (FastAPI)  │  │  (Token)     │  │  (API)        │ │
│  └─────────────┘  └──────────────┘  └───────────────┘ │
│         │                                    │          │
│         ▼                                    ▼          │
│  ┌─────────────────┐              ┌──────────────────┐│
│  │ config_manager  │              │ Secret Manager   ││
│  │ (Config)        │              │ (Tokens)         ││
│  └─────────────────┘              └──────────────────┘│
└──────────────────────────┬──────────────────────────────┘
                           │
                           ▼
               ┌──────────────────────┐
               │     Dhan API         │
               │  (Order Placement)   │
               └──────────────────────┘
```

### File Structure

```
webhook-service/
├── app.py                         # FastAPI webhook server
├── dhan_auth.py                   # OAuth 2.0 implementation (3-step)
├── dhan_client.py                 # Dhan API wrapper
├── telegram_notifier.py           # Telegram notifications
├── security_id_list.csv           # 217,959 tradable symbols
├── webhook_orders.csv             # Order history (IST timestamps)
├── .env                           # Local credentials
├── Dockerfile                     # Cloud deployment
├── requirements.txt               # Dependencies
└── docs/
    └── COMPLETE_DEPLOYMENT_GUIDE.md   # This file

Root:
├── core/
│   └── config_manager.py          # Centralized config (MOVED from root)
└── utils/
    └── production_utils.py        # Retry, circuit breaker, security (NEW)
```

### Dependencies

```
fastapi==0.115.6           # Web framework
uvicorn==0.34.0            # ASGI server
dhanhq==2.0.2              # Dhan API client
pydantic==2.10.4           # Data validation
python-dotenv==1.0.1       # Environment variables
playwright==1.49.1         # Browser automation (OAuth)
pyotp==2.9.0               # TOTP codes
aiohttp==3.11.11           # Async HTTP (Telegram)
google-cloud-secret-manager # Google Secret Manager
```

---

## OAuth Authentication

### How OAuth Works

Dhan uses OAuth 2.0 with 3-step authorization:

**Step 1: Generate Consent**
```bash
POST https://auth.dhan.co/app/generate-consent
Headers: app_id (API key), app_secret (API secret)
Returns: consentAppId (UUID)
```

**Step 2: Browser Authorization** (Playwright automation)
```bash
1. Navigate to: https://auth.dhan.co/consentApp-login?{consentAppId}
2. Enter mobile number
3. Enter TOTP code (Google Authenticator)
4. Enter PIN
5. Capture tokenId from redirect URL
```

**Step 3: Generate Access Token**
```bash
GET https://auth.dhan.co/app/consumeApp-consent?tokenId={tokenId}
Returns: access_token (JWT, valid ~30 hours)
```

### OAuth Implementation

**File**: `webhook-service/dhan_auth.py` (1137 lines)

Key methods:
- `generate_new_token()` - Full 3-step OAuth flow
- `_step1_generate_consent()` - Get consent ID
- `_step2_browser_automation()` - Playwright automation (mobile + TOTP + PIN)
- `_step3_consume_consent()` - Get access token
- `get_valid_token()` - Check validity, auto-refresh if needed

### Token Storage

Tokens stored in 3 locations (priority order):

1. **Environment Variables** (highest priority)
2. **Google Secret Manager** (production)
3. **.env files** (local development)
   - `/webhook-service/.env` (service)
   - `/.env` (root - for backtesting)

**Auto-Update**: `_update_env_file()` method updates all 3 locations when new token generated.

### Token Lifecycle

```
Token Generated (30 hours validity)
    ↓
Stored in: Secret Manager + 2x .env files
    ↓
Cron job checks daily (8 AM IST)
    ↓
If < 1 hour remaining:
    ↓
Trigger OAuth flow (browser automation)
    ↓
New token generated → Update all 3 locations
    ↓
Repeat cycle
```

### Cron Job Configuration

```bash
# Job: dhan-token-refresh
# Schedule: 0 8 * * * (Asia/Kolkata timezone)
# Endpoint: /refresh-token (FIXED - was /ready before)
# URL: https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token

# Check status
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Manual trigger
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# View logs
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit=20
```

### OAuth Credentials

Required in `.env`:

```bash
# Dhan OAuth Credentials
DHAN_CLIENT_ID=1108351648
DHAN_API_KEY=fdbe282b...
DHAN_API_SECRET=457c0207-2d9c-4a94-b44b-ac530c64894d

# Automation Credentials (for browser login)
DHAN_USER_ID=9624973000          # Mobile number
DHAN_TOTP_SECRET=N26PEJEHQR...   # TOTP secret (from Dhan)
DHAN_PASSWORD=your_password       # Dhan login password
DHAN_PIN=123456                   # 6-digit PIN

# Optional: Pre-generated token (will be refreshed)
DHAN_ACCESS_TOKEN=eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9...
```

---

## Configuration Management

### New: Centralized Config Manager

**File**: `core/config_manager.py` (324 lines)

Loads configuration from multiple sources with priority:

```python
from core.config_manager import get_config

config = get_config()

# Get single value
client_id = config.get('DHAN_CLIENT_ID')

# Get all Dhan credentials
dhan_config = config.get_dhan_config()

# Update token (updates Secret Manager + both .env files)
config.update_token(new_token, expiry_datetime)

# Validate required keys present
valid, missing_keys = config.validate_dhan_config()
```

**Priority Chain**:
1. Environment variables (highest)
2. Google Secret Manager
3. .env files (lowest)

**Auto-Update**: When token refreshes, automatically updates all 3 locations.

### New: OAuth Service Interface

**File**: `oauth_service.py` (246 lines)

Clean interface wrapping `dhan_auth.py`:

```python
# Async (for webhook service)
from oauth_service import get_dhan_token

token = await get_dhan_token()  # Auto-refreshes if expired

# Sync (for backtesting)
from oauth_service import get_dhan_token_sync

token = get_dhan_token_sync()

# Check token status
from oauth_service import check_token_status

status = check_token_status()
# Returns: {valid, expiry, hours_remaining, needs_refresh}
```

**Use Cases**:
- Webhook service: `await get_dhan_token()`
- Backtesting runners: `get_dhan_token_sync()`
- Health checks: `check_token_status()`

### Environment Variables

**Webhook Service** (`webhook-service/.env`):

```bash
# Core Settings
ENABLE_DHAN=true                 # Enable live trading
ENVIRONMENT=production
PORT=8080

# Dhan OAuth
DHAN_CLIENT_ID=1108351648
DHAN_API_KEY=fdbe282b...
DHAN_API_SECRET=457c0207-2d9c...
DHAN_USER_ID=9624973000
DHAN_TOTP_SECRET=N26PEJEHQR...
DHAN_PASSWORD=your_password
DHAN_PIN=123456

# Security
WEBHOOK_SECRET=GTcl4

# Telegram (Optional)
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=987654321

# Logging
CSV_LOG_PATH=/app/webhook_orders.csv
```

**Root** (`.env` for backtesting):

```bash
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJhbGci...
```

---

## Live Trading Operations

### Order Flow

```
1. TradingView Alert Triggered
   ↓
2. HTTP POST to /webhook endpoint
   ↓
3. Validate webhook secret
   ↓
4. Check market status (AMO supported)
   ↓
5. Get valid OAuth token (auto-refresh if needed)
   ↓
6. Map symbol → security_id (security_id_list.csv)
   ↓
7. Place order via Dhan API
   ↓
8. Log to webhook_orders.csv (IST timestamp)
   ↓
9. Send Telegram notification (if configured)
   ↓
10. Return 200 OK to TradingView
```

### Order Types

| Type | Code | Description | Use Case |
|------|------|-------------|----------|
| **Market** | `MKT` | Execute at best price | Immediate execution |
| **Limit** | `LMT` | Execute at specific price | Control entry price |
| **Stop Loss** | `SL` | Trigger limit order | Limit losses |
| **Stop Loss Market** | `SL-M` | Trigger market order | Guaranteed stop |

### Product Types

| Type | Code | Margin | Holding | Use Case |
|------|------|--------|---------|----------|
| **CNC** | `C` | 100% | Overnight (T+2) | Delivery |
| **Intraday** | `I` | 20-40% | Same day | Day trading |
| **Margin** | `M` | Varies | Overnight | Leveraged |

### Market Hours (IST)

- **Pre-open**: 9:00-9:15 AM
- **Normal**: 9:15 AM - 3:30 PM
- **AMO Orders**: Outside market hours (executed next session)

### Order Examples

**Market Buy (Delivery)**:
```json
{
  "transactionType": "B",
  "orderType": "MKT",
  "quantity": "10",
  "price": "0",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

**Limit Sell**:
```json
{
  "transactionType": "S",
  "orderType": "LMT",
  "quantity": "10",
  "price": "2550.00",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

**Stop Loss Market**:
```json
{
  "transactionType": "S",
  "orderType": "SL-M",
  "quantity": "10",
  "price": "0",
  "triggerPrice": "2450.00",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

### Multi-Leg Orders

**Bracket Order** (Entry + Stop + Target):
```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "sort_order": "1",
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "10",
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "productType": "I"
    },
    {
      "sort_order": "2",
      "transactionType": "S",
      "orderType": "SL-M",
      "quantity": "10",
      "triggerPrice": "2450.00",
      "symbol": "RELIANCE"
    },
    {
      "sort_order": "3",
      "transactionType": "S",
      "orderType": "LMT",
      "quantity": "10",
      "price": "2600.00",
      "symbol": "RELIANCE"
    }
  ]
}
```

---

## Monitoring & Maintenance

### Health Checks

**Endpoints**:

1. `/health` - Basic health
   ```bash
   curl https://dhan-webhook-service-86335712552.asia-south1.run.app/health
   ```

2. `/ready` - Token status
   ```bash
   curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready
   # Returns: {ready, checks: {dhan_client, access_token}, token_expires_in_hours}
   ```

3. `/refresh-token` - Force token refresh (used by cron)
   ```bash
   curl -X POST https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token
   ```

### Daily Checklist

**Morning (8:00-8:30 AM IST)**:
```bash
# 1. Check cron ran
gcloud scheduler jobs list --location=asia-south1

# 2. Verify token refreshed
gcloud logging read 'textPayload:"Token"' --limit=5

# 3. Check token expiry
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready | jq '.token_expires_in_hours'
```

**During Trading (9:15 AM - 3:30 PM)**:
```bash
# Monitor webhooks
gcloud logging read 'textPayload:"Alert received"' --limit=10

# Check orders
gcloud logging read 'textPayload:"Order placed"' --limit=10
```

**Evening**:
```bash
# Review order history
cat webhook_orders.csv | tail -20

# Check error logs
gcloud logging read 'severity>=ERROR' --limit=20
```

### Viewing Logs

```bash
# Real-time tail
gcloud logging tail 'resource.type=cloud_run_revision' --limit=50

# Recent logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# Search specific
gcloud logging read 'textPayload:"OAuth"' --limit=20

# Errors only
gcloud logging read 'severity>=ERROR' --limit=50
```

### Telegram Notifications (Optional)

**Setup**:

1. Create Telegram bot via @BotFather
2. Get bot token: `123456:ABC-DEF...`
3. Get chat ID: Message bot, then visit `https://api.telegram.org/bot{token}/getUpdates`
4. Add to `.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=987654321
   ```
5. Redeploy service

**Notifications Sent**:
- ✅ Alert received
- ✅ Order placed successfully
- ❌ Order failed
- ⚠️ Token expiring soon
- 📊 Daily summary

**Fix Telegram Not Working**:

```bash
# Check environment variables
gcloud run services describe dhan-webhook-service \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].env)"

# Update if missing
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars TELEGRAM_BOT_TOKEN=your_token,TELEGRAM_CHAT_ID=your_chat_id
```

---

## Troubleshooting

### Token Expired

**Symptoms**: 401 errors, orders not executing

**Diagnosis**:
```bash
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready
# Check: token_expires_in_hours
```

**Solutions**:
1. Wait for 8 AM cron to auto-refresh
2. Manual trigger:
   ```bash
   gcloud scheduler jobs run dhan-token-refresh --location=asia-south1
   ```
3. Force refresh via endpoint:
   ```bash
   curl -X POST https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token
   ```

### Cron Job Not Running

**Check Status**:
```bash
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1
# Look for: state: ENABLED
```

**If Paused**:
```bash
gcloud scheduler jobs resume dhan-token-refresh --location=asia-south1
```

**Check Logs**:
```bash
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit=20
```

### Orders Not Placing

**1. Check ENABLE_DHAN**:
```bash
gcloud run services describe dhan-webhook-service \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].env[?name=='ENABLE_DHAN'].value)"
```

**If false**:
```bash
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars ENABLE_DHAN=true
```

**2. Check Token**:
```bash
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready
```

**3. Check Logs**:
```bash
gcloud logging read 'textPayload:"Order" OR textPayload:"Error"' --limit=20
```

### Symbol Not Found

**Error**: `SecurityId not found for symbol RELIANCE_NSE`

**Cause**: Symbol format wrong or not in `security_id_list.csv`

**Solutions**:
- Check symbol format: Use `RELIANCE` not `RELIANCE-EQ`
- Verify in CSV: `grep RELIANCE webhook-service/security_id_list.csv`
- Update CSV if needed (217,959 instruments included)

### Market Closed

**Error**: `Market is closed`

**Cause**: Order placed outside 9:15 AM - 3:30 PM IST

**Solutions**:
- AMO orders accepted outside market hours
- Check webhook service supports AMO (it does!)
- Verify market status endpoint working

### Telegram Not Working

**Symptoms**: No notifications received

**Check Configuration**:
```bash
# View environment variables
gcloud run services describe dhan-webhook-service \
  --region=asia-south1 \
  --format=yaml | grep -A 2 TELEGRAM

# Expected:
# - name: TELEGRAM_BOT_TOKEN
#   value: 123456:ABC...
# - name: TELEGRAM_CHAT_ID
#   value: 987654321
```

**If Missing**:
```bash
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars TELEGRAM_BOT_TOKEN=your_token,TELEGRAM_CHAT_ID=your_chat_id
```

**Test Locally**:
```python
import aiohttp
import asyncio

async def test():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": "Test"}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data) as resp:
            print(await resp.json())

asyncio.run(test())
```

---

## Security Best Practices

### Credential Management

**Never Commit**:
```bash
# .gitignore
.env
.env.*
webhook_orders.csv
*.log
secrets.json
```

**Use Secret Manager** (Production):
```bash
# Create secrets
gcloud secrets create dhan-access-token --data-file=token.txt
gcloud secrets create dhan-api-key --data-file=key.txt

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding dhan-access-token \
  --member="serviceAccount:86335712552-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Token Security

- ✅ Tokens auto-rotate daily
- ✅ Stored in Secret Manager (encrypted)
- ✅ Never logged in full
- ✅ Environment variables only
- ✅ HTTPS only (no plain HTTP)

### Webhook Security

**Secret Verification**:
```python
# app.py checks webhook secret
secret_header = request.headers.get("X-Webhook-Secret")
if secret_header != WEBHOOK_SECRET:
    raise HTTPException(status_code=401, detail="Invalid secret")
```

**Rate Limiting** (NEW):
```python
from utils.production_utils import RateLimiter

limiter = RateLimiter(max_requests=100, window_seconds=60)

if not limiter.allow_request(client_id):
    raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

**HMAC Signature** (NEW):
```python
from utils.production_utils import WebhookSecurity

# Verify signature
if not WebhookSecurity.verify_signature(payload, signature, secret):
    raise HTTPException(status_code=401, detail="Invalid signature")
```

### API Rate Limits

**Dhan API Limits**:
- Orders: 200/second
- Holdings: 5/second
- Market data: 1/second per symbol

**Webhook Service**:
- Max concurrent: 80 requests/second
- Auto-scaling: 0-10 instances
- Timeout: 60 seconds/request

---

## Advanced Features

### New: Production Utilities

**File**: `utils/production_utils.py` (342 lines)

#### Retry with Exponential Backoff

```python
from utils.production_utils import retry_with_backoff, RetryConfig

@retry_with_backoff(RetryConfig(
    max_attempts=3,
    initial_delay=1.0,
    max_delay=60.0
))
def place_order():
    response = dhan_client.place_order(...)
    return response

# Retries: 1s → 2s → 4s on failure
```

#### Circuit Breaker

```python
from utils.production_utils import CircuitBreaker

# Open after 5 failures, timeout 60s
breaker = CircuitBreaker(failure_threshold=5, timeout=60)

@breaker.call
def call_dhan_api():
    return dhan_client.get_positions()

# States: CLOSED → OPEN → HALF_OPEN
```

#### Webhook HMAC Verification

```python
from utils.production_utils import WebhookSecurity

# Generate signature (TradingView side)
signature = WebhookSecurity.generate_signature(payload, secret)

# Verify signature (webhook service)
is_valid = WebhookSecurity.verify_signature(payload, signature, secret)
```

#### Rate Limiting

```python
from utils.production_utils import RateLimiter

limiter = RateLimiter(max_requests=100, window_seconds=60)

if not limiter.allow_request(client_id):
    return {"error": "Rate limit exceeded"}
```

### India VIX Integration

**What**: Volatility index for Indian markets (fear gauge)

**Use**: Adjust position sizes based on market volatility

```python
# Load VIX data
from data.loaders import load_india_vix

vix_df = load_india_vix(interval="1d")
current_vix = vix_df['close'].iloc[-1]

# Adjust position size
if current_vix < 15:
    position_size = 1.0    # Full size (low volatility)
elif current_vix < 20:
    position_size = 0.75   # 75% (normal)
elif current_vix < 30:
    position_size = 0.5    # 50% (elevated)
else:
    position_size = 0.0    # No trades (high volatility)
```

**VIX Levels**:
- **< 15**: Low volatility (complacent)
- **15-20**: Normal volatility
- **20-30**: Elevated volatility (cautious)
- **> 30**: High volatility (fear)

### Sell Order Validation

**Purpose**: Prevent accidental shorting

**How It Works**:
1. Receive sell order
2. Check current holdings via Dhan API
3. Validate quantity ≤ available holdings
4. Accept if sufficient, reject if insufficient

**Enable**:
```bash
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars ENABLE_SELL_VALIDATION=true
```

---

## Deployment Commands

### Initial Deployment

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service

# Deploy to Cloud Run
gcloud run deploy dhan-webhook-service \
  --source . \
  --region=asia-south1 \
  --allow-unauthenticated \
  --memory=1Gi \
  --timeout=300 \
  --set-env-vars="DHAN_CLIENT_ID=1108351648,ENVIRONMENT=production,ENABLE_DHAN=true" \
  --set-secrets="DHAN_ACCESS_TOKEN=dhan-access-token:latest,DHAN_API_KEY=dhan-api-key:latest,..."
```

### Update Environment Variables

```bash
# Single variable
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars KEY=VALUE

# Multiple variables
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars KEY1=value1,KEY2=value2
```

### Setup Cron Job

```bash
cd webhook-service
bash setup-cron-job.sh

# Or manually:
gcloud scheduler jobs create http dhan-token-refresh \
  --schedule="0 8 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token" \
  --http-method=POST \
  --location=asia-south1
```

### View Service Details

```bash
# Describe service
gcloud run services describe dhan-webhook-service --region=asia-south1

# List revisions
gcloud run revisions list --service=dhan-webhook-service --region=asia-south1

# View environment variables
gcloud run services describe dhan-webhook-service \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].env)"
```

---

## Migration Guide

### From Old Documentation

**Consolidated Files**:
- ❌ `NEW_ARCHITECTURE_README.md` → ✅ This guide (Section: Architecture)
- ❌ `INTEGRATION_GUIDE.md` → ✅ This guide (Section: Configuration Management)
- ❌ `DEPLOYMENT_SUMMARY.md` → ✅ This guide (Section: Current Deployment)
- ❌ `DHAN_OAUTH_COMPLETE_GUIDE.md` → ✅ This guide (Section: OAuth Authentication)

**What's New**:
1. **Centralized core/config_manager.py** - No more scattered .env reads
2. **oauth_service.py interface** - Clean OAuth API for webhook & backtesting
3. **Production utilities** - Retry, circuit breaker, security, rate limiting
4. **Telegram bot fixed** - Environment variables now properly set
5. **Cron job fixed** - Endpoint updated to `/refresh-token`

### Updating Existing Code

**Before** (direct .env reads):
```python
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DHAN_ACCESS_TOKEN')
```

**After** (centralized config):
```python
from config_manager import get_config

config = get_config()
token = config.get('DHAN_ACCESS_TOKEN')
```

**Before** (direct dhan_auth import):
```python
from dhan_auth import DhanAuth

auth = DhanAuth(...)
token = await auth.get_token()
```

**After** (clean interface):
```python
from oauth_service import get_dhan_token

token = await get_dhan_token()  # Auto-refreshes!
```

---

## Files Removed (Unnecessary)

### Test & Debug Files

The following files can be **safely deleted**:

```bash
# Test files (development only)
webhook-service/test_oauth_flow.py         # OAuth testing
webhook-service/test_oauth_trigger.py      # OAuth trigger test
webhook-service/test_step1.py              # Step 1 test
webhook-service/test-deployment.sh         # Deployment test
webhook-service/debug_dhan_page.py         # Debug script

# Setup scripts (superseded by deploy.sh)
webhook-service/setup-cron-job.sh          # Cron setup (manual now)

# Consolidated documentation (replaced by this guide)
NEW_ARCHITECTURE_README.md
INTEGRATION_GUIDE.md
DEPLOYMENT_SUMMARY.md
webhook-service/docs/DHAN_OAUTH_COMPLETE_GUIDE.md
```

**To Remove**:
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace

# Remove test files
rm webhook-service/test_oauth_flow.py
rm webhook-service/test_oauth_trigger.py
rm webhook-service/test_step1.py
rm webhook-service/test-deployment.sh
rm webhook-service/debug_dhan_page.py
rm webhook-service/setup-cron-job.sh

# Remove old documentation
rm NEW_ARCHITECTURE_README.md
rm INTEGRATION_GUIDE.md
rm DEPLOYMENT_SUMMARY.md
rm webhook-service/docs/DHAN_OAUTH_COMPLETE_GUIDE.md

# Update git
git rm <files>
git commit -m "docs: consolidate into COMPLETE_DEPLOYMENT_GUIDE.md, remove test files"
```

---

## Quick Reference

### Service URLs

- **Health**: https://dhan-webhook-service-86335712552.asia-south1.run.app/health
- **Ready**: https://dhan-webhook-service-86335712552.asia-south1.run.app/ready
- **Webhook**: https://dhan-webhook-service-86335712552.asia-south1.run.app/webhook
- **Refresh Token**: https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token

### Essential Commands

```bash
# Check token status
curl https://dhan-webhook-service-86335712552.asia-south1.run.app/ready | jq

# Force token refresh
curl -X POST https://dhan-webhook-service-86335712552.asia-south1.run.app/refresh-token

# View logs
gcloud logging tail 'resource.type=cloud_run_revision' --limit=50

# Cron status
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Manual cron trigger
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# Update environment variable
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars KEY=VALUE
```

### Configuration Files

- **Local**: `webhook-service/.env`
- **Root**: `.env`
- **Production**: Google Secret Manager
- **Order History**: `webhook_orders.csv`
- **Symbol Mapping**: `security_id_list.csv` (217,959 instruments)

---

## Support & Resources

### Documentation

- **This Guide**: Complete deployment & operations reference
- **Main README**: `/Users/abhishekshah/Desktop/quantlab-workspace/README.md`
- **Strategy Development**: `docs/QUANTLAB_GUIDE.md`
- **Backtesting**: `docs/BACKTEST_GUIDE.md`

### External Resources

- **Dhan API**: https://dhanhq.co/docs/
- **Cloud Run**: https://cloud.google.com/run/docs
- **TradingView**: https://www.tradingview.com/support/
- **Telegram Bots**: https://core.telegram.org/bots

### Logs & Monitoring

```bash
# Cloud Run Dashboard
https://console.cloud.google.com/run/detail/asia-south1/dhan-webhook-service

# Cloud Scheduler
https://console.cloud.google.com/cloudscheduler?project=tradingview-webhook-prod

# Secret Manager
https://console.cloud.google.com/security/secret-manager?project=tradingview-webhook-prod
```

---

## Completion Checklist

### Initial Setup
- [ ] Dhan credentials obtained
- [ ] OAuth flow tested (manual authorization)
- [ ] Service deployed to Cloud Run
- [ ] Cron job configured (8 AM IST)
- [ ] TradingView webhook configured
- [ ] Telegram notifications setup (optional)

### Verification
- [ ] `/health` returns healthy
- [ ] `/ready` shows valid token
- [ ] Test order placed successfully
- [ ] Order visible in Dhan app
- [ ] Telegram notification received (if configured)
- [ ] Cron job shows ENABLED
- [ ] Token auto-refreshed at 8 AM

### Monitoring
- [ ] Daily health check at 8 AM
- [ ] Weekly log review
- [ ] Monthly token rotation audit
- [ ] Quarterly security review

---

**Version**: 3.0.0  
**Status**: Production Ready ✅  
**Last Updated**: 26-Nov-2025 03:00 IST  
**Maintainer**: Abhishek Shah  
**Repository**: quantlab-bot

*All systems operational. Happy automated trading! 📈*

---

## Appendix A: Telegram Notifications Setup

### Quick Configuration (5 Minutes)

**Status**: ✅ Telegram bot implementation complete, just needs environment variables

#### Step 1: Create Telegram Bot

```bash
# 1. Open Telegram, search for @BotFather
# 2. Send: /newbot
# 3. Follow prompts, save bot token
# Example: 8208173603:AAGG2mx34E9qfaBnTyswlIOIOTT0Zsi4L0k
```

#### Step 2: Get Chat ID

```bash
# 1. Start conversation with your bot
# 2. Send any message
# 3. Visit (replace {BOT_TOKEN}):
https://api.telegram.org/bot{BOT_TOKEN}/getUpdates

# 4. Find "chat":{"id":5055508551}
# 5. Save that chat ID
```

#### Step 3: Configure Cloud Run

```bash
# Add environment variables
gcloud run services update dhan-webhook-service \
  --region=asia-south1 \
  --update-env-vars \
    TELEGRAM_BOT_TOKEN=8208173603:AAGG2mx34E9qfaBnTyswlIOIOTT0Zsi4L0k,\
    TELEGRAM_CHAT_ID=5055508551,\
    ENABLE_TELEGRAM=true
```

#### Step 4: Verify

```bash
# Check logs
gcloud logging read 'textPayload:"Telegram notifications enabled"' --limit=3

# Expected: ✅ Telegram notifications enabled for chat 5055508551
```

### Notification Types

1. **Alert Received**: Sent when TradingView webhook arrives
2. **Order Success**: Order placed successfully with order ID
3. **Order Failure**: Order rejected with error details  
4. **Token Warning**: When OAuth token expires in <1 hour

### Troubleshooting

**Bot token invalid**: Regenerate via @BotFather → /mybots → Regenerate Token

**Chat ID wrong**: Verify by sending message and checking /getUpdates again

**Notifications disabled**: Check environment variables are set in Cloud Run

---

## Appendix B: Repository Architecture

### Repository Health: 89/100 ⭐⭐⭐⭐

**Strengths**:
- ✅ Core backtesting engine well-structured
- ✅ Production-ready webhook service deployed
- ✅ Comprehensive test suite (42/42 tests passing)
- ✅ Modern CI/CD with GitHub Actions
- ✅ Clean separation: backtesting vs webhook service

**Recent Improvements** (26-Nov-2025):
- ✅ Moved `config_manager.py` → `core/config_manager.py`
- ✅ Moved `oauth_service.py` → `webhook-service/oauth_service.py`
- ✅ Removed 9 unnecessary files (test scripts + old docs)
- ✅ Consolidated documentation (4 guides → 1)
- ✅ Fixed Telegram bot (added env vars)
- ✅ Added unit tests for new modules

### File Organization

```
quantlab-workspace/
├── core/                       # Backtesting engine & config
│   ├── config_manager.py       # ✅ MOVED from root
│   ├── engine.py
│   └── ...
├── webhook-service/            # Production trading
│   ├── oauth_service.py        # ✅ MOVED from root
│   ├── app.py
│   ├── dhan_auth.py
│   └── docs/
│       └── COMPLETE_DEPLOYMENT_GUIDE.md  # ✅ This file
├── utils/
│   └── production_utils.py     # Retry, circuit breaker, HMAC
└── tests/
    ├── test_config_manager.py  # ✅ NEW
    ├── test_oauth_service.py   # ✅ NEW
    └── test_production_utils.py # ✅ NEW
```

### Files Removed (Cleanup)

**Webhook Service** (6 test/debug files):
- `test_oauth_flow.py`, `test_oauth_trigger.py`, `test_step1.py`
- `test-deployment.sh`, `debug_dhan_page.py`, `setup-cron-job.sh`

**Root Documentation** (3 old guides):
- `NEW_ARCHITECTURE_README.md`, `INTEGRATION_GUIDE.md`, `DEPLOYMENT_SUMMARY.md`

**Reason**: Development artifacts consolidated into production-ready structure

### Test Coverage

- **Total Tests**: 42 passing
- **New Tests**: 22 (config_manager, oauth_service, production_utils)
- **Coverage**: 35%+ (core functionality)
- **CI/CD**: GitHub Actions running all tests

### Maintenance Schedule

**Daily** (Automated):
- OAuth token refresh (8 AM IST)
- Health check logs

**Weekly** (Manual):
- Review Cloud Run logs
- Check order execution success rate
- Verify Telegram notifications

**Monthly** (Manual):
- Security audit (credentials, API limits)
- Performance review (latency, error rate)
- Test coverage expansion

**Quarterly** (Manual):
- Architecture review
- Dependency updates
- Documentation refresh

---

## Appendix C: Migration Notes

### From Old Documentation

This guide consolidates:
1. `NEW_ARCHITECTURE_README.md` → Architecture section
2. `INTEGRATION_GUIDE.md` → Configuration Management
3. `DEPLOYMENT_SUMMARY.md` → Quick Start
4. `DHAN_OAUTH_COMPLETE_GUIDE.md` → OAuth Authentication
5. `TELEGRAM_FIX.md` → Appendix A
6. `REPOSITORY_AUDIT.md` → Appendix B

### Import Changes

**Before**:
```python
from config_manager import get_config
from oauth_service import get_dhan_token
```

**After**:
```python
from core.config_manager import get_config
from oauth_service import get_dhan_token  # No change (in webhook-service/)
```

### Deployment Changes

No changes needed - all deployments work as before. File moves were internal reorganization only.

---

**Document Version**: 4.0.0  
**Last Major Update**: 26-Nov-2025 03:30 IST  
**Status**: ✅ Complete (All systems documented)  
**Next Review**: December 2025

*This is now the single source of truth for all deployment, configuration, and operational procedures.*
