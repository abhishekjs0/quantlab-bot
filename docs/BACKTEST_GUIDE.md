# Backtest Execution Guide

## Quick Start - Running Backtests (Default Method)

### Prerequisites
1. Activate virtual environment: `source .venv/bin/activate`
2. Ensure Dhan historical files are in `data/cache/` directory (system automatically loads from cache)
3. Use the consolidated symbol mapping file: `data/api-scrip-master-detailed.csv` (single source of truth)

### Default Command Structure (Recommended)
```bash
# Set PYTHONPATH and run backtest
PYTHONPATH=. python -m runners.run_basket --basket_file <basket> --strategy <strategy> --use_cache_only
```

**Important Notes:**
- **PYTHONPATH=.**: Required to ensure proper module loading from the project root
- **`--use_cache_only`**: Recommended default approach for consistent, fast backtesting using cached historical data
- **Run from project root**: All commands should be executed from the `/quantlab` directory
- **Module imports**: Always use module format (e.g., `python -m runners.run_basket`) not direct file execution

### Example Commands

**Run Donchian on mega basket (default method):**
```bash
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy donchian --use_cache_only
```

**Run Ichimoku strategy (default method):**
```bash
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku --use_cache_only
```

**Run EMA Cross strategy (default method):**
```bash
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ema_cross --use_cache_only
```

### Alternative Methods
For live data fetching (slower, requires API access):
```bash
PYTHONPATH=. python -m runners.run_basket --basket_file data/basket_mega.txt --strategy ichimoku
```

## Symbol Mapping - Single Source of Truth

### Consolidated Symbol Mapping File
**File:** `data/api-scrip-master-detailed.csv` (2,674 symbols mapped)

This is the **only** symbol mapping file you need. Previous duplicate files have been removed:
- ❌ `dhan_symbol_mapping_comprehensive.csv` (removed - was duplicate)
- ❌ `clean_symbol_mapping.csv` (removed - was subset)
- ✅ `api-scrip-master-detailed.csv` (master file - use this one)

### File Format
```csv
SYMBOL_NAME,SECURITY_ID,UNDERLYING_SYMBOL
RELIANCE,2885,RELIANCE
HDFCBANK,1333,HDFCBANK
ICICIBANK,4963,ICICIBANK
```

## Data Setup and Availability

### Cache Directory Structure
The system loads data from `data/cache/` directory:
```
data/cache/
  dhan_historical_2885.csv     # RELIANCE
  dhan_historical_1333.csv     # HDFCBANK
  dhan_historical_4963.csv     # ICICIBANK
  ... (345 total cache files)
```

### Mega Basket Coverage
**72 out of 73** mega basket symbols have available data in cache.

**Available symbols include:**
- RELIANCE, HDFCBANK, ICICIBANK, SBIN, BHARTIARTL
- INFY, ITC, WIPRO, ONGC, NTPC, COALINDIA
- TATASTEEL, HINDZINC, VEDL, ADANIPOWER, POWERGRID
- And 57 more... (full list available via data coverage check)

### Historical Data Format
```csv
date,open,high,low,close,volume
2019-12-31,682.6,686.69,676.97,678.82,6402372.0
2020-01-01,679.9,692.92,679.9,690.37,8096561.0
```

## Portfolio Calculation (Fixed Issues)

### Previous Issues (Now Resolved)
❌ **Portfolio return calculation bug** (FIXED): Previously showed impossible returns like 260,318.79% due to cumulative realized P&L being added every day after trade close instead of only on close date.

❌ **Duplicate symbol mapping files** (FIXED): System previously had 3 duplicate mapping files with same data but different column names.

### Current Portfolio Calculation Method
✅ **Correct realized P&L accumulation**: Trades contribute to portfolio P&L only once on their close date
✅ **Realistic returns**: Portfolio returns based on actual trade performance (e.g., 409% over 5+ years)
✅ **Single symbol mapping**: Uses consolidated `api-scrip-master-detailed.csv` as single source of truth

### Position Sizing and Leverage
- **Position size**: 5% of equity per trade (`qty_pct_of_equity = 0.05` in BrokerConfig)
- **Leverage**: System allows simultaneous positions that can exceed 100% allocation
- **Typical exposure**: Average 115%, max observed 264% (2.6x leverage)
- **Trading days with leverage**: ~58% of days exceed 100% allocation

This leverage behavior is **working as designed** for the strategy. To use cash-only approach, reduce `qty_pct_of_equity` in `core/config.py`.

## Strategy Parameters

### Default Parameters 
Most strategies work with default parameters (no `--params` needed):
```bash
# Uses default parameters automatically
python -m runners.run_basket --basket_file data/basket_mega.txt --strategy strategies.donchian --use_cache_only
```

