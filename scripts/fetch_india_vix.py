#!/usr/bin/env python3
"""
Fetch India VIX historical data from Dhan API.

India VIX SECURITY_ID: 21
Exchange: NSE
Segment: INDEX

Usage:
    python3 scripts/fetch_india_vix.py
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import CACHE_DIR, DATA_DIR

# Load .env from both main directory and webhook-service
load_dotenv()  # Load from current directory
webhook_env = Path(__file__).parent.parent / "webhook-service" / ".env"
if webhook_env.exists():
    load_dotenv(webhook_env)  # Load from webhook-service

# Try to import Dhan client
try:
    from dhanhq import dhanhq
except ImportError:
    print("ERROR: dhanhq package not installed. Install with:")
    print("  pip install dhanhq")
    sys.exit(1)


def fetch_india_vix(
    client_id: Optional[str] = None,
    access_token: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    interval: str = "1d",
    save_to: str = "cache",
) -> pd.DataFrame:
    """
    Fetch India VIX historical data from Dhan API.

    Args:
        client_id: Dhan client ID (if None, reads from env DHAN_CLIENT_ID)
        access_token: Dhan access token (if None, reads from env DHAN_ACCESS_TOKEN)
        from_date: Start date (YYYY-MM-DD). Default: 5 years ago
        to_date: End date (YYYY-MM-DD). Default: today
        interval: Timeframe ("1" for 1-min, "5" for 5-min, "1d" for daily)
        save_to: Where to save ("cache", "data", or "both")

    Returns:
        DataFrame with India VIX OHLC data
    """
    # Read credentials from environment if not provided
    if client_id is None:
        client_id = os.getenv("DHAN_CLIENT_ID")
    if access_token is None:
        access_token = os.getenv("DHAN_ACCESS_TOKEN")

    if not client_id or not access_token:
        print("ERROR: Dhan credentials not provided.")
        print("Set environment variables:")
        print("  export DHAN_CLIENT_ID='your_client_id'")
        print("  export DHAN_ACCESS_TOKEN='your_access_token'")
        print("\nOr pass as arguments to fetch_india_vix()")
        print(f"\nDebug: CLIENT_ID={'set' if client_id else 'NOT SET'}, TOKEN={'set' if access_token else 'NOT SET'}")
        sys.exit(1)
    
    print(f"Using CLIENT_ID: {client_id}, TOKEN: {access_token[:20]}...")

    # Initialize Dhan client
    dhan = dhanhq(client_id, access_token)

    # Set default date range
    if to_date is None:
        to_date = datetime.now().strftime("%Y-%m-%d")
    if from_date is None:
        # Default: 5 years of data
        from_date = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")

    print(f"📊 Fetching India VIX data from {from_date} to {to_date}")
    print(f"⏰ Interval: {interval}")

    # India VIX details
    security_id = 21
    exchange_segment = "IDX_I"  # NSE Index segment
    instrument_type = "INDEX"  # Index instrument type

    # Map interval to Dhan API format
    interval_map = {
        "1": 1,
        "5": 5,
        "15": 15,
        "60": 60,
        "1d": dhanhq.DAY,
        "daily": dhanhq.DAY,
    }

    if interval not in interval_map:
        print(f"ERROR: Unsupported interval '{interval}'")
        print(f"Supported: {list(interval_map.keys())}")
        sys.exit(1)

    dhan_interval = interval_map[interval]

    try:
        # Fetch historical data using REST API (same approach as dhan_fetch_data.py)
        print(f"🔄 Calling Dhan API for SECURITY_ID={security_id}...")
        
        # Use historical endpoint for daily data
        if interval in ["1d", "daily"]:
            url = "https://api.dhan.co/v2/charts/historical"
            payload = {
                "securityId": str(security_id),
                "exchangeSegment": exchange_segment,
                "instrument": instrument_type,
                "expiryCode": 0,
                "oi": False,
                "fromDate": from_date,
                "toDate": to_date,
            }
            
            import requests
            headers = {
                "Content-Type": "application/json",
                "access-token": access_token,
                "dhanClientId": client_id,
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"ERROR: HTTP {response.status_code}: {response.text}")
                return pd.DataFrame()
            
            data = response.json()
        else:
            # Intraday data
            url = "https://api.dhan.co/v2/charts/intraday"
            from_str = datetime.strptime(from_date, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
            to_str = datetime.strptime(to_date, "%Y-%m-%d").strftime("%Y-%m-%d %H:%M:%S")
            
            payload = {
                "securityId": str(security_id),
                "exchangeSegment": exchange_segment,
                "instrument": instrument_type,
                "interval": dhan_interval,
                "oi": False,
                "fromDate": from_str,
                "toDate": to_str,
            }
            
            import requests
            headers = {
                "Content-Type": "application/json",
                "access-token": access_token,
                "dhanClientId": client_id,
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                print(f"ERROR: HTTP {response.status_code}: {response.text}")
                return pd.DataFrame()
            
            data = response.json()

        if not data or "timestamp" not in data:
            print("ERROR: No data returned from Dhan API")
            print(f"Response: {data}")
            return pd.DataFrame()

        # Parse response
        timestamps = data["timestamp"]
        if not timestamps:
            print("WARNING: Empty data array in response")
            return pd.DataFrame()

        print(f"✅ Received {len(timestamps)} bars")

        # Convert to DataFrame
        df = pd.DataFrame(
            {
                "time": timestamps,
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data.get("volume", [0] * len(timestamps)),
            }
        )

        # Convert Unix epoch to datetime
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
        df = df.sort_values("time").reset_index(drop=True)

        # Save to files
        timeframe_suffix = interval if interval != "daily" else "1d"
        
        # Convert time column to index for saving
        df_save = df.copy()
        if df_save["time"].dt.tz is not None:
            df_save["time"] = df_save["time"].dt.tz_localize(None)
        
        df_save = df_save.rename(columns={"time": "date"})
        df_save = df_save.set_index("date")
        
        if save_to in ["cache", "both"]:
            cache_path = CACHE_DIR / f"dhan_21_INDIAVIX_{timeframe_suffix}.csv"
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            df_save.to_csv(cache_path)
            print(f"💾 Saved to cache: {cache_path}")

        if save_to in ["data", "both"]:
            data_path = DATA_DIR / "dhan_historical_21.csv"
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            df_save.to_csv(data_path)
            print(f"💾 Saved to data: {data_path}")

        print(f"\n📈 India VIX Data Summary:")
        print(f"   Date range: {df.index[0]} to {df.index[-1]}")
        print(f"   Rows: {len(df)}")
        print(f"   Latest close: {df['close'].iloc[-1]:.2f}")
        print(f"\n   Recent data:")
        print(df.tail())

        return df

    except Exception as e:
        print(f"❌ Error fetching India VIX data: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()


def load_india_vix(interval: str = "1d") -> pd.DataFrame:
    """
    Load India VIX data from cache.

    Args:
        interval: Timeframe ("1d" for daily, "1" for 1-min, etc.)

    Returns:
        DataFrame with India VIX OHLC data

    Raises:
        FileNotFoundError: If cache file not found
    """
    timeframe_suffix = interval if interval != "daily" else "1d"
    cache_path = CACHE_DIR / f"dhan_21_INDIAVIX_{timeframe_suffix}.csv"

    if not cache_path.exists():
        # Also check data directory
        data_path = DATA_DIR / "dhan_historical_21.csv"
        if data_path.exists():
            cache_path = data_path
        else:
            raise FileNotFoundError(
                f"India VIX data not found. Run fetch_india_vix() first.\n"
                f"Expected: {cache_path}"
            )

    df = pd.read_csv(cache_path, parse_dates=["date"], index_col="date")
    return df.sort_index()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fetch India VIX historical data from Dhan")
    parser.add_argument(
        "--from-date",
        help="Start date (YYYY-MM-DD). Default: 5 years ago",
        default=None,
    )
    parser.add_argument(
        "--to-date",
        help="End date (YYYY-MM-DD). Default: today",
        default=None,
    )
    parser.add_argument(
        "--interval",
        help="Timeframe (1, 5, 15, 60, 1d). Default: 1d",
        default="1d",
    )
    parser.add_argument(
        "--save-to",
        help="Where to save (cache, data, both). Default: cache",
        default="cache",
        choices=["cache", "data", "both"],
    )

    args = parser.parse_args()

    # Fetch and save India VIX data
    df = fetch_india_vix(
        from_date=args.from_date,
        to_date=args.to_date,
        interval=args.interval,
        save_to=args.save_to,
    )

    if df.empty:
        print("\n❌ Failed to fetch India VIX data")
        sys.exit(1)
    else:
        print("\n✅ India VIX data fetched successfully!")
