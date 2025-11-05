# Dhan API Usage

## Setup

1. **Get Access Token**
   ```bash
   python scripts/dhan_auth.py
   ```
   - Browser opens automatically
   - Script auto-fills mobile, password, TOTP
   - You copy tokenId from redirect URL
   - Token saved to .env

2. **Verify Setup**
   ```bash
   python scripts/test_dhan.py
   ```

## Fetch Data

**Live Quotes**
```python
from scripts.dhan_data_fetcher import fetch_live_quote
quote = fetch_live_quote("NSE_EQ|100")  # RELIANCE
```

**Minute Candles**
```python
from scripts.dhan_data_fetcher import fetch_historical_candles
candles = fetch_historical_candles("NSE_EQ|100", interval_minutes=1, days_back=1)
```

**Use in Backtest**
```bash
python scripts/fetch_data.py RELIANCE
```

## Security IDs

| Symbol | ID |
|--------|-----|
| RELIANCE | 100 |
| INFY | 10188 |
| TCS | 1023 |
| HDFCBANK | 10397 |

See `data/api-scrip-master-detailed.csv` for full list.

## API Docs

https://dhanhq.co/docs/v2/
