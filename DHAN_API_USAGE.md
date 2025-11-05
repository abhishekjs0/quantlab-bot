# Dhan API - Account Data & Market Data Guide

## Overview

This guide covers using Dhan REST APIs to fetch account data (holdings, positions, orders, trades) and market data (quotes, historical data).

---

## ✅ Quick Start

### 1. Check Your Token
```bash
python scripts/dhan_token_manager.py
```

### 2. Test API Access
```bash
python scripts/test_simple.py
```

### 3. View Your Account Data
```bash
python scripts/dhan_working.py
```

---

## 🔐 Authentication

All API requests require two headers:

```python
headers = {
    "access-token": "eyJ0eXAiOiJKV1QiLCJhbGc...",  # Your JWT token
    "dhanClientId": "1108351648"                      # Your client ID
}
```

**Token Source:** `DHAN_ACCESS_TOKEN` from `.env`
**Client ID Source:** `DHAN_CLIENT_ID` from `.env`

---

## 📊 Account Data APIs

### Base URL
```
https://api.dhan.co
```

### 1. Get Profile Information

```bash
GET /profile
```

**Python Example:**
```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

response = requests.get(
    "https://api.dhan.co/profile",
    headers=headers,
    timeout=10
)

data = response.json()
print(f"Client ID: {data['clientId']}")
print(f"Token Valid Until: {data['tokenValidity']}")
print(f"Active Segments: {data['activeSegments']}")
```

**Response Example:**
```json
{
  "clientId": "1108351648",
  "tokenValidity": "2025-11-06 20:24:48",
  "activeSegments": ["Equity", "Derivative", "Currency", "Commodity"],
  "dataPlans": "Active"
}
```

---

### 2. Get Holdings (Your Stocks)

```bash
GET /holdings
```

**Python Example:**
```python
import requests
import pandas as pd

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

response = requests.get(
    "https://api.dhan.co/holdings",
    headers=headers,
    timeout=10
)

holdings = response.json()

# Display holdings
for holding in holdings:
    symbol = holding['symbol']
    qty = holding['quantity']
    price = holding['price']
    value = holding['totalValue']
    print(f"{symbol:12} {qty:6} units @ ₹{price:10.2f} = ₹{value:12.2f}")

# Calculate totals
total_value = sum(h['totalValue'] for h in holdings)
total_qty = sum(h['quantity'] for h in holdings)
print(f"\nTotal: {total_qty} units worth ₹{total_value:,.2f}")
```

**Response Format:**
```json
[
  {
    "symbol": "SWIGGY",
    "quantity": 17,
    "price": 449.68,
    "totalValue": 7644.56,
    "dayChange": 5.2
  },
  {
    "symbol": "LT",
    "quantity": 1,
    "price": 3861.10,
    "totalValue": 3861.10,
    "dayChange": -1.2
  }
]
```

**Fields Explained:**
- `symbol` - Stock ticker (NSE symbol)
- `quantity` - Number of units held
- `price` - Current market price per unit
- `totalValue` - quantity × price
- `dayChange` - % change today

---

### 3. Get Open Positions

```bash
GET /positions
```

**Python Example:**
```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

response = requests.get(
    "https://api.dhan.co/positions",
    headers=headers,
    timeout=10
)

positions = response.json()

print(f"Total open positions: {len(positions)}")

for pos in positions:
    symbol = pos['symbol']
    qty = pos['quantity']
    entry_price = pos['entryPrice']
    current_price = pos['currentPrice']
    pnl = pos['pnl']
    pnl_pct = pos['pnlPercentage']
    
    print(f"{symbol:12} {qty:6} @ {entry_price:8.2f} → {current_price:8.2f} | "
          f"P&L: ₹{pnl:8.2f} ({pnl_pct:6.2f}%)")
```

**Response Format:**
```json
[
  {
    "symbol": "INFY",
    "quantity": 10,
    "entryPrice": 2850.50,
    "currentPrice": 2920.75,
    "pnl": 703.50,
    "pnlPercentage": 2.46,
    "tradingType": "BUY"
  }
]
```

