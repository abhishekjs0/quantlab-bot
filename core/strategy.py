"""
Enhanced strategy base class with indicator wrapper and plotting support.

Adapted from backtesting.py to provide cleaner indicator declaration and automatic
plotting capabilities while maintaining QuantLab's architecture.
"""

from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd


def _as_str(value) -> str:
    """Convert value to string representation for parameter formatting."""
    if isinstance(value, type):
        return value.__name__
    return str(value)


class _Indicator(np.ndarray):
    """
    Enhanced ndarray for indicator values with plotting metadata.

    This stores indicator values along with plotting options like name,
    color, overlay settings, etc. for use in visualization.
    """

    def __new__(
        cls,
        array,
        *,
        name=None,
        plot=True,
        overlay=None,
        color=None,
        scatter=False,
        **kwargs,
    ):
        obj = np.asarray(array, dtype=float).view(cls)
        obj._opts = dict(
            name=name,
            plot=plot,
            overlay=overlay,
            color=color,
            scatter=scatter,
            **kwargs,
        )
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self._opts = getattr(obj, "_opts", {})

    @property
    def name(self):
        """Get indicator name."""
        return self._opts.get("name", "Indicator")

    @property
    def color(self):
        """Get indicator color."""
        return self._opts.get("color", "blue")

    @property
    def overlay(self):
        """Get overlay setting."""
        return self._opts.get("overlay", True)

    @property
    def s(self) -> pd.Series:
        """Return indicator as pandas Series with proper index."""
        index = self._opts.get("index", range(len(self)))
        return pd.Series(self, index=index, name=self.name)


