# Documentation Index

## 🏗️ Project Architecture (Updated Nov 2025)

### Two Separate Systems

**1. Main Project (`quantlab-workspace/`)** - Strategy Development & Backtesting
- **Purpose:** Develop trading strategies, run backtests, analyze results
- **Location:** Local development on your Mac
- **Documentation:** This folder (`docs/`)
- **Dependencies:** Full stack (pandas, matplotlib, scipy, etc.)
- **Use Cases:** Strategy development, backtesting, data analysis, report generation

**2. Webhook Service (`webhook-service/`)** - Production Trading
- **Purpose:** Receive TradingView alerts and execute live orders via Dhan
- **Location:** Same repo, deployed independently to Google Cloud Run (24/7 availability)
- **Documentation:** `webhook-service/docs/` (self-contained)
- **Dependencies:** Minimal (5 packages: fastapi, uvicorn, pydantic, dhanhq, python-dotenv)
- **Use Cases:** Live order execution, 24/7 webhook server, production trading
- **Deployment:** `cd webhook-service && gcloud run deploy --source .`

**Why Two Systems?**

**Clean Separation of Concerns:**
- Main project has heavy dependencies (backtesting, data analysis) not needed for live trading
- Webhook service is lightweight (~27MB) for fast cloud deployment
- Different update cycles (strategies vs production webhook)
- No risk of breaking live trading when developing strategies
- **Both in same repo** for easy setup - Google Cloud only deploys `webhook-service/` folder

**Cost & Performance:**
- Webhook service: $0/month on Google Cloud Run free tier
- Main project: Local development, no cloud costs
- Small webhook service = faster deployments (30 seconds)

**How They Work Together:**
```
[Main Project] → Develop Strategy → Backtest → Validate
                                                   ↓
[TradingView] → Configure Alert → [Webhook Service] → [Dhan Trading]
```

### Testing Webhook Service

See section "🧪 Testing Webhook Service" below for complete testing guide.

---

## 📚 Main Project Documentation (Backtesting & Strategy Development)

### Getting Started (Essential Reading)
1. **`STARTUP_PROMPT.md`** ⭐ START HERE FOR DEVELOPMENT
   - Initial setup and dependencies
   - Environment configuration
   - Virtual environment activation
   - First run guide
   - Common issues and solutions

2. **`QUANTLAB_GUIDE.md`** ⭐ FRAMEWORK OVERVIEW
   - Complete framework documentation
   - System architecture
   - Strategy development guide
   - Backtesting workflow
   - Project structure navigation

### Backtesting & Analysis
3. **`BACKTEST_GUIDE.md`** ⭐ COMPREHENSIVE REFERENCE
   - Running backtests (default and advanced methods)
   - Symbol mapping and data setup
   - Data validation framework (SHA256 fingerprinting)
   - Cache management
   - **NEW**: Open trades metrics calculation and fixes (Dec 2, 2025)
   - Report interpretation
   - Stop loss optimization analysis
   - Troubleshooting guide

4. **`OPEN_TRADES_VALIDATION_REPORT.md`** 🔴 LATEST - VALIDATION RESULTS
   - Open trades metrics validation (Dec 2, 2025)
   - Issues fixed and verified
   - Code changes applied
   - Example trade analysis (ICICIBANK, KOTAKBANK, LT)
   - Why holding_days = 0 for same-day entries (correct behavior)
   - Interpretation guide for open position metrics

### Strategy Development
5. **`STRATEGIES.md`**
   - Available trading strategies
   - Creating new strategies
   - Strategy parameters and configuration
   - Strategy testing and validation

6. **`DHAN_COMPREHENSIVE_GUIDE.md`**
   - Dhan API reference
   - Historical data fetching
   - Order types and execution
   - Multi-timeframe aggregation
   - Webhook integration

### Production Deployment
7. **`WEBHOOK_SERVICE_COMPLETE_GUIDE.md`** 🚀 PRODUCTION REFERENCE
   - Complete webhook service setup
   - OAuth implementation (callback-based)
   - Order routing logic and market hours
   - API endpoints documentation
   - Deployment instructions (Cloud Run)
   - Token management and refresh
   - Monitoring and troubleshooting

### Development & Credentials
8. **`DHAN_CREDENTIALS_GUIDE.md`**
   - Setting up Dhan API credentials
   - Authentication methods
   - Sandbox vs production setup
   - Secret Manager configuration

9. **`DHAN_OAUTH_COMPLETE_GUIDE.md`**
   - OAuth flow explanation
   - Token refresh procedures
   - Callback-based authentication

### Additional References
10. **`DHAN_LIVE_TRADING_GUIDE.md`**
    - Live order execution via webhook
    - Order types and product types
    - Risk management

11. **`JANITOR_PROMPT.md`**
    - Repository maintenance procedures
    - Cleanup and git operations
    - End-of-session checklist

---

## 🚀 Webhook Service Documentation (Production Trading)

