# TradingView Webhook Integration - Cloud Deployment

> **Google Cloud Run deployment guide for TradingView webhook integration with Dhan trading**

**Last Updated**: 2025-11-23 (v2.2.0)  
**Status**: ✅ Production Ready - AMO Mode Enabled  
**Deployment**: Google Cloud Run with permanent HTTPS URL

---

## Architecture Overview

```
TradingView Alert (anytime) → Google Cloud Run (webhook-service) → Dhan API (AMO Order)
                                                                          ↓
                                                            Next Day 9:45 AM: Order Executes
```

**How it works:**
1. TradingView alert triggered on your strategy signal (anytime - even after market closes)
2. TradingView sends POST request to Cloud Run webhook URL
3. Cloud Run webhook-service receives alert, validates secret
4. Webhook-service translates alert to Dhan AMO order format
5. AMO order placed on Dhan via API (queued for next trading day)
6. Response logged to webhook_orders.csv (accessible via /logs endpoint)
7. Next day 9:45 AM: Order executes automatically

---

## Table of Contents

1. [Cloud Run Deployment](#cloud-run-deployment)
2. [TradingView Alert Setup](#tradingview-alert-setup)
3. [Webhook Payload Structure](#webhook-payload-structure)
4. [Monitoring & Logs](#monitoring--logs)
5. [Troubleshooting](#troubleshooting)

---

## Cloud Run Deployment

### Prerequisites
- Google Cloud account with billing enabled
- `gcloud` CLI installed and authenticated
- Webhook service folder ready (see `webhook-service/QUICKSTART.md`)

### Deploy to Cloud Run

```bash
cd webhook-service

# Deploy (follow prompts)
gcloud run deploy tradingview-webhook --source .

# Choose:
# - Region: asia-south1 (Mumbai, India)
# - Allow unauthenticated invocations: Yes
```

**Your permanent webhook URL:**
```
https://tradingview-webhook-XXXXXXXXXX-uc.a.run.app/webhook
```

Save this URL - you'll use it in TradingView alerts.

### Update Environment Variables

```bash
# Enable live trading (after testing)
gcloud run services update tradingview-webhook \
  --update-env-vars ENABLE_DHAN=true

# Update Dhan credentials (when token expires)
gcloud run services update tradingview-webhook \
  --update-env-vars DHAN_ACCESS_TOKEN=your_new_token

# Change webhook secret
gcloud run services update tradingview-webhook \
  --update-env-vars WEBHOOK_SECRET=your_custom_secret
```

### Test Deployment

```bash
# Get your Cloud Run URL
WEBHOOK_URL=$(gcloud run services describe tradingview-webhook \
  --region=asia-south1 --format="value(status.url)")

# Test health endpoint
curl $WEBHOOK_URL/health

# Test webhook endpoint
curl -X POST $WEBHOOK_URL/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [{
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "1",
      "exchange": "NSE",
      "symbol": "RELIANCE",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "1D",
        "time": "2025-11-21T09:15:00Z",
        "timenow": "2025-11-21T10:30:00Z"
      }
    }]
  }'
```

---

## TradingView Alert Setup

### Step 1: Get Your Cloud Run Webhook URL

```bash
# Get your deployed service URL
gcloud run services describe tradingview-webhook \
  --region=asia-south1 \
  --format="value(status.url)"

# Output: https://tradingview-webhook-XXXXXXXXXX-uc.a.run.app
```

Your webhook URL will be:
```
https://tradingview-webhook-XXXXXXXXXX-uc.a.run.app/webhook
```

### Step 2: Create TradingView Alert

1. Open any TradingView chart
2. Click the alarm clock icon to create an alert
3. Configure your alert conditions
4. In the "Notifications" tab:
   - Enable "Webhook URL"
   - Enter your webhook URL from Step 1
   - Paste the message payload (see below)

### Step 3: Alert Message Format

**Copy this JSON exactly** (replace only the values you need to customize):

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
      "symbol": "{{ticker}}",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "{{interval}}",
        "time": "{{time}}",
        "timenow": "{{timenow}}"
      }
    }
  ]
}
```

### TradingView Placeholder Variables

TradingView will automatically replace these placeholders:

- `{{ticker}}` - Symbol name (e.g., "RELIANCE", "INFY")
- `{{close}}` - Current close price
- `{{interval}}` - Chart timeframe (e.g., "1D", "1H", "15")
- `{{time}}` - Bar timestamp (ISO 8601 format)
- `{{timenow}}` - Current timestamp (ISO 8601 format)
- `{{exchange}}` - Exchange (e.g., "NSE", "BSE")

---

## Webhook Payload Structure

### Complete Example

```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "10",
      "exchange": "NSE",
      "symbol": "RELIANCE",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "1D",
        "time": "2025-11-20T09:15:00Z",
        "timenow": "2025-11-20T15:31:44Z"
      }
    }
  ]
}
```

### Field Descriptions

#### Root Level
- `secret` (string, required): Authentication secret (must match `.env`)
- `alertType` (string, required): Type of alert
  - `"multi_leg_order"` - Multi-leg order execution
  - `"single_order"` - Single order
  - `"cancel_order"` - Cancel existing order
- `order_legs` (array, required): List of order legs to execute (min 1)

#### Order Leg Fields
- `transactionType` (string, required): 
  - `"B"` = Buy
  - `"S"` = Sell
- `orderType` (string, required):
  - `"MKT"` = Market order
  - `"LMT"` = Limit order
  - `"SL"` = Stop Loss
  - `"SL-M"` = Stop Loss Market
- `quantity` (string, required): Number of shares/contracts
- `exchange` (string, required):
  - `"NSE"` = National Stock Exchange
  - `"BSE"` = Bombay Stock Exchange
  - `"NFO"` = NSE Futures & Options
  - `"MCX"` = Multi Commodity Exchange
- `symbol` (string, required): Trading symbol (e.g., "RELIANCE", "INFY")
- `instrument` (string, required):
  - `"EQ"` = Equity
  - `"FUT"` = Futures
  - `"CE"` = Call Option
  - `"PE"` = Put Option
- `productType` (string, required):
  - `"C"` = CNC (Cash and Carry / Delivery)
  - `"I"` = Intraday
  - `"M"` = Margin
- `sort_order` (string, required): Execution priority ("1", "2", "3", ...)
- `price` (string, required): Order price
  - `"0"` for market orders
  - Specific price for limit orders

#### Metadata Fields
- `interval` (string, required): Chart timeframe
- `time` (string, required): Bar timestamp (ISO 8601)
- `timenow` (string, required): Current timestamp (ISO 8601)

---

## Monitoring & Logs

### Cloud Run Logs

View real-time logs:
```bash
# Stream logs
gcloud run services logs tail tradingview-webhook \
  --region=asia-south1

