# QuantLab Trading Strategies

**Complete reference for all implemented strategies in QuantLab. Add new strategies by copying the template section and implementing the on_bar() method.**

---

## Overview

QuantLab supports multiple trading strategies with a clean, extensible architecture. Each strategy:
- Inherits from `Strategy` base class
- Implements `on_bar(ts, row, state)` method
- Returns entry/exit signals as dictionary
- Handles NaN indicators automatically
- Integrates with backtesting engine

### Current Strategies

| Strategy | Status | Return (5Y) | Max DD | Win Rate | Best For |
|----------|--------|------------|--------|----------|----------|
| **EMA Crossover** | ✅ Production | 1090.35% | 30.54% | 57.24% | Growth (3-5+ years) |
| **Ichimoku** | ✅ Production | ~800-1000% | ~28% | ~56% | Trending markets |
| **Knoxville** | ✅ Production | 558.59% | 25.79% | 55.29% | Conservative (1-2 years) |

---

## 📊 1. EMA Crossover Strategy

**Status**: ✅ Production Ready | **Best For**: Growth portfolios (2-5+ years)

### Overview
Trend-following approach using exponential moving average crossovers combined with RSI-based pyramiding to capture sustained price movements while buying dips during uptrends.

### Key Characteristics
- **Entry Signal**: EMA 89 > EMA 144 (bullish crossover) + RSI pyramiding
- **Pyramiding**: Up to 3 additional entries when RSI < 30 during uptrend
- **Exit Signal**: EMA 89 < EMA 144 (bearish crossover)
- **Stop Loss**: None (intentional for full trend capture)

### Performance (5-Year, Mega Basket)
```
Net P&L:        1090.35% (🏆 Best)
Max Drawdown:   30.54%
Total Trades:   194 (high quality)
Win Rate:       57.24%
Profit Factor:  14.26 (2.9× better than Knoxville)
Avg P&L/Trade:  56.90% (2.0× higher)
CAGR:           64.11% (+40% vs Knoxville)
```

### Strategy Logic

#### Primary Entry: Bullish EMA Crossover
```python
# Entry when fast EMA crosses above slow EMA
if (current.ema_89 > current.ema_144 and 
    previous.ema_89 <= previous.ema_144):
    return {"enter_long": True}
```

#### Pyramiding Entry: RSI Dip During Uptrend
```python
# Add position during uptrend when RSI < 30
if (position_qty > 0 and 
    current.ema_89 > current.ema_144 and 
    current.rsi_14 < 30 and 
    pyramid_level < 3):
    return {"add_to_position": True}
```

#### Exit: Bearish EMA Crossover
```python
# Exit when fast EMA crosses below slow EMA
if (current.ema_89 < current.ema_144 and 
    previous.ema_89 >= previous.ema_144):
    return {"exit_long": True}
```

### Why No Stop Loss?
- Stops exit premature reversals before trend resumes
- Full trend capture from crossover to reversal maximizes gains
- RSI pyramiding scales position in dips (manages risk via sizing)
- 5-year data shows higher returns justify higher drawdowns

### Recommended Settings
```python
# From strategies/ema_crossover.py
ema_fast = 89      # Fast EMA period
ema_slow = 144     # Slow EMA period
rsi_period = 14    # RSI calculation period
rsi_threshold = 30 # RSI level for pyramiding
max_pyramids = 3   # Max pyramid levels
```

### Time Horizon
- **1Y**: 28.63% return (comparable to Knoxville)
- **3Y**: 585.98% return (+130% vs Knoxville)
- **5Y**: 1090.35% return (+95% vs Knoxville)

---

## 🌊 2. Ichimoku Strategy

**Status**: ✅ Production Ready | **Best For**: Trending markets with clear support/resistance

### Overview
The Ichimoku Kinko Hyo is a comprehensive indicator system that provides support/resistance, trend confirmation, and momentum assessment all in one. This implementation combines core Ichimoku indicators with confirmation filters for robust trend-following entries and exits.

**Type**: Trend-following with confirmation filters  
**Market Regimes**: Strong uptrends, breakouts, trend continuation

### Core Components

#### 1. Conversion Line (Tenkan-sen)
```
Formula: (9-period High + 9-period Low) / 2
Purpose: Short-term trend identification (fast)
Signal: Above price = support; Below price = resistance
```

#### 2. Base Line (Kijun-sen)
```
Formula: (26-period High + 26-period Low) / 2
Purpose: Mid-term trend and support/resistance (medium)
Signal: Above price = strong support; Below = strong resistance
```

#### 3. Leading Span B (Senkou Span B)
```
Formula: (52-period High + 52-period Low) / 2, shifted 26 bars forward
Purpose: Long-term trend and cloud boundary (slow)
Signal: Defines Ichimoku cloud top; strong resistance/support
```

#### 4. Ichimoku Cloud (Kumo)
```
Cloud = Area between Leading Span A and Leading Span B
Thick cloud: Strong support/resistance
Thin cloud: Weak support/resistance
Price above: Bullish signal
Price below: Bearish signal
```

### Entry Conditions (All Must Be True)