class Strategy:
    """
    Enhanced strategy base class with indicator wrapper and plotting support.

    Provides clean API for indicator declaration via self.I() method and automatic
    plotting integration while maintaining QuantLab's execution model.
    """

    def __init__(self):
        """Initialize strategy with empty indicators list."""
        self._indicators = []
        self._data = None

    def I(
        self,  # noqa: E743
        func: Callable,
        *args,
        name=None,
        plot=True,
        overlay=None,
        color=None,
        scatter=False,
        **kwargs,
    ) -> np.ndarray:
        """
        Declare an indicator for use in strategy.

        An indicator is an array of values (or tuple of arrays) that gets revealed
        gradually during backtesting, similar to how price data is revealed.

        Args:
            func: Function that returns indicator array(s) of same length as data
            *args: Positional arguments passed to func
            name: Display name for indicator (auto-generated if None)
            plot: Whether to plot this indicator
            overlay: Whether to overlay on price chart (auto-detected if None)
            color: Color for plotting (auto-assigned if None)
            scatter: Use scatter plot instead of line
            **kwargs: Additional arguments passed to func

        Returns:
            np.ndarray of indicator values

        Example:
            def init(self):
                self.sma20 = self.I(SMA, self.data.Close, 20)
                self.rsi = self.I(RSI, self.data.Close, 14, overlay=False)
        """

        def _format_name(name: str) -> str:
            """Format name string with parameter substitution."""
            return name.format(
                *map(_as_str, args),
                **dict(zip(kwargs.keys(), map(_as_str, kwargs.values()), strict=False)),
            )

        # Generate automatic name if not provided
        if name is None:
            params = ",".join(filter(None, map(_as_str, [*args, *kwargs.values()])))
            func_name = _as_str(func)
            name = f"{func_name}({params})" if params else func_name
        elif isinstance(name, str):
            name = _format_name(name)
        elif isinstance(name, (list, tuple)) and all(isinstance(n, str) for n in name):
            name = [_format_name(n) for n in name]
        else:
            raise TypeError(
                f"Unexpected `name=` type {type(name)}; expected str or Sequence[str]"
            )

        # Calculate indicator values
        try:
            value = func(*args, **kwargs)
        except Exception as e:
            raise RuntimeError(f"Indicator '{name}' error. See traceback above.") from e

        # Convert DataFrame to numpy array if needed
        if isinstance(value, pd.DataFrame):
            value = value.values.T

        # Ensure we have a proper numpy array
        if value is not None:
            value = np.asarray(value, order="C")

        is_arraylike = bool(value is not None and value.shape)

        # Transpose if needed (user returned e.g. df.values)
        if is_arraylike and np.argmax(value.shape) == 0:
            value = value.T

        # Validate array dimensions and length
        if isinstance(name, list) and np.atleast_2d(value).shape[0] != len(name):
            raise ValueError(
                f"Length of `name=` ({len(name)}) must agree with the number "
                f"of arrays the indicator returns ({value.shape[0]})."
            )

        if not is_arraylike or not 1 <= value.ndim <= 2:
            raise ValueError(
                f"Indicators must return numpy arrays of 1 or 2 dimensions. "
                f"Indicator '{name}' shape: {getattr(value, 'shape', 'N/A')}"
            )

        # Auto-detect overlay setting based on values
        if overlay is None and np.issubdtype(value.dtype, np.number):
            # Use sample of data to detect if values are price-like
            sample = value.flat[: min(100, value.size)]
            sample = sample[~np.isnan(sample)]

            if len(sample) > 0 and hasattr(self, "_data") and self._data is not None:
                # Try to get a price reference for comparison
                try:
                    if hasattr(self._data, "Close"):
                        price_sample = self._data.Close[: len(sample)]
                        ratio = sample / price_sample[: len(sample)]
                        # Overlay if most values are within reasonable range of price
                        overlay = np.mean((ratio > 0.5) & (ratio < 2.0)) > 0.7
                    else:
                        overlay = False
                except Exception:
                    overlay = False
            else:
                overlay = False

        # Create indicator object with metadata
        indicator = _Indicator(
            value,
            name=name,
            plot=plot,
            overlay=overlay,
            color=color,
            scatter=scatter,
            index=(
                getattr(self._data, "index", None) if hasattr(self, "_data") else None
            ),
        )

        # Store for later plotting/analysis
        self._indicators.append(indicator)
        return indicator

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data for strategy execution.

        Override this method to add custom indicators or data transformations.
        Called once before strategy execution begins.

        Args:
            df: Input OHLCV DataFrame

        Returns:
            Enhanced DataFrame with additional columns/indicators
        """
        self._data = df
        return df

    def on_bar(self, ts, row, state: dict[str, Any]) -> dict[str, Any]:
        """
        Process each bar/candle of data.

        Override this method to implement trading logic.

        Args:
            ts: Timestamp of current bar
            row: Current bar data (OHLCV)
            state: Current strategy state

        Returns:
            Dictionary with trading signals (enter_long, exit_long, etc.)
        """
        return {"enter_long": False, "exit_long": False}

    def size(self, equity: float, price: float, cfg) -> int:
        """
        Calculate position size for trades.

        Args:
            equity: Current account equity
            price: Entry price
            cfg: Configuration object

        Returns:
            Number of shares/units to trade
        """
        budget = equity * cfg.qty_pct_of_equity
        qty = budget / price if price > 0 else 0.0
        return int(np.floor(qty)) if cfg.round_qty else int(qty)

    def on_entry(
        self, entry_time, entry_price: float, state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Hook called immediately after entry fill.

        Args:
            entry_time: Entry timestamp
            entry_price: Fill price
            state: Strategy state

        Returns:
            Dictionary with optional trade metadata (stop, take_profit, etc.)
        """
        return {}

    @property
    def indicators(self):
        """Get list of declared indicators."""
        return self._indicators

    def __class_getitem__(cls, item):
        """Support for generic type hints."""
        return cls


