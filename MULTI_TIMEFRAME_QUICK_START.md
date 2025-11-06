# Multi-Timeframe Backtesting - Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Fetch Real Minute Data
```python
from scripts.dhan_data_fetcher import fetch_intraday_minute_data, save_minute_data_to_csv

# Fetch 1-minute SBIN data (last trading day)
data = fetch_intraday_minute_data("1023", interval=1, days_back=1)

# Save to CSV
save_minute_data_to_csv(data, "1023_sbin", 1)
# Saved to: data/cache/dhan_minute_1023_sbin_1m.csv
```

### Step 2: Load Data
```python
import pandas as pd
from core.multi_timeframe import aggregate_to_timeframe

# Load real 1-minute data
df_1m = pd.read_csv("data/cache/dhan_minute_1023_sbin_1m.csv")

# Convert to DatetimeIndex (required for aggregation)
df_1m["date"] = pd.to_datetime(df_1m["date"])
df_1m = df_1m.set_index("date")

print(f"Loaded {len(df_1m)} minute candles")
# Output: Loaded 216 minute candles
```

### Step 3: Aggregate to Your Timeframe
```python
# Aggregate to 75-minute candles
df_75m = aggregate_to_timeframe(df_1m, "75m")

# Or any other timeframe
df_125m = aggregate_to_timeframe(df_1m, "125m")
df_1h = aggregate_to_timeframe(df_1m, "1h")
df_1d = aggregate_to_timeframe(df_1m, "1d")

print(f"75m bars: {len(df_75m)}")
print(f"125m bars: {len(df_125m)}")
print(f"1h bars: {len(df_1h)}")
print(f"Daily bars: {len(df_1d)}")
```

### Step 4: Backtest Your Strategy
```python
from core.engine import BacktestEngine
from strategies.your_strategy import YourStrategy

# Create strategy
strategy = YourStrategy()

# Create config
config = {
    "cash": 100000,
    "symbols": ["SBIN"],
    "start_date": "2025-11-06",
}

# Run backtest on 75-minute timeframe
engine = BacktestEngine(df_75m, strategy, config)
trades_df, equity_df, signals_df = engine.run()

# Analyze results
print(f"Total trades: {len(trades_df)}")
print(f"Win rate: {(trades_df['profit'] > 0).sum() / len(trades_df) * 100:.1f}%")
```

---

## 📊 Supported Timeframes

| Interval | Example | Use Case |
|----------|---------|----------|
| `"1m"` | 1-minute | Scalping, HFT |
| `"5m"` | 5-minute | Intraday swing |
| `"15m"` | 15-minute | Intraday swing |
| `"75m"` | 75-minute | Intraday swing (custom) |
| `"125m"` | 125-minute | Intraday swing (custom) |
| `"1h"` | 1-hour | Day trading |
| `"4h"` | 4-hour | Multi-day swing |
| `"1d"` | Daily | Swing/position trading |

---

## 🔄 Available Symbols

### Equity NSE Symbols (examples)

| Symbol | Security ID | Exchange |
|--------|------------|----------|
| RELIANCE | 100 | NSE_EQ |
| SBIN | 1023 | NSE_EQ |
| INFY | 10188 | NSE_EQ |
| BHARTIARTL | 1038 | NSE_EQ |
| HDFC BANK | 1333 | NSE_EQ |

To fetch data for any symbol:
```python
# Fetch INFY 5-minute data
data = fetch_intraday_minute_data("10188", interval=5, days_back=1)
save_minute_data_to_csv(data, "10188_infy", 5)
```

---

## 💾 Cached Data

Pre-cached real data ready to use:

```bash
data/cache/
├── dhan_minute_100_reliance_1m.csv    # RELIANCE - 216 1-min bars
├── dhan_minute_1023_sbin_5m.csv       # SBIN - 44 5-min bars
└── dhan_minute_10188_infy_dailym.csv  # INFY - 20 daily bars
```

Load directly:
```python
df = pd.read_csv("data/cache/dhan_minute_100_reliance_1m.csv")
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")
```

---

## 🧪 Test Your Strategy on Different Timeframes

```python
# Test same strategy on multiple timeframes
def test_strategy_multiframe():
    strategy = MyEMACrossover()
    config = {"cash": 100000}
    
    for timeframe in ["75m", "125m", "1h", "1d"]:
        # Aggregate
        df = aggregate_to_timeframe(df_1m, timeframe)
        
        # Backtest
        engine = BacktestEngine(df, strategy, config)
        trades, equity, signals = engine.run()
        
        # Compare
        win_rate = (trades["profit"] > 0).sum() / len(trades) * 100
        roi = (equity["equity"].iloc[-1] - config["cash"]) / config["cash"] * 100
        
        print(f"{timeframe:8} | Win Rate: {win_rate:5.1f}% | ROI: {roi:6.1f}%")
```

---

## 🔧 Common Use Cases

