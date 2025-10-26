# QuantLab Complete Workflow Guide

**Comprehensive documentation for the entire QuantLab backtesting workflow - from basket configuration to report generation**

*Updated: 2025-10-19*

---

## 🎯 Overview

This guide documents the complete workflow for using QuantLab, from initial setup through generating backtest reports. It formalizes the entire process with best practices, data management rules, and production-ready procedures.

## 📋 Table of Contents

1. [System Setup & Configuration](#1-system-setup--configuration)
2. [Basket Management](#2-basket-management)
3. [Symbol Mapping & Data Sources](#3-symbol-mapping--data-sources)
4. [Data Fetching Pipeline](#4-data-fetching-pipeline)
5. [Backtest Execution](#5-backtest-execution)
6. [Report Generation & Analysis](#6-report-generation--analysis)
7. [Data Management Best Practices](#7-data-management-best-practices)
8. [Production Workflow](#8-production-workflow)
9. [Troubleshooting Guide](#9-troubleshooting-guide)

---

## 1. System Setup & Configuration

### 1.1 Initial Environment Setup

```bash
# 1. Clone and setup project
git clone <repo-url> quantlab
cd quantlab

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Validate system structure
python3 config.py
```

### 1.2 Dhan API Configuration

**Step 1**: Create `.env` file in project root:
```env
DHAN_ACCESS_TOKEN=eyJ...your_jwt_token_here
DHAN_CLIENT_ID=your_client_id
```

**Step 2**: Validate credentials:
```bash
python3 config.py
# Expected: "✅ System ready for use!"
```

### 1.3 Directory Structure Validation

Ensure all required directories exist:
```
quantlab/
├── config.py                    # ✅ Centralized configuration
├── .env                         # ✅ API credentials
├── data/
│   ├── basket.txt              # ✅ Default trading symbols
│   ├── basket_mega.txt         # ✅ Mega-cap basket (72 stocks)
│   ├── basket_large.txt        # ✅ Large-cap basket (103 stocks)
│   ├── basket_mid.txt          # ✅ Mid-cap basket (51 stocks)
│   ├── basket_small.txt        # ✅ Small-cap basket (99 stocks)
│   └── cache/                  # ✅ Data cache directory
├── scripts/                     # ✅ Utility scripts
├── core/                        # ✅ Backtesting engine
├── strategies/                  # ✅ Trading strategies
├── runners/                     # ✅ Execution scripts
└── reports/                     # ✅ Generated results
```

---

## 2. Basket Management

### 2.1 Basket Types & Configuration

QuantLab supports multiple basket configurations managed through `config.py`:

| Basket Type | File | Symbol Count | Market Cap | Volume Criteria |
|-------------|------|--------------|------------|-----------------|
| **Default** | `data/basket.txt` | Variable | Mixed | User-defined |
| **Mega** | `data/basket_mega.txt` | 72 | Large-cap | 5M+ daily volume |
| **Large** | `data/basket_large.txt` | 103 | Large-cap | 2.5M+ daily volume |
| **Mid** | `data/basket_mid.txt` | 51 | Mid-cap | 500K+ daily volume |
| **Small** | `data/basket_small.txt` | 99 | Small-cap | 100K+ daily volume |

### 2.2 Basket Selection Logic

```python
# From config.py
BASKET_FILES = {
    "default": "data/basket.txt",
    "mega": "data/basket_mega.txt", 
    "large": "data/basket_large.txt",
    "mid": "data/basket_mid.txt",
    "small": "data/basket_small.txt"
}

DEFAULT_BASKET_SIZE = "default"  # Points to basket.txt for backward compatibility
```

### 2.3 Basket Usage Examples

```bash
# Use default basket (data/basket.txt)
python3 -m runners.run_basket --strategy ichimoku

# Use specific basket size
python3 -m runners.run_basket --basket_size mega --strategy ichimoku

# Use custom basket file
python3 -m runners.run_basket --basket_file data/my_custom_basket.txt --strategy ichimoku
```

### 2.4 Creating Custom Baskets

**Format**: One symbol per line
```txt
RELIANCE
HDFCBANK
ICICIBANK
INFY
TCS
```

**Validation**:
```bash
python3 scripts/check_basket_data.py --basket_file data/my_basket.txt
```

---

## 3. Symbol Mapping & Data Sources

### 3.1 Symbol to Security ID Mapping

QuantLab uses Dhan Security IDs for data fetching. The mapping process:

1. **Master File**: `data/dhan_symbol_mapping_comprehensive.csv`
2. **Format**:
   ```csv
   symbol,security_id,instrument_type,exchange
   RELIANCE,2885,EQUITY,NSE
   HDFCBANK,1333,EQUITY,NSE
   ```

3. **Auto-generation**:
   ```bash
   python3 scripts/create_symbol_mapping.py
   ```

### 3.2 Data Source Priority

**Primary → Fallback Chain**:
1. **Dhan API** (Primary): Real-time Indian market data
2. **yfinance** (Fallback): When Dhan unavailable
3. **Cache** (Local): Previously fetched data

### 3.3 Symbol Resolution Process

```python
def resolve_symbol_to_security_id(symbol):
    """
    1. Check dhan_symbol_mapping_comprehensive.csv
    2. If not found, attempt direct API call
    3. If API fails, use yfinance with .NS suffix
    4. Cache successful mappings for future use
    """
```

---

## 4. Data Fetching Pipeline

### 4.1 Unified Data Fetching System

**Core Script**: `scripts/fetch_data.py`

**Key Features**:
- ✅ Cache-first approach (30-day expiry)
- ✅ Dhan API primary, yfinance fallback
- ✅ Intelligent error handling & retry logic
- ✅ Metadata tracking and validation
- ✅ Rate limiting (0.1s between API calls)

### 4.2 Data Fetching Rules (Formalized)

#### Rule 1: Cache-First Policy
```
IF cache exists AND age < 30 days:
    USE cached data
ELSE:
    FETCH new data from API
    UPDATE cache
```

#### Rule 2: Source Priority
```
TRY Dhan API with security_id
IF Dhan fails:
    TRY yfinance with symbol.NS
IF both fail:
    USE existing cache (if available)
    LOG warning
```

#### Rule 3: Cache Management
```
- Automatic 30-day expiry
- Metadata tracking (source, timestamp, row count)
- Duplicate detection and cleanup
- No manual cache deletion during active fetching
```

### 4.3 Data Fetching Commands

#### Basic Usage
```bash
# Fetch all symbols in default basket
python3 scripts/fetch_data.py

# Fetch specific symbols
python3 scripts/fetch_data.py RELIANCE INFY HDFCBANK

# Fetch all symbols in specific basket
python3 scripts/fetch_data.py --basket_file data/basket_mega.txt
```

#### Advanced Options
```bash
# Force refresh (ignore cache)
python3 scripts/fetch_data.py --force-refresh

# Clean redundant cache files
python3 scripts/fetch_data.py --clean-cache

# Dry run (show what would be done)
python3 scripts/fetch_data.py --dry-run

# Use cache only (no API calls)
python3 scripts/fetch_data.py --use_cache_only
```

### 4.4 Data Quality Validation

**Automatic Checks**:
- Minimum row count (252 days for 1-year data)
- Date range validation
- OHLCV data completeness
- Volume > 0 validation

**Manual Validation**:
```bash
python3 scripts/check_basket_data.py --basket_file data/basket_mega.txt
```

---

## 5. Backtest Execution

### 5.1 Backtest Engine Architecture

**Core Components**:
```
core/
├── engine.py          # Main backtesting engine
├── strategy.py        # Strategy base class
├── perf.py            # Performance calculations
├── report.py          # Report generation
└── pine_adapter.py    # Pine Script compatibility
```

### 5.2 Strategy Execution Framework

**Available Strategies**:
- `ichimoku` - Ichimoku Cloud strategy
- `ema_cross` - EMA crossover strategy  
- `atr_breakout` - ATR-based breakout
- `donchian` - Donchian Channel strategy
- `envelope_kd` - Envelope with KD indicators

### 5.3 Backtest Execution Commands

#### Basic Backtesting
```bash
# Run with default parameters
python3 -m runners.run_basket --strategy ichimoku

# Specify basket size
python3 -m runners.run_basket --basket_size mega --strategy ichimoku

# Custom parameters
python3 -m runners.run_basket --strategy ichimoku --params '{"conversion_line_length": 9, "base_line_length": 26}'
```

#### Advanced Configuration
```bash
# Full parameter specification
python3 -m runners.run_basket \
  --basket_size mega \
  --strategy ichimoku \
  --params '{}' \
  --interval 1d \
  --period 1y \
  --cache_dir data/cache
```

### 5.4 Strategy Parameters

**Parameter Format**: JSON string
```bash
# Default parameters (empty)
--params '{}'

# Ichimoku parameters
--params '{"conversion_line_length": 9, "base_line_length": 26, "leading_span_b_length": 52}'

# EMA Cross parameters  
--params '{"ema_fast": 12, "ema_slow": 26}'
```

### 5.5 Execution Validation

**Pre-execution Checks**:
1. ✅ Data availability for all basket symbols
2. ✅ Strategy parameter validation
3. ✅ Cache freshness verification
4. ✅ Output directory creation

**During Execution**:
- Symbol-by-symbol processing with debug logs
- Trade entry/exit time validation
- Performance metric calculation
- Error handling for individual symbol failures

---

## 6. Report Generation & Analysis

### 6.1 Report Structure

**Generated Report Directory**: `reports/YYYYMMDD-HHMMSS/`

```
reports/20251019-210224/
├── strategy_backtests_summary.csv              # Strategy overview
├── portfolio_key_metrics_1Y.csv                # 1-year metrics
├── portfolio_key_metrics_3Y.csv                # 3-year metrics  
├── portfolio_key_metrics_5Y.csv                # 5-year metrics
├── portfolio_key_metrics_ALL.csv               # All-time metrics
├── consolidated_trades_1Y.csv                  # 1-year trades
├── consolidated_trades_3Y.csv                  # 3-year trades
├── consolidated_trades_5Y.csv                  # 5-year trades
├── consolidated_trades_ALL.csv                 # All trades
├── portfolio_daily_equity_curve_1Y.csv         # Daily performance
├── portfolio_monthly_equity_curve_1Y.csv       # Monthly performance
└── ...                                         # Multiple timeframes
```

### 6.2 Key Performance Metrics

**Portfolio-Level Metrics**:
- Total Return %
- CAGR (Compound Annual Growth Rate)
- Maximum Drawdown %
- Sharpe Ratio
- Volatility %
- Win Rate %
- Profit Factor

**Trade-Level Analysis**:
- Individual trade P&L
- Entry/Exit timestamps
- Hold duration
- Return per trade
- Cumulative performance

### 6.3 Report Formats

**CSV Format**: Standardized with proper formatting
- Percentage columns: 2 decimals + % suffix
- Currency columns: No decimals (INR whole numbers)
- Date columns: YYYY-MM-DD format

**Example Metrics**:
```csv
Symbol,Total_Return_%,CAGR_%,Max_Drawdown_%,Sharpe_Ratio,Win_Rate_%
RELIANCE,23.45%,8.67%,12.34%,1.23,67.89%
HDFCBANK,18.92%,6.45%,8.76%,1.45,72.34%
```

---

## 7. Data Management Best Practices

### 7.1 Cache Management Rules

#### Automatic Cache Management
- **Expiry**: 30 days from creation
- **Cleanup**: Automatic removal of redundant files
- **Validation**: Metadata consistency checks
- **Storage**: Efficient CSV format with metadata JSON

#### Manual Cache Operations
```bash
# Check cache status
python3 scripts/fetch_data.py --dry-run

# Clean redundant files
python3 scripts/fetch_data.py --clean-cache

# Force complete refresh
python3 scripts/fetch_data.py --force-refresh --basket_file data/basket_mega.txt
```

### 7.2 Data Freshness Policy

**Requirements**:
- Market data must be < 30 days old for backtesting
- Intraday strategies require daily refresh
- Long-term strategies can use weekly refresh

**Implementation**:
```python
def is_cache_fresh(cache_file, max_age_days=30):
    """Check if cached data is within acceptable age limit"""
    if not os.path.exists(cache_file):
        return False
    
    file_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).days
    return file_age <= max_age_days
```

### 7.3 Error Handling & Recovery

**Data Fetching Failures**:
1. Log the failure with timestamp
2. Attempt fallback data source
3. Use existing cache if available
4. Skip symbol if no data available
5. Continue processing remaining symbols

**Recovery Procedures**:
```bash
# Recover failed symbol fetches
python3 scripts/fetch_data.py FAILED_SYMBOL --force-refresh

# Check system integrity
python3 config.py
python3 scripts/check_basket_data.py
```

---

## 8. Production Workflow

### 8.1 Daily Workflow

**Morning Setup** (Before Market Open):
```bash
# 1. Validate system
source .venv/bin/activate
python3 config.py

# 2. Check data freshness
python3 scripts/fetch_data.py --dry-run

# 3. Refresh stale data
python3 scripts/fetch_data.py --basket_file data/basket_mega.txt
```

**Strategy Execution**:
```bash
# 4. Run primary strategies
python3 -m runners.run_basket --basket_size mega --strategy ichimoku --params '{}'

# 5. Generate additional analysis
python3 scripts/rank_strategies.py
```

**End-of-Day Cleanup**:
```bash
# 6. Clean redundant cache
python3 scripts/fetch_data.py --clean-cache

# 7. Archive old reports (optional)
# Manual: move old report folders to archive/
```

### 8.2 Weekly Workflow

**Weekly Maintenance**:
```bash
# 1. Complete data refresh
python3 scripts/fetch_data.py --force-refresh

# 2. Update symbol mappings
python3 scripts/create_symbol_mapping.py

# 3. Validate all baskets
for basket in mega large mid small; do
    python3 scripts/check_basket_data.py --basket_file data/basket_${basket}.txt
done

# 4. Run comprehensive backtests
python3 -m runners.run_basket --basket_size mega --strategy ichimoku --period 3y
```

### 8.3 Monthly Workflow

**Monthly Analysis**:
```bash
# 1. Historical performance analysis
python3 -m runners.run_basket --basket_size mega --strategy ichimoku --period 5y

# 2. Strategy comparison
python3 scripts/rank_strategies.py --timeframe all

# 3. Portfolio rebalancing analysis
# Manual: Review basket compositions and performance
```

---

## 9. Troubleshooting Guide

### 9.1 Common Issues & Solutions

#### System Configuration Issues

**Problem**: `AttributeError: 'QuantLabConfig' object has no attribute 'X'`
```bash
# Solution: Update imports
# OLD: from config import config.X
# NEW: from config import X
```

**Problem**: `FileNotFoundError: .env file not found`
```bash
# Solution: Create .env file
echo "DHAN_ACCESS_TOKEN=your_token" > .env
echo "DHAN_CLIENT_ID=your_client_id" >> .env
```

#### Data Fetching Issues

**Problem**: `DH-906: Invalid Token`
```bash
# Solution: Refresh Dhan token
# 1. Get new token from Dhan dashboard
# 2. Update .env file
# 3. Restart terminal session
```

**Problem**: `No data returned for symbol X`
```bash
# Solution: Check symbol mapping
python3 scripts/create_symbol_mapping.py
# Manual: Verify symbol exists in market
```

#### Backtest Execution Issues

**Problem**: `No trades generated for symbol X`
```bash
# Solution: Check data quality and strategy parameters
python3 scripts/check_basket_data.py --symbol X
# Review strategy parameters for reasonableness
```

**Problem**: `Memory error during large basket processing`
```bash
# Solution: Process in smaller chunks
# Split large baskets into smaller files
# Increase system memory or use cloud instance
```

### 9.2 Performance Optimization

#### Data Fetching Performance
```bash
# Use cache-only mode when possible
python3 scripts/fetch_data.py --use_cache_only

# Batch process multiple symbols
python3 scripts/fetch_data.py SYMBOL1 SYMBOL2 SYMBOL3 --batch_size 10
```

#### Backtest Performance
```bash
# Use shorter time periods for testing
python3 -m runners.run_basket --period 1y --strategy test_strategy

# Process smaller baskets first
python3 -m runners.run_basket --basket_size small --strategy ichimoku
```

### 9.3 Debug Mode

**Enable Debug Logging**:
```bash
# Set environment variable
export QUANTLAB_DEBUG=1

# Run with verbose output
python3 -m runners.run_basket --basket_size mega --strategy ichimoku --verbose
```

**Debug Information Includes**:
- Data loading timestamps
- Strategy signal generation
- Trade entry/exit details
- Performance calculation steps
- Cache hit/miss statistics

---

## 10. Best Practices Summary

### 10.1 System Hygiene
- ✅ Always validate system before use: `python3 config.py`
- ✅ Keep data fresh: refresh cache weekly
- ✅ Clean redundant files: use `--clean-cache` option
- ✅ Monitor disk space: cache can grow large
- ✅ Backup reports: important results should be archived

### 10.2 Data Management  
- ✅ Use cache-first approach for performance
- ✅ Validate data quality before backtesting
- ✅ Handle missing data gracefully
- ✅ Keep symbol mappings updated
- ✅ Monitor API rate limits

### 10.3 Backtesting
- ✅ Start with small baskets for testing
- ✅ Validate strategy parameters
- ✅ Review generated reports thoroughly
- ✅ Compare multiple timeframes
- ✅ Document strategy modifications

### 10.4 Production Deployment
- ✅ Use virtual environments
- ✅ Secure API credentials
- ✅ Implement monitoring and alerts
- ✅ Schedule regular maintenance
- ✅ Keep comprehensive logs

---

## 📞 Support & Documentation

- **System Validation**: `python3 config.py`
- **Script Help**: `python3 scripts/fetch_data.py --help`
- **Complete Guide**: `docs/QUANTLAB_GUIDE.md`
- **API Reference**: `docs/README.md`

---

*This workflow guide provides the complete formalized process for using QuantLab from initial setup through production deployment. Follow these procedures for consistent, reliable backtesting results.*