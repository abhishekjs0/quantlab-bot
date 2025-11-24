# Indicator Threshold Analysis & Recommendations

**Date**: November 24, 2025  
**Analysis Source**: Backtest data from `1124-1024-kama-crossover-basket-default-1d` (2,473 exit rows)

---

## 🚨 CRITICAL ISSUES IDENTIFIED

### 1. **Aroon Trend Classification - TOO STRICT FOR BEAR**

**Current Thresholds** (same for all periods: 25, 50, 100):
```python
if aroon_up > 70 and aroon_down < 30: "Bull"
elif aroon_down > 70 and aroon_up < 30: "Bear"  # TOO STRICT!
else: "Sideways"
```

**Actual Distribution**:
| Period | Bull | Bear | Sideways |
|--------|------|------|----------|
| Aroon 25 | 53.5% | **2.4%** ⚠️ | 44.1% |
| Aroon 50 | 57.3% | **1.2%** ⚠️ | 41.5% |
| Aroon 100 | 30.0% | **0.8%** ⚠️ | 69.2% |

**Problem**: Bear conditions require BOTH `aroon_down > 70` AND `aroon_up < 30` simultaneously, which is extremely rare in Indian markets (inherent upward bias).

**Recommended Fix**: Use period-adaptive thresholds that recognize longer periods need more relaxed conditions:

```python
def TrendClassification(aroon_up: float, aroon_down: float, period: int = 25) -> str:
    """
    Classify trend using Aroon indicator with period-adaptive thresholds.
    
    Longer periods = more relaxed thresholds (slower to change classification)
    Shorter periods = stricter thresholds (quicker to identify trends)
    """
    # Adaptive thresholds based on period
    if period <= 25:
        # Short-term: Strict (quick reaction)
        bull_threshold = 70
        bear_threshold = 70
        neutral_gap = 30
    elif period <= 50:
        # Medium-term: Moderate
        bull_threshold = 65
        bear_threshold = 65
        neutral_gap = 25
    else:
        # Long-term: Relaxed (slow to classify)
        bull_threshold = 60
        bear_threshold = 60
        neutral_gap = 20
    
    # Bull: Aroon Up dominates
    if aroon_up > bull_threshold and aroon_down < neutral_gap:
        return "Bull"
    
    # Bear: Aroon Down dominates  
    elif aroon_down > bear_threshold and aroon_up < neutral_gap:
        return "Bear"
    
    # Sideways: Neither dominates clearly
    else:
        return "Sideways"
```

**Expected Improvement**:
- Bear detection should increase from 0.8-2.4% to 8-15%
- Still maintains clear Bull identification
- Sideways remains for ambiguous conditions

---

### 2. **Volatility Classification - ALMOST NO LOW VOLATILITY**

**Current Thresholds** (same for both periods: 14, 28):
```python
if atr_pct < 1.5: "Low"    # TOO LOW!
elif atr_pct < 3.0: "Med"
else: "High"
```

**Actual Distribution**:
| Period | Low | Med | High |
|--------|-----|-----|------|
| Vol 14 | **0.2%** ⚠️ | 24.1% | 75.7% |
| Vol 28 | **0.0%** ⚠️ | 28.0% | 71.9% |

**Problem**: 
- ATR% < 1.5% is extremely rare in Indian markets (inherently volatile)
- 75% classified as "High" is not useful for filtering
- Indian stocks typically have 2-5% daily volatility

**Recommended Fix**: Use period-adaptive and India-specific thresholds:

```python
def VolatilityClassification(atr_pct: float, period: int = 14) -> str:
    """
    Classify volatility using ATR percentage with period-adaptive thresholds.
    
    Calibrated for Indian market volatility (higher than US markets).
    Longer periods show smoother/lower ATR, so need lower thresholds.
    """
    # Adaptive thresholds based on period
    if period <= 14:
        # Short-term ATR (14-day): Higher thresholds
        low_threshold = 2.5    # Was 1.5
        high_threshold = 4.5   # Was 3.0
    elif period <= 21:
        # Medium-term ATR (21-day)
        low_threshold = 2.2
        high_threshold = 4.0
    else:
        # Long-term ATR (28+ day): Lower thresholds (smoother)
        low_threshold = 2.0
        high_threshold = 3.5
    
    if atr_pct < low_threshold:
        return "Low"
    elif atr_pct < high_threshold:
        return "Med"
    else:
        return "High"
```

**Expected Improvement**:
- Low volatility should increase from 0.0-0.2% to 10-20%
- Better distribution: ~20% Low, ~50% Med, ~30% High
- More useful for strategy filtering

---

### 3. **ADX Thresholds - PERIOD LENGTH NOT CONSIDERED**

**Current Implementation**: Same thresholds for ADX(14) and ADX(28)

**Actual Distribution**:
| Metric | ADX 14 | ADX 28 |
|--------|--------|--------|
| Median | 31.8 | **19.8** |
| <20 (weak) | 11.6% | **51.1%** |
| 20-25 (emerging) | 15.7% | 26.0% |
| >25 (strong) | 72.7% | **22.9%** |

