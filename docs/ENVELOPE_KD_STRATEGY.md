# Envelope + Knoxville Divergence Strategy Guide

**Advanced trend-following strategy combining envelope-based mean reversion with divergence-based momentum confirmation**

---

## 📋 Strategy Overview

The **Envelope + Knoxville Divergence (Envelope + KD)** strategy is a sophisticated trading system that combines:

1. **Dynamic Envelope Filter** (SMA/EMA with bands) - Identifies support/resistance levels
2. **Knoxville Divergence (KD)** - Detects momentum divergences at pivot points
3. **Trend Filter** - Validates uptrend with basis slope and volatility confirmation
4. **Risk Management** - ATR-based or percent-based stops with time-based exits

This strategy is particularly effective in range-bound markets with distinct pivot points and momentum shifts.

---

## 🎯 Trading Rules

### Entry Conditions (All must be true):
1. **Bullish Knoxville Divergence** detected:
   - Lower low in price compared to previous pivot low
   - Higher momentum than previous pivot low
   - Stochastic %K below oversold level (30%)

2. **Price below envelope basis** (SMA/EMA)

3. **Trend Filter passes**:
   - Strict mode (default): Basis slope up AND volatility adequate
   - Loose mode: Basis slope up OR volatility adequate
   - Off mode: No trend filter

### Exit Conditions (Any can trigger exit):
1. **Take Profit**: Price crosses above upper envelope band
2. **Trailing Stop**: Price crosses below envelope basis (trailing stop)
3. **Bearish KD**: Bearish divergence signal detected:
   - Higher high in price vs previous pivot high
   - Lower momentum than previous pivot high
   - Stochastic %K above overbought level (70%)

---

## ⚙️ Configuration Parameters

### Envelope Parameters
```python
envelope_length = 200      # SMA/EMA period for basis calculation
envelope_percent = 14.0    # Band width as % of basis (e.g., 14% = ±14% bands)
use_ema_envelope = False   # True for EMA, False for SMA basis
```

**Example**: 
- Basis = SMA(200) of close
- Upper band = Basis × 1.14
- Lower band = Basis × 0.86

### Knoxville Divergence Parameters
```python
momentum_length = 20           # Period for momentum calculation
stoch_k_length = 70            # Stochastic %K period
stoch_k_smooth = 30            # SMA smoothing period for %K
stoch_d_smooth = 30            # SMA smoothing period for %D
stoch_ob = 70.0               # Overbought level (default 70%)
stoch_os = 30.0               # Oversold level (default 30%)
bars_back_max = 200           # Max bars to look back for previous pivot
pivot_left_bars = 2           # Bars to left of pivot for detection
pivot_right_bars = 2          # Bars to right of pivot for detection
```

**How KD Works**:
- Detects pivot highs and lows with divergence
- Compares current pivot with previous pivot
- Checks momentum direction change + stochastic confirmation
- Bullish KD: Price lower, momentum higher, stoch oversold
- Bearish KD: Price higher, momentum lower, stoch overbought

### Trend Filter Parameters
```python
trend_mode = "Strict"          # "Off", "Loose", or "Strict"
slope_lookback = 60            # Bars to look back for basis slope
use_atr_floor = False          # Enable ATR volatility floor
atr_volume_length = 14         # ATR period for volatility
min_atr_pct = 0.8             # Minimum ATR as % of price
```

**Trend Filter Logic**:
- **Strict**: Basis must be above its value 60 bars ago AND volatility adequate
- **Loose**: Either basis slope up OR volatility adequate
- **Off**: No trend filter applied

### Risk Management Parameters
```python
stop_type = "ATR"              # "ATR" for ATR-based, "Percent" for fixed %
init_sl_pct = 5.0             # % below entry for percent-based stop
stop_atr_length = 14          # ATR period for stop calculation
stop_atr_mult = 10.0          # ATR multiplier (stop = entry - mult×ATR)
time_stop_bars = 60           # Max bars in trade (0 = disabled)
```

**Stop Loss Examples**:
- **ATR mode**: If entry = 100, ATR = 1, mult = 10 → Stop = 100 - 10 = 90
- **Percent mode**: If entry = 100, init_sl_pct = 5 → Stop = 95

---

## 📊 Usage Examples

### Backtest with Default Parameters
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_test.txt \
  --strategy strategies.envelope_kd \
  --windows 1Y,3Y,5Y
```

### Backtest with Custom Parameters
```bash
PYTHONPATH=/Users/abhishekshah/Desktop/quantlab-workspace \
/opt/homebrew/bin/python3.11 runners/run_basket.py \
  --basket_file data/basket_test.txt \
  --strategy strategies.envelope_kd \
  --params '{
    "envelope_length": 150,
    "envelope_percent": 12.0,
    "momentum_length": 25,
    "trend_mode": "Loose",
    "stop_atr_mult": 8.0
  }' \
  --windows 1Y
