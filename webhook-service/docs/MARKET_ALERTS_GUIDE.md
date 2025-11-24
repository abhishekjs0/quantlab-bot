# Market Alerts Guide - TradingView to Dhan

> **Simple guide to automate your trading using TradingView alerts**

**What this does:** Automatically executes orders on Dhan when TradingView alerts trigger  
**Where it runs:** Google Cloud (always online, costs $0/month)  
**Last Updated:** 2025-11-25

---

## 🎯 What You'll Build

```
Your Strategy on TradingView
        ↓
    Alert Triggers
        ↓
    Webhook Sends Signal
        ↓
    Cloud Service Receives
        ↓
    Order Placed on Dhan
```

**Example:** When your moving average crossover happens on TradingView, it automatically buys/sells on Dhan.

---

## 📦 What's Included in webhook-service Folder

### Core Files (3)
- `app.py` - Receives alerts from TradingView
- `dhan_client.py` - Places orders on Dhan
- `security_id_list.csv` - Knows all 217,959 tradable symbols

### Configuration (4)
- `.env` - Your Dhan login details
- `Dockerfile` - Packages everything for cloud
- `requirements.txt` - Software dependencies
- `.gcloudignore` - Files to ignore when uploading

### Documentation (in docs/)
- `MARKET_ALERTS_GUIDE.md` - This file
- `IMPLEMENTATION_PLAN.md` - Complete 671-line roadmap
- `DHAN_CREDENTIALS_GUIDE.md` - How to get API access
- `DHAN_ORDER_TYPES_ANALYSIS.md` - Order types explained
- `SELL_ORDER_VALIDATION.md` - Sell validation
- `TELEGRAM_SETUP.md` - Telegram notifications

### Logs
- `webhook_orders.csv` - History of all orders (with IST timestamps)

**Total:** 17 files, ready to upload

---

## 🚀 Quick Setup (15 Minutes)

### Current Deployment Status
- **URL**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app
- **Region**: asia-south1 (Mumbai)
- **Status**: Deployed ✅
- **OAuth**: Enabled with auto-refresh
- **Cron Job**: Daily token refresh at 8am IST

### Step 1: Get Dhan Credentials (5 min)

1. Login to https://web.dhan.co
2. Go to Settings → API Management
3. Click "Generate API Key" (if not already done)
4. Copy these values:
   - **Client ID** (looks like: `1108351648`)
   - **API Key** (looks like: `fdbe282b`)
   - **API Secret** (long string with dashes)

**Save these!** You'll need them for OAuth setup.

### Step 2: OAuth Setup (One-Time, 5 min)

**The service uses OAuth 2.0 for secure authentication:**

1. Visit https://web.dhan.co → API Management
2. Find your API key: `fdbe282b`
3. Click **"Authorize"**
4. Complete 2FA authentication:
   - Mobile OTP
   - TOTP (Google Authenticator)
   - PIN
5. Dhan redirects to: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback?tokenId=xxx`
6. Service automatically generates access token (valid ~30 hours)
7. Token refreshes automatically daily at 8am IST via cron job

**OAuth Flow:**
```
Generate Consent → Browser Login (2FA) → Token Generation → Auto-Refresh
```

### Step 3: Test Service (2 min)

```bash
# Test health
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
# Expected: {"status":"healthy","timestamp":"2025-11-25T15:30:00+05:30"}

# Test token status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready
# Expected: {"ready":true,"checks":{"dhan_client":"initialized","access_token":"valid"}}
```

✅ If you see these responses, your service is running!

### Step 4: Deploy to Cloud (If Starting Fresh)

```bash
# Go to webhook-service folder
cd /path/to/webhook-service

# Deploy (one command!)
bash deploy.sh
```

**Choose:**
- Region: `asia-south1` (Mumbai - closest to Indian markets)
- Allow unauthenticated: `Yes`

**You'll get a URL like:**
```
https://tradingview-webhook-xyz123-el.a.run.app
```

**Save this URL!** This is your webhook address.

---

## 🔐 Automatic Token Renewal

**Problem:** Dhan access tokens expire every ~30 hours. Manually authorizing daily is tedious.

**Solution:** Cloud Scheduler cron job automatically calls `/ready` endpoint daily at 8am IST, which checks token validity and triggers OAuth re-authorization if needed.

### How It Works

```
8am IST Daily (Cron Job)
    ↓
Call /ready endpoint
    ↓
Check Token Expiry
    ↓
< 6 hours remaining?
    ↓ Yes
Trigger OAuth Re-auth
    ↓
