# Firestore Persistent Logging Setup

## Overview
The webhook service now logs all orders to **Google Cloud Firestore** for persistent storage across container restarts. This solves the problem of losing order logs when Cloud Run containers are recycled.

## What Was Added
- ✅ Firestore client initialization in `webhook-service/app.py`
- ✅ `log_order_to_firestore()` function that logs orders with full details
- ✅ `/logs/firestore` endpoint to retrieve persistent order history
- ✅ `google-cloud-firestore==2.16.1` added to `requirements.txt`
- ✅ Cloud Run deployed with revision 00030 (includes Firestore code)

## What Still Needs To Be Done

### 1. Grant Service Account Firestore Permissions
The Cloud Run service account needs the `roles/datastore.user` role to access Firestore.

**Required Command** (must be run by someone with Project Editor/Owner permissions):
```bash
gcloud projects add-iam-policy-binding quantlab-bot \
  --member="serviceAccount:86335712552-compute@developer.gserviceaccount.com" \
  --role="roles/datastore.user" \
  --quiet
```

**Why**: The service account running Cloud Run needs permission to read/write to Firestore collections.

### 2. Current Status
- ✅ Code deployed to Cloud Run revision 00030
- ✅ Telegram notifications configured
- ❌ Firestore permissions not yet granted (403 Permission Denied error)
- ❌ Cannot test /logs/firestore endpoint until permissions are granted

## How It Works (After Permissions Are Granted)

### Order Logging Flow
```
TradingView Alert arrives
        ↓
Webhook processes alert
        ↓
Order execution (success/reject/fail)
        ↓
        ├─→ Log to CSV (ephemeral, lost on restart)
        └─→ Log to Firestore (persistent, survives restarts)
        ↓
Telegram notification sent
```

### Database Collection Structure
**Collection**: `webhook_orders`
**Documents**: Organized by `<timestamp>_<leg_number>_<symbol>`

**Fields in each document**:
```json
{
  "timestamp": "2025-12-03T15:32:45+05:30",
  "alert_type": "BUY|SELL",
  "leg_number": 1,
  "symbol": "UTIAMC",
  "exchange": "NSE|BSE|MCX",
  "transaction_type": "BUY|S",
  "quantity": 100,
  "order_type": "MARKET|LIMIT",
  "product_type": "MIS|NRML",
  "price": 0.0,
  "status": "success|rejected|failed|error",
  "message": "SELL order rejected: Security ID 527 not found in holdings",
  "order_id": "12345678" or "",
  "security_id": "527",
  "source_ip": "203.0.113.45"
}
```

## Accessing Order Logs

### Via API Endpoint
Once permissions are granted, query persistent order history:
```bash
# Get last 100 orders from Firestore
curl "https://tradingview-webhook-86335712552.asia-south1.run.app/logs/firestore?limit=100"

# Example response:
{
  "status": "success",
  "count": 50,
  "logs": [
    {
      "timestamp": "2025-12-03T15:32:45+05:30",
      "alert_type": "SELL",
      "symbol": "UTIAMC",
      "status": "rejected",
      "message": "SELL order rejected: Security ID 527 not found in holdings",
      ...
    }
  ],
  "source": "firestore",
  "note": "These logs are persisted across container restarts"
}
```

### Via Google Cloud Console
1. Go to **Firestore** → **quantlab-bot** project
2. Select collection: **webhook_orders**
3. View all orders with filtering and search capabilities

## Testing After Setup

### 1. Verify Permissions Granted
```bash
gcloud projects get-iam-policy quantlab-bot \
  --flatten="bindings[].members" \
  --filter="bindings.roles:roles/datastore.user"
```

### 2. Query Firestore Logs
```bash
curl "https://tradingview-webhook-86335712552.asia-south1.run.app/logs/firestore?limit=10"
```

### 3. Send Test Alert
Send a TradingView alert to verify it's logged to both CSV and Firestore.

### 4. Stop/Restart Container
Scale down and up the Cloud Run service to verify logs persist:
```bash
# Container restarts, logs should still be in Firestore
gcloud run services update-traffic tradingview-webhook --region=asia-south1 --no-traffic
# Wait 30 seconds
gcloud run services update-traffic tradingview-webhook --region=asia-south1 --to-revisions=LATEST=100
```

## Troubleshooting

### Error: "Permission denied on resource project quantlab-bot"
- **Cause**: Service account doesn't have Firestore permissions
- **Fix**: Run the `gcloud projects add-iam-policy-binding` command above with Project Owner/Editor account

### Error: "Firestore not available"
- **Cause**: google-cloud-firestore package not installed
- **Fix**: Cloud Run should have automatically installed from requirements.txt during deployment
- **Verify**: Check Cloud Run logs: `gcloud run services logs read tradingview-webhook --region=asia-south1`

### Logs show in /logs but not in /logs/firestore
- **Cause**: Firestore permission issue or collection doesn't exist yet
- **Fix**: Check Cloud Run logs for permission errors; wait for first order to create collection

## Previous Order Recovery

Once Firestore is set up, new orders will be persisted. **Previous orders from this morning (UTIAMC rejection) are lost** because:
1. They were only logged to CSV (ephemeral)
2. The container was recycled or restarted
3. The CSV file was deleted

**Future orders will be recoverable** because they'll be in Firestore (persistent).

## Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| Code Implementation | ✅ Done | Deployed in revision 00030 |
| Requirements Updated | ✅ Done | google-cloud-firestore added |
| Firestore Permissions | ❌ Pending | Needs Project Editor to grant |
| API Endpoint | ✅ Ready | /logs/firestore available |
| Testing | ⏸ Blocked | Waiting for permissions |
| CSV Logging | ✅ Works | Ephemeral (lost on restart) |

