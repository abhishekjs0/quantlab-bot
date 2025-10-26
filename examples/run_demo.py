"""Demo script showing basic backtesting workflow using Donchian Channel strategy."""

from strategies.donchian import DonchianStrategy

from core.config import BrokerConfig
from core.engine import BacktestEngine
from data.loaders import load_ohlc_yf
from viz.tv_plot import plot_tv_donchian  # <- add this import

if __name__ == "__main__":
    df = load_ohlc_yf("AAPL", interval="1d", period="3y")
    strat = DonchianStrategy(length=20, exit_option=1)
    cfg = BrokerConfig()
    trades, equity, signals = BacktestEngine(df, strat, cfg).run()
    print("Trades sample:\n", trades.head())
    print("\nEquity tail:\n", equity.tail())
    print("\nSignals tail:\n", signals.tail())

    # Show TV-style chart for last 12 months
    plot_tv_donchian(df, trades, length=20, months=12, title="AAPL - Donchian TV-style")