# Utility functions for common indicator operations
def crossover(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Return True where series1 crosses over series2.

    Args:
        series1: First series
        series2: Second series or scalar value

    Returns:
        Boolean array indicating crossover points
    """
    series1 = np.asarray(series1)
    series2 = np.asarray(series2)

    if series2.ndim == 0:  # scalar
        return (series1[:-1] <= series2) & (series1[1:] > series2)
    else:
        return (series1[:-1] <= series2[:-1]) & (series1[1:] > series2[1:])


def crossunder(series1: np.ndarray, series2: np.ndarray) -> np.ndarray:
    """
    Return True where series1 crosses under series2.

    Args:
        series1: First series
        series2: Second series or scalar value

    Returns:
        Boolean array indicating crossunder points
    """
    return crossover(series2, series1)


class StrategyMixin:
    """Mixin class to add plotting capabilities to Strategy classes."""

    def plot(
        self,
        data: pd.DataFrame = None,
        equity: pd.Series = None,
        trades: pd.DataFrame = None,
        use_bokeh: bool = True,
        **kwargs,
    ):
        """
        Plot strategy results with indicators and trades.

        Args:
            data: OHLC DataFrame (uses self._data if not provided)
            equity: Equity curve (attempts to extract from results if not provided)
            trades: Trades DataFrame
            use_bokeh: Whether to use interactive Bokeh plots (fallback to matplotlib)
            **kwargs: Additional plotting arguments

        Returns:
            Chart object or matplotlib figure
        """
        # Use provided data or attempt to use strategy's data
        if data is None and hasattr(self, "_data"):
            data = self._data
        elif data is None:
            raise ValueError("No data available for plotting")

        # Collect indicator values that have plotting enabled
        indicators = {}
        for name, attr in self.__dict__.items():
            if isinstance(attr, _Indicator) and attr._opts.get("plot", True):
                indicator_name = attr._opts.get("name", name)
                # Convert to pandas Series with proper index
                if hasattr(data, "index"):
                    series = pd.Series(attr, index=data.index, name=indicator_name)
                    # Add plotting metadata
                    series._plot_data = attr._opts
                    indicators[indicator_name] = series

        # Try Bokeh first if requested and available
        if use_bokeh:
            try:
                from ..viz.bokeh_charts import plot_backtest_results

                return plot_backtest_results(
                    results={"equity_curve": equity} if equity is not None else {},
                    data=data,
                    indicators=indicators,
                    trades=trades,
                    **kwargs,
                )
            except ImportError:
                # Fall back to matplotlib
                pass

        # Fallback to matplotlib
        try:
            import matplotlib.pyplot as plt

            # Plot price chart with indicators
            fig, axes = plt.subplots(2, 1, figsize=(12, 8))

            # Price and indicators on top subplot
            ax1 = axes[0]
            ax1.plot(data.index, data["Close"], label="Close", linewidth=1)

            for name, series in indicators.items():
                plot_data = getattr(series, "_plot_data", {})
                overlay = plot_data.get("overlay", True)
                color = plot_data.get("color", None)

                if overlay:
                    ax1.plot(
                        data.index, series.values, label=name, color=color, alpha=0.8
                    )

            ax1.set_title("Price Chart with Indicators")
            ax1.legend()
            ax1.grid(True, alpha=0.3)

            # Equity curve on bottom subplot if available
            if equity is not None:
                ax2 = axes[1]
                ax2.plot(equity.index, equity.values, "b-", linewidth=2)
                ax2.set_title("Equity Curve")
                ax2.grid(True, alpha=0.3)
            else:
                axes[1].set_visible(False)

            plt.tight_layout()
            return fig

        except ImportError:
            raise ImportError(
                "Neither Bokeh nor matplotlib available for plotting"
            ) from None

    def get_indicators(self) -> dict:
        """
        Get all indicators defined in the strategy.

        Returns:
            Dictionary of indicator name -> _Indicator mappings
        """
        indicators = {}
        for name, attr in self.__dict__.items():
            if isinstance(attr, _Indicator):
                indicator_name = attr._opts.get("name", name)
                indicators[indicator_name] = attr
        return indicators
