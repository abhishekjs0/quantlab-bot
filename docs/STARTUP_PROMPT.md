# QuantLab Repository Startup - AI Agent Initialization Prompt

**For AI Agents**: Use this prompt at the start of each development session to initialize the environment, understand the repository structure, and prepare for backtesting operations.

---

## 🚀 COMPREHENSIVE STARTUP INITIALIZATION PROMPT

### Objective
Execute a complete repository initialization cycle that sets up the Python environment, loads all documentation and learnings, verifies data availability, and prepares the system for backtesting operations.

---

## Phase 1: Environment Setup and Verification

### 1.1 Python Environment Configuration
```bash
# Verify Python version and location
/opt/homebrew/bin/python3.11 --version

# Configure Python environment for workspace
# This sets up the correct interpreter and installs dependencies
```

**Expected Output**: Python 3.11.x

### 1.2 Dependency Verification
```bash
# Check if key dependencies are installed
/opt/homebrew/bin/python3.11 -c "
import pandas as pd
import numpy as np
import plotly
import scipy
print('✅ All core dependencies available')
print(f'  pandas: {pd.__version__}')
print(f'  numpy: {np.__version__}')
print(f'  plotly: {plotly.__version__}')
"
```

**If dependencies are missing, install them:**
```bash
/opt/homebrew/bin/python3.11 -m pip install pandas numpy plotly scipy tabulate requests
```

---

## Phase 2: Repository Structure Understanding

### 2.1 Core Directory Structure
```
quantlab-workspace/
├── core/              # Backtesting engine (engine.py, strategy.py, optimizer.py)
├── strategies/        # Trading strategies (ichimoku.py is production)
├── runners/           # Execution orchestration (run_basket.py)
├── data/              # Market data and basket files
│   ├── cache/         # Cached historical data (dhan_historical_*.csv)
│   ├── basket_*.txt   # Symbol basket files
│   └── loaders.py     # Data loading utilities
├── viz/               # Dashboard visualization (dashboard.py)
├── utils/             # Technical indicators and analysis
├── tests/             # Test suite
├── scripts/           # Utility scripts (fetch_data.py, check_basket_data.py)
├── examples/          # Example implementations
├── reports/           # Backtest output directory (timestamped folders)
└── docs/              # Complete documentation suite
```

### 2.2 Critical Files to Know
- **config.py**: System configuration (data directories, API settings)
- **runners/run_basket.py**: Main backtesting orchestrator (3443 lines, recently optimized)
- **viz/dashboard.py**: Dashboard generator (2384 lines, recently optimized)
- **strategies/ichimoku.py**: Production strategy with global market regime filters
- **data/loaders.py**: Data loading and caching logic
- **OPTIMIZATION_NOTES.md**: Recent performance optimizations (15-25% faster)

---

## Phase 3: Documentation Reading (Critical Knowledge)

### 3.1 Primary Documentation to Read
Execute these reads to understand the system:

1. **Complete Workflow Guide** (docs/WORKFLOW_GUIDE.md)
   - End-to-end workflow from setup to analysis
   - Basket management procedures
   - Data fetching and caching
   - Backtest execution patterns

2. **Optimization Notes** (OPTIMIZATION_NOTES.md)
   - Recent performance improvements
   - Vectorization patterns used
   - Dashboard fixes applied
   - Code quality standards

3. **Coding Standards** (docs/CODING_STANDARDS.md)
   - Python best practices
   - Vectorization requirements
   - Testing standards

4. **Walk Forward Guide** (docs/WALK_FORWARD_GUIDE.md)
   - Multi-period analysis
   - Window definitions (1Y, 3Y, 5Y)
   - Performance metrics

### 3.2 Key Learnings from Documentation

**Backtesting Command Pattern:**
```bash
# Standard basket backtest
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_test.txt \
  --strategy strategies.ichimoku \
  --windows 1Y,3Y,5Y

# Single window backtest
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket data/basket_test.txt \
  --output-dir reports \
  --windows 1Y
```

