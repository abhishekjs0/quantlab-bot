#!/usr/bin/env python3
"""
Dhan Historical Data Fetcher - Production Ready
================================================
Universal script for fetching OHLCV data from any basket and timeframe.
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")

CACHE_DIR = Path("data/cache")
MASTER_FILE = Path("data/api-scrip-master-detailed.csv")

# Historical data cutoff dates
DAILY_DATA_CUTOFF = datetime(2015, 11, 9)  # 1d data from 2015-11-09 onwards
INTRADAY_DATA_CUTOFF = datetime(2017, 4, 3)  # Intraday from 2017-04-03 onwards

BASKETS = {
    "main": "data/basket_main.txt",
    "mega": "data/basket_mega.txt",
    "large": "data/basket_large.txt",
    "small": "data/basket_small.txt",
    "test": "data/basket_test.txt",
    "all_baskets": "data/basket_all_baskets.txt",
    "midcap_highbeta": "data/basket_midcap_highbeta.txt",
    "largecap_highbeta": "data/basket_largecap_highbeta.txt",
    "smallcap_highbeta": "data/basket_smallcap_highbeta.txt",
    "largecap_lowbeta": "data/basket_largecap_lowbeta.txt",
    "midcap_lowbeta": "data/basket_midcap_lowbeta.txt",
    "smallcap_lowbeta": "data/basket_smallcap_lowbeta.txt",
}

# Special symbols that need different exchange segments
SPECIAL_SYMBOLS = {
    "INDIA_VIX": {"security_id": 21, "exchange_segment": "IDX_I", "instrument": "INDEX"},
    "NIFTY": {"security_id": 13, "exchange_segment": "IDX_I", "instrument": "INDEX"},
    "BANKNIFTY": {"security_id": 25, "exchange_segment": "IDX_I", "instrument": "INDEX"},
    "NIFTYBEES": {"security_id": 10576, "exchange_segment": "NSE_EQ", "instrument": "ETF"},
}

TIMEFRAMES_INTRADAY = {"1m": 1, "5m": 5, "15m": 15, "25m": 25, "60m": 60}

MAX_RETRIES = 3
BASE_WAIT_TIME = 0.5
MAX_WAIT_TIME = 8


def check_token_expiry():
    """Check if access token is valid."""
    if not DHAN_ACCESS_TOKEN:
        return False, "❌ DHAN_ACCESS_TOKEN not set in .env"

    try:
        parts = DHAN_ACCESS_TOKEN.split(".")
        if len(parts) != 3:
            return False, "❌ Invalid token format"

        payload = parts[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))

        exp = decoded.get("exp", 0)
        now = time.time()

        if now > exp:
            return False, "❌ Token expired"

        hours_left = (exp - now) / 3600
        if hours_left < 1:
            return False, f"❌ Token expires in {hours_left:.1f} hours"

        return True, f"✅ Token valid ({hours_left:.1f} hours left)"

    except Exception:
        return False, "⚠️ Cannot validate token (will attempt fetch)"


def get_headers():
    """Get request headers."""
    return {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
    }


def load_master_data():
    """Load NSE master data."""
    if not MASTER_FILE.exists():
        print(f"❌ Master file not found: {MASTER_FILE}")
        return {}

    try:
        df = pd.read_csv(MASTER_FILE)
        mapping = {}
        for _, row in df.iterrows():
            symbol = row["SYMBOL_NAME"]
            secid = int(row["SECURITY_ID"])
            mapping[symbol] = secid
        return mapping
    except Exception:
        print("❌ Failed to load master data")
        return {}


def load_basket(basket_name):
    """Load basket symbols."""
    if basket_name not in BASKETS:
        print(f"❌ Unknown basket: {basket_name}")
        return []

    basket_file = Path(BASKETS[basket_name])
    if not basket_file.exists():
        print(f"❌ Basket file not found: {basket_file}")
        return []

    try:
        with open(basket_file) as f:
            symbols = [line.strip() for line in f if line.strip()]
        return symbols
    except Exception:
        print("❌ Failed to load basket")
        return []


def get_cached_symbols(timeframe):
    """Get cached symbols for timeframe."""
    cached = set()
    if not CACHE_DIR.exists():
        return cached

    suffix = f"_{timeframe}.csv"
    for csv_file in CACHE_DIR.glob(f"dhan_*{suffix}"):
        parts = csv_file.stem.split("_")
        if len(parts) >= 3:
            symbol = parts[2]
            cached.add(symbol)

    return cached


def fetch_with_retry(endpoint, payload, description):
    """Make API request with exponential backoff."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=get_headers(),
                timeout=15,
            )

            if response.status_code == 200:
                return response.json()

            if response.status_code == 401:
                return None

            if response.status_code == 429:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), MAX_WAIT_TIME)
                time.sleep(wait)
                continue

            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), MAX_WAIT_TIME)
                time.sleep(wait)

        except (requests.Timeout, Exception):
            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), MAX_WAIT_TIME)
                time.sleep(wait)

    return None


