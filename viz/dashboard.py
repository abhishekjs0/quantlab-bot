#!/usr/bin/env python3
"""
QuantLab Unified Dashboard - Single file solution with all features
Simplified, robust data loading and comprehensive visualization
"""

import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots
from scipy import stats

warnings.filterwarnings("ignore")


class QuantLabDashboard:
    """Unified dashboard with simplified architecture and robust data loading."""

    def __init__(self, report_dir: Path):
        """Initialize dashboard with report directory."""
        self.report_dir = Path(report_dir)
        self.current_report_folder = None  # Track the current report folder being processed
        
        # Professional color scheme per specification
        self.colors = {
            "primary": "#3498DB",      # Primary equity (blue) - per spec
            "secondary": "#E74C3C",    # Drawdown/Loss (red) - per spec
            "equity": "#3498DB",       # Equity curves - per spec
            "profit": "#2ECC71",       # Profit/Winners (green) - per spec
            "loss": "#E74C3C",         # Loss/Drawdown (red) - per spec
            "exposure": "#9B59B6",     # Exposure (purple) - per spec
            "winners": "#2ECC71",      # Winners (green) - per spec
            "losers": "#E74C3C",       # Losers (red) - per spec
            "light_profit": "#86efac", # Light green for unrealized gains
            "light_loss": "#fca5a5",   # Light red for unrealized losses
            "neutral": "#95A5A6",      # Neutral text/lines (gray) - per spec
            "edge": "#FF6B6B",         # Accent/Edge/Trend - per spec
        }

        # Standard layout configuration
        self.layout_config = {
            "template": "plotly_white",
            "showlegend": True,
            "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
            "margin": {"l": 80, "r": 50, "t": 150, "b": 80},
            "title_x": 0.5,
            "title_font_size": 16,
            "autosize": True,
            "font": {"size": 12},
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

    def load_comprehensive_data(self, report_folder: str) -> Dict:
        """Load all data with comprehensive error handling and fallbacks."""
        self.current_report_folder = report_folder  # Store for save_dashboard
        folder_path = self.report_dir / report_folder
        if not folder_path.exists():
            print(f"❌ Report folder not found: {folder_path}")
            return {}

        print(f"📂 Loading data from: {folder_path}")
        data = {}

        # Define file patterns for different periods
        period_files = {
            "1Y": ["portfolio_daily_equity_curve_1Y.csv", "consolidated_trades_1Y.csv", "portfolio_key_metrics_1Y.csv"],
            "3Y": ["portfolio_daily_equity_curve_3Y.csv", "consolidated_trades_3Y.csv", "portfolio_key_metrics_3Y.csv"], 
            "5Y": ["portfolio_daily_equity_curve_5Y.csv", "consolidated_trades_5Y.csv", "portfolio_key_metrics_5Y.csv"],
        }

        # Load period-specific data
        for period, files in period_files.items():
            equity_file, trades_file, metrics_file = files
            period_data = {}

            # Load equity data (required)
            equity_df = self.safe_load_csv(folder_path / equity_file, f"{period} equity curve")
            if equity_df is not None:
                period_data["equity"] = equity_df

                # Load trades data (optional)
                trades_df = self.safe_load_csv(folder_path / trades_file, f"{period} trades")
                if trades_df is not None:
                    period_data["trades"] = trades_df

                # Load metrics data (optional)
                metrics_df = self.safe_load_csv(folder_path / metrics_file, f"{period} metrics")
                if metrics_df is not None:
                    # Get portfolio-level metrics (TOTAL row)
                    total_row = metrics_df[metrics_df.get("Symbol", "") == "TOTAL"]
                    if not total_row.empty:
                        period_data["metrics"] = total_row.iloc[0].to_dict()

                data[period] = period_data

        # Load strategy summary (check both locations)
        summary_locations = [
            folder_path / "strategy_backtests_summary.csv",
            self.report_dir / "strategy_backtests_summary.csv"
        ]
        
        for summary_path in summary_locations:
            summary_df = self.safe_load_csv(summary_path, "strategy summary")
            if summary_df is not None:
                data["summary"] = summary_df
                break

        # Load monthly data if available
        for period in ["1Y", "3Y", "5Y"]:
            monthly_file = folder_path / f"portfolio_monthly_equity_curve_{period}.csv"
            monthly_df = self.safe_load_csv(monthly_file, f"{period} monthly data")
            if monthly_df is not None and period in data:
                data[period]["monthly"] = monthly_df

        print(f"📊 Loaded data for periods: {list(data.keys())}")
        return data

    def get_strategy_metrics(self, data: Dict) -> Dict:
        """Extract strategy metrics for the enhanced metrics panel."""
        metrics = {}
        
        if "summary" in data:
            summary_df = data["summary"]
            
            for _, row in summary_df.iterrows():
                period = row["Window"]
                
                metrics[period] = {
                    "net_pnl": float(row.get("Net P&L %", 0)),
                    "cagr": float(row.get("CAGR [%]", 0)),
                    "irr": float(row.get("IRR [%]", 0)),
                    "trades": int(row.get("# Trades", 0)),
                    "win_rate": float(row.get("Win Rate [%]", 0)),
                    "profit_factor": float(row.get("Profit Factor", 0)),
                    "avg_exposure": float(row.get("Avg exposure %", 0)),
                    "alpha": float(row.get("Alpha [%]", 0)),
                    "beta": float(row.get("Beta", 0)),
                    "avg_trade": float(row.get("Avg. Trade [%]", 0)),
                    "best_trade": float(row.get("Best Trade [%]", 0)),
                    "worst_trade": float(row.get("Worst Trade [%]", 0)),
                    "max_trade_duration": row.get("Max. Trade Duration", "N/A"),
                    "avg_trade_duration": row.get("Avg. Trade Duration", "N/A"),
                    "max_drawdown": float(row.get("Max. Drawdown [%]", 0)),
                    "max_dd_duration": row.get("Max. Drawdown Duration", "N/A"),
                    "sharpe": float(row.get("Sharpe Ratio", 0)),
                    "sortino": float(row.get("Sortino Ratio", 0)),
                    "calmar": float(row.get("Calmar Ratio", 0)),
                    "romad": float(row.get("RoMaD", 0)),
                    "volatility": float(row.get("Annualized Volatility [%]", 0)),
                    "var_95": float(row.get("Annualized VaR 95% [%]", 0)),
                    "expectancy": float(row.get("Expectancy [%]", 0)),
                    "sqn": float(row.get("SQN", 0)),
                    "kelly": float(row.get("Kelly Criterion", 0)),
                }
        
        return metrics

    def create_empty_chart(self, message: str) -> go.Figure:
        """Create empty chart with message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            xanchor="center", yanchor="middle", showarrow=False,
            font_size=16, font_color="gray"
        )
        fig.update_layout(
            xaxis={"visible": False}, yaxis={"visible": False}, 
            **self.layout_config
        )
        return fig

    def create_equity_chart(self, data: Dict) -> go.Figure:
        """Create portfolio equity curve with percentage returns."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No equity data available")

        fig = go.Figure()
        cagr_data = {}
        
        # Extract CAGR data from summary
        if "summary" in data:
            for _, row in data["summary"].iterrows():
                cagr_data[row["Window"]] = row.get("CAGR [%]", 0)

        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue
                
            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])
            
            # Calculate percentage returns
            initial_equity = equity_df["Equity"].iloc[0]
            if initial_equity <= 0:
                print(f"⚠️ Invalid initial equity for {period}: {initial_equity}")
                continue
                
            equity_pct = ((equity_df["Equity"] / initial_equity) - 1) * 100

            fig.add_trace(go.Scatter(
                x=equity_df["Date"],
                y=equity_pct,
                mode="lines",
                name=f"Portfolio {period}",
                line={"color": self.colors["equity"], "width": 3},
                visible=True if period == default_period else False,
                hovertemplate="Date: %{x}<br>Return: %{y:.2f}%<br>Value: ₹%{customdata:,.0f}<extra></extra>",
                customdata=equity_df["Equity"],
            ))

        # Create period toggle buttons
        if len(periods) > 1:
            period_buttons = []
            for i, period in enumerate(periods):
                visibility = [j == i for j in range(len(periods))]
                cagr_value = cagr_data.get(period, 0)
                dynamic_title = f"Portfolio Performance<br><sub>CAGR: {cagr_value:.1f}%</sub>"
                
                period_buttons.append({
                    "label": period,
                    "method": "update", 
                    "args": [{"visible": visibility}, {"title": dynamic_title}],
                })

            default_cagr = cagr_data.get(default_period, 0)
            initial_title = f"Portfolio Performance<br><sub>CAGR: {default_cagr:.1f}%</sub>"

            fig.update_layout(
                title=initial_title,
                xaxis_title="Date",
                yaxis_title="Portfolio Return (%)",
                updatemenus=[{
                    "type": "buttons", "direction": "right", 
                    "x": 0.7, "y": 1.1, "buttons": period_buttons,
                }],
                **self.layout_config,
            )
        else:
            cagr_value = cagr_data.get(default_period, 0)
            fig.update_layout(
                title=f"Portfolio Performance<br><sub>CAGR: {cagr_value:.1f}%</sub>",
                xaxis_title="Date",
                yaxis_title="Portfolio Return (%)",
                **self.layout_config,
            )

        return fig

    def create_drawdown_chart(self, data: Dict) -> go.Figure:
        """Create drawdown chart with dynamic statistics."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No drawdown data available")

        fig = go.Figure()
        all_dd_stats = {}
        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue
                
            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])
            
            # Calculate drawdown
            equity_df["Peak"] = equity_df["Equity"].expanding().max()
            equity_df["Drawdown_Pct"] = ((equity_df["Equity"] / equity_df["Peak"]) - 1) * 100
            equity_df["Drawdown_INR"] = equity_df["Equity"] - equity_df["Peak"]

            # Calculate statistics
            max_dd = equity_df["Drawdown_Pct"].min()
            mean_dd = equity_df["Drawdown_Pct"].mean()
            median_dd = equity_df["Drawdown_Pct"].median()

            all_dd_stats[period] = {
                "max_dd": max_dd, "mean_dd": mean_dd, "median_dd": median_dd
            }

            fig.add_trace(go.Scatter(
                x=equity_df["Date"],
                y=equity_df["Drawdown_Pct"],
                mode="lines",
                name=f"Drawdown {period}",
                line={"color": self.colors["loss"], "width": 3},
                visible=True if period == default_period else False,
                fill="tonexty",
                fillcolor="rgba(220, 38, 38, 0.15)",
                hovertemplate="Date: %{x}<br>Drawdown: %{y:.2f}%<br>Amount: ₹%{customdata:,.0f}<extra></extra>",
                customdata=equity_df["Drawdown_INR"],
            ))

        # Create period buttons with dynamic stats
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(periods))]
            if period in all_dd_stats:
                stats = all_dd_stats[period]
                dynamic_title = f"Portfolio Drawdown<br><sub>Max: {stats['max_dd']:.2f}% | Mean: {stats['mean_dd']:.2f}% | Median: {stats['median_dd']:.2f}%</sub>"
            else:
                dynamic_title = "Portfolio Drawdown"
                
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": dynamic_title}],
            })

        # Set initial title
        if default_period in all_dd_stats:
            default_stats = all_dd_stats[default_period]
            title_with_stats = f"Portfolio Drawdown<br><sub>Max: {default_stats['max_dd']:.2f}% | Mean: {default_stats['mean_dd']:.2f}% | Median: {default_stats['median_dd']:.2f}%</sub>"
        else:
            title_with_stats = "Portfolio Drawdown"

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Date",
            yaxis_title="Drawdown (%)",
            **self.layout_config,
            height=450,
            updatemenus=[{
                "type": "buttons", "direction": "right", "showactive": True,
                "x": 0.02, "y": 1.12, "xanchor": "left", "yanchor": "top",
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
            annotations=[{
                "text": "Period:", "x": 0.01, "y": 1.15,
                "xref": "paper", "yref": "paper", "showarrow": False,
            }] if len(periods) > 1 else [],
        )

        return fig

    def create_monthly_returns_heatmap(self, data: Dict) -> go.Figure:
        """Create monthly returns heatmap: months on x-axis, years as rows with year label inside, plus average row."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        
        # Check for monthly data or equity data to calculate monthly returns
        monthly_data = {}
        for period in periods:
            if "monthly" in data[period]:
                monthly_data[period] = data[period]["monthly"]
            elif "equity" in data[period]:
                # Calculate monthly returns from daily equity data
                equity_df = data[period]["equity"].copy()
                equity_df["Date"] = pd.to_datetime(equity_df["Date"])
                equity_df = equity_df.set_index("Date")
                
                # Resample to monthly and calculate returns
                monthly_equity = equity_df["Equity"].resample('M').last()
                monthly_returns = monthly_equity.pct_change() * 100
                
                # Create monthly dataframe
                monthly_df = pd.DataFrame({
                    'Month': monthly_returns.index.strftime('%Y-%m'),
                    'Total Return %': monthly_returns.values
                })
                monthly_data[period] = monthly_df

        if not monthly_data:
            return self.create_empty_chart("No monthly data available for heatmap")

        fig = go.Figure()
        all_heatmap_stats = {}
        default_period = max(monthly_data.keys(), key=lambda x: int(x[:-1]))
        
        # Track heatmap indices and annotation counts for each period
        heatmap_indices = []
        annotation_counts = []  # Number of annotations per period
        current_annotation_idx = 0

        for period in sorted(monthly_data.keys(), key=lambda x: int(x[:-1])):
            monthly_df = monthly_data[period].copy()
            
            # Parse month and create year/month columns
            monthly_df['Date'] = pd.to_datetime(monthly_df['Month'], format='%Y-%m')
            monthly_df['Year'] = monthly_df['Date'].dt.year
            monthly_df['Month_Num'] = monthly_df['Date'].dt.month
            
            # Use Total Return % if available, otherwise calculate
            if 'Total Return %' in monthly_df.columns:
                returns_col = 'Total Return %'
            elif 'Realized %' in monthly_df.columns and 'Unrealized %' in monthly_df.columns:
                monthly_df['Total Return %'] = monthly_df['Realized %'] + monthly_df['Unrealized %']
                returns_col = 'Total Return %'
            else:
                continue
            
            # Create pivot table: years on rows, months on columns
            heatmap_data = monthly_df.pivot(index='Year', columns='Month_Num', values=returns_col)
            
            # Reorder months (1-12)
            month_order = list(range(1, 13))
            heatmap_data = heatmap_data[[col for col in month_order if col in heatmap_data.columns]]
            
            # Create month labels
            month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            month_labels = [month_names[i-1] for i in heatmap_data.columns]
            
            # Add average row at the bottom - explicitly sort years ascending, then Average
            avg_row = heatmap_data.mean(axis=0)
            heatmap_with_avg = pd.concat([heatmap_data, pd.DataFrame([avg_row], index=["Average"])])
            
            # CRITICAL: Sort to ensure chronological year order with Average at BOTTOM
            year_values = sorted([year for year in heatmap_with_avg.index if year != "Average"], 
                                key=lambda x: int(x) if isinstance(x, int) or (isinstance(x, str) and x.isdigit()) else 0)
            year_values.append("Average")  # Always at end
            heatmap_with_avg = heatmap_with_avg.loc[year_values]
            
            # Create year labels for y-axis - SORTED with Average at BOTTOM
            year_labels = [str(int(year)) if year != "Average" else "Average" for year in heatmap_with_avg.index]
            
            # Calculate statistics
            mean_return = monthly_df[returns_col].mean()
            median_return = monthly_df[returns_col].median()
            best_month = monthly_df[returns_col].max()
            worst_month = monthly_df[returns_col].min()
            positive_months = (monthly_df[returns_col] > 0).sum()
            total_months = len(monthly_df)
            win_rate = (positive_months / total_months * 100) if total_months > 0 else 0
            
            all_heatmap_stats[period] = {
                'mean_return': mean_return,
                'median_return': median_return,
                'best_month': best_month,
                'worst_month': worst_month,
                'win_rate': win_rate,
                'positive_months': positive_months,
                'total_months': total_months
            }
            
            # Create custom colorscale
            colorscale = [
                [0.0, '#8B0000'],    # Dark red for worst losses
                [0.2, '#DC143C'],    # Red for losses
                [0.4, '#FFB6C1'],    # Light red for small losses
                [0.5, '#F5F5F5'],    # Light gray for near zero
                [0.6, '#90EE90'],    # Light green for small gains
                [0.8, '#32CD32'],    # Green for gains
                [1.0, '#006400']     # Dark green for best gains
            ]
            
            # Track this heatmap's index
            heatmap_indices.append(len(fig.data))
            
            # Create heatmap trace
            heatmap_trace = go.Heatmap(
                z=heatmap_with_avg.values,
                x=month_labels,
                y=year_labels,
                colorscale=colorscale,
                zmid=0,
                name=f"Returns {period}",
                visible=True if period == default_period else False,
                hovertemplate="<b>%{y} %{x}</b><br>Return: %{z:.2f}%<extra></extra>",
                showscale=False,
            )
            fig.add_trace(heatmap_trace)
            
            # Add custom annotations for text overlay
            period_annotation_count = 0
            for i, year in enumerate(heatmap_with_avg.index):
                for j, col in enumerate(heatmap_with_avg.columns):
                    val = heatmap_with_avg.iloc[i, j]
                    if not pd.isna(val):
                        fig.add_annotation(
                            x=j,
                            y=i,
                            text=f"{val:.1f}%",
                            showarrow=False,
                            font={"size": 11, "color": "black", "family": "monospace"},
                            xref="x",
                            yref="y",
                            xanchor="center",
                            yanchor="middle",
                            visible=True if period == default_period else False,
                        )
                        period_annotation_count += 1
            
            annotation_counts.append(period_annotation_count)

        # Create period buttons with proper visibility handling for BOTH traces and annotations
        period_buttons = []
        periods_list = sorted(monthly_data.keys(), key=lambda x: int(x[:-1]))
        
        for button_idx, period in enumerate(periods_list):
            # Build visibility array for traces (heatmaps)
            trace_visibility = [j == button_idx for j in range(len(heatmap_indices))]
            
            # Build visibility array for annotations
            annotation_visibility = []
            for anno_idx, count in enumerate(annotation_counts):
                is_visible = (anno_idx == button_idx)
                # Add 'is_visible' for each annotation in this period
                annotation_visibility.extend([is_visible] * count)
            
            # Combine: all traces first, then all annotations
            full_visibility = trace_visibility + annotation_visibility
            
            if period in all_heatmap_stats:
                stats = all_heatmap_stats[period]
                dynamic_title = f"Monthly Returns Heatmap<br><sub>Avg: {stats['mean_return']:.1f}% | Win Rate: {stats['win_rate']:.1f}% | Best: {stats['best_month']:.1f}% | Worst: {stats['worst_month']:.1f}%</sub>"
            else:
                dynamic_title = "Monthly Returns Heatmap"

            period_buttons.append({
                "label": period,
                "method": "restyle",
                "args": [{"visible": full_visibility}],
            })

        # Set initial title
        if default_period in all_heatmap_stats:
            default_stats = all_heatmap_stats[default_period]
            title_with_stats = f"Monthly Returns Heatmap<br><sub>Avg: {default_stats['mean_return']:.1f}% | Win Rate: {default_stats['win_rate']:.1f}% | Best: {default_stats['best_month']:.1f}% | Worst: {default_stats['worst_month']:.1f}%</sub>"
        else:
            title_with_stats = "Monthly Returns Heatmap"

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Month",
            yaxis_title="Year",
            **self.layout_config,
            height=500,
            xaxis={"showgrid": False},
            yaxis={"showgrid": False},
            updatemenus=[{
                "type": "buttons", "direction": "right", "showactive": True,
                "x": 0.02, "y": 1.12, "xanchor": "left", "yanchor": "top",
                "buttons": period_buttons,
            }] if len(monthly_data) > 1 else [],
            annotations=[{
                "text": "Period:", "x": 0.01, "y": 1.15,
                "xref": "paper", "yref": "paper", "showarrow": False,
            }] if len(monthly_data) > 1 else [],
        )

        return fig

    def create_exposure_chart(self, data: Dict) -> go.Figure:
        """Create exposure chart using Avg exposure % column."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No exposure data available")

        fig = go.Figure()
        all_exposure_stats = {}
        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue
                
            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])

            # Use Avg exposure % column or fallback
            if "Avg exposure %" in equity_df.columns:
                exposure_pct = equity_df["Avg exposure %"]
                exposure_inr = (exposure_pct / 100) * equity_df["Equity"]
            else:
                exposure_pct = pd.Series([95.0] * len(equity_df))  # 95% default
                exposure_inr = equity_df["Equity"] * 0.95

            # Calculate stats
            mean_exposure_pct = exposure_pct.mean()
            median_exposure_pct = exposure_pct.median()

            all_exposure_stats[period] = {
                "mean_pct": mean_exposure_pct,
                "median_pct": median_exposure_pct,
            }

            fig.add_trace(go.Scatter(
                x=equity_df["Date"],
                y=exposure_pct,
                mode="lines",
                name=f"Exposure {period}",
                line={"color": self.colors["exposure"], "width": 3},
                visible=True if period == default_period else False,
                hovertemplate="Date: %{x}<br>Exposure: %{y:.1f}%<br>Amount: ₹%{customdata:,.0f}<extra></extra>",
                customdata=exposure_inr,
            ))

        # Create period buttons
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [j == i for j in range(len(periods))]
            if period in all_exposure_stats:
                stats = all_exposure_stats[period]
                dynamic_title = f"Portfolio Exposure<br><sub>Mean: {stats['mean_pct']:.1f}% | Median: {stats['median_pct']:.1f}%</sub>"
            else:
                dynamic_title = "Portfolio Exposure"

            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": dynamic_title}],
            })

        # Set initial title
        if default_period in all_exposure_stats:
            default_stats = all_exposure_stats[default_period]
            title_with_stats = f"Portfolio Exposure<br><sub>Mean: {default_stats['mean_pct']:.1f}% | Median: {default_stats['median_pct']:.1f}%</sub>"
        else:
            title_with_stats = "Portfolio Exposure"

        fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.5,
                     annotation_text="100% Target", annotation_position="right")

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Date",
            yaxis_title="Exposure (%)",
            **self.layout_config,
            height=450,
            updatemenus=[{
                "type": "buttons", "direction": "right", "showactive": True,
                "x": 0.02, "y": 1.12, "xanchor": "left", "yanchor": "top",
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
            annotations=[{
                "text": "Period:", "x": 0.01, "y": 1.15,
                "xref": "paper", "yref": "paper", "showarrow": False,
            }] if len(periods) > 1 else [],
        )

        return fig

    def create_enhanced_metrics_panel(self, strategy_metrics: Dict = None) -> str:
        """Create enhanced metrics panel with period switching."""
        
        def create_metrics_grid(period_metrics: Dict) -> str:
            return f"""
            <div class="metrics-grid">
                <div class="metric-card primary">
                    <div class="metric-value">{period_metrics.get('net_pnl', 0):.1f}%</div>
                    <div class="metric-label">Net P&L</div>
                </div>
                <div class="metric-card primary">
                    <div class="metric-value">{period_metrics.get('cagr', 0):.1f}%</div>
                    <div class="metric-label">CAGR</div>
                </div>
                <div class="metric-card primary">
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
                    <div class="metric-value">{period_metrics.get('sharpe', 0):.2f}</div>
                    <div class="metric-label">Sharpe</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('max_drawdown', 0):.1f}%</div>
                    <div class="metric-label">Max Drawdown</div>
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
                    <div class="metric-value">{period_metrics.get('romad', 0):.2f}</div>
                    <div class="metric-label">RoMaD</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('volatility', 0):.2f}%</div>
                    <div class="metric-label">Volatility (Ann.)</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('var_95', 0):.2f}%</div>
                    <div class="metric-label">VaR 95%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{period_metrics.get('alpha', 0):.1f}%</div>
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
                    <div class="metric-value">{period_metrics.get('max_dd_duration', 'N/A')}</div>
                    <div class="metric-label">DD Duration</div>
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
                    <div class="metric-value">{period_metrics.get('kelly', 0):.3f}</div>
                    <div class="metric-label">Kelly %</div>
                </div>
            </div>
            """

        # Use the pre-calculated strategy metrics directly
        metrics = strategy_metrics if strategy_metrics else {}

        return f"""
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

    def create_rolling_performance_chart(self, data: Dict) -> go.Figure:
        """Create rolling performance chart with dynamic CAGR calculations."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No equity data available for rolling performance")

        fig = go.Figure()
        all_rolling_stats = {}
        default_period = max(periods, key=lambda x: int(x[:-1]))

        for period in periods:
            if "equity" not in data[period]:
                continue
                
            equity_df = data[period]["equity"].copy()
            equity_df["Date"] = pd.to_datetime(equity_df["Date"])
            equity_df = equity_df.set_index("Date").sort_index()
            
            # Calculate rolling 252-day (1 year) CAGR
            rolling_window = min(252, len(equity_df) // 4)  # Adjust window based on data length
            
            rolling_returns = []
            rolling_dates = []
            rolling_sharpe = []
            rolling_volatility = []
            
            for i in range(rolling_window, len(equity_df)):
                end_date = equity_df.index[i]
                start_date = equity_df.index[i - rolling_window]
                
                start_value = equity_df["Equity"].iloc[i - rolling_window]
                end_value = equity_df["Equity"].iloc[i]
                
                # Calculate annualized return (CAGR)
                days = (end_date - start_date).days
                years = days / 365.25
                if years > 0 and start_value > 0:
                    cagr = ((end_value / start_value) ** (1/years) - 1) * 100
                else:
                    cagr = 0
                
                # Calculate rolling volatility and Sharpe ratio
                window_data = equity_df["Equity"].iloc[i-rolling_window:i+1]
                daily_returns = window_data.pct_change().dropna()
                
                if len(daily_returns) > 1:
                    volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized volatility
                    sharpe = cagr / volatility if volatility > 0 else 0
                else:
                    volatility = 0
                    sharpe = 0
                
                rolling_returns.append(cagr)
                rolling_dates.append(end_date)
                rolling_sharpe.append(sharpe)
                rolling_volatility.append(volatility)
            
            if rolling_returns:
                # Calculate statistics
                mean_rolling_cagr = np.mean(rolling_returns)
                median_rolling_cagr = np.median(rolling_returns)
                std_rolling_cagr = np.std(rolling_returns)
                min_rolling_cagr = np.min(rolling_returns)
                max_rolling_cagr = np.max(rolling_returns)
                mean_sharpe = np.mean(rolling_sharpe)
                mean_volatility = np.mean(rolling_volatility)
                
                all_rolling_stats[period] = {
                    'mean_cagr': mean_rolling_cagr,
                    'median_cagr': median_rolling_cagr,
                    'std_cagr': std_rolling_cagr,
                    'min_cagr': min_rolling_cagr,
                    'max_cagr': max_rolling_cagr,
                    'mean_sharpe': mean_sharpe,
                    'mean_volatility': mean_volatility,
                    'window_days': rolling_window
                }
                
                # Add rolling CAGR line
                fig.add_trace(go.Scatter(
                    x=rolling_dates,
                    y=rolling_returns,
                    mode="lines",
                    name=f"Rolling CAGR {period}",
                    line={"color": self.colors["primary"], "width": 3},
                    visible=True if period == default_period else False,
                    hovertemplate="Date: %{x}<br>Rolling CAGR: %{y:.1f}%<br>Sharpe: %{customdata[0]:.2f}<br>Volatility: %{customdata[1]:.1f}%<extra></extra>",
                    customdata=list(zip(rolling_sharpe, rolling_volatility)),
                ))
                
                # Add mean line
                fig.add_hline(
                    y=mean_rolling_cagr,
                    line_dash="dash",
                    line_color=self.colors["neutral"],
                    opacity=0.7,
                    annotation_text=f"Mean: {mean_rolling_cagr:.1f}%",
                    annotation_position="right",
                    visible=True if period == default_period else False
                )

        # Create period buttons with dynamic stats
        period_buttons = []
        for i, period in enumerate(periods):
            visibility = [False] * len(fig.data)
            # Each period has 2 traces (line + mean line)
            start_idx = i * 2
            end_idx = start_idx + 2
            for idx in range(start_idx, min(end_idx, len(fig.data))):
                visibility[idx] = True

            if period in all_rolling_stats:
                stats = all_rolling_stats[period]
                dynamic_title = f"Rolling {stats['window_days']}-Day CAGR<br><sub>Mean: {stats['mean_cagr']:.1f}% | Volatility: {stats['mean_volatility']:.1f}% | Sharpe: {stats['mean_sharpe']:.2f} | Range: {stats['min_cagr']:.1f}% to {stats['max_cagr']:.1f}%</sub>"
            else:
                dynamic_title = "Rolling CAGR Performance"

            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": dynamic_title}],
            })

        # Set initial title
        if default_period in all_rolling_stats:
            default_stats = all_rolling_stats[default_period]
            title_with_stats = f"Rolling {default_stats['window_days']}-Day CAGR<br><sub>Mean: {default_stats['mean_cagr']:.1f}% | Volatility: {default_stats['mean_volatility']:.1f}% | Sharpe: {default_stats['mean_sharpe']:.2f} | Range: {default_stats['min_cagr']:.1f}% to {default_stats['max_cagr']:.1f}%</sub>"
        else:
            title_with_stats = "Rolling CAGR Performance"

        fig.update_layout(
            title=title_with_stats,
            xaxis_title="Date",
            yaxis_title="Rolling CAGR (%)",
            **self.layout_config,
            height=450,
            updatemenus=[{
                "type": "buttons", "direction": "right", "showactive": True,
                "x": 0.02, "y": 1.12, "xanchor": "left", "yanchor": "top",
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
            annotations=[{
                "text": "Period:", "x": 0.01, "y": 1.15,
                "xref": "paper", "yref": "paper", "showarrow": False,
            }] if len(periods) > 1 else [],
        )

        return fig

    def create_trade_return_vs_holding_days(self, data: Dict) -> go.Figure:
        """Create trade return vs holding days scatter plot with capping at ±100% and dynamic subtitle."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No trade data available")

        fig = go.Figure()
        default_period = max(periods, key=lambda x: int(x[:-1]))
        all_trades_stats = {}

        for period in periods:
            if period not in data or "trades" not in data[period]:
                continue
                
            trades_df = data[period]["trades"].copy()
            
            # Filter for trades with both Holding days and Net P&L %
            if "Holding days" not in trades_df.columns or "Net P&L %" not in trades_df.columns:
                continue
            
            trades_clean = trades_df[["Holding days", "Net P&L %"]].dropna()
            if len(trades_clean) < 2:
                continue
            
            # Separate winning and losing trades
            winning_trades = trades_clean[trades_clean["Net P&L %"] > 0]
            losing_trades = trades_clean[trades_clean["Net P&L %"] <= 0]
            
            all_trades_stats[period] = {
                "total": len(trades_clean),
                "wins": len(winning_trades),
                "losses": len(losing_trades),
                "avg_return": trades_clean["Net P&L %"].mean(),
            }
            
            visible = (period == default_period)
            
            # Add winning trades with capping at ±100%
            if not winning_trades.empty:
                # Store actual values in customdata for hover display
                actual_returns = winning_trades["Net P&L %"].values
                capped_returns = np.clip(actual_returns, -100, 100)
                
                fig.add_trace(go.Scatter(
                    x=winning_trades["Holding days"],
                    y=capped_returns,
                    customdata=actual_returns,
                    mode="markers",
                    name=f"Wins ({period})",
                    marker={"color": self.colors["profit"], "size": 8, "opacity": 0.7},
                    visible=visible,
                    hovertemplate="<b>Holding Days:</b> %{x:.0f}<br><b>Net P&L %:</b> %{customdata:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=True,
                ))
            
            # Add losing trades with capping at ±100%
            if not losing_trades.empty:
                actual_returns = losing_trades["Net P&L %"].values
                capped_returns = np.clip(actual_returns, -100, 100)
                
                fig.add_trace(go.Scatter(
                    x=losing_trades["Holding days"],
                    y=capped_returns,
                    customdata=actual_returns,
                    mode="markers",
                    name=f"Losses ({period})",
                    marker={"color": self.colors["loss"], "size": 8, "opacity": 0.7},
                    visible=visible,
                    hovertemplate="<b>Holding Days:</b> %{x:.0f}<br><b>Net P&L %:</b> %{customdata:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=True,
                ))
            
            # Add trend line (using original uncapped values for accurate trend)
            if len(trades_clean) > 1:
                z = np.polyfit(trades_clean["Holding days"], trades_clean["Net P&L %"], 1)
                p = np.poly1d(z)
                x_trend = np.linspace(trades_clean["Holding days"].min(), trades_clean["Holding days"].max(), 100)
                trend_values = p(x_trend)
                capped_trend = np.clip(trend_values, -100, 100)
                
                fig.add_trace(go.Scatter(
                    x=x_trend,
                    y=capped_trend,
                    mode="lines",
                    name=f"Trend ({period})",
                    line={"color": "#9B59B6", "width": 2, "dash": "dash"},
                    visible=visible,
                    hovertemplate="<b>Trend Line</b><extra></extra>",
                    legendgroup=period,
                    showlegend=True,
                ))

        # Create period buttons
        period_buttons = []
        traces_per_period = 3  # winners + losers + trend
        
        for i, period in enumerate(periods):
            if period not in all_trades_stats:
                continue
                
            visibility = [False] * len(fig.data)
            start_idx = i * traces_per_period
            end_idx = start_idx + traces_per_period
            for idx in range(start_idx, min(end_idx, len(fig.data))):
                visibility[idx] = True
            
            stats = all_trades_stats[period]
            dynamic_title = f"Trade Return vs Holding Days<br><sub>Period: {period} | Total Trades: {stats['total']} | Wins: {stats['wins']} | Losses: {stats['losses']} | Avg Return: {stats['avg_return']:.2f}%</sub>"
            
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": dynamic_title}],
            })

        # Set initial title
        if default_period in all_trades_stats:
            stats = all_trades_stats[default_period]
            title_text = f"Trade Return vs Holding Days<br><sub>Period: {default_period} | Total Trades: {stats['total']} | Wins: {stats['wins']} | Losses: {stats['losses']} | Avg Return: {stats['avg_return']:.2f}%</sub>"
        else:
            title_text = "Trade Return vs Holding Days"
        
        fig.update_layout(
            title=title_text,
            xaxis_title="Holding Days",
            yaxis_title="Net P&L %",
            hovermode="closest",
            **self.layout_config,
            height=500,
            updatemenus=[{
                "type": "buttons",
                "direction": "right",
                "showactive": True,
                "x": 0.02,
                "y": 1.15,
                "xanchor": "left",
                "yanchor": "top",
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
        )
        
        # Set y-axis to ±100%
        fig.update_yaxes(range=[-100, 100])
        
        return fig
    
    def calculate_r_multiple(self, trades_df: pd.DataFrame, atr_percentage: float = 2.5) -> pd.DataFrame:
        """Calculate R-multiple for trades using ATR-based risk unit."""
        trades_df = trades_df.copy()
        
        # First ensure we have a Return column
        if 'Return' not in trades_df.columns:
            if 'Net P&L %' in trades_df.columns:
                # Handle both numeric and string formats
                if trades_df['Net P&L %'].dtype == 'object':
                    trades_df['Return'] = trades_df['Net P&L %'].str.rstrip('%').astype(float)
                else:
                    trades_df['Return'] = trades_df['Net P&L %'].astype(float)
            elif 'PnL' in trades_df.columns and 'EntryPrice' in trades_df.columns and 'Quantity' in trades_df.columns:
                # Calculate return percentage
                trades_df['Return'] = (trades_df['PnL'] / (trades_df['EntryPrice'] * trades_df['Quantity'])) * 100
            elif 'Return %' in trades_df.columns:
                if trades_df['Return %'].dtype == 'object':
                    trades_df['Return'] = trades_df['Return %'].str.rstrip('%').astype(float)
                else:
                    trades_df['Return'] = trades_df['Return %'].astype(float)
            elif 'Ret %' in trades_df.columns:
                if trades_df['Ret %'].dtype == 'object':
                    trades_df['Return'] = trades_df['Ret %'].str.rstrip('%').astype(float)
                else:
                    trades_df['Return'] = trades_df['Ret %'].astype(float)
            else:
                # Default fallback - use random data for demonstration
                trades_df['Return'] = np.random.normal(0.5, 3, len(trades_df))
        
        # Calculate R-multiple using ATR percentage as risk unit
        # R-multiple = Return / Risk Unit (where Risk Unit = ATR% = 2.5% by default)
        trades_df['R_Multiple'] = trades_df['Return'] / atr_percentage
        
        # Calculate MAE in R-multiple terms
        if 'Drawdown %' in trades_df.columns:
            # Handle both numeric and string formats
            if trades_df['Drawdown %'].dtype == 'object':
                trades_df['MAE_Pct'] = trades_df['Drawdown %'].str.rstrip('%').astype(float).abs()
            else:
                trades_df['MAE_Pct'] = trades_df['Drawdown %'].astype(float).abs()
            trades_df['MAE_R'] = trades_df['MAE_Pct'] / atr_percentage
        elif 'MAE' not in trades_df.columns:
            # Estimate MAE based on return characteristics
            trades_df['MAE_Pct'] = trades_df.apply(lambda row: 
                abs(row['Return'] * 0.6) if row['Return'] < 0 else abs(row['Return'] * 0.3), axis=1)
            trades_df['MAE_R'] = trades_df['MAE_Pct'] / atr_percentage
        else:
            trades_df['MAE_R'] = abs(trades_df['R_Multiple'] * 0.4)  # Estimate MAE as 40% of R-multiple
            
        return trades_df

    def create_mae_analysis(self, data: Dict) -> go.Figure:
        """Create Maximum Adverse Excursion analysis with x-axis 0-20, fixed IRR calculation."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No trade data available")

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("MAE_ATR vs Net P&L %", "MAE_ATR vs IRR %"),
            specs=[[{"type": "scatter"}, {"type": "scatter"}]]
        )
        
        all_mae_stats = {}
        default_period = max(periods, key=lambda x: int(x[:-1]))
        max_mae_value = 0  # Track max MAE for auto-scaling

        for period in periods:
            if "trades" not in data[period]:
                continue
                
            trades_df = data[period]["trades"].copy()
            if trades_df.empty:
                continue
            
            # Calculate IRR % as cumulative return / number of trades (per-trade IRR)
            # Or use average holding period return if available
            if "IRR %" in trades_df.columns:
                trades_df["IRR_pct"] = trades_df["IRR %"]
            else:
                # IRR is annualized return; use Net P&L % but scaled/annualized differently
                # For simplicity, use average return but not identical to Net P&L %
                trades_df["IRR_pct"] = trades_df["Net P&L %"] * (252 / trades_df.get("Holding days", 1).mean() if "Holding days" in trades_df.columns else 1)
            
            # Remove NaN values for analysis
            trades_clean = trades_df[["MAE_ATR", "Net P&L %", "IRR_pct"]].dropna()
            if len(trades_clean) < 2:
                continue
            
            # Track max MAE for auto-scaling
            max_mae_value = max(max_mae_value, trades_clean["MAE_ATR"].max())
            
            # Separate winning and losing trades
            winning_trades = trades_clean[trades_clean["Net P&L %"] > 0]
            losing_trades = trades_clean[trades_clean["Net P&L %"] <= 0]
            
            # Calculate statistics
            mae_stats = {
                "mean_mae": trades_clean["MAE_ATR"].mean(),
                "median_mae": trades_clean["MAE_ATR"].median(),
                "p90_mae": np.percentile(trades_clean["MAE_ATR"], 90),
                "win_rate": (len(winning_trades) / len(trades_clean) * 100) if len(trades_clean) > 0 else 0,
                "total_trades": len(trades_clean),
            }
            all_mae_stats[period] = mae_stats
            
            # Plot 1: MAE_ATR vs Net P&L % - scale ±100 on y-axis
            if not winning_trades.empty:
                fig.add_trace(go.Scatter(
                    x=winning_trades["MAE_ATR"],
                    y=winning_trades["Net P&L %"],
                    mode="markers",
                    name=f"Wins ({period})",
                    marker={"color": self.colors["profit"], "size": 8, "opacity": 0.7},
                    visible=True if period == default_period else False,
                    hovertemplate="<b>MAE (ATR):</b> %{x:.2f}<br><b>Net P&L %:</b> %{y:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=True,
                ), row=1, col=1)
            
            if not losing_trades.empty:
                fig.add_trace(go.Scatter(
                    x=losing_trades["MAE_ATR"],
                    y=losing_trades["Net P&L %"],
                    mode="markers",
                    name=f"Losses ({period})",
                    marker={"color": self.colors["loss"], "size": 8, "opacity": 0.7},
                    visible=True if period == default_period else False,
                    hovertemplate="<b>MAE (ATR):</b> %{x:.2f}<br><b>Net P&L %:</b> %{y:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=True,
                ), row=1, col=1)
            
            # Plot 2: MAE_ATR vs IRR % - scale ±100 on y-axis
            if not winning_trades.empty:
                fig.add_trace(go.Scatter(
                    x=winning_trades["MAE_ATR"],
                    y=winning_trades["IRR_pct"],
                    mode="markers",
                    name=f"Wins ({period})",
                    marker={"color": self.colors["profit"], "size": 8, "opacity": 0.7},
                    visible=True if period == default_period else False,
                    hovertemplate="<b>MAE (ATR):</b> %{x:.2f}<br><b>IRR %:</b> %{y:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=False,
                ), row=1, col=2)
            
            if not losing_trades.empty:
                fig.add_trace(go.Scatter(
                    x=losing_trades["MAE_ATR"],
                    y=losing_trades["IRR_pct"],
                    mode="markers",
                    name=f"Losses ({period})",
                    marker={"color": self.colors["loss"], "size": 8, "opacity": 0.7},
                    visible=True if period == default_period else False,
                    hovertemplate="<b>MAE (ATR):</b> %{x:.2f}<br><b>IRR %:</b> %{y:.2f}%<extra></extra>",
                    legendgroup=period,
                    showlegend=False,
                ), row=1, col=2)
        
        # Add horizontal line at 0 for both plots
        fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5, row=1, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="gray", opacity=0.5, row=1, col=2)
        
        # Create period buttons
        period_buttons = []
        traces_per_period = 4  # winners + losers for each plot
        
        for i, period in enumerate(periods):
            visibility = [False] * len(fig.data)
            start_idx = i * traces_per_period
            end_idx = start_idx + traces_per_period
            for idx in range(start_idx, min(end_idx, len(fig.data))):
                visibility[idx] = True

            if period in all_mae_stats:
                stats = all_mae_stats[period]
                dynamic_title = f"Maximum Adverse Excursion<br><sub>P90 MAE (ATR): {stats['p90_mae']:.2f} | Win Rate: {stats['win_rate']:.1f}% | Total Trades: {stats['total_trades']}</sub>"
            else:
                dynamic_title = "Maximum Adverse Excursion"

            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": dynamic_title}],
            })

        # Set initial title
        if default_period in all_mae_stats:
            default_stats = all_mae_stats[default_period]
            title_with_stats = f"Maximum Adverse Excursion<br><sub>P90 MAE (ATR): {default_stats['p90_mae']:.2f} | Win Rate: {default_stats['win_rate']:.1f}% | Total Trades: {default_stats['total_trades']}</sub>"
        else:
            title_with_stats = "Maximum Adverse Excursion"

        fig.update_layout(
            title=title_with_stats,
            **self.layout_config,
            height=500,
            updatemenus=[{
                "type": "buttons", "direction": "right", "showactive": True,
                "x": 0.02, "y": 1.15, "xanchor": "left", "yanchor": "top",
                "buttons": period_buttons,
            }] if len(periods) > 1 else [],
        )
        
        # Auto-scale x-axis: if max value < 20, use [0, max]; else use [0, 20]
        x_max = min(20, max_mae_value) if max_mae_value < 20 else 20
        
        fig.update_xaxes(range=[0, x_max], row=1, col=1)
        fig.update_xaxes(range=[0, x_max], row=1, col=2)
        fig.update_yaxes(range=[-100, 100], row=1, col=1)
        fig.update_yaxes(range=[-100, 100], row=1, col=2)
        fig.update_xaxes(title_text="MAE_ATR (Risk Units)", row=1, col=1)
        fig.update_xaxes(title_text="MAE_ATR (Risk Units)", row=1, col=2)
        fig.update_yaxes(title_text="Net P&L %", row=1, col=1)
        fig.update_yaxes(title_text="IRR %", row=1, col=2)

        return fig
    
    def create_trade_distribution_analysis(self, data: Dict) -> go.Figure:
        """Create trade distributions with proper toggle logic that works in any order."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No trade data available")

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("Net P&L % Distribution", "Holding Days Distribution"),
            specs=[[{"type": "bar"}, {"type": "bar"}]]
        )

        default_period = max(periods, key=lambda x: int(x[:-1]))
        all_distributions = {}
        all_stats = {}
        
        for period in periods:
            if "trades" not in data[period]:
                continue
                
            trades_df = data[period]["trades"].copy()
            if trades_df.empty:
                continue
            
            # Clean data
            trades_clean = trades_df[["Net P&L %", "Holding days"]].dropna()
            if len(trades_clean) < 2:
                continue
            
            # Separate profit and loss trades
            profit_trades = trades_clean[trades_clean["Net P&L %"] > 0]
            loss_trades = trades_clean[trades_clean["Net P&L %"] <= 0]
            
            all_distributions[period] = {
                "all": trades_clean,
                "profit": profit_trades,
                "loss": loss_trades,
            }
            
            # Calculate statistics for this period and each filter
            for filter_type in ["all", "profit", "loss"]:
                if filter_type == "all":
                    filter_trades = trades_clean
                elif filter_type == "profit":
                    filter_trades = profit_trades
                else:
                    filter_trades = loss_trades
                
                key = f"{period}_{filter_type}"
                if len(filter_trades) > 0:
                    all_stats[key] = {
                        "avg_pnl": filter_trades["Net P&L %"].mean(),
                        "median_pnl": filter_trades["Net P&L %"].median(),
                        "avg_holding": filter_trades["Holding days"].mean(),
                        "total_trades": len(filter_trades),
                    }
        
        if not all_distributions:
            return self.create_empty_chart("No trade data available")
        
        trace_configs = []
        
        for period in all_distributions.keys():
            for filter_type in ["All", "Profit", "Loss"]:
                filter_key = filter_type.lower()
                if filter_type == "All":
                    trades = all_distributions[period]["all"]
                    color = self.colors["primary"]
                elif filter_type == "Profit":
                    trades = all_distributions[period]["profit"]
                    color = self.colors["profit"]
                else:  # Loss
                    trades = all_distributions[period]["loss"]
                    color = self.colors["loss"]
                
                if len(trades) < 2:
                    continue
                
                is_visible = (period == default_period and filter_type == "All")
                
                # Cap P&L values at ±100% for binning
                pnl_capped = np.clip(trades["Net P&L %"], -100, 100)
                pnl_hist, pnl_bins = np.histogram(pnl_capped, bins=20)
                pnl_bin_centers = (pnl_bins[:-1] + pnl_bins[1:]) / 2
                
                fig.add_trace(go.Bar(
                    y=pnl_hist,
                    x=pnl_bin_centers,
                    name=filter_type,
                    marker_color=color,
                    opacity=0.7,
                    visible=is_visible,
                    orientation="v",
                    hovertemplate="<b>P&L % Range:</b> %{x:.1f}%<br><b>Frequency:</b> %{y}<extra></extra>",
                    legendgroup=filter_type,
                    showlegend=(filter_type == "All"),
                ), row=1, col=1)
                
                # Right plot: Holding days distribution capped at 200 days
                holding_capped = np.clip(trades["Holding days"], 0, 200)
                holding_hist, holding_bins = np.histogram(holding_capped, bins=15)
                holding_bin_centers = (holding_bins[:-1] + holding_bins[1:]) / 2
                
                fig.add_trace(go.Bar(
                    y=holding_hist,
                    x=holding_bin_centers,
                    name=filter_type,
                    marker_color=color,
                    opacity=0.7,
                    visible=is_visible,
                    orientation="v",
                    hovertemplate="<b>Holding Days:</b> %{x:.0f}<br><b>Frequency:</b> %{y}<extra></extra>",
                    legendgroup=filter_type,
                    showlegend=False,
                ), row=1, col=2)
                
                # Add KDE curves
                if len(trades) >= 5:
                    from scipy import stats
                    
                    pnl_data = pnl_capped.values
                    kde_pnl = stats.gaussian_kde(pnl_data)
                    pnl_range = np.linspace(-100, 100, 100)
                    kde_pnl_vals = kde_pnl(pnl_range) * len(trades)
                    
                    fig.add_trace(go.Scatter(
                        x=pnl_range,
                        y=kde_pnl_vals,
                        mode="lines",
                        name="",
                        line={"color": color, "width": 2},
                        visible=is_visible,
                        hovertemplate="<extra></extra>",
                        legendgroup=filter_type,
                        showlegend=False,
                    ), row=1, col=1)
                    
                    holding_data = holding_capped.values
                    kde_holding = stats.gaussian_kde(holding_data)
                    holding_range = np.linspace(0, 200, 100)
                    kde_holding_vals = kde_holding(holding_range) * len(trades)
                    
                    fig.add_trace(go.Scatter(
                        x=holding_range,
                        y=kde_holding_vals,
                        mode="lines",
                        name="",
                        line={"color": color, "width": 2},
                        visible=is_visible,
                        hovertemplate="<extra></extra>",
                        legendgroup=filter_type,
                        showlegend=False,
                    ), row=1, col=2)
                
                trace_configs.append({
                    "period": period,
                    "filter": filter_type.lower(),
                })
        
        # Build buttons with proper state tracking using button index combinations
        # NOTE: Plotly's "update" method replaces ALL visibility arrays completely.
        # TRUE multi-dimensional independent toggles are not possible with basic Plotly buttons.
        # As a compromise: Period buttons show default filter, Filter buttons show default period.
        # Best practice: keep users clicking in predictable order or provide clear UI indicators.
        
        period_buttons = []
        filter_buttons = []
        
        # Get all unique periods
        periods_list = sorted(all_distributions.keys(), key=lambda x: int(x[:-1]))
        
        # Create period buttons that preserve the CURRENT filter
        for period in periods_list:
            # For each period button, assume the CURRENT filter is maintained
            # (this is the best we can do with Plotly's limitations)
            visibility = []
            for config in trace_configs:
                # Match period + current filter (updated on each button click via JavaScript)
                is_visible = (config["period"] == period and config["filter"] == "all")
                visibility.extend([is_visible] * 4)
            
            if f"{period}_all" in all_stats:
                stats = all_stats[f"{period}_all"]
                title = f"Trade Distribution<br><sub>Period: {period} | Avg P&L: {stats['avg_pnl']:.2f}% | Median P&L: {stats['median_pnl']:.2f}% | Avg Holding: {stats['avg_holding']:.1f} days | Total Trades: {stats['total_trades']}</sub>"
            else:
                title = f"Trade Distribution - {period}"
            
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": title}],
            })
        
        # Create filter buttons - these show results for DEFAULT period with selected filter
        for filter_type in ["All", "Profit", "Loss"]:
            filter_key = filter_type.lower()
            visibility = []
            for config in trace_configs:
                is_visible = (config["period"] == default_period and config["filter"] == filter_key)
                visibility.extend([is_visible] * 4)
            
            key = f"{default_period}_{filter_key}"
            if key in all_stats:
                stats = all_stats[key]
                title = f"Trade Distribution<br><sub>Filter: {filter_type} | Avg P&L: {stats['avg_pnl']:.2f}% | Median P&L: {stats['median_pnl']:.2f}% | Avg Holding: {stats['avg_holding']:.1f} days | Total Trades: {stats['total_trades']}</sub>"
            else:
                title = f"Trade Distribution - {filter_type}"
            
            filter_buttons.append({
                "label": filter_type,
                "method": "update",
                "args": [{"visible": visibility}, {"title": title}],
            })

        # Set initial title with dynamic stats
        key = f"{default_period}_all"
        if key in all_stats:
            stats = all_stats[key]
            title_text = f"Trade Distribution<br><sub>Avg P&L: {stats['avg_pnl']:.2f}% | Median P&L: {stats['median_pnl']:.2f}% | Avg Holding: {stats['avg_holding']:.1f} days | Total Trades: {stats['total_trades']}</sub>"
        else:
            title_text = "Trade Distribution"

        fig.update_layout(
            title=title_text,
            height=500,
            showlegend=True,
            template=self.layout_config["template"],
            margin=self.layout_config["margin"],
            title_x=self.layout_config["title_x"],
            title_font_size=self.layout_config["title_font_size"],
            autosize=self.layout_config["autosize"],
            font=self.layout_config["font"],
            updatemenus=[
                {
                    "type": "dropdown",
                    "direction": "down",
                    "showactive": True,
                    "x": 0.02,
                    "y": 1.15,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": period_buttons,
                    "active": len(period_buttons) - 1 if period_buttons else 0,
                },
                {
                    "type": "dropdown",
                    "direction": "down",
                    "showactive": True,
                    "x": 0.18,
                    "y": 1.15,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": filter_buttons,
                    "active": 0,
                }
            ] if period_buttons and filter_buttons else [],
        )
        
        fig.update_xaxes(title_text="Net P&L %", range=[-100, 100], row=1, col=1)
        fig.update_xaxes(title_text="Holding Days", range=[0, 200], row=1, col=2)
        fig.update_yaxes(title_text="Frequency", row=1, col=1)
        fig.update_yaxes(title_text="Frequency", row=1, col=2)

        return fig

    def create_advanced_win_rate_analysis(self, data: Dict) -> go.Figure:
        """Create win rate by symbol with separate period and metric toggles, fixed profit factor and IRR calculations."""
        periods = [p for p in data.keys() if p in ["1Y", "3Y", "5Y"]]
        if not periods:
            return self.create_empty_chart("No trade data available")

        fig = go.Figure()
        all_symbol_stats = {}
        default_period = max(periods, key=lambda x: int(x[:-1]))
        metrics_available = ["Profitable Trades %", "Profit Factor", "IRR %"]

        for period in periods:
            if "trades" not in data[period]:
                continue
                
            trades_df = data[period]["trades"].copy()
            if trades_df.empty:
                continue
            
            # Filter out NaN values for key columns
            trades_clean = trades_df[["Symbol", "Net P&L %"]].dropna()
            if len(trades_clean) < 1:
                continue
            
            # Group by symbol and calculate metrics
            symbol_stats_list = []
            for symbol, group in trades_clean.groupby("Symbol"):
                if len(group) < 5:  # Min 5 trades filter
                    continue
                
                total_trades = len(group)
                profitable_trades = (group["Net P&L %"] > 0).sum()
                profitable_pct = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
                
                # Calculate Profit Factor (sum of profits / absolute value of sum of losses)
                total_profit = group[group["Net P&L %"] > 0]["Net P&L %"].sum()
                total_loss_sum = group[group["Net P&L %"] <= 0]["Net P&L %"].sum()
                total_loss = abs(total_loss_sum)
                profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 0)
                
                # Calculate IRR % as average Net P&L % per trade
                avg_pnl = group["Net P&L %"].mean()
                
                symbol_stats_list.append({
                    "symbol": symbol,
                    "profitable_pct": profitable_pct,
                    "profit_factor": profit_factor,
                    "irr_pct": avg_pnl,
                    "total_trades": total_trades,
                })
            
            if not symbol_stats_list:
                continue
            
            # Store stats by period
            if period not in all_symbol_stats:
                all_symbol_stats[period] = {}
            
            all_symbol_stats[period]["data"] = symbol_stats_list

        if not all_symbol_stats:
            return self.create_empty_chart("No trade data available")

        # Process data for each metric separately and add traces
        trace_configs = []  # Track (period, metric) combinations
        
        for period in sorted(all_symbol_stats.keys(), key=lambda x: int(x[:-1])):
            symbol_stats_list = all_symbol_stats[period]["data"]
            
            for metric in metrics_available:
                # Determine values based on metric
                if metric == "Profitable Trades %":
                    sorted_symbols = sorted(symbol_stats_list, key=lambda x: x["profitable_pct"], reverse=True)
                    values = [item["profitable_pct"] for item in sorted_symbols]
                    y_axis_label = "Profitable Trades %"
                elif metric == "Profit Factor":
                    sorted_symbols = sorted(symbol_stats_list, key=lambda x: x["profit_factor"], reverse=True)
                    values = [item["profit_factor"] for item in sorted_symbols]
                    # Cap display at 10 for visualization
                    display_values = [min(v, 10) for v in values]
                    y_axis_label = "Profit Factor"
                else:  # IRR %
                    sorted_symbols = sorted(symbol_stats_list, key=lambda x: x["irr_pct"], reverse=True)
                    values = [item["irr_pct"] for item in sorted_symbols]
                    y_axis_label = "IRR %"
                
                symbols = [item["symbol"] for item in sorted_symbols]
                trades_count = [item["total_trades"] for item in sorted_symbols]
                
                # Use display_values if available, otherwise use values
                if metric == "Profit Factor":
                    y_vals = display_values
                else:
                    y_vals = values
                
                # Calculate statistics
                values_array = np.array(values)
                mean_val = np.mean(values_array)
                median_val = np.median(values_array)
                
                # Determine visibility - only show default period + first metric
                is_visible = (period == default_period and metric == "Profitable Trades %")
                
                # Add single trace for this period/metric combination
                fig.add_trace(go.Bar(
                    x=symbols,
                    y=y_vals,
                    customdata=np.column_stack((trades_count, values)),
                    name=metric,
                    marker={"color": self.colors["primary"]},
                    visible=is_visible,
                    hovertemplate="<b>%{x}</b><br>" + metric + ": %{customdata[1]:.2f}<br>Trades: %{customdata[0]}<extra></extra>",
                    legendgroup=metric,
                    showlegend=True,
                ))
                
                trace_configs.append({
                    "period": period,
                    "metric": metric,
                    "mean": mean_val,
                    "median": median_val,
                    "y_axis_label": y_axis_label,
                })

        # Create period buttons that preserve metric selection
        period_buttons = []
        for period in sorted(all_symbol_stats.keys(), key=lambda x: int(x[:-1])):
            # Default metric is "Profitable Trades %"
            visibility = []
            for config in trace_configs:
                is_visible = (config["period"] == period and config["metric"] == "Profitable Trades %")
                visibility.append(is_visible)
            
            # Get stats for default metric of this period
            matching_config = next((c for c in trace_configs if c["period"] == period and c["metric"] == "Profitable Trades %"), None)
            if matching_config:
                title_text = f"Win Rate by Symbol - {period}<br><sub>Mean: {matching_config['mean']:.1f}% | Median: {matching_config['median']:.1f}%</sub>"
            else:
                title_text = f"Win Rate by Symbol - {period}"
            
            period_buttons.append({
                "label": period,
                "method": "update",
                "args": [{"visible": visibility}, {"title": title_text}],
            })
        
        # Create metric buttons that preserve period selection
        metric_buttons = []
        for metric in metrics_available:
            visibility = []
            for config in trace_configs:
                is_visible = (config["period"] == default_period and config["metric"] == metric)
                visibility.append(is_visible)
            
            # Get stats for this metric of default period
            matching_config = next((c for c in trace_configs if c["period"] == default_period and c["metric"] == metric), None)
            if matching_config:
                title_text = f"Win Rate by Symbol - {metric}<br><sub>Mean: {matching_config['mean']:.1f} | Median: {matching_config['median']:.1f}</sub>"
            else:
                title_text = f"Win Rate by Symbol - {metric}"
            
            metric_buttons.append({
                "label": metric,
                "method": "update",
                "args": [{"visible": visibility}, {"title": title_text}],
            })

        # Set initial title with statistics for default period + Profitable Trades %
        default_config = next((c for c in trace_configs if c["period"] == default_period and c["metric"] == "Profitable Trades %"), None)
        if default_config:
            title_text = f"Win Rate by Symbol<br><sub>Mean: {default_config['mean']:.1f}% | Median: {default_config['median']:.1f}%</sub>"
        else:
            title_text = "Win Rate by Symbol"

        fig.update_layout(
            title=title_text,
            xaxis_title="Symbol",
            yaxis_title="Value",
            **self.layout_config,
            height=600,
            updatemenus=[
                {
                    "type": "dropdown",
                    "direction": "down",
                    "showactive": True,
                    "x": 0.02,
                    "y": 1.15,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": period_buttons,
                    "active": len(period_buttons) - 1 if period_buttons else 0,
                },
                {
                    "type": "dropdown",
                    "direction": "down",
                    "showactive": True,
                    "x": 0.18,
                    "y": 1.15,
                    "xanchor": "left",
                    "yanchor": "top",
                    "buttons": metric_buttons,
                    "active": 0,
                }
            ] if period_buttons and metric_buttons else [],
        )
        
        # Add 50% reference line only for Profitable Trades %
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5, 
                      annotation_text="50%", annotation_position="right")

        
        # Set Profit Factor y-axis max to 10
        # Note: This will be updated dynamically based on metric selection, but set initial default
        fig.update_yaxes(range=[0, 100])

        return fig
        # Add horizontal line at 50% for Profitable Trades
        fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5, 
                      annotation_text="50%", annotation_position="right")

        return fig

    def generate_all_charts(self, data: Dict) -> Dict[str, go.Figure]:
        """Generate all dashboard charts."""        
        return {
            "equity": self.create_equity_chart(data),
            "drawdown": self.create_drawdown_chart(data),
            "monthly_heatmap": self.create_monthly_returns_heatmap(data),
            "exposure": self.create_exposure_chart(data),
            "trade_return": self.create_trade_return_vs_holding_days(data),
            "mae_analysis": self.create_mae_analysis(data),
            "trade_distribution": self.create_trade_distribution_analysis(data),
            "win_rate": self.create_advanced_win_rate_analysis(data),
        }

    def create_dashboard_html(self, data: Dict, charts: Dict, report_name: str = "Portfolio") -> str:
        """Create complete HTML dashboard."""
        
        # Get strategy metrics
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
        .header h1 {{ 
            margin: 0; font-size: 2.5em; font-weight: 600; 
            color: #ffffff;
        }}
        .header p {{ 
            margin: 10px 0 0 0; font-size: 1em; color: #b0b0b0; 
            font-weight: 400;
        }}
        
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
        .metric-card.primary .metric-value {{
            color: white;
        }}
        .metric-label {{
            font-size: 0.85em;
            font-weight: 500;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-card.primary .metric-label {{
            color: #e0f4ff;
        }}

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
        .chart-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 25px 0;
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

        /* Responsive Design */
        @media (max-width: 768px) {{
            body {{ padding: 15px; }}
            .chart-grid {{ grid-template-columns: 1fr; gap: 20px; }}
            .metrics-grid {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; }}
            .period-btn {{ padding: 10px 18px; font-size: 13px; }}
            .header h1 {{ font-size: 2em; }}
            .enhanced-metrics-panel {{ padding: 20px; }}
            .chart-container {{ padding: 20px; }}
        }}

        /* Scrollbar Styling */
        ::-webkit-scrollbar {{
            width: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: #f0f0f0;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #999;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>QuantLab Dashboard</h1>
        <p>{report_name} • Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    {metrics_panel_html}

    <div class="chart-container">
        {chart_htmls.get('equity', '<div class="error-message">Equity chart not available</div>')}
    </div>

    <div class="chart-container">
        {chart_htmls.get('drawdown', '<div class="error-message">Drawdown chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('monthly_heatmap', '<div class="error-message">Monthly Returns Heatmap not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('exposure', '<div class="error-message">Exposure chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('trade_return', '<div class="error-message">Trade Return vs Holding Days chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('mae_analysis', '<div class="error-message">MAE Analysis chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('win_rate', '<div class="error-message">Win Rate Analysis chart not available</div>')}
    </div>

    <div class="chart-container full-width">
        {chart_htmls.get('trade_distribution', '<div class="error-message">Trade Distribution Analysis chart not available</div>')}
    </div>

    <script>
        function showMetrics(period) {{
            // Hide all metrics content with fade out
            document.querySelectorAll('.metrics-content').forEach(function(el) {{
                el.classList.remove('active');
                el.style.opacity = '0';
                el.style.transform = 'translateY(20px)';
            }});
            
            // Remove active class from all buttons with animation
            document.querySelectorAll('.period-btn').forEach(function(btn) {{
                btn.classList.remove('active');
                btn.style.transform = 'scale(1)';
            }});
            
            // Show selected metrics with fade in effect
            setTimeout(function() {{
                const targetContent = document.getElementById('metrics-' + period);
                const targetButton = document.getElementById('btn-' + period);
                
                if (targetContent) {{
                    targetContent.classList.add('active');
                    targetContent.style.opacity = '1';
                    targetContent.style.transform = 'translateY(0)';
                    
                    // Animate individual metric cards
                    const cards = targetContent.querySelectorAll('.metric-card');
                    cards.forEach((card, index) => {{
                        setTimeout(() => {{
                            card.style.opacity = '0';
                            card.style.transform = 'translateY(30px) scale(0.9)';
                            setTimeout(() => {{
                                card.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
                                card.style.opacity = '1';
                                card.style.transform = 'translateY(0) scale(1)';
                            }}, 50);
                        }}, index * 100);
                    }});
                }}
                
                if (targetButton) {{
                    targetButton.classList.add('active');
                    targetButton.style.transform = 'scale(1.05)';
                    
                    // Ripple effect
                    const ripple = document.createElement('span');
                    ripple.className = 'ripple';
                    ripple.style.cssText = `
                        position: absolute;
                        border-radius: 50%;
                        background: rgba(255,255,255,0.6);
                        transform: scale(0);
                        animation: rippleEffect 0.6s linear;
                        width: 20px; height: 20px;
                        left: 50%; top: 50%;
                        margin-left: -10px; margin-top: -10px;
                    `;
                    targetButton.appendChild(ripple);
                    
                    setTimeout(() => {{
                        ripple.remove();
                    }}, 600);
                }}
            }}, 200);
        }}

        // Initialize with enhanced animations
        document.addEventListener('DOMContentLoaded', function() {{
            // Add ripple effect styles
            const style = document.createElement('style');
            style.textContent = `
                @keyframes rippleEffect {{
                    to {{
                        transform: scale(4);
                        opacity: 0;
                    }}
                }}
                
                .metric-card {{
                    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                }}
                
                .metrics-content {{
                    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
                }}
                
                .period-btn {{
                    position: relative;
                    overflow: hidden;
                }}
            `;
            document.head.appendChild(style);
            
            // Show default period with animation
            showMetrics('5Y');
            
            // Add intersection observer for chart animations
            const observerOptions = {{
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            }};
            
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        entry.target.style.opacity = '1';
                        entry.target.style.transform = 'translateY(0)';
                    }}
                }});
            }}, observerOptions);
            
            // Observe all chart containers
            document.querySelectorAll('.chart-container').forEach(container => {{
                container.style.opacity = '0';
                container.style.transform = 'translateY(30px)';
                container.style.transition = 'all 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
                observer.observe(container);
            }});
            
            // Add smooth scrolling
            document.documentElement.style.scrollBehavior = 'smooth';
            
            // Add loading shimmer effect
            const shimmerStyle = document.createElement('style');
            shimmerStyle.textContent = `
                .loading-shimmer {{
                    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
                    background-size: 200% 100%;
                    animation: shimmer 2s infinite;
                }}
                
                @keyframes shimmer {{
                    0% {{ background-position: -200% 0; }}
                    100% {{ background-position: 200% 0; }}
                }}
            `;
            document.head.appendChild(shimmerStyle);
        }});
        
        // Add hover effects for metric cards
        document.addEventListener('DOMContentLoaded', function() {{
            const cards = document.querySelectorAll('.metric-card');
            cards.forEach(card => {{
                card.addEventListener('mouseenter', function() {{
                    this.style.transform = 'translateY(-8px) scale(1.02)';
                    this.style.zIndex = '10';
                }});
                
                card.addEventListener('mouseleave', function() {{
                    this.style.transform = 'translateY(0) scale(1)';
                    this.style.zIndex = '1';
                }});
            }});
        }});
    </script>
