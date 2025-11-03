"""
Interactive Bokeh-based charting system adapted from backtesting.py for QuantLab.

Provides advanced interactive charts with candlestick plots, indicators, trade markers,
equity curves, and drawdown analysis optimized for Indian equities analysis.

Original implementation: https://github.com/kernc/backtesting.py
Adapted for QuantLab's architecture and requirements.
"""

import warnings

import pandas as pd

try:
    from bokeh.io import output_file, output_notebook, save
    from bokeh.layouts import column, gridplot
    from bokeh.models import (
        BoxZoomTool,
        ColumnDataSource,
        CrosshairTool,
        DatetimeTickFormatter,
        HoverTool,
        LinearAxis,
        NumeralTickFormatter,
        PanTool,
        Range1d,
        ResetTool,
        SaveTool,
        WheelZoomTool,
    )
    from bokeh.palettes import Category10
    from bokeh.plotting import figure, show

    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False


class BokehChart:
    """
    Interactive Bokeh-based charting for QuantLab backtesting results.

    Provides comprehensive visualization including:
    - OHLC candlestick charts with indicators
    - Trade entry/exit markers
    - Equity curve and drawdown analysis
    - Position size tracking
    - Multi-timeframe support
    """

    def __init__(self, width=800, height=600, tools="auto"):
        """
        Initialize chart with configuration.

        Args:
            width: Chart width in pixels
            height: Chart height in pixels
            tools: Bokeh tools to include ("auto" for default set)
        """
        if not BOKEH_AVAILABLE:
            raise ImportError(
                "Bokeh is required for interactive charts. "
                "Install with: pip install bokeh"
            )

        self.width = width
        self.height = height
        self.tools = self._get_tools() if tools == "auto" else tools
        self.colors = Category10[10]
        self._figures = []

    def _get_tools(self):
        """Get default tool set for charts."""
        return [
            PanTool(),
            BoxZoomTool(),
            WheelZoomTool(),
            CrosshairTool(),
            ResetTool(),
            SaveTool(),
            HoverTool(
                tooltips=[
                    ("Date", "@date{%F}"),
                    ("Open", "@open{0.00}"),
                    ("High", "@high{0.00}"),
                    ("Low", "@low{0.00}"),
                    ("Close", "@close{0.00}"),
                    ("Volume", "@volume{0,0}"),
                ],
                formatters={"@date": "datetime"},
            ),
        ]

    def plot_ohlc_with_indicators(
        self,
        data: pd.DataFrame,
        indicators: dict = None,
        trades: pd.DataFrame = None,
        title: str = "OHLC Chart",
    ):
        """
        Plot OHLC candlestick chart with technical indicators and trade markers.

        Args:
            data: OHLC DataFrame with DatetimeIndex
            indicators: Dict of indicator name -> Series mappings
            trades: DataFrame with trade entry/exit information
            title: Chart title

        Returns:
            Bokeh figure object
        """
        # Prepare data
        df = data.copy()
        df["date"] = df.index

        # Determine colors for candlesticks
        df["color"] = [
            "green" if close >= open else "red"
            for close, open in zip(df["Close"], df["Open"])
        ]

        source = ColumnDataSource(
            {
                "date": df.index,
                "open": df["Open"],
                "high": df["High"],
                "low": df["Low"],
                "close": df["Close"],
                "volume": df.get("Volume", [0] * len(df)),
                "color": df["color"],
            }
        )

        # Create main price chart
        p = figure(
            width=self.width,
            height=int(self.height * 0.7),
            x_axis_type="datetime",
            title=title,
            tools=self.tools,
        )

        # Add candlesticks
        p.segment("date", "high", "date", "low", color="black", source=source)
        p.vbar(
            "date",
            0.7 * 24 * 60 * 60 * 1000,
            "open",
            "close",
            color="color",
            source=source,
            alpha=0.8,
        )

        # Add indicators
        if indicators:
            self._add_indicators(p, indicators, df.index)

        # Add trade markers
        if trades is not None:
            self._add_trade_markers(p, trades)

        # Format axes
        p.xaxis.formatter = DatetimeTickFormatter(days="%m/%d", months="%m/%Y")
        p.yaxis.formatter = NumeralTickFormatter(format="0.00")

        self._figures.append(p)
        return p

    def plot_equity_curve(
        self, equity: pd.Series, drawdown: pd.Series = None, title: str = "Equity Curve"
    ):
        """
        Plot equity curve with optional drawdown.

        Args:
            equity: Equity time series
            drawdown: Drawdown time series (optional)
            title: Chart title

        Returns:
            Bokeh figure object
        """
        source = ColumnDataSource(
            {
                "date": equity.index,
                "equity": equity.values,
                "drawdown": (
                    drawdown.values if drawdown is not None else [0] * len(equity)
                ),
            }
        )

        # Create equity chart
        p = figure(
            width=self.width,
            height=int(self.height * 0.3),
            x_axis_type="datetime",
            title=title,
            tools=self.tools,
        )

        p.line("date", "equity", color="blue", line_width=2, source=source)

        # Add drawdown on secondary axis if provided
        if drawdown is not None:
            p.extra_y_ranges = {"drawdown": Range1d(start=drawdown.min() * 1.1, end=0)}
            p.add_layout(LinearAxis(y_range_name="drawdown"), "right")
            p.line(
                "date",
                "drawdown",
                color="red",
                line_width=1,
                y_range_name="drawdown",
                source=source,
                alpha=0.7,
            )

        # Format axes
        p.xaxis.formatter = DatetimeTickFormatter(days="%m/%d", months="%m/%Y")
        p.yaxis.formatter = NumeralTickFormatter(format="0,0")

        self._figures.append(p)
        return p

    def plot_volume(self, data: pd.DataFrame, title: str = "Volume"):
        """
        Plot volume bars.

        Args:
            data: OHLC DataFrame with Volume column
            title: Chart title

        Returns:
            Bokeh figure object
        """
        if "Volume" not in data.columns:
            warnings.warn("No Volume data found", stacklevel=2)
            return None

        source = ColumnDataSource(
            {
                "date": data.index,
                "volume": data["Volume"],
                "color": [
                    "green" if close >= open else "red"
                    for close, open in zip(data["Close"], data["Open"])
                ],
            }
        )

        p = figure(
            width=self.width,
            height=int(self.height * 0.2),
            x_axis_type="datetime",
            title=title,
            tools=self.tools,
        )

        p.vbar(
            "date",
            0.7 * 24 * 60 * 60 * 1000,
            0,
            "volume",
            color="color",
            source=source,
            alpha=0.6,
        )

        p.xaxis.formatter = DatetimeTickFormatter(days="%m/%d", months="%m/%Y")
        p.yaxis.formatter = NumeralTickFormatter(format="0,0")

        self._figures.append(p)
        return p

    def _add_indicators(self, p, indicators: dict, index: pd.DatetimeIndex):
        """Add technical indicators to the chart."""
        color_idx = 0

        for name, series in indicators.items():
            if hasattr(series, "_plot_data"):
                # Use plotting metadata from Strategy.I() method
                plot_data = series._plot_data
                color = plot_data.get(
                    "color", self.colors[color_idx % len(self.colors)]
                )
                overlay = plot_data.get("overlay", True)

                if overlay:
                    # Plot on main price axis
                    p.line(
                        index,
                        series.values,
                        legend_label=name,
                        color=color,
                        line_width=2,
                        alpha=0.8,
                    )
                else:
                    # Create separate subplot for non-overlay indicators
                    warnings.warn(
                        f"Non-overlay indicator {name} plotted on main chart",
                        stacklevel=2,
                    )

            else:
                # Simple line plot
                color = self.colors[color_idx % len(self.colors)]
                p.line(
                    index,
                    series.values,
                    legend_label=name,
                    color=color,
                    line_width=2,
                    alpha=0.8,
                )

            color_idx += 1

        # Configure legend
        p.legend.location = "top_left"
        p.legend.click_policy = "hide"

    def _add_trade_markers(self, p, trades: pd.DataFrame):
        """Add trade entry/exit markers to the chart."""
        if trades.empty:
            return

        # Add entry markers
        if "entry_time" in trades.columns and "entry_price" in trades.columns:
            entries = ColumnDataSource(
                {"x": trades["entry_time"], "y": trades["entry_price"]}
            )
            p.triangle("x", "y", source=entries, size=10, color="green", alpha=0.8)

        # Add exit markers
        if "exit_time" in trades.columns and "exit_price" in trades.columns:
            exits = ColumnDataSource(
                {"x": trades["exit_time"], "y": trades["exit_price"]}
            )
            p.inverted_triangle("x", "y", source=exits, size=10, color="red", alpha=0.8)

    def show_charts(self, layout="vertical"):
        """
        Display all created charts.

        Args:
            layout: "vertical" or "grid" layout arrangement
        """
        if not self._figures:
            warnings.warn("No charts to display", stacklevel=2)
            return

        if layout == "vertical":
            layout_obj = column(self._figures)
        elif layout == "grid":
            # Arrange in 2-column grid
            layout_obj = gridplot(
                [self._figures[i : i + 2] for i in range(0, len(self._figures), 2)]
            )
        else:
            raise ValueError("layout must be 'vertical' or 'grid'")

        show(layout_obj)

    def create_dashboard(
        self,
        data: pd.DataFrame,
        equity: pd.Series,
        drawdown: pd.Series = None,
        indicators: dict = None,
        trades: pd.DataFrame = None,
        title: str = "Trading Dashboard",
    ):
        """
        Create comprehensive trading dashboard with all charts.

        Args:
            data: OHLC DataFrame
            equity: Equity time series
            drawdown: Drawdown time series
            indicators: Technical indicators dictionary
            trades: Trades DataFrame
            title: Dashboard title

        Returns:
            Combined layout object
        """
        charts = []

        # Main OHLC chart with indicators
        main_chart = self.plot_ohlc_with_indicators(
            data, indicators, trades, f"{title} - Price Chart"
        )
        charts.append(main_chart)

        # Volume chart
        volume_chart = self.plot_volume(data, "Volume")
        if volume_chart:
            charts.append(volume_chart)

        # Equity curve
        equity_chart = self.plot_equity_curve(equity, drawdown, "Portfolio Performance")
        charts.append(equity_chart)

        # Link x-axes for synchronized zoom/pan
        for chart in charts[1:]:
            chart.x_range = main_chart.x_range

        return column(charts)