Continue Trading
```

**Before Each Order:**
1. Check if current token is valid (>6 hours remaining)
2. If expiring soon, OAuth flow triggers (you authorize once)
3. Place order with fresh token
4. Minimal manual intervention!

### Check Token Status

```bash
# Check readiness (includes token status)
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# Response shows token validity:
{
  "ready": true,
  "checks": {
    "dhan_client": "initialized",
    "access_token": "valid"
  },
  "token_expires_in_hours": 18.5
}
```

### Cron Job Management

```bash
# Check cron job status
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Manual trigger (for testing)
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# Pause/Resume
gcloud scheduler jobs pause dhan-token-refresh --location=asia-south1
gcloud scheduler jobs resume dhan-token-refresh --location=asia-south1
```

### Logs Show Auto-Refresh

```bash
# View logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# You'll see:
# 2025-11-25 08:00:00 - Token valid (20.5 hours remaining)
# 2025-11-26 08:00:00 - Token expiring soon, triggering OAuth...
# 2025-11-26 08:00:05 - OAuth authorization required, check browser
```

**Benefits:**
- ✅ Set once, works with daily check
- ✅ Tokens checked automatically before expiry
- ✅ OAuth-based secure authentication
- ✅ Cron job ensures daily health check

---

## 📱 Configure TradingView (10 Minutes)

### Step 1: Create an Alert

1. Open any chart on TradingView
2. Click the **🔔 Alert** button (top toolbar)
3. Set your conditions (e.g., "Price crosses 100")

### Step 2: Add Webhook

In the alert dialog:

1. Scroll to **"Notifications"** section
2. Check ☑️ **"Webhook URL"**
3. Paste your Cloud Run URL + `/webhook`:
   ```
   https://tradingview-webhook-cgy4m5alfq-el.a.run.app/webhook
   ```

### Step 3: Set Alert Message

Copy and paste this into the "Message" box:

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
    "price": "0",
    "meta": {
      "interval": "{{interval}}",
      "time": "{{time}}",
      "timenow": "{{timenow}}"
    }
  }]
}
```

**What this means:**
- `"transactionType": "B"` = Buy (change to `"S"` for Sell)
- `"orderType": "MKT"` = Market order (executes immediately)
- `"quantity": "1"` = Buy 1 share (change as needed)
- `"exchange": "NSE"` = National Stock Exchange
- `"symbol": "{{ticker}}"` = TradingView fills this automatically
- `"productType": "C"` = Cash (delivery), use `"I"` for intraday

### Step 4: Save and Test

1. Click **"Create"**
2. Click **"Test"** to trigger manually
3. Check if order appears in Dhan

---

## 🧪 Testing Before Live Trading

### Test Mode (Safe - No Real Orders)

Your service can start in **test mode** (`ENABLE_DHAN=false`).

**What happens:**
- ✅ Receives alerts from TradingView
- ✅ Validates everything
- ✅ Logs to `webhook_orders.csv`
- ❌ **Does NOT place real orders**

### View Test Results

```bash
# Check logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# View order history CSV (if downloaded)
cat webhook_orders.csv
```

### Enable Live Trading

**After testing successfully:**

```bash
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars ENABLE_DHAN=true
```

⚠️ **Important:** Start with small quantities (1 share) when going live!

### Check Order History

All orders logged to `webhook_orders.csv` with IST timestamps:

```csv
timestamp,symbol,transaction,quantity,status,order_id
2025-11-25 15:30:47 IST,INFY,B,10,success,123456789
```

### Monitor on Google Cloud

Visit: https://console.cloud.google.com/run

You'll see:
- 📊 Request count (how many alerts received)
- ⏱️ Response time (how fast)
- ❌ Error rate (if any failed)
- 💰 Cost (should be $0)

---

## 💰 Cost Breakdown

### Google Cloud Run (Free Tier)

**What you get free:**
- 2 million requests per month
- 360,000 GB-seconds of memory
- 180,000 vCPU-seconds

**Your typical usage:**
- 10-50 alerts per day = ~1,500/month
- **Cost: $0/month** ✅

**If you trade heavily:**
- 500 alerts per day = ~15,000/month
- Still **$0/month** (within free tier)

### Dhan Brokerage

Separate charges apply per order:
- Equity delivery: ₹0 (free)
- Equity intraday: ₹20 per order
- F&O: ₹20 per order

See: https://dhanhq.co/pricing

---

## ⚙️ Order Types Explained

### Market Order (MKT) - Most Common
**What it does:** Buys/sells immediately at current market price

```json
"orderType": "MKT",
"price": "0"
```

**Use when:** You want immediate execution and don't care about exact price

