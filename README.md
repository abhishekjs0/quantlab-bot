# QuantLab v2.2 - Professional Trading System

[![Python 3.9+](https://img.shields.i### **Development Workflow (NEW)**
- 🛠️ **Modern Setup**: Virtual environment with development dependencies
- 📋 **Quality Checks**: Automated linting, formatting, and testing
- 📚 **Documentation**: Sphinx API docs with automatic GitHub Pages deployment
- 🔄 **CI/CD**: Comprehensive GitHub Actions pipeline with matrix testing
- 🧪 **Testing**: Unit, integration, and performance test coverage
- 🛡️ **Security**: Automated vulnerability scanning and dependency updates

### **Traditional Risk Analytics**
- **Individual Trade Drawdown**: Real intra-trade risk using OHLC data
- **Symbol-Level Max Drawdown**: Uses highest individual trade drawdown
- **Run-up Analysis**: Maximum favorable movement tracking
- **Stop Loss Framework**: Optional stop loss with performance comparison

### **Comprehensive Reporting**
- **Portfolio Key Metrics**: Net P&L, CAGR, Max Drawdown, Profit Factor
- **Consolidated Trades**: Detailed trade logs with entry/exit analysis
- **Equity Curves**: Daily and monthly portfolio progression
- **Multi-Timeframe Analysis**: 1Y, 3Y, 5Y, and ALL period comparisonsge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![CI/CD](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-green.svg)](https://github.com/features/actions)
[![Documentation](https://img.shields.io/badge/docs-Sphinx-blue.svg)](https://sphinx-doc.org/)
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting](https://img.shields.io/badge/linting-ruff-red.svg)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Professional backtesting framework for Indian equities with clean architecture and comprehensive risk analysis**

## 🎯 **Recent Major Updates (Oct 2024)**

### **Repository Optimization & Professional Tooling - COMPLETE v2.2**
- ✅ **CI/CD Pipeline**: Comprehensive GitHub Actions workflow with multi-Python testing (3.9, 3.10, 3.11)
- ✅ **Code Quality**: Enhanced Ruff linting with pragmatic rules, Black formatting, isort import organization
- ✅ **Test Coverage**: Expanded test suite with 40+ tests, 35%+ coverage requirement, Strategy.I() wrapper validation
- ✅ **API Documentation**: Professional Sphinx documentation with autodoc, type hints, and RTD theme
- ✅ **Security**: Bandit security scanning, Dependabot automated updates, comprehensive vulnerability checks
- ✅ **Performance**: 353.27% validated returns with streamlined backtesting (~8 stocks/second)

### **Architecture Modernization**
- 🏗️ **Strategy.I() System**: Modern wrapper architecture for indicator integration and consistency
- 📊 **Comprehensive Testing**: 10 new tests covering strategy wrappers, market regime detection, template validation
- 🔧 **Development Workflow**: Complete development guide with pre-commit hooks, automated quality checks
- � **Professional Documentation**: API docs with cross-references, code examples, and automatic deployment
- �️ **Production Ready**: Security scanning, dependency management, automated release workflow

## 🚀 Quick Start

### Installation & Quick Start
```bash
# Clone and setup
git clone <repository-url> quantlab
cd quantlab
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Validate setup
python config.py  # Should show "✅ System ready for use!"

# Run quality checks
black . && isort . && ruff check .
pytest --cov=. --cov-fail-under=35

# Build documentation
cd docs/api && make html
```

### Run Your First Backtest
```bash
# Ichimoku strategy on mega basket
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku --use_cache_only
```

## �️ Architecture Overview

```
quantlab/
├── 📊 core/              # Backtesting engine with enhanced metrics
├── 📈 strategies/        # Trading strategies (ichimoku, donchian, ema_cross, etc.)
├── 🏃 runners/           # Strategy execution with comprehensive reporting
├── 🛠️ scripts/          # Data fetching and utilities
├── 📁 data/             # Market data and baskets
├── 📚 docs/             # Complete documentation
├── 🧪 tests/            # Quality assurance
└── 📊 viz/              # Visualization tools
```

## ✨ Key Features (v2.2)

### 🚀 **Professional Development Environment**
- **Modern Tooling**: Ruff linting, Black formatting, isort import organization
- **CI/CD Pipeline**: GitHub Actions with multi-Python testing (3.9, 3.10, 3.11)
- **Automated Quality**: Pre-commit hooks, coverage requirements, security scanning
- **API Documentation**: Sphinx with autodoc, type hints, and GitHub Pages deployment

### 🧪 **Comprehensive Testing Framework**
- **Test Coverage**: 40+ tests with 35% minimum coverage requirement
- **Strategy Validation**: Strategy.I() wrapper testing and template validation
- **Integration Tests**: Full backtest workflow validation
- **Performance Benchmarks**: Automated performance regression detection

### �️ **Security & Maintenance**
- **Security Scanning**: Bandit static analysis for vulnerability detection
- **Dependency Management**: Dependabot automated updates with intelligent grouping
- **Code Quality**: Enhanced Ruff rules with pragmatic legacy compatibility
- **Documentation**: Professional API docs with cross-references and examples

## 📈 Available Strategies

| Strategy | Description | Status | Key Features |
|----------|-------------|---------|--------------|
| `ichimoku` | **Production-Ready** Ichimoku with Global Market Regime | ✅ **FINAL** | Ultra-fast regime filtering, optimized parameters |
| `ichimoku_original` | Original Ichimoku implementation (backup) | 📚 **BACKUP** | Reference implementation preserved |
| `donchian` | Donchian channel breakout | ⚠️ **LEGACY** | `length: 20` |
| `ema_cross` | EMA crossover signals | ⚠️ **LEGACY** | `fast: 12, slow: 26` |
| `atr_breakout` | ATR-based momentum | ⚠️ **LEGACY** | `atr_period: 14` |
| `envelope_kd` | Envelope with KD oscillator | ⚠️ **LEGACY** | Advanced parameters |

**Note**: The `ichimoku` strategy is now the production-ready version with integrated global market regime system. Original version preserved as `ichimoku_original.py`.

## �️ Basket Configurations

| Basket | Stocks | Criteria | Usage |
|--------|--------|----------|-------|
| **Mega** | 72 | Large-cap, 5M+ daily volume | `data/basket_mega.txt` |
| **Large** | 103 | Large-cap, 2.5M+ daily volume | `data/basket_large.txt` |
| **Mid** | 51 | Mid-cap, 500K+ daily volume | `data/basket_mid.txt` |
| **Small** | 99 | Small-cap, 100K+ daily volume | `data/basket_small.txt` |

## � Performance Example

Recent ichimoku strategy results (no stop loss):
```
Portfolio Performance (ALL period):
├── Net P&L: 381.18%
├── CAGR: 31.15%
├── Max Drawdown: 11.84%
├── Total Trades: 1,014
├── Win Rate: 45.49%
└── Profit Factor: 2.69
```

## 🛠️ Common Commands

```bash
# Data Management
python3 scripts/fetch_data.py RELIANCE INFY    # Fetch specific symbols
python3 scripts/fetch_data.py --clean-cache    # Clean old cache files

# Strategy Backtesting
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku --use_cache_only
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_large.txt --strategy donchian --use_cache_only

# Custom Parameters
PYTHONPATH=. python -m runners.run_basket --strategy ema_cross --params '{"fast": 10, "slow": 30}' --use_cache_only

# Data Validation
python3 scripts/check_basket_data.py           # Validate basket data
python3 scripts/rank_strategies.py             # Analyze strategy performance
```

## 📁 Generated Reports

Each backtest creates timestamped reports in `reports/YYYYMMDD-HHMMSS/`:

```
reports/20251022-133109/
├── portfolio_key_metrics_ALL.csv              # Performance metrics
├── consolidated_trades_ALL.csv                # Individual trade details
├── portfolio_daily_equity_curve_ALL.csv       # Daily portfolio values
├── portfolio_monthly_equity_curve_ALL.csv     # Monthly summaries
└── strategy_backtests_summary.csv             # Cross-timeframe analysis
```

## 🔬 System Quality & Professional Standards

### **Modern Development Practices**
- ✅ **Code Quality**: Ruff linting with 100+ rules, Black formatting (88-char), isort import organization
- ✅ **Type Safety**: Comprehensive type hints with mypy validation
- ✅ **Testing**: 40+ tests with 35% coverage requirement, Strategy.I() wrapper validation
- ✅ **Documentation**: Professional Sphinx API docs with autodoc and GitHub Pages deployment
- ✅ **CI/CD**: GitHub Actions pipeline with multi-Python testing and automated quality checks

### **Security & Maintenance**
- ✅ **Security Scanning**: Bandit static analysis for vulnerability detection
- ✅ **Dependency Management**: Dependabot automated updates with intelligent grouping
- ✅ **Code Standards**: Google-style docstrings, PEP 8 compliance, comprehensive error handling
- ✅ **Performance**: Vectorized operations, memory management, smart caching strategies

### **Development Experience**
- ✅ **Quick Setup**: One-command development environment installation
- ✅ **Quality Automation**: Pre-commit hooks and automated formatting
- ✅ **Professional Docs**: API documentation with cross-references and code examples
- ✅ **Modern Tooling**: Ruff (fastest Python linter), Black (uncompromising formatter), pytest (modern testing)

## 📚 Documentation & Resources

| Document | Purpose |
|----------|---------|
| **`DEVELOPMENT_WORKFLOW.md`** | **NEW**: Complete development guide with CI/CD, testing, and quality standards |
| **`docs/api/`** | **NEW**: Professional Sphinx API documentation with auto-generation |
| `QUANTLAB_GUIDE.md` | Complete system overview and architecture |
| `BACKTEST_GUIDE.md` | Detailed backtesting execution guide |
| `CODING_STANDARDS.md` | Development standards and protocols |
| `WORKFLOW_GUIDE.md` | Development workflow and best practices |

### **API Documentation**
- 🌐 **Online**: Available at GitHub Pages (auto-deployed)
- 🏠 **Local**: Build with `cd docs/api && make html`
- 🔗 **Features**: Type hints, cross-references, code examples, search functionality

## 🧪 Testing & Quality Assurance

### **Development Commands**
```bash
# Quality checks (run before commit)
black . && isort . && ruff check .

# Test execution
pytest --cov=. --cov-report=html  # With coverage report
pytest tests/test_strategy_wrapper.py -v  # Specific test module
pytest -x  # Stop on first failure

# Documentation
cd docs/api && make html  # Build API docs
python -m http.server 8080 -d docs/api/_build/html  # Serve locally

# Performance analysis
python scripts/universal_indicator_analysis.py --profile
```

### **CI/CD Pipeline**
The GitHub Actions pipeline automatically:
- ✅ **Multi-Python Testing**: Tests on Python 3.9, 3.10, and 3.11
- ✅ **Code Quality**: Runs Black, isort, and Ruff checks
- ✅ **Test Coverage**: Enforces 35% minimum coverage
- ✅ **Security Scanning**: Bandit vulnerability analysis
- ✅ **Documentation**: Builds and deploys API docs to GitHub Pages
- ✅ **Performance**: Validates strategy performance benchmarks

## 🔄 Version History

| Version | Date | Key Features |
|---------|------|--------------|
| **2.2** | 2025-10-24 | **Professional Tooling**: Complete CI/CD pipeline, Sphinx API docs, enhanced testing (40+ tests), security scanning, automated quality checks |
| **2.1** | 2025-10-23 | Global market regime system, performance optimization, comprehensive utils library |
| **2.0** | 2025-10-22 | Enhanced risk analytics, individual trade drawdowns, stop loss framework |
| 1.5 | 2025-10-19 | Clean architecture, centralized config, comprehensive reporting |
| 1.0 | 2025-10-18 | Initial release with basic backtesting |

## 🎯 **Code Linkages & System Architecture**

### **Core Components**
- `core/global_market_regime.py` → Global market regime system used by production ichimoku strategy
- `core/engine.py` → Enhanced backtesting engine with market regime integration
- `utils/` → Complete technical analysis library (SMA, EMA, RSI, ATR, MACD, etc.)
- `viz/` → Professional visualization system with Bokeh interactive charts

### **Production Strategy Flow**
```
strategies/ichimoku.py (FINAL)
├── Imports: core.strategy.Strategy
├── Uses: utils indicators (RSI, CCI, ADX, ATR, CMF)
├── Integrates: core.global_market_regime for consistent filtering
└── Outputs: Optimized trades with regime-aware entry/exit
```

### **Data Pipeline**
```
data/loaders.py → Enhanced caching → runners/run_basket.py → Multi-window analysis
├── 30-day intelligent cache
├── Metadata tracking
└── Performance optimizations
```

## 🎯 System Architecture Benefits

### **Professional Grade**
- 📊 **Institutional-Quality Metrics**: Individual trade risk analysis
- 🏗️ **Scalable Architecture**: Modular design for growth
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
