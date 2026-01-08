# Weekly Green Candle Hypothesis Test Results
## Large Basket (104 stocks) - Comprehensive Analysis

**Date:** January 3, 2026  
**Test Period:** 2016-2025  
**Basket:** Large Cap (104 symbols)

---

## Executive Summary

❌ **HYPOTHESIS VERDICT: NOT PROFITABLE**

The hypothesis of trading on the completion of a weekly green candle with specific Bollinger Band and body conditions **produces consistent losses** across all tested variants.

### Tested Variants:

| Variant | Trades | Win Rate | Avg Return | Total Return | Status |
|---------|--------|----------|-----------|--------------|--------|
| **STRICT** (Green + BB 1SD + Bigger Body) | 1,884 | 41.7% | -0.64% | **-1,197%** | ❌ Best (least bad) |
| MODERATE (Green + Bigger Body) | 12,100 | 40.5% | -0.63% | -7,604% | ❌ Worse |
| BB_ONLY (Green + BB 1SD) | 4,019 | 41.4% | -0.75% | -3,012% | ❌ Worse |
| RELAXED (Green Only) | 23,915 | 40.6% | -0.64% | -15,297% | ❌ Worst |

---

## Detailed Analysis (STRICT Variant - Best Performer)

### Core Problem

**Gross average price move: +0.10%** while **transaction costs: 0.74%**

This is the fundamental issue: The hypothesis generates signals where the subsequent price move is **so small it doesn't cover trading costs**.

### Entry/Exit Timing Breakdown

- **Winning trades avg move:** +4.07%
- **Losing trades avg move:** -2.73%
- **Difference (separation):** 6.80%

The issue is that winning and losing trades are NOT separated well. The filter conditions don't identify momentum continuation reliably.

### Return Distribution (1,884 Trades)

```
Return Range        Count    %      Status
>10%                 39     2.1%    Rare winners
5-10%               122     6.5%    Some winners
2-5%                277    14.7%    Winners
1-2%                156     8.3%    Winners
0.5-1%               89     4.7%    Break-even area
0-0.5%              102     5.4%    Break-even area
-0.5-0%             102     5.4%    Slight losses
-1--0.5%            116     6.2%    Slight losses
-2--1%              208    11.0%    Losses
-5--2%              409    21.7%    Major losses
-10--5%             227    12.1%    Major losses
<-10%                37     2.0%    Rare disasters
```

**Key finding:** 21.7% of trades lose 5-2%, but only 8.3% gain 1-2%. **Asymmetric risk.**

### Performance by Year

| Year | Trades | Avg Return | Total Return | Status |
|------|--------|-----------|--------------|--------|
| 2017 | 141 | +0.18% | +25.45% | ✅ Only profitable |
| 2019 | 179 | +0.03% | +5.49% | ✅ Barely profitable |
| 2021 | 105 | -0.02% | -1.90% | ~~ Break-even |
| 2025 | 277 | -1.44% | -398.42% | ❌ Very bad |

**Only 2 out of 10 years profitable.** Recent years (2024-2025) show **deterioration**.

### Performance by Month

```
Best months:   July (+7.4%), Sept (+10.9%)
Worst months:  Feb (-286%), March (-190%), May (-98%), Dec (-137%)
```

No consistent pattern - appears to be random seasonal variation.

---

## Why This Hypothesis Fails

### 1. **Signal Timing is Wrong**
- Signal occurs when weekly candle CLOSES green (Friday)
- Entry happens on NEXT Monday
- By Monday, the market has had a weekend + any gap
- The momentum is already exhausted or reversed

### 2. **Filters Don't Predict Continuation**
- Green candle with opening below BB 1SD and bigger body does NOT predict UP move
- Many such candles are exhaustion patterns (not continuation)
- Win rate of 41.7% < 50% break-even threshold

### 3. **Price Action is Too Small**
- Average gross move: only +0.10% (less than noise)
- Needs +0.74% just to break even on transaction costs
- Winners only +4.07% on average (rare)

### 4. **Portfolio-Level Impact**
- Testing ALL variants: MORE trades = WORSE results
- This suggests the signal quality DECREASES with relaxation
- Even strict filtering can't fix the fundamental flaw

---

## Recommendations

### ❌ Do NOT Trade This Hypothesis

The fundamental issue cannot be fixed with position sizing or stop losses - the signal itself has negative edge.

### ✅ Alternative Approaches to Test

1. **Reverse the Signal: Fade Green Candles**
   - When green candle closes near BB upper band
   - Sell on Monday, expecting reversal
   - Test if mean-reversion is the actual pattern

2. **Different Holding Period**
   - Instead of Monday-Friday hold, try:
     - Enter same week (Friday), hold 1 week (Thu close)
     - Enter on dips during the green week (intraday)
     - Use multiple timeframes (daily signals, not weekly)

3. **Condition Refinement**
   - Current conditions: Green + BB + Size
   - Try additional filters:
     - Volume increase during green week
     - RSI oversold before green week (setup scan)
     - Confluence with other timeframes (daily + weekly)
     - Specific market conditions (trend direction, sector strength)

4. **Entry/Exit Optimization**
   - Current: Enter Monday open, exit Friday close
   - Better options:
     - Enter Friday of signal week (better price discovery)
     - Exit when target hit (fixed risk:reward)
     - Use trailing stops instead of calendar exits

---

## Files Generated

- **Test Script:** `scripts/test_weekly_green_bb_variants.py`
- **Analysis Script:** `scripts/analyze_hypothesis_results.py`
- **Results CSV:** `reports/hypothesis_weekly_green_strict_results.csv`
- **This Report:** `reports/hypothesis_weekly_green_analysis.md`

---

## Data Summary

- **Symbols tested:** 104 (large cap basket)
- **Time period:** Jan 2016 - Dec 2025
- **Total signals generated:** 2,072 (STRICT variant)
- **Total trades executed:** 1,884 (some signals had no valid entry/exit)
- **Data source:** Dhan daily OHLC cached files

---

## Conclusion

**The hypothesis is fundamentally flawed as currently structured.** The pattern of weekly green candles does not predict profitable price movement on the following week's first trading day with weekly hold-to-close strategy.

The consistent loss of 0.64% per trade across 1,884 trades indicates the signal has **negative edge** rather than random chance.

**Suggested next step:** Test reversal hypothesis or different entry/exit logic rather than attempting to optimize this unprofitable pattern.
