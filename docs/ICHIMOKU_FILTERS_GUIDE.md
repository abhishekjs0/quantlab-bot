# Ichimoku Strategy with Entry Confirmation Filters

## Overview

The enhanced Ichimoku strategy now includes togglable entry confirmation filters that can significantly improve signal quality and reduce false entries. These filters are based on commonly used technical indicators and can be enabled or disabled independently.

## Filter Types

### 1. ATR% Filter (Average True Range Percentage)
- **Purpose**: Ensures adequate volatility for meaningful price moves
- **Default Range**: 2.0% - 5.0%
- **Rationale**: Filters out low volatility periods where price movements may be insignificant
- **Parameters**:
  - `use_atr_filter`: Enable/disable (default: True)
  - `atr_period`: Calculation period (default: 14)
  - `atr_min_pct`: Minimum ATR percentage (default: 2.0)
  - `atr_max_pct`: Maximum ATR percentage (default: 5.0)

### 2. ADX Filter (Average Directional Index)
- **Purpose**: Confirms trend strength before entry
- **Default Threshold**: > 20
- **Rationale**: ADX values above 20 indicate trending markets, reducing whipsaws
- **Parameters**:
  - `use_adx_filter`: Enable/disable (default: True)
  - `adx_period`: Calculation period (default: 14)
  - `adx_min`: Minimum ADX value (default: 20.0)

### 3. RSI Filter (Relative Strength Index)
- **Purpose**: Avoids entries in overbought/oversold conditions
- **Default Range**: 40 - 70
- **Rationale**: Filters out extreme momentum conditions that may reverse
- **Parameters**:
  - `use_rsi_filter`: Enable/disable (default: True)
  - `rsi_period`: Calculation period (default: 14)
  - `rsi_min`: Minimum RSI value (default: 40.0)
  - `rsi_max`: Maximum RSI value (default: 70.0)

### 4. EMA Filter (Exponential Moving Average)
- **Purpose**: Confirms long-term trend direction
- **Default**: Price > 200 EMA
- **Rationale**: Only takes long positions when price is above long-term trend
- **Parameters**:
  - `use_ema_filter`: Enable/disable (default: True)
  - `ema_period`: EMA calculation period (default: 200)

## Usage Examples

### Basic Usage (All Filters Enabled)
```python
from strategies.ichimoku import IchimokuStrategy

# Default configuration with all filters enabled
strategy = IchimokuStrategy()
```

### Custom Filter Configuration
```python
# Enable only specific filters
strategy = IchimokuStrategy(
    use_atr_filter=True,
    atr_min_pct=1.5,
    atr_max_pct=4.0,
    use_adx_filter=True,
    adx_min=25.0,
    use_rsi_filter=False,  # Disable RSI filter
    use_ema_filter=True,
    ema_period=150  # Shorter EMA period
)
```

### No Filters (Original Ichimoku)
```python
# Disable all filters for original ichimoku behavior
strategy = IchimokuStrategy(
    use_atr_filter=False,
    use_adx_filter=False,
    use_rsi_filter=False,
    use_ema_filter=False
)
```

## Filter Implementation Details

### Technical Calculations

1. **ATR Percentage**: `(ATR / Close) * 100`
   - Uses Wilder's smoothing for ATR calculation
   - Expressed as percentage of current close price

2. **ADX**: Average Directional Index
   - Calculated using +DI, -DI, and true range
   - Uses Wilder's smoothing for all components
   - Values range from 0-100

3. **RSI**: Relative Strength Index
   - Uses Wilder's smoothing for gain/loss calculations
   - Values range from 0-100
   - 50 is neutral, above/below indicates momentum direction

4. **EMA**: Exponential Moving Average
   - Uses pandas ewm() with adjust=False
   - Gives more weight to recent prices

### Signal Integration

Filters are applied as logical AND conditions to the base Ichimoku signals:

```python
# Base ichimoku signal
ichimoku_signal = conv_cross_up & (lagging_span > lead_line_a) & (lagging_span > lead_line_b)

# Apply filters
filter_conditions = True
if use_atr_filter:
    filter_conditions &= (atr_pct >= atr_min_pct) & (atr_pct <= atr_max_pct)
if use_adx_filter:
    filter_conditions &= (adx > adx_min)
if use_rsi_filter:
    filter_conditions &= (rsi >= rsi_min) & (rsi <= rsi_max)
if use_ema_filter:
    filter_conditions &= (close > ema)

# Final filtered signal
final_signal = ichimoku_signal & filter_conditions
```

## Performance Considerations

### Expected Benefits
- **Reduced False Signals**: Filters eliminate low-quality setups
- **Better Risk-Adjusted Returns**: Higher win rate, better Sharpe ratio
- **Trend Alignment**: EMA filter ensures trend following
- **Volatility Awareness**: ATR filter adapts to market conditions

### Potential Drawbacks
- **Fewer Signals**: More selective entry criteria
- **Missed Opportunities**: Some profitable signals may be filtered out
- **Parameter Sensitivity**: Filter thresholds may need optimization
- **Lag Introduction**: Additional indicators add computational lag

## Backtesting Comparison

To compare performance with and without filters:

```python
# Run without filters
python runners/run_basket.py --basket_size large --strategy ichimoku \
    --params_json '{"use_atr_filter": false, "use_adx_filter": false, "use_rsi_filter": false, "use_ema_filter": false}'

# Run with filters
python runners/run_basket.py --basket_size large --strategy ichimoku \
    --params_json '{"use_atr_filter": true, "use_adx_filter": true, "use_rsi_filter": true, "use_ema_filter": true}'
```

## Recommended Settings

### Conservative (Quality over Quantity)
```python
strategy = IchimokuStrategy(
    use_atr_filter=True,
    atr_min_pct=2.5,
    atr_max_pct=4.0,
    use_adx_filter=True,
    adx_min=25.0,
    use_rsi_filter=True,
    rsi_min=45.0,
    rsi_max=65.0,
    use_ema_filter=True,
    ema_period=200
)
```

### Aggressive (More Signals)
```python
strategy = IchimokuStrategy(
    use_atr_filter=True,
    atr_min_pct=1.5,
    atr_max_pct=6.0,
    use_adx_filter=True,
    adx_min=15.0,
    use_rsi_filter=True,
    rsi_min=35.0,
    rsi_max=75.0,
    use_ema_filter=False  # Disable for more opportunities
)
```

## Output Columns

When filters are enabled, additional columns are added to the strategy output:

- `atr_pct`: ATR as percentage of close price
- `adx`: Average Directional Index value
- `rsi`: Relative Strength Index value
- `ema_200`: Exponential Moving Average value
- `ichimoku_signal`: Original ichimoku signal (before filters)
- `filtered_signal`: Final signal after applying filters
- `exit_signal`: Exit signal (unchanged)

## Integration with Existing System

The filter functionality is fully backward compatible:
- Default behavior enables all filters with recommended settings
- All existing code continues to work unchanged
- Filters can be toggled independently for A/B testing
- No changes required to the backtesting engine or reporting system

## Next Steps

1. **Parameter Optimization**: Use grid search to find optimal filter parameters
2. **Market Regime Adaptation**: Consider different filter settings for different market conditions
3. **Dynamic Thresholds**: Implement adaptive filter thresholds based on market volatility
4. **Additional Filters**: Consider adding Volume, MACD, or Bollinger Band filters