"""
Visualization and charting utilities for QuantLab.

Provides both traditional matplotlib plots and modern interactive Bokeh-based
visualizations adapted from backtesting.py for comprehensive market analysis.
"""

from .equity_plot import plot_equity_and_dd

# Import Bokeh-based visualization if available
try:
    from .bokeh_charts import (
        BokehChart,
        enable_notebook_inline,
        plot_backtest_results,
        plot_heatmaps,
        plot_optimization_surface,
        setup_notebook,
        show_heatmap,
    )

    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False

__all__ = [
    "plot_equity_and_dd",
]

if BOKEH_AVAILABLE:
    __all__.extend(
        [
            "BokehChart",
            "plot_backtest_results",
            "setup_notebook",
            "enable_notebook_inline",
            "plot_heatmaps",
            "plot_optimization_surface",
            "show_heatmap",
        ]
    )
