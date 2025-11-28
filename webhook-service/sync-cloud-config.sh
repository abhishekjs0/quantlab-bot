#!/bin/bash

##############################################################################
# Webhook Service Configuration Sync Script
#
# Purpose: Synchronize webhook-service/.env to Cloud Run deployment
#
# Usage:
#   ./sync-cloud-config.sh          # Deploy to production
#   ./sync-cloud-config.sh --dry    # Show what would be deployed
#   ./sync-cloud-config.sh --verify # Check if Cloud Run matches local
#
# This script reads webhook-service/.env and updates Cloud Run environment
# variables to keep local and cloud configurations in sync.
#
# SAFETY FIRST: Always test with --dry before deploying with --verify
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ENV_FILE="${SCRIPT_DIR}/.env"
PROJECT_ID="tradingview-webhook-prod"
SERVICE_NAME="tradingview-webhook"
REGION="asia-south1"
DRY_RUN=false
VERIFY_ONLY=false

##############################################################################
# Helper Functions
##############################################################################

print_header() {
    echo -e "\n${BLUE}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════════${NC}\n"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

check_prerequisites() {
    # Check if .env exists
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Environment file not found: $ENV_FILE"
        echo "Current directory: $(pwd)"
        echo "Expected path: $ENV_FILE"
        exit 1
    fi
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI not found"
        echo "Install from: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    # Check if gcloud is authenticated
    if ! gcloud auth list 2>/dev/null | grep -q ACTIVE; then
        print_error "gcloud is not authenticated"
        echo "Run: gcloud auth login"
        exit 1
    fi
    
    # Check if project is set
    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
    if [ -z "$CURRENT_PROJECT" ]; then
        print_warning "No gcloud project set, will use PROJECT_ID: $PROJECT_ID"
    fi
}

parse_env_file() {
    # Parse .env file and build env vars string for gcloud
    # Skips comments, empty lines, and certain variables
    
    ENV_VARS=""
    EXCLUDED_VARS=("PORT" "HOST" "CSV_LOG_PATH")
    
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ $key =~ ^#.*$ ]] && continue
        [[ -z $key ]] && continue
        
        # Skip excluded variables
        skip=false
        for excluded in "${EXCLUDED_VARS[@]}"; do
            if [ "$key" == "$excluded" ]; then
                skip=true
                break
            fi
        done
        [ "$skip" = true ] && continue
        
        # Remove surrounding quotes
        value=$(echo "$value" | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
        
        # Add to env vars
        if [ -z "$ENV_VARS" ]; then
            ENV_VARS="${key}=${value}"
        else
            ENV_VARS="${ENV_VARS},${key}=${value}"
        fi
    done < "$ENV_FILE"
    
    echo "$ENV_VARS"
}

count_env_vars() {
    local env_vars="$1"
    echo "$env_vars" | awk -F',' '{print NF}'
}

show_env_vars() {
    local env_vars="$1"
    local count=$(count_env_vars "$env_vars")
    
    echo -e "${BLUE}Environment variables to sync ($count total):${NC}\n"
    
    # Parse and display
    IFS=',' read -ra VARS <<< "$env_vars"
    for var in "${VARS[@]}"; do
        IFS='=' read -r key value <<< "$var"
        
        # Mask sensitive values
        if [[ "$key" == *"TOKEN"* ]] || [[ "$key" == *"PASSWORD"* ]] || [[ "$key" == *"PIN"* ]] || [[ "$key" == *"SECRET"* ]]; then
            masked_value="${value:0:10}..."
        else
            masked_value="$value"
        fi
        
        echo "  ${BLUE}${key}${NC} = ${masked_value}"
    done
}

deploy_to_cloud_run() {
    local env_vars="$1"
    
    if [ "$DRY_RUN" = true ]; then
        print_info "DRY RUN MODE - Would execute:"
        echo ""
        echo "gcloud run services update ${SERVICE_NAME} \\"
        echo "    --region ${REGION} \\"
        echo "    --set-env-vars \"${env_vars:0:80}...\""
        echo ""
        return 0
    fi
    
    print_info "Deploying to Cloud Run..."
    
    if gcloud run services update "${SERVICE_NAME}" \
        --region "${REGION}" \
        --set-env-vars "${env_vars}" \
        --project "${PROJECT_ID}" 2>&1; then
        print_success "Cloud Run deployment updated successfully"
        return 0
    else
        print_error "Failed to update Cloud Run deployment"
        return 1
    fi
}

verify_sync() {
    local local_count=$(count_env_vars "$1")
    
    print_info "Verifying Cloud Run configuration..."
    
    # Get current Cloud Run env vars
    CLOUD_ENV=$(gcloud run services describe "${SERVICE_NAME}" \
        --region "${REGION}" \
        --project "${PROJECT_ID}" \
        --format='value(spec.template.spec.containers[0].env[])' 2>/dev/null || echo "")
    
    local cloud_count=$(echo "$CLOUD_ENV" | wc -l)
    
    if [ -z "$CLOUD_ENV" ]; then
        print_warning "Could not retrieve Cloud Run env vars"
        return 1
    fi
    
    print_success "Cloud Run configuration verified"
    echo "  Local .env variables: $local_count"
    echo "  Cloud Run variables: $cloud_count"
    
    return 0
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTION]

Synchronize webhook-service/.env to Cloud Run deployment

Options:
  (default)     Deploy local .env to Cloud Run
  --dry         Show what would be deployed (no changes)
  --verify      Verify Cloud Run matches local config
  --help        Show this help message

Examples:
  # Preview changes
  ./sync-cloud-config.sh --dry
  
  # Verify current sync status
  ./sync-cloud-config.sh --verify
  
  # Deploy changes to production
  ./sync-cloud-config.sh

Security Notes:
  • Sensitive values (TOKEN, PASSWORD, PIN, SECRET) are masked in output
  • Use --dry before deploying to verify changes
  • Always commit .env changes before syncing

EOF
}

##############################################################################
# Main Script
##############################################################################

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry)
            DRY_RUN=true
            shift
            ;;
        --verify)
            VERIFY_ONLY=true
            shift
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

