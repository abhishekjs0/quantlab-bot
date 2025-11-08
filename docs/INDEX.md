# QuantLab Documentation Index# QuantLab Documentation Index



**Complete documentation suite for the QuantLab trading system**



**Last Updated**: November 8, 2025 (Documentation consolidation - 60% file reduction)**Quick navigation to core documentation****Complete documentation suite for the QuantLab trading system**  



---**Last Updated**: November 5, 2025 (Major consolidation - 56% documentation reduction)



## 📚 Core Documentation (8 Files)---



### 1. **QUANTLAB_GUIDE.md** ⭐ START HERE---

High-level overview of QuantLab with features, quick start, and architecture summary.

→ Read this first for an introduction## 📚 Core Documentation (5 Files)



### 2. **BACKTEST_GUIDE.md** 📖 COMPREHENSIVE REFERENCE## 📚 Documentation Organization (Consolidated)

Complete backtesting documentation including test suite organization, running tests with coverage, validation procedures, real data integration, and all 542 stocks in the 6-basket universe.

→ Read this for backtesting procedures and stock universe reference### 1. **OVERVIEW.md** ⭐ START HERE



### 3. **DHAN_COMPREHENSIVE_GUIDE.md** 🔌 API REFERENCEHigh-level overview of QuantLab with features, quick start, and architecture summary.  ### 🚀 [Getting Started Guide](GETTING_STARTED.md) ⭐ **START HERE**

Complete Dhan API documentation and integration details.

→ Read this to understand Dhan API setup and usage→ Read this first for an introduction**All-in-one quick reference for setup, running backtests, and common tasks:**



### 4. **DEVELOPMENT_WORKFLOW.md** 🛠️ DEVELOPMENT- 5-minute quick start setup

Code quality standards, testing procedures, and CI/CD setup for developers.

→ Read this for development setup and best practices### 2. **COMPREHENSIVE_GUIDE.md** 📖 MAIN REFERENCE- Directory structure explanation



### 5. **STARTUP_PROMPT.md** 🤖 AI INITIALIZATIONComplete end-to-end procedures: setup, backtesting, testing, development, architecture, data management.  - Common tasks and examples

Context and information for AI agents at session start.

→ For AI sessions only→ Read this for step-by-step instructions on everything- Git workflow basics



### 6. **JANITOR_PROMPT.md** 🧹 CLEANUP- Test suite reference

Repository maintenance and cleanup procedures for end-of-session.

→ For session cleanup tasks### 3. **STRATEGIES.md** 🎯 STRATEGY DETAILS- Troubleshooting



### 7. **CONSOLIDATION_COMPLETE_NOV8.md** 📋 STATUS REPORTAll trading strategies (EMA Crossover, Ichimoku, Knoxville) with performance, parameters, and how to add new ones.  - *Replaces: DIRECTORY_REFERENCE.md, QUANTLAB_GUIDE.md, REPO_SETUP_GUIDE.md*

Summary of documentation consolidation and code structure analysis (November 8, 2025).

→ Reference document showing what was consolidated and removed→ Read this to understand strategies or add your own



### 8. **README.md** 📖 PRODUCT OVERVIEW### 🎯 [Complete Workflow Guide](WORKFLOW_GUIDE.md) **COMPREHENSIVE REFERENCE**

High-level features, quick start, and general information.

→ Quick overview of the project### 4. **STARTUP_PROMPT.md** 🤖 AI INITIALIZATION**Detailed end-to-end workflow documentation for production use:**



---Context and information for AI agents at session start.  - System setup and configuration



## 🗂️ Quick Navigation by Use Case→ For AI sessions only- Basket management and symbol mapping



### "I'm new and want to get started"- Data fetching pipeline with cache management

→ Read QUANTLAB_GUIDE.md first

### 5. **JANITOR_PROMPT.md** 🧹 CLEANUP- Backtest execution procedures

### "I want to run a backtest"

→ Read BACKTEST_GUIDE.mdRepository maintenance and cleanup procedures for end-of-session.  - Report generation and analysis



### "I want to set up the Dhan API"→ For session cleanup tasks- Production workflow and best practices

→ Read DHAN_COMPREHENSIVE_GUIDE.md

