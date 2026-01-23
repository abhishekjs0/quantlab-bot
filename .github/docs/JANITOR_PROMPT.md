# QuantLab Janitor Prompt v3.2

**Updated**: January 8, 2026  
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

# Remove grid search and optimization scripts (regenerate as needed)
rm -f grid_search*.py grid_search*.csv mfe_analysis*.csv

# Remove duplicate documentation files (keep consolidated docs/ versions)
rm -f *_FILTERS*.md *_IMPLEMENTATION*.md *_CHECKLIST*.md *_VERIFICATION*.md

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
# Simple verification - run each command separately
git status --short | head -15
```

If you see unexpected files, investigate manually. The cleanup in Phase 1 should handle most cases.

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

## ⚠️ Phase 5b: Check Terminal Warnings

```bash
echo "=== CHECKING FOR WARNINGS ==="

# Run tests and capture warnings
python3 -m pytest tests/ -v --tb=short \
  --ignore=tests/test_integration_basket.py \
  --ignore=tests/test_parity_basket.py 2>&1 | grep -i "warning\|deprecat" | head -20
```

### Known Acceptable Warnings:
- **Python 3.9 EOL**: Environment issue - upgrade Python when possible
- **urllib3 LibreSSL**: macOS system SSL - not a code issue
- **core.optimizer not found**: Expected - module not yet implemented
- **Plotting 'Close' warning**: Test fixture, non-critical

### Warnings That Need Action:
- DeprecationWarning in YOUR code (not dependencies)
- FutureWarning about APIs you're using directly
- Any import errors or missing modules you expect to exist

---

## 🔄 Phase 6a: Check GitHub CI Status (MANDATORY)

Before committing, check if there are any failing CI runs:

```bash
echo "=== CHECKING GITHUB CI STATUS ==="

# Use gh CLI (preferred)
gh run list --limit 5 --repo abhishekjs0/quantlab-bot
```

**Note**: If `gh` CLI is not installed, install it with `brew install gh` and authenticate with `gh auth login`.

### Common CI Errors to Fix:

1. **pyproject.toml errors** (setuptools/license issues):
   - Update `license = "MIT"` (not `{text = "MIT"}`)
   - Add `[tool.setuptools.packages.find]` to explicitly list packages
   - Remove deprecated license classifiers

2. **Python version errors** (escaped `\$` in matrix):
   - Check `.github/workflows/ci.yml` for `\${{ matrix.python-version }}`
   - Should be `${{ matrix.python-version }}`

3. **Import errors** in tests:
   - Ensure all modules have `__init__.py`
   - Check PYTHONPATH is set correctly

4. **Strategy key mismatches**:
   - Engine expects `qty` not `position` in state
   - Strategy returns must use exact keys (`stop` not `stop_price`)

### Fix CI errors BEFORE committing new changes!

---

## 📦 Phase 6b: Git Commit

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

## 📝 Phase 9: Update Existing Documentation (MANDATORY)

**Purpose**: Keep all documentation current with the actual state of the codebase. Review chat history and terminal output from the session to identify what needs updating.

### Documents to Review and Update:

| Document | What to Update |
|----------|----------------|
| `README.md` | Version, features, architecture diagrams, quick start commands |
| `docs/STARTUP_PROMPT.md` | Current Cloud Run revision, cron schedules, token status, active strategies |
| `docs/JANITOR_PROMPT.md` | New common issues, CI fixes, cleanup patterns |
| `docs/BACKTEST_GUIDE.md` | New backtest commands, parameters, examples |
| `docs/WRITING_STRATEGIES.md` | Strategy patterns, filter usage, state keys |
| `reports/README.md` | Report structure, metrics explanations |
| `webhook-service/docs/WEBHOOK_SERVICE_GUIDE.md` | Endpoints, notification format, deployment |
| `webhook-service/docs/DHAN_CREDENTIALS_GUIDE.md` | Token refresh, API changes |

### What to Update in Each:

1. **STARTUP_PROMPT.md** - Should reflect current repo state:
   - Cloud Run revision number (e.g., `tradingview-webhook-00043-vsh`)
   - Cron job times (8AM/8PM IST)
   - Active strategy configurations
   - Telegram notification format

2. **WRITING_STRATEGIES.md** - Code patterns:
   - State key names (use `qty` not `position`)
   - Return key names (use `stop` not `stop_price`)
   - Filter usage examples

3. **WEBHOOK_SERVICE_GUIDE.md** - Service details:
   - Current notification format
   - AMO timing defaults
   - Endpoint behaviors

### Update Process:

1. Review terminal history for commands run
2. Review chat history for changes made
3. Check each doc for outdated information
4. Update values, examples, and references
5. Update "Last Updated" dates where present

### Important:
- Focus on CURRENT STATE, not change history
- Don't document what changed - document what IS
- Keep docs concise and accurate
- Remove outdated examples/values

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

---

## 🔧 Fix Terminal Warnings During Session

During the session, watch for and fix these common warnings:

### Python Deprecation Warnings
```
# typing.Dict, typing.List deprecated
# Fix: Use dict, list instead of Dict, List

# asyncio.TimeoutError deprecated
# Fix: Use TimeoutError instead

# Optional[X] deprecated
# Fix: Use X | None instead
```

### Strategy State Issues
```
# state.get("position", 0) - WRONG!
# Fix: state.get("qty", 0) - engine uses "qty"

# Return {"stop_price": x} - WRONG!
# Fix: Return {"stop": x} - engine expects "stop"
```

### Package/Import Issues
```
# Multiple top-level packages discovered
# Fix: Add [tool.setuptools.packages.find] to pyproject.toml

# License classifiers deprecated
# Fix: Use license = "MIT" (string, not table)
```
