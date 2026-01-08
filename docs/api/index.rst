QuantLab API Documentation
==========================

Welcome to QuantLab's API documentation. This documentation is auto-generated
from the source code docstrings.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   core
   strategies
   utils
   runners

Quick Start
-----------

QuantLab is a quantitative trading backtesting framework for Indian markets.

Installation::

    pip install -e ".[dev]"

Basic Usage::

    from core.engine import BacktestEngine
    from core.config import BrokerConfig
    from core.strategy import Strategy
    from utils.indicators import SMA

    class MyStrategy(Strategy):
        def prepare(self, df):
            self.data = df
            self.sma20 = self.I(SMA, df.close, 20, name="SMA20")
            return super().prepare(df)

        def should_enter(self, i):
            return self.data.close.iloc[i-1] > self.sma20[i-1]

        def should_exit(self, i):
            return self.data.close.iloc[i-1] < self.sma20[i-1]

    # Run backtest
    strategy = MyStrategy()
    cfg = BrokerConfig()
    engine = BacktestEngine(df=data, strategy=strategy, cfg=cfg, symbol="HDFCBANK_NS")
    result = engine.run()


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
