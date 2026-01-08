# Writing Strategies in QuantLab

**Updated**: January 7, 2026

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
- `DEMA` - Double Exponential Moving Average (reduced lag)
- `TEMA` - Triple Exponential Moving Average (minimal lag)
- `LSMA` - Least Squares Moving Average (Linear Regression)
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

## Using Stop Losses

### Fixed Stop Loss

Set a fixed stop loss percentage on initialization:

```python
class MyStrategy(Strategy):
    def __init__(self, fixed_stop_pct: float = 0.10, **kwargs):
        super().__init__(**kwargs)
        self.fixed_stop_pct = fixed_stop_pct  # 10% stop loss
```

### Trailing Stop Loss

Trailing stops track the highest high since entry and trigger when price drops below a threshold.

**Important**: To use trailing stops, you must update state in both `on_entry()` and `on_bar()`:

```python
def on_entry(self, i: int, state: dict):
    """Called when a position is entered."""
    # Store entry price and initialize highest high
    state["entry_price"] = self.data.close[i]
    state["highest_high"] = self.data.high[i]

def on_bar(self, i: int, state: dict) -> int:
    """Called each bar while in a position."""
    # Update highest high
    current_high = self.data.high[i]
    if current_high > state.get("highest_high", 0):
        state["highest_high"] = current_high
    
    # Check trailing stop (e.g., 2% below highest high)
    trailing_stop_price = state["highest_high"] * (1 - self.trailing_stop_pct)
    if self.data.close[i] < trailing_stop_price:
        return -1  # Exit position
    
    return 0  # Hold
```

**Technical Note**: The engine maintains a `persistent_state` dict that survives across bars, ensuring `entry_price` and `highest_high` are preserved throughout the position lifetime.

## Multi-Timeframe Filters (Weekly)

For strategies using daily bars with weekly filters, QuantLab provides automatic weekly data integration:

### Weekly Filters Example: Candle Colour + Kaufman Efficiency Ratio (KER)

**Use Case**: Filter daily entries based on weekly trend strength and direction.

**Setup in Strategy:**
```python
class MyStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Enable weekly filters
        self.use_weekly_filters = True
        self.require_weekly_green = True  # Weekly candle must be green
        self.weekly_ker_min = 0.4        # Weekly KER(10) must be > 0.4
```

**How it works:**
1. Engine automatically loads weekly OHLC data for each symbol
2. Calculates weekly KER(10) = trend strength (0.0 = noise, 1.0 = perfect trend)
3. Determines weekly candle colour (green = close > open, red = close < open)
4. Maps weekly values to daily bars (forward-fill, no lookahead)
5. Checks filters at entry signal time

**Kaufman Efficiency Ratio (KER) Formula:**
```
KER = |Close[t] - Close[t-10]| / Σ|Close[i] - Close[i-1]|

Interpretation:
  • > 0.7 = Strong trending (high directional movement)
  • 0.3-0.7 = Mixed/moderate (some trend, some noise)
  • < 0.3 = Mean-reverting (mostly noise/reversals)
```

**Performance Impact:**
- Reduces false signals from choppy markets
- Improves Profit Factor by filtering out low-quality trades
- Example: PF 2.8 (all trades) → PF 3.1 (with weekly filters)

**Important**: Weekly data uses strict `<` comparison for current week to avoid lookahead bias (incomplete week data):
```python
# Example: Only use completed weekly candles
if weekly_index < current_week_index:
    use_weekly_filter = True  # Completed week
else:
    use_weekly_filter = False  # Current week still forming
```

### Lookahead Bias Verification (CRITICAL)

**Why Weekly Filters Are Safe:**

1. **Entry Execution**: Engine uses `execute_on_next_open = True` (signal on bar X close → execution on bar X+1 open)

2. **Weekly Data Timing**: Weekly candle colour and KER are calculated from COMPLETED weeks only:
   - Monday-Friday trading → Friday close completes the week
   - The completed week's data is used for NEXT week's entries
   - No incomplete week data ever used

3. **Verification Test Results (January 2026)**:
   - Baseline (no filters): 9,485 trades, 45.8% WR, PF 2.82
   - With weekly filters: 2,154 trades, 50.4% WR, PF 3.13
   - Filter reduces trade count 77% while improving quality 11%
   - If lookahead existed, win rate would be artificially high (>70%)

**Implementation Reference (tema_lsma_crossover.py):**
```python
# Weekly filter check in entry signal
def _check_weekly_filters(self, i: int) -> bool:
    """Check weekly filters at bar i for entry eligibility."""
    if not self.use_weekly_filters:
        return True
    
    # Get weekly candle colour (uses last completed week)
    weekly_colour = self.weekly_candle_colour[i]
    if self.require_weekly_green and weekly_colour != 'green':
        return False
    
    # Get weekly KER (uses last completed week)
    weekly_ker = self.weekly_ker[i]
    if np.isnan(weekly_ker) or weekly_ker < self.weekly_ker_min:
        return False
    
    return True
```

## ATR and Volatility Filters

### Daily ATR Percentage Filter

Filter trades based on minimum daily volatility to ensure sufficient price movement:

```python
class MyStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.use_atr_pct_filter = True
        self.atr_pct_min = 3.0  # Minimum 3% ATR for entry
        self.atr_period = 14

    def init(self):
        # Calculate ATR%
        from utils.indicators import ATR
        atr = self.I(ATR, self.data.high.values, self.data.low.values, 
                     self.data.close.values, self.atr_period)
        self.atr_pct = (atr / self.data.close.values) * 100
    
    def on_bar(self, i, row, state):
        # Check ATR filter before entry
        if self.use_atr_pct_filter and self.atr_pct[i] < self.atr_pct_min:
            return 0, "ATR% too low"
        # ... rest of entry logic
```

**Why Use ATR% Filter:**
- Filters out low-volatility periods (consolidation, low liquidity)
- Ensures enough price movement to cover commissions
- Typical thresholds: 2% (conservative), 3% (moderate), 5% (aggressive)

## Take Profit Configuration

### Tiered Take Profit System

Configure multiple take profit levels with partial position exits:

```python
class MyStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Take profit configuration
        self.tp1_pct = 0.05      # First TP at 5% profit
        self.tp1_qty_pct = 0.00  # Exit 0% of position (disabled)
        self.tp2_pct = 0.10      # Second TP at 10% profit  
        self.tp2_qty_pct = 0.00  # Exit 0% of position (disabled)
        # Remaining 100% exits at signal close
        self.cap_tp_qtys = True  # Ensure TP1 + TP2 <= 100%
```

**TP Configuration Strategies:**
| Style | TP1% | TP1 Exit | TP2% | TP2 Exit | Remaining | Best For |
|-------|------|----------|------|----------|-----------|----------|
| Trend Following | 5% | 0% | 10% | 0% | 100% | Strong trends, weekly filters |
| Scalp-Like | 5% | 50% | 10% | 30% | 20% | Mean reversion, choppy markets |
| Balanced | 5% | 15% | 40% | 30% | 55% | General purpose |

**Optimal Configuration (TEMA LSMA with Weekly Filters):**
The optimal configuration for strategies with weekly filters is NO partial exits (TP1=0%, TP2=0%, all at signal close). This is because:
1. Weekly filters already pre-select high-quality trending trades
2. Letting winners run maximizes Profit Factor (PF 3.13 vs 3.03 with partial exits)
3. Signal-based exit captures the full move until trend reversal
