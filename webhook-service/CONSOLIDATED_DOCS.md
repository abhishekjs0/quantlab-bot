# Webhook Service Documentation Consolidation

This file consolidates the scattered webhook service documentation into one reference.

---

## Cloud Run Deployment & Troubleshooting

### Service Information
- **URL**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app
- **Region**: asia-south1
- **Platform**: Cloud Run (Google Cloud)
- **Runtime**: Python 3.11, FastAPI, Uvicorn

### Common Issues & Solutions

#### Issue 1: Playwright Sync API Error ✅ RESOLVED
**Problem**: Service crashes with "It looks like you are using Playwright Sync API inside the asyncio loop"
**Solution**: Converted entire codebase to `async_playwright` throughout `dhan_auth.py`

#### Issue 2: Missing Python Modules ✅ RESOLVED
**Problem**: ModuleNotFoundError for telegram_notifier, signal_queue
**Solution**: Added `COPY` statements to Dockerfile for all required modules

#### Issue 3: OAuth Redirect Issue ✅ RESOLVED
**Problem**: Browser automation completes but tokenId not captured
**Root Cause**: Localhost redirect_uri won't work for Cloud Run deployment
**Solution**: 
1. Regenerate API key with proper redirect URI: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback`
2. Added `/auth/callback` endpoint to capture tokenId
3. Updated `dhan_auth.py` to support redirect_uri parameter

---

## Dhan Authentication

### 3-Step OAuth Flow

1. **Generate Consent** (API call)
   - POST `/app/generate-consent` with API key + secret
   - Returns `consentAppId`

2. **Browser Login** (Required for Individual Traders)
   - Navigate to login page with consentAppId
   - Enter mobile → TOTP → PIN
   - Redirect to callback URL with tokenId

3. **Consume Consent** (API call)
   - GET `/app/consumeApp-consent` with tokenId
   - Returns access_token (valid ~20 hours)

### Token Management

**Token Validity**: ~20 hours (not 23 days!)
**Auto-Refresh**: Every 6 hours (21600s) via background task
**Manual Refresh**: Available at `/auth/callback` endpoint

### New API Credentials (Nov 24, 2025)
```
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
```

---

## Daily Token Refresh Automation

### Cloud Scheduler Setup

**Schedule**: Every day at 8:00 AM IST (before market opens)
**Action**: GET request to `/ready` endpoint triggers token validity check

#### Quick Setup
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
bash setup-cron-job.sh
```

#### Manual Setup
```bash
gcloud scheduler jobs create http dhan-token-refresh \
  --schedule="0 8 * * *" \
  --time-zone="Asia/Kolkata" \
  --uri="https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready" \
  --http-method=GET \
  --location=asia-south1 \
  --description="Daily Dhan access token refresh at 8:00 AM IST"
```

#### Monitor Job
```bash
# List jobs
gcloud scheduler jobs list --location=asia-south1

# View job details
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Test manually
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# View logs
gcloud logging read "resource.type=cloud_scheduler_job AND resource.labels.job_id=dhan-token-refresh" --limit=20
```

---

## Deployment

### Quick Deploy with New Credentials
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
bash deploy-with-new-credentials.sh
```

### Manual Deployment
```bash
# From webhook-service directory
gcloud run deploy tradingview-webhook \
  --source . \
  --region=asia-south1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=1 \
  --timeout=300 \
  --set-env-vars="..."  # See deploy-with-new-credentials.sh for full list
```

### Verify Deployment
```bash
# Check health
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health

# Check readiness
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# View status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/

# Check logs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="tradingview-webhook"' --limit=50
```

---

## API Endpoints

### Public Endpoints

#### `GET /` - Service Status
Returns service configuration, market status, and available endpoints

#### `GET /health` - Health Check
Simple liveness probe, always returns 200 if service is running

#### `GET /ready` - Readiness Check
Comprehensive readiness probe:
- Checks Dhan client initialization
- Validates access token (auto-refreshes if expired)
- Returns 200 if ready, 503 if not ready

#### `GET /market-status` - Market Information
Returns:
- Current market status (OPEN/CLOSED/HOLIDAY)
- Trading sessions (pre-market, normal, post-market, AMO window)
- AMO order acceptance status
- Upcoming holidays
- Market hours

#### `GET /auth/callback?tokenId=xxx` - OAuth Callback
Receives tokenId from Dhan OAuth redirect:
- Stores tokenId in dhan_auth
- Generates access token
- Updates global dhan_client
- Returns success/error status

### Protected Endpoints

#### `POST /webhook` - TradingView Webhook
**Authentication**: Requires `secret` field in payload matching `WEBHOOK_SECRET`

**Payload Structure**:
```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "1",
      "exchange": "NSE",
      "symbol": "RELIANCE-EQ",
      "instrument": "EQ",
      "productType": "I",
      "sort_order": "1",
      "price": "0",
      "amoTime": "PRE_OPEN",
      "meta": {
        "interval": "1D",
        "time": "2025-11-24T09:15:00Z",
        "timenow": "2025-11-24T09:15:30Z"
      }
    }
  ]
}
```

**Processing**:
1. Validates webhook secret
2. Checks market status and AMO timing
3. Queues orders if outside trading hours
4. Executes orders immediately if during market hours
5. Sends Telegram notifications
6. Logs all orders to CSV

---

## Environment Variables

### Required Variables
```bash
# Dhan API Credentials
DHAN_CLIENT_ID=1108351648
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback

# Dhan Authentication
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=9624973000
DHAN_PASSWORD=v*L4vb&n
DHAN_PIN=224499

# Current Access Token (auto-updated)
DHAN_ACCESS_TOKEN=eyJ0eXAi...

