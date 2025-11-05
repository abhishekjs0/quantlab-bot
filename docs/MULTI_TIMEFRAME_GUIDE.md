# Multi-Timeframe Backtesting Guide

## Overview

QuantLab supports running strategies on multiple timeframes using data aggregation from Dhan API minute candles:

- **75-minute candles**: For swing trading (6+ hour to multi-day holding)
- **125-minute candles**: Custom timeframe testing
- **Daily candles**: EOD trading (default)
- **Custom intervals**: Any timeframe you need (1h, 2h, 4h, etc.)

All using a **single strategy** toggled by timeframe parameter.

## Architecture

```
┌─────────────────────────────────────────┐
│  Dhan API                               │
│  Minute-wise historical candles (1m)   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  load_minute_data()                     │
│  - Load from dhan_historical_*.csv      │
│  - Resolve symbol → SECURITY_ID         │
│  - Normalize OHLCV                      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  aggregate_to_timeframe()               │
│  - Resample to 75m, 125m, 1d, etc.    │
│  - Preserve OHLCV integrity             │
│  - Remove overnight gaps (NaN)          │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Strategy (same for all timeframes)     │
│  - on_bar() processes bars              │
│  - on_entry()/on_exit() executes trades │
│  - Logic unchanged, only input varies   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  BacktestEngine                         │
│  - Single-bar processing                │
│  - Entry/exit execution                 │
│  - P&L calculation                      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Results                                │
│  - trades_df: Individual trades         │
│  - equity_df: Daily/per-bar equity      │
│  - signals_df: Entry/exit signals       │
└─────────────────────────────────────────┘
```

## Usage

### Basic Example

```python
from core.multi_timeframe import aggregate_to_timeframe
from data.loaders import load_minute_data
from core.engine import BacktestEngine
from strategies.ema_crossover import EMAcrossoverStrategy
from core.config import BrokerConfig

# Load minute-wise data for SBIN (SECURITY_ID: 1023)
minute_df = load_minute_data(1023)

# Aggregate to 75-minute candles
df_75m = aggregate_to_timeframe(minute_df, "75m")

# Run strategy on 75-minute timeframe
strategy = EMAcrossoverStrategy()
engine = BacktestEngine(df_75m, strategy, BrokerConfig())
trades_df, equity_df, signals_df = engine.run()

print(f"Trades on 75-min: {len(trades_df)}")
print(f"Final equity: {equity_df.iloc[-1]}")
```

### Load Data for Multiple Symbols

```python
from data.loaders import load_minute_data
from core.multi_timeframe import aggregate_to_timeframe

# List of SECURITY_IDs
security_ids = [1023, 1038, 10397]  # SBIN, HDFC, LT

for secid in security_ids:
    try:
        # Load minute data
        minute_df = load_minute_data(secid)
        
        # Aggregate to 75-minute
        df_75m = aggregate_to_timeframe(minute_df, "75m")
        
        print(f"SECURITY_ID {secid}: {len(df_75m)} 75-min bars")
    except FileNotFoundError:
        print(f"SECURITY_ID {secid}: Data not found")
```

### Load by Symbol

```python
from data.loaders import load_minute_data

# Load by symbol string (converts to SECURITY_ID)
minute_df = load_minute_data("SBIN")  # Uses instrument master
df = aggregate_to_timeframe(minute_df, "75m")
```

### Compare Strategies Across Timeframes

```python
import pandas as pd
from core.multi_timeframe import aggregate_to_timeframe
from data.loaders import load_minute_data

minute_df = load_minute_data(1023)

# Test on multiple timeframes
timeframes = ["75m", "125m", "1d"]
results = []

for tf in timeframes:
    df = aggregate_to_timeframe(minute_df, tf)
    
    strategy = EMAcrossoverStrategy()
    engine = BacktestEngine(df, strategy, BrokerConfig())
    trades_df, equity_df, signals_df = engine.run()
    
    results.append({
        "Timeframe": tf,
        "Trades": len(trades_df),
        "Return %": 100 * (equity_df.iloc[-1] / equity_df.iloc[0] - 1),
        "Max DD %": 100 * (equity_df.min() / equity_df.cummax().max() - 1),
    })

results_df = pd.DataFrame(results)
print(results_df)
```

## Data Loading

### load_minute_data()

Load minute-wise candles from Dhan historical CSV files.