```

### Generate Dashboard
```bash
/opt/homebrew/bin/python3.11 -m viz.dashboard <report-folder-name>
```

---

## 🔍 Strategy Analysis

### Strengths
1. **Mean Reversion Focus**: Trades price extremes (envelope bands)
2. **Divergence Confirmation**: Stochastic + pivot divergence = high-probability signals
3. **Trend Filtering**: Avoids counter-trend trades
4. **Flexible Risk Management**: Choice of ATR or fixed-% stops
5. **Parameterizable**: Easily adjustable for different market conditions

### Weaknesses
1. **Lag**: 200-bar SMA adds lag to trend identification
2. **Range-Bound**: Works best in ranging markets, struggles in strong trends
3. **Pivot Detection**: May miss trades in highly volatile markets
4. **Parameter Sensitivity**: Performance varies significantly with parameter changes

### Best Market Conditions
- ✅ Ranging/consolidating markets
- ✅ Moderate volatility (ATR 0.5-2% of price)
- ✅ Distinct pivot points and reversals
- ✅ Mean reversion environments

### Avoid During
- ❌ Strong directional trends
- ❌ Very low volatility (< 0.3% ATR)
- ❌ Earnings/news-driven gaps
- ❌ Market regime changes

---

## 🧪 Optimization Suggestions

### For Trending Markets
```python
trend_mode = "Off"          # Remove trend filter
envelope_length = 50        # Shorter SMA for faster response
stoch_os = 40.0            # Higher oversold threshold
```

### For Volatile Markets
```python
envelope_length = 300      # Longer SMA for stability
stoch_k_length = 100       # Longer stochastic period
use_atr_floor = True       # Enable volatility floor
min_atr_pct = 1.5         # Require higher volatility
```

### For Conservative Trading
```python
stop_atr_mult = 15.0       # Wider stops
init_sl_pct = 7.5         # Larger percent stop
time_stop_bars = 30        # Exit earlier
bars_back_max = 100        # Look back less far
```

### For Aggressive Trading
```python
stop_atr_mult = 6.0        # Tight stops
init_sl_pct = 2.0         # Small percent stop
bars_back_max = 400        # Look back further for divergence
```

---

## 📈 Performance Metrics to Monitor

| Metric | Target | Reason |
|--------|--------|--------|
| **Win Rate** | > 45% | Conservative system, should win nearly half trades |
| **Profit Factor** | > 1.5 | Winners must be 1.5x losers on average |
| **Sharpe Ratio** | > 1.0 | Risk-adjusted returns should be positive |
| **Max Drawdown** | < 20% | Preserve capital with stop losses |
| **Average Trade Length** | 20-50 bars | Not excessively long holding periods |
| **Monthly Consistency** | > 60% profitable months | Consistent monthly profitability |

---

## 🔧 Troubleshooting

### Few or No Trades Generated
- Lower `momentum_length` to make pivots easier to detect
- Increase `bars_back_max` to look back further for previous pivots
- Set `trend_mode = "Off"` to remove trend filter restriction
- Increase `envelope_percent` to widen bands (more entries)

### Too Many Losing Trades
- Increase `stoch_ob` / `stoch_os` thresholds (be more selective)
- Enable `use_atr_floor` for volatility confirmation
- Set `trend_mode = "Strict"` for trend validation
- Decrease `envelope_percent` (tighter bands = better mean reversion)

### Whipsaws and False Breakouts
- Increase `envelope_length` for smoother basis
- Increase `pivot_left_bars` / `pivot_right_bars` for stricter pivot detection
- Increase `stoch_k_length` for more stable stochastic
- Increase `stop_atr_mult` or `init_sl_pct` for wider stops

### Strategy Stops Too Frequently
- Decrease `stop_atr_mult` or increase `init_sl_pct`
- Increase `time_stop_bars` to allow more time for trade development
- Set `use_atr_floor = False` to avoid exiting on low volatility

---

## 📚 Related Documentation

- [Strategy Development Guide](DEVELOPMENT_WORKFLOW.md)
- [Backtesting Guide](BACKTEST_GUIDE.md)
- [Workflow Guide](WORKFLOW_GUIDE.md)
- [Technical Indicators](../utils/indicators.py)

---

## 🎓 Learning Resources

**Envelope Concept**:
- Moving average envelopes create dynamic support/resistance
- Bands expand/contract with volatility
- Price extremes (touching upper/lower band) often signal reversals

**Knoxville Divergence**:
- Compares price action with momentum indicators
- Divergence = price making new extreme but momentum doesn't
- Strong signal of weakening trend and reversal potential

**Stochastic Oscillator**:
- Compares close to high-low range over period
- Values 0-100, with 70+ = overbought, 30- = oversold
- Helps confirm divergence signals

---

*Strategy implementation adapted from TradingView Pine Script v6 for QuantLab backtesting engine.*
