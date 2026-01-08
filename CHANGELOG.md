# Changelog

All notable changes to QuantLab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.2] - 2026-01-08 - **REPOSITORY CLEANUP & TOOLING**

### 🧹 **REPOSITORY CLEANUP**

- **Scripts Consolidation** (`scripts/`)
  - Consolidated 40+ one-off scripts into `scripts/archive/` folder:
    - `hypothesis_tests.py` - 12 test_hypothesis_*.py files
    - `ema20_experiments.py` - 4 EMA20 experiment files  
    - `mean_reversion_experiments.py` - 3 mean reversion files
    - `weekly_green_bb_experiments.py` - 2 weekly green BB files
    - `weekly_rotation_experiments.py` - 3 weekly rotation files
    - `analysis_scripts.py` - 20+ analysis scripts
  - Active scripts: 6 (dhan_fetch_data, fetch_groww_*, export_webhook_logs, check_strategy_imports)

- **Root Directory Cleanup**
  - Deleted: `.bandit`, `.coverage`, `backtest_run.log`, migration artifacts
  - Moved to scripts/: `create_benchmark_data.py`, `recalculate_alpha_beta.py`

- **Cache/Build Cleanup**
  - Deleted: `cache/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/`, `quantlab.egg-info/`
  - Updated `.gitignore` with additional exclusions

- **Documentation Consolidation**
  - Deleted: `docs/ARCHITECTURE.md`, `docs/CRITIQUE.md` (content in README)
  - Updated: `docs/STARTUP_PROMPT.md` v3.2, `docs/JANITOR_PROMPT.md` v3.2

### 🔧 **WEBHOOK SERVICE ENHANCEMENTS**

- **Strategy Attribution** (`webhook-service/app.py`)
  - Added optional `strategy` field to `WebhookPayload` model
  - Strategy name logged to Firestore for trade attribution
  - TradingView alerts can include: `"strategy": "tema_lsma_crossover"`

- **Export Script Rewrite** (`scripts/export_webhook_logs.py`)
  - Uses gcloud auth token instead of ADC (no setup required)
  - Added `strategy` column to CSV output
  - Works with just `gcloud auth login`

### 🔄 **TELEGRAM SUMMARIZER FIXES**

- **Retry Logic** (`telegram-summarizer/summarizer.py`)
  - Added exponential backoff for OpenAI API calls (3 retries)
  - Fixed "AI summarization failed: Connection error" in Cloud Run
  - Strips whitespace from API keys

### 📊 **TRADE LOGGING**

- **P&L Calculation**: Net P&L from webhook logs: -₹834.20 (-6.0%)
  - 3 closed trades: BLUEJET (-3.1%), PCBL (-1.5%), KAYNES (-13.9%)
  - 16 open positions totaling ~₹50K in holdings

---

## [2.4.1] - 2026-01-07 - **API MIGRATIONS & CODE QUALITY**

### 🔧 **API MIGRATIONS**

- **DhanHQ v2.2.0 Migration** (`webhook-service/*.py`)
  - Updated to new `DhanContext` initialization pattern (v2.2.0+ breaking change)
  - Old: `dhanhq(client_id, access_token)`
  - New: `dhanhq(DhanContext(client_id, access_token))`
  - Files updated: `dhan_client.py`, `dhan_forever_orders.py`, `app.py`
  - Updated compatibility tests in `test_dhanhq_v2_2_compat.py`
  - ⚠️ Requires: `pip install --pre dhanhq` (v2.2.0 stable due Jan 10, 2026)

- **Groww API v2 Migration** (`strategies/groww/*.py`)
  - Updated `get_historical_candles()` parameter names:
    - `trading_symbol` → `groww_symbol` (with `NSE-` prefix)
    - `interval_in_minutes` → `candle_interval` (using SDK constants)
  - Files updated: `weekly_green_bb.py`, `tema_lsma_crossover.py`, `marubozu_intraday.py`, `weekly_dip_buyer.py`, `supertrend_vix_atr.py`

### 🐛 **BUG FIXES**