**Signature:**
```python
def load_minute_data(
    symbol_or_secid: str | int,
    cache_dir: str | None = None
) -> pd.DataFrame
```

**Parameters:**
- `symbol_or_secid`: Either a symbol string (e.g., "SBIN") or Dhan SECURITY_ID (e.g., 1023)
- `cache_dir`: Optional directory for CSV files (defaults to CACHE_DIR from config)

**Returns:**
- DataFrame with DatetimeIndex and columns: open, high, low, close, volume

**Examples:**
```python
# Load by SECURITY_ID
df = load_minute_data(1023)

# Load by symbol (with NSE: prefix)
df = load_minute_data("NSE:SBIN")

# Load by symbol (without prefix)
df = load_minute_data("SBIN")
```

**Errors:**
- `FileNotFoundError`: If CSV not found in cache
- `ValueError`: If symbol cannot be resolved to SECURITY_ID

### Resolution Process

When given a symbol string, `load_minute_data()` resolves it to SECURITY_ID using the instrument master:

1. Check `api-scrip-master-detailed.parquet` (fast)
2. Check `api-scrip-master-detailed.csv` (fallback)
3. Return SECURITY_ID if found, error if not

Symbol normalization:
- "NSE:SBIN" → "SBIN"
- "SBIN.NS" → "SBIN"
- Matches against SYMBOL_NAME and UNDERLYING_SYMBOL columns

## Aggregation

### aggregate_to_timeframe()

Aggregate minute candles to a target timeframe using OHLC resampling.

**Signature:**
```python
def aggregate_to_timeframe(
    df: pd.DataFrame,
    target_interval: str
) -> pd.DataFrame
```

**Parameters:**
- `df`: DataFrame with minute OHLCV (DatetimeIndex, columns: open, high, low, close, volume)
- `target_interval`: Target interval as string (e.g., "75m", "125m", "1h", "1d")

**Returns:**
- Aggregated DataFrame with target timeframe candles

**OHLCV Aggregation Rules:**
- **Open**: First candle's open
- **High**: Maximum high across all candles
- **Low**: Minimum low across all candles
- **Close**: Last candle's close
- **Volume**: Sum of all volumes

**Examples:**
```python
# 75-minute candles
df_75m = aggregate_to_timeframe(minute_df, "75m")

# 125-minute candles
df_125m = aggregate_to_timeframe(minute_df, "125m")

# 1-hour candles
df_1h = aggregate_to_timeframe(minute_df, "1h")

# Daily candles
df_1d = aggregate_to_timeframe(minute_df, "1d")

# Custom 2-hour candles
df_2h = aggregate_to_timeframe(minute_df, "2h")
```

**Features:**
- Removes NaN rows (overnight gaps, market hours boundaries)
- Preserves OHLCV relationships: High ≥ Low, Close between High/Low
- Efficient pandas resampling
- Works with any standard interval format

## Understanding Results

### Trades DataFrame

```python
trades_df.columns:
- time: Entry timestamp
- entry_price: Entry price
- entry_qty: Position size
- exit_time: Exit timestamp  
- exit_price: Exit price
- gross_pnl: Profit/loss before commission
- net_pnl: Profit/loss after commission
- return_pct: Return percentage
```

### Equity DataFrame

```python
equity_df.columns:
- time: Timestamp (bar close)
- equity: Total portfolio value
- cash: Available cash
- qty: Current position size
- price: Current bar close
```

### Signals DataFrame

```python
signals_df.columns:
- time: Signal timestamp
- type: "entry" or "exit"
- signal_reason: Human-readable reason
- price: Entry/exit price
```

## Timeframe Selection

### When to Use Each Timeframe

**75-minute candles:**
- Intermediate-term swing trading
- 6+ hour to multi-day holding periods
- Capture intraday trends with less noise
- Good for part-time traders

**125-minute candles:**
- Custom timeframe for research
- Between 75m and daily
- Fewer bars, longer holding periods

**Daily candles:**
- EOD position trading
- Overnight holding
- Classic swing trading
- Lower trading costs

**Hourly candles:**
- Active day trading
- Same-day positions
- More frequent signals

### Performance Considerations

Timeframe impacts:
- **Signal frequency**: Shorter timeframes = more trades
- **Holding period**: 75m trades hold 6-36 hours, daily trades hold 1-30+ days
- **Commission impact**: More trades = higher total commission
- **Volatility exposure**: Different realized volatility per timeframe

## Advanced Usage

### Backtesting Pipeline

