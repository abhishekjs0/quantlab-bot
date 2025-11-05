# Market Regime Detection Guide

## Overview

The Market Regime Detection system identifies market conditions to help inform trading decisions. The system classifies markets into three main regimes:

- **Bullish**: Strong upward trending markets
- **Bearish**: Strong downward trending markets
- **Sideways**: Range-bound or consolidating markets

This is particularly useful for trend-following strategies that perform better in trending markets, or mean-reversion strategies that work well in sideways markets.

## Key Features

- **Multiple Detection Methods**: Combines trend, momentum, and volatility analysis
- **Configurable Parameters**: Adjustable timeframes and thresholds
- **Regime Strength**: Confidence measure for each classification
- **Historical Analysis**: Analyze regime patterns over time
- **Strategy Integration**: Filter trades based on market conditions

## Quick Start

```python
from core.market_regime import RegimeDetector, create_trend_following_filter

# Load market data (NIFTY50 or market index)
data = load_symbol_data("NIFTY50")

# Create detector
detector = RegimeDetector(
    short_ma=20,
    medium_ma=50,
    long_ma=200,
    lookback_days=60
)

# Detect regimes
regimes = detector.detect_regime(data)

# Get current regime
current_regime = detector.get_current_regime(data)
regime_strength = detector.get_regime_strength(data)

print(f"Current regime: {current_regime.value}")
print(f"Strength: {regime_strength:.2f}")
```

## Regime Detection Methods

### 1. Trend-Based Detection

Uses moving average analysis:
- **Moving Average Slopes**: Long-term trend direction
- **Price Position**: Relative to key moving averages
- **MA Alignment**: Bullish/bearish moving average order

```python
# Bullish conditions
- Long MA slope > 2% (configurable)
- Price above 50 MA and 200 MA
- 20 MA > 50 MA > 200 MA

# Bearish conditions
- Long MA slope < -2%
- Price below 50 MA and 200 MA
- 20 MA < 50 MA < 200 MA

# Sideways conditions
- Long MA slope between -0.5% and +0.5%
- Mixed moving average signals
```

### 2. Momentum-Based Detection

Uses RSI and rate of change:
- **RSI Levels**: Momentum direction and strength
- **Rate of Change**: Medium-term price momentum

```python
# Bullish momentum
- RSI > 50 and medium-term ROC > 2%

# Bearish momentum
- RSI < 50 and medium-term ROC < -2%

# Neutral momentum
- RSI between 40-60 and ROC between -2% to +2%
```

### 3. Volatility-Based Detection

Uses ADX and volatility measures:
- **ADX**: Trend strength indicator
- **Volatility**: Market uncertainty measure

```python
# Strong trending (high ADX > 25)
- Use trend and momentum signals

# Weak trending (low ADX < 20)
- Likely sideways market
```

## Configuration Parameters

### RegimeDetector Parameters

```python
RegimeDetector(
    short_ma=20,           # Short-term MA period
    medium_ma=50,          # Medium-term MA period
    long_ma=200,           # Long-term MA period
    lookback_days=60,      # Regime classification window
    volatility_window=20,  # Volatility calculation window
    trend_threshold=0.02,  # Minimum slope for trending (2%)
    sideways_threshold=0.005  # Maximum slope for sideways (0.5%)
)
```

### Sensitivity Tuning

- **Faster Response**: Reduce `lookback_days`, lower thresholds
- **Smoother Classification**: Increase `lookback_days`, higher thresholds
- **Trend Following**: Higher `trend_threshold` for clearer trends
- **Mean Reversion**: Lower `sideways_threshold` for more sideways detection

## Regime Strength

The system provides a confidence measure (0.0 to 1.0) based on:

- **Trend Consistency**: How consistent the trend direction is
- **Momentum Alignment**: How well momentum confirms the trend
- **Volatility Clarity**: How clear the regime signals are

```python
strength = detector.get_regime_strength(data)

if strength > 0.7:
    print("High confidence regime")
elif strength > 0.4:
    print("Moderate confidence regime")
else:
    print("Low confidence - mixed signals")
```

## Strategy Integration

### Trend Following Filter

```python
from core.market_regime import create_trend_following_filter

# Create filter that only allows trades in bull markets
trend_filter = create_trend_following_filter()

# In your strategy
if trend_filter.should_trade(market_data):
    # Take trend-following trades
    enter_long = your_strategy_signal
else:
    # Block trades in unfavorable conditions
    enter_long = False
```

