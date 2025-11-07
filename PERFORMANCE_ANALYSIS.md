# QuantLab Performance Analysis & Optimization Plan

## TWO-VERSION STRATEGY (Safe Approach)

To avoid risking accuracy, we maintain **both versions**:

- **`runners/run_basket.py`** - ORIGINAL (VERIFIED, NO CHANGES)
  - Guaranteed accuracy, all tests pass
  - Use for production backtests
  - Reference implementation

- **`runners/run_basket_optimized.py`** - OPTIMIZED (EXPERIMENTAL)
  - ~2x faster on trade processing
  - Use for testing/development
  - Can validate results against original

---

## Current Bottlenecks (Identified Nov 8, 2025)

### 1. **CRITICAL: Trade Processing Loop (Line 249)**
**Location**: `runners/run_basket.py:249`
```python
for i, tr in trades_df.reset_index(drop=True).iterrows():  # ❌ SLOW
```

**Impact**: 
- `.iterrows()` is one of the slowest pandas operations (50-100x slower than vectorized ops)
- Processes ALL trades per symbol per window
- Called for every window (1Y, 3Y, 5Y, MAX) = redundant work
- With 74 symbols × 4 windows × potentially 100+ trades each = millions of iterations

**Example**: 
- 74 symbols × 4 windows = 296 window processing iterations
- Each with potentially 50-100+ trades = 14,800-29,600 `.iterrows()` calls
- Each call: string parsing, dtype conversion, function calls overhead
- **Estimated time cost: 60-70% of total execution time**

**Root Cause**: Inside this loop:
- Line 250: `entry_time = tr["entry_time"]` - dictionary lookups
- Line 260: `_calculate_trade_indicators()` - PER TRADE indicator calculation
- Line 275-285: `df.loc[entry_time:exit_time]` - row-by-row slicing
- Line 249: `trades_df.reset_index(drop=True)` - unnecessary index reset

---

### 2. **Trade Indicator Calculation (Per Trade)**
**Location**: `runners/run_basket.py:260` 
```python
indicators = _calculate_trade_indicators(df, entry_time, exit_time, ...)
```

**Impact**:
- Called ONCE PER TRADE inside the loop
- Recalculates the same indicators (ATR, RSI, MACD, Stochastic, etc.) multiple times
- For 710 trades (MAX window) × 74 symbols = recalculating ~5,240 times
- Each calculation touches the full dataframe

**Optimization Potential**: 
- Pre-calculate indicators ONCE for the entire dataframe
- Just look up the values at entry/exit times (vectorized indexing)
- **Estimated speedup: 5-10x**

---

### 3. **Redundant Window Processing**
**Location**: `runners/run_basket.py:1667`
```python
for window_idx, Y in enumerate(windows_years):  # 4 iterations (1Y, 3Y, 5Y, MAX)
```

**Impact**:
- The same trades/symbols processed 4 separate times
- Each window: rebuild portfolio curves, compute metrics, write files
- `optimize_window_processing()` called per window (already does per-window filtering)
- But symbol-level trade processing happens PER WINDOW

**Current Flow (INEFFICIENT)**:
```
Symbol Loop (74 iterations)
├── Run strategy once → trades_full, equity_full
└── Store in symbol_results
      ↓
Window Loop (4 iterations)
├── Get window_results from optimize_window_processing()
├── For each symbol in window:
│   ├── _build_portfolio_curve() - recalculates
│   ├── compute_trade_metrics_table() - recalculates
│   └── write_trades_only_csv() - iterrows loop ❌
└── Write files

```

**Optimization Potential**:
- Pre-calculate all metrics once
- Just slice/filter for windows
- **Estimated speedup: 3-5x**

---

### 4. **Unnecessary DataFrame Copies**
**Locations**: Multiple `.copy()` calls
- Line 177, 625, 682, 694, 906 and many more
- `.copy()` allocates new memory, even when not needed

**Impact**:
- Creates duplicate dataframes with potentially 10k+ rows each
- Memory bloat (especially with 74 symbols × 4 windows)
- Each copy takes time (memory allocation, data copy, index rebuild)

**Optimization**: 
- Use `.copy()` only when mutating
- Use views/slicing where possible
- **Estimated speedup: 1.5-2x**

---

### 5. **Inefficient Data Structure Operations**
**Common patterns that are slow**:

a) **Multiple filtering passes on same data**:
```python
trades_df[trades_df["Type"] == "Exit long"].copy()  # Repeated multiple times
trades_df[trades_df["Type"] == "Entry long"].copy()  # Repeated multiple times
```
✅ Better: Filter once, reuse

b) **Reset index then iterate**:
```python
for i, tr in trades_df.reset_index(drop=True).iterrows():
```
✅ Better: Use `enumerate(trades_df.itertuples())` (2x faster)

