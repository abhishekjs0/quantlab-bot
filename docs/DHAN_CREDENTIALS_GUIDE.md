# How to Get Dhan API Credentials

> **Used by:** Both main project (data fetching) and webhook-service (live trading)

---

## Configuration Values Explained

### Main Project (.env in project root)

Your main project `.env` needs these values for **data fetching**:

```bash
# Dhan API Credentials (for data fetching)
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAi...  # Your access token
```

### Webhook Service (webhook-service/.env)

Your webhook service `.env` needs these values for **live trading**:

```bash
# Dhan Broker Credentials
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAi...  # Your access token

# Webhook Server Settings
WEBHOOK_SECRET=GTcl4
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8080
ENABLE_DHAN=false  # Change to 'true' for live trading
```

**Note:** Same client ID and access token used in both locations.

---

## Where to Get Each Value

### 1. DHAN_CLIENT_ID

**Location:** Dhan Web > Profile Section

1. Log in to https://web.dhan.co
2. Click on your profile icon (top right)
3. Go to "Settings" or "Profile"
4. Your Client ID will be displayed (format: 10 digits like `1108351648`)

### 2. DHAN_ACCESS_TOKEN

**Important:** Access tokens expire! You need to regenerate them regularly.

**How to Generate:**

1. Log in to https://web.dhan.co
2. Navigate to **API Management** section:
   - Dashboard → Settings → API Management
   - Or direct link: https://web.dhan.co/api-management

3. Click on **"Generate Token"** or **"Create New Token"**

4. Copy the generated token (long string starting with `eyJ0eXAi...`)
   - Format: JWT token (looks like: `eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9...`)
   - Validity: Usually 7 days
   
5. Paste it in your `.env` file as `DHAN_ACCESS_TOKEN`

**Token Expiry:**
- Tokens typically expire after **7 days**
- When expired, you'll get authentication errors
- Simply regenerate a new token and update `.env`

### 3. WEBHOOK_HOST

**Default:** `0.0.0.0` (listens on all network interfaces)

- `0.0.0.0` = Listen on all interfaces (recommended for remote access)
- `127.0.0.1` = Only local machine can access
- Your specific IP = Only that IP can access

**Use `0.0.0.0` unless you have specific security requirements**

### 4. WEBHOOK_PORT

**Default:** `8000`

The port where your webhook server runs. You can change this if:
- Port 8000 is already in use
- You want to run multiple servers
- Firewall restrictions require a different port

**Common ports:**
- `8000` (default for FastAPI)
- `8080` (alternative HTTP)
- `443` (for HTTPS in production)

### 5. ENABLE_DHAN

**Options:**
- `true` = Actually place orders on Dhan (LIVE TRADING) ⚠️
- `false` = Log orders only, don't execute (TESTING MODE) ✅

**Recommendation:**
- Start with `false` for testing
- Once verified, change to `true` for live trading

## Quick Setup Steps

### Step 1: Get Your Client ID
```bash
# Already have it: 1108351648
```

### Step 2: Generate Fresh Access Token

1. Go to: https://web.dhan.co/api-management
2. Click "Generate Token"
3. Copy the token (starts with `eyJ0eXAi...`)
4. Update `.env`:

```bash
DHAN_ACCESS_TOKEN=<paste_your_token_here>
```

### Step 3: Verify Configuration

```bash
# Test that credentials work
cd /Users/abhishekshah/Desktop/quantlab-workspace
source .venv/bin/activate
python -c "from dhan_broker import DhanBroker; d = DhanBroker(); print('✅ Credentials valid!')"
```

### Step 4: Start Server

```bash
./start_webhook.sh
```

## Troubleshooting

### Authentication Error: "Invalid credentials"

**Cause:** Access token expired or invalid

**Solution:**
1. Go to Dhan API Management
2. Generate new token
3. Update `.env` with new `DHAN_ACCESS_TOKEN`
4. Restart webhook server

### Error: "Failed to fetch security list"

**Cause:** Network issue or API rate limiting

**Solution:**
- Check internet connection
- Wait 1-2 minutes and try again
- Verify Dhan API is not down: https://status.dhan.co

### Order Failed: "Security ID not found"

**Cause:** Symbol not found in exchange

**Solution:**
- Verify symbol is correct (e.g., `RELIANCE` not `RELIANCE-EQ`)
- Check exchange is correct (NSE for most stocks)
- Symbol must match exact trading symbol on Dhan

## API Documentation

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
   - Set reminder for every 7 days
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
- Access Token: ✅ Updated (expires in ~7 days)
- Webhook Host: ✅ `0.0.0.0`
- Webhook Port: ✅ `8000`
- Dhan Execution: ✅ `true` (LIVE TRADING ENABLED)

**Next Steps:**
1. Monitor first few trades carefully
2. Check webhook logs: `tail -f webhook_server.log`
3. Verify orders in Dhan app/web
4. Set up position monitoring
