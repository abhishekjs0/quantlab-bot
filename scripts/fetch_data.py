#!/usr/bin/env python3
"""
Unified Data Fetcher for QuantLab
================================

A robust, production-ready data fetching system that:
- Prioritizes Dhan API for Indian stocks
- Falls back to yfinance when Dhan is unavailable
- Validates cache age (1 month threshold for refresh)
- Prevents environment variable conflicts
- Provides comprehensive error handling and logging

Usage:
    python fetch_data.py                    # Fetch all basket symbols
    python fetch_data.py RELIANCE          # Fetch specific symbol
    python fetch_data.py --force-refresh   # Force refresh all cache
    python fetch_data.py --clean-cache     # Remove old yfinance files

Author: QuantLab System
Date: 2025-10-19
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# Add parent directory to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import BASKET_FILE, CACHE_DIR, DATA_DIR, config

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

# Use centralized configuration
MAPPING_FILE = DATA_DIR / "api-scrip-master-detailed.csv"

# Cache and API settings from config
CACHE_EXPIRY_DAYS = config.cache.expiry_days
DHAN_RATE_LIMIT = config.dhan.rate_limit_seconds
YFINANCE_RATE_LIMIT = config.yfinance.rate_limit_seconds

# Dhan API configuration
DHAN_BASE_URL = config.dhan.base_url
DHAN_HISTORICAL_ENDPOINT = f"{DHAN_BASE_URL}/{config.dhan.historical_endpoint}"


# ============================================================================
# ENVIRONMENT VALIDATION & SETUP
# ============================================================================


def validate_environment() -> dict[str, str]:
    """
    Validate and load environment variables using centralized config.

    Returns:
        Dict containing validated environment variables

    Raises:
        SystemExit: If critical environment setup fails
    """
    print("🔧 Validating environment setup...")

    # Use config's credential validation
    if not config.validate_dhan_credentials():
        print("❌ Error: Invalid Dhan credentials!")
        print(
            "   Please check .env file with proper DHAN_ACCESS_TOKEN and DHAN_CLIENT_ID"
        )
        sys.exit(1)

    credentials = config.dhan_credentials

    print(f"   ✅ DHAN_ACCESS_TOKEN loaded ({len(credentials['access_token'])} chars)")
    print(f"   ✅ DHAN_CLIENT_ID: {credentials['client_id']}")

    return credentials


# ============================================================================
# SYMBOL MAPPING & CACHE UTILITIES
# ============================================================================


def load_symbol_mapping() -> pd.DataFrame:
    """Load symbol to security ID mapping from cache or data files."""
    try:
        # Try parquet first (faster)
        parquet_path = CACHE_DIR / "api-scrip-master-detailed.parquet"
        if parquet_path.exists():
            import pyarrow.parquet as pq

            return pq.read_table(parquet_path).to_pandas()

        # Fallback to CSV - use our api-scrip-master-detailed.csv
        csv_path = MAPPING_FILE
        if csv_path.exists():
            return pd.read_csv(csv_path, dtype={"SECURITY_ID": float})

        print("⚠️  Warning: No symbol mapping file found")
        return pd.DataFrame()

    except Exception as e:
        print(f"⚠️  Warning: Error loading symbol mapping: {e}")
        return pd.DataFrame()


def get_security_id(symbol: str, mapping_df: pd.DataFrame):
    """Get Dhan security ID for a given symbol."""
    if mapping_df.empty:
        return None

    # Clean symbol name
    clean_symbol = symbol.replace("NSE:", "").replace(".NS", "").strip()

    # Search in mapping
    matches = mapping_df[
        (mapping_df["SYMBOL_NAME"] == clean_symbol)
        | (mapping_df["UNDERLYING_SYMBOL"] == clean_symbol)
    ]

    if matches.empty:
        return None

    # Return the first match's security ID
    return int(matches.iloc[0]["SECURITY_ID"])


def is_cache_fresh(file_path: Path, max_age_days: int = CACHE_EXPIRY_DAYS) -> bool:
    """Check if cache file is fresh (within max_age_days)."""
    if not file_path.exists():
        return False

    file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
    return file_age.days < max_age_days


def get_cache_paths(symbol: str, security_id=None):
    """Get cache file paths for a symbol."""
    paths = {}

    if security_id:
        paths["dhan"] = CACHE_DIR / f"dhan_historical_{security_id}.csv"
        paths["dhan_meta"] = CACHE_DIR / f"dhan_historical_{security_id}_metadata.json"

    clean_symbol = symbol.replace("NSE:", "").replace(".NS", "").strip()
    paths["yfinance"] = CACHE_DIR / f"yfinance_{clean_symbol}.csv"
    paths["yfinance_meta"] = CACHE_DIR / f"yfinance_{clean_symbol}_metadata.json"

    return paths


# ============================================================================
# DHAN API FUNCTIONS
# ============================================================================


def validate_dhan_token(credentials: dict[str, str]) -> bool:
    """Test Dhan API access with a simple request."""
    try:
        headers = {
            "access-token": credentials["access_token"],
            "client-id": credentials["client_id"],
            "Content-Type": "application/json",
        }

        # Test with fund limits endpoint (lightweight)
        response = requests.get(
            f"{DHAN_BASE_URL}/fundlimit", headers=headers, timeout=10
        )

        return response.status_code == 200

    except Exception:
        return False


def fetch_dhan_data(
    symbol: str,
    security_id: int,
    credentials: dict,
    from_date: str = "2020-01-01",
    to_date=None,
):
    """
    Fetch historical data from Dhan API.

    Returns:
        Tuple of (DataFrame, error_message)
    """
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")

    headers = {
        "access-token": credentials["access_token"],
        "client-id": credentials["client_id"],
        "Content-Type": "application/json",
    }

    payload = {
        "securityId": security_id,
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",
        "expiryCode": 0,
        "fromDate": from_date,
        "toDate": to_date,
    }

    try:
        response = requests.post(
            DHAN_HISTORICAL_ENDPOINT, headers=headers, json=payload, timeout=30
        )

        if response.status_code != 200:
            return None, f"HTTP {response.status_code}: {response.text}"

        data = response.json()

        # Handle Dhan response format: {"open": [], "high": [], ...}
        if not all(
            key in data
            for key in ["open", "high", "low", "close", "volume", "timestamp"]
        ):
            return None, "Invalid Dhan API response format"

        # Convert to DataFrame
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(data["timestamp"], unit="s").strftime(
                    "%Y-%m-%d"
                ),
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
            }
        )

        if df.empty:
            return None, "No data returned from Dhan API"

        return df, None

    except requests.RequestException as e:
        return None, f"Request error: {str(e)}"
    except Exception as e:
        return None, f"Dhan API error: {str(e)}"


# ============================================================================
# YFINANCE FUNCTIONS
# ============================================================================


def fetch_yfinance_data(symbol: str, from_date: str = "2020-01-01", to_date=None):
    """
    Fetch historical data from yfinance as fallback.

    Returns:
        Tuple of (DataFrame, error_message)
    """
    try:
        import yfinance as yf

        # Add .NS suffix for NSE stocks
        clean_symbol = symbol.replace("NSE:", "").replace(".NS", "").strip()
        ticker = f"{clean_symbol}.NS"

        if not to_date:
            to_date = datetime.now().strftime("%Y-%m-%d")

        # Download data
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(start=from_date, end=to_date)

        if df.empty:
            return None, f"No data returned from yfinance for {ticker}"

        # Normalize format
        df = df.reset_index()
        df.columns = df.columns.str.lower()
        df = df.rename(columns={"date": "date"})

        # Ensure date column is string format
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        # Select required columns
        required_cols = ["date", "open", "high", "low", "close", "volume"]
        df = df[required_cols]

        return df, None

    except ImportError:
        return None, "yfinance package not installed"
    except Exception as e:
        return None, f"yfinance error: {str(e)}"


# ============================================================================
# UNIFIED FETCHING LOGIC
# ============================================================================


def save_data_with_metadata(
    df: pd.DataFrame, file_path: Path, source: str, symbol: str
):
    """Save data with metadata for tracking."""
    # Save CSV
    df.to_csv(file_path, index=False)

    # Save metadata
    meta_path = file_path.with_suffix(".csv_metadata.json")
    metadata = {
        "source": source,
        "symbol": symbol,
        "rows": len(df),
        "date_range": {"start": df["date"].min(), "end": df["date"].max()},
        "created_at": datetime.now().isoformat(),
        "columns": list(df.columns),
    }

    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)


def fetch_symbol_data(
    symbol: str,
    credentials: dict[str, str],
    mapping_df: pd.DataFrame,
    force_refresh: bool = False,
) -> dict[str, any]:
    """
    Fetch data for a single symbol with Dhan primary, yfinance fallback.

    Returns:
        Dict with status information
    """
    result = {
        "symbol": symbol,
        "success": False,
        "source": None,
        "rows": 0,
        "error": None,
        "cached": False,
    }

    # Get security ID and cache paths
    security_id = get_security_id(symbol, mapping_df)
    cache_paths = get_cache_paths(symbol, security_id)

    # Check cache first (unless forced refresh)
    if not force_refresh:
        # Check Dhan cache
        if security_id and cache_paths.get("dhan"):
            dhan_path = cache_paths["dhan"]
            if is_cache_fresh(dhan_path):
                try:
                    df = pd.read_csv(dhan_path)
                    result.update(
                        {
                            "success": True,
                            "source": "dhan_cache",
                            "rows": len(df),
                            "cached": True,
                        }
                    )
                    return result
                except Exception:
                    pass

        # Check yfinance cache
        yf_path = cache_paths["yfinance"]
        if is_cache_fresh(yf_path):
            try:
                df = pd.read_csv(yf_path)
                result.update(
                    {
                        "success": True,
                        "source": "yfinance_cache",
                        "rows": len(df),
                        "cached": True,
                    }
                )
                return result
            except Exception:
                pass

    # Try Dhan API first
    if security_id:
        print(f"   Trying Dhan API for {symbol} (ID: {security_id})")
        df, error = fetch_dhan_data(symbol, security_id, credentials)
        if df is not None:
            try:
                save_data_with_metadata(df, cache_paths["dhan"], "dhan", symbol)
                result.update({"success": True, "source": "dhan_api", "rows": len(df)})
                time.sleep(DHAN_RATE_LIMIT)
                return result
            except Exception as e:
                result["error"] = f"Failed to save Dhan data: {e}"
        else:
            print(f"   Dhan API failed for {symbol}: {error}")
            result["error"] = f"Dhan API failed: {error}"
    else:
        print(f"   No security ID found for {symbol}, skipping Dhan API")

    # Fallback to yfinance
    df, error = fetch_yfinance_data(symbol)
    if df is not None:
        try:
            save_data_with_metadata(df, cache_paths["yfinance"], "yfinance", symbol)
            result.update({"success": True, "source": "yfinance_api", "rows": len(df)})
            time.sleep(YFINANCE_RATE_LIMIT)
            return result
        except Exception as e:
            result["error"] = f"Failed to save yfinance data: {e}"
    else:
        result["error"] = f"yfinance failed: {error}"

    return result


# ============================================================================
# CACHE MANAGEMENT
# ============================================================================


def clean_old_cache(dry_run: bool = True) -> dict[str, int]:
    """Remove old cache files, particularly redundant yfinance files."""
    stats = {"removed": 0, "kept": 0, "errors": 0}

    print(f"🧹 {'Simulating' if dry_run else 'Executing'} cache cleanup...")

    for file_path in CACHE_DIR.glob("yfinance_*.csv"):
        try:
            # Get corresponding symbol
            symbol = file_path.stem.replace("yfinance_", "")

            # Check if we have fresh Dhan data for this symbol
            mapping_df = load_symbol_mapping()
            security_id = get_security_id(symbol, mapping_df)

            if security_id:
                dhan_path = CACHE_DIR / f"dhan_historical_{security_id}.csv"
                if dhan_path.exists() and is_cache_fresh(dhan_path):
                    print(
                        f"   🗑️  Would remove: {file_path.name} (have fresh Dhan data)"
                    )
                    if not dry_run:
                        file_path.unlink()
                        # Also remove metadata
                        meta_path = file_path.with_suffix(".csv_metadata.json")
                        if meta_path.exists():
                            meta_path.unlink()
                    stats["removed"] += 1
                    continue

            # Keep if no Dhan alternative or if still fresh
            if is_cache_fresh(file_path):
                stats["kept"] += 1
            else:
                print(f"   🗑️  Would remove: {file_path.name} (expired)")
                if not dry_run:
                    file_path.unlink()
                    # Also remove metadata
                    meta_path = file_path.with_suffix(".csv_metadata.json")
                    if meta_path.exists():
                        meta_path.unlink()
                stats["removed"] += 1

        except Exception as e:
            print(f"   ❌ Error processing {file_path.name}: {e}")
            stats["errors"] += 1

    return stats


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def load_basket_symbols() -> list[str]:
    """Load symbols from basket file."""
    try:
        if not BASKET_FILE.exists():
            print(f"❌ Basket file not found: {BASKET_FILE}")
            return []

        with open(BASKET_FILE) as f:
            symbols = [line.strip() for line in f if line.strip()]

        # Remove header if present
        if symbols and symbols[0].lower() == "symbol":
            symbols = symbols[1:]

        return symbols

    except Exception as e:
        print(f"❌ Error loading basket: {e}")
        return []


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Unified Data Fetcher for QuantLab",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python fetch_data.py                     # Fetch all basket symbols
  python fetch_data.py RELIANCE INFY       # Fetch specific symbols
  python fetch_data.py --force-refresh     # Force refresh all cache
  python fetch_data.py --clean-cache       # Remove redundant cache files
  python fetch_data.py --dry-run           # Simulate cache cleanup
        """,
    )

    parser.add_argument(
        "symbols",
        nargs="*",
        help="Specific symbols to fetch (default: all basket symbols)",
    )
    parser.add_argument(
        "--force-refresh", action="store_true", help="Force refresh cache even if fresh"
    )
    parser.add_argument(
        "--clean-cache",
        action="store_true",
        help="Remove old and redundant cache files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be cleaned without actually doing it",
    )

    args = parser.parse_args()

    # Setup
    CACHE_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)

    print("=" * 80)
    print("🚀 QUANTLAB UNIFIED DATA FETCHER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Cache cleanup mode
    if args.clean_cache or args.dry_run:
        stats = clean_old_cache(dry_run=args.dry_run)
        print("\n📊 Cache cleanup results:")
        print(f"   Removed: {stats['removed']}")
        print(f"   Kept: {stats['kept']}")
        print(f"   Errors: {stats['errors']}")
        if args.dry_run:
            print("   (Dry run - no files actually removed)")
        return

    # Data fetching mode
    try:
        # Validate environment
        credentials = validate_environment()

        # Test Dhan API
        print("\n🔌 Testing Dhan API connection...")
        if validate_dhan_token(credentials):
            print("   ✅ Dhan API connection successful")
        else:
            print("   ⚠️  Dhan API connection failed - will use yfinance only")

        # Load symbol mapping
        print("\n📋 Loading symbol mapping...")
        mapping_df = load_symbol_mapping()
        print(f"   Loaded {len(mapping_df)} symbol mappings")

        # Determine symbols to fetch
        if args.symbols:
            symbols = args.symbols
            print(f"\n🎯 Fetching {len(symbols)} specified symbols")
        else:
            symbols = load_basket_symbols()
            print(f"\n📦 Fetching {len(symbols)} basket symbols")

        if not symbols:
            print("❌ No symbols to fetch!")
            return

        # Statistics
        stats = {
            "total": len(symbols),
            "success": 0,
            "failed": 0,
            "cached": 0,
            "dhan_api": 0,
            "yfinance_api": 0,
            "dhan_cache": 0,
            "yfinance_cache": 0,
        }

        failed_symbols = []

        print(f"\n🔄 Processing {len(symbols)} symbols...")
        print("-" * 80)

        # Process each symbol
        for i, symbol in enumerate(symbols, 1):
            result = fetch_symbol_data(
                symbol, credentials, mapping_df, force_refresh=args.force_refresh
            )

            # Update statistics
            if result["success"]:
                stats["success"] += 1
                stats[result["source"]] += 1
                if result["cached"]:
                    stats["cached"] += 1

                cache_indicator = " (cached)" if result["cached"] else ""
                print(
                    f"[{i:3d}/{len(symbols)}] {symbol:15s} ✅ {result['source']}{cache_indicator} ({result['rows']} rows)"
                )
            else:
                stats["failed"] += 1
                failed_symbols.append((symbol, result["error"]))
                print(f"[{i:3d}/{len(symbols)}] {symbol:15s} ❌ {result['error']}")

        # Final summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"Total symbols:        {stats['total']}")
        print(f"Successful:           {stats['success']}")
        print(f"Failed:               {stats['failed']}")
        print(f"From cache:           {stats['cached']}")
        print("")
        print("Source breakdown:")
        print(f"  Dhan API:           {stats['dhan_api']}")
        print(f"  yfinance API:       {stats['yfinance_api']}")
        print(f"  Dhan cache:         {stats['dhan_cache']}")
        print(f"  yfinance cache:     {stats['yfinance_cache']}")
        print("")
        print(f"Success rate:         {stats['success']/stats['total']*100:.1f}%")

        if failed_symbols:
            print(f"\n❌ Failed symbols ({len(failed_symbols)}):")
            for symbol, error in failed_symbols[:10]:  # Show first 10
                print(f"  {symbol}: {error}")
            if len(failed_symbols) > 10:
                print(f"  ... and {len(failed_symbols) - 10} more")

        print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
