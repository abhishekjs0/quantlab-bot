# Data & Analysis Guide

**Complete reference for data management, sources, and analysis methods in QuantLab**

---

## Table of Contents
1. [Data Quality Standards](#data-quality-standards)
2. [Data Sources](#data-sources)
3. [Fetching Data](#fetching-data)
4. [Analysis Methods](#analysis-methods)
5. [API Integration](#api-integration)

---

## Data Quality Standards

### Quality Criteria

✓ **Completeness**: No missing dates in trading days
✓ **Accuracy**: OHLC relationships valid (High ≥ Close ≥ Low)
✓ **Consistency**: No duplicate timestamps
✓ **Freshness**: Data updated within 24 hours
✓ **Format**: Standardized CSV with required columns

### Required Columns

```
Date, Open, High, Low, Close, Volume
```

### Validation Checks

```python
# Basic validation
assert df['High'].ge(df['Low']).all(), "High < Low found"
assert df['High'].ge(df['Close']).all(), "High < Close found"
assert df['Low'].le(df['Close']).all(), "Low > Close found"
assert df.index.is_unique, "Duplicate dates found"
```

### Cleanup Procedures

**Remove Duplicates**
```bash
# Automatic deduplication
python scripts/fix_duplicate_etf_data.py
```

**Fill Missing Data**
```python
# Forward fill missing days (use sparingly)
df = df.resample('D').ffill()
```

**Validate OHLC**
```python
# Fix inverted High/Low
df['High'] = df[['High', 'Low']].max(axis=1)
df['Low'] = df[['High', 'Low']].min(axis=1)
```

### Best Practices

- Always validate data after fetching
- Keep raw data backups before cleanup
- Document all transformations
- Use `data_validation.py` module for checks

---

## Data Sources

### Available Instruments

**ETFs (Exchange Traded Funds)**
- Nifty 50 ETF, Nifty Next 50 ETF
- Bank Nifty ETF, Financial Services ETF
- IT ETF, Pharma ETF, Auto ETF
- Gold ETF, Silver ETF
- 30+ total ETFs covering major sectors

**Indices**
- Nifty 50, Nifty Bank, Nifty IT
- Nifty Midcap 100, Nifty Smallcap 100
- Nifty Alpha 50, Nifty Quality 30
- Nifty Momentum 50, Nifty Value 20
- Factor indices (Quality, Momentum, Value, Low Vol)

**Stocks**
- All Nifty 50 constituents
- Selected Midcap/Smallcap stocks
- Coverage via Groww/Dhan scrip masters

### Data Granularity

| Source | Timeframes | History |
|--------|------------|---------|
| Groww | 1d, 1w | 5+ years |
| Yahoo Finance | 1d | 10+ years |
| Dhan | Intraday | 60 days |
| NSE Archive | 1d | Full history |

---

## Fetching Data

### ETF Data

**Fetch All ETFs (Weekly)**
```bash
python scripts/fetch_etf_weekly_groww.py
```

**Fetch Specific ETF**
```bash
python scripts/fetch_etf_data.py --symbol NIFTYBEES
```

**Output Location**
```
data/etf/
├── NIFTYBEES_1d.csv
├── GOLDBEES_1d.csv
└── BANKBEES_1d.csv
```

### Index Data

**Fetch NSE Indices**
```bash
python scripts/fetch_nse_indices_yahoo.py
```

**Fetch Factor Indices**
```bash
python scripts/fetch_nse_factor_indices.py
```

**Output Location**
```
data/indices/
├── NIFTY50_1d.csv
├── NIFTYBANK_1d.csv
└── NIFTY_ALPHA50_1d.csv
```

### Stock Data

**Fetch from Groww**
```bash
python scripts/fetch_groww_daily_data.py --symbols RELIANCE,TCS,INFY
```

**Update Instrument Master**
```bash
python scripts/fetch_groww_instruments.py
```

### Automation

**Cron Job (Daily Update)**
```bash
# Add to crontab -e
0 18 * * 1-5 cd /path/to/quantlab && python scripts/fetch_all_etf_data.sh
```

**Make Workflow**
```bash
# Fetch all data sources
make fetch-data

# Validate after fetching
make validate-data
```

---

## Analysis Methods

### Factor Analysis

**Overview**: Analyze performance of factor-based strategies (Quality, Momentum, Value, Low Volatility)

**Run Analysis**
```bash
python scripts/analyze_factor_correlations.py
```

**Output**: Factor correlation matrix, performance comparison

**Key Findings**:
- Quality & Momentum: Moderate positive correlation (0.45)
- Value & Momentum: Negative correlation (-0.32)
- Low Vol & Quality: High correlation (0.68)

### Correlation Analysis

**Purpose**: Identify diversification opportunities

```python
import pandas as pd

# Load multiple assets
nifty = pd.read_csv('data/indices/NIFTY50_1d.csv', index_col='Date', parse_dates=True)
gold = pd.read_csv('data/etf/GOLDBEES_1d.csv', index_col='Date', parse_dates=True)

# Calculate returns
returns = pd.DataFrame({
    'Nifty': nifty['Close'].pct_change(),
    'Gold': gold['Close'].pct_change()
})

# Correlation
corr = returns.corr()
print(corr)
```

**Interpretation**:
- Correlation < 0.3: Good diversification
- Correlation > 0.7: Redundant exposure
- Negative correlation: Hedge potential

### Momentum vs Value Analysis

**Run Comparison**
```bash
python scripts/analyze_worst_performer_hypothesis.py
```

**Strategy Comparison**:
- **Momentum**: Buy past winners (20-day return > 10%)
- **Value**: Buy past losers (20-day return < -10%)

**Results**:
- Momentum: Higher Sharpe, lower drawdown
- Value: Lower win rate, but larger wins
- Hybrid: Best risk-adjusted returns

### Pattern Analysis

**Candlestick Patterns**
```bash
python scripts/analyze_candlestick_patterns.py
```

**TA-Lib Patterns**
```bash
python scripts/analyze_talib_patterns.py
```

**Output**: Pattern frequency, win rates, avg returns

---

## API Integration

### Groww API

**Overview**: Unofficial API for Indian market data

**Common Endpoints**:
- `/api/chartsApi/v2/delayed/chart/{search_id}` - OHLCV data
- `/api/v3/search` - Symbol search
- `/app-assets/scrips/` - Instrument master

**Authentication**: None (public endpoints)

### Common Issues & Fixes

**Issue 1: Rate Limiting**
```python
# Add delays between requests
import time
time.sleep(1)  # 1 second between calls
```

**Issue 2: Invalid search_id**
```python
# Load from scrip master first
scrip_master = pd.read_csv('data/groww-scrip-master-detailed.csv')
search_id = scrip_master[scrip_master['symbol'] == 'RELIANCE']['search_id'].iloc[0]
```

**Issue 3: Empty Response**
```python
# Check if symbol is active
if response.status_code == 404:
    print(f"Symbol {symbol} not found or delisted")
```

**Issue 4: Date Format**
```python
# Use ISO 8601 format
from_date = "2024-01-01T00:00:00.000Z"
to_date = "2024-12-31T23:59:59.999Z"
```

**Issue 5: Timeframe Mismatch**
```python
# Valid timeframes: '1d', '1w', '1m'
# Intraday requires different endpoint
```

### Integration Pattern

```python
import requests
import pandas as pd

def fetch_groww_data(search_id, from_date, to_date, timeframe='1d'):
    """Fetch OHLCV data from Groww API"""
    url = f"https://groww.in/v1/api/chartsApi/v2/delayed/chart/{search_id}"
    
    params = {
        'intervalInDays': 1 if timeframe == '1d' else 7,
        'fromDate': from_date,  # ISO 8601 format
        'toDate': to_date,
        'chartType': 'CANDLES'
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()['candles']
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df[['date', 'open', 'high', 'low', 'close', 'volume']]
    else:
        raise Exception(f"API error: {response.status_code}")
```

### Dhan API

**Overview**: Official broker API with real-time data

**Authentication**: API Key + Client ID required

**Rate Limits**: 
- 60 requests/minute (free tier)
- 300 requests/minute (paid tier)

### Yahoo Finance

**Library**: `yfinance`

```python
import yfinance as yf

# Fetch Nifty 50
nifty = yf.download('^NSEI', start='2020-01-01', end='2024-12-31')
```

**Limitations**:
- 15-minute delay
- Limited to major indices
- No intraday data

---

## Related Resources

- [Strategy Guide](STRATEGY_GUIDE.md) - Creating strategies
- [Backtest Guide](BACKTEST_GUIDE.md) - Running backtests
- Main README.md - Project overview