### Custom Parameters (Advanced)
```bash
# Custom Donchian parameters (if needed)
python -m runners.run_basket --basket_file data/basket_mega.txt --strategy strategies.donchian --params '{"length":30}' --use_cache_only
```

## Performance Optimization

### For Large Baskets (20+ symbols)
- **Use smaller time windows first**: Start with `--period 1y` to test
- **Monitor memory usage**: Large baskets with ALL window can be memory intensive
- **Use background execution**: Append `&` to run in background for long-running tests
- **Check intermediate results**: Look for partial reports if interrupted

### Example Performance Command
```bash
# Run in background for large basket
nohup python -m runners.run_basket --basket_file data/basket_mega_with_data.txt --strategy ichimoku --params "{}" --use_cache_only > backtest.log 2>&1 &

# Monitor progress
tail -f backtest.log
```

## Common Issues & Solutions

### Error: "no local Dhan CSVs loaded" or "Cache missing for SYMBOL"
**Solution:** System expects data in `data/cache/` directory (automatically loaded):
- ✅ Data should be in: `data/cache/dhan_historical_{SECURITY_ID}.csv`
- ❌ Don't copy to: `data/dhan_historical_{SECURITY_ID}.csv` (not needed)
- Check symbol exists in mapping file: `data/api-scrip-master-detailed.csv`

### Error: "TypeError: Strategy.__init__() got unexpected keyword argument"
**Solution:** Remove `--params` argument for default strategy execution:
```bash
# Correct (no params needed)
python -m runners.run_basket --strategy strategies.donchian --use_cache_only

# Incorrect (unnecessary params)
python -m runners.run_basket --strategy strategies.donchian --params "{}" --use_cache_only
```

### Unrealistic Portfolio Returns (e.g., 260,318%)
**Status:** ✅ **FIXED** - This was due to portfolio calculation bug that has been resolved.
- Portfolio now correctly calculates returns based on actual trade P&L
- Typical expected returns: 400-500% over 5+ years (reasonable for leveraged strategy)

### Symbol Not Found in Mapping
**Solution:** 
1. Check if symbol exists: `grep "SYMBOL_NAME" data/api-scrip-master-detailed.csv`
2. Use exact symbol name from mega basket file
3. Verify corresponding cache file exists for the security ID

### Performance Issues with Large Baskets
**Solutions:**
- Use smaller baskets for testing (create custom `.txt` files)
- Monitor system memory during execution  
- Process mega basket in chunks if needed

## Output Files

### Files Generated Successfully ✅
The system generates comprehensive output files for each time window:

**Core Metric Files:**
- `portfolio_key_metrics_{window}.csv` - Performance metrics per symbol + portfolio total
- `summary.json` - Backtest metadata and configuration

**Trade Detail Files:**
- `consolidated_trades_{window}.csv` - All individual trades with entry/exit details
- `strategy_backtests_summary.csv` - Comprehensive metrics across all windows

**Portfolio Tracking Files:**
- `portfolio_daily_equity_curve_{window}.csv` - Daily portfolio values and exposure  
- `portfolio_monthly_equity_curve_{window}.csv` - Monthly portfolio summary

### Enhanced Performance Metrics (v2.0)
QuantLab now provides comprehensive performance analysis with improved accuracy:

#### **Risk-Adjusted Metrics**
- **Individual Trade Drawdown**: Maximum adverse movement during each trade using daily OHLC data
- **Symbol-Level Max Drawdown**: Uses highest individual trade drawdown (more meaningful than equity curve)
- **Run-up Analysis**: Maximum favorable movement during trades
- **Trade-by-Trade Risk Assessment**: Detailed risk exposure for each position

#### **Stop Loss Analysis (Available)**
The system supports stop loss implementation for strategy optimization:
- Engine-level stop loss via `on_entry()` method in strategies
- Returns `{"stop": price}` for automatic stop loss orders
- Performance comparison across different stop loss levels
- Analysis shows pure strategy signals often outperform stop loss variants

#### **Calculation Methodology**
```python
# Individual trade drawdown calculation
def calculate_trade_drawdown(entry_time, exit_time, entry_price, symbol_df):
    trade_data = symbol_df.loc[(symbol_df.index >= entry_time) & (symbol_df.index <= exit_time)]
    min_low = trade_data["low"].min()
    drawdown = (entry_price - min_low) / entry_price * 100
    return drawdown

# Symbol-level max drawdown (improved method)
symbol_max_drawdown = max(all_trade_drawdowns_for_symbol)
```
```csv
Window,Symbol,Net P&L %,Max equity drawdown %,Total trades,Profitable trades %,Profit factor,Avg P&L % per trade,Avg bars per trade,IRR %,Equity CAGR %
ALL,TOTAL,9.03,1.09,30,48.28,3.23,6.78,82,20.08,1.5
ALL,BHARTIARTL,16.09,0.49,6,80.0,29.35,16.21,138,28.64,0.72
```

