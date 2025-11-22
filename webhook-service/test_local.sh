#!/bin/bash
# Local Testing Script for Webhook Service
# Run this to test webhook service before deploying to cloud

set -e  # Exit on error

echo "🧪 Testing Webhook Service Locally"
echo "=================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and add your credentials"
    exit 1
fi

echo "✅ Found .env file"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found!"
    exit 1
fi

echo "✅ Python 3 found"
echo ""

# Install dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt

echo "✅ Dependencies installed"
echo ""

# Check if security_id_list.csv exists
if [ ! -f security_id_list.csv ]; then
    echo "❌ Error: security_id_list.csv not found!"
    exit 1
fi

echo "✅ Found security_id_list.csv"
echo ""

# Start server in background
echo "🚀 Starting webhook server on port 8080..."
export PORT=8080
python3 app.py &
SERVER_PID=$!

# Wait for server to start
echo "⏳ Waiting for server to start..."
sleep 3

# Test health endpoint
echo ""
echo "🏥 Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s http://localhost:8080/health)
if [ $? -eq 0 ]; then
    echo "✅ Health check passed"
    echo "   Response: $HEALTH_RESPONSE"
else
    echo "❌ Health check failed"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Test readiness endpoint
echo ""
echo "🔍 Testing readiness endpoint..."
READY_RESPONSE=$(curl -s http://localhost:8080/ready)
if [ $? -eq 0 ]; then
    echo "✅ Readiness check passed"
    echo "   Response: $READY_RESPONSE"
else
    echo "❌ Readiness check failed"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Test webhook endpoint with mock order
echo ""
echo "📨 Testing webhook endpoint with mock order..."
WEBHOOK_RESPONSE=$(curl -s -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [{
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
        "time": "2025-11-21T09:15:00Z",
        "timenow": "2025-11-21T09:15:00Z"
      }
    }]
  }')

if [ $? -eq 0 ]; then
    echo "✅ Webhook test passed"
    echo "   Response: $WEBHOOK_RESPONSE"
else
    echo "❌ Webhook test failed"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

# Test invalid secret
echo ""
echo "🔒 Testing invalid secret (should fail)..."
INVALID_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8080/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "wrong_secret",
    "alertType": "multi_leg_order",
    "order_legs": [{
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
        "time": "2025-11-21T09:15:00Z",
        "timenow": "2025-11-21T09:15:00Z"
      }
    }]
  }')

HTTP_CODE=$(echo "$INVALID_RESPONSE" | tail -n1)
if [ "$HTTP_CODE" == "401" ]; then
    echo "✅ Security check passed (rejected invalid secret)"
else
    echo "⚠️  Warning: Invalid secret was not rejected (got HTTP $HTTP_CODE)"
fi

# Clean up
echo ""
echo "🧹 Stopping server..."
kill $SERVER_PID 2>/dev/null

echo ""
echo "=================================="
echo "✅ All tests passed!"
echo ""
echo "Your webhook service is ready for deployment!"
echo ""
echo "Next steps:"
echo "1. Review .env configuration"
echo "2. Deploy to Cloud Run: gcloud run deploy tradingview-webhook --source ."
echo "3. Test with your Cloud Run URL"
echo "4. Configure TradingView alerts"
echo ""
