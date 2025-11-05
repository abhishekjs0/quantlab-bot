# QuantLab Comprehensive Guide

**Complete end-to-end reference for setup, backtesting, testing, development, and architecture. This single document consolidates all procedural documentation.**

**Last Updated**: November 5, 2025

---

## Table of Contents

1. [Quick Start (5 Minutes)](#quick-start)
2. [Installation & Setup](#installation--setup)
3. [Running Backtests](#running-backtests)
4. [Testing & Validation](#testing--validation)
5. [Development Workflow](#development-workflow)
6. [System Architecture](#system-architecture)
7. [Data Management](#data-management)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 5-Minute Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/abhishekjs0/quantlab-bot.git quantlab
cd quantlab

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Validate system
python3 config.py           # Should output: ✅ System ready for use!

# 5. Run first backtest
PYTHONPATH=. python3 -m runners.run_basket \
  --strategy ema_crossover \
  --basket_file data/basket_test.txt \
  --use_cache_only

# 6. Run tests with coverage
pytest tests/ --cov=. --cov-report=html
open reports/coverage/index.html
```

**Total time: ~10-15 minutes** (first run includes data setup)

---

## Installation & Setup

### Prerequisites
- Python 3.9+ (3.9, 3.10, or 3.11 recommended)
- Git
- pip and venv
- 2-4 GB disk space for data cache

### Step 1: Clone Repository

```bash
git clone https://github.com/abhishekjs0/quantlab-bot.git quantlab
cd quantlab
```

### Step 2: Create Virtual Environment

```bash
# Create venv
python3 -m venv .venv

# Activate venv
source .venv/bin/activate

# On Windows
.venv\Scripts\activate
```

**Verification:**
- Prompt should show `(.venv)` prefix
- `which python` should show path inside `.venv`

### Step 3: Install Dependencies

```bash
# Standard installation
pip install -r requirements.txt

# OR Development installation (includes testing tools)
pip install -e ".[dev]"
```

**What's Installed:**
- Core: pandas, numpy, scipy
- Backtesting: backtesting library
- Development: pytest, black, isort, ruff
- Documentation: sphinx, sphinx-rtd-theme

### Step 4: Configure Dhan API (Optional)

To fetch live data, create `.env` file:

```env
# .env file in project root
DHAN_ACCESS_TOKEN=eyJ...your_jwt_token_here
DHAN_CLIENT_ID=your_client_id
```

### Step 5: Validate System

```bash
python3 config.py
```

**Expected Output:**
```
✅ System ready for use!
- Virtual environment: Active
- Python version: 3.11.x
- Required packages: Installed
- Data cache: Ready
```

**If you get errors:**
- Check Python version: `python3 --version` (need 3.9+)
- Check venv active: `which python` (should be in .venv)
- Reinstall packages: `pip install -e ".[dev]"`

---

## Running Backtests

### Basic Backtest (Default Basket)

```bash
# Run EMA crossover on default basket
python3 -m runners.run_basket --strategy ema_crossover

# Run Ichimoku on default basket
python3 -m runners.run_basket --strategy ichimoku

# Run Knoxville on default basket
python3 -m runners.run_basket --strategy knoxville
```

**Output:**
- `reports/YYYY-MMDD-HHMM-*-basket-size/` - Results directory
- `trades.csv` - All trades with entry/exit details
- `metrics.csv` - Summary metrics (Sharpe, Drawdown, etc.)
- `equity_curve.csv` - Daily equity progression

### Basket Sizes

Available baskets (by market cap):

| Basket | File | Symbols | Volume Criteria |
|--------|------|---------|-----------------|
| **test** | basket_test.txt | 1 | For quick testing |
| **small** | basket_small.txt | 99 | 100K+ daily volume |
| **mid** | basket_mid.txt | 51 | 500K+ daily volume |
| **large** | basket_large.txt | 103 | 2.5M+ daily volume |
| **mega** | basket_mega.txt | 72 | 5M+ daily volume |

### Running with Specific Basket

```bash
# Mega basket (72 largest stocks) - comprehensive test
python3 -m runners.run_basket --strategy ema_crossover --basket_size mega

# Large basket (103 symbols)
python3 -m runners.run_basket --strategy ichimoku --basket_size large

# Small basket (99 symbols) - faster, good for development
python3 -m runners.run_basket --strategy knoxville --basket_size small

# Custom basket file
python3 -m runners.run_basket --strategy ema_crossover --basket_file path/to/symbols.txt
```

### Using Cached Data

For faster testing without API calls:

```bash
# Use only cached data (skip Dhan API)
python3 -m runners.run_basket --strategy ema_crossover --use_cache_only

# Force refresh cache from Dhan API
python3 -m runners.run_basket --strategy ichimoku --force_refresh
```

### Fetching Data

```bash
# Fetch all symbols in default basket
python3 scripts/fetch_data.py

# Fetch specific symbols
python3 scripts/fetch_data.py RELIANCE INFY HDFCBANK

# Force refresh (ignore cache)
python3 scripts/fetch_data.py --force-refresh

# Clean cache (remove old files)
python3 scripts/fetch_data.py --clean-cache
```

---

## Testing & Validation

### Test Suite Status

```
✅ 42 Tests Passing
✅ 0 Failures
✅ 28% Code Coverage
✅ No Regressions
```

### Running All Tests

```bash
# Run all tests with coverage
pytest tests/ --cov=. --cov-report=html

# View coverage in browser
open reports/coverage/index.html
```

### Running Specific Tests

```bash
# Quick smoke tests (5 seconds)
pytest tests/test_smoke.py -v

# Integration tests (30 seconds)
pytest tests/test_backtesting_integration.py -v

# Basket metrics tests (20 seconds)
pytest tests/test_basket_metrics.py -v

# Performance tests (1-2 minutes)
pytest tests/test_perf.py -v
```

### Coverage by Module

```
core/engine.py:             59% (backtest logic)
core/strategy.py:           64% (strategy base)
strategies/ema_crossover.py: 92% (production strategy)
utils/indicators.py:        55% (indicators)
```

### Pre-commit Validation

Run before committing changes:

```bash
# 1. Format code
black .
isort .

# 2. Lint code
ruff check .

# 3. Run tests with coverage
pytest tests/ --cov=. --cov-fail-under=35

# 4. Build documentation (optional)
cd docs/api && make html
```

### Test Categories

| Category | File | Purpose | Runtime |
|----------|------|---------|---------|
| **Smoke** | test_smoke.py | Quick validation | ~5s |
| **Integration** | test_backtesting_integration.py | Full backtest workflow | ~30s |
| **Metrics** | test_basket_metrics.py | Portfolio math | ~20s |
| **Performance** | test_perf.py | Performance benchmarks | ~1-2m |
| **Strategy** | test_strategy_wrapper.py | Strategy API | ~10s |
| **Parity** | test_parity_basket.py | Results consistency | ~15s |

---

## Development Workflow

### Setting Up Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Verify installation
python3 config.py
```

### Making Code Changes

1. **Create feature branch:**
```bash
git checkout -b feature/your-feature-name
```

2. **Make changes** to files

3. **Format and lint:**
```bash
# Format code
black .
isort .

# Check linting
ruff check .
```

4. **Run tests:**
```bash
pytest tests/ --cov=. --cov-fail-under=35
```

5. **Commit changes:**
```bash
git add .
git commit -m "feat: description of changes"
```

6. **Push to GitHub:**
```bash
git push origin feature/your-feature-name
```

### Code Quality Standards

**Formatting** (Black):
- 88-character line length
- 4-space indentation
- Run: `black .`

**Import Organization** (isort):
- Alphabetical ordering
- Black-compatible configuration
- Run: `isort .`

**Linting** (Ruff):
- Fast Python linter
- Pragmatic rules for legacy code
- Run: `ruff check .`

### Testing New Features

```python
# tests/test_my_feature.py
import pytest
from core.engine import BacktestEngine
from strategies.my_strategy import MyStrategy

def test_my_feature():
    """Test description."""
    strategy = MyStrategy()
    assert strategy is not None
    # Add more tests...
```

**Run specific test:**
```bash
pytest tests/test_my_feature.py -v
```

### Adding New Indicators

1. Add method to `utils/indicators.py`
2. Register in strategy's `__init__`
3. Access via `self.indicator['indicator_name']`
4. Always check for NaN in on_bar()

### Adding New Strategy

See STRATEGIES.md document for detailed instructions.

---

## System Architecture

### Core Components

#### BacktestEngine (core/engine.py)
- Orchestrates backtesting process
- Manages trade execution
- Calculates daily metrics
- Generates reports

**Key Classes:**
- `BacktestEngine` - Main backtesting orchestrator
- `Trade` - Individual trade record
- `PortfolioMetrics` - Daily performance metrics

#### Strategy Framework (core/strategy.py)
- Base class for all strategies
- Indicator management
- Signal generation
- State tracking

**Key Classes:**
- `Strategy` - Base strategy class
- `StrategyI` - Strategy wrapper with I() method

#### Registry (core/registry.py)
- Central strategy registration
- Indicator management
- Factory pattern for strategy creation

**Example:**
```python
from core.registry import STRATEGIES, INDICATORS

strategy = STRATEGIES['ema_crossover']()
indicator = INDICATORS['sma'](period=20)
```

### Data Flow

```
Raw OHLC Data
    ↓
Load into DataFrame (data/cache/)
    ↓
Instantiate Strategy (strategies/)
    ↓
Calculate Indicators (utils/indicators.py)
    ↓
Process Each Bar (on_bar method)
    ↓
Generate Signals (entry/exit)
    ↓
Execute Trades (core/engine.py)
    ↓
Calculate Metrics (core/perf.py)
    ↓
Generate Reports (core/report.py)
    ↓
Output Files (reports/)
```

### Execution Model

**on_bar() Method:**
```python
def on_bar(self, ts, row, state):
    """
    Called once per bar of data.
    
    Args:
        ts: Timestamp (datetime)
        row: Current bar data (OHLCV)
        state: Portfolio state (position, cash)
    
    Returns:
        Dict with entry/exit signals
    """
    # Calculate indicators
    # Check NaN for startup
    # Generate signals
    # Return entry/exit decisions
```

### Key Design Principles

1. **Clean Separation**: Engine, strategies, utilities independent
2. **Indicator NaN Handling**: Automatically skip trading during warmup
3. **No Look-Ahead**: Data filled at next bar open
4. **Gap & Slippage**: Simulated for realistic execution
5. **Professional Metrics**: Industry-standard calculations

---

## Data Management

### Directory Structure

```
data/
├── cache/                       # Historical data cache
│   ├── dhan_historical_*.csv   # Downloaded data files
│   └── *.csv_metadata.json     # Cache metadata
├── basket_test.txt             # 1 symbol for testing
├── basket_small.txt            # 99 small-cap symbols
├── basket_mid.txt              # 51 mid-cap symbols
├── basket_large.txt            # 103 large-cap symbols
├── basket_mega.txt             # 72 mega-cap symbols
└── *.csv                       # Master data files
```

### Cache Management

**Cache Features:**
- 30-day auto-expiration
- Automatic cleanup of old files
- Metadata tracking (download date, version)
- Fallback to cached data if API unavailable

**Manual cache operations:**
```bash
# Check cache status
python3 scripts/check_basket_data.py

# Clean cache
python3 scripts/fetch_data.py --clean-cache

# Force refresh
python3 scripts/fetch_data.py --force-refresh
```

### Data Quality

- **Source**: Dhan API or cached yfinance data
- **Adjustments**: Corporate actions (splits, dividends)
- **Frequency**: Daily OHLCV data
- **History**: Typically 1-5 years per symbol
- **Validation**: check_basket_data.py verifies completeness

---

## Troubleshooting

### Common Issues

#### "Cache miss" Error
```
Error: Cache miss for SYMBOL
```
**Solution:**
```bash
python3 scripts/fetch_data.py SYMBOL
python3 -m runners.run_basket --strategy ema_crossover
```

#### "Module not found" Error
```
ModuleNotFoundError: No module named 'core'
```
**Solution:**
```bash
# Ensure venv is activated
source .venv/bin/activate

# Set PYTHONPATH
export PYTHONPATH="."

# Or install in development mode
pip install -e "."
```

#### "API Token Invalid" Error
```
AuthenticationError: Invalid API token
```
**Solution:**
```bash
# Check .env file exists
cat .env

# Verify token format
# Use --use_cache_only flag
python3 -m runners.run_basket --strategy ema_crossover --use_cache_only
```

#### "Test failures" Error
```
FAILED tests/test_*.py - AssertionError
```
**Solution:**
```bash
# Run single test with verbose output
pytest tests/test_*.py::test_name -vv --tb=long

# Check coverage
pytest tests/ --cov=. --cov-report=html

# Rebuild cache
python3 scripts/fetch_data.py --clean-cache
python3 scripts/fetch_data.py
```

#### "Slow backtest" Issue
```
Backtest running slowly on large baskets
```
**Solution:**
- Use smaller basket: `--basket_size small`
- Use cached data: `--use_cache_only`
- Profile code: `python -m cProfile -s cumtime runner.py`
- Run in parallel: Process multiple baskets

### Debug Commands

```bash
# Check system configuration
python3 config.py -v

# List available strategies
python3 -c "from core.registry import STRATEGIES; print(STRATEGIES.keys())"

# List available indicators
python3 -c "from core.registry import INDICATORS; print(INDICATORS.keys())"

# Check data cache
find data/cache -name "*.csv" | wc -l

# Verify test setup
pytest --collect-only tests/

# Run with detailed output
pytest tests/ -vv --tb=long --capture=no
```

---

## Performance Benchmarks

### Backtesting Speed
- **Small basket** (1 symbol): < 1 second
- **Small basket** (99 symbols): 5-10 seconds
- **Large basket** (103 symbols): 10-20 seconds
- **Mega basket** (72 symbols): 8-15 seconds

### Memory Usage
- **1Y data, small basket**: ~50MB
- **1Y data, mega basket**: ~500MB
- **Coverage reports**: ~200MB (HTML files)

### Test Suite
- **Full suite** (42 tests): ~3 seconds
- **Smoke tests** (5 tests): ~1 second
- **Integration tests** (10 tests): ~1.5 seconds

---

## Next Steps

1. **Read OVERVIEW.md** - Understand system features
2. **Read STRATEGIES.md** - Learn about strategies
3. **Run first backtest** - See system in action
4. **Run test suite** - Verify everything works
5. **Make modifications** - Add custom strategy
6. **Check coverage** - Understand test status
7. **Deploy changes** - Push to GitHub

---

## Additional Resources

- **Sphinx API Docs**: `cd docs/api && make html`
- **Strategy Implementation**: See `strategies/template.py`
- **Testing**: See `tests/test_*.py` files
- **Configuration**: See `config.py`
- **Data Loading**: See `data/loaders.py`

---

**Questions?** Check OVERVIEW.md or STRATEGIES.md for more information.