- Troubleshooting guide

### "I want to understand system architecture"

→ Read QUANTLAB_GUIDE.md (Architecture section)---



### "I want to run tests"### � [Backtest Guide](BACKTEST_GUIDE.md) **DETAILED TESTING & VALIDATION**

→ Read BACKTEST_GUIDE.md (Testing section)

## 🗂️ Quick Navigation by Use Case**Comprehensive backtesting documentation:**

### "I want to set up development"

→ Read DEVELOPMENT_WORKFLOW.md- Test suite organization and status



### "I want to troubleshoot an issue"### "I'm new and want to get started"- Running tests with coverage

→ Read QUANTLAB_GUIDE.md (Troubleshooting section)

→ Read OVERVIEW.md first, then COMPREHENSIVE_GUIDE.md (Quick Start section)- Validation procedures

---

- Real data integration

## 📊 Documentation Statistics

### "I want to run a backtest"

| Metric | Before | After | Change |

|--------|--------|-------|--------|→ Read COMPREHENSIVE_GUIDE.md (Running Backtests section)### 🏗️ [System Architecture](ARCHITECTURE_AND_DATA_QUALITY.md) **SYSTEM DESIGN**

| **Total Documentation Files** | 15 files | 8 files | -47% |

| **Overlapping Content** | High | Low | -60% |**Technical architecture and data quality documentation:**

| **Total Lines** | ~6,000 lines | ~3,500 lines | -42% |

### "I want to understand a strategy"- System design decisions

**Consolidation Summary (November 8, 2025):**

- ✅ Deleted 7 old documentation files (merged into existing guides)→ Read STRATEGIES.md (strategy of interest)- Data quality assurance

- ✅ BACKTEST_GUIDE.md now includes all 542 stocks from 6-basket universe

- ✅ DHAN_COMPREHENSIVE_GUIDE.md already complete (consolidated from DHAN_API_USAGE.md)- Implementation details

- ✅ Created CONSOLIDATION_COMPLETE_NOV8.md summary

- ✅ Improved navigation with consolidated INDEX.md### "I want to add a new strategy"



---→ Read STRATEGIES.md (Adding a New Strategy section)### 🚀 [Startup Prompt](STARTUP_PROMPT.md) **AI AGENT INITIALIZATION**



## 🎯 Quick Commands**Context for AI agents at session start:**



```bash### "I want to understand the system architecture"- Current system architecture

# Validate system

python3 config.py→ Read COMPREHENSIVE_GUIDE.md (System Architecture section)- Known issues and implementation status



# Run backtest- Test failures and fixes needed

python3 -m runners.run_basket --strategy ema_crossover

### "I want to run tests"- Critical rules for AI operations

# Run tests

pytest tests/ --cov=. --cov-report=html→ Read COMPREHENSIVE_GUIDE.md (Testing & Validation section)



# Format code### 🧹 [Janitor Prompt](JANITOR_PROMPT.md) **SESSION CLEANUP**

black . && isort . && ruff check .

### "I want to set up development"**End-of-session repository maintenance:**

# Fetch data

python3 scripts/fetch_data.py→ Read COMPREHENSIVE_GUIDE.md (Development Workflow section)- Cleanup procedures

```

- Git operations and deployment

---

### "I want to troubleshoot an issue"- Code quality standards

## ✅ Current Status

→ Read COMPREHENSIVE_GUIDE.md (Troubleshooting section)- Repository verification

- **Tests**: 42/42 passing ✅

- **Coverage**: 28% overall

- **Code Quality**: Black + isort + Ruff compliant

- **Documentation**: Consolidated (8 core files)------

- **Volatility Calculation**: Simplified (2.75% using all daily returns)



---

## 📊 Documentation Statistics## 📊 Strategy Implementation Guides

**Start with QUANTLAB_GUIDE.md →**



| File | Purpose | Lines | Read Time |- [EMA Crossover Strategy](./EMA_CROSSOVER_STRATEGY.md) - EMA crossover trading system

|------|---------|-------|-----------|- [Ichimoku Strategy](./ICHIMOKU_STRATEGY.md) - Ichimoku cloud strategy

