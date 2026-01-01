#!/usr/bin/env python3
"""Download Groww Instrument Master List and convert to CSV format.

This script downloads the Groww instrument CSV from their API documentation
and converts it to a standardized format compatible with the backtesting system.

Endpoint: https://groww.in/trade-api/docs/curl/instruments#download-instrument-csv
"""

import os
import sys
import pandas as pd
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "groww-scrip-master-detailed.csv"

# Groww instrument CSV download URL (as per their documentation)
GROWW_INSTRUMENTS_URL = "https://growwapi-assets.groww.in/instruments/instrument.csv"

def download_groww_instruments():
    """Download instrument list from Groww API."""
    try:
        print("📥 Downloading Groww instrument master list...")
        print(f"   URL: {GROWW_INSTRUMENTS_URL}")
        
        response = requests.get(GROWW_INSTRUMENTS_URL, timeout=30)
        response.raise_for_status()
        
        # Parse CSV content
        df = pd.read_csv(pd.io.common.StringIO(response.text))
        
        print(f"✅ Downloaded {len(df)} instruments")
        print(f"\n📋 Columns: {list(df.columns)}")
        print(f"\nSample data:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"❌ Error downloading instruments: {e}")
        return None


def standardize_groww_format(df):
    """Standardize Groww instrument data to our format.
    
    Groww CSV expected columns: symbol, isin, name, exchange, segment, ...
    Our format: SYMBOL_NAME, Description, ISIN, SECURITY_ID, ...
    """
    try:
        # Rename columns to match our standard format
        df_std = df.copy()
        
        # Common column mappings
        column_mapping = {
            'symbol': 'SYMBOL_NAME',
            'name': 'Description',
            'isin': 'ISIN',
            'exchange': 'EXCHANGE',
            'segment': 'SEGMENT',
        }
        
        # Rename available columns
        available_mappings = {k: v for k, v in column_mapping.items() if k in df_std.columns}
        df_std.rename(columns=available_mappings, inplace=True)
        
        print(f"\n✅ Standardized to {len(df_std)} instruments")
        return df_std
        
    except Exception as e:
        print(f"❌ Error standardizing format: {e}")
        return None


def save_master_file(df):
    """Save standardized master file."""
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"\n💾 Saved to: {OUTPUT_FILE}")
        print(f"   Instruments: {len(df)}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving file: {e}")
        return False


def main():
    """Main execution."""
    print("\n" + "="*70)
    print("GROWW INSTRUMENT MASTER LIST DOWNLOADER")
    print("="*70)
    
    # Download instruments
    df = download_groww_instruments()
    if df is None:
        return 1
    
    # Standardize format
    df_std = standardize_groww_format(df)
    if df_std is None:
        return 1
    
    # Save master file
    if not save_master_file(df_std):
        return 1
    
    print("\n" + "="*70)
    print("✅ SUCCESS")
    print("="*70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
