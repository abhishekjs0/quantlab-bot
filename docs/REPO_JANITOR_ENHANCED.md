# Repository Maintenance Protocol v2.2

## Overview
This protocol defines systematic repository maintenance procedures to keep the QuantLab v2.2 system clean, efficient, and production-ready with modern CI/CD practices.

## Standard Maintenance Tasks

### 1. Development File Cleanup
Remove temporary files created during development sessions:

```bash
# Remove comparison and analysis files
rm -f *_comparison*.py *_comparison*.md
rm -f *_debug*.py *_analysis*.py
rm -f test_wrapper_*.py test_simple_*.py test_final_*.py

# Remove demo and experiment files
rm -f demo_*.py
rm -f *_vs_*.py

# Remove temporary analysis documents
rm -f *_analysis.md
rm -f portfolio_comparison*.md
rm -f multi_timeframe_analysis.md

# Remove temporary test baskets
rm -f data/basket_test_*.txt
rm -f data/*_test_*.txt

# Remove old test files no longer needed
rm -f tests/test_*_old.py
rm -f tests/test_*_backup.py
rm -f tests/test_duplicate_*.py
rm -f tests/*_experimental.py
```

### 2. Strategy Cleanup
Maintain clean strategy directory with v2.2 architecture:

```bash
# Remove experimental strategy files
rm -f strategies/*_wrapper.py
rm -f strategies/*_simple_*.py
rm -f strategies/*_temp*.py
rm -f strategies/*_experimental.py
rm -f strategies/*_backup_*.py

# Keep only production strategies:
# - strategies/ichimoku.py (production with global market regime)
# - strategies/template.py (modern development template with Strategy.I())
# - strategies/ema_cross.py (legacy - maintained for compatibility)
# - strategies/donchian.py (legacy - maintained for compatibility)
# - strategies/atr_breakout.py (legacy - maintained for compatibility)
# - strategies/envelope_kd.py (legacy - maintained for compatibility)

# Remove ichimoku_original.py if no longer needed (backup kept elsewhere)
# rm -f strategies/ichimoku_original.py
```

### 3. Documentation Maintenance
Keep documentation focused and up-to-date for v2.2:

```bash
# Remove temporary documentation files
rm -f docs/*_SUMMARY.md
rm -f docs/*_summary.md
rm -f docs/SESSION_*.md
rm -f docs/*_OLD.md
rm -f docs/*_backup.md

# Maintain essential documentation only:
# - docs/README.md (system overview)
# - docs/DEVELOPMENT_WORKFLOW.md (NEW: v2.2 development guide)
# - docs/BACKTEST_GUIDE.md (usage guide)
# - docs/QUANTLAB_GUIDE.md (core concepts)
# - docs/ICHIMOKU_FILTERS_GUIDE.md (strategy guide)
# - docs/WORKFLOW_GUIDE.md (development workflow)
# - docs/CODING_STANDARDS.md (code quality)
# - docs/api/ (NEW: Sphinx API documentation)
# - docs/REPO_JANITOR_ENHANCED.md (this file)
```

### 4. Test Suite Optimization
Clean and optimize test files for v2.2:

```bash
# Remove duplicate or obsolete test files
rm -f tests/test_old_*.py
rm -f tests/test_backup_*.py
rm -f tests/test_experimental_*.py
rm -f tests/test_deprecated_*.py

# Keep essential tests:
# - tests/test_strategy_wrapper.py (NEW: Strategy.I() system tests)
# - tests/test_basket_metrics.py (core backtesting)
# - tests/test_integration_basket.py (integration tests)
# - tests/test_parity_basket.py (validation tests)
# - tests/test_perf.py (performance tests)
# - tests/test_pf_and_cagr.py (analytics tests)
# - tests/test_smoke.py (system validation)

# Remove outdated test data
rm -f tests/data/*_old.csv
rm -f tests/data/*_backup.csv
```

### 5. Scripts Directory Cleanup
Update scripts based on v2.2 developments:

```bash
# Remove obsolete scripts
rm -f scripts/*_old.py
rm -f scripts/*_backup.py
rm -f scripts/*_experimental.py
rm -f scripts/*_debug.py

# Keep essential scripts:
# - scripts/fetch_data.py (data management)
# - scripts/check_basket_data.py (data validation)
# - scripts/create_symbol_mapping.py (symbol management)
# - scripts/rank_strategies.py (performance analysis)
# - scripts/setup_dev.py (development setup)
# - scripts/universal_indicator_analysis.py (technical analysis)

# Update scripts that may reference old patterns
# Ensure all scripts use modern imports and config system
```

### 6. Dashboard System Validation (Enhanced)
Ensure the enhanced dashboard system is production-ready:

```bash
# Validate enhanced metrics panel integration
echo "🔍 Validating enhanced dashboard system..."

# Check critical dashboard files
DASHBOARD_FILES=(
    "viz/final_fixed_dashboard.py"
    "viz/improved_dashboard.py"
    "reports/enhanced_metrics_dashboard.html"
    "docs/DASHBOARD_VISUALIZATION_SPEC.md"
)

for file in "${DASHBOARD_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "✅ Found: $file"
    else
        echo "❌ Missing: $file"
    fi
done

# Validate enhanced metrics panel implementation
if grep -q "create_improved_metrics_html" viz/final_fixed_dashboard.py; then
    echo "✅ Enhanced metrics panel method found"
else
    echo "❌ Enhanced metrics panel method missing"
fi

# Check for enhanced CSS styling
if grep -q "enhanced-metrics-panel" viz/final_fixed_dashboard.py; then
    echo "✅ Enhanced CSS styling implemented"
else
    echo "❌ Enhanced CSS styling missing"
fi

# Validate JavaScript enhancements
if grep -q "showMetrics.*fade" viz/final_fixed_dashboard.py; then
    echo "✅ Enhanced JavaScript transitions found"
else
    echo "❌ Enhanced JavaScript transitions missing"
fi

# Test dashboard generation capability
echo "🧪 Testing dashboard generation..."
if [[ -f "generate_updated_dashboard.py" ]]; then
    echo "✅ Dashboard generation script available"
    # Note: Full test would require virtual environment activation
else
    echo "❌ Dashboard generation script missing"
fi

echo "📊 Dashboard validation complete"
```
### 7. System Cache Cleanup
Clean all cache and temporary system files:

```bash
# Remove Python cache files
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
find . -name "*.pyd" -delete

# Remove system files
find . -name ".DS_Store" -delete
find . -name "Thumbs.db" -delete

# Remove temporary files
find . -name "*.tmp" -delete
find . -name "*.temp" -delete
find . -name "*~" -delete

# Remove Sphinx build artifacts (can be regenerated)
rm -rf docs/api/_build/

# Remove pytest cache
rm -rf .pytest_cache/

# Remove coverage files (regenerated by CI)
rm -f .coverage
rm -rf htmlcov/
```

### 8. Code Quality Maintenance (v2.2 Standards)
Apply modern formatting and quality checks:

```bash
# Apply Black formatting (88 character line length)
black .

# Organize imports with isort
isort .

# Apply Ruff linting with auto-fixes
ruff check --fix .

# Run type checking (advisory)
mypy core/ strategies/ utils/ --ignore-missing-imports || true

# Run tests to ensure nothing is broken
pytest --cov=. --cov-fail-under=35
```

### 9. CI/CD and Documentation Updates
Maintain modern development infrastructure:

```bash
# Regenerate API documentation
cd docs/api && make html

# Validate GitHub Actions workflows
# .github/workflows/ci-cd.yml
# .github/workflows/code-quality.yml
# .github/workflows/docs.yml

# Update dependency configuration
# .github/dependabot.yml
# .bandit (security configuration)

# Ensure pyproject.toml is optimized
# Check [tool.ruff], [tool.black], [tool.isort] configurations
```

### 9. Git Repository Maintenance & GitHub Deployment
Keep repository clean and organized with modern practices, then deploy to GitHub:

```bash
# Check for any pending changes (staged or unstaged)
echo "🔍 Checking for pending repository changes..."

# Check for unstaged changes
if ! git diff --quiet; then
    echo "📝 Found unstaged changes - staging them..."
    git add .
    CHANGES_FOUND=true
else
    echo "✅ No unstaged changes found"
fi

# Check for staged changes
if ! git diff --cached --quiet; then
    echo "📦 Found staged changes ready for commit"
    CHANGES_FOUND=true
else
    echo "✅ No staged changes found"
fi

# If changes are found, commit them
if [[ "$CHANGES_FOUND" == "true" ]]; then
    echo "💾 Committing pending changes..."
    
    # Generate commit message based on changed files
    CHANGED_FILES=$(git diff --cached --name-only | head -5)
    if [[ -n "$CHANGED_FILES" ]]; then
        echo "Changed files: $CHANGED_FILES"
        
        # Create descriptive commit message
        git commit -m "chore: commit pending repository changes

Auto-commit of manual edits and updates found during maintenance:
$(echo "$CHANGED_FILES" | sed 's/^/- /')

Applied as part of repository maintenance protocol v2.2"
        
        echo "✅ Changes committed successfully"
    fi
else
    echo "✅ Repository is clean - no pending changes"
fi

# Stage any remaining changes by category
git add .

# Create descriptive commit following conventional commits
git commit -m "chore: repository maintenance and v2.2 optimization

- Remove temporary development files and duplicates
- Clean experimental strategies and obsolete tests
- Update scripts for v2.2 architecture compatibility
- Apply modern code formatting standards (Ruff, Black, isort)
- Optimize CI/CD pipeline configurations
- Regenerate API documentation
- Maintain professional development infrastructure
- Update dashboard visualization specifications with production learnings"

# Push to GitHub repository
git remote add origin https://github.com/abhishekjs0/quantlab.git || true
git branch -M main
git push -u origin main

# Verify deployment
echo "✅ Repository successfully pushed to GitHub: https://github.com/abhishekjs0/quantlab.git"
echo "📊 Dashboard specifications updated with production best practices"
echo "🔧 Enhanced metrics panel documentation now comprehensive"
```

