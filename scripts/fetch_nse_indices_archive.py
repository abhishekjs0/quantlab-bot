#!/usr/bin/env python3
"""
Fetch NSE Factor Indices Historical Data from NSE Archives

This script downloads daily index closing data from nsearchives.nseindia.com,
which is the official NSE archive that allows programmatic access.

Data includes:
- Factor indices (Alpha, Momentum, Quality, Value, Low Volatility, etc.)
- Broad market indices (NIFTY 50, 100, 200, 500, Midcap, Smallcap)
- Sector indices

Archive availability:
- NSE Archives start from: Feb 28, 2012
- Factor indices first appear: Jan 2, 2013 (as CNX Alpha, CNX Low Volatility, CNX High Beta)
- Factor indices renamed to Nifty format: 2015-2016
- Newer factor indices added progressively through 2024-2025

The script handles name mapping between old CNX and new Nifty naming conventions
to provide complete historical data for each factor index.

Usage:
    python scripts/fetch_nse_indices_archive.py                    # Fetch last 2 years
    python scripts/fetch_nse_indices_archive.py --years 5          # Fetch last 5 years
    python scripts/fetch_nse_indices_archive.py --full             # Fetch all available (from Feb 2012)
    python scripts/fetch_nse_indices_archive.py --factor-only      # Only factor indices
"""

import os
import sys
import time
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List
from io import StringIO
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
CACHE_DIR = Path(__file__).parent.parent / "data" / "cache" / "nse" / "daily"
ARCHIVE_URL = "https://nsearchives.nseindia.com/content/indices/ind_close_all_{date}.csv"

# Earliest date archives are available
ARCHIVE_START_DATE = datetime(2012, 2, 28)

# Mapping of old CNX names to new Nifty names (for merging historical data)
# Format: "old_name": "new_name" - data from old_name will be merged into new_name
INDEX_NAME_MAP = {
    # Old CNX names (2013-2015) -> New Nifty names (2016+)
    "CNX Alpha Index": "Nifty Alpha 50",
    "CNX Alpha": "Nifty Alpha 50",
    "CNX Low Volatility": "Nifty Low Volatility 50",
    "CNX High Beta": "Nifty High Beta 50",
    "NSE Quality 30": "Nifty100 Quality 30",
    "Nifty Quality 30": "Nifty100 Quality 30",
    # Variations in naming
    "NIFTY Alpha 50": "Nifty Alpha 50",
    "NIFTY High Beta 50": "Nifty High Beta 50",
    "NIFTY Low Volatility 50": "Nifty Low Volatility 50",
    "NIFTY100 Quality 30": "Nifty100 Quality 30",
    "NIFTY200 Quality 30": "Nifty200 Quality 30",
    "NIFTY200 Momentum 30": "Nifty200 Momentum 30",
    "NIFTY50 Value 20": "Nifty50 Value 20",
    "NIFTY500 Value 50": "Nifty500 Value 50",
    "NIFTY Alpha Low-Volatility 30": "Nifty Alphalowvol",
    "NIFTY Alpha Quality Low-Volatility 30": "Nifty Alpha Quality Low Vol 30",
    "NIFTY Quality Low-Volatility 30": "Nifty Quality Low Vol 30",
    "NIFTY Alpha Quality Value Low-Volatility 30": "Nifty Alpha Quality Value Low Vol 30",
    "NIFTY100 Alpha 30": "Nifty100 Alpha 30",
    "NIFTY100 Low Volatility 30": "Nifty100 Low Volatility 30",
    "NIFTY Midcap150 Quality 50": "Nifty Midcap150 Quality 50",
}

