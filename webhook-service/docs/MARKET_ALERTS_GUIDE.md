# TradingView Market Alerts - Complete Guide

**Version**: 2.3.0  
**Last Updated**: November 25, 2025  
**Service URL**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app

For complete implementation details, see **[IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md)** in webhook-service root.

---

## 📚 Quick Navigation

- **[Quick Start](#quick-start)** - Get started in 5 minutes
- **[OAuth Setup](#oauth-setup)** - 3-step authentication process
- **[Deployment](#deployment)** - Deploy to Cloud Run
- **[API Endpoints](#api-endpoints)** - All 6 endpoints documented
- **[Token Management](#token-management)** - Auto-refresh & cron setup
- **[Monitoring](#monitoring)** - Daily checklist & log analysis
- **[Troubleshooting](#troubleshooting)** - Common issues & solutions
- **[Quick Commands](#quick-commands)** - Copy-paste command reference

---

## Quick Start

### Service Information
- **URL**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app
- **Region**: asia-south1 (Mumbai)
- **Platform**: Google Cloud Run
- **Status**: Deployed ✅

### Test Service
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
# Expected: {"status":"healthy"}
```

---

## OAuth Setup

### 3-Step Process

**Step 1: Generate Consent** (Automatic)
- Service calls Dhan API with API_KEY + API_SECRET

**Step 2: Browser Login** (Manual - One Time)
1. Visit https://web.dhan.co → API Management
2. Find API key: `fdbe282b`
3. Click "Authorize"
4. Complete 2FA: Mobile → TOTP → PIN
5. Dhan redirects to callback URL with tokenId

**Step 3: Token Generation** (Automatic)
- Service receives tokenId → generates access_token
- Token valid for ~30 hours
- Auto-refreshes daily at 8am IST

### Required Credentials
```bash
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
```

---

## Deployment

### Method 1: Environment Variable Update (Fastest)
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars="DHAN_API_KEY=xxx,DHAN_API_SECRET=xxx" \
  --no-traffic

gcloud run services update-traffic tradingview-webhook \
  --region=asia-south1 \
  --to-latest
```

### Method 2: Full Rebuild
```bash
cd webhook-service
gcloud builds submit --tag gcr.io/tradingview-webhook-prod/tradingview-webhook:latest
bash deploy.sh
```

### Verification
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
gcloud run services describe tradingview-webhook --region=asia-south1
```

---

## API Endpoints

### 1. Health: `/health`
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
```

### 2. Ready: `/ready`
Checks token validity, triggers refresh if needed
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready
```

### 3. Market Status: `/market-status`
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/market-status
```

### 4. OAuth Callback: `/auth/callback?tokenId=xxx`
Receives tokenId from Dhan OAuth redirect

### 5. Webhook: `/webhook` (POST)
```bash
curl -X POST https://tradingview-webhook-cgy4m5alfq-el.a.run.app/webhook \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: GTcl4" \
  -d '{"action":"BUY","symbol":"RELIANCE","quantity":10,"product":"INTRADAY","order_type":"MARKET"}'
```

### 6. Root: `/`
Service info and all endpoint documentation

---

## Token Management

### Automatic Refresh

**Cloud Scheduler Cron Job**:
- **Schedule**: Daily at 8:00 AM IST
- **Target**: `/ready` endpoint
- **Status**: ENABLED ✅

```bash
# Check cron job
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Manual trigger
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1
```

### Manual Refresh
```bash
# Option 1: Visit Dhan website
# https://web.dhan.co → API Management → Authorize

# Option 2: Call ready endpoint
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready
```

---

## Monitoring

### Daily Checklist

**Morning (8am IST)**:
```bash
# Check cron job ran
gcloud scheduler jobs list --location=asia-south1

# Verify token refreshed
gcloud logging read 'textPayload:"Token valid"' --limit=3
```

**During Trading (9:15am-3:30pm)**:
```bash
# Monitor webhooks
gcloud logging read 'textPayload:"Alert received"' --limit=10

# Check orders
gcloud logging read 'textPayload:"Order placed"' --limit=10
```

**Evening**:
```bash
# Check token expiry
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready | jq '.token_expires_in_hours'
```

### View Logs
```bash
# Recent logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# Search specific
gcloud logging read 'textPayload:"Token"' --limit=20

# Errors only
gcloud logging read 'severity>=ERROR' --limit=50

# Real-time tail
gcloud logging tail 'resource.type=cloud_run_revision' --limit=50
```

---

## Troubleshooting

### Issue 1: Token Expired
**Symptoms**: 401 errors, orders not executing

**Solution**:
```bash
# Trigger OAuth again
# Visit https://web.dhan.co → API Management → Authorize

# Or update manually
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --set-env-vars="DHAN_ACCESS_TOKEN=<new_token>"
```

### Issue 2: Cron Job Not Running
```bash
# Check if paused
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Resume if paused
gcloud scheduler jobs resume dhan-token-refresh --location=asia-south1
```

### Issue 3: Service Down
```bash
# Check status
gcloud run services describe tradingview-webhook --region=asia-south1

# Check error logs
gcloud logging read 'severity>=ERROR' --limit=50

# Redeploy if needed
cd webhook-service && bash deploy.sh
```

### Issue 4: OAuth Callback Not Working
**Check**: Redirect URI must match exactly
- Dhan API settings: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback`
- Environment variable: Same URL

```bash
# Test callback
curl "https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback?tokenId=test"
# Should return error for invalid tokenId
```

---

## Quick Commands

### Deploy
```bash
cd webhook-service
bash deploy.sh
bash setup-cron-job.sh
bash test-deployment.sh
```

### Monitor
```bash
# Health
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health

# Token status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# Logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50
```

### Cron Job
```bash
# Status
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Run now
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# Pause/Resume
gcloud scheduler jobs pause dhan-token-refresh --location=asia-south1
gcloud scheduler jobs resume dhan-token-refresh --location=asia-south1
```

---

## Additional Resources

### Documentation
- **IMPLEMENTATION_PLAN.md**: Complete 671-line roadmap
- **DHAN_CREDENTIALS_GUIDE.md**: API credential setup
- **DHAN_ORDER_TYPES_ANALYSIS.md**: Order types
- **SELL_ORDER_VALIDATION.md**: Sell validation
- **TELEGRAM_SETUP.md**: Telegram notifications

### External
- **Dhan API**: https://dhanhq.co/docs/
- **Cloud Run**: https://cloud.google.com/run/docs
- **TradingView**: https://www.tradingview.com/support/

---

**Version**: 2.3.0  
**Status**: Deployed ✅  
**Last Updated**: November 25, 2025
