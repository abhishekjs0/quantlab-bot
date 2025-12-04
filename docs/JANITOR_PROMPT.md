# QuantLab Janitor Prompt v2.5

**Updated**: December 4, 2025  
**Purpose**: End-of-session cleanup, testing, and commit workflow

---

## ⚠️ CRITICAL RULE

**NEVER commit if tests fail!** Fix issues first, then commit.

---

## 🧹 Phase 1: Cleanup Temporary Files

```bash
cd /Users/abhishekshah/Desktop/quantlab-workspace

# Remove debug/test scripts from root
rm -f debug_*.py test_*.py demo_*.py *_comparison*.py *_analysis*.py
rm -f run_*.sh *.sh
rm -f *_REPORT.txt *_SUMMARY.txt *.log

# Remove Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -name "*.pyo" -delete 2>/dev/null || true

# Remove system files
find . -name ".DS_Store" -delete 2>/dev/null || true

# Remove pytest/coverage artifacts
rm -rf .pytest_cache/ htmlcov/ .coverage 2>/dev/null || true
```

---

## ✅ Phase 2: Verify Cleanup

```bash
echo "=== CLEANUP VERIFICATION ==="

# Check for remaining temp files
echo "Checking for temp files..."
ls *.py *.sh *.log 2>/dev/null | grep -E "debug|test_|demo_|comparison" && \
  echo "⚠️  TEMP FILES FOUND - Delete them!" || echo "✅ No temp files"

# Check __pycache__
echo ""
echo "Checking for cache..."
find . -type d -name "__pycache__" | wc -l | xargs -I {} bash -c '[ {} -eq 0 ] && echo "✅ No cache" || echo "⚠️  Cache found"'

# Show git status
echo ""
echo "Git status:"
git status --short | head -10
```

---

## 🧪 Phase 3: Run Test Suite (MANDATORY)

```bash
echo "=== RUNNING TESTS ==="
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -30

echo ""
echo "Expected: 88 passed, 14 skipped, 0 failed"
echo ""
echo "⚠️  DO NOT PROCEED IF TESTS FAIL!"
```

### If Tests Fail:
1. Read error messages carefully
2. Fix the code/tests
3. Re-run: `python3 -m pytest tests/ -v`
4. Only proceed when all tests pass

---

## 💅 Phase 4: Code Quality (Optional)

```bash
# Format code
black . --quiet 2>/dev/null || true
isort . --quiet 2>/dev/null || true
ruff check --fix . 2>/dev/null || true
```

---

## 📦 Phase 5: Git Commit

```bash
# Stage changes
git add .

# Check what's staged
git status

# Commit with descriptive message
git commit -m "chore: session cleanup and maintenance

- [List specific changes made this session]
- Tests: 88 passed, 14 skipped
- Code quality: Applied Black/isort/ruff"
```

### Commit Message Guidelines:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation
- `chore:` - Maintenance
- `refactor:` - Code restructure

---

## 🚀 Phase 6: Push (Only When Requested)

```bash
# Only run when user explicitly requests push
git push origin main
```

---

## ✅ Phase 7: Final Verification

```bash
echo "=== FINAL STATUS ==="
git status
echo ""
git log --oneline -3
echo ""
echo "✅ Session complete"
```

---

## 📋 Quick Reference: What to Keep vs Delete

### ✅ KEEP (Production Files)
```
Root:
  config.py, pyproject.toml, Makefile, README.md, CHANGELOG.md, requirements.txt

Directories:
  core/, strategies/, runners/, utils/, data/, tests/, docs/, viz/
  brokers/, webhook-service/, scripts/, cache/

docs/:
  QUANTLAB_GUIDE.md, BACKTEST_GUIDE.md, STRATEGIES.md
  STARTUP_PROMPT.md, JANITOR_PROMPT.md
  WEBHOOK_SERVICE_COMPLETE_GUIDE.md, DHAN_COMPREHENSIVE_GUIDE.md
  README.md, TRADINGVIEW_POST.md
```

### ❌ DELETE (Temporary Files)
```
Patterns:
  debug_*.py, test_*.py (in root), demo_*.py
  *_comparison*.py, *_analysis*.py
  *.sh (in root), *.log, *_REPORT.txt
  __pycache__/, .pytest_cache/, htmlcov/
```

---

## 🚨 Common Mistakes to Avoid

1. **Committing temp files**: Always run Phase 1 cleanup FIRST
2. **Pushing with failing tests**: NEVER push if tests fail
3. **Forgetting to stage**: Run `git status` before commit
4. **Unclear commit messages**: Be specific about what changed
5. **Force pushing**: Avoid `--force` unless absolutely necessary

---

## 🔧 Emergency Fixes

### Accidentally Committed Temp Files
```bash
git reset HEAD~1  # Undo last commit (keeps changes)
rm -f [temp_files]
git add .
git commit -m "correct message"
```

### Committed But Not Pushed
```bash
git commit --amend -m "new message"  # Fix last commit message
```

### Tests Broken After Changes
```bash
git stash          # Save changes temporarily
git checkout .     # Revert to last commit
pytest tests/ -v   # Verify tests pass
git stash pop      # Restore changes
# Fix the issue, then commit
```
