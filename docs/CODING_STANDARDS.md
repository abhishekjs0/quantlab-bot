# QuantLab Coding Standards and Protocols

## Code Style Guidelines

### Python Code Formatting
- **String Quotes**: Use double quotes (`"`) for all strings consistently
- **Line Length**: Maximum 120 characters per line
- **Indentation**: 4 spaces, no tabs
- **Blank Lines**: Use 2 blank lines between top-level functions and classes
- **Imports**: Group imports in the following order:
  1. Standard library imports
  2. Third-party imports
  3. Local application imports

### Naming Conventions
- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private methods**: `_leading_underscore`

### Documentation Standards
- All public functions must have docstrings
- Use Google-style docstrings
- Include parameter types and return types
- Example:
```python
def calculate_returns(prices: pd.Series, method: str = "simple") -> pd.Series:
    """Calculate returns from price series.
    
    Args:
        prices: Series of asset prices
        method: Return calculation method ("simple" or "log")
        
    Returns:
        Series of calculated returns
        
    Raises:
        ValueError: If method is not supported
    """
```

## Project Structure Standards

### Directory Organization
```
quantlab/
├── core/           # Core backtesting engine
├── data/           # Data management and loading
├── strategies/     # Trading strategy implementations
├── runners/        # Execution scripts
├── scripts/        # Utility and data scripts
├── tests/          # Unit and integration tests
├── viz/           # Visualization modules
├── docs/          # Documentation
├── examples/      # Example usage
└── reports/       # Generated backtest reports
```

### File Naming
- Use descriptive names with underscores
- Strategy files: `strategy_name.py` (e.g., `ichimoku.py`)
- Utility scripts: `action_description.py` (e.g., `fetch_data.py`)
- Test files: `test_module_name.py`

## Development Workflow

### Before Committing
1. Run linting: `ruff check .`
2. Run tests: `python -m pytest tests/`
3. Clean cache: `find . -name "__pycache__" -type d -exec rm -rf {} +`
4. Validate imports with Pylance

### Code Quality Checks
- No unused imports
- No trailing whitespace
- Consistent quote usage
- Type hints for public functions
- Error handling for external data sources

## Backtesting Standards

### Strategy Implementation
- Inherit from base `Strategy` class
- Implement required methods: `on_data()`, `on_entry()` (if using stop losses)
- Use consistent parameter naming
- Include strategy description and parameters in docstring

### Performance Metrics
- Always calculate: Net P&L %, CAGR, Max Drawdown, Profit Factor
- Use individual trade drawdowns for symbol-level risk metrics
- Include trade count and win rate statistics
- Report both INR and percentage values

### Data Handling
- Cache historical data for performance
- Validate data integrity before backtesting
- Handle missing data gracefully
- Use consistent datetime indexing

## Testing Protocols

### Test Categories
1. **Unit Tests**: Individual function testing
2. **Integration Tests**: End-to-end workflow testing
3. **Smoke Tests**: Basic functionality validation
4. **Performance Tests**: Backtesting accuracy verification

### Test Data
- Use small, controlled datasets for unit tests
- Include edge cases (missing data, zero prices, etc.)
- Validate against known good results
- Test multiple time periods and market conditions

## Documentation Requirements

### Strategy Documentation
- Strategy logic explanation
- Parameter descriptions and valid ranges
- Expected market conditions for best performance
- Backtest results and performance analysis

### Code Documentation
- Module-level docstrings explaining purpose
- Function docstrings with parameters and returns
- Inline comments for complex logic
- Examples for public APIs

## Error Handling Standards

### Exception Handling
- Use specific exception types
- Provide meaningful error messages
- Log errors with context
- Fail gracefully with fallback behavior

### Data Validation
- Validate input parameters
- Check data types and ranges
- Handle missing or corrupted data
- Provide clear feedback on validation failures

## Performance Guidelines

### Optimization Practices
- Cache expensive calculations
- Use vectorized operations with pandas/numpy
- Minimize data copying
- Profile performance-critical sections

### Memory Management
- Clean up large DataFrames when no longer needed
- Use appropriate data types (float32 vs float64)
- Monitor memory usage during long backtests

## Version Control

### Commit Standards
- Use descriptive commit messages
- Keep commits focused and atomic
- Include issue numbers when applicable
- Tag releases with semantic versioning

### Branch Management
- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/`: Individual feature development
- `hotfix/`: Critical bug fixes

## Configuration Management

### Environment Variables
- Use `.env` files for local configuration
- Never commit sensitive data
- Provide `.env.example` template
- Document required environment variables

### Configuration Files
- Use `pyproject.toml` for Python project configuration
- Separate development and production configs
- Include validation for configuration values