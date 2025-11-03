# Ichimoku Strategy Guide

## Overview

The Ichimoku Kinko Hyo ("one glance equilibrium chart") is a comprehensive indicator system that provides support/resistance, trend confirmation, and momentum assessment all in one. This QuantLab implementation combines the core Ichimoku indicators with additional filters for robust trend-following entries and exits.

**Strategy Type:** Trend-following with confirmation filters  
**Best For:** Trending markets with clear support/resistance  
**Market Regimes:** Strong uptrends, breakouts, trend continuation  

---

## Core Ichimoku Components

### 1. Conversion Line (Tenkan-sen)
```
Formula: (9-period High + 9-period Low) / 2
Period: 9 bars
Purpose: Short-term trend identification
Speed: Fast - reacts quickly to price changes
```

**Interpretation:**
- Above price: Support level
- Below price: Resistance level
- Crosses base: Potential trend change signal

### 2. Base Line (Kijun-sen)
```
Formula: (26-period High + 26-period Low) / 2
Period: 26 bars
Purpose: Mid-term trend and support/resistance
Speed: Medium - more stable than conversion line
```

**Interpretation:**
- Above price: Strong support
- Below price: Strong resistance
- Used as dynamic stop level

### 3. Leading Span B (Senkou Span B)
```
Formula: (52-period High + 52-period Low) / 2
Period: 52 bars (shifted 26 bars into future)
Purpose: Long-term trend and cloud boundary
Speed: Slow - most stable, clearest trends
```

**Interpretation:**
- Defines top of Ichimoku cloud
- Strong dynamic resistance when below price
- Strong support when above price

### 4. Ichimoku Cloud (Kumo)
```
Cloud = Area between Leading Span A and Leading Span B
- Thick cloud: Strong support/resistance
- Thin cloud: Weak support/resistance
- Price above cloud: Bullish
- Price below cloud: Bearish
```

---

## Trading Rules

### Entry Conditions (All Must Be True)

**Primary Entry Signal:**
```
1. Conversion Line > Base Line
   └─> Indicates momentum shift
   └─> Short-term trend above mid-term
   
2. Conversion Line > Leading Span B
   └─> Price momentum above long-term cloud
   └─> Confirms broader trend strength
   
3. Price > Base Line
   └─> Price above dynamic support
   └─> Mid-term support confirmed
```

### Confirmation Filters (Optional but Recommended)

All filters are configurable (enabled/disabled independently).

#### RSI Filter (Default: Enabled)
```python
use_rsi_filter = True
rsi_min = 50.0          # RSI must be > 50 (bullish momentum)
rsi_period = 14

Logic: Confirm with additional momentum indicator
```

**Interpretation:**
- RSI > 50: Bullish territory
- RSI > 70: Overbought (caution, consider partial)
- RSI < 30: Oversold (exit signal)

#### CCI Filter (Default: Enabled)
```python
use_cci_filter = True
cci_min = 0.0           # CCI must be > 0 (above midline)
cci_period = 20

Logic: Commodity Channel Index confirms strength
```

**Interpretation:**
- CCI > 0: Bullish cycle
- CCI > 100: Very strong
- CCI < -100: Very weak (potential exit)

#### EMA20 Filter (Default: Enabled)
```python
use_ema20_filter = True

Logic: Price must be above 20-period EMA (short-term uptrend)
```

**Interpretation:**
- Price > EMA20: Uptrend confirmed
- Price < EMA20: Downtrend or consolidation
- Used as trailing stop reference

#### ATR Filter (Optional)
```python
use_atr_filter = False
atr_min_pct = 2.0       # Minimum volatility %
atr_max_pct = 5.0       # Maximum volatility %
atr_period = 14

Logic: Only trade when volatility is in acceptable range
```

**Interpretation:**
- ATR too low: Choppy, no clear direction
- ATR too high: Risky breakouts
- Best when ATR 2-5% of price

#### Volume Filter (Optional)
```python
use_cmf_filter = False
cmf_min = -0.15         # Chaikin Money Flow minimum
cmf_period = 20

Logic: Confirm strength with volume analysis (requires volume data)
```

**Interpretation:**
- CMF > 0: Money flowing in (bullish)
- CMF < -0.15: Money flowing out (bearish)

#### Directional Indicator Filter (Optional - Disabled by default)
```python
use_di_filter = False   # Disabled due to ADX calculation issues

Logic: Use ADX directional movement for trend confirmation
```

---

## Exit Conditions (Any One Triggers)

### 1. Stop Loss (Hard Stop)
```
Exit when: Price crosses below Base Line
└─> Indicates trend reversal
└─> Risk-controlled exit
└─> Uses on_bar() method (signal on close, execute on next open)
```