### Limit Order (LMT)
**What it does:** Buys/sells only at your specified price or better

```json
"orderType": "LMT",
"price": "2500.50"
```

**Use when:** You want a specific entry/exit price

### Stop Loss Market (SL-M)
**What it does:** Triggers a market order when price hits your stop level

```json
"orderType": "SL-M",
"price": "0",
"triggerPrice": "2450.00"
```

**Use when:** You want to limit losses with guaranteed execution

---

## 📊 India VIX Integration

**India VIX** (Volatility Index) measures expected market volatility over the next 30 days. It's the "fear gauge" of Indian markets.

### VIX Data Details
- **SECURITY_ID:** 21
- **Exchange:** NSE
- **Symbol:** INDIA VIX

### Using VIX for Trade Filtering

**VIX Regime Guidelines:**
- **< 15:** Low Volatility (Complacent) - Safe for trend-following
- **15-20:** Normal Volatility - Normal trading
- **20-30:** Elevated Volatility (Cautious) - Reduce position sizes
- **> 30:** High Volatility (Fear) - Avoid new positions or use tight stops

### Fetch VIX Data (for backtesting)

```bash
# Fetch daily India VIX data (last 5 years)
python3 scripts/fetch_india_vix.py

# Fetch 1-minute intraday data
python3 scripts/fetch_india_vix.py --interval 1
```

### Load VIX in Strategies

```python
from data.loaders import load_india_vix

# Load daily VIX data
vix_df = load_india_vix(interval="1d")

# Get current VIX level
current_vix = vix_df['close'].iloc[-1]

# Adjust position sizing based on VIX
if current_vix < 15:
    position_size = 1.0  # Full size
elif current_vix < 20:
    position_size = 0.75  # 75% size
elif current_vix < 30:
    position_size = 0.5   # 50% size
else:
    position_size = 0.0   # No trades
```

**VIX Notes:**
- VIX typically moves inversely to stock markets
- Higher VIX = More risk, consider smaller positions
- Lower VIX = Less risk, but watch for complacency
- VIX above 30 often indicates significant market stress

---

## 📍 API Endpoints

### 1. Health: `/health`
Basic health check
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
```

### 2. Ready: `/ready`
Checks token validity, triggers refresh if needed
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready
```

### 3. Market Status: `/market-status`
Check if markets are open
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/market-status
```

### 4. OAuth Callback: `/auth/callback?tokenId=xxx`
Receives tokenId from Dhan OAuth redirect (automatic)

### 5. Webhook: `/webhook` (POST)
Receives TradingView alerts and places orders
```bash
curl -X POST https://tradingview-webhook-cgy4m5alfq-el.a.run.app/webhook   -H "Content-Type: application/json"   -H "X-Webhook-Secret: GTcl4"   -d '{"action":"BUY","symbol":"RELIANCE","quantity":10,"product":"INTRADAY","order_type":"MARKET"}'
```

### 6. Root: `/`
Service info and documentation

---

## 📊 Monitoring

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

## 🐛 Troubleshooting

### Issue 1: Token Expired
**Symptoms**: 401 errors, orders not executing

**Solution**:
```bash
# Trigger OAuth again
# Visit https://web.dhan.co → API Management → Authorize

# Check token status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready
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

### Issue 5: "Order not placed - TEST MODE"

**Cause:** Service is in test mode  
**Fix:** Enable live trading:
```bash
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars ENABLE_DHAN=true
```

### Issue 6: "Invalid webhook secret"

**Cause:** Secret in TradingView doesn't match environment variable  
**Fix:** Check both match exactly (case-sensitive)

### Issue 7: "Symbol not found"

**Cause:** Symbol spelling or exchange wrong  
**Fix:** Use exact Dhan format (e.g., "RELIANCE" not "RELIANCE-EQ")

### Issue 8: "Market closed"

**Cause:** Order placed outside trading hours  
**Fix:** Indian markets: 9:15 AM - 3:30 PM IST (Mon-Fri)

---

## 🔐 Security Best Practices

### 1. Change Default Webhook Secret

Your environment has `WEBHOOK_SECRET=GTcl4` by default.

**Change it:**
```bash
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars WEBHOOK_SECRET=your_random_secret_here
```

Then update TradingView alerts with new secret.

### 2. Token Security

- Never commit tokens to git
- OAuth tokens rotate automatically (~30 hour lifetime)
- Use environment variables only
- Monitor token expiry (cron job checks daily)

### 3. Test Before Live

Always test with `ENABLE_DHAN=false` first!

---

## 📚 File Structure Explained

