#!/bin/bash

# Cloud Run Deployment Script for TradingView Webhook Service
# This script deploys the webhook service to Google Cloud Run

set -e  # Exit on error

# Configuration
PROJECT_ID="tradingview-webhook-prod"
SERVICE_NAME="tradingview-webhook"
REGION="asia-south1"  # Mumbai region for lower latency
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   TradingView Webhook - Cloud Run Deployment${NC}"
echo -e "${BLUE}================================================${NC}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI not found. Please install it first:${NC}"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check required environment variables
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "   Please create .env with required variables"
    exit 1
fi

echo -e "${GREEN}✓ Environment file found${NC}"

# Set the project
echo -e "\n${BLUE}Setting Google Cloud project...${NC}"
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo -e "\n${BLUE}Enabling required Google Cloud APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com

# Build the container image
echo -e "\n${BLUE}Building Docker container...${NC}"
gcloud builds submit --tag ${IMAGE_NAME}

# Read environment variables from .env
echo -e "\n${BLUE}Loading environment variables...${NC}"
ENV_VARS=""
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    [[ $key =~ ^#.*$ ]] && continue
    [[ -z $key ]] && continue
    
    # Skip Cloud Run reserved variables
    [[ $key == "PORT" ]] && continue
    [[ $key == "HOST" ]] && continue
    
    # Remove quotes from value
    value=$(echo $value | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    
    # Add to env vars (comma-separated for gcloud)
    if [ -z "$ENV_VARS" ]; then
        ENV_VARS="${key}=${value}"
    else
        ENV_VARS="${ENV_VARS},${key}=${value}"
    fi
done < .env

# Deploy to Cloud Run
echo -e "\n${BLUE}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "${ENV_VARS}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --format 'value(status.url)')

echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo -e "${GREEN}================================================${NC}"
echo -e "\n${BLUE}Service URL:${NC} ${SERVICE_URL}"
echo -e "${BLUE}Webhook endpoint:${NC} ${SERVICE_URL}/webhook"
echo -e "${BLUE}Health check:${NC} ${SERVICE_URL}/health"
echo -e "${BLUE}Ready check:${NC} ${SERVICE_URL}/ready"
echo -e "\n${BLUE}To view logs:${NC}"
echo "   gcloud logs tail --service=${SERVICE_NAME} --project=${PROJECT_ID}"
echo -e "\n${BLUE}To view service details:${NC}"
echo "   gcloud run services describe ${SERVICE_NAME} --region=${REGION}"
echo ""
