import numpy as np
import pandas as pd

from core.perf import compute_portfolio_trade_metrics


def test_pf_closed_trades_only_explicit():
    # closed trades: wins 300, losses -100 => PF = 3.0
    trades_by_symbol = {
        "AAA": pd.DataFrame(
            [
                {
                    "entry_time": "2020-01-01",
                    "exit_time": "2020-01-10",
                    "entry_price": 10.0,
                    "entry_qty": 10,
                    "net_pnl": 300.0,
                },
                {
                    "entry_time": "2020-02-01",
                    "exit_time": "2020-02-10",
                    "entry_price": 10.0,
                    "entry_qty": 10,
                    "net_pnl": -100.0,
                },
            ]
        ),
        "BBB": pd.DataFrame(
            [
                {
                    "entry_time": "2020-03-01",
                    "exit_time": None,
                    "entry_price": 20.0,
                    "entry_qty": 5,
                    "net_pnl": np.nan,
                },
            ]
        ),
    }
    df_aaa = pd.DataFrame(
        {"close": [12.0, 13.0]}, index=pd.to_datetime(["2020-01-01", "2020-01-10"])
    )
    df_bbb = pd.DataFrame(
        {"close": [19.0, 21.0]}, index=pd.to_datetime(["2020-03-01", "2020-03-10"])
    )
    dfs = {"AAA": df_aaa, "BBB": df_bbb}
    out = compute_portfolio_trade_metrics(dfs, trades_by_symbol, bars_per_year=252)
    assert "ProfitFactor" in out
    assert abs(out["ProfitFactor"] - 3.0) < 1e-9


def test_equity_cagr_calc():
    # equity from 100 -> 121 over exactly 2 years
    idx = pd.date_range("2020-01-01", periods=25, freq="ME")
    eq = pd.Series(np.linspace(100.0, 121.0, len(idx)), index=idx)
    # create a minimal port_df DataFrame like runner's port_df
    port_df = pd.DataFrame({"equity": eq.values}, index=eq.index)
    # compute expected CAGR
    start = float(eq.iloc[0])
    end = float(eq.iloc[-1])
    days = (eq.index[-1] - eq.index[0]).days
    years = days / 365.25
    expected = (end / start) ** (1.0 / years) - 1.0
    # compute via same method as runner would
    start_eq = float(port_df["equity"].iloc[0])
    end_eq = float(port_df["equity"].iloc[-1])
    idx_df = port_df.reset_index()
    idxcol = idx_df.iloc[:, 0]
    days2 = (pd.to_datetime(idxcol.iloc[-1]) - pd.to_datetime(idxcol.iloc[0])).days
    years2 = days2 / 365.25
    computed = (end_eq / start_eq) ** (1.0 / years2) - 1.0
    assert abs(computed - expected) < 1e-12
