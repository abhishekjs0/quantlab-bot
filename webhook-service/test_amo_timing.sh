#!/bin/bash
# Test Script for AMO Timing Control
# Tests different AMO timing values (PRE_OPEN, OPEN, OPEN_30, OPEN_60)

echo "🧪 Testing AMO Timing Control"
echo "=============================="
echo ""

BASE_URL="http://localhost:8080"

# Test 1: Default PRE_OPEN timing
echo "Test 1: Default AMO Timing (PRE_OPEN)"
echo "--------------------------------------"
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
        "sort_order": "1",
        "price": "0",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T15:30:00Z",
          "timenow": "2025-11-23T15:30:05Z"
        }
      }
    ]
  }'
echo -e "\n\n"

# Test 2: OPEN timing
echo "Test 2: AMO Timing = OPEN (9:15 AM)"
echo "------------------------------------"
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
        "symbol": "INFY",
        "instrument": "EQ",
        "productType": "C",
        "sort_order": "1",
        "price": "0",
        "amoTime": "OPEN",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T15:30:00Z",
          "timenow": "2025-11-23T15:30:05Z"
        }
      }
    ]
  }'
echo -e "\n\n"

# Test 3: OPEN_30 timing
echo "Test 3: AMO Timing = OPEN_30 (9:45 AM)"
echo "---------------------------------------"
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
        "symbol": "RELIANCE",
        "instrument": "EQ",
        "productType": "C",
        "sort_order": "1",
        "price": "0",
        "amoTime": "OPEN_30",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T15:30:00Z",
          "timenow": "2025-11-23T15:30:05Z"
        }
      }
    ]
  }'
echo -e "\n\n"

# Test 4: OPEN_60 timing
echo "Test 4: AMO Timing = OPEN_60 (10:15 AM)"
echo "----------------------------------------"
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
        "symbol": "HDFCBANK",
        "instrument": "EQ",
        "productType": "C",
        "sort_order": "1",
        "price": "0",
        "amoTime": "OPEN_60",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T15:30:00Z",
          "timenow": "2025-11-23T15:30:05Z"
        }
      }
    ]
  }'
echo -e "\n\n"

echo "✅ AMO Timing Tests Complete"
echo ""
echo "📊 Check logs for AMO timing values:"
echo "   grep 'AMO order.*timing' webhook-service/webhook_orders.csv"
echo ""
echo "📋 Expected Results:"
echo "   - Test 1: timing: PRE_OPEN"
echo "   - Test 2: timing: OPEN"
echo "   - Test 3: timing: OPEN_30"
echo "   - Test 4: timing: OPEN_60"
