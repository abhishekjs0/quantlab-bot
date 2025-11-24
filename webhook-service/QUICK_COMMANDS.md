# Webhook Service - Quick Commands

## 🚀 Deploy Service
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
gcloud builds submit --tag gcr.io/tradingview-webhook-prod/tradingview-webhook:latest
```

Then deploy:
```bash
bash deploy-with-new-credentials.sh
```

## ⏰ Setup Cron Job
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
bash setup-cron-job.sh
```

## 🧪 Test Deployment
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
bash test-deployment.sh
```

## 📊 Check Status
```bash
# Health
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health

# Ready (checks token)
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# Market status
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/market-status
```

## 📝 View Logs
```bash
# Recent logs
gcloud logging read 'resource.type="cloud_run_revision"' --limit=50

# OAuth callback logs
gcloud logging read 'textPayload:"OAuth callback"' --limit=20

# Token refresh logs
gcloud logging read 'textPayload:"Token"' --limit=30

# Cron job logs
gcloud logging read 'resource.type="cloud_scheduler_job"' --limit=20
```

## 🔧 Manage Cron Job
```bash
# View job
gcloud scheduler jobs describe dhan-token-refresh --location=asia-south1

# Run manually
gcloud scheduler jobs run dhan-token-refresh --location=asia-south1

# Pause
gcloud scheduler jobs pause dhan-token-refresh --location=asia-south1

# Resume
gcloud scheduler jobs resume dhan-token-refresh --location=asia-south1
```

## 🔑 Key URLs
- **Service**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app
- **Health**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health
- **OAuth Callback**: https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
- **Dhan API**: https://web.dhan.co (for generating API keys)

## 📋 New API Credentials
```
API_KEY: fdbe282b
API_SECRET: 2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
REDIRECT_URI: https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
```

## ✅ Testing OAuth Flow
1. Visit https://web.dhan.co → API Management
2. Find your API key with redirect URL above
3. Click "Authorize" or "Test"
4. Complete login (mobile → TOTP → PIN)
5. Dhan redirects to your callback URL
6. Service auto-generates new token
7. Check logs: `gcloud logging read 'textPayload:"Successfully generated"' --limit=5`

## 📚 Documentation
- **Complete Guide**: `webhook-service/CONSOLIDATED_DOCS.md`
- **Implementation Summary**: `webhook-service/IMPLEMENTATION_SUMMARY.md`
- **Cron Job Config**: `webhook-service/cron-job.yaml`