```python
# Primary entry signal (all conditions required)
if (conversion_line > base_line and           # Momentum shift
    conversion_line > leading_span_b and      # Above long-term trend
    price > base_line):                       # Price above dynamic support
    return {"enter_long": True}
```

### Confirmation Filters (Optional)

#### RSI Filter (Enabled by default)
```python
rsi_filter_enabled = True
rsi_min_threshold = 50.0  # RSI must be > 50 (bullish)
rsi_period = 14

# Additional filter
if rsi_value > rsi_min_threshold:
    confirm_entry()  # Proceed with additional validation
```

**Interpretation:**
- RSI > 50: Bullish territory (good for long entry)
- RSI > 70: Overbought (consider partial profit)
- RSI < 30: Oversold (exit signal for existing positions)

#### MACD Filter (Optional)
```python
macd_filter_enabled = True

# Confirm entry with MACD signal
if macd_line > macd_signal:
    additional_confirmation()
```

#### Volume Confirmation (Optional)
```python
volume_filter_enabled = True

# Confirm with above-average volume
if current_volume > sma_volume:
    volume_confirmed()
```

### Exit Conditions

```python
# Exit when any condition triggers
exits = [
    conversion_line < base_line,      # Momentum reversal
    price < leading_span_b,           # Break below long-term cloud
    rsi_value < 30,                   # Oversold
]
if any(exits):
    return {"exit_long": True}
```

### Performance (5-Year, Mega Basket)
```
Estimated Return:   800-1000%
Max Drawdown:       ~28%
Win Rate:           ~56%
Profit Factor:      ~12-14
Characteristics:    Very profitable in trending markets
```

### Recommended Settings
```python
conversion_period = 9      # Tenkan-sen (short-term)
base_period = 26          # Kijun-sen (medium-term)
leading_span_b_period = 52 # Senkou Span B (long-term)
displacement = 26          # Cloud displacement (bars forward)

# Filters
use_rsi_filter = True
rsi_min = 50.0
rsi_period = 14

use_macd_filter = False    # Optional
use_volume_filter = False  # Optional
```

### Best Used In
- Strong uptrends (clear cloud-to-price relationship)
- Breakout trading (price clears cloud)
- Support/resistance trading (cloud boundaries)
- Multiple timeframe confirmation

### Limitations
- Less effective in choppy/sideways markets
- Cloud lags price (by design - trade-off)
- Requires sufficient history for leading span calculation

---

## 🎯 3. Knoxville Strategy

**Status**: ✅ Production Ready | **Best For**: Conservative portfolios (1-2 years)

### Overview
Divergence-based mean reversion approach combining fractal-based divergence detection with ATR-based stop losses and SMA trend filtering for controlled, conservative trading.

### Key Characteristics
- **Entry Signal**: Knoxville divergence detection on momentum + SMA trend filter
- **Trend Filter**: SMA 20 < SMA 50 (downtrend filter for safer entries)
- **Stop Loss**: 5×ATR (strict risk management)
- **Exit Signals**: Stop loss (priority 1), Bearish divergence (priority 2), Reversal tabs (priority 3)

### Performance (5-Year, Mega Basket)
```
Net P&L:        558.59% (solid, lower than EMA)
Max Drawdown:   25.79% (lower - good risk control)
Total Trades:   203 (higher frequency)
Win Rate:       55.29%
Profit Factor:  4.86 (good, but lower than EMA)
Avg P&L/Trade:  27.82% (conservative)
CAGR:           45.79% (solid, lower volatility)
```

### Strategy Logic

#### Primary Entry: Knoxville Divergence
```python
# Detect when price makes new high but momentum fails
if divergence_detected and sma_20 < sma_50:
    return {"enter_long": True}  # Conservative entry
```

**Divergence Detection:**
- Identify momentum highs/lows using fractal analysis (3-bar lookback)
- Compare current momentum with recent extremes
- Signal when price makes new high but momentum fails to confirm
- Only entry if trend filter allows (SMA 20 < SMA 50)

#### Exit: Stop Loss (5×ATR) - HIGHEST PRIORITY
```python
# Hard stop at 5× ATR
stop_loss_level = entry_price - (atr_14 * 5)

if price < stop_loss_level:
    return {"exit_long": True}  # Hard stop - always executed
```

**ATR Configuration:**
```python
atr_period = 14        # Standard ATR calculation
atr_multiplier = 5.0x  # 5× ATR for stop loss
```

#### Exit: Bearish Divergence Signal
```python
# Exit when momentum turns against position
if bearish_divergence_detected:
    return {"exit_long": True}
```

#### Exit: Reversal Tab Pattern
```python
# Exit on reversal pattern completion
if reversal_tab_pattern_complete:
    return {"exit_long": True}
```

### Exit Priority
1. **Stop Loss (5×ATR)** - Always executed first
2. **Bearish Divergence** - Primary signal reversal
3. **Reversal Tabs** - Pattern-based exit

### Recommended Settings
```python
# Divergence detection
divergence_lookback = 3  # Bars for fractal analysis

# Trend filter
sma_short = 20
sma_long = 50

# Stop loss
atr_period = 14
atr_multiplier = 5.0

# Reversal tab detection
tab_min_bars = 3  # Minimum bars in reversal pattern
```

