# QuantLab Startup Prompt - Session Initialization

**For AI Agents**: Use this prompt at the start of each development session to establish context, verify environment, and understand available resources.

---

## 🚀 Quick Session Start

```bash
# 1. Navigate to workspace
cd /Users/abhishekshah/Desktop/quantlab-workspace

# 2. Activate virtual environment
source .venv/bin/activate

# 3. Verify installation
python3 config.py

# 4. Run startup context
python3 << 'EOF'
# Session context script (see below)
EOF
```

---

## 📊 Repository Context

### Basic Information
- **Repository**: quantlab-bot
- **Owner**: abhishekjs0
- **URL**: https://github.com/abhishekjs0/quantlab-bot.git
- **Branch**: main
- **Remote**: origin

### Current Status
```bash
# Check status
git status                    # Should show "nothing to commit, working tree clean"
git log --oneline -5         # Show recent commits
git remote -v                # Verify remote configuration
```

---

## 🔧 Environment Verification

### Python Environment
```python
import sys
import subprocess

# Check Python version
print(f"Python: {sys.version}")
print(f"Executable: {sys.executable}")
print(f"Virtual Env Active: {sys.prefix}")

# Should output:
# Python: 3.9.6 (or similar)
# Executable: /path/to/.venv/bin/python3
# Virtual Env Active: /path/to/.venv
```

### Dependencies
```bash
# Install if needed
pip install -r requirements.txt

# Verify key packages
python3 -c "import pandas; print(f'pandas: {pandas.__version__}')"
python3 -c "import numpy; print(f'numpy: {numpy.__version__}')"
python3 -c "import requests; print(f'requests: {requests.__version__}')"
```

### Configuration
```bash
# Verify config loads
python3 config.py

# Expected output: Configuration and directory structure shown
```

### Environment Variables
```bash
# Check .env file exists
ls -la .env

# Should exist with:
# - DHAN_ACCESS_TOKEN
# - DHAN_CLIENT_ID
# - DHAN_USER_ID
# - DHAN_PASSWORD
# - DHAN_TOTP_SECRET
# - etc.
```

---

## 📁 Project Structure Reference

### Core Directories

| Directory | Purpose | Files |
|-----------|---------|-------|
| `core/` | Backtesting engine | 10 files |
| `strategies/` | Trading strategies | 5 files (4 production + template) |
| `utils/` | Technical indicators | 5 files |
| `data/` | Market data & baskets | 12 files |
| `scripts/` | Utility scripts | 6 files |
| `runners/` | Execution orchestration | 2 files |
| `tests/` | Test suite | 11 files |
| `docs/` | Documentation | 10+ files |
| `viz/` | Dashboard & visualization | 2 files |

### Available Strategies
```
strategies/
├── ema_crossover.py        # EMA crossover strategy
├── ichimoku.py             # Ichimoku strategy
├── knoxville.py            # Knoxville strategy
└── template.py             # Strategy template
```

### Available Data Baskets
```
data/
├── basket_small.txt        # 99 symbols
├── basket_mid.txt          # 51 symbols
├── basket_large.txt        # 103 symbols
├── basket_default.txt      # 162 symbols
├── basket_mega.txt         # 73 symbols
└── basket_test.txt         # 3 symbols
```

### Test Suite
```
tests/
├── test_smoke.py
├── test_strategy_wrapper.py
├── test_basket_metrics.py
├── test_backtesting_integration.py
├── test_integration_basket.py
├── test_perf.py
└── ... (11 total)
```

---

## 🎯 Common Tasks

### 1. Run a Backtest

```bash
# EMA Crossover on default basket
python3 -m runners.run_basket --strategy ema_crossover

# Ichimoku on mega basket
python3 -m runners.run_basket --strategy ichimoku --basket mega

# Knoxville on small basket
python3 -m runners.run_basket --strategy knoxville --basket small

# With specific date range
python3 -m runners.run_basket --strategy ema_crossover --start 2024-01-01 --end 2024-12-31
```

### 2. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_smoke.py -v

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run and stop on first failure
pytest tests/ -x