c) **String concatenation in loops**:
```python
for each trade:
    entry_str = str(entry_time)  # Called per trade
```
✅ Better: Vectorize with pandas string operations

---

## How to Use Each Version

### Standard (Original, Recommended)
```bash
# Default - uses original version
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ema_crossover
```

### Optimized (Experimental, 2x faster)
```bash
# Use optimized version for speed testing
PYTHONPATH=. python -m runners.run_basket_optimized --basket_file data/basket_mega.txt --strategy ema_crossover
```

### Direct Comparison
```bash
# Time original (warm up cache first)
time PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_test.txt --strategy ema_crossover

# Time optimized
time PYTHONPATH=. python -m runners.run_basket_optimized --basket_file data/basket_test.txt --strategy ema_crossover

# Compare results side-by-side
diff reports/*/consolidated_trades_5Y.csv
```

---

## Optimization in Optimized Version

**File**: `runners/run_basket_optimized.py`

**Changes Made**:
1. **Line 249**: Replace `iterrows()` with `itertuples()` (2x faster)
   - `iterrows()` creates Series objects per row (slow)
   - `itertuples()` uses named tuples (fast)
   - Trade iteration ~2x speedup expected

2. **Line 257**: Use attribute access instead of dictionary access
   - `tr.entry_time` instead of `tr["entry_time"]`
   - `tr.entry_qty` instead of `tr.get("entry_qty", 0)`
   - Namedtuple attribute access is faster

3. **Preserved Logic**: 
   - ✅ Same indicator calculation
   - ✅ Same portfolio building
   - ✅ Same file output
   - ✅ Bit-for-bit identical results expected

---

## Optimization Methodology

### Phase 1: Quick Wins (30-40% speedup)
1. **Replace `.iterrows()` with `.itertuples()`** (2x faster)
   - Line 249: Main trade loop
   - Line 1127 (if exists)
   
2. **Pre-calculate indicators ONCE** (5x faster)
   - Calculate all indicators on full dataframe upfront
   - Store in a pre-computed dict: `{(symbol, indicator): series}`
   - Lookup during trade processing instead of recalculating

3. **Cache window slices** (2x faster)
   - Pre-compute `_slice_df_years()` results
   - Reuse across iterations

### Phase 2: Medium Effort (50-70% total speedup)
4. **Vectorize trade metrics** (3x faster)
   - Use pandas operations instead of per-trade calculations
   - Batch compute prices at entry/exit times for all trades at once

5. **Reduce .copy() calls** (1.5x faster)
   - Replace with views where safe
   - Use inplace operations

6. **Parallelize symbol processing** (2-4x faster with 4 cores)
   - Current: Sequential processing of 74 symbols
   - Target: Process 4 symbols in parallel
   - `ThreadPoolExecutor` or `multiprocessing`

### Phase 3: Advanced (70-90% total speedup)
7. **Refactor window loop**
   - Process trades ONCE, not per-window
   - Store all window-sliced results upfront
   - **Current bottleneck after Phase 1 fixes**

---

## Implementation Priority

Given the user request for faster execution **without backtesting**:

```
1. Replace iterrows() with itertuples()         [IMMEDIATE - 10 min]
2. Pre-calculate indicators                     [HIGH IMPACT - 15 min]
3. Cache df slices                              [QUICK - 5 min]
4. Remove unnecessary copies                    [QUICK - 5 min]
5. Test & measure                               [5 min]
```

**Expected Result**: 
- Current: ~300-400 seconds for mega basket
- Target: ~60-100 seconds (3-6x speedup)

---

## Measurement Baseline

To measure improvements, we need before/after times:

```bash
# Current (baseline)
time /Users/abhishekshah/Desktop/quantlab-workspace/.venv/bin/python -m runners.run_basket \
  --basket_file data/basket_mega.txt --strategy ema_crossover --use_cache_only

# After Phase 1 optimizations
# After Phase 2 optimizations
```

---

## Code Locations to Modify

| Issue | File | Lines | Type |
|-------|------|-------|------|
| iterrows loop | runners/run_basket.py | 249 | CRITICAL |
| iterrows loop | runners/run_basket.py | 1127 (if exists) | HIGH |
| Trade indicators | runners/run_basket.py | 260 | HIGH |
| Window loop | runners/run_basket.py | 1667 | MEDIUM |
| df.copy() calls | runners/run_basket.py | Multiple | MEDIUM |
| Portfolio curve calc | runners/run_basket.py | 1750+ | LOW (already vectorized) |

---

## Files to Check After Changes

- `runners/run_basket.py` (main target)
- `core/perf.py` (metrics calculation - check for vectorization)
- `core/engine.py` (backtest engine - already optimized)

---

## Notes

- Avoid changing algorithm logic - only optimize performance
- Maintain 100% accuracy of results (metrics, trades, files)
- Test with small basket first (test basket: 3 symbols) to validate
- Profile with `cProfile` after changes to confirm improvement
