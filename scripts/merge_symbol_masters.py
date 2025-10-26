#!/usr/bin/env python3
"""
Merge API scrip master files to create comprehensive symbol mapping.

This script merges the existing api-scrip-master-detailed.csv with the new
api-scrip-master-new.csv to create a comprehensive symbol database including
indices, ETFs, and other instruments.
"""

import sys
from pathlib import Path

import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config import DATA_DIR


def load_existing_detailed():
    """Load the existing detailed CSV file."""
    detailed_path = DATA_DIR / "api-scrip-master-detailed.csv"
    if not detailed_path.exists():
        print(f"Warning: {detailed_path} not found")
        return pd.DataFrame()

    df = pd.read_csv(detailed_path)
    print(f"Loaded existing detailed file: {len(df)} rows")
    return df


def load_new_master():
    """Load the new comprehensive master CSV file."""
    new_path = DATA_DIR / "api-scrip-master-new.csv"
    if not new_path.exists():
        print(f"Error: {new_path} not found")
        return pd.DataFrame()

    df = pd.read_csv(new_path)
    print(f"Loaded new master file: {len(df)} rows")
    return df


def normalize_new_master(df_new):
    """Normalize the new master file to match detailed file structure."""
    if df_new.empty:
        return df_new

    # Map columns from new format to detailed format
    normalized = pd.DataFrame()

    # Basic mappings
    normalized["SYMBOL_NAME"] = df_new["SEM_TRADING_SYMBOL"]
    normalized["Description"] = df_new["SEM_CUSTOM_SYMBOL"].fillna(
        df_new["SM_SYMBOL_NAME"]
    )
    normalized["SECURITY_ID"] = df_new["SEM_SMST_SECURITY_ID"]
    normalized["UNDERLYING_SYMBOL"] = df_new["SEM_TRADING_SYMBOL"]

    # Add exchange information
    normalized["EXCHANGE"] = df_new["SEM_EXM_EXCH_ID"]
    normalized["SEGMENT"] = df_new["SEM_SEGMENT"]
    normalized["INSTRUMENT_TYPE"] = df_new["SEM_INSTRUMENT_NAME"]
    normalized["SERIES"] = df_new["SEM_SERIES"]
    normalized["LOT_SIZE"] = df_new["SEM_LOT_UNITS"]

    # Set default values for missing columns
    normalized["Sector"] = "Unknown"  # Will be updated for known symbols
    normalized["ISIN"] = ""  # Not available in new file
    normalized["Status"] = "NEW"  # Mark as new entries

    print(f"Normalized new master file: {len(normalized)} rows")
    return normalized


def merge_masters(df_detailed, df_new_norm):
    """Merge the detailed and normalized new master files."""
    if df_detailed.empty:
        return df_new_norm

    if df_new_norm.empty:
        return df_detailed

    # First, update existing symbols with any new information
    existing_symbols = set(df_detailed["SYMBOL_NAME"].str.upper())
    new_symbols = set(df_new_norm["SYMBOL_NAME"].str.upper())

    # Find symbols that exist in both files
    common_symbols = existing_symbols & new_symbols
    print(f"Found {len(common_symbols)} common symbols")

    # Find new symbols from the new master
    only_new_symbols = new_symbols - existing_symbols
    print(f"Found {len(only_new_symbols)} new symbols")

    # Start with existing detailed data
    merged = df_detailed.copy()

    # Add new columns from normalized new master if they don't exist
    new_columns = ["EXCHANGE", "SEGMENT", "INSTRUMENT_TYPE", "SERIES", "LOT_SIZE"]
    for col in new_columns:
        if col not in merged.columns:
            merged[col] = ""

    # Update existing symbols with additional information from new master
    for symbol in common_symbols:
        # Find rows in both dataframes
        detailed_mask = merged["SYMBOL_NAME"].str.upper() == symbol
        new_mask = df_new_norm["SYMBOL_NAME"].str.upper() == symbol

        if detailed_mask.any() and new_mask.any():
            # Update new columns with data from new master
            new_row = df_new_norm[new_mask].iloc[0]
            for col in new_columns:
                if col in df_new_norm.columns and pd.notna(new_row[col]):
                    merged.loc[detailed_mask, col] = new_row[col]

    # Add completely new symbols
    new_symbols_df = df_new_norm[
        df_new_norm["SYMBOL_NAME"].str.upper().isin(only_new_symbols)
    ].copy()

    # Ensure all columns exist in new_symbols_df
    for col in merged.columns:
        if col not in new_symbols_df.columns:
            new_symbols_df[col] = ""

    # Reorder columns to match merged dataframe
    new_symbols_df = new_symbols_df[merged.columns]

    # Append new symbols
    merged = pd.concat([merged, new_symbols_df], ignore_index=True)

    print(f"Merged result: {len(merged)} total rows")
    return merged