**consolidated_trades_{window}.csv:**
```csv
Trade #,Symbol,Type,Date/Time,Signal,Price INR,Position size (qty),Position size (value),Net P&L INR,Net P&L %
1,RELIANCE,Exit long,2020-01-31,Close entry(s) order LONG,1423,35,49805,2100,4.22%
1,RELIANCE,Entry long,2020-01-19,LONG,1363,35,47705,,
```

### Calculation Issues Fixed

#### Individual Symbol Metrics Alignment (RESOLVED)
✅ **Net P&L % and Equity CAGR % Alignment**: Individual symbol calculations now use consistent methodology
- **Previous Issue**: Net P&L % used trade-based calculation while CAGR % used equity-based calculation
- **Current Implementation**: Both metrics now use equity curve data for mathematical consistency
- **Fix Applied**: Modified Net P&L % calculation in `runners/run_basket.py` lines 895-920 to use equity-based approach

**Verification Results:**
```csv
Window,Symbol,Net P&L %,Equity CAGR %,Status
1Y,ABCAPITAL,2.5,2.5,✅ Perfect alignment
1Y,ADANIPOWER,1.76,1.76,✅ Perfect alignment
3Y,ABCAPITAL,4.6,1.51,✅ Proper annualized relationship (4.6% total → 1.51% CAGR)
```

**Mathematical Consistency:**
1. **Same Data Source**: Both metrics use `symbol_equities` data
2. **Net P&L % Formula**: `(end_equity / start_equity - 1.0) * 100.0`
3. **CAGR % Formula**: `(end_equity / start_equity) ** (1.0 / years) - 1.0) * 100.0`
4. **Perfect 1Y Alignment**: When period is exactly 1 year, both formulas produce identical results

#### IRR vs CAGR Relationship (RESTORED)
✅ **Current Implementation**: IRR and CAGR calculated independently and both meaningful
- **IRR**: Trade-based metric including open positions at mark-to-market value
- **CAGR**: Portfolio-level equity curve compounding 
- **IRR > CAGR is normal and expected** due to position sizing (5% per trade) and cash allocation

**Example Results:**
```csv
Symbol,IRR %,Equity CAGR %,Explanation
RELIANCE,25.61,0.6,Strategy generates 25.6% on deployed capital, 0.6% portfolio impact
TOTAL,20.08,1.5,Portfolio IRR 20% vs equity growth 1.5%
```

**Why IRR > CAGR:**
1. **Position sizing**: Only 5% capital deployed per trade limits portfolio CAGR
2. **Open trades**: IRR includes unrealized gains from current positions  
3. **Strategy efficiency**: IRR shows alpha when capital is actively deployed

#### Portfolio Metrics Interpretation
- **Net P&L %**: Now shows realistic portfolio returns (e.g., 409% over 5+ years, not 260,318%)
- **Max equity drawdown %**: Maximum percentage decline from portfolio peak
- **Avg exposure %**: Average market exposure (>100% indicates leverage usage)
- **Total trades**: Aggregate count across all symbols
- **IRR %**: Trade-based Internal Rate of Return including open trades at mark-to-market (often > CAGR due to 5% position sizing)

## Time Windows and Bar Calculations

### Window Overview
The system analyzes backtests across 4 time windows:

| Window | Calculation | Time Range | Use Case |
|--------|-------------|-----------|----------|
| **1Y** | Based on bars_per_year | ~1 trading year | Recent performance |
| **3Y** | 3× bars_per_year | ~3 trading years | Medium-term trends |
| **5Y** | 5× bars_per_year | ~5 trading years | Long-term trends |
| **MAX** | All available bars | Full history | Complete performance |

### Bars Per Year Configuration

The system supports different timeframes, each with a specific bar density:

```python
BARS_PER_YEAR_MAP: dict[str, int] = {
    "1d": 245,      # Daily: ~245 trading days per year
    "125m": 735,    # 125-minute: 3x daily bar count
    "75m": 1225,    # 75-minute: 5x daily bar count
}
```

### Window Calculation Examples

#### For 1d Timeframe (245 bars/year)
- **1Y window**: 1 × 245 = **245 bars** (~1 trading year)
- **3Y window**: 3 × 245 = **735 bars** (~3 trading years)
- **5Y window**: 5 × 245 = **1,225 bars** (~5 trading years)
- **MAX window**: All available bars (no limit)