# Webhook Configuration
WEBHOOK_SECRET=GTcl4
ENABLE_DHAN=true

# Service Configuration
AUTO_HEALTH_CHECK=true
HEALTH_CHECK_INTERVAL=21600  # 6 hours
PORT=8080
HOST=0.0.0.0

# Telegram Notifications
ENABLE_TELEGRAM=true
TELEGRAM_BOT_TOKEN=8208173603:AAGG2mx34E9qfaBnTyswlIOIOTT0Zsi4L0k
TELEGRAM_CHAT_ID=5055508551
```

---

## Trading Calendar Integration

### Market Sessions
- **Pre-Open**: 09:00 - 09:08
- **Normal Trading**: 09:15 - 15:30
- **Post-Market**: 15:40 - 16:00
- **AMO Window**: 17:00 - 08:59 (next day)

### AMO Order Timing
- `PRE_OPEN`: Execute at market open (09:15)
- `OPEN`: Execute immediately at open
- `OPEN_30`: Execute 30 minutes after open
- `OPEN_60`: Execute 1 hour after open

### Signal Queue
Orders received outside trading hours are queued and executed:
- Weekend orders → Execute on Monday at market open
- Holiday orders → Execute on next trading day
- After-hours orders → Execute as AMO on next trading day

---

## Monitoring & Logging

### View Recent Logs
```bash
# Last 50 logs
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="tradingview-webhook"' --limit=50

# Filter by severity
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' --limit=20

# Filter by text
gcloud logging read 'textPayload:"token"' --limit=20

# Specific time range
gcloud logging read 'timestamp>="2025-11-24T00:00:00Z"' --limit=100
```

### Key Log Patterns

**Token Generation**:
- `🔄 Starting automatic token generation...`
- `✅ Token generation complete! Expires at ...`
- `❌ Failed at step X`

**Order Execution**:
- `📊 Processing X order legs`
- `✅ Order placed successfully`
- `❌ Order rejected`

**OAuth Callback**:
- `✅ OAuth callback received tokenId`
- `✅ Successfully generated access token from OAuth callback`

---

## Quick Reference Commands

### Deploy Service
```bash
cd webhook-service
bash deploy-with-new-credentials.sh
```

### Setup Cron Job
```bash
cd webhook-service
bash setup-cron-job.sh
```

### Test Endpoints
```bash
# Health check
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health

# Readiness check
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# Market status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/market-status
```

### Monitor Logs
```bash
# Real-time logs
gcloud logging tail 'resource.labels.service_name="tradingview-webhook"'

# Recent errors
gcloud logging read 'severity>=ERROR' --limit=20 --format=json
```

### Manage Service
```bash
# View service details
gcloud run services describe tradingview-webhook --region=asia-south1

# View revisions
gcloud run revisions list --service=tradingview-webhook --region=asia-south1

# Scale service
gcloud run services update tradingview-webhook \
  --min-instances=1 \
  --max-instances=10 \
  --region=asia-south1
```

---

## Troubleshooting

### Token Not Refreshing
1. Check cron job status: `gcloud scheduler jobs list --location=asia-south1`
2. Test manual trigger: `gcloud scheduler jobs run dhan-token-refresh --location=asia-south1`
3. Check service logs for token generation errors
4. Verify OAuth callback endpoint is accessible

### Orders Not Executing
1. Check market status: `curl .../market-status`
2. Verify webhook secret matches
3. Check signal queue: Orders may be queued for next trading day
4. Review logs for rejection reasons
5. Verify Dhan credentials are valid

### OAuth Callback Not Working
1. Verify redirect_uri in Dhan API settings matches: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback`
2. Check if callback endpoint is accessible
3. Review logs for tokenId capture
4. Test manual OAuth flow from Dhan website

### Service Not Starting
1. Check deployment logs: `gcloud logging read 'resource.type="cloud_run_revision"' --limit=50`
2. Verify all environment variables are set
3. Check for missing Python dependencies
4. Review Dockerfile for missing COPY statements

---

## Files Reference

### Key Files
- `app.py` - Main FastAPI application (1142 lines)
- `dhan_auth.py` - Authentication module with OAuth (872 lines)
- `dhan_client.py` - Dhan API client wrapper
- `telegram_notifier.py` - Telegram notification service
- `signal_queue.py` - Order queuing for off-hours
- `trading_calendar.py` - Market calendar and session tracking
- `Dockerfile` - Container build configuration
- `.env` - Environment variables (credentials)

### Deployment Scripts
- `deploy-with-new-credentials.sh` - Deploy with updated credentials
- `setup-cron-job.sh` - Setup Cloud Scheduler job
- `cron-job.yaml` - Cron job configuration reference

### Documentation
- `docs/DHAN_CREDENTIALS_GUIDE.md` - Complete authentication guide
- `webhook-service/CONSOLIDATED_DOCS.md` - This file

---

## Next Steps After Deployment

1. ✅ Deploy service with new credentials
2. ✅ Setup Cloud Scheduler cron job
3. ⏳ Test OAuth callback by triggering manual login
4. ⏳ Monitor first automated token refresh at 8:00 AM IST
5. ⏳ Test webhook with TradingView alert
6. ⏳ Verify Telegram notifications working
7. ⏳ Monitor order execution during market hours

---

## Support & Resources

- **Dhan API Docs**: https://api.dhan.co/
- **Cloud Run Docs**: https://cloud.google.com/run/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **Playwright Docs**: https://playwright.dev/python/

---

**Last Updated**: November 24, 2025
**Service Version**: 2.2.0
**Status**: ✅ Deployed and operational
