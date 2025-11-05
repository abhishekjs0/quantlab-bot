# Dhan API Integration Guide

## Overview

QuantLab integrates with Dhan API for live market data and minute-level candles for intraday trading. This guide covers setup, authentication, and usage.

## Files

- **`dhan_simple_auth.py`** - Initial authentication flow with OAuth
- **`dhan_token_scheduler.py`** - Background scheduler for automatic token refresh (9 AM & 4 PM daily)
- **`dhan_data_fetcher.py`** - Live market data and historical candles fetcher

## Initial Setup

### 1. Environment Configuration

Add to `.env`:

```
DHAN_CLIENT_ID=<your_client_id>
DHAN_API_KEY=<your_api_key>
DHAN_API_SECRET=<your_api_secret>
DHAN_USER_ID=<your_mobile_number>
DHAN_PASSWORD=<your_password>
DHAN_TOTP_SECRET=<your_totp_secret_key>
DHAN_ACCESS_TOKEN=<will_be_filled_by_auth>
```

### 2. Initial Authentication

Run the authentication script once to get the access token:

```bash
python scripts/dhan_simple_auth.py
```

**What it does:**
1. Generates OAuth consent
2. Opens your browser to the login page
3. Automatically fills in mobile number, password, and TOTP
4. Captures the access token and saves it to `.env`

**Note:** The script automatically enters:
- **Mobile number** (from `DHAN_USER_ID`)
- **Password** (from `DHAN_PASSWORD`)
- **OTP** (auto-generated from `DHAN_TOTP_SECRET`)

### 3. Token Refresh Schedule

Start the background token refresher:

```bash
python scripts/dhan_token_scheduler.py
```

**Schedule:**
- **9:00 AM** - Daily token refresh
- **4:00 PM** - Daily token refresh

The script automatically repeats the authentication flow to get a fresh token before expiry.

## Data Fetching

### Live Market Quotes

```python
from scripts.dhan_data_fetcher import fetch_live_quote

# Get live quote for RELIANCE (security ID 100)
quote = fetch_live_quote("NSE_EQ|100")
print(quote)
```

### Historical Candles

```python
from scripts.dhan_data_fetcher import fetch_historical_candles

# Fetch 1-minute candles for last day
candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=1, days_back=1)

# Fetch 5-minute candles for last 5 days
candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=5, days_back=5)
```

### Test Integration

```bash
python scripts/dhan_data_fetcher.py
```

## Troubleshooting

### Token Expired Error

**Problem:** `401 Client Error: Unauthorized`

**Solution:** Run authentication again or ensure scheduler is running

```bash
python scripts/dhan_simple_auth.py
```

### Form Not Filling

**Problem:** Login form not being filled automatically

**Solution:** Ensure browser window is focused and not minimized during authentication

### No Data Returned

**Problem:** Empty response from Dhan API

**Solutions:**
1. Verify security ID is correct (use `fetch_data.py` for mapping)
2. Check if date range is valid
3. Ensure token is fresh (run auth again if expired)

## API Reference

### Common Security IDs

| Symbol | Security ID |
|--------|------------|
| RELIANCE | 100 |
| INFY | 10188 |
| TCS | 1023 |
| HDFCBANK | 10397 |

For complete mapping, see `data/api-scrip-master-detailed.csv`

### Exchange Token Format

Use format: `NSE_EQ|<SECURITY_ID>`

Examples:
- `NSE_EQ|100` - RELIANCE
- `NSE_EQ|10188` - INFY
- `NSE_EQ|1023` - TCS

### Candle Intervals

Supported intervals (in minutes):
- `1` - 1-minute candles
- `5` - 5-minute candles
- `15` - 15-minute candles
- `30` - 30-minute candles
- `60` - 1-hour candles

## Integration with QuantLab

The data fetcher integrates seamlessly with QuantLab's strategy engine:

```python
from scripts.dhan_data_fetcher import fetch_historical_candles
from core.engine import BacktestEngine

# Fetch minute candles for intraday strategy
candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=1, days_back=5)

# Use with your strategy
engine = BacktestEngine(...)
results = engine.run(candles)
```

## Rate Limits

Dhan API rate limits:
- **25 requests/second**
- **250 requests/minute**
- **1000 requests/hour**
- **7000 requests/day**

The fetcher respects these limits automatically.

## Support

For issues with Dhan API, refer to official docs: https://dhanhq.co/docs/v2/

For QuantLab integration issues, check core module documentation.
