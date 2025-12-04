# QuantLab Trading System

**Professional backtesting framework for Indian equities with clean architecture**

**Latest Update**: December 2, 2025 - Open trades metrics fixes verified and production-ready

---

## 🆕 Latest Updates (December 2, 2025)

### ✅ Open Trades Metrics - All Issues Resolved

Three critical issues with open trade calculations have been **fixed and validated**:

| Issue | Status | Details |
|-------|--------|---------|
| **Run-up/Drawdown identical** | ✅ FIXED | Now shows different values (run-up ≥ 0, drawdown ≤ 0) |
| **Holding days showing 0** | ✅ FIXED | Now shows actual days held; 0 only for same-day entries |
| **Net P&L % showing 0** | ✅ FIXED | Now shows mark-to-market percentage |

**Code Changes**: `runners/run_basket.py` lines 3760-3945  
**Affected Files**: Consolidated trades CSV files now show correct metrics

### ✅ Documentation Consolidated

Three separate webhook guides have been consolidated into one comprehensive guide:
- `WEBHOOK_SERVICE_COMPLETE_GUIDE.md` (450+ lines, production-ready)
- Covers OAuth, order routing, API endpoints, deployment, monitoring

### ✅ KAMA Strategy Fixed

- Missing `len_filter` parameter added
- Filter value set to 200 (optimal for backtests)
- Strategy now runs without errors

---

## 📚 Documentation Navigation

### Getting Started (Choose Your Path)

| If You Want To... | Read This | Next |
|-------------------|-----------|------|
| **Get started quickly** | Start here (this page) | BACKTEST_GUIDE.md |
| **Check open trades** | BACKTEST_GUIDE.md (Open Trades Section) | STRATEGIES.md |
| **Run a backtest** | BACKTEST_GUIDE.md | STRATEGIES.md |
| **Set up Dhan API** | DHAN_COMPREHENSIVE_GUIDE.md | BACKTEST_GUIDE.md |
| **Deploy webhook service** | WEBHOOK_SERVICE_COMPLETE_GUIDE.md | See webhook-service/docs/ |
| **Develop features** | STARTUP_PROMPT.md (Dev Workflow section) | Code Quality Standards |
| **Set up new session** | STARTUP_PROMPT.md (Quick Session Start) | Verify Environment |
| **Clean up session** | JANITOR_PROMPT.md | Commit & Push |
| **Add new strategy** | STRATEGIES.md | BACKTEST_GUIDE.md (Testing) |

### Documentation Files (Complete Reference)
1. **QUANTLAB_GUIDE.md** ← You are here (system overview)
2. **BACKTEST_GUIDE.md** (how to run backtests, open trades metrics)
3. **STRATEGIES.md** (trading strategies reference)
4. **STARTUP_PROMPT.md** (session initialization and dev workflow)
5. **JANITOR_PROMPT.md** (session cleanup)

**Additional References:**
- **WEBHOOK_SERVICE_COMPLETE_GUIDE.md** (production webhook service)
- **DHAN_COMPREHENSIVE_GUIDE.md** (API reference)
- **webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md** (credential setup)
- **webhook-service/docs/DHAN_OAUTH_COMPLETE_GUIDE.md** (OAuth details)
- **webhook-service/docs/DHAN_LIVE_TRADING_GUIDE.md** (live order execution)
- **README.md** (documentation index)

---

## 🏗️ **System Architecture (v2.0)**

### **Clean Directory Structure**
```
quantlab/
├── config.py                    # 🎯 Centralized configuration
├── scripts/                     # 🛠️ All utility scripts
│   ├── fetch_data.py            # Data fetching (Dhan + yfinance)
│   ├── create_symbol_mapping.py # Symbol mapping utilities
│   ├── check_basket_data.py     # Data validation
│   └── rank_strategies.py       # Strategy analysis
├── data/
│   ├── cache/                   # 📦 Smart cache (30-day expiry)
│   ├── basket.txt              # Trading symbols
│   └── *.csv                   # Market data
├── core/                        # 🧠 Backtesting engine
├── strategies/                  # 📈 Trading strategies
├── runners/                     # ⚡ Strategy execution
├── reports/                     # 📊 Generated results
├── docs/                        # 📚 All documentation (here!)
├── viz/                         # 📉 Visualization tools
└── tests/                       # 🧪 Test suite
```

