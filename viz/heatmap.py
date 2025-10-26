"""
Interactive heatmap visualization for parameter optimization results.

Provides sophisticated heatmap plotting capabilities for QuantLab optimization
results with support for multi-dimensional parameter spaces and interactive
analysis adapted from backtesting.py.
"""

import warnings

import pandas as pd

try:
    from bokeh.models import BasicTicker, ColorBar, LinearColorMapper
    from bokeh.palettes import RdYlBu11
    from bokeh.plotting import figure, show
    from bokeh.transform import transform

    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import seaborn as sns

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False


def plot_heatmaps(
    results: pd.Series,
    agg="mean",
    ncols=3,
    plot_width=250,
    plot_height=250,
    filename=None,
    open_browser=None,
):
    """
    Plot parameter optimization results as interactive heatmaps.

    Args:
        results: Series with MultiIndex containing parameter combinations and values
        agg: Aggregation method for duplicate values ("mean", "max", "min")
        ncols: Number of columns in heatmap grid
        plot_width: Width of individual heatmap plots
        plot_height: Height of individual heatmap plots
        filename: Optional filename to save the plot
        open_browser: Whether to open in browser (None for auto-detect)

    Returns:
        Bokeh layout object or matplotlib figure
    """
    if not isinstance(results, pd.Series):
        raise TypeError("results must be a pandas Series")

    if not isinstance(results.index, pd.MultiIndex):
        raise ValueError("results Series must have MultiIndex")

    if len(results.index.names) < 2:
        warnings.warn("Need at least 2 parameters for heatmap", stacklevel=2)
        return None

    # Aggregate duplicates if any
    if agg == "mean":
        results = results.groupby(level=list(range(len(results.index.names)))).mean()
    elif agg == "max":
        results = results.groupby(level=list(range(len(results.index.names)))).max()
    elif agg == "min":
        results = results.groupby(level=list(range(len(results.index.names)))).min()

    param_names = results.index.names
    n_params = len(param_names)

    if BOKEH_AVAILABLE:
        return _plot_bokeh_heatmaps(
            results, param_names, n_params, ncols, plot_width, plot_height
        )
    elif MATPLOTLIB_AVAILABLE:
        warnings.warn("Bokeh not available, using matplotlib", stacklevel=2)
        return _plot_matplotlib_heatmaps(results, param_names, n_params, ncols)
    else:
        raise ImportError("Neither Bokeh nor matplotlib available for plotting")


def _plot_bokeh_heatmaps(
    results, param_names, n_params, ncols, plot_width, plot_height
):
    """Create interactive Bokeh heatmaps."""
    from bokeh.layouts import gridplot
    from bokeh.models import ColumnDataSource

    plots = []

    # Create heatmap for each parameter pair
    for i in range(n_params):
        for j in range(i + 1, n_params):
            param_x, param_y = param_names[i], param_names[j]

            # Aggregate data for this parameter pair
            df = results.reset_index()
            pivot_df = df.pivot_table(
                index=param_y, columns=param_x, values=results.name, aggfunc="mean"
            )

            if pivot_df.empty:
                continue

            # Prepare data for Bokeh
            pivot_df = pivot_df.fillna(0)

            # Create meshgrid for heatmap
            x_vals = list(pivot_df.columns)
            y_vals = list(pivot_df.index)

            xx, yy = [], []
            values = []

            for i_y, y in enumerate(y_vals):
                for i_x, x in enumerate(x_vals):
                    xx.append(x)
                    yy.append(y)
                    values.append(pivot_df.iloc[i_y, i_x])

            # Color mapping
            max_val = max(values) if values else 1
            min_val = min(values) if values else 0

            color_mapper = LinearColorMapper(
                palette=RdYlBu11[::-1], low=min_val, high=max_val
            )

            source = ColumnDataSource({"x": xx, "y": yy, "values": values})

            # Create plot
            p = figure(
                title=f"{param_x} vs {param_y}",
                x_axis_label=param_x,
                y_axis_label=param_y,
                width=plot_width,
                height=plot_height,
                toolbar_location="above",
            )

            # Add rectangles for heatmap
            if len(x_vals) > 1 and len(y_vals) > 1:
                x_width = abs(x_vals[1] - x_vals[0]) * 0.9
                y_height = abs(y_vals[1] - y_vals[0]) * 0.9 if len(y_vals) > 1 else 1
            else:
                x_width = 1
                y_height = 1

            p.rect(
                "x",
                "y",
                x_width,
                y_height,
                source=source,
                fill_color=transform("values", color_mapper),
                line_color=None,
            )

            # Add color bar
            color_bar = ColorBar(
                color_mapper=color_mapper,
                ticker=BasicTicker(),
                label_standoff=12,
                location=(0, 0),
            )
            p.add_layout(color_bar, "right")

            plots.append(p)

    if not plots:
        warnings.warn("No parameter combinations to plot", stacklevel=2)
        return None

    # Arrange in grid
    grid = []
    for i in range(0, len(plots), ncols):
        grid.append(plots[i : i + ncols])

    layout = gridplot(grid)
    return layout


