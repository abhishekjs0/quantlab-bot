# Groww Cloud Trading Bot Guide

Complete guide for deploying the **Bullish Candlestick Patterns Strategy** on Groww Cloud.

## 📋 Strategy Overview

| Parameter | Value |
|-----------|-------|
| **Strategy Name** | Bullish Candlestick Patterns (C2C) |
| **Holding Period** | 1 day (Close-to-Close) |
| **Entry Time** | 3:25 PM (before market close) |
| **Exit Time** | 3:25 PM next day |
| **Expected Return** | ~3.5% per trade (strong patterns only) |
| **Win Rate** | ~56% |
| **Total Trades (10Y backtest)** | ~800 |

### Entry Conditions
1. **Bullish Pattern** - Today's candle shows a strong bullish pattern
2. **Stock < ALL EMAs** - Stock price below EMA 20, 50, and 200 (oversold)
3. **NIFTY > ALL EMAs** - NIFTY index above all EMAs (bullish market)

### Backtest Results (Verified Dec 2024)

| Configuration | Trades | Avg Return | Win Rate |
|--------------|--------|------------|----------|
| **Strong patterns only** | **793** | **3.50%** | **55.9%** |
| All 8 patterns | 1,539 | 2.40% | 54.5% |

**Strong patterns** exclude DOJI (1.27% avg) and INVERTED_HAMMER (1.10% avg).

### Pattern Performance

| Pattern | Trades | Avg Return |
|---------|--------|------------|
| MARUBOZU | 37 | 3.63% |
| BELT_HOLD | 399 | 3.61% |
| LONG_LINE | 301 | 3.55% |
| HAMMER | 55 | 2.41% |
| DOJI | 543 | 1.27% *(excluded)* |
| INV_HAMMER | 203 | 1.10% *(excluded)* |

### Strong Patterns Detected
- HAMMER (lower shadow ≥ 2x body, bullish close)
- DRAGONFLY_DOJI (tiny body, long lower shadow)
- BULLISH_MARUBOZU (body > 90% of range)
- BELT_HOLD (open at low, body > 60% range)
- LONG_LINE (bullish body > 70% range)
- TAKURI (lower shadow ≥ 3x body)

---

## 🚀 Groww Cloud Setup

