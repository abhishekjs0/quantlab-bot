#!/bin/bash

# Test script for Telegram notifications
# Tests all Telegram notification types and formats

echo "🧪 Testing Telegram Notifications"
echo "=================================================="
echo ""

# Configuration
BASE_URL="http://localhost:8080"
DB_PATH="./signal_queue.db"

# Get Telegram bot token and chat ID from .env
BOT_TOKEN=$(grep TELEGRAM_BOT_TOKEN .env | cut -d '=' -f2)
CHAT_ID=$(grep TELEGRAM_CHAT_ID .env | cut -d '=' -f2)

if [ -z "$BOT_TOKEN" ] || [ -z "$CHAT_ID" ]; then
    echo "❌ Missing Telegram credentials in .env file"
    echo "   TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required"
    exit 1
fi

echo "📋 Configuration:"
echo "   Bot Token: ${BOT_TOKEN:0:20}..."
echo "   Chat ID: $CHAT_ID"
echo ""

# Test 1: Order Success Notification
echo "Test 1: Order Success Notification"
echo "--------------------------------------------------"
echo "📤 Sending successful order webhook..."
curl -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "MKT",
        "quantity": "1",
        "exchange": "NSE_EQ",
        "symbol": "TCS",
        "instrument": "EQ",
        "productType": "C",
        "price": "0",
        "sort_order": "1",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T12:00:00",
          "timenow": "2025-11-23T12:00:00"
        }
      }
    ]
  }'
echo ""
echo ""
echo "✅ Expected Telegram message:"
echo "   Title: ✅ Order Executed"
echo "   Details: Symbol, Transaction, Quantity, Status"
echo "   Message format: Formatted with emoji indicators"
echo ""
sleep 2

# Test 2: Multi-leg Order Notification
echo "Test 2: Multi-leg Order Notification"
echo "--------------------------------------------------"
echo "📤 Sending multi-leg order webhook..."
curl -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "LMT",
        "quantity": "1",
        "exchange": "NSE_EQ",
        "symbol": "INFY",
        "instrument": "EQ",
        "productType": "C",
        "price": "1450.0",
        "sort_order": "1",
        "meta": {"interval": "1D", "time": "2025-11-23T12:01:00", "timenow": "2025-11-23T12:01:00"}
      },
      {
        "transactionType": "S",
        "orderType": "LMT",
        "quantity": "1",
        "exchange": "NSE_EQ",
        "symbol": "RELIANCE",
        "instrument": "EQ",
        "productType": "C",
        "price": "2850.0",
        "sort_order": "2",
        "meta": {"interval": "1D", "time": "2025-11-23T12:01:00", "timenow": "2025-11-23T12:01:00"}
      }
    ]
  }'
echo ""
echo ""
echo "✅ Expected Telegram message:"
echo "   Title: ✅ 2 Orders Executed"
echo "   Details: Each leg with symbol, direction, status"
echo "   Format: Separate line per leg"
echo ""
sleep 2

# Test 3: Signal Queued Notification (weekend)
echo "Test 3: Signal Queued Notification"
echo "--------------------------------------------------"
echo "📤 This should queue the signal (weekend/holiday)..."
curl -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "MKT",
        "quantity": "10",
        "exchange": "NSE_EQ",
        "symbol": "HDFCBANK",
        "instrument": "EQ",
        "productType": "C",
        "price": "0",
        "sort_order": "1",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T12:05:00",
          "timenow": "2025-11-23T12:05:00"
        }
      }
    ]
  }'
echo ""
echo ""
echo "✅ Expected Telegram message:"
echo "   Title: 🕐 Signal Queued"
echo "   Reason: Non-trading day / Market closed"
echo "   Scheduled: Monday 9:00 AM IST"
echo "   Details: Full order details"
echo ""
sleep 2

