#!/usr/bin/env python3
"""
Fetch NSE Factor Indices Historical Data

Since NSE website blocks automated access and Yahoo Finance doesn't have factor indices,
we use a combination of:
1. investpy (Investing.com) - Has longer history for some indices
2. Manual NSE CSV download instructions

Usage:
    python scripts/fetch_nse_factor_indices.py
    python scripts/fetch_nse_factor_indices.py --list
    python scripts/fetch_nse_factor_indices.py --manual-download

Note: For the best historical data, manually download from:
    https://www.nseindia.com/reports/indices-historical-data
    - Select "Factor Indices" category
    - Download CSV for each index
"""

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd

# NSE Factor Indices with their launch dates (approximate)
# Note: Factor indices were introduced starting 2014-2015
NSE_FACTOR_INDICES = {
    # Index Name: (Launch Year, Description)
    "NIFTY200 MOMENTUM 30": (2020, "Top 30 momentum stocks from NIFTY 200"),
    "NIFTY100 QUALITY 30": (2015, "Top 30 quality stocks from NIFTY 100"),
    "NIFTY50 VALUE 20": (2016, "Top 20 value stocks from NIFTY 50"),
    "NIFTY ALPHA 50": (2014, "Top 50 alpha stocks"),
    "NIFTY100 LOW VOLATILITY 30": (2016, "30 low volatility stocks from NIFTY 100"),
    "NIFTY50 EQUAL WEIGHT": (2017, "Equal weighted NIFTY 50"),
    "NIFTY ALPHA LOW-VOLATILITY 30": (2016, "Alpha + Low Vol combined"),
    "NIFTY HIGH BETA 50": (2014, "Top 50 high beta stocks"),
    "NIFTY LOW VOLATILITY 50": (2014, "Top 50 low volatility stocks"),
    "NIFTY200 QUALITY 30": (2016, "Top 30 quality from NIFTY 200"),
    "NIFTY200 ALPHA 30": (2020, "Top 30 alpha from NIFTY 200"),
    "NIFTY GROWTH SECTORS 15": (2017, "Growth sector exposure"),
    "NIFTY DIVIDEND OPPORTUNITIES 50": (2014, "Dividend focused"),
    "NIFTY100 EQUAL WEIGHT": (2017, "Equal weighted NIFTY 100"),
    "NIFTY QUALITY LOW-VOLATILITY 30": (2017, "Quality + Low Vol combined"),
    "NIFTY MIDCAP150 MOMENTUM 50": (2020, "Midcap momentum"),
    "NIFTY MIDCAP150 QUALITY 50": (2020, "Midcap quality"),
    "NIFTY500 MOMENTUM 50": (2021, "Large universe momentum"),
}

# ETFs tracking factor indices (have actual tradeable history)
FACTOR_ETFS = {
    "MOM30IETF": ("NIFTY200 MOMENTUM 30", "ICICI Prudential"),
    "QUAL30IETF": ("NIFTY200 QUALITY 30", "ICICI Prudential"),  
    "VAL30IETF": ("NIFTY200 VALUE 30", "ICICI Prudential"),
    "ALPL30IETF": ("NIFTY ALPHA LOW-VOLATILITY 30", "ICICI Prudential"),
    "ALPHAETF": ("NIFTY ALPHA 50", "ICICI Prudential"),
    "LOWVOLIETF": ("NIFTY100 LOW VOLATILITY 30", "ICICI Prudential"),
    "SBIETFQLTY": ("NIFTY200 QUALITY 30", "SBI"),
    "MOM50": ("NIFTY50 MOMENTUM", "Nippon"),
    "GROWWMOM50": ("NIFTY500 MOMENTUM 50", "Groww"),
}