```python
def backtest_multi_timeframe(symbol, timeframes, strategy_class):
    """Run strategy across multiple timeframes."""
    minute_df = load_minute_data(symbol)
    results = {}
    
    for tf in timeframes:
        df = aggregate_to_timeframe(minute_df, tf)
        
        strategy = strategy_class()
        engine = BacktestEngine(df, strategy, BrokerConfig())
        trades_df, equity_df, signals_df = engine.run()
        
        results[tf] = {
            "trades": trades_df,
            "equity": equity_df,
            "signals": signals_df,
        }
    
    return results

# Usage
results = backtest_multi_timeframe("SBIN", ["75m", "1d"], EMAcrossoverStrategy)
```

### Batch Processing

```python
from data.loaders import load_minute_data
from core.multi_timeframe import aggregate_to_timeframe
import pandas as pd

symbols = ["SBIN", "HDFC", "LT", "INFY"]
timeframes = ["75m", "125m", "1d"]

# Create all combinations
for symbol in symbols:
    minute_df = load_minute_data(symbol)
    
    for tf in timeframes:
        df = aggregate_to_timeframe(minute_df, tf)
        
        # Your backtesting logic here
        strategy = EMAcrossoverStrategy()
        engine = BacktestEngine(df, strategy, BrokerConfig())
        trades_df, _, _ = engine.run()
        
        print(f"{symbol} {tf}: {len(trades_df)} trades")
```

## Testing

### Running Tests

```bash
# Test minute data loader
python3 -m pytest tests/test_minute_loader.py -v

# Test multi-timeframe aggregation
python3 -m pytest tests/test_multi_timeframe.py -v

# All tests
python3 -m pytest tests/ -v
```

### Test Coverage

- ✅ Loading minute data from cache
- ✅ Symbol resolution to SECURITY_ID
- ✅ Aggregation to different timeframes
- ✅ OHLCV validation
- ✅ No NaN values in output
- ✅ Data sorted by date

## Troubleshooting

### FileNotFoundError: Minute data not found

**Cause:** Dhan historical CSV not in cache
**Solution:** 
```bash
# Fetch data from Dhan API
python3 scripts/fetch_data.py SBIN

# Check cache directory
ls -la data/cache/dhan_historical_*.csv
```

### ValueError: Cannot resolve symbol to SECURITY_ID

**Cause:** Instrument master not available or symbol doesn't exist
**Solution:**
1. Load instrument master first: `python3 scripts/fetch_data.py`
2. Use SECURITY_ID directly: `load_minute_data(1023)`
3. Check symbol spelling

### No data points after aggregation

**Cause:** Data has gaps or insufficient minute bars
**Solution:**
1. Check raw minute data: `print(len(minute_df))`
2. Verify date range: `print(minute_df.index[0], minute_df.index[-1])`
3. Use smaller timeframe: `aggregate_to_timeframe(df, "75m")` instead of "1d"

## Integration with Existing Code

### Replacing Daily Data

Replace daily data loading with minute-based aggregation:

```python
# OLD: Load daily data
from data.loaders import load_many_india
daily_data = load_many_india(["SBIN", "HDFC"])

# NEW: Load minute data and aggregate
from data.loaders import load_minute_data
from core.multi_timeframe import aggregate_to_timeframe

minute_data = load_minute_data("SBIN")
daily_data = aggregate_to_timeframe(minute_data, "1d")
```

### Backward Compatibility

- Daily aggregation produces identical results to current daily data
- Strategy logic unchanged
- Engine behavior unchanged
- Existing backtests continue to work

## Performance Metrics

### Typical Data Sizes

| Timeframe | Bars (1 month) | Bars (1 year) |
|-----------|---|---|
| 1-minute | ~6,000 | ~240,000 |
| 75-minute | ~80 | ~3,200 |
| 125-minute | ~48 | ~1,920 |
| Daily | ~22 | ~252 |

### Backtesting Speed

- 1-year daily: ~100ms
- 1-year 75m: ~500ms
- 1-year minute: ~10s

Speed scales linearly with number of bars.

## Next Steps

1. **Load minute data**: Use `load_minute_data()` for your symbols
2. **Aggregate timeframes**: Use `aggregate_to_timeframe()` to create 75m/125m data
3. **Test strategies**: Run existing strategies on new timeframes
4. **Compare results**: Analyze performance across timeframes
5. **Optimize parameters**: Fine-tune indicators for each timeframe
