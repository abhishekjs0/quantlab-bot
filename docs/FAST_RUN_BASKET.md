# fast_run_basket.py - Ultra-Fast Backtest Runner

## Overview

`fast_run_basket.py` is a lightweight runner designed for rapid parameter testing and benchmarking. It skips all file writing and generates only essential performance metrics, dramatically reducing runtime.

## Usage

```bash
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_midcap_highbeta.txt \
  --interval 1d \
  --workers 6
```

## Output Format

For each time window (1Y, 3Y, 5Y, MAX), it prints:

```
🔍 Window: 3Y
────────────────────────────────────────────────────────────────────────────────────────────────────

📈 TOTAL:
Window,Symbol,Net P&L %,Max equity drawdown %,Total trades,Profitable trades %,Profit factor,Avg P&L % per trade,Avg bars per trade,IRR %,Equity CAGR %
3Y,TOTAL,211.18,18.51,260,36.15,5.09,17.86,72,60.63,45.99

📌 First Symbol (ABSOLUTE):
3Y,ABSOLUTE,5.21,9.41,2,50.0,13.49,56.17,213,5.99,1.71

   📊 92 symbols with trades | 520 total trades
```

## Performance Improvement

| Metric | run_basket.py | fast_run_basket.py |
|--------|--------------|-------------------|
| File I/O | ✅ Full files | ❌ None |
| CSV Files | ✅ 20+ files | ❌ 0 files |
| Dashboard | ✅ Generated | ❌ Skipped |
| Equity Curves | ✅ Saved | ❌ Skipped |
| Output | ✅ Comprehensive | ✅ Summary only |
| Speed | Baseline | **~40% faster** |

## Key Features

✅ **Multi-window support** (1Y, 3Y, 5Y, MAX)  
✅ **Parallel processing** (auto-detects CPU cores)  
✅ **Minimal memory footprint** (no file storage)  
✅ **Real-time progress** (logs every 10 symbols)  
✅ **Error resilience** (continues on symbol failures)  

## Use Cases

### Rapid Parameter Sweep
Test 10 parameter combinations in sequence:
```bash
for fast in 3 9 13 21 34; do
  for slow in 9 21 55 144 233; do
    echo "Testing $fast/$slow..."
    python3 runners/fast_run_basket.py \
      --strategy your_strategy \
      --basket_file data/basket_test.txt
  done
done
```

### Quick Verification
Verify backtest logic before running full suite:
```bash
# Test on small basket first
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_test.txt
```

### Performance Profiling
Identify slow symbols quickly:
```bash
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_small.txt \
  --workers 1  # Single worker to profile
```

## Limitations

⚠️ **No file output** - Results are terminal-only  
⚠️ **No dashboard** - No visualization generated  
⚠️ **No equity curves** - Cannot see daily/monthly P&L  
⚠️ **Summary only** - TOTAL + first symbol per window  

## When to Use

| Scenario | Use fast_run_basket | Use run_basket |
|----------|-------------------|---------------|
| Testing parameters | ✅ Yes | ❌ No |
| Quick benchmarking | ✅ Yes | ❌ No |
| Production backtest | ❌ No | ✅ Yes |
| Detailed analysis | ❌ No | ✅ Yes |
| Report generation | ❌ No | ✅ Yes |

## Advanced Options

### Custom Worker Count
```bash
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_midcap_highbeta.txt \
  --workers 8  # Use 8 processes instead of auto
```

### Different Intervals
```bash
# 125-minute bars
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_midcap_highbeta.txt \
  --interval 125m

# 75-minute bars
python3 runners/fast_run_basket.py \
  --strategy kama_13_55_filter \
  --basket_file data/basket_midcap_highbeta.txt \
  --interval 75m
```

## Output Columns

| Column | Meaning |
|--------|---------|
| Window | Time period (1Y, 3Y, 5Y, MAX) |
| Symbol | Stock symbol or TOTAL |
| Net P&L % | Total profit as percentage |
| Max equity drawdown % | Worst peak-to-trough loss |
| Total trades | Number of completed trades |
| Profitable trades % | % of winning trades |
| Profit factor | Sum(wins) / Sum(losses) |
| Avg P&L % per trade | Average profit per trade |
| Avg bars per trade | Average holding period |
| IRR % | Internal rate of return |
| Equity CAGR % | Compound annual growth rate |

## Architecture

```
fast_run_basket.py
├── backtest_symbol()      - Worker function for single symbol
├── run_fast_backtest()    - Main orchestration
├── Parallel Processing    - multiprocessing.Pool
├── Trade Aggregation      - Per-window per-symbol
└── Metrics Computation    - compute_trade_metrics_table()
```

## Error Handling

Errors in individual symbols don't stop the process:
```
2025-11-15 09:18:11,487 - WARNING - ❌ Error for ABCAPITAL
2025-11-15 09:18:11,490 - WARNING - ❌ Error for PTCIL
...
✅ 98/98 symbols complete (with 5 errors)
```

## Future Enhancements

- [ ] CSV output option for selected windows
- [ ] Streaming output to avoid memory buildup
- [ ] Batch mode with multiple baskets
- [ ] Comparison table generation
- [ ] Export to database instead of files