### 2. Take Profit
```
Exit when: Price crosses above Leading Span B
└─> Profit target at major resistance
└─> Locks in gains before reversal
└─> Uses on_bar() method
```

### 3. Signal-Based Exit
```
Exit when: Conversion Line < Base Line
└─> Trend reversal signal
└─> Short-term momentum turning negative
└─> Uses on_bar() method
```

### 4. Filter-Based Exit
```
Exit when any active filter turns negative:
  - RSI < 30 (oversold)
  - CCI < -100 (very bearish)
  - Price < EMA20 (short-term weakness)
  - CMF < -0.15 (volume selling)
```

---

## Parameter Reference

### Core Ichimoku Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `conversion_length` | 9 | 5-14 | Tenkan-sen period (fast trend) |
| `base_length` | 26 | 20-30 | Kijun-sen period (mid trend) |
| `lagging_length` | 52 | 40-60 | Senkou Span B period (slow trend) |

**Optimization Tips:**
- Shorter periods: More signals, higher drawdown
- Longer periods: Fewer signals, smoother performance
- Classic: 9, 26, 52 (usually optimal)

### Filter Toggle Parameters

| Parameter | Default | Options | Description |
|-----------|---------|---------|-------------|
| `use_rsi_filter` | True | True/False | Enable RSI confirmation |
| `use_cci_filter` | True | True/False | Enable CCI confirmation |
| `use_ema20_filter` | True | True/False | Enable EMA20 confirmation |
| `use_atr_filter` | False | True/False | Enable volatility check |
| `use_cmf_filter` | False | True/False | Enable volume check (requires volume) |
| `use_di_filter` | False | True/False | Enable directional indicator (disabled - ADX issue) |

### Filter Threshold Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `rsi_min` | 50.0 | 30-70 | RSI entry threshold |
| `rsi_period` | 14 | 7-28 | RSI calculation period |
| `cci_min` | 0.0 | -100 to 100 | CCI entry threshold |
| `cci_period` | 20 | 10-30 | CCI calculation period |
| `atr_min_pct` | 2.0 | 0.5-5.0 | Minimum ATR % of price |
| `atr_max_pct` | 5.0 | 5.0-15.0 | Maximum ATR % of price |
| `atr_period` | 14 | 7-21 | ATR calculation period |
| `cmf_min` | -0.15 | -1.0 to 0.5 | CMF entry threshold |
| `cmf_period` | 20 | 10-30 | CMF calculation period |

---

## Usage Examples

### Example 1: Default Strategy (Most Common)
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_test.txt \
  --strategy strategies.ichimoku \
  --windows 1Y,3Y,5Y
```

**Configuration:** Classic parameters with RSI, CCI, EMA20 filters enabled

**Expected Performance:**
- Win Rate: 40-50%
- Profit Factor: 1.2-1.8
- Avg Trade Duration: 20-50 bars

### Example 2: Aggressive (Shorter Periods, Fewer Filters)
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_mid.txt \
  --strategy strategies.ichimoku \
  --params '{
    "conversion_length": 7,
    "base_length": 22,
    "lagging_length": 44,
    "use_rsi_filter": false,
    "use_cci_filter": true
  }' \
  --windows 1Y
```

**Characteristics:**
- More frequent trades (more entries)
- Higher drawdown (20-35%)
- Better for volatile markets

### Example 3: Conservative (Longer Periods, All Filters)
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_large.txt \
  --strategy strategies.ichimoku \
  --params '{
    "conversion_length": 12,
    "base_length": 30,
    "lagging_length": 60,
    "use_rsi_filter": true,
    "use_cci_filter": true,
    "use_ema20_filter": true,
    "use_atr_filter": true,
    "atr_min_pct": 2.5,
    "atr_max_pct": 4.0,
    "rsi_min": 55.0,
    "cci_min": 10.0
  }' \
  --windows 1Y,3Y
