# Walk-Forward Optimization Guide

## Overview

Walk-forward optimization is a robust method for validating trading strategies that helps prevent overfitting and provides more realistic performance expectations. This framework implements a rolling window approach where strategies are:

1. **Trained** on N years of historical data to find optimal parameters
2. **Tested** on the next M months of out-of-sample data
3. **Rolled forward** and the process repeats

## Key Features

- **Configurable Windows**: Default 4-year training, 1-year testing
- **Parameter Optimization**: Grid search on training data
- **Out-of-Sample Testing**: Unbiased performance on test data
- **Comprehensive Metrics**: CAGR, Sharpe, drawdown, win rate, etc.
- **Stability Analysis**: Measure consistency across periods

## Quick Start

```python
from core.walk_forward import WalkForwardOptimizer
from strategies.ichimoku import IchimokuStrategy
from core.config import BrokerConfig

# Load your data
data = load_symbol_data("RELIANCE")

# Configure broker settings
config = BrokerConfig(
    commission_pct=0.1,
    initial_capital=100000,
    qty_pct_of_equity=0.95
)

# Define parameter grid
param_grid = {
    'conversion_length': [7, 9, 12],
    'base_length': [20, 26, 30],
    'use_rsi_filter': [True, False],
    'rsi_min': [45.0, 50.0, 55.0]
}

# Create optimizer
optimizer = WalkForwardOptimizer(
    strategy_class=IchimokuStrategy,
    data=data,
    config=config,
    train_years=4,
    test_years=1
)

# Run optimization
results = optimizer.run_walk_forward(param_grid)

# Analyze results
from core.walk_forward import analyze_walk_forward_results
analysis = analyze_walk_forward_results(results)
```

## Framework Components

### WalkForwardOptimizer

Main class that handles the optimization process:

- **create_periods()**: Splits data into train/test periods
- **optimize_parameters()**: Finds best parameters on training data
- **run_walk_forward()**: Executes complete optimization
- **_calculate_metrics()**: Computes performance metrics

### WalkForwardResult

Data structure containing results for each period:

- Period dates (train/test start/end)
- Training and testing metrics
- Best parameters found
- Equity curve and trades for test period

### Key Parameters

- **train_years**: Years of data for parameter optimization (default: 4)
- **test_years**: Years for out-of-sample testing (default: 1)
- **step_years**: Years to advance between periods (default: 1)
- **min_train_days**: Minimum training data required (default: 1000)
- **min_test_days**: Minimum test data required (default: 200)

## Optimization Score

The framework uses a composite score for parameter selection:

```python
score = sharpe * (1 - max_drawdown) * (1 + win_rate)
```

This balances risk-adjusted returns with drawdown control and trade success rate. You can customize the `_calculate_optimization_score()` method for different objectives.

## Analysis Metrics

The `analyze_walk_forward_results()` function provides:

### Test Performance
- Mean/std CAGR across periods
- Mean/std Sharpe ratio
- Average and worst drawdown
- Win rate and total trades
- Profitable periods percentage

### Stability Metrics
- CAGR stability (1 - coefficient of variation)
- Sharpe stability
- Parameter consistency

### Period-by-Period Results
- Individual period performance
- Best/worst performing periods
- Parameter evolution over time

## Best Practices

### Data Requirements
- **Minimum 6 years** of data (4 train + 1 test + 1 buffer)
- **Daily or higher frequency** for robust statistics
- **Quality data** with proper adjustments for splits/dividends

### Parameter Grids
- **Reasonable ranges**: Don't over-optimize with too many values
- **Logical parameters**: Test values that make economic sense
- **Computational limits**: Consider grid size vs. processing time

### Interpretation
- **Consistency matters**: Stable performance across periods > single great period
- **Out-of-sample focus**: Test metrics are more important than training
- **Risk-adjusted metrics**: Sharpe ratio often better than raw returns

## Example Usage

See `examples/walk_forward_demo.py` for a complete example that:

1. Loads data for multiple symbols
2. Configures parameter optimization
3. Runs walk-forward analysis
4. Generates comprehensive reports
5. Saves detailed results to CSV

## Integration with QuantLab

The framework integrates seamlessly with:

- **All QuantLab strategies**: Any Strategy subclass works
- **Existing backtesting**: Uses same engine and configuration
- **Performance analysis**: Compatible with existing metrics
- **Visualization**: Can plot equity curves and results

## Performance Considerations

- **Parallel processing**: Consider parallelizing parameter combinations
- **Data caching**: Preload data to avoid repeated I/O
- **Progress monitoring**: Use logging to track long-running optimizations
- **Memory management**: Clear unused results for large parameter grids

## Limitations

- **Look-ahead bias**: Ensure no future data leaks into training
- **Survivorship bias**: Use complete universe, not just successful stocks
- **Transaction costs**: Include realistic commission and slippage
- **Market regime changes**: Consider regime detection for robustness

## Future Enhancements

- Monte Carlo permutation testing
- Bootstrap confidence intervals
- Multi-objective optimization (Pareto frontiers)
- Regime-aware optimization
- Cross-asset validation

This framework provides a solid foundation for robust strategy validation while remaining flexible and extensible for advanced use cases.