def _plot_matplotlib_heatmaps(results, param_names, n_params, ncols):
    """Create matplotlib heatmaps as fallback."""
    import math

    n_plots = n_params * (n_params - 1) // 2
    nrows = math.ceil(n_plots / ncols)

    fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 4, nrows * 3))
    if n_plots == 1:
        axes = [axes]
    elif nrows == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    plot_idx = 0

    for i in range(n_params):
        for j in range(i + 1, n_params):
            if plot_idx >= len(axes):
                break

            param_x, param_y = param_names[i], param_names[j]

            # Aggregate data for this parameter pair
            df = results.reset_index()
            pivot_df = df.pivot_table(
                index=param_y, columns=param_x, values=results.name, aggfunc="mean"
            )

            if not pivot_df.empty:
                sns.heatmap(
                    pivot_df,
                    ax=axes[plot_idx],
                    cmap="RdYlBu_r",
                    annot=True,
                    fmt=".3f",
                    cbar_kws={"shrink": 0.8},
                )
                axes[plot_idx].set_title(f"{param_x} vs {param_y}")

            plot_idx += 1

    # Hide unused subplots
    for idx in range(plot_idx, len(axes)):
        axes[idx].set_visible(False)

    plt.tight_layout()
    return fig


def plot_optimization_surface(results: pd.Series, param1: str, param2: str):
    """
    Plot 3D optimization surface for two parameters.

    Args:
        results: Optimization results Series with MultiIndex
        param1: First parameter name
        param2: Second parameter name

    Returns:
        3D plot figure
    """
    if param1 not in results.index.names or param2 not in results.index.names:
        raise ValueError(f"Parameters {param1}, {param2} not found in results")

    # Extract data for the two parameters
    df = results.reset_index()

    # Create pivot table
    pivot_df = df.pivot_table(
        index=param2, columns=param1, values=results.name, aggfunc="mean"
    )

    if BOKEH_AVAILABLE:
        # Create 3D surface plot with Bokeh (simplified as contour plot)

        x_vals = list(pivot_df.columns)
        y_vals = list(pivot_df.index)

        p = figure(
            title=f"Optimization Surface: {param1} vs {param2}",
            x_axis_label=param1,
            y_axis_label=param2,
            width=600,
            height=500,
        )

        # Add contour-like visualization
        for i, y in enumerate(y_vals):
            for j, x in enumerate(x_vals):
                val = pivot_df.iloc[i, j]
                if not pd.isna(val):
                    # Color based on value
                    color_intensity = int(
                        255
                        * (val - pivot_df.min().min())
                        / (pivot_df.max().max() - pivot_df.min().min())
                    )
                    color = f"rgb({255-color_intensity}, {color_intensity}, 0)"

                    p.circle([x], [y], size=15, color=color, alpha=0.7)

        return p

    elif MATPLOTLIB_AVAILABLE:
        # Use matplotlib for 3D surface
        import numpy as np

        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection="3d")

        X, Y = np.meshgrid(pivot_df.columns, pivot_df.index)
        Z = pivot_df.values

        surface = ax.plot_surface(X, Y, Z, cmap="RdYlBu_r", alpha=0.8)

        ax.set_xlabel(param1)
        ax.set_ylabel(param2)
        ax.set_zlabel(results.name or "Value")
        ax.set_title(f"Optimization Surface: {param1} vs {param2}")

        fig.colorbar(surface, shrink=0.5)

        return fig
    else:
        raise ImportError("Neither Bokeh nor matplotlib available for 3D plotting")


def show_heatmap(results: pd.Series, **kwargs):
    """
    Convenience function to show optimization heatmaps.

    Args:
        results: Optimization results Series
        **kwargs: Additional arguments for plot_heatmaps
    """
    layout = plot_heatmaps(results, **kwargs)
    if layout:
        if BOKEH_AVAILABLE:
            show(layout)
        else:
            plt.show()
    else:
        warnings.warn("No heatmap generated", stacklevel=2)