**Dashboard Generation Pattern:**
```bash
# Generate dashboard from report directory
/opt/homebrew/bin/python3.11 -m viz.dashboard <report-folder-name>

# Example:
/opt/homebrew/bin/python3.11 -m viz.dashboard 1103-2040-ichimoku-basket-test
```

**Data Fetching Pattern:**
```bash
# Fetch data for basket symbols
/opt/homebrew/bin/python3.11 scripts/fetch_data.py --basket data/basket_test.txt
```

---

## Phase 4: Data Verification

### 4.1 Check Available Baskets
```bash
# List all basket files
ls -lh data/basket_*.txt

# Expected baskets:
# - basket_test.txt (3 symbols - for testing)
# - basket_small.txt (small cap)
# - basket_mid.txt (mid cap)
# - basket_large.txt (large cap)
# - basket_mega.txt (mega cap)
# - basket_default.txt (default selection)
```

### 4.2 Verify Symbol Master Data
```bash
# Check symbol master file exists
ls -lh data/api-scrip-master-detailed.csv

# Count symbols available
wc -l data/api-scrip-master-detailed.csv
```

### 4.3 Check Cache Status
```bash
# Count cached symbols
ls data/cache/dhan_historical_*.csv 2>/dev/null | wc -l

# Check cache metadata
ls data/cache/*.json | head -5
```

### 4.4 Verify Cache Utility Script
```bash
# Check basket data availability
/opt/homebrew/bin/python3.11 scripts/check_basket_data.py data/basket_test.txt
```

**Expected Output:**
```
✅ Symbol available: <SYMBOL_NAME>
📊 Data points: 1000+
📅 Date range: YYYY-MM-DD to YYYY-MM-DD
```

---

## Phase 5: Recent Optimization Learnings

### 5.1 Performance Optimizations Applied
Read from OPTIMIZATION_NOTES.md:

**run_basket.py (15-25% faster):**
- ✅ Trade matching: O(n²) → O(n log n) with pandas merge()
- ✅ Trade events: Vectorized with list(zip())
- ✅ Formatting: 7 .apply() calls replaced with vectorized operations

**dashboard.py (10-20% faster):**
- ✅ Eliminated 2 iterrows() loops
- ✅ Replaced .apply() with np.where()
- ✅ Added 3 helper methods for code reuse

**Dashboard Fix:**
- ✅ Combined period×metric dropdown (can now access "IRR % - 1Y", "Profit Factor - 3Y", etc.)

### 5.2 Code Quality Standards
**Always follow these patterns:**
- ❌ Never use `.iterrows()` - use vectorized operations
- ❌ Avoid `.apply(lambda ...)` - use np.where() or direct operations
- ✅ Use pandas merge() for matching operations
- ✅ Use list(zip()) for parallel iteration
- ✅ Use pd.to_numeric(), pd.to_datetime() with fillna()
- ✅ Add helper functions to reduce duplication

---

## Phase 6: System Health Check

### 6.1 Run Smoke Test
```bash
# Quick validation that system works
/opt/homebrew/bin/python3.11 -c "
import sys
sys.path.insert(0, '/Users/abhishekshah/Desktop/quantlab-workspace')
from core.engine import Backtest
from data.loaders import load_data
print('✅ Core modules import successfully')
"
```

### 6.2 Verify Test Suite
```bash
# Run minimal smoke test (optional - only if requested)
# /opt/homebrew/bin/python3.11 -m pytest tests/test_smoke.py -v
```

---

## Phase 7: Understanding Report Structure

### 7.1 Report Directory Format
Reports are saved in: `reports/<MMDD-HHMM>-<strategy>-<basket>/`

**Example:** `reports/1103-2040-ichimoku-basket-test/`

