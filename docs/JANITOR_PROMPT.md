# QuantLab Janitor Prompt v3.0

**Updated**: December 4, 2025  
**Purpose**: End-of-session cleanup, testing, and commit workflow

---

## ⚠️ CRITICAL RULES

1. **NEVER commit if tests fail!** Fix issues first, then commit.
2. **NEVER push without explicit user request.**
3. **Run ALL phases in order** - don't skip steps.

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
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true

# Remove system files
find . -name ".DS_Store" -delete 2>/dev/null || true

# Remove pytest/coverage artifacts
rm -rf .pytest_cache/ htmlcov/ .coverage 2>/dev/null || true

# Remove empty directories in reports (keep structure)
find reports/ -type d -empty -delete 2>/dev/null || true
```

---

## ✅ Phase 2: Verify Cleanup

```bash
echo "=== CLEANUP VERIFICATION ==="

# Check for remaining temp files in root
echo "Checking for temp files in root..."
ls *.py 2>/dev/null | grep -v "^config.py$" && echo "⚠️  Unexpected .py files in root!" || echo "✅ No temp .py files"

# Check for shell scripts
ls *.sh 2>/dev/null && echo "⚠️  Shell scripts in root!" || echo "✅ No shell scripts"

# Check __pycache__
echo ""
echo "Checking for cache..."
CACHE_COUNT=$(find . -type d -name "__pycache__" 2>/dev/null | wc -l | tr -d ' ')
[ "$CACHE_COUNT" -eq 0 ] && echo "✅ No __pycache__ dirs" || echo "⚠️  Found $CACHE_COUNT cache dirs"

# Show git status summary
echo ""
echo "Git status:"
git status --short | head -15
```

---

## 🧪 Phase 3: Run Test Suite (MANDATORY)

```bash
echo "=== RUNNING TESTS ==="

# Run tests with short traceback
python3 -m pytest tests/ -v --tb=short \
  --ignore=tests/test_integration_basket.py \
  --ignore=tests/test_parity_basket.py \
  2>&1 | tail -40

echo ""
echo "Expected: ~66 passed, ~8 skipped, 0 failed"
echo ""
echo "⚠️  DO NOT PROCEED IF TESTS FAIL!"
```

### If Tests Fail:
1. Read error messages carefully
2. Check if it's an import error (missing dependency)
3. Check if it's a renamed file/class not updated
4. Fix the code/tests
5. Re-run: `python3 -m pytest tests/ -v`
6. **Only proceed when all tests pass**

---

## 🔍 Phase 4: Strategy Validation

```bash
echo "=== STRATEGY VALIDATION ==="

# Verify all strategies import correctly
python3 -c "
from strategies import *
import strategies
import pkgutil
for importer, name, ispkg in pkgutil.iter_modules(strategies.__path__):
    if not name.startswith('_'):
        mod = __import__(f'strategies.{name}', fromlist=[name])
        classes = [c for c in dir(mod) if not c.startswith('_') and c[0].isupper()]
        print(f'✅ {name}: {classes}')
"

# Check for unauthorized imports (should use utils.indicators)
echo ""
echo "Checking for unauthorized indicator imports..."
grep -rn "^import ta$\|^from ta import\|^import talib" strategies/*.py && \
  echo "⚠️  Found unauthorized imports!" || echo "✅ All strategies use utils.indicators"
```

---

## 💅 Phase 5: Code Quality (Optional)

```bash
# Only if black/isort/ruff are installed
which black >/dev/null 2>&1 && black . --quiet --check || echo "black not installed"
which isort >/dev/null 2>&1 && isort . --quiet --check-only || echo "isort not installed"
which ruff >/dev/null 2>&1 && ruff check . --quiet || echo "ruff not installed"
```

---

## 📦 Phase 6: Git Commit

```bash
# Stage all changes
git add -A

# Review what's staged
echo "=== STAGED CHANGES ==="
git diff --cached --stat

# Commit with descriptive message
git commit -m "chore: session cleanup and maintenance

- [List specific changes made this session]
- Tests: 66 passed, 8 skipped
- Strategies validated: all import correctly"
```

### Commit Message Prefixes:
| Prefix | Use For |
|--------|---------|
| `feat:` | New feature |
| `fix:` | Bug fix |
| `docs:` | Documentation |
| `chore:` | Maintenance |
| `refactor:` | Code restructure |
| `cleanup:` | Removing dead code |
| `test:` | Test updates |

---

## 🚀 Phase 7: Push (Only When Requested)

```bash
# ONLY run when user explicitly requests push
git push origin main
```

---

## ✅ Phase 8: Final Verification

```bash
echo "=== FINAL STATUS ==="
git status
echo ""
echo "Recent commits:"
git log --oneline -5
echo ""
echo "Current branch:"
git branch --show-current
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
  brokers/, webhook-service/, scripts/, cache/, reports/

docs/:
  STARTUP_PROMPT.md, JANITOR_PROMPT.md
  BACKTEST_GUIDE.md, WRITING_STRATEGIES.md

webhook-service/docs/:
  WEBHOOK_SERVICE_GUIDE.md, DHAN_CREDENTIALS_GUIDE.md
```

### ❌ DELETE (Temporary Files)
```
Patterns in root:
  debug_*.py, test_*.py, demo_*.py
  *_comparison*.py, *_analysis*.py
  *.sh, *.log, *_REPORT.txt, *_SUMMARY.txt

Anywhere:
  __pycache__/, .pytest_cache/, htmlcov/, .coverage
  .DS_Store
```

---

## 🚨 Common Mistakes to Avoid

1. **Committing temp files**: Always run Phase 1 cleanup FIRST
2. **Pushing with failing tests**: NEVER push if tests fail
3. **Forgetting to stage**: Run `git status` before commit
4. **Unclear commit messages**: Be specific about what changed
5. **Force pushing**: Avoid `--force` unless absolutely necessary
6. **Skipping strategy validation**: Can break backtest runs

---

## 🔧 Emergency Fixes

### Accidentally Committed Temp Files
```bash
git reset HEAD~1  # Undo last commit (keeps changes)
rm -f [temp_files]
git add -A
git commit -m "correct message"
```

### Committed But Not Pushed - Fix Message
```bash
git commit --amend -m "new message"
```

### Tests Broken After Changes
```bash
git stash          # Save changes temporarily
git checkout .     # Revert to last commit
pytest tests/ -v   # Verify tests pass
git stash pop      # Restore changes
# Fix the issue, then commit
```

### Undo Last Push (DANGEROUS)
```bash
# Only if you're the only one using the repo!
git reset --hard HEAD~1
git push --force origin main
```

---

## 📊 Health Checks

### Check Token Status
```bash
curl -s https://tradingview-webhook-cgy4m5alfq-el.a.run.app/health | python3 -m json.tool
```

### Check Recent Cloud Run Errors
```bash
gcloud logging read 'resource.type="cloud_run_revision" AND severity>=ERROR' \
  --project=tradingview-webhook-prod --limit=5 --format='table(timestamp,textPayload)'
```

### Verify Data Cache
```bash
echo "Cached data files:"
ls data/cache/*.csv 2>/dev/null | wc -l
echo "Most recent cache update:"
ls -lt data/cache/*.csv 2>/dev/null | head -1
```
