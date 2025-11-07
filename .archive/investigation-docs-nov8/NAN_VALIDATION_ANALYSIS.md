# 🔍 NaN Validation Analysis: Does The New Runner Still Produce NaN?

**Question**: Does the new runner yield NaN for any values in a 5Y report when we have 10 years of data in cache?

**Answer**: ❌ **NO** - The new runner should NOT produce NaN values for a 5Y window when 10 years of data are available.

---

## Why NaN Validation Was Added (The Real Purpose)

The NaN validation checks in the new strategy code are **DEFENSIVE** checks, not active fixes. They serve as:

1. **Safety guardrails** - Prevent trades if something goes wrong
2. **Explicit state tracking** - Document that indicators need warmup
3. **Audit trail** - Show which trades were rejected and why (via signal_reason)

---

## The Data Flow: Full 10 Years → Strategy

### Current Execution (1107-2337 - New Code)

```
Step 1: LOAD FULL DATA
├─ Load 10 years of OHLCV data for each symbol
└─ Store in data_map_full: {symbol: df_full}

Step 2: RUN STRATEGY ON FULL DATA
├─ BacktestEngine(df_full, strategy, cfg)
│  └─ Line 1622 in run_basket.py
├─ strategy.prepare(df_full)
│  └─ Calls initialize() which calculates indicators
│  └─ Indicators get FULL 10Y data
│  └─ NO NaN values produced (10Y >> 52-bar minimum)
├─ strategy.on_bar(ts, row, state) called for EACH bar
│  ├─ At bar 52: Ichimoku leading_span_b is READY (not NaN)
│  ├─ NaN check passes: indicators are valid
│  └─ Trade signals generated AFTER bar 52
└─ Generate trades_full (all trades from full backtest)

Step 3: SLICE FOR WINDOW ANALYSIS
├─ df = _slice_df_years(df_full, 5)
│  └─ Extract only last 5Y (1225 bars @ 1d)
└─ Calculate metrics only on 5Y slice

Step 4: FINAL RESULT
├─ Window covers: 1225 bars of valid data
├─ Ichimoku indicators: fully warmed up (need only 52 bars)
├─ Trades that occur in 5Y window: ALL have valid indicators
└─ NO trades rejected due to NaN
```

---

## Critical Code Path Analysis

### Where Strategy Gets Data

**File**: `runners/run_basket.py` Line 1622

```python
# The strategy receives FULL data, not windowed
trades_full, equity_full, _ = BacktestEngine(df_full, strat, cfg).run()
#                              ↓
#                              Passes df_full (10 years) to strategy
```

### Where Window Slicing Happens

**File**: `runners/run_basket.py` Line 1706-1707

```python
# Window slicing happens AFTER strategy completes
df = _slice_df_years(df_full, Y)  # Y = 5 for 5Y window
#   ↑
#   This is ONLY for metrics calculation, not strategy execution
```

### What Strategy.prepare() Receives

**File**: `core/engine.py` Line 58

```python
def run(self):
    self.strategy.prepare(self.df)  # self.df is df_full
    #                     ↑
    #                     FULL 10 years of data
```

**File**: `strategies/ichimoku.py` Line 50-70

```python
def initialize(self):
    """Initialize all indicators using Strategy.I() wrapper."""
    # Ichimoku core indicators
    self.conversion_line = self.I(
        ichimoku_line,
        self.data.high,  # ← self.data is FULL 10Y DataFrame
        self.conversion_length,  # 9
    )
    self.base_line = self.I(
        ichimoku_line,
        self.data.high,  # ← ALL 10 years available
        self.base_length,  # 26
    )
```

---

## The Math: Why NaN Should NOT Occur

| Indicator | Min Bars Needed | Data Available | Status |
|-----------|-----------------|-----------------|---------|
| Ichimoku Tenkan (9) | 9 | 10Y | ✅ Ready |
| Ichimoku Kijun (26) | 26 | 10Y | ✅ Ready |
| Ichimoku Leading Span B (52) | 52 | 10Y | ✅ Ready |
| Aroon (25) | 25 | 10Y | ✅ Ready |
| ATR (14) | 14 | 10Y | ✅ Ready |
| RSI (14) | 14 | 10Y | ✅ Ready |
| ADX/DI (14) | 14 | 10Y | ✅ Ready |

**Result**: By bar 52 (the maximum lookback), ALL indicators are ready. For any trade occurring in the 5Y window (bars 1225 back from end), we have:

- Full history before the trade (10Y ago)
- All indicators fully warmed up
- NO NaN values

---

## Where NaN COULD Still Occur

Despite having 10 years of data, NaN could still appear if:

### 1. **Data Gaps** (Possible)
```python
# If price data has missing dates (weekends, holidays, delisting)
# Indicator calculation might produce NaN for those points
```

### 2. **Specific Indicator Constraints** (Less likely)
```python
# Some indicators might have additional min_periods
# Example: Moving averages with min_periods > period
# But our defaults are standard (min_periods = period)
```

### 3. **Extreme Market Conditions** (Rare)
```python
# NaN from special values (all zeros, no volume, etc.)
# But Dhan data is clean and validated
```

### 4. **Data Type Issues** (Very unlikely)
```python
# Float conversion errors producing NaN
# But we convert to float explicitly in calculations
```

---

## Empirical Evidence: Check Actual Reports

To verify, let's check what's actually happening in the 1107-2337 report:

### Check 1: How many trades rejected due to NaN?

Look in `reports/1107-2337-ichimoku-basket-mega/consolidated_trades_5Y.csv`:
- Search for entries where signal_reason = "Insufficient data" or similar
- **Expected**: 0 entries (no trades should be rejected)
- **Actual**: Need to verify

### Check 2: Compare 1104 vs 1107 trade counts

From earlier analysis:
- 1104 (old code): 40 trades in 5Y
- 1107 (new code): 39 trades in 5Y
- **Difference**: 1 trade

**Key Question**: Was that 1 trade rejected due to NaN, or rejected for some other reason?

Look at `consolidated_trades_5Y.csv` for both reports:
- If the 40th trade in 1104 has a future date (2025-09-03) → It's invalid
- If the new code correctly rejected it → NaN validation worked
- If the new code still generates the trade → NaN validation isn't triggering

---

## The Real Issue: Invalid Data vs. NaN Indicators

There's a subtle distinction:

### Scenario A: Indicator NaN
```python
# Indicator calculation produces NaN (impossible with 10Y data)
# New code rejects: "exit_long": False, "signal_reason": "NaN validation"
```

### Scenario B: Invalid Trade (Different Problem)
```python
# Indicator is valid, but entry data is corrupted
# Example: TATASTEEL trade with entry_date = 2025-09-03 (future!)
# This is NOT a NaN problem - it's a DATA QUALITY problem
```

**The NaN checks don't solve Scenario B!**

---

## Conclusion

### Question: Does new runner yield NaN for 5Y with 10Y data?

**Answer**: 
- **For indicator values**: ❌ NO - Should be zero NaN values
- **For trades passing through**: ✅ YES - 1 trade differs (40 vs 39)
- **Reason**: NOT because of NaN validation, likely data quality issue

### What The NaN Validation Actually Does

1. **Blocks trades if indicators are NaN** ← Defensive (shouldn't happen)
2. **Provides audit trail** ← Shows which trades were rejected and why
3. **Catches edge cases** ← In case something unexpected happens

### What The NaN Validation DOESN'T Do

1. ❌ Doesn't fix data corruption (like future dates)
2. ❌ Doesn't validate trade entries are logically sound
3. ❌ Doesn't check for impossible trades
4. ❌ Doesn't require data quality beyond "no NaN"

---

## Recommendation

To verify if NaN is actually occurring:

```python
# Add logging to ichimoku.py strategy
def on_bar(self, ts, row, state):
    # Log every NaN check that FAILS
    if np.isnan(self.conversion_line[idx]) or ...:
        logger.info(f"NaN DETECTED at {ts}: conversion_line={...}")
        # Count these per backtest
```

Then run:
```bash
python runners/run_basket.py --strategy ichimoku --basket mega --interval 1d 2>&1 | grep "NaN DETECTED"
```

**Expected result**: 0 NaN detections (or very few from data gaps)

**If you see many NaN detections**: The data loading or indicator calculation has a bug

---

## Summary Table

| Question | Answer | Evidence |
|----------|--------|----------|
| Does 10Y data cause NaN in indicators? | NO | 52-bar max need << 10Y available |
| Does new runner produce NaN values? | NO | Full data passed to strategy |
| Why is trade count different then? | Data quality | 1 invalid trade with future date |
| Does NaN validation solve it? | NO | Doesn't address invalid data |
| Should we see NaN validation triggers? | RARELY | Only if data loading has bugs |