- **FutureWarning Fixes** (`runners/*.py`)
  - Fixed deprecated `fillna(method='ffill')` → `.ffill()`
  - Added `.infer_objects(copy=False)` before `.ffill()` to prevent implicit downcasting
  - Files fixed: `fast_run_basket.py`, `max_trades.py`, `standard_run_basket.py`

- **Weekly Green BB Strategy Cleanup** (`strategies/weekly_green_bb.py`)
  - Removed unused variant classes (WeeklyGreenBB20SD, WeeklyGreenBB15SD, etc.)
  - Changed from EMA to SMA for Bollinger Bands (matching optimization results)
  - Registry updated to remove variant registrations

### 📚 **DOCUMENTATION**

- **New Architecture Documentation** (`docs/ARCHITECTURE.md`)
  - Comprehensive module reference
  - Data flow diagrams
  - Design pattern explanations
  - Technical decisions rationale

- **Code Review Document** (`docs/CRITIQUE.md`)
  - Full repository analysis
  - Technical debt inventory
  - Improvement recommendations
  - Priority matrix for fixes

- **Strategy Documentation Template** (`docs/STRATEGY_TEMPLATE.md`)
  - Standard template for strategy docstrings
  - Entry/exit conditions format
  - Parameter documentation guide
  - Applied to all 15 strategies

- **Sphinx API Documentation** (`docs/api/`)
  - Auto-generated API docs from docstrings
  - Core module documentation
  - Strategy reference
  - Indicator reference
  - Build with: `cd docs/api && make html`

### ✨ **NEW FEATURES**

- **Centralized Indicators** (`utils/indicators.py`)
  - Added `TEMA()` - Triple Exponential Moving Average
  - Added `LSMA()` - Least Squares Moving Average (Linear Regression)
  - Updated strategy imports to use centralized definitions
  - Exported via `utils/__init__.py`

- **Test Fixtures** (`tests/conftest.py`)
  - Mock OHLCV data generators for CI
  - Synthetic VIX data generator
  - Basket data fixtures
  - No live cache required for tests

- **Runner Integration Tests** (`tests/test_runners.py`)
  - 18 new tests for runner functionality
  - Backtest engine integration tests
  - Metrics calculation tests
  - Edge case handling tests

### 🔧 **TYPE ANNOTATIONS**

- Added `py.typed` marker for PEP 561 compliance
- Relaxed mypy configuration for gradual adoption
- Fixed `Optional` type hints in `core/metrics.py`
- Module-specific strictness via `[[tool.mypy.overrides]]`

### 📦 **DEPENDENCIES**

- Added `docs` optional dependencies for Sphinx
- Fixed dhanhq version constraint (removed upper bound)

---

## [2.4.0] - 2026-01-02 - **WEEKLY FILTERS & TP OPTIMIZATION**

### ✨ **NEW FEATURES**

- **Weekly Filters for TEMA LSMA Strategy** (`strategies/tema_lsma_crossover.py`)
  - Added Weekly Candle Colour filter (require green = bullish week)
  - Added Weekly KER(10) > 0.4 filter (Kaufman Efficiency Ratio for trend strength)
  - Added Daily ATR% > 3.0% filter (volatility filter)
  - Filters verified for NO lookahead bias (strict `<` comparison for current week)
  - Performance improvement: PF 2.82 → 3.13 (+11%), trades 9,485 → 2,154 (77% reduction)

- **MFE-Based Take Profit Optimization** (`analyze_mfe_tp.py`)
  - New utility script for smart TP parameter optimization
  - Uses Maximum Favorable Excursion data to simulate 480 combinations
  - Completes in ~28 seconds vs 32-40 hours for full grid search
  - Identified optimal config: TP1=5%/0%, TP2=10%/0% (all exits at signal close)

- **ATR/MFE/MAE Columns in Consolidated Trades** (`runners/max_trades.py`)
  - Fixed bug where ATR, ATR%, MAE%, MAE_ATR, MFE%, MFE_ATR columns were empty
  - Changed `entry_data` → `symbol_df` to correctly access price data
  - Same fix applied to `runners/standard_run_basket.py`

### 🐛 **BUG FIXES**

