# India VIX Data Fetching Guide

## Overview

India VIX (Volatility Index) measures the expected market volatility over the next 30 days. It's based on NIFTY 50 index options and is often called the "fear gauge" of the Indian stock market.

**India VIX Details:**
- **SECURITY_ID:** 21
- **Exchange:** NSE
- **Segment:** INDEX
- **Symbol:** INDIA VIX

## Quick Start

### 1. Fetch India VIX Data

```bash
# Fetch daily India VIX data (default: last 5 years)
python3 scripts/fetch_india_vix.py

# Fetch with custom date range
python3 scripts/fetch_india_vix.py --from-date 2020-01-01 --to-date 2024-12-31

# Fetch 1-minute data
python3 scripts/fetch_india_vix.py --interval 1

# Fetch 5-minute data
python3 scripts/fetch_india_vix.py --interval 5

# Save to both cache and data directories
python3 scripts/fetch_india_vix.py --save-to both
```

### 2. Load India VIX Data

```python
from data.loaders import load_india_vix

# Load daily India VIX data
vix_df = load_india_vix(interval="1d")

# Display recent data
print(vix_df.tail())
```

### 3. Test Loading

```bash
# Run test script
python3 scripts/test_india_vix.py
```

## Configuration

### Environment Variables

Set your Dhan credentials:

```bash
export DHAN_CLIENT_ID='your_client_id'
export DHAN_ACCESS_TOKEN='your_access_token'
```

Or pass them directly to the fetch function:

```python
from scripts.fetch_india_vix import fetch_india_vix

df = fetch_india_vix(
    client_id="your_client_id",
    access_token="your_access_token",
    interval="1d"
)
```

## Supported Timeframes

| Interval | Description | API Constant |
|----------|-------------|--------------|
| `1` | 1-minute | `dhanhq.MINUTE` |
| `5` | 5-minute | `dhanhq.FIVE` |
| `15` | 15-minute | `dhanhq.FIFTEEN` |
| `60` | 1-hour | `dhanhq.HOUR` |
| `1d` or `daily` | Daily | `dhanhq.DAY` |

## File Locations

India VIX data is saved to:

- **Cache:** `cache/dhan_21_INDIAVIX_{interval}.csv`
- **Data:** `data/dhan_historical_21.csv`

Example filenames:
- Daily: `cache/dhan_21_INDIAVIX_1d.csv`
- 1-minute: `cache/dhan_21_INDIAVIX_1.csv`
- 5-minute: `cache/dhan_21_INDIAVIX_5.csv`

## Usage Examples

### Example 1: Load and Plot India VIX

```python
import matplotlib.pyplot as plt
from data.loaders import load_india_vix

# Load data
vix = load_india_vix()

# Plot
plt.figure(figsize=(12, 6))
plt.plot(vix.index, vix['close'], label='India VIX')
plt.title('India VIX - Volatility Index')
plt.xlabel('Date')
plt.ylabel('VIX Level')
plt.legend()
plt.grid(True)
plt.show()
```

### Example 2: Calculate VIX Statistics

```python
from data.loaders import load_india_vix

vix = load_india_vix()

print(f"Current VIX: {vix['close'].iloc[-1]:.2f}")
print(f"30-day Average: {vix['close'].tail(30).mean():.2f}")
print(f"52-week High: {vix['close'].tail(252).max():.2f}")
print(f"52-week Low: {vix['close'].tail(252).min():.2f}")
```

### Example 3: Use VIX for Market Regime Detection

```python
from data.loaders import load_india_vix

vix = load_india_vix()

# Define VIX regimes
def get_vix_regime(vix_level):
    if vix_level < 15:
        return "Low Volatility (Complacent)"
    elif vix_level < 20:
        return "Normal Volatility"
    elif vix_level < 30:
        return "Elevated Volatility (Cautious)"
    else:
        return "High Volatility (Fear)"

current_vix = vix['close'].iloc[-1]
regime = get_vix_regime(current_vix)

print(f"Current VIX: {current_vix:.2f}")
print(f"Market Regime: {regime}")
```

### Example 4: Correlate VIX with Strategy Performance

```python
import pandas as pd
from data.loaders import load_india_vix, load_ohlc_yf

# Load India VIX
vix = load_india_vix()

# Load stock data (example: RELIANCE)
stock = load_ohlc_yf("RELIANCE")

# Merge data
combined = pd.merge(
    stock['close'].rename('stock_close'),
    vix['close'].rename('vix'),
    left_index=True,
    right_index=True,
    how='inner'
)

# Calculate correlation
correlation = combined['stock_close'].pct_change().corr(
    combined['vix'].pct_change()
)

print(f"Stock-VIX Correlation: {correlation:.4f}")
```

## API Reference

### `fetch_india_vix()`

Fetch India VIX historical data from Dhan API.

**Parameters:**
- `client_id` (str, optional): Dhan client ID. Defaults to `DHAN_CLIENT_ID` env var.
- `access_token` (str, optional): Dhan access token. Defaults to `DHAN_ACCESS_TOKEN` env var.
- `from_date` (str, optional): Start date (YYYY-MM-DD). Default: 5 years ago.
- `to_date` (str, optional): End date (YYYY-MM-DD). Default: today.
- `interval` (str): Timeframe ("1", "5", "15", "60", "1d"). Default: "1d".
- `save_to` (str): Where to save ("cache", "data", "both"). Default: "cache".

**Returns:**
- `pd.DataFrame`: DataFrame with India VIX OHLC data

### `load_india_vix()`

Load India VIX data from cache.

**Parameters:**
- `interval` (str): Timeframe ("1d", "1", "5", etc.). Default: "1d".
- `cache_dir` (str, optional): Directory to search. Defaults to `CACHE_DIR`.

**Returns:**
- `pd.DataFrame`: DataFrame with India VIX OHLC data

**Raises:**
- `FileNotFoundError`: If cache file not found

## Data Format

India VIX CSV files contain the following columns:

| Column | Type | Description |
|--------|------|-------------|
| `date` | datetime | Timestamp (index) |
| `open` | float | Opening VIX level |
| `high` | float | Highest VIX level |
| `low` | float | Lowest VIX level |
| `close` | float | Closing VIX level |
| `volume` | int | Volume (usually 0 for indices) |

## Troubleshooting

### Error: "dhanhq package not installed"

```bash
pip install dhanhq
```

### Error: "Dhan credentials not provided"

Set environment variables:

```bash
export DHAN_CLIENT_ID='your_client_id'
export DHAN_ACCESS_TOKEN='your_access_token'
```

### Error: "India VIX data not found"

Fetch the data first:

```bash
python3 scripts/fetch_india_vix.py
```

### Error: "No data returned from Dhan API"

Check your credentials and date range. Ensure your Dhan account has data access permissions.

## Notes

- India VIX is calculated by NSE and represents implied volatility
- Higher VIX = Higher expected volatility = Market fear
- Lower VIX = Lower expected volatility = Market complacency
- VIX typically moves inversely to stock markets
- VIX above 30 often indicates significant market stress
- VIX below 15 suggests low volatility and potential complacency

## References

- [NSE India VIX](https://www.nseindia.com/products-services/indices-india-vix)
- [Dhan API Documentation](https://dhanhq.co/docs/)
- [CBOE VIX White Paper](https://www.cboe.com/micro/vix/vixwhite.pdf)
