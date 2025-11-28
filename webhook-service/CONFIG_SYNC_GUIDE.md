# Configuration Management - Best Practices Guide

**Date:** 2025-11-27  
**Issue:** Configuration duplication between local `.env` and Cloud Run deployment  
**Solution:** Single source of truth with automated sync  

---

## Problem Statement

Your webhook service has configuration duplicated across three places:

1. **Local:** `/webhook-service/.env`
2. **Cloud Run:** Environment variables (manually set)
3. **Root workspace:** `/.env` (partially overlaps)

**Result:** When you updated Telegram token locally, Cloud Run wasn't updated → 401 error.

---

## Solution: Sync Script

Created: `webhook-service/sync-cloud-config.sh`

This script is your **single source of truth gateway** - it ensures Cloud Run always matches your local `.env`.

### How It Works

```
You edit: webhook-service/.env
         ↓
         Run: ./sync-cloud-config.sh
         ↓
         Script reads .env
         ↓
         Updates Cloud Run env vars
         ↓
         Cloud Run config = Local config ✅
```

---

## Quick Start

### 1. **Preview What Will Be Deployed** (Safe, no changes)

```bash
cd webhook-service
./sync-cloud-config.sh --dry
```

Output shows what variables will be synced without making changes.

### 2. **Deploy to Cloud Run** (Updates production)

```bash
cd webhook-service
./sync-cloud-config.sh
```

Prompts for confirmation, then updates Cloud Run.

### 3. **Verify Sync Status** (Check if in sync)

```bash
cd webhook-service
./sync-cloud-config.sh --verify
```

Compares local `.env` with deployed Cloud Run config.

---

## Workflow: Update Credentials

### When You Update Any Credential

```bash
# 1. Edit the config
nano webhook-service/.env

# 2. Preview changes (ALWAYS do this first!)
cd webhook-service
./sync-cloud-config.sh --dry

# 3. Review the output - looks correct?
# 4. Deploy
./sync-cloud-config.sh

# 5. Monitor logs to confirm it worked
gcloud logs tail --service=tradingview-webhook
```

---

## What Gets Synced

### Synced Variables ✅

All variables in `webhook-service/.env` EXCEPT:
- `PORT` (Cloud Run hardcoded to 8080)
- `HOST` (Cloud Run hardcoded to 0.0.0.0)
- `CSV_LOG_PATH` (local file path, not applicable to cloud)

### Synced Variables Include

```
✅ DHAN_CLIENT_ID
✅ DHAN_API_KEY
✅ DHAN_API_SECRET
✅ DHAN_TOTP_SECRET
✅ DHAN_USER_ID
✅ DHAN_PASSWORD
✅ DHAN_PIN
✅ TELEGRAM_BOT_TOKEN     ← This was the problem!
✅ TELEGRAM_CHAT_ID
✅ WEBHOOK_SECRET
✅ ENABLE_DHAN
✅ ENABLE_TELEGRAM
✅ AUTO_HEALTH_CHECK
✅ HEALTH_CHECK_INTERVAL
```

---

## Security

### Sensitive Values Are Masked

The script automatically masks:
- `*_TOKEN` variables → `8208173603...`
- `*_PASSWORD` variables → `v*L4v...`
- `*_PIN` variables → `224...`
- `*_SECRET` variables → `GTcl...`

Output example:
```
ℹ️  Environment variables to sync (15 total):

  DHAN_CLIENT_ID = 1108351648
  DHAN_API_KEY = fdbe282b
  TELEGRAM_BOT_TOKEN = 8208173603...
  DHAN_PASSWORD = v*L4vb...
  ✅ This will update Cloud Run environment variables
```

### Never Commit `.env` to Git

Make sure `.env` is in `.gitignore`:

```bash
# Verify it's ignored
cat .gitignore | grep "\.env"
# Should output: .env
```

---

## Manual Sync vs Automated Sync

### Option 1: Manual Sync (Current) ⏳

**When to use:** Small teams, infrequent changes

```bash
# Update local config
nano webhook-service/.env

# Sync to cloud (must remember!)
cd webhook-service && ./sync-cloud-config.sh
```

**Pros:**
- Simple, explicit control
- Low automation overhead
- Good for learning

**Cons:**
- Must remember to run script
- Manual process, error-prone
- No history/audit trail

---

### Option 2: Automated Sync via GitHub Actions (Future) 🤖

**When to use:** Professional deployments, larger teams

