# Webhook Monitoring & CSV Logging Guide

## 📊 How to Monitor Your Webhook

### 1. Real-time Log Monitoring

**Watch logs as they happen:**
```bash
tail -f webhook_server.log
```

**View last 50 lines:**
```bash
tail -50 webhook_server.log
```

**View last 100 lines:**
```bash
tail -100 webhook_server.log
```

**Search for specific symbol:**
```bash
grep "RELIANCE" webhook_server.log
```

**Search for errors:**
```bash
grep "ERROR" webhook_server.log
```

**Filter by today's date:**
```bash
grep "2025-11-20" webhook_server.log
```

### 2. CSV Order Log

**Location:** `webhook_orders.csv`

All orders are automatically logged to CSV with these columns:
- `timestamp` - When order was received
- `alert_type` - Type of alert (multi_leg_order, etc.)
- `symbol` - Stock symbol
- `exchange` - Exchange (NSE, BSE, etc.)
- `transaction` - B (Buy) or S (Sell)
- `quantity` - Number of shares
- `order_type` - MKT, LMT, etc.
- `product_type` - I (Intraday), C (CNC), etc.
- `price` - Order price
- `status` - Order status (test_mode, success, failed, etc.)
- `order_id` - Dhan order ID (if executed)
- `message` - Additional details

**View CSV in terminal:**
```bash
# View all orders
cat webhook_orders.csv

# View last 10 orders
tail -10 webhook_orders.csv

# View with nice formatting (requires column command)
column -t -s',' webhook_orders.csv | tail -20

# Open in Excel/Numbers
open webhook_orders.csv
```

**View CSV with pandas:**
```bash
python3 << EOF
import pandas as pd
df = pd.read_csv('webhook_orders.csv')
print(df.tail(10))  # Last 10 orders
print("\nToday's orders:")
print(df[df['timestamp'].str.contains('2025-11-20')])
EOF
```

### 3. Server Status Commands

**Check if server is running:**
```bash
curl http://localhost:80/health
```

**Check port 80 is in use:**
```bash
lsof -i :80
```

**View server process:**
```bash
ps aux | grep webhook_server
```

**Kill server:**
```bash
lsof -ti :80 | xargs kill -9
```

**Restart server:**
```bash
./start_webhook.sh
```

### 4. Live Order Monitoring Dashboard

**Create a simple monitoring script:**
```bash
#!/bin/bash
# Save as monitor_webhook.sh

while true; do
    clear
    echo "=== WEBHOOK SERVER STATUS ==="
    echo ""
    
    # Server status
    if curl -s http://localhost:80/health > /dev/null 2>&1; then
        echo "✅ Server: RUNNING"
    else
        echo "❌ Server: DOWN"
    fi
    
    echo ""
    echo "=== LAST 5 ORDERS ==="
    tail -6 webhook_orders.csv | tail -5 | column -t -s','
    
    echo ""
    echo "=== RECENT LOG ENTRIES ==="
    tail -5 webhook_server.log
    
    sleep 5
done
```

**Make it executable and run:**
```bash
chmod +x monitor_webhook.sh
./monitor_webhook.sh
```

### 5. Testing Mode vs Live Mode

**Current setting: ENABLE_DHAN=false (Test Mode)** ✅

In **test mode**:
- Orders are logged to CSV with status `test_mode`
- No actual orders placed on Dhan
- Perfect for testing TradingView integration
- No risk to your trading account

In **live mode** (ENABLE_DHAN=true):
- Orders are actually executed on Dhan
- CSV logs include actual order IDs
- Real money at risk ⚠️

**Switch to live mode:**
```bash
# Edit .env file
ENABLE_DHAN=true

# Restart server
lsof -ti :80 | xargs kill -9
./start_webhook.sh
```

### 6. Analyzing CSV Data

**Count orders by symbol:**
```bash
awk -F',' 'NR>1 {print $3}' webhook_orders.csv | sort | uniq -c | sort -rn
```

**Count buy vs sell:**
```bash
awk -F',' 'NR>1 {print $5}' webhook_orders.csv | sort | uniq -c
```

