#!/bin/bash
# Deploy Telegram Summarizer to Google Cloud Run

set -e

# Configuration
PROJECT_ID="tradingview-webhook-prod"
REGION="asia-south1"
JOB_NAME="telegram-summarizer"
IMAGE_NAME="gcr.io/${PROJECT_ID}/telegram-summarizer"

echo "🚀 Deploying Telegram Summarizer to Google Cloud"
echo "================================================"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Install from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
echo "📁 Setting project to ${PROJECT_ID}..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable cloudscheduler.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Build and push Docker image
echo "🐳 Building Docker image..."
gcloud builds submit --tag ${IMAGE_NAME}:latest .

# Create secrets (if not exists)
echo "🔐 Setting up secrets..."

# Check if secrets exist, create if not
for SECRET_NAME in telegram-api-id telegram-api-hash telegram-bot-token telegram-chat-id openai-api-key telegram-groups telegram-session; do
    if ! gcloud secrets describe ${SECRET_NAME} &>/dev/null 2>&1; then
        echo "   Creating secret: ${SECRET_NAME}"
        gcloud secrets create ${SECRET_NAME} --replication-policy="automatic"
    fi
done

echo ""
echo "⚠️  IMPORTANT: Add secret values manually if not already set:"
echo "   gcloud secrets versions add telegram-api-id --data-file=-"
echo "   (then paste value and press Ctrl+D)"
echo ""

# Create Cloud Run Job
echo "☁️ Creating/Updating Cloud Run Job..."
gcloud run jobs create ${JOB_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --memory 2Gi \
    --cpu 1 \
    --max-retries 1 \
    --task-timeout 600s \
    --set-secrets="TELEGRAM_API_ID=telegram-api-id:latest,TELEGRAM_API_HASH=telegram-api-hash:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TELEGRAM_SUMMARY_CHAT_ID=telegram-chat-id:latest,OPENAI_API_KEY=openai-api-key:latest,TELEGRAM_GROUPS=telegram-groups:latest" \
    2>/dev/null || \
gcloud run jobs update ${JOB_NAME} \
    --image ${IMAGE_NAME}:latest \
    --region ${REGION} \
    --memory 2Gi \
    --cpu 1 \
    --max-retries 1 \
    --task-timeout 600s \
    --set-secrets="TELEGRAM_API_ID=telegram-api-id:latest,TELEGRAM_API_HASH=telegram-api-hash:latest,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TELEGRAM_SUMMARY_CHAT_ID=telegram-chat-id:latest,OPENAI_API_KEY=openai-api-key:latest,TELEGRAM_GROUPS=telegram-groups:latest"

# Create Cloud Scheduler Job (11:55 PM IST = 18:25 UTC)
echo "⏰ Creating Cloud Scheduler (11:55 PM IST daily)..."
gcloud scheduler jobs create http ${JOB_NAME}-scheduler \
    --location ${REGION} \
    --schedule "25 18 * * *" \
    --time-zone "Asia/Kolkata" \
    --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method POST \
    --oauth-service-account-email "${PROJECT_ID}@appspot.gserviceaccount.com" \
    2>/dev/null || \
gcloud scheduler jobs update http ${JOB_NAME}-scheduler \
    --location ${REGION} \
    --schedule "25 18 * * *" \
    --time-zone "Asia/Kolkata" \
    --uri "https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run" \
    --http-method POST \
    --oauth-service-account-email "${PROJECT_ID}@appspot.gserviceaccount.com"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Add secrets if not already done (see above)"
echo "   2. Upload Pyrogram session file as secret:"
echo "      gcloud secrets versions add telegram-session --data-file=telegram_summarizer.session"
echo "   3. Test run the job:"
echo "      gcloud run jobs execute ${JOB_NAME} --region ${REGION}"
echo "   4. Check logs:"
echo "      gcloud run jobs executions list --job ${JOB_NAME} --region ${REGION}"
echo ""
echo "🕐 Job will run daily at 11:55 PM IST"