### **Key Improvements**
- ✅ **Clean Structure**: No clutter, everything organized
- ✅ **Centralized Config**: All settings in `config.py`
- ✅ **Single Scripts Dir**: Tools merged into scripts  
- ✅ **Documentation Hub**: Everything in `docs/`
- ✅ **Smart Caching**: Automatic cleanup and expiry

---

## 🚀 **Quick Start**

### **1. Setup Environment**
```bash
# Clone and setup
git clone <repo-url> quantlab
cd quantlab

# Virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### **2. Configure Dhan API**
Create `.env` file:
```env
DHAN_ACCESS_TOKEN=eyJ...your_jwt_token_here
DHAN_CLIENT_ID=your_client_id
```

### **3. Validate System**
```bash
python3 config.py                               # Test configuration
```

### **4. Fetch Market Data**
```bash
# Fetch all basket data using Dhan API
python3 scripts/dhan_fetch_data.py

# Note: Data cache automatically manages refresh with 30-day expiry
```

### **5. Run Backtesting**
## 🚀 Quick Start

### Basic Backtest
```bash
# Run on default basket (data/basket.txt) with ichimoku strategy
python3 -m runners.run_basket --strategy ichimoku --interval 1d --period max

# Run on specific basket size  
python3 -m runners.run_basket --basket_size large --strategy ichimoku --interval 1d --period max

# Run EMA Crossover strategy with custom parameters
python3 -m runners.run_basket --strategy ema_crossover --params '{"fast": 12, "slow": 26}' --interval 1d --period max
```

### Available Baskets
- **Default (data/basket.txt)**: Your main basket file
- **Mega**: Large-cap, high-volume stocks
- **Large**: Established large-cap stocks
- **Mid**: Mid-cap stocks
- **Small**: Small-cap stocks
- **Test**: 3 stocks for quick testing

**Default Behavior**: Uses `data/basket.txt` for backward compatibility with existing scripts.

### Custom Baskets
```bash
# Use your own basket file
python3 -m runners.run_basket --basket_file data/my_basket.txt --strategy ema_crossover --interval 1d --period max
```

---

## 📁 **Configuration System**

### **Centralized Management**
All system settings are in `config.py`:

```python
from config import config, DATA_DIR, CACHE_DIR

# File paths
cache_dir = CACHE_DIR                    # data/cache/
data_dir = DATA_DIR                      # data/

# API settings  
dhan_rate_limit = config.dhan.rate_limit_seconds     # 0.1s
cache_expiry = config.cache.expiry_days              # 30 days
```

### **Environment Features**
- ✅ **Auto-validation**: Credential checking
- ✅ **Path Management**: Automatic directory creation
- ✅ **Error Prevention**: Token conflict resolution
- ✅ **Production Ready**: Environment safety

---

## 🗂️ **Data Management**

### **Smart Cache System**
```
data/cache/
├── dhan_historical_2885.csv           # RELIANCE (Dhan API)
├── dhan_historical_2885_metadata.json # Source tracking
├── dhan_historical_1333.csv           # HDFCBANK (Dhan API)  
└── dhan_historical_1333_metadata.json # Metadata
```

### **Data Sources & Fallback**
1. **Dhan API** (Primary): Real Indian market data
2. **yfinance** (Fallback): Backup when Dhan unavailable
3. **Cache** (Speed): 30-day local storage

### **Cache Features**
- ✅ **30-day expiry**: Automatic refresh
- ✅ **Metadata tracking**: Source, timestamp, rows
- ✅ **Smart cleanup**: Remove redundant files
- ✅ **Rate limiting**: API protection

### **Cache Management**
```bash
# Data fetching with primary script
python3 scripts/dhan_fetch_data.py

