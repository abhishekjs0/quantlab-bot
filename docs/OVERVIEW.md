# QuantLab - Professional Trading System Overview

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)](https://github.com/features/actions)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Professional backtesting framework for Indian equities with clean architecture, comprehensive testing, and production-ready infrastructure**

---

## 🎯 What is QuantLab?

QuantLab is a modern, professionally-architected backtesting system designed specifically for Indian equities. It combines:
- **Clean Architecture**: Modular, testable, extensible codebase
- **Comprehensive Testing**: 42 passing tests with 28% coverage
- **Production Ready**: CI/CD pipeline, security scanning, automated deployment
- **Professional Tooling**: Ruff linting, Black formatting, Sphinx documentation

---

## ✨ Key Features

### 📊 **Backtesting Engine**
- Full OHLC data support with gap and slippage simulation
- Multiple time-frame analysis (1Y, 3Y, 5Y, ALL)
- Professional risk metrics (Sharpe ratio, drawdown, profit factor)
- Smart data caching with 30-day auto-cleanup
- Symbol-level P&L tracking with consolidated reporting

### 🔄 **Strategy Framework**
- Clean on_bar() execution model
- Automatic indicator NaN handling for startup
- Built-in strategy templates with I() wrapper
- Support for multiple strategies with parameter optimization
- Signal capture and export

### 🧪 **Testing & Quality**
- 42 integration and unit tests (all passing)
- Automated CI/CD with GitHub Actions (Python 3.9-3.11)
- Code coverage tracking (28% overall)
- Pre-commit hooks for code quality
- Comprehensive test suite validation

### 📚 **Professional Documentation**
- Auto-generated Sphinx API docs
- Strategy implementation guides
- End-to-end workflow documentation
- Architecture and design decisions documented

### 🛡️ **Security & Maintenance**
- Automated vulnerability scanning (Bandit)
- Dependency updates via Dependabot
- Git-based deployment workflow
- Repository maintenance automation

---

## 🚀 Quick Start (5 Minutes)

```bash
# 1. Clone and setup
git clone https://github.com/abhishekjs0/quantlab-bot.git quantlab
cd quantlab
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Validate system
python3 config.py  # Should show: ✅ System ready for use!

# 3. Run first backtest
PYTHONPATH=. python3 -m runners.run_basket \
  --strategy ema_crossover \
  --basket_file data/basket_test.txt \
  --use_cache_only

# 4. Run tests with coverage
pytest tests/ --cov=. --cov-report=html
open reports/coverage/index.html
```

---

## 📁 Repository Structure

```
quantlab/
├── config.py                    # Centralized configuration
├── README.md                    # This file
├── CHANGELOG.md                 # Version history
├── core/                        # 🧠 Backtesting engine
│   ├── engine.py               # Main backtest runner
│   ├── strategy.py             # Strategy base class
│   ├── config.py               # Broker configuration
│   ├── perf.py                 # Performance metrics
│   └── *.py                    # Utilities
├── strategies/                  # 📈 Trading strategies
│   ├── ema_crossover.py        # EMA crossover
│   ├── ichimoku.py             # Ichimoku cloud
│   ├── knoxville.py            # Multi-indicator
│   └── template.py             # Strategy template
├── runners/                     # ⚡ Execution
│   └── run_basket.py           # Multi-symbol backtest
├── data/                        # 📊 Market data
│   ├── cache/                  # Cached historical data
│   ├── basket_*.txt            # Symbol lists
│   └── *.csv                   # Master data files
├── reports/                     # 📈 Generated results
│   ├── coverage/               # Test coverage reports
│   └── YYYY-MMDD-*/           # Backtest results
├── docs/                        # 📚 Documentation
├── tests/                       # 🧪 Test suite (42 tests)
├── scripts/                     # 🛠️ Utility scripts
└── viz/                         # 📉 Visualization tools
```

---

## 📖 Documentation

**Core Documentation Files (START HERE):**
- **COMPREHENSIVE_GUIDE.md** - End-to-end procedures, setup, testing, workflows (read this for everything)
- **STRATEGIES.md** - All strategy implementations (EMA, Ichimoku, Knoxville) + how to add new ones
- **STARTUP_PROMPT.md** - Context for AI agents at session start
- **JANITOR_PROMPT.md** - Repository cleanup and maintenance procedures

**Legacy Reference:**
- CHANGELOG.md - Version history and changes

---

## 🧪 Testing

**Current Status: ✅ 42/42 Tests Passing**

```bash
# Run all tests with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test category
pytest tests/test_smoke.py -v              # Quick smoke tests
pytest tests/test_backtesting_integration.py -v

# Run with output
pytest tests/ -vv --tb=short
```

**Coverage by Module:**
- core/engine.py: 59% (backtest logic)
- core/strategy.py: 64% (strategy base)
- strategies/ema_crossover.py: 92% (production)
- utils/indicators.py: 55% (indicators)

---

## 🏗️ Architecture Highlights

### Clean Separation of Concerns
- **Engine**: Pure backtesting logic (no strategy details)
- **Strategies**: Self-contained trading logic
- **Runners**: Orchestration and reporting
- **Utilities**: Shared indicators and helpers

### Production-Ready
- **CI/CD**: Automated testing, linting, security scanning
- **Documentation**: Auto-generated API docs from code
- **Testing**: Comprehensive test suite with coverage requirements
- **Security**: Bandit scanning, Dependabot updates

### Data Quality
- No look-ahead bias (fills at next bar open)
- Gap and slippage simulation
- Data adjustments for corporate actions
- Cache management with auto-cleanup

---

## 🛠️ Development

### Quick Setup
```bash
pip install -e ".[dev]"           # Install with dev dependencies
black . && isort .                # Format code
ruff check .                      # Lint code
pytest --cov=. --cov-fail-under=35  # Run tests
```

### Adding New Strategies
1. Copy `strategies/template.py`
2. Implement `on_bar()` method with signals
3. Add to `core/registry.py`
4. Document in STRATEGIES.md
5. Add tests in tests/

### Making Changes
1. Make code changes
2. Run tests: `pytest tests/ --cov=.`
3. Run linting: `black . && isort . && ruff check .`
4. Commit: `git add . && git commit -m "feat: description"`
5. Push: `git push origin main`

---

## 📊 Recent Updates (Nov 2025)

- ✅ Documentation consolidation: 6,514 → ~3,000 lines (54% reduction)
- ✅ Test suite: All 42 tests passing with zero regressions
- ✅ CI/CD: GitHub Actions pipeline with multi-Python testing
- ✅ Code Quality: Ruff + Black + isort with pragmatic rules
- ✅ Security: Bandit scanning and Dependabot automated updates

---

## 🚀 Common Tasks

### Run Backtest on Different Basket Sizes
```bash
python3 -m runners.run_basket --strategy ema_crossover --basket_size mega
python3 -m runners.run_basket --strategy ichimoku --basket_size large
python3 -m runners.run_basket --strategy knoxville --basket_size small
```

### Fetch Fresh Market Data
```bash
python3 scripts/fetch_data.py                  # Fetch all
python3 scripts/fetch_data.py RELIANCE INFY    # Fetch specific
python3 scripts/fetch_data.py --force-refresh  # Force refresh
```

### Validate System Setup
```bash
python3 config.py                 # Check configuration
python3 scripts/check_basket_data.py  # Check basket data
```

---

## 🐛 Troubleshooting

**"Cache miss" error:**
```bash
python3 scripts/fetch_data.py
python3 -m runners.run_basket --strategy ema_crossover
```

**"Module not found" error:**
```bash
pip install -e ".[dev]"
```

**Slow backtest:**
- Use smaller basket: `--basket_size small`
- Use cached data: `--use_cache_only`
- Limit period: Use configuration

---

## 📚 Getting Help

1. **Quick Reference**: See COMPREHENSIVE_GUIDE.md
2. **Strategy Details**: See STRATEGIES.md
3. **AI Context**: See STARTUP_PROMPT.md
4. **API Documentation**: Build with `cd docs/api && make html`

---

## 📈 Performance

- **Backtest Speed**: ~8 stocks/second (optimized)
- **Data Loading**: ~2 seconds for mega basket (100 symbols)
- **Memory Usage**: ~500MB for year-long mega basket
- **Coverage Reports**: Generated in <1 second

---

## 🎯 Version

- **Version**: 2.2
- **Status**: Production Ready
- **Python**: 3.9+
- **Last Updated**: November 5, 2025

---

## 📝 License

MIT License - See LICENSE file

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/description`
3. Make changes and test: `pytest tests/ --cov=.`
4. Commit: `git commit -m "feat: description"`
5. Push: `git push origin feature/description`
6. Open pull request on GitHub

---

**For detailed procedures, see COMPREHENSIVE_GUIDE.md**