**Fields Explained:**
- `symbol` - Stock ticker
- `quantity` - Number of units
- `entryPrice` - Purchase price
- `currentPrice` - Current market price
- `pnl` - Profit/Loss in rupees
- `pnlPercentage` - P&L as percentage

---

### 4. Get Pending Orders

```bash
GET /orders
```

**Python Example:**
```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

response = requests.get(
    "https://api.dhan.co/orders",
    headers=headers,
    timeout=10
)

orders = response.json()

print(f"Total pending orders: {len(orders)}")

for order in orders:
    symbol = order['symbol']
    order_type = order['orderType']  # BUY or SELL
    qty = order['quantity']
    price = order['price']
    status = order['status']
    
    print(f"{order_type:4} {symbol:12} {qty:6} @ ₹{price:8.2f} - {status}")
```

**Response Format:**
```json
[
  {
    "orderId": "1234567890",
    "symbol": "TCS",
    "orderType": "BUY",
    "quantity": 5,
    "price": 3850.50,
    "status": "PENDING",
    "orderTime": "2025-11-05 14:30:00"
  }
]
```

**Fields Explained:**
- `orderId` - Unique order identifier
- `symbol` - Stock ticker
- `orderType` - BUY or SELL
- `quantity` - Number of units
- `price` - Limit price
- `status` - PENDING, EXECUTED, CANCELLED, etc.
- `orderTime` - When order was placed

---

### 5. Get Trade History

```bash
GET /trades
```

**Python Example:**
```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

response = requests.get(
    "https://api.dhan.co/trades",
    headers=headers,
    timeout=10
)

trades = response.json()

print(f"Total trades: {len(trades)}")

for trade in trades:
    symbol = trade['symbol']
    qty = trade['quantity']
    price = trade['executedPrice']
    trade_type = trade['tradeType']  # BUY or SELL
    timestamp = trade['executedTime']
    
    print(f"{trade_type:4} {symbol:12} {qty:6} @ ₹{price:8.2f} at {timestamp}")
```

**Response Format:**
```json
[
  {
    "tradeId": "9876543210",
    "symbol": "INFY",
    "tradeType": "BUY",
    "quantity": 10,
    "executedPrice": 2850.50,
    "executedTime": "2025-11-05 14:45:30"
  }
]
```

---

## 📈 Market Data

### Live Quotes (WebSocket)

**NOT available via REST API** - Must use WebSocket for real-time quotes.

```python
# WebSocket example (advanced)
import websocket
import json

def on_message(ws, message):
    data = json.loads(message)
    print(f"LTP: {data['ltp']}, Bid: {data['bid']}, Ask: {data['ask']}")

ws = websocket.WebSocketApp(
    "wss://api-feed.dhan.co",
    on_message=on_message
)
ws.run_forever()
```

**See:** `scripts/dhan_live_feed.py` for full implementation.

### Historical Data

Historical OHLC data can be accessed via wrapper:

```python
from scripts.dhan_market_data_rest import DhanMarketDataFetcher

fetcher = DhanMarketDataFetcher()

# Note: Actual implementation depends on Dhan's available endpoints
# Currently REST API doesn't expose historical data directly
```

---

## 🛠️ Complete Example: Daily Report

