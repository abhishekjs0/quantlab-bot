# QuantLab Startup Prompt v3.1

**Updated**: January 2, 2026  
**Purpose**: Initialize AI agent session with complete system context

---

## ⚠️ CRITICAL POLICIES

1. **GIT PUSH**: Do NOT auto-push. Only push when explicitly requested.
2. **BACKTEST**: 
   - `backtest` → `runners.run_basket` (full analysis with reports)
   - `fast backtest` → `runners.fast_run_basket` (quick metrics only)
3. **TIMEZONE**: Always use IST (Indian Standard Time = UTC+5:30)
4. **TOKEN VALIDITY**: Dhan tokens are valid for max 24 hours
5. **STRATEGIES**: All strategies must import indicators from `utils.indicators`

---

## 🚀 Quick Start

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace
source .venv/bin/activate
python3 config.py  # Verify system ready
```

---

## 📁 Repository Structure

```
quantlab-workspace/
├── core/                    # Backtesting engine
│   ├── engine.py           # Event-driven backtest execution
│   ├── strategy.py         # Base Strategy class with I() wrapper
│   ├── metrics.py          # Performance calculations
│   └── config.py           # BrokerConfig (capital, commission, slippage)
│
├── strategies/              # 15 trading strategies
│   ├── bollinger_rsi.py    # Bollinger + RSI confluence
│   ├── candlestick_patterns.py  # 20+ patterns with filters
│   ├── dual_tema_lsma.py   # TEMA/LSMA crossover
│   ├── ema_crossover.py    # EMA 89/144 with RSI pyramiding
│   ├── ichimoku_simple.py  # Lean Ichimoku (filters disabled)
│   ├── ichimoku_cloud.py   # Full Ichimoku with cloud/Tenkan/Kijun logic
│   ├── kama_crossover_filtered.py  # KAMA with Aroon/DI/CCI filters
│   ├── knoxville.py        # Knoxville divergence
│   ├── stoch_rsi_pyramid_long.py  # Stoch RSI with pyramiding
│   ├── supertrend_dema.py  # Supertrend + DEMA combo
│   ├── supertrend_vix_atr.py  # Supertrend with VIX/ATR filters
│   ├── tema_lsma_crossover.py  # ★ BEST: TEMA/LSMA with weekly filters (PF 3.13)
│   ├── weekly_rotation.py  # Weekly rotation with ADX filter
│   └── triple_ema_aligned.py  # Triple EMA alignment
│
├── runners/                 # Execution scripts
│   ├── run_basket.py       # Full backtest with reports (4600+ lines)
│   ├── fast_run_basket.py  # Quick metrics only (850 lines)
│   ├── max_trades.py       # Generate consolidated trades CSV (1270 lines)
│   └── standard_run_basket.py  # Standard backtest with indicators (4600+ lines)
│
├── utils/                   # Shared utilities
│   ├── indicators.py       # 25+ technical indicators (SMA, EMA, RSI, ATR, etc.)
│   └── production_utils.py # Rate limiting, circuit breakers
│
├── data/                    # Market data
│   ├── basket_*.txt        # Symbol baskets (test, small, mid, large, mega)
│   ├── cache/              # Historical OHLCV data (CSV)
│   └── loaders.py          # Data loading utilities
│
├── scripts/                 # Utility scripts
│   ├── dhan_fetch_data.py  # Unified data fetcher (supports INDIAVIX, NIFTY50)
│   ├── check_strategy_imports.py  # Validates strategy imports
│   └── export_webhook_logs.py  # Export Firestore logs
│
├── tests/                   # Test suite (66 passing)
│
├── webhook-service/         # Production trading (Cloud Run)
│   ├── app.py              # FastAPI webhook server
│   ├── dhan_client.py      # Dhan API wrapper
│   ├── dhan_auth.py        # OAuth token management
│   ├── signal_queue.py     # Firestore-based queuing
│   └── docs/               # Service-specific docs
│
└── docs/                    # Documentation (this folder)
```

---

## 🌐 Production Infrastructure

### Cloud Run Service
- **URL**: `https://tradingview-webhook-cgy4m5alfq-el.a.run.app`
- **Project**: `tradingview-webhook-prod` (86335712552)
- **Region**: `asia-south1`
- **Revision**: 00037+

### Cron Jobs (Token Refresh)
| Job | Schedule (IST) | Purpose |
|-----|----------------|---------|
| `dhan-token-refresh` | 08:00 | Morning refresh |
| `dhan-token-refresh-evening` | 20:00 | Evening refresh |

### Key Endpoints
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/webhook` | POST | TradingView alerts |
| `/health` | GET | Health check |
| `/refresh-token` | POST | Manual token refresh |
| `/process-queue` | POST | Process queued signals |
| `/logs/firestore` | GET | View Firestore logs |

---

## 📊 Core Components

### 1. Backtesting Engine (`core/engine.py`)
- Event-driven bar-by-bar processing
- **Next-open execution**: Signals on close → fills at next open
- No lookahead bias guaranteed
- Supports: Daily, 75m, 125m, 1m, 5m, 15m, 25m, 60m timeframes

### 2. Strategy Base Class (`core/strategy.py`)
```python
class Strategy:
    def I(self, func, *args, **kwargs):
        """Indicator wrapper - caches results, handles NaN"""
        
    def prepare(self, df) -> pd.DataFrame:
        """Called once before backtest - initialize indicators"""
        
    def on_bar(self, ts, row, state) -> tuple[signal, reason]:
        """Called each bar - return (1=BUY, -1=SELL, 0=HOLD), reason"""
        
    def on_entry(self, entry_time, entry_price, state) -> dict:
        """Called on position entry - return stop_loss config"""
