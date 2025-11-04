# QuantLab Repository Janitor - Final Cleanup Prompt

**For AI Agents**: Use this prompt at the end of each development session to perform comprehensive repository cleanup and commit all changes to GitHub.

---

## 🧹 COMPREHENSIVE CLEANUP EXECUTION PROMPT

### Objective
Execute a complete repository maintenance cycle that removes all temporary files, applies code quality standards, and commits changes to GitHub with a clear audit trail.

### Execution Steps

#### Phase 1: Development File Cleanup
Remove all temporary development artifacts:

```bash
rm -f *_comparison*.py *_comparison*.md
rm -f *_debug*.py *_analysis*.py
rm -f test_wrapper_*.py test_simple_*.py test_final_*.py
rm -f demo_*.py *_vs_*.py
rm -f *_analysis.md portfolio_comparison*.md multi_timeframe_analysis.md
rm -f data/basket_test_*.txt data/*_test_*.txt
rm -f tests/test_*_old.py tests/test_*_backup.py tests/test_duplicate_*.py tests/*_experimental.py

# 🚫 DELETE ALL SUMMARY DOCUMENTS (Created during sessions, deleted at end)
rm -f SESSION_SUMMARY.md
rm -f STRATEGY_COMPARISON.md
rm -f DEPLOYMENT_CHECKLIST.md
rm -f PROFIT_FACTOR_ANALYSIS.md
rm -f WARNINGS_AND_WINDOWS_RESOLUTION.md
rm -f *_SESSION*.md
rm -f *_ANALYSIS*.md
rm -f *_COMPARISON*.md
```

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
# - scripts/universal_indicator_analysis.py
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
- DASHBOARD_FIXES.md
- generate_updated_dashboard.py
- git_cleanup_commands.sh
- HYGIENE_CHECK_REPORT.md
- JANITOR_FINAL_PROMPT.md (this file - only for reference)
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

### Viz Directory (Cleaned)
```
✅ Keep:
- __init__.py
- dashboard.py (production dashboard only)

❌ Remove:
- dashboard_broken.py
- equity_plot.py
- bokeh_charts.py
- heatmap.py
- tv_plot.py
- README.md
```

### Docs Directory (Essential Only)
```
✅ Keep:
- BACKTEST_GUIDE.md
- CODING_STANDARDS.md
- DEVELOPMENT_WORKFLOW.md
- INDEX.md
- QUANTLAB_GUIDE.md
- WORKFLOW_GUIDE.md
- api/ (Sphinx documentation)

❌ Remove:
- ARCHITECTURE_REFACTOR_PLAN.md
- DASHBOARD_VISUALIZATION_SPEC.md (consolidated in README)
- DHAN_DATA_FETCHING_GUIDE.md
- ICHIMOKU_FILTERS_GUIDE.md
- TREND_VOLATILITY_CLASSIFICATION.md
- REPO_JANITOR_ENHANCED.md
- REPO_JANITOR_ENHANCED.md.backup
```

---

## 🎯 How to Use This Prompt

### For AI Agents at Session End
```
"Execute the comprehensive repository cleanup using the JANITOR_FINAL_PROMPT.md:
1. Remove all temporary development files
2. Clean test and strategy directories
3. Apply code quality standards
4. Commit all changes with clear message
5. Push to GitHub quantlab-bot repository
No summaries or verbose output needed - just execute silently."
```

### Integration with Session Workflow
- **Start of Session**: Fresh checkout from GitHub
- **During Session**: Develop features, run tests, iterate
- **End of Session**: Execute this janitor prompt
- **Deployment**: Automatic push to GitHub

### Example Command
```bash
#!/bin/bash
# Run at end of session
cd /path/to/quantlab-workspace

# Execute all cleanup phases
source <(curl -s https://raw.github.com/abhishekjs0/quantlab-bot/main/JANITOR_FINAL_PROMPT.md)

# Or manually run the phases listed above
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

**Size Reduction:**
- Typical session cleanup: 5-50MB (temporary files)
- Cache removal: 10-100MB (Python cache)
- Total repository remains <500MB

---

## 🚀 Automation Integration

### GitHub Actions Hook
Add to CI/CD to auto-cleanup on PR merge:

```yaml
# .github/workflows/janitor.yml
name: Repository Janitor
on:
  push:
    branches: [main]

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Execute janitor cleanup
        run: |
          # Run cleanup phases from this prompt
          find . -name "*.pyc" -delete
          find . -type d -name "__pycache__" -exec rm -rf {} +
          git config user.email "bot@quantlab.io"
          git config user.name "QuantLab Bot"
          git add .
          git commit -m "chore: automated janitor cleanup" || true
          git push
```

### Local Pre-Commit Hook
Save as `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Auto-cleanup before commit
find . -name "*.pyc" -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
git add .
```

---

## 📞 Troubleshooting

### Push Fails with Git-LFS Errors
```bash
# Fix git-lfs configuration
git config --local --unset filter.lfs.process
git config --local --unset filter.lfs.required
find . -name ".gitattributes" -delete
git add .
git commit -m "fix: remove git-lfs configuration"
git push -u origin main
```

### Repository Not Found
```bash
# Verify repository exists
git ls-remote origin main

# If not found, create on GitHub first
# Then update remote
git remote set-url origin https://github.com/abhishekjs0/quantlab-bot.git
git push -u origin main
```

### Permission Denied on Push
```bash
# Check SSH configuration
ssh -T git@github.com

# Or use HTTPS token authentication
git config credential.helper store
git push origin main
```

---

## 📝 Notes

- This prompt consolidates all repository maintenance logic
- No summaries or detailed reports - execution focused
- Designed for AI agents to run at session end
- Safe to run multiple times - idempotent operations
- All commits to quantlab-bot repository tracked in git history

---

**Last Updated**: November 3, 2025  
**Repository**: https://github.com/abhishekjs0/quantlab-bot.git  
**Version**: v2.2 Final