| OVERVIEW.md | Features & quick start | ~300 | 5 min |- [Knoxville Strategy](./KNOXVILLE_STRATEGY.md) - Advanced multi-indicator strategy

| COMPREHENSIVE_GUIDE.md | All procedures | ~1000 | 20 min |

| STRATEGIES.md | Trading strategies | ~800 | 15 min |---

| STARTUP_PROMPT.md | AI context | ~900 | - |

| JANITOR_PROMPT.md | Cleanup | ~500 | - |## 🛠️ Development & Maintenance

| **TOTAL** | **Everything** | **~3500** | **~40 min** |

- [Development Workflow](DEVELOPMENT_WORKFLOW.md) - Code quality, testing, CI/CD setup

---- [README.md](../README.md) - Product overview and features



## 🎯 Quick Commands---



```bash## 🚀 Quick Navigation

# Validate system

python3 config.py### For New Users

1. **Start Here**: [Getting Started Guide](GETTING_STARTED.md) - 5-minute setup

# Run backtest2. **First Backtest**: Follow quick start section

python3 -m runners.run_basket --strategy ema_crossover3. **Deeper Learning**: [Complete Workflow Guide](WORKFLOW_GUIDE.md)



# Run tests### For AI Agents  

pytest tests/ --cov=. --cov-report=html1. **Session Start**: [Startup Prompt](STARTUP_PROMPT.md) - Initialization

2. **Common Tasks**: [Getting Started Guide](GETTING_STARTED.md)

# Format code3. **Architecture Details**: [System Architecture](ARCHITECTURE_AND_DATA_QUALITY.md)

black . && isort . && ruff check .4. **Session End**: [Janitor Prompt](JANITOR_PROMPT.md) - Cleanup



# Fetch data### For Developers

python3 scripts/fetch_data.py1. **Setup**: [Development Workflow](DEVELOPMENT_WORKFLOW.md)

2. **Architecture**: [System Architecture](ARCHITECTURE_AND_DATA_QUALITY.md)

# Build API docs3. **Testing**: [Backtest Guide](BACKTEST_GUIDE.md)

cd docs/api && make html4. **Detailed Procedures**: [Complete Workflow Guide](WORKFLOW_GUIDE.md)

```

### For Production Use

---1. **Daily Operations**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 8

2. **Data Management**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 7

## ✅ Current Status3. **Issue Resolution**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 9



- **Tests**: 42/42 passing ✅---

- **Coverage**: 28% overall

- **Code Quality**: Black + isort + Ruff compliant## 📋 Quick Command Reference

- **Documentation**: Consolidated (5 core files)

### System Validation

---```bash

python3 config.py                               # Validate system setup

**Start with OVERVIEW.md →**```


### Testing
```bash
pytest tests/ --cov=. --cov-report=html        # Run all tests with coverage
pytest tests/test_smoke.py -v                  # Quick smoke tests
```

### Backtesting
```bash
python3 -m runners.run_basket --strategy ema_crossover --use_cache_only
```

### Data Management
```bash
python3 scripts/fetch_data.py                  # Fetch all basket data
python3 scripts/fetch_data.py --force-refresh  # Force refresh cache
```

---

## � Documentation Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Total Documentation** | 6,546 lines | 2,800 lines | -57% |
| **Docs Files** | 16 files | 11 files | -31% |
| **Overlapping Guides** | 4 files | 1 file | -75% |
| **Ad-hoc Files** | 2 files | 0 files | -100% |

**Consolidation Summary:**
- ✅ Merged 4 overlapping guides → GETTING_STARTED.md
- ✅ Deleted 2 historical test documents
- ✅ Kept all critical strategy and workflow documentation
- ✅ Improved navigation with clearer INDEX.md

---

## 🎯 Getting Started Checklist

**5-minute quick start:**
1. Read: [Getting Started Guide](GETTING_STARTED.md) - Quick Start section
2. Setup: `pip install -e ".[dev]"`
3. Validate: `python3 config.py`
4. Test: `.venv/bin/python -m pytest test_signal_reasons.py`
5. Backtest: `python3 -m runners.run_basket --strategy ema_crossover --use_cache_only`

**Total time: ~10-15 minutes**

---

*This documentation has been consolidated for clarity and maintainability. Updated: November 5, 2025*