# Run specific test function
pytest tests/test_smoke.py::test_import_strategies -v
```

### 3. Check Dhan API

```bash
# View account holdings and status
python3 scripts/dhan_working.py

# Check token status
python3 scripts/dhan_token_manager.py

# Refresh token (automated)
python3 scripts/dhan_login_auto_improved.py

# Manual token refresh
python3 scripts/dhan_token_refresh.py
```

### 4. Data Operations

```bash
# Fetch historical data
python3 scripts/fetch_data.py

# Check basket data
python3 scripts/check_basket_data.py

# Create symbol mapping
python3 scripts/create_symbol_mapping.py
```

### 5. Code Quality

```bash
# Format code with Black
black .

# Organize imports
isort .

# Run Ruff linter
ruff check .

# All at once
black . && isort . && ruff check .
```

### 6. Generate Dashboard

```bash
# From latest report
python3 viz/dashboard.py 1104-1729-knoxville-basket-mega

# List available reports
ls -la reports/ | grep "^d" | awk '{print $NF}'
```

---

## 📚 Documentation Guide

### Essential Reading
1. **Quick Start**: `docs/INDEX.md` (5 min)
   - Navigation and quick reference

2. **Architecture**: `docs/QUANTLAB_GUIDE.md` (15 min)
   - System design and components

3. **Workflow**: `docs/WORKFLOW_GUIDE.md` (20 min)
   - Complete end-to-end processes

4. **Backtesting**: `docs/BACKTEST_GUIDE.md` (10 min)
   - How to run and interpret backtests

### For Specific Tasks
- **Data**: `docs/DHAN_USAGE.md`
- **Market Regime**: `docs/MARKET_REGIME_GUIDE.md`
- **Walk-Forward**: `docs/WALK_FORWARD_GUIDE.md`
- **Development**: `docs/DEVELOPMENT_WORKFLOW.md`

### Session End
- Use `docs/JANITOR_PROMPT.md` for cleanup and commit

---

## 🔐 Dhan API Setup

### Quick Status Check
```bash
python3 scripts/dhan_token_manager.py
```

Expected output shows:
- ✅ Token Status: VALID
- 📅 Valid Until: [date]
- ⏳ Days Remaining: [days]

### If Token Expired
```bash
# Automated refresh (requires Chrome)
python3 scripts/dhan_login_auto_improved.py

# OR manual refresh
python3 scripts/dhan_token_refresh.py
```

### View Account
```bash
python3 scripts/dhan_working.py
```

Shows:
- Portfolio holdings (symbols, quantities, values)
- Total invested value
- Position details
- Recent trades

---

## ⚡ Session Workflow

### At Session Start
1. ✅ Review this prompt
2. ✅ Check repository status: `git status`
3. ✅ Verify environment: `python3 config.py`
4. ✅ Read relevant documentation
5. ✅ Run quick verification: `pytest tests/test_smoke.py -v`

### During Session
1. 💻 Make code changes
2. 🧪 Run tests frequently: `pytest tests/ -v`
3. 📝 Commit regularly: `git add . && git commit -m "message"`
4. 📊 Check formatting: `black . && isort .`

### At Session End
1. 🧹 Run janitor cleanup: Follow `docs/JANITOR_PROMPT.md`
2. 📝 Commit final changes: `git add . && git commit -m "final message"`
3. 🚀 Push to GitHub: `git push origin main`
4. ✅ Verify: `git status` shows "nothing to commit"

---

## 💡 Key Environment Variables

```bash
# API Credentials
DHAN_ACCESS_TOKEN=eyJ...        # JWT token for Dhan API
DHAN_CLIENT_ID=...              # Client ID

# Login Credentials (for token refresh)
DHAN_USER_ID=...                # Dhan user ID
DHAN_PASSWORD=...               # Dhan password
DHAN_TOTP_SECRET=...            # 2FA secret

# Optional
DEBUG=false                      # Debug logging
LOG_LEVEL=INFO                   # Logging level
```

Check with:
```bash
cat .env | grep -v "^#" | grep -v "^$"
```

---

## 🚨 Troubleshooting

### Virtual Environment Issues
```bash
# Verify venv is active
which python3          # Should show .venv path
echo $VIRTUAL_ENV      # Should show .venv path

