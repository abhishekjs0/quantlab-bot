#!/usr/bin/env python3
"""
Add Sector Column to Scrip Master Files
========================================
Enriches dhan-scrip-master-detailed.csv and groww-scrip-master-detailed.csv
with sector information from Large Cap, Mid Cap, and Small Cap CSV files.
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path("data")

def load_sector_data():
    """Load and combine sector data from all cap files."""
    sector_map = {}
    
    files = [
        ("Large Cap_NSE_2026-01-02.csv", "Large Cap"),
        ("Mid Cap_NSE_2026-01-02.csv", "Mid Cap"),
        ("Small Cap_NSE_2026-01-02.csv", "Small Cap"),
    ]
    
    for filename, cap_type in files:
        filepath = DATA_DIR / filename
        if filepath.exists():
            print(f"Loading {filename}...")
            df = pd.read_csv(filepath)
            print(f"   Found {len(df)} rows")
            
            for _, row in df.iterrows():
                symbol = str(row.get("Symbol", "")).strip()
                sector = str(row.get("Sector", "")).strip()
                
                if symbol and sector and sector != "nan":
                    # Clean symbol - remove any suffixes like .E1
                    clean_symbol = symbol.split(".")[0]
                    
                    # Store both the original and cleaned symbol
                    if symbol not in sector_map:
                        sector_map[symbol] = {"sector": sector, "cap_type": cap_type}
                    if clean_symbol not in sector_map:
                        sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
        else:
            print(f"   Warning: {filename} not found")
    
    print(f"\nTotal unique symbols with sector data: {len(sector_map)}")
    return sector_map


def update_dhan_scrip_master(sector_map):
    """Update dhan-scrip-master-detailed.csv with sector information."""
    filepath = DATA_DIR / "dhan-scrip-master-detailed.csv"
    
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return
    
    print(f"\nUpdating {filepath}...")
    df = pd.read_csv(filepath)
    print(f"   Original rows: {len(df)}")
    
    # Add new columns
    df["SECTOR"] = ""
    df["CAP_TYPE"] = ""
    
    # Match count
    matched = 0
    
    # Try to match by SEM_TRADING_SYMBOL (column 6) and SM_SYMBOL_NAME (column 16)
    for idx, row in df.iterrows():
        trading_symbol = str(row.get("SEM_TRADING_SYMBOL", "")).strip()
        symbol_name = str(row.get("SM_SYMBOL_NAME", "")).strip()
        
        # Clean trading symbol - take first part before any dash
        clean_trading = trading_symbol.split("-")[0] if trading_symbol else ""
        
        # Try different matching strategies
        sector_info = None
        
        # 1. Try exact trading symbol match
        if trading_symbol in sector_map:
            sector_info = sector_map[trading_symbol]
        # 2. Try cleaned trading symbol
        elif clean_trading in sector_map:
            sector_info = sector_map[clean_trading]
        # 3. Try symbol name (typically first word)
        elif symbol_name:
            first_word = symbol_name.split()[0] if symbol_name else ""
            if first_word in sector_map:
                sector_info = sector_map[first_word]
        
        if sector_info:
            df.at[idx, "SECTOR"] = sector_info["sector"]
            df.at[idx, "CAP_TYPE"] = sector_info["cap_type"]
            matched += 1
    
    print(f"   Matched {matched} rows with sector data")
    
    # Save updated file
    df.to_csv(filepath, index=False)
    print(f"   Saved updated file: {filepath}")
    
    # Show sample of matched rows
    matched_df = df[df["SECTOR"] != ""].head(10)
    print(f"\n   Sample matched rows:")
    if "SEM_TRADING_SYMBOL" in df.columns:
        print(matched_df[["SEM_TRADING_SYMBOL", "SECTOR", "CAP_TYPE"]].to_string())


def update_groww_scrip_master(sector_map):
    """Update groww-scrip-master-detailed.csv with sector information."""
    filepath = DATA_DIR / "groww-scrip-master-detailed.csv"
    
    if not filepath.exists():
        print(f"Error: {filepath} not found")
        return
    
    print(f"\nUpdating {filepath}...")
    df = pd.read_csv(filepath)
    print(f"   Original rows: {len(df)}")
    
    # Add new columns
    df["SECTOR"] = ""
    df["CAP_TYPE"] = ""
    
    # Match count
    matched = 0
    
    # Try to match by trading_symbol, underlying_symbol, or groww_symbol
    for idx, row in df.iterrows():
        trading_symbol = str(row.get("trading_symbol", "")).strip()
        underlying_symbol = str(row.get("underlying_symbol", "")).strip()
        groww_symbol = str(row.get("groww_symbol", "")).strip()
        
        # Clean symbols
        clean_trading = trading_symbol.split("-")[0] if trading_symbol else ""
        
        # Try different matching strategies
        sector_info = None
        
        # 1. Try exact trading symbol match
        if trading_symbol in sector_map:
            sector_info = sector_map[trading_symbol]
        # 2. Try underlying symbol
        elif underlying_symbol in sector_map:
            sector_info = sector_map[underlying_symbol]
        # 3. Try cleaned trading symbol  
        elif clean_trading in sector_map:
            sector_info = sector_map[clean_trading]
        # 4. Try extracting from groww_symbol (format: NSE-SYMBOL-...)
        elif groww_symbol:
            parts = groww_symbol.split("-")
            if len(parts) >= 2:
                extracted = parts[1]
                if extracted in sector_map:
                    sector_info = sector_map[extracted]
        
        if sector_info:
            df.at[idx, "SECTOR"] = sector_info["sector"]
            df.at[idx, "CAP_TYPE"] = sector_info["cap_type"]
            matched += 1
    
    print(f"   Matched {matched} rows with sector data")
    
    # Save updated file
    df.to_csv(filepath, index=False)
    print(f"   Saved updated file: {filepath}")
    
    # Show sample of matched rows
    matched_df = df[df["SECTOR"] != ""].head(10)
    print(f"\n   Sample matched rows:")
    cols_to_show = ["trading_symbol", "SECTOR", "CAP_TYPE"]
    cols_available = [c for c in cols_to_show if c in df.columns]
    if cols_available:
        print(matched_df[cols_available].to_string())


def print_sector_summary(sector_map):
    """Print summary of sectors found."""
    sectors = {}
    for symbol, info in sector_map.items():
        sector = info["sector"]
        if sector not in sectors:
            sectors[sector] = 0
        sectors[sector] += 1
    
    print("\n" + "="*50)
    print("SECTOR SUMMARY")
    print("="*50)
    for sector, count in sorted(sectors.items(), key=lambda x: -x[1]):
        print(f"   {sector}: {count} symbols")


def main():
    print("="*60)
    print("ADDING SECTOR DATA TO SCRIP MASTER FILES")
    print("="*60)
    
    # Load sector data
    sector_map = load_sector_data()
    
    if not sector_map:
        print("No sector data loaded. Exiting.")
        return
    
    # Print sector summary
    print_sector_summary(sector_map)
    
    # Update scrip master files
    update_dhan_scrip_master(sector_map)
    update_groww_scrip_master(sector_map)
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
