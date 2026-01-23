#!/usr/bin/env python3
"""
Script to fetch NSE indices data from Dhan and Groww APIs

USAGE:
======
# Fetch all indices (requires Dhan & Groww API credentials in .env)
python3 scripts/fetch_all_indices.py

# Fetch only from Dhan
python3 scripts/fetch_all_indices.py --dhan-only

# Fetch only from Groww  
python3 scripts/fetch_all_indices.py --groww-only

# Custom date range
python3 scripts/fetch_all_indices.py --from-date 2020-01-01 --to-date 2025-12-31


NOTES:
======
1. Dhan API Access:
   - Indices are available via Dhan /charts/historical endpoint
   - Exchange segment must be: "NSE_INDEX"
   - Instrument type must be: "INDEX"
   - Requires valid DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN in .env
   
2. Groww API Access:
   - Requires GROWW_API_KEY and GROWW_API_SECRET in .env
   - Uses checksum-based authentication flow
   - Must be approved for "back_test" (historical data) permissions
   
3. Cache Location:
   - Daily data: data/cache/dhan/daily/dhan_{SECID}_{SYMBOL}_1d.csv
   - Weekly data: data/cache/groww/weekly/groww_{TOKEN}_{SYMBOL}_1w.csv
   
4. Available Indices (Dhan SECID):
   - NIFTY (13) - Nifty 50 Index
   - NIFTY 100 (17)
   - NIFTY 200 (18)
   - NIFTY 500 (19)
   - NIFTYMCAP50 (20) - Nifty Mid Cap 50
   - BANKNIFTY (25) - Nifty Bank
   - FINNIFTY (27) - Nifty Financial Services
   - NIFTYIT (29) - Nifty IT
   - NIFTY FMCG (28)
   - NIFTY METAL (31)
   - NIFTY PHARMA (32)
   - NIFTY REALTY (34)
   - NIFTY PSU BANK (33)
   - INDIA VIX (21)
   - And more...

CURRENT STATUS:
===============
✅ Script created: scripts/fetch_all_indices.py
⚠️  Dhan API endpoint requires NSE_INDEX segment (not available via v2/historical/candle)
⚠️  Groww API requires active authentication with approved scopes

WORKAROUND - MANUAL FETCH:
==========================
Use existing scripts instead:
1. For Dhan: python3 scripts/dhan_fetch_data.py --basket <basket_name> --timeframe 1d
2. For Groww: python3 scripts/fetch_groww_weekly_data.py --basket <basket_name>

Then create a basket file with index symbols and run the above commands.

CREATING INDICES BASKET:
========================
1. Create data/baskets/basket_indices.txt with index symbols
2. Run: python3 scripts/dhan_fetch_data.py --basket-file data/baskets/basket_indices.txt --timeframe 1d
3. Run: python3 scripts/fetch_groww_weekly_data.py --basket-file data/baskets/basket_indices.txt

The master files already have index symbols - just extract them:
grep "NSE,I" data/dhan-scrip-master-detailed.csv | cut -d',' -f5 | grep -v "^0$" | sort | uniq > data/baskets/basket_indices.txt
"""

print(__doc__)