### **NEW: Complete Deployment Guide** ⭐ ALL-IN-ONE
**`webhook-service/docs/COMPLETE_DEPLOYMENT_GUIDE.md`** (26-Nov-2025)

**Consolidates 4 previous guides into one comprehensive resource:**
- OAuth Authentication (3-step flow, browser automation, auto-refresh)
- Architecture & Components (FastAPI, config management, token storage)
- Live Trading Operations (order types, market hours, multi-leg orders)
- Configuration Management (centralized config, new modules)
- Monitoring & Maintenance (health checks, daily checklist, logs)
- Troubleshooting (token issues, cron job, Telegram bot)
- Security Best Practices (credentials, API limits, rate limiting)
- Advanced Features (production utilities, VIX integration, sell validation)

**Quick Start**: 15 minutes from zero to first live order
**Status**: Production ready, deployed, OAuth auto-refreshing daily

---

### Original Guides (Still Available)

**⚠️ For webhook/trading documentation, see: `webhook-service/docs/`**

The webhook service is completely standalone with its own documentation:

- **`webhook-service/README.md`** - Deployment guide (Google Cloud Run)
- **`webhook-service/docs/MARKET_ALERTS_GUIDE.md`** - Complete beginner-friendly deployment guide
- **`webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md`** - Live trading & order types
- **`webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md`** - Credentials setup
- **`webhook-service/docs/TRADINGVIEW_POST.md`** - Cloud Run webhook setup

**Why separate?**
- Webhook service has minimal dependencies (5 packages vs 19)
- Can be deployed independently to cloud
- Different purpose (live trading vs backtesting)
- No code duplication between projects
- Small size (~27MB) for fast cloud deployments

### Webhook Service Contents (13 files)

**Core Application:**
- `app.py` - FastAPI webhook server (IST timestamps)
- `dhan_client.py` - Dhan API wrapper for order execution
- `security_id_list.csv` - 217,959 symbol mappings (26MB)

**Configuration:**
- `.env` - Your Dhan credentials (configured)
- `requirements.txt` - Minimal dependencies (5 packages)
- `Dockerfile` - Docker configuration for Cloud Run

**Documentation:**
- 8 comprehensive guides in root + `docs/` folder
- Cloud deployment focused (no local/ngrok setup)

**Cost:** $0/month (within Google Cloud Run free tier)

---

## 🎯 Navigation Guide

### Main Project Tasks

**Understand system architecture:**
→ Read `ARCHITECTURE_AND_DATA_QUALITY.md` (sections 1-4)

**Develop new strategy:**
→ Read `STRATEGIES.md` + `QUANTLAB_GUIDE.md`

**Run backtests:**
→ Read `BACKTEST_GUIDE.md` or `FAST_RUN_BASKET.md`

**Implement new feature:**
→ Read `IMPLEMENTATION_ROADMAP.md` (pick Feature 1, 2, or 3)

**Check test status:**
→ Read `TEST_STATUS.md`

### Webhook/Trading Tasks

**Deploy webhook server:**
→ Go to `webhook-service/docs/` and read `MARKET_ALERTS_GUIDE.md`

**Configure TradingView alerts:****
→ Read `webhook-service/docs/TRADINGVIEW_POST.md`

**Setup Dhan credentials:**
→ Read `webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md`

**Understand order types:**
→ Read `webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md`

---

## 📊 Main Project Status

| Component | Status | Location |
|-----------|--------|----------|
| Strategy Development | ✅ Working | `strategies/` |
| Backtesting Engine | ✅ Working | `core/engine.py` |
| Data Loaders | ✅ Working | `data/loaders.py` |
| Report Generation | ✅ Working | `core/report.py` |
| Multi-timeframe | 🟡 Partial | `core/multi_timeframe.py` |
| Tests | ✅ 31 passing | `tests/` |

---

## 🚀 Quick Start for New Session

### For Strategy Development:
1. Read `QUANTLAB_GUIDE.md` (15 min)
2. Review `STRATEGIES.md` (10 min)
3. Run a backtest: `python runners/run_basket.py --strategy ema_crossover --basket_size default --interval 1d`

### For Live Trading:
1. Go to `webhook-service/docs/` folder
2. Read `MARKET_ALERTS_GUIDE.md`
3. Deploy: `gcloud run deploy tradingview-webhook --source .`

---

## 🧪 Testing Webhook Service

### Prerequisites
```bash
cd webhook-service

# Verify files present
ls -lh app.py dhan_client.py security_id_list.csv .env
```

### Test 1: Local Health Check

**Start server locally:**
```bash
cd webhook-service
python app.py
```

**In another terminal, test health:**
```bash
curl http://localhost:8080/health

# Expected response:
{
  "status": "healthy",
  "timestamp": "2025-11-21T10:30:00+05:30",
  "security_ids_loaded": 217959
}
```

### Test 2: Local Webhook POST

**Send test order:**
```bash
curl -X POST http://localhost:8080/webhook \
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
        "timenow": "2025-11-21T10:30:00Z"
      }
    }]
  }'

# Expected: Order logged to webhook_orders.csv with IST timestamp
# Check: tail webhook-service/webhook_orders.csv
```