```

**Characteristics:**
- Fewer but higher quality trades
- Lower drawdown (10-18%)
- Better for range-bound markets

### Example 4: Volatility-Adjusted
```bash
# Only trade when volatility is high (breakout detection)
--params '{
  "use_atr_filter": true,
  "atr_min_pct": 3.0,
  "atr_max_pct": 8.0,
  "rsi_min": 50.0
}'
```

### Example 5: Volume-Confirmed (If Volume Data Available)
```bash
# Add volume confirmation to filter noise
--params '{
  "use_rsi_filter": true,
  "use_cci_filter": true,
  "use_cmf_filter": true,
  "cmf_min": 0.0,
  "cmf_period": 20
}'
```

---

## Strategy Analysis

### Strengths ✅

1. **Multi-Timeframe Analysis**
   - Combines fast (9), medium (26), and slow (52) periods
   - Identifies trends across multiple timeframes
   - Natural support/resistance levels built-in

2. **Trend Confirmation**
   - Conversion > Base confirms momentum
   - Multiple indicators align for high-confidence signals
   - Less choppy than single-indicator strategies

3. **Flexible Filtering**
   - Can adjust filter strictness easily
   - Enable/disable filters based on market conditions
   - Adapt strategy without code changes

4. **Clear Signals**
   - Visual on charts (cloud clearly shows trend)
   - Mechanical rules (no subjective judgment)
   - Suitable for automation

### Weaknesses ❌

1. **Choppy Sideways Markets**
   - Cloud whipsaws common in ranges
   - False signals during consolidation
   - Filters help but can't eliminate completely

2. **Lagging Indicators**
   - Conversion/Base based on recent highs/lows
   - Signals come after trend already started
   - May miss early entries

3. **Cloud Penetration Noise**
   - Cloud penetrations can generate false exits
   - Price may briefly cross lines before continuing
   - Requires confirmation filters to reduce

4. **Parameter Sensitivity**
   - Changing 9/26/52 significantly alters performance
   - No universal "best" parameters for all markets
   - Requires optimization per instrument

### Best Market Conditions

| Condition | Performance | Notes |
|-----------|-------------|-------|
| **Strong Uptrend** | ⭐⭐⭐⭐⭐ | Excellent - natural trend-follower |
| **Breakout/Breakdowns** | ⭐⭐⭐⭐ | Very Good - filters help eliminate noise |
| **Range-Bound Markets** | ⭐⭐ | Poor - generates false signals |
| **High Volatility** | ⭐⭐⭐ | Good - if ATR filter enabled |
| **Low Volatility** | ⭐⭐ | Poor - lack of clear direction |
| **Reversals** | ⭐⭐⭐ | Good - catches early via base/conversion |

---

## Optimization Suggestions

### For Higher Win Rate
```python
# Stricter entry conditions
use_rsi_filter=True, rsi_min=55.0         # Only strong upside momentum
use_cci_filter=True, cci_min=10.0         # Additional confirmation
atr_min_pct=2.5                           # Filter choppy low-vol moves
```

### For Higher Profit Factor
```python
# Better trend selection
conversion_length=12, base_length=30      # Slightly longer (less whipsaw)
use_ema20_filter=True                     # Confirm short-term trend
rsi_min=50.0, cci_min=0.0                 # Balanced filters
```

### For Lower Drawdown
```python
# Conservative approach
use_atr_filter=True, atr_max_pct=4.0      # Skip very volatile instruments
conversion_length=10, base_length=28      # Classic with slight extension
use_rsi_filter=True, rsi_min=55.0         # Higher RSI requirement
```

### For More Trades
```python
# Reduce filter strictness
use_rsi_filter=False                      # Remove RSI check
cci_min=-50.0                             # Loosen CCI threshold
conversion_length=7, base_length=20       # Shorter periods (faster signals)
```

---

## Performance Metrics to Monitor

### Primary Metrics

| Metric | Target | Interpretation |
|--------|--------|-----------------|
| **Win Rate** | > 40% | % of profitable trades |
| **Profit Factor** | > 1.3 | Avg profit / Avg loss |
| **CAGR** | > 15% annually | Compound annual return |
| **Max Drawdown** | < 25% | Largest peak-to-trough loss |
| **Sharpe Ratio** | > 1.0 | Risk-adjusted return |

### Secondary Metrics

| Metric | Interpretation |
|--------|-----------------|
| **Avg Trade Bars** | How long trades typically hold (20-50 bars typical) |
| **Avg Profit/Loss** | Gauge of trade sizing and market conditions |
| **Consecutive Losses** | Risk management check (2-3 acceptable) |
| **Recovery Factor** | Net Profit / Max Drawdown (higher is better) |

### Monitoring Dashboard
```bash
# After backtest, check reports:
# - Win Rate %
# - Profit Factor
# - CAGR
# - Max Drawdown %
# - Sharpe Ratio
# - Avg Trade Duration (bars)
# - Number of Trades
```

---

## Troubleshooting

### Problem: Too Few Trades

**Possible Causes:**
1. Filters too strict (RSI, CCI thresholds too high)
2. Periods too long (9/26/52 → 12/30/60)
3. Market regime not trending (sideways markets)

**Solutions:**
```python
# Loosen filters
use_rsi_filter=False              # Remove RSI filter
rsi_min=45.0                      # Lower RSI requirement
cci_min=-50.0                     # Lower CCI requirement