### Use Case 1: Scalping (1-minute)
```python
# Fetch 1-minute data
data = fetch_intraday_minute_data("100", interval=1, days_back=1)
df_1m = prepare_data(data)

# Run directly on 1-minute bars
engine = BacktestEngine(df_1m, ScalpingStrategy(), config)
```

### Use Case 2: Day Trading (75-minute)
```python
# Aggregate to 75-minute
df_75m = aggregate_to_timeframe(df_1m, "75m")
# Gives ~4 bars during trading hours (09:15-15:30 IST)

engine = BacktestEngine(df_75m, DayTradingStrategy(), config)
```

### Use Case 3: Swing Trading (1-hour to daily)
```python
# Aggregate to 1-hour
df_1h = aggregate_to_timeframe(df_1m, "1h")

# Or 1-day for multi-day swings
df_1d = aggregate_to_timeframe(df_1m, "1d")

engine = BacktestEngine(df_1h, SwingStrategy(), config)
```

---

## 🚨 Important Notes

### Data Preparation
Always convert date column to datetime and set as index:
```python
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")
```

### Time Zones
- Dhan API returns data in UTC
- Data is converted to IST (India Standard Time)
- Market hours: 09:15 - 15:30 IST

### Data Availability
- Intraday data: Last 5 trading days only
- Daily data: Available for ~5 years
- Weekends & holidays: No data

### Performance Tips
- Cache yesterday's data for quick testing
- Test on aggregated intervals first (faster)
- Then backtest on minute data for validation

---

## 📈 Example: Complete Strategy Backtest

```python
import pandas as pd
from core.multi_timeframe import aggregate_to_timeframe
from core.engine import BacktestEngine
from strategies.ema_crossover import EMA_Crossover
from scripts.dhan_data_fetcher import fetch_intraday_minute_data

# 1. Fetch fresh data
print("Fetching data...")
data = fetch_intraday_minute_data("1023", interval=1, days_back=1)

# 2. Prepare dataframe
df_1m = pd.DataFrame(data)
df_1m["date"] = pd.to_datetime(df_1m["timestamp"], unit="s", utc=True)
df_1m = df_1m[["date", "open", "high", "low", "close", "volume"]].set_index("date")

# 3. Aggregate to 75 minutes
df_75m = aggregate_to_timeframe(df_1m, "75m")
print(f"Loaded {len(df_75m)} 75-minute bars")

# 4. Create strategy
strategy = EMA_Crossover(ema_short=5, ema_long=10)

# 5. Create config
config = {
    "cash": 100000,
    "symbols": ["SBIN"],
    "start_date": "2025-11-06",
    "trades_per_day": 3,
}

# 6. Run backtest
engine = BacktestEngine(df_75m, strategy, config)
trades, equity, signals = engine.run()

# 7. Analyze
print(f"\nResults on 75-minute timeframe:")
print(f"Total Trades: {len(trades)}")
print(f"Winning Trades: {(trades['profit'] > 0).sum()}")
print(f"Win Rate: {(trades['profit'] > 0).sum() / len(trades) * 100:.1f}%")
print(f"Avg Win: ₹{trades[trades['profit'] > 0]['profit'].mean():.2f}")
print(f"Avg Loss: ₹{trades[trades['profit'] < 0]['profit'].mean():.2f}")
print(f"Max Equity: ₹{equity['equity'].max():.2f}")
print(f"Final Return: {(equity['equity'].iloc[-1] - config['cash']) / config['cash'] * 100:.1f}%")
```

---

## ✅ Validation Checklist

Before running production backtest:
- ✅ Data loads without errors
- ✅ Date column is DatetimeIndex
- ✅ OHLCV columns present
- ✅ No NaN values
- ✅ Time gaps are reasonable (1 min for 1m data, 75 min for 75m data)
- ✅ Volume > 0 for all bars
- ✅ Strategy initializes correctly
- ✅ Backtest runs without errors

---

## 📞 Troubleshooting

### Error: "Only valid with DatetimeIndex"
**Solution:** Set date as index
```python
df["date"] = pd.to_datetime(df["date"])
df = df.set_index("date")
```

### Error: "column 'date' not found"
**Solution:** Check CSV column names
```python
df = pd.read_csv("file.csv")
print(df.columns)  # Check columns
```

### No data returned from API
**Solution:** Check dates and security ID
```python
# Make sure dates are valid trading days
from datetime import datetime
print(f"Today: {datetime.now().date()}")

# Verify security ID (use 100 for RELIANCE)
data = fetch_intraday_minute_data("100", interval=1, days_back=1)
```

---

## 🎓 Learn More

See the following docs for details:
- `MULTI_TIMEFRAME_IMPLEMENTATION.md` - Technical details
- `core/multi_timeframe.py` - Aggregation logic
- `scripts/dhan_data_fetcher.py` - API integration
- `core/engine.py` - Backtesting engine

---

**Ready to backtest? Start with the quick start guide above! 🚀**
