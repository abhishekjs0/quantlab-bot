"""Data loaders for OHLC and instrument data from cache and CSV files."""

import os

import pandas as pd

from config import CACHE_DIR, DATA_DIR


def _guess_cache_filename(sym: str, cache_dir: str) -> str:
    # Normalize symbol to match cache filenames used previously: replace ':' and '.' with '' and append _NS.parquet
    base = sym.replace("NSE:", "").replace(":", "_").replace("/", "_")
    # common cache naming used earlier: <SYMBOL>_NS.parquet
    cand = os.path.join(cache_dir, f"{base}_NS.parquet")
    if os.path.exists(cand):
        return cand
    # fallback: try raw symbol name
    cand2 = os.path.join(cache_dir, f"{base}.parquet")
    if os.path.exists(cand2):
        return cand2
    # last resort: return cand (caller will check existence)
    return cand


def load_many_india(
    symbols: list[str],
    interval: str = "1d",
    period: str = "max",
    cache: bool = True,
    cache_dir: str = None,
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
        path = _guess_cache_filename(sym, cache_dir)
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
                # Try yfinance fallback before giving up
                base_name = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                yf_data_path = DATA_DIR / f"yfinance_{base_name}.csv"
                yf_cache_path = os.path.join(cache_dir, f"yfinance_{base_name}.csv")
                if yf_data_path.exists():
                    path = str(yf_data_path)
                elif os.path.exists(yf_cache_path):
                    path = yf_cache_path
                elif use_cache_only:
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

            # Check for corrupted timestamps (1970-01-01 epoch bug in some Dhan CSV files)
            if not df.empty:
                first_date = df.index[0]
                last_date = df.index[-1]
                # If all dates are in 1970 (Unix epoch), the data is corrupted
                if first_date.year == 1970 and last_date.year == 1970:
                    # Try to find yfinance data as fallback
                    base_name = sym.replace("NSE:", "").replace(".NS", "").split(".")[0]
                    yf_path = DATA_DIR / f"yfinance_{base_name}.csv"
                    if yf_path.exists():
                        print(
                            f"WARNING: Corrupted timestamps in {path}, falling back to {yf_path}"
                        )
                        df = pd.read_csv(
                            yf_path, parse_dates=["date"], index_col="date"
                        )
                        if not isinstance(df.index, pd.DatetimeIndex):
                            if "date" in df.columns:
                                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                                df = df.set_index("date")
                            else:
                                df.index = pd.to_datetime(df.index)
                    else:
                        print(
                            f"WARNING: Corrupted timestamps in {path}. No yfinance fallback available for {sym}. Skipping."
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