# Shorten periods
conversion_length=7               # Faster signals
base_length=22                    # Shorter base
lagging_length=44                 # Shorter lag

# Check market: Is instrument trending?
# Run on basket_large.txt (diverse instruments)
```

### Problem: Too Many Losing Trades

**Possible Causes:**
1. Filters too loose (missing important signals)
2. Periods too short (choppy, whipsaw-prone)
3. Trading range-bound instruments
4. Stop-loss hit by noise (price touches base line briefly)

**Solutions:**
```python
# Add more filters
use_rsi_filter=True               # Require RSI > 50
rsi_min=55.0                      # Stricter RSI
use_atr_filter=True               # Require adequate volatility
atr_min_pct=2.5

# Lengthen periods
conversion_length=11              # Less sensitive
base_length=28                    # More stable
lagging_length=56                 # Clearer trends

# Check: Are you trading trending instruments?
# Avoid: range-bound forex pairs, choppy stocks in sideways market
```

### Problem: High Drawdown

**Possible Causes:**
1. Large losing streak during market reversal
2. Stop-loss too far away (large per-trade loss)
3. Positions held too long (max bars needed)
4. All signals going wrong simultaneously

**Solutions:**
```python
# Shorter max hold time
time_stop_bars=30                 # Exit after 30 bars max

# Better trend filter
use_atr_filter=True
atr_max_pct=4.0                   # Skip super volatile runs

# Stricter entry filters
use_rsi_filter=True, rsi_min=55.0 # Only strong trends
use_cci_filter=True, cci_min=10.0

# Reduce position size in config
qty_pct_of_equity=0.02            # 2% per trade instead of 5%
```

### Problem: Strategy Not Trading at All

**Possible Causes:**
1. Strategy file error (Python syntax issue)
2. Basket file has no data
3. Minimum bars not reached
4. All entry filters returning False

**Debugging:**
```bash
# Check strategy syntax
python3.11 -c "from strategies.ichimoku import IchimokuQuantLabWrapper; print('OK')"

# Check basket file
head -5 data/basket_test.txt

# Check config
grep -E "qty_pct|max_bars" config.py

# Try default strategy on test basket
--strategy strategies.ichimoku --basket_file data/basket_test.txt
```

---

## Related Documentation

- **[ON_BAR_EXECUTION_MODEL.md](./ON_BAR_EXECUTION_MODEL.md)**: How signals are generated and executed
- **[ENVELOPE_KD_STRATEGY.md](./ENVELOPE_KD_STRATEGY.md)**: Alternative strategy comparison
- **[BACKTEST_GUIDE.md](./BACKTEST_GUIDE.md)**: Running backtests and interpreting results
- **[DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)**: Making strategy modifications

---

## Key Insights for Best Results

### 1. **Match Strategy to Market**
- Ichimoku = Trend follower
- Best in: Strong uptrends, breakouts
- Avoid: Sideways markets, high noise

### 2. **Filter Stacking Works**
- RSI + CCI + EMA20 together > any single filter
- Each filter removes different types of false signals
- Don't use ALL filters blindly - use 2-3 most relevant

### 3. **Parameter Optimization Path**
1. Start with classic (9, 26, 52)
2. Add filters based on market (RSI, CCI for trending; ATR for range)
3. Adjust thresholds slightly (±5-10% typical range)
4. Test across multiple timeframes and instruments

### 4. **Realistic Expectations**
- Win Rate: 40-55% typical (not guaranteed to be high)
- Profit Factor: 1.2-2.0 typical
- CAGR: 10-25% annually (depends on market)
- Drawdown: 15-30% typical (larger in trending markets)

### 5. **Execution Timing**
- Signals generated: End of bar (on_bar)
- Execution: Start of next bar (at open)
- This realistic timing slightly reduces performance vs backtesting
- Always use `execute_on_next_open=True` for accuracy

---

## Quick Reference Card

```
ENTRY: Conversion > Base AND Conversion > Leading Span B AND Price > Base
        (+ optional: RSI > 50, CCI > 0, Price > EMA20)

EXIT:   Price < Base (stop loss)
        OR Price > Leading Span B (take profit)
        OR Conversion < Base (trend reversal)
        (+ optional filters)

SIGNAL: Generated at bar close
EXECUTION: Next bar open

OPTIMIZE: Try 9/26/52 first, then adjust filters
```

---

*Last Updated: November 3, 2025*
*Strategy Status: Production Ready*
