Strategies
==========

QuantLab includes several built-in trading strategies for different market conditions.

All strategies inherit from :class:`core.strategy.Strategy` and implement:

- ``prepare(df)``: Initialize indicators using ``self.I()``
- ``should_enter(i)``: Return True when entry conditions are met
- ``should_exit(i)``: Return True when exit conditions are met

Trend Following
---------------

TEMA-LSMA Crossover
^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.tema_lsma_crossover
   :members:
   :undoc-members:
   :show-inheritance:

Dual TEMA-LSMA
^^^^^^^^^^^^^^

.. automodule:: strategies.dual_tema_lsma
   :members:
   :undoc-members:
   :show-inheritance:

Triple EMA Aligned
^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.triple_ema_aligned
   :members:
   :undoc-members:
   :show-inheritance:

EMA Crossover
^^^^^^^^^^^^^

.. automodule:: strategies.ema_crossover
   :members:
   :undoc-members:
   :show-inheritance:

Supertrend Strategies
^^^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.supertrend_dema
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: strategies.supertrend_vix_atr
   :members:
   :undoc-members:
   :show-inheritance:

Mean Reversion
--------------

Bollinger RSI
^^^^^^^^^^^^^

.. automodule:: strategies.bollinger_rsi
   :members:
   :undoc-members:
   :show-inheritance:

Weekly Green BB
^^^^^^^^^^^^^^^

.. automodule:: strategies.weekly_green_bb
   :members:
   :undoc-members:
   :show-inheritance:

Weekly Rotation
^^^^^^^^^^^^^^^

.. automodule:: strategies.weekly_rotation
   :members:
   :undoc-members:
   :show-inheritance:

Pattern Recognition
-------------------

Candlestick Patterns
^^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.candlestick_patterns
   :members:
   :undoc-members:
   :show-inheritance:

Ichimoku Strategies
^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.ichimoku_cloud
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: strategies.ichimoku_simple
   :members:
   :undoc-members:
   :show-inheritance:

Momentum
--------

Stochastic RSI Pyramid
^^^^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.stoch_rsi_pyramid_long
   :members:
   :undoc-members:
   :show-inheritance:

KAMA Crossover
^^^^^^^^^^^^^^

.. automodule:: strategies.kama_crossover_filtered
   :members:
   :undoc-members:
   :show-inheritance:

Knoxville Divergence
^^^^^^^^^^^^^^^^^^^^

.. automodule:: strategies.knoxville
   :members:
   :undoc-members:
   :show-inheritance:
