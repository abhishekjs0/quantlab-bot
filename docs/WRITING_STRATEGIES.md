# Writing Strategies in QuantLab

This guide explains how to write new trading strategies that follow QuantLab's best practices.

## Key Principles

1. **Always import indicators from `utils.indicators`** - Don't calculate indicators inline
2. **Inherit from `core.strategy.Strategy`** - Use the base class for all strategies
3. **Use `Strategy.I()` wrapper** - For clean indicator management
4. **No future-leak** - Only use previous bar data for signals

## Template

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
        """Initialize indicators using Strategy.I() wrapper."""
        # Use Strategy.I() to declare indicators - they'll be computed once
        self.fast_ema = self.I(EMA, self.data.close, self.fast_period, name="FastEMA")
        self.slow_ema = self.I(EMA, self.data.close, self.slow_period, name="SlowEMA")
        self.rsi = self.I(RSI, self.data.close, 14, name="RSI")
    
    def next(self, i: int) -> int:
        """
        Generate signal for bar i.
        
        Args:
            i: Current bar index
            
        Returns:
            1 for buy, -1 for sell, 0 for hold
        """
        # IMPORTANT: Use previous bar values (i-1) to avoid future leak
        if i < self.slow_period + 1:
            return 0
            
        prev = i - 1
        
        # Entry: Fast EMA crosses above Slow EMA
        if (self.fast_ema[prev] > self.slow_ema[prev] and 
            self.fast_ema[prev-1] <= self.slow_ema[prev-1]):
            return 1  # Buy
        
        # Exit: Fast EMA crosses below Slow EMA
        if (self.fast_ema[prev] < self.slow_ema[prev] and 
            self.fast_ema[prev-1] >= self.slow_ema[prev-1]):
            return -1  # Sell
        
        return 0  # Hold
```

## Available Indicators

All these are available from `utils.indicators`:

### Moving Averages
- `SMA` - Simple Moving Average
- `EMA` - Exponential Moving Average
- `WMA` - Weighted Moving Average
- `HullMovingAverage` - Hull Moving Average
- `VWMA` - Volume Weighted Moving Average

### Oscillators
- `RSI` - Relative Strength Index
- `MACD` - Moving Average Convergence Divergence
- `Stochastic` - Stochastic Oscillator
- `StochasticRSI` - Stochastic RSI
- `CCI` - Commodity Channel Index
- `WilliamsR` - Williams %R
- `Momentum` - Momentum Indicator

### Trend Indicators
- `ATR` - Average True Range
- `ADX` - Average Directional Index
- `Aroon` - Aroon Indicator
- `Supertrend` - Supertrend Indicator
- `IchimokuKinkoHyo` - Ichimoku Cloud

### Bands
- `BollingerBands` - Bollinger Bands
- `KeltnerChannels` - Keltner Channels
- `DonchianChannels` - Donchian Channels
- `Envelope` - Price Envelopes

### Volume Indicators
- `VWAP` - Volume Weighted Average Price
- `MFI` - Money Flow Index
- `CMF` - Chaikin Money Flow
- `OBV` - On Balance Volume

### Utility Functions
- `crossover(a, b)` - Check if series a crosses above series b
- `crossunder(a, b)` - Check if series a crosses below series b
- `true_range(high, low, close)` - Calculate true range

## Don'ts ❌

```python
# DON'T: Calculate indicators inline
sma = df['close'].rolling(20).mean()  # Bad!

# DON'T: Use ta library directly
import ta
rsi = ta.momentum.RSIIndicator(df['close'], window=14).rsi()  # Bad!

# DON'T: Use talib directly
import talib
ema = talib.EMA(df['close'].values, timeperiod=20)  # Bad!
```

## Do's ✅

```python
# DO: Import from utils.indicators
from utils.indicators import SMA, RSI, EMA

# DO: Use Strategy.I() wrapper
self.sma = self.I(SMA, self.data.close, 20, name="SMA20")
self.rsi = self.I(RSI, self.data.close, 14, name="RSI")
self.ema = self.I(EMA, self.data.close, 20, name="EMA20")
```

## Registering Your Strategy

Add your strategy to `core/registry.py`:

```python
from strategies.my_strategy import MyStrategy

STRATEGIES = {
    "my_strategy": MyStrategy,
    # ... other strategies
}
```

## Running the Import Checker

Before committing, run:

```bash
python scripts/check_strategy_imports.py strategies/my_strategy.py
```

This will catch any direct usage of `ta.` or inline calculations.
