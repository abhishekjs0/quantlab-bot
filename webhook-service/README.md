# TradingView Webhook Service for Dhan

Standalone webhook service for receiving TradingView alerts and executing orders on Dhan.

**Designed for Cloud Deployment** (Google Cloud Run, DigitalOcean, AWS)

---

## 📖 Documentation

**Start here:** [`docs/MARKET_ALERTS_GUIDE.md`](docs/MARKET_ALERTS_GUIDE.md) - Complete beginner-friendly guide

**Additional guides:**
- [`docs/DHAN_LIVE_TRADING_GUIDE.md`](docs/DHAN_LIVE_TRADING_GUIDE.md) - Order types explained
- [`docs/TRADINGVIEW_POST.md`](docs/TRADINGVIEW_POST.md) - TradingView alert setup
- [`docs/DHAN_CREDENTIALS_GUIDE.md`](docs/DHAN_CREDENTIALS_GUIDE.md) - Get API access
- [`docs/SELL_ORDER_VALIDATION.md`](docs/SELL_ORDER_VALIDATION.md) - SELL order validation with portfolio checks
- [`docs/TELEGRAM_SETUP.md`](docs/TELEGRAM_SETUP.md) - **NEW:** Real-time Telegram notifications

---

## 🚀 Quick Start - Google Cloud Run (Recommended)

### Why Docker?
- **Cloud Run requires Docker** - it runs containers, not raw Python
- **Consistency**: Works identically everywhere (your Mac, Cloud Run, any server)
- **Isolation**: All dependencies packaged together, no conflicts
- **Scalability**: Cloud Run auto-scales your Docker container

### Prerequisites
1. **Google Cloud Account** (free tier: 2M requests/month)
2. **gcloud CLI installed**: `brew install google-cloud-sdk`
3. **Docker Desktop installed**: `brew install --cask docker`

### Step 1: Setup Google Cloud Project

```bash
# Login to Google Cloud
gcloud auth login

# Create new project (or use existing)
gcloud projects create tradingview-webhook --name="TradingView Webhook"

# Set as active project
gcloud config set project tradingview-webhook

# Enable required APIs
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Step 2: Prepare Files

```bash
cd webhook-service

# Copy security_id_list.csv from main project
cp ../data/security_id_list.csv .

# Create .env file with your credentials
cp .env.example .env

# Edit .env file with your Dhan credentials
nano .env
```

**Important**: Set these in `.env`:
```bash
DHAN_CLIENT_ID=your_actual_client_id
DHAN_ACCESS_TOKEN=your_actual_access_token
WEBHOOK_SECRET=GTcl4  # Change this to your own secret
ENABLE_DHAN=true      # Set to true for live trading
```

### Step 3: Deploy to Cloud Run (2 Methods)

#### Method A: Direct Deploy (Easiest - No Docker Required Locally)

```bash
# Deploy directly from source (Google Cloud builds Docker for you)
gcloud run deploy tradingview-webhook \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars WEBHOOK_SECRET=GTcl4 \
  --set-env-vars ENABLE_DHAN=false

# Add Dhan credentials as secrets (secure method)
gcloud run deploy tradingview-webhook \
  --update-secrets DHAN_CLIENT_ID=dhan-client-id:latest \
  --update-secrets DHAN_ACCESS_TOKEN=dhan-access-token:latest
```

#### Method B: Build & Deploy with Docker (More Control)

```bash
# Build Docker image locally (test first)
docker build -t tradingview-webhook .

# Test locally
docker run -p 8080:8080 --env-file .env tradingview-webhook

# Test endpoint
curl http://localhost:8080/health

# If test passes, deploy to Cloud Run
# Configure Docker to push to Google Container Registry
gcloud auth configure-docker

# Build and push to Google Container Registry
docker tag tradingview-webhook gcr.io/tradingview-webhook/webhook:latest
docker push gcr.io/tradingview-webhook/webhook:latest

# Deploy from container
gcloud run deploy tradingview-webhook \
  --image gcr.io/tradingview-webhook/webhook:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars WEBHOOK_SECRET=GTcl4,ENABLE_DHAN=false
```

### Step 4: Get Your Webhook URL

After deployment completes:

```bash
# Get your service URL
gcloud run services describe tradingview-webhook \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)'
```

**Output example**: `https://tradingview-webhook-abc123-uc.a.run.app`

Your webhook endpoint: `https://tradingview-webhook-abc123-uc.a.run.app/webhook`

### Step 5: Test Deployment

```bash
# Health check
curl https://YOUR-CLOUD-RUN-URL/health

# Test webhook (use your actual URL and secret)
curl -X POST https://YOUR-CLOUD-RUN-URL/webhook \
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
        "timenow": "2025-11-21T09:15:00Z"
      }
    }]
  }'
```

### Step 6: Configure TradingView

1. Go to TradingView → Create Alert
2. Set Webhook URL: `https://YOUR-CLOUD-RUN-URL/webhook`
3. Use the JSON payload template from `docs/TRADINGVIEW_POST.md`

---

## 📊 Monitoring & Logs

### View Logs in Real-Time

```bash
# Stream logs
gcloud run services logs tail tradingview-webhook \
  --platform managed \
  --region us-central1

# View recent logs in Cloud Console
gcloud run services logs read tradingview-webhook \
  --platform managed \
  --region us-central1 \
  --limit 50
```

### Cloud Run Monitoring Dashboard

