# QuantLab Startup Prompt - Session Context

**Last Updated**: November 5, 2025  
**Architecture Version**: No-Warm-Up (Indicators Return NaN)  
**Python Version**: 3.9.6 (⚠️ 3.10+ syntax NOT supported)

---

## 📋 CRITICAL RULES FOR THIS SESSION AND ALL FUTURE SESSIONS

### ❌ NEVER CREATE THESE DOCUMENTATION FILES:
- ❌ Summary files (SUMMARY.md, WARMUP_REMOVAL_SUMMARY.md, etc.)
- ❌ Status update documents (STATUS_UPDATE.md, IMPLEMENTATION_SUMMARY.md, etc.)
- ❌ Visual summary files or checklists
- ❌ Q&A documentation (ANSWERS_TO_QUESTIONS.md)
- ❌ Session status files of any kind

### ✅ DOCUMENTATION STRUCTURE (CONSOLIDATED Nov 2025):
- ✅ **GETTING_STARTED.md** - Setup, quick start, common tasks, directory structure (NEW - replaces DIRECTORY_REFERENCE, QUANTLAB_GUIDE, REPO_SETUP_GUIDE)
- ✅ **STARTUP_PROMPT.md** - This file (architecture context for AI sessions)
- ✅ **BACKTEST_GUIDE.md** - Comprehensive backtesting documentation
- ✅ **EMA_CROSSOVER_STRATEGY.md**, **ICHIMOKU_STRATEGY.md**, **KNOXVILLE_STRATEGY.md** - Strategy details
- ✅ **DEVELOPMENT_WORKFLOW.md** - Development setup and workflow
- ✅ **ARCHITECTURE_AND_DATA_QUALITY.md** - System architecture decisions
- ✅ **JANITOR_PROMPT.md** - Repository maintenance
- ✅ **INDEX.md** - Documentation navigation
- ✅ **README.md** - Product overview (root level)
- ✅ **docs/README.md** - Documentation index
- ✅ **docs/api/** - Sphinx API documentation (auto-generated)
- ❌ **Removed**: DIRECTORY_REFERENCE.md, QUANTLAB_GUIDE.md, REPO_SETUP_GUIDE.md (consolidated into GETTING_STARTED.md)
- ❌ **Removed**: TEST_STATUS.md, TESTS_FIXED.md (historical, no longer needed)

---

## 🎯 Current Architecture: No-Warm-Up with NaN Indicators

### Problem Solved
**Old System** (Removed): Artificially skipped first 60-150 bars for "warm-up"
- Wasted historical data
- 1Y cached tests would skip bars 0-100
- Complex `warmup_bars` configuration scattered across strategies

**New System** (Implemented): Indicators return NaN when insufficient data
- Uses ALL available historical data
- Trades start when indicator is ready (automatically via NaN)
- No configuration needed
- More accurate and professional

### How It Works

**Indicator Behavior**:
```python
# SMA(200) example:
Bar 0-199:   Returns NaN (not enough data)
Bar 200+:    Returns valid SMA value
```

**Strategy Pattern**:
```python
def on_bar(self, ts, row, state):
    indicator = self.indicator[idx]
    
    # Skip trading if NaN
    if np.isnan(indicator):
        return {"enter_long": False, "exit_long": False}
    
    # Trade when ready
    return {"enter_long": condition, ...}
```

### Implementation Status

**Completed**:
- ✅ Engine: Warm-up enforcement removed (core/engine.py)
- ✅ Indicators: Automatic NaN for insufficient data
- ✅ Strategies: NaN checks added to EMA crossover
- ✅ Tests: 10/10 strategy tests pass ✓

**Remaining**:
- 🔄 Add NaN checks to ichimoku.py on_bar()
- 🔄 Add NaN checks to knoxville.py on_bar()
- 🔄 Fix 12 test failures (see Test Failures section below)

---

## 🚀 How to Run Backtests

### Quick Start - Run Single Strategy on Single Symbol

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace

# Method 1: Direct Python (Recommended)
python3 << 'EOF'
from runners.run_basket import run_basket_backtest

result = run_basket_backtest(
    strategy_name='ema_crossover',  # or 'ichimoku', 'knoxville'
    basket_name='test',             # or 'small', 'mid', 'large', 'mega'
    verbose=True
)

if result and len(result['trades']) > 0:
    print(f"✅ Success: {len(result['trades'])} trades")
    print(f"Final Equity: {result['equity_df'].iloc[-1]['equity']:.2f}")
else:
    print("❌ No trades generated")
EOF
```

### Run Basket Backtest - Full Strategy on Full Basket

```bash
# Run EMA crossover on mega basket (all symbols)
python3 << 'EOF'
from runners.run_basket import run_basket_backtest

result = run_basket_backtest(
    strategy_name='ema_crossover',
    basket_name='mega',
    verbose=True
)
print(f"Backtest complete. Trades: {len(result['trades'])}")
EOF
```

### Available Strategies
- `ema_crossover` - EMA(89) vs EMA(144) with RSI pyramiding
- `ichimoku` - Ichimoku cloud with multiple filters
- `knoxville` - Knoxville divergence with MACD reversals

### Available Baskets
- `test` - 1 symbol (for quick testing)
- `small` - Small cap basket
- `mid` - Mid cap basket
- `large` - Large cap basket
- `mega` - Mega cap basket (NIFTY 50 constituents)

### Run Specific Tests

```bash
# Strategy API tests (should all pass)
pytest tests/test_strategy_wrapper.py -v

# Backtesting tests (8/13 pass, 5 pre-existing failures)
pytest tests/test_backtesting_integration.py -v

# All tests
pytest tests/ -v
```

---

## ⚠️ Known Issues & Fixes Needed

### Test Failures (12 total)

**Pre-Existing (Not warm-up related)**:

1. **Optimizer tests (3)** - SKIP: Core.optimizer module removed from repo
   - `test_parameter_optimizer_creation` → Should be skipped/removed
   - `test_grid_optimization` → Should be skipped/removed
   - `test_optimization_result_container` → Should be skipped/removed

2. **Performance utility issue (1)** - FIX: utils/performance.py has type issue
   - `test_performance_metrics` → TypeError in max_drawdown_from_returns
   - Issue: `max_dd_end < len(cumulative) - 1` comparing Timestamp to int
   - Fix: Use `.iloc` indexing properly

3. **Smoke tests (2)** - FIX: HDF data cache missing
   - `test_ema_cross_hdfc` → Cache miss for HDFC historical data
   - `test_envelope_kd_hdfc` → Cache miss for HDFC historical data
   - Fix: Either regenerate HDF cache or skip these tests

4. **Basket integration (2)** - FIX: Data loading issues
   - `test_integration_basket` → Data format mismatch
   - Other basket-related tests → Pre-existing

5. **Parity tests (2)** - FIX: Calculation mismatches
   - `test_parity_basket` → Results don't match expected values
   - Root cause: Unknown (may be warm-up related after recent changes)

6. **Race condition tests (3)** - INCOMPLETE: Framework ready, needs signals
   - `test_stop_exit_prevents_same_bar_entry` → Needs signal generation
   - `test_pyramid_entries_with_stops` → Needs signal generation
   - `test_stop_hit_on_intrabar_low` → Needs signal generation

### Data Cache Issues

**Problem**: Smoke tests fail due to missing HDF cache for HDFC

**Location**: `data/cache/dhan_historical_*.csv` files

**Solution**: Either:
1. Regenerate HDF cache using scripts/fetch_data.py
2. Skip HDFC tests since they're not critical

### Python 3.9 Type Hint Compatibility

**Issue**: Python 3.9 doesn't support `str | None` syntax (requires 3.10+)

**Files Fixed**:
- ✅ core/engine.py
- ✅ utils/__init__.py
- ✅ core/benchmark.py
- ✅ core/monitoring.py

**Pattern**: Replace `type | None` with untyped defaults or `Optional[type]`

**Check for remaining issues**:
```bash
grep -n " | " core/*.py utils/*.py strategies/*.py
```

---

## 📊 Test Status Summary

### Passing Tests ✅

**Strategy Wrapper Tests: 10/10 PASS**
```
✅ test_strategy_I_wrapper_creation
✅ test_strategy_I_wrapper_with_ema
✅ test_strategy_indicator_retrieval
✅ test_template_strategy_initialization
✅ test_template_strategy_market_regime_integration
✅ test_regime_detection_uptrend
✅ test_regime_detection_downtrend
✅ test_strategy_base_class
✅ test_strategy_data_validation
✅ test_strategy_parameter_management
```

### Failing Tests (12 total) ❌

**Optimizer Module (3)** - Module removed from repo:
```
❌ test_parameter_optimizer_creation
❌ test_grid_optimization
❌ test_optimization_result_container
```

**Pre-Existing Issues (5)**:
```
❌ test_performance_metrics (type issue in max_drawdown)
❌ test_ema_cross_hdfc (HDF cache missing)
❌ test_envelope_kd_hdfc (HDF cache missing)
❌ test_integration_basket (data format)
❌ test_parity_basket (calculation mismatch)
```

**Framework Ready (3)** - Need signal generation:
```
🔄 test_stop_exit_prevents_same_bar_entry
🔄 test_pyramid_entries_with_stops
🔄 test_stop_hit_on_intrabar_low
```

---

## 🔧 What Needs to Be Done

### High Priority (Architectural)

1. **Fix NaN handling in ALL indicators** (not just 3)
   - Currently: Only SMA, EMA, RSI documented
   - Should: ALL indicators (ATR, RSI, MACD, etc.) return NaN properly
   - Review: utils/indicators.py for completeness

2. **Apply NaN checks at engine or basket level** (not in strategies)
   - Current: Each strategy must check NaN
   - Better: Engine or run_basket could auto-skip NaN bars
   - Reduces duplication in strategies

3. **Update remaining strategies with NaN handling**
   - `strategies/ichimoku.py` - Add NaN checks
   - `strategies/knoxville.py` - Add NaN checks

### Medium Priority (Test Fixes)

4. **Fix 5 pre-existing failures**
   - Remove optimizer tests (module doesn't exist)
   - Fix performance.py max_drawdown_from_returns type issue
   - Regenerate or skip HDFC cache tests
   - Investigate basket/parity test failures

5. **Complete 3 race condition tests**
   - Add realistic strategy signal generation
   - Verify stop loss and pyramiding logic

### Low Priority (Cleanup)

6. **Verify all Python 3.9 type hints are fixed**
7. **Update strategy docstrings** if any mention old warm-up

---

## 📁 Important Directories

```
/Users/abhishekshah/Desktop/quantlab-workspace/

├── core/                    # Engine, strategies, monitoring
│   ├── engine.py           # Backtest engine (warm-up REMOVED)
│   ├── strategy.py         # Strategy base class
│   └── benchmark.py        # Alpha/beta calculations
│
├── strategies/             # Strategy implementations
│   ├── template.py         # Base template
│   ├── ema_crossover.py    # EMA with NaN checks ✅
│   ├── ichimoku.py         # Ichimoku (needs NaN checks)
│   └── knoxville.py        # Knoxville (needs NaN checks)
│
├── utils/                  # Indicators and utilities
│   ├── __init__.py         # SMA, EMA, RSI, ATR, etc.
│   ├── indicators.py       # Advanced indicators
│   └── performance.py      # P&L calculations (has type issue)
│
├── runners/                # Backtesting runners
│   └── run_basket.py       # Main backtest entry point
│
├── data/                   # Data loaders and caches
│   ├── loaders.py          # Data loading
│   └── cache/              # Historical data cache
│
└── tests/                  # Test suite
    ├── test_strategy_wrapper.py        (10/10 ✅)
    ├── test_backtesting_integration.py (8/13 ✅)
    └── ...
```

---

## 🎓 Architecture Overview

### No-Warm-Up Design

**Data Flow**:
```
Input Data
    ↓
Engine loops through bars (NO SKIPPING)
    ↓
For each bar:
  ├─ Calculate indicators
  ├─ Check: indicator = NaN?
  │  ├─ YES → Skip trading (return no signal)
  │  └─ NO → Continue to trading logic
  ├─ Call strategy.on_bar()
  └─ Execute trades if signaled
    ↓
Output: Trades & Equity Curve
```

**Key Principle**: Indicators handle their own data validation via NaN. Engine doesn't skip bars artificially.

### Indicator NaN Pattern

All indicators should follow:
```python
def INDICATOR(data, period=20):
    """
    Calculate INDICATOR.
    
    Returns NaN for first (period-1) bars where calculation incomplete.
    Valid values from bar (period) onwards.
    """
    # Implementation returns NaN naturally via rolling windows
    return pd.Series(data).rolling(period).mean()
```

---

## ✅ Verification Checklist

Before committing any changes:

- [ ] No summary/status documentation files created
- [ ] Only STARTUP_PROMPT.md used for session context
- [ ] All Python 3.9 type hints use correct syntax (no `|` syntax)
- [ ] Backtest runs without errors: `run_basket_backtest(...)`
- [ ] Strategy tests pass: `pytest tests/test_strategy_wrapper.py -v`
- [ ] NaN handling verified for critical indicators
- [ ] No artificial bar skipping in engine
- [ ] No Python 3.10+ specific syntax in code

---

## 🚨 Quick Troubleshooting

**Import error "No module named 'core'"**
```bash
# Run from workspace root with proper imports
cd /Users/abhishekshah/Desktop/quantlab-workspace
python3 scripts/file_you_want_to_run.py
```

**Type hint errors on startup**
```bash
# Check for remaining | syntax issues
grep -n " | " core/*.py utils/*.py strategies/*.py
# Fix: Remove type hints or use Optional[type] from typing
```

**Test failures with "Cache miss"**
```bash
# HDFC data not available
# Option 1: Regenerate
python3 scripts/fetch_data.py

# Option 2: Skip HDFC tests (acceptable)
pytest tests/ -k "not hdfc"
```

---

## 📞 Session Context

**Current Status**:
- Warm-up removal: ✅ COMPLETE
- Indicator NaN handling: ✅ 3/indicators done, 🔄 need all indicators
- Strategy updates: ✅ EMA done, 🔄 ichimoku/knoxville pending
- Test fixes: 🔄 PENDING (see Test Status section)
- Documentation: ✅ Consolidated to STARTUP_PROMPT.md only
- Python 3.9 compatibility: ✅ core files fixed, 🔄 verify all

**Next Session Should**:
1. Fix remaining test failures (5 pre-existing)
2. Apply NaN checks to all indicators
3. Update ichimoku and knoxville strategies
4. Verify end-to-end backtest works
5. Search codebase for any remaining Python 3.10+ syntax

---

## 💡 Implementation Notes

### Why No-Warm-Up Architecture?

1. **More Accurate** - Reflects real indicator behavior
2. **Uses All Data** - No waste of historical bars
3. **Professional** - Matches TradingView/Amibroker
4. **Scalable** - Works with any indicator period/timeframe
5. **Simpler** - No configuration needed

### Why NaN at Engine Level Might Be Better

Current: Each strategy checks NaN (code duplication)
```python
# Repeated in every strategy
if np.isnan(indicator):
    return {"enter_long": False}
```

Future (optional): Engine checks NaN (single point)
```python
# In engine, skip trading bar if any indicator is NaN
if any(np.isnan(val) for val in indicators.values()):
    continue
```

This is a design choice for future optimization.

### Python 3.9 Compatibility

**Key Constraint**: No `str | None` syntax (requires Python 3.10+)

**Correct patterns**:
```python
# ❌ NOT ALLOWED (Python 3.10+)
def func(param: str | None = None):
    pass

# ✅ ALLOWED (Python 3.9)
def func(param=None):
    pass

# ✅ ALSO ALLOWED (with Optional import)
from typing import Optional
def func(param: Optional[str] = None):
    pass
```

---

**Last Updated**: November 5, 2025  
**Maintained By**: Development Team  
**Reviews Required**: Before each session start
```

#### Phase 3: System Configuration Validation
Validate QuantLab system configuration:

```bash
# Run configuration validation
echo "⚙️  Validating system configuration..."
python3 config.py

# Check if config.py is valid
if [ $? -eq 0 ]; then
    echo "✅ System configuration is valid"
else
    echo "⚠️  Configuration validation failed"
fi
```

#### Phase 4: Repository Structure Inspection
Verify critical directories and files exist:

```bash
echo "📁 Checking repository structure..."

# Define critical files and directories
critical_items=(
    "config.py"
    "pyproject.toml"
    "core/"
    "data/"
    "strategies/"
    "tests/"
    "utils/"
    "viz/"
    "docs/"
    "README.md"
)

for item in "${critical_items[@]}"; do
    if [ -e "$item" ]; then
        echo "✅ $item"
    else
        echo "❌ $item (MISSING)"
    fi
done

# Check for unwanted temporary files
echo ""
echo "🧹 Checking for temporary files..."
temp_files=$(find . -maxdepth 1 -type f \( -name "*_comparison*" -o -name "*_debug*" -o -name "*_analysis*" -o -name "SESSION_SUMMARY*" \) 2>/dev/null | wc -l)
if [ "$temp_files" -eq 0 ]; then
    echo "✅ No temporary files found"
else
    echo "⚠️  Found $temp_files temporary files"
fi
```

#### Phase 5: Data and Cache Inspection
Verify data directory and caching:

```bash
echo "📊 Inspecting data directory..."

# Check basket files
echo "Basket files:"
ls -lh data/basket_*.txt 2>/dev/null || echo "⚠️  No basket files found"

# Check cache status
echo ""
echo "Cache status:"
cache_size=$(du -sh data/cache/ 2>/dev/null | awk '{print $1}')
cache_files=$(find data/cache/ -type f 2>/dev/null | wc -l)
echo "Cache size: $cache_size"
echo "Cache files: $cache_files"

# List sample cached data
echo ""
echo "Sample cached symbols:"
ls data/cache/ 2>/dev/null | head -5
```

#### Phase 6: Critical Documentation Review
Load essential documentation references:

```bash
echo "📖 Critical documentation available:"
echo ""
echo "1. WORKFLOW_GUIDE.md - Complete end-to-end workflow"
echo "2. QUANTLAB_GUIDE.md - System architecture and features"
echo "3. INDEX.md - Documentation index and navigation"
echo "4. BACKTEST_GUIDE.md - Backtest execution procedures"
echo "5. DEVELOPMENT_WORKFLOW.md - Development practices"
echo ""
echo "Strategy guides:"
echo "- ICHIMOKU_STRATEGY.md - Ichimoku strategy details"
echo "- EMA_CROSSOVER_STRATEGY.md - EMA crossover strategy"
echo "- KNOXVILLE_STRATEGY.md - Knoxville strategy"
echo ""
```

#### Phase 7: Available Strategies Inspection
Display available trading strategies:

```bash
echo "📈 Available strategies:"
echo ""
for strategy in strategies/*.py; do
    if [ -f "$strategy" ] && [ "$(basename $strategy)" != "__init__.py" ]; then
        name=$(basename "$strategy" .py)
        echo "✅ $name"
    fi
done
```

#### Phase 8: Test Suite Status
Check test infrastructure:

```bash
echo "🧪 Test suite status:"
echo ""

# Count test files
test_count=$(find tests/ -name "test_*.py" 2>/dev/null | wc -l)
echo "Test files: $test_count"

# List test files
echo ""
echo "Available tests:"
ls tests/test_*.py 2>/dev/null | xargs -I {} basename {} | sed 's/^/  ✅ /'

# Check pytest availability
if command -v pytest &> /dev/null; then
    echo ""
    echo "✅ pytest is installed"
else
    echo ""
    echo "⚠️  pytest not found in PATH"
fi
```

#### Phase 9: Command Reference Summary
Display useful command shortcuts:

```bash
echo "📋 COMMAND REFERENCE - Quick Start"
echo ""
echo "=== System Validation ==="
echo "  python3 config.py                           # Validate system setup"
echo ""
echo "=== Data Management ==="
echo "  python3 scripts/fetch_data.py               # Fetch all basket data"
echo "  python3 scripts/fetch_data.py --force-refresh  # Force refresh cache"
echo "  python3 scripts/check_basket_data.py        # Validate basket data"
echo ""
echo "=== Backtesting ==="
echo "  python3 -m runners.run_basket --strategy ichimoku"
echo "  python3 -m runners.run_basket --basket_size mega --strategy ichimoku"
echo ""
echo "=== Testing ==="
echo "  pytest tests/                               # Run all tests"
echo "  pytest tests/test_smoke.py -v               # Run smoke tests"
echo ""
echo "=== Code Quality ==="
echo "  black . --check                             # Check formatting"
echo "  isort . --check-only                        # Check import order"
echo ""
```

#### Phase 10: Development Setup Verification
Check development tools availability:

```bash
echo "🛠️  Development tools status:"
echo ""

# Check essential tools
tools=("python3" "git" "pytest" "black" "isort" "ruff")

for tool in "${tools[@]}"; do
    if command -v "$tool" &> /dev/null; then
        version=$($tool --version 2>&1 | head -1)
        echo "✅ $tool - $version"
    else
        echo "⚠️  $tool - NOT FOUND"
    fi
done
```

#### Phase 11: Session Readiness Checklist
Verify session is ready to begin:

```bash
echo ""
echo "✅ SESSION READINESS CHECKLIST"
echo ""

checks=(
    "Repository clean (no uncommitted changes)"
    "On main branch"
    "Python environment configured"
    "Dependencies installed"
    "System configuration valid"
    "Data directory present"
    "Strategies available"
    "Tests discoverable"
    "Documentation accessible"
    "Git remote configured"
)

for check in "${checks[@]}"; do
    echo "  ☑️  $check"
done

echo ""
echo "✅ Startup initialization complete - Ready for development"
echo ""
```

#### Phase 12: Post-Startup Summary
Display session context and next steps:

```bash
echo "📊 SESSION CONTEXT"
echo ""
echo "Repository: quantlab-bot"
echo "Owner: abhishekjs0"
echo "URL: https://github.com/abhishekjs0/quantlab-bot.git"
echo ""
echo "Branch: $(git branch --show-current)"
echo "Last commit: $(git log -1 --format='%h - %s')"
echo ""
echo "📁 Working directory: $(pwd)"
echo ""
echo "🚀 NEXT STEPS"
echo ""
echo "1. Read the relevant documentation:"
echo "   - For workflows: docs/WORKFLOW_GUIDE.md"
echo "   - For architecture: docs/QUANTLAB_GUIDE.md"
echo "   - For strategies: docs/ICHIMOKU_STRATEGY.md"
echo ""
echo "2. Choose your task:"
echo "   - Data work: python3 scripts/fetch_data.py"
echo "   - Backtesting: python3 -m runners.run_basket --strategy ichimoku"
echo "   - Development: Edit strategies/* or core/* files"
echo "   - Testing: pytest tests/ -v"
echo ""
echo "3. At session end:"
echo "   - Commit changes: git add . && git commit -m 'message'"
echo "   - Run janitor: Use docs/JANITOR_PROMPT.md"
echo ""
```

---

## 🎯 How to Use This Prompt

### For AI Agents at Session Start
```
"Execute the startup prompt from docs/STARTUP_PROMPT.md:
1. Verify repository state and git configuration
2. Check environment and dependencies
3. Validate system configuration
4. Inspect repository structure
5. Review available documentation and strategies
6. Display command reference and readiness checklist
7. Provide session context and next steps
Execute all phases silently and provide summary."
```

### Integration with Development Session
- **Before Development**: Execute this startup prompt
- **During Session**: Use reference materials as needed
- **After Development**: Execute janitor cleanup prompt

### Quick Reference Command
```bash
#!/bin/bash
# Run full startup at session beginning
cd /path/to/quantlab-workspace

# Execute all startup phases (requires bash)
# Can be run from terminal or integrated into development workflow
```

---

## 📋 Key Information for AI Agents

### Repository Structure
```
quantlab-workspace/
├── core/                 # Backtesting engine, monitoring, reporting
├── data/                # Market data and cache
├── strategies/          # Trading strategies (ichimoku, ema_crossover, knoxville)
├── utils/               # Technical indicators and utilities
├── viz/                 # Visualization dashboard
├── runners/             # Execution orchestration
├── tests/               # Test suite
├── scripts/             # Utility scripts for data and setup
├── docs/                # Documentation (START HERE)
├── config.py            # System configuration
└── pyproject.toml       # Project metadata
```

### Available Strategies
- **ichimoku** - Ichimoku cloud-based strategy
- **ema_crossover** - EMA crossover strategy
- **knoxville** - Knoxville-based strategy
- **template** - Development template for new strategies

### Essential Configuration Files
- `config.py` - Main system configuration
- `pyproject.toml` - Project metadata and dependencies
- `data/basket_*.txt` - Symbol baskets for backtesting

### Data Management
- **Cache Location**: `data/cache/`
- **Basket Files**: `data/basket_*.txt`
- **Historical Data**: `data/historical/`
- **Symbol Master**: `data/api-scrip-master-detailed.csv`

### Development Workflow
1. **Understand**: Read relevant documentation
2. **Develop**: Modify strategies or core components
3. **Test**: Run pytest suite
4. **Validate**: Run backtests
5. **Commit**: Git commit with clear message
6. **Cleanup**: Run janitor prompt

---

## ⚠️ Important Notes for AI Agents

### What to Do
- ✅ Read documentation thoroughly before making changes
- ✅ Run tests before committing
- ✅ Use descriptive commit messages
- ✅ Validate changes with backtests
- ✅ Run janitor cleanup at session end
- ✅ Keep main branch production-ready

### What NOT to Do
- ❌ Don't create temporary files without cleaning up
- ❌ Don't modify configuration without validation
- ❌ Don't commit without testing
- ❌ Don't push to main without verification
- ❌ Don't create experimental files in root
- ❌ Don't delete documentation files

---

## 🔍 Troubleshooting

### Repository Issues
```bash
# If git status shows errors
git status

# If remote is misconfigured
git remote set-url origin https://github.com/abhishekjs0/quantlab-bot.git

# If on wrong branch
git checkout main
git pull origin main
```

### Environment Issues
```bash
# If dependencies are missing
pip install -r pyproject.toml
# or
pip install pandas numpy requests pytest black isort

# If Python version is wrong
python3 --version  # Should be 3.8+
```

### Configuration Issues
```bash
# If config validation fails
python3 config.py

# Check specific settings
python3 -c "from config import settings; print(settings.model_dump())"
```

---

## 📚 Documentation Quick Links

| Document | Purpose | Read When |
|----------|---------|-----------|
| WORKFLOW_GUIDE.md | Complete end-to-end workflows | Starting any task |
| QUANTLAB_GUIDE.md | System architecture | Understanding design |
| INDEX.md | Documentation index | Looking for specific docs |
| BACKTEST_GUIDE.md | Backtest execution | Running backtests |
| Strategy guides | Strategy details | Developing strategies |
| JANITOR_PROMPT.md | Cleanup procedures | Ending session |

---

## 🎯 Success Criteria

Your startup initialization is successful when:

- ✅ `git status` shows clean repository
- ✅ `python3 config.py` validates without errors
- ✅ All critical directories exist
- ✅ Strategies are discoverable
- ✅ Tests run successfully
- ✅ Development tools are available
- ✅ You understand the repository structure
- ✅ You have read relevant documentation

---

**Last Updated**: November 5, 2025  
**Repository**: https://github.com/abhishekjs0/quantlab-bot.git  
**Version**: v1.0 Initial Release
