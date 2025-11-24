# Market Alerts Guide - TradingView to Dhan

> **Simple guide to automate your trading using TradingView alerts**

**What this does:** Automatically executes orders on Dhan when TradingView alerts trigger  
**Where it runs:** Google Cloud (always online, costs $0/month)  
**Last Updated:** 2025-11-21

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

### Documentation (3 in docs/)
- `DHAN_LIVE_TRADING_GUIDE.md` - Order types explained
- `DHAN_CREDENTIALS_GUIDE.md` - How to get API access
- `TRADINGVIEW_POST.md` - Detailed TradingView setup

### Logs
- `webhook_orders.csv` - History of all orders (with IST timestamps)

**Total:** 17 files, ready to upload

---

## 🚀 Quick Setup (15 Minutes)

### Step 1: Get Dhan Credentials (5 min)

1. Login to https://web.dhan.co
2. Go to Settings → API Management
3. Click "Generate Token"
4. Copy these two values:
   - **Client ID** (looks like: `1108351648`)
   - **Access Token** (long text starting with `eyJ...`)

**Save these!** You'll need them in Step 3.

### Step 2: Install Google Cloud Tools (5 min)

```bash
# Install once
brew install google-cloud-sdk

# Login to Google
gcloud auth login
```

Follow the browser prompts to login.

### Step 3: Deploy to Cloud (2 min)

```bash
# Go to webhook-service folder
cd /path/to/webhook-service

# Deploy (one command!)
gcloud run deploy tradingview-webhook --source .
```

**Choose:**
- Region: `asia-south1` (Mumbai - closest to Indian markets)
- Allow unauthenticated: `Yes`

**You'll get a URL like:**
```
https://tradingview-webhook-xyz123-uc.a.run.app
```

**Save this URL!** This is your webhook address.

### Step 4: Test It Works (3 min)

```bash
# Test health (replace with your URL)
curl https://YOUR-URL-HERE/health

# Expected response:
{"status":"healthy","timestamp":"2025-11-21T15:30:00+05:30"}
```

✅ If you see this, your service is running!

---

## 🔐 Automatic Token Renewal

**Problem:** Dhan access tokens expire every 24 hours. Manually generating new tokens daily is tedious.

**Solution:** The webhook service automatically generates fresh tokens using TOTP (Time-based One-Time Password) authentication - just like Google Authenticator!

### How It Works

```
Service Startup
    ↓
Check Token Expiry
    ↓
< 1 hour remaining?
    ↓ Yes
Auto-Generate New Token
    ↓
Continue Trading
```

**Before Each Order:**
1. Check if current token is valid (>1 hour remaining)
2. If expiring soon, automatically generate a new 24-hour token
3. Place order with fresh token
4. Zero manual intervention required!

### Setup TOTP (One-Time, 5 Minutes)

#### Step 1: Get TOTP Secret from Dhan

1. Login to https://web.dhan.co
2. Go to **Settings → DhanHQ Trading APIs**
3. Find **"Setup TOTP"** section
4. Click **"Generate TOTP Secret"**
5. Copy the secret (looks like: `N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM`)

#### Step 2: Add to Environment Variables

In your `.env` file (webhook-service folder), add:

```bash
# Dhan Auto-Authentication (for automatic token generation)
DHAN_API_KEY=your_api_key_here
DHAN_API_SECRET=your_api_secret_here
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=your_dhan_user_id
DHAN_PASSWORD=your_dhan_password
```

**Get these values:**
- **API Key & Secret**: Settings → API Management → "API Key" section
- **TOTP Secret**: Settings → DhanHQ Trading APIs → "Setup TOTP"
- **User ID**: Your Dhan login ID (usually 10 digits)
- **Password**: Your Dhan login password

#### Step 3: Deploy with Auto-Renewal

When deploying to Google Cloud, set these as environment variables:

```bash
gcloud run deploy tradingview-webhook \
  --source . \
  --region=asia-south1 \
  --update-env-vars DHAN_API_KEY=your_key,DHAN_API_SECRET=your_secret,DHAN_TOTP_SECRET=your_totp_secret
```

**Or** set in Google Cloud Console:
1. Go to Cloud Run → Your Service
2. Click **"Edit & Deploy New Revision"**
3. Go to **"Variables & Secrets"** tab
4. Add each `DHAN_*` variable

### Check Token Status

```bash
# Check readiness (includes token status)
curl https://YOUR-URL-HERE/ready

# Response shows token validity:
{
  "ready": true,
  "checks": {
    "dhan_client": "initialized",
    "access_token": "valid"
  }
}
```

### Logs Show Auto-Refresh

```bash
# View logs
gcloud run services logs tail tradingview-webhook

# You'll see:
# 2025-11-22 20:29:35 - Token valid (20.5 hours remaining)
# 2025-11-23 18:00:00 - Token expiring soon, generating new token...
# 2025-11-23 18:00:05 - New token generated, valid for 24 hours
```

**Benefits:**
- ✅ Set once, works forever
- ✅ Tokens refresh automatically before expiry
- ✅ No manual intervention needed
- ✅ Secure TOTP-based authentication (same as your bank)

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
   https://YOUR-URL-HERE/webhook
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

Your service starts in **test mode** (`ENABLE_DHAN=false`).

**What happens:**
- ✅ Receives alerts from TradingView
- ✅ Validates everything
- ✅ Logs to `webhook_orders.csv`
- ❌ **Does NOT place real orders**

### View Test Results

```bash
# Check logs
gcloud run services logs tail tradingview-webhook --region=asia-south1

# You'll see:
# ✅ Webhook received from TradingView
# ✅ Order validated: BUY 1 RELIANCE @ MKT
# ⚠️  TEST MODE - Order not placed (ENABLE_DHAN=false)
```

### Enable Live Trading (When Ready)

```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars ENABLE_DHAN=true
```

**⚠️ Important:** After this, alerts will place REAL orders!

---

## 📊 Monitoring Your Orders

### View Real-Time Logs

```bash
# Stream logs (updates live)
gcloud run services logs tail tradingview-webhook --region=asia-south1

# You'll see:
# 2025-11-21 15:30:45 IST | ✅ Webhook received
# 2025-11-21 15:30:46 IST | 📝 Parsed: BUY 10 INFY
# 2025-11-21 15:30:47 IST | ✅ Order placed: ID 123456789
```

### Check Order History

All orders logged to `webhook_orders.csv` with IST timestamps:

```csv
timestamp,symbol,transaction,quantity,status,order_id
2025-11-21 15:30:47 IST,INFY,B,10,success,123456789
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

## 🔐 Security Best Practices

### 1. Change Default Webhook Secret

Your `.env` has `WEBHOOK_SECRET=GTcl4` by default.

**Change it:**
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars WEBHOOK_SECRET=your_random_secret_here
```

Then update TradingView alerts with new secret.

### 2. Token Expiry

Dhan tokens expire after **~20 hours**.

**Symptoms:**
- Orders stop placing
- Logs show "Token expired"

**Fix:**
1. Generate new token at https://web.dhan.co
2. Update Cloud Run:
   ```bash
   gcloud run services update tradingview-webhook \
     --region=asia-south1 \
     --update-env-vars DHAN_ACCESS_TOKEN=new_token_here
   ```

### 3. Test Before Live

Always test with `ENABLE_DHAN=false` first!

---

## 🐛 Common Issues & Fixes

### "Order not placed - TEST MODE"

**Cause:** Service is in test mode  
**Fix:** Enable live trading:
```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars ENABLE_DHAN=true
```

### "Invalid webhook secret"

**Cause:** Secret in TradingView doesn't match `.env`  
**Fix:** Check both match exactly (case-sensitive)

### "Symbol not found"

**Cause:** Symbol spelling or exchange wrong  
**Fix:** Use exact Dhan format (e.g., "RELIANCE" not "RELIANCE-EQ")

### "Token expired"

**Cause:** Dhan token older than 20 hours  
**Fix:** Generate new token and update (see Security section above)

### "Market closed"

**Cause:** Order placed outside trading hours  
**Fix:** Indian markets: 9:15 AM - 3:30 PM IST (Mon-Fri)

---

## 📚 File Structure Explained

```
webhook-service/
├── app.py                    # Receives TradingView alerts
├── dhan_client.py            # Places orders on Dhan
├── security_id_list.csv      # All tradable symbols
├── webhook_orders.csv        # Order history
├── .env                      # Your credentials
├── Dockerfile                # Cloud packaging
├── requirements.txt          # Software needed
└── docs/
    ├── DHAN_LIVE_TRADING_GUIDE.md     # Order types
    ├── DHAN_CREDENTIALS_GUIDE.md      # API access
    ├── TRADINGVIEW_POST.md            # Alert setup
    └── MARKET_ALERTS_GUIDE.md         # This file
```

**Everything needed to run is included!**

---

## 🔄 Updating Your Deployment

### Update Dhan Token

```bash
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars DHAN_ACCESS_TOKEN=new_token_here
```

### Update Code (if needed)

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
- [ ] Get Dhan Client ID
- [ ] Get Dhan Access Token
- [ ] Deploy to Cloud Run
- [ ] Copy webhook URL

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
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 --limit=50
```

### 5. Keep Token Fresh
Set calendar reminder to regenerate Dhan token every 24 hours.

---

## 📞 Need Help?

### Documentation
- **This guide** - Overview and quick start
- `DHAN_LIVE_TRADING_GUIDE.md` - All order types explained
- `TRADINGVIEW_POST.md` - Advanced TradingView setup
- `DHAN_CREDENTIALS_GUIDE.md` - API access details

### View Logs
```bash
gcloud run services logs tail tradingview-webhook --region=asia-south1
```

### Test Connection
```bash
curl https://YOUR-URL/health
```

### Common Commands
```bash
# View service details
gcloud run services describe tradingview-webhook --region=asia-south1

# Update environment variable
gcloud run services update tradingview-webhook \
  --region=asia-south1 --update-env-vars KEY=VALUE

# Redeploy
cd webhook-service && gcloud run deploy tradingview-webhook --source .
```

---

## 🎉 You're Ready!

**Recap:**
1. ✅ Deploy webhook service to Google Cloud ($0/month)
2. ✅ Get permanent HTTPS webhook URL
3. ✅ Configure TradingView alerts
4. ✅ Orders automatically execute on Dhan

**Test first, then go live!**

Happy automated trading! 📈
