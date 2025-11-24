#!/bin/bash
# Test Script for Signal Queueing System
# Tests weekend/holiday signal queueing and execution

echo "🧪 Testing Signal Queueing System"
echo "==================================="
echo ""

BASE_URL="http://localhost:8080"
DB_PATH="./signal_queue.db"

# Test 1: Send signal (should be queued on weekend)
echo "Test 1: Send Signal on Weekend (Should Queue)"
echo "----------------------------------------------"
echo "Current date: $(date)"
echo "Sending webhook signal..."
echo ""

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
        "amoTime": "PRE_OPEN",
        "meta": {
          "interval": "1D",
          "time": "2025-11-23T15:30:00Z",
          "timenow": "2025-11-23T15:30:05Z"
        }
      }
    ]
  }'
echo -e "\n\n"

# Test 2: Check queue database
echo "Test 2: Check Signal Queue Database"
echo "------------------------------------"
if [ -f "$DB_PATH" ]; then
    echo "✅ Database exists: $DB_PATH"
    echo ""
    echo "📊 Queue Statistics:"
    sqlite3 $DB_PATH "SELECT status, COUNT(*) as count FROM signal_queue GROUP BY status;"
    echo ""
    echo "📋 All Signals:"
    sqlite3 $DB_PATH "SELECT signal_id, status, received_time, scheduled_time FROM signal_queue ORDER BY signal_id DESC LIMIT 10;" | column -t -s '|'
else
    echo "❌ Database not found: $DB_PATH"
fi
echo ""

# Test 3: Check pending signals
echo "Test 3: Check Pending Signals"
echo "------------------------------"
if [ -f "$DB_PATH" ]; then
    PENDING_COUNT=$(sqlite3 $DB_PATH "SELECT COUNT(*) FROM signal_queue WHERE status='QUEUED';")
    echo "📥 Pending signals: $PENDING_COUNT"
    echo ""
    if [ "$PENDING_COUNT" -gt 0 ]; then
        echo "Details:"
        sqlite3 $DB_PATH "SELECT signal_id, scheduled_time, payload FROM signal_queue WHERE status='QUEUED';" | while IFS='|' read -r id time payload; do
            echo "  Signal ID: $id"
            echo "  Scheduled: $time"
            echo "  Payload: $(echo $payload | jq -c '.order_legs[0].symbol' 2>/dev/null || echo 'N/A')"
            echo ""
        done
    fi
fi
echo ""

# Test 4: View queue stats
echo "Test 4: Queue Statistics"
echo "------------------------"
if [ -f "$DB_PATH" ]; then
    echo "Status Distribution:"
    sqlite3 $DB_PATH "SELECT status, COUNT(*) as count, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM signal_queue), 2) as percentage FROM signal_queue GROUP BY status;" | while IFS='|' read -r status count pct; do
        echo "  $status: $count ($pct%)"
    done
    echo ""
    echo "Total Signals: $(sqlite3 $DB_PATH 'SELECT COUNT(*) FROM signal_queue;')"
    echo "Earliest Signal: $(sqlite3 $DB_PATH 'SELECT received_time FROM signal_queue ORDER BY received_time ASC LIMIT 1;')"
    echo "Latest Signal: $(sqlite3 $DB_PATH 'SELECT received_time FROM signal_queue ORDER BY received_time DESC LIMIT 1;')"
fi
echo ""

# Test 5: Cleanup test (commented out for safety)
echo "Test 5: Cleanup Options"
echo "-----------------------"
echo "To cleanup old signals:"
echo "  sqlite3 $DB_PATH \"DELETE FROM signal_queue WHERE status IN ('EXECUTED','FAILED') AND created_at < datetime('now', '-30 days');\""
echo ""
echo "To reset stuck signals:"
echo "  sqlite3 $DB_PATH \"UPDATE signal_queue SET status='QUEUED' WHERE status='PROCESSING' AND created_at < datetime('now', '-10 minutes');\""
echo ""
echo "To view all signals:"
echo "  sqlite3 $DB_PATH \"SELECT * FROM signal_queue;\""
echo ""

echo "✅ Signal Queue Tests Complete"
echo ""
echo "📊 Expected Results:"
echo "   - Signal should be queued (status=QUEUED)"
echo "   - Scheduled time should be Monday 9:00 AM"
echo "   - Check Telegram for 'Signal Queued' notification"
echo ""
echo "🔄 Background processor will execute signal on Monday 9:00 AM"
echo "   Check logs with: tail -f /path/to/webhook_service.log"
