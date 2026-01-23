# Strategy Development Guide

**Complete guide for creating and documenting trading strategies in QuantLab**

---

## Table of Contents
1. [Writing Strategies](#writing-strategies)
2. [Strategy Template](#strategy-template)
3. [Documentation Template](#documentation-template)
4. [Portfolio Construction](#portfolio-construction)
5. [Performance Evaluation](#performance-evaluation)

---

## Writing Strategies

### Key Principles

1. **Always import indicators from `utils.indicators`** - Don't calculate indicators inline
2. **Inherit from `core.strategy.Strategy`** - Use the base class for all strategies
3. **Use `Strategy.I()` wrapper** - For clean indicator management
4. **No future-leak** - Only use previous bar data for signals

### Quick Start Template

```python
"""
My Strategy
===========
Brief description of what this strategy does.
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import EMA, RSI, SMA, ATR  # Import from utils.indicators!


class MyStrategy(Strategy):
    """
    Strategy description.
    
    Entry Conditions:
    - List your entry conditions here
    
    Exit Conditions:
    - List your exit conditions here
    """
    
    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 20,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.fast_period = fast_period
        self.slow_period = slow_period
    
    def init(self):
        """Initialize indicators using Strategy.I() wrapper"""
        close = self.data.Close
        
        # Use Strategy.I() for all indicators
        self.fast_ema = self.I(EMA, close, self.fast_period)
        self.slow_ema = self.I(EMA, close, self.slow_period)
        self.rsi = self.I(RSI, close, 14)
    
    def next(self):
        """Execute strategy logic on each bar"""
        # Access previous values (avoid look-ahead bias)
        if self.fast_ema[-1] > self.slow_ema[-1]:
            if not self.position:
                self.buy()
        elif self.fast_ema[-1] < self.slow_ema[-1]:
            if self.position:
                self.position.close()
```

### Common Patterns

**Entry with Confirmation**
```python
def next(self):
    # Primary signal
    bullish_signal = self.fast_ma[-1] > self.slow_ma[-1]
    
    # Confirmation filters
    rsi_filter = 30 < self.rsi[-1] < 70
    volume_filter = self.data.Volume[-1] > self.data.Volume[-2]
    
    if bullish_signal and rsi_filter and volume_filter:
        if not self.position:
            self.buy()
```

**Pyramiding (Adding to Winners)**
```python
def next(self):
    if not self.position:
        if self.entry_signal():
            self.buy()
    else:
        # Add to position if profitable and signal persists
        if self.position.pl_pct > 0.05 and self.entry_signal():
            if len(self.trades) < self.max_pyramids:
                self.buy()
```

**ATR-Based Stops**
```python
def next(self):
    if self.position:
        atr_value = self.atr[-1]
        stop_price = self.position.entry_price - (2 * atr_value)
        
        if self.data.Close[-1] < stop_price:
            self.position.close()
```

### Best Practices

✓ **DO**:
- Import indicators from `utils.indicators`
- Use `self.I()` wrapper for indicators
- Access previous bar with `[-1]` index
- Test strategies on multiple timeframes
- Document entry/exit conditions
- Use ATR for dynamic stops

✗ **DON'T**:
- Calculate indicators inline (e.g., `df['sma'] = df.Close.rolling(20).mean()`)
- Use current bar `[0]` for signals (look-ahead bias)
- Hardcode stop-loss percentages without ATR
- Forget to initialize indicators in `init()`
- Skip documentation

---

## Strategy Template

### Full Template Code

```python
"""
Strategy Name
=============

**Type**: Trend Following / Mean Reversion / Momentum / Hybrid

**Summary**: One-line description of what the strategy does.

Entry Conditions:
-----------------
1. Primary signal (indicator/pattern details)
2. Filter 1 (confirmation condition)
3. Filter 2 (if applicable)

Exit Conditions:
----------------
1. Signal reversal
2. Take profit at X%
3. Stop loss at X% (or ATR-based: N × ATR)

Filters:
--------
- VIX Filter: Trade when VIX < X OR VIX > Y
- ATR% Filter: ATR(14)% > X%
- ADX Filter: ADX(28) > X (trend strength)

Parameters:
-----------
- param1 (int): Description. Default: X
- param2 (float): Description. Default: Y.Y
- use_filter (bool): Description. Default: True

Performance Notes:
------------------
- Best timeframe: 1d / 125m / 75m
- Typical win rate: X%
- Suitable markets: [trending/volatile/ranging]
"""

import numpy as np
import pandas as pd

from core.strategy import Strategy
from utils.indicators import EMA, RSI, SMA, ATR, ADX


class MyStrategy(Strategy):
    """
    Detailed strategy description.
    """
    
    # Class-level defaults
    fast_period = 10
    slow_period = 20
    rsi_period = 14
    use_filters = True
    
    def init(self):
        """Initialize all indicators"""
        close = self.data.Close
        high = self.data.High
        low = self.data.Low
        
        # Trend indicators
        self.fast_ma = self.I(EMA, close, self.fast_period)
        self.slow_ma = self.I(EMA, close, self.slow_period)
        
        # Momentum indicators
        self.rsi = self.I(RSI, close, self.rsi_period)
        
        # Volatility indicators
        self.atr = self.I(ATR, high, low, close, 14)
        
        # Trend strength
        self.adx = self.I(ADX, high, low, close, 28)
    
    def next(self):
        """Execute on each bar"""
        # Entry logic
        if not self.position:
            if self.entry_signal():
                self.buy()
        
        # Exit logic
        else:
            if self.exit_signal():
                self.position.close()
    
    def entry_signal(self) -> bool:
        """Check if entry conditions are met"""
        # Primary signal
        trend_bullish = self.fast_ma[-1] > self.slow_ma[-1]
        
        # Filters
        rsi_ok = 30 < self.rsi[-1] < 70
        strong_trend = self.adx[-1] > 25 if self.use_filters else True
        
        return trend_bullish and rsi_ok and strong_trend
    
    def exit_signal(self) -> bool:
        """Check if exit conditions are met"""
        # Exit on trend reversal
        trend_bearish = self.fast_ma[-1] < self.slow_ma[-1]
        
        # Exit on profit target
        profit_target = self.position.pl_pct > 0.25
        
        # Exit on stop loss
        stop_loss = self.position.pl_pct < -0.12
        
        return trend_bearish or profit_target or stop_loss
```

---

## Documentation Template

### Module Docstring Structure

```python
"""
Strategy Name
=============

**Type**: [Trend Following / Mean Reversion / Momentum / Hybrid]

**Summary**: Clear one-line description of core logic.

Entry Conditions:
-----------------
1. Primary signal (be specific: EMA(10) > EMA(20))
2. Confirmation filter (RSI > 50)
3. Volume confirmation (Volume > SMA(Volume, 20))

Exit Conditions:
----------------
1. Trend reversal (EMA(10) < EMA(20))
2. Take profit: +25%
3. Stop loss: -12% or 2 × ATR

Filters (Optional):
------------------
- VIX Filter: Only trade when VIX < 20
- ADX Filter: Require ADX(28) > 25 (strong trend)
- Time Filter: No trades in first/last 15 minutes

Pyramiding:
-----------
- Max additions: 2
- Add when: Price > entry + 1 × ATR and signal persists

Parameters:
-----------
- fast_period (int): Fast EMA period. Default: 10
- slow_period (int): Slow EMA period. Default: 20
- rsi_period (int): RSI period. Default: 14
- use_filters (bool): Enable ADX/VIX filters. Default: True

Performance Notes:
------------------
- Best timeframe: Daily
- Typical win rate: 45-55%
- Average trade: 7-12 days
- Suitable for: Trending markets
- Avoid in: Choppy/ranging conditions
"""
```

### README.md Structure

Each strategy should have a README.md with:

```markdown
# Strategy Name

## Overview
Brief description and strategy type.

## Performance Summary
- **Best Timeframe**: Daily
- **Win Rate**: ~50%
- **Sharpe Ratio**: 1.2
- **Max Drawdown**: -18%

## Entry Logic
1. Condition 1
2. Condition 2
3. Condition 3

## Exit Logic
1. Stop loss: -12%
2. Take profit: +25%
3. Signal reversal

## Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| fast_period | 10 | Fast EMA period |
| slow_period | 20 | Slow EMA period |

## Usage
\`\`\`python
from strategies.my_strategy import MyStrategy

strategy = MyStrategy(
    fast_period=12,
    slow_period=26
)
\`\`\`

## Backtesting
\`\`\`bash
python -m runners.standard_run_basket my_strategy --timeframe 1d
\`\`\`
```

---

## Portfolio Construction

### Asset Allocation Framework

**Conservative (Low Risk)**
- 60% Large-cap Index (Nifty 50)
- 20% Value ETF
- 15% Debt/Gold
- 5% Quality Factor

**Balanced (Medium Risk)**
- 50% Index (Nifty 50)
- 20% Growth Factor
- 15% Mid-cap
- 10% Commodities
- 5% International

**Aggressive (High Risk)**
- 40% Growth Factor
- 25% Small-cap/Momentum
- 20% Sector Bets (Banking, IT)
- 10% Mid-cap
- 5% Alternative

### Rebalancing Strategy

- **Quarterly**: Check allocations, rebalance if >5% drift
- **Annual**: Review factor allocations, update stock selection
- **Event-based**: Market corrections >15%, earnings surprises

### Risk Management

- **Max Drawdown**: -20% portfolio limit
- **Position Size**: Max 5% per stock, 15% per sector
- **Stop Loss**: 12-15% trailing stop on individual holdings
- **Profit Target**: 25-40% depending on timeframe

---

## Performance Evaluation

### Key Metrics

**Returns**
- Total Return %
- Annualized Return %
- Sharpe Ratio (>1.0 good, >2.0 excellent)
- Sortino Ratio (downside risk-adjusted)

**Risk**
- Max Drawdown % (lower is better)
- Volatility (annualized std dev)
- Beta (vs benchmark)
- Value at Risk (VaR)

**Trade Quality**
- Win Rate % (># 50% for trend following)
- Profit Factor (gross profit / gross loss, >1.5 good)
- Average Win / Average Loss Ratio (>2.0 ideal)
- Max Consecutive Losses

**Efficiency**
- Trades per Year
- Average Days in Trade
- Exposure % (time in market)

### Evaluation Checklist

Before deploying a strategy:

✓ **Backtested on 3+ years of data**
✓ **Sharpe Ratio > 1.0**
✓ **Max Drawdown < 25%**
✓ **Win Rate appropriate for strategy type**
✓ **Profit Factor > 1.5**
✓ **Tested on multiple timeframes**
✓ **Walk-forward validated**
✓ **Documented thoroughly**

### Common Issues

**Problem**: High win rate but low profit
- **Cause**: Small winners, large losers
- **Fix**: Widen profit targets, tighten stops

**Problem**: High returns but huge drawdown
- **Cause**: Over-leveraging or no risk management
- **Fix**: Reduce position sizes, implement stops

**Problem**: Good backtest, poor live performance
- **Cause**: Overfitting, look-ahead bias
- **Fix**: Simplify strategy, validate on out-of-sample data

---

## Related Resources

- [Backtest Guide](BACKTEST_GUIDE.md) - Running backtests
- [Data Sources](DATA_GUIDE.md) - Available data and fetching
- Main README.md - Project setup and overview
