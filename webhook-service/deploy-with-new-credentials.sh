#!/bin/bash
# Deploy webhook service with updated Dhan API credentials

set -e

echo "🚀 Deploying TradingView Webhook Service with new Dhan credentials..."
echo ""

# Load environment variables from .env
if [ -f .env ]; then
    echo "📄 Loading credentials from .env..."
    export $(grep -v '^#' .env | xargs)
else
    echo "❌ .env file not found!"
    exit 1
fi

# Display credentials (masked)
echo "✅ Credentials loaded:"
echo "   - DHAN_API_KEY: ${DHAN_API_KEY:0:4}****"
echo "   - DHAN_API_SECRET: ${DHAN_API_SECRET:0:4}****"
echo "   - DHAN_REDIRECT_URI: $DHAN_REDIRECT_URI"
echo ""

# Build and deploy
echo "🔨 Building and deploying to Cloud Run..."
gcloud run deploy tradingview-webhook \
  --source . \
  --region=asia-south1 \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=80 \
  --min-instances=0 \
  --max-instances=10 \
  --set-env-vars="DHAN_CLIENT_ID=$DHAN_CLIENT_ID,\
DHAN_API_KEY=$DHAN_API_KEY,\
DHAN_API_SECRET=$DHAN_API_SECRET,\
DHAN_REDIRECT_URI=$DHAN_REDIRECT_URI,\
DHAN_TOTP_SECRET=$DHAN_TOTP_SECRET,\
DHAN_USER_ID=$DHAN_USER_ID,\
DHAN_PASSWORD=$DHAN_PASSWORD,\
DHAN_PIN=$DHAN_PIN,\
DHAN_ACCESS_TOKEN=$DHAN_ACCESS_TOKEN,\
WEBHOOK_SECRET=$WEBHOOK_SECRET,\
ENABLE_DHAN=$ENABLE_DHAN,\
AUTO_HEALTH_CHECK=$AUTO_HEALTH_CHECK,\
HEALTH_CHECK_INTERVAL=$HEALTH_CHECK_INTERVAL,\
ENABLE_TELEGRAM=$ENABLE_TELEGRAM,\
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN,\
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Service URL: https://tradingview-webhook-cgy4m5alfq-el.a.run.app"
echo ""
echo "🔍 Test endpoints:"
echo "   Health:  https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health"
echo "   Ready:   https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready"
echo "   Status:  https://tradingview-webhook-cgy4m5alfq-el.a.run.app/"
echo ""
echo "🔐 OAuth Callback:"
echo "   https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback"
echo ""
echo "📝 Next steps:"
echo "   1. Test OAuth flow by visiting Dhan API management page"
echo "   2. Trigger manual login to test callback endpoint"
echo "   3. Monitor logs: gcloud logging read 'resource.type=\"cloud_run_revision\"' --limit=50"
echo "   4. Setup cron job: bash setup-cron-job.sh"