### 7.2 Report Files Generated
```
<report-dir>/
├── portfolio_summary_<window>.csv         # Key metrics by period
├── portfolio_trades_<window>.csv          # All trades
├── portfolio_monthly_equity_curve_<window>.csv  # Monthly equity
├── portfolio_daily_equity_curve_<window>.csv    # Daily equity  
├── portfolio_trade_volume_<window>.csv    # Volume analysis
├── portfolio_trade_duration_<window>.csv  # Duration analysis
├── portfolio_metrics_<window>.csv         # Detailed metrics
├── portfolio_top_trades_<window>.csv      # Best/worst trades
├── symbol_results_<window>.csv            # Per-symbol results
└── quantlab_dashboard.html                # Interactive dashboard
```

### 7.3 Key Metrics in Reports
**From portfolio_summary_<window>.csv:**
- Net P&L %
- CAGR [%]
- Max Drawdown [%]
- Profit Factor
- Win Rate [%]
- Sharpe Ratio
- Sortino Ratio
- IRR %
- Total Trades

---

## Phase 8: Common Operations Checklist

### 8.1 Before Running Backtests
- [ ] Verify basket file exists in `data/`
- [ ] Check cache availability with `check_basket_data.py`
- [ ] Fetch missing data with `fetch_data.py` if needed
- [ ] Set PYTHONPATH correctly
- [ ] Use absolute path to Python 3.11

### 8.2 After Running Backtests
- [ ] Check reports directory for timestamped folder
- [ ] Verify all CSV files generated (summary, trades, equity curves)
- [ ] Generate dashboard with `viz.dashboard`
- [ ] Review key metrics in summary files

### 8.3 Dashboard Operations
- [ ] Dashboard requires completed backtest report
- [ ] Use report folder name (without path)
- [ ] Check for "quantlab_dashboard.html" in report folder
- [ ] Test dropdown functionality (period×metric combinations)

---

## Phase 9: Troubleshooting Quick Reference

### 9.1 Common Issues and Solutions

**Issue: "Module not found" errors**
```bash
# Solution: Set PYTHONPATH
export PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace
```

**Issue: "No data available for symbol"**
```bash
# Solution: Fetch data first
/opt/homebrew/bin/python3.11 scripts/fetch_data.py --basket data/basket_file.txt
```

**Issue: "Empty DataFrame" in results**
```bash
# Solution: Check basket data availability
/opt/homebrew/bin/python3.11 scripts/check_basket_data.py data/basket_file.txt
```

**Issue: Dashboard generation fails**
```bash
# Solution: Verify report structure
ls -lh reports/<report-folder>/portfolio_*.csv
# All required CSVs must exist
```

---

## Phase 10: AI Agent Operational Guidelines

### 10.1 Code Modification Guidelines
When modifying code:
1. **Always** read surrounding context (50+ lines before/after)
2. **Never** use iterrows() or row-by-row operations
3. **Always** use vectorized pandas/numpy operations
4. **Test** changes with basket_test.txt before larger baskets
5. **Document** significant changes in OPTIMIZATION_NOTES.md

### 10.2 Backtest Execution Guidelines
1. **Start small**: Always test with basket_test.txt first
2. **Single window**: Test with `--windows 1Y` before multi-window
3. **Monitor output**: Check for errors during execution
4. **Verify results**: Check CSV files and dashboard generation

### 10.3 Performance Optimization Guidelines
1. **Profile first**: Use grep to find iterrows(), .apply() patterns
2. **Vectorize**: Replace with merge(), list(zip()), np.where()
3. **Test impact**: Measure before/after with basket_test.txt
4. **Document**: Add entries to OPTIMIZATION_NOTES.md

### 10.4 Dashboard Usage Guidelines
1. **Combined dropdown**: Use period×metric format ("IRR % - 1Y")
2. **All periods available**: 1Y, 3Y, 5Y
3. **All metrics accessible**: Net P&L %, CAGR, Profit Factor, IRR %, etc.
4. **Report folder**: Use exact folder name from reports/ directory

---

## Phase 11: Quick Command Reference

### Most Common Commands

