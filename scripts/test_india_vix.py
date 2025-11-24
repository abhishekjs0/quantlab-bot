#!/usr/bin/env python3
"""
Test script to demonstrate India VIX data loading.

Usage:
    python3 scripts/test_india_vix.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loaders import load_india_vix

if __name__ == "__main__":
    try:
        print("📊 Loading India VIX data...")
        
        # Load daily India VIX data
        vix_df = load_india_vix(interval="1d")
        
        print(f"\n✅ Loaded India VIX data successfully!")
        print(f"   Date range: {vix_df.index[0]} to {vix_df.index[-1]}")
        print(f"   Total bars: {len(vix_df)}")
        print(f"   Latest close: {vix_df['close'].iloc[-1]:.2f}")
        
        print("\n📈 Recent India VIX data:")
        print(vix_df.tail(10))
        
        print("\n📊 Statistics:")
        print(vix_df['close'].describe())
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\n💡 To fetch India VIX data, run:")
        print("   python3 scripts/fetch_india_vix.py")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