```python
#!/usr/bin/env python3
"""
Generate daily account summary report
"""

import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

class DhanReporter:
    def __init__(self):
        self.headers = {
            "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
            "dhanClientId": os.getenv("DHAN_CLIENT_ID")
        }
        self.base_url = "https://api.dhan.co"
    
    def get_profile(self):
        r = requests.get(f"{self.base_url}/profile", headers=self.headers, timeout=10)
        return r.json()
    
    def get_holdings(self):
        r = requests.get(f"{self.base_url}/holdings", headers=self.headers, timeout=10)
        return r.json()
    
    def get_positions(self):
        r = requests.get(f"{self.base_url}/positions", headers=self.headers, timeout=10)
        return r.json()
    
    def get_orders(self):
        r = requests.get(f"{self.base_url}/orders", headers=self.headers, timeout=10)
        return r.json()
    
    def generate_report(self):
        print(f"\n{'='*70}")
        print(f"DHAN ACCOUNT REPORT - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        # Profile
        profile = self.get_profile()
        print(f"\n📊 PROFILE:")
        print(f"  Client ID: {profile['clientId']}")
        print(f"  Token Valid Until: {profile['tokenValidity']}")
        
        # Holdings
        holdings = self.get_holdings()
        print(f"\n📈 HOLDINGS ({len(holdings)} stocks):")
        total_value = 0
        for h in holdings:
            print(f"  {h['symbol']:12} {h['quantity']:6} units @ ₹{h['price']:10.2f}")
            total_value += h['totalValue']
        print(f"  {'TOTAL':12} {'':6} ₹{total_value:10.2f}")
        
        # Positions
        positions = self.get_positions()
        print(f"\n📊 OPEN POSITIONS ({len(positions)} trades):")
        total_pnl = 0
        for p in positions:
            pnl_sign = "+" if p['pnl'] > 0 else ""
            print(f"  {p['symbol']:12} {p['quantity']:6} {pnl_sign}₹{p['pnl']:8.2f} "
                  f"({p['pnlPercentage']:+6.2f}%)")
            total_pnl += p['pnl']
        if positions:
            pnl_sign = "+" if total_pnl > 0 else ""
            print(f"  {'TOTAL':12} {pnl_sign}₹{total_pnl:8.2f}")
        
        # Orders
        orders = self.get_orders()
        print(f"\n📋 PENDING ORDERS ({len(orders)}):")
        if orders:
            for o in orders:
                print(f"  {o['orderType']:4} {o['symbol']:12} {o['quantity']:6} "
                      f"@ ₹{o['price']:8.2f}")
        else:
            print("  None")
        
        print(f"\n{'='*70}\n")

if __name__ == "__main__":
    reporter = DhanReporter()
    reporter.generate_report()
```

**Run it:**
```bash
python daily_report.py
```

---

## 🔍 Error Handling

### Common HTTP Status Codes

| Code | Meaning | Solution |
|------|---------|----------|
| 200 | Success | Proceed normally |
| 400 | Bad Request | Check parameters |
| 401 | Unauthorized | Refresh token, verify headers |
| 403 | Forbidden | Check permissions |
| 404 | Not Found | Wrong endpoint |
| 500 | Server Error | Dhan API issue, retry later |
| 503 | Service Unavailable | Dhan servers down |

### Error Handling Example

```python
import requests

headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

try:
    response = requests.get(
        "https://api.dhan.co/holdings",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        holdings = response.json()
        print(f"✅ Got {len(holdings)} holdings")
    
    elif response.status_code == 401:
        print("❌ Token expired or invalid")
        print("   Run: python scripts/dhan_login_auto_improved.py")
    
    elif response.status_code == 500:
        print("❌ Dhan API error")
        print(f"   Response: {response.text}")
    
    else:
        print(f"❌ HTTP {response.status_code}: {response.text}")

except requests.Timeout:
    print("❌ Request timeout - Dhan API slow or unreachable")

except Exception as e:
    print(f"❌ Error: {e}")
```

---

## 📡 API Limits

- **Rate Limiting:** Check Dhan documentation for rate limits
- **Timeout:** Set reasonable timeouts (10 seconds recommended)
- **Batch Size:** Avoid huge payloads
- **Frequency:** Don't hammer the API - reasonable polling intervals

---

## 🔗 Integration with Backtesting

Use real account data in your backtester:

```python
from scripts.dhan_working import DhanAccountManager

# Get real holdings
manager = DhanAccountManager()
holdings = manager.get_holdings()

# Use in backtest
for holding in holdings:
    symbol = holding['symbol']
    qty = holding['quantity']
    # ... add to portfolio for backtesting
```

---

## 📚 API Reference Summary

| Endpoint | Method | Purpose | Parameters |
|----------|--------|---------|------------|
| `/profile` | GET | Account info | None |
| `/holdings` | GET | Your stocks | None |
| `/positions` | GET | Open trades | None |
| `/orders` | GET | Pending orders | None |
| `/trades` | GET | Trade history | None |

---

## 🛠️ Testing APIs

### Quick Test
```bash
python scripts/test_simple.py
```