### Risk Management
- **Max risk per trade**: 5×ATR below entry
- **Position sizing**: Should account for 5×ATR stop
- **Example**: On $100 stock with $2 ATR:
  - Stop loss: $100 - (5 × $2) = $90
  - Risk per trade: $10 per share

### Time Horizon
- **1Y**: 28.01% return (nearly tied with EMA)
- **3Y**: 254.15% return (lower but more stable)
- **5Y**: 558.59% return (conservative growth)

### Best Used In
- Choppy/mean-reverting markets
- Accounts with low drawdown tolerance
- Conservative traders prioritizing capital preservation
- Shorter time horizons (1-2 years)

---

## 🆕 Adding a New Strategy

### Step 1: Copy Template
```bash
cp strategies/template.py strategies/my_new_strategy.py
```

### Step 2: Implement Strategy Class

```python
# strategies/my_new_strategy.py
from core.strategy import Strategy
import numpy as np

class MyNewStrategy(Strategy):
    """Your strategy description here."""
    
    def on_bar(self, ts, row, state):
        """Execute strategy logic on each bar."""
        
        # Calculate indicators
        sma_20 = self.indicator['sma_20'][len(self) - 1]
        rsi_14 = self.indicator['rsi_14'][len(self) - 1]
        
        # Skip if NaN (startup period)
        if np.isnan(sma_20) or np.isnan(rsi_14):
            return {"enter_long": False, "exit_long": False}
        
        # Entry logic
        enter_long = (row['close'] > sma_20 and rsi_14 < 70)
        
        # Exit logic
        exit_long = (row['close'] < sma_20 or rsi_14 > 90)
        
        return {
            "enter_long": enter_long,
            "exit_long": exit_long,
        }
```

### Step 3: Register Strategy

```python
# core/registry.py - Add to STRATEGIES dict
STRATEGIES = {
    'ema_crossover': EMAcrossoverStrategy,
    'ichimoku': IchimokuStrategy,
    'knoxville': KnoxvilleStrategy,
    'my_new_strategy': MyNewStrategy,  # ← Add this
}
```

### Step 4: Document Strategy

Add a section to this STRATEGIES.md file following the template above.

### Step 5: Add Tests

```python
# tests/test_my_new_strategy.py
def test_my_new_strategy_initialization():
    strategy = MyNewStrategy()
    assert strategy is not None

def test_my_new_strategy_execution():
    # Test on sample data
    # Verify entry/exit signals
    pass
```

### Step 6: Run Tests

```bash
pytest tests/ --cov=. --cov-report=html
```

---

## 📈 Comparison Matrix

| Aspect | EMA Crossover | Ichimoku | Knoxville |
|--------|---------------|----------|-----------|
| **Type** | Trend Following | Trend Following + Confirmation | Mean Reversion |
| **Best Market** | Trending (uptrends) | Strong trends/breakouts | Choppy/sideways |
| **Risk Level** | Higher (no stops) | Medium | Lower (strict stops) |
| **Return (5Y)** | 1090% (🏆) | 800-1000% | 559% |
| **Max DD (5Y)** | 30.54% | ~28% | 25.79% |
| **Win Rate** | 57% | ~56% | 55% |
| **Complexity** | Low | Medium | High |
| **Data Required** | Moderate | More (for cloud) | Standard |
| **Recommended For** | Growth | Trending markets | Conservative |
| **Time Horizon** | 3-5+ years | 2-5 years | 1-2 years |

---

## 🔧 Strategy Development Tips

### Do's
- ✅ Use NaN checks to handle startup period
- ✅ Test on multiple market regimes
- ✅ Document your indicators and parameters
- ✅ Include stop loss or position management
- ✅ Add to test suite
- ✅ Compare performance across time horizons

### Don'ts
- ❌ Use look-ahead bias (future data)
- ❌ Hardcode symbols or dates
- ❌ Skip indicator calculations
- ❌ Ignore NaN values
- ❌ Leave strategies untested
- ❌ Over-optimize parameters

---

## 📊 Running Strategies

### Via CLI
```bash
# EMA Crossover on mega basket
python3 -m runners.run_basket --strategy ema_crossover --basket_size mega

# Ichimoku on large basket
python3 -m runners.run_basket --strategy ichimoku --basket_size large

# Knoxville on small basket
python3 -m runners.run_basket --strategy knoxville --basket_size small
```

### Via Python
```python
from runners.run_basket import run_basket_backtest

result = run_basket_backtest(
    strategy_name='ema_crossover',
    basket_name='mega',
    verbose=True
)

print(f"Trades: {len(result['trades'])}")
print(f"Final Equity: {result['equity_df'].iloc[-1]['equity']:.2f}")
```

---

## 📚 References

- **Core Implementation**: `strategies/` directory
- **Base Class**: `core/strategy.py`
- **Template**: `strategies/template.py`
- **Tests**: `tests/test_backtesting_integration.py`
- **Registry**: `core/registry.py`

---

**Last Updated**: November 5, 2025  
**Next Update**: When new strategies added or existing ones modified
