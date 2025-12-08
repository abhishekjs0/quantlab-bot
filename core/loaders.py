"""Data loaders for OHLC and instrument data from cache and CSV files."""

from __future__ import annotations

import os

import pandas as pd

from config import CACHE_DIR, DATA_DIR


def _guess_cache_filename(sym: str, cache_dir: str, interval: str = "1d") -> str:
    # Normalize symbol to match cache filenames
    base = sym.replace("NSE:", "").replace(":", "_").replace("/", "_")

    # Try new dhan format: dhan_<SECID>_<SYMBOL>_<TIMEFRAME>.csv
    # First, try to find any dhan file matching the symbol and timeframe
    import glob

    pattern = os.path.join(cache_dir, f"dhan_*_{base}_{interval}.csv")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]

    # Fallback to old parquet formats
    # common cache naming used earlier: <SYMBOL>_NS.parquet
    cand = os.path.join(cache_dir, f"{base}_NS.parquet")
    if os.path.exists(cand):
        return cand
    # fallback: try raw symbol name
    cand2 = os.path.join(cache_dir, f"{base}.parquet")
    if os.path.exists(cand2):
        return cand2
    # last resort: return new dhan format path (caller will check existence)
    return os.path.join(cache_dir, f"dhan_*_{base}_{interval}.csv")