# Test 4: Order Error Notification
echo "Test 4: Order Error Notification"
echo "--------------------------------------------------"
echo "📤 Sending order with invalid symbol..."
curl -X POST "$BASE_URL/webhook" \
  -H "Content-Type: application/json" \
  -d '{
    "secret": "GTcl4",
    "alertType": "multi_leg_order",
    "order_legs": [
      {
        "transactionType": "B",
        "orderType": "MKT",
        "quantity": "1",
        "exchange": "NSE_EQ",
        "symbol": "INVALIDSYMBOL123",
        "instrument": "EQ",
        "productType": "C",
        "price": "0",
        "sort_order": "1",
        "meta": {"interval": "1D", "time": "2025-11-23T12:06:00", "timenow": "2025-11-23T12:06:00"}
      }
    ]
  }'
echo ""
echo ""
echo "✅ Expected Telegram message:"
echo "   Title: ❌ Order Failed"
echo "   Error: Symbol not found / Invalid security ID"
echo "   Details: Order parameters and error message"
echo ""
sleep 2

# Test 5: Check Telegram Bot Status
echo "Test 5: Telegram Bot Status Check"
echo "--------------------------------------------------"
echo "🔍 Checking Telegram bot status..."
echo ""
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getMe" | python3 -m json.tool
echo ""
echo "✅ Expected: Bot information (username, first_name, etc.)"
echo ""

# Test 6: Check Recent Messages
echo "Test 6: Check Recent Messages Sent"
echo "--------------------------------------------------"
echo "🔍 Checking last few messages sent by bot..."
echo ""
echo "To verify messages were sent, check your Telegram chat: $CHAT_ID"
echo ""
echo "Alternatively, use Telegram Bot API to get updates:"
echo "curl -s \"https://api.telegram.org/bot${BOT_TOKEN}/getUpdates?limit=5\""
echo ""

# Test 7: Notification Format Verification
echo "Test 7: Notification Format Verification"
echo "--------------------------------------------------"
echo "✅ Telegram Message Format Standards:"
echo ""
echo "1. Order Success:"
echo "   ✅ Order Executed"
echo "   Symbol: TCS"
echo "   Direction: BUY"
echo "   Quantity: 1"
echo "   Status: Success"
echo ""
echo "2. Multi-leg Order:"
echo "   ✅ 2 Orders Executed"
echo "   Leg 1: INFY | BUY | 1 | Success"
echo "   Leg 2: RELIANCE | SELL | 1 | Success"
echo ""
echo "3. Signal Queued:"
echo "   🕐 Signal Queued"
echo "   Reason: Non-trading day"
echo "   Scheduled: 2025-11-24 09:00:00 IST"
echo "   Symbol: HDFCBANK | BUY | 10"
echo ""
echo "4. Order Error:"
echo "   ❌ Order Failed"
echo "   Symbol: INVALIDSYMBOL123"
echo "   Error: Symbol not found in security master"
echo ""

# Test 8: Telegram Configuration Check
echo "Test 8: Telegram Configuration Check"
echo "--------------------------------------------------"
echo "📋 Current Telegram Settings:"
echo ""
grep -E "TELEGRAM_BOT_TOKEN|TELEGRAM_CHAT_ID|ENABLE_TELEGRAM" .env
echo ""
echo "✅ Notifications enabled: Check ENABLE_TELEGRAM=true"
echo "✅ Bot token configured: Check TELEGRAM_BOT_TOKEN present"
echo "✅ Chat ID configured: Check TELEGRAM_CHAT_ID present"
echo ""

# Summary
echo "=================================================="
echo "✅ Telegram Notification Tests Complete"
echo ""
echo "📊 Test Summary:"
echo "   - Order success notification sent"
echo "   - Multi-leg order notification sent"
echo "   - Signal queued notification sent"
echo "   - Error notification sent"
echo "   - Bot status verified"
echo ""
echo "📱 Verification Steps:"
echo "   1. Check Telegram chat: $CHAT_ID"
echo "   2. Verify 4 messages received (success, multileg, queued, error)"
echo "   3. Confirm message formatting (emoji, layout)"
echo "   4. Check all details present in messages"
echo ""
echo "📚 Documentation:"
echo "   - Telegram module: telegram_notifier.py"
echo "   - Configuration: .env file"
echo "   - Integration: app.py webhook endpoint"
echo ""