```

### 3. Indicators (`utils/indicators.py`)
All strategies MUST use these centralized indicators:
- **Momentum**: RSI, StochasticRSI, MACD, CCI, MFI
- **Trend**: EMA, SMA, KAMA, TEMA, LSMA, Ichimoku, ADX, Aroon
- **Volatility**: ATR, BollingerBands, DonchianChannels
- **Volume**: VWAP

### 4. BrokerConfig (`core/config.py`)
```python
BrokerConfig(
    initial_capital=100_000,
    qty_pct_of_equity=0.05,    # 5% per trade
    commission_pct=0.11,        # 0.22% round-trip
    slippage_ticks=3,
    execute_on_next_open=True,  # CRITICAL
)
```

---

## 🔧 Common Commands

### Running Backtests
```bash
# Fast backtest (recommended for quick testing)
PYTHONPATH=. python runners/fast_run_basket.py --strategy tema_lsma_crossover --basket_file data/baskets/basket_main.txt --interval 1d

# Full backtest with reports
PYTHONPATH=. python runners/run_basket.py --basket_file data/baskets/basket_main.txt --strategy tema_lsma_crossover --use_cache_only

# Generate consolidated trades with all indicators (for analysis)
PYTHONPATH=. python runners/max_trades.py --strategy tema_lsma_crossover --basket_file data/baskets/basket_main.txt --interval 1d
```

### 🏆 Current Best Strategy: TEMA LSMA Crossover
```
Configuration (strategies/tema_lsma_crossover.py):
├── Entry: TEMA(25) crosses above LSMA(100), executes next bar open
├── Exit: TEMA(25) crosses below LSMA(100)
├── Filters (all enabled):
│   ├── Weekly Candle Colour = Green (close > open)
│   ├── Weekly KER(10) > 0.4 (trending market)
│   └── Daily ATR% > 3.0% (volatility filter)
├── Take Profits: TP1=5%/0%, TP2=10%/0% (no partial exits, all at signal close)
└── Performance (MAX window):
    ├── Profit Factor: 3.13
    ├── Win Rate: 50.4%
    ├── Total Trades: 2,152
    └── Net P&L: 765,453 INR (7.5% avg per trade)
```

### Fetching Data
```bash
# Fetch daily data for basket
python scripts/dhan_fetch_data.py --basket large --timeframe 1d

# Fetch specific symbols
python scripts/dhan_fetch_data.py --symbols RELIANCE,TCS --timeframe 1d

# Fetch India VIX
python scripts/dhan_fetch_data.py --symbols INDIAVIX --timeframe 1d
```

### Testing
```bash
# Run all unit tests
python -m pytest tests/ -v --ignore=tests/test_integration_basket.py --ignore=tests/test_parity_basket.py

# Run specific test
python -m pytest tests/test_strategy_wrapper.py -v

# Check strategy imports
python scripts/check_strategy_imports.py
```

### Webhook Service
```bash
# Deploy
cd webhook-service && gcloud run deploy tradingview-webhook --source .

# Check logs
gcloud logging read 'resource.type="cloud_run_revision"' \
  --project=tradingview-webhook-prod --limit=20

# Manual token refresh
curl -X POST https://tradingview-webhook-cgy4m5alfq-el.a.run.app/refresh-token
```

---

## 📚 Documentation Reference

| Document | Purpose | When to Read |
|----------|---------|--------------|
| `docs/STARTUP_PROMPT.md` | Agent initialization guide | Start of session |
| `docs/JANITOR_PROMPT.md` | End-of-session cleanup | End of session |
| `docs/BACKTEST_GUIDE.md` | Complete backtesting reference | Running backtests, understanding reports |
| `docs/WRITING_STRATEGIES.md` | Strategy development guide | Creating new strategies |
| `webhook-service/docs/WEBHOOK_SERVICE_GUIDE.md` | Complete webhook service guide | Deployment, OAuth, order routing |
| `webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md` | Dhan API credentials | Getting API keys, TOTP setup |

---

## 🔍 Quick Health Checks

### Check Token Status
```bash
curl https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health | python -m json.tool
```

### Check Recent Errors
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=tradingview-webhook-prod --limit=10
```

### Verify Data Cache
```bash
ls -la data/cache/*.csv | wc -l  # Count cached files
```

---

## ⚡ Session Checklist

Before starting work:
- [ ] Activate venv: `source .venv/bin/activate`
- [ ] Check git status: `git status`
- [ ] Run quick test: `python -m pytest tests/test_smoke.py -v`

Before committing:
- [ ] Run tests: `python -m pytest tests/ -v --ignore=tests/test_integration_basket.py`
- [ ] Check strategy imports: `python scripts/check_strategy_imports.py`
- [ ] Verify no debug prints: `grep -rn "print(" strategies/*.py | grep -v "^#"`

---

## 🎯 Key Design Decisions

1. **Indicators centralized**: All in `utils/indicators.py` - no `ta.` or inline calcs
2. **Next-open execution**: Prevents lookahead bias
3. **Firestore logging**: Replaces SQLite for cloud persistence
4. **Signal queuing**: Handles after-hours/weekend signals
5. **Pre-commit hooks**: Enforce strategy import rules