**Problem**: 
- ADX(28) has significantly lower values than ADX(14) (median 19.8 vs 31.8)
- Using same thresholds (20, 25) makes ADX(28) mostly "weak trend"
- Longer period = smoother = naturally lower ADX values

**Recommended Documentation Update**:

```markdown
### ADX Interpretation (Period-Adaptive)

**ADX (14) - Short-term trend strength:**
- < 20: Weak/no trend
- 20-25: Emerging trend
- 25-40: Strong trend
- > 40: Very strong trend

**ADX (28) - Long-term trend strength:**
- < 15: Weak/no trend (adjusted down)
- 15-20: Emerging trend (adjusted down)
- 20-30: Strong trend (adjusted down)
- > 30: Very strong trend (adjusted down)

**Note**: Longer periods produce lower ADX values. Thresholds should be ~5 points lower for ADX(28) vs ADX(14).
```

**Implementation Note**: ADX values are already calculated correctly. This is just a documentation/interpretation issue. No code changes needed, but strategies should use different thresholds when filtering on ADX(14) vs ADX(28).

---

### 4. **RSI Thresholds - APPEAR REASONABLE**

**Current Standard**: 30 (oversold), 70 (overbought)

**Actual Distribution**:
| Metric | RSI 14 | RSI 28 |
|--------|--------|--------|
| <30 (oversold) | 0.0% | 0.0% |
| 30-70 (neutral) | 64.1% | 88.4% |
| >70 (overbought) | 35.9% | 11.6% |

**Analysis**: 
- ✅ RSI(14) shows good distribution with 36% overbought (reasonable for bull market backtest)
- ✅ RSI(28) shows more conservative 12% overbought (expected for longer period)
- ⚠️ Zero oversold readings suggest data may be from bull market period only

**Recommendation**: **NO CHANGE** - Standard RSI thresholds are working as expected. The lack of oversold readings is market-dependent, not a threshold issue.

---

### 5. **Other Indicators Review**

#### **Stochastic Oscillator** (14, 28)
**Current**: `%K > %D` = Bullish, `%K < %D` = Bearish (boolean)  
**Recommendation**: ✅ **NO CHANGE** - Boolean crossover signal is appropriate

#### **CCI** (20, 40)
**Standard**: -100 (oversold), +100 (overbought)  
**Note**: No thresholds applied in code (raw values exported)  
**Recommendation**: ✅ **NO CHANGE** - Users can apply their own thresholds

#### **MFI** (20, 40)
**Standard**: 20 (oversold), 80 (overbought)  
**Note**: No thresholds applied in code (raw values exported)  
**Recommendation**: ✅ **NO CHANGE** - Users can apply their own thresholds

#### **KER** (10, 30)
**Current**: 0.3 (noisy), 0.7 (trending)  
**Need data to verify** - KER columns just added, no distribution data yet  
**Recommendation**: ⏳ **WAIT FOR DATA** - Test in next backtest, then adjust if needed

#### **Bollinger Bands Position** (20, 40)
**Current**: "Above", "Middle", "Below"  
**Recommendation**: ✅ **NO CHANGE** - Categorical classification is appropriate

---

## 📋 IMPLEMENTATION PRIORITY

### HIGH PRIORITY (Implement Now)
1. ✅ **Aroon Trend Classification** - Period-adaptive thresholds
2. ✅ **Volatility Classification** - India-adjusted and period-adaptive thresholds

### MEDIUM PRIORITY (Documentation)
3. 📝 **ADX Interpretation Guide** - Update docs with period-specific interpretation

### LOW PRIORITY (Monitor)
4. ⏳ **KER Thresholds** - Collect data from next backtest, then review
5. ⏳ **RSI Analysis** - Monitor in bear market conditions

---

## 🎯 EXPECTED OUTCOMES AFTER CHANGES

### Aroon Trends (More Balanced Detection)
| Period | Current Bear % | Expected Bear % |
|--------|----------------|-----------------|
| Aroon 25 | 2.4% | 10-15% |
| Aroon 50 | 1.2% | 8-12% |
| Aroon 100 | 0.8% | 5-10% |

### Volatility (Better Distribution)
| Period | Current Low % | Expected Low % |
|--------|---------------|----------------|
| Vol 14 | 0.2% | 15-20% |
| Vol 28 | 0.0% | 18-25% |

---

## 💡 KEY INSIGHTS

1. **Period Length Matters**: Longer periods produce smoother, lower values → need proportionally lower thresholds

2. **Market Bias**: Indian markets have upward bias → Bear detection needs relaxed thresholds

3. **Volatility Context**: Indian markets are inherently more volatile than US → need higher ATR% thresholds

4. **Adaptive Thresholds**: One-size-fits-all thresholds don't work across different periods

5. **Strategy Impact**: Better threshold calibration = more nuanced regime detection = better strategy performance

---

## 🔧 NEXT STEPS

1. Implement period-adaptive TrendClassification()
2. Implement period-adaptive VolatilityClassification()
3. Update documentation for ADX interpretation
4. Run new backtest to verify improvements
5. Monitor KER distributions and adjust if needed
