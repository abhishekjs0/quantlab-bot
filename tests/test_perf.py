import pandas as pd

from core.perf import (
    combine_equal_weight,
    compute_portfolio_trade_metrics,
    compute_trade_metrics_table,
)


def test_compute_trade_metrics_table_empty():
    res = compute_trade_metrics_table(pd.DataFrame(), pd.DataFrame(), bars_per_year=245)
    assert res["NumTrades"] == 0
    assert res["CAGR_pct"] == 0.0


def test_compute_trade_metrics_table_single_trade():
    # create a small daily df index
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    df = pd.DataFrame(index=idx)
    trades = pd.DataFrame(
        [
            {
                "entry_time": idx[0],
                "exit_time": idx[1],
                "entry_price": 100.0,
                "entry_qty": 1,
                "net_pnl": 10.0,
            }
        ]
    )
    out = compute_trade_metrics_table(df, trades, bars_per_year=245)
    assert out["NumTrades"] == 1
    assert out["AvgProfitPerTradePct"] > 0.0
    assert out["AvgBarsPerTrade"] > 0
    assert out["CAGR_pct"] > 0.0


def test_compute_portfolio_trade_metrics_simple():
    # two symbols with simple trades
    idx = pd.date_range("2025-01-01", periods=4, freq="D")
    df_a = pd.DataFrame(index=idx)
    df_b = pd.DataFrame(index=idx)
    trades_a = pd.DataFrame(
        [
            {
                "entry_time": idx[0],
                "exit_time": idx[1],
                "entry_price": 50.0,
                "entry_qty": 2,
                "net_pnl": 10.0,
            }
        ]
    )
    trades_b = pd.DataFrame(
        [
            {
                "entry_time": idx[1],
                "exit_time": idx[2],
                "entry_price": 200.0,
                "entry_qty": 1,
                "net_pnl": -5.0,
            }
        ]
    )
    dfs = {"A": df_a, "B": df_b}
    trades = {"A": trades_a, "B": trades_b}
    out = compute_portfolio_trade_metrics(dfs, trades, bars_per_year=245)
    assert out["NumTrades"] == 2
    # total net pnl = 5, total deployed = (50*2)+(200*1)=300 -> avg_profit_frac=5/300
    assert abs(out["AvgProfitPerTradePct"] / 100.0 - (5.0 / 300.0)) < 1e-6


def test_combine_equal_weight():
    # two simple equity series
    idx = pd.date_range("2025-01-01", periods=3, freq="D")
    e1 = pd.Series([100.0, 110.0, 121.0], index=idx)
    e2 = pd.Series([100.0, 105.0, 110.25], index=idx)
    df = combine_equal_weight({"A": e1, "B": e2}, initial_capital=100000.0)
    # first equity should equal initial_capital
    assert float(df["equity"].iloc[0]) == 100000.0
    # returns on day2 should be average of individual returns
    r1 = e1.pct_change().iloc[1]
    r2 = e2.pct_change().iloc[1]
    avg = (r1 + r2) / 2.0
    combined_r = df["equity"].pct_change().iloc[1]
    assert abs(combined_r - avg) < 1e-9
