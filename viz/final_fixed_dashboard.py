"""
Final Fixed Comprehensive Dashboard addressing all remaining user feedback.
"""

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from scipy import stats
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures

warnings.filterwarnings("ignore")


class FinalFixedDashboard:
    """Final fixed comprehensive dashboard addressing all user feedback."""

    def __init__(self, report_dir: Path):
        """Initialize dashboard with report directory."""
        self.report_dir = Path(report_dir)
        self.colors = {
            "primary": "#1e3a8a",  # Professional dark blue
            "secondary": "#374151",  # Dark gray-blue
            "accent": "#059669",  # Professional green
            "profit": "#10b981",  # Emerald green for profits
            "loss": "#dc2626",  # Professional red for losses
            "neutral": "#6b7280",  # Medium gray
            "equity": "#2563eb",  # Clean blue for equity curves
            "exposure": "#7c3aed",  # Purple for exposure
            "edge": "#e11d48",  # Rose red for edge indicators
            "good_performance": "#059669",  # Green for good performance
            "poor_performance": "#dc2626",  # Red for poor performance
            "winners": "#065f46",  # Dark green for winners
            "losers": "#991b1b",  # Dark red for losers
            "light_profit": "#86efac",  # Light green for unrealized gains
            "light_loss": "#fca5a5",  # Light red for unrealized losses
            "background": "#f8fafc",  # Light gray-blue background
            "metrics_panel": "#e0f2fe",  # Light blue for key metrics panel
            "chart_bg": "#ffffff",  # White for chart backgrounds
        }

        # Layout configuration with much more space for buttons
        self.layout_config = {
            "template": "plotly_white",
            "showlegend": True,
            "legend": {
                "orientation": "h",
                "yanchor": "bottom",
                "y": 1.02,
                "xanchor": "right",
                "x": 1,
            },
            "margin": {"l": 80, "r": 50, "t": 150, "b": 80},
            "title_x": 0.5,
            "title_font_size": 16,
            "autosize": True,
            "font": {"size": 12},
        }

    def _create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            showarrow=False,
            font_size=16,
            font_color="gray",
        )
        fig.update_layout(
            xaxis={"visible": False}, yaxis={"visible": False}, **self.layout_config
        )
        return fig

    def create_enhanced_metrics_panel(self, summary_data):
        """Create enhanced metrics panel similar to improved dashboard."""
        # Load strategy summary
        metrics = {}
        if summary_data is not None:
            for _, row in summary_data.iterrows():
                period = row["Window"]
                metrics[period] = {
                    "net_pnl": row["Net P&L %"],
                    "cagr": row["CAGR [%]"],
                    "irr": row["IRR [%]"],
                    "trades": row["# Trades"],
                    "win_rate": row["Win Rate [%]"],
                    "profit_factor": row["Profit Factor"],
                    "avg_exposure": row["Avg exposure %"],
                    "alpha": row["Alpha [%]"],
                    "beta": row["Beta"],
                    "avg_trade": row["Avg. Trade [%]"],
                    "best_trade": row["Best Trade [%]"],
                    "worst_trade": row["Worst Trade [%]"],
                    "max_trade_duration": row["Max. Trade Duration"],
                    "avg_trade_duration": row["Avg. Trade Duration"],
                    "max_drawdown": row["Max. Drawdown [%]"],
                    "max_dd_duration": row["Max. Drawdown Duration"],
                    "sharpe": row["Sharpe Ratio"],
                    "sortino": row["Sortino Ratio"],
                    "calmar": row["Calmar Ratio"],
                    "expectancy": row["Expectancy [%]"],
                    "sqn": row["SQN"],
                    "kelly": row["Kelly Criterion"],
                }

        def create_metrics_grid(period_metrics):
            """Create metrics grid HTML for a specific period."""
            return f"""
            <div class="metrics-grid">
                <div class="metric-card highlight">
                    <div class="metric-value">{period_metrics.get('net_pnl', 0):.1f}%</div>
                    <div class="metric-label">Net P&L</div>
                </div>
                <div class="metric-card highlight">
                    <div class="metric-value">{period_metrics.get('cagr', 0):.1f}%</div>
                    <div class="metric-label">CAGR</div>
                </div>
                <div class="metric-card highlight">
                    <div class="metric-value">{period_metrics.get('irr', 0):.1f}%</div>
                    <div class="metric-label">IRR</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{int(period_metrics.get('trades', 0))}</div>
                    <div class="metric-label"># Trades</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('win_rate', 0):.1f}%</div>
                    <div class="metric-label">Win Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('profit_factor', 0):.2f}</div>
                    <div class="metric-label">Profit Factor</div>
                </div>

                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('avg_exposure', 0):.1f}%</div>
                    <div class="metric-label">Avg Exposure</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('alpha', 0):.2f}%</div>
                    <div class="metric-label">Alpha</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('beta', 0):.2f}</div>
                    <div class="metric-label">Beta</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('avg_trade', 0):.2f}%</div>
                    <div class="metric-label">Avg Trade</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('best_trade', 0):.1f}%</div>
                    <div class="metric-label">Best Trade</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('worst_trade', 0):.1f}%</div>
                    <div class="metric-label">Worst Trade</div>
                </div>

                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('max_trade_duration', 'N/A')}</div>
                    <div class="metric-label">Max Duration</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('avg_trade_duration', 'N/A')}</div>
                    <div class="metric-label">Avg Duration</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('max_drawdown', 0):.1f}%</div>
                    <div class="metric-label">Max Drawdown</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('max_dd_duration', 'N/A')}</div>
                    <div class="metric-label">DD Duration</div>
                </div>

                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('sharpe', 0):.2f}</div>
                    <div class="metric-label">Sharpe</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('sortino', 0):.2f}</div>
                    <div class="metric-label">Sortino</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('calmar', 0):.2f}</div>
                    <div class="metric-label">Calmar</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('expectancy', 0):.2f}%</div>
                    <div class="metric-label">Expectancy</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('sqn', 0):.2f}</div>
                    <div class="metric-label">SQN</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('kelly', 0):.2f}</div>
                    <div class="metric-label">Kelly %</div>
                </div>
            </div>
            """

        # Create the complete metrics panel HTML
        metrics_html = f"""
        <div class="enhanced-metrics-panel">
            <h2>Portfolio Performance Metrics</h2>

            <div class="period-selector">
                <button class="period-btn active" id="btn-1Y" onclick="showMetrics('1Y')">1 Year</button>
                <button class="period-btn" id="btn-3Y" onclick="showMetrics('3Y')">3 Years</button>
                <button class="period-btn" id="btn-5Y" onclick="showMetrics('5Y')">5 Years</button>
            </div>

            <div class="metrics-content active" id="metrics-1Y">
                {create_metrics_grid(metrics.get("1Y", {}))}
            </div>

            <div class="metrics-content" id="metrics-3Y">
                {create_metrics_grid(metrics.get("3Y", {}))}
            </div>

            <div class="metrics-content" id="metrics-5Y">
                {create_metrics_grid(metrics.get("5Y", {}))}
            </div>
        </div>
        """

        return metrics_html

    def load_comprehensive_data(self, report_folder: str) -> dict:
        """Load all data from a report folder."""
        folder_path = self.report_dir / report_folder
        if not folder_path.exists():
            print(f"Report folder not found: {folder_path}")
            return {}

        data = {}

        # Try to load data for different periods
        period_files = {
            "1Y": [
                "portfolio_daily_equity_curve_1Y.csv",
                "consolidated_trades_1Y.csv",
                "portfolio_key_metrics_1Y.csv",
            ],
            "3Y": [
                "portfolio_daily_equity_curve_3Y.csv",
                "consolidated_trades_3Y.csv",
                "portfolio_key_metrics_3Y.csv",
            ],
            "5Y": [
                "portfolio_daily_equity_curve_5Y.csv",
                "consolidated_trades_5Y.csv",
                "portfolio_key_metrics_5Y.csv",
            ],
            "ALL": ["equity.csv", "trades.csv", None],
        }

        for period, files in period_files.items():
            equity_file, trades_file, metrics_file = files
            equity_path = folder_path / equity_file
            trades_path = folder_path / trades_file
            metrics_path = folder_path / metrics_file if metrics_file else None

            period_data = {}

            # Load existing portfolio metrics if available
            if metrics_path and metrics_path.exists():
                try:
                    metrics_df = pd.read_csv(metrics_path)
                    # Get the TOTAL row which contains portfolio-level metrics
                    total_row = metrics_df[metrics_df["Symbol"] == "TOTAL"]
                    if not total_row.empty:
                        period_data["metrics"] = total_row.iloc[0].to_dict()
                except Exception as e:
                    print(f"Error loading metrics file {metrics_path}: {e}")

            # Load equity data
            if equity_path.exists():
                try:
                    period_data["equity"] = pd.read_csv(equity_path)
                except Exception as e:
                    print(f"Error loading {equity_file}: {e}")
                    continue

            # Load trades data
            if trades_path.exists():
                try:
                    period_data["trades"] = pd.read_csv(trades_path)
                except Exception as e:
                    print(f"Error loading {trades_file}: {e}")

            if period_data:
                data[period] = period_data

        # If no period-specific files, try loading main files
        if not data:
            equity_path = folder_path / "equity.csv"
            trades_path = folder_path / "trades.csv"

            if equity_path.exists():
                try:
                    equity_df = pd.read_csv(equity_path)
                    data["ALL"] = {"equity": equity_df}

                    if trades_path.exists():
                        data["ALL"]["trades"] = pd.read_csv(trades_path)

                except Exception as e:
                    print(f"Error loading main files: {e}")

        return data

    def create_equity_dashboard(self, data: dict) -> go.Figure:
        """Create equity curve chart with % Y-axis and enhanced hover tooltips."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No equity data available")

        # Load strategy summary for CAGR information
        summary_path = self.report_dir / "strategy_backtests_summary.csv"
        cagr_data = {}
        if summary_path.exists():
            try:
                summary_df = pd.read_csv(summary_path)
                for _, row in summary_df.iterrows():
                    cagr_data[row["Window"]] = row["CAGR [%]"]
            except Exception as e:
                print(f"Error loading strategy summary: {e}")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        for period in periods:
            period_data = data[period]
            if "equity" not in period_data or period_data["equity"].empty:
                continue

            equity_df = period_data["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])

            # Calculate cumulative percentage returns from initial equity
            initial_equity = equity_df["Equity"].iloc[0]
            equity_pct = ((equity_df["Equity"] / initial_equity) - 1) * 100

            fig.add_trace(
                go.Scatter(
                    x=equity_df["Date"],
                    y=equity_pct,
                    mode="lines",
                    name=f"Portfolio {period}",
                    line={"color": self.colors["equity"], "width": 3},
                    visible=True if period == default_period else False,
                    hovertemplate="Date: %{x}<br>Portfolio Return: %{y:.2f}%<br>Portfolio Value: ₹%{customdata:,.0f}<extra></extra>",
                    customdata=equity_df["Equity"],
                )
            )

        # Create period toggle buttons if multiple periods exist
        if len(periods) > 1:
            period_buttons = []
            for i, period in enumerate(periods):
                visibility = [j == i for j in range(len(periods))]
                # Create dynamic title with CAGR
                cagr_value = cagr_data.get(period, 0)
                dynamic_title = (
                    f"Portfolio Performance<br><sub>CAGR: {cagr_value:.1f}%</sub>"
                )

                period_buttons.append(
                    {
                        "label": period,
                        "method": "update",
                        "args": [{"visible": visibility}, {"title": dynamic_title}],
                    }
                )

            # Set initial title with default period CAGR
            default_cagr = cagr_data.get(default_period, 0)
            initial_title = (
                f"Portfolio Performance<br><sub>CAGR: {default_cagr:.1f}%</sub>"
            )

            fig.update_layout(
                title=initial_title,
                xaxis_title="Date",
                yaxis_title="Portfolio Return (%)",
                updatemenus=[
                    {
                        "type": "buttons",
                        "direction": "right",
                        "x": 0.7,
                        "y": 1.1,
                        "buttons": period_buttons,
                    }
                ],
                **self.layout_config,
            )
        else:
            # Single period chart
            cagr_value = cagr_data.get(default_period, 0)
            fig.update_layout(
                title=f"Portfolio Performance<br><sub>CAGR: {cagr_value:.1f}%</sub>",
                xaxis_title="Date",
                yaxis_title="Portfolio Return (%)",
                **self.layout_config,
            )

        return fig

    def create_drawdown_chart(self, data: dict) -> go.Figure:
        """Create drawdown chart with dynamic stats and INR hover tooltips."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No drawdown data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        all_dd_stats = {}

        for period in periods:
            period_data = data[period]
            if "equity" not in period_data or period_data["equity"].empty:
                continue

            equity_df = period_data["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])

            # Calculate drawdown percentage and INR values
            equity_df["Peak"] = equity_df["Equity"].expanding().max()
            equity_df["Drawdown_Pct"] = (
                (equity_df["Equity"] / equity_df["Peak"]) - 1
            ) * 100
            equity_df["Drawdown_INR"] = equity_df["Equity"] - equity_df["Peak"]

            # Calculate stats for this period
            max_dd = equity_df["Drawdown_Pct"].min()
            mean_dd = equity_df["Drawdown_Pct"].mean()
            median_dd = equity_df["Drawdown_Pct"].median()

            all_dd_stats[period] = {
                "max_dd": max_dd,
                "mean_dd": mean_dd,
                "median_dd": median_dd,
            }

            fig.add_trace(
                go.Scatter(
                    x=equity_df["Date"],
                    y=equity_df["Drawdown_Pct"],
                    mode="lines",
                    name=f"Drawdown {period}",
                    line={"color": self.colors["loss"], "width": 3},
                    visible=True if period == default_period else False,
                    fill="tonexty",
                    fillcolor="rgba(220, 38, 38, 0.15)",
                    hovertemplate="Date: %{x}<br>Portfolio Drawdown: %{y:.2f}%<br>Drawdown Amount: ₹%{customdata:,.0f}<extra></extra>",
                    customdata=equity_df["Drawdown_INR"],
                )
            )

        # Create period buttons with dynamic stats updates
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(periods))]

            # Create dynamic title with stats for this period
            if period in all_dd_stats:
                stats = all_dd_stats[period]
                dynamic_title = f"Portfolio Drawdown<br><sub>Max: {stats['max_dd']:.2f}% | Mean: {stats['mean_dd']:.2f}% | Median: {stats['median_dd']:.2f}%</sub>"
            else:
                dynamic_title = "Portfolio Drawdown"

            period_buttons.append(
                {
                    "label": period,
                    "method": "update",
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                }
            )

        # Create title with default stats
        if default_period in all_dd_stats:
            default_stats = all_dd_stats[default_period]
            title_with_stats = f"Portfolio Drawdown<br><sub>Max: {default_stats['max_dd']:.2f}% | Mean: {default_stats['mean_dd']:.2f}% | Median: {default_stats['median_dd']:.2f}%</sub>"
        else:
            title_with_stats = "Portfolio Drawdown"

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Trading Period",
            yaxis_title="Portfolio Drawdown (%)",
            **self.layout_config,
            height=450,
            updatemenus=(
                [
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.02,
                        "y": 1.12,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": period_buttons,
                    }
                ]
                if len(periods) > 1
                else []
            ),
            annotations=(
                [
                    {
                        "text": "Period:",
                        "x": 0.01,
                        "y": 1.15,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    }
                ]
                if len(periods) > 1
                else []
            ),
        )

        return fig

    def create_monthly_pnl_chart(self, data: dict) -> go.Figure:
        """Create monthly P&L chart with realized/unrealized breakdown from monthly equity curve data."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No monthly data available")

        # Try to load monthly equity curve data
        monthly_data = {}
        for period in periods:
            folder_path = self.report_dir
            monthly_file = f"portfolio_monthly_equity_curve_{period}.csv"
            monthly_path = folder_path / monthly_file

            if monthly_path.exists():
                try:
                    monthly_df = pd.read_csv(monthly_path)
                    monthly_data[period] = monthly_df
                except Exception as e:
                    print(f"Error loading monthly data for {period}: {e}")

        if not monthly_data:
            return self._create_empty_chart("No monthly equity curve data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        all_monthly_stats = {}

        for period in periods:
            if period not in monthly_data:
                continue

            monthly_df = monthly_data[period].copy()

            # Convert Month to readable format
            monthly_df["Month_Display"] = pd.to_datetime(
                monthly_df["Month"], format="%Y-%m"
            ).dt.strftime("%b %Y")

            # Calculate stats
            mean_realized = monthly_df["Realized %"].mean()
            mean_unrealized = monthly_df["Unrealized %"].mean()
            mean_total = monthly_df["Total Return %"].mean()

            all_monthly_stats[period] = {
                "mean_realized": mean_realized,
                "mean_unrealized": mean_unrealized,
                "mean_total": mean_total,
            }

            # Create stacked bars for gains and losses
            for i, row in monthly_df.iterrows():
                realized_pct = row["Realized %"]
                unrealized_pct = row["Unrealized %"]

                if realized_pct >= 0:
                    # Positive realized (dark green)
                    fig.add_trace(
                        go.Bar(
                            x=[row["Month_Display"]],
                            y=[realized_pct],
                            name="Realized Gain",
                            marker_color=self.colors["winners"],  # Dark green
                            visible=True if period == default_period else False,
                            hovertemplate="Month: %{x}<br>Realized Gain: %{y:.2f}%<extra></extra>",
                            showlegend=False,
                            width=0.8,
                        )
                    )
                else:
                    # Negative realized (dark red)
                    fig.add_trace(
                        go.Bar(
                            x=[row["Month_Display"]],
                            y=[realized_pct],
                            name="Realized Loss",
                            marker_color=self.colors["losers"],  # Dark red
                            visible=True if period == default_period else False,
                            hovertemplate="Month: %{x}<br>Realized Loss: %{y:.2f}%<extra></extra>",
                            showlegend=False,
                            width=0.8,
                        )
                    )

                if unrealized_pct >= 0:
                    # Positive unrealized (light green) - stacked on top
                    fig.add_trace(
                        go.Bar(
                            x=[row["Month_Display"]],
                            y=[unrealized_pct],
                            name="Unrealized Gain",
                            marker_color=self.colors["light_profit"],  # Light green
                            visible=True if period == default_period else False,
                            hovertemplate="Month: %{x}<br>Unrealized Gain: %{y:.2f}%<extra></extra>",
                            showlegend=False,
                            width=0.8,
                            base=[realized_pct] if realized_pct >= 0 else [0],
                        )
                    )
                else:
                    # Negative unrealized (light red) - stacked on bottom
                    fig.add_trace(
                        go.Bar(
                            x=[row["Month_Display"]],
                            y=[unrealized_pct],
                            name="Unrealized Loss",
                            marker_color=self.colors["light_loss"],  # Light red
                            visible=True if period == default_period else False,
                            hovertemplate="Month: %{x}<br>Unrealized Loss: %{y:.2f}%<extra></extra>",
                            showlegend=False,
                            width=0.8,
                            base=[realized_pct] if realized_pct < 0 else [0],
                        )
                    )

        # Create period buttons with dynamic stats updates
        period_buttons = []
        traces_per_period = (
            len(monthly_data[default_period]) * 2
        )  # 2 traces per month (realized + unrealized)

        for i, period in enumerate(periods):
            if period not in monthly_data:
                continue

            visibility = [False] * len(fig.data)
            # Show traces for this period
            start_idx = i * traces_per_period
            end_idx = start_idx + traces_per_period
            for idx in range(start_idx, min(end_idx, len(fig.data))):
                visibility[idx] = True

            # Create dynamic title with stats for this period
            if period in all_monthly_stats:
                stats = all_monthly_stats[period]
                dynamic_title = f"Monthly Portfolio Returns - Realized vs Unrealized<br><sub>Avg Realized: {stats['mean_realized']:.2f}% | Avg Unrealized: {stats['mean_unrealized']:.2f}% | Avg Total: {stats['mean_total']:.2f}%</sub>"
            else:
                dynamic_title = "Monthly Portfolio Returns - Realized vs Unrealized"

            period_buttons.append(
                {
                    "label": period,
                    "method": "update",
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                }
            )

        # Create title with default stats
        if default_period in all_monthly_stats:
            default_stats = all_monthly_stats[default_period]
            title_with_stats = f"Monthly Portfolio Returns - Realized vs Unrealized<br><sub>Avg Realized: {default_stats['mean_realized']:.2f}% | Avg Unrealized: {default_stats['mean_unrealized']:.2f}% | Avg Total: {default_stats['mean_total']:.2f}%</sub>"
        else:
            title_with_stats = "Monthly Portfolio Returns - Realized vs Unrealized"

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Month",
            yaxis_title="Monthly Return (%)",
            template="plotly_white",
            margin={"l": 80, "r": 50, "t": 150, "b": 80},
            title_x=0.5,
            title_font_size=16,
            autosize=True,
            font={"size": 12},
            height=600,
            showlegend=False,
            bargap=0.2,  # Less space between bars
            xaxis={
                "tickangle": 0,  # Horizontal text
                "dtick": "M3",  # Show every 3 months (quarterly)
                "tickformat": "%b %Y",  # Format as "Jan 2024"
            },
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "showactive": True,
                    "x": 0.02,
                    "y": 1.12,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": period_buttons,
                }
            ],
            annotations=[
                {
                    "text": "Period:",
                    "x": 0.01,
                    "y": 1.15,
                    "xref": "paper",
                    "yref": "paper",
                    "xanchor": "right",
                    "yanchor": "middle",
                    "showarrow": False,
                }
            ],
        )

        return fig

    def create_exposure_chart(self, data: dict) -> go.Figure:
        """Create exposure chart using Avg exposure % column with dynamic stats."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No exposure data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        all_exposure_stats = {}

        for period in periods:
            period_data = data[period]
            if "equity" not in period_data or period_data["equity"].empty:
                continue

            equity_df = period_data["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])

            # Use Avg exposure % column directly from CSV
            if "Avg exposure %" in equity_df.columns:
                exposure_pct = equity_df["Avg exposure %"]
                # Calculate corresponding INR values based on equity
                exposure_inr = (exposure_pct / 100) * equity_df["Equity"]
            else:
                # Fallback: calculate based on deployment assumption
                exposure_pct = pd.Series([95.0] * len(equity_df))  # 95% default
                exposure_inr = equity_df["Equity"] * 0.95

            # Calculate stats for this period
            mean_exposure_pct = exposure_pct.mean()
            median_exposure_pct = exposure_pct.median()
            mean_exposure_inr = exposure_inr.mean()
            median_exposure_inr = exposure_inr.median()

            all_exposure_stats[period] = {
                "mean_pct": mean_exposure_pct,
                "median_pct": median_exposure_pct,
                "mean_inr": mean_exposure_inr,
                "median_inr": median_exposure_inr,
            }

            fig.add_trace(
                go.Scatter(
                    x=equity_df["Date"],
                    y=exposure_pct,
                    mode="lines",
                    name=f"Exposure {period}",
                    line={"color": self.colors["exposure"], "width": 3},
                    visible=True if period == default_period else False,
                    hovertemplate="Date: %{x}<br>Exposure: %{y:.1f}%<br>Amount: ₹%{customdata:,.0f}<extra></extra>",
                    customdata=exposure_inr,
                )
            )

        # Create period buttons with dynamic stats updates
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(periods))]

            # Create dynamic title with stats for this period
            if period in all_exposure_stats:
                stats = all_exposure_stats[period]
                dynamic_title = f"Portfolio Exposure<br><sub>Mean: {stats['mean_pct']:.1f}% | Median: {stats['median_pct']:.1f}%</sub>"
            else:
                dynamic_title = "Portfolio Exposure"

            period_buttons.append(
                {
                    "label": period,
                    "method": "update",
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                }
            )

        # Create title with default stats
        if default_period in all_exposure_stats:
            default_stats = all_exposure_stats[default_period]
            title_with_stats = f"Portfolio Exposure<br><sub>Mean: {default_stats['mean_pct']:.1f}% | Median: {default_stats['median_pct']:.1f}%</sub>"
        else:
            title_with_stats = "Portfolio Exposure"

        # Add reference line at 100% exposure
        fig.add_hline(
            y=100,
            line_dash="dot",
            line_color="gray",
            opacity=0.5,
            annotation_text="100% Target",
            annotation_position="right",
        )

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Trading Period",
            yaxis_title="Portfolio Exposure (%)",
            **self.layout_config,
            height=450,
            updatemenus=(
                [
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.02,
                        "y": 1.12,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": period_buttons,
                    }
                ]
                if len(periods) > 1
                else []
            ),
            annotations=(
                [
                    {
                        "text": "Period:",
                        "x": 0.01,
                        "y": 1.15,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    }
                ]
                if len(periods) > 1
                else []
            ),
        )

        return fig

    def create_trade_return_vs_holding_days(self, data: dict) -> go.Figure:
        """Create trade return vs holding days with period toggles and dynamic stats."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No trade data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        all_trade_stats = {}

        for period in periods:
            period_data = data[period]
            if "trades" not in period_data or period_data["trades"].empty:
                continue

            trades_df = period_data["trades"].copy()

            # Filter for exit trades only
            exit_trades = trades_df[
                trades_df["Type"].str.contains("Exit", na=False)
            ].copy()

            if exit_trades.empty:
                continue

            # Parse dates and calculate holding periods
            try:
                trade_periods = []
                returns = []

                for trade_num in exit_trades["Trade #"].unique():
                    trade_rows = trades_df[trades_df["Trade #"] == trade_num].copy()
                    trade_rows["Date/Time"] = pd.to_datetime(trade_rows["Date/Time"])
                    trade_rows = trade_rows.sort_values("Date/Time")

                    if len(trade_rows) >= 2:
                        entry_date = trade_rows.iloc[0]["Date/Time"]
                        exit_date = trade_rows.iloc[-1]["Date/Time"]
                        holding_days = (exit_date - entry_date).days

                        # Get return percentage
                        exit_row = trade_rows.iloc[-1]
                        if "Net P&L %" in exit_row:
                            pnl_str = str(exit_row["Net P&L %"])
                            if "%" in pnl_str:
                                trade_return = float(pnl_str.replace("%", ""))
                            else:
                                trade_return = float(pnl_str)
                        else:
                            pnl_inr = exit_row.get("Net P&L INR", 0)
                            trade_return = (
                                pnl_inr / 5000
                            ) * 100  # Based on 5k position size

                        if holding_days > 0 and holding_days < 365:
                            trade_periods.append(holding_days)
                            returns.append(trade_return)

                if len(trade_periods) < 5:
                    continue

                trade_periods = np.array(trade_periods)
                returns = np.array(returns)

                # Calculate stats for this period
                mean_return = np.mean(returns)
                median_return = np.median(returns)
                mean_days = np.mean(trade_periods)
                median_days = np.median(trade_periods)

                all_trade_stats[period] = {
                    "mean_return": mean_return,
                    "median_return": median_return,
                    "mean_days": mean_days,
                    "median_days": median_days,
                }

                # Color code by profit/loss
                colors = ["green" if r > 0 else "red" for r in returns]

                fig.add_trace(
                    go.Scatter(
                        x=trade_periods,
                        y=returns,
                        mode="markers",
                        name=f"Trades {period}",
                        marker={
                            "color": colors,
                            "size": 6,
                            "opacity": 0.7,
                            "line": {"width": 1, "color": "white"},
                        },
                        visible=True if period == default_period else False,
                        hovertemplate="Holding Days: %{x}<br>Return: %{y:.2f}%<extra></extra>",
                    )
                )

                # Add trend line
                if len(trade_periods) > 10:
                    z = np.polyfit(trade_periods, returns, 1)
                    p = np.poly1d(z)
                    x_trend = np.linspace(trade_periods.min(), trade_periods.max(), 100)
                    y_trend = p(x_trend)

                    fig.add_trace(
                        go.Scatter(
                            x=x_trend,
                            y=y_trend,
                            mode="lines",
                            name=f"Trend {period}",
                            line={
                                "color": self.colors["edge"],
                                "width": 3,
                                "dash": "dash",
                            },
                            visible=True if period == default_period else False,
                            hovertemplate="Holding Days: %{x}<br>Trend Return: %{y:.2f}%<extra></extra>",
                        )
                    )

            except Exception as e:
                print(f"Error processing trade periods for {period}: {e}")
                continue

        # Create period buttons with dynamic stats updates
        period_buttons = []
        traces_per_period = 2  # Each period has scatter + trend line

        for i, period in enumerate(periods):
            visibility = [False] * len(fig.data)
            start_idx = i * traces_per_period
            end_idx = start_idx + traces_per_period
            for j in range(start_idx, min(end_idx, len(fig.data))):
                visibility[j] = True

            # Create dynamic title with stats for this period
            if period in all_trade_stats:
                stats = all_trade_stats[period]
                dynamic_title = f"Trade Return vs Holding Days<br><sub>Mean Return: {stats['mean_return']:.2f}% | Median Return: {stats['median_return']:.2f}% | Mean Days: {stats['mean_days']:.0f} | Median Days: {stats['median_days']:.0f}</sub>"
            else:
                dynamic_title = "Trade Return vs Holding Days"

            period_buttons.append(
                {
                    "label": period,
                    "method": "update",
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                }
            )

        # Create title with default stats
        if default_period in all_trade_stats:
            default_stats = all_trade_stats[default_period]
            title_with_stats = f"Trade Return vs Holding Days<br><sub>Mean Return: {default_stats['mean_return']:.2f}% | Median Return: {default_stats['median_return']:.2f}% | Mean Days: {default_stats['mean_days']:.0f} | Median Days: {default_stats['median_days']:.0f}</sub>"
        else:
            title_with_stats = "Trade Return vs Holding Days"

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Trade Duration (Days)",
            yaxis_title="Individual Trade Return (%)",
            **self.layout_config,
            height=500,
            updatemenus=(
                [
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.02,
                        "y": 1.12,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": period_buttons,
                    }
                ]
                if len(periods) > 1
                else []
            ),
            annotations=(
                [
                    {
                        "text": "Period:",
                        "x": 0.01,
                        "y": 1.15,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    }
                ]
                if len(periods) > 1
                else []
            ),
        )

        return fig

    def create_mae_analysis(self, data: dict) -> go.Figure:
        """Create Maximum Adverse Excursion with Winners/Losers toggle buttons."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No trade data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()
        suggested_stop_rounded = 2.5  # Default R value

        for period in periods:
            period_data = data[period]
            if "trades" not in period_data or period_data["trades"].empty:
                continue

            trades_df = period_data["trades"].copy()

            # Filter exit trades
            exit_trades = trades_df[trades_df["Type"].str.contains("Exit", na=False)]

            if exit_trades.empty:
                continue

            # Calculate MAE for each trade
            mae_winners = []
            mae_losers = []

            for _, exit_row in exit_trades.iterrows():
                try:
                    # Get MAE data
                    drawdown_inr = abs(exit_row.get("Drawdown INR", 0))
                    position_value = exit_row.get("Position size (value)", 5000)
                    net_pnl = exit_row.get("Net P&L INR", 0)

                    # Calculate MAE in R units (simplified - using 2% as 1R)
                    if position_value > 0 and drawdown_inr > 0:
                        mae_pct = (drawdown_inr / position_value) * 100
                        mae_r = mae_pct / 2.0  # 2% = 1R

                        # Classify as winner or loser
                        if net_pnl > 0:
                            mae_winners.append(mae_r)
                        else:
                            mae_losers.append(mae_r)

                except Exception:
                    continue

            # Create histograms for winners and losers
            if mae_winners:
                fig.add_trace(
                    go.Histogram(
                        x=mae_winners,
                        nbinsx=20,
                        name=f"Winners {period}",
                        marker_color=self.colors["winners"],
                        opacity=0.7,
                        visible=True if period == default_period else False,
                        hovertemplate="MAE (R): %{x:.1f}<br>Count: %{y}<extra></extra>",
                    )
                )

            if mae_losers:
                fig.add_trace(
                    go.Histogram(
                        x=mae_losers,
                        nbinsx=20,
                        name=f"Losers {period}",
                        marker_color=self.colors["losers"],
                        opacity=0.7,
                        visible=False,  # Start with losers hidden
                        hovertemplate="MAE (R): %{x:.1f}<br>Count: %{y}<extra></extra>",
                    )
                )

            # Calculate suggested stop for winners (85th percentile)
            if mae_winners and period == default_period:
                suggested_stop = np.percentile(mae_winners, 85)
                suggested_stop_rounded = round(suggested_stop, 1)

        # Create Winners/Losers toggle buttons
        winners_losers_buttons = [
            {
                "label": "Winners",
                "method": "update",
                "args": [
                    {
                        "visible": [
                            True if "Winners" in trace.name else False
                            for trace in fig.data
                        ]
                    },
                ],
            },
            {
                "label": "Losers",
                "method": "update",
                "args": [
                    {
                        "visible": [
                            True if "Losers" in trace.name else False
                            for trace in fig.data
                        ]
                    },
                ],
            },
            {
                "label": "Both",
                "method": "update",
                "args": [
                    {"visible": [True for _ in fig.data]},
                ],
            },
        ]

        # Add reference lines and suggested stop
        if mae_winners:
            fig.add_vline(
                x=suggested_stop_rounded,
                line_dash="dash",
                line_color="blue",
                opacity=0.8,
                annotation_text=f"Suggested Stop: {suggested_stop_rounded}R",
                annotation_position="top right",
            )

        # Simple title
        title_text = f"Maximum Adverse Excursion Analysis<br><sub>Suggested Stop Loss: {suggested_stop_rounded}R</sub>"

        fig.update_layout(
            title=title_text,
            xaxis_title="Maximum Adverse Excursion (R Units)",
            yaxis_title="Number of Trades",
            **self.layout_config,
            height=400,
            barmode="overlay",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "showactive": True,
                    "x": 0.02,
                    "y": 1.02,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": winners_losers_buttons,
                }
            ],
        )

        return fig

    def create_enhanced_win_rate_analysis(self, data: dict) -> go.Figure:
        """Create Win Rate chart with period toggles, dynamic stats, and cleaned titles."""

        periods = list(data.keys())
        if not periods:
            return self._create_empty_chart("No trade data available")

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )

        fig = go.Figure()

        all_win_rate_stats = {}

        for period in periods:
            period_data = data[period]
            if "trades" not in period_data or period_data["trades"].empty:
                continue

            trades_df = period_data["trades"].copy()

            # Filter exit trades
            exit_trades = trades_df[trades_df["Type"].str.contains("Exit", na=False)]

            if exit_trades.empty:
                continue

            # Calculate comprehensive metrics by symbol
            def calculate_symbol_metrics(group):
                total_trades = len(group)
                winning_trades = (group["Net P&L INR"] > 0).sum()
                losing_trades = (group["Net P&L INR"] < 0).sum()

                win_rate = (
                    (winning_trades / total_trades * 100) if total_trades > 0 else 0
                )

                # Profit factor calculation
                gross_profit = (
                    group[group["Net P&L INR"] > 0]["Net P&L INR"].sum()
                    if winning_trades > 0
                    else 0
                )
                gross_loss = (
                    abs(group[group["Net P&L INR"] < 0]["Net P&L INR"].sum())
                    if losing_trades > 0
                    else 1
                )
                profit_factor = (
                    gross_profit / gross_loss if gross_loss > 0 else gross_profit
                )
                profit_factor_actual = profit_factor  # Store actual value
                profit_factor_display = min(profit_factor, 10)  # Cap display at 10

                # IRR estimation (simplified annualized return)
                avg_return_pct = (
                    group["Net P&L INR"].mean() / 5000
                ) * 100  # Based on 5k position
                irr_pct = avg_return_pct * 252  # Annualized
                irr_actual = irr_pct  # Store actual value
                irr_display = np.clip(irr_pct, -100, 100)  # Cap display at ±100%

                return pd.Series(
                    {
                        "Win_Rate": win_rate,
                        "Profit_Factor_Display": profit_factor_display,
                        "Profit_Factor_Actual": profit_factor_actual,
                        "IRR_Display": irr_display,
                        "IRR_Actual": irr_actual,
                        "Total_Trades": total_trades,
                        "Total_PnL": group["Net P&L INR"].sum(),
                    }
                )

            symbol_stats = exit_trades.groupby("Symbol").apply(calculate_symbol_metrics)

            # Filter symbols with more than 5 trades
            symbol_stats = symbol_stats[symbol_stats["Total_Trades"] > 5]

            if symbol_stats.empty:
                continue

            # Calculate overall stats for this period
            mean_win_rate = symbol_stats["Win_Rate"].mean()
            median_win_rate = symbol_stats["Win_Rate"].median()

            all_win_rate_stats[period] = {
                "mean_wr": mean_win_rate,
                "median_wr": median_win_rate,
            }

            # Create three sets of data with different sorting
            win_rate_sorted = symbol_stats.sort_values("Win_Rate", ascending=False)
            irr_sorted = symbol_stats.sort_values(
                "IRR_Actual", ascending=False
            )  # Sort by actual IRR
            pf_sorted = symbol_stats.sort_values(
                "Profit_Factor_Actual", ascending=False
            )  # Sort by actual PF

            # Win Rate traces
            colors_wr = [
                "#2D5016" if wr >= 50 else "#8B0000"
                for wr in win_rate_sorted["Win_Rate"]
            ]
            fig.add_trace(
                go.Bar(
                    x=win_rate_sorted.index,
                    y=win_rate_sorted["Win_Rate"],
                    name=f"Win Rate % {period}",
                    marker_color=colors_wr,
                    visible=True if period == default_period else False,
                    customdata=list(
                        zip(
                            win_rate_sorted["Total_Trades"],
                            win_rate_sorted["Total_PnL"],
                            strict=True,
                        )
                    ),
                    hovertemplate="Symbol: %{x}<br>Win Rate: %{y:.1f}%<br>Total Trades: %{customdata[0]}<br>Total P&L: ₹%{customdata[1]:,.0f}<extra></extra>",
                )
            )

            # IRR% traces (sorted by IRR, showing actual values in hover)
            colors_irr = [
                "#2E8B57" if irr > 0 else "#DC143C" for irr in irr_sorted["IRR_Display"]
            ]
            fig.add_trace(
                go.Bar(
                    x=irr_sorted.index,
                    y=irr_sorted["IRR_Display"],
                    name=f"IRR % {period}",
                    marker_color=colors_irr,
                    visible=False,
                    customdata=list(
                        zip(
                            irr_sorted["IRR_Actual"],
                            irr_sorted["Win_Rate"],
                            irr_sorted["Total_Trades"],
                            strict=True,
                        )
                    ),
                    hovertemplate="Symbol: %{x}<br>IRR: %{customdata[0]:.1f}%<br>Win Rate: %{customdata[1]:.1f}%<br>Total Trades: %{customdata[2]}<extra></extra>",
                )
            )

            # Profit Factor traces (sorted by PF, showing actual values in hover)
            colors_pf = [
                "#1E90FF" if pf > 1 else "#FF6347"
                for pf in pf_sorted["Profit_Factor_Display"]
            ]
            fig.add_trace(
                go.Bar(
                    x=pf_sorted.index,
                    y=pf_sorted["Profit_Factor_Display"],
                    name=f"Profit Factor {period}",
                    marker_color=colors_pf,
                    visible=False,
                    customdata=list(
                        zip(
                            pf_sorted["Profit_Factor_Actual"],
                            pf_sorted["Win_Rate"],
                            strict=True,
                        )
                    ),
                    hovertemplate="Symbol: %{x}<br>Profit Factor: %{customdata[0]:.2f}<br>Win Rate: %{customdata[1]:.1f}%<extra></extra>",
                )
            )

        # Create metric toggle buttons with better visibility logic
        metric_buttons = [
            {
                "label": "Win Rate %",
                "method": "update",
                "args": [
                    {"visible": ["Win Rate" in trace.name for trace in fig.data]},
                    {
                        "yaxis": {"title": "Win Rate (%)"},
                        "shapes": [
                            {
                                "type": "line",
                                "x0": 0,
                                "x1": 1,
                                "xref": "paper",
                                "y0": 50,
                                "y1": 50,
                                "line": {"dash": "dash", "color": "gray"},
                            }
                        ],
                    },
                ],
            },
            {
                "label": "IRR %",
                "method": "update",
                "args": [
                    {"visible": ["IRR" in trace.name for trace in fig.data]},
                    {
                        "yaxis": {
                            "title": "Internal Rate of Return (%)",
                            "range": [-100, 100],
                        },
                        "shapes": [
                            {
                                "type": "line",
                                "x0": 0,
                                "x1": 1,
                                "xref": "paper",
                                "y0": 0,
                                "y1": 0,
                                "line": {"dash": "dash", "color": "gray"},
                            }
                        ],
                    },
                ],
            },
            {
                "label": "Profit Factor",
                "method": "update",
                "args": [
                    {"visible": ["Profit Factor" in trace.name for trace in fig.data]},
                    {
                        "yaxis": {"title": "Profit Factor", "range": [0, 10]},
                        "shapes": [
                            {
                                "type": "line",
                                "x0": 0,
                                "x1": 1,
                                "xref": "paper",
                                "y0": 1,
                                "y1": 1,
                                "line": {"dash": "dash", "color": "gray"},
                            }
                        ],
                    },
                ],
            },
        ]

        # Create period buttons with better visibility logic
        period_buttons = []

        for i, period in enumerate(periods):
            # Create dynamic title with stats for this period
            if period in all_win_rate_stats:
                stats = all_win_rate_stats[period]
                dynamic_title = f"Win Rate by Symbol<br><sub>Mean: {stats['mean_wr']:.1f}% | Median: {stats['median_wr']:.1f}%</sub>"
            else:
                dynamic_title = "Win Rate by Symbol"

            # Show only the Win Rate traces for this period by default
            visibility = [
                "Win Rate" in trace.name and period in trace.name for trace in fig.data
            ]

            period_buttons.append(
                {
                    "label": period,
                    "method": "update",
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                }
            )

        # Create title with default stats
        if default_period in all_win_rate_stats:
            default_stats = all_win_rate_stats[default_period]
            title_with_stats = f"Win Rate by Symbol<br><sub>Mean: {default_stats['mean_wr']:.1f}% | Median: {default_stats['median_wr']:.1f}%</sub>"
        else:
            title_with_stats = "Win Rate by Symbol"

        # Update layout config for this chart to remove legend
        layout_config = self.layout_config.copy()
        layout_config["showlegend"] = (
            False  # Remove legends since we have period toggles
        )

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Trading Symbol",
            yaxis_title="Win Rate (%)",
            **layout_config,
            height=500,
            updatemenus=(
                [
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.02,
                        "y": 1.25,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": metric_buttons,
                    },
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.35,
                        "y": 1.25,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": period_buttons,
                    },
                ]
                if len(periods) > 1
                else [
                    {
                        "type": "buttons",
                        "direction": "right",
                        "showactive": True,
                        "x": 0.02,
                        "y": 1.20,
                        "xanchor": "left",
                        "yanchor": "top",
                        "buttons": metric_buttons,
                    }
                ]
            ),
            annotations=(
                [
                    {
                        "text": "Metric:",
                        "x": 0.01,
                        "y": 1.28,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    },
                    {
                        "text": "Period:",
                        "x": 0.34,
                        "y": 1.28,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    },
                ]
                if len(periods) > 1
                else [
                    {
                        "text": "Metric:",
                        "x": 0.01,
                        "y": 1.23,
                        "xref": "paper",
                        "yref": "paper",
                        "showarrow": False,
                    }
                ]
            ),
        )

        # Add reference line for win rate
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)

        # Rotate x-axis labels for better readability
        fig.update_xaxes(tickangle=45)

        return fig

    def generate_charts(self, data: dict) -> dict:
        """Generate all charts for the dashboard."""
        charts = {
            "equity": self.create_equity_dashboard(data),
            "drawdown": self.create_drawdown_chart(data),
            "monthly_pnl": self.create_monthly_pnl_chart(data),
            "exposure": self.create_exposure_chart(data),
            "trade_return_days": self.create_trade_return_vs_holding_days(data),
            "mae_analysis": self.create_mae_analysis(data),
            "win_rate": self.create_enhanced_win_rate_analysis(data),
        }
        return charts

    def calculate_portfolio_metrics(self, data: dict) -> dict:
        """Calculate key portfolio metrics for display."""
        metrics = {}

        # Use the longest period available for metrics
        periods = list(data.keys())
        if not periods:
            return {}

        default_period = max(
            periods, key=lambda x: int(x[:-1]) if x[:-1].isdigit() else 0
        )
        period_data = data[default_period]

        # Try to use existing portfolio metrics first
        if "metrics" in period_data:
            existing_metrics = period_data["metrics"]
            metrics = {
                "total_return": existing_metrics.get("Net P&L %", 0),
                "cagr": existing_metrics.get("Equity CAGR %", 0),
                "max_drawdown": existing_metrics.get("Max equity drawdown %", 0),
                "win_rate": existing_metrics.get("Profitable trades %", 0),
                "profit_factor": existing_metrics.get("Profit factor", 0),
                "total_trades": existing_metrics.get("Total trades", 0),
                "period": default_period,
                "annual_volatility": 0,  # Not available in CSV, would need calculation
                "sharpe_ratio": 0,  # Not available in CSV, would need calculation
            }
            return metrics

        # Fallback to calculations if no existing metrics (legacy code)
        if "equity" in period_data and not period_data["equity"].empty:
            equity_df = period_data["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])

            # Basic calculations
            initial_equity = equity_df["Equity"].iloc[0]
            final_equity = equity_df["Equity"].iloc[-1]
            total_return = ((final_equity / initial_equity) - 1) * 100

            # CAGR calculation
            days = (equity_df["Date"].iloc[-1] - equity_df["Date"].iloc[0]).days
            years = days / 365.25
            cagr = (
                ((final_equity / initial_equity) ** (1 / years) - 1) * 100
                if years > 0
                else 0
            )

            # Drawdown calculations
            equity_df["Peak"] = equity_df["Equity"].expanding().max()
            equity_df["Drawdown_Pct"] = (
                (equity_df["Equity"] / equity_df["Peak"]) - 1
            ) * 100
            max_drawdown = equity_df["Drawdown_Pct"].min()

            # Volatility (annualized)
            equity_df["Daily_Return"] = equity_df["Equity"].pct_change()
            daily_vol = equity_df["Daily_Return"].std()
            annual_vol = daily_vol * (252**0.5) * 100

            # Sharpe ratio (assuming 6% risk-free rate)
            risk_free_rate = 6.0
            sharpe_ratio = (cagr - risk_free_rate) / annual_vol if annual_vol > 0 else 0

            metrics = {
                "total_return": total_return,
                "cagr": cagr,
                "max_drawdown": max_drawdown,
                "annual_volatility": annual_vol,
                "sharpe_ratio": sharpe_ratio,
                "period": default_period,
            }

        # Add trade metrics if available
        if "trades" in period_data and not period_data["trades"].empty:
            trades_df = period_data["trades"]
            if "Net P&L INR" in trades_df.columns:
                # Win rate calculation
                exit_trades = trades_df[trades_df.get("Type", "") == "Exit"]
                if not exit_trades.empty:
                    winning_trades = exit_trades[exit_trades["Net P&L INR"] > 0]
                    win_rate = (len(winning_trades) / len(exit_trades)) * 100

                    # Profit factor
                    gross_profit = (
                        winning_trades["Net P&L INR"].sum()
                        if len(winning_trades) > 0
                        else 0
                    )
                    gross_loss = abs(
                        exit_trades[exit_trades["Net P&L INR"] < 0]["Net P&L INR"].sum()
                    )
                    profit_factor = (
                        gross_profit / gross_loss if gross_loss > 0 else float("inf")
                    )

                    metrics.update(
                        {
                            "win_rate": win_rate,
                            "profit_factor": profit_factor,
                            "total_trades": len(exit_trades),
                        }
                    )

        return metrics

    def create_improved_metrics_html(self, strategy_metrics: dict) -> str:
        """Create improved metrics panel HTML matching improved_dashboard.py design."""
        return f"""
        <div class="enhanced-metrics-panel">
            <div class="period-selector">
                <button onclick="showMetrics('1Y')" id="btn-1Y" class="period-btn">1Y</button>
                <button onclick="showMetrics('3Y')" id="btn-3Y" class="period-btn">3Y</button>
                <button onclick="showMetrics('5Y')" id="btn-5Y" class="period-btn active">5Y</button>
            </div>

            <!-- 5Y Metrics (default) -->
            <div id="metrics-5Y" class="metrics-grid active">
                <div class="metric-card highlight"><h3>{strategy_metrics.get('5Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('5Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('5Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('5Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>

            <!-- 3Y Metrics -->
            <div id="metrics-3Y" class="metrics-grid">
                <div class="metric-card highlight"><h3>{strategy_metrics.get('3Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('3Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('3Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('3Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>

            <!-- 1Y Metrics -->
            <div id="metrics-1Y" class="metrics-grid">
                <div class="metric-card highlight"><h3>{strategy_metrics.get('1Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('1Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{strategy_metrics.get('1Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{strategy_metrics.get('1Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>
        </div>
        """

    def create_dashboard_html(
        self, data: dict, charts: dict, report_name: str = "Portfolio"
    ) -> str:
        """Create the complete HTML dashboard."""

        # Load strategy summary for comprehensive metrics
        summary_path = self.report_dir / "strategy_backtests_summary.csv"
        strategy_metrics = {}
        if summary_path.exists():
            try:
                summary_df = pd.read_csv(summary_path)
                for _, row in summary_df.iterrows():
                    period = row["Window"]
                    strategy_metrics[period] = {
                        "net_pnl": row["Net P&L %"],
                        "cagr": row["CAGR [%]"],
                        "irr": row["IRR [%]"],
                        "trades": row["# Trades"],
                        "win_rate": row["Win Rate [%]"],
                        "profit_factor": row["Profit Factor"],
                        "avg_exposure": row["Avg exposure %"],
                        "alpha": row["Alpha [%]"],
                        "beta": row["Beta"],
                        "avg_trade": row["Avg. Trade [%]"],
                        "best_trade": row["Best Trade [%]"],
                        "worst_trade": row["Worst Trade [%]"],
                        "max_trade_duration": row["Max. Trade Duration"],
                        "avg_trade_duration": row["Avg. Trade Duration"],
                        "max_drawdown": row["Max. Drawdown [%]"],
                        "max_dd_duration": row["Max. Drawdown Duration"],
                        "sharpe": row["Sharpe Ratio"],
                        "sortino": row["Sortino Ratio"],
                        "calmar": row["Calmar Ratio"],
                        "expectancy": row["Expectancy [%]"],
                        "sqn": row["SQN"],
                        "kelly": row["Kelly Criterion"],
                    }
            except Exception as e:
                print(f"Error loading strategy summary: {e}")

        # Convert charts to HTML (simplified approach)
        chart_htmls = {}

        for chart_name, fig in charts.items():
            try:
                chart_htmls[chart_name] = pio.to_html(
                    fig, include_plotlyjs=False, div_id=f"{chart_name}_chart"
                )
            except Exception as e:
                print(f"Error generating HTML for {chart_name}: {e}")
                chart_htmls[chart_name] = (
                    f'<div class="error-message">Error loading {chart_name} chart</div>'
                )

        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Final Fixed Dashboard - All Fixes Implemented</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8fafc;
            color: #333;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
            background: linear-gradient(135deg, #1e3a8a 0%, #374151 100%);
            color: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .metrics-row {{
            display: flex;
            flex-direction: column;
            gap: 20px;
            margin: 30px 0;
            padding: 20px;
            background: #e0f2fe;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-row {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            justify-content: space-between;
        }}
        .metric-card {{
            background: rgba(173, 216, 230, 0.2);
            padding: 12px;
            border-radius: 8px;
            text-align: center;
            flex: 1;
            min-width: 110px;
            max-width: 140px;
        }}
        .metric-card h3 {{
            margin: 0;
            font-size: 16px;
            color: #333;
            font-weight: bold;
        }}
        .metric-card p {{
            margin: 5px 0 0 0;
            font-size: 11px;
            color: #666;
            font-weight: 500;
        }}
        .period-btn {{
            background: #f0f0f0;
            border: 1px solid #ccc;
            padding: 8px 16px;
            margin: 0 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s ease;
        }}
        .period-btn.active {{
            background: #007acc;
            color: white;
            border-color: #007acc;
        }}
        .period-btn:hover {{
            background: #e0e0e0;
        }}
        .period-btn.active:hover {{
            background: #0066aa;
        }}
        .metrics-content {{
            display: none;
        }}
        .metrics-content.active {{
            display: block;
        }}
        .chart-container {{
            background: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart-full-width {{
            width: 100%;
        }}
        .error-message {{
            color: #dc2626;
            text-align: center;
            padding: 20px;
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
            margin: 10px 0;
        }}
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
        }}

        /* Enhanced Metrics Panel Styles */
        .enhanced-metrics-panel {{
            margin: 30px 0;
            padding: 25px;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border-radius: 15px;
            box-shadow: 0 8px 16px rgba(0,0,0,0.1);
            border: 1px solid #e2e8f0;
        }}

        .period-selector {{
            text-align: center;
            margin-bottom: 25px;
            padding: 15px;
            background: rgba(255,255,255,0.7);
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }}

        .period-btn {{
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            border: 2px solid #cbd5e1;
            padding: 12px 24px;
            margin: 0 8px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            color: #475569;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}

        .period-btn:hover {{
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e1 100%);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }}

        .period-btn.active {{
            background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
            color: white;
            border-color: #1d4ed8;
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(59, 130, 246, 0.4);
        }}

        .period-btn.active:hover {{
            background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
            box-shadow: 0 8px 16px rgba(59, 130, 246, 0.5);
        }}

        .metrics-grid {{
            display: none;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            animation: fadeIn 0.4s ease-in-out;
        }}

        .metrics-grid.active {{
            display: grid;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .metric-card {{
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 2px solid #e2e8f0;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
            overflow: hidden;
        }}

        .metric-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #06b6d4, #3b82f6, #8b5cf6);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 12px 24px rgba(0,0,0,0.15);
            border-color: #cbd5e1;
        }}

        .metric-card:hover::before {{
            opacity: 1;
        }}

        .metric-card.highlight {{
            background: linear-gradient(135deg, #fef3c7 0%, #fbbf24 30%, #f59e0b 100%);
            border-color: #f59e0b;
            box-shadow: 0 8px 16px rgba(245, 158, 11, 0.3);
        }}

        .metric-card.highlight::before {{
            background: linear-gradient(90deg, #f59e0b, #d97706, #92400e);
            opacity: 1;
        }}

        .metric-card.highlight:hover {{
            box-shadow: 0 16px 32px rgba(245, 158, 11, 0.4);
            transform: translateY(-6px);
        }}

        .metric-card h3 {{
            margin: 0 0 8px 0;
            font-size: 24px;
            font-weight: 700;
            color: #1f2937;
            line-height: 1.2;
        }}

        .metric-card.highlight h3 {{
            color: #92400e;
            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
        }}

        .metric-card p {{
            margin: 0;
            font-size: 13px;
            color: #6b7280;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .metric-card.highlight p {{
            color: #78350f;
        }}

        @media (max-width: 1200px) {{
            .metrics-grid {{
                grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 15px;
            }}
        }}

        @media (max-width: 768px) {{
            .enhanced-metrics-panel {{
                margin: 20px 0;
                padding: 20px;
            }}
            .metrics-grid {{
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 12px;
            }}
            .metric-card {{
                padding: 15px;
            }}
            .metric-card h3 {{
                font-size: 20px;
            }}
            .period-btn {{
                padding: 10px 16px;
                margin: 0 4px;
                font-size: 14px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{report_name} Dashboard</h1>
        <p>Professional Quantitative Trading Analysis</p>
        <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <!-- Key Portfolio Metrics -->
    {self.create_improved_metrics_html(strategy_metrics)}

    <!-- Portfolio Equity Curve -->
    <div class="chart-container chart-full-width">
        {chart_htmls["equity"]}
    </div>

    <!-- Portfolio Drawdown -->
    <div class="chart-container chart-full-width">
        {chart_htmls["drawdown"]}
    </div>

    <!-- Monthly P&L -->
    <div class="chart-container chart-full-width">
        {chart_htmls["monthly_pnl"]}
    </div>

    <!-- Portfolio Exposure -->
    <div class="chart-container chart-full-width">
        {chart_htmls["exposure"]}
    </div>

    <!-- Trade Return vs Holding Days -->
    <div class="chart-container chart-full-width">
        {chart_htmls["trade_return_days"]}
    </div>

    <!-- Maximum Adverse Excursion -->
    <div class="chart-container chart-full-width">
        {chart_htmls["mae_analysis"]}
    </div>

    <!-- Win Rate Analysis -->
    <div class="chart-container chart-full-width">
        {chart_htmls["win_rate"]}
    </div>

    <script>
    function showMetrics(period) {{
        // Hide all metrics grid sections with fade out
        document.querySelectorAll('.metrics-grid').forEach(function(el) {{
            if (el.classList.contains('active')) {{
                el.style.opacity = '0';
                setTimeout(function() {{
                    el.classList.remove('active');
                    el.style.opacity = '1';
                }}, 150);
            }}
        }});

        // Remove active class from all period buttons
        document.querySelectorAll('.period-btn').forEach(function(el) {{
            el.classList.remove('active');
        }});

        // Add smooth transition and show selected metrics grid
        setTimeout(function() {{
            const targetGrid = document.getElementById('metrics-' + period);
            if (targetGrid) {{
                targetGrid.classList.add('active');
                targetGrid.style.opacity = '0';
                setTimeout(function() {{
                    targetGrid.style.opacity = '1';
                }}, 50);
            }}
        }}, 150);

        // Add active class to selected button
        const activeBtn = document.getElementById('btn-' + period);
        if (activeBtn) {{
            activeBtn.classList.add('active');
        }}
    }}

    // Initialize dashboard on load
    document.addEventListener('DOMContentLoaded', function() {{
        // Ensure 5Y is active by default
        showMetrics('5Y');
    }});
    </script>
</body>
</html>
"""
        return html_template

    def save_comprehensive_dashboard(
        self,
        data: dict,
        output_name: str = "final_fixed_dashboard",
        report_name: str = "Portfolio",
    ) -> Path:
        """Save the complete dashboard to HTML file."""
        charts = self.generate_charts(data)
        html_content = self.create_dashboard_html(data, charts, report_name)

        output_path = self.report_dir / f"{output_name}.html"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path


if __name__ == "__main__":
    # Example usage
    from pathlib import Path

    # Use command line argument if provided, otherwise use default
    if len(sys.argv) > 1:
        report_folder = sys.argv[1].strip("/")
    else:
        report_folder = "1025-1343-ichimoku-basket-large"

    # Initialize dashboard with the reports directory
    dashboard = FinalFixedDashboard(Path("reports"))

    data = dashboard.load_comprehensive_data(report_folder)

    if data:
        # Change the output directory to the specific report folder for saving
        dashboard.report_dir = Path("reports") / report_folder
        output_path = dashboard.save_comprehensive_dashboard(
            data, "dashboard", report_folder
        )
        print(f"✅ Final Fixed Dashboard restored and saved to: {output_path}")
    else:
        print("❌ No data found to generate dashboard")
