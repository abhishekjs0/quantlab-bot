"""
Visualization and charting utilities for QuantLab.

Provides both traditional matplotlib plots and modern interactive Bokeh-based
visualizations adapted from backtesting.py for comprehensive market analysis.
"""

# Import visualization modules only when needed to avoid dependency issues
__all__ = []

# Optional imports to avoid breaking when dependencies are missing
try:
    from .equity_plot import plot_equity_and_dd

    __all__.append("plot_equity_and_dd")
except ImportError:
    pass

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
    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False
