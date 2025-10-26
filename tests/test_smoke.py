import pandas as pd
import pytest

from config import CACHE_DIR
from core.config import BrokerConfig
from core.engine import BacktestEngine
from core.registry import make_strategy


def load_cache(sym):
    p = CACHE_DIR / f"{sym}.parquet"
    if not p.exists():
        pytest.skip(f"Cache miss for {sym}")
    df = pd.read_parquet(p)
    df.index = pd.to_datetime(df.index)
    return df


def test_ema_cross_hdfc():
    df = load_cache("HDFCBANK_NS")
    strat = make_strategy("ema_cross", "{}")
    cfg = BrokerConfig()
    eng = BacktestEngine(df, strat, cfg)
    trades, equity, signals = eng.run()
    # sanity checks
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)


def test_envelope_kd_hdfc():
    df = load_cache("HDFCBANK_NS")
    strat = make_strategy("envelope_kd", "{}")
    cfg = BrokerConfig()
    eng = BacktestEngine(df, strat, cfg)
    trades, equity, signals = eng.run()
    assert isinstance(trades, pd.DataFrame)
    assert isinstance(equity, pd.DataFrame)