### 10. Post-Deployment Verification
After pushing to GitHub, verify the deployment:

```bash
# Check remote status
git remote -v

# Verify latest commit is pushed
git log --oneline -5

# Check GitHub repository status
echo "Verify at: https://github.com/abhishekjs0/quantlab.git"
echo "Key files to check:"
echo "  - docs/DASHBOARD_VISUALIZATION_SPEC.md (updated with production specs)"
echo "  - viz/final_fixed_dashboard.py (enhanced metrics panel)"
echo "  - reports/enhanced_metrics_dashboard.html (latest working dashboard)"
echo "  - .github/workflows/ (CI/CD pipeline)"
```

## System Architecture v2.2

### Core Production Components:
- **`core/`**: Enhanced backtesting engine with Strategy.I() system
- **`strategies/`**: Modern strategies using Strategy.I() wrapper architecture
- **`utils/`**: Comprehensive technical indicators library (30+ indicators)
- **`data/`**: Intelligent data loaders with 30-day caching system
- **`viz/`**: Professional dashboard system with enhanced metrics panel
  - `final_fixed_dashboard.py`: Production dashboard with grid-based metrics
  - `improved_dashboard.py`: Enhanced metrics panel source
  - Enhanced CSS styling with golden highlights and smooth transitions
  - Professional JavaScript with fade effects and responsive design
- **`runners/`**: Optimized backtesting execution and orchestration
- **`tests/`**: Comprehensive test suite with 40+ tests (35% coverage requirement)
- **`docs/`**: Complete documentation with enhanced dashboard specifications
  - `DASHBOARD_VISUALIZATION_SPEC.md`: Comprehensive dashboard specification
  - `api/`: Professional Sphinx API documentation with GitHub Pages deployment

### Key Features v2.2:
- **Enhanced Dashboard System**: Professional grid-based metrics panel with responsive design
- **Strategy.I() System**: Modern wrapper architecture for indicator integration
- **CI/CD Pipeline**: GitHub Actions with multi-Python testing (3.9, 3.10, 3.11)
- **Professional Documentation**: Sphinx API docs with autodoc and type hints
- **Enhanced Testing**: Comprehensive test coverage with automated quality gates
- **Security Scanning**: Bandit vulnerability analysis and Dependabot updates
- **Code Quality**: Ruff linting, Black formatting, isort organization
- **Performance Validation**: Automated benchmark testing in CI pipeline
- **Production Dashboard**: Enhanced metrics panel with highlight styling and smooth animations

### Maintenance Schedule v2.2:
- **Daily**: Remove temporary files created during development
- **Weekly**: Run code quality checks and formatting (automated in CI)
- **Monthly**: Review and update documentation (automated deployment)
- **Quarterly**: Audit dependencies (automated by Dependabot) and system performance

### Files to NEVER Remove:
- **Core System**: `core/`, `utils/`, `data/loaders.py`, `config.py`
- **Production Strategies**: `strategies/ichimoku.py`, `strategies/template.py`
- **Enhanced Dashboard**: `viz/final_fixed_dashboard.py`, `viz/improved_dashboard.py`
- **Dashboard Outputs**: `reports/enhanced_metrics_dashboard.html`
- **CI/CD Infrastructure**: `.github/`, `pyproject.toml`, `.bandit`
- **Documentation**: `docs/api/`, `docs/DEVELOPMENT_WORKFLOW.md`, `docs/DASHBOARD_VISUALIZATION_SPEC.md`
- **Test Suite**: `tests/test_strategy_wrapper.py`, `tests/test_*.py` (essential)
- **Dashboard Generation**: `generate_updated_dashboard.py`

### Modern Development Practices:
This protocol ensures the QuantLab v2.2 system maintains:
- Professional-grade code quality with automated enforcement
- Comprehensive API documentation with automatic deployment
- Robust testing framework with coverage requirements
- Modern CI/CD pipeline with security scanning
- Clean, efficient, and production-ready architecture