```yaml
# .github/workflows/deploy-webhook.yml
name: Deploy Webhook

on:
  push:
    branches: [main]
    paths: ['webhook-service/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/setup-gcloud@v1
      - run: |
          cd webhook-service
          ./sync-cloud-config.sh --dry  # Verify first
          ./sync-cloud-config.sh         # Deploy
```

**Pros:**
- Automatic (on every commit)
- Version controlled (Git history)
- Audit trail (who changed what)
- CI/CD integration

**Cons:**
- Requires GitHub Actions setup
- Delayed (pipeline execution time)
- Overkill for manual changes

---

## Troubleshooting

### Issue: "gcloud CLI not found"

**Solution:**
```bash
# Install gcloud
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Authenticate
gcloud auth login

# Set project
gcloud config set project tradingview-webhook-prod
```

---

### Issue: "Environment file not found"

**Solution:**
Make sure you're in the correct directory:
```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
./sync-cloud-config.sh
```

---

### Issue: "gcloud is not authenticated"

**Solution:**
```bash
gcloud auth login
# Opens browser, complete authentication
```

---

### Issue: "No gcloud project set"

**Solution:**
```bash
# Set the project
gcloud config set project tradingview-webhook-prod

# Verify
gcloud config get-value project
```

---

### Issue: Variables updated locally but Cloud Run still shows old values

**Possible cause:** You forgot to run the sync script!

**Solution:**
```bash
cd webhook-service
./sync-cloud-config.sh
```

---

### Issue: "This will update Cloud Run environment variables - Continue? (y/N)"

**Meaning:** Script is asking for confirmation before updating production

**Action:** Type `y` and press Enter to proceed, or `n` to cancel

---

## File Structure

```
webhook-service/
├── .env                        ← Single source of truth for config
├── sync-cloud-config.sh        ← Script to sync .env → Cloud Run
├── app.py                      ← Uses env vars
├── dhan_auth.py               ← Uses env vars
├── telegram_notifier.py        ← Uses env vars
├── deploy.sh                  ← OLD script (keep for history)
└── cron-job.yaml              ← Cron config
```

---

## Daily Workflow Checklist

### When You Update a Credential

- [ ] Edit `webhook-service/.env`
- [ ] Run `./sync-cloud-config.sh --dry` to preview
- [ ] Review output carefully
- [ ] Run `./sync-cloud-config.sh` to deploy
- [ ] Monitor logs: `gcloud logs tail --service=tradingview-webhook`
- [ ] Confirm service is working

### Weekly Review

- [ ] Check Cloud Run logs for any errors
- [ ] Verify tokens haven't expired
- [ ] Run `./sync-cloud-config.sh --verify` to check sync status

---

## Future Improvements

### To Implement Soon

1. **Pre-commit hook** - Prevents .env from being committed to Git
   ```bash
   # Add to .git/hooks/pre-commit
   if git diff --cached --name-only | grep -q "webhook-service/.env"; then
       echo "❌ Error: Do not commit .env file"
       exit 1
   fi
   ```

2. **Validation** - Checks if all required vars are set
   ```bash
   # Check in sync script
   for var in DHAN_CLIENT_ID TELEGRAM_BOT_TOKEN; do
       if [ -z "${!var}" ]; then
           echo "❌ Missing required variable: $var"
           exit 1
       fi
   done
   ```

### To Implement Later

1. **GitHub Actions** - Automated deployment on changes
2. **Google Secret Manager** - Centralized secret storage
3. **Terraform** - Infrastructure as Code
4. **Multi-environment** - Separate staging/production configs

---

## Summary

**Manual sync script = Bridge to automated infrastructure**

- **Now:** Use `sync-cloud-config.sh` for explicit control
- **Soon:** Add pre-commit hook + GitHub Actions
- **Future:** Full Infrastructure as Code with Terraform

This prevents the Telegram token bug from happening again while you plan a more automated solution.

---

## Quick Reference Card

```bash
# Always start here when changing config
cd webhook-service

# Step 1: See what changed
./sync-cloud-config.sh --dry

# Step 2: Deploy to Cloud Run
./sync-cloud-config.sh

# Step 3: Verify it worked
./sync-cloud-config.sh --verify

# Monitor logs
gcloud logs tail --service=tradingview-webhook

# Show help anytime
./sync-cloud-config.sh --help
```

---

**Created:** 2025-11-27  
**Purpose:** Prevent configuration drift between local and Cloud Run  
**Next Review:** When setting up GitHub Actions for CI/CD