- **ATR Calculation Bug** (`runners/max_trades.py`, `runners/standard_run_basket.py`)
  - Fixed undefined variable `entry_data` - should be `symbol_df`
  - ATR and related columns now correctly populated in consolidated trades

### 📊 **STRATEGY UPDATES**

- **TEMA LSMA Crossover** (`strategies/tema_lsma_crossover.py`)
  - Optimal configuration found after testing 10+ TP combinations:
    - TP1: 5% level, 0% exit (no partial exit)
    - TP2: 10% level, 0% exit (no partial exit)
    - All position exits at signal close
  - Weekly filters enabled by default:
    - `use_weekly_filters = True`
    - `require_weekly_green = True`
    - `weekly_ker_min = 0.4`
  - Performance: PF 3.13, WR 50.4%, 2,152 trades, 765K INR net P&L

### 📚 **DOCUMENTATION**

- **Consolidated Documentation** - Merged 8+ duplicate weekly filter docs into:
  - `docs/WRITING_STRATEGIES.md` (multi-timeframe filters section)
  - `docs/BACKTEST_GUIDE.md` (TP optimization section)
  - `docs/STARTUP_PROMPT.md` (current best strategy reference)

- **Cleanup** - Removed 45+ temporary files:
  - Log files (*.log)
  - Grid search scripts (grid_search*.py)
  - Analysis results (*.csv)
  - Verification scripts (*verify*.py)
  - Duplicate documentation (*FILTERS*.md, *IMPLEMENTATION*.md)

## [2.3.0] - 2025-12-26 - **TRAILING STOP FIX & WEBHOOK IMPROVEMENTS**

### 🐛 **CRITICAL BUG FIXES**

- **Trailing Stop Now Working** (`core/engine.py`)
  - Fixed critical bug where trailing stop was never actually working
  - Root cause: `state` dict was recreated fresh each bar, losing `entry_price` and `highest_high`
  - Solution: Added `persistent_state` dict that survives across bars
  - State is now synced properly between `on_entry()` and `on_bar()` calls
  - Trailing stop now correctly updates and triggers at varied P&L levels

- **Webhook Holdings Lookup Fixed** (`webhook-service/dhan_client.py`)
  - Fixed field name from `totalHoldings` (non-existent) to `availableQty` (correct Dhan API field)
  - This was causing all SELL orders to fail with "Available: 0"
  - Added fallback to `totalQty` if `availableQty` not present

### ✨ **NEW FEATURES**

- **Partial Sell Support** (`webhook-service/app.py`, `webhook-service/dhan_client.py`)
  - If trigger requests more shares than available, sells all available instead of rejecting
  - Response includes `partial_sell: true` flag and `original_quantity` field
  - Message indicates "(partial: X of Y)" when applicable
  - Only rejects if security not in holdings OR 0 shares available

- **Enhanced Holdings Debug Logging** (`webhook-service/dhan_client.py`)
  - Logs number of holdings found during validation
  - When security not found, shows first 10 security IDs in holdings for debugging

### 📊 **STRATEGY UPDATES**

- **Weekly Rotation Strategy** (`strategies/weekly_rotation.py`)
  - Added ADX > 25 filter for strong trend entries
  - Removed MACD and EMA filters (simplified)
  - Trailing stop disabled by default (use_trailing_stop=False)
  - Fixed stop loss at 10% below entry

### 🔧 **TECHNICAL CHANGES**

- **Engine State Persistence** (`core/engine.py`)
  - New `persistent_state = {}` initialized before position loop
  - State merged into bar context: `state.update(persistent_state)`
  - Key values synced back after `on_bar()`: `entry_price`, `highest_high`
  - `persistent_state` cleared on position close (3 locations)

---

## [2.2.0] - 2025-10-24 - **COMPLETE SYSTEM FINALIZATION**

### 🎯 **MAJOR ACHIEVEMENTS**
- **Portfolio Performance**: 353.27% total return (65.5% CAGR) with 10.33% max drawdown
- **Production Deployment**: System proven on 213-stock basket (943 trades over 3 years)
- **Architecture Complete**: Global market regime system fully operational
- **Repository Finalized**: Clean, optimized codebase ready for collaborative development

