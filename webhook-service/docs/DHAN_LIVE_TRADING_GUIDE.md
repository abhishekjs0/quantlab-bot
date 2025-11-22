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

Dhan tokens expire after ~7 days. Update when needed:

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