def fetch_intraday_data(sec_id, symbol, interval, start_date, end_date, exchange_segment="NSE_EQ", instrument="EQUITY"):
    """Fetch intraday candles."""
    from_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    to_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "securityId": str(sec_id),
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "interval": interval,
        "oi": False,
        "fromDate": from_str,
        "toDate": to_str,
    }

    data = fetch_with_retry(
        f"{DHAN_BASE_URL}/charts/intraday",
        payload,
        f"{interval}m {symbol}",
    )

    if not data or "timestamp" not in data:
        return None

    try:
        df = pd.DataFrame(
            {
                "time": data["timestamp"],
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
            }
        )

        if df.empty:
            return None

        # CRITICAL FIX: Convert Unix epoch to IST (UTC+5:30), not UTC
        # Dhan API returns epoch timestamps which are timezone-agnostic
        # Indian market operates in IST, so convert to that timezone
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
        return df.sort_values("time").reset_index(drop=True)

    except Exception:
        return None


def fetch_intraday_chunked(sec_id, symbol, interval, start_date, end_date, exchange_segment="NSE_EQ", instrument="EQUITY"):
    """Fetch intraday data in 90-day chunks."""
    all_dfs = []
    current_start = start_date

    while current_start < end_date:
        current_end = min(current_start + timedelta(days=89), end_date)

        df = fetch_intraday_data(sec_id, symbol, interval, current_start, current_end, exchange_segment, instrument)
        if df is not None and not df.empty:
            all_dfs.append(df)

        current_start = current_end + timedelta(seconds=1)
        time.sleep(0.1)

    if not all_dfs:
        return None

    result = pd.concat(all_dfs, ignore_index=True)
    return (
        result.sort_values("time")
        .reset_index(drop=True)
        .drop_duplicates(subset=["time"])
    )


def fetch_daily_data(sec_id, symbol, start_date, end_date, exchange_segment="NSE_EQ", instrument="EQUITY"):
    """Fetch daily candles."""
    payload = {
        "securityId": str(sec_id),
        "exchangeSegment": exchange_segment,
        "instrument": instrument,
        "expiryCode": 0,
        "oi": False,
        "fromDate": start_date.strftime("%Y-%m-%d"),
        "toDate": end_date.strftime("%Y-%m-%d"),
    }

    data = fetch_with_retry(
        f"{DHAN_BASE_URL}/charts/historical",
        payload,
        f"daily {symbol}",
    )

    if not data or "timestamp" not in data:
        return None

    try:
        df = pd.DataFrame(
            {
                "time": data["timestamp"],
                "open": data["open"],
                "high": data["high"],
                "low": data["low"],
                "close": data["close"],
                "volume": data["volume"],
            }
        )

        if df.empty:
            return None

        # CRITICAL FIX: Convert Unix epoch to IST (UTC+5:30), not UTC
        # Dhan API returns epoch timestamps which are timezone-agnostic
        # Indian market operates in IST, so convert to that timezone
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
        return df.sort_values("time").reset_index(drop=True)

    except Exception:
        return None


def aggregate_intraday(df_base, target_minutes):
    """Aggregate base candles to target timeframe."""
    if df_base is None or df_base.empty:
        return None

    df = df_base.copy()
    df["period"] = df["time"].dt.floor(f"{target_minutes}min")

    agg_list = []
    for _, group in df.groupby("period"):
        if group.empty:
            continue

        agg_list.append(
            {
                "time": group["time"].iloc[0],
                "open": group["open"].iloc[0],
                "high": group["high"].max(),
                "low": group["low"].min(),
                "close": group["close"].iloc[-1],
                "volume": group["volume"].sum(),
            }
        )

    if not agg_list:
        return None

    return pd.DataFrame(agg_list).sort_values("time").reset_index(drop=True)


