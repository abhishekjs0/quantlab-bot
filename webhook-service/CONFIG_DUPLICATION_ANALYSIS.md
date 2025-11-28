# Configuration Duplication Analysis - Single Source of Truth

**Date:** 2025-11-27  
**Analysis:** Investigation of credential and configuration management across local and Cloud Run deployments  

---

## Executive Summary

**Problem:** Your webhook service has significant configuration duplication across multiple files with inconsistent values, creating maintenance burden and the Telegram token bug we just fixed.

**Root Cause:** 
- Multiple `.env` files (workspace root + webhook-service)
- Manual deployment scripts copying env vars
- No centralized credential management
- No automation to keep them in sync
- Manual Cloud Run environment variable updates

**Impact:**
- ✗ Token updated locally, forgotten in Cloud Run (today's bug)
- ✗ Configuration drift between environments
- ✗ No audit trail of changes
- ✗ Manual, error-prone deployment process
- ✗ Hard to manage secrets securely

---

## Current State: Configuration Files Map

### 1. **Workspace Root: `/Users/abhishekshah/Desktop/quantlab-workspace/.env`**

```dotenv
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
DHAN_USER_ID=9624973000
DHAN_PASSWORD=v*L4vb&n
DHAN_PIN=224499
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM

WEBHOOK_SECRET=GTcl4
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=80
ENABLE_DHAN=false
```

**Purpose:** Root workspace configuration (backtesting, local development)  
**Used by:** Core/strategies, not by webhook service

---

### 2. **Webhook Service: `/webhook-service/.env`**

```dotenv
# Dhan API Credentials
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=9624973000
DHAN_PASSWORD=v*L4vb&n
DHAN_PIN=224499

# Webhook Configuration
WEBHOOK_SECRET=GTcl4
ENABLE_DHAN=true

# Order Execution Configuration
AUTO_HEALTH_CHECK=true
HEALTH_CHECK_INTERVAL=21600
CSV_LOG_PATH=./webhook_orders.csv

# Server Configuration (Cloud Run will override PORT)
PORT=8080
HOST=0.0.0.0

# Telegram Notifications
ENABLE_TELEGRAM=true
TELEGRAM_BOT_TOKEN=8208173603:AAGG2mx34E9qfaBnTyswlIOITT0Zsi4L0k
TELEGRAM_CHAT_ID=5055508551
```

**Purpose:** Webhook service local development/testing  
**Used by:** app.py, dhan_auth.py, telegram_notifier.py  

---

### 3. **Cloud Run (Deployed)**

Set manually via `gcloud run services update --set-env-vars`:
```
TELEGRAM_BOT_TOKEN=8208173603:AAGG2mx34E9qfaBnTyswlIOITT0Zsi4L0k  ✅ (NOW CORRECT)
TELEGRAM_CHAT_ID=5055508551
DHAN_CLIENT_ID=1108351648
DHAN_API_KEY=fdbe282b
DHAN_API_SECRET=2caf6c46-9bde-45b3-a1c7-a6d38a0f75b9
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=9624973000
DHAN_PASSWORD=v*L4vb&n
DHAN_PIN=224499
WEBHOOK_SECRET=GTcl4
ENABLE_DHAN=true
```

**Purpose:** Production webhook service  
**Set by:** Manual `gcloud` commands (no automation)  

---

### 4. **Deployment Script: `webhook-service/deploy.sh`**

```bash
# Reads .env line by line and converts to comma-separated format
while IFS='=' read -r key value; do
    # ... processing ...
    ENV_VARS="${ENV_VARS},${key}=${value}"
done < .env

# Passes to Cloud Run
gcloud run deploy ${SERVICE_NAME} \
    --set-env-vars "${ENV_VARS}"
```

**Issue:** Only works if user runs deploy.sh, manual deployments bypass this

---

### 5. **Cron Job Config: `webhook-service/cron-job.yaml`**

```yaml
httpTarget:
  uri: https://tradingview-webhook-cgy4m5alfq-el.a.run.app/refresh-token
  # Service URL is HARDCODED ⚠️
```

**Issue:** Service URL hardcoded, not parametrized

---

### 6. **Docker Configuration: `webhook-service/Dockerfile`**

```dockerfile
ENV PYTHONUNBUFFERED=1
# No env vars set here - relies on Cloud Run to inject them
EXPOSE 8080
```

**Issue:** No build-time secrets, relies entirely on runtime injection

---

## Identified Duplication Points

### Duplication #1: DHAN Credentials (3 places)

| Location | Value | Sync Status |
|----------|-------|-------------|
| `/.env` | ✓ DHAN_CLIENT_ID=1108351648 | ✅ |
| `/webhook-service/.env` | ✓ DHAN_CLIENT_ID=1108351648 | ✅ |
| `Cloud Run env vars` | ✓ DHAN_CLIENT_ID=1108351648 | ✅ |
| | | |
| `/.env` | ✓ DHAN_API_KEY=fdbe282b | ✅ |
| `/webhook-service/.env` | ✓ DHAN_API_KEY=fdbe282b | ✅ |
| `Cloud Run env vars` | ✓ DHAN_API_KEY=fdbe282b | ✅ |

**Why Duplication?** Root .env shouldn't have webhook secrets; webhook .env has its own copy.

---

### Duplication #2: Telegram Credentials (2 places + gap)

| Location | Value | Sync Status |
|----------|-------|-------------|
| `/.env` | ✗ NOT PRESENT | ❌ Missing |
| `/webhook-service/.env` | ✓ TELEGRAM_BOT_TOKEN=8208173603:AAGG... | ✅ |
| `Cloud Run env vars` | ✓ TELEGRAM_BOT_TOKEN=8208173603:AAGG... | ✅ |

**⚠️ Bug Found:** Root `.env` doesn't have Telegram tokens, only webhook-service does.
**Result:** If someone updates root .env and redeploys, Telegram credentials get lost!

---

### Duplication #3: WEBHOOK_SECRET (2 places)

| Location | Value | Sync Status |
|----------|-------|-------------|
| `/.env` | ✓ WEBHOOK_SECRET=GTcl4 | ✅ |
| `/webhook-service/.env` | ✓ WEBHOOK_SECRET=GTcl4 | ✅ |
| `Cloud Run env vars` | ✓ WEBHOOK_SECRET=GTcl4 | ✅ |

**Why?** Root .env has it but doesn't use it (ENABLE_DHAN=false locally).

---

### Duplication #4: Deployment Process

Current flow has THREE separate update paths:

**Path 1: Manual gcloud command**
```bash
gcloud run services update tradingview-webhook \
  --set-env-vars="TELEGRAM_BOT_TOKEN=..."
  # User manually maintains sync
```

**Path 2: Using deploy.sh**
```bash
./webhook-service/deploy.sh
# Reads .env, but only if user runs script
```

**Path 3: Cloud Console**
- Manual web UI updates (no tracking, no version control)

**Result:** No single source of truth. Configuration can diverge at any update.

---

### Duplication #5: Service URL Hardcoding

| File | Content | Issue |
|------|---------|-------|
| `deploy.sh` | N/A (outputs URL) | ✅ |
| `cron-job.yaml` | `https://tradingview-webhook-cgy4m5alfq-el.a.run.app/refresh-token` | ❌ HARDCODED |
| `.env` | `DHAN_REDIRECT_URI=https://tradingview-webhook-cgy4m5alfq-el.a.run.app/auth/callback` | ⚠️ Must match Cloud Run URL |

**Problem:** If service URL changes (new region, new project), must update 2+ places manually.

---

## Solutions: Single Source of Truth Options

### Option 1: **Google Secret Manager (RECOMMENDED) ⭐⭐⭐⭐⭐**

Store all secrets in Google Secret Manager, Cloud Run pulls at runtime.

**Pros:**
- ✅ Centralized, version-controlled
- ✅ Encrypted storage
- ✅ Audit trail (who accessed what, when)
- ✅ IAM-based access control
- ✅ No secrets in Git
- ✅ Automatic rollback capability
- ✅ Integration with Cloud Run native

**Cons:**
- ⚠️ Requires Google Cloud project (you already have it)
- ⚠️ Slight latency (milliseconds, not noticeable)

**Implementation:**
```bash
# Store secrets
gcloud secrets create dhan-client-id --replication-policy="automatic" \
  --data-file=- <<< "1108351648"

gcloud secrets create telegram-bot-token --replication-policy="automatic" \
  --data-file=- <<< "8208173603:AAGG2mx34E9qfaBnTyswlIOITT0Zsi4L0k"

# Mount in Cloud Run
gcloud run services update tradingview-webhook \
  --update-secrets=DHAN_CLIENT_ID=dhan-client-id:latest \
  --update-secrets=TELEGRAM_BOT_TOKEN=telegram-bot-token:latest
```

**Local Development:**
```bash
# Download secrets for local .env
gcloud secrets versions access latest --secret="dhan-client-id"
# Create local .env manually (not synced to cloud)
```

---

### Option 2: **Terraform/Infrastructure as Code (RECOMMENDED) ⭐⭐⭐⭐⭐**

Define entire Cloud Run deployment in Terraform code.

**Pros:**
- ✅ Infrastructure as Code (version controlled)
- ✅ Reproducible deployments
- ✅ Can manage secrets + service + cron job together
- ✅ Consistent across environments
- ✅ Easy rollback

**Cons:**
- ⚠️ Learning curve for Terraform
- ⚠️ Terraform state file management needed

**Example:**
```hcl
resource "google_cloud_run_service" "webhook" {
  name     = "tradingview-webhook"
  location = "asia-south1"

  template {
    spec {
      containers {
        image = "gcr.io/project/webhook:latest"
        
        env {
          name  = "TELEGRAM_BOT_TOKEN"
          value = data.google_secret_manager_secret_version.telegram_token.secret_data
        }
      }
    }
  }
}

resource "google_cloud_scheduler_job" "token_refresh" {
  name            = "dhan-token-refresh"
  schedule        = "0 8 * * *"
  time_zone       = "Asia/Kolkata"
  http_target {
    uri = google_cloud_run_service.webhook.status[0].url + "/refresh-token"
    # ✅ URL automatically generated, stays in sync
  }
}
```

---

### Option 3: **CI/CD Pipeline (GitHub Actions) ⭐⭐⭐⭐**

Automate deployment to keep environments in sync.

**Pros:**
- ✅ Version-controlled (Git commits trigger deploys)
- ✅ Automatic testing before deploy
- ✅ Audit trail (who deployed when)
- ✅ Rollback via Git revert

**Cons:**
- ⚠️ Requires GitHub workflows setup
- ⚠️ Slightly slower (pipeline execution)

**Example Workflow:**
```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
    paths:
      - 'webhook-service/**'
      - '.github/workflows/deploy.yml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
        with:
          service_account_key: ${{ secrets.GCP_SA_KEY }}
      
      - name: Build and push Docker image
        run: |
          gcloud builds submit webhook-service --tag gcr.io/project/webhook:${{ github.sha }}
      
      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy tradingview-webhook \
            --image=gcr.io/project/webhook:${{ github.sha }} \
            --set-env-vars TELEGRAM_BOT_TOKEN=${{ secrets.TELEGRAM_BOT_TOKEN }}
```

---

### Option 4: **env-sync Script (QUICK FIX) ⭐⭐**

Create a script that keeps files in sync.

**Pros:**
- ✅ Quick to implement
- ✅ No new infrastructure

**Cons:**
- ⚠️ Still manual (must remember to run)
- ⚠️ Error-prone
- ⚠️ No audit trail

**Example:**
```bash
#!/bin/bash
# sync-env.sh - Sync webhook-service/.env to Cloud Run

set -e

if [ "$1" == "push" ]; then
    echo "📤 Syncing .env to Cloud Run..."
    
    # Read .env and extract telegram vars
    TELEGRAM_BOT_TOKEN=$(grep "TELEGRAM_BOT_TOKEN=" webhook-service/.env | cut -d'=' -f2)
    TELEGRAM_CHAT_ID=$(grep "TELEGRAM_CHAT_ID=" webhook-service/.env | cut -d'=' -f2)
    
    gcloud run services update tradingview-webhook \
      --update-env-vars=TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN,TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID
    
    echo "✅ Done"
elif [ "$1" == "pull" ]; then
    echo "📥 Pulling from Cloud Run..."
    # ... download and update .env
fi
```

---

## Recommendation: Hybrid Approach

**Phase 1 (Immediate - This Week)** - Fix sync issues
1. **Consolidate .env files**
   - Delete root `.env` or move Telegram/webhook-specific vars
   - Keep only webhook-service/.env as source of truth
   
2. **Create env-sync script**
   - Quick safety net before automated solution
   - Run before every Cloud Run deployment

**Phase 2 (Next Week)** - Automate with CI/CD
1. **Set up GitHub Actions**
   - Automatically deploy on webhook-service changes
   - Automatically sync env vars to Cloud Run
   - Add pre-deploy testing

**Phase 3 (Future)** - Full Infrastructure as Code
1. **Migrate to Terraform**
   - Manage Cloud Run + Scheduler + Secrets together
   - Version controlled, reproducible infrastructure

---

## Implementation: Phase 1 (This Week)

### Step 1: Consolidate ENV Files

**Current state:**
```
/.env                          (workspace root, not for webhook)
/webhook-service/.env          (webhook service, source of truth)
Cloud Run env vars             (manually set, out of sync)
```

**Target state:**
```
/.env                          (only backtest/strategy settings)
/webhook-service/.env          (webhook service, SINGLE SOURCE)
Cloud Run env vars             (auto-synced from webhook-service/.env)
```

**Action:**
1. Remove Telegram/webhook vars from root `.env`
2. Keep `/webhook-service/.env` as authoritative source
3. Document: "Always update /webhook-service/.env first, then sync"

---

### Step 2: Create Sync Script

Create `/webhook-service/sync-cloud-config.sh`:

```bash
#!/bin/bash

set -e

PROJECT_ID="tradingview-webhook-prod"
SERVICE_NAME="tradingview-webhook"
REGION="asia-south1"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env not found"
    exit 1
fi

echo "📤 Syncing webhook-service/.env to Cloud Run..."

# Parse .env and build env-vars string
ENV_VARS=""
while IFS='=' read -r key value; do
    [[ $key =~ ^#.*$ ]] && continue
    [[ -z $key ]] && continue
    [[ $key == "PORT" || $key == "HOST" ]] && continue
    
    value=$(echo $value | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
    
    if [ -z "$ENV_VARS" ]; then
        ENV_VARS="${key}=${value}"
    else
        ENV_VARS="${ENV_VARS},${key}=${value}"
    fi
done < .env

# Deploy to Cloud Run
gcloud run services update ${SERVICE_NAME} \
    --region ${REGION} \
    --set-env-vars "${ENV_VARS}"

echo "✅ Successfully synced to Cloud Run"
```

**Usage:**
```bash
cd webhook-service
./sync-cloud-config.sh
```

---

### Step 3: Update Documentation

Add to `/webhook-service/README.md`:

```markdown
## Configuration Management

### Source of Truth
- **Webhook service config:** `webhook-service/.env`
- **Cloud Run deployment:** Synced from `.env` via `sync-cloud-config.sh`

### Updating Configuration

1. Edit `webhook-service/.env`
2. Sync to Cloud Run:
   ```bash
   cd webhook-service
   ./sync-cloud-config.sh
   ```

### DO NOT
- ❌ Manually update Cloud Run env vars via gcloud command
- ❌ Update via Cloud Console UI
- ❌ Forget to sync after .env changes
```

---

## Files Currently Affected by Duplication

| File | Issue | Severity |
|------|-------|----------|
| `/.env` | Contains webhook-specific vars (WEBHOOK_SECRET, ENABLE_DHAN) | ⚠️ Medium |
| `/.env` | Missing Telegram vars | ❌ High |
| `/webhook-service/.env` | Duplicates DHAN vars from root .env | ⚠️ Medium |
| `webhook-service/deploy.sh` | Only syncs if user manually runs it | ⚠️ Medium |
| `webhook-service/cron-job.yaml` | Service URL hardcoded | ❌ High |
| `webhook-service/Dockerfile` | No validation of env vars at build time | ⚠️ Low |
| Cloud Run deployment | Manual env var management, no automation | ❌ High |

---

## Quick Reference: What Needs Fixing

```
PRIORITY 1 - CRITICAL (Do This Week)
├─ Create sync-cloud-config.sh script ✅
├─ Document sync procedure ✅
├─ Add pre-commit hook to warn about .env changes ⏳
└─ Add to deployment checklist ⏳

PRIORITY 2 - IMPORTANT (Do Next Week)
├─ Set up GitHub Actions workflow
├─ Migrate to Google Secret Manager
└─ Add automated testing to deployment

PRIORITY 3 - NICE TO HAVE (Future)
├─ Full Terraform infrastructure
├─ Multi-environment support (staging/production)
└─ Automated credential rotation
```

---

## Summary

**Current Risk:** Telegram/DHAN token mismatches will keep happening until you centralize configuration.

**Root Cause:** Multiple configuration sources with manual sync → human error inevitable.

**Best Solution:** Single source of truth + automated sync.

**Quickest Fix:** Consolidate `.env` files + create sync script (1-2 hours to implement).

**Long-term:** Terraform + GitHub Actions (professional infrastructure management).

The webhook service code is excellent. The duplication problem is purely operational/deployment infrastructure, not code quality.

---

**Next Steps:**
1. Implement Phase 1 immediately (prevents future token bugs)
2. Plan Phase 2 for next week (automate via GitHub Actions)
3. Consider Phase 3 when scaling to multiple services
