# Webhook Server - Quick Reference

## 🚀 Quick Start

```bash
# Start the webhook server
./start_webhook.sh

# Or manually
source .venv/bin/activate
python webhook_server.py
```

Server runs at: `http://localhost:8000`

## 📍 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Root / version info |
| `/health` | GET | Health check |
| `/webhook` | POST | Main TradingView webhook |
| `/webhook/test` | POST | Test endpoint (auto JSON parse) |

## 🧪 Testing

```bash
# Run test suite
python test_webhook.py

# Or test manually with curl
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: text/plain" \
  -d '{"secret":"iilqB","alertType":"multi_leg_order","order_legs":[{"transactionType":"B","orderType":"MKT","quantity":"10","exchange":"NSE","symbol":"RELIANCE","instrument":"EQ","productType":"C","sort_order":"1","price":"2820.25","meta":{"interval":"1D","time":"2025-03-14T09:15:00Z","timenow":"2025-03-14T15:31:44Z"}}]}'
```

## 📝 TradingView Alert Setup

1. Create alert in TradingView
2. Set webhook URL: `http://your-domain.com/webhook` (Port 80 for HTTP)
3. In your Pine Script strategy, use this alert message format:

**Your Pine Script is PERFECT!** ✅ Just update `__SECRET__` to `GTcl4`:

```pine
// TradingView Pine Script Alert Message Builder
var string baseTemplate = ""
if barstate.isfirst
    baseTemplate := ""
    baseTemplate += "{"
    baseTemplate += "\"secret\":\"__SECRET__\","
    baseTemplate += "\"alertType\":\"multi_leg_order\","
    baseTemplate += "\"order_legs\":["
    baseTemplate += "{"
    baseTemplate += "\"transactionType\":\"__SIDE__\","
    baseTemplate += "\"orderType\":\"MKT\","
    baseTemplate += "\"quantity\":\"{{strategy.order.contracts}}\","
    baseTemplate += "\"exchange\":\"{{exchange}}\","
    baseTemplate += "\"symbol\":\"{{ticker}}\","
    baseTemplate += "\"instrument\":\"EQ\","
    baseTemplate += "\"productType\":\"I\","
    baseTemplate += "\"sort_order\":\"1\","
    baseTemplate += "\"price\":\"{{strategy.order.price}}\","
    baseTemplate += "\"meta\":{"
    baseTemplate += "\"interval\":\"{{interval}}\","
    baseTemplate += "\"time\":\"{{time}}\","
    baseTemplate += "\"timenow\":\"{{timenow}}\""
    baseTemplate += "}"
    baseTemplate += "}"
    baseTemplate += "]"
    baseTemplate += "}"

build_msg(_side) =>
    string m = baseTemplate
    m := str.replace(m, "__SECRET__", "GTcl4")  // Your webhook secret
    m := str.replace(m, "__SIDE__", _side)
    m

buyMsg  = build_msg("B")
sellMsg = build_msg("S")
```

**In Alert Settings:**
- Message: `{{strategy.order.alert_message}}`
- Webhook URL: `http://your-domain.com/webhook`

### 🌐 Finding Your Server IP

**For local testing (same computer):**
```
http://localhost:8000/webhook
```

**For remote server (find public IP):**
```bash
# On macOS/Linux terminal
curl ifconfig.me

# Alternative
curl ipinfo.io/ip
```

**Your public IP:** `2405:201:200c:3822:a512:1588:1584:5d6e` (use with brackets for IPv6)

**For ngrok (temporary public URL):**
```bash
# Install ngrok from https://ngrok.com/download
ngrok http 8000

# Use the HTTPS URL shown in terminal
# Example: https://1234-56-78-90-12.ngrok.io/webhook
```

**For cloud servers:**
- AWS EC2: Check instance details in AWS Console
- DigitalOcean: Listed in Droplet dashboard
- Google Cloud: Check VM instance details
```

## 🔧 Configuration

Edit `.env` file (main configuration file):

```bash
# Dhan broker credentials (already configured)
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_token

# Webhook settings
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8000
ENABLE_DHAN=true  # Set to false for testing without executing orders
```

## 📊 Field Reference

### Transaction Types
- `B` = Buy
- `S` = Sell

### Order Types
- `MKT` = Market
- `LMT` = Limit
- `SL` = Stop Loss
- `SL-M` = Stop Loss Market

### Product Types
- `C` = CNC (Delivery)
- `I` = Intraday
- `M` = Margin

### Instruments
- `EQ` = Equity
- `FUT` = Futures
- `CE` = Call Option
- `PE` = Put Option

## 📖 Full Documentation

See [WEBHOOK_SERVER_GUIDE.md](docs/WEBHOOK_SERVER_GUIDE.md) for complete documentation.

## 🔐 Security Notes

1. **Change default secret** in production
2. **Use HTTPS** (deploy behind nginx/Caddy with SSL)
3. **IP whitelist** TradingView IPs if possible
4. **Monitor logs** for suspicious activity

## 📁 Files

```
webhook_server.py           # Main FastAPI server
test_webhook.py            # Test suite
start_webhook.sh           # Quick start script
.env.webhook.example       # Configuration template
docs/WEBHOOK_SERVER_GUIDE.md  # Complete guide
```

## 🐛 Troubleshooting

### Server won't start
```bash
# Check if port is in use
lsof -i :8000

# Kill existing process
kill -9 $(lsof -t -i :8000)
```

### Test connection
```bash
curl http://localhost:8000/health
```

### View logs
```bash
tail -f webhook_server.log
```

## 📞 Support

For issues, check `webhook_server.log` or see full documentation.
