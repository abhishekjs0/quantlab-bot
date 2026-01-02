#!/usr/bin/env python3
"""
Fetch Daily OHLCV data for ETFs from Dhan API
=============================================
Fetches historical daily data for all ETFs listed in input CSV.
"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
DHAN_BASE_URL = "https://api.dhan.co/v2"
DHAN_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJkaGFuIiwicGFydG5lcklkIjoiIiwiZXhwIjoxNzY3NDI0NTgyLCJpYXQiOjE3NjczMzgxODIsInRva2VuQ29uc3VtZXJUeXBlIjoiU0VMRiIsIndlYmhvb2tVcmwiOiIiLCJkaGFuQ2xpZW50SWQiOiIxMTA4MzUxNjQ4In0.ONvXG5h3E1ka12NAOGEyoP7UInZww3Z5gFyctSqWaDPdtvbfGYpg04GfcBrKdnzVPA8WvBpgAc8RcKxG34n6gA"

CACHE_DIR = Path("data/cache/dhan/daily")
MASTER_FILE = Path("data/dhan-scrip-master-detailed.csv")

# ETF symbols from the user's file
ETF_SYMBOLS = [
    "NIFTYBETA", "NEXT50BETA", "ALPHA", "IT", "LOWVOL1", "MIDCAP", "GILT5BETA",
    "GILT10BETA", "MIDCAPBETA", "MNC", "CONS", "VAL30IETF", "MOMIDMTM", "ESG",
    "MID150CASE", "BSLNIFTY", "ELIQUID", "MULTICAP", "NEXT50IETF", "MOMNC",
    "SENSEXADD", "ESENSEX", "TECH", "MONQ50", "BANKADD", "LICNETFGSC",
    "MIDCAPIETF", "AUTOBEES", "TATAGOLD", "GOLDBEES", "GROWWNET", "AXSENSEX",
    "METALIETF", "MSCIADD", "TNIDETF", "ALPHAETF", "SBIETFQLTY", "AONENIFTY",
    "TOP10ADD", "NV20IETF", "METAL", "MOLOWVOL", "LOWVOLIETF", "MONIFTY500",
    "HEALTHIETF", "UNIONGOLD", "SETFNN50", "LIQUIDADD", "ALPL30IETF",
    "SILVERBEES", "MOSILVER", "HDFCQUAL", "GSEC10ABSL", "MAFANG", "GILT5YBEES",
    "MOINFRA", "HDFCNEXT50", "MONEXT50", "NIFTYCASE", "SBIETFCON", "GOLDBND",
    "ABSLLIQUID", "EVIETF", "LIQUIDETF", "SETFNIFBK", "TOP15IETF", "SILVERBND",
    "CONSUMIETF", "HDFCGROWTH", "CPSEETF", "SBINEQWETF", "GSEC10YEAR", "HDFCGOLD",
    "MOHEALTH", "BANKIETF", "MOMGF", "MOIPO", "ITETF", "SML100CASE", "GOLDIETF",
    "TOP100CASE", "QUAL30IETF", "GROWWNXT50", "GOLDADD", "HDFCPVTBAN",
    "MIDQ50ADD", "MOGOLD", "BANKPSU", "CONSUMER", "GSEC10IETF", "MOVALUE",
    "HDFCNIFTY", "AXISTECETF", "INTERNET", "SELECTIPO", "EBANKNIFTY",
    "SILVERCASE", "GROWWGOLD", "PSUBNKBEES", "LICNETFN50", "EMULTIMQ",
    "NIFTYQLITY", "GROWWPOWER", "GROWWLOVOL", "GSEC5IETF", "SNXT30BEES",
    "SBIETFPB", "GROWWMOM50", "ABSLNN50ET", "NIF100BEES", "SMALL250",
    "MIDSELIETF", "LOWVOL", "LIQUID", "FINIETF", "LICMFGOLD", "NIFTYADD",
    "LIQUIDSHRI", "FMCGIETF", "CONSUMBEES", "CHOICEGOLD", "LIQUIDPLUS",
    "HDFCVALUE", "SILVERADD", "INFRAIETF", "HNGSNGBEES", "MANUFGBEES",
    "ABSLBANETF", "QGOLDHALF", "GOLD360", "MOGSEC", "MOPSE", "GROWWLIQID",
    "INFRABEES"
]

MAX_RETRIES = 3
BASE_WAIT_TIME = 0.5
DAILY_DATA_CUTOFF = datetime(2015, 11, 9)


def get_headers():
    """Get request headers."""
    return {
        "Content-Type": "application/json",
        "access-token": DHAN_ACCESS_TOKEN,
    }


def load_etf_mapping():
    """Load ETF security IDs from master file."""
    if not MASTER_FILE.exists():
        print(f"❌ Master file not found: {MASTER_FILE}")
        return {}

    try:
        df = pd.read_csv(MASTER_FILE, low_memory=False)
        # Filter for NSE equity (ETFs are under NSE equity segment)
        nse_eq = df[(df['SEM_EXM_EXCH_ID'] == 'NSE') & (df['SEM_SEGMENT'] == 'E')]
        
        mapping = {}
        for _, row in nse_eq.iterrows():
            symbol = row["SEM_TRADING_SYMBOL"]
            if symbol in ETF_SYMBOLS:
                secid = int(row["SEM_SMST_SECURITY_ID"])
                mapping[symbol] = secid
        
        print(f"📊 Found {len(mapping)} ETFs in master file out of {len(ETF_SYMBOLS)} requested")
        return mapping
    except Exception as e:
        print(f"❌ Failed to load master data: {e}")
        return {}


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
                print(f"❌ Unauthorized - check token")
                return None

            if response.status_code == 429:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                print(f"⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                time.sleep(wait)

        except (requests.Timeout, Exception) as e:
            if attempt < MAX_RETRIES:
                wait = min(BASE_WAIT_TIME * (2 ** (attempt - 1)), 8)
                time.sleep(wait)

    return None


def fetch_daily_data(sec_id, symbol, start_date, end_date):
    """Fetch daily candles for an ETF."""
    payload = {
        "securityId": str(sec_id),
        "exchangeSegment": "NSE_EQ",
        "instrument": "EQUITY",  # ETFs use EQUITY instrument type in Dhan
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
        df = pd.DataFrame({
            "time": data["timestamp"],
            "open": data["open"],
            "high": data["high"],
            "low": data["low"],
            "close": data["close"],
            "volume": data["volume"],
        })

        if df.empty:
            return None

        # Convert Unix epoch to IST
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df["time"] = df["time"].dt.tz_convert("Asia/Kolkata")
        return df.sort_values("time").reset_index(drop=True)

    except Exception as e:
        print(f"❌ Error parsing {symbol}: {e}")
        return None


def save_candles(df, sec_id, symbol):
    """Save candles to CSV."""
    if df is None or df.empty:
        return False

    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        output_file = CACHE_DIR / f"dhan_{sec_id}_{symbol}_1d.csv"

        df_save = df[["time", "open", "high", "low", "close", "volume"]].copy()
        df_save["time"] = pd.to_datetime(df_save["time"])

        # Convert IST to tz-naive for storage
        if df_save["time"].dt.tz is not None:
            df_save["time"] = df_save["time"].dt.tz_localize(None)

        df_save.set_index("time").to_csv(output_file)
        return True

    except Exception as e:
        print(f"❌ Error saving {symbol}: {e}")
        return False


def main():
    print("=" * 60)
    print("ETF Daily Data Fetcher - Dhan API")
    print("=" * 60)
    
    # Load ETF mapping
    etf_mapping = load_etf_mapping()
    
    if not etf_mapping:
        print("❌ No ETF mappings found. Check master file.")
        return
    
    # Find missing symbols
    missing = set(ETF_SYMBOLS) - set(etf_mapping.keys())
    if missing:
        print(f"\n⚠️ {len(missing)} symbols not found in master:")
        for s in sorted(missing):
            print(f"   - {s}")
    
    # Set date range
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    start_date = DAILY_DATA_CUTOFF
    
    print(f"\n📅 Date range: {start_date.date()} to {end_date.date()}")
    print(f"📂 Cache directory: {CACHE_DIR}")
    
    # Fetch data for each ETF
    success_count = 0
    fail_count = 0
    
    print(f"\n🚀 Fetching {len(etf_mapping)} ETFs...\n")
    
    for i, (symbol, sec_id) in enumerate(sorted(etf_mapping.items()), 1):
        print(f"[{i}/{len(etf_mapping)}] {symbol} (ID: {sec_id})...", end=" ")
        
        df = fetch_daily_data(sec_id, symbol, start_date, end_date)
        
        if df is not None and not df.empty:
            if save_candles(df, sec_id, symbol):
                print(f"✅ {len(df)} candles")
                success_count += 1
            else:
                print("❌ Save failed")
                fail_count += 1
        else:
            print("❌ No data")
            fail_count += 1
        
        # Rate limiting
        time.sleep(0.3)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Successfully fetched: {success_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"⚠️ Not in master: {len(missing)}")
    print(f"\n📂 Data saved to: {CACHE_DIR}")


if __name__ == "__main__":
    main()
