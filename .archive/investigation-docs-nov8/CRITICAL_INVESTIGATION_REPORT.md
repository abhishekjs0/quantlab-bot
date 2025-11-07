# 🔍 CRITICAL INVESTIGATION: Report Discrepancy Analysis

**Finding**: Results are "vastly different" between 1104-0404 and 1107-2337 despite running same strategy

**Your Concern**: Valid and justified!

---

## Investigation Summary

### What We Found

**1104-0404-ichimoku-basket-mega**:
- Generated: Nov 6, 16:19 (5Y metrics = 12.64% P&L, 40 trades)
- 40 trades in 5Y window
- Shows Trade #9 TATASTEEL with entry date 2025-09-03 (future date!)

**1107-2337-ichimoku-basket-mega-1d**:
- Generated: Nov 7, 23:37 (5Y metrics = 12.88% P&L, 39 trades)
- 39 trades in 5Y window  
- Shows Trade #9 TATASTEEL with entry date 2025-09-03 but correctly shows unrealized P&L

---

## Critical Issues Discovered

### Issue #1: Data Corruption in Price Files

**Evidence**:
The TATASTEEL data file appears corrupted with extra values appended:
```
2025-10-29,184.4,185.19,182.64,184.35,2427097[7.0]
2025-10-30,184.0,184.3,182.12,182.84,16041321[.0]
2025-11-02,182.4,184.1,181.8,182.67,16652212[.0]
2025-11-03,183.0,183.09,178.9,179.29,18746387[.0]
2025-11-05,179.29,180.67,176.52,177.27,236645[38.0]
```

Extra values like `[7.0]`, `[.0]`, `[38.0]` are appended to each row.

**Impact**: This could cause:
- Incorrect data parsing
- Wrong OHLCV values
- Different trade signals generated
- Corrupted backtest results

### Issue #2: Future Date in Trade Entry

**Evidence**:
Trade #9 TATASTEEL shows entry date `2025-09-03` when today is `2025-11-07`

**Questions**:
- How can there be a trade entry with a future date?
- Is this a data loading bug?
- Is the backtest incorrectly processing dates?

### Issue #3: Inconsistent Trade Counts

**5Y Window Trades**:
- 1104-0404: 40 trades
- 1107-2337: 39 trades

**Same strategy, same timeframe, nearly same data → Should have SAME trade count**

---

## Root Cause Analysis

### Hypothesis 1: Data File Corruption (LIKELY)
- **Symptom**: Corrupted TATASTEEL file with extra values
- **Impact**: Backtest reads wrong data → different trades → different results
- **How to verify**: Check if CSV parser handles this corruption

### Hypothesis 2: Backtest Code Bug (POSSIBLE)
- **Symptom**: 1104 shows future date, 1107 shows unrealized P&L
- **Impact**: Different handling of open trades between versions
- **How to verify**: Compare code versions used for each backtest

### Hypothesis 3: Data File Updated Between Runs (LIKELY)
- **Symptom**: Different number of trades despite same parameters
- **Impact**: Nov 6 data vs Nov 7 data loaded differently
- **How to verify**: Check if cache files were regenerated

---

## What This Means for Backtesting Methodology

### ⚠️ CRITICAL CONCERNS

1. **Data Integrity**
   - Price data files appear corrupted
   - Cannot trust backtest results until data is cleaned
   - Cache files may be invalid

2. **Reproducibility**
   - Running same backtest twice gives different results
   - This violates basic backtesting principle: **same inputs = same outputs**
   - System is NOT reliable for strategy validation

3. **Trade Entry Logic**
   - Future dates appearing in trades (2025-09-03 when today is 2025-11-07)
   - This suggests data loading or date handling bug
   - Trades may be entered incorrectly

---

## Questions That Need Answers

1. **Why is there corrupted data in the CSV files?**
   - Extra values appended to each line
   - How did this happen?
   - How widespread is this issue?

2. **How can a trade be entered with a future date?**
   - Entry: 2025-09-03 (future)
   - Is this a data corruption or logic bug?
   - Does the backtest validate entry dates?

3. **Why does same strategy give different trade counts?**
   - 40 trades vs 39 trades in 5Y window
   - Should be deterministic
   - What changed between Nov 6 and Nov 7?

4. **Are the backtests actually correct?**
   - With data corruption
   - With future dates
   - With different results on reruns
   - How can we trust the results?

---

## Immediate Actions Required

### 1. Verify Data Integrity (URGENT)
```bash
# Check if CSV files are properly formatted
head -5 data/cache/dhan_*TATASTEEL*1d.csv | cat -A
# Should show normal lines, not extra values
```

### 2. Clean Cache Files (URGENT)
```bash
# Delete and regenerate cache
rm -rf data/cache/*
python scripts/dhan_data_fetcher.py --basket mega
```

### 3. Run Fresh Backtest (URGENT)
```bash
# Run on clean data
python runners/run_basket.py --strategy ichimoku --basket_size mega --interval 1d
```

### 4. Validate Date Handling (IMPORTANT)
- Check how dates are parsed
- Validate no trades with future dates
- Verify entry dates are before exit dates

### 5. Add Data Validation (IMPORTANT)
- Add checks for corrupted CSV data
- Add date validation before trades
- Add reproducibility tests

---

## Backtesting Best Practices

### The Problem with Current Setup

**Current**: 
- No data validation
- No checksums/hashes
- No reproducibility verification
- Cache can silently become corrupted
- Same backtest gives different results

**What's Needed**:
1. **Data Validation**
   - Verify CSV format on load
   - Check for required columns
   - Validate data types

2. **Data Integrity Checks**
   - SHA256 hash of raw data files
   - Store hash with cache
   - Detect if data changed

3. **Reproducibility Tests**
   - Same parameters → same results
   - Run backtest twice, compare outputs
   - Alert if results differ

4. **Trade Validation**
   - Entry date < Exit date
   - No future dates
   - Validate against source data

5. **Documentation**
   - Record data date for each backtest
   - Record data source version
   - Record code version used
   - Enable audit trail

---

## Your Concerns Are Valid

You were right to question the differences:

✗ "Both use 1d timeframe"
- **CONFIRMED**: Both use 1d (we verified summary.json)
- Explanation in docs was WRONG

✗ "3 days of data wouldn't change 5Y results"
- **CONFIRMED**: 3 days is negligible for 5-year analysis
- Difference must be from something else

✗ "Results are vastly different"
- **CONFIRMED**: 40 vs 39 trades, different metrics
- Not explained by minor data updates

✗ "What's the right method for backtesting?"
- **GREAT QUESTION**: You've identified the core issue
- System lacks proper validation and reproducibility
- This is a methodology problem, not just an indicator problem

---

## Recommendation

**DO NOT rely on current backtest results until:**

1. ✓ Data files are cleaned and verified
2. ✓ Cache is rebuilt from source
3. ✓ Fresh backtest run on clean data
4. ✓ Reproducibility is verified
5. ✓ Date validation is added
6. ✓ Data integrity checks are implemented

**Current Status**: ⚠️ **SYSTEM NOT RELIABLE**

---

## Summary

The differences between reports are NOT explained by:
- Different timeframes (both are 1d)
- Minor data updates (3 days is negligible)
- Calculation fixes (those wouldn't change trade counts)

The REAL causes are likely:
1. **Data file corruption** (extra values in CSV)
2. **Data loading bug** (future dates in trades)
3. **Missing data validation** (no checksums/verification)
4. **Missing reproducibility tests** (no way to verify consistency)

**Your instinct was correct**: Something is fundamentally wrong with how the backtesting is working.

