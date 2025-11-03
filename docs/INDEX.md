# QuantLab Documentation Index

**Complete documentation suite for the QuantLab trading system**

---

## 📚 Documentation Hierarchy

### 🎯 [Complete Workflow Guide](WORKFLOW_GUIDE.md) ⭐ **START HERE**
**Comprehensive end-to-end workflow documentation covering:**
- System setup and configuration
- Basket management and symbol mapping
- Data fetching pipeline with cache management
- Backtest execution procedures
- Report generation and analysis
- Production workflow and best practices
- Troubleshooting guide

### 🚀 [Startup Prompt](STARTUP_PROMPT.md) 🆕 **AI AGENT INITIALIZATION**
**Complete initialization guide for AI agents at session start:**
- Environment setup and verification
- Repository structure understanding
- Documentation reading checklist
- Data verification procedures
- System health checks and validation
- Command reference and best practices

### 🧹 [Janitor Prompt](JANITOR_PROMPT.md) 🆕 **SESSION CLEANUP**
**End-of-session repository maintenance:**
- Comprehensive cleanup procedures
- Git operations and deployment
- Code quality standards application
- Repository status verification

### 🏗️ [System Architecture Guide](QUANTLAB_GUIDE.md)
**Technical architecture and system features:**
- Clean directory structure
- Configuration management
- Smart caching system
- API integration details
- Development guidelines

---

## Strategy Guides

- [Ichimoku Strategy Guide](./ICHIMOKU_STRATEGY.md) - Complete Ichimoku strategy reference with trading rules, filters, and optimization
- [Ichimoku Filters Guide](./ICHIMOKU_FILTERS_GUIDE.md) - Detailed parameter reference for Ichimoku filter tuning
- [Envelope + KD Strategy Guide](./ENVELOPE_KD_STRATEGY.md) - Envelope-based mean reversion with divergence confirmation
- [on_bar() Execution Model](./ON_BAR_EXECUTION_MODEL.md) - Understanding signal generation and execution timing

---
**Quick start and project overview:**
- Installation instructions
- Basic usage examples
- Command references
- Migration notes

---

## 🚀 Quick Navigation

### For AI Agents
1. **Session Start**: [Startup Prompt](STARTUP_PROMPT.md) - Complete initialization
2. **Session End**: [Janitor Prompt](JANITOR_PROMPT.md) - Repository cleanup

### For New Users
1. **Start Here**: [Complete Workflow Guide](WORKFLOW_GUIDE.md)
2. **Setup System**: Follow Section 1 (System Setup & Configuration)
3. **First Backtest**: Follow Section 5 (Backtest Execution)

### For Developers  
1. **Architecture**: [System Architecture Guide](QUANTLAB_GUIDE.md)
2. **Technical Details**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 3 & 4
3. **Best Practices**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 7 & 10

### For Production Use
1. **Workflow**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 8
2. **Data Management**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 7
3. **Troubleshooting**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 9

---

## 📋 Command Quick Reference

### System Validation
```bash
python3 config.py                               # Validate system setup
```

### Data Management
```bash
python3 scripts/fetch_data.py                   # Fetch all basket data
python3 scripts/fetch_data.py SYMBOL1 SYMBOL2   # Fetch specific symbols
python3 scripts/fetch_data.py --force-refresh   # Force refresh cache
python3 scripts/fetch_data.py --clean-cache     # Clean redundant files
```

### Backtesting
```bash
# Basic backtest
python3 -m runners.run_basket --strategy ichimoku

# Specific basket
python3 -m runners.run_basket --basket_size mega --strategy ichimoku

# With parameters
python3 -m runners.run_basket --strategy ichimoku --params '{"conversion_line_length": 9}'
```

### Data Validation
```bash
python3 scripts/check_basket_data.py            # Check default basket
python3 scripts/check_basket_data.py --basket_file data/basket_mega.txt
```

---

## 🔍 Documentation Features

### Comprehensive Coverage
- ✅ **Complete Workflow**: End-to-end process documentation
- ✅ **Technical Architecture**: System design and implementation
- ✅ **Best Practices**: Production-ready procedures
- ✅ **Troubleshooting**: Common issues and solutions
- ✅ **Examples**: Real command examples and use cases

### Production Ready
- ✅ **Formalized Procedures**: Step-by-step workflows
- ✅ **Error Handling**: Comprehensive error scenarios
- ✅ **Performance Guidelines**: Optimization recommendations
- ✅ **Maintenance Schedules**: Daily/weekly/monthly procedures

### Developer Friendly
- ✅ **Clear Structure**: Logical organization
- ✅ **Code Examples**: Practical implementation examples
- ✅ **Configuration Management**: Centralized settings
- ✅ **Integration Guidelines**: How to extend the system

---

## 📅 Documentation Updates

| Document | Last Updated | Version | Changes |
|----------|--------------|---------|---------|
| **WORKFLOW_GUIDE.md** | 2025-10-19 | 2.0 | ✅ Complete formalized workflow |
| **QUANTLAB_GUIDE.md** | 2025-10-19 | 2.0 | ✅ Updated architecture |
| **README.md** | 2025-10-19 | 2.0 | ✅ Clean structure |
| **INDEX.md** | 2025-10-19 | 1.0 | 🆕 New documentation index |

---

## 🎯 Getting Started

**For immediate results, follow this path:**

1. **📖 Read**: [Complete Workflow Guide](WORKFLOW_GUIDE.md) - Section 1
2. **⚙️ Setup**: Follow system configuration steps
3. **🔄 Validate**: Run `python3 config.py`
4. **📊 Execute**: Run your first backtest
5. **📈 Analyze**: Review generated reports

**Total time to first backtest: ~15 minutes**

---

*This documentation index provides a clear path through all QuantLab documentation. Start with the Workflow Guide for complete coverage of the system.*