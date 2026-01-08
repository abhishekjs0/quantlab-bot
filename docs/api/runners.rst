Runners
=======

Runners are the execution scripts that orchestrate backtesting across
multiple symbols (baskets).

Fast Run Basket
---------------

Optimized runner using multiprocessing for parallel symbol processing.
Best for quick iteration during strategy development.

.. automodule:: runners.fast_run_basket
   :members:
   :undoc-members:
   :show-inheritance:

Standard Run Basket
-------------------

Full-featured runner with comprehensive reporting, performance windows,
and detailed trade analysis.

.. automodule:: runners.standard_run_basket
   :members:
   :undoc-members:
   :show-inheritance:

Max Trades
----------

Runner optimized for strategies with many trades, includes trade-level
analysis and position sizing validation.

.. automodule:: runners.max_trades
   :members:
   :undoc-members:
   :show-inheritance:

Usage
-----

All runners follow a similar pattern::

    from runners.fast_run_basket import run_basket_backtest
    from strategies.tema_lsma_crossover import TemaLsmaCrossover

    # Run backtest on NIFTY 50 basket
    results = run_basket_backtest(
        strategy_class=TemaLsmaCrossover,
        basket="nifty50",
        start_date="2015-01-01",
        end_date="2025-01-01",
    )

Runner Output
^^^^^^^^^^^^^

Runners produce:

1. **Console Summary**: Win rate, profit factor, Sharpe ratio
2. **Trade CSV**: Detailed trade log with entry/exit prices
3. **Equity Curve**: Portfolio value over time
4. **Performance Windows**: 1Y, 3Y, 5Y, MAX metrics
5. **Report Directory**: HTML/PDF reports (if enabled)
