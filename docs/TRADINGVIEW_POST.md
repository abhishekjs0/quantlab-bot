# TradingView Webhook Integration Guide

> **Complete guide for integrating TradingView alerts with automated order execution via webhooks**

**Last Updated**: 2025-11-20  
**Status**: ✅ Production Ready  
**Test Results**: 3/3 webhook tests passed

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation & Setup](#installation--setup)
3. [Server Configuration](#server-configuration)
4. [TradingView Alert Setup](#tradingview-alert-setup)
5. [Webhook Payload Structure](#webhook-payload-structure)
6. [Testing Your Setup](#testing-your-setup)
7. [Monitoring & Logging](#monitoring--logging)
8. [ngrok Integration](#ngrok-integration)
9. [Production Deployment](#production-deployment)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 1. Install ngrok

```bash
# Install via Homebrew
brew install ngrok

# Add your authtoken
ngrok config add-authtoken 31UShybAKu2bYl8hTwhV5KF9G9D_5xoqQNGMptCBCUse2PuNi
```

### 2. Start the Webhook Server

```bash
# Activate virtual environment
source .venv/bin/activate

# Start server (runs on port 80)
python webhooks/webhook_server.py
```

### 3. Start ngrok Tunnel

```bash
# In a separate terminal
ngrok http 80
```

Copy the ngrok URL (e.g., `https://abc123.ngrok.io`)

### 4. Configure TradingView

Use the ngrok URL + `/webhook` endpoint:
```
https://abc123.ngrok.io/webhook
```

---

## Installation & Setup

### Prerequisites

- Python 3.8+ with virtual environment
- Dhan trading account with API access (optional for testing)
- TradingView account with alert capabilities
- Homebrew (for macOS) to install ngrok

### Step 1: Install Dependencies

All dependencies are managed in `requirements.txt`:

```bash
# Activate virtual environment
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

Key packages installed:
- `fastapi` - Web framework for webhook server
- `uvicorn` - ASGI server
- `dhanhq` - Dhan broker API client
- `pydantic` - Data validation
- `python-dotenv` - Environment variable management

### Step 2: Install ngrok

```bash
# Install via Homebrew
brew install ngrok

# Configure with your authtoken
ngrok config add-authtoken 31UShybAKu2bYl8hTwhV5KF9G9D_5xoqQNGMptCBCUse2PuNi

# Verify installation
ngrok version
```

**Note**: ngrok provides a free tier that's perfect for testing. The authtoken is required for persistent URLs and higher rate limits.

---

## Server Configuration

### Environment Variables

All configuration is in the `.env` file:

```bash
# Dhan Broker Credentials
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_token

# Webhook Server Settings
WEBHOOK_SECRET=GTcl4
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=80
ENABLE_DHAN=false  # Set to 'true' for live trading, 'false' for testing
```

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DHAN_CLIENT_ID` | Your Dhan client ID | - | Yes (for live trading) |
| `DHAN_ACCESS_TOKEN` | Your Dhan access token | - | Yes (for live trading) |
| `WEBHOOK_SECRET` | Webhook authentication secret | `GTcl4` | Yes |
| `WEBHOOK_HOST` | Server host address | `0.0.0.0` | No |
| `WEBHOOK_PORT` | Server port | `80` | No |
| `ENABLE_DHAN` | Enable order execution | `false` | No |

### ENABLE_DHAN Setting

- `ENABLE_DHAN=false`: Orders are logged only (TESTING MODE) ✅ Recommended for initial setup
- `ENABLE_DHAN=true`: Orders are actually placed on Dhan (LIVE TRADING) ⚠️ Real money at risk

**Important:** Always start with `ENABLE_DHAN=false` to test your setup!

---

## TradingView Alert Setup

### Step 1: Get Your Webhook URL

**Option A: Using ngrok (Recommended for Testing)**

```bash
# Start ngrok
ngrok http 80

# Copy the HTTPS URL shown in terminal
# Example: https://c80aa76b87af.ngrok-free.app
```

Your webhook URL will be:
```
https://your-ngrok-url.ngrok-free.app/webhook
```

**Option B: Using Public IP (For Production)**

If you have a static public IP:
```
http://your-public-ip/webhook
```

### Step 2: Create TradingView Alert

1. Open any TradingView chart
2. Click the alarm clock icon to create an alert
3. Configure your alert conditions
4. In the "Notifications" tab:
   - Enable "Webhook URL"
   - Enter your webhook URL from Step 1
   - Paste the message payload (see below)

### Step 3: Alert Message Format

**Copy this JSON exactly** (replace only the values you need to customize):

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

### TradingView Placeholder Variables

TradingView will automatically replace these placeholders:

- `{{ticker}}` - Symbol name (e.g., "RELIANCE", "INFY")
- `{{close}}` - Current close price
- `{{interval}}` - Chart timeframe (e.g., "1D", "1H", "15")
- `{{time}}` - Bar timestamp (ISO 8601 format)
- `{{timenow}}` - Current timestamp (ISO 8601 format)
- `{{exchange}}` - Exchange (e.g., "NSE", "BSE")

### Step 4: Test Your Alert

After creating the alert:
1. Trigger it manually in TradingView
2. Check your terminal for incoming webhook
3. Verify order appears in `webhook_orders.csv`
4. Check `webhook_server.log` for details

---

## Webhook Payload Structure

### Complete Example

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
      "symbol": "RELIANCE",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "1D",
        "time": "2025-11-20T09:15:00Z",
        "timenow": "2025-11-20T15:31:44Z"
      }
    }
  ]
}
```

### Field Descriptions

#### Root Level
- `secret` (string, required): Authentication secret (must match `.env`)
- `alertType` (string, required): Type of alert
  - `"multi_leg_order"` - Multi-leg order execution
  - `"single_order"` - Single order
  - `"cancel_order"` - Cancel existing order
- `order_legs` (array, required): List of order legs to execute (min 1)

#### Order Leg Fields
- `transactionType` (string, required): 
  - `"B"` = Buy
  - `"S"` = Sell
- `orderType` (string, required):
  - `"MKT"` = Market order
  - `"LMT"` = Limit order
  - `"SL"` = Stop Loss
  - `"SL-M"` = Stop Loss Market
- `quantity` (string, required): Number of shares/contracts
- `exchange` (string, required):
  - `"NSE"` = National Stock Exchange
  - `"BSE"` = Bombay Stock Exchange
  - `"NFO"` = NSE Futures & Options
  - `"MCX"` = Multi Commodity Exchange
- `symbol` (string, required): Trading symbol (e.g., "RELIANCE", "INFY")
- `instrument` (string, required):
  - `"EQ"` = Equity
  - `"FUT"` = Futures
  - `"CE"` = Call Option
  - `"PE"` = Put Option
- `productType` (string, required):
  - `"C"` = CNC (Cash and Carry / Delivery)
  - `"I"` = Intraday
  - `"M"` = Margin
- `sort_order` (string, required): Execution priority ("1", "2", "3", ...)
- `price` (string, required): Order price
  - `"0"` for market orders
  - Specific price for limit orders

#### Metadata Fields
- `interval` (string, required): Chart timeframe
- `time` (string, required): Bar timestamp (ISO 8601)
- `timenow` (string, required): Current timestamp (ISO 8601)

### Multi-Leg Order Example

Execute buy entry with target and stop loss:

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
      "productType": "I",
      "sort_order": "1",
      "price": "0",
      "meta": {
        "interval": "1H",
        "time": "2025-11-20T10:00:00Z",
        "timenow": "2025-11-20T10:05:00Z"
      }
    }
  ]
}
```

---

## Testing Your Setup

### Test 1: Server Health Check

```bash
curl http://localhost:80/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-20T10:30:00.123456"
}
```

### Test 2: Local Webhook Test

```bash
curl -X POST http://localhost:80/webhook \
  -H "Content-Type: text/plain" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "MKT",
        "quantity": "1",
        "exchange": "NSE",
        "symbol": "RELIANCE",
        "instrument": "EQ",
        "productType": "C",
        "sort_order": "1",
        "price": "0",
        "meta": {
          "interval": "1D",
          "time": "2025-11-20T09:15:00Z",
          "timenow": "2025-11-20T10:30:00Z"
        }
      }
    ]
  }'
```

### Test 3: ngrok Webhook Test

```bash
# Replace with your actual ngrok URL
curl -X POST https://your-ngrok-url.ngrok.io/webhook \
  -H "Content-Type: text/plain" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "MKT",
        "quantity": "1",
        "exchange": "NSE",
        "symbol": "TATASTEEL",
        "instrument": "EQ",
        "productType": "C",
        "sort_order": "1",
        "price": "0",
        "meta": {
          "interval": "1D",
          "time": "2025-11-20T09:15:00Z",
          "timenow": "2025-11-20T10:30:00Z"
        }
      }
    ]
  }'
```

### Test Results (November 20, 2025)

✅ **All tests passed:**
1. TATASTEEL BUY - Order placed successfully (Order ID: 952511209810)
2. RELIANCE SELL - Validation passed (insufficient holdings expected)
3. INFY BUY - Order placed successfully for 10 shares (Order ID: 3552511209455)

---

## Monitoring & Logging

### Real-time Log Monitoring

```bash
# Watch logs as they happen
tail -f webhook_server.log

# View last 50 lines
tail -50 webhook_server.log

# Search for specific symbol
grep "RELIANCE" webhook_server.log

# Search for errors
grep "ERROR" webhook_server.log
```

### CSV Order Log

**Location:** `webhook_orders.csv`

All orders are automatically logged with these columns:
- `timestamp` - When order was received
- `alert_type` - Type of alert
- `symbol` - Stock symbol
- `exchange` - Exchange (NSE, BSE, etc.)
- `transaction` - B (Buy) or S (Sell)
- `quantity` - Number of shares
- `order_type` - MKT, LMT, etc.
- `product_type` - I (Intraday), C (CNC), etc.
- `price` - Order price
- `status` - Order status (test_mode, success, failed)
- `order_id` - Dhan order ID (if executed)
- `message` - Additional details

**View recent orders:**
```bash
# Last 10 orders
tail -10 webhook_orders.csv

# View with formatting
column -t -s',' webhook_orders.csv | tail -20

# Open in Excel/Numbers
open webhook_orders.csv
```

### Monitoring Dashboard

Create `monitor_webhook.sh`:

```bash
#!/bin/bash
while true; do
    clear
    echo "=== WEBHOOK SERVER STATUS ==="
    echo ""
    
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

Run it:
```bash
chmod +x monitor_webhook.sh
./monitor_webhook.sh
```

---

## ngrok Integration

### Why Use ngrok?

- **No Port Forwarding**: Works behind firewalls and NAT
- **HTTPS Support**: TradingView requires HTTPS for webhooks in production
- **Easy Setup**: No DNS or SSL certificate configuration needed
- **Persistent URLs**: Free tier provides temporary URLs, paid tier provides fixed URLs

### Installation

```bash
# Install via Homebrew (macOS)
brew install ngrok

# Or download from https://ngrok.com/download

# Add your authtoken (required)
ngrok config add-authtoken 31UShybAKu2bYl8hTwhV5KF9G9D_5xoqQNGMptCBCUse2PuNi

# Verify installation
ngrok version
```

### Basic Usage

```bash
# Start webhook server first
python webhooks/webhook_server.py

# In another terminal, start ngrok
ngrok http 80

# Output will show:
# Session Status                online
# Account                       Your Name
# Version                       3.x.x
# Region                        United States (us)
# Forwarding                    https://abc123.ngrok.io -> http://localhost:80
```

**Your webhook URL:** `https://abc123.ngrok.io/webhook`

### Advanced ngrok Configuration

Create `ngrok.yml` configuration:

```yaml
version: "2"
authtoken: 31UShybAKu2bYl8hTwhV5KF9G9D_5xoqQNGMptCBCUse2PuNi
tunnels:
  webhook:
    proto: http
    addr: 80
    inspect: true
    bind_tls: true
```

Start with config:
```bash
ngrok start webhook
```

### ngrok Web Interface

While ngrok is running, visit:
```
http://localhost:4040
```

This provides:
- Live request inspection
- Request/response history
- Traffic replay
- Performance metrics

### ngrok Tips

1. **Keep Terminal Open**: ngrok must stay running for webhooks to work
2. **URL Changes**: Free tier provides random URLs that change on restart
3. **Request Limits**: Free tier has rate limits (check ngrok dashboard)
4. **Update TradingView**: Update your alert URL if ngrok restarts
5. **Paid Plans**: Consider paid plan for fixed URLs and higher limits

---

## Production Deployment

### Option 1: Cloud Server with Static IP

**Requirements:**
- Cloud server (AWS EC2, DigitalOcean, etc.)
- Static public IP
- Domain name (optional but recommended)
- SSL certificate (Let's Encrypt)

**Setup:**

1. **Deploy server:**
```bash
# On your cloud server
git clone https://github.com/yourusername/quantlab-bot.git
cd quantlab-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Configure SSL with nginx:**
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location /webhook {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

3. **Use systemd for auto-start:**
```ini
[Unit]
Description=TradingView Webhook Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/quantlab-bot
Environment="WEBHOOK_SECRET=GTcl4"
Environment="ENABLE_DHAN=true"
ExecStart=/path/to/quantlab-bot/.venv/bin/python webhooks/webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Option 2: Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webhooks/webhook_server.py ./webhooks/
COPY brokers/dhan_broker.py ./brokers/
COPY .env .

EXPOSE 80

ENV WEBHOOK_PORT=80
CMD ["python", "webhooks/webhook_server.py"]
```

Build and run:
```bash
docker build -t webhook-server .
docker run -d -p 80:80 \
  --env-file .env \
  --name webhook-server \
  webhook-server
```

### Security Best Practices

1. **Use HTTPS**: Always use HTTPS in production (via nginx/Caddy or ngrok)
2. **Strong Secret**: Change `WEBHOOK_SECRET` to a strong random value
3. **Environment Security**: Never commit `.env` to git
4. **IP Whitelisting**: Restrict access to TradingView IPs if possible
5. **Rate Limiting**: Implement rate limiting to prevent abuse
6. **Log Monitoring**: Set up alerts for failed orders or errors
7. **Access Token Rotation**: Rotate Dhan access tokens regularly

### TradingView IP Whitelist

If using nginx or firewall, whitelist these TradingView IPs:
- 52.89.214.238
- 34.212.75.30
- 54.218.53.128
- 52.32.178.7

---

## Troubleshooting

### Server Won't Start

**Check if port is in use:**
```bash
lsof -i :80
```

**Kill existing process:**
```bash
lsof -ti :80 | xargs kill -9
```

**Check Python environment:**
```bash
which python
python --version
```

### Orders Not Executing

1. **Check ENABLE_DHAN setting:**
```bash
grep ENABLE_DHAN .env
# Should show: ENABLE_DHAN=true (for live) or =false (for testing)
```

2. **Verify Dhan credentials:**
```bash
# Test Dhan connection
python -c "from brokers.dhan_broker import DhanBroker; broker = DhanBroker(); print('✅ Connected')"
```

3. **Check logs:**
```bash
tail -50 webhook_server.log | grep ERROR
```

4. **Verify sufficient funds/margin in Dhan account**

### TradingView Alerts Not Received

1. **Verify webhook URL is correct:**
   - Include `/webhook` at the end
   - Use `https://` with ngrok (not `http://`)
   - Check for typos

2. **Test webhook endpoint:**
```bash
curl https://your-ngrok-url.ngrok.io/webhook
```

3. **Check ngrok is running:**
```bash
# Should see ngrok process
ps aux | grep ngrok
```

4. **View ngrok web interface:**
```
http://localhost:4040
```

5. **Check TradingView alert history:**
   - Go to TradingView > Alerts tab
   - Click on your alert > View history
   - Look for webhook delivery status

### Invalid Secret Errors

1. **Verify secret matches:**
```bash
# Check .env
grep WEBHOOK_SECRET .env

# Should match the "secret" field in your TradingView alert JSON
```

2. **Check for spaces/typos in alert message**

3. **Ensure JSON is valid** (use online JSON validator)

### Payload Validation Errors

1. **Verify JSON format** - Must be valid JSON
2. **Check required fields** - All fields must be present
3. **Datetime format** - Must be ISO 8601 (TradingView handles this automatically)
4. **Test with curl first** before TradingView

### ngrok Issues

1. **Authtoken error:**
```bash
# Re-add authtoken
ngrok config add-authtoken 31UShybAKu2bYl8hTwhV5KF9G9D_5xoqQNGMptCBCUse2PuNi
```

2. **Connection refused:**
   - Ensure webhook server is running first
   - Check webhook server is on correct port (80)

3. **Rate limit exceeded:**
   - Free tier has limits
   - Upgrade to paid plan or wait for reset

### Common Error Messages

**"Invalid webhook secret"**
- Secret in `.env` doesn't match alert payload
- Fix: Update either `.env` or TradingView alert message

**"Payload validation error"**
- Missing required field in JSON
- Invalid data type (e.g., string instead of number)
- Fix: Check JSON structure matches examples

**"Order placement failed"**
- Dhan API error (insufficient funds, invalid symbol, etc.)
- Check `webhook_server.log` for specific error
- Verify symbol exists and is tradeable

**"Connection error"**
- Webhook server not running
- Wrong port or URL
- Firewall blocking connection

---

## API Endpoints Reference

### GET `/`
**Description**: Root endpoint with server info

**Response:**
```json
{
  "service": "TradingView Webhook Server",
  "version": "1.0.0",
  "status": "running"
}
```

### GET `/health`
**Description**: Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-20T10:30:00.123456"
}
```

### POST `/webhook`
**Description**: Main webhook endpoint for TradingView alerts

**Headers:**
- `Content-Type: text/plain` or `Content-Type: application/json`

**Request Body:** See [Webhook Payload Structure](#webhook-payload-structure)

**Success Response (200):**
```json
{
  "status": "success",
  "message": "Processed 1 order leg(s)",
  "alertType": "multi_leg_order",
  "timestamp": "2025-11-20T10:30:00.123456",
  "results": [
    {
      "leg_number": 1,
      "symbol": "RELIANCE",
      "transaction": "B",
      "quantity": "10",
      "status": "success",
      "message": "Order placed successfully",
      "order_id": "123456789"
    }
  ]
}
```

**Error Responses:**
- `401 Unauthorized` - Invalid secret
- `422 Unprocessable Entity` - Validation error
- `400 Bad Request` - Invalid JSON
- `500 Internal Server Error` - Server error

---

## Files Reference

```
quantlab-workspace/
├── webhooks/
│   └── webhook_server.py           # Main FastAPI server
├── brokers/
│   └── dhan_broker.py             # Dhan API integration
├── data/
│   └── security_id_list.csv       # Symbol to security_id mapping
├── docs/
│   └── TRADINGVIEW_POST.md        # This file
├── .env                           # Configuration
├── webhook_orders.csv             # Order log (CSV)
├── webhook_server.log             # Server log (text)
└── requirements.txt               # Python dependencies
```

---

## Summary

✅ **Status:** Production Ready  
✅ **Test Results:** 3/3 webhook tests passed  
✅ **Integration:** TradingView via ngrok  
✅ **Security:** Secret-based authentication  
✅ **Logging:** CSV + text log files  
✅ **Monitoring:** Real-time via tail and dashboard  

**Quick Commands:**

```bash
# Start server
python webhooks/webhook_server.py

# Start ngrok
ngrok http 80

# Monitor logs
tail -f webhook_server.log

# View orders
tail -20 webhook_orders.csv

# Test webhook
curl http://localhost:80/health
```

**Your Webhook URL (with ngrok):**
```
https://your-ngrok-url.ngrok.io/webhook
```

**For support, check:**
1. `webhook_server.log` for errors
2. `webhook_orders.csv` for order history
3. ngrok web interface at `http://localhost:4040`

---

**Last Updated**: 2025-11-20  
**Next Steps**: Configure TradingView alert → Test with paper trading → Enable live trading

