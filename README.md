# QuantLab - Professional Algorithmic Trading Framework# QuantLab v2.2 - Professional Trading System



**Status:** ✅ Production Ready  [![Python 3.9+](https://img.shields.i### **Development Workflow (NEW)**

**Latest Release:** Event-driven backtesting with next-open execution  - 🛠️ **Modern Setup**: Virtual environment with development dependencies

**Data Fetch Success Rate:** 99.5%- 📋 **Quality Checks**: Automated linting, formatting, and testing

- 📚 **Documentation**: Sphinx API docs with automatic GitHub Pages deployment

---- 🔄 **CI/CD**: Comprehensive GitHub Actions pipeline with matrix testing

- 🧪 **Testing**: Unit, integration, and performance test coverage

## Quick Start- 🛡️ **Security**: Automated vulnerability scanning and dependency updates



### Setup### **Traditional Risk Analytics**

```bash- **Individual Trade Drawdown**: Real intra-trade risk using OHLC data

git clone <repo> quantlab && cd quantlab- **Symbol-Level Max Drawdown**: Uses highest individual trade drawdown

python -m venv .venv && source .venv/bin/activate- **Run-up Analysis**: Maximum favorable movement tracking

pip install -e ".[dev]"- **Stop Loss Framework**: Optional stop loss with performance comparison

python config.py  # Verify system ready

```### **Comprehensive Reporting**

- **Portfolio Key Metrics**: Net P&L, CAGR, Max Drawdown, Profit Factor

### Run a Backtest- **Consolidated Trades**: Detailed trade logs with entry/exit analysis

```bash- **Equity Curves**: Daily and monthly portfolio progression

# EMA Crossover on Mega Basket- **Multi-Timeframe Analysis**: 1Y, 3Y, 5Y, and ALL period comparisonsge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

python runners/run_basket.py --basket mega --strategy ema_crossover --timeframe 1d[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)](https://github.com/features/actions)

```[![Documentation](https://img.shields.io/badge/docs-Sphinx-blue.svg)](https://sphinx-doc.org/)

[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

### Fetch Historical Data[![Linting](https://img.shields.io/badge/linting-ruff-red.svg)](https://github.com/astral-sh/ruff)

```bash[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

# Download 2 years of data

python scripts/dhan_fetch_data.py --basket large --timeframe 1d**Professional backtesting framework for Indian equities with clean architecture and comprehensive risk analysis**



# Multi-timeframe (25m → 75m, 125m automatic)## 🎯 **Recent Major Updates (Oct 2024)**

python scripts/dhan_fetch_data.py --basket mega --timeframe 25m

```### **Repository Optimization & Professional Tooling - COMPLETE v2.2**

- ✅ **CI/CD Pipeline**: Comprehensive GitHub Actions workflow with multi-Python testing (3.9, 3.10, 3.11)

---- ✅ **Code Quality**: Enhanced Ruff linting with pragmatic rules, Black formatting, isort import organization

- ✅ **Test Coverage**: Expanded test suite with 40+ tests, 35%+ coverage requirement, Strategy.I() wrapper validation

## Architecture- ✅ **API Documentation**: Professional Sphinx documentation with autodoc, type hints, and RTD theme

- ✅ **Security**: Bandit security scanning, Dependabot automated updates, comprehensive vulnerability checks

```- ✅ **Performance**: 353.27% validated returns with streamlined backtesting (~8 stocks/second)

quantlab/

├── core/               # Event-driven backtesting engine### **Architecture Modernization**

├── strategies/         # Trading strategies- 🏗️ **Strategy.I() System**: Modern wrapper architecture for indicator integration and consistency

├── runners/            # Portfolio backtesting & reporting- 📊 **Comprehensive Testing**: 10 new tests covering strategy wrappers, market regime detection, template validation

├── scripts/            # Unified data fetcher (dhan_fetch_data.py)- 🔧 **Development Workflow**: Complete development guide with pre-commit hooks, automated quality checks

├── data/              # Market data & baskets- � **Professional Documentation**: API docs with cross-references, code examples, and automatic deployment

├── utils/             # Indicators & calculations- �️ **Production Ready**: Security scanning, dependency management, automated release workflow

├── tests/             # Test suite

└── docs/              # Documentation## 🚀 Quick Start

```

### Installation & Quick Start

---```bash

# Clone and setup

## Core Componentsgit clone <repository-url> quantlab

cd quantlab

### 1. **Backtesting Engine** (`core/engine.py`)python -m venv .venv

- **Event-Driven:** Processes bars sequentiallysource .venv/bin/activate  # Windows: .venv\Scripts\activate

- **Next-Open Execution:** Signals on current bar close → fills at next bar openpip install -e ".[dev]"

- **No Lookahead Bias:** Real-world execution model

- **Supports:** Daily, 75m, 125m, 1m, 5m, 15m, 25m, 60m timeframes# Validate setup

- **Features:** Pyramiding, per-lot stops, slippage modelingpython config.py  # Should show "✅ System ready for use!"



**Key Config** (`core/config.py`):# Run quality checks

```pythonblack . && isort . && ruff check .

BrokerConfig(pytest --cov=. --cov-fail-under=35

    initial_capital=100_000,          # Starting capital

    qty_pct_of_equity=0.05,          # 5% per trade# Build documentation

    commission_pct=0.11,             # 0.22% round-tripcd docs/api && make html

    slippage_ticks=3,                # Realistic slippage```

    execute_on_next_open=True,       # ← CRITICAL: Next bar execution

)### Run Your First Backtest

``````bash

# Ichimoku strategy on mega basket

### 2. **Data Fetcher** (`scripts/dhan_fetch_data.py`)PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku --use_cache_only

- **Universal:** Any basket, symbol, or timeframe```

- **Production-Ready:** Token validation, error recovery, smart caching

- **Multi-Timeframe:** Aggregates 25m → 75m, 125m automatically## �️ Architecture Overview

- **Smart Chunking:** 90-day API limitations handled

```

**Usage:**quantlab/

```bash├── 📊 core/              # Backtesting engine with enhanced metrics

# Full basket├── 📈 strategies/        # Trading strategies (ichimoku, donchian, ema_cross, etc.)

python scripts/dhan_fetch_data.py --basket large --timeframe 1d├── 🏃 runners/           # Strategy execution with comprehensive reporting

├── 🛠️ scripts/          # Data fetching and utilities

# Multi-timeframe aggregation├── 📁 data/             # Market data and baskets

python scripts/dhan_fetch_data.py --basket mega --timeframe 25m --days-back 730├── 📚 docs/             # Complete documentation

├── 🧪 tests/            # Quality assurance

# Specific symbols└── 📊 viz/              # Visualization tools

python scripts/dhan_fetch_data.py --symbols RELIANCE,TCS --timeframe 1d```

```

## ✨ Key Features (v2.2)

### 3. **Strategies**

Located in `strategies/`:### 🚀 **Professional Development Environment**

- **ema_crossover.py:** Fast/slow EMA crossover- **Modern Tooling**: Ruff linting, Black formatting, isort import organization

- **ichimoku.py:** Ichimoku cloud with trend confirmation- **CI/CD Pipeline**: GitHub Actions with multi-Python testing (3.9, 3.10, 3.11)

- **knoxville.py:** Multi-indicator trend follower- **Automated Quality**: Pre-commit hooks, coverage requirements, security scanning

- **template.py:** Development template- **API Documentation**: Sphinx with autodoc, type hints, and GitHub Pages deployment



### 4. **Runners & Reporting**### 🧪 **Comprehensive Testing Framework**

```bash- **Test Coverage**: 40+ tests with 35% minimum coverage requirement

python runners/run_basket.py \- **Strategy Validation**: Strategy.I() wrapper testing and template validation

  --basket mega \- **Integration Tests**: Full backtest workflow validation

  --strategy ichimoku \- **Performance Benchmarks**: Automated performance regression detection

  --timeframe 1d

```### �️ **Security & Maintenance**

- **Security Scanning**: Bandit static analysis for vulnerability detection

Outputs:- **Dependency Management**: Dependabot automated updates with intelligent grouping

- Portfolio metrics (CAGR, Sharpe, Max DD, Win Rate)- **Code Quality**: Enhanced Ruff rules with pragmatic legacy compatibility

- Trade logs and equity curves- **Documentation**: Professional API docs with cross-references and examples

- Symbol breakdown

- Multi-window analysis (1Y, 3Y, 5Y, ALL)## 📈 Available Strategies



---| Strategy | Description | Status | Notes |

|----------|-------------|--------|-------|

## Backtesting Methodology| `ichimoku` | Production Ichimoku with global market regime filters | ✅ **PRODUCTION** | Recommended for live trading |

| `envelope_kd` | Envelope + Knoxville Divergence trend-following system | ✅ **PRODUCTION** | Mean reversion + divergence confirmation |

### Why Event-Driven with Next-Open Execution?| `template` | Modern development template with best practices | 📚 **TEMPLATE** | Use for new strategy development |



Real trading doesn't execute same-bar. Here's what happens:**Note**: Both `ichimoku` and `envelope_kd` are production-ready strategies optimized for Indian equity markets.



```## �️ Basket Configurations

BAR N Close (3:30 PM)

  ├─ Strategy sees full OHLC| Basket | Stocks | Criteria | Usage |

  ├─ Generates signal|--------|--------|----------|-------|

  └─ Order placed → queued| **Mega** | 72 | Large-cap, 5M+ daily volume | `data/basket_mega.txt` |

| **Large** | 103 | Large-cap, 2.5M+ daily volume | `data/basket_large.txt` |

BAR N+1 Open (9:15 AM)| **Mid** | 51 | Mid-cap, 500K+ daily volume | `data/basket_mid.txt` |

  └─ Order fills ← EXECUTION HERE| **Small** | 99 | Small-cap, 100K+ daily volume | `data/basket_small.txt` |

```

## � Performance Example

**Why this matters:**

- ✅ **No Lookahead:** Can't use data that doesn't exist yetRecent ichimoku strategy results (no stop loss):

- ✅ **Real Gaps:** Accounts for overnight gaps```

- ✅ **Matches Reality:** How traders actually executePortfolio Performance (ALL period):

- ✅ **Industry Standard:** Professional platforms use this├── Net P&L: 381.18%

├── CAGR: 31.15%

**Critical Config:**├── Max Drawdown: 11.84%

```python├── Total Trades: 1,014

execute_on_next_open = True  # ALWAYS True for live-tradable results├── Win Rate: 45.49%

```└── Profit Factor: 2.69

```

See `BACKTEST_METHODOLOGY.md` for deep analysis.

## 🛠️ Common Commands

---

```bash

## Data Status# Data Management

python3 scripts/fetch_data.py RELIANCE INFY    # Fetch specific symbols

### Current Cachepython3 scripts/fetch_data.py --clean-cache    # Clean old cache files

- **Mega Basket:** 73 stocks, all timeframes ✅ COMPLETE

- **Large Basket:** 103 stocks, daily complete, intraday in progress# Strategy Backtesting

- **Coverage:** 2+ years daily, 8.5+ years intraday (from Apr 2017)PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku --use_cache_only

PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_large.txt --strategy donchian --use_cache_only

### Check Cache Status

```bash# Custom Parameters

python << 'EOF'PYTHONPATH=. python -m runners.run_basket --strategy ema_cross --params '{"fast": 10, "slow": 30}' --use_cache_only

import os

from pathlib import Path# Data Validation

python3 scripts/check_basket_data.py           # Validate basket data

CACHE_DIR = Path("data/cache")python3 scripts/rank_strategies.py             # Analyze strategy performance

for tf in ["1d", "75m", "125m"]:```

    count = len(list(CACHE_DIR.glob(f"dhan_*_*_{tf}.csv")))

    print(f"{tf}: {count} symbols")## 📁 Generated Reports

EOF

```Each backtest creates timestamped reports in `reports/YYYYMMDD-HHMMSS/`:



---```

reports/20251022-133109/

## Available Strategies├── portfolio_key_metrics_ALL.csv              # Performance metrics

├── consolidated_trades_ALL.csv                # Individual trade details

| Strategy | Type | Status | Best For |├── portfolio_daily_equity_curve_ALL.csv       # Daily portfolio values

|----------|------|--------|----------|├── portfolio_monthly_equity_curve_ALL.csv     # Monthly summaries

| `ichimoku` | Trend | ✅ PRODUCTION | Sustained trends |└── strategy_backtests_summary.csv             # Cross-timeframe analysis

| `ema_crossover` | Crossover | ✅ PRODUCTION | Fast markets |```

| `knoxville` | Multi-indicator | ✅ PRODUCTION | Complex conditions |

| `template` | Example | 📚 TEMPLATE | Custom development |## 🔬 System Quality & Professional Standards



---### **Test Suite Status**



## Baskets✅ **All 42 Tests Passing**

- 14 integration and backtesting tests

| Name | Stocks | Criteria |- 3 basket metrics validation tests

|------|--------|----------|- 2 integration parity checks

| mega | 73 | Large-cap, 5M+ daily volume |- 2 parity validation tests

| large | 103 | Large-cap, 2.5M+ daily volume |- 4 performance calculation tests

| mid | 51 | Mid-cap, 500K+ daily volume |- 2 CAGR and profit factor tests

| small | 99 | Small-cap, 100K+ daily volume |- 2 smoke tests

| test | 5 | Quick testing |- 11 strategy wrapper and architecture tests



---**Coverage**: ~28% with focus on core engine (59%), strategy base (64%), and production strategies (80-92%)



## DocumentationRun tests with:

```bash

- **`BACKTEST_METHODOLOGY.md`** — Backtesting theory & correctnesspytest tests/ -v

- **`DHAN_API_USAGE.md`** — API endpoints & configurationpytest tests/ --cov=. --cov-report=html  # Generate coverage report

- **`docs/DHAN_DATA_FETCHING_GUIDE.md`** — Comprehensive fetch guide```

- **`docs/DEVELOPMENT_WORKFLOW.md`** — Dev setup & contribution

- **`CHANGELOG.md`** — Version historyFor detailed test documentation, see `docs/BACKTEST_GUIDE.md` (Part 3: Test Suite & Validation)



---### **Modern Development Practices**

- ✅ **Code Quality**: Ruff linting with 100+ rules, Black formatting (88-char), isort import organization

## Create Your Own Strategy- ✅ **Type Safety**: Comprehensive type hints with mypy validation

- ✅ **Testing**: 40+ tests with 35% coverage requirement, Strategy.I() wrapper validation

Edit `strategies/template.py`:- ✅ **Documentation**: Professional Sphinx API docs with autodoc and GitHub Pages deployment

- ✅ **CI/CD**: GitHub Actions pipeline with multi-Python testing and automated quality checks

```python

class MyStrategy(Strategy):### **Security & Maintenance**

    def prepare(self, df):- ✅ **Security Scanning**: Bandit static analysis for vulnerability detection

        """Prepare indicators (once before loop)"""- ✅ **Dependency Management**: Dependabot automated updates with intelligent grouping

        df['ema_fast'] = df['close'].ewm(span=12).mean()- ✅ **Code Standards**: Google-style docstrings, PEP 8 compliance, comprehensive error handling

        df['ema_slow'] = df['close'].ewm(span=26).mean()- ✅ **Performance**: Vectorized operations, memory management, smart caching strategies

    

    def on_bar(self, ts, row, state):### **Development Experience**

        """Generate signals per bar"""- ✅ **Quick Setup**: One-command development environment installation

        enter = row['ema_fast'] > row['ema_slow']- ✅ **Quality Automation**: Pre-commit hooks and automated formatting

        exit = row['ema_fast'] < row['ema_slow']- ✅ **Professional Docs**: API documentation with cross-references and code examples

        - ✅ **Modern Tooling**: Ruff (fastest Python linter), Black (uncompromising formatter), pytest (modern testing)

        return {

            'enter_long': enter,## 📚 Documentation & Resources

            'exit_long': exit,

            'signal_reason': 'EMA crossover',| Document | Purpose |

        }|----------|---------|

    | **`DEVELOPMENT_WORKFLOW.md`** | Complete development guide with CI/CD, testing, and quality standards |

    def size(self, equity, price, cfg):| **`docs/api/`** | Professional Sphinx API documentation with auto-generation |

        """Position sizing"""| **`JANITOR_FINAL_PROMPT.md`** | End-of-session repository cleanup prompt for AI agents |

        notional = equity * cfg.qty_pct_of_equity| `QUANTLAB_GUIDE.md` | Complete system overview and architecture |

        return int(notional / price)| `BACKTEST_GUIDE.md` | Detailed backtesting execution guide |

```| `CODING_STANDARDS.md` | Development standards and protocols |

| `WORKFLOW_GUIDE.md` | Development workflow and best practices |

Run it:

```bash### **API Documentation**

python runners/run_basket.py --basket mega --strategy my_strategy --timeframe 1d- 🌐 **Online**: Available at GitHub Pages (auto-deployed)

```- 🏠 **Local**: Build with `cd docs/api && make html`

- 🔗 **Features**: Type hints, cross-references, code examples, search functionality

---

## 🧪 Testing & Quality Assurance

## Sample Results

### **Development Commands**

**Ichimoku on Mega Basket (1d)**```bash

# Quality checks (run before commit)

| Period | CAGR | Sharpe | Max DD | Win Rate |black . && isort . && ruff check .

|--------|------|--------|--------|----------|

| 1Y | 42.1% | 1.8 | 1.25% | 58% |# Test execution

| 3Y | 28.5% | 1.2 | 5.47% | 55% |pytest --cov=. --cov-report=html  # With coverage report

| 5Y | 22.3% | 0.9 | 5.57% | 52% |pytest tests/test_strategy_wrapper.py -v  # Specific test module

pytest -x  # Stop on first failure

---

# Documentation

## Requirementscd docs/api && make html  # Build API docs

python -m http.server 8080 -d docs/api/_build/html  # Serve locally

- Python 3.9+

- pandas, numpy, requests# Performance analysis

- Dhan API credentialspython scripts/universal_indicator_analysis.py --profile

```

**Setup:**

```bash### **CI/CD Pipeline**

# .env fileThe GitHub Actions pipeline automatically:

DHAN_ACCESS_TOKEN=your_token- ✅ **Multi-Python Testing**: Tests on Python 3.9, 3.10, and 3.11

DHAN_CLIENT_ID=your_client_id- ✅ **Code Quality**: Runs Black, isort, and Ruff checks

```- ✅ **Test Coverage**: Enforces 35% minimum coverage

- ✅ **Security Scanning**: Bandit vulnerability analysis

---- ✅ **Documentation**: Builds and deploys API docs to GitHub Pages

- ✅ **Performance**: Validates strategy performance benchmarks

## Troubleshooting

## 🔄 Version History

### Data Fetch

```bash| Version | Date | Key Features |

# Test token validity|---------|------|--------------|

python scripts/dhan_fetch_data.py --basket test --timeframe 1d| **2.2** | 2025-10-24 | **Professional Tooling**: Complete CI/CD pipeline, Sphinx API docs, enhanced testing (40+ tests), security scanning, automated quality checks |

| **2.1** | 2025-10-23 | Global market regime system, performance optimization, comprehensive utils library |

# Fetch specific basket| **2.0** | 2025-10-22 | Enhanced risk analytics, individual trade drawdowns, stop loss framework |

python scripts/dhan_fetch_data.py --basket large --timeframe 25m| 1.5 | 2025-10-19 | Clean architecture, centralized config, comprehensive reporting |

```| 1.0 | 2025-10-18 | Initial release with basic backtesting |



### Backtest## 🎯 **Code Linkages & System Architecture**

```bash

# Check cache exists### **Core Components**

ls data/cache/dhan_*.csv | wc -l- `core/global_market_regime.py` → Global market regime system used by production ichimoku strategy

- `core/engine.py` → Enhanced backtesting engine with market regime integration

# Run small test- `utils/` → Complete technical analysis library (SMA, EMA, RSI, ATR, MACD, etc.)

python runners/run_basket.py --basket test --strategy ichimoku- `viz/` → Professional visualization system with Bokeh interactive charts

```

### **Production Strategy Flow**

---```

strategies/ichimoku.py (FINAL)

## Contributing├── Imports: core.strategy.Strategy

├── Uses: utils indicators (RSI, CCI, ADX, ATR, CMF)

1. Create branch: `git checkout -b feature/my-strategy`├── Integrates: core.global_market_regime for consistent filtering

2. Add strategy to `strategies/`└── Outputs: Optimized trades with regime-aware entry/exit

3. Test: `pytest tests/````

4. Format: `black . && isort . && ruff check .`

5. Open PR### **Data Pipeline**

```

---data/loaders.py → Enhanced caching → runners/run_basket.py → Multi-window analysis

├── 30-day intelligent cache

## References├── Metadata tracking

└── Performance optimizations

- **Dhan API:** https://dhanhq.co/docs/v2/```

- **Backtesting Best Practices:** `BACKTEST_METHODOLOGY.md`

- **Strategy Template:** `strategies/template.py`## 🎯 System Architecture Benefits



---### **Professional Grade**

- 📊 **Institutional-Quality Metrics**: Individual trade risk analysis

Made with ❤️ for Indian traders- 🏗️ **Scalable Architecture**: Modular design for growth

- 🔒 **Production Ready**: Robust error handling and validation
- 📈 **Research Focused**: Comprehensive analysis capabilities

### **Developer Experience**
- 🚀 **Easy Setup**: One-command installation and validation
- 📝 **Clear Documentation**: Comprehensive guides and examples
- 🧪 **Quality Assurance**: Automated testing and validation
- 🔧 **Extensible**: Easy strategy and feature development

### **Performance & Reliability**
- ⚡ **Fast Execution**: Optimized data processing and caching
- 🎯 **Accurate Results**: Validated against industry standards
- 🔄 **Consistent Output**: Reproducible backtest results
- 📊 **Comprehensive Analysis**: Multi-timeframe and cross-strategy comparison

---

**Ready to start?** Run `python config.py` to validate your setup and begin professional-grade backtesting with QuantLab v2.2!

### **What's New in v2.2?**
- 🚀 **Complete CI/CD Pipeline**: GitHub Actions with multi-Python testing, automated quality checks, and security scanning
- 📚 **Professional API Documentation**: Sphinx-generated docs with autodoc, type hints, and GitHub Pages deployment
- 🧪 **Enhanced Testing**: 40+ comprehensive tests including Strategy.I() wrapper validation and market regime detection
- 🛡️ **Security & Maintenance**: Bandit security scanning, Dependabot automated updates, modern development workflow
- 🎯 **Developer Experience**: One-command setup, automated formatting, comprehensive development guides

*Experience the difference of professional-grade quantitative trading infrastructure.*
