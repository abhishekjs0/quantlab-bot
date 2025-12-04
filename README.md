# QuantLab v2.2 - Professional Trading System

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)](https://github.com/features/actions)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting](https://img.shields.io/badge/linting-ruff-red.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Professional backtesting framework for Indian equities with clean architecture and comprehensive risk analysis**

**Status:** ✅ Production Ready | **Data Fetch Success Rate:** 99.5%

---

## 🚀 Quick Start

### Installation
```bash
git clone <repo> quantlab && cd quantlab
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python config.py  # Verify system ready
```

### Run a Backtest
```bash
# EMA Crossover on Mega Basket
python runners/run_basket.py --basket mega --strategy ema_crossover --timeframe 1d
```

### Fetch Historical Data
```bash
# Download 2 years of data
python scripts/dhan_fetch_data.py --basket large --timeframe 1d

# Multi-timeframe (25m → 75m, 125m automatic)
python scripts/dhan_fetch_data.py --basket mega --timeframe 25m
```

---

## 🏗️ Architecture

```
quantlab/
├── core/               # Event-driven backtesting engine
├── strategies/         # Trading strategies
├── runners/            # Portfolio backtesting & reporting
├── scripts/            # Unified data fetcher (dhan_fetch_data.py)
├── data/               # Market data & baskets
├── utils/              # Indicators & calculations
├── tests/              # Test suite
├── docs/               # Documentation
├── webhook-service/    # TradingView webhook service (Cloud Run)
└── viz/                # Visualization tools
```

---

## ✨ Key Features

### Development Workflow
- 🛠️ **Modern Setup**: Virtual environment with development dependencies
- 📋 **Quality Checks**: Automated linting, formatting, and testing
- 📚 **Documentation**: Comprehensive guides in `docs/`
- 🔄 **CI/CD**: GitHub Actions pipeline with matrix testing
- 🧪 **Testing**: 88+ tests passing with comprehensive coverage
- 🛡️ **Security**: Automated vulnerability scanning

### Risk Analytics
- **Individual Trade Drawdown**: Real intra-trade risk using OHLC data
- **Symbol-Level Max Drawdown**: Highest individual trade drawdown per symbol
- **Run-up Analysis**: Maximum favorable movement tracking
- **Stop Loss Framework**: Optional stop loss with performance comparison

### Comprehensive Reporting
- **Portfolio Key Metrics**: Net P&L, CAGR, Max Drawdown, Profit Factor
- **Consolidated Trades**: Detailed trade logs with entry/exit analysis
- **Equity Curves**: Daily and monthly portfolio progression
- **Multi-Timeframe Analysis**: 1Y, 3Y, 5Y, and ALL period comparisons

---

## 📊 Core Components

### 1. Backtesting Engine (`core/engine.py`)
- **Event-Driven:** Processes bars sequentially
- **Next-Open Execution:** Signals on current bar close → fills at next bar open
- **No Lookahead Bias:** Real-world execution model
- **Supports:** Daily, 75m, 125m, 1m, 5m, 15m, 25m, 60m timeframes
- **Features:** Pyramiding, per-lot stops, slippage modeling

**Key Config** (`core/config.py`):
```python
BrokerConfig(
    initial_capital=100_000,          # Starting capital
    qty_pct_of_equity=0.05,           # 5% per trade
    commission_pct=0.11,              # 0.22% round-trip
    slippage_ticks=3,                 # Realistic slippage
    execute_on_next_open=True,        # ← CRITICAL: Next bar execution
)
```

### 2. Data Fetcher (`scripts/dhan_fetch_data.py`)
- **Universal:** Any basket, symbol, or timeframe
- **Production-Ready:** Token validation, error recovery, smart caching
- **Multi-Timeframe:** Aggregates 25m → 75m, 125m automatically
- **Smart Chunking:** 90-day API limitations handled

**Usage:**
```bash
# Full basket
python scripts/dhan_fetch_data.py --basket large --timeframe 1d

# Multi-timeframe aggregation
python scripts/dhan_fetch_data.py --basket mega --timeframe 25m --days-back 730

# Specific symbols
python scripts/dhan_fetch_data.py --symbols RELIANCE,TCS --timeframe 1d
```

### 3. Strategies
Located in `strategies/`:
- **ema_crossover.py:** Fast/slow EMA crossover
- **ichimoku.py:** Ichimoku cloud with trend confirmation
- **kama_crossover.py:** KAMA-based crossover strategy
- **stoch_rsi_ob_long.py:** Stochastic RSI oversold/overbought
- **candlestick_patterns.py:** 20+ bullish patterns with filters
- **bollinger_rsi.py:** Bollinger Bands with RSI confluence

### 4. Runners & Reporting
```bash
python runners/run_basket.py \
  --basket mega \
  --strategy ema_crossover \
  --timeframe 1d
```

Generates comprehensive reports in `reports/` with:
- HTML dashboard with interactive charts
- CSV trade logs and metrics
- Equity curves and drawdown analysis

---

## 🌐 Webhook Service

Production TradingView webhook service deployed on Google Cloud Run.

**Features:**
- TradingView alert integration
- Dhan order execution
- OAuth token auto-refresh (8 AM/PM IST)
- Signal queuing for after-hours/holidays
- Firestore logging

**Endpoints:**
- `POST /webhook` - Receive TradingView alerts
- `GET /health` - Service health check
- `POST /oauth/callback` - Dhan OAuth callback
- `POST /refresh-token` - Manual token refresh

See `docs/WEBHOOK_SERVICE_COMPLETE_GUIDE.md` for full documentation.

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `docs/QUANTLAB_GUIDE.md` | Complete backtesting guide |
| `docs/BACKTEST_GUIDE.md` | Detailed backtest documentation |
| `docs/STRATEGIES.md` | Strategy development guide |
| `docs/WEBHOOK_SERVICE_COMPLETE_GUIDE.md` | Webhook service setup |
| `webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md` | Dhan API credentials |
| `webhook-service/docs/COMPLETE_DEPLOYMENT_GUIDE.md` | Cloud Run deployment |

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=html

# Webhook service tests
cd webhook-service && python -m pytest tests/ -v
```

**Current Status:** 88 tests passing, 14 skipped (require live data)

---

## 🔧 Development

### Code Quality
```bash
# Format code
black . && isort .

# Lint
ruff check .

# Run pre-commit hooks
pre-commit run --all-files
```

### Project Dependencies
```bash
pip install -e ".[dev]"  # All development dependencies
```

---

## 📈 Performance

- **Backtest Speed:** ~8 stocks/second
- **Data Fetch:** 99.5% success rate
- **Supported Timeframes:** 1m, 5m, 15m, 25m, 60m, 75m, 125m, 1d

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests and quality checks
4. Submit a pull request

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Dhan](https://dhan.co/) for market data API
- [TradingView](https://tradingview.com/) for charting and alerts
- [pandas-ta](https://github.com/twopirllc/pandas-ta) for technical indicators

