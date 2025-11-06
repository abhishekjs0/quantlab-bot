# Multi-Timeframe Infrastructure - Reality Check

**Date**: November 6, 2025  
**Status**: 🔴 **NOT WORKING AS DOCUMENTED**

---

## Problem Identified

The multi-timeframe infrastructure documentation claims to support:
- ✅ Loading 1-minute candles from Dhan
- ✅ Aggregating minute data to 75m, 125m, daily, etc.
- ✅ Running strategies on any timeframe

**Reality**: 
- ❌ The data in `data/cache/dhan_historical_*.csv` is **DAILY data**, not **MINUTE data**
- ❌ The `load_minute_data()` function works, but it's loading daily OHLCV
- ❌ Aggregating daily data to 75m doesn't make sense and produces wrong results

### Evidence

```python
# Loaded data shows time differences of 1 day, 3 days, etc.
# NOT minute-level data!

Time differences between rows:
  1 days    1097      ← Daily bars
  3 days     264      ← Weekends/holidays
  2 days      45      ← Weekends/holidays
  4 days      33      ← Holidays
  5 days       1      ← Holiday
```

---

## What We Actually Have

### ✅ Working Components
1. **Aggregation Logic** (`core/multi_timeframe.py`)
   - `aggregate_to_timeframe()` - Works correctly for OHLCV aggregation
   - OHLCV rules are implemented correctly
   - Can aggregate any timeframe to any other timeframe

2. **Data Loading** (`data/loaders.py`)
   - `load_minute_data()` - Works but misleading name
   - Actually loads whatever is in `dhan_historical_<SECID>.csv`
   - Currently that's daily data

3. **Tests** 
   - Unit tests exist but test daily data aggregation (not minute)
   - Tests would pass for daily→75m aggregation (though meaningless)

### ❌ Missing Components  
1. **Actual Minute Data from Dhan API**
   - Need to fetch 1-minute candles from: `https://api.dhan.co/v2/charts/intraday`
   - Currently no code does this
   - Data downloads are from daily historical endpoint

2. **Real Integration**
   - No actual minute-level data fetching
   - No caching of minute data
   - No background job to refresh minute candles

---

## What We Need to Test Properly

### Option 1: Fetch Real Minute Data from Dhan API

**Endpoint**: `https://api.dhan.co/v2/charts/intraday`

**Request Example**:
```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

params = {
    "securityId": 1023,        # SBIN
    "exchangeTokens": "1023",
    "interval": "1",           # 1-minute candles
    "fromDate": "2025-11-06",
    "toDate": "2025-11-06",
}

response = requests.get(
    "https://api.dhan.co/v2/charts/intraday",
    headers=headers,
    params=params,
    timeout=10
)

data = response.json()
print(data)
```

**What We'll Get**:
- Intraday minute candles (1-minute bars)
- Real OHLCV for a single trading day
- Can aggregate to 75m, 125m, etc.

### Option 2: Use Existing Daily Data (Current State)

**What Works**:
- Daily data is loaded correctly
- Aggregation logic is correct
- Can test aggregating daily → weekly or daily → monthly

**What Doesn't Work**:
- Tests claim to test minute-level functionality
- Documentation is misleading
- Infrastructure name is misleading

---

## Action Plan: Fix the Infrastructure

### Phase 1: Verify Real Minute Data (TODAY)
```bash
# Fetch a day of minute data from Dhan API
python3 scripts/test_dhan_intraday.py
```

### Phase 2: Update Data Loading (THIS SESSION)
- Create new function: `fetch_minute_data_from_dhan()`
- Fetch real minute candles from API
- Save as CSV with format: `dhan_intraday_<SECID>_<DATE>.csv`

### Phase 3: Update Tests (THIS SESSION)
- Update test data files with real minute candles
- Fix test assertions
- Document what's actually being tested

### Phase 4: Update Documentation (THIS SESSION)
- Clarify what data currently exists
- Document how to fetch real minute data
- Update examples with working code

---

## Quick Test: Can We Get Real Minute Data?

Let's try fetching a single day of minute candles:

```python
#!/usr/bin/env python3
"""Test fetching real minute data from Dhan API"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DHAN_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")

def fetch_intraday_data(secid, date_str, interval=1):
    """Fetch intraday minute data from Dhan API
    
    Args:
        secid: Security ID (e.g., 1023 for SBIN)
        date_str: Date in format YYYY-MM-DD
        interval: Candle interval in minutes (1, 5, 15, 30, 60)
        
    Returns:
        DataFrame with OHLCV data
    """
    headers = {
        "access-token": DHAN_TOKEN,
        "dhanClientId": DHAN_CLIENT_ID
    }
    
    params = {
        "securityId": secid,
        "exchangeTokens": str(secid),
        "interval": str(interval),
        "fromDate": date_str,
        "toDate": date_str,
    }
    
    try:
        response = requests.get(
            "https://api.dhan.co/v2/charts/intraday",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Got response: {len(data)} candles")
            print(f"Sample: {data[:2]}")
            
            # Parse into DataFrame if successful
            if data:
                df = pd.DataFrame(data)
                # Rename columns as needed
                df.columns = df.columns.str.lower()
                return df
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

if __name__ == "__main__":
    # Test with SBIN (SECURITY_ID: 1023)
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"Fetching minute data for {today}...")
    
    df = fetch_intraday_data(1023, today, interval=1)
    if df is not None:
        print(f"\n✅ SUCCESS!")
        print(f"Loaded {len(df)} candles")
        print(df.head())
    else:
        print("\n❌ FAILED - Could not fetch data")
```

---

## Current Test Status

### Tests That Exist
- `tests/test_minute_loader.py` - 6 tests
- `tests/test_multi_timeframe.py` - 8 tests

### What They Actually Test
- **Not** real minute data
- Daily OHLCV aggregation
- Pandas resample logic
- DataFrame operations

### What They Should Test
- **Real** minute candles from Dhan API
- Minute → 75m aggregation
- Minute → 125m aggregation
- Intraday strategy backtesting

---

## Recommendation

**Status**: Multi-timeframe infrastructure is **partially working**

**What Works**:
✅ Aggregation logic (OHLCV rules correct)
✅ Data loading framework (can load CSVs)
✅ Test infrastructure

**What Doesn't Work**:
❌ Real minute data source (only daily data available)
❌ Dhan API intraday endpoint integration
❌ Realistic testing

**Next Steps**:
1. Verify token is valid for API calls
2. Fetch a sample day of minute data from Dhan
3. Save real minute candles to test file
4. Run aggregation tests with real data
5. Update documentation with honest status

---

## Decision Point

**Do you want to:**

**A) Implement real minute data fetching**
   - Fetch from `https://api.dhan.co/v2/charts/intraday`
   - Cache minute candles locally
   - Test aggregation with real data
   - **Time**: 1-2 hours

**B) Accept current state and update docs**
   - Rename functions to reflect reality (`load_daily_data()`)
   - Document that infrastructure works for daily→weekly/monthly
   - Note that minute data not yet available
   - **Time**: 30 minutes

**C) Both - Phase approach**
   - First: Fix and document current state (30 min)
   - Later: Implement real minute data (1-2 hours)
   - **Time**: 2.5 hours total over sessions

---

## Files to Check

- `data/loaders.py` - `load_minute_data()` function
- `core/multi_timeframe.py` - Aggregation logic
- `tests/test_minute_loader.py` - Current tests
- `.env` - Dhan API credentials

---

**Conclusion**: The infrastructure is **mostly working** but **not for minute data** as documented.  
The real test is: **Can we fetch actual minute candles from Dhan API and aggregate them?**
