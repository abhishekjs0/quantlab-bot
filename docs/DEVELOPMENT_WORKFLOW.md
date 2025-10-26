# Development Workflow Guide

## Overview

QuantLab v2.2 follows modern Python development practices with automated CI/CD pipelines, comprehensive testing, and professional documentation generation.

## Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd quantlab
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run tests
pytest --cov=.

# Format code
black .
isort .

# Lint code
ruff check .

# Build documentation
cd docs/api && make html
```

## Development Environment

### Prerequisites
- Python 3.9, 3.10, or 3.11
- Git
- Virtual environment (recommended)

### Installation
```bash
# Development installation with all optional dependencies
pip install -e ".[dev]"
```

## Code Quality Standards

### Formatting
- **Black**: Code formatting with 88-character line length
- **isort**: Import statement organization
- **Ruff**: Fast Python linter replacing Flake8, pycodestyle, and more

### Configuration
All tools are configured in `pyproject.toml`:
- Black: 88-char lines, standard settings
- isort: Black-compatible profile
- Ruff: Enhanced rules with pragmatic ignores for legacy compatibility

### Pre-commit Checks
Run before committing:
```bash
# Format code
black .
isort .

# Check linting
ruff check .

# Run tests
pytest --cov=. --cov-fail-under=35
```

## Testing Framework

### Test Structure
```
tests/
├── test_*.py              # Unit tests
├── test_integration_*.py  # Integration tests
└── test_parity_*.py      # Parity validation tests
```

### Test Categories
1. **Unit Tests**: Core functionality, indicators, strategies
2. **Integration Tests**: Full backtest workflows
3. **Parity Tests**: Validation against reference implementations
4. **Performance Tests**: Benchmark validation

### Running Tests
```bash
# All tests with coverage
pytest --cov=. --cov-report=html

# Specific test categories
pytest tests/test_unit_*.py
pytest tests/test_integration_*.py

# Quick smoke tests
pytest tests/test_smoke.py
```

### Coverage Requirements
- Minimum overall coverage: 35%
- Core modules should aim for >50% coverage
- Strategy templates should have >40% coverage

## Documentation

### API Documentation
- **Sphinx**: Automated API documentation generation
- **RTD Theme**: Professional documentation styling
- **Type Hints**: Full type annotation support
- **Autodoc**: Automatic docstring extraction

### Building Documentation
```bash
cd docs/api
make html
# Documentation available at _build/html/index.html

# Serve locally
python -m http.server 8080 -d _build/html
```

### Docstring Standards
Use Google-style docstrings:
```python
def strategy_function(data: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate technical indicator.

    Args:
        data: OHLCV price data
        period: Calculation period

    Returns:
        Series with indicator values

    Raises:
        ValueError: If period is invalid
    """
```

## CI/CD Pipeline

### Automated Workflows

#### 1. Main CI/CD Pipeline (`.github/workflows/ci-cd.yml`)
- **Triggers**: Push to main/develop, PRs to main
- **Matrix Testing**: Python 3.9, 3.10, 3.11
- **Steps**:
  - Code quality checks (Black, isort, Ruff)
  - Test execution with coverage reporting
  - Documentation building
  - Security scanning
  - Performance benchmarks
  - GitHub Pages deployment

#### 2. Code Quality Workflow (`.github/workflows/code-quality.yml`)
- **Focus**: Comprehensive code analysis
- **Tools**: Ruff, Black, isort, mypy, complexity analysis
- **Advisory**: Type checking and complexity warnings

#### 3. Documentation Workflow (`.github/workflows/docs.yml`)
- **Trigger**: Changes to code or documentation
- **Features**: Link checking, coverage badges, PR comments
- **Deployment**: Automatic GitHub Pages updates

### Dependency Management
- **Dependabot**: Automated weekly dependency updates
- **Grouping**: Related dependencies updated together
- **Security**: Automatic security update PRs

## Strategy Development

### Template Usage
```python
from core.strategy import Strategy

class MyStrategy(Strategy):
    """Custom strategy implementation."""

    # Parameters
    fast_period = 12
    slow_period = 26

    def initialize(self):
        """Setup indicators."""
        self.ema_fast = self.I(self.utils.EMA, self.data.close, self.fast_period)
        self.ema_slow = self.I(self.utils.EMA, self.data.close, self.slow_period)

    def next(self):
        """Strategy logic executed on each bar."""
        if self.utils.crossover(self.ema_fast, self.ema_slow):
            self.buy()
        elif self.utils.crossunder(self.ema_fast, self.ema_slow):
            self.sell()
```

### Best Practices
1. **Use Strategy.I()**: Wrap indicators for proper integration
2. **Parameter Validation**: Validate inputs in `initialize()`
3. **Market Regime Filters**: Use provided regime detection
4. **Risk Management**: Implement position sizing and stops
5. **Testing**: Create comprehensive test coverage

## Performance Optimization

### Profiling
```bash
# Profile strategy execution
python -m cProfile -o profile.stats runners/run_basket.py
python -c "import pstats; pstats.Stats('profile.stats').sort_stats('cumulative').print_stats(20)"
```

### Memory Management
- Use vectorized operations (NumPy/Pandas)
- Avoid loops in strategy logic
- Cache expensive calculations
- Monitor memory usage in long backtests

## Release Process

### Version Management
1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Commit with message containing `[release]`
4. Automated workflow creates GitHub release

### Validation Checklist
- [ ] All tests pass
- [ ] Code quality checks pass
- [ ] Documentation builds successfully
- [ ] Performance benchmarks within acceptable range
- [ ] Security scan clean
- [ ] Coverage requirements met

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure `pip install -e ".[dev]"` completed
2. **Test Failures**: Check data file formats (lowercase column names)
3. **Linting Errors**: Run `black .` and `isort .` to auto-fix
4. **Documentation Build**: Check Sphinx configuration and docstrings

### Debug Mode
```bash
# Verbose test output
pytest -v -s

# Debug strategy execution
python runners/run_basket.py --debug --strategies template

# Profile performance
python scripts/universal_indicator_analysis.py --profile
```

## Contributing

### Pull Request Process
1. Fork repository
2. Create feature branch
3. Implement changes with tests
4. Ensure all checks pass
5. Submit PR with description
6. Address review feedback
7. Automated merge after approval

### Code Review Criteria
- Code quality (formatting, linting)
- Test coverage
- Documentation updates
- Performance impact
- Security considerations

---

*This guide ensures consistent, high-quality development practices across the QuantLab project.*
