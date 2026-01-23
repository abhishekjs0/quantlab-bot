#!/usr/bin/env python3
"""
Fetch daily and weekly ETF data from Dhan API
"""

import subprocess
import sys
import time
from pathlib import Path

def fetch_etf_data(timeframe):
    """Fetch ETF data for specified timeframe"""
    etf_file = Path("data/baskets/basket_etf_all.txt")
    
    if not etf_file.exists():
        print(f"❌ ETF basket file not found: {etf_file}")
        return False
    
    # Read all ETF symbols
    with open(etf_file) as f:
        etfs = [line.strip() for line in f if line.strip()]
    
    print(f"\n{'='*70}")
    print(f"📊 Fetching {len(etfs)} ETFs - {timeframe} timeframe")
    print(f"{'='*70}\n")
    
    # Batch process ETFs in groups (avoid command line length limits)
    batch_size = 50
    total_batches = (len(etfs) + batch_size - 1) // batch_size
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(etfs))
        batch_symbols = etfs[start_idx:end_idx]
        symbols_str = ",".join(batch_symbols)
        
        print(f"📌 Batch {batch_num + 1}/{total_batches} - {len(batch_symbols)} symbols")
        
        cmd = [
            "python",
            "scripts/dhan_fetch_data.py",
            "--symbols", symbols_str,
            "--timeframe", timeframe
        ]
        
        result = subprocess.run(cmd, capture_output=False, text=True)
        
        if result.returncode != 0:
            print(f"⚠️  Batch {batch_num + 1} had issues")
        
        # Rate limiting - wait between batches
        if batch_num < total_batches - 1:
            time.sleep(1)
    
    return True

def main():
    print("\n🚀 Starting ETF data fetch...")
    
    # Fetch daily data
    print("\n⏳ Fetching daily data...")
    if not fetch_etf_data("1d"):
        sys.exit(1)
    
    print("\n✅ Daily data fetch complete!")
    
    # Fetch 25m data (for aggregating to weekly)
    print("\n⏳ Fetching 25m data (for weekly aggregation)...")
    if not fetch_etf_data("25m"):
        sys.exit(1)
    
    print("\n✅ All ETF data fetch complete!")
    print(f"\n📁 Data cached in: data/cache/dhan/")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
