# Cloud Monitoring & Alerting Setup Guide

## Overview

This guide provides step-by-step instructions to set up Cloud Monitoring dashboards, alert policies, and uptime checks for the TradingView webhook service.

## Prerequisites

- Project Owner or Editor permissions on `tradingview-webhook-prod`
- Google Cloud SDK installed
- Webhook service deployed on Cloud Run

## 1. Cloud Monitoring Dashboard Setup

### Create Dashboard via Google Cloud Console

1. Go to **Cloud Monitoring** → **Dashboards**
2. Click **Create Dashboard**
3. Name: "TradingView Webhook Production"
4. Add widgets for:

#### Widget 1: Request Rate
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/request_count`
- **Resource**: Cloud Run Revision (tradingview-webhook)
- **Aggregation**: 60-second alignment, ALIGN_RATE
- **Chart Title**: "Requests per Second"

#### Widget 2: Error Rate
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/request_count`
- **Filter**: Add metric.response_code_class="5xx"
- **Aggregation**: 60-second alignment, ALIGN_RATE
- **Chart Title**: "Error Rate (5xx responses)"

#### Widget 3: Request Latency
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/request_latencies`
- **Aggregation**: 60-second alignment, ALIGN_PERCENTILE_95
- **Chart Title**: "P95 Request Latency (ms)"

#### Widget 4: Container Memory
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/container_memory_utilization`
- **Aggregation**: 60-second alignment, ALIGN_MEAN
- **Chart Title**: "Memory Utilization (%)"

#### Widget 5: Container CPU
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/container_cpu_utilization`
- **Aggregation**: 60-second alignment, ALIGN_MEAN
- **Chart Title**: "CPU Utilization (%)"

#### Widget 6: Instance Count
- **Type**: Line Chart
- **Metric**: `run.googleapis.com/instance_count`
- **Aggregation**: ALIGN_MAX
- **Chart Title**: "Active Instances (0-3)"

### Save Dashboard

Click **Save** to persist the dashboard.

**Dashboard URL**: https://console.cloud.google.com/monitoring/dashboards

---

## 2. Alert Policies Setup

### Alert Policy 1: High Error Rate

**Create via Console**:
1. Go to **Cloud Monitoring** → **Alert Policies**
2. Click **Create Policy**
3. Configure:

**Condition**:
- Metric: `run.googleapis.com/request_count`
- Filter: `metric.response_code_class="5xx"`
- Threshold: > 5% of requests (calculate based on typical traffic)
- Duration: 5 minutes
- Comparison: COMPARISON_GT

**Notification Channel**:
- Email (add your email)
- Webhook (optional, for Slack/Teams integration)

**Alert Name**: "High Error Rate on Webhook Service"

### Alert Policy 2: High Latency

**Condition**:
- Metric: `run.googleapis.com/request_latencies`
- Aggregation: ALIGN_PERCENTILE_95
- Threshold: > 5000ms (5 seconds)
- Duration: 5 minutes

**Notification Channel**: Email + Webhook

**Alert Name**: "High Request Latency on Webhook Service"

### Alert Policy 3: Memory Usage

**Condition**:
- Metric: `run.googleapis.com/container_memory_utilization`
- Threshold: > 80%
- Duration: 5 minutes

**Notification Channel**: Email

**Alert Name**: "High Memory Usage on Webhook Service"

### Alert Policy 4: Service Unavailable

**Condition**:
- Metric: `run.googleapis.com/request_count`
- Threshold: = 0 (no requests for 5 minutes)
- Duration: 5 minutes

**Notification Channel**: Email + Webhook

**Alert Name**: "Webhook Service Unavailable"

---

## 3. Uptime Checks Setup

### Create Uptime Check via Console

1. Go to **Cloud Monitoring** → **Uptime checks**
2. Click **Create Uptime Check**
3. Configure:

**Protocol**: HTTPS  
**Hostname**: `tradingview-webhook-86335712552.asia-south1.run.app`  
**Path**: `/logs`  
**Port**: 443  
**Check Interval**: 60 seconds  
**Timeout**: 10 seconds  

**Advanced Options**:
- Auth: None
- Custom Headers: None
- Expected Response Status: 200 OK
- Expected Response Body: (leave empty)

**Monitoring Regions**:
- Select: us-east1, europe-west1, asia-south1

**Name**: "TradingView Webhook Uptime Check"

**Save** the uptime check.

### Create Alert from Uptime Check

1. From the uptime check, click **Create Alert Policy**
2. Configure:

**Condition**:
- Uptime Check: TradingView Webhook Uptime Check
- Failure Threshold: 2 consecutive failures
- Duration: 2 minutes

**Notification Channel**: Email + SMS (if critical)

**Alert Name**: "Webhook Service Uptime Alert"

---

## 4. Notification Channels Setup

### Email Notifications

1. Go to **Cloud Monitoring** → **Notification Channels**
2. Click **Create Notification Channel**
3. **Type**: Email
4. **Email Address**: your-email@example.com
5. **Display Name**: "DevOps Team Email"
6. Click **Create**

### Slack Integration (Optional)

1. **Type**: Slack
2. **Channel ID**: Get from Slack workspace settings
3. **Display Name**: "Alerts to DevOps Channel"
4. Click **Create**

### PagerDuty Integration (Optional)

1. **Type**: PagerDuty
2. **Integration Key**: Get from PagerDuty account
3. **Display Name**: "PagerDuty Escalation"
4. Click **Create**

---

## 5. Custom Metrics Setup

### Log-based Metrics

Create custom metrics from application logs:

1. Go to **Cloud Logging** → **Logs-based Metrics**
2. Click **Create Metric**
3. **Name**: `custom.googleapis.com/webhook/order_processed`
4. **Filter**: 
   ```
   resource.type="cloud_run_revision"
   AND resource.labels.service_name="tradingview-webhook"
   AND jsonPayload.status="success"
   ```
5. **Metric Type**: Counter
6. **Value Field**: (leave empty for count)

### Create Alert on Custom Metric

1. Create new Alert Policy
2. **Condition**:
   - Metric: `custom.googleapis.com/webhook/order_processed`
   - Threshold: > 0 (ensure orders are being processed)
   - Duration: 5 minutes
3. **Alert Name**: "Orders Processing Alert"

---

## 6. Logs Configuration

### Log Router Filters

Go to **Cloud Logging** → **Log Router** to ensure logs are being captured:

**Filter 1 - Application Logs**:
```
resource.type="cloud_run_revision"
AND resource.labels.service_name="tradingview-webhook"
```

**Filter 2 - Errors Only**:
```
resource.type="cloud_run_revision"
AND resource.labels.service_name="tradingview-webhook"
AND severity="ERROR"
```

**Retention**: 30 days (default), increase to 90 days if needed

### Log Sink for Long-term Storage

Create a sink to export logs to BigQuery for analysis:

1. Go to **Cloud Logging** → **Log Router**
2. Click **Create Sink**
3. **Name**: `webhook-logs-to-bigquery`
4. **Destination**: BigQuery
5. **Filter**: (use application logs filter above)
6. **Create**

---

## 7. Grafana Integration (Optional)

### Connect Grafana to Cloud Monitoring

1. Install Grafana (local or cloud instance)
2. Add Data Source:
   - **Type**: Google Cloud Monitoring
   - **Authentication**: Service Account Key
   - **Project**: tradingview-webhook-prod
3. Create Dashboard:
   - Add panels for metrics from Cloud Monitoring
   - Set refresh interval: 30 seconds

---

## 8. View Metrics and Alerts

### Dashboard Access URLs

```
Monitoring Dashboards:
https://console.cloud.google.com/monitoring/dashboards