def add_index_mappings(df_merged):
    """Add specific mappings for important index instruments."""

    # Key index mappings we want to ensure are present
    index_mappings = [
        {
            "SYMBOL_NAME": "NIFTY",
            "Description": "Nifty 50 Index",
            "Sector": "Index",
            "SECURITY_ID": 13,
            "EXCHANGE": "NSE",
            "INSTRUMENT_TYPE": "INDEX",
            "SERIES": "X",
            "Status": "INDEX",
        },
        {
            "SYMBOL_NAME": "NIFTYBEES",
            "Description": "Nippon Nifty 50 ETF (NIFTYBEES)",
            "Sector": "ETF",
            "SECURITY_ID": 10576,
            "EXCHANGE": "NSE",
            "INSTRUMENT_TYPE": "EQUITY",
            "SERIES": "EQ",
            "Status": "ETF",
        },
        {
            "SYMBOL_NAME": "BANKNIFTY",
            "Description": "Nifty Bank Index",
            "Sector": "Index",
            "SECURITY_ID": 25,
            "EXCHANGE": "NSE",
            "INSTRUMENT_TYPE": "INDEX",
            "SERIES": "X",
            "Status": "INDEX",
        },
    ]

    # Check if these mappings already exist, if not add them
    for mapping in index_mappings:
        symbol = mapping["SYMBOL_NAME"]
        existing = df_merged[df_merged["SYMBOL_NAME"].str.upper() == symbol.upper()]

        if existing.empty:
            # Add the mapping
            new_row = pd.DataFrame([mapping])
            # Ensure all columns exist
            for col in df_merged.columns:
                if col not in new_row.columns:
                    new_row[col] = ""

            # Reorder columns to match merged dataframe
            new_row = new_row[df_merged.columns]
            df_merged = pd.concat([df_merged, new_row], ignore_index=True)
            print(f"Added index mapping for {symbol}")
        else:
            print(f"Index mapping for {symbol} already exists")

    return df_merged


def save_merged_file(df_merged):
    """Save the merged file as the new detailed master."""
    # Create backup of existing file
    detailed_path = DATA_DIR / "api-scrip-master-detailed.csv"
    backup_path = DATA_DIR / "api-scrip-master-detailed.csv.backup"

    if detailed_path.exists():
        detailed_path.rename(backup_path)
        print(f"Created backup: {backup_path}")

    # Save merged file
    df_merged.to_csv(detailed_path, index=False)
    print(f"Saved merged file: {detailed_path} ({len(df_merged)} rows)")

    # Also create a parquet version for faster loading
    parquet_path = DATA_DIR.parent / "cache" / "api-scrip-master-detailed.parquet"
    df_merged.to_parquet(parquet_path, index=False)
    print(f"Saved parquet version: {parquet_path}")


def main():
    """Main function to merge symbol master files."""
    print("=" * 60)
    print("MERGING API SCRIP MASTER FILES")
    print("=" * 60)

    # Load files
    print("\n1. Loading existing files...")
    df_detailed = load_existing_detailed()
    df_new = load_new_master()

    if df_new.empty:
        print("Error: Could not load new master file")
        return False

    # Normalize new master
    print("\n2. Normalizing new master file...")
    df_new_norm = normalize_new_master(df_new)

    # Merge files
    print("\n3. Merging files...")
    df_merged = merge_masters(df_detailed, df_new_norm)

    # Add important index mappings
    print("\n4. Adding index mappings...")
    df_merged = add_index_mappings(df_merged)

    # Save result
    print("\n5. Saving merged file...")
    save_merged_file(df_merged)

    print("\n" + "=" * 60)
    print("MERGE COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Total instruments: {len(df_merged)}")

    # Show summary by instrument type
    if "INSTRUMENT_TYPE" in df_merged.columns:
        print("\nInstrument types:")
        type_counts = df_merged["INSTRUMENT_TYPE"].value_counts()
        for inst_type, count in type_counts.head(10).items():
            print(f"  {inst_type}: {count}")

    # Show exchange distribution
    if "EXCHANGE" in df_merged.columns:
        print("\nExchanges:")
        exchange_counts = df_merged["EXCHANGE"].value_counts()
        for exchange, count in exchange_counts.items():
            print(f"  {exchange}: {count}")

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
