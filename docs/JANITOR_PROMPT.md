# QuantLab Repository Janitor - Final Cleanup Prompt

**For AI Agents**: Use this prompt at the end of each development session to perform comprehensive repository cleanup and commit all changes to GitHub.

---

## 📋 Session Completion Notes (Updated November 13, 2025)

### Latest Session Summary
**Completed Tasks:**
- ✅ Commission verification: Both entry and exit commissions correctly applied
- ✅ Documentation consolidation: Deleted 13 secondary .md files
- ✅ Consolidated 5 primary documentation files with critical information
- ✅ Cleaned up temporary/debug scripts and test files
- ✅ Updated STARTUP_PROMPT with comprehensive development workflow
- ✅ Updated QUANTLAB_GUIDE with navigation index
- ✅ Updated BACKTEST_GUIDE with commission verification findings
- ✅ Removed 9 temporary development files (debug_*.py, test_*.py, shell scripts, etc.)

### Important: Documentation Consolidation
Documentation was consolidated from 18+ files down to 7 primary files:
1. QUANTLAB_GUIDE.md (System overview + navigation index)
2. BACKTEST_GUIDE.md (Backtesting + commission verification)
3. STRATEGIES.md (Trading strategies)
4. STARTUP_PROMPT.md (Session setup + development workflow)
5. JANITOR_PROMPT.md (Cleanup procedures - this file)
6. DHAN_COMPREHENSIVE_GUIDE.md (API reference)
7. README.md (Project overview)

**Critical information from deleted files was preserved** and merged into appropriate primary docs.

---

## ⚠️ CRITICAL: Common Mistake to Avoid

### Previous Error: Files Not Deleted in Phase 1

**What Went Wrong:**
In a previous session, Phase 1 cleanup failed to delete temporary files like:
- `debug_*.py`, `test_*.py` scripts
- `run_all_emas.sh` and similar shell scripts
- `.log` and output CSV files
- `COMPLETION_REPORT.txt` and status files

These files were created during development but NOT deleted, so they got committed to GitHub.

**Why It Happened:**
- Phase 1 cleanup ran but didn't explicitly list all temporary file patterns
- Files were in git status but treated as legitimate changes to commit
- No verification checkpoint between cleanup and git add

**How to Prevent This:**
✅ **Execute Phase 1 COMPLETELY before any git operations**
✅ **Run verification:** `git status` should show ONLY intentional changes
✅ **Check root directory:** `ls -la *.py *.sh *.log *.csv` should be minimal
✅ **Don't commit** if you see unexpected files
✅ **Delete problematic files** BEFORE `git add .`
✅ **Follow the CRITICAL CHECKPOINT** in Phase 1 instructions

---

## 🧹 COMPREHENSIVE CLEANUP EXECUTION PROMPT

### Objective
Execute a complete repository maintenance cycle that removes all temporary files, applies code quality standards, and commits changes to GitHub with a clear audit trail.

### Execution Steps

#### Phase 1: Development File Cleanup (CRITICAL - Execute First!)
Remove ALL temporary development artifacts from root directory:

```bash
# ⚠️ IMPORTANT: Execute these BEFORE git add
# These are temporary files created during development/debugging

# Debug and test scripts
find . -maxdepth 1 -type f \( \
  -name "*_debug*.py" -o \
  -name "*_comparison*.py" -o \
  -name "test_*.py" -o \
  -name "debug_*.py" -o \
  -name "demo_*.py" \
\) -delete

# Shell scripts and temporary runners
rm -f run_*.sh run_all_*.sh *.sh

# Temporary output files
rm -f *_comparison*.md *_analysis*.md portfolio_comparison*.md
rm -f *_REPORT.txt *_SUMMARY.txt COMPLETION_REPORT.txt
rm -f *.log *.csv (except essential ones)

# Root-level test/debug files
rm -f test_*.py ema_*.csv run_all_emas.sh

# Specific files to always remove (if present):
rm -f scripts/add_open_positions_to_trades.py
rm -f run_all_emas.sh
rm -f test_engine_direct.py
rm -f ema_final_results.csv
rm -f debug_trades.py
rm -f debug_360one.py
rm -f COMPLETION_REPORT.txt
rm -f backtest_run.log
rm -f backtest_output.log
rm -f data/basket_debug.txt
rm -f data/basket_debug_small.txt

# Data directory cleanup (keep only essential baskets)
find data/ -maxdepth 1 -name "basket_*.txt" ! \
  -name "basket_all_baskets.txt" ! \
  -name "basket_default.txt" ! \
  -name "basket_large.txt" ! \
  -name "basket_largecap_highbeta.txt" ! \
  -name "basket_largecap_lowbeta.txt" ! \
  -name "basket_mega.txt" ! \
  -name "basket_mid.txt" ! \
  -name "basket_midcap_highbeta.txt" ! \
  -name "basket_midcap_lowbeta.txt" ! \
  -name "basket_small.txt" ! \
  -name "basket_smallcap_highbeta.txt" ! \
  -name "basket_smallcap_lowbeta.txt" ! \
  -name "basket_test.txt" -delete
```

