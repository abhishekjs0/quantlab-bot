# Trend and Volatility Classification Guide

## Overview
The backtesting system automatically classifies each trade's market conditions using two key metrics: **Trend** and **Volatility**. These classifications help analyze which market conditions favor the strategy.

---

## 📈 Trend Classification

### Indicator Used: **Aroon Indicator (25-period)**

The Aroon indicator identifies trend changes and measures trend strength by tracking how recently the highest high and lowest low occurred within a lookback period.

### Components:
- **Aroon Up**: Measures uptrend strength (0-100)
  - Formula: `((25 - days_since_highest_high) / 25) × 100`
  - High values (>70) indicate strong uptrend
  
- **Aroon Down**: Measures downtrend strength (0-100)
  - Formula: `((25 - days_since_lowest_low) / 25) × 100`
  - High values (>70) indicate strong downtrend

### Classification Logic:

```python
def TrendClassification(aroon_up, aroon_down):
    if aroon_up > 70 and aroon_down < 30:
        return "Bull"       # Strong uptrend
    elif aroon_down > 70 and aroon_up < 30:
        return "Bear"       # Strong downtrend
    else:
        return "Sideways"   # Consolidation/ranging market
```

### Interpretation:

| Trend | Aroon Up | Aroon Down | Market Condition | Trading Implications |
|-------|----------|------------|------------------|---------------------|
| **Bull** | >70 | <30 | Strong uptrend, recent new highs | Long positions favorable |
| **Bear** | <30 | >70 | Strong downtrend, recent new lows | Short positions favorable (or avoid longs) |
| **Sideways** | Mixed | Mixed | Consolidation, no clear direction | Range-bound strategies, be cautious |

### Examples:
- **Aroon Up = 96, Aroon Down = 0** → **Bull** (just made new 25-day high)
- **Aroon Up = 4, Aroon Down = 92** → **Bear** (just made new 25-day low)
- **Aroon Up = 50, Aroon Down = 50** → **Sideways** (no clear trend)

---

## 📊 Volatility Classification

### Indicator Used: **ATR % (Average True Range as % of Price)**

ATR measures market volatility by analyzing the range of price movement. ATR % normalizes this across different price levels.

### Formula:
```
ATR % = (ATR / Close Price) × 100
```

Where ATR is the 14-period exponential moving average of True Range:
```
True Range = max(
    High - Low,
    abs(High - Previous Close),
    abs(Low - Previous Close)
)
```

### Classification Logic:

```python
def VolatilityClassification(atr_pct):
    if atr_pct < 1.5:
        return "Low"        # Low volatility
    elif atr_pct < 3.0:
        return "Med"        # Medium volatility
    else:
        return "High"       # High volatility
```

### Interpretation:

| Volatility | ATR % Range | Market Condition | Trading Implications |
|------------|-------------|------------------|---------------------|
| **Low** | <1.5% | Stable, tight ranges | Smaller stops possible, lower risk/reward |
| **Med** | 1.5% - 3.0% | Normal market conditions | Standard position sizing |
| **High** | >3.0% | Volatile, wide swings | Wider stops needed, higher risk/reward |

### Examples:
- **ATR % = 0.8%** → **Low** (calm market, prices moving <1% daily)
- **ATR % = 2.1%** → **Med** (normal market, ~2% daily movements)
- **ATR % = 5.5%** → **High** (volatile market, >5% daily swings)

---

## 🎯 Combined Analysis

### Strategy Performance by Market Regime:

| Trend | Volatility | Win Rate Impact | Suggested Action |
|-------|-----------|-----------------|------------------|
| Bull | Low | Variable | Small positions, tight stops |
| Bull | Med | **Often Best** | Standard strategy works well |
| Bull | High | Risky | Wide stops or reduce size |
| Sideways | Low | Poor | Avoid or use mean reversion |
| Sideways | Med | Variable | Range-bound strategies |
| Sideways | High | **Often Worst** | Avoid choppy markets |
| Bear | Low | Poor | Exit longs quickly |
| Bear | Med | Poor | Avoid long trades |
| Bear | High | Very Poor | Stay out or short only |

---

## 📊 Use Cases

### 1. **Post-Trade Analysis**
Review which market conditions produced best/worst trades:
```
Filter trades by: Trend="Bull" AND Volatility="Med"
→ Identify optimal entry conditions
```

### 2. **Strategy Optimization**
Optimize parameters separately for each regime:
```
Bull/Med: Aggressive entries, standard stops
Sideways/Low: Tighter entries, quicker exits
High Volatility: Wider stops, smaller positions
```

### 3. **Real-Time Filtering**
Add regime filters to strategy:
```python
if trend == "Sideways" and volatility == "Low":
    skip_trade()  # Avoid unfavorable conditions
```

### 4. **Position Sizing**
Adjust risk based on volatility:
```python
if volatility == "High":
    position_size *= 0.5  # Half size in volatile markets
```

---

## 🔍 Key Insights

### Why Aroon for Trend?
- **Time-based**: Focuses on recency of highs/lows (not just price levels)
- **Leading**: Identifies trend changes early
- **Clear thresholds**: 70/30 levels provide objective classifications
- **Works in all timeframes**: 25-period adapts to daily/weekly/monthly

### Why ATR % for Volatility?
- **Normalized**: Comparable across different price levels
- **Absolute measure**: True range captures gaps and limit moves
- **Standard metric**: Widely used for position sizing (e.g., 2× ATR stops)
- **Adaptive**: Automatically adjusts to market conditions

---

## 📈 Practical Example

**Trade Entry Analysis:**
```
Symbol: RELIANCE
Entry Date: 2025-01-19
Entry Price: 1316 INR

Calculated at Entry:
- ATR: 25 INR
- ATR %: 1.9% → Volatility = "Med"
- Aroon Up: 84
- Aroon Down: 16
- Trend = "Bull" (84 > 70 and 16 < 30)

Classification: Bull + Med Volatility
→ Favorable conditions for long entry
→ Standard position sizing appropriate
→ Use 2× ATR stop (50 INR) = 1266 stop loss
```

---

## 🎓 Further Reading

- **Aroon Indicator**: Developed by Tushar Chande in 1995
- **ATR**: Developed by J. Welles Wilder in 1978 (from "New Concepts in Technical Trading Systems")
- **Position Sizing**: Van Tharp's work on volatility-based position sizing

---

## 💡 Tips

1. **Backtest by Regime**: Analyze performance separately for each Trend × Volatility combination
2. **Avoid Sideways/High**: Often the worst combination (choppy, unpredictable)
3. **Favor Bull/Med**: Typically best risk/reward for trend-following strategies
4. **Use for Filters**: Skip trades when conditions are historically unprofitable
5. **Dynamic Stops**: Use ATR % for adaptive stop-loss placement (e.g., 2-3× ATR)