def list_indices():
    """List all NSE factor indices with launch dates."""
    print("\n📊 NSE Factor Indices")
    print("=" * 80)
    print(f"{'Index Name':<45} {'Launch':<8} {'Description'}")
    print("-" * 80)
    
    for name, (year, desc) in sorted(NSE_FACTOR_INDICES.items(), key=lambda x: x[1][0]):
        print(f"{name:<45} {year:<8} {desc}")
    
    print("\n📈 Factor ETFs (Tradeable, have price history)")
    print("-" * 80)
    for etf, (index, issuer) in FACTOR_ETFS.items():
        print(f"{etf:<15} tracks {index:<35} ({issuer})")
    
    print("=" * 80)
    print("""
⚠️  IMPORTANT: Factor indices were introduced 2014-2020, so historical data
   before launch dates doesn't exist. For backtesting factor strategies
   before 2014, you would need to:
   
   1. Use ETF price data (limited to ETF launch dates)
   2. Construct synthetic factor indices from constituent stocks
   3. Use backtested index data from NSE (available for some indices)

📥 Manual Download Instructions:
   1. Go to: https://www.nseindia.com/reports/indices-historical-data
   2. Select Index Category: "Strategy Indices" or "Factor Indices"  
   3. Select the specific index
   4. Choose date range and download CSV
   5. Place in: data/cache/nse/daily/nse_0_{INDEX_NAME}_1d.csv
""")


def show_manual_instructions():
    """Show detailed manual download instructions."""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NSE FACTOR INDICES - MANUAL DOWNLOAD                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Since NSE blocks automated scraping, follow these steps:

STEP 1: Go to NSE Historical Data Viewer
        https://www.nseindia.com/reports/historical-data-viewer

STEP 2: Select Parameters
        - Select "Index"
        - Category: "Factor Indices" or "Strategy Indices"
        - Index Name: Select from list below
        - Date Range: From 01-Jan-2000 to Today
        - Click "Get Data"

STEP 3: Download and Save
        - Click "Download (.csv)"
        - Rename file to format: nse_0_{INDEX_NAME}_1d.csv
        - Save to: data/cache/nse/daily/

═══════════════════════════════════════════════════════════════════════════════
FACTOR INDICES TO DOWNLOAD (with backtested history available):
═══════════════════════════════════════════════════════════════════════════════

1. NIFTY ALPHA 50              - Backtested from Apr 2005
2. NIFTY HIGH BETA 50          - Backtested from Apr 2005
3. NIFTY LOW VOLATILITY 50     - Backtested from Apr 2005
4. NIFTY100 QUALITY 30         - Backtested from Apr 2006
5. NIFTY50 VALUE 20            - Backtested from Apr 2006
6. NIFTY100 LOW VOLATILITY 30  - Backtested from Apr 2006
7. NIFTY ALPHA LOW-VOL 30      - Backtested from Apr 2006
8. NIFTY DIVIDEND OPP 50       - Backtested from Apr 2006
9. NIFTY200 MOMENTUM 30        - Backtested from Apr 2005
10. NIFTY200 QUALITY 30        - Backtested from Apr 2006

═══════════════════════════════════════════════════════════════════════════════
ALTERNATIVE: Use Factor ETFs (actual trading data)
═══════════════════════════════════════════════════════════════════════════════

Already fetched via Groww API in: data/cache/groww/daily/
- ALPHAETF, LOWVOLIETF, MOM30IETF, QUAL30IETF, etc.

These have shorter history (2020-present) but are actual traded prices.

═══════════════════════════════════════════════════════════════════════════════
""")


def main():
    parser = argparse.ArgumentParser(description="NSE Factor Indices Data")
    parser.add_argument("--list", action="store_true", help="List all factor indices")
    parser.add_argument("--manual-download", action="store_true", help="Show manual download instructions")
    args = parser.parse_args()
    
    if args.list:
        list_indices()
    elif args.manual_download:
        show_manual_instructions()
    else:
        # Default: show summary and options
        print("""
📊 NSE Factor Indices Historical Data Fetcher

Since NSE India blocks automated access, use one of these options:

Option 1: Manual Download (Longest History - Back to 2005)
          python scripts/fetch_nse_factor_indices.py --manual-download

Option 2: Use Factor ETFs (Already fetched - 2020 onwards)
          ls data/cache/groww/daily/*ETF*

Option 3: List All Available Indices
          python scripts/fetch_nse_factor_indices.py --list

For detailed help, run with --manual-download
""")


if __name__ == "__main__":
    main()