# View last 50 lines
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 \
  --limit=50

# Search for specific symbol
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 | grep "RELIANCE"
```

### View CSV Order Logs (Easy Method)

```bash
# Via HTTP endpoint (recommended)
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/logs?limit=100 | jq

# View in browser
open https://tradingview-webhook-cgy4m5alfq-el.a.run.app/logs

# Filter today's orders
curl -s https://tradingview-webhook-cgy4m5alfq-el.a.run.app/logs?limit=500 | \
  jq --arg date "$(date +%Y-%m-%d)" '.logs[] | select(.timestamp | startswith($date))'

# Find failed orders
curl -s https://tradingview-webhook-cgy4m5alfq-el.a.run.app/logs?limit=100 | \
  jq '.logs[] | select(.status != "success")'
```

**CSV Format:**
- timestamp, alert_type, leg_number
- symbol, exchange, transaction_type, quantity
- order_type, product_type, price
- status, message, order_id, security_id, source_ip

### Monitoring Dashboard

Google Cloud Console provides:
- **Request count** - Total webhook calls
- **Latency** - Response time metrics
- **Error rate** - Failed requests percentage
- **Instance count** - Auto-scaling activity
- **Memory usage** - Resource consumption

Access: https://console.cloud.google.com/run

---

## Troubleshooting

### Orders Not Executing

1. **Check ENABLE_DHAN setting:**
```bash
gcloud run services describe tradingview-webhook \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].env[?name=='ENABLE_DHAN'].value)"

# Should show: true (for live) or false (for testing)
```

2. **Update ENABLE_DHAN:**
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars ENABLE_DHAN=true
```

3. **Check logs for errors:**
```bash
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 \
  --limit=50 | grep ERROR
```

4. **Verify sufficient funds/margin in Dhan account**

### TradingView Alerts Not Received

1. **Verify webhook URL is correct:**
   - Include `/webhook` at the end
   - Use full Cloud Run URL (starts with `https://`)
   - Check for typos

2. **Test webhook endpoint:**
```bash
WEBHOOK_URL=$(gcloud run services describe tradingview-webhook \
  --region=asia-south1 --format="value(status.url)")

curl $WEBHOOK_URL/health
```

3. **Check TradingView alert history:**
   - Go to TradingView > Alerts tab
   - Click on your alert > View history
   - Look for webhook delivery status

### Invalid Secret Errors

1. **Check current secret:**
```bash
gcloud run services describe tradingview-webhook \
  --region=asia-south1 \
  --format="value(spec.template.spec.containers[0].env[?name=='WEBHOOK_SECRET'].value)"
```

2. **Update secret:**
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars WEBHOOK_SECRET=your_new_secret
```

3. **Ensure JSON is valid** (use online JSON validator)

### Dhan Token Expired

Dhan access tokens expire after ~7 days. Update when needed:

```bash
# Generate new token (see DHAN_CREDENTIALS_GUIDE.md)
# Then update Cloud Run
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars DHAN_ACCESS_TOKEN=your_new_token
```

---

## Cost Estimate

Google Cloud Run pricing (as of Nov 2025):

| Resource | Free Tier | Usage | Cost |
|----------|-----------|-------|------|
| Requests | 2M/month | ~5K alerts/month | $0 |
| CPU | 180K vCPU-seconds | ~5 sec/alert | $0 |
| Memory | 360K GiB-seconds | ~128MB × 5 sec | $0 |
| Networking | 1GB/month | ~1KB/alert | $0 |

**Expected monthly cost: $0** (well within free tier)

---

## Quick Reference

### Deploy Service
```bash
cd webhook-service
gcloud run deploy tradingview-webhook --source .
```

### Update Environment Variable
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars KEY=VALUE
```

### View Logs
```bash
gcloud run services logs tail tradingview-webhook \
  --region=asia-south1
```

### Get Webhook URL
```bash
gcloud run services describe tradingview-webhook \
  --region=asia-south1 \
  --format="value(status.url)"
```

### Test Health
```bash
WEBHOOK_URL=$(gcloud run services describe tradingview-webhook \
  --region=asia-south1 --format="value(status.url)")
curl $WEBHOOK_URL/health
```

---

**For detailed setup, see:**
- `webhook-service/QUICKSTART.md` - Full deployment guide
- `webhook-service/DEPLOYMENT_CHECKLIST.md` - Pre-deployment checklist
- `DHAN_CREDENTIALS_GUIDE.md` - How to get/refresh Dhan credentials

