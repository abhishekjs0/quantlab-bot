#!/usr/bin/env python3
"""
Hybrid Dashboard - Combines the best metrics panel from improved_dashboard
with the proper chart layout from final_fixed_dashboard.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio


class HybridDashboard:
    """Hybrid dashboard combining best features from both dashboards."""

    def __init__(self, report_dir: Path):
        self.report_dir = Path(report_dir)
        self.colors = {
            "primary": "#1f2937",
            "secondary": "#374151",
            "accent": "#3b82f6",
            "success": "#10b981",
            "warning": "#f59e0b",
            "danger": "#ef4444",
            "background": "#f8fafc",
            "surface": "#ffffff",
            "chart_bg": "#fefefe",
            "text_primary": "#1f2937",
            "text_secondary": "#6b7280",
            "realized_profit": "#10b981",
            "realized_loss": "#ef4444",
            "unrealized_profit": "#22c55e",
            "unrealized_loss": "#f87171",
        }

        self.layout_config = {
            "template": "plotly_white",
            "showlegend": True,
            "margin": {"l": 60, "r": 40, "t": 80, "b": 60},
            "title_x": 0.5,
            "title_font_size": 16,
            "font": {"size": 12},
            "plot_bgcolor": self.colors["chart_bg"],
            "paper_bgcolor": self.colors["background"],
        }

    def load_data(self) -> dict:
        """Load all necessary data from report directory."""
        data = {}

        for period in ["1Y", "3Y", "5Y"]:
            # Load portfolio equity curve
            equity_file = self.report_dir / f"portfolio_daily_equity_curve_{period}.csv"
            if equity_file.exists():
                data[f"equity_{period}"] = pd.read_csv(
                    equity_file, parse_dates=["Date"]
                )

            # Load trades
            trades_file = self.report_dir / f"consolidated_trades_{period}.csv"
            if trades_file.exists():
                data[f"trades_{period}"] = pd.read_csv(
                    trades_file, parse_dates=["Date/Time"]
                )

        # Load strategy summary
        summary_file = self.report_dir / "strategy_backtests_summary.csv"
        if summary_file.exists():
            data["summary"] = pd.read_csv(summary_file)

        return data

    def create_improved_metrics_html(self, data: dict) -> str:
        """Create improved metrics panel HTML (preserved from improved_dashboard)."""
        # Load strategy summary
        metrics = {}
        if "summary" in data:
            summary_df = data["summary"]
            for _, row in summary_df.iterrows():
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
            """Create metrics grid HTML."""
            return f"""
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('net_pnl', 0):.1f}%</div>
                    <div class="metric-label">Net P&L</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('cagr', 0):.1f}%</div>
                    <div class="metric-label">CAGR</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('irr', 0):.1f}%</div>
                    <div class="metric-label">IRR</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{int(period_metrics.get('trades', 0))}</div>
                    <div class="metric-label">Trades</div>
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

        # Create metrics HTML for each period
        metrics_html = f"""
        <div class="metrics-section">
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

    def create_equity_chart(self, data: dict) -> go.Figure:
        """Create portfolio equity chart with proper layout."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"equity_{period}" in data:
                df = data[f"equity_{period}"]
                fig.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=df["Total Return %"],
                        mode="lines",
                        name=f"{period} Portfolio",
                        visible=(period == "1Y"),
                        line={"width": 2},
                    )
                )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Portfolio Equity Curve",
            xaxis_title="Date",
            yaxis_title="Portfolio Value (%)",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def create_drawdown_chart(self, data: dict) -> go.Figure:
        """Create drawdown chart with statistics."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"equity_{period}" in data:
                df = data[f"equity_{period}"]
                if "Drawdown %" in df.columns:
                    # Calculate statistics
                    max_dd = df["Drawdown %"].min()
                    mean_dd = df["Drawdown %"].mean()
                    median_dd = df["Drawdown %"].median()

                    fig.add_trace(
                        go.Scatter(
                            x=df["Date"],
                            y=df["Drawdown %"],
                            mode="lines",
                            name=f"{period} Drawdown",
                            visible=(period == "1Y"),
                            fill="tonexty" if period == "1Y" else None,
                            line={"color": "red", "width": 1},
                            hovertemplate=f"<b>{period}</b><br>Date: %{{x}}<br>Drawdown: %{{y:.2f}}%<br>Max: {max_dd:.2f}%<br>Mean: {mean_dd:.2f}%<br>Median: {median_dd:.2f}%<extra></extra>",
                        )
                    )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Portfolio Drawdown Analysis",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def create_monthly_pnl_chart(self, data: dict) -> go.Figure:
        """Create monthly P&L chart."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"trades_{period}" in data:
                trades_df = data[f"trades_{period}"]
                if not trades_df.empty:
                    # Filter for exit trades only (they have P&L data)
                    exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                    if not exit_trades.empty and "Net P&L %" in exit_trades.columns:
                        # Clean and convert P&L percentage to numeric
                        exit_trades["Net P&L %"] = (
                            exit_trades["Net P&L %"]
                            .astype(str)
                            .str.replace("%", "")
                            .astype(float)
                        )

                        exit_trades["exit_month"] = pd.to_datetime(
                            exit_trades["Date/Time"]
                        ).dt.to_period("M")
                        monthly_pnl = (
                            exit_trades.groupby("exit_month")["Net P&L %"]
                            .sum()
                            .reset_index()
                        )
                        monthly_pnl["exit_month"] = monthly_pnl[
                            "exit_month"
                        ].dt.to_timestamp()

                        colors = [
                            "green" if x > 0 else "red"
                            for x in monthly_pnl["Net P&L %"]
                        ]

                        fig.add_trace(
                            go.Bar(
                                x=monthly_pnl["exit_month"],
                                y=monthly_pnl["Net P&L %"],
                                name=f"{period} Monthly P&L",
                                visible=(period == "1Y"),
                                marker_color=colors,
                            )
                        )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Monthly P&L Distribution",
            xaxis_title="Month",
            yaxis_title="P&L (%)",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def create_exposure_chart(self, data: dict) -> go.Figure:
        """Create portfolio exposure chart."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"equity_{period}" in data:
                df = data[f"equity_{period}"]
                if "Avg exposure %" in df.columns:
                    # Calculate statistics
                    max_exp = df["Avg exposure %"].max()
                    mean_exp = df["Avg exposure %"].mean()
                    median_exp = df["Avg exposure %"].median()

                    fig.add_trace(
                        go.Scatter(
                            x=df["Date"],
                            y=df["Avg exposure %"],
                            mode="lines",
                            name=f"{period} Exposure",
                            visible=(period == "1Y"),
                            line={"width": 2},
                            hovertemplate=f"<b>{period}</b><br>Date: %{{x}}<br>Exposure: %{{y:.1f}}%<br>Max: {max_exp:.1f}%<br>Mean: {mean_exp:.1f}%<br>Median: {median_exp:.1f}%<extra></extra>",
                        )
                    )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Portfolio Exposure Over Time",
            xaxis_title="Date",
            yaxis_title="Exposure (%)",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def create_trade_return_days_chart(self, data: dict) -> go.Figure:
        """Create a placeholder chart for trade return vs holding days."""
        fig = go.Figure()

        # Add a simple text annotation since the trade data format doesn't include holding days
        fig.add_annotation(
            text="Trade Return vs Holding Days<br><br>Data not available in current format<br>Individual trade entries/exits are stored separately",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            xanchor="center",
            yanchor="middle",
            font_size=16,
            font_color="gray",
        )
        fig.update_layout(
            title="Trade Return vs Holding Days",
            xaxis={"visible": False},
            yaxis={"visible": False},
            **self.layout_config,
        )
        return fig

    def create_mae_analysis_chart(self, data: dict) -> go.Figure:
        """Create MAE analysis chart using available drawdown data."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"trades_{period}" in data:
                trades_df = data[f"trades_{period}"]
                if (
                    not trades_df.empty
                    and "Drawdown %" in trades_df.columns
                    and "Net P&L %" in trades_df.columns
                ):
                    # Filter for exit trades only (they have P&L data)
                    exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                    if not exit_trades.empty:
                        # Clean and convert percentages to numeric
                        exit_trades["Net P&L %"] = (
                            exit_trades["Net P&L %"]
                            .astype(str)
                            .str.replace("%", "")
                            .astype(float)
                        )
                        exit_trades["Drawdown %"] = (
                            exit_trades["Drawdown %"]
                            .astype(str)
                            .str.replace("%", "")
                            .astype(float)
                        )

                        colors = [
                            "green" if x > 0 else "red"
                            for x in exit_trades["Net P&L %"]
                        ]

                        fig.add_trace(
                            go.Scatter(
                                x=exit_trades["Drawdown %"],
                                y=exit_trades["Net P&L %"],
                                mode="markers",
                                name=f"{period} MAE vs Return",
                                visible=(period == "1Y"),
                                marker={"color": colors, "size": 6, "opacity": 0.6},
                                hovertemplate="MAE: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
                            )
                        )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Maximum Adverse Excursion (MAE) Analysis",
            xaxis_title="MAE (%)",
            yaxis_title="Final Return (R)",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def create_win_rate_chart(self, data: dict) -> go.Figure:
        """Create win rate by symbol chart."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if f"trades_{period}" in data:
                trades_df = data[f"trades_{period}"]
                if not trades_df.empty and "Symbol" in trades_df.columns:
                    # Filter for exit trades only (they have P&L data)
                    exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                    if not exit_trades.empty:
                        # Clean and convert P&L percentage to numeric
                        exit_trades["Net P&L %"] = (
                            exit_trades["Net P&L %"]
                            .astype(str)
                            .str.replace("%", "")
                            .astype(float)
                        )

                        symbol_stats = (
                            exit_trades.groupby("Symbol")
                            .agg({"Net P&L %": ["count", lambda x: (x > 0).sum()]})
                            .round(1)
                        )
                        symbol_stats.columns = ["total_trades", "winning_trades"]
                        symbol_stats["win_rate"] = (
                            symbol_stats["winning_trades"]
                            / symbol_stats["total_trades"]
                            * 100
                        ).round(1)
                        symbol_stats = symbol_stats.sort_values(
                            "win_rate", ascending=True
                        )

                        colors = [
                            "green" if x >= 50 else "red"
                            for x in symbol_stats["win_rate"]
                        ]

                        fig.add_trace(
                            go.Bar(
                                x=symbol_stats["win_rate"],
                                y=symbol_stats.index,
                                orientation="h",
                                name=f"{period} Win Rate",
                                visible=(period == "1Y"),
                                marker_color=colors,
                            )
                        )

        # Add period selector buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visibility = [False] * 3
            visibility[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visibility}]}
            )

        fig.update_layout(
            title="Win Rate by Symbol",
            xaxis_title="Win Rate (%)",
            yaxis_title="Trading Symbol",
            updatemenus=[
                {
                    "type": "buttons",
                    "direction": "right",
                    "x": 0.7,
                    "y": 1.1,
                    "buttons": buttons,
                }
            ],
            **self.layout_config,
        )

        return fig

    def generate_charts(self, data: dict) -> dict[str, go.Figure]:
        """Generate all charts."""
        return {
            "equity": self.create_equity_chart(data),
            "drawdown": self.create_drawdown_chart(data),
            "monthly_pnl": self.create_monthly_pnl_chart(data),
            "exposure": self.create_exposure_chart(data),
            "trade_return_days": self.create_trade_return_days_chart(data),
            "mae_analysis": self.create_mae_analysis_chart(data),
            "win_rate": self.create_win_rate_chart(data),
        }

    def create_dashboard_html(
        self, data: dict, charts: dict, report_name: str = "Portfolio"
    ) -> str:
        """Create complete HTML dashboard using final_fixed_dashboard structure."""

        # Convert charts to HTML
        chart_htmls = {}
        for chart_name, fig in charts.items():
            chart_htmls[chart_name] = pio.to_html(
                fig, include_plotlyjs=False, div_id=f"{chart_name}_chart"
            )

        metrics_html = self.create_improved_metrics_html(data)

        # Use the CSS and structure from final_fixed_dashboard for proper chart layout
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hybrid Portfolio Dashboard</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: #1f2937;
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}

        .header {{
            text-align: center;
            background: linear-gradient(135deg, #1f2937 0%, #374151 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }}

        .header p {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        /* Metrics Panel Styles (from improved_dashboard) */
        .metrics-section {{
            background: white;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }}

        .metrics-section h2 {{
            font-size: 1.5rem;
            color: #1f2937;
            margin-bottom: 20px;
            text-align: center;
        }}

        .period-selector {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 25px;
        }}

        .period-btn {{
            background: #f3f4f6;
            border: 2px solid #e5e7eb;
            color: #6b7280;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.2s ease;
        }}

        .period-btn:hover {{
            background: #e5e7eb;
            border-color: #d1d5db;
        }}

        .period-btn.active {{
            background: #3b82f6;
            border-color: #3b82f6;
            color: white;
        }}

        .metrics-content {{
            display: none;
        }}

        .metrics-content.active {{
            display: block;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 15px;
        }}

        .metric-card {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 20px 15px;
            text-align: center;
            transition: all 0.2s ease;
        }}

        .metric-card:hover {{
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }}

        .metric-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 5px;
        }}

        .metric-label {{
            font-size: 0.875rem;
            color: #6b7280;
            font-weight: 500;
        }}

        /* Chart Styles (from final_fixed_dashboard) */
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

        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}

            .metrics-grid {{
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 12px;
            }}

            .metric-card {{
                padding: 16px 12px;
            }}

            .metric-card h3 {{
                font-size: 1.25rem;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{report_name} Dashboard</h1>
            <p>Professional Quantitative Trading Analysis</p>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>

        {metrics_html}

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
    </div>

    <script>
        function showMetrics(period) {{
            // Hide all metric contents
            document.querySelectorAll('.metrics-content').forEach(function(el) {{
                el.classList.remove('active');
            }});

            // Remove active class from all buttons
            document.querySelectorAll('.period-btn').forEach(function(el) {{
                el.classList.remove('active');
            }});

            // Show selected metrics grid
            document.getElementById('metrics-' + period).classList.add('active');

            // Add active class to selected button
            document.getElementById('btn-' + period).classList.add('active');
        }}
    </script>
</body>
</html>
"""

    def save_dashboard(
        self, output_name: str = "hybrid_dashboard", report_name: str = "Portfolio"
    ) -> Path:
        """Save the complete hybrid dashboard."""
        data = self.load_data()
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
        report_folder = "1026-2033-ichimoku-basket-mega"

    # Initialize dashboard with the reports directory
    dashboard = HybridDashboard(Path("reports") / report_folder)

    output_path = dashboard.save_dashboard(
        "hybrid_dashboard", "QuantLab Hybrid Analysis"
    )
    print(f"✅ Hybrid dashboard saved to: {output_path}")
    print(f"🌐 Open in browser: file://{output_path}")