def plot_backtest_results(
    results: dict,
    data: pd.DataFrame = None,
    indicators: dict = None,
    trades: pd.DataFrame = None,
    show_plot: bool = True,
    **kwargs,
):
    """
    Convenience function to plot comprehensive backtest results.

    Args:
        results: Backtest results dictionary
        data: OHLC DataFrame
        indicators: Technical indicators
        trades: Trades DataFrame
        show_plot: Whether to display the plot
        **kwargs: Additional chart configuration

    Returns:
        BokehChart instance
    """
    if not BOKEH_AVAILABLE:
        warnings.warn("Bokeh not available, falling back to matplotlib", stacklevel=2)
        return None

    chart = BokehChart(**kwargs)

    # Extract equity and drawdown from results
    if "equity_curve" in results:
        equity = results["equity_curve"]
        drawdown = equity / equity.cummax() - 1
    else:
        warnings.warn("No equity curve found in results", stacklevel=2)
        equity = pd.Series([100], index=[pd.Timestamp.now()])
        drawdown = pd.Series([0], index=[pd.Timestamp.now()])

    # Create dashboard
    if data is not None:
        dashboard = chart.create_dashboard(data, equity, drawdown, indicators, trades)

        if show_plot:
            show(dashboard)
    else:
        # Just plot equity curve
        equity_chart = chart.plot_equity_curve(equity, drawdown)
        if show_plot:
            show(equity_chart)

    return chart


# Utility functions for notebook environments
def setup_notebook():
    """Setup Bokeh for Jupyter notebook display."""
    if BOKEH_AVAILABLE:
        output_notebook()
    else:
        warnings.warn("Bokeh not available", stacklevel=2)


def enable_notebook_inline():
    """Enable inline Bokeh plots in notebooks."""
    if BOKEH_AVAILABLE:
        from bokeh.io import output_notebook

        output_notebook()
    else:
        warnings.warn("Bokeh not available for notebook inline plots", stacklevel=2)