**⚠️ CRITICAL CHECKPOINT**: Before proceeding, run:
```bash
git status  # Should show only legitimate changes, NOT new temp files
ls -la *.py *.sh *.log *.csv 2>/dev/null | wc -l  # Should be minimal
```

If you see temp files still listed, delete them now BEFORE Phase 2!

#### Phase 2: Strategy Directory Cleanup
Remove experimental strategies while keeping production versions:

```bash
rm -f strategies/*_wrapper.py strategies/*_simple_*.py strategies/*_temp*.py
rm -f strategies/*_experimental.py strategies/*_backup_*.py

# Production strategies to keep:
# - strategies/ichimoku.py (production with global market regime)
# - strategies/template.py (modern development template)
```

#### Phase 3: Test Suite Optimization
Remove obsolete test files:

```bash
rm -f tests/test_old_*.py tests/test_backup_*.py tests/test_experimental_*.py tests/test_deprecated_*.py
rm -f tests/data/*_old.csv tests/data/*_backup.csv

# Production tests to keep:
# - tests/test_strategy_wrapper.py
# - tests/test_basket_metrics.py
# - tests/test_integration_basket.py
# - tests/test_parity_basket.py
# - tests/test_perf.py
# - tests/test_pf_and_cagr.py
# - tests/test_smoke.py
```

#### Phase 4: Scripts Directory Cleanup
Remove obsolete scripts:

```bash
rm -f scripts/*_old.py scripts/*_backup.py scripts/*_experimental.py scripts/*_debug.py

# Production scripts to keep:
# - scripts/fetch_data.py
# - scripts/check_basket_data.py
# - scripts/create_symbol_mapping.py
# - scripts/rank_strategies.py
# - scripts/setup_dev.py
```

#### Phase 5: System Cache Cleanup
Remove all cache and temporary files:

```bash
# Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name "*.pyd" -delete 2>/dev/null || true

# System files
find . -name ".DS_Store" -delete 2>/dev/null || true
find . -name "Thumbs.db" -delete 2>/dev/null || true

# Temporary files
find . -name "*.tmp" -delete 2>/dev/null || true
find . -name "*.temp" -delete 2>/dev/null || true
find . -name "*~" -delete 2>/dev/null || true

# Build artifacts
rm -rf docs/api/_build/ 2>/dev/null || true
rm -rf .pytest_cache/ 2>/dev/null || true
rm -f .coverage 2>/dev/null || true
rm -rf htmlcov/ 2>/dev/null || true
```

#### Phase 6: Code Quality Formatting
Apply modern code standards (requires tools in environment):

```bash
# Apply Black formatting (88-char line length)
if command -v black &> /dev/null; then
    black . --quiet
fi

# Organize imports
if command -v isort &> /dev/null; then
    isort . --quiet
fi

# Apply Ruff auto-fixes
if command -v ruff &> /dev/null; then
    ruff check --fix . 2>/dev/null || true
fi
```

#### 🛑 VERIFICATION CHECKPOINT - DO NOT SKIP
Before proceeding to Git phases, verify cleanup was successful:

```bash
echo "=== VERIFICATION CHECKLIST ==="

# 1. Check for remaining temporary files
echo "❓ Checking for temp files in root..."
ls -la *.py *.sh *.log *.csv *.txt 2>/dev/null | grep -E "debug|test_|demo_|_comparison|_analysis" && echo "⚠️  FOUND TEMP FILES - DELETE THEM FIRST!" || echo "✅ No temp files in root"

# 2. Check git status
echo ""
echo "❓ Checking git status..."
git status --short | head -10
echo ""
echo "⚠️  If you see files like 'debug_*.py' or 'test_*.py' in git status,"
echo "    delete them NOW with 'rm -f filename' before proceeding!"

# 3. Check for __pycache__
echo ""
echo "❓ Checking for cache directories..."
find . -type d -name "__pycache__" | wc -l
echo "   (Should be 0 - if not, something went wrong in Phase 5)"

# 4. Verify core structure intact
echo ""
echo "❓ Verifying core directories exist..."
for dir in core strategies runners tests utils data docs; do
    [ -d "$dir" ] && echo "  ✅ $dir/" || echo "  ❌ $dir/ MISSING!"
done

echo ""
echo "If everything above is ✅, proceed to Phase 7. Otherwise, fix issues!"
```

#### Phase 7: Git Repository Preparation
Prepare repository for deployment:

```bash
# Remove git-lfs configuration issues
git config --local --unset filter.lfs.process 2>/dev/null || true
git config --local --unset filter.lfs.required 2>/dev/null || true
git config --local --unset filter.lfs.clean 2>/dev/null || true
git config --local --unset filter.lfs.smudge 2>/dev/null || true
find . -name ".gitattributes" -delete 2>/dev/null || true

# Ensure quantlab-bot remote is configured
git remote set-url origin https://github.com/abhishekjs0/quantlab-bot.git 2>/dev/null || \
    git remote add origin https://github.com/abhishekjs0/quantlab-bot.git 2>/dev/null || true

# Set main branch
git branch -M main 2>/dev/null || true
```

#### Phase 8: Git Staging and Commit
Stage all changes and create comprehensive commit:

```bash
# Stage all changes
git add .

# Create commit if changes exist
if ! git diff --cached --quiet; then
    git commit -m "chore: end-of-session repository maintenance and cleanup

CLEANUP APPLIED:
- Removed temporary development files and duplicates
- Cleaned experimental strategies and obsolete tests
- Removed old scripts and analysis files
- Applied modern code formatting (Black, isort, Ruff)
- Cleaned system cache and build artifacts
- Fixed git configuration issues

REPOSITORY STATUS:
- All temporary files removed
- Code quality standards applied
- Clean architecture maintained
- Ready for next development session"
else
    echo "ℹ️  Repository already clean - no changes to commit"
fi
```

#### Phase 9: GitHub Deployment
Push changes to production repository:

```bash
# Push to GitHub
git push -u origin main

if [ $? -eq 0 ]; then
    echo "✅ Successfully deployed to GitHub"
    echo "📍 Repository: https://github.com/abhishekjs0/quantlab-bot.git"
else
    echo "⚠️  Push failed - checking connectivity and permissions"
    git ls-remote origin main >/dev/null 2>&1 && \
    git push --force-with-lease origin main || \
    echo "❌ Deployment failed - manual intervention may be required"
fi
```

#### Phase 10: Post-Deployment Verification
Verify cleanup was successful:

```bash
# Display git status
echo "🔍 Repository Status:"
git status

echo ""
echo "📊 Latest commits:"
git log --oneline -3

echo ""
echo "🔗 Remote configuration:"
git remote -v

echo ""
echo "✅ Repository cleanup complete"
echo "📍 Production: https://github.com/abhishekjs0/quantlab-bot.git"
```

---

## 📋 Production File Structure (What Should Remain)

### Root Level
```
✅ Keep:
- config.py (system configuration)
- pyproject.toml (project metadata and dependencies)
- Makefile (build automation)
- README.md (system documentation)
- CHANGELOG.md (version history)
- .gitignore (git exclusions)

❌ Remove:
- *_SUMMARY.md, *_REPORT.md files from development
- run_backtest.sh (use runners/run_basket.py instead)
```

### Core Directories
```
✅ Keep:
- core/ (backtesting engine)
- strategies/ (trading strategies)
- utils/ (technical indicators)
- data/ (market data and baskets)
- viz/ (visualization - only dashboard.py)
- runners/ (execution orchestration)
- tests/ (test suite)
- scripts/ (utility scripts)
- examples/ (example implementations)
- docs/ (essential documentation only)
```