```
webhook-service/
├── app.py                    # Receives TradingView alerts
├── dhan_client.py            # Places orders on Dhan
├── security_id_list.csv      # All tradable symbols
├── webhook_orders.csv        # Order history
├── .env                      # Your credentials (local)
├── Dockerfile                # Cloud packaging
├── requirements.txt          # Software needed
├── deploy.sh                 # Deployment script
├── setup-cron-job.sh         # Cron job setup
├── test-deployment.sh        # Test script
└── docs/
    ├── IMPLEMENTATION_PLAN.md         # Complete 671-line roadmap
    ├── MARKET_ALERTS_GUIDE.md         # This file
    ├── DHAN_CREDENTIALS_GUIDE.md      # API access
    ├── DHAN_ORDER_TYPES_ANALYSIS.md   # Order types
    ├── SELL_ORDER_VALIDATION.md       # Sell validation
    └── TELEGRAM_SETUP.md              # Telegram notifications
```

**Everything needed to run is included!**

---

## 🔄 Updating Your Deployment

### Update Environment Variables

```bash
# Single variable
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars KEY=VALUE

# Multiple variables
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars KEY1=value1,KEY2=value2
```

### Update Code

```bash
cd webhook-service
gcloud run deploy tradingview-webhook --source .
```

Google Cloud will:
1. Rebuild with your changes
2. Deploy new version
3. Keep same URL (no TradingView update needed)

---

## ✅ Quick Checklist

### Initial Setup
- [ ] Install Google Cloud SDK
- [ ] Get Dhan API credentials (Key, Secret)
- [ ] Setup OAuth (one-time browser authorization)
- [ ] Deploy to Cloud Run
- [ ] Copy webhook URL
- [ ] Setup cron job for token refresh

### TradingView Configuration  
- [ ] Create alert
- [ ] Add webhook URL
- [ ] Paste JSON message
- [ ] Test alert manually
- [ ] Check Cloud Run logs

### Before Going Live
- [ ] Test with `ENABLE_DHAN=false`
- [ ] Verify orders logged correctly
- [ ] Check logs for errors
- [ ] Enable live trading
- [ ] Monitor first few orders

---

## 💡 Pro Tips

### 1. Start Small
Begin with quantity `"1"` to test. Increase after confirming it works.

### 2. Use Intraday for Testing
Set `"productType": "I"` (intraday) instead of `"C"` (delivery) for lower margin requirements.

### 3. Set Up Multiple Strategies
Each TradingView alert can have different:
- Symbols
- Quantities
- Order types
- Product types

All use the same webhook URL!

### 4. Monitor Regularly
Check logs at least daily:
```bash
gcloud run services logs read tradingview-webhook   --region=asia-south1 --limit=50
```

### 5. Token Auto-Refresh
The cron job checks token status daily at 8am IST. OAuth re-authorization required if token expired.

### 6. Use VIX for Risk Management
Integrate India VIX into your strategy to adjust position sizes based on market volatility.

---

## 🎯 Quick Commands

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

### Update Environment Variables
```bash
# Single variable
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars KEY=VALUE

# Multiple variables
gcloud run services update tradingview-webhook   --region=asia-south1   --update-env-vars KEY1=value1,KEY2=value2
```

---

## 🎉 You're Ready!

**Recap:**
1. ✅ Deploy webhook service to Google Cloud ($0/month)
2. ✅ Get permanent HTTPS webhook URL
3. ✅ Configure TradingView alerts
4. ✅ Setup automatic token refresh (cron job + OAuth)
5. ✅ Use India VIX for risk management
6. ✅ Orders automatically execute on Dhan

**Test first, then go live!**

Happy automated trading! 📈

---

## �� Additional Resources

### Documentation
- **IMPLEMENTATION_PLAN.md**: Complete 671-line roadmap with OAuth flow
- **DHAN_CREDENTIALS_GUIDE.md**: API credential setup
- **DHAN_ORDER_TYPES_ANALYSIS.md**: All order types explained
- **SELL_ORDER_VALIDATION.md**: Sell order validation logic
- **TELEGRAM_SETUP.md**: Telegram notifications setup

### External Resources
- **Dhan API**: https://dhanhq.co/docs/
- **Cloud Run**: https://cloud.google.com/run/docs
- **TradingView**: https://www.tradingview.com/support/
- **NSE India VIX**: https://www.nseindia.com/products-services/indices-india-vix

---

**Version**: 2.3.0  
**Status**: Deployed ✅  
**OAuth**: Enabled with auto-refresh  
**Last Updated**: November 25, 2025