def load_many_india(
    symbols: list[str],
    interval: str = "1d",
    period: str = "max",
    cache: bool = True,
    cache_dir: str | None = None,
    use_cache_only: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load OHLC data for a list of Indian symbols from local cache parquet files.

    This is a small, conservative loader used for cache-only smoke runs. It looks
    for files in `cache_dir` named like `<SYMBOL>_NS.parquet` or `<SYMBOL>.parquet`.

    Returns a dict mapping the original symbol string to a pandas DataFrame with a DatetimeIndex.

    Raises FileNotFoundError if `use_cache_only` is True and a symbol's cache file is missing.
    """
    if cache_dir is None:
        cache_dir = str(CACHE_DIR)
    out = {}
    os.makedirs(cache_dir, exist_ok=True)
    for sym in symbols:
        path = _guess_cache_filename(sym, cache_dir, interval)
        if not os.path.exists(path):
            # Try to find a Dhan-historical CSV we may have already saved under data/dhan_historical_<SECID>.csv
            # First attempt: map symbol to SECURITY_ID using instrument parquet or CSV
            secid = None
            # try parquet in cache
            pq_path = os.path.join(cache_dir, "api-scrip-master-detailed.parquet")
            try:
                if os.path.exists(pq_path):
                    import pyarrow.parquet as pq

                    tbl = pq.read_table(pq_path)
                    df_inst = tbl.to_pandas()
                    base_name = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                    row = df_inst[
                        (df_inst["SYMBOL_NAME"] == base_name)
                        | (df_inst["UNDERLYING_SYMBOL"] == base_name)
                    ]
                    if not row.empty:
                        # If there are multiple matching rows, prefer a SECURITY_ID
                        # for which we already have a data/dhan_historical_<SECID>.csv file.
                        secid = None
                        try:
                            cand_ids = [int(x) for x in row["SECURITY_ID"].tolist()]
                        except Exception:
                            cand_ids = [int(row.iloc[0]["SECURITY_ID"])]
                        for cid in cand_ids:
                            # Check both data/ and cache/ directories
                            alt_data = DATA_DIR / f"dhan_historical_{cid}.csv"
                            alt_cache = os.path.join(
                                cache_dir, f"dhan_historical_{cid}.csv"
                            )
                            if alt_data.exists():
                                secid = cid
                                path = str(alt_data)
                                break
                            elif os.path.exists(alt_cache):
                                secid = cid
                                path = alt_cache
                                break
                        if secid is None:
                            secid = int(row.iloc[0]["SECURITY_ID"])
            except Exception:
                secid = None

            # fallback: try data CSV of instrument list
            if secid is None:
                csv_inst = DATA_DIR / "api-scrip-master-detailed.csv"
                try:
                    if csv_inst.exists():
                        df_inst = pd.read_csv(csv_inst)
                        base_name = (
                            sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                        )
                        row = df_inst[
                            (df_inst["SYMBOL_NAME"] == base_name)
                            | (df_inst["UNDERLYING_SYMBOL"] == base_name)
                        ]
                        if not row.empty:
                            secid = None
                            try:
                                cand_ids = [int(x) for x in row["SECURITY_ID"].tolist()]
                            except Exception:
                                cand_ids = [int(row.iloc[0]["SECURITY_ID"])]
                            for cid in cand_ids:
                                # Check both data/ and cache/ directories
                                alt_data = DATA_DIR / f"dhan_historical_{cid}.csv"
                                alt_cache = os.path.join(
                                    cache_dir, f"dhan_historical_{cid}.csv"
                                )
                                if alt_data.exists():
                                    secid = cid
                                    path = str(alt_data)
                                    break
                                elif os.path.exists(alt_cache):
                                    secid = cid
                                    path = alt_cache
                                    break
                            if secid is None:
                                secid = int(row.iloc[0]["SECURITY_ID"])
                except Exception:
                    secid = None

            if secid is not None:
                # Check both data/ and cache/ directories for Dhan files
                alt_data = DATA_DIR / f"dhan_historical_{secid}.csv"
                alt_cache = os.path.join(cache_dir, f"dhan_historical_{secid}.csv")
                if alt_data.exists():
                    path = str(alt_data)
                elif os.path.exists(alt_cache):
                    path = alt_cache

            if not os.path.exists(path):
                if use_cache_only:
                    raise FileNotFoundError(
                        f"Cache missing for {sym}: looked for {path}"
                    )
                else:
                    raise FileNotFoundError(
                        f"Cache missing for {sym}: {path}. Enable caching or provide data/loaders implementation."
                    )
        try:
            if str(path).lower().endswith(".csv"):
                # Try to read CSV with different date column formats
                try:
                    # Try with 'time' column (Dhan format)
                    df = pd.read_csv(path, parse_dates=["time"], index_col="time")
                    # Normalize column names to lowercase
                    df.columns = df.columns.str.lower()
                except (ValueError, KeyError):
                    try:
                        # Try with 'Date' column (old yfinance format)
                        df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
                        # Normalize column names to lowercase
                        df.columns = df.columns.str.lower()
                    except (ValueError, KeyError):
                        # Try with 'date' column (new format)
                        df = pd.read_csv(path, parse_dates=["date"], index_col="date")
            else:
                df = pd.read_parquet(path)

            if not isinstance(df.index, pd.DatetimeIndex):
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df = df.set_index("date")
                else:
                    df.index = pd.to_datetime(df.index)

            # CRITICAL: Normalize timezone-aware datetimes to tz-naive (local time)
            # This fixes compatibility issues between UTC (1d) and IST (intraday) cache files
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            # Check for corrupted timestamps (1970-01-01 epoch bug in some Dhan CSV files)
            if not df.empty:
                first_date = df.index[0]
                last_date = df.index[-1]
                # If all dates are in 1970 (Unix epoch), the data is corrupted
                if first_date.year == 1970 and last_date.year == 1970:
                    print(
                        f"ERROR: Corrupted timestamps in {path}. Skipping symbol {sym}."
                    )
                    continue  # Skip this symbol and continue with others

            # ensure standard columns exist
            for c in ["open", "high", "low", "close", "volume"]:
                if c not in df.columns:
                    df[c] = pd.NA

            out[sym] = df.sort_index()
        except Exception as e:
            raise RuntimeError(f"Failed to read cached data for {sym} from {path}: {e}")
    return out


# Backwards-compatible small helpers used elsewhere in the repo
def load_ohlc_yf(
    symbol: str, interval: str = "1d", period: str = "max", use_cache_only: bool = False
):
    # alias to load_many_india for single symbol
    return load_many_india(
        [symbol],
        interval=interval,
        period=period,
        cache=True,
        cache_dir=None,  # Will use CACHE_DIR
        use_cache_only=use_cache_only,
    )[symbol]


def load_ohlc_from_csv(path: str):
    df = pd.read_csv(path, parse_dates=[0], index_col=0)
    return df


def load_nifty_data():
    """Load NIFTYBEES ETF data for market regime detection."""
    niftybees_cache_path = CACHE_DIR / "dhan_historical_10576.csv"
    if niftybees_cache_path.exists():
        df = pd.read_csv(niftybees_cache_path, parse_dates=["date"], index_col="date")
        return df.sort_index()
    else:
        raise FileNotFoundError(
            f"NIFTYBEES data not found at {niftybees_cache_path}. Please fetch NIFTYBEES data first."
        )


def load_india_vix(interval: str = "1d", cache_dir: str | None = None) -> pd.DataFrame:
    """Load India VIX volatility index data.
    
    India VIX SECURITY_ID: 21
    Data available from 2015-11-09 onwards.
    
    Args:
        interval: Timeframe ("1d" for daily, "1" for 1-min, etc.)
        cache_dir: Directory to search for data files. Defaults to CACHE_DIR.
        
    Returns:
        DataFrame with India VIX OHLC data
        
    Raises:
        FileNotFoundError: If cache file not found
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    else:
        cache_dir = os.path.abspath(cache_dir)
        
    timeframe_suffix = interval if interval != "daily" else "1d"
    
    # Try new format first (INDIA_VIX), then old format (INDIAVIX) for backward compat
    cache_path = os.path.join(cache_dir, f"dhan_21_INDIA_VIX_{timeframe_suffix}.csv")
    if not os.path.exists(cache_path):
        cache_path = os.path.join(cache_dir, f"dhan_21_INDIAVIX_{timeframe_suffix}.csv")
    
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"India VIX data not found.\n"
            f"Expected: {cache_dir}/dhan_21_INDIA_VIX_{timeframe_suffix}.csv"
        )
    
    # CSV may have 'time' or 'date' column depending on version
    df = pd.read_csv(cache_path)
    if 'time' in df.columns:
        df['date'] = pd.to_datetime(df['time'])
        df = df.set_index('date').drop(columns=['time'], errors='ignore')
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
    df.columns = df.columns.str.lower()
    return df.sort_index()