### Custom Regime Filter

```python
from core.market_regime import MarketRegimeFilter, RegimeDetector, MarketRegime

# Create custom detector
detector = RegimeDetector(lookback_days=90)  # Longer-term view

# Create filter for mean reversion (sideways markets only)
reversion_filter = MarketRegimeFilter(
    detector=detector,
    allowed_regimes=[MarketRegime.SIDEWAYS],
    min_strength=0.3
)

# Use in strategy
if reversion_filter.should_trade(market_data):
    # Take mean reversion trades
    pass
```

## Analysis and Backtesting

### Historical Regime Analysis

```python
from core.market_regime import analyze_regime_history

# Analyze regime patterns
analysis = analyze_regime_history(data, detector)

print("Regime Distribution:")
for regime, pct in analysis["regime_percentages"].items():
    print(f"  {regime}: {pct:.1f}%")

print("Average Durations:")
for regime, days in analysis["average_durations"].items():
    print(f"  {regime}: {days:.1f} days")
```

### Performance by Regime

```python
# Calculate returns by regime
regimes = detector.detect_regime(data)

for regime in [MarketRegime.BULLISH, MarketRegime.BEARISH, MarketRegime.SIDEWAYS]:
    regime_mask = regimes == regime
    regime_returns = data[regime_mask]["close"].pct_change().dropna()

    avg_return = regime_returns.mean() * 252  # Annualized
    volatility = regime_returns.std() * (252 ** 0.5)
    sharpe = avg_return / volatility if volatility > 0 else 0

    print(f"{regime.value}: Return {avg_return:.1%}, Vol {volatility:.1%}, Sharpe {sharpe:.2f}")
```

## Best Practices

### Data Requirements

- **Minimum History**: At least 1 year for stable detection
- **Quality Data**: Use broad market indices (NIFTY50, SENSEX)
- **Frequency**: Daily data works best, hourly for shorter-term regimes

### Parameter Selection

- **Market Characteristics**: Adjust thresholds for your market's volatility
- **Strategy Timeframe**: Match regime detection timeframe to strategy holding period
- **Backtesting**: Test different parameters on historical data

### Integration Tips

- **Conservative Approach**: Use regime as filter, not primary signal
- **Regime Transitions**: Be careful during regime change periods
- **Multiple Timeframes**: Consider regime on multiple timeframes
- **Regime Strength**: Use strength as position sizing factor

## Limitations

- **Lagging Nature**: Based on historical data, may miss rapid regime changes
- **False Signals**: Market regimes can change quickly during major events
- **Market Dependent**: Parameters may need adjustment for different markets
- **Data Quality**: Requires clean, representative market data

## Advanced Usage

### Multi-Timeframe Analysis

```python
# Short-term regime (for entries)
short_detector = RegimeDetector(lookback_days=30)
short_regime = short_detector.get_current_regime(data)

# Long-term regime (for overall bias)
long_detector = RegimeDetector(lookback_days=120)
long_regime = long_detector.get_current_regime(data)

# Trade only when both align
if short_regime == long_regime == MarketRegime.BULLISH:
    # Strong bullish signal
    pass
```

### Dynamic Position Sizing

```python
# Use regime strength for position sizing
base_position_size = 1.0
regime_strength = detector.get_regime_strength(data)
current_regime = detector.get_current_regime(data)

if current_regime == MarketRegime.BULLISH:
    position_multiplier = 0.5 + (regime_strength * 0.5)  # 0.5x to 1.0x
else:
    position_multiplier = 0.2  # Reduced size in non-bullish regimes

final_position_size = base_position_size * position_multiplier
```

### Regime-Based Stop Losses

```python
# Tighter stops in uncertain regimes
base_stop_pct = 0.08  # 8%
regime_strength = detector.get_regime_strength(data)

if regime_strength > 0.7:
    stop_loss_pct = base_stop_pct  # Normal stop
else:
    stop_loss_pct = base_stop_pct * 0.7  # Tighter stop (5.6%)
```

## Example Applications

See `examples/market_regime_demo.py` for a complete example that:

1. Loads market data
2. Detects regimes over time
3. Analyzes regime characteristics
4. Creates visualizations
5. Tests regime filters

The market regime detection system provides a robust framework for identifying market conditions and can significantly improve strategy performance when used appropriately.