Alert Policies:
https://console.cloud.google.com/monitoring/alertpolicies

Uptime Checks:
https://console.cloud.google.com/monitoring/uptime

Logs:
https://console.cloud.google.com/logs

Metrics:
https://console.cloud.google.com/monitoring/metrics-explorer
```

### Using gcloud CLI

```bash
# List alert policies
gcloud alpha monitoring policies list --format=table

# Describe specific policy
gcloud alpha monitoring policies describe <POLICY_ID>

# List uptime checks
gcloud monitoring uptime list

# View recent alerts
gcloud logging read \
  'resource.type="cloud_run_revision" AND severity="ERROR"' \
  --limit=50 \
  --format=json
```

---

## 9. Alert Response Playbook

### When You Receive an Alert

**High Error Rate Alert**:
1. Check dashboard for error pattern
2. Review logs: `gcloud run services logs read tradingview-webhook --limit=50`
3. Check if service was recently deployed
4. If critical: Roll back to previous revision
5. Post incident review

**High Latency Alert**:
1. Check CPU/Memory utilization
2. Review request queue size
3. Check for slow external API calls
4. Scale up if needed: `gcloud run services update tradingview-webhook --memory=2Gi`

**Uptime Check Failed**:
1. Verify service is running: `gcloud run services describe tradingview-webhook`
2. Check if service is accessible: `curl -v https://webhook-url/logs`
3. Review logs for startup errors
4. Check Cloud Run quotas

**Memory Usage High**:
1. Check for memory leaks in logs
2. Review recent deployments
3. Increase memory allocation if needed
4. Consider caching optimization

---

## 10. Testing Alerts

### Trigger Test Alert

```bash
# Simulate error by calling non-existent endpoint
curl -i "https://tradingview-webhook-86335712552.asia-south1.run.app/nonexistent"

# Check if alert fires within 5 minutes
# Verify notification received
```

### Disable Alerts During Maintenance

```bash
# Temporarily disable alert policy
gcloud alpha monitoring policies update <POLICY_ID> \
  --update-enabled=false

# Enable again
gcloud alpha monitoring policies update <POLICY_ID> \
  --update-enabled=true
```

---

## 11. Best Practices

✅ **Do**:
- Set meaningful threshold values based on your SLOs
- Use multiple notification channels (email + webhook)
- Review alerts regularly for false positives
- Document alert runbooks in your team wiki
- Test alerts monthly
- Set up escalation policies (email → SMS → PagerDuty)

❌ **Don't**:
- Set overly sensitive thresholds (causes alert fatigue)
- Ignore alerts (acknowledging reduces fatigue)
- Leave default thresholds unchanged
- Skip testing alerts before going to production
- Keep irrelevant alerts enabled

---

## 12. Monitoring SLOs

Define Service Level Objectives:

| SLO | Target | Measurement |
|-----|--------|-------------|
| Availability | 99.9% | Uptime checks pass |
| Error Rate | <1% | 5xx errors / total requests |
| Latency (P95) | <2s | 95th percentile request time |
| Response Time | <500ms | Mean request duration |

**Create SLO Dashboard**:
1. Go to **Cloud Monitoring** → **SLOs**
2. Click **Create SLO**
3. Configure for each objective above
4. Set alert when SLO is at risk

---

## Resources

- [Cloud Monitoring Docs](https://cloud.google.com/monitoring/docs)
- [Alert Policy Documentation](https://cloud.google.com/monitoring/alerts/basics)
- [Uptime Checks Guide](https://cloud.google.com/monitoring/uptime-checks)
- [Cloud Logging Docs](https://cloud.google.com/logging/docs)
- [SLOs Guide](https://cloud.google.com/monitoring/slos)

