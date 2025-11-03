#!/usr/bin/env python3
"""
QuantLab Dashboard - Modern Flat Design
Optimized for 101+ symbol backtests with streamlined visualizations
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

warnings.filterwarnings("ignore")


class QuantLabDashboard:
    """Unified dashboard with modern flat design and optimized charts."""

    def __init__(self, report_dir: Path):
        """Initialize dashboard with report directory."""
        self.report_dir = Path(report_dir)
        self.current_report_folder = None

        # Modern flat color scheme
        self.colors = {
            "primary": "#3498db",      # Blue
            "secondary": "#e74c3c",    # Red
            "success": "#2ecc71",      # Green
            "danger": "#e74c3c",       # Red
            "neutral": "#95a5a6",      # Gray
            "text": "#333333",         # Dark text
            "bg": "#f5f5f5",           # Light background
        }

    def safe_load_csv(self, file_path: Path, description: str = "") -> Optional[pd.DataFrame]:
        """Safely load CSV with error handling."""
        try:
            if file_path.exists() and file_path.stat().st_size > 0:
                df = pd.read_csv(file_path)
                if not df.empty:
                    print(f"✅ Loaded {description}: {len(df)} rows from {file_path.name}")
                    return df
                else:
                    print(f"⚠️ Empty file: {file_path.name}")
            else:
                print(f"⚠️ Missing or empty: {file_path.name}")
        except Exception as e:
            print(f"❌ Error loading {file_path.name}: {str(e)}")
        return None

    def load_comprehensive_data(self, report_folder: str) -> dict:
        """Load all data with comprehensive error handling."""
        self.current_report_folder = report_folder
        folder_path = self.report_dir / report_folder
        if not folder_path.exists():
            print(f"❌ Report folder not found: {folder_path}")
            return {}

        print(f"📂 Loading data from: {folder_path}")
        data = {}

        # Define file patterns for different periods
        period_files = {
            "1Y": ["portfolio_daily_equity_curve_1Y.csv", "consolidated_trades_1Y.csv", 
                   "portfolio_key_metrics_1Y.csv", "portfolio_monthly_equity_curve_1Y.csv"],
            "3Y": ["portfolio_daily_equity_curve_3Y.csv", "consolidated_trades_3Y.csv", 
                   "portfolio_key_metrics_3Y.csv", "portfolio_monthly_equity_curve_3Y.csv"],
            "5Y": ["portfolio_daily_equity_curve_5Y.csv", "consolidated_trades_5Y.csv", 
                   "portfolio_key_metrics_5Y.csv", "portfolio_monthly_equity_curve_5Y.csv"],
        }

        # Load period-specific data
        for period, files in period_files.items():
            equity_file, trades_file, metrics_file, monthly_file = files
            period_data = {}

            equity_df = self.safe_load_csv(folder_path / equity_file, f"{period} equity curve")
            if equity_df is not None:
                period_data["equity"] = equity_df

            trades_df = self.safe_load_csv(folder_path / trades_file, f"{period} trades")
            if trades_df is not None:
                period_data["trades"] = trades_df

            metrics_df = self.safe_load_csv(folder_path / metrics_file, f"{period} metrics")
            if metrics_df is not None:
                period_data["metrics"] = metrics_df

            monthly_df = self.safe_load_csv(folder_path / monthly_file, f"{period} monthly")
            if monthly_df is not None:
                period_data["monthly"] = monthly_df

            if period_data:
                data[period] = period_data

        # Load strategy summary
        strategy_file = self.safe_load_csv(folder_path / "strategy_backtests_summary.csv", "strategy summary")
        if strategy_file is not None:
            data["summary"] = strategy_file

        print(f"📊 Loaded data for periods: {list(data.keys())}")
        return data

    def get_strategy_metrics(self, data: dict) -> dict:
        """Extract strategy metrics from all data."""
        metrics = {}
        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "metrics" in data[period]:
                metrics_df = data[period]["metrics"]
                total_row = metrics_df[metrics_df["Symbol"] == "TOTAL"]
                if not total_row.empty:
                    metrics[period] = total_row.iloc[0].to_dict()
        return metrics

    def create_equity_chart(self, data: dict) -> go.Figure:
        """Create equity curve chart."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No equity data available")

        fig = go.Figure()
        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue

            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])
            equity_df = equity_df.sort_values("Date")

            fig.add_trace(go.Scatter(
                x=equity_df["Date"],
                y=equity_df["Equity"],
                mode="lines",
                name=f"Equity {period}",
                line=dict(color=self.colors["primary"], width=2),
                visible=(period == default_period),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Equity: ₹%{y:,.0f}<extra></extra>",
            ))

        # Create period buttons
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(fig.data))]
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title.text": f"Portfolio Equity Curve - {period}"}],
            })

        fig.update_layout(
            title=f"Portfolio Equity Curve - {default_period}",
            xaxis_title="Date",
            yaxis_title="Equity (₹)",
            template="plotly_white",
            hovermode="x unified",
            height=400,
            updatemenus=[{
                "type": "buttons",
                "direction": "left",
                "x": 0.0,
                "y": 1.15,
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
        )

        return fig

    def create_drawdown_chart(self, data: dict) -> go.Figure:
        """Create drawdown chart."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No equity data available")

        fig = go.Figure()
        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue

            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])
            equity_df = equity_df.sort_values("Date")

            # Calculate drawdown
            running_max = equity_df["Equity"].expanding().max()
            drawdown = ((equity_df["Equity"] - running_max) / running_max * 100)

            fig.add_trace(go.Scatter(
                x=equity_df["Date"],
                y=drawdown,
                mode="lines",
                name=f"Drawdown {period}",
                fill="tozeroy",
                line=dict(color=self.colors["danger"], width=1),
                fillcolor="rgba(231, 76, 60, 0.2)",
                visible=(period == default_period),
                hovertemplate="Date: %{x|%Y-%m-%d}<br>Drawdown: %{y:.2f}%<extra></extra>",
            ))

        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(fig.data))]
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title.text": f"Drawdown Analysis - {period}"}],
            })

        fig.update_layout(
            title=f"Drawdown Analysis - {default_period}",
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            template="plotly_white",
            hovermode="x unified",
            height=300,
            updatemenus=[{
                "type": "buttons",
                "direction": "left",
                "x": 0.0,
                "y": 1.15,
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
        )

        return fig

    def create_monthly_returns_heatmap(self, data: dict) -> go.Figure:
        """Create modern monthly returns heatmap - full width."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "monthly" not in data.get(periods[0], {}):
            return self.create_empty_chart("No monthly data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        monthly_df = data[default_period]["monthly"].copy()

        # Parse month and extract year, month
        monthly_df["Month"] = pd.to_datetime(monthly_df["Month"])
        monthly_df["Year"] = monthly_df["Month"].dt.year
        monthly_df["MonthName"] = monthly_df["Month"].dt.strftime("%b")
        monthly_df["MonthNum"] = monthly_df["Month"].dt.month

        # Create pivot table
        heatmap_data = monthly_df.pivot_table(
            values="Total Return %",
            index="Year",
            columns="MonthNum",
            aggfunc="first"
        )

        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                      "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        heatmap_data.columns = [month_names[int(c)-1] for c in heatmap_data.columns]

        # Color scale - green for positive, red for negative
        z_values = heatmap_data.values
        colors = []
        for row in z_values:
            row_colors = []
            for val in row:
                if pd.isna(val):
                    row_colors.append("#ffffff")
                elif val > 0:
                    # Green scale
                    intensity = min(val / 20, 1.0)  # Normalize to max 20%
                    row_colors.append(f"rgba(46, 204, 113, {0.2 + intensity * 0.8})")
                else:
                    # Red scale
                    intensity = min(abs(val) / 20, 1.0)
                    row_colors.append(f"rgba(231, 76, 60, {0.2 + intensity * 0.8})")
            colors.append(row_colors)

        # Text annotations - show return % inside cells
        text_matrix = []
        for row in z_values:
            text_row = []
            for val in row:
                if pd.isna(val):
                    text_row.append("-")
                else:
                    text_row.append(f"{val:.1f}%")
            text_matrix.append(text_row)

        fig = go.Figure(data=go.Heatmap(
            z=z_values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 12, "color": "#000"},
            colorscale=None,
            showscale=False,
            hovertemplate="%{y} %{x}<br>Return: %{z:.2f}%<extra></extra>",
        ))

        fig.update_layout(
            title="Monthly Returns Heatmap",
            xaxis_title="Month",
            yaxis_title="Year",
            template="plotly_white",
            height=300,
            width=None,
            margin=dict(l=50, r=50, t=80, b=50),
        )

        return fig

    def create_exposure_chart(self, data: dict) -> go.Figure:
        """Create portfolio exposure chart - full width."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "monthly" not in data.get(periods[0], {}):
            return self.create_empty_chart("No exposure data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        monthly_df = data[default_period]["monthly"].copy()
        monthly_df["Month"] = pd.to_datetime(monthly_df["Month"])
        monthly_df = monthly_df.sort_values("Month")

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=monthly_df["Month"],
            y=monthly_df["Avg exposure %"],
            mode="lines+markers",
            name="Average Exposure %",
            line=dict(color=self.colors["primary"], width=2),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(52, 152, 219, 0.2)",
            hovertemplate="Date: %{x|%Y-%m}<br>Exposure: %{y:.1f}%<extra></extra>",
        ))

        fig.update_layout(
            title=f"Average Portfolio Exposure - {default_period}",
            xaxis_title="Date",
            yaxis_title="Exposure (%)",
            template="plotly_white",
            hovermode="x unified",
            height=350,
        )

        return fig

    def create_trade_return_vs_holding_days(self, data: dict) -> go.Figure:
        """Create trade return vs holding days scatter - full width."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "trades" not in data.get(periods[0], {}):
            return self.create_empty_chart("No trade data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        trades_df = data[default_period]["trades"].copy()

        # Use Net P&L % and Holding days from consolidated trades
        if "Net P&L %" not in trades_df.columns or "Holding days" not in trades_df.columns:
            return self.create_empty_chart("Required trade columns not available")

        # Remove NaN values
        trades_df = trades_df.dropna(subset=["Net P&L %", "Holding days"])
        if trades_df.empty:
            return self.create_empty_chart("Insufficient trade data")

        # Color by profit/loss
        colors_list = [self.colors["success"] if x > 0 else self.colors["danger"] 
                       for x in trades_df["Net P&L %"]]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=trades_df["Holding days"],
            y=trades_df["Net P&L %"],
            mode="markers",
            marker=dict(
                size=8,
                color=colors_list,
                opacity=0.7,
                line=dict(width=0.5, color="#fff")
            ),
            text=trades_df.get("Symbol", ""),
            hovertemplate="Symbol: %{text}<br>Holding Days: %{x}<br>Return: %{y:.2f}%<extra></extra>",
        ))

        fig.update_layout(
            title=f"Trade Return vs Holding Days - {default_period}",
            xaxis_title="Holding Days",
            yaxis_title="Net P&L (%)",
            template="plotly_white",
            hovermode="closest",
            height=350,
            shapes=[dict(type="line", x0=0, y0=0, x1=1, y1=0, xref="paper", yref="y",
                        line=dict(color=self.colors["neutral"], dash="dash", width=1))],
        )

        return fig

    def create_mae_analysis(self, data: dict) -> go.Figure:
        """Create MAE analysis with dual plots - toggleable, full width."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "trades" not in data.get(periods[0], {}):
            return self.create_empty_chart("No trade data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        trades_df = data[default_period]["trades"].copy()

        # Ensure required columns
        required_cols = ["MAE_ATR", "IRR %", "Net P&L %"]
        if not all(col in trades_df.columns for col in required_cols):
            return self.create_empty_chart("Required MAE columns not available")

        trades_df = trades_df.dropna(subset=required_cols)
        if trades_df.empty:
            return self.create_empty_chart("Insufficient MAE data")

        # Color by profit/loss
        colors_list = [self.colors["success"] if x > 0 else self.colors["danger"] 
                       for x in trades_df["Net P&L %"]]

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("MAE_ATR vs IRR %", "MAE_ATR vs Net P&L %")
        )

        # Plot 1: MAE_ATR vs IRR %
        fig.add_trace(go.Scatter(
            x=trades_df["MAE_ATR"],
            y=trades_df["IRR %"],
            mode="markers",
            marker=dict(size=8, color=colors_list, opacity=0.7),
            name="MAE_ATR vs IRR",
            hovertemplate="MAE_ATR: %{x:.2f}<br>IRR: %{y:.1f}%<extra></extra>",
        ), row=1, col=1)

        # Plot 2: MAE_ATR vs Net P&L %
        fig.add_trace(go.Scatter(
            x=trades_df["MAE_ATR"],
            y=trades_df["Net P&L %"],
            mode="markers",
            marker=dict(size=8, color=colors_list, opacity=0.7),
            name="MAE_ATR vs P&L %",
            hovertemplate="MAE_ATR: %{x:.2f}<br>P&L: %{y:.2f}%<extra></extra>",
        ), row=1, col=2)

        fig.update_xaxes(title_text="MAE_ATR", row=1, col=1)
        fig.update_yaxes(title_text="IRR (%)", row=1, col=1)
        fig.update_xaxes(title_text="MAE_ATR", row=1, col=2)
        fig.update_yaxes(title_text="Net P&L (%)", row=1, col=2)

        fig.update_layout(
            title_text=f"MAE Analysis - {default_period} (ATR preserving 90% gains)",
            template="plotly_white",
            hovermode="closest",
            height=380,
            showlegend=False,
        )

        return fig

    def create_win_rate_analysis(self, data: dict) -> go.Figure:
        """Create win rate analysis by symbol with toggles - full width."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "metrics" not in data.get(periods[0], {}):
            return self.create_empty_chart("No metrics data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        metrics_df = data[default_period]["metrics"].copy()

        # Remove TOTAL row, keep only symbols with 5+ trades
        metrics_df = metrics_df[metrics_df["Symbol"] != "TOTAL"]
        metrics_df = metrics_df[metrics_df["Total trades"] >= 5]

        if metrics_df.empty:
            return self.create_empty_chart("No symbols with 5+ trades")

        # Sort by Profitable trades %
        metrics_df = metrics_df.sort_values("Profitable trades %", ascending=False)

        fig = go.Figure()

        # Add trace for Profitable trades %
        fig.add_trace(go.Bar(
            x=metrics_df["Symbol"],
            y=metrics_df["Profitable trades %"],
            name="Profitable Trades %",
            marker=dict(color=self.colors["success"]),
            visible=True,
        ))

        # Add trace for Profit factor
        fig.add_trace(go.Bar(
            x=metrics_df["Symbol"],
            y=metrics_df["Profit factor"],
            name="Profit Factor",
            marker=dict(color=self.colors["primary"]),
            visible=False,
        ))

        # Add trace for IRR %
        fig.add_trace(go.Bar(
            x=metrics_df["Symbol"],
            y=metrics_df["IRR %"],
            name="IRR %",
            marker=dict(color=self.colors["secondary"]),
            visible=False,
        ))

        # Create toggle buttons
        toggle_buttons = [
            dict(label="Profitable Trades %", method="update",
                 args=[{"visible": [True, False, False]},
                       {"title": f"Win Rate Analysis by Symbol - {default_period} (Profitable Trades %)"}]),
            dict(label="Profit Factor", method="update",
                 args=[{"visible": [False, True, False]},
                       {"title": f"Win Rate Analysis by Symbol - {default_period} (Profit Factor)"}]),
            dict(label="IRR %", method="update",
                 args=[{"visible": [False, False, True]},
                       {"title": f"Win Rate Analysis by Symbol - {default_period} (IRR %)"}]),
        ]

        fig.update_layout(
            title=f"Win Rate Analysis by Symbol - {default_period} (Profitable Trades %)",
            xaxis_title="Symbol",
            yaxis_title="Value",
            template="plotly_white",
            height=400,
            updatemenus=[{
                "type": "buttons",
                "direction": "left",
                "x": 0.0,
                "y": 1.15,
                "buttons": toggle_buttons,
            }],
            xaxis=dict(tickangle=45),
        )

        return fig

    def create_trade_distribution_analysis(self, data: dict) -> go.Figure:
        """Create trade distribution - returns and holding period, toggleable."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods or "trades" not in data.get(periods[0], {}):
            return self.create_empty_chart("No trade data available")

        default_period = max(periods, key=lambda x: int(x[:-1]))
        trades_df = data[default_period]["trades"].copy()

        # Separate profitable and losing trades
        trades_df = trades_df.dropna(subset=["Net P&L %", "Holding days"])
        if trades_df.empty:
            return self.create_empty_chart("Insufficient trade data")

        profitable = trades_df[trades_df["Net P&L %"] > 0]
        losing = trades_df[trades_df["Net P&L %"] <= 0]

        # Create distribution histograms
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Returns Distribution", "Holding Period Distribution")
        )

        # Returns distribution - Profitable
        fig.add_trace(go.Histogram(
            x=profitable["Net P&L %"],
            name="Profitable",
            marker=dict(color=self.colors["success"]),
            opacity=0.7,
            visible=True,
        ), row=1, col=1)

        # Returns distribution - Losing
        fig.add_trace(go.Histogram(
            x=losing["Net P&L %"],
            name="Losing",
            marker=dict(color=self.colors["danger"]),
            opacity=0.7,
            visible=True,
        ), row=1, col=1)

        # Holding days distribution - Profitable
        fig.add_trace(go.Histogram(
            x=profitable["Holding days"],
            name="Profitable",
            marker=dict(color=self.colors["success"]),
            opacity=0.7,
            visible=True,
            showlegend=False,
        ), row=1, col=2)

        # Holding days distribution - Losing
        fig.add_trace(go.Histogram(
            x=losing["Holding days"],
            name="Losing",
            marker=dict(color=self.colors["danger"]),
            opacity=0.7,
            visible=True,
            showlegend=False,
        ), row=1, col=2)

        fig.update_xaxes(title_text="Net P&L %", row=1, col=1)
        fig.update_yaxes(title_text="Count", row=1, col=1)
        fig.update_xaxes(title_text="Holding Days", row=1, col=2)
        fig.update_yaxes(title_text="Count", row=1, col=2)

        fig.update_layout(
            title_text=f"Trade Distribution Analysis - {default_period}",
            template="plotly_white",
            height=380,
            barmode="group",
        )

        return fig

    def create_empty_chart(self, message: str) -> go.Figure:
        """Create placeholder chart."""
        fig = go.Figure()
        fig.add_annotation(text=message, x=0.5, y=0.5, showarrow=False, font=dict(size=14))
        fig.update_layout(template="plotly_white", height=300)
        return fig

    def create_enhanced_metrics_panel(self, strategy_metrics: Optional[dict] = None) -> str:
        """Create metrics panel with period switching."""
        if not strategy_metrics:
            strategy_metrics = {}

        html = '<div class="enhanced-metrics-panel"><h2>Performance Metrics</h2>'
        html += '<div class="period-selector">'

        for period in ["1Y", "3Y", "5Y"]:
            active = "active" if period == "1Y" else ""
            html += f'<button class="period-btn {active}" onclick="showPeriod(\'{period}\')">{period}</button>'

        html += '</div>'

        # Create metrics for each period
        for period in ["1Y", "3Y", "5Y"]:
            display = "block" if period == "1Y" else "none"
            html += f'<div class="metrics-content" id="metrics-{period}" style="display: {display};">'
            html += '<div class="metrics-grid">'

            if period in strategy_metrics:
                metrics = strategy_metrics[period]
                metric_list = [
                    ("Net P&L %", metrics.get("Net P&L %", "N/A")),
                    ("CAGR %", metrics.get("Equity CAGR %", "N/A")),
                    ("Sharpe Ratio", "N/A"),
                    ("Max DD %", metrics.get("Max equity drawdown %", "N/A")),
                    ("Win Rate %", metrics.get("Profitable trades %", "N/A")),
                    ("Profit Factor", metrics.get("Profit factor", "N/A")),
                    ("Total Trades", metrics.get("Total trades", "N/A")),
                    ("Avg P&L %", metrics.get("Avg P&L % per trade", "N/A")),
                ]

                for i, (label, value) in enumerate(metric_list):
                    primary = "primary" if i == 0 else ""
                    val_str = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                    html += f'<div class="metric-card {primary}">'
                    html += f'<div class="metric-value">{val_str}</div>'
                    html += f'<div class="metric-label">{label}</div></div>'

            html += '</div></div>'

        html += '</div>'
        return html

    def generate_all_charts(self, data: dict) -> dict:
        """Generate all dashboard charts."""
        return {
            "equity": self.create_equity_chart(data),
            "drawdown": self.create_drawdown_chart(data),
            "monthly_heatmap": self.create_monthly_returns_heatmap(data),
            "exposure": self.create_exposure_chart(data),
            "trade_return": self.create_trade_return_vs_holding_days(data),
            "mae_analysis": self.create_mae_analysis(data),
            "win_rate": self.create_win_rate_analysis(data),
            "trade_distribution": self.create_trade_distribution_analysis(data),
        }

    def create_dashboard_html(self, data: dict, charts: dict, report_name: str = "Portfolio") -> str:
        """Create complete HTML dashboard with modern flat design."""
        strategy_metrics = self.get_strategy_metrics(data)
        metrics_panel_html = self.create_enhanced_metrics_panel(strategy_metrics)

        # Convert charts to HTML
        chart_htmls = {}
        for chart_name, fig in charts.items():
            try:
                chart_htmls[chart_name] = pio.to_html(
                    fig, include_plotlyjs=False, div_id=f"{chart_name}_chart"
                )
            except Exception as e:
                print(f"❌ Error generating HTML for {chart_name}: {e}")
                chart_htmls[chart_name] = f'<div class="error-message">Error loading {chart_name} chart</div>'

        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QuantLab Dashboard - {report_name}</title>
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0; padding: 20px;
            background: #f5f5f5;
            color: #333;
            min-height: 100vh;
        }}

        .header {{
            text-align: center; margin-bottom: 30px; padding: 30px;
            background: #1a1a1a;
            color: white; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .header h1 {{ margin: 0; font-size: 2.5em; font-weight: 600; color: #ffffff; }}
        .header p {{ margin: 10px 0 0 0; font-size: 1em; color: #b0b0b0; font-weight: 400; }}

        .enhanced-metrics-panel {{
            background: #ffffff;
            border-radius: 8px; padding: 30px; margin: 30px 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
        }}
        .enhanced-metrics-panel h2 {{
            text-align: center; margin-bottom: 25px;
            color: #1a1a1a;
            font-size: 1.8em; font-weight: 600;
        }}

        .period-selector {{
            display: flex; justify-content: center; gap: 10px; margin-bottom: 30px;
            flex-wrap: wrap;
        }}
        .period-btn {{
            background: #ffffff;
            border: 1px solid #d0d0d0;
            padding: 12px 24px; border-radius: 6px; cursor: pointer;
            font-size: 14px; font-weight: 500;
            transition: all 0.2s ease;
            color: #333;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        .period-btn:hover {{
            background: #f9f9f9;
            border-color: #999;
            color: #000;
        }}
        .period-btn.active {{
            background: #3498db;
            color: white; border-color: #3498db;
            box-shadow: 0 2px 6px rgba(52, 152, 219, 0.3);
        }}

        .metrics-content {{
            display: none;
            opacity: 0;
            transition: opacity 0.2s ease;
        }}
        .metrics-content.active {{
            display: block;
            opacity: 1;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}

        .metric-card {{
            background: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
            transition: all 0.2s ease;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        .metric-card:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            border-color: #999;
        }}
        .metric-card.primary {{
            background: #3498db;
            border-color: #3498db;
            color: white;
        }}
        .metric-card.primary:hover {{
            background: #2980b9;
            box-shadow: 0 2px 8px rgba(52, 152, 219, 0.2);
        }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: 700;
            margin-bottom: 8px;
            color: #1a1a1a;
        }}
        .metric-card.primary .metric-value {{ color: white; }}
        .metric-label {{
            font-size: 0.85em;
            font-weight: 500;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card.primary .metric-label {{ color: #e0f4ff; }}

        .chart-container {{
            background: #ffffff;
            margin: 25px 0;
            padding: 25px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid #e0e0e0;
            transition: all 0.2s ease;
        }}
        .chart-container:hover {{
            box-shadow: 0 2px 8px rgba(0,0,0,0.12);
        }}
        .chart-container.full-width {{
            width: 100%;
        }}

        .error-message {{
            color: #c41e3a;
            background: #fff5f5;
            padding: 20px;
            border-radius: 6px;
            text-align: center;
            font-weight: 500;
            border: 1px solid #ffcccc;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        @media (max-width: 768px) {{
            body {{ padding: 15px; }}
            .metrics-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }}
            .period-btn {{ padding: 10px 18px; font-size: 13px; }}
            .header h1 {{ font-size: 2em; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QuantLab Dashboard</h1>
        <p>{report_name} • Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    {metrics_panel_html}

    <div class="chart-container full-width">
        {chart_htmls.get('equity', '<div class="error-message">Equity chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('drawdown', '<div class="error-message">Drawdown chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('monthly_heatmap', '<div class="error-message">Monthly heatmap not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('exposure', '<div class="error-message">Exposure chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('trade_return', '<div class="error-message">Trade return chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('mae_analysis', '<div class="error-message">MAE analysis not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('win_rate', '<div class="error-message">Win rate analysis not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('trade_distribution', '<div class="error-message">Trade distribution not available</div>')}
    </div>

    <script>
        function showPeriod(period) {{
            // Hide all periods
            document.querySelectorAll('.metrics-content').forEach(el => {{
                el.classList.remove('active');
                el.style.display = 'none';
            }});
            // Show selected period
            document.getElementById('metrics-' + period).classList.add('active');
            document.getElementById('metrics-' + period).style.display = 'block';

            // Update buttons
            document.querySelectorAll('.period-btn').forEach(btn => {{
                btn.classList.remove('active');
            }});
            event.target.classList.add('active');
        }}

        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {{
            document.getElementById('metrics-1Y').classList.add('active');
            document.getElementById('metrics-1Y').style.display = 'block';
        }});
    </script>
</body>
</html>
"""
        return html_template

    def save_dashboard(self, data: dict, output_name: str = "dashboard") -> Path:
        """Save dashboard to file."""
        try:
            charts = self.generate_all_charts(data)
            html = self.create_dashboard_html(data, charts)

            # Determine output path
            if self.current_report_folder:
                output_dir = self.report_dir / self.current_report_folder
            else:
                output_dir = self.report_dir

            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{output_name}_dashboard.html"

            with open(output_path, "w") as f:
                f.write(html)

            print(f"✅ Dashboard saved to: {output_path}")
            print(f"🌐 Open in browser: file://{output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Error saving dashboard: {e}")
            return None


def main():
    """Main execution function."""
    from pathlib import Path
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m viz.dashboard <report_folder>")
        sys.exit(1)

    report_dir = Path.cwd() / "reports"
    report_folder = sys.argv[1]

    dashboard = QuantLabDashboard(report_dir)
    data = dashboard.load_comprehensive_data(report_folder)

    if data:
        dashboard.save_dashboard(data, "portfolio")
    else:
        print("Failed to load data")
        sys.exit(1)


if __name__ == "__main__":
    main()
