import pandas as pd
import pytest

from config import CACHE_DIR
from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.registry import make_strategy


def load_cache(sym):
    """
    Load cached data for a symbol.

    Tries multiple cache formats:
    1. Parquet file (sym.parquet)
    2. CSV file from Dhan historical cache (dhan_historical_SECURITY_ID.csv)

    For HDFC: HDFCBANK_NS maps to security_id 1333 in Dhan
    """
    # Try parquet first
    p = CACHE_DIR / f"{sym}.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        df.index = pd.to_datetime(df.index)
        return df

    # Special handling for HDFC Bank
    if sym == "HDFCBANK_NS":
        # HDFC Bank Security ID is 1333 in Dhan API
        csv_path = CACHE_DIR / "dhan_historical_1333.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index)
            return df

    # If we reach here, data is not available
    pytest.skip(f"Cache miss for {sym}")


def test_ema_cross_hdfc():
    df = load_cache("HDFCBANK_NS")
    strat = make_strategy("ema_crossover", "{}")
    cfg = BrokerConfig()
    eng = BacktestEngine(df, strat, cfg)
    trades, equity, signals = eng.run()
    # sanity checks
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)


def test_envelope_kd_hdfc():
    df = load_cache("HDFCBANK_NS")
    strat = make_strategy("ichimoku", "{}")
    cfg = BrokerConfig()
    eng = BacktestEngine(df, strat, cfg)
    trades, equity, signals = eng.run()
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)
