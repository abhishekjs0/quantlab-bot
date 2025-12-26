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
| [basket_main.txt](../data/basket_main.txt) | Stock universe (103 symbols) |

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
