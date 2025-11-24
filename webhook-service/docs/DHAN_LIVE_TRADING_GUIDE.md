# Dhan Live Trading Guide - Webhook Service

> **Focus**: Live order placement via webhook-service on Google Cloud Run

**Last Updated**: 2025-11-23 (v2.2.0)  
**Status**: ✅ Production Ready - AMO Mode Enabled

---

## Table of Contents

1. [Order Types & Execution](#order-types--execution)
2. [Product Types](#product-types)
3. [Exchanges & Instruments](#exchanges--instruments)
4. [Order Placement](#order-placement)
5. [Order Status & Tracking](#order-status--tracking)
6. [Error Handling](#error-handling)
7. [Common Issues](#common-issues)

---

## Order Types & Execution

### Supported Order Types

| Order Type | Code | Description | Use Case |
|------------|------|-------------|----------|
| **Market** | `MKT` | Execute at best available price | Immediate execution |
| **Limit** | `LMT` | Execute at specific price or better | Control entry/exit price |
| **Stop Loss** | `SL` | Trigger limit order when price reached | Limit losses |
| **Stop Loss Market** | `SL-M` | Trigger market order when price reached | Quick stop loss |

### Market Order (MKT)

**Use when:** Need immediate execution, don't care about exact price

```json
{
  "orderType": "MKT",
  "quantity": "10",
  "price": "0",
  "transactionType": "B",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "instrument": "EQ",
  "productType": "C"
}
```

**Characteristics:**
- ✅ Guaranteed execution (if market open)
- ❌ Price not guaranteed (slippage possible)
- ✅ Fast execution (~1-2 seconds)

### Limit Order (LMT)

**Use when:** Want specific price or better

```json
{
  "orderType": "LMT",
  "quantity": "10",
  "price": "2500.50",
  "transactionType": "B",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "instrument": "EQ",
  "productType": "C"
}
```

**Characteristics:**
- ✅ Price guaranteed (at limit or better)
- ❌ Execution not guaranteed (may not fill)
- ⏱️ Can stay pending until filled or cancelled

### Stop Loss (SL)

**Use when:** Want to exit at specific price if market moves against you

```json
{
  "orderType": "SL",
  "quantity": "10",
  "price": "2450.00",
  "triggerPrice": "2460.00",
  "transactionType": "S",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "instrument": "EQ",
  "productType": "C"
}
```

**How it works:**
1. Price drops to trigger price (2460)
2. Limit order placed at limit price (2450)
3. Executes if market price reaches 2450 or lower

### Stop Loss Market (SL-M)

**Use when:** Want guaranteed execution on stop loss (accept slippage)

```json
{
  "orderType": "SL-M",
  "quantity": "10",
  "price": "0",
  "triggerPrice": "2460.00",
  "transactionType": "S",
  "symbol": "RELIANCE",
  "exchange": "NSE",
  "instrument": "EQ",
  "productType": "C"
}
```

**How it works:**
1. Price drops to trigger price (2460)
2. Market order placed immediately
3. Executes at best available price

---

## Product Types

| Product Type | Code | Description | Margin Required | Holding Period |
|--------------|------|-------------|-----------------|----------------|
| **CNC (Cash and Carry)** | `C` | Delivery-based | 100% | Overnight (T+2 settlement) |
| **Intraday** | `I` | Intraday MIS | 20-40% | Must square off same day |
| **Margin** | `M` | Margin trading | Varies | Overnight allowed |

### CNC (C) - Delivery Trading

**Best for:** Long-term positions, dividend collection

```json
{
  "productType": "C",
  "quantity": "10",
  "orderType": "MKT",
  "transactionType": "B",
  "symbol": "RELIANCE",
  "exchange": "NSE"
}
```

**Characteristics:**
- Full capital required (100% of trade value)
- Shares delivered to demat account (T+2)
- Can hold indefinitely
- No auto square-off

### Intraday (I) - MIS Trading

**Best for:** Day trading, leverage

```json
{
  "productType": "I",
  "quantity": "50",
  "orderType": "MKT",
  "transactionType": "B",
  "symbol": "RELIANCE",
  "exchange": "NSE"
}
```

**Characteristics:**
- Lower margin (20-40% typically)
- Must square off by 3:20 PM
- Auto square-off if not closed
- Higher leverage available

---

## Exchanges & Instruments

### Supported Exchanges

| Exchange | Code | Asset Class | Trading Hours (IST) |
|----------|------|-------------|---------------------|
| **NSE** | `NSE` | Equities | 9:15 AM - 3:30 PM |
| **BSE** | `BSE` | Equities | 9:15 AM - 3:30 PM |
| **NFO** | `NFO` | Futures & Options | 9:15 AM - 3:30 PM |
| **BFO** | `BFO` | BSE F&O | 9:15 AM - 3:30 PM |
| **MCX** | `MCX` | Commodities | 9:00 AM - 11:30/55 PM |

### Instrument Types

| Instrument | Code | Description | Example |
|------------|------|-------------|---------|
| **Equity** | `EQ` | Stocks | RELIANCE, INFY |
| **Futures** | `FUT` | Future contracts | NIFTY24NOVFUT |
| **Call Option** | `CE` | Call option | BANKNIFTY24NOV50000CE |
| **Put Option** | `PE` | Put option | BANKNIFTY24NOV50000PE |

---

## Order Placement

### Via TradingView Webhook

Orders are placed automatically when TradingView sends alert to Cloud Run webhook URL.

**Alert JSON:**
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

### Order Flow

```
TradingView Alert
       ↓
Cloud Run Webhook (/webhook endpoint)
       ↓
Parse & Validate JSON
       ↓
Map Symbol → Security ID (security_id_list.csv)
       ↓
Dhan API Order Placement
       ↓
Log to webhook_orders.csv (with IST timestamp)
       ↓
Return Response to TradingView
```

---

## Order Status & Tracking

### Order Statuses

| Status | Code | Meaning | Next Action |
|--------|------|---------|-------------|
| **Pending** | `PENDING` | Order placed, awaiting execution | Wait |
| **Transit** | `TRANSIT` | Order sent to exchange | Wait |
| **Traded** | `TRADED` | Fully executed | None |
| **Partial** | `PARTIAL` | Partially filled | Wait or cancel |
| **Cancelled** | `CANCELLED` | Order cancelled | Resubmit if needed |
| **Rejected** | `REJECTED` | Order rejected | Check reason, fix |

### Monitoring Orders

**Via Cloud Run Logs:**
```bash
# View real-time logs
gcloud run services logs tail tradingview-webhook \
  --region=asia-south1

# Search for specific symbol
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 | grep "RELIANCE"
```

**Via Dhan Platform:**
1. Login to Dhan web/app
2. Go to Orders section
3. View order status, execution details

---

## Error Handling

### Common Dhan API Errors

| Error | Reason | Solution |
|-------|--------|----------|
| `RMS:Rule: Check fund` | Insufficient funds | Add funds to account |
| `Invalid Symbol` | Symbol not found | Check symbol format |
| `Token Expired` | Access token expired | Regenerate token (see DHAN_CREDENTIALS_GUIDE.md) |
| `Market Closed` | Outside trading hours | Wait for market open |
| `Quantity not in lot size` | Wrong quantity for F&O | Use correct lot size |

### Token Expiry

Dhan tokens expire after ~20 hours. Update when needed:

```bash
# Generate new token (see DHAN_CREDENTIALS_GUIDE.md)

# Update Cloud Run
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars DHAN_ACCESS_TOKEN=eyJ0eXAi...
```

---

## Common Issues

### Order Not Placed

1. **Check ENABLE_DHAN setting:**
   ```bash
   gcloud run services describe tradingview-webhook \
     --region=asia-south1 \
     --format="value(spec.template.spec.containers[0].env[?name=='ENABLE_DHAN'].value)"
   ```

2. **Enable live trading:**
   ```bash
   gcloud run services update tradingview-webhook \
     --region=asia-south1 \
     --update-env-vars ENABLE_DHAN=true
   ```

### Symbol Not Found

```
Error: SecurityId not found for symbol RELIANCE_NSE
```

**Solution:** Symbol exists in security_id_list.csv (217,959 instruments). Check spelling/format.

### Insufficient Funds

```
Error: RMS:Rule: Check fund
```

**Solutions:**
1. Add funds to Dhan account
2. Reduce quantity
3. Use Intraday (I) instead of CNC (C) for leverage

### Market Closed

```
Error: Market is closed
```

**Trading Hours (IST):**
- Pre-open: 9:00-9:15 AM
- Normal: 9:15 AM - 3:30 PM
- Post-close: After 3:30 PM

---

## Quick Reference

### Market Order (Buy)
```json
{
  "transactionType": "B",
  "orderType": "MKT",
  "quantity": "10",
  "price": "0",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

### Limit Order (Sell)
```json
{
  "transactionType": "S",
  "orderType": "LMT",
  "quantity": "10",
  "price": "2550.00",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

### Stop Loss (Exit Position)
```json
{
  "transactionType": "S",
  "orderType": "SL-M",
  "quantity": "10",
  "price": "0",
  "triggerPrice": "2450.00",
  "exchange": "NSE",
  "symbol": "RELIANCE",
  "instrument": "EQ",
  "productType": "C"
}
```

---

**For more details:**
- `TRADINGVIEW_POST.md` - Webhook integration guide
- `DHAN_CREDENTIALS_GUIDE.md` - Token generation
- Main project `docs/DHAN_COMPREHENSIVE_GUIDE.md` - Data fetching & API reference

---

## Forever Orders (GTT - Good Till Triggered)

Forever Orders allow you to place orders that trigger automatically when price conditions are met, even when you're not actively monitoring.

### Setup

```python
from dhan_forever_orders import DhanForeverOrders

# Initialize
forever = DhanForeverOrders(client_id, access_token)
```

### Place Forever Order

```python
# Example: Sell SWIGGY at market price when it hits ₹450
response = forever.place_forever_order(
    security_id="27066",  # SWIGGY
    exchange="NSE",
    transaction_type="SELL",
    quantity=3,
    order_type="MARKET",
    product_type="CNC",
    trigger_price=450.0
)
```

### Get All Forever Orders

```python
orders = forever.get_all_forever_orders()
for order in orders:
    print(f"Order ID: {order['id']}, Status: {order['status']}")
```

### Manage Static IP

Dhan requires whitelisting your server's static IP address:

```python
# Get current static IPs
ips = forever.get_static_ips()
print(f"Current IPs: {ips}")

# Add new static IP
forever.set_static_ip("14.102.163.116")

# Modify existing IP
forever.modify_static_ip(1, "203.0.113.50")
```

**Note**: Maximum 2 static IPs allowed per account.

---

## Sell Order Validation

The webhook service can validate sell orders to prevent accidental shorting.

### Enable Validation

```bash
# Enable sell validation
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars ENABLE_SELL_VALIDATION=true
```

### How It Works

1. Receive sell order from TradingView
2. Check current holdings via Dhan API
3. Validate quantity ≤ available holdings
4. **Accept** if sufficient holdings
5. **Reject** if insufficient (log error, send Telegram notification)

### Example Validation

```json
{
  "transactionType": "S",
  "symbol": "RELIANCE",
  "quantity": "10",
  ...
}
```

**Validation Logic:**
```python
holdings = dhan.get_holdings()  # Your current positions
reliance_qty = holdings.get("RELIANCE", 0)

if sell_quantity <= reliance_qty:
    # Place sell order
    place_order(...)
else:
    # Reject order
    logger.error(f"Insufficient holdings: have {reliance_qty}, need {sell_quantity}")
    send_telegram_notification("❌ Sell order rejected: insufficient holdings")
```

### Edge Cases

**Scenario 1: Pending Sell Orders**
- Holdings: 100 shares
- Pending sell: 50 shares
- New sell: 60 shares
- **Result**: Rejected (only 50 available)

**Scenario 2: Intraday Position**
- Bought intraday: 50 shares
- Sell intraday: 50 shares
- **Result**: Allowed (intraday square-off)

**Scenario 3: Mixed Products**
- CNC holdings: 100 shares
- Intraday sell: 50 shares
- **Result**: Allowed (different product types)

---

## Security Best Practices

### Credential Management

**Environment Variables:**
All sensitive credentials stored in `.env` file:
```bash
WEBHOOK_SECRET=your_secret
DHAN_CLIENT_ID=1234567890
DHAN_ACCESS_TOKEN=eyJ0eXAi...
DHAN_TOTP_SECRET=ABCD1234...
TELEGRAM_BOT_TOKEN=123456:ABC...
```

**Git Protection:**
```gitignore
# .gitignore
.env
.env.local
.env.production
secrets.json
```

### Token Management

**Token Lifecycle:**
- Validity: 24 hours
- Auto-refresh: When <1 hour remaining
- Manual refresh: Via DHAN_CREDENTIALS_GUIDE.md

**Token Security:**
- Never log full tokens
- Rotate regularly
- Monitor expiry via health endpoint

### API Rate Limits

**Dhan API Limits:**
- Orders: 200/second
- Holdings: 5/second
- Market data: 1/second per symbol

**Webhook Service:**
- Max concurrent: 80 requests/second
- Auto-scaling: 0-10 instances
- Timeout: 60 seconds/request

---

## Advanced Order Scenarios

### Multi-Leg Bracket Order

Place entry + stop loss + target in single alert:

```json
{
  "secret": "GTcl4",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "sort_order": "1",
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "10",
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "instrument": "EQ",
      "productType": "I",
      "price": "0"
    },
    {
      "sort_order": "2",
      "transactionType": "S",
      "orderType": "SL-M",
      "quantity": "10",
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "instrument": "EQ",
      "productType": "I",
      "price": "0",
      "triggerPrice": "2450.00"
    },
    {
      "sort_order": "3",
      "transactionType": "S",
      "orderType": "LMT",
      "quantity": "10",
      "symbol": "RELIANCE",
      "exchange": "NSE",
      "instrument": "EQ",
      "productType": "I",
      "price": "2600.00"
    }
  ]
}
```

**Execution Order:**
1. Buy 10 RELIANCE @ market (entry)
2. Place stop loss @ ₹2450 trigger
3. Place target @ ₹2600 limit

### Conditional Orders

Use TradingView strategy conditions:

```pine
//@version=5
strategy("Conditional Order", overlay=true)

// Entry condition
longCondition = ta.crossover(ta.sma(close, 10), ta.sma(close, 20))

if longCondition
    strategy.entry("Long", strategy.long)
    alert('{"secret":"GTcl4","alertType":"multi_leg_order",...]', alert.freq_once_per_bar)
```

### Order Modification

To modify existing orders:
1. Cancel via Dhan web/app
2. Place new order via webhook
3. Or use Forever Orders for automated triggers

---

## Performance Monitoring

### Key Metrics

**Response Time:**
- Target: <500ms
- P95: <1000ms
- P99: <2000ms

**Success Rate:**
- Target: >99%
- Typical: 99.5-99.9%

**Order Execution:**
- Market orders: <2 seconds
- Limit orders: Variable (depends on price)

### Monitoring Tools

**Cloud Run Console:**
- Request count
- Error rate
- Latency percentiles
- Instance count
- Memory/CPU usage

**Telegram Notifications:**
- Real-time order status
- Error alerts
- Daily summaries

**CSV Logs:**
- Historical order data
- Performance analysis
- Debugging failed orders