def load_nifty50(interval: str = "1d", cache_dir: str | None = None) -> pd.DataFrame:
    """Load NIFTY 50 index data.
    
    NIFTY 50 SECURITY_ID: 13
    Data available from 2015-11-09 onwards.
    
    Args:
        interval: Timeframe ("1d" for daily, "1" for 1-min, etc.)
        cache_dir: Directory to search for data files. Defaults to CACHE_DIR.
        
    Returns:
        DataFrame with NIFTY 50 OHLC data
        
    Raises:
        FileNotFoundError: If cache file not found
    """
    if cache_dir is None:
        cache_dir = CACHE_DIR
    else:
        cache_dir = os.path.abspath(cache_dir)
        
    timeframe_suffix = interval if interval != "daily" else "1d"
    
    cache_path = os.path.join(cache_dir, f"dhan_13_NIFTY50_{timeframe_suffix}.csv")
    
    if not os.path.exists(cache_path):
        raise FileNotFoundError(
            f"NIFTY 50 data not found.\n"
            f"Expected: {cache_path}"
        )
    
    # CSV has 'time' column, parse as date index
    df = pd.read_csv(cache_path, parse_dates=["time"], index_col="time")
    df.index.name = "date"  # Normalize index name
    df.columns = df.columns.str.lower()
    return df.sort_index()