### Test 3: Cloud Run Deployment Test

**Deploy to Cloud Run:**
```bash
cd webhook-service
gcloud run deploy tradingview-webhook --source .
```

**Get URL:**
```bash
WEBHOOK_URL=$(gcloud run services describe tradingview-webhook \
  --region=asia-south1 --format="value(status.url)")
echo $WEBHOOK_URL
```

**Test health:**
```bash
curl $WEBHOOK_URL/health
```

**Test webhook:**
```bash
curl -X POST $WEBHOOK_URL/webhook \
  -H "Content-Type: application/json" \
  -d '{ ... same JSON as Test 2 ... }'
```

**View logs:**
```bash
gcloud run services logs tail tradingview-webhook --region=asia-south1
```

### Test 4: TradingView Integration Test

1. **Create TradingView alert:**
   - Use Cloud Run URL: `https://YOUR-URL/webhook`
   - Paste test payload from Test 2

2. **Trigger alert manually**

3. **Check Cloud Run logs:**
```bash
gcloud run services logs read tradingview-webhook \
  --region=asia-south1 --limit=20
```

### Troubleshooting Tests

**Server won't start:**
```bash
# Check port not in use
lsof -i :8080

# Check .env file exists
cat webhook-service/.env | grep DHAN_
```

**Health check fails:**
```bash
# Check security_id_list.csv size
ls -lh webhook-service/security_id_list.csv
# Should be ~26MB

# Check Python environment
which python
python --version  # Should be 3.9+
```

**Orders not executing:**
```bash
# Check ENABLE_DHAN setting
grep ENABLE_DHAN webhook-service/.env
# Should be 'false' for testing, 'true' for live

# Update if needed:
gcloud run services update tradingview-webhook \
  --region=asia-south1 \
  --update-env-vars ENABLE_DHAN=true
```

---

## 📝 Recent Session Summary

**Strategies:**
- ✅ `strategies/ema_crossover.py` - Added signal_reason tracking
- ✅ `strategies/ichimoku.py` - Added signal_reason tracking  
- ✅ `strategies/knoxville.py` - Added signal_reason tracking

**Engine:**
- ✅ `core/engine.py` - Captures entry/exit signal reasons

**Export:**
- ✅ `runners/run_basket.py` - Uses signal_reason in Signal column

**Architecture:**
- ✅ Webhook service separated into standalone package
- ✅ No code duplication between main project and webhook service
- ✅ Clear separation: backtesting vs production trading

---

## ✨ Highlights

### What's Working Great
- ✅ Signal differentiation implemented and tested
- ✅ No look-ahead bias (verified)
- ✅ 31 tests passing, no failures
- ✅ Clean architecture documented
- ✅ Data quality guaranteed (Dhan adjusted data)
- ✅ Webhook service ready for cloud deployment

### What's Ready to Build Next
- 🟡 Intraday support (blueprint in IMPLEMENTATION_ROADMAP.md)
- 🟡 T+1 settlement (design complete)
- 🟡 HDFC cache fix (quick fix available)

---

## 🔗 External References

- **Dhan Historical Data:** https://dhanhq.co/docs/v2/historical-data/
- **Dhan Corporate Actions:** https://dhan.co/support/platforms/dhanhq-api/
- **Google Cloud Run:** https://cloud.google.com/run/docs
- **TradingView Webhooks:** https://www.tradingview.com/support/solutions/43000529348-about-webhooks/

---

## 📂 Repository Structure

```
quantlab-workspace/                 # Main project (backtesting)
├── strategies/                     # Trading strategies
├── core/                          # Backtesting engine
├── data/                          # Data loaders & baskets
├── runners/                       # Backtest runners
├── reports/                       # Backtest results
├── tests/                         # Unit tests
├── docs/                          # This documentation
└── webhook-service/               # Production trading (separate)
    ├── app.py                     # Webhook server
    ├── dhan_client.py             # Dhan API wrapper
    ├── Dockerfile                 # Cloud deployment
    ├── docs/                      # Webhook docs (separate)
    └── ...                        # See webhook-service/STRUCTURE.md
```

---

## 📞 Questions?

### Main Project Questions:
- **"Why no look-ahead bias?"** → ARCHITECTURE_AND_DATA_QUALITY.md Section 1
- **"How to implement intraday?"** → IMPLEMENTATION_ROADMAP.md Feature 1
- **"Why are some tests skipped?"** → TEST_STATUS.md
- **"How do I create a strategy?"** → STRATEGIES.md + QUANTLAB_GUIDE.md

### Webhook/Trading Questions:
- **"How do I deploy to cloud?"** → webhook-service/docs/MARKET_ALERTS_GUIDE.md
- **"How do I setup Dhan?"** → webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md
- **"How do I configure TradingView?"** → webhook-service/docs/TRADINGVIEW_POST.md
- **"What order types are supported?"** → webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md