```bash
# Open in browser
gcloud run services describe tradingview-webhook \
  --platform managed \
  --region us-central1 \
  --format 'value(status.url)'
```

Visit: https://console.cloud.google.com/run

---

## 🔧 Configuration

### Environment Variables

Set via `gcloud run deploy` command:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DHAN_CLIENT_ID` | Yes | - | Dhan API client ID |
| `DHAN_ACCESS_TOKEN` | Yes | - | Dhan API access token |
| `WEBHOOK_SECRET` | Yes | GTcl4 | Authentication secret |
| `ENABLE_DHAN` | No | false | Enable live order execution |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token (for notifications) |
| `TELEGRAM_CHAT_ID` | No | - | Telegram chat ID (for notifications) |
| `PORT` | No | 8080 | Server port (Cloud Run sets this) |

### Update Environment Variables

```bash
gcloud run services update tradingview-webhook \
  --platform managed \
  --region us-central1 \
  --set-env-vars ENABLE_DHAN=true,WEBHOOK_SECRET=new_secret
```

### Using Secrets (Recommended for Production)

```bash
# Create secrets
echo -n "your_client_id" | gcloud secrets create dhan-client-id --data-file=-
echo -n "your_access_token" | gcloud secrets create dhan-access-token --data-file=-

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding dhan-client-id \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Deploy with secrets
gcloud run deploy tradingview-webhook \
  --update-secrets DHAN_CLIENT_ID=dhan-client-id:latest,DHAN_ACCESS_TOKEN=dhan-access-token:latest
```

---

## 🛠️ Local Development

### Run Locally Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Copy security ID list
cp ../data/security_id_list.csv .

# Create .env file
cp .env.example .env

# Edit .env with your credentials
nano .env

# Run server
python app.py
```

Visit: http://localhost:8080/health

### Run Locally With Docker

```bash
# Build image
docker build -t webhook-service .

# Run container
docker run -p 8080:8080 --env-file .env webhook-service

# Test
curl http://localhost:8080/health
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check (returns 200 if alive) |
| `/ready` | GET | Readiness check (checks Dhan connection) |
| `/webhook` | POST | Main webhook endpoint for TradingView |
| `/docs` | GET | Interactive API documentation |

---

## 💰 Cost Estimate (Google Cloud Run)

**Free Tier Includes:**
- 2 million requests per month
- 360,000 GB-seconds of memory
- 180,000 vCPU-seconds

**Typical Usage for Webhook:**
- ~1-10 alerts per day = 300/month
- **Cost: $0/month** (well within free tier)

**If exceeding free tier:**
- $0.40 per million requests
- $0.00002400 per GB-second
- Estimated: $1-5/month for moderate use

---

## 🔒 Security Best Practices

1. **Change WEBHOOK_SECRET**: Don't use default "GTcl4"
2. **Use Secrets Manager**: Store credentials in Google Secret Manager
3. **Enable HTTPS**: Cloud Run provides this automatically
4. **Restrict Access**: Use Cloud Run IAM for internal services
5. **Monitor Logs**: Set up alerts for failed orders

---

## 🚨 Troubleshooting

### Deployment Fails

```bash
# Check build logs
gcloud builds list --limit=5

# View specific build
gcloud builds describe BUILD_ID
```

### Container Crashes

```bash
# View logs
gcloud run services logs read tradingview-webhook --limit 100

# Check health endpoint
curl https://YOUR-URL/health
```

### Orders Not Executing

1. Check `ENABLE_DHAN=true` in environment
2. Verify Dhan credentials are correct
3. Check logs for error messages
4. Verify security_id_list.csv is present

### Can't Find Symbol

- Ensure `security_id_list.csv` is included in Docker image
- Check symbol spelling matches Dhan's format
- View logs: symbol not found errors will be logged

---

## 📚 Additional Resources

- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Docker Documentation](https://docs.docker.com/)
- [Dhan API Documentation](https://dhanhq.co/docs/)
- [TradingView Webhooks](https://www.tradingview.com/support/solutions/43000529348-about-webhooks/)

---

## 🔄 Update Deployment

### Deploy New Version

```bash
# After making code changes
gcloud run deploy tradingview-webhook \
  --source . \
  --platform managed \
  --region us-central1
```

### Rollback to Previous Version

```bash
# List revisions
gcloud run revisions list --service tradingview-webhook

# Rollback to specific revision
gcloud run services update-traffic tradingview-webhook \
  --to-revisions REVISION_NAME=100
```

---

## 🎯 Next Steps

1. ✅ Deploy to Cloud Run
2. ✅ Test with TradingView alert
3. ✅ Monitor logs for 24 hours
4. ✅ Enable live trading (`ENABLE_DHAN=true`)
5. ✅ Set up Cloud Monitoring alerts
6. ✅ Backup strategy: Deploy to multiple regions

---

## ❓ FAQ

**Q: Do I need to learn Docker?**
A: No! Use Method A (direct deploy). Google Cloud builds the Docker image for you.

**Q: Can I use other cloud providers?**
A: Yes! This works on:
- AWS App Runner / Elastic Beanstalk
- DigitalOcean App Platform
- Heroku (with Dockerfile)
- Any platform that supports Docker

**Q: What if Cloud Run goes down?**
A: Multi-region deployment:
```bash
gcloud run deploy tradingview-webhook --region asia-south1
gcloud run deploy tradingview-webhook --region us-west1
```

**Q: How do I update security_id_list.csv?**
A: Replace file and redeploy. Cloud Run will use new version.