# Factor indices to track (canonical names after mapping)
FACTOR_INDICES = [
    "Nifty Alpha 50",
    "Nifty High Beta 50",
    "Nifty Low Volatility 50",
    "Nifty100 Quality 30",
    "Nifty200 Quality 30",
    "Nifty200 Momentum 30",
    "Nifty50 Value 20",
    "Nifty Alphalowvol",  # Alpha Low Volatility 30
    "Nifty200 Alpha 30",
    "Nifty100 Alpha 30",
    "Nifty200 Value 30",
    "Nifty500 Value 50",
    "Nifty500 Momentum 50",
    "Nifty Midcap150 Momentum 50",
    "Nifty100 Low Volatility 30",
    "Nifty Quality Low Vol 30",
    "Nifty Alpha Quality Low Vol 30",
    "Nifty Midcap150 Quality 50",
    "Nifty Smallcap250 Quality 50",
    "Nifty Smallcap250 Momentum Quality 100",
    "Nifty MidSmallcap400 Momentum Quality 100",
    "Nifty500 Multicap Momentum Quality 50",
    "Nifty500 Quality 50",
    "Nifty500 Low Volatility 50",
    "Nifty Growth Sectors 15",
    "Nifty100 Eql Wgt",
    "Nifty50 Eql Wgt",
]

# Broad market indices for reference
BROAD_INDICES = [
    "Nifty 50",
    "Nifty Next 50",
    "Nifty 100",
    "Nifty 200",
    "Nifty 500",
    "Nifty Midcap 50",
    "Nifty Midcap 100",
    "Nifty Smlcap 100",
    "Nifty Smlcap 250",
    "Nifty Bank",
    "Nifty IT",
    "Nifty Fin Service",
    "India VIX",
]


def create_session() -> requests.Session:
    """Create a session with proper headers."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': '*/*',
    })
    return session


def fetch_daily_bhavcopy(session: requests.Session, date: datetime) -> Optional[pd.DataFrame]:
    """Fetch the daily index bhavcopy for a given date."""
    date_str = date.strftime('%d%m%Y')
    url = ARCHIVE_URL.format(date=date_str)
    
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            df = pd.read_csv(StringIO(resp.text))
            df['Date'] = date
            return df
        elif resp.status_code == 404:
            # Weekend or holiday - normal
            return None
        else:
            return None
    except Exception as e:
        return None


def get_trading_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Generate list of potential trading dates (weekdays only)."""
    dates = []
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0, Friday=4
            dates.append(current)
        current += timedelta(days=1)
    return dates


def fetch_batch(session: requests.Session, dates: List[datetime], progress_callback=None) -> List[pd.DataFrame]:
    """Fetch a batch of dates sequentially."""
    results = []
    for i, date in enumerate(dates):
        df = fetch_daily_bhavcopy(session, date)
        if df is not None:
            results.append(df)
        if progress_callback:
            progress_callback(i + 1, len(dates))
        time.sleep(0.1)  # Be nice to server
    return results


