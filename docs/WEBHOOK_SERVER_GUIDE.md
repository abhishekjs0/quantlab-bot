# FastAPI Webhook Server for TradingView Alerts

A production-ready FastAPI webhook server that receives TradingView alerts and processes multi-leg order execution requests.

## Features

- ✅ **Text/Plain Content-Type Support**: Accepts raw JSON strings in POST body
- ✅ **Request Validation**: Pydantic models for robust payload validation
- ✅ **Secret Authentication**: Shared secret verification for security
- ✅ **Multi-Leg Orders**: Support for complex multi-leg order execution
- ✅ **Comprehensive Logging**: File and console logging with timestamps
- ✅ **Health Check Endpoints**: Monitor server status
- ✅ **Error Handling**: Graceful error handling with proper HTTP status codes

## Installation

### 1. Install Dependencies

```bash
pip install fastapi uvicorn python-dotenv pydantic
```

Or add to your existing `requirements.txt`:

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
python-dotenv>=1.0.0
```

### 2. Configuration

Copy the example environment file:

```bash
cp .env.webhook.example .env.webhook
```

Edit `.env.webhook` with your settings:

```bash
WEBHOOK_SECRET=your_secret_here
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8000
```

## Usage

### Start the Server

```bash
# Basic start
python webhook_server.py

# Or with environment file
source .env.webhook && python webhook_server.py

# With custom port
WEBHOOK_PORT=8080 python webhook_server.py
```

The server will start at `http://0.0.0.0:8000` (or your configured port).

### Endpoints

#### 1. Health Check
```bash
GET http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-20T10:00:00.000000"
}
```

#### 2. Main Webhook Endpoint
```bash
POST http://localhost:8000/webhook
Content-Type: text/plain

{
  "secret": "iilqB",
  "alertType": "multi_leg_order",
  "order_legs": [...]
}
```

#### 3. Test Endpoint (with automatic JSON parsing)
```bash
POST http://localhost:8000/webhook/test
Content-Type: application/json

{
  "secret": "iilqB",
  "alertType": "multi_leg_order",
  "order_legs": [...]
}
```

## TradingView Alert Configuration

### Alert Message Format

In TradingView, create an alert with the following message body:

```json
{
  "secret": "iilqB",
  "alertType": "multi_leg_order",
  "order_legs": [
    {
      "transactionType": "B",
      "orderType": "MKT",
      "quantity": "10",
      "exchange": "NSE",
      "symbol": "{{ticker}}",
      "instrument": "EQ",
      "productType": "C",
      "sort_order": "1",
      "price": "{{close}}",
      "meta": {
        "interval": "{{interval}}",
        "time": "{{time}}",
        "timenow": "{{timenow}}"
      }
    }
  ]
}
```

### TradingView Variables

- `{{ticker}}` - Symbol name
- `{{close}}` - Close price
- `{{interval}}` - Chart interval (1, 5, 15, 60, 1D, etc.)
- `{{time}}` - Bar timestamp
- `{{timenow}}` - Current timestamp

### Webhook URL

Set your TradingView webhook URL to:
```
http://your-server-ip:8000/webhook
```

## Payload Structure

### Complete Example

```json
{
  "secret": "iilqB",
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
      "price": "2820.25",
      "meta": {
        "interval": "1D",
        "time": "2025-03-14T09:15:00Z",
        "timenow": "2025-03-14T15:31:44Z"
      }
    }
  ]
}
```

### Field Descriptions

#### Root Level
- `secret` (string, required): Shared secret for authentication
- `alertType` (string, required): Type of alert (multi_leg_order, single_order, cancel_order)
- `order_legs` (array, required): List of order legs to execute

#### Order Leg Fields
- `transactionType` (string, required): "B" for Buy, "S" for Sell
- `orderType` (string, required): "MKT" (Market), "LMT" (Limit), "SL" (Stop Loss), "SL-M" (Stop Loss Market)
- `quantity` (string, required): Number of shares/contracts
- `exchange` (string, required): "NSE", "BSE", "NFO", "BFO", "MCX", etc.
- `symbol` (string, required): Trading symbol
- `instrument` (string, required): "EQ" (Equity), "FUT" (Futures), "CE" (Call Option), "PE" (Put Option)
- `productType` (string, required): "C" (CNC/Delivery), "I" (Intraday), "M" (Margin)
- `sort_order` (string, required): Execution priority (1, 2, 3...)
- `price` (string, required): Price for limit orders (use close price for market orders)

#### Metadata Fields
- `interval` (string, required): Chart timeframe (1, 5, 15, 60, 1D, 1W, etc.)
- `time` (string, required): Bar timestamp in ISO 8601 format
- `timenow` (string, required): Current timestamp in ISO 8601 format

## Response Format

### Success Response

```json
{
  "status": "success",
  "message": "Processed 1 order leg(s)",
  "alertType": "multi_leg_order",
  "timestamp": "2025-11-20T10:00:00.000000",
  "results": [
    {
      "leg_number": 1,
      "symbol": "RELIANCE",
      "transaction": "B",
      "quantity": "10",
      "status": "acknowledged",
      "message": "Order leg received and queued for execution"
    }
  ]
}
```