### Step 1: Access Groww Cloud
1. Go to [Groww Trade API](https://groww.in/trade-api)
2. Login with your Groww account
3. Navigate to **Cloud Bots** section

### Step 2: Create New Bot
1. Click **"Create New Bot"**
2. Name: `BullishPatterns_C2C`
3. Description: `Bullish candlestick pattern strategy - Close to Close`

### Step 3: Configure Scheduling
```
Schedule Type: Daily
Run Time: 3:25 PM IST
Days: Monday to Friday (Market Days)
```

### Step 4: Requirements Tab
Add these packages with versions:
```
growwapi>=0.0.8
pyotp>=2.9.0
numpy>=1.24.0
```

> **Why NumPy and not TA-Lib?**  
> TA-Lib is a C library requiring compilation - it's NOT available on Groww Cloud.  
> NumPy is pure Python and universally available. Our EMA calculation is mathematically identical to TA-Lib.

### Step 5: Environment Variables (Recommended)
Instead of hardcoding credentials in the script, use environment variables:

```
GROWW_TOTP_TOKEN = eyJraWQiOiJaTUtjVXciLCJhbGciOiJFUzI1NiJ9...
GROWW_TOTP_SECRET = LCJJGPXB7WDUKW5QDSU5BGPLBZ5FT4AA
```

The script automatically loads from environment variables with fallback to hardcoded values.

For local development, create a `.env.groww` file (already gitignored):
```bash
# .env.groww - DO NOT COMMIT!
GROWW_TOTP_TOKEN=eyJraWQi...
GROWW_TOTP_SECRET=LCJJGPXB7WDUKW5QDSU5BGPLBZ5FT4AA
```

### Step 6: Script Tab
Copy the entire content from [bullish_patterns_groww.py](../scripts/bullish_patterns_groww.py)

### Step 7: Authentication (TOTP Flow - No Daily Expiry!)
The script uses **TOTP authentication** which does NOT expire daily:
```python
# These are already configured in the script:
TOTP_TOKEN = "eyJraWQi..."  # Your TOTP token (never expires)
TOTP_SECRET = "LCJJGPXB7WDUKW5QDSU5BGPLBZ5FT4AA"  # For generating 6-digit codes

# The script auto-generates TOTP code using pyotp:
totp_generator = pyotp.TOTP(TOTP_SECRET)
totp_code = totp_generator.now()  # 6-digit code

# Then authenticates automatically:
access_token = GrowwAPI.get_access_token(api_key=TOTP_TOKEN, totp=totp_code)
```

**Why TOTP is better than API Key/Secret:**
- API Key/Secret: Expires daily at 6:00 AM, requires manual approval
- TOTP Flow: Never expires, fully automated!

### Step 8: Deploy & Activate
1. Click **"Deploy Bot"**
2. Toggle **"Active"** to enable
3. Monitor first few runs in **Logs** section

---

## 💰 Capital & Position Sizing

| Parameter | Value |
|-----------|-------|
| **Initial Capital** | ₹1,00,000 |
| **Position Size** | 5% of capital (₹5,000 per trade) |
| **Max Positions** | Unlimited |

### How Position Size Works
```python
# For a stock priced at Rs. 500:
Position Amount = Rs. 1,00,000 × 5% = Rs. 5,000
Quantity = Rs. 5,000 / Rs. 500 = 10 shares

# For a stock priced at Rs. 2,500:
Quantity = Rs. 5,000 / Rs. 2,500 = 2 shares
```

---

## 📊 Daily Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    3:25 PM - Bot Starts                      │
├─────────────────────────────────────────────────────────────┤
│  1. Initialize Groww API                                     │
│  2. Fetch NIFTY data + today's OHLC                         │
│  3. Calculate NIFTY EMAs (20/50/200)                        │
│  4. Check: Is NIFTY > ALL EMAs?                             │
│     ├─ NO  → Exit (no trades today)                         │
│     └─ YES → Continue scanning                              │
├─────────────────────────────────────────────────────────────┤
│  5. EXIT: Sell all holdings from yesterday                  │
├─────────────────────────────────────────────────────────────┤
│  6. SCAN: Loop through 103 stocks                           │
│     ├─ Fetch historical data                                │
│     ├─ Get today's OHLC (as of 3:25 PM)                    │
│     ├─ Detect bullish candlestick pattern                  │
│     ├─ Calculate EMAs                                       │
│     └─ Check: Pattern + Stock < ALL EMAs?                  │
├─────────────────────────────────────────────────────────────┤
│  7. ENTRY: Place BUY orders for all signals                 │
│     └─ Quantity = 5% of capital / LTP                       │
├─────────────────────────────────────────────────────────────┤
│  8. Summary: Print results                                   │
│                                                              │
│                    3:29 PM - Bot Ends                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📈 Stock Universe (103 Stocks)

The strategy scans these stocks daily:

**Large Cap:**
RELIANCE, ICICIBANK, SBIN, BHARTIARTL, BAJFINANCE, LT, HCLTECH, KOTAKBANK, TITAN, MARUTI, HINDUNILVR, SUNPHARMA, M&M, NTPC, ONGC, POWERGRID, DRREDDY, WIPRO, TECHM, ASIANPAINT

**Mid Cap:**
TATAPOWER, ADANIENT, ADANIPORTS, COALINDIA, GRASIM, JSWSTEEL, HINDALCO, TATASTEEL, BPCL, CIPLA, APOLLOHOSP, GAIL, IOC, EICHERMOT, INDIGO, DLF, HAL, BEL, IRCTC, ZOMATO

**Banks & Finance:**
AXISBANK, HDFCLIFE, BAJAJFINSV, SBILIFE, HDFCAMC, ICICIPRULI, PNB, CANBK, BANKBARODA, UNIONBANK, PFC, RECLTD, CHOLAFIN, MUTHOOTFIN, JIOFIN, POLICYBZR

**Others:**
ULTRACEMCO, TATACONSUM, DABUR, GODREJCP, COLPAL, MARICO, VBL, SIEMENS, ABB, HAVELLS, BHEL, VOLTAS, MOTHERSON, LUPIN, TORNTPHARM, ZYDUSLIFE, MAXHEALTH, DIVISLAB, PIIND, BOSCHLTD, PERSISTENT, TRENT, PATANJALI, and more...

---

## 🔧 API Rate Limits

Groww API has rate limits to prevent abuse:

| Endpoint | Rate Limit |
|----------|------------|
| Orders | 15/sec, 250/min |
| Live Data | 10/sec, 300/min |
| Historical Data | 5/sec, 150/min |

The script includes `time.sleep()` calls to respect these limits.

---

## 📝 Logs & Monitoring

### Expected Log Output
```
🚀 Initializing Groww API...
✅ Groww API Ready

📊 Checking NIFTY trend...
📈 NIFTY Today: O=24150.00 H=24285.00 L=24100.00 C=24230.00
   NIFTY EMA20: 24050.00
   NIFTY EMA50: 23800.00
   NIFTY EMA200: 22500.00

✅ NIFTY is ABOVE all EMAs - Market is bullish. Scanning stocks...

📤 Checking for positions to exit...
   Found 3 position(s) to exit
   Selling 10 shares of SBIN...
   ✅ SELL order placed: SBIN x10. Order ID: GMK39038RDT490CCVRO

🔍 Scanning 103 stocks for bullish patterns...
   Scanned 20/103 stocks...
   🎯 SIGNAL: TATASTEEL - HAMMER @ Rs.142.50
   Scanned 40/103 stocks...
   🎯 SIGNAL: HINDALCO - DRAGONFLY_DOJI @ Rs.625.00
   ...

📊 Scan complete. Found 5 signals.

📥 Placing BUY orders for 5 signals...
   Position size: 5% of Rs.1,00,000 = Rs.5,000 per trade
   Buying 35 shares of TATASTEEL @ Rs.142.50 (Rs.4,988)...
   ✅ BUY order placed: TATASTEEL x35 (HAMMER). Order ID: GMK39038RDT490CCVR1

============================================================
📊 TRADING SESSION SUMMARY
============================================================
   Date/Time: 2024-12-26 15:25:30
   NIFTY Status: ABOVE all EMAs ✅
   Stocks Scanned: 103
   Signals Found: 5
   Orders Placed: 5
============================================================
✅ Strategy execution complete!
```

### No Signals Day
```
🔴 NIFTY is NOT above all EMAs. No signals today.
   Strategy requires bullish market condition (NIFTY > ALL EMAs)
```

---

## ⚠️ Important Notes

### 1. TOTP Setup Required
You mentioned TOTP is pending. Complete this before deploying:
1. Open Groww App
2. Settings → Security → Enable TOTP
3. Scan QR code with authenticator app

### 2. First Trade Verification
- Run the bot manually first
- Verify orders appear correctly in Groww app
- Check position sizes are correct

### 3. Market Holidays
- The bot will fail on market holidays
- Groww Cloud handles holiday detection automatically

### 4. Capital Tracking
- The script uses fixed `INITIAL_CAPITAL = 100000`
- For dynamic capital tracking, modify to fetch available funds:
```python
# Get available margin
margin = groww.get_margin()
available_capital = margin.get("available_margin", INITIAL_CAPITAL)
```

### 5. Slippage & Charges
- Expected return (4.41%) includes 0.37% charges
- Market orders may have slight slippage at 3:25 PM
- High liquidity stocks should have minimal slippage

---

## 🛠️ Troubleshooting

### Error: "Authentication Failed"
- Verify API key and secret are correct
- Check if TOTP is enabled
- Regenerate API keys if needed

### Error: "Insufficient Funds"
- Check available margin in Groww
- Reduce POSITION_SIZE_PCT if needed

### Error: "Rate Limit Exceeded"
- Increase `time.sleep()` values
- Reduce number of stocks scanned

### No Orders Placed
- Check if NIFTY is above all EMAs (market must be bullish)
- Verify stock symbols are correct
- Check Groww API logs for errors

---

## 📞 Support

- **Groww API Docs:** https://groww.in/trade-api/docs/python-sdk
- **API Support:** trade-api@groww.in
- **Strategy Issues:** Check this workspace's logs and reports

---

## 📄 Files Reference

| File | Purpose |
|------|---------|
| [bullish_patterns_groww.py](../scripts/bullish_patterns_groww.py) | Main strategy for Groww Cloud |
| [overnight_gap_strategy.py](../scripts/overnight_gap_strategy.py) | Original local strategy (with TA-Lib) |
| [basket_main.txt](../data/baskets/basket_main.txt) | Stock universe (103 symbols) |

---

*Last Updated: December 26, 2024*

## Intraday Marubozu Strategy

**Current Configuration (2025-01-09)**:
- Body ≥ 5% of close price
- Body ≥ 80% of candle range  
- No EMA filter (immediate entries)
- 1-day hold period
- 0.11% roundtrip transaction cost

**Backtest Performance**:
- 9/9 years positive (2016-2024)
- 1,130 trades, +0.64% avg return
- 52.7% win rate

**Key Settings in marubozu_intraday.py**:
- `MIN_BODY_PERCENT = 0.05` (5% body size)
- `MIN_BODY_RANGE = 0.80` (80% of candle is body)
- `USE_EMA_FILTER = False`
- `MAX_HOLD_DAYS = 1` (intraday exit)
- `LOOKBACK_DAYS = 180` (Groww API limit)

---

## 📊 Groww API - Historical Data Fetcher

### Overview

The Groww weekly data fetcher (`scripts/fetch_groww_weekly_data.py`) automatically downloads and caches historical OHLCV data for backtesting. It supports all NSE-listed stocks with data back to 2016.

### ✅ Authentication (Checksum-Based Flow)

**Problem Solved (Dec 30, 2025):**
- Previous token had only `auth-totp` role (login-only)
- Couldn't access historical data endpoints (403 Forbidden)

**Solution Implemented:**
The fetcher now generates fresh access tokens dynamically using checksum-based authentication:

```
1. Generate SHA256 checksum = hash(API_SECRET + current_timestamp)
2. POST to /v1/token/api/access with checksum
3. Receive access token with back_test role (13-hour validity)
4. Fetch historical data using the new token
```

**Required Credentials in `.env`:**
```env
GROWW_API_KEY=<your-api-key>
GROWW_API_SECRET=<your-api-secret>
```

Get these from: https://groww.in/trade-api/api-keys

### 📥 Fetching Weekly Data

**Single Symbol:**
```bash
python3 scripts/fetch_groww_weekly_data.py --symbols RELIANCE
```

**Multiple Symbols:**
```bash
python3 scripts/fetch_groww_weekly_data.py --symbols RELIANCE,INFY,TCS
```

**Entire Basket:**
```bash
python3 scripts/fetch_groww_weekly_data.py --basket large
```

**All Baskets:**
```bash
python3 scripts/fetch_groww_weekly_data.py --all-baskets
```

**Available Baskets:**
- `main`: 563 stocks (primary portfolio)
- `large`: 103 large-cap stocks
- `mid`: Mid-cap stocks
- `small`: Small-cap stocks
- `test`: Test symbols (RELIANCE, INFY, KOTAKBANK, LT, ICICIBANK)
- `debug`: Debug symbols
- `midcap_highbeta`, `largecap_highbeta`, `smallcap_highbeta`: High beta variants
- `largecap_lowbeta`, `midcap_lowbeta`, `smallcap_lowbeta`: Low beta variants

### 📁 Data Organization

Weekly data is organized in cache structure:
```
data/cache/groww/weekly/
├── groww_2885_RELIANCE_1w.csv
├── groww_1594_INFY_1w.csv
├── groww_1922_KOTAKBANK_1w.csv
└── ... (one file per symbol)

data/cache/groww/daily/
└── (for future daily data fetching)

data/cache/dhan/daily/
├── dhan_*.csv (daily data from Dhan)

data/cache/dhan/intraday/
├── dhan_*_5m.csv (intraday candles)
└── dhan_*_15m.csv (15-minute candles)
```

### 📊 Data Format

Each CSV contains weekly OHLCV data:
```
time,open,high,low,close,volume
2016-01-03 18:30:00,248.89,257.16,244.36,254.03,25813943
2016-01-10 18:30:00,251.60,269.88,250.38,265.81,41323881
```

- **time**: Market close timestamp (YYYY-MM-DD HH:MM:SS)
- **open**: Opening price
- **high**: Weekly high
- **low**: Weekly low
- **close**: Closing price
- **volume**: Total trading volume

### ✅ Performance & Success Rate

**Session Results (Dec 30, 2025):**
- Main basket: 563/563 symbols ✅ 100% success
- Large basket: 103/103 symbols ✅ 100% success
- Test basket: 5/5 symbols ✅ 100% success

**Data Coverage:**
- Historical depth: 2016-present (516+ weeks)
- Symbols per basket: 5-563 stocks
- Fetch time: ~30-50 seconds for 50+ symbols

### 🔧 Technical Details

**API Endpoint:**
- URL: `GET https://api.groww.in/v1/historical/candle/range`
- Authentication: Bearer token in Authorization header
- Headers: `X-API-VERSION: 1.0`, `Accept: application/json`

**Parameters:**
- `exchange`: NSE (stock exchange)
- `segment`: CASH (equity segment)
- `trading_symbol`: Stock symbol (e.g., RELIANCE)
- `start_time`: yyyy-MM-dd HH:mm:ss format
- `end_time`: yyyy-MM-dd HH:mm:ss format
- `interval_in_minutes`: 10080 (1 week)

**Rate Limits:**
- 300 requests per minute (non-trading API tier)
- Token auto-renewal: Every 13 hours

### ⚠️ Troubleshooting

**Token Generation Failed:**
- Verify GROWW_API_KEY and GROWW_API_SECRET in .env
- Check credentials at https://groww.in/trade-api/api-keys
- Regenerate new credentials if needed

**Symbol Not Found:**
- Check symbol spelling (must be uppercase)
- Verify it's listed on NSE
- Confirm in `data/groww-scrip-master-detailed.csv`

**Connection Timeout:**
- Check internet connection
- Verify Groww API is accessible
- Retry the command

### 📈 Integration with Backtesting

**Current Usage:**
- Weekly OHLC data used for multi-timeframe analysis
- Supports basket-based backtesting
- Compatible with existing strategy runners

**Future Enhancements:**
- Add daily data fetching from Groww
- Combine with Dhan intraday data
- Real-time data streaming integration
- Automatic daily/weekly data updates

---

## 📡 Groww API Reference (Complete Technical Specification)

### Authentication: Checksum-Based Token Generation

**Endpoint**: `POST https://api.groww.in/v1/token/api/access`

**Purpose**: Generates short-lived access tokens with `back_test` role (required for historical data)

**How It Works**:
1. Generate SHA256 checksum: `hash(API_SECRET + current_epoch_timestamp)`
2. Send checksum and timestamp to token endpoint
3. Receive access token valid for 13 hours
4. Use token as Bearer in Authorization header

**Implementation**:
```python
import hashlib
import time
import requests

def get_access_token(api_key: str, api_secret: str) -> str:
    """Generate fresh access token via checksum flow"""
    timestamp = str(int(time.time()))
    checksum = hashlib.sha256(
        f"{api_secret}{timestamp}".encode()
    ).hexdigest()
    
    response = requests.post(
        'https://api.groww.in/v1/token/api/access',
        json={
            'checksum': checksum,
            'timestamp': timestamp
        },
        headers={
            'Authorization': f'Bearer {api_key}'
        }
    )
    
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Token generation failed: {response.status_code}")
```

**Permissions Granted**:
- `back_test` - Historical data access ✅
- `order-basic` - Order placement
- `order_read_only-basic` - Order viewing
- `live_data-basic` - Live price data
- `non_trading-basic` - Non-trading features

**Token Validity**: 13 hours (auto-renewable on each fetch)

### Historical Data Endpoint

**Endpoint**: `GET https://api.groww.in/v1/historical/candle/range`

**Purpose**: Fetch OHLC bars at any timeframe (daily, weekly, monthly, intraday)

**Parameters**:

| Parameter | Type | Required | Example | Notes |
|-----------|------|----------|---------|-------|
| `exchange` | string | ✅ | `NSE` | Stock exchange |
| `segment` | string | ✅ | `CASH` | Market segment (CASH for equities) |
| `trading_symbol` | string | ✅ | `RELIANCE` | Stock symbol |
| `start_time` | string | ✅ | `2024-01-01 00:00:00` | Format: `yyyy-MM-dd HH:mm:ss` |
| `end_time` | string | ✅ | `2025-12-30 23:59:59` | Format: `yyyy-MM-dd HH:mm:ss` |
| `interval_in_minutes` | integer | ✅ | `10080` | See intervals below |

**Common Intervals**:
| Timeframe | Minutes | Use Case |
|-----------|---------|----------|
| 5-minute | 5 | Intraday scalping |
| 15-minute | 15 | Intraday swings |
| 25-minute | 25 | Custom intraday |
| 60-minute | 60 | Intraday medium-term |
| Daily | 1440 | Daily trading |
| **Weekly** | **10080** | **Multi-timeframe analysis** |
| Monthly | 43200 | Long-term trends |

**Response Format**:
```json
{
  "status": 200,
  "statusMessage": "success",
  "statusCode": "200",
  "data": [
    [
      1577145600,      // Epoch timestamp (seconds)
      681.0,           // Open
      686.69,          // High
      672.95,          // Low
      678.82,          // Close
      6402372          // Volume
    ]
  ]
}
```

**HTTP Status Codes**:
- `200` - Success ✅
- `400` - Bad request (invalid parameters)
- `401` - Unauthorized (invalid token)
- `403` - Forbidden (insufficient permissions)
- `429` - Rate limit exceeded (300 req/min)
- `500` - Server error (retry later)

**Rate Limits**:
- **Non-trading tier**: 300 requests/minute
- **Recommended batch**: 50-100 symbols per minute
- **Main basket (563 symbols)**: ~2-3 minutes

### Instrument Master Data

**Endpoint**: `GET https://api.groww.in/v1/instruments/all`

**Purpose**: Get list of all tradeable instruments with their exchange tokens

**Parameters**:
- No parameters required (returns all 170K+ instruments)

**Response Format**:
```json
{
  "status": 200,
  "data": [
    {
      "exchange": "NSE",
      "exchange_token": 2885,
      "trading_symbol": "RELIANCE",
      "groww_symbol": "RELIANCE",
      "segment": "CASH",
      "name": "Reliance Industries Limited",
      "isin": "INE002A01018",
      ...
    }
  ]
}
```

**File Size**: ~25MB CSV (170,006 rows)

### Error Handling & Recovery

**Common Errors**:

| Issue | Cause | Solution |
|-------|-------|----------|
| 403 Forbidden | Token lacks `back_test` role | Use checksum flow, not TOTP |
| 400 Bad Request | Invalid date format or missing parameter | Use `yyyy-MM-dd HH:mm:ss` format |
| Empty response | Date range has no trading days | Check for weekends/holidays |
| 429 Rate Limit | Too many requests | Add delays between requests |
| Connection timeout | Network issue | Retry with exponential backoff |

**Retry Strategy**:
```python
import time
from requests.exceptions import RequestException

def fetch_with_retry(url, headers, params, max_retries=3):
    """Fetch data with exponential backoff"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            elif response.status_code in [429, 500]:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
                continue
            else:
                raise Exception(f"HTTP {response.status_code}")
        except RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

### Data Validation

**Quality Checks**:
```python
def validate_candles(data: list) -> bool:
    """Validate OHLC data integrity"""
    for candle in data:
        timestamp, open, high, low, close, volume = candle
        
        # Logical checks
        assert high >= open, f"High < Open: {candle}"
        assert high >= close, f"High < Close: {candle}"
        assert high >= low, f"High < Low: {candle}"
        assert low <= close, f"Low > Close: {candle}"
        assert volume >= 0, f"Negative volume: {candle}"
        
        return True
```

**Data Consistency**:
- **Week boundary**: Friday to next Friday
- **Day boundary**: Previous close matches next open when adjacent
- **Volume**: Always >= 0, typically > 0 on trading days
- **Gap detection**: Identify non-trading days (weekends, holidays)

### Complete Example: Fetching Weekly Data

```python
import hashlib
import time
import requests
import pandas as pd

# Configuration
API_KEY = "your_jwt_token"
API_SECRET = "your_secret"

# Step 1: Generate token
timestamp = str(int(time.time()))
checksum = hashlib.sha256(f"{API_SECRET}{timestamp}".encode()).hexdigest()

token_response = requests.post(
    'https://api.groww.in/v1/token/api/access',
    json={'checksum': checksum, 'timestamp': timestamp},
    headers={'Authorization': f'Bearer {API_KEY}'}
)

access_token = token_response.json()['access_token']

# Step 2: Fetch weekly data for RELIANCE (2024-2025)
candle_response = requests.get(
    'https://api.groww.in/v1/historical/candle/range',
    headers={
        'Authorization': f'Bearer {access_token}',
        'X-API-VERSION': '1.0'
    },
    params={
        'exchange': 'NSE',
        'segment': 'CASH',
        'trading_symbol': 'RELIANCE',
        'start_time': '2024-01-01 00:00:00',
        'end_time': '2025-12-30 23:59:59',
        'interval_in_minutes': 10080
    }
)

# Step 3: Process and save
data = candle_response.json()['data']
df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
df['time'] = pd.to_datetime(df['time'], unit='s')
df.to_csv('data/cache/groww/weekly/groww_2885_RELIANCE_1w.csv', index=False)

print(f"✅ Saved {len(df)} weeks of RELIANCE data")
```

### API Limitations

**Data Availability**:
- **Daily**: Available from 2016-present (500+ weeks)
- **Intraday**: Available from 2019-2022 (varies by symbol)
- **Delisted stocks**: May have incomplete history

**Session Management**:
- **Token renewal**: Every 13 hours (automatic in production)
- **No persistent sessions**: Each script run generates fresh token
- **No account state**: API is stateless (no positions, balance tracking)

**Data Accuracy**:
- **Delayed**: Not real-time (typically T+1 or cached)
- **Consolidated**: Includes all traded volumes (NSE regular, iESE, etc.)
- **Adjusted**: Dividend/split adjustments applied by Groww

---

