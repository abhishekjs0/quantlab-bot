# Dhan API Comprehensive Guide

> **Focus**: Historical data fetching for backtesting  
> **For live trading:** See `webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md`

**Status**: ✅ Production Ready | **Latest Update**: 2025-11-21 | **Success Rate**: 99.5%

---

## Architecture Note

This guide covers **data fetching for backtesting** in the main project.

**For live order placement via webhooks:**
- See `webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md`
- Covers order types, product types, live trading specifics
- Focused on production webhook deployment

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Setup & Authentication](#setup--authentication)
3. [Order Types & Execution](#order-types--execution)
4. [Webhook Integration](#webhook-integration)
5. [API Endpoints](#api-endpoints)
6. [Unified Data Fetcher](#unified-data-fetcher)
7. [Supported Timeframes](#supported-timeframes)
8. [Multi-Timeframe Aggregation](#multi-timeframe-aggregation)
9. [Data Availability](#data-availability)
10. [Error Handling & Retry Logic](#error-handling--retry-logic)
11. [Output Format & Verification](#output-format--verification)
12. [Cache Management](#cache-management)
13. [Integration with Backtesting](#integration-with-backtesting)
14. [Troubleshooting](#troubleshooting)
15. [Performance Characteristics](#performance-characteristics)
16. [API Reference](#api-reference)

---

## Quick Start

The unified fetcher supports **any basket**, **any symbol**, **any timeframe** with automatic multi-timeframe aggregation, token validation, and error handling.

### Basic Usage

```bash
# Fetch entire basket
python3 scripts/dhan_fetch_data.py --basket large --timeframe 1d

# Fetch specific symbols
python3 scripts/dhan_fetch_data.py --symbols RELIANCE,INFY,TCS --timeframe 1d

# Fetch with custom history
python3 scripts/dhan_fetch_data.py --basket mega --timeframe 25m --days-back 90

# Skip token validation (if token recently refreshed)
python3 scripts/dhan_fetch_data.py --basket small --timeframe 1d --skip-token-check
```

### Typical Execution

```
python3 scripts/dhan_fetch_data.py --basket large --timeframe 1d --days-back 60

✅ Token valid (23.2 hours left)
✅ Loaded 17533 symbols
📌 Fetching 103 symbols (1d, 60d)
✅ Cached: 95
📌 Missing: 8

[  1/8] RELIANCE     ✅ 41 candles
[  2/8] INFY         ✅ 41 candles
...
[  8/8] TCS          ✅ 41 candles

✅ Successful: 8/8
❌ Failed: 0/8

📁 Cache: /path/to/data/cache/
```

---

## Setup & Authentication

### Get Access Token

1. **Automated Setup (Recommended)**
   ```bash
   python scripts/dhan_token_manager.py
   ```
   - Browser opens automatically
   - Script auto-fills mobile, password, TOTP
   - Copy tokenId from redirect URL
   - Token saved to `.env`

2. **Manual Setup**
   ```bash
   # Create .env file with credentials
   echo "DHAN_ACCESS_TOKEN=your_token_here" > .env
   echo "DHAN_CLIENT_ID=your_client_id_here" >> .env
   
   # Verify
   cat .env
   ```

3. **Verify Setup**
   ```bash
   # Test token validity
   python3 scripts/dhan_fetch_data.py --symbols RELIANCE --skip-token-check
   ```

### Token Management

The fetcher automatically:

---

## Order Types & Execution

### Overview

The Dhan broker integration supports three types of orders:

1. **Regular Orders** - Standard market/limit orders with AMO timing support
2. **Super Orders** - Entry + Target + Stop Loss in a single order with trailing
3. **Forever Orders** - GTT (Good Till Triggered) orders for automated triggers

### Regular Orders with AMO Timing

Regular orders can be placed with After Market Orders (AMO) timing:

```python
from dhan_broker import DhanBroker

broker = DhanBroker()

# Place order 30 minutes after market open
broker.place_order(
    security_id="1333",
    exchange="NSE",
    transaction_type="BUY",
    quantity=10,
    order_type="MARKET",
    product_type="CNC",
    amo_time="OPEN_30"  # Execute 30 min after market open
)
```

**AMO Timing Options:**
- `PRE_OPEN` - Before market open
- `OPEN` - At market open
- `OPEN_30` - 30 minutes after market open (default)
- `OPEN_60` - 60 minutes after market open

### Super Orders

Super Orders combine entry, target, and stop loss in a single order with trailing stop loss:

```python
# Buy with target and stop loss
broker.place_super_order(
    security_id="1333",
    exchange="NSE",
    transaction_type="BUY",
    quantity=10,
    order_type="MARKET",
    product_type="CNC",
    price=0,  # Market order
    target_price=1550.00,  # Target price
    stop_loss_price=1450.00,  # Stop loss price
    trailing_jump=5.0,  # Trailing stop jump (optional)
    tag="MyStrategy"
)
```

**Features:**
- Three legs: ENTRY_LEG, TARGET_LEG, STOP_LOSS_LEG
- Trailing stop loss support
- Automatic OCO (One Cancels Other) between target and stop loss
- Requires Static IP whitelisting (see Authentication section)

### Forever Orders (GTT)

Forever Orders are Good Till Triggered orders that remain active until triggered or cancelled:

```python
# Get current LTP
ltp = broker.get_ltp("27066", "NSE")  # SWIGGY

# Place forever order to sell at 2% below LTP
trigger_price = ltp * 0.981
sell_price = ltp * 0.98

broker.place_forever_order(
    security_id="27066",
    exchange="NSE",
    transaction_type="SELL",
    quantity=1,
    order_type="LIMIT",
    product_type="CNC",
    price=sell_price,
    trigger_price=trigger_price,
    order_flag="SINGLE",  # or "OCO" for two-way triggers
    validity="DAY",
    tag="GTT-SWIGGY"
)
```

**Order Flags:**
- `SINGLE` - Single trigger condition
- `OCO` - One Cancels Other (requires price1, trigger_price1, quantity1)

**OCO Example:**
```python
# Buy if price goes up OR down
broker.place_forever_order(
    security_id="27066",
    exchange="NSE",
    transaction_type="BUY",
    quantity=1,
    order_type="LIMIT",
    product_type="CNC",
    price=520.00,
    trigger_price=525.00,
    order_flag="OCO",
    validity="DAY",
    # Second trigger condition
    price1=500.00,
    trigger_price1=495.00,
    quantity1=1,
    tag="OCO-SWIGGY"
)
```

**Requirements:**
- Forever Orders require Static IP whitelisting
- Visit: https://dhanhq.co/docs/v2/authentication/#setup-static-ip
- Market Data API subscription needed for real-time LTP

### Getting LTP (Last Traded Price)

```python
# Get current market price
ltp = broker.get_ltp("27066", "NSE")  # Returns float

if ltp:
    print(f"Current price: ₹{ltp:.2f}")
else:
    print("Market Data API not subscribed or market closed")
```

**Note:** Market Data API requires separate subscription from Dhan.

---

## Webhook Integration

### TradingView Webhook Setup

The webhook server accepts POST requests from TradingView alerts:

**1. Start the webhook server:**
```bash
# Set up ngrok tunnel (for external access)
ngrok http 80

# Server runs on port 80 by default
python webhook_server.py
```

**2. Configure TradingView Alert:**

Webhook URL: `https://your-ngrok-url.ngrok.app/webhook`

Message payload:
```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "1",
      "exchange": "NSE",
      "symbol": "{{ticker}}",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "{{interval}}",
        "time": "{{time}}",
        "timenow": "{{timenow}}"
      }
    }
  ]
}
```

**3. Test the webhook:**
```bash
# Run test suite
python test_tradingview_webhook.py

# Monitor incoming webhooks
tail -f webhook_server.log
```

### Webhook Payload Structure

```python
class WebhookPayload:
    secret: str              # Authentication secret (GTcl4)
    alertType: str           # "multi_leg_order", "single_order", "cancel_order"
    order_legs: list[OrderLeg]  # List of order legs

class OrderLeg:
    transactionType: str     # "B" = Buy, "S" = Sell
    orderType: str          # "MKT", "LMT", "SL", "SL-M"
    quantity: str           # Number of shares
    exchange: str           # "NSE", "BSE", "NFO"
    symbol: str             # Trading symbol
    instrument: str         # "EQ", "FUT", "CE", "PE"
    productType: str        # "C" = CNC, "I" = Intraday, "M" = Margin
    sort_order: str         # Execution priority
    price: str              # Limit price (0 for market orders)
    meta: OrderMetadata     # Alert timing metadata
```

### Multi-Leg Orders

Execute multiple orders in sequence (e.g., buy + sell target + stop loss):

```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "10",
      "exchange": "NSE",
      "symbol": "INFY",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "1D",
        "time": "2025-11-20T15:30:00",
        "timenow": "2025-11-20T15:30:00"
      }
    }
  ]
}
```

### Webhook Security

- Secret key validation (configured in `.env`)
- HTTPS recommended (use ngrok for testing)
- Order logging to `webhook_orders.csv`
- Detailed logging in `webhook_server.log`

### Environment Variables

```bash
# .env configuration
WEBHOOK_SECRET=GTcl4
WEBHOOK_PORT=80
WEBHOOK_HOST=0.0.0.0
ENABLE_DHAN=false  # Set to true for live trading
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_token
```

---

### Token Management

The fetcher automatically:
- ✅ Checks JWT expiry before requests
- ✅ Warns when token expires within 24 hours
- ✅ Allows skipping check if recently refreshed (`--skip-token-check`)

---

## API Endpoints

Dhan API v2 provides two main endpoints for historical data:

### Daily Historical Data

**Endpoint:** `POST /v2/charts/historical`

**Request Parameters:**
```json
{
  "securityId": "1594",
  "exchangeSegment": "NSE_EQ",
  "instrument": "EQUITY",
  "expiryCode": 0,
  "oi": false,
  "fromDate": "2024-01-01",
  "toDate": "2024-12-31"
}
```

**Response Format:**
```json
{
  "open": [100.5, 101.2, 99.8, ...],
  "high": [102.1, 103.4, 101.5, ...],
  "low": [99.2, 100.1, 98.5, ...],
  "close": [101.0, 102.1, 100.2, ...],
  "volume": [1000000, 1200000, 800000, ...],
  "timestamp": [1704067200, 1704153600, 1704240000, ...]
}
```

**Key Characteristics:**
- ✅ Unlimited historical data (inception onwards)
- ✅ Single API call per stock
- ✅ Date format: `YYYY-MM-DD`
- ✅ Response: Parallel arrays (NOT array of objects)

### Intraday Historical Data

**Endpoint:** `POST /v2/charts/intraday`

**Request Parameters:**
```json
{
  "securityId": "1594",
  "exchangeSegment": "NSE_EQ",
  "instrument": "EQUITY",
  "interval": 25,
  "oi": false,
  "fromDate": "2024-01-01 09:15:00",
  "toDate": "2024-03-31 15:30:00"
}
```

**Response Format:** Same as daily (parallel arrays)

**Interval Options:**
```
1  = 1-minute candles
5  = 5-minute candles
15 = 15-minute candles
25 = 25-minute candles (recommended for aggregation)
60 = 60-minute candles
```

**Important Limitations:**
- ⚠️ Only 90 days of data per request
- ⚠️ Script automatically chunks longer periods
- ⚠️ Market hours only (9:15 AM - 3:30 PM IST)
- ⚠️ No weekend or holiday data

### Authentication

**Header:** `access-token: JWT_TOKEN`

Token is read from `.env`:
```bash
DHAN_ACCESS_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
DHAN_CLIENT_ID=your_client_id
```

---

## Unified Data Fetcher

### Purpose

The `scripts/dhan_fetch_data.py` script replaces 7 fragmented older scripts with a single, production-ready unified fetcher.

### Replaced Scripts

- ❌ `dhan_data_fetcher.py`
- ❌ `fetch_large_basket_robust.py`
- ❌ `fetch_large_basket_clean.py`
- ❌ `fetch_large_missing_robust.py`
- ❌ `fetch_missing_large.py`
- ❌ `fetch_niftybees_benchmark.py`
- ❌ `test_simple.py`

### Full Syntax

```bash
python3 scripts/dhan_fetch_data.py [options]
```

### Required Arguments (one of)

```bash
--basket {mega|large|small|test}
```
or
```bash
--symbols SYMBOL1,SYMBOL2,...
```

### Optional Arguments

```bash
--timeframe {1d|1m|5m|15m|25m|60m}    # Default: 1d
--days-back INTEGER                    # Default: 730 (2 years)
--skip-token-check                     # Skip expiry validation
```

### Examples

```bash
# Fetch entire mega basket for daily
python3 scripts/dhan_fetch_data.py --basket mega --timeframe 1d

# Fetch large basket for 25m + aggregates (90 days)
python3 scripts/dhan_fetch_data.py --basket large --timeframe 25m --days-back 90

# Fetch specific symbols (60 days history)
python3 scripts/dhan_fetch_data.py --symbols RELIANCE,INFY,TCS --timeframe 1d --days-back 60

# Fetch small basket 1m data (last 30 days, skip token check)
python3 scripts/dhan_fetch_data.py --basket small --timeframe 1m --days-back 30 --skip-token-check
```

### Key Features

- 🔄 **Universal:** Works with any basket, symbol, or timeframe
- 🚀 **Fast:** Smart caching prevents re-fetching
- 🛡️ **Robust:** Token validation + exponential backoff retry logic
- 📊 **Complete:** Multi-timeframe aggregation (25m → 75m, 125m)
- 📈 **Accurate:** Direct Dhan API implementation
- 🎯 **Simple:** Single command for all use cases

---

## Supported Timeframes

| Timeframe | Interval | Limitation | Typical Per Stock |
|-----------|----------|------------|------------------|
| `1d` | Daily | Unlimited history | 2,500+ candles |
| `1m` | 1 minute | 90-day chunks | 10,000+ candles |
| `5m` | 5 minute | 90-day chunks | 2,000+ candles |
| `15m` | 15 minute | 90-day chunks | 600+ candles |
| `25m` | 25 minute | 90-day chunks (base for agg) | 360+ candles |
| `60m` | 60 minute | 90-day chunks | 130+ candles |

**Chunking:** Intraday data automatically fetched in 90-day chunks and transparently combined.

---

## Multi-Timeframe Aggregation

The script automatically creates derived timeframes from base candles.

### Automatic Aggregation from 25m

When you fetch `--timeframe 25m`, the script creates two aggregated files:

```
dhan_1594_INFY_75m.csv    ← Aggregated (3 × 25m = 75m)
dhan_1594_INFY_125m.csv   ← Aggregated (5 × 25m = 125m)
```

**Note:** 25m base candles are NOT cached (only temporary for aggregation).

### Aggregation Logic

```
Period:  09:15-09:40 | 09:40-10:05 | 10:05-10:30  (3 × 25m = 75m)

Open:    First candle's open
High:    Maximum of all highs in period
Low:     Minimum of all lows in period
Close:   Last candle's close
Volume:  Sum of all volumes
```

### Session Boundaries (NSE 9:15 AM - 3:30 PM IST)

**25-Minute Candles** (6 per day, with final 5m bar):
```
09:15-09:40, 09:40-10:05, 10:05-10:30, 10:30-10:55, ...
```

**75-Minute Candles** (5 per day):
```
09:15-10:30, 10:30-11:45, 11:45-13:00, 13:00-14:15, 14:15-15:30
```

**125-Minute Candles** (3 per day):
```
09:15-11:20, 11:20-13:25, 13:25-15:30
```

---

## Data Availability

### Typical Coverage

| Timeframe | Data Available From | Hours of Data |
|-----------|-------------------|---------------|
| Daily (1d) | Inception (~2015+) | ~10 years |
| Intraday (1m-60m) | ~2017-04-03 | ~8.5 years |

**Note:** Intraday data starts from April 2017 due to Dhan's data vendor licensing (industry standard limitation).

### Cache Status (Current)

```
Baskets:
├─ mega:  73 stocks
├─ large: 103 stocks
└─ benchmark: 1 stock (NIFTYBEES)
Total: 177 stocks

Cached Files:
├─ 1d:   176 files (1 missing: DHANI - API limitation)
├─ 75m:  177 files ✓
└─ 125m: 177 files ✓
```

### Example Candle Counts (30-day fetch)

```
Stock: INFY (30 days)
├─ 1d:    30 candles (1 per day)
├─ 60m:   ~150 candles (5 per day)
├─ 25m:   ~289 candles (temporary, not cached)
├─ 75m:   ~106 candles (aggregated, cached)
└─ 125m:  ~75 candles (aggregated, cached)
```

---

## Error Handling & Retry Logic

### Automatic Retry with Exponential Backoff

```
Attempt 1: Immediate
Attempt 2: Wait 0.5 seconds
Attempt 3: Wait 2.0 seconds
Attempt 4: Wait 8.0 seconds (max)
```

### Handled HTTP Status Codes

| Status | Meaning | Action |
|--------|---------|--------|
| 200 | Success | Return data |
| 401 | Unauthorized | Stop (token expired) |
| 429 | Rate limited | Backoff, retry |
| 500+ | Server error | Backoff, retry |
| Timeout | Network issue | Backoff, retry |

### Output Indicators

```
✅ Symbol - Successfully fetched X candles
❌ Symbol - Failed (with reason)
⊘ Symbol - Not in master data
```

### Example Error Recovery

```
[  1/10] RELIANCE     (attempt 1) ⏳ Timeout...
                      (wait 0.5s)
                      (attempt 2) ⏳ HTTP 429...
                      (wait 2.0s)
                      (attempt 3) ✅ Success, 41 candles
```

---

## Output Format & Verification

### CSV File Naming

```
dhan_{securityId}_{symbol}_{timeframe}.csv

Examples:
- dhan_1594_INFY_1d.csv
- dhan_1594_INFY_75m.csv
- dhan_1594_INFY_125m.csv
```

### CSV Content Structure

```csv
time,open,high,low,close,volume
2024-01-01 09:15:00,100.50,102.10,99.20,101.00,1000000
2024-01-01 09:40:00,101.00,103.40,100.10,102.10,1200000
2024-01-01 10:05:00,102.10,104.50,101.50,103.75,1100000
```

**Columns:**
- `time`: UTC timestamp (timezone-aware)
- `open`: Opening price
- `high`: Highest price in period
- `low`: Lowest price in period
- `close`: Closing price
- `volume`: Volume traded

### Verification Script

```python
import pandas as pd

df = pd.read_csv("data/cache/dhan_1594_INFY_1d.csv", 
                 parse_dates=[0], index_col=0)

print(f"✅ Candles: {len(df)}")
print(f"✅ Date range: {df.index.min()} to {df.index.max()}")
print(f"✅ Columns: {df.columns.tolist()}")
print(f"✅ Data integrity: {df.isnull().sum().sum()} null values")
```

---

## Cache Management

### Cache Location

```
data/cache/
├─ dhan_1594_INFY_1d.csv
├─ dhan_1594_INFY_75m.csv
├─ dhan_1594_INFY_125m.csv
├─ dhan_2885_RELIANCE_1d.csv
└─ ... (177+ files)
```

### Smart Caching

- ✅ Detects cached files before fetching
- ✅ Skips already-downloaded data
- ✅ Shows cached vs missing count
- ✅ Only fetches missing symbols

### Clear Cache

```bash
# Remove specific symbol
rm data/cache/dhan_*_INFY_*.csv

# Remove specific timeframe
rm data/cache/dhan_*_*_75m.csv

# Remove everything (careful!)
rm data/cache/*.csv
```

---

## Integration with Backtesting

### Load Data in Python

```python
from data.loaders import load_many_dhan_multiframe

# Load 75m data for backtest
data_75m = load_many_dhan_multiframe(["RELIANCE", "INFY", "TCS"], timeframe="75m")

# Iterate through symbols
for symbol, df in data_75m.items():
    print(f"{symbol}: {len(df)} candles")
    
    # Use in strategy
    for idx, row in df.iterrows():
        close = row["close"]
        high = row["high"]
        volume = row["volume"]
        # ... process candle
```

### Run Backtests

```bash
# Daily timeframe
python runners/run_basket.py --basket mega --strategy ichimoku --timeframe 1d

# 75-minute timeframe
python runners/run_basket.py --basket mega --strategy ichimoku --timeframe 75m

# 125-minute timeframe
python runners/run_basket.py --basket mega --strategy ichimoku --timeframe 125m
```

### Programmatic Backtest

```python
from core.engine import BacktestEngine
from core.registry import make_strategy
from data.loaders import load_many_dhan_multiframe

# Load data
data = load_many_dhan_multiframe(["RELIANCE"], timeframe="75m")

# Run backtest
for symbol, df in data.items():
    strat = make_strategy("ichimoku", None)
    trades, equity_curve, events = BacktestEngine(df, strat).run()
    print(f"{symbol}: {len(trades)} trades, {len(df)} candles")
```

---

## Troubleshooting

### Problem: "DHAN credentials not in .env"

**Solution:**
```bash
# Create .env file with credentials
echo "DHAN_ACCESS_TOKEN=your_token_here" > .env
echo "DHAN_CLIENT_ID=your_client_id_here" >> .env

# Verify
cat .env
```

### Problem: "Token expired"

**Solution:**
```bash
# Refresh token
python3 scripts/dhan_token_manager.py

# Or skip check this time
python3 scripts/dhan_fetch_data.py --symbols RELIANCE --skip-token-check
```

### Problem: HTTP 429 (Rate Limited)

**Cause:** Too many API requests too quickly

**Solution:** Script handles automatically with exponential backoff. If still occurring:
1. Wait 30 minutes before retry
2. Fetch smaller basket
3. Use fewer symbols

### Problem: No data for symbol

**Cause:** Symbol not in NSE master or API has no data

**Solution:**
```bash
# Check if symbol exists in master
grep -i "SYMBOLNAME" data/api-scrip-master-detailed.csv

# Try different date range
python3 scripts/dhan_fetch_data.py --symbols SYMBOL --timeframe 1d --days-back 1825
```

### Problem: Empty CSV file

**Cause:** API returned no data (before intraday availability date)

**Solution:**
- Use daily (1d) timeframe instead of intraday for pre-2017 data
- Check symbol has sufficient liquidity
- Verify in another symbol that fetching works

### Problem: Timeout errors

**Cause:** Network issues or API slow

**Solution:**
- Script retries automatically (3 attempts with backoff)
- Check internet connection
- Try at off-peak hours (market closed)
- Reduce number of symbols

---

## Performance Characteristics

### Fetch Speed

```
Daily data:  ~100ms per stock (single API call)
25m data:    ~500ms per stock (multiple 90-day chunks)
Rate limit:  100ms delay between requests (built-in)
```

### Typical Run Times

| Basket | Size | Cached | Missing | Fetch Time |
|--------|------|--------|---------|-----------|
| test | 3 stocks | 3 | 0 | 0.1s |
| small | 10 stocks | 10 | 0 | 0.2s |
| large | 103 stocks | 95 | 8 | 2s |
| mega | 73 stocks | 72 | 1 | 1s |

### Data Volumes

```
Per stock (730 days):
├─ 1d:    ~250 candles = 5KB
├─ 60m:   ~1,250 candles = 25KB
├─ 25m:   ~3,000 candles = 60KB (temporary)
├─ 75m:   ~1,000 candles = 20KB (cached)
└─ 125m:  ~600 candles = 12KB (cached)

Total per stock (cached only): ~37KB
Mega basket (73 stocks): ~2.7MB
Large basket (103 stocks): ~3.8MB
All with benchmark (177 stocks): ~6.5MB
```

---

## API Reference

### Official Documentation

- **Dhan Official Docs:** https://dhanhq.co/docs/v2/
- **Historical Data Endpoint:** https://dhanhq.co/docs/v2/historical-data/
- **GitHub SDK:** https://github.com/dhan-oss/DhanHQ-py

### Internal Resources

- **Master Data:** `data/api-scrip-master-detailed.csv` (17,533 NSE symbols)
- **Baskets:** 
  - `data/basket_test.txt` (3 stocks)
  - `data/basket_small.txt` (10 stocks)
  - `data/basket_large.txt` (103 stocks)
  - `data/basket_mega.txt` (73 stocks)
  - Benchmark: NIFTYBEES (1 stock)
- **Cache:** `data/cache/` (all downloaded CSV files)

### Implementation Details

**Script Location:** `scripts/dhan_fetch_data.py`

**Key Functions:**
- `check_token_expiry()` - JWT validation
- `fetch_intraday_chunked()` - 90-day chunking
- `fetch_daily_data()` - Daily candles
- `aggregate_intraday()` - 25m → 75m/125m
- `fetch_stock_data()` - Orchestration

### Security IDs Reference

| Symbol | ID |
|--------|-----|
| RELIANCE | 2885 |
| INFY | 1594 |
| TCS | 1023 |
| HDFCBANK | 10397 |
| BHARTIARTL | 10604 |
| NIFTYBEES | 10576 |

See `data/api-scrip-master-detailed.csv` for complete list of all 17,533 NSE symbols.

---

## Quick Reference Commands

```bash
# Fetch test basket
python3 scripts/dhan_fetch_data.py --basket test --timeframe 1d

# Fetch large basket with 25m aggregation
python3 scripts/dhan_fetch_data.py --basket large --timeframe 25m

# Fetch specific stocks
python3 scripts/dhan_fetch_data.py --symbols RELIANCE,INFY,TCS --timeframe 1d

# Fetch with custom history (90 days)
python3 scripts/dhan_fetch_data.py --basket mega --timeframe 1d --days-back 90

# Verify downloaded data
ls -1 data/cache/dhan_*.csv | wc -l

# Check specific file
head -5 data/cache/dhan_1594_INFY_1d.csv

# Count candles per file
wc -l data/cache/dhan_*.csv | tail -1

# Load data for backtesting
python3 -c "
from data.loaders import load_many_dhan_multiframe
symbols = open('data/basket_mega.txt').read().strip().split('\n')
data = load_many_dhan_multiframe(symbols, timeframe='75m')
print(f'Loaded {len(data)} symbols')
"
```

---

## Summary

✅ **Status:** Production Ready  
✅ **Success Rate:** 99.5% (165/166 stocks recovered)  
✅ **API Endpoints:** Verified and documented  
✅ **Multi-Timeframe:** Fully implemented and tested  
✅ **Order Types:** Regular, Super Orders, Forever Orders (GTT)  
✅ **AMO Timing:** PRE_OPEN, OPEN, OPEN_30, OPEN_60  
✅ **Webhook Integration:** TradingView alerts with ngrok support  
✅ **Error Handling:** Robust with exponential backoff  
✅ **Documentation:** Complete with examples  

**The unified system provides:**

- 🔄 **Universal:** Any basket, symbol, timeframe
- 🚀 **Fast:** Smart caching prevents re-fetching
- 🛡️ **Robust:** Token validation + retry logic
- 📊 **Complete:** Multi-timeframe aggregation
- 📈 **Accurate:** Direct API implementation
- 🎯 **Simple:** Single command for any use case
- 📡 **Connected:** TradingView webhook integration
- 🎛️ **Advanced:** Super Orders, Forever Orders, AMO timing

**One script. Endless data. Infinite possibilities.**

---

Last Updated: 2025-11-20  
Success Rate: 99.5% → 165/166 stocks  
Multi-Timeframe: ✅ Working (25m → 75m, 125m)  
Order Types: ✅ Regular, Super, Forever (GTT)  
Webhook: ✅ TradingView integration tested  
Cache: 177 symbols × 2 timeframes = ~6.5MB

