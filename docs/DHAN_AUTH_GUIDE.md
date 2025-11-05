# Dhan API Authentication - Setup Guide

## Overview

This guide implements **automated Dhan API token management** using their v2 OAuth-like authentication flow:

1. **Generate Consent** - Server-to-server call for consentAppId
2. **Headless Login** - Automated Chrome login with credentials + TOTP
3. **Exchange Token** - Convert tokenId to accessToken
4. **Token Rotation** - RenewToken for fresh 24-hour tokens (no re-login)

## Files

- **`scripts/dhan_auth.py`** - Standalone Python script (production-ready)
- **`Untitled-1.ipynb`** - Jupyter notebook with interactive examples
- This guide - Setup and usage instructions

## Installation

### 1. Install Dependencies

```bash
pip install requests flask pyotp selenium webdriver-manager DhanHQ-py
```

### 2. Setup Environment Variables

Create a `.env` file or export to shell:

```bash
export DHAN_CLIENT_ID="your_client_id"           # From Dhan profile
export DHAN_API_KEY="your_app_id"                # App ID from API key tab
export DHAN_API_SECRET="your_app_secret"         # App secret
export DHAN_USER_ID="your_login_user_id"         # Your Dhan login ID
export DHAN_PASSWORD="your_password_or_pin"      # Your Dhan password/PIN
export DHAN_TOTP_SECRET="base32_totp_secret"     # TOTP secret (from 2FA QR)
export DHAN_REDIRECT_URL="http://127.0.0.1:5000/dhan/callback"  # Optional
```

### 3. Get Your Credentials

