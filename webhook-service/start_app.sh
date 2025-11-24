#!/bin/bash

# Kill existing process on port 8080
echo "🔍 Checking for existing process on port 8080..."
PID=$(lsof -ti:8080)
if [ ! -z "$PID" ]; then
    echo "⚠️  Killing existing process: $PID"
    kill -9 $PID 2>/dev/null
    sleep 2
fi

# Start app in background
echo "🚀 Starting webhook service..."
cd /Users/abhishekshah/Desktop/quantlab-workspace/webhook-service
nohup /usr/bin/python3 app.py > app.log 2>&1 &
NEW_PID=$!

# Wait a moment for startup
sleep 3

# Check if it's running
if ps -p $NEW_PID > /dev/null; then
    echo "✅ App started successfully!"
    echo "📋 Process ID: $NEW_PID"
    echo "📍 URL: http://localhost:8080"
    echo "📝 Logs: tail -f app.log"
else
    echo "❌ App failed to start. Check app.log for errors"
    tail -20 app.log
fi