**1. Test backtest (3 symbols, 1 year):**
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket data/basket_test.txt --windows 1Y
```

**2. Production backtest (all windows):**
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_large.txt \
  --strategy strategies.ichimoku \
  --windows 1Y,3Y,5Y
```

**3. Generate dashboard:**
```bash
/opt/homebrew/bin/python3.11 -m viz.dashboard <report-folder>
```

**4. Check data availability:**
```bash
/opt/homebrew/bin/python3.11 scripts/check_basket_data.py data/basket_test.txt
```

**5. Fetch missing data:**
```bash
/opt/homebrew/bin/python3.11 scripts/fetch_data.py --basket data/basket_test.txt
```

---

## ✅ STARTUP INITIALIZATION CHECKLIST

Execute this checklist at the start of every session:

- [ ] **Phase 1**: Verify Python 3.11 environment
- [ ] **Phase 2**: Understand repository structure
- [ ] **Phase 3**: Read critical documentation (WORKFLOW_GUIDE.md, OPTIMIZATION_NOTES.md)
- [ ] **Phase 4**: Verify data availability (baskets, cache, symbol master)
- [ ] **Phase 5**: Review recent optimizations and coding standards
- [ ] **Phase 6**: Run system health check (imports, smoke test)
- [ ] **Phase 7**: Understand report structure and metrics
- [ ] **Phase 8**: Review common operations checklist
- [ ] **Phase 9**: Familiarize with troubleshooting guide
- [ ] **Phase 10**: Acknowledge AI agent operational guidelines
- [ ] **Phase 11**: Bookmark quick command reference

---

## 🎯 Session Goals Template

At session start, establish:

1. **Primary Objective**: [What is the main goal?]
   - Example: "Run backtest on large cap basket"
   - Example: "Optimize performance of equity curve generation"
   - Example: "Debug dashboard metric accessibility"

2. **Required Resources**: [What do we need?]
   - Basket files available
   - Data cached or needs fetching
   - Documentation to reference

3. **Success Criteria**: [How do we know we succeeded?]
   - Backtest completes without errors
   - Dashboard generates successfully
   - Performance improves by X%
   - All tests pass

4. **Risk Assessment**: [What could go wrong?]
   - Missing data for symbols
   - Memory issues with large baskets
   - API rate limits
   - Code changes breaking existing functionality

---

## 📚 Essential Documentation References

Always have these available:

1. **docs/WORKFLOW_GUIDE.md** - Complete end-to-end workflow
2. **docs/QUANTLAB_GUIDE.md** - System architecture
3. **docs/WALK_FORWARD_GUIDE.md** - Multi-period analysis
4. **docs/CODING_STANDARDS.md** - Development best practices
5. **OPTIMIZATION_NOTES.md** - Recent performance improvements
6. **README.md** - Quick start guide

---

## 🚀 Ready State Confirmation

After completing this startup sequence, confirm:

✅ **Environment**: Python 3.11 configured, dependencies verified  
✅ **Knowledge**: Documentation read, system understood  
✅ **Data**: Baskets verified, cache checked  
✅ **Health**: Imports working, system functional  
✅ **Standards**: Coding guidelines acknowledged  
✅ **Commands**: Reference bookmarked  

**Agent Status**: READY FOR OPERATIONS ✅

---

## 💡 Pro Tips for AI Agents

1. **Always test with basket_test.txt first** - 3 symbols run in ~8 seconds
2. **Use grep to explore code** - Faster than reading entire files
3. **Check existing reports** - Learn from successful runs
4. **Read OPTIMIZATION_NOTES.md** - Understand recent changes
5. **Follow vectorization patterns** - Never use iterrows() or row-by-row apply()
6. **Monitor terminal output** - Catch errors early
7. **Verify CSVs after backtest** - Ensure data quality
8. **Test dashboard immediately** - Catch visualization issues
9. **Document significant changes** - Update OPTIMIZATION_NOTES.md
10. **Use absolute paths** - Avoid working directory issues

---

**End of Startup Prompt** - Agent is now fully initialized and ready for QuantLab operations! 🎉