### Error Responses

#### Invalid Secret (401)
```json
{
  "detail": "Invalid webhook secret"
}
```

#### Invalid Payload (422)
```json
{
  "detail": "Payload validation error: ..."
}
```

#### Invalid JSON (400)
```json
{
  "detail": "Invalid JSON format: ..."
}
```

## Testing

### Using curl

```bash
# Test with raw JSON
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: text/plain" \
  -d '{
    "secret": "iilqB",
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
        "price": "2820.25",
        "meta": {
          "interval": "1D",
          "time": "2025-03-14T09:15:00Z",
          "timenow": "2025-03-14T15:31:44Z"
        }
      }
    ]
  }'
```

### Using Python requests

```python
import requests
import json

url = "http://localhost:8000/webhook"
payload = {
    "secret": "iilqB",
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
            "price": "2820.25",
            "meta": {
                "interval": "1D",
                "time": "2025-03-14T09:15:00Z",
                "timenow": "2025-03-14T15:31:44Z"
            }
        }
    ]
}

response = requests.post(
    url,
    headers={"Content-Type": "text/plain"},
    data=json.dumps(payload)
)

print(response.status_code)
print(response.json())
```

## Production Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/webhook-server.service`:

```ini
[Unit]
Description=TradingView Webhook Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/quantlab-workspace
Environment="WEBHOOK_SECRET=your_secret"
Environment="WEBHOOK_PORT=8000"
ExecStart=/path/to/quantlab-workspace/.venv/bin/python webhook_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable webhook-server
sudo systemctl start webhook-server
sudo systemctl status webhook-server
```

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webhook_server.py .
EXPOSE 8000

ENV WEBHOOK_SECRET=iilqB
ENV WEBHOOK_PORT=8000

CMD ["python", "webhook_server.py"]
```

Build and run:
```bash
docker build -t webhook-server .
docker run -d -p 8000:8000 \
  -e WEBHOOK_SECRET=your_secret \
  --name webhook-server webhook-server
```

### Using ngrok (for testing)

```bash
# Start the server
python webhook_server.py

# In another terminal, expose with ngrok
ngrok http 8000

# Use the ngrok URL in TradingView
# https://xxxx-xx-xx-xx-xx.ngrok.io/webhook
```

## Security Considerations

1. **Change the Default Secret**: Always use a strong, unique secret in production
2. **Use HTTPS**: Deploy behind a reverse proxy (nginx, Caddy) with SSL/TLS
3. **IP Whitelisting**: Consider restricting access to TradingView IPs
4. **Rate Limiting**: Implement rate limiting to prevent abuse
5. **Log Monitoring**: Monitor logs for suspicious activity

### Optional: Add HMAC Signature Verification

For additional security, you can implement HMAC signature verification:

```python
import hmac
import hashlib

def verify_hmac_signature(payload: str, signature: str, secret: str) -> bool:
    """Verify HMAC signature"""
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Logging

Logs are written to both console and `webhook_server.log`:

```
2025-11-20 10:00:00,000 - __main__ - INFO - Starting webhook server on 0.0.0.0:8000
2025-11-20 10:00:05,123 - __main__ - INFO - Received webhook request from 203.0.113.1
2025-11-20 10:00:05,124 - __main__ - INFO - Valid webhook received: multi_leg_order with 1 leg(s)
2025-11-20 10:00:05,125 - __main__ - INFO - Order Leg 1/1: B 10 RELIANCE @ NSE (MKT)
```

## Integration with Broker API

To integrate with your broker (Dhan, Zerodha, etc.), modify the order processing section in `webhook_server.py`:

```python
# In the /webhook endpoint, replace the mock processing with:
from your_broker_module import place_order

for idx, leg in enumerate(payload.order_legs, 1):
    try:
        order_id = place_order(
            transaction_type=leg.transactionType,
            symbol=leg.symbol,
            quantity=int(leg.quantity),
            order_type=leg.orderType,
            product=leg.productType,
            exchange=leg.exchange,
            price=float(leg.price) if leg.orderType == "LMT" else None
        )
        result = {
            "leg_number": idx,
            "symbol": leg.symbol,
            "order_id": order_id,
            "status": "placed"
        }
    except Exception as e:
        result = {
            "leg_number": idx,
            "symbol": leg.symbol,
            "status": "failed",
            "error": str(e)
        }
    results.append(result)
```

## Troubleshooting

### Server won't start
- Check if port is already in use: `lsof -i :8000`
- Verify Python dependencies are installed
- Check file permissions

### TradingView alerts not received
- Verify webhook URL is correct and accessible
- Check firewall settings
- Ensure server is running and reachable
- Test with curl first

### Authentication errors
- Verify secret matches between TradingView and server
- Check for trailing spaces in secret configuration

### Payload validation errors
- Verify JSON format is correct
- Check all required fields are present
- Ensure datetime formats are ISO 8601

## License

MIT License - See LICENSE file for details

## Support

For issues and questions, please open an issue in the repository.