def load_market_index(interval: str = "1d", cache_dir: str | None = None) -> pd.DataFrame:
    """Load NIFTY50 market index data for regime filters.
    
    Uses NIFTY50 which has complete data from 2015-11-09 onwards.
    
    NIFTY 50 SECURITY_ID: 13
    
    Args:
        interval: Timeframe ("1d" for daily, "1" for 1-min, etc.)
        cache_dir: Directory to search for data files. Defaults to CACHE_DIR.
        
    Returns:
        DataFrame with NIFTY 50 OHLC data (used as market regime proxy)
        
    Raises:
        FileNotFoundError: If cache file not found
    """
    return load_nifty50(interval=interval, cache_dir=cache_dir)


# Backward compatibility alias
load_nifty200 = load_market_index


def load_ohlc_dhan_multiframe(
    symbol: str,
    security_id: int | str | None = None,
    timeframe: str = "1d",
    cache_dir: str | None = None,
) -> pd.DataFrame:
    """Load OHLCV data from Dhan CSV files with support for multiple timeframes.

    Supports timeframes:
    - "1d" or "daily": Daily candles
    - "75m": 75-minute candles
    - "125m": 125-minute candles

    Args:
        symbol: Stock symbol (e.g., "RELIANCE", "SBIN")
        security_id: Dhan SECURITY_ID. If None, will be resolved from symbol.
        timeframe: Timeframe to load. Default "1d".
        cache_dir: Directory with CSV files. Defaults to CACHE_DIR.

    Returns:
        DataFrame with DatetimeIndex and OHLCV columns

    Raises:
        FileNotFoundError: If CSV file not found
        ValueError: If symbol/security_id cannot be resolved
    """
    if cache_dir is None:
        cache_dir = str(CACHE_DIR)

    # Normalize timeframe
    if timeframe in ["daily", "1d"]:
        timeframe = "1d"
    elif timeframe not in ["75m", "125m"]:
        raise ValueError(
            f"Unsupported timeframe '{timeframe}'. Use '1d', '75m', or '125m'"
        )

    # Resolve security_id if not provided
    if security_id is None:
        security_id = _symbol_to_security_id(symbol, cache_dir)
        if security_id is None:
            raise ValueError(
                f"Cannot resolve symbol '{symbol}' to SECURITY_ID. "
                "Provide security_id explicitly or check instrument master."
            )

    security_id = str(int(security_id))  # Ensure it's a string for filename

    # Construct filename: dhan_<secid>_<symbol>_<timeframe>.csv
    csv_path = os.path.join(cache_dir, f"dhan_{security_id}_{symbol}_{timeframe}.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Dhan data not found for {symbol} ({security_id}) at {timeframe}. "
            f"Expected: {csv_path}"
        )

    # Load CSV
    df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower()

    # Ensure required OHLCV columns exist
    required_cols = ["open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Missing required column '{col}' in {symbol} {timeframe} data. "
                f"Found: {list(df.columns)}"
            )

    return df[required_cols].sort_index()


def load_many_dhan_multiframe(
    symbols: list[str],
    security_ids: dict[str, int | str] | None = None,
    timeframe: str = "1d",
    cache_dir: str | None = None,
) -> dict[str, pd.DataFrame]:
    """Load multi-timeframe Dhan data for multiple symbols.

    Args:
        symbols: List of stock symbols
        security_ids: Optional dict mapping symbol -> security_id
        timeframe: Timeframe to load ("1d", "75m", "125m")
        cache_dir: Directory with CSV files

    Returns:
        Dict mapping symbol -> DataFrame
    """
    if cache_dir is None:
        cache_dir = str(CACHE_DIR)

    if security_ids is None:
        security_ids = {}

    out = {}
    for symbol in symbols:
        try:
            sec_id = security_ids.get(symbol)
            df = load_ohlc_dhan_multiframe(
                symbol, security_id=sec_id, timeframe=timeframe, cache_dir=cache_dir
            )
            out[symbol] = df
        except (FileNotFoundError, ValueError) as e:
            print(f"WARNING: Failed to load {symbol}: {e}")
            continue

    return out


