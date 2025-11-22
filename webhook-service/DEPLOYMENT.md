# TradingView Webhook Service - Deployment Guide

## 🚀 Quick Deploy to Google Cloud Run

### Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed ([Install Guide](https://cloud.google.com/sdk/docs/install))
3. **.env file** with your Dhan credentials

### Step 1: Enable Billing

1. Go to [Google Cloud Console - Billing](https://console.cloud.google.com/billing)
2. Create or select a billing account
3. Link it to the project `tradingview-webhook-prod`

### Step 2: Deploy

```bash
# Make sure you're in the webhook-service directory
cd webhook-service

# Run the deployment script
./deploy.sh
```

That's it! The script will:
- ✅ Enable required Google Cloud APIs
- ✅ Build the Docker container with Playwright support
- ✅ Deploy to Cloud Run with your environment variables
- ✅ Configure automatic scaling (up to 10 instances)
- ✅ Allocate 2GB RAM and 1 CPU per instance
- ✅ Set 5-minute timeout for requests

### Step 3: Get Your Webhook URL

After deployment completes, you'll see:
```
Service URL: https://tradingview-webhook-XXXXXXXXX.run.app
Webhook endpoint: https://tradingview-webhook-XXXXXXXXX.run.app/webhook
```

Use this URL in your TradingView alerts!

---

## 🔧 Manual Deployment (Alternative)

If you prefer manual control:

```bash
# 1. Set project
gcloud config set project tradingview-webhook-prod

# 2. Enable APIs
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com

# 3. Build image
gcloud builds submit --tag gcr.io/tradingview-webhook-prod/tradingview-webhook

# 4. Deploy to Cloud Run
gcloud run deploy tradingview-webhook \
    --image gcr.io/tradingview-webhook-prod/tradingview-webhook \
    --platform managed \
    --region asia-south1 \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 300 \
    --set-env-vars WEBHOOK_SECRET=your_secret,DHAN_CLIENT_ID=your_id,...
```

---

## 📊 Monitoring & Logs

### View Real-time Logs
```bash
gcloud logs tail --service=tradingview-webhook --project=tradingview-webhook-prod
```

### View Service Details
```bash
gcloud run services describe tradingview-webhook --region=asia-south1
```

### Test Endpoints

**Health Check:**
```bash
curl https://your-service-url.run.app/health
```

**Ready Check (Dhan Connection):**
```bash
curl https://your-service-url.run.app/ready
```

**Test Webhook (Local):**
```bash
curl -X POST https://your-service-url.run.app/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "your_secret",
    "symbol": "RELIANCE",
    "action": "buy",
    "quantity": 1,
    "product_type": "INTRADAY"
  }'
```

---

## 🔐 Environment Variables

Create a `.env` file with these variables:

```bash
# Webhook Security
WEBHOOK_SECRET=your_secret_here

# Dhan API Configuration
DHAN_CLIENT_ID=your_client_id
DHAN_API_KEY=your_api_key
DHAN_API_SECRET=your_api_secret
DHAN_ACCESS_TOKEN=your_access_token

# Dhan Authentication (for auto token renewal)
DHAN_TOTP_SECRET=your_totp_secret
DHAN_USER_ID=your_mobile_number
DHAN_PASSWORD=your_password
DHAN_PIN=your_pin

# Service Configuration
ENABLE_DHAN=true
PORT=8080
```

---

## 💰 Cost Estimation

**Cloud Run Pricing (Mumbai Region):**
- Free tier: 2 million requests/month
- CPU: $0.00002400/vCPU-second
- Memory: $0.00000250/GiB-second
- Requests: $0.40 per million

**Estimated Monthly Cost:**
- Low usage (100 alerts/day): **FREE** ✅
- Medium usage (1000 alerts/day): ~$2-5/month
- High usage (10,000 alerts/day): ~$10-20/month

**Cloud Build (first 120 builds/day free):**
- Included in deployment script
- Additional builds: $0.003/build-minute

---

## 🔄 Auto Token Renewal

The service automatically:
1. ✅ Checks Dhan token expiry before each order
2. ✅ Refreshes token when <1 hour remains (extends by 24 hours)
3. ✅ Generates new token via browser automation if refresh fails
4. ✅ Saves new token to avoid repeated logins

**Note:** During rate limit (25 consent requests/day), the service will use the existing token until it expires.

---

## 🐛 Troubleshooting

### Deployment fails with "billing not enabled"
```bash
# Link billing account
gcloud billing projects link tradingview-webhook-prod \
    --billing-account=YOUR_BILLING_ACCOUNT_ID
```

### "Too many requests" error from Dhan
- Wait a few hours (daily rate limit: 25 consent requests)
- Existing token will continue working for 24 hours
- Use token refresh endpoint to extend without new consent

### Service doesn't respond
```bash
# Check logs
gcloud logs tail --service=tradingview-webhook

# Check service status
gcloud run services describe tradingview-webhook --region=asia-south1
```

### Update environment variables
```bash
# Redeploy with new env vars
./deploy.sh

# Or update specific variables
gcloud run services update tradingview-webhook \
    --update-env-vars WEBHOOK_SECRET=new_secret
```

---

## 📱 TradingView Alert Setup

**Webhook URL:**
```
https://your-service-url.run.app/webhook
```

**Alert Message (JSON):**
```json
{
  "secret": "{{your_secret}}",
  "symbol": "{{ticker}}",
  "action": "{{strategy.order.action}}",
  "quantity": 1,
  "product_type": "INTRADAY",
  "order_type": "MARKET",
  "validity": "DAY"
}
```

**Supported Actions:**
- `buy` - Open long position
- `sell` - Open short position  
- `exit` - Close all positions for symbol

---

## 🎯 Next Steps

After deployment:

1. **Test the webhook** with a sample alert
2. **Set up TradingView alerts** with your webhook URL
3. **Monitor logs** for the first few trades
4. **Check `/ready` endpoint** to verify Dhan connection
5. **Set up alerting** for errors (optional)

**Production Checklist:**
- [ ] Billing enabled and confirmed
- [ ] `.env` file with all credentials
- [ ] Webhook secret configured in TradingView
- [ ] Test order executed successfully
- [ ] Logs showing successful authentication
- [ ] `/ready` endpoint returns healthy status

---

## 📚 Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Dhan API Documentation](https://dhanhq.co/docs/v2/)
- [TradingView Webhook Alerts](https://www.tradingview.com/support/solutions/43000529348-i-want-to-know-more-about-webhooks/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

**Ready to deploy?** Just run `./deploy.sh` and your webhook service will be live in minutes! 🚀
