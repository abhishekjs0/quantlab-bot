# Webhook Server Configuration Guide

## Overview

The webhook server receives alerts from TradingView and executes trades on Dhan automatically. This guide explains the complete configuration setup.

## Prerequisites

- Python 3.8+ with virtual environment
- Dhan trading account with API access
- TradingView account with alert capabilities

## Step 1: Install Dependencies

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

## Step 2: Configure Environment Variables

All configuration is in the main `.env` file (no separate webhook config needed):

```bash
# Dhan Broker Credentials (already configured)
DHAN_CLIENT_ID=1108351648
DHAN_ACCESS_TOKEN=eyJ0eXAi...  # Your Dhan access token
DHAN_API_KEY=1cf9de88
DHAN_API_SECRET=457c0207-2d9c-4a94-b44b-ac530c64894d
DHAN_USER_ID=9624973000

# Webhook Server Settings
WEBHOOK_HOST=0.0.0.0           # Listen on all interfaces
WEBHOOK_PORT=8000              # Server port
ENABLE_DHAN=true               # Set to 'false' for testing without executing orders
```

### Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DHAN_CLIENT_ID` | Your Dhan client ID | - | Yes |
| `DHAN_ACCESS_TOKEN` | Your Dhan access token | - | Yes |
| `WEBHOOK_HOST` | Server host address | `0.0.0.0` | No |
| `WEBHOOK_PORT` | Server port | `8000` | No |
| `ENABLE_DHAN` | Enable order execution | `true` | No |

## Step 3: Understanding the Configuration

### No Secret Authentication

The webhook server **does not** use secret-based authentication. This simplifies integration with TradingView. For production:

1. Use HTTPS (nginx/Caddy with SSL certificate)
2. Optionally whitelist TradingView IPs:
   - 52.89.214.238
   - 34.212.75.30
   - 54.218.53.128
   - 52.32.178.7

### ENABLE_DHAN Setting

- `ENABLE_DHAN=true`: Orders are actually placed on Dhan (LIVE TRADING)
- `ENABLE_DHAN=false`: Orders are logged only (TESTING MODE)

**Important:** Start with `ENABLE_DHAN=false` to test your setup!

## Step 4: Start the Webhook Server

### Using the Quick Start Script

```bash
./start_webhook.sh
```

### Manual Start

```bash
source .venv/bin/activate
python webhook_server.py
```

The server will start at `http://0.0.0.0:8000`

## Step 5: Configure TradingView Alerts

### Your Webhook URL

Based on your public IP: `2405:201:200c:3822:a512:1588:1584:5d6e`

**IPv6 URL format:**
```
http://[2405:201:200c:3822:a512:1588:1584:5d6e]:8000/webhook
```

**For local testing:**
```
http://localhost:8000/webhook
```

### TradingView Alert Message Format

TradingView automatically sends JSON when the message is valid JSON format:

```json
{"alertType":"multi_leg_order","order_legs":[{"transactionType":"{{strategy.order.action}}","orderType":"MKT","quantity":"{{strategy.order.contracts}}","exchange":"NSE","symbol":"{{ticker}}","instrument":"EQ","productType":"C","sort_order":"1","price":"{{close}}","meta":{"interval":"{{interval}}","time":"{{time}}","timenow":"{{timenow}}"}}]}
```

**Important:** Paste this as a **single line** with no extra spaces or line breaks!

### TradingView Placeholder Variables

- `{{strategy.order.action}}` → "buy" or "sell" (converted to "B"/"S")
- `{{strategy.order.contracts}}` → Number of shares to trade
- `{{ticker}}` → Stock symbol (e.g., "RELIANCE")
- `{{close}}` → Current close price
- `{{interval}}` → Chart timeframe (e.g., "1D")
- `{{time}}` → Bar time (ISO format)
- `{{timenow}}` → Current time (ISO format)

## Step 6: Test Your Setup