### Detailed Test
```python
# test_apis.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

base_url = "https://api.dhan.co"
headers = {
    "access-token": os.getenv("DHAN_ACCESS_TOKEN"),
    "dhanClientId": os.getenv("DHAN_CLIENT_ID")
}

endpoints = [
    ("/profile", "Account Profile"),
    ("/holdings", "Holdings"),
    ("/positions", "Positions"),
    ("/orders", "Orders"),
    ("/trades", "Trades")
]

print("Testing all endpoints...\n")

for endpoint, name in endpoints:
    try:
        r = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            count = len(data) if isinstance(data, list) else 1
            print(f"✅ {name:20} - {count} items")
        else:
            print(f"❌ {name:20} - HTTP {r.status_code}")
    except Exception as e:
        print(f"❌ {name:20} - {e}")
```

Run: `python test_apis.py`

---

## 🔒 Security Notes

✅ **DO:**
- Store token in `.env`
- Use HTTPS only
- Validate responses
- Handle errors gracefully
- Set timeouts

❌ **DON'T:**
- Hardcode tokens
- Log tokens to console
- Send over HTTP
- Share API responses publicly
- Trust unvalidated data

---

## 📊 Data Processing Tips

### Convert to Pandas DataFrame
```python
import pandas as pd

holdings = fetcher.get_holdings()
df = pd.DataFrame(holdings)
print(df.to_string(index=False))
```

### Calculate Portfolio Metrics
```python
def portfolio_stats(holdings):
    total_value = sum(h['totalValue'] for h in holdings)
    avg_price = total_value / sum(h['quantity'] for h in holdings)
    
    return {
        'total_value': total_value,
        'avg_price': avg_price,
        'num_holdings': len(holdings)
    }
```

### Filter Holdings
```python
# Get only stocks with gain
gainers = [h for h in holdings if h['dayChange'] > 0]

# Get top holdings by value
top = sorted(holdings, key=lambda x: x['totalValue'], reverse=True)[:5]
```

---

## 🎯 Common Use Cases

### 1. Daily Report
```bash
python scripts/dhan_working.py
```

### 2. Monitor Holdings
```python
# Monitor price changes
import time

while True:
    holdings = fetcher.get_holdings()
    for h in holdings:
        if abs(h['dayChange']) > 2:
            print(f"Alert: {h['symbol']} moved {h['dayChange']}%")
    time.sleep(60)
```

### 3. Check Open P&L
```python
positions = fetcher.get_positions()
total_pnl = sum(p['pnl'] for p in positions)
print(f"Total P&L: ₹{total_pnl:,.2f}")
```

### 4. Execute Backtests
```python
# Use real account data
holdings = fetcher.get_holdings()
positions = fetcher.get_positions()
# ... run backtest with real data
```

---

## ❓ FAQ

**Q: Can I access market data via REST?**
A: No - only account data. Use WebSocket for live quotes.

**Q: How often should I call the APIs?**
A: Reasonable intervals - not too frequent. Depends on your use case.

**Q: What's the difference between holdings and positions?**
A: Holdings = stocks you own. Positions = active trades (derivatives).

**Q: Can I modify orders via API?**
A: Check Dhan documentation - may have additional endpoints.

**Q: Is API data real-time?**
A: Yes for REST endpoints, but has slight delay. WebSocket is truly real-time.

**Q: Can I access other accounts?**
A: No, only the account for this client ID.

**Q: What if API is slow?**
A: Increase timeout, add retry logic, or check Dhan status.

---

## 🚀 Next Steps

1. **Test Your API Access:**
   ```bash
   python scripts/test_simple.py
   ```

2. **View Your Holdings:**
   ```bash
   python scripts/dhan_working.py
   ```

3. **Build Custom Scripts:**
   Use the examples above as templates

4. **Integrate with Your System:**
   Fetch data regularly for your backtester or reporting

5. **Handle Edge Cases:**
   Add error handling for production use

---

## ✨ Summary

✅ 5 REST API endpoints available  
✅ Complete account data access  
✅ Python examples provided  
✅ Error handling patterns shown  
✅ WebSocket for live data  
✅ Ready to integrate with backtesting  

You now have full API access to your Dhan account!