**Failed orders:**
```bash
grep "failed" webhook_orders.csv
```

**Test mode orders:**
```bash
grep "test_mode" webhook_orders.csv
```

**Successful orders:**
```bash
grep "success" webhook_orders.csv
```

### 7. Port 80 Requirements

**⚠️ IMPORTANT:** TradingView only allows port 80 (HTTP) or 443 (HTTPS)

**Check if port 80 is available:**
```bash
sudo lsof -i :80
```

**Start server on port 80 (requires sudo):**
```bash
sudo /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python webhook_server.py
```

**Or use ngrok (recommended for testing):**
```bash
# Start server on any port (e.g., 8000)
python webhook_server.py  # Uses port 80 from .env

# In another terminal
ngrok http 80

# Use the http URL: http://abc123.ngrok.io/webhook
```

### 8. Webhook Testing

**Test with curl:**
```bash
curl -X POST http://localhost:80/webhook \
  -H "Content-Type: text/plain" \
  -d '{"secret":"GTcl4","alertType":"multi_leg_order","order_legs":[{"transactionType":"B","orderType":"MKT","quantity":"1","exchange":"NSE","symbol":"RELIANCE","instrument":"EQ","productType":"I","sort_order":"1","price":"0","meta":{"interval":"1D","time":"2025-11-20T09:15:00Z","timenow":"2025-11-20T16:05:00Z"}}]}'
```

**Test with Python:**
```bash
python test_webhook_simple.py
```

### 9. Common Monitoring Patterns

**Watch for errors in real-time:**
```bash
tail -f webhook_server.log | grep --line-buffered ERROR
```

**Monitor specific symbol:**
```bash
tail -f webhook_orders.csv | grep "RELIANCE"
```

**Count today's orders:**
```bash
grep "2025-11-20" webhook_orders.csv | wc -l
```

**Last order timestamp:**
```bash
tail -1 webhook_orders.csv | awk -F',' '{print $1}'
```

### 10. Backup & Archive

**Backup CSV logs:**
```bash
# Daily backup
cp webhook_orders.csv webhook_orders_backup_$(date +%Y%m%d).csv

# Compress old logs
gzip webhook_orders_backup_*.csv
```

**Rotate logs:**
```bash
# Move current log and start fresh
mv webhook_server.log webhook_server.log.$(date +%Y%m%d)
mv webhook_orders.csv webhook_orders.csv.$(date +%Y%m%d)

# Server will create new files automatically
```

## Quick Reference

```bash
# View real-time logs
tail -f webhook_server.log

# View CSV orders
tail -20 webhook_orders.csv

# Check server health
curl http://localhost:80/health

# Count today's orders
grep $(date +%Y-%m-%d) webhook_orders.csv | wc -l

# View errors
grep ERROR webhook_server.log | tail -20

# Restart server
lsof -ti :80 | xargs kill -9 && ./start_webhook.sh
```

## CSV Analysis with Pandas

```python
import pandas as pd

# Load orders
df = pd.read_csv('webhook_orders.csv')

# Basic stats
print(f"Total orders: {len(df)}")
print(f"Test mode orders: {len(df[df['status'] == 'test_mode'])}")
print(f"Live orders: {len(df[df['status'] == 'success'])}")

# Orders by symbol
print("\nOrders by symbol:")
print(df['symbol'].value_counts())

# Buy vs Sell
print("\nBuy vs Sell:")
print(df['transaction'].value_counts())

# Today's orders
df['timestamp'] = pd.to_datetime(df['timestamp'])
today = df[df['timestamp'].dt.date == pd.Timestamp.now().date()]
print(f"\nToday's orders: {len(today)}")

# Export summary
summary = df.groupby(['symbol', 'transaction']).size().reset_index(name='count')
summary.to_csv('order_summary.csv', index=False)
```

---

**Your Current Setup:**
- Logs: `webhook_server.log` (text log)
- CSV: `webhook_orders.csv` (structured data)
- Mode: Test (ENABLE_DHAN=false)
- Port: 80 (TradingView compatible)
- Secret: GTcl4