# Note: Data cache is automatically managed with 30-day expiry
```

---

## 🛠️ **Scripts Directory**

### **Available Scripts**

| Script | Purpose | Usage |
|--------|---------|-------|
| `dhan_fetch_data.py` | Data fetching with Dhan API | `python3 scripts/dhan_fetch_data.py` |

### **Script Features**
- All scripts use centralized config
- Consistent error handling
- Progress reporting
- Help documentation (`--help`)

---

## 📈 **Trading & Backtesting**

### **Strategy Development**
```python
# strategies/my_strategy.py
def my_strategy(data, params):
    # Your trading logic here
    return signals

# Core backtesting
from core.engine import backtest_strategy
results = backtest_strategy(data, my_strategy, params)
```

### **Performance Metrics**
QuantLab v2.0 includes comprehensive performance analysis:

#### **Key Metrics Calculated**
- **Net P&L %**: Total portfolio return percentage
- **CAGR**: Compound Annual Growth Rate
- **Max Equity Drawdown %**: Maximum portfolio decline from peak
- **Individual Trade Metrics**: Run-up and drawdown for each trade
- **Profit Factor**: Gross profit / Gross loss ratio
- **Win Rate**: Percentage of profitable trades

#### **Enhanced Drawdown Calculation**
The system now uses **individual trade-based drawdown calculation** for more accurate risk assessment:
- Symbol-level max drawdown uses the highest individual trade drawdown
- More meaningful than equity curve-based calculations
- Represents actual trading risk during position holding

#### **Consolidated Trade Reports**
Each backtest generates detailed trade files with:
- Entry/Exit prices and dates
- Position sizes and values
- Net P&L in INR and percentage
- Run-up: Maximum favorable movement during trade
- Drawdown: Maximum adverse movement during trade

### **Running Backtests**
```bash
# Basic run
python3 -m runners.run_basket --basket_file data/basket.txt --strategy ema_crossover

# With parameters
python3 -m runners.run_basket --strategy ema_crossover --params '{"fast": 12, "slow": 26}'

# Different timeframes
python3 -m runners.run_basket --interval 1d --period 1y --strategy ema_crossover
```

### **Available Strategies**

#### **Ichimoku Cloud Strategy** ⭐ 
Advanced trend-following strategy with multi-timeframe confirmation.

```bash
# Basic ichimoku (1d interval)
python3 -m runners.run_basket --strategy ichimoku --basket_size large --interval 1d --period max

# With specific parameters
python3 -m runners.run_basket --strategy ichimoku --basket_size large --interval 1d \
    --params '{"conversion_period": 9, "base_period": 26}'
```

**Strategy Features**:
- Conversion line (fast trend): 9-period high-low average
- Base line (slow trend): 26-period high-low average
- Cloud (leading indicator): 52-period range
- Trend confirmation across multiple timeframes

#### **Other Strategies**
- **EMA Cross**: Simple moving average crossover (fast/slow periods)
- **Knoxville**: Multi-indicator advanced strategy

### Running Backtests
```bash
# Basic run
python3 -m runners.run_basket --basket_file data/basket.txt --strategy ema_crossover

# With parameters
python3 -m runners.run_basket --strategy ema_crossover --params '{"fast": 12, "slow": 26}'

# Different timeframes
python3 -m runners.run_basket --interval 1d --period max --strategy ema_crossover
```

#### **Other Strategies**
- **EMA Cross**: Simple moving average crossover
- **ATR Breakout**: Volatility-based breakout system
- **Donchian**: Channel breakout strategy
- **Envelope KD**: KD oscillator with price envelopes

### **Report Generation**
Results are saved in `reports/` with timestamp folders:
- **Portfolio Key Metrics**: Symbol-wise and total performance
- **Consolidated Trades**: Individual trade details with run-up/drawdown
- **Equity Curves**: Daily and monthly portfolio value progression
- **Strategy Summaries**: Comparative analysis across time periods

---

## 🔧 **API Configuration**

### **Dhan API Setup**
1. **Get Credentials**: From Dhan trading platform
2. **Create .env**: In project root
3. **Format**: 
   ```env
   DHAN_ACCESS_TOKEN=eyJ...your_jwt_token
   DHAN_CLIENT_ID=your_client_id
   ```

### **API Settings**
```python
# Configured in config.py
DHAN_API_URL = "https://api.dhan.co/v2"
RATE_LIMIT = 0.1  # seconds between requests
TIMEOUT = 30      # request timeout
```

### **Data Format**
```csv
date,open,high,low,close,volume
2024-01-01,2500.0,2550.0,2480.0,2520.0,1000000
2024-01-02,2520.0,2580.0,2510.0,2570.0,1200000
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