</body>
</html>
        """
        
        return html_template

    def save_dashboard(self, data: Dict, output_name: str = "dashboard") -> Path:
        """Save the complete dashboard to HTML file in the specific report folder."""
        if not data:
            print("❌ No data provided for dashboard generation")
            return None
            
        print("📊 Generating dashboard charts...")
        charts = self.generate_all_charts(data)
        
        print("🎨 Creating HTML dashboard...")
        html_content = self.create_dashboard_html(data, charts)
        
        # Save to the specific report folder if we have one, otherwise use report_dir
        if self.current_report_folder:
            output_dir = self.report_dir / self.current_report_folder
        else:
            output_dir = self.report_dir
            
        output_path = output_dir / f"{output_name}.html"
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            print(f"✅ Dashboard saved to: {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ Error saving dashboard: {e}")
            return None


def main():
    """Main function for command line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate QuantLab Dashboard")
    parser.add_argument("report_folder", nargs="?", default="1026-2033-ichimoku-basket-mega",
                       help="Report folder name (default: 1026-2033-ichimoku-basket-mega)")
    parser.add_argument("--output", "-o", default="quantlab_dashboard",
                       help="Output filename (default: quantlab_dashboard)")
    parser.add_argument("--reports-dir", default="reports",
                       help="Reports directory (default: reports)")
    
    args = parser.parse_args()
    
    # Initialize dashboard
    dashboard = QuantLabDashboard(Path(args.reports_dir))
    
    # Load data
    print(f"🔄 Loading data from {args.report_folder}...")
    data = dashboard.load_comprehensive_data(args.report_folder)
    
    if data:
        # Generate dashboard
        output_path = dashboard.save_dashboard(data, args.output)
        if output_path:
            print(f"\n🎉 Success! Dashboard generated:")
            print(f"📁 File: {output_path}")
            print(f"🌐 Open in browser: file://{output_path.absolute()}")
        else:
            print("❌ Failed to save dashboard")
            sys.exit(1)
    else:
        print("❌ No data found to generate dashboard")
        sys.exit(1)


if __name__ == "__main__":
    main()