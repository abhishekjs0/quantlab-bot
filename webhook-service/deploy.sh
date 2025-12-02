#!/bin/bash
#
# Webhook Service Deployment Script
# Deploys to Google Cloud Run with secrets from Secret Manager
#
# Usage:
#   ./deploy.sh              # Deploy to Cloud Run
#   ./deploy.sh --build-only # Build and push image only
#

set -e

# Configuration
PROJECT_ID="tradingview-webhook-prod"
SERVICE_NAME="tradingview-webhook"
REGION="asia-south1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Webhook Service - Cloud Run Deploy${NC}"
echo -e "${BLUE}======================================${NC}"

# Check gcloud
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not installed${NC}"
    exit 1
fi

# Set project
gcloud config set project ${PROJECT_ID} 2>/dev/null

echo -e "\n${BLUE}Deploying to Cloud Run...${NC}"

gcloud run deploy ${SERVICE_NAME} \
  --source=. \
  --region=${REGION} \
  --allow-unauthenticated \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --set-env-vars="\
ENABLE_DHAN=true,\
GCP_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="\
DHAN_CLIENT_ID=dhan-client-id:latest,\
DHAN_API_KEY=dhan-api-key:latest,\
DHAN_API_SECRET=dhan-api-secret:latest,\
DHAN_TOTP_SECRET=dhan-totp-secret:latest,\
DHAN_USER_ID=dhan-user-id:latest,\
DHAN_PASSWORD=dhan-password:latest,\
DHAN_PIN=dhan-pin:latest,\
DHAN_ACCESS_TOKEN=dhan-access-token:latest"

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}✅ Deployment successful!${NC}"
    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')
    echo -e "Service URL: ${SERVICE_URL}"
    echo -e "\nVerify health: curl ${SERVICE_URL}/health"
else
    echo -e "\n${RED}❌ Deployment failed${NC}"
    exit 1
fi