# Reactivate if needed
source .venv/bin/activate
```

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Verify installation
python3 -c "import runners; print('✅ runners module works')"
```

### Git Issues
```bash
# Check remote
git remote -v
# Should show: origin https://github.com/abhishekjs0/quantlab-bot.git

# Pull latest
git fetch origin
git pull origin main
```

### Token Issues
```bash
# Check token validity
python3 scripts/dhan_token_manager.py

# If expired, refresh
python3 scripts/dhan_login_auto_improved.py
```

---

## 📞 Quick References

### Backtesting Parameters
```python
# In strategy files
entry_signal: bool              # Entry condition
exit_signal: bool               # Exit condition
quantity: int                   # Position size
stop_loss_pct: float           # Stop loss %
take_profit_pct: float         # Take profit %
```

### Test Running
```bash
pytest tests/ -v               # Verbose output
pytest tests/ -x               # Stop on first failure
pytest tests/ -k keyword       # Run tests matching keyword
pytest tests/ --co             # Only collect tests
```

### Git Workflow
```bash
git status                     # Check status
git add .                      # Stage all changes
git commit -m "message"        # Create commit
git push origin main           # Push to GitHub
git log --oneline -5           # See recent commits
```

---

## ✅ Session Start Checklist

- [ ] Virtual environment activated
- [ ] `python3 config.py` runs without errors
- [ ] `pytest tests/test_smoke.py -v` passes
- [ ] `python3 scripts/dhan_token_manager.py` shows valid token
- [ ] `.env` file present with credentials
- [ ] `git status` shows clean working tree
- [ ] Documentation reviewed for task type
- [ ] Ready to start development!

---

---

## �️ Development Workflow & Code Quality

### Code Quality Standards

**All commits must follow these standards:**

#### Formatting
- **Black**: Code formatted with 88-character line length
  ```bash
  black . --quiet
  ```
- **isort**: Import statements organized
  ```bash
  isort . --quiet
  ```
- **Ruff**: Fast Python linter
  ```bash
  ruff check . --fix
  ```

#### Pre-Commit Checklist
Before committing any code:
```bash
# 1. Format code
black .
isort .

# 2. Lint and fix
ruff check . --fix

# 3. Run tests
pytest tests/ --cov=. -v

# 4. Verify changes
git diff
```

### Testing Framework

**Test Structure:**
```
tests/
├── test_*.py              # Unit tests
├── test_integration_*.py  # Integration tests
└── test_parity_*.py       # Parity validation tests
```

**Running Tests:**
```bash
# All tests with coverage
pytest tests/ --cov=. --cov-report=html

# Specific test file
pytest tests/test_integration_basket.py -v

# Quick smoke tests
pytest tests/test_smoke.py
```

**Coverage Requirements:**
- Minimum: 35% overall coverage
- Target: 50%+ for core modules
- Command: `pytest --cov=. --cov-fail-under=35`

### Development Setup

**Quick Start:**
```bash
# 1. Clone repository
git clone https://github.com/abhishekjs0/quantlab-bot.git
cd quantlab-workspace

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install development dependencies
pip install -e ".[dev]"

# 4. Install code quality tools
pip install black isort ruff pytest pytest-cov
```

**Configuration Files:**
- `pyproject.toml`: All tool configurations (Black, isort, Ruff)
- `.gitignore`: Git exclusions and patterns
- `requirements.txt`: Production dependencies
- `config.py`: System configuration

---

## ✅ Session End Checklist

- [ ] All changes committed: `git status`
- [ ] No uncommitted work: `git diff`
- [ ] Code formatted: `black . && isort . && ruff check .`
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Cleanup executed: Follow `docs/JANITOR_PROMPT.md`
- [ ] Final push: `git push origin main`
- [ ] Verify: `git status` shows "nothing to commit"

---

**Last Updated**: November 6, 2025  
**Version**: 2.0 - Post-Janitor Cleanup  
**For**: quantlab-bot development sessions
