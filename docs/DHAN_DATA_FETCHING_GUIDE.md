# Dhan Data Fetching Guide

## Overview
This guide documents the correct process for fetching data from Dhan API, including the common issues and their solutions.

## Common Issues and Solutions

### 1. Authentication Problems
**Problem**: HTTP 401 errors with "Invalid_Authentication" or "Client ID or user generated access token is invalid or expired"

**Solution**:
- Update the `.env` file with correct credentials
- Ensure `DHAN_CLIENT_ID` and `DHAN_ACCESS_TOKEN` match
- The `.env` file overrides environment variables, so updating it is essential

### 2. Security ID Mapping Issues
**Problem**: HTTP 400 errors with "Missing required fields" when fetching ETFs/indices

**Solution**:
- Use the correct security ID for the exchange (NSE vs BSE)
- For NIFTYBEES: Use NSE ID `10576` instead of BSE ID `590103`
- Check the `api-scrip-master-detailed.csv` for correct mappings

### 3. Instrument Type Configuration
**Problem**: API rejecting requests due to incorrect instrument parameters

**Solution**:
```json
{
    "securityId": 10576,
    "exchangeSegment": "NSE_EQ",  // For NSE equity
    "instrument": "EQUITY",       // For ETFs use EQUITY, not ETF
    "expiryCode": 0,             // Always 0 for equity
    "fromDate": "2020-01-01",
    "toDate": "2025-10-24"
}
```

## Step-by-Step Process

### Step 1: Update Credentials
```bash
# Edit .env file in project root
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=<your_current_token>
```

### Step 2: Find Security ID
```bash
# Search for symbol in scrip master
grep -i "NIFTYBEES" data/api-scrip-master-detailed.csv
```

Output should show:
```
NIFTYBEES,...,590103.0,NEW,NIFTYBEES,BSE,E,EQUITY,B,1.0
NIFTYBEES,...,10576.0,NEW,NIFTYBEES,NSE,E,EQUITY,EQ,1.0
```

### Step 3: Use Correct Exchange
- **NSE**: Generally more reliable for ETFs and indices
- **BSE**: May have different data availability
- **Preference**: Use NSE ID when available (10576 for NIFTYBEES)

### Step 4: Fetch Data
```bash
# Using the official fetch script
cd /Users/abhishekshah/Desktop/quantlab
.venv/bin/python scripts/fetch_data.py NIFTYBEES --force-refresh
```

### Step 5: Verify Cache Creation
```bash
# Check if files were created
ls -la data/cache/dhan_historical_10576*
```

Expected files:
- `dhan_historical_10576.csv`
- `dhan_historical_10576.csv_metadata.json`

## Direct API Call Method

If the standard fetch script fails, use direct API calls:

```python
import requests
import pandas as pd

headers = {
    "access-token": "your_token_here",
    "client-id": "1108351648",
    "Content-Type": "application/json",
}

payload = {
    "securityId": 10576,
    "exchangeSegment": "NSE_EQ",
    "instrument": "EQUITY",
    "expiryCode": 0,
    "fromDate": "2020-01-01",
    "toDate": "2025-10-24",
}

response = requests.post(
    "https://api.dhan.co/v2/charts/historical",
    headers=headers,
    json=payload,
    timeout=30
)

data = response.json()
df = pd.DataFrame({
    "date": pd.to_datetime(data["timestamp"], unit="s").strftime("%Y-%m-%d"),
    "open": data["open"],
    "high": data["high"],
    "low": data["low"],
    "close": data["close"],
    "volume": data["volume"],
})
```

## Key Lessons Learned

1. **Always check .env file first** - Environment variables may be overridden
2. **Use NSE security IDs for better reliability** - Especially for ETFs and indices
3. **Test API connection before bulk fetching** - Verify credentials work
4. **Check response structure** - Ensure all required fields are present
5. **Use proper date formatting** - Remove `.dt` when working with DatetimeIndex.strftime()

## Troubleshooting Checklist

- [ ] Credentials updated in `.env` file
- [ ] Correct security ID identified (NSE preferred)
- [ ] Exchange segment matches security ID
- [ ] Instrument type is correct (EQUITY for ETFs)
- [ ] Date range is reasonable (not too far back)
- [ ] Network connectivity is stable
- [ ] Cache directory exists and is writable

## Success Indicators

When successful, you should see:
```
✅ Response status: 200
✅ Response keys: ['open', 'high', 'low', 'close', 'volume', 'timestamp']
✅ Saved NIFTYBEES data: 1444 rows
📊 Date range: 2019-12-31 to 2025-10-22
```

## Common Symbols and Their NSE Security IDs

- NIFTYBEES (NIFTY 50 ETF): 10576
- RELIANCE: 2885
- HDFCBANK: 1333
- TCS: 11536
- ICICIBANK: 4963
- INFY: 1594

---

**Last Updated**: October 24, 2025
**Tested With**: Dhan API v2, QuantLab v2.2