### Test Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-20T10:30:00.123456"
}
```

### Test Order Webhook

```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: text/plain" \
  -d '{"alertType":"multi_leg_order","order_legs":[{"transactionType":"B","orderType":"MKT","quantity":"1","exchange":"NSE","symbol":"RELIANCE","instrument":"EQ","productType":"C","sort_order":"1","price":"2820.25","meta":{"interval":"1D","time":"2025-11-20T09:15:00Z","timenow":"2025-11-20T10:30:00Z"}}]}'
```

### Run Test Suite

```bash
python test_webhook.py
```

## Troubleshooting

### Server Won't Start

```bash
# Check if port is already in use
lsof -i :8000

# Kill existing process
kill -9 $(lsof -t -i :8000)
```

### Orders Not Executing

1. Check `ENABLE_DHAN` is set to `true` in `.env`
2. Verify Dhan credentials are correct
3. Check `webhook_server.log` for errors
4. Ensure Dhan account has sufficient funds/margin

### View Server Logs

```bash
# Real-time log viewing
tail -f webhook_server.log

# Last 50 lines
tail -50 webhook_server.log
```

### TradingView Alert Not Triggering

1. Verify webhook URL is correct (use brackets for IPv6)
2. Check TradingView 2FA is enabled (required for webhooks)
3. Test webhook endpoint is accessible from internet
4. Check TradingView alert history for error messages

## Production Deployment

### Security Best Practices

1. **Use HTTPS**: Deploy behind nginx/Caddy with SSL
2. **Firewall Rules**: Allow only TradingView IPs if possible
3. **Environment Security**: Keep `.env` file secure, never commit to git
4. **Access Token**: Rotate Dhan access tokens regularly
5. **Monitoring**: Set up alerts for failed orders

### Example nginx Configuration

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location /webhook {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Using ngrok for Testing

If you don't have a static IP:

```bash
# Install ngrok from https://ngrok.com/download
ngrok http 8000

# Use the HTTPS URL shown in ngrok terminal
# Example: https://abc123.ngrok.io/webhook
```

## Order Execution Flow

1. **TradingView Alert Triggers** → Sends POST request with JSON payload
2. **Webhook Server Receives** → Validates JSON structure with Pydantic
3. **Security ID Lookup** → Fetches security_id from Dhan for the symbol
4. **Order Placement** → Calls Dhan API with mapped parameters
5. **Response Logged** → Order ID and status logged to `webhook_server.log`

## Parameter Mappings

### Exchange Codes

| TradingView | Dhan API |
|------------|----------|
| NSE | NSE_EQ |
| BSE | BSE_EQ |
| NFO | NSE_FNO |
| MCX | MCX_COMM |

### Transaction Types

| TradingView | Dhan API |
|------------|----------|
| B | BUY |
| S | SELL |
| buy | BUY |
| sell | SELL |

### Order Types

| TradingView | Dhan API |
|------------|----------|
| MKT | MARKET |
| LMT | LIMIT |
| SL | STOP_LOSS |
| SL-M | STOP_LOSS_MARKET |

### Product Types

| TradingView | Dhan API |
|------------|----------|
| C | CNC |
| I | INTRADAY |
| M | MARGIN |

## Files Reference

```
webhook_server.py           # Main FastAPI server
dhan_broker.py             # Dhan API integration
test_webhook.py            # Test suite
start_webhook.sh           # Quick start script
requirements.txt           # Python dependencies
.env                       # Configuration (single file)
webhook_server.log         # Server logs
```

## Support

For issues:
1. Check `webhook_server.log`
2. Run test suite: `python test_webhook.py`
3. Verify environment variables in `.env`
4. Review Dhan API documentation: https://dhanhq.co/docs/v2/

## Next Steps

1. ✅ Install dependencies: `pip install -r requirements.txt`
2. ✅ Configure `.env` file with Dhan credentials
3. ✅ Start server: `./start_webhook.sh`
4. ✅ Test locally: `python test_webhook.py`
5. ⚠️ Test with ENABLE_DHAN=false first
6. ⚠️ Configure TradingView alert with your webhook URL
7. ⚠️ Run paper trades to verify
8. ⚠️ Enable live trading: ENABLE_DHAN=true
9. ⚠️ Monitor logs and positions

**Remember:** Always test thoroughly with paper trading before enabling live execution!
