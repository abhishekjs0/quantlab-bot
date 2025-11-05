# Multi-Timeframe Quick Reference

## 📚 Load Minute Data

```python
from data.loaders import load_minute_data

# By SECURITY_ID (fastest)
df = load_minute_data(1023)  # SBIN

# By symbol
df = load_minute_data("SBIN")
df = load_minute_data("NSE:SBIN")
```

## 📊 Aggregate to Timeframes

```python
from core.multi_timeframe import aggregate_to_timeframe

df_75m = aggregate_to_timeframe(minute_df, "75m")    # 75-minute
df_125m = aggregate_to_timeframe(minute_df, "125m")  # 125-minute
df_1h = aggregate_to_timeframe(minute_df, "1h")      # 1-hour
df_1d = aggregate_to_timeframe(minute_df, "1d")      # Daily
df_4h = aggregate_to_timeframe(minute_df, "4h")      # Custom: 4-hour
```

## ⚡ Run Strategy

```python
from core.engine import BacktestEngine
from strategies.ema_crossover import EMAcrossoverStrategy
from core.config import BrokerConfig

# Create strategy and engine
strategy = EMAcrossoverStrategy()
engine = BacktestEngine(df_75m, strategy, BrokerConfig())

# Run backtest
trades_df, equity_df, signals_df = engine.run()

# Results
print(f"Trades: {len(trades_df)}")
print(f"Final equity: {equity_df.iloc[-1]}")
```

## 📈 Compare Timeframes

```python
import pandas as pd

results = []
for tf in ["75m", "125m", "1d"]:
    df = aggregate_to_timeframe(minute_df, tf)
    strategy = EMAcrossoverStrategy()
    engine = BacktestEngine(df, strategy, BrokerConfig())
    trades_df, equity_df, _ = engine.run()
    
    results.append({
        "Timeframe": tf,
        "Trades": len(trades_df),
        "Return %": 100 * (equity_df.iloc[-1] / equity_df.iloc[0] - 1),
    })

print(pd.DataFrame(results))
```

## 🔍 Validate Data

```python
# Check structure
print(len(df))  # Number of bars
print(df.index[0], df.index[-1])  # Date range
print(df.columns)  # Columns

# Validate OHLCV
assert (df["high"] >= df["low"]).all()
assert not df[["open", "high", "low", "close", "volume"]].isnull().any().any()
```

## 🧪 Run Tests

```bash
# Multi-timeframe tests
python3 -m pytest tests/test_multi_timeframe.py -v

# Minute loader tests
python3 -m pytest tests/test_minute_loader.py -v

# All
python3 -m pytest tests/test_multi_timeframe.py tests/test_minute_loader.py -v
```

## 📁 File Locations

| Component | File |
|-----------|------|
| Minute loader | `data/loaders.py` |
| Aggregation | `core/multi_timeframe.py` |
| Tests (multi-tf) | `tests/test_multi_timeframe.py` |
| Tests (minute) | `tests/test_minute_loader.py` |
| Guide | `docs/MULTI_TIMEFRAME_GUIDE.md` |
| Example | `examples/multi_timeframe_example.py` |

## 🎯 Common SECURITY_IDs

| Symbol | SECURITY_ID |
|--------|-------------|
| SBIN | 1023 |
| HDFC | 1038 |
| LT | 10397 |
| INFY | 10348 |
| TCS | 10649 |

See `api-scrip-master-detailed.csv` for full list.

## ⚠️ Troubleshooting

**FileNotFoundError: Minute data not found**
- Run: `python3 scripts/fetch_data.py SBIN`
- Check: `ls -la data/cache/dhan_historical_*.csv`

**ValueError: Cannot resolve symbol**
- Use SECURITY_ID directly: `load_minute_data(1023)`
- Check symbol spelling in instrument master

**No bars after aggregation**
- Use smaller timeframe: `"75m"` instead of `"1d"`
- Check minute data exists: `print(len(minute_df))`

## 📞 Key Functions

### load_minute_data()
```
Load minute OHLCV from Dhan CSV
- Input: symbol_or_secid (str | int)
- Output: DataFrame with DatetimeIndex
- Raises: FileNotFoundError, ValueError
```

### aggregate_to_timeframe()
```
Aggregate minute data to target timeframe
- Input: df (DataFrame), target_interval (str)
- Output: DataFrame with aggregated OHLCV
- Raises: ValueError (invalid interval)
```

### _symbol_to_security_id()
```
Resolve symbol to SECURITY_ID
- Input: symbol (str)
- Output: int (SECURITY_ID) or None
- Uses: instrument master (parquet/CSV)
```

## 🚀 Getting Started

1. **Load minute data**: `df = load_minute_data("SBIN")`
2. **Aggregate**: `df_75m = aggregate_to_timeframe(df, "75m")`
3. **Run strategy**: Use with `BacktestEngine`
4. **Analyze**: Compare results across timeframes
5. **Iterate**: Fine-tune for each timeframe

See `docs/MULTI_TIMEFRAME_GUIDE.md` for detailed documentation.

---

Last Updated: 2024
Status: ✅ Production Ready
Tests: 14/14 Passing