| Credential | Source | How to Get |
|-----------|--------|-----------|
| **Client ID** | Profile | Login to Dhan → Account → Client ID |
| **API Key & Secret** | Dashboard | Dhan dashboard → "API key" tab → Copy App ID & Secret |
| **User ID** | Account | Your Dhan login user ID |
| **Password** | Account | Your Dhan login password or PIN |
| **TOTP Secret** | 2FA | Generate from QR code (use Google Authenticator or Kite app) |
| **Redirect URL** | Settings | Register in Dhan dashboard (default: http://127.0.0.1:5000/dhan/callback) |

## Usage

### Command-Line Script

```bash
# Full login (3-step OAuth) - first time
python3 scripts/dhan_auth.py login

# Renew token (no re-login needed) - hourly or as needed
python3 scripts/dhan_auth.py renew

# Validate token works
python3 scripts/dhan_auth.py validate

# Show token information
python3 scripts/dhan_auth.py info
```

### Python Notebook

Open `Untitled-1.ipynb` and run cells sequentially:

```python
# Step 1: Configuration (automatic)
# Uses environment variables from CONFIG dict

# Step 2: Generate Consent
consent_id = generate_consent()

# Step 3: Start callback server
# (Automatically starts background Flask server)

# Step 4: Headless login
token_id = headless_login(consent_id)

# Step 5: Exchange for access token
auth_data = full_login_flow()

# Token saved to .dhan_token.json
```

### Python Script

```python
from scripts.dhan_auth import DhanTokenManager, full_login_flow

# Initial login (one-time)
auth_data = full_login_flow()

# Use token manager for production
token_mgr = DhanTokenManager()
token = token_mgr.get_token()  # Auto-renews if expired

# Validate token
token_mgr.validate_token()

# Use in API calls
import requests
headers = {
    "access-token": token,
    "dhanClientId": token_mgr.token_data["dhanClientId"]
}
response = requests.get("https://api.dhan.co/v2/profile", headers=headers)
```

## Architecture

### 3-Step OAuth-Like Flow

```
┌─────────────────────────────────────────┐
│ Step 1: Generate Consent                │
│ POST /app/generate-consent              │
│ Returns: consentAppId                   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 2: Headless Login                  │
│ - Open Dhan login URL                   │
│ - Auto-submit credentials + TOTP        │
│ - Dhan redirects with tokenId           │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Step 3: Exchange Token                  │
│ POST /app/consumeApp-consent            │
│ Input: tokenId                          │
│ Returns: accessToken, expiryTime        │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│ Token Saved & Ready for API Use         │
│ .dhan_token.json                        │
└─────────────────────────────────────────┘
```

### Token Rotation (Optional)

```
┌─────────────────────────────────────┐
│ RenewToken (Hourly/Daily)           │
│ No re-login needed                  │
│ Fresh 24-hour token                 │
└─────────────────────────────────────┘
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /app/generate-consent` | POST | Get consentAppId |
| `/login/consentApp-login` | GET | User login form |
| `/app/consumeApp-consent` | POST | Exchange tokenId for token |
| `/v2/RenewToken` | POST | Rotate token (24h renewal) |
| `/v2/profile` | GET | Validate token |

Base URLs:
- Auth: `https://auth.dhan.co`
- API: `https://api.dhan.co/v2`

## Token Management

### Token File (.dhan_token.json)

```json
{
  "dhanClientId": "your_client_id",
  "accessToken": "your_access_token",
  "expiryTime": "2024-11-05 15:30:00"
}
```

### Auto-Renewal

The `DhanTokenManager` class automatically:
- Loads tokens from disk
- Checks expiration before use
- Renews expired tokens via RenewToken
- Saves new tokens to disk

```python
# Automatically handles renewal
token = token_mgr.get_token()  # Returns valid token
```

## Production Checklist

- ✅ Use environment variables (never hardcode credentials)
- ✅ Store tokens securely (restrict file permissions: `chmod 600`)
- ✅ Validate tokens before trading (`validate_token()`)
- ✅ Rotate tokens hourly/daily (prevent expiry during trading)
- ✅ Monitor expiryTime and renew proactively
- ✅ Use static IP for order placement (SEBI requirement)
- ✅ Implement error handling and retry logic
- ✅ Log token lifecycle events (not the tokens themselves)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Chrome not found | `pip install webdriver-manager` |
| "userId" field not found | Dhan UI changed, update By.NAME selector |
| TOTP invalid | Verify TOTP secret is base32 format |
| Timeout waiting for redirect | Check redirect URL registered in Dhan |
| Token validation failed | Token expired, run `renew` |
| Connection refused (port 5000) | Port already in use, change CONFIG["PORT"] |
| Permission denied (.dhan_token.json) | Run `chmod 600 .dhan_token.json` |

## Security Best Practices

### ✅ Do

- Store credentials in environment variables or secure vault
- Use restricted file permissions on token files (`chmod 600`)
- Rotate tokens regularly (hourly or daily)
- Validate tokens before trading
- Implement request signing (Dhan may require)
- Use HTTPS for all API calls
- Monitor token usage and set alerts

### ❌ Don't

- Hardcode credentials in code or notebooks
- Commit `.env` or `.dhan_token.json` to version control
- Share access tokens across machines
- Log sensitive data (tokens, passwords, credentials)
- Store tokens in plain text on public servers
- Use same token for multiple API consumers
- Ignore token expiry warnings

## Integration with QuantLab

To integrate with QuantLab backtesting:

```python
from scripts.dhan_auth import DhanTokenManager

# Initialize token manager
token_mgr = DhanTokenManager()

# Get valid token
dhan_token = token_mgr.get_token()
dhan_client_id = token_mgr.token_data["dhanClientId"]

# Use in Dhan API calls for fetching minute data
headers = {
    "access-token": dhan_token,
    "dhanClientId": dhan_client_id,
}

# Fetch minute candles
response = requests.get(
    "https://api.dhan.co/v2/historicalCandle",
    params={"securityId": 1023, "interval": "1min"},
    headers=headers
)

# Process for multi-timeframe backtesting
from data.loaders import load_minute_data
from core.multi_timeframe import aggregate_to_timeframe

minute_df = response_to_dataframe(response)  # Parse response
df_75m = aggregate_to_timeframe(minute_df, "75m")
```

## References

- **Dhan Authentication**: https://dhanhq.co/docs/v2/authentication
- **Dhan API**: https://dhanhq.co/docs/v2
- **Selenium WebDriver**: https://www.selenium.dev/documentation/webdriver
- **PyOTP (TOTP)**: https://pyauth.github.io/pyotp

## Support

For issues:
1. Check troubleshooting section above
2. Review Dhan documentation
3. Verify environment variables are set
4. Check file permissions (especially .dhan_token.json)
5. Enable debug logging for more details

---

**Last Updated**: November 5, 2024
**Status**: Production Ready ✅