#### For 125m Timeframe (735 bars/year)
- **1Y window**: 1 × 735 = **735 bars** (~1 trading year)
- **3Y window**: 3 × 735 = **2,205 bars** (~3 trading years)
- **5Y window**: 5 × 735 = **3,675 bars** (~5 trading years)
- **MAX window**: All available bars (no limit)

#### For 75m Timeframe (1,225 bars/year)
- **1Y window**: 1 × 1,225 = **1,225 bars** (~1 trading year)
- **3Y window**: 3 × 1,225 = **3,675 bars** (~3 trading years)
- **5Y window**: 5 × 1,225 = **6,125 bars** (~5 trading years)
- **MAX window**: All available bars (no limit)

### How MAX Window Works

The **MAX window uses 100% of available historical data** without any filtering:

```python
# For 1Y/3Y/5Y: Filter to specific time range
window_start = df_full.index[-(y * bars_per_year) :].min()
window_trades = trades[trades['entry_time'] >= window_start]

# For MAX: No filtering - use complete data
window_trades = results["trades"]       # All trades from beginning
window_equity = results["equity"]       # Full equity curve
window_data = results["data"]           # All OHLC data
```

### Implementation Details

**Configuration Location**: `runners/run_basket.py` lines 35-39
- Contains `BARS_PER_YEAR_MAP` for each timeframe
- Extracted dynamically based on `--interval` parameter
- Passed to `optimize_window_processing()` in `core/monitoring.py`

**Window Processing Logic**: `core/monitoring.py` lines 139-211
- Loops through windows: `[1, 3, 5, None]` (None = MAX)
- For 1Y/3Y/5Y: Calculates start date using `bars_per_year`
- For MAX: Uses all data without date filtering

## Success Verification
A successful run should show:
- **Debug output** for each symbol during processing
- **Trade counts** for each symbol and time window
- **Final report generation** with all output files
- **Realistic portfolio total** in key metrics (not astronomical percentages)

Example successful output:
```
DEBUG RELIANCE: filtered trades count: 12 (from 12 total)
DEBUG HDFCBANK: filtered trades count: 10 (from 10 total)
...
Saved consolidated reports:
- ALL: portfolio_key_metrics_ALL.csv (Net P&L %: 409.44%, not 260,318%)
```

## Backtest Methodology & Validation

### Execution Model
The system uses an **event-driven data loop** with `execute_on_next_open = True`:
- **Signal Generated**: Analyzed at Bar N close
- **Execution**: Bar N+1 open price  
- **Why**: Prevents lookahead bias, matches market reality, industry standard

### NaN Validation for Indicators
**Status**: ✅ Implemented (strategies/ichimoku.py)

The ichimoku strategy includes NaN validation for robust backtesting:
- Rejects trades when indicators lack sufficient history
- Prevents invalid trades with insufficient data
- Lookback requirements:
  - Ichimoku leading span B: 52 bars minimum
  - Aroon: 25 bars
  - ATR: 14 bars
  - RSI: 14 bars

**Data Flow**:
1. Load full historical data (10+ years where available)
2. Strategy calculates indicators on full history
3. Backtest runs on complete data
4. NaN validation prevents trades during warmup period
5. Window analysis performed on valid trades only

### Important Investigation Findings (Nov 2025)

**Report Differences**: Two reports (1104-0404 vs 1107-2337) had different trade counts due to strategy code improvements:
- 1104: 40 trades (included invalid trades with NaN indicators)
- 1107: 39 trades (NaN validation prevented invalid trades)
- **Status**: ✅ This is correct behavior - not a bug

**Verified Correct**: 
- ✅ Both reports use same 1d timeframe
- ✅ Data differences are negligible
- ✅ NaN validation with 10Y data prevents issues
- ✅ Results with 10Y history: no NaN values in 5Y window

**For Details**: See `docs/BACKTEST_INVESTIGATION_AND_NAN_ANALYSIS.md` for complete analysis.

## System Cleanup Completed
✅ **Duplicate files removed**: `dhan_symbol_mapping_comprehensive.csv`, `clean_symbol_mapping.csv`
✅ **Portfolio calculation fixed**: Unrealistic returns issue resolved
✅ **Single mapping file**: Uses `api-scrip-master-detailed.csv` as single source of truth
✅ **Cache-only approach**: All data loaded from `data/cache/` directory
✅ **NaN validation**: Prevents invalid trades with insufficient indicator history
✅ **Investigation documented**: All findings consolidated in docs/