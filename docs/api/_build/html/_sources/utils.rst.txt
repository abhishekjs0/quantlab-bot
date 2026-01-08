Utilities
=========

Technical Indicators
--------------------

QuantLab provides a comprehensive library of technical indicators optimized
for vectorized operations with NumPy.

All indicators follow consistent patterns:

- Accept ``np.ndarray`` or ``pd.Series`` inputs
- Return ``np.ndarray`` outputs
- Handle NaN values for insufficient data periods
- Use Wilder's smoothing for RSI/ATR (matches TradingView)

.. automodule:: utils.indicators
   :members:
   :undoc-members:
   :show-inheritance:

Indicator Reference
^^^^^^^^^^^^^^^^^^^

Moving Averages
"""""""""""""""

- **SMA** - Simple Moving Average
- **EMA** - Exponential Moving Average
- **WMA** - Weighted Moving Average
- **DEMA** - Double Exponential Moving Average
- **TEMA** - Triple Exponential Moving Average
- **LSMA** - Least Squares Moving Average (Linear Regression)
- **KAMA** - Kaufman's Adaptive Moving Average
- **SMMA** - Smoothed Moving Average (Wilder's)

Momentum Oscillators
""""""""""""""""""""

- **RSI** - Relative Strength Index (Wilder's smoothing)
- **StochasticRSI** - Stochastic RSI
- **CCI** - Commodity Channel Index
- **ROC** - Rate of Change
- **Momentum** - Simple momentum

Volatility
""""""""""

- **ATR** - Average True Range
- **BollingerBands** - Bollinger Bands (SMA ± N × std)
- **CHOP** - Choppiness Index

Trend
"""""

- **ADX** - Average Directional Index
- **Supertrend** - Supertrend indicator
- **MACD** - Moving Average Convergence Divergence
- **Aroon** - Aroon Up/Down

Volume
""""""

- **VWAP** - Volume Weighted Average Price
- **MFI** - Money Flow Index

Production Utilities
--------------------

.. automodule:: utils.production_utils
   :members:
   :undoc-members:
   :show-inheritance:
