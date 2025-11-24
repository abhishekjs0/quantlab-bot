#!/bin/bash
# Test the deployed webhook service

echo "🧪 Testing Deployed Webhook Service..."
echo ""

SERVICE_URL="https://tradingview-webhook-cgy4m5alfq-el.a.run.app"

echo "1️⃣  Testing Health Endpoint..."
HEALTH=$(curl -s "$SERVICE_URL/health")
echo "$HEALTH"
echo ""

echo "2️⃣  Testing Ready Endpoint..."
READY=$(curl -s "$SERVICE_URL/ready")
echo "$READY"
echo ""

echo "3️⃣  Testing Root Endpoint (Status)..."
STATUS=$(curl -s "$SERVICE_URL/")
echo "$STATUS" | head -20
echo ""

echo "4️⃣  Testing Market Status Endpoint..."
MARKET=$(curl -s "$SERVICE_URL/market-status")
echo "$MARKET" | head -20
echo ""

echo "5️⃣  Testing OAuth Callback (will fail without tokenId - expected)..."
CALLBACK=$(curl -s "$SERVICE_URL/auth/callback")
echo "$CALLBACK"
echo ""

echo "✅ Deployment tests complete!"
echo ""
echo "📝 Next steps:"
echo "   1. Service appears to be: $(echo $HEALTH | grep -q 'healthy' && echo '✅ HEALTHY' || echo '❌ NOT HEALTHY')"
echo "   2. Setup cron job: bash setup-cron-job.sh"
echo "   3. Test OAuth flow by visiting Dhan API management"
