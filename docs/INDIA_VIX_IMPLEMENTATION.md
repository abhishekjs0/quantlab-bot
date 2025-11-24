# India VIX Data Fetching - Implementation Summary

## What Was Created

### 1. Main Script: `scripts/fetch_india_vix.py`
A comprehensive script to fetch India VIX (Volatility Index) historical data from Dhan API.

**Features:**
- ✅ Fetches India VIX data from Dhan API (SECURITY_ID: 21)
- ✅ Supports multiple timeframes: 1m, 5m, 15m, 60m, 1d
- ✅ Configurable date ranges (default: last 5 years)
- ✅ Save to cache, data, or both directories
- ✅ Command-line interface with argparse
- ✅ Reads credentials from environment or parameters
- ✅ Data validation and error handling

**Usage:**
```bash
# Fetch daily India VIX (default: last 5 years)
python3 scripts/fetch_india_vix.py

# Custom date range
python3 scripts/fetch_india_vix.py --from-date 2020-01-01 --to-date 2024-12-31

# Fetch 1-minute data
python3 scripts/fetch_india_vix.py --interval 1

# Save to both directories
python3 scripts/fetch_india_vix.py --save-to both
```

### 2. Data Loader Function: `data/loaders.py`
Added `load_india_vix()` function to existing loaders module.

**Function Signature:**
```python
def load_india_vix(interval: str = "1d", cache_dir: Optional[str] = None) -> pd.DataFrame
```

**Features:**
- ✅ Loads India VIX data from cache or data directory
- ✅ Supports multiple timeframes
- ✅ Automatic fallback between cache and data directories
- ✅ Returns standardized DataFrame with datetime index
- ✅ Proper error messages if data not found

**Usage:**
```python
from data.loaders import load_india_vix

# Load daily India VIX
vix_df = load_india_vix(interval="1d")
print(vix_df.tail())
```

### 3. Test Script: `scripts/test_india_vix.py`
Simple test script to demonstrate loading and displaying India VIX data.

**Usage:**
```bash
python3 scripts/test_india_vix.py
```

### 4. Documentation: `docs/INDIA_VIX_GUIDE.md`
Comprehensive guide covering:
- ✅ Quick start instructions
- ✅ Configuration and credentials
- ✅ Supported timeframes
- ✅ File locations and naming conventions
- ✅ 4 detailed usage examples
- ✅ API reference
- ✅ Data format specification
- ✅ Troubleshooting guide
- ✅ Market regime interpretation notes

## File Locations

### Data Files
India VIX data will be saved to:
- **Cache:** `cache/dhan_21_INDIAVIX_{interval}.csv`
- **Data:** `data/dhan_historical_21.csv`

Examples:
- Daily: `cache/dhan_21_INDIAVIX_1d.csv`
- 1-minute: `cache/dhan_21_INDIAVIX_1.csv`

### Code Files Created/Modified
1. **Created:** `scripts/fetch_india_vix.py` (235 lines)
2. **Created:** `scripts/test_india_vix.py` (44 lines)
3. **Created:** `docs/INDIA_VIX_GUIDE.md` (360 lines)
4. **Modified:** `data/loaders.py` (added `load_india_vix()` function)

## Key Features

### India VIX Details
- **SECURITY_ID:** 21
- **Exchange:** NSE
- **Segment:** INDEX
- **Symbol:** INDIA VIX

### Supported Timeframes
| Interval | Description |
|----------|-------------|
| `1` | 1-minute candles |
| `5` | 5-minute candles |
| `15` | 15-minute candles |
| `60` | 1-hour candles |
| `1d` | Daily candles |

### Data Format
Standard OHLCV format:
- `date` (index): datetime
- `open`, `high`, `low`, `close`: float
- `volume`: int

## How to Use

### Step 1: Set Credentials
```bash
export DHAN_CLIENT_ID='your_client_id'
export DHAN_ACCESS_TOKEN='your_access_token'
```

### Step 2: Fetch Data
```bash
python3 scripts/fetch_india_vix.py
```

### Step 3: Use in Code
```python
from data.loaders import load_india_vix

# Load India VIX
vix = load_india_vix()

# Current VIX level
print(f"Current VIX: {vix['close'].iloc[-1]:.2f}")

# Market regime
current_vix = vix['close'].iloc[-1]
if current_vix < 15:
    regime = "Low Volatility"
elif current_vix < 20:
    regime = "Normal"
elif current_vix < 30:
    regime = "Elevated"
else:
    regime = "High Fear"
print(f"Regime: {regime}")
```

## Integration Points

The India VIX data can be integrated with existing QuantLab features:

### 1. Market Regime Detection
Use VIX to adjust strategy parameters:
```python
vix = load_india_vix()
current_vix = vix['close'].iloc[-1]

if current_vix > 25:
    # High volatility: use wider stops, reduce position sizes
    atr_multiplier = 3.0
elif current_vix < 15:
    # Low volatility: tighter stops, larger positions
    atr_multiplier = 1.5
```

### 2. Portfolio Risk Management
Filter trades based on VIX levels:
```python
vix = load_india_vix()
vix_current = vix['close'].iloc[-1]

# Only take new trades when VIX is below threshold
if vix_current < 30:
    execute_trade(...)
```

### 3. Strategy Performance Analysis
Analyze how strategies perform in different VIX regimes:
```python
trades['vix_at_entry'] = trades.apply(
    lambda row: vix.loc[row['entry_date'], 'close'],
    axis=1
)

# Group by VIX regime
high_vix_trades = trades[trades['vix_at_entry'] > 25]
low_vix_trades = trades[trades['vix_at_entry'] < 15]
```

## VIX Interpretation

### VIX Levels and Market Sentiment
- **< 15:** Low volatility, market complacency
- **15-20:** Normal volatility range
- **20-30:** Elevated volatility, caution advised
- **> 30:** High volatility, market fear/stress

### Typical Behavior
- VIX typically moves **inversely** to stock markets
- Spikes during market selloffs and uncertainty
- Declines during calm, bullish periods
- Can be used as a contrarian indicator

## Next Steps

To actually fetch India VIX data:

1. **Set up Dhan credentials:**
   ```bash
   export DHAN_CLIENT_ID='your_client_id'
   export DHAN_ACCESS_TOKEN='your_access_token'
   ```

2. **Fetch data:**
   ```bash
   python3 scripts/fetch_india_vix.py
   ```

3. **Test loading:**
   ```bash
   python3 scripts/test_india_vix.py
   ```

4. **Use in strategies:**
   ```python
   from data.loaders import load_india_vix
   vix = load_india_vix()
   ```

## Technical Notes

- Uses Dhan `historical_data()` API
- Handles timezone conversion automatically
- Compatible with existing QuantLab data loaders
- Follows same naming convention as other Dhan data files
- Normalized column names (lowercase)
- Sorted datetime index

## References

- Dhan API: https://dhanhq.co/docs/
- NSE India VIX: https://www.nseindia.com/products-services/indices-india-vix
- VIX Methodology: https://www.cboe.com/micro/vix/vixwhite.pdf
