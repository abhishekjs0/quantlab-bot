# Dhan API Authentication Setup Guide

## Overview

This is a simplified, Zerodha-style authentication script for Dhan API using their 3-step OAuth-like flow with automatic TOTP support and callback server.

## File Structure

```
scripts/dhan_auth.py          # Main authentication script
.env                          # Configuration file (credentials)
.dhan_token.json              # Generated token file (after login)
```

## Configuration (.env)

The `.env` file contains your credentials. Fill in the following:

```properties
# Required - Your Dhan credentials
DHAN_CLIENT_ID=1108351648           # From Dhan dashboard
DHAN_API_KEY=1cf9de88               # From API key tab (app_id)
DHAN_API_SECRET=457c0207-...        # From API key tab (app_secret)
DHAN_USER_ID=                        # Your Dhan login user ID
DHAN_PASSWORD=                       # Your Dhan password or PIN
DHAN_TOTP_SECRET=N26PEJEHQ...       # Base32 TOTP secret (from 2FA QR code)
```

### How to Get Each Value

1. **DHAN_CLIENT_ID**: Dashboard → Profile → Client ID
2. **DHAN_API_KEY & DHAN_API_SECRET**: Dashboard → API Key Settings → Copy "app_id" and "app_secret"
3. **DHAN_USER_ID**: Your Dhan trading username
4. **DHAN_PASSWORD**: Your Dhan login password
5. **DHAN_TOTP_SECRET**: During 2FA setup, save the "backup code" (base32 format)

## How It Works

### 3-Step OAuth Flow

```
Step 1: Generate Consent
  └─ Server-to-server call to auth.dhan.co
  └─ Returns: consentAppId

Step 2: Start Callback Server
  └─ Local HTTP server listening on port 8000
  └─ Waits for redirect from Dhan

Step 3: Open Browser & Login
  └─ Opens Dhan login page in your default browser
  └─ You enter: User ID → Password → TOTP code
  └─ Dhan redirects with tokenId to http://127.0.0.1:8000/callback

Step 4: Exchange Token
  └─ Server-to-server call exchanges tokenId for accessToken
  └─ Returns: accessToken (valid for 24 hours)
  └─ Saved to: .dhan_token.json

Step 5: Validate Token
  └─ Tests token with /v2/profile endpoint
  └─ Confirms everything is working
```

## Usage

### Basic Login

```bash
python3 scripts/dhan_auth.py
```

This will:
1. Start a callback server on port 8000
2. Open your browser to Dhan login page
3. Show your TOTP code
4. Wait for you to complete login
5. Exchange token and save to `.dhan_token.json`
6. Validate token works

### Output Example

```
======================================================================
DHAN API: COMPLETE AUTOMATED LOGIN FLOW
======================================================================

📋 Checking configuration...
✅ DHAN_CLIENT_ID: **...
✅ DHAN_API_KEY: ****
✅ DHAN_API_SECRET: ******************
✅ DHAN_USER_ID: ****
✅ DHAN_PASSWORD: ****
✅ DHAN_TOTP_SECRET: ****************

🔄 STEP 1: Generating consent...
✅ Consent generated: 4a5c8f2b0c...

🔄 STEP 2: Starting callback server on http://127.0.0.1:8000
   Waiting for redirect from Dhan login page...

🔄 STEP 3: Opening Dhan login page in browser...
   URL: https://auth.dhan.co/login/consentApp-login?consentAppId=...

   📱 TOTP code: 123456

   ⏳ Please complete login in your browser...
   ⏳ Waiting up to 120s for tokenId...
✅ Login successful!

🔄 STEP 4: Exchanging tokenId for accessToken...
✅ Access token obtained!
   Dhan Client ID: 1108351648
   Access Token: eyJ0eXAiOiJKV1QiLCJhbGc...
   Expiry Time: 2024-11-06 15:30:00

🔍 Validating token...
✅ Token is valid!

======================================================================
✅ LOGIN SUCCESSFUL!
======================================================================
Access Token: eyJ0eXAiOiJKV1QiLCJhbGc...
Dhan Client ID: 1108351648
Expiry Time: 2024-11-06 15:30:00
Token saved to: .dhan_token.json
======================================================================
```