def fetch_index_history(
    start_date: datetime,
    end_date: datetime,
    indices: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Fetch historical data for specified indices.
    
    Args:
        start_date: Start date
        end_date: End date
        indices: List of index names to filter (None = all indices)
    
    Returns:
        DataFrame with historical index data
    """
    session = create_session()
    
    # Get all trading dates
    all_dates = get_trading_dates(start_date, end_date)
    total_days = len(all_dates)
    
    print(f"Fetching data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Trading days to fetch: {total_days}")
    
    all_data = []
    fetched = 0
    
    # Process in chunks for progress reporting
    chunk_size = 20
    for i in range(0, len(all_dates), chunk_size):
        chunk = all_dates[i:i+chunk_size]
        
        for date in chunk:
            df = fetch_daily_bhavcopy(session, date)
            if df is not None:
                all_data.append(df)
                fetched += 1
            time.sleep(0.1)
        
        progress = (i + len(chunk)) / total_days * 100
        print(f"  Progress: {progress:.1f}% ({fetched} trading days fetched)")
    
    if not all_data:
        print("No data fetched!")
        return pd.DataFrame()
    
    result = pd.concat(all_data, ignore_index=True)
    print(f"\nFetched {fetched} trading days, {len(result)} total records")
    return result


def process_and_save(df: pd.DataFrame, output_dir: Path, indices_filter: Optional[List[str]] = None) -> Dict[str, Path]:
    """Process the combined data and save individual index files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    saved_files = {}
    
    # Rename columns to standard format
    column_map = {
        'Index Name': 'index_name',
        'Index Date': 'date_str',
        'Open Index Value': 'open',
        'High Index Value': 'high',
        'Low Index Value': 'low',
        'Closing Index Value': 'close',
        'Points Change': 'change',
        'Change(%)': 'change_pct',
        'Volume': 'volume',
        'Turnover (Rs. Cr.)': 'turnover_cr',
        'P/E': 'pe',
        'P/B': 'pb',
        'Div Yield': 'div_yield',
        'Date': 'date',
    }
    df = df.rename(columns=column_map)
    
    # Apply name mapping to merge old CNX names with new Nifty names
    df['canonical_name'] = df['index_name'].map(lambda x: INDEX_NAME_MAP.get(x, x))
    
    # Filter to requested indices if specified (using canonical names)
    if indices_filter:
        indices_lower = [i.lower() for i in indices_filter]
        df = df[df['canonical_name'].str.lower().isin(indices_lower)]
    
    # Group by canonical name and save individual files
    for index_name, group in df.groupby('canonical_name'):
        # Clean filename
        safe_name = index_name.lower().replace(' ', '_').replace('/', '_')
        filepath = output_dir / f"{safe_name}.csv"
        
        # Sort by date and remove duplicates (in case of overlapping old/new names)
        group = group.sort_values('date').drop_duplicates(subset=['date'], keep='last')
        
        # Select relevant columns
        cols = ['date', 'open', 'high', 'low', 'close', 'volume', 'turnover_cr', 'pe', 'pb', 'div_yield']
        cols = [c for c in cols if c in group.columns]
        
        group[cols].to_csv(filepath, index=False)
        saved_files[index_name] = filepath
        
        date_range = f"{group['date'].min().strftime('%Y-%m-%d')} to {group['date'].max().strftime('%Y-%m-%d')}"
        print(f"  {filepath.name}: {len(group)} rows ({date_range})")
    
    return saved_files


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fetch NSE indices historical data from archives")
    parser.add_argument('--years', type=int, default=2, help='Number of years to fetch (default: 2)')
    parser.add_argument('--full', action='store_true', help='Fetch all available data (from Feb 2012)')
    parser.add_argument('--factor-only', action='store_true', help='Only fetch factor indices')
    parser.add_argument('--output-dir', type=str, default=None, help='Output directory')
    args = parser.parse_args()
    
    # Set date range
    end_date = datetime.now() - timedelta(days=1)
    
    if args.full:
        start_date = ARCHIVE_START_DATE  # Feb 28, 2012 - earliest available
        print("Fetching full history from Feb 28, 2012 (earliest available in NSE archives)...")
        print("Note: Factor indices first appear in Jan 2013 as CNX Alpha, CNX Low Volatility, etc.")
    else:
        start_date = end_date - timedelta(days=365 * args.years)
        print(f"Fetching last {args.years} year(s)...")
    
    # Set output directory
    output_dir = Path(args.output_dir) if args.output_dir else CACHE_DIR
    
    # Determine indices to fetch
    if args.factor_only:
        indices = FACTOR_INDICES
        print(f"Filtering to {len(indices)} factor indices")
    else:
        indices = FACTOR_INDICES + BROAD_INDICES
        print(f"Fetching {len(indices)} indices (factor + broad market)")
    
    print(f"\n{'='*60}")
    print("NSE Indices Historical Data Fetcher (via NSE Archives)")
    print(f"{'='*60}")
    print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"Output: {output_dir}")
    print()
    
    # Sample indices to show
    print("Target indices (sample):")
    for idx in indices[:8]:
        print(f"  - {idx}")
    if len(indices) > 8:
        print(f"  ... and {len(indices) - 8} more")
    print()
    
    # Fetch data
    df = fetch_index_history(start_date, end_date)
    
    if df.empty:
        print("\nNo data fetched. Check your internet connection or date range.")
        return 1
    
    # Process and save
    print(f"\nSaving to {output_dir}...")
    saved = process_and_save(df, output_dir, indices)
    
    print(f"\n{'='*60}")
    print(f"Done! Saved {len(saved)} index files")
    print(f"{'='*60}")
    
    # Print summary of factor indices
    print("\nFactor indices saved:")
    factor_lower = [f.lower() for f in FACTOR_INDICES]
    for name, path in sorted(saved.items()):
        if name.lower() in factor_lower:
            print(f"  ✓ {name}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