### Docs Directory (Essential Only)
```
✅ Keep:
- BACKTEST_GUIDE.md (includes methodology and validation)
- CODING_STANDARDS.md
- DEVELOPMENT_WORKFLOW.md
- INDEX.md
- QUANTLAB_GUIDE.md
- WORKFLOW_GUIDE.md
- STARTUP_PROMPT.md
- JANITOR_PROMPT.md
- api/ (Sphinx documentation)

❌ Remove (consolidate into primary docs):
- BACKTEST_INVESTIGATION_AND_NAN_ANALYSIS.md
- BACKTEST_METHODOLOGY.md
- INVESTIGATION_DOCUMENTATION_INDEX.md
- All *_SUMMARY.md, *_REPORT.md investigation files
```

---

## 📚 Documentation Consolidation (NEW)

### Primary Documentation Files (Keep Only These 5)
```
1. docs/DHAN_COMPREHENSIVE_GUIDE.md
2. docs/BACKTEST_GUIDE.md
3. docs/QUANTLAB_GUIDE.md
4. docs/STARTUP_PROMPT.md
5. docs/STRATEGIES.md
```

### Consolidation Task
When running full janitor cleanup:

1. **Audit all .md files** in root and docs/ directories
   - Identify secondary documentation files (not in the 5 primary)
   - Map content to appropriate primary documentation
   - Ensure no critical information is lost

2. **Consolidate secondary documentation** into primary files
   - BACKTEST_ISSUES_ANALYSIS.md → BACKTEST_GUIDE.md
   - CANDLESTICK_PATTERNS_V2.md → STRATEGIES.md
   - CONSOLIDATION_COMPLETE.md → QUANTLAB_GUIDE.md
   - DEVELOPMENT_WORKFLOW.md → STARTUP_PROMPT.md
   - KAMA_STRATEGY.md → STRATEGIES.md
   - STRATEGY_FIXES_SUMMARY.md → STRATEGIES.md
   - TRADINGVIEW_ANALYSIS.md → BACKTEST_GUIDE.md
   - INDEX.md → QUANTLAB_GUIDE.md (merge content)
   - All *_SUMMARY.md, *_REPORT.md, *_ANALYSIS.md → appropriate primary

3. **Delete all secondary .md files** after consolidation
   - Keep only the 5 primary documentation files
   - No other .md files should exist in docs/

4. **Clean up test and debug scripts**
   - Remove: test_*.py, debug_*.py, *_debug.py files
   - Keep: Only integration tests in tests/ directory
   - Remove root-level debug scripts

5. **Code optimization pass**
   - Review key files for opportunities to make code more concise
   - Maintain all functionality while reducing line count where possible
   - Focus on: runners/run_basket.py, core/engine.py, core/strategy.py

6. **Update primary documentation**
   - Reflect current repository state in all 5 docs
   - Update examples to match current code
   - Ensure all API references are current
   - Add any new features documented in secondary files

---

## 🎯 How to Use This Prompt

### For AI Agents at Session End
```
Execute the comprehensive repository cleanup:
1. Remove all temporary development files
2. Clean test and strategy directories
3. Apply code quality standards
4. Consolidate documentation into 5 primary files
5. Clean up debug and test scripts
6. Commit all changes with clear message
7. Push to GitHub quantlab-bot repository
No summaries or verbose output needed - just execute silently.
```

### For Documentation Consolidation Only
```
To consolidate documentation without full cleanup:
1. Review all .md files in docs/ and root
2. Map secondary documentation to 5 primary files
3. Merge content into appropriate primary docs
4. Delete secondary .md files
5. Update primary docs to reflect current state
6. Commit changes with message: "docs: consolidate into 5 primary documentation files"
```

---

## ✅ Verification Checklist

After running janitor cleanup, verify:

- [ ] No `*_comparison*.py` or `*_debug*.py` files remain
- [ ] No experimental strategies in `strategies/` directory
- [ ] No old test files in `tests/` directory
- [ ] No `__pycache__`, `.pyc`, or `.DS_Store` files present
- [ ] All code formatted with Black (88-char)
- [ ] All imports organized with isort
- [ ] Git remote points to `quantlab-bot`
- [ ] All changes committed with descriptive message
- [ ] Successfully pushed to GitHub
- [ ] `git status` shows "nothing to commit"

---

## 📊 Repository Health After Cleanup

**Expected State:**
- ✅ Clean directory structure
- ✅ No temporary files
- ✅ Modern code formatting applied
- ✅ All changes tracked in git
- ✅ Production-ready codebase
- ✅ GitHub synchronized

---

**Last Updated**: November 8, 2025
**Repository**: https://github.com/abhishekjs0/quantlab-bot.git
**Version**: v2.3