def load_minute_data(
    symbol_or_secid: str | int,
    cache_dir: str | None = None,
) -> pd.DataFrame:
    """Load minute-wise OHLCV data from Dhan CSV files.

    Dhan API provides historical minute candles in CSV format:
    dhan_historical_<SECURITY_ID>.csv

    Args:
        symbol_or_secid: Either a symbol (e.g., "SBIN") or Dhan SECURITY_ID (e.g., 1023).
                         If symbol provided, converts to SECURITY_ID using instrument master.
        cache_dir: Directory to search for CSV files. Defaults to CACHE_DIR.

    Returns:
        DataFrame with DatetimeIndex and columns: open, high, low, close, volume

    Raises:
        FileNotFoundError: If CSV not found in cache
        ValueError: If symbol cannot be resolved to SECURITY_ID
    """
    if cache_dir is None:
        cache_dir = str(CACHE_DIR)

    # If input is symbol string, resolve to SECURITY_ID first
    if isinstance(symbol_or_secid, str):
        secid = _symbol_to_security_id(symbol_or_secid)
        if secid is None:
            raise ValueError(
                f"Cannot resolve symbol '{symbol_or_secid}' to SECURITY_ID. "
                "Check instrument master or provide SECURITY_ID directly."
            )
    else:
        secid = int(symbol_or_secid)

    # Look for minute data CSV
    csv_path = os.path.join(cache_dir, f"dhan_historical_{secid}.csv")
    if not os.path.exists(csv_path):
        # Also check data directory
        csv_path = DATA_DIR / f"dhan_historical_{secid}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Minute data not found for SECURITY_ID {secid}. "
                f"Expected: {cache_dir}/dhan_historical_{secid}.csv"
            )
        csv_path = str(csv_path)

    # Load minute data
    try:
        df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
    except KeyError:
        # Try alternate date column names
        df = pd.read_csv(csv_path)
        date_cols = [c for c in df.columns if "date" in c.lower()]
        if not date_cols:
            raise ValueError(
                f"No date column found in {csv_path}. Expected 'date' column."
            )
        df = df.set_index(
            df.columns[
                [
                    df.columns.str.lower().tolist().index(d)
                    for d in [c.lower() for c in date_cols]
                ][0]
            ]
        )
        df.index = pd.to_datetime(df.index)

    # Normalize column names to lowercase
    df.columns = df.columns.str.lower()

    # Ensure required OHLCV columns exist
    required_cols = ["open", "high", "low", "close", "volume"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(
                f"Missing required column '{col}' in minute data. "
                f"Found columns: {list(df.columns)}"
            )

    # Return sorted by date
    return df[required_cols].sort_index()


def _symbol_to_security_id(symbol: str, cache_dir: str | None = None) -> int | None:
    """Resolve a symbol to its Dhan SECURITY_ID using instrument master.

    Returns SECURITY_ID if found, None otherwise.
    """
    if cache_dir is None:
        cache_dir = str(CACHE_DIR)

    # Normalize symbol
    base_name = symbol.replace("NSE:", "").replace(".NS", "").split(".")[0]

    # Try parquet first
    pq_path = os.path.join(cache_dir, "api-scrip-master-detailed.parquet")
    if os.path.exists(pq_path):
        try:
            import pyarrow.parquet as pq

            tbl = pq.read_table(pq_path)
            df_inst = tbl.to_pandas()
            row = df_inst[
                (df_inst["SYMBOL_NAME"] == base_name)
                | (df_inst["UNDERLYING_SYMBOL"] == base_name)
            ]
            if not row.empty:
                return int(row.iloc[0]["SECURITY_ID"])
        except Exception:
            pass

    # Try CSV
    csv_path = DATA_DIR / "api-scrip-master-detailed.csv"
    if csv_path.exists():
        try:
            df_inst = pd.read_csv(csv_path)
            row = df_inst[
                (df_inst["SYMBOL_NAME"] == base_name)
                | (df_inst["UNDERLYING_SYMBOL"] == base_name)
            ]
            if not row.empty:
                return int(row.iloc[0]["SECURITY_ID"])
        except Exception:
            pass

    return None