def save_candles(df, sec_id, symbol, timeframe):
    """Save candles to CSV."""
    if df is None or df.empty:
        return False

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        output_file = CACHE_DIR / f"dhan_{sec_id}_{symbol}_{timeframe}.csv"

        df_save = df[["time", "open", "high", "low", "close", "volume"]].copy()
        df_save["time"] = pd.to_datetime(df_save["time"])

        # Convert IST to tz-naive for storage
        # At this point, timestamps should be in IST timezone from fetch functions
        if df_save["time"].dt.tz is not None:
            # If timezone-aware, remove timezone info (already in IST)
            df_save["time"] = df_save["time"].dt.tz_localize(None)

        df_save.set_index("time").to_csv(output_file)

        return True

    except Exception:
        return False


def fetch_stock_data(sec_id, symbol, timeframe, days_back=730, exchange_segment="NSE_EQ", instrument="EQUITY"):
    """Fetch all data for a symbol from historical cutoff dates or days_back (whichever is longer)."""
    # Use yesterday as end_date (market data available up to yesterday)
    end_date = datetime.now().replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=1)

    # Determine start date based on timeframe
    if timeframe == "1d":
        # Daily: from 2015-11-09 onwards
        cutoff_date = DAILY_DATA_CUTOFF
    else:
        # Intraday: from 2017-04-03 onwards
        cutoff_date = INTRADAY_DATA_CUTOFF

    # Also consider days_back for user override
    days_back_date = end_date - timedelta(days=days_back)

    # Use the earlier date (longer history)
    start_date = min(cutoff_date, days_back_date)

    try:
        # Daily timeframe
        if timeframe == "1d":
            df = fetch_daily_data(sec_id, symbol, start_date, end_date, exchange_segment, instrument)
            if df is None or df.empty:
                return False, "No data"

            if not save_candles(df, sec_id, symbol, "1d"):
                return False, "Save failed"

            return True, f"{len(df)} candles"

        # Special-case: 25m is used as a temporary base to derive 75m and 125m
        if timeframe == "25m":
            df_25m = fetch_intraday_chunked(sec_id, symbol, 25, start_date, end_date, exchange_segment, instrument)
            if df_25m is None or df_25m.empty:
                return False, "No data"

            # Aggregate to 75m and 125m and persist those. Do NOT persist the 25m base.
            df_75m = aggregate_intraday(df_25m, 75)
            df_125m = aggregate_intraday(df_25m, 125)

            if (df_75m is None or df_75m.empty) and (df_125m is None or df_125m.empty):
                return False, "Aggregation failed"

            saved75 = saved125 = True
            if df_75m is not None and not df_75m.empty:
                saved75 = save_candles(df_75m, sec_id, symbol, "75m")
            if df_125m is not None and not df_125m.empty:
                saved125 = save_candles(df_125m, sec_id, symbol, "125m")

            if not (saved75 and saved125):
                return False, "Save failed"

            return (
                True,
                f"{len(df_25m)} base (25m) -> {len(df_75m) if df_75m is not None else 0} (75m), {len(df_125m) if df_125m is not None else 0} (125m)",
            )

        # Other intraday timeframes (1m/5m/15m/60m) - fetch and persist directly
        if timeframe in TIMEFRAMES_INTRADAY:
            interval = TIMEFRAMES_INTRADAY[timeframe]
            df = fetch_intraday_chunked(sec_id, symbol, interval, start_date, end_date, exchange_segment, instrument)
            if df is None or df.empty:
                return False, "No data"

            if not save_candles(df, sec_id, symbol, timeframe):
                return False, "Save failed"

            return True, f"{len(df)} candles"

        return False, "Unknown timeframe"

    except Exception as e:
        return False, str(e)[:120]


def main():
    parser = argparse.ArgumentParser(
        description="Fetch historical OHLCV data from Dhan API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 dhan_fetch_data.py --basket large --timeframe 1d
  python3 dhan_fetch_data.py --basket mega --timeframe 25m
  python3 dhan_fetch_data.py --symbols RELIANCE,INFY,TCS --timeframe 1d
  python3 dhan_fetch_data.py --symbols INDIA_VIX --timeframe 1d
  python3 dhan_fetch_data.py --symbols NIFTY,BANKNIFTY --timeframe 1d
  python3 dhan_fetch_data.py --basket small --timeframe 1d --days-back 90

Special symbols (indexes):
  INDIA_VIX, NIFTY, BANKNIFTY, NIFTYBEES
        """,
    )

    parser.add_argument("--basket", choices=list(BASKETS.keys()), help="Basket name")
    parser.add_argument("--symbols", type=str, help="Comma-separated symbols")
    parser.add_argument(
        "--timeframe",
        choices=["1d"] + list(TIMEFRAMES_INTRADAY.keys()) + ["25m"],
        default="1d",
    )
    parser.add_argument("--days-back", type=int, default=730, help="Days of history")
    parser.add_argument(
        "--skip-token-check", action="store_true", help="Skip expiry check"
    )
    parser.add_argument(
        "--refetch", action="store_true", help="Refetch all symbols even if cached"
    )

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("DhanHQ Historical Data Fetcher - Production Ready")
    print("=" * 70)

    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("❌ DHAN credentials not in .env")
        sys.exit(1)

    if not args.skip_token_check:
        valid, msg = check_token_expiry()
        print(msg)
        if not valid and "Cannot validate" not in msg:
            sys.exit(1)

    print("\n📊 Loading data...")
    master = load_master_data()
    if not master:
        sys.exit(1)

    print(f"✅ Loaded {len(master)} symbols")

    symbols_to_fetch = []
    if args.symbols:
        symbols_to_fetch = [s.strip().upper() for s in args.symbols.split(",")]
    elif args.basket:
        symbols_to_fetch = load_basket(args.basket)
    else:
        print("❌ Specify --basket or --symbols")
        parser.print_help()
        sys.exit(1)

    if not symbols_to_fetch:
        print("❌ No symbols")
        sys.exit(1)

    print(
        f"📌 Fetching {len(symbols_to_fetch)} symbols ({args.timeframe}, {args.days_back}d)"
    )

    cached = get_cached_symbols(args.timeframe)
    missing = [s for s in symbols_to_fetch if s not in cached]

    # If refetch flag is set, treat all symbols as missing
    if args.refetch:
        missing = symbols_to_fetch
        print(f"🔄 Refetch mode: {len(missing)} symbols will be refetched")

    print(f"✅ Cached: {len(cached)}")
    print(f"📌 Missing: {len(missing)}\n")

    if not missing:
        print("✅ All symbols cached!")
        sys.exit(0)

    successful = 0
    failed = 0
    failed_symbols = []

    for i, symbol in enumerate(missing, 1):
        # Check if it's a special symbol (index/ETF)
        if symbol in SPECIAL_SYMBOLS:
            spec = SPECIAL_SYMBOLS[symbol]
            sec_id = spec["security_id"]
            exchange_segment = spec["exchange_segment"]
            instrument = spec["instrument"]
        elif symbol not in master:
            print(f"[{i:3d}/{len(missing)}] {symbol:12} ⊘ Not in master")
            failed += 1
            failed_symbols.append(symbol)
            continue
        else:
            sec_id = master[symbol]
            exchange_segment = "NSE_EQ"
            instrument = "EQUITY"

        success, message = fetch_stock_data(
            sec_id, symbol, args.timeframe, args.days_back, exchange_segment, instrument
        )

        if success:
            print(f"[{i:3d}/{len(missing)}] {symbol:12} ✅ {message}")
            successful += 1
        else:
            print(f"[{i:3d}/{len(missing)}] {symbol:12} ❌ {message}")
            failed += 1
            failed_symbols.append(symbol)

        if i < len(missing):
            time.sleep(0.1)

    print("\n" + "=" * 70)
    print(f"✅ Successful: {successful}/{len(missing)}")
    print(f"❌ Failed: {failed}/{len(missing)}")

    if failed_symbols:
        print("\n🔴 Failed symbols:")
        for sym in failed_symbols[:10]:
            print(f"   - {sym}")
        if len(failed_symbols) > 10:
            print(f"   ... and {len(failed_symbols) - 10} more")

    print(f"\n📁 Cache: {CACHE_DIR.absolute()}")
    print("=" * 70 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
