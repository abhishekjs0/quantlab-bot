#!/bin/bash
# Setup Google Cloud Scheduler job for daily Dhan token refresh at 8:00 AM IST

set -e

echo "⏰ Setting up Cloud Scheduler job for daily token refresh..."
echo ""

PROJECT_ID="tradingview-webhook-prod"
JOB_NAME="dhan-token-refresh"
REGION="asia-south1"
SERVICE_URL="https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready"

# Check if project is set
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null)
if [ "$CURRENT_PROJECT" != "$PROJECT_ID" ]; then
    echo "📝 Setting project to: $PROJECT_ID"
    gcloud config set project $PROJECT_ID
fi

# Check if job already exists
if gcloud scheduler jobs describe $JOB_NAME --location=$REGION &>/dev/null; then
    echo "⚠️  Job '$JOB_NAME' already exists. Updating..."
    
    gcloud scheduler jobs update http $JOB_NAME \
      --schedule="0 8 * * *" \
      --time-zone="Asia/Kolkata" \
      --uri="$SERVICE_URL" \
      --http-method=GET \
      --location=$REGION \
      --description="Daily Dhan access token refresh at 8:00 AM IST" \
      --attempt-deadline=60s
    
    echo "✅ Job updated successfully!"
else
    echo "📝 Creating new job..."
    
    gcloud scheduler jobs create http $JOB_NAME \
      --schedule="0 8 * * *" \
      --time-zone="Asia/Kolkata" \
      --uri="$SERVICE_URL" \
      --http-method=GET \
      --location=$REGION \
      --description="Daily Dhan access token refresh at 8:00 AM IST" \
      --attempt-deadline=60s
    
    echo "✅ Job created successfully!"
fi

echo ""
echo "📊 Job Details:"
gcloud scheduler jobs describe $JOB_NAME --location=$REGION

echo ""
echo "🧪 Testing job (manual trigger)..."
gcloud scheduler jobs run $JOB_NAME --location=$REGION

echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Job Configuration:"
echo "   - Name: $JOB_NAME"
echo "   - Schedule: Every day at 8:00 AM IST"
echo "   - Target: $SERVICE_URL"
echo "   - Location: $REGION"
echo ""
echo "🔍 Monitor executions:"
echo "   gcloud scheduler jobs list --location=$REGION"
echo "   gcloud logging read 'resource.type=cloud_scheduler_job' --limit=20"
echo ""
echo "🔧 Manage job:"
echo "   Pause:  gcloud scheduler jobs pause $JOB_NAME --location=$REGION"
echo "   Resume: gcloud scheduler jobs resume $JOB_NAME --location=$REGION"
echo "   Delete: gcloud scheduler jobs delete $JOB_NAME --location=$REGION"
echo "   Run:    gcloud scheduler jobs run $JOB_NAME --location=$REGION"
