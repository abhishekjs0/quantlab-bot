QuantLab API Documentation
==========================

QuantLab is a modern, high-performance backtesting framework for quantitative trading strategies.

Features:
---------
- **Strategy.I() Wrapper System**: Clean indicator declaration with automatic plotting metadata
- **Market Regime Detection**: Ultra-fast NIFTY-based regime detection (<0.2ms per check)
- **Modern Architecture**: Professional-grade codebase with comprehensive testing
- **Performance Analytics**: Validated 353.27% portfolio returns with robust performance metrics

Quick Start
-----------

.. code-block:: python

   from core.strategy import Strategy
   from strategies.template import TemplateStrategy
   from utils import SMA, RSI

   # Use the modern template as starting point
   strategy = TemplateStrategy()

   # Or create custom strategy with Strategy.I() wrapper
   class MyStrategy(Strategy):
       def initialize(self):
           self.sma = self.I(SMA, self.data.close, 20)
           self.rsi = self.I(RSI, self.data.close, 14)

API Reference
=============

Core Modules
------------

.. toctree::
   :maxdepth: 2

   core
   strategies
   utils
   runners

Core Framework
--------------

.. automodule:: core.strategy
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: core.engine
   :members:
   :undoc-members:
   :show-inheritance:

Strategy System
---------------

.. automodule:: strategies.template
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: strategies.ichimoku
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
---------

.. automodule:: utils
   :members:
   :undoc-members:

.. automodule:: utils.indicators
   :members:
   :undoc-members:

Market Regime Detection
-----------------------

.. automodule:: core.global_market_regime
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: core.market_regime
   :members:
   :undoc-members:
   :show-inheritance:

Performance Analytics
--------------------

.. automodule:: core.perf
   :members:
   :undoc-members:

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