### Added
- **Global Market Regime System** (`core/global_market_regime.py`)
  - Ultra-fast NIFTY-based regime detection (<0.2ms per check)
  - Intelligent caching system for optimal performance
  - Consistent regime filtering across all stocks
  - Production-tested on large basket backtests

- **Complete Utils Library** (`utils/`)
  - 30+ technical indicators (SMA, EMA, RSI, ATR, MACD, Bollinger Bands, etc.)
  - Professional-grade indicator implementations
  - Performance analysis tools and risk metrics
  - Strategy management and optimization utilities

- **Advanced Visualization System** (`viz/`)
  - Interactive Bokeh-based charting system
  - Equity curve and drawdown analysis
  - Parameter optimization heatmaps
  - Professional trading dashboard components

- **Enhanced Documentation**
  - Complete session summary with code linkages
  - Architecture documentation with system flow
  - Performance benchmarks and optimization results
  - Production deployment guidelines

### Changed
- **Final Strategy Architecture**
  - `strategies/ichimoku.py`: Production-ready with global market regime integration
  - Removed experimental wrappers and development artifacts
  - Optimized for production deployment

- **Repository Structure Optimization**
  - Enhanced .gitignore with comprehensive temporary file patterns
  - Cleaned all session-specific development files
  - Removed experimental comparison and debug scripts
  - Optimized imports and dependency management

- **Performance Enhancements**
  - Streamlined backtesting pipeline (~8 stocks/second processing)
  - Optimized memory usage (~2.6% during large runs)
  - Enhanced caching system with intelligent expiry
  - Vectorized calculations for improved speed

### Fixed
- **Market Regime Architecture**: Fixed duplicate regime calculations across stocks
- **Code Quality**: Applied Black, isort, Ruff formatting across entire codebase
- **Import Optimization**: Removed unused imports and cleaned dependencies
- **Documentation**: Updated all references to maintain code linkages

### Removed
- **Temporary Development Files**
  - All comparison scripts and analysis files
  - Demo and baseline comparison files
  - Experimental strategy wrappers
  - Temporary test basket files
  - Session-specific debug scripts

- **Experimental Code**: Cleaned up all wrapper experiments and debug artifacts

## [2.1.0] - 2025-10-23 - **GLOBAL MARKET REGIME IMPLEMENTATION**

### Added
- Global market regime system architecture
- NIFTY-based market condition analysis
- Performance optimization and caching
- Comprehensive backtesting on large baskets

### Fixed
- Market regime calculation duplication across stocks
- Performance bottlenecks in regime detection
- Memory optimization for large basket processing

## [2.0.0] - 2025-01-23

### Added
- Complete repository cleanup and modernization
- Comprehensive CI/CD pipeline with GitHub Actions
- Pre-commit hooks for code quality enforcement
- Modern Python 3.11+ type annotations throughout codebase
- Automated code formatting with Black, isort, and Ruff
- Professional project structure and documentation
- Development automation with Makefile
- Comprehensive .gitignore and .editorconfig
- Security scanning with Bandit and Safety

### Changed
- **BREAKING**: Updated all type annotations to modern Python 3.11+ syntax
- **BREAKING**: Standardized code style across entire codebase
- Improved error handling and logging throughout
- Enhanced pyproject.toml with complete project metadata
- Modernized pre-commit configuration
- Updated README with comprehensive documentation

### Fixed
- Resolved 120+ linting issues across codebase
- Fixed quote consistency (single → double quotes)
- Corrected variable naming conventions (PEP 8 compliance)
- Improved exception handling patterns
- Fixed trailing whitespace and formatting issues

### Removed
- Deprecated typing imports (Dict, List, Optional, Tuple)
- Unused variables and dead code
- Temporary files and cache artifacts
- Outdated configuration files

## [1.9.0] - 2024-10-23

### Added
- Ichimoku Cloud strategy with comprehensive filter system
- Support for 308-stock basket backtesting
- Multi-timeframe portfolio analysis (1Y, 3Y, 5Y, ALL)
- Enhanced error handling in portfolio curve building
- Robust datetime handling for trade management

