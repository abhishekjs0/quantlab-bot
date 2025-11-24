# Dhan API Credentials & Auto Token Setup Guide

> **Complete guide for setting up Dhan API access with automatic token renewal**

**Last Updated**: 2025-11-23 (v2.2.0)  
**Status**: ✅ Production Ready with Auto Token Refresh

---

## Table of Contents

1. [Configuration Values Explained](#configuration-values-explained)
2. [Where to Get Each Credential](#where-to-get-each-credential)
3. [Automatic Token Generation Setup](#automatic-token-generation-setup)
4. [Quick Setup Steps](#quick-setup-steps)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

---

## Configuration Values Explained

Your `.env` file needs these values:

```bash
# Dhan API Credentials (Basic)
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAi...  # Optional: will be auto-generated

# Dhan Auto-Authentication (for automatic token renewal)
DHAN_API_KEY=1cf9de88
DHAN_API_SECRET=457c0207-2d9c-4a94-b44b-ac530c64894d
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=9624973000
DHAN_PASSWORD=your_password_here

# Webhook Configuration
WEBHOOK_SECRET=GTcl4
ENABLE_DHAN=true

# Health Check Configuration
AUTO_HEALTH_CHECK=true
HEALTH_CHECK_INTERVAL=21600  # 6 hours

# Server Configuration
PORT=8080
```

---

## Where to Get Each Credential

### 1. DHAN_CLIENT_ID

**Location:** Dhan Web > Settings > API Management

1. Log in to https://web.dhan.co
2. Navigate to **Settings → API Management**
3. Your Client ID will be displayed (format: 10 digits like `1108351648`)

---

### 2. DHAN_API_KEY & DHAN_API_SECRET

**Location:** Dhan Web > Settings > API Management > API Key Section

1. Log in to https://web.dhan.co
2. Go to **Settings → API Management**
3. Find **"API Key"** section
4. If not generated:
   - Click **"Generate API Key"**
   - Save both **API Key** (like `1cf9de88`) and **API Secret** (UUID format)
5. **Important**: Save API Secret immediately - you can only see it once!

**Format:**
- API Key: Short alphanumeric (e.g., `1cf9de88`)
- API Secret: UUID format (e.g., `457c0207-2d9c-4a94-b44b-ac530c64894d`)

---

### 3. DHAN_TOTP_SECRET (For Auto Token Generation)

**Location:** Dhan Web > Settings > DhanHQ Trading APIs > Setup TOTP

**What is TOTP?**
- Time-based One-Time Password (like Google Authenticator)
- Generates 6-digit codes every 30 seconds
- Used for secure, automated authentication without browser

**How to Get:**

1. Log in to https://web.dhan.co
2. Navigate to **Settings → DhanHQ Trading APIs**
3. Find **"Setup TOTP"** section
4. Click **"Generate TOTP Secret"**
5. **CRITICAL**: Copy and save the secret immediately - you can only see it once!
6. Format: 32-character Base32 string (e.g., `N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM`)

**Important Notes:**
- This is NOT the 6-digit code you see
- This is the SECRET used to generate those 6-digit codes
- Store securely - anyone with this can generate login codes
- Rotate every 6 months for security

---

### 4. DHAN_USER_ID & DHAN_PASSWORD

**User ID:** Your Dhan login ID (10-digit mobile number)  
**Password:** Your Dhan account password

**Security Notes:**
- Use a strong, unique password (not shared with other services)
- Enable 2FA on your Dhan account
- Never commit password to git (keep in `.env` only)

---

### 5. DHAN_ACCESS_TOKEN (Optional - Auto-Generated)

**Token Validity**: ~20 hours (not 23 days)

**Manual Generation (if needed):**
1. Log in to https://web.dhan.co
2. Navigate to **API Management** → **Generate Token**
3. Copy the JWT token (starts with `eyJ0eXAi...`)

**With Auto Token Setup:**
- You DON'T need to manually generate tokens
- System automatically generates new tokens using TOTP
- Tokens refresh automatically before expiry (checked every 6 hours)
- No manual intervention required

---

### 6. Other Configuration

**WEBHOOK_SECRET**: `GTcl4` (validate TradingView alerts)  
**ENABLE_DHAN**: 
- `true` = Live trading (orders will be placed) ⚠️
- `false` = Test mode (logs only, no orders) ✅

**AUTO_HEALTH_CHECK**: `true` (auto-check token every 6 hours)  
**HEALTH_CHECK_INTERVAL**: `21600` (6 hours in seconds)

---

## Automatic Token Generation Setup

### 🎯 Overview

**Problem:** Dhan access tokens expire every ~20 hours, requiring manual regeneration

**Solution:** Automatic token generation using TOTP authentication

**How It Works:**
1. Background task checks token validity every 6 hours
2. If token expired or expiring soon (<1 hour), generates new 20-hour token automatically
3. Uses TOTP (6-digit codes) for headless authentication - no browser needed
4. Zero manual intervention required

### Token Lifecycle

```
Token Generated (20 hours validity)
    ↓
Background health check (every 6 hours)
    ↓
After ~19 hours (<1 hour remaining detected)
    ↓
Service automatically generates new token via TOTP
    ↓
Old token replaced, trading continues uninterrupted
    ↓
Repeat cycle
```

### Authentication Flow

```python
# Step 1: Generate Consent
POST https://auth.dhan.co/app/generate-consent
Headers: app_id (API key), app_secret (API secret)
Returns: consentAppId

# Step 2: Login with TOTP
GET https://auth.dhan.co/login/consentApp-login
Params: consentAppId, userId, password, totp (6-digit code from TOTP_SECRET)
Returns: tokenId

# Step 3: Get Access Token
GET https://auth.dhan.co/app/consumeApp-consent
Params: tokenId
Returns: access_token (valid ~20 hours)
```

---

## Quick Setup Steps

### Step 1: Gather All Credentials

Checklist:
- [ ] Client ID (from API Management)
- [ ] API Key (from API Management → API Key section)
- [ ] API Secret (from API Management → API Key section)
- [ ] TOTP Secret (from DhanHQ Trading APIs → Setup TOTP)
- [ ] User ID (your 10-digit login ID)
- [ ] Password (your Dhan account password)

### Step 2: Update .env File

Edit `webhook-service/.env`:

```bash
# Dhan API Credentials
DHAN_CLIENT_ID=1108351648

# Dhan Auto-Authentication
DHAN_API_KEY=1cf9de88
DHAN_API_SECRET=457c0207-2d9c-4a94-b44b-ac530c64894d
DHAN_TOTP_SECRET=N26PEJEHQRHHFYMZ3H5LY57BF6X3BQBM
DHAN_USER_ID=9624973000
DHAN_PASSWORD=your_password_here

# Optional: Manual token (will be auto-refreshed)
DHAN_ACCESS_TOKEN=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...

# Configuration
WEBHOOK_SECRET=GTcl4
ENABLE_DHAN=true
AUTO_HEALTH_CHECK=true
HEALTH_CHECK_INTERVAL=21600  # 6 hours
CSV_LOG_PATH=/app/webhook_orders.csv
```

**Security**: Never commit `.env` to git! Add to `.gitignore`.

### Step 3: Test Locally (Optional)

```bash
# Navigate to webhook-service folder
cd webhook-service

# Test automatic token generation
python dhan_auth.py

# Expected output:
# ✅ Got valid token: eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...
# Expires: 2025-11-23 17:02:23
```

If successful, your TOTP setup is working!

### Step 4: Deploy to Google Cloud Run

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
./deploy.sh
```

The `deploy.sh` script automatically:
- Reads credentials from `.env`
- Deploys to Google Cloud Run
- Sets all environment variables
- No manual configuration needed!

---

## Verification

### Check Service Health

```bash
# Basic health check
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health

# Response:
{
  "status": "healthy"
}
```

### Check Token Status

```bash
# Detailed readiness check
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ready

# Response:
{
  "ready": true,
  "checks": {
    "dhan_client": "initialized",
    "access_token": "valid"
  }
}
```

✅ **If `"access_token": "valid"`** → Token generation is working!

### Monitor Auto Health Checks

```bash
# View live logs
gcloud beta run services logs tail tradingview-webhook --region=asia-south1

# Look for (every 6 hours):
# ✅ Periodic health check: Dhan token is valid
# ✅ Token valid (18.5 hours remaining)

# When auto-refresh triggers (<1 hour remaining):
# ⚠️  Token expiring soon, generating new token...
# ✅ New token generated, valid for 20 hours
```

### View CSV Logs

```bash
# Check recent orders
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/logs?limit=10 | jq
```

---

## Troubleshooting

### "Token generation failed"

**Symptoms:** Logs show "Failed to generate new token"

**Causes:**
1. Incorrect TOTP secret
2. Wrong user ID or password
3. Dhan account locked (too many failed attempts)
4. API key/secret invalid

**Solutions:**

```bash
# Test TOTP code generation locally
python -c "import pyotp; print(pyotp.TOTP('YOUR_TOTP_SECRET').now())"

# Verify 6-digit code matches Dhan mobile app
# If different → TOTP secret is wrong, regenerate from Dhan web

# Test full authentication flow
cd webhook-service
python dhan_auth.py
```

### "Invalid credentials" or "Authentication failed"

**Cause:** Wrong API key, secret, or password

**Solution:**
1. Verify all credentials in `.env` match Dhan web portal
2. Check for typos (copy-paste recommended)
3. Regenerate API key/secret if needed
4. Ensure password is correct (test manual login)

### "Token expired" errors during orders

**Symptoms:** Orders fail with "Invalid token" error, but auto-refresh didn't trigger

**Cause:** Health check not running or interval too long

**Solution:**

```bash
# Check health check interval (should be 21600)
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/ | jq '.config.health_check_interval'

# Check logs for health check activity
gcloud beta run services logs tail tradingview-webhook | grep "Periodic health check"

# If not running, verify AUTO_HEALTH_CHECK=true in .env and redeploy
```

### TOTP code doesn't work

**Symptoms:** "Invalid TOTP code" in logs

**Causes:**
1. System time out of sync (TOTP is time-based!)
2. Wrong TOTP secret format
3. TOTP secret not Base32 encoded

**Solutions:**

```bash
# Check system time (must be accurate within ±30 seconds)
date

# Test TOTP generation
python -c "import pyotp; print('Code:', pyotp.TOTP('YOUR_SECRET').now())"

# Compare with Dhan mobile app code (should match within 30 seconds)

# If still fails, regenerate TOTP secret from Dhan web portal
```

### "Missing required environment variables"

**Symptoms:** Service starts but logs show missing variables

**Cause:** Environment variables not set in Cloud Run

**Solution:**

```bash
# Verify environment variables
gcloud run services describe tradingview-webhook \
  --region=asia-south1 \
  --format=yaml | grep -A 20 env

# Redeploy with deploy.sh (reads from .env)
cd webhook-service && ./deploy.sh
```

### Health checks too frequent or not frequent enough

**Current Setting:** 21600 seconds (6 hours)  
**Token Validity:** ~20 hours

**To Change:**

Edit `.env`:
```bash
# Check every 4 hours
HEALTH_CHECK_INTERVAL=14400

# Check every 12 hours
HEALTH_CHECK_INTERVAL=43200
```

Then redeploy: `./deploy.sh`

**Recommendation:** Keep at 6 hours (21600) - good balance between coverage and API usage

---

## Security Best Practices

### ✅ DO

- **Use strong, unique password** (not shared with other services)
- **Enable 2FA** on your Dhan account
- **Rotate TOTP secret** every 6 months
- **Monitor logs** weekly for suspicious activity
- **Add `.env` to `.gitignore`** (never commit credentials)
- **Use Google Secret Manager** for production (optional, more secure)

### ❌ DON'T

- **Never commit** `.env` file to git
- **Never log** passwords or TOTP secrets in application logs
- **Never share** TOTP secret with anyone
- **Don't reuse** same password across multiple services
- **Don't expose** API keys in public repositories

### Using Google Secret Manager (Optional - More Secure)

```bash
# Create secrets
gcloud secrets create dhan-api-key --data-file=- <<< "1cf9de88"
gcloud secrets create dhan-api-secret --data-file=- <<< "457c..."
gcloud secrets create dhan-totp-secret --data-file=- <<< "N26P..."
gcloud secrets create dhan-password --data-file=- <<< "your_pass"

# Deploy with secrets
gcloud run deploy tradingview-webhook \
  --source . \
  --region=asia-south1 \
  --update-secrets=DHAN_API_KEY=dhan-api-key:latest \
  --update-secrets=DHAN_API_SECRET=dhan-api-secret:latest \
  --update-secrets=DHAN_TOTP_SECRET=dhan-totp-secret:latest \
  --update-secrets=DHAN_PASSWORD=dhan-password:latest
```

---

## Monitoring & Alerts

### Key Metrics to Track

1. **Token Age**: How old is current token?
2. **Health Check Success**: Are periodic checks running?
3. **Token Refresh Success Rate**: % of successful auto-refreshes
4. **Order Success Rate**: % of orders placed successfully

### Set Up Cloud Monitoring Alert (Optional)

```bash
# Alert if token generation fails
gcloud alpha monitoring policies create \
  --notification-channels=YOUR_CHANNEL_ID \
  --display-name="Dhan Token Refresh Failed" \
  --condition-display-name="Token error in logs" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=300s \
  --condition-filter='resource.type="cloud_run_revision"
    AND severity="ERROR"
    AND textPayload=~"Token generation failed"'
```

---

## Technical Details

### Files Involved

1. **`dhan_auth.py`** (498 lines)
   - `DhanAuth` class with complete OAuth flow
   - `get_valid_token()`: Main method for token management
   - `generate_new_token()`: 3-step TOTP authentication
   - `load_auth_from_env()`: Factory function

2. **`app.py`**
   - Imports `dhan_auth` module
   - Initializes auth on startup
   - Background task `periodic_health_check()` runs every 6 hours
   - Calls `auth.get_valid_token()` before each order

3. **`requirements.txt`**
   - `pyotp==2.9.0` (TOTP code generation)
   - `requests==2.32.3` (OAuth API calls)
   - `dhanhq==2.0.2` (Dhan API client)

### Dependencies

```python
import pyotp  # RFC 6238 TOTP implementation
import requests  # HTTP client for OAuth flow
import json  # Parse API responses
import base64  # Decode JWT tokens
import datetime  # Token expiry calculations
import logging  # Debug logging
```

---

## Completion Checklist

- [ ] TOTP secret generated from Dhan web portal
- [ ] All 6 credentials added to `.env` file
- [ ] Local test passes (optional): `python dhan_auth.py`
- [ ] Deployed to Cloud Run: `./deploy.sh`
- [ ] `/health` endpoint returns healthy
- [ ] `/ready` endpoint shows `"access_token": "valid"`
- [ ] Logs show "✅ Periodic health check" every 6 hours
- [ ] Test webhook places AMO order successfully
- [ ] CSV logs accessible via `/logs` endpoint

**If all checked** → Your automatic token renewal is fully operational! 🎉

---

## Additional Resources

- **Dhan API Documentation**: https://api.dhan.co
- **TOTP Standard (RFC 6238)**: https://tools.ietf.org/html/rfc6238
- **Google Cloud Run Docs**: https://cloud.google.com/run/docs
- **pyotp Library**: https://github.com/pyauth/pyotp
- **OPERATIONS_GUIDE.md**: Complete operations reference

---

*For questions or issues, check logs: `gcloud beta run services logs tail tradingview-webhook --region=asia-south1`*

**Official Dhan API Docs:**
- https://dhanhq.co/docs/v2/
- GitHub: https://github.com/dhan-oss/DhanHQ-py

**Token Generation Guide:**
- https://dhanhq.co/docs/v2/authentication/

## Security Best Practices

1. **Never commit `.env` to git**
   ```bash
   # Already in .gitignore
   ```

2. **Regenerate tokens regularly**
   - Set reminder for every 24 hours
   - Or after each trading session

3. **Use ENABLE_DHAN=false for testing**
   - Test with paper/dummy orders first
   - Only enable live trading when confident

4. **Monitor webhook logs**
   ```bash
   tail -f webhook_server.log
   ```

5. **Use HTTPS in production**
   - Deploy behind nginx/Caddy with SSL
   - Or use ngrok for testing

## Testing Without Dhan

If you want to test webhooks without Dhan credentials:

```bash
# Set in .env
ENABLE_DHAN=false

# Server will accept webhooks but not execute orders
# Perfect for testing TradingView integration
```

## Quick Reference

```bash
# Check if token is valid
curl -X GET "https://api.dhan.co/v2/margincalculator" \
  -H "access-token: YOUR_TOKEN" \
  -H "client-id: YOUR_CLIENT_ID"

# Should return 200 OK if valid
# Should return 401 Unauthorized if expired
```

---

**Your Current Setup:**
- Client ID: ✅ `1108351648`
- Access Token: ✅ Updated (expires in ~20 hours)
- Webhook Host: ✅ `0.0.0.0`
- Webhook Port: ✅ `8000`
- Dhan Execution: ✅ `true` (LIVE TRADING ENABLED)

**Next Steps:**
1. Monitor first few trades carefully
2. Check webhook logs: `tail -f webhook_server.log`
3. Verify orders in Dhan app/web
4. Set up position monitoring
