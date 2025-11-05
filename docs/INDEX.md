# QuantLab Documentation Index# QuantLab Documentation Index



**Quick navigation to core documentation****Complete documentation suite for the QuantLab trading system**  

**Last Updated**: November 5, 2025 (Major consolidation - 56% documentation reduction)

---

---

## 📚 Core Documentation (5 Files)

## 📚 Documentation Organization (Consolidated)

### 1. **OVERVIEW.md** ⭐ START HERE

High-level overview of QuantLab with features, quick start, and architecture summary.  ### 🚀 [Getting Started Guide](GETTING_STARTED.md) ⭐ **START HERE**

→ Read this first for an introduction**All-in-one quick reference for setup, running backtests, and common tasks:**

- 5-minute quick start setup

### 2. **COMPREHENSIVE_GUIDE.md** 📖 MAIN REFERENCE- Directory structure explanation

Complete end-to-end procedures: setup, backtesting, testing, development, architecture, data management.  - Common tasks and examples

→ Read this for step-by-step instructions on everything- Git workflow basics

- Test suite reference

### 3. **STRATEGIES.md** 🎯 STRATEGY DETAILS- Troubleshooting

All trading strategies (EMA Crossover, Ichimoku, Knoxville) with performance, parameters, and how to add new ones.  - *Replaces: DIRECTORY_REFERENCE.md, QUANTLAB_GUIDE.md, REPO_SETUP_GUIDE.md*

→ Read this to understand strategies or add your own

### 🎯 [Complete Workflow Guide](WORKFLOW_GUIDE.md) **COMPREHENSIVE REFERENCE**

### 4. **STARTUP_PROMPT.md** 🤖 AI INITIALIZATION**Detailed end-to-end workflow documentation for production use:**

Context and information for AI agents at session start.  - System setup and configuration

→ For AI sessions only- Basket management and symbol mapping

- Data fetching pipeline with cache management

### 5. **JANITOR_PROMPT.md** 🧹 CLEANUP- Backtest execution procedures

Repository maintenance and cleanup procedures for end-of-session.  - Report generation and analysis

→ For session cleanup tasks- Production workflow and best practices

- Troubleshooting guide

---

### � [Backtest Guide](BACKTEST_GUIDE.md) **DETAILED TESTING & VALIDATION**

## 🗂️ Quick Navigation by Use Case**Comprehensive backtesting documentation:**

- Test suite organization and status

### "I'm new and want to get started"- Running tests with coverage

→ Read OVERVIEW.md first, then COMPREHENSIVE_GUIDE.md (Quick Start section)- Validation procedures

- Real data integration

### "I want to run a backtest"

→ Read COMPREHENSIVE_GUIDE.md (Running Backtests section)### 🏗️ [System Architecture](ARCHITECTURE_AND_DATA_QUALITY.md) **SYSTEM DESIGN**

**Technical architecture and data quality documentation:**

### "I want to understand a strategy"- System design decisions

→ Read STRATEGIES.md (strategy of interest)- Data quality assurance

- Implementation details

### "I want to add a new strategy"

→ Read STRATEGIES.md (Adding a New Strategy section)### 🚀 [Startup Prompt](STARTUP_PROMPT.md) **AI AGENT INITIALIZATION**

**Context for AI agents at session start:**

### "I want to understand the system architecture"- Current system architecture

→ Read COMPREHENSIVE_GUIDE.md (System Architecture section)- Known issues and implementation status

- Test failures and fixes needed

### "I want to run tests"- Critical rules for AI operations

→ Read COMPREHENSIVE_GUIDE.md (Testing & Validation section)

### 🧹 [Janitor Prompt](JANITOR_PROMPT.md) **SESSION CLEANUP**

### "I want to set up development"**End-of-session repository maintenance:**

→ Read COMPREHENSIVE_GUIDE.md (Development Workflow section)- Cleanup procedures

- Git operations and deployment

### "I want to troubleshoot an issue"- Code quality standards

→ Read COMPREHENSIVE_GUIDE.md (Troubleshooting section)- Repository verification



------



## 📊 Documentation Statistics## 📊 Strategy Implementation Guides



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