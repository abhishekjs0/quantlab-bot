#!/usr/bin/env python3
"""
Fetch NSE Indices Historical Data from Yahoo Finance (back to 2000)

Yahoo Finance provides free historical data for major NSE indices going back to 1990s.

Usage:
    python scripts/fetch_nse_indices_yahoo.py
    python scripts/fetch_nse_indices_yahoo.py --symbols "^NSEI,^NSEBANK"
    python scripts/fetch_nse_indices_yahoo.py --start 2000-01-01

Requires:
    pip install yfinance pandas
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("❌ yfinance not installed. Run: pip install yfinance")
    exit(1)

# NSE Indices available on Yahoo Finance
# Format: Yahoo Symbol -> (Display Name, Our Symbol Name)
YAHOO_NSE_INDICES = {
    "^NSEI": ("NIFTY 50", "NIFTY_50"),
    "^NSEBANK": ("Bank Nifty", "BANKNIFTY"),
    "^CNXIT": ("Nifty IT", "NIFTYIT"),
    "^CNXPHARMA": ("Nifty Pharma", "NIFTY_PHARMA"),
    "^CNXFMCG": ("Nifty FMCG", "NIFTY_FMCG"),
    "^CNXMETAL": ("Nifty Metal", "NIFTY_METAL"),
    "^CNXREALTY": ("Nifty Realty", "NIFTY_REALTY"),
    "^CNXENERGY": ("Nifty Energy", "NIFTY_ENERGY"),
    "^CNXINFRA": ("Nifty Infra", "NIFTY_INFRA"),
    "^CNXPSUBANK": ("Nifty PSU Bank", "NIFTY_PSU_BANK"),
    "^CNXAUTO": ("Nifty Auto", "NIFTY_AUTO"),
    "^CNXMEDIA": ("Nifty Media", "NIFTY_MEDIA"),
    "^CNXPSE": ("Nifty PSE", "NIFTY_PSE"),
    "^CNXSERVICE": ("Nifty Services", "NIFTY_SERVICES"),
    "^CNXFINANCE": ("Nifty Financial Services", "NIFTY_FIN_SERVICES"),
    "^CNXCOMMODITIES": ("Nifty Commodities", "NIFTY_COMMODITIES"),
    "^CNXCONSUMPTION": ("Nifty Consumption", "NIFTY_CONSUMPTION"),
    "^CNXMNC": ("Nifty MNC", "NIFTY_MNC"),
    "^CNX100": ("Nifty 100", "NIFTY_100"),
    "^CNX200": ("Nifty 200", "NIFTY_200"),
    "^CNX500": ("Nifty 500", "NIFTY_500"),
    "^CNXMIDCAP": ("Nifty Midcap 50", "NIFTY_MIDCAP_50"),
    "^NSMIDCP": ("Nifty Midcap 100", "NIFTY_MIDCAP_100"),
    "^CNXSMALLCAP": ("Nifty Smallcap 100", "NIFTY_SMALLCAP_100"),
    "^NSEMDCP50": ("Nifty Midcap Select", "NIFTY_MIDCAP_SELECT"),
    "^INDIAVIX": ("India VIX", "INDIA_VIX"),
}

# Cache directory
CACHE_DIR = Path("data/cache/yahoo/daily")


def fetch_index(yahoo_symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch historical data for a single index from Yahoo Finance."""
    try:
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if df.empty:
            return pd.DataFrame()
        
        # Standardize column names
        df = df.reset_index()
        df = df.rename(columns={
            "Date": "time",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        
        # Keep only relevant columns
        df = df[["time", "open", "high", "low", "close", "volume"]]
        
        # Convert timezone-aware datetime to naive
        if df["time"].dt.tz is not None:
            df["time"] = df["time"].dt.tz_localize(None)
        
        # Format time as date string
        df["time"] = df["time"].dt.strftime("%Y-%m-%d")
        
        return df
    
    except Exception as e:
        print(f"   Error: {e}")
        return pd.DataFrame()


def main():
    parser = argparse.ArgumentParser(description="Fetch NSE indices from Yahoo Finance")
    parser.add_argument("--symbols", type=str, default="all",
                        help="Comma-separated Yahoo symbols (e.g., '^NSEI,^NSEBANK') or 'all'")
    parser.add_argument("--start", type=str, default="2000-01-01",
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--list", action="store_true",
                        help="List available indices")
    args = parser.parse_args()
    
    # List available indices
    if args.list:
        print("\n📊 Available NSE Indices on Yahoo Finance:")
        print("=" * 60)
        for yahoo_sym, (name, our_sym) in YAHOO_NSE_INDICES.items():
            print(f"  {yahoo_sym:20} -> {name:30} ({our_sym})")
        print("=" * 60)
        return
    
    # Create cache directory
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Determine which symbols to fetch
    if args.symbols.lower() == "all":
        symbols_to_fetch = list(YAHOO_NSE_INDICES.keys())
    else:
        symbols_to_fetch = [s.strip() for s in args.symbols.split(",")]
    
    print(f"\n📊 Fetching NSE Indices from Yahoo Finance")
    print(f"   Period: {args.start} to {args.end}")
    print(f"   Indices: {len(symbols_to_fetch)}")
    print("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for yahoo_symbol in symbols_to_fetch:
        if yahoo_symbol not in YAHOO_NSE_INDICES:
            print(f"⚠️  {yahoo_symbol}: Unknown symbol, skipping")
            continue
        
        display_name, our_symbol = YAHOO_NSE_INDICES[yahoo_symbol]
        print(f"{display_name:30}", end=" ", flush=True)
        
        df = fetch_index(yahoo_symbol, args.start, args.end)
        
        if df.empty:
            print("❌ No data")
            error_count += 1
            continue
        
        # Save to cache
        cache_file = CACHE_DIR / f"yahoo_0_{our_symbol}_1d.csv"
        df.to_csv(cache_file, index=False)
        
        # Calculate years of data
        start_dt = pd.to_datetime(df["time"].iloc[0])
        end_dt = pd.to_datetime(df["time"].iloc[-1])
        years = (end_dt - start_dt).days / 365.25
        
        print(f"✅ {len(df):,} days ({years:.1f} years) | {start_dt.year}-{end_dt.year}")
        success_count += 1
    
    print("=" * 60)
    print(f"\n📊 Summary: ✅ {success_count} fetched  ❌ {error_count} failed")
    print(f"   Cache: {CACHE_DIR}")


if __name__ == "__main__":
    main()