## Using the Token

Once authenticated, read the token file:

```python
import json

with open(".dhan_token.json") as f:
    token_data = json.load(f)

access_token = token_data["accessToken"]
dhan_client_id = token_data["dhanClientId"]

# Use in API calls
headers = {
    "access-token": access_token,
    "dhanClientId": dhan_client_id,
}

# Example: Fetch historical data
response = requests.get(
    "https://api.dhan.co/v2/historicalCandle",
    params={"securityId": 1023, "interval": "1min", "fromDate": "2024-11-01", "toDate": "2024-11-05"},
    headers=headers
)
```

## Token Renewal (Optional)

The token lasts 24 hours. To renew without re-login, use the `renew_token_api()` function in the script:

```python
from scripts.dhan_auth import renew_token_api
import json

with open(".dhan_token.json") as f:
    token_data = json.load(f)

new_data = renew_token_api(
    token_data["accessToken"],
    token_data["dhanClientId"]
)

# Save new token
with open(".dhan_token.json", "w") as f:
    json.dump(new_data, f, indent=2)
```

Or manually call the endpoint:

```python
import requests
import json

with open(".dhan_token.json") as f:
    token_data = json.load(f)

response = requests.post(
    "https://api.dhan.co/v2/RenewToken",
    headers={
        "access-token": token_data["accessToken"],
        "dhanClientId": token_data["dhanClientId"],
    }
)

new_data = response.json()
with open(".dhan_token.json", "w") as f:
    json.dump(new_data, f, indent=2)
```

## Troubleshooting

### Port 8000 Already in Use

```bash
# Find what's using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>
```

### Browser Doesn't Open

The login URL is printed. Open it manually in your browser.

### TOTP Code Not Accepting

1. Verify `DHAN_TOTP_SECRET` is correct (base32 format)
2. Sync your system clock: `ntpdate -s time.nist.gov`
3. Re-run the script to get fresh TOTP code

### Token Validation Fails

- Token may have expired (24-hour validity)
- API key/secret may be wrong
- Client ID may not match your account

### Missing Environment Variables

Ensure all required fields in `.env` are filled:

```bash
cat .env | grep -E "DHAN_|TOTP"
```

## Dependencies

```
pyotp            # TOTP code generation
requests         # HTTP requests
python-dotenv    # Environment variable loading
```

Install with:
```bash
pip install pyotp requests python-dotenv
```

## Security Notes

1. **Never commit `.env` to git** - Add to `.gitignore`:
   ```
   .env
   .dhan_token.json
   ```

2. **Token file permissions** - Ensure `.dhan_token.json` is readable only by you:
   ```bash
   chmod 600 .dhan_token.json
   ```

3. **Rotate credentials regularly** - If compromised, change password in Dhan dashboard

4. **Use environment variables in production** - Don't use `.env` files in production; use a secrets manager

## API Documentation

- **Dhan API v2**: https://dhanhq.co/docs/v2
- **Authentication**: https://dhanhq.co/docs/v2/authentication
- **Historical Data**: https://dhanhq.co/docs/v2/historical-candle

## Integration with QuantLab

```python
from scripts.dhan_auth import renew_token_api
from data.loaders import load_minute_data
from core.multi_timeframe import aggregate_to_timeframe
import json
import requests

# Load token
with open(".dhan_token.json") as f:
    token_data = json.load(f)

access_token = token_data["accessToken"]

# Load minute data from Dhan
minute_df = load_minute_data(1023, token=access_token)

# Aggregate to 75-minute candles
df_75m = aggregate_to_timeframe(minute_df, "75m")

# Run backtests...
```

---

**Last Updated**: November 5, 2024
**Status**: ✅ Production Ready