**1. Configuration Error**
```bash
# Check system
python3 config.py

# Expected output: "✅ System ready for use!"
```

**2. Data Fetching Failed**
```bash
# Test connection
python3 scripts/fetch_data.py --dry-run

# Force refresh
python3 scripts/fetch_data.py SYMBOL --force-refresh
```

**3. Environment Issues**
```bash
# Check .env file
cat .env | grep DHAN_

# Validate format
python3 -c "from config import config; print(config.validate_dhan_credentials())"
```

### **Error Messages**

| Error | Solution |
|-------|----------|
| `AttributeError: 'QuantLabConfig'...` | Update imports: `from config import DATA_DIR` |
| `FileNotFoundError: Cache missing...` | Run: `python3 scripts/fetch_data.py SYMBOL` |
| `Invalid DHAN credentials` | Check `.env` file format and token validity |

---

## 📊 **Development Workflow**

### **Best Practices**
```bash
# 1. Validate system
python3 config.py

# 2. Fetch fresh data  
python3 scripts/fetch_data.py --force-refresh

# 3. Run backtesting
python3 -m runners.run_basket --basket_file data/basket.txt --strategy ema_cross

# 4. Clean cache periodically
python3 scripts/fetch_data.py --clean-cache
```

### **Code Integration**
```python
# Import system components
from config import config, DATA_DIR, CACHE_DIR
from data.loaders import load_many_india
from core.engine import backtest_strategy

# Use centralized paths
cache_file = config.get_cache_path("my_data.csv")
report_file = config.get_reports_path("results.csv")
```

---

## 🎯 **System Features**

### **Architecture Benefits**
- ✅ **Clean Organization**: Everything in logical folders
- ✅ **Centralized Config**: Single source of truth
- ✅ **Smart Caching**: Automatic management
- ✅ **Error Prevention**: Environment validation
- ✅ **Production Ready**: Robust error handling
- ✅ **Developer Friendly**: Clear APIs and docs

### **Data Quality**
- ✅ **Fresh Data**: 30-day cache ensures recent data
- ✅ **Fallback Sources**: Dhan → yfinance → cache
- ✅ **Metadata Tracking**: Source, timestamp, validation
- ✅ **Format Consistency**: Standardized CSV structure

### **Performance**
- ✅ **Rate Limiting**: API protection
- ✅ **Batch Processing**: Efficient multi-symbol handling
- ✅ **Cache First**: Fast data access
- ✅ **Parallel Safe**: Concurrent execution support

---

## 📝 **Version History**

| Version | Date | Changes |
|---------|------|---------|
| **2.0** | 2025-10-19 | 🆕 Clean architecture: config.py, docs/, scripts/ |
| 1.5 | 2025-10-19 | Unified fetch_data.py with Dhan+yfinance |
| 1.0 | 2025-10-18 | Initial separate scripts |

---

## 🏆 **Quick Commands Reference**

```bash
# System validation
python3 config.py

# Data fetching
python3 scripts/dhan_fetch_data.py

# Backtesting
python3 -m runners.run_basket --basket_file data/basket.txt --strategy ichimoku
```

---

**Need Help?** 
- Run `python3 config.py` to validate setup
- Check `scripts/` directory for available tools
- All documentation is in this `docs/` folder
- Use `--help` with any script for detailed usage