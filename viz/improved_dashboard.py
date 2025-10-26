"""
Improved Dashboard - Streamlined, visually appealing, and fully functional.
"""

import json
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


class ImprovedDashboard:
    """Streamlined dashboard with improved visuals and functionality."""

    def __init__(self, report_dir: Path):
        """Initialize dashboard with report directory."""
        self.report_dir = Path(report_dir)

        # Improved color scheme
        self.colors = {
            "primary": "#1f2937",
            "secondary": "#374151",
            "accent": "#059669",
            "profit": "#10b981",
            "loss": "#dc2626",
            "neutral": "#6b7280",
            "equity": "#2563eb",
            "exposure": "#7c3aed",
            "realized_profit": "#059669",  # Green for realized profit
            "realized_loss": "#dc2626",  # Red for realized loss
            "unrealized_profit": "#86efac",  # Light green for unrealized profit
            "unrealized_loss": "#fca5a5",  # Light red for unrealized loss
            "background": "#f8fafc",
            "chart_bg": "#ffffff",
        }

        # Layout configuration
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
            try:
                # Load equity curves
                daily_path = (
                    self.report_dir / f"portfolio_daily_equity_curve_{period}.csv"
                )
                monthly_path = (
                    self.report_dir / f"portfolio_monthly_equity_curve_{period}.csv"
                )
                trades_path = self.report_dir / f"consolidated_trades_{period}.csv"

                period_data = {}
                if daily_path.exists():
                    period_data["daily_equity"] = pd.read_csv(
                        daily_path, parse_dates=["Date"]
                    )
                if monthly_path.exists():
                    period_data["monthly_equity"] = pd.read_csv(monthly_path)
                if trades_path.exists():
                    period_data["trades"] = pd.read_csv(trades_path)

                if period_data:
                    data[period] = period_data

            except Exception as e:
                print(f"Error loading data for {period}: {e}")

        # Load strategy summary
        try:
            summary_path = self.report_dir / "strategy_backtests_summary.csv"
            if summary_path.exists():
                data["summary"] = pd.read_csv(summary_path)
        except Exception as e:
            print(f"Error loading strategy summary: {e}")

        return data

    def fix_percentage_calculations(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix percentage calculations to use current equity as denominator."""
        df = df.copy()

        # Fix percentage columns to use current equity as denominator
        for col in ["Realized %", "Unrealized %", "Total Return %"]:
            if col in df.columns and "Equity" in df.columns:
                base_col = col.replace(" %", " INR")
                if base_col in df.columns:
                    # Use current equity as denominator
                    df[col] = (df[base_col] / df["Equity"] * 100).round(2)

        return df

    def create_equity_chart(self, data: dict) -> go.Figure:
        """Create portfolio equity curve chart."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "daily_equity" in data[period]:
                df = data[period]["daily_equity"]
                df = self.fix_percentage_calculations(df)

                fig.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=df["Equity"],
                        mode="lines",
                        name=f"{period} Equity",
                        line={"width": 2},
                        visible=(period == "5Y"),  # Show 5Y by default
                    )
                )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Portfolio Equity Curve",
            xaxis_title="Date",
            yaxis_title="Equity (INR)",
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
            if period in data and "daily_equity" in data[period]:
                df = data[period]["daily_equity"]

                # Calculate statistics
                drawdown_vals = df["Drawdown %"].dropna()
                if len(drawdown_vals) > 0:
                    max_dd = drawdown_vals.max()
                    mean_dd = drawdown_vals.mean()
                    median_dd = drawdown_vals.median()
                else:
                    max_dd = mean_dd = median_dd = 0

                fig.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=-df["Drawdown %"],  # Negative for proper display
                        mode="lines",
                        name=f"{period} Drawdown",
                        fill="tozeroy",
                        fillcolor="rgba(220, 38, 38, 0.3)",
                        line={"color": self.colors["loss"], "width": 1},
                        visible=(period == "5Y"),
                        hovertemplate=f"<b>{period}</b><br>"
                        + "Date: %{x}<br>"
                        + "Drawdown: %{y:.2f}%<br>"
                        + f"Max: {max_dd:.2f}%<br>"
                        + f"Mean: {mean_dd:.2f}%<br>"
                        + f"Median: {median_dd:.2f}%<extra></extra>",
                    )
                )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
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

    def create_exposure_chart(self, data: dict) -> go.Figure:
        """Create exposure chart with statistics."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "daily_equity" in data[period]:
                df = data[period]["daily_equity"]

                # Calculate statistics
                exposure_vals = df["Avg exposure %"].dropna()
                if len(exposure_vals) > 0:
                    max_exp = exposure_vals.max()
                    mean_exp = exposure_vals.mean()
                    median_exp = exposure_vals.median()
                else:
                    max_exp = mean_exp = median_exp = 0

                fig.add_trace(
                    go.Scatter(
                        x=df["Date"],
                        y=df["Avg exposure %"],
                        mode="lines",
                        name=f"{period} Exposure",
                        line={"color": self.colors["exposure"], "width": 2},
                        visible=(period == "5Y"),
                        hovertemplate=f"<b>{period}</b><br>"
                        + "Date: %{x}<br>"
                        + "Exposure: %{y:.1f}%<br>"
                        + f"Max: {max_exp:.1f}%<br>"
                        + f"Mean: {mean_exp:.1f}%<br>"
                        + f"Median: {median_exp:.1f}%<extra></extra>",
                    )
                )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Portfolio Exposure Analysis",
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

    def create_monthly_pnl_chart(self, data: dict) -> go.Figure:
        """Create monthly P&L chart with improved colors."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "monthly_equity" in data[period]:
                df = data[period]["monthly_equity"]
                df = self.fix_percentage_calculations(df)

                # Limit x-axis labels to avoid overlap
                months = df["Month"].tolist()
                if len(months) > 8:
                    # Show every 3rd month for longer periods
                    tick_indices = list(range(0, len(months), 3))
                    [months[i] for i in tick_indices]
                else:
                    pass

                # Realized P&L
                fig.add_trace(
                    go.Bar(
                        x=df["Month"],
                        y=df["Realized INR"],
                        name=f"{period} Realized",
                        marker_color=[
                            (
                                self.colors["realized_profit"]
                                if x >= 0
                                else self.colors["realized_loss"]
                            )
                            for x in df["Realized INR"]
                        ],
                        visible=(period == "5Y"),
                        opacity=1.0,
                    )
                )

                # Unrealized P&L
                fig.add_trace(
                    go.Bar(
                        x=df["Month"],
                        y=df["Unrealized INR"],
                        name=f"{period} Unrealized",
                        marker_color=[
                            (
                                self.colors["unrealized_profit"]
                                if x >= 0
                                else self.colors["unrealized_loss"]
                            )
                            for x in df["Unrealized INR"]
                        ],
                        visible=(period == "5Y"),
                        opacity=0.7,
                    )
                )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * (len(["1Y", "3Y", "5Y"]) * 2)  # 2 traces per period
            visible[i * 2] = True  # Realized
            visible[i * 2 + 1] = True  # Unrealized
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Monthly Portfolio Returns (Realized vs Unrealized)",
            xaxis_title="Month",
            yaxis_title="Return (INR)",
            barmode="relative",
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
        """Create trade return vs holding days chart."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "trades" in data[period]:
                trades_df = data[period]["trades"]

                # Filter exit trades and extract data
                exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                if not exit_trades.empty:
                    # Calculate holding days
                    entry_trades = trades_df[trades_df["Type"] == "Entry long"].copy()

                    returns = []
                    days = []

                    for _, exit_trade in exit_trades.iterrows():
                        trade_num = exit_trade["Trade #"]
                        entry_trade = entry_trades[entry_trades["Trade #"] == trade_num]

                        if not entry_trade.empty:
                            entry_date = pd.to_datetime(
                                entry_trade.iloc[0]["Date/Time"]
                            )
                            exit_date = pd.to_datetime(exit_trade["Date/Time"])
                            holding_days = (exit_date - entry_date).days

                            # Extract return percentage
                            return_str = str(exit_trade["Net P&L %"])
                            if return_str and return_str != "":
                                try:
                                    return_pct = float(return_str.replace("%", ""))
                                    returns.append(return_pct)
                                    days.append(holding_days)
                                except Exception:
                                    continue

                    if returns and days:
                        colors = [
                            self.colors["profit"] if r >= 0 else self.colors["loss"]
                            for r in returns
                        ]

                        fig.add_trace(
                            go.Scatter(
                                x=days,
                                y=returns,
                                mode="markers",
                                name=f"{period} Trades",
                                marker={
                                    "color": colors,
                                    "size": 8,
                                    "opacity": 0.7,
                                    "line": {"width": 1, "color": "white"},
                                },
                                visible=(period == "5Y"),
                            )
                        )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Trade Return vs Holding Days",
            xaxis_title="Holding Days",
            yaxis_title="Return (%)",
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

    def create_mae_chart(self, data: dict) -> go.Figure:
        """Create simplified MAE chart with R notation."""
        fig = go.Figure()

        for period in ["1Y", "3Y", "5Y"]:
            if period in data and "trades" in data[period]:
                trades_df = data[period]["trades"]

                # Filter exit trades
                exit_trades = trades_df[trades_df["Type"] == "Exit long"].copy()
                if not exit_trades.empty:
                    returns = []
                    maes = []

                    for _, trade in exit_trades.iterrows():
                        try:
                            return_str = str(trade["Net P&L %"])
                            mae_str = str(trade["Drawdown %"])

                            if (
                                return_str
                                and mae_str
                                and return_str != ""
                                and mae_str != ""
                            ):
                                return_pct = float(return_str.replace("%", ""))
                                mae_pct = float(
                                    mae_str.replace("%", "").replace("-", "")
                                )

                                returns.append(return_pct)
                                maes.append(mae_pct)
                        except Exception:
                            continue

                    if returns and maes:
                        colors = [
                            self.colors["profit"] if r >= 0 else self.colors["loss"]
                            for r in returns
                        ]

                        fig.add_trace(
                            go.Scatter(
                                x=maes,
                                y=returns,
                                mode="markers",
                                name=f"{period} Trades",
                                marker={"color": colors, "size": 8, "opacity": 0.7},
                                visible=(period == "5Y"),
                            )
                        )

        # Add suggested stop loss line at 1R (2.5%)
        fig.add_hline(
            y=-2.5,
            line_dash="dash",
            line_color="red",
            annotation_text="Suggested Stop: 1R (-2.5%)",
        )

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Maximum Adverse Excursion (MAE) Analysis<br><sub>1R = 2.5% risk unit</sub>",
            xaxis_title="MAE (%)",
            yaxis_title="Final Return (%)",
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
        """Create fixed win rate by symbols chart."""
        fig = go.Figure()

        # Load metrics data for win rates
        for period in ["1Y", "3Y", "5Y"]:
            metrics_path = self.report_dir / f"portfolio_key_metrics_{period}.csv"
            if metrics_path.exists():
                try:
                    df = pd.read_csv(metrics_path)
                    # Remove TOTAL row and sort by win rate
                    df = df[df["Symbol"] != "TOTAL"].copy()
                    df = df.sort_values("Profitable trades %")

                    # Calculate proper statistics
                    win_rates = df["Profitable trades %"].dropna()
                    mean_wr = win_rates.mean() if len(win_rates) > 0 else 0
                    median_wr = win_rates.median() if len(win_rates) > 0 else 0

                    # Create color array
                    colors = [
                        self.colors["profit"] if x >= 50 else self.colors["loss"]
                        for x in df["Profitable trades %"]
                    ]

                    fig.add_trace(
                        go.Bar(
                            x=df["Symbol"],
                            y=df["Profitable trades %"],
                            name=f"{period} Win Rate",
                            marker_color=colors,
                            visible=(period == "5Y"),
                            hovertemplate=f"<b>{period}</b><br>"
                            + "Symbol: %{x}<br>"
                            + "Win Rate: %{y:.1f}%<br>"
                            + f"Mean: {mean_wr:.1f}%<br>"
                            + f"Median: {median_wr:.1f}%<extra></extra>",
                        )
                    )

                except Exception as e:
                    print(f"Error loading metrics for {period}: {e}")

        # Add period toggle buttons
        buttons = []
        for i, period in enumerate(["1Y", "3Y", "5Y"]):
            visible = [False] * len(["1Y", "3Y", "5Y"])
            visible[i] = True
            buttons.append(
                {"label": period, "method": "update", "args": [{"visible": visible}]}
            )

        fig.update_layout(
            title="Win Rate by Symbol",
            xaxis_title="Trading Symbol",
            yaxis_title="Win Rate (%)",
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

    def create_improved_metrics_html(self, data: dict) -> str:
        """Create improved metrics panel HTML."""
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

        return f"""
        <div class="enhanced-metrics-panel">
            <div class="period-selector">
                <button onclick="showMetrics('1Y')" id="btn-1Y" class="period-btn">1Y</button>
                <button onclick="showMetrics('3Y')" id="btn-3Y" class="period-btn">3Y</button>
                <button onclick="showMetrics('5Y')" id="btn-5Y" class="period-btn active">5Y</button>
            </div>

            <!-- 5Y Metrics (default) -->
            <div id="metrics-5Y" class="metrics-grid active">
                <div class="metric-card highlight"><h3>{metrics.get('5Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('5Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('5Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{metrics.get('5Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>

            <!-- 3Y Metrics -->
            <div id="metrics-3Y" class="metrics-grid">
                <div class="metric-card highlight"><h3>{metrics.get('3Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('3Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('3Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{metrics.get('3Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>

            <!-- 1Y Metrics -->
            <div id="metrics-1Y" class="metrics-grid">
                <div class="metric-card highlight"><h3>{metrics.get('1Y', {}).get('net_pnl', 0):.1f}%</h3><p>Net P&L %</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('1Y', {}).get('cagr', 0):.1f}%</h3><p>CAGR [%]</p></div>
                <div class="metric-card highlight"><h3>{metrics.get('1Y', {}).get('irr', 0):.1f}%</h3><p>IRR [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('trades', 0)}</h3><p># Trades</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('win_rate', 0):.1f}%</h3><p>Win Rate [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('profit_factor', 0):.2f}</h3><p>Profit Factor</p></div>

                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('avg_exposure', 0):.1f}%</h3><p>Avg Exposure %</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('alpha', 0):.1f}%</h3><p>Alpha [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('beta', 0):.2f}</h3><p>Beta</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('avg_trade', 0):.2f}%</h3><p>Avg. Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('best_trade', 0):.1f}%</h3><p>Best Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('worst_trade', 0):.1f}%</h3><p>Worst Trade [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('max_trade_duration', 'N/A')}</h3><p>Max Trade Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('avg_trade_duration', 'N/A')}</h3><p>Avg Trade Duration</p></div>

                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('max_drawdown', 0):.1f}%</h3><p>Max Drawdown [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('max_dd_duration', 'N/A')}</h3><p>Max DD Duration</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('sharpe', 0):.2f}</h3><p>Sharpe Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('sortino', 0):.2f}</h3><p>Sortino Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('calmar', 0):.2f}</h3><p>Calmar Ratio</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('expectancy', 0):.2f}%</h3><p>Expectancy [%]</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('sqn', 0):.2f}</h3><p>SQN</p></div>
                <div class="metric-card"><h3>{metrics.get('1Y', {}).get('kelly', 0):.3f}</h3><p>Kelly Criterion</p></div>
            </div>
        </div>
        """

    def create_dashboard_html(
        self, data: dict, charts: dict, report_name: str = "Portfolio"
    ) -> str:
        """Create complete HTML dashboard."""

        # Convert charts to HTML
        chart_htmls = {}
        for chart_name, fig in charts.items():
            chart_htmls[chart_name] = pio.to_html(
                fig, include_plotlyjs=False, div_id=f"{chart_name}_chart"
            )

        metrics_html = self.create_improved_metrics_html(data)

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Improved Portfolio Dashboard</title>
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
            font-weight: 700;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .enhanced-metrics-panel {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.08);
            border: 1px solid #e5e7eb;
        }}

        .period-selector {{
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-bottom: 30px;
        }}

        .period-btn {{
            background: #f3f4f6;
            border: 2px solid #e5e7eb;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s ease;
            color: #4b5563;
        }}

        .period-btn:hover {{
            background: #e5e7eb;
            transform: translateY(-2px);
        }}

        .period-btn.active {{
            background: #2563eb;
            color: white;
            border-color: #2563eb;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
        }}

        .metrics-grid {{
            display: none;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 16px;
        }}

        .metrics-grid.active {{
            display: grid;
        }}

        .metric-card {{
            background: #f8fafc;
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 20px 16px;
            text-align: center;
            transition: all 0.3s ease;
        }}

        .metric-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        }}

        .metric-card.highlight {{
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
            border-color: #2563eb;
        }}

        .metric-card h3 {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #1f2937;
            margin-bottom: 6px;
        }}

        .metric-card.highlight h3 {{
            color: #1d4ed8;
        }}

        .metric-card p {{
            font-size: 0.75rem;
            color: #6b7280;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .chart-container {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.06);
            border: 1px solid #e5e7eb;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 15px;
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

        <div class="chart-container">
            {chart_htmls.get("equity", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("drawdown", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("monthly_pnl", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("exposure", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("trade_return_days", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("mae_analysis", "")}
        </div>

        <div class="chart-container">
            {chart_htmls.get("win_rate", "")}
        </div>
    </div>

    <script>
        function showMetrics(period) {{
            // Hide all metrics grids
            document.querySelectorAll('.metrics-grid').forEach(el => {{
                el.classList.remove('active');
            }});

            // Remove active class from all buttons
            document.querySelectorAll('.period-btn').forEach(el => {{
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

    def generate_charts(self, data: dict) -> dict[str, go.Figure]:
        """Generate all charts for the dashboard."""
        charts = {}

        try:
            charts["equity"] = self.create_equity_chart(data)
            charts["drawdown"] = self.create_drawdown_chart(data)
            charts["monthly_pnl"] = self.create_monthly_pnl_chart(data)
            charts["exposure"] = self.create_exposure_chart(data)
            charts["trade_return_days"] = self.create_trade_return_days_chart(data)
            charts["mae_analysis"] = self.create_mae_chart(data)
            charts["win_rate"] = self.create_win_rate_chart(data)
        except Exception as e:
            print(f"Error generating charts: {e}")
            # Create empty charts for any failures
            for chart_name in [
                "equity",
                "drawdown",
                "monthly_pnl",
                "exposure",
                "trade_return_days",
                "mae_analysis",
                "win_rate",
            ]:
                if chart_name not in charts:
                    charts[chart_name] = self._create_empty_chart(
                        f"Error loading {chart_name} chart"
                    )

        return charts

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

    def save_dashboard(
        self, output_name: str = "improved_dashboard", report_name: str = "Portfolio"
    ) -> Path:
        """Save the complete improved dashboard."""
        data = self.load_data()
        charts = self.generate_charts(data)
        html_content = self.create_dashboard_html(data, charts, report_name)

        output_path = self.report_dir / f"{output_name}.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_path