print_header "Webhook Service Configuration Sync"

# Check prerequisites
print_info "Checking prerequisites..."
check_prerequisites
print_success "Prerequisites met"

# Parse environment file
print_info "Reading configuration from $ENV_FILE..."
ENV_VARS=$(parse_env_file)

if [ -z "$ENV_VARS" ]; then
    print_error "No environment variables found in $ENV_FILE"
    exit 1
fi

print_success "Configuration parsed"

# Show what we're about to do
show_env_vars "$ENV_VARS"

# Handle verify-only mode
if [ "$VERIFY_ONLY" = true ]; then
    echo ""
    verify_sync "$ENV_VARS"
    exit 0
fi

# Confirm deployment
echo ""
if [ "$DRY_RUN" = true ]; then
    print_info "DRY RUN MODE - No changes will be made"
else
    print_warning "This will update Cloud Run environment variables"
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled"
        exit 0
    fi
fi

echo ""

# Deploy to Cloud Run
deploy_to_cloud_run "$ENV_VARS"
DEPLOY_STATUS=$?

echo ""

# Verify if not dry run
if [ "$DRY_RUN" = false ] && [ $DEPLOY_STATUS -eq 0 ]; then
    sleep 2  # Wait a moment for Cloud Run to process
    verify_sync "$ENV_VARS"
fi

echo ""

# Summary
if [ "$DRY_RUN" = true ]; then
    print_info "Dry run completed. To deploy, run: ./sync-cloud-config.sh"
else
    if [ $DEPLOY_STATUS -eq 0 ]; then
        print_success "Configuration sync completed successfully!"
        echo ""
        echo "Next steps:"
        echo "  • Monitor Cloud Run logs: gcloud logs tail --service=${SERVICE_NAME}"
        echo "  • Verify webhook is working: curl https://SERVICE_URL/health"
        echo ""
        echo "Service URL: https://$(gcloud run services describe ${SERVICE_NAME} --region=${REGION} --format='value(status.url)')"
    else
        print_error "Configuration sync failed"
        exit 1
    fi
fi

echo ""
