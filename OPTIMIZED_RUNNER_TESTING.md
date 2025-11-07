# Optimized Runner Testing Guide

## Quick Start: Test for Speed & Accuracy

### Step 1: Run on Small Basket (Baseline)
```bash
# Original version
time /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python -m runners.run_basket \
  --basket_file data/basket_test.txt --strategy ema_crossover --use_cache_only

# Note the total time (should be ~10-20 seconds)
```

### Step 2: Run Optimized Version on Same Basket
```bash
# Optimized version
time /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python -m runners.run_basket_optimized \
  --basket_file data/basket_test.txt --strategy ema_crossover --use_cache_only

# Note the total time (should be ~5-10 seconds, roughly 2x faster)
```

### Step 3: Verify Bit-for-Bit Identical Results
```bash
# Compare the trade files
ls -la reports/

# Look at the two report folders (timestamps should be close)
# They should have similar names: HHMM-ss-ema-crossover-basket-test-1d

# Compare key metrics
diff -u <(sort reports/*/consolidated_trades_5Y.csv | head -20) \
         <(sort reports/*/consolidated_trades_5Y.csv | head -20)

# Compare portfolio metrics
diff reports/*/portfolio_key_metrics_5Y.csv
```

---

## Full Comparison Test (Mega Basket)

### Baseline: Original Runner
```bash
echo "=== ORIGINAL RUNNER START ===" && date

time /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python -m runners.run_basket \
  --basket_file data/basket_mega.txt --strategy ema_crossover --use_cache_only

echo "=== ORIGINAL RUNNER END ===" && date

# Save report folder name
ORIGINAL_REPORT=$(ls -td reports/[0-9]*-ema-crossover-basket-mega-1d | head -1)
echo "Original report: $ORIGINAL_REPORT"
```

### Optimized: Optimized Runner  
```bash
echo "=== OPTIMIZED RUNNER START ===" && date

time /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python -m runners.run_basket_optimized \
  --basket_file data/basket_mega.txt --strategy ema_crossover --use_cache_only

echo "=== OPTIMIZED RUNNER END ===" && date

# Save report folder name
OPTIMIZED_REPORT=$(ls -td reports/[0-9]*-ema-crossover-basket-mega-1d | head -1)
echo "Optimized report: $OPTIMIZED_REPORT"
```

### Validation: Compare Results
```bash
# Set these based on above
ORIGINAL_REPORT="reports/1108-0022-ema-crossover-basket-mega-1d"
OPTIMIZED_REPORT="reports/1108-0103-ema-crossover-basket-mega-1d"

echo "Comparing results..."
echo ""
echo "=== TRADES COMPARISON (5Y) ==="
diff -u "$ORIGINAL_REPORT/consolidated_trades_5Y.csv" "$OPTIMIZED_REPORT/consolidated_trades_5Y.csv" | head -50

echo ""
echo "=== METRICS COMPARISON (5Y) ==="
diff -u "$ORIGINAL_REPORT/portfolio_key_metrics_5Y.csv" "$OPTIMIZED_REPORT/portfolio_key_metrics_5Y.csv"

echo ""
echo "=== EQUITY CURVE COMPARISON (5Y) ==="
diff -u "$ORIGINAL_REPORT/portfolio_daily_equity_curve_5Y.csv" "$OPTIMIZED_REPORT/portfolio_daily_equity_curve_5Y.csv" | head -20
```

---

## What to Check For Accuracy

### ✅ PASS Criteria (Identical Results)
- Trade count matches (710 trades in MAX)
- Portfolio metrics match exactly:
  - Total return %
  - Win rate %
  - Max drawdown
  - Sharpe ratio
- Equity curves are identical
- Holding times match

### ⚠️ WARN Criteria (Minor Differences)
- Rounding differences in last decimal places (acceptable)
- File generation order differs (acceptable)
- Timestamp differences (acceptable)

### ❌ FAIL Criteria (Accuracy Lost)
- Trade count differs
- Entry/exit prices differ
- Portfolio return differs by >0.01%
- Equity curves diverge

---

## Debugging: If Results Differ

### 1. Check Indicator Calculations
```bash
# Look for NaN differences
grep -i "nan" $ORIGINAL_REPORT/consolidated_trades_MAX.csv | wc -l
grep -i "nan" $OPTIMIZED_REPORT/consolidated_trades_MAX.csv | wc -l

# Should be identical
```

### 2. Check Trade Timing
```bash
# Get first 5 trades from each
head -6 $ORIGINAL_REPORT/consolidated_trades_MAX.csv | tail -5 > /tmp/orig_trades.txt
head -6 $OPTIMIZED_REPORT/consolidated_trades_MAX.csv | tail -5 > /tmp/opt_trades.txt

diff /tmp/orig_trades.txt /tmp/opt_trades.txt
```

### 3. Revert if Issues Found
```bash
# Go back to original only
rm runners/run_basket_optimized.py
git checkout runners/run_basket.py

# Original remains untouched (this was the safety measure)
```

---

## Performance Expected

| Operation | Original | Optimized | Speedup |
|-----------|----------|-----------|---------|
| Symbol loop | N/A | N/A | ~1x (unchanged) |
| Trade iteration (iterrows) | 1.0x | 0.5x | **2x faster** |
| Window processing | 1.0x | 1.0x | ~1x (unchanged) |
| Portfolio building | 1.0x | 1.0x | ~1x (unchanged) |
| **Overall** | **1.0x** | **~0.7x** | **~1.4x faster** |

*Note*: Overall speedup lower than iteration speedup because trade iteration is only 60-70% of total runtime.

---

## Next Optimization Phases

Once itertuples is validated, consider:

1. **Pre-calculate indicators** (5x speedup on indicator lookup)
2. **Vectorize portfolio building** (already partially done)
3. **Parallelize symbol processing** (2-4x with 4 cores)
4. **Cache dataframe slices** (avoid re-slicing)

---

## Files

- `runners/run_basket_optimized.py` - Optimized version
- `PERFORMANCE_ANALYSIS.md` - Detailed analysis document
- This file - Testing guide

## Questions?

Check results with:
```bash
# See all differences
diff -u reports/*/consolidated_trades_MAX.csv | grep -E "^[-+]" | head -50
```