### Fixed
- Portfolio curve building errors and arithmetic operations
- Trade filtering and validation issues
- DateTime comparison and timezone handling
- Technical indicator calculation stability

## [1.8.0] - 2024-09-15

### Added
- Enhanced strategy registry system
- Improved data loading and caching mechanisms
- TradingView-compatible trade export functionality
- Comprehensive performance metrics calculation

### Changed
- Refactored core backtesting engine for better modularity
- Improved strategy interface and base class design
- Enhanced configuration management system

## [1.7.0] - 2024-08-10

### Added
- Donchian Channel strategy implementation
- EMA Cross strategy with trend filters
- ATR-based breakout strategy
- Enhanced risk management features

### Fixed
- Performance calculation edge cases
- Data alignment issues in multi-symbol backtests
- Memory optimization for large datasets

## [1.6.0] - 2024-07-05

### Added
- Multi-symbol portfolio backtesting capability
- Comprehensive basket management system
- Enhanced reporting and visualization features
- Risk-adjusted performance metrics

### Changed
- Improved data fetching and API integration
- Enhanced strategy parameter management
- Better error handling and logging

## [1.5.0] - 2024-06-01

### Added
- Technical indicator library expansion
- Custom strategy development framework
- Advanced position sizing algorithms
- Enhanced stop-loss and take-profit logic

# Changelog

All notable changes to QuantLab will be documented in this file.

## [2.1.0] - 2024-10-24

### 🎯 Major Architectural Improvements
- **FIXED**: Global Market Regime System - Market regime now calculated ONCE using NIFTY data and applied consistently across ALL stocks
- **OPTIMIZED**: Ultra-fast regime checks (< 0.2ms per check) with intelligent caching system
- **PERFORMANCE**: Successfully backtested 213-stock basket generating 943 trades over 3Y (353.27% portfolio return, 65.5% CAGR, 10.33% max drawdown)

### 🧹 Repository Cleanup & Code Quality
- **CLEANED**: Removed temporary analysis files (test_*.py, performance_*.py, *_comparison.py)
- **FORMATTED**: Applied Black, isort, and Ruff for consistent code style across entire codebase
- **OPTIMIZED**: Cleaned unused imports and streamlined project structure
- **ORGANIZED**: Updated .gitignore to prevent future temporary file accumulation

### 🚀 Performance Improvements
- **STREAMLINED**: Backtesting pipeline processing at ~8 stocks/second
- **EFFICIENT**: Memory usage optimized to ~2.6% during large basket runs
- **FAST**: Eliminated pandas performance bottlenecks in market regime calculations

### 📚 Documentation Updates
- **UPDATED**: README with recent improvements and performance metrics
- **ENHANCED**: Repository structure documentation and cleanup protocols

## [2.0.0] - 2024-01-01

### Added
- Complete system architecture redesign
- Enhanced strategy framework with Strategy.I() wrapper
- Professional technical indicators library
- Advanced market regime detection
- Comprehensive performance reporting
- Interactive HTML visualizations

---

## Release Notes

### Version 2.0.0 - Major Modernization

This release represents a complete modernization of the QuantLab codebase:

#### Development Experience Improvements
- **Modern Tooling**: Full integration of Black, isort, Ruff, and MyPy
- **Automation**: Comprehensive Makefile for common development tasks
- **Pre-commit Hooks**: Automatic code quality checks on every commit
- **CI/CD**: Professional GitHub Actions pipeline with testing and security scanning

#### Code Quality Enhancements
- **Type Safety**: Complete migration to Python 3.11+ type annotations
- **Style Consistency**: Enforced PEP 8 compliance across entire codebase
- **Error Handling**: Improved exception handling and logging patterns
- **Security**: Added security scanning and vulnerability checking

#### Project Structure
- **Professional Setup**: Complete pyproject.toml with all metadata
- **Documentation**: Enhanced README and comprehensive docs
- **Git Configuration**: Proper .gitignore, .gitattributes, and repository setup

This release maintains full backward compatibility while significantly improving maintainability and developer experience.
