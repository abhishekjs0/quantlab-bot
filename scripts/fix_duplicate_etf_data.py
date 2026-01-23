#!/usr/bin/env python3
"""
Fix duplicate dates in ETF cache files by keeping only unique dates with most recent data.
For duplicate dates with different prices, keep the row with the higher price scale.
"""

import pandas as pd
import os
from pathlib import Path
import shutil

def fix_etf_file(filepath):
    """Fix duplicate dates in a single ETF file."""
    # Backup original file
    backup_path = str(filepath) + '.backup'
    shutil.copy2(filepath, backup_path)
    
    # Read file
    df = pd.read_csv(filepath)
    
    # Determine date column
    if 'time' in df.columns:
        date_col = 'time'
    elif 'date' in df.columns:
        date_col = 'date'
    else:
        print(f"  ⚠️  No date column found in {filepath}")
        return False
    
    original_len = len(df)
    df[date_col] = pd.to_datetime(df[date_col])
    
    # Count duplicates before fix
    dup_count = df[date_col].duplicated().sum()
    
    if dup_count == 0:
        print(f"  ✓ No duplicates in {filepath.name}")
        os.remove(backup_path)
        return True
    
    # For duplicates, keep the row with highest close price (highest scale)
    # This handles cases where prices are in different scales (e.g., 11.74 vs 117.4)
    df = df.sort_values([date_col, 'close'], ascending=[True, False])
    df = df.drop_duplicates(subset=[date_col], keep='first')
    df = df.sort_values(date_col)
    
    # Save fixed file
    df.to_csv(filepath, index=False)
    
    print(f"  ✓ Fixed {filepath.name}: {original_len} → {len(df)} rows (removed {dup_count} duplicates)")
    return True

def main():
    # Read ETF basket
    basket_file = Path('data/baskets/basket_etf.txt')
    with open(basket_file) as f:
        etfs = [line.strip() for line in f if line.strip()]
    
    print(f"Fixing duplicate dates in ETF cache files...")
    print("=" * 80)
    
    # Problem files identified
    problem_etfs = [
        'AUTOIETF', 'BSE500IETF', 'COMMOIETF', 'FINIETF', 'HEALTHIETF',
        'INFRAIETF', 'ITIETF', 'MIDCAPIETF', 'SETFGOLD', 'SILVERIETF'
    ]
    
    fixed_count = 0
    error_count = 0
    
    for symbol in problem_etfs:
        # Find the cache file
        daily_files = [f for f in os.listdir('data/cache/dhan/daily/') 
                      if symbol in f and f.endswith('_1d.csv')]
        
        if not daily_files:
            print(f"  ⚠️  {symbol}: File not found")
            error_count += 1
            continue
        
        filepath = Path('data/cache/dhan/daily') / daily_files[0]
        
        try:
            if fix_etf_file(filepath):
                fixed_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"  ✗ {symbol}: Error - {str(e)}")
            error_count += 1
    
    print("\n" + "=" * 80)
    print(f"Summary: {fixed_count} files fixed, {error_count} errors")
    print("\nBackup files created with .backup extension")
    print("If everything looks good, you can remove them with:")
    print("  rm data/cache/dhan/daily/*.backup")

if __name__ == '__main__':
    main()
