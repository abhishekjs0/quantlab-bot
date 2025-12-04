# QuantLab Startup Prompt v2.5

**Updated**: December 4, 2025  
**Purpose**: Initialize AI agent session with essential context

---

## ⚠️ CRITICAL POLICIES

1. **GIT PUSH**: Do NOT auto-push. Only push when explicitly requested.
2. **BACKTEST**: 
   - `backtest` → `runners.run_basket` (full analysis)
   - `fast backtest` → `runners.fast_run_basket` (quick metrics)
3. **TIMEZONE**: Always use IST (Indian Standard Time = UTC+5:30)
4. **TOKEN VALIDITY**: Dhan tokens are valid for max 24 hours

---

## 🚀 Quick Start (Run First)

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace
source .venv/bin/activate
python3 config.py  # Verify system ready
```

---

## 📊 Repository Overview

| Component | Location | Purpose |
|-----------|----------|---------|
| **Backtesting** | `core/` | Event-driven engine |
| **Strategies** | `strategies/` | 15 trading strategies |
| **Execution** | `runners/` | Portfolio backtesting |
| **Data** | `data/` | Baskets & market data |
| **Tests** | `tests/` | 88 passing, 14 skipped |
| **Webhook** | `webhook-service/` | TradingView → Dhan (Cloud Run) |
| **Docs** | `docs/` | 9 documentation files |

---

## 🌐 Production Infrastructure

### Cloud Run Service
- **URL**: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app`
- **Project**: `tradingview-webhook-prod` (86335712552)
- **Region**: `asia-east1`

### Cron Jobs (Token Refresh)
| Job | Schedule (IST) | Purpose |
|-----|----------------|---------|
| `dhan-token-refresh` | 08:00 | Morning refresh |
| `dhan-token-refresh-evening` | 20:00 | Evening refresh |

### Key Endpoints
- `POST /webhook` - TradingView alerts
- `GET /health` - Health check
- `POST /refresh-token` - Manual token refresh
- `POST /oauth/callback` - Dhan OAuth callback

---

## 🔍 Quick Health Checks

### 1. Check Token Status
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND textPayload=~"token"' \
  --project=tradingview-webhook-prod --limit=5 --format="table(timestamp,textPayload)"
```

### 2. Check Recent Errors
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND (textPayload=~"error" OR textPayload=~"ERROR" OR textPayload=~"failed")' \
  --project=tradingview-webhook-prod --limit=10 --format="table(timestamp,textPayload)"
```

### 3. Manual Token Refresh
```bash
curl -X POST https://tradingview-webhook-cgy4m5alfq-el.a.run.app/refresh-token
```

### 4. Verify Cron Jobs
```bash
gcloud scheduler jobs list --project=tradingview-webhook-prod --location=asia-south1
```

---

## 📁 Key Files Reference

### Strategies
```
strategies/
├── ema_crossover.py           # EMA crossover
├── ichimoku.py                # Ichimoku cloud
├── kama_crossover.py          # KAMA-based
├── stoch_rsi_ob_long.py       # Stochastic RSI
├── envelope_kd.py             # Envelope + KD
└── template.py                # Development template
```

### Data Baskets
```
data/
├── basket_default.txt         # 162 symbols
├── basket_mega.txt            # 73 symbols
├── basket_large.txt           # 103 symbols
├── basket_mid.txt             # 51 symbols
├── basket_small.txt           # 99 symbols
└── basket_test.txt            # 3 symbols (for testing)
```

### Documentation
```
docs/
├── QUANTLAB_GUIDE.md          # System architecture
├── BACKTEST_GUIDE.md          # Backtesting guide
├── STRATEGIES.md              # Strategy development
├── WEBHOOK_SERVICE_COMPLETE_GUIDE.md
├── STARTUP_PROMPT.md          # This file
└── JANITOR_PROMPT.md          # Session cleanup
```

---

## 🎯 Common Commands

### Run Backtest
```bash
python3 -m runners.run_basket --basket mega --strategy ema_crossover --timeframe 1d
```

### Run Tests
```bash
python3 -m pytest tests/ -v --tb=short
```

### Code Quality
```bash
black . && isort . && ruff check .
```

### Fetch Data
```bash
python3 scripts/dhan_fetch_data.py --basket mega --timeframe 1d
```

---

## 📋 Session Workflow

### Start
1. Read this prompt
2. Run quick start commands
3. Check `git status`

### During
1. Make changes
2. Run tests frequently
3. Commit regularly (don't push)

### End
1. Use JANITOR_PROMPT.md
2. Run full test suite
3. Commit with clear message
4. Push only when requested

---

## 🔗 Essential Links

- **GitHub**: https://github.com/abhishekjs0/quantlab-bot
- **Cloud Console**: https://console.cloud.google.com/run?project=tradingview-webhook-prod
- **Logs**: https://console.cloud.google.com/logs?project=tradingview-webhook-prod
- **Scheduler**: https://console.cloud.google.com/cloudscheduler?project=tradingview-webhook-prod

---

## 🚨 Troubleshooting

### Token Invalid
1. Check cron job URLs are correct
2. Manually trigger: `curl -X POST .../refresh-token`
3. Check logs for CONSENT_LIMIT_EXCEED (Dhan rate limit)

### 503 Service Unavailable  
- Wrong Cloud Run URL being used
- Check cron job configuration

### Tests Failing
```bash
python3 -m pytest tests/ -v --tb=long  # Get detailed error output
```

### Webhook Not Working
1. Check `/health` endpoint
2. Verify webhook secret matches TradingView
3. Check Cloud Run logs for errors
