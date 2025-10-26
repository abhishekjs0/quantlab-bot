"""
Advanced Walk-Forward Analysis Implementation for QuantLab
========================================================

Comprehensive walk-forward analysis system featuring:
1. Rolling window optimization
2. Out-of-sample validation
3. Parameter stability analysis
4. Robustness metrics
5. Performance degradation detection
6. Strategy lifecycle management

Author: QuantLab Team
Date: 2025-10-24
"""

import warnings

warnings.filterwarnings("ignore")

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats


class WalkForwardAnalyzer:
    """Advanced walk-forward analysis with comprehensive validation."""

    def __init__(self, reports_dir: str = None):
        """Initialize walk-forward analyzer."""
        self.reports_dir = Path(reports_dir) if reports_dir else Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

        # Analysis configuration
        self.default_config = {
            "training_months": 12,
            "testing_months": 3,
            "step_months": 1,
            "min_trades": 10,
            "optimization_metric": "sharpe_ratio",
            "reoptimization_threshold": 0.3,
        }

        # Results storage
        self.walk_forward_results = []
        self.parameter_evolution = {}
        self.performance_metrics = {}

    def run_walk_forward_analysis(
        self,
        strategy_name: str,
        initial_params: dict,
        basket_size: str = "mega",
        config: dict = None,
    ) -> pd.DataFrame:
        """
        Run comprehensive walk-forward analysis.

        Args:
            strategy_name: Strategy to analyze
            initial_params: Initial strategy parameters
            basket_size: Basket size for testing
            config: Analysis configuration

        Returns:
            DataFrame with walk-forward results
        """
        # Merge config
        analysis_config = {**self.default_config, **(config or {})}

        print(f"🚶 Starting walk-forward analysis for {strategy_name}")
        print(
            f"📅 Config: {analysis_config['training_months']}M train, "
            f"{analysis_config['testing_months']}M test, "
            f"{analysis_config['step_months']}M step"
        )

        # Generate analysis windows
        windows = self._generate_analysis_windows(analysis_config)
        print(f"📊 Generated {len(windows)} analysis windows")

        # Run walk-forward analysis
        results = []
        current_params = initial_params.copy()

        for i, window in enumerate(windows):
            try:
                print(f"🔄 Processing window {i+1}/{len(windows)}")

                # Step 1: Optimize on training period (simulate)
                if i == 0 or self._should_reoptimize(results, analysis_config):
                    optimized_params = self._optimize_on_training_period(
                        strategy_name, window, current_params
                    )
                    current_params = optimized_params

                # Step 2: Test on out-of-sample period
                test_results = self._test_on_oos_period(
                    strategy_name, window, current_params, basket_size
                )

                if test_results:
                    window_result = {
                        **window,
                        **test_results,
                        "window_id": i + 1,
                        "parameters_used": current_params.copy(),
                        "reoptimized": i == 0
                        or self._should_reoptimize(results, analysis_config),
                    }
                    results.append(window_result)

                    print(
                        f"✅ Window {i+1}: Return={test_results.get('oos_return', 0):.2f}%, "
                        f"Sharpe={test_results.get('oos_sharpe', 0):.2f}"
                    )

            except Exception as e:
                print(f"❌ Window {i+1} failed: {e}")

        # Convert to DataFrame and analyze
        if not results:
            print("❌ No successful windows")
            return pd.DataFrame()

        results_df = pd.DataFrame(results)

        # Calculate additional metrics
        results_df = self._calculate_walkforward_metrics(results_df)

        # Store results
        self.walk_forward_results = results_df
        self._analyze_parameter_stability(results_df)
        self._calculate_performance_metrics(results_df)

        print(f"🎯 Analysis complete: {len(results_df)} successful windows")
        print(f"📊 Avg OOS Return: {results_df['oos_return'].mean():.2f}%")
        print(f"📊 Avg OOS Sharpe: {results_df['oos_sharpe'].mean():.2f}")

        return results_df

    def _generate_analysis_windows(self, config: dict) -> list:
        """Generate walk-forward analysis windows."""
        windows = []

        # Use last 3 years for analysis
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * 3)

        current_start = start_date
        train_months = config["training_months"]
        test_months = config["testing_months"]
        step_months = config["step_months"]

        while True:
            train_end = current_start + timedelta(days=30 * train_months)
            test_start = train_end
            test_end = test_start + timedelta(days=30 * test_months)

            # Stop if we go beyond available data
            if test_end > end_date:
                break

            windows.append(
                {
                    "train_start": current_start,
                    "train_end": train_end,
                    "test_start": test_start,
                    "test_end": test_end,
                    "train_period_months": train_months,
                    "test_period_months": test_months,
                }
            )

            current_start += timedelta(days=30 * step_months)

        return windows

    def _should_reoptimize(self, results: list, config: dict) -> bool:
        """Determine if parameters should be reoptimized."""
        if len(results) < 3:
            return False

        # Check if recent performance has degraded
        recent_performance = [r["oos_sharpe"] for r in results[-3:]]
        avg_recent = np.mean(recent_performance)

        # Check against historical average
        all_performance = [r["oos_sharpe"] for r in results]
        avg_all = np.mean(all_performance)

        degradation = (avg_all - avg_recent) / avg_all if avg_all != 0 else 0

        return degradation > config["reoptimization_threshold"]

    def _optimize_on_training_period(
        self, strategy_name: str, window: dict, base_params: dict
    ) -> dict:
        """
        Simulate parameter optimization on training period.

        In a real implementation, this would run backtests on the training period
        and optimize parameters. For demo purposes, we simulate this.
        """
        # Simulate parameter optimization with some randomization
        optimized_params = base_params.copy()

        # Add some realistic parameter adjustments
        if strategy_name == "ichimoku":
            adjustments = {
                "tenkan_period": np.random.choice([-3, 0, 3]),
                "kijun_period": np.random.choice([-5, 0, 5]),
                "senkou_b_period": np.random.choice([-10, 0, 10]),
            }

            for param, adjustment in adjustments.items():
                if param in optimized_params:
                    new_value = optimized_params[param] + adjustment
                    optimized_params[param] = max(
                        5, new_value
                    )  # Minimum value constraint

        return optimized_params

    def _test_on_oos_period(
        self, strategy_name: str, window: dict, params: dict, basket_size: str
    ) -> dict | None:
        """
        Test strategy on out-of-sample period.

        In a real implementation, this would run backtest on OOS period.
        For demo purposes, we simulate realistic results.
        """
        try:
            # Simulate realistic out-of-sample performance
            # Base performance with some randomness
            base_monthly_return = np.random.normal(0.02, 0.08)  # 2% ± 8%

            # Simulate monthly returns for the test period
            test_months = window["test_period_months"]
            monthly_returns = np.random.normal(base_monthly_return, 0.05, test_months)

            # Calculate metrics
            total_return = (np.prod(1 + monthly_returns) - 1) * 100
            sharpe_ratio = (
                np.mean(monthly_returns) / np.std(monthly_returns) * np.sqrt(12)
                if np.std(monthly_returns) > 0
                else 0
            )

            # Simulate drawdown
            cum_returns = np.cumprod(1 + monthly_returns)
            peak = np.maximum.accumulate(cum_returns)
            drawdowns = (cum_returns - peak) / peak
            max_drawdown = abs(drawdowns.min()) * 100

            # Simulate trade count
            trades_per_month = np.random.randint(3, 12)
            total_trades = trades_per_month * test_months

            # Win rate simulation
            win_rate = np.random.uniform(35, 65)

            return {
                "oos_return": total_return,
                "oos_sharpe": sharpe_ratio,
                "oos_max_drawdown": max_drawdown,
                "oos_trades": total_trades,
                "oos_win_rate": win_rate,
                "oos_volatility": np.std(monthly_returns) * np.sqrt(12) * 100,
                "monthly_returns": monthly_returns.tolist(),
            }

        except Exception as e:
            print(f"❌ OOS testing failed: {e}")
            return None

    def _calculate_walkforward_metrics(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate additional walk-forward specific metrics."""

        # Cumulative performance
        results_df["cumulative_return"] = (
            1 + results_df["oos_return"] / 100
        ).cumprod() - 1

        # Rolling metrics
        window_size = min(6, len(results_df))
        results_df["rolling_sharpe"] = (
            results_df["oos_sharpe"].rolling(window_size).mean()
        )
        results_df["rolling_return"] = (
            results_df["oos_return"].rolling(window_size).mean()
        )

        # Performance consistency
        results_df["positive_return"] = results_df["oos_return"] > 0
        results_df["win_streak"] = self._calculate_win_streaks(
            results_df["positive_return"]
        )

        # Parameter stability (if parameters change frequently)
        results_df["param_changes"] = self._count_parameter_changes(results_df)

        return results_df

    def _calculate_win_streaks(self, positive_returns: pd.Series) -> pd.Series:
        """Calculate current win streaks."""
        streaks = []
        current_streak = 0

        for is_positive in positive_returns:
            if is_positive:
                current_streak += 1
            else:
                current_streak = 0
            streaks.append(current_streak)

        return pd.Series(streaks, index=positive_returns.index)

    def _count_parameter_changes(self, results_df: pd.DataFrame) -> pd.Series:
        """Count cumulative parameter changes."""
        changes = [0]  # First window has no changes

        for i in range(1, len(results_df)):
            prev_params = results_df.iloc[i - 1]["parameters_used"]
            curr_params = results_df.iloc[i]["parameters_used"]

            # Count changed parameters
            param_changes = sum(
                1
                for key in prev_params
                if key in curr_params and prev_params[key] != curr_params[key]
            )

            changes.append(changes[-1] + param_changes)

        return pd.Series(changes, index=results_df.index)

    def _analyze_parameter_stability(self, results_df: pd.DataFrame):
        """Analyze parameter stability over time."""
        if results_df.empty:
            return

        # Track parameter evolution
        param_evolution = {}
        for _, row in results_df.iterrows():
            for param, value in row["parameters_used"].items():
                if param not in param_evolution:
                    param_evolution[param] = []
                param_evolution[param].append(value)

        # Calculate stability metrics
        stability_metrics = {}
        for param, values in param_evolution.items():
            stability_metrics[param] = {
                "mean": np.mean(values),
                "std": np.std(values),
                "cv": np.std(values) / np.mean(values) if np.mean(values) != 0 else 0,
                "range": max(values) - min(values),
                "changes": len(set(values)),
            }

        self.parameter_evolution = param_evolution
        self.parameter_stability = stability_metrics

        print("📊 Parameter Stability Analysis:")
        for param, metrics in stability_metrics.items():
            print(f"   {param}: CV={metrics['cv']:.3f}, Changes={metrics['changes']}")

    def _calculate_performance_metrics(self, results_df: pd.DataFrame):
        """Calculate comprehensive performance metrics."""
        if results_df.empty:
            return

        oos_returns = results_df["oos_return"].values
        oos_sharpes = results_df["oos_sharpe"].values

        self.performance_metrics = {
            # Return metrics
            "mean_oos_return": np.mean(oos_returns),
            "median_oos_return": np.median(oos_returns),
            "std_oos_return": np.std(oos_returns),
            "total_return": results_df["cumulative_return"].iloc[-1] * 100,
            # Risk metrics
            "mean_sharpe": np.mean(oos_sharpes),
            "sharpe_consistency": np.std(oos_sharpes),
            "positive_periods": (oos_returns > 0).sum() / len(oos_returns),
            "max_consecutive_losses": self._max_consecutive_losses(oos_returns),
            # Stability metrics
            "return_stability": 1 / (1 + np.std(oos_returns)),
            "sharpe_stability": 1 / (1 + np.std(oos_sharpes)),
            "parameter_changes": results_df["param_changes"].iloc[-1],
            # Statistical tests
            "normality_pvalue": (
                stats.shapiro(oos_returns)[1] if len(oos_returns) >= 3 else None
            ),
            "mean_positive_test": (
                stats.ttest_1samp(oos_returns, 0)[1] if len(oos_returns) >= 3 else None
            ),
        }

    def _max_consecutive_losses(self, returns: np.ndarray) -> int:
        """Calculate maximum consecutive loss periods."""
        max_consecutive = 0
        current_consecutive = 0

        for ret in returns:
            if ret < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    def create_walkforward_dashboard(
        self, results_df: pd.DataFrame, strategy_name: str
    ) -> go.Figure:
        """Create comprehensive walk-forward analysis dashboard."""

        if results_df.empty:
            return go.Figure().add_annotation(text="No walk-forward results available")

        # Create subplots
        fig = make_subplots(
            rows=3,
            cols=2,
            subplot_titles=[
                "Out-of-Sample Performance Timeline",
                "Cumulative Return Evolution",
                "Performance Distribution",
                "Parameter Stability",
                "Rolling Metrics",
                "Risk Analysis",
            ],
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "histogram"}, {"type": "scatter"}],
                [{"type": "scatter"}, {"type": "bar"}],
            ],
            vertical_spacing=0.08,
        )

        # 1. OOS Performance Timeline
        fig.add_trace(
            go.Scatter(
                x=results_df["window_id"],
                y=results_df["oos_return"],
                mode="lines+markers",
                name="OOS Return %",
                line={"color": "blue", "width": 2},
                marker={
                    "size": 8,
                    "color": results_df["oos_return"],
                    "colorscale": "RdYlGn",
                },
                hovertemplate="Window: %{x}<br>Return: %{y:.2f}%<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="red", row=1, col=1)

        # 2. Cumulative Return
        fig.add_trace(
            go.Scatter(
                x=results_df["window_id"],
                y=results_df["cumulative_return"] * 100,
                mode="lines+markers",
                name="Cumulative Return %",
                line={"color": "green", "width": 3},
            ),
            row=1,
            col=2,
        )

        # 3. Return Distribution
        fig.add_trace(
            go.Histogram(
                x=results_df["oos_return"],
                nbinsx=15,
                name="Return Distribution",
                marker_color="lightblue",
                opacity=0.7,
            ),
            row=2,
            col=1,
        )

        # 4. Parameter Stability (first parameter)
        if hasattr(self, "parameter_evolution") and self.parameter_evolution:
            first_param = list(self.parameter_evolution.keys())[0]
            param_values = self.parameter_evolution[first_param]

            fig.add_trace(
                go.Scatter(
                    x=list(range(1, len(param_values) + 1)),
                    y=param_values,
                    mode="lines+markers",
                    name=f"{first_param} Evolution",
                    line={"color": "purple", "width": 2},
                ),
                row=2,
                col=2,
            )

        # 5. Rolling Sharpe
        if "rolling_sharpe" in results_df.columns:
            fig.add_trace(
                go.Scatter(
                    x=results_df["window_id"],
                    y=results_df["rolling_sharpe"],
                    mode="lines+markers",
                    name="Rolling Sharpe",
                    line={"color": "orange", "width": 2},
                ),
                row=3,
                col=1,
            )

        # 6. Risk Metrics Bar Chart
        if hasattr(self, "performance_metrics"):
            metrics = self.performance_metrics
            risk_metrics = ["mean_sharpe", "return_stability", "positive_periods"]
            risk_values = [metrics.get(m, 0) for m in risk_metrics]

            fig.add_trace(
                go.Bar(
                    x=["Avg Sharpe", "Return Stability", "Win Rate"],
                    y=risk_values,
                    name="Risk Metrics",
                    marker_color=["green", "blue", "orange"],
                    text=[f"{v:.2f}" for v in risk_values],
                    textposition="outside",
                ),
                row=3,
                col=2,
            )

        # Update layout
        fig.update_layout(
            title=f"{strategy_name.title()} Walk-Forward Analysis Dashboard",
            height=1000,
            showlegend=False,
            font={"size": 11},
        )

        # Update axes labels
        fig.update_xaxes(title_text="Window #", row=1, col=1)
        fig.update_yaxes(title_text="Return (%)", row=1, col=1)

        fig.update_xaxes(title_text="Window #", row=1, col=2)
        fig.update_yaxes(title_text="Cumulative Return (%)", row=1, col=2)

        fig.update_xaxes(title_text="Return (%)", row=2, col=1)
        fig.update_yaxes(title_text="Frequency", row=2, col=1)

        return fig

    def save_walkforward_analysis(self, results_df: pd.DataFrame, strategy_name: str):
        """Save complete walk-forward analysis results."""

        # Create output directory
        timestamp = datetime.now().strftime("%m%d-%H%M")
        output_dir = self.reports_dir / f"walkforward_{strategy_name}_{timestamp}"
        output_dir.mkdir(exist_ok=True)

        # Save main results
        results_df.to_csv(output_dir / "walkforward_results.csv", index=False)

        # Save parameter evolution
        if hasattr(self, "parameter_evolution"):
            param_df = pd.DataFrame(self.parameter_evolution)
            param_df.to_csv(output_dir / "parameter_evolution.csv", index=False)

        # Save performance metrics
        if hasattr(self, "performance_metrics"):
            with open(output_dir / "performance_metrics.json", "w") as f:
                json.dump(self.performance_metrics, f, indent=2, default=str)

        # Save parameter stability
        if hasattr(self, "parameter_stability"):
            with open(output_dir / "parameter_stability.json", "w") as f:
                # Convert numpy types to native Python types for JSON serialization
                stability_json = {}
                for param, metrics in self.parameter_stability.items():
                    stability_json[param] = {
                        key: float(value) if hasattr(value, "dtype") else value
                        for key, value in metrics.items()
                    }
                json.dump(stability_json, f, indent=2)

        # Create and save dashboard
        dashboard = self.create_walkforward_dashboard(results_df, strategy_name)
        dashboard.write_html(output_dir / "walkforward_dashboard.html")

        # Create summary report
        self._create_summary_report(output_dir, strategy_name, results_df)

        print(f"📁 Walk-forward analysis saved to: {output_dir}")
        return output_dir

    def _create_summary_report(
        self, output_dir: Path, strategy_name: str, results_df: pd.DataFrame
    ):
        """Create a summary report of the walk-forward analysis."""

        report_lines = [
            f"# Walk-Forward Analysis Report: {strategy_name.title()}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary Statistics",
            f"- Total Windows Analyzed: {len(results_df)}",
            f"- Average OOS Return: {results_df['oos_return'].mean():.2f}% per period",
            f"- Average OOS Sharpe Ratio: {results_df['oos_sharpe'].mean():.2f}",
            f"- Win Rate (Positive Periods): {(results_df['oos_return'] > 0).mean():.1%}",
            f"- Total Cumulative Return: {results_df['cumulative_return'].iloc[-1]*100:.2f}%",
            "",
            "## Performance Metrics",
        ]

        if hasattr(self, "performance_metrics"):
            metrics = self.performance_metrics
            report_lines.extend(
                [
                    f"- Return Stability: {metrics.get('return_stability', 0):.3f}",
                    f"- Sharpe Consistency: {metrics.get('sharpe_consistency', 0):.3f}",
                    f"- Max Consecutive Losses: {metrics.get('max_consecutive_losses', 0)}",
                    f"- Parameter Changes: {metrics.get('parameter_changes', 0)}",
                ]
            )

        report_lines.extend(["", "## Parameter Stability"])

        if hasattr(self, "parameter_stability"):
            for param, stability in self.parameter_stability.items():
                report_lines.append(
                    f"- {param}: CV={stability['cv']:.3f}, "
                    f"Range={stability['range']}, Changes={stability['changes']}"
                )

        # Write report
        with open(output_dir / "summary_report.md", "w") as f:
            f.write("\n".join(report_lines))


def main():
    """Demonstrate the walk-forward analysis framework."""
    analyzer = WalkForwardAnalyzer("/Users/abhishekshah/Desktop/quantlab/reports")

    # Define strategy and initial parameters
    strategy = "ichimoku"
    initial_params = {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52}

    print(f"🚀 Running walk-forward analysis for {strategy}")

    # Run comprehensive walk-forward analysis
    results = analyzer.run_walk_forward_analysis(
        strategy_name=strategy,
        initial_params=initial_params,
        basket_size="mega",
        config={
            "training_months": 6,
            "testing_months": 2,
            "step_months": 1,
            "reoptimization_threshold": 0.25,
        },
    )

    if not results.empty:
        # Save complete analysis
        output_dir = analyzer.save_walkforward_analysis(results, strategy)

        print("\n✅ Walk-forward analysis completed!")
        print(f"📊 Results available at: {output_dir}")

        # Display summary
        print("\n📈 Summary:")
        print(f"   Windows Analyzed: {len(results)}")
        print(f"   Average OOS Return: {results['oos_return'].mean():.2f}% per period")
        print(f"   Average OOS Sharpe: {results['oos_sharpe'].mean():.2f}")
        print(f"   Win Rate: {(results['oos_return'] > 0).mean():.1%}")
        print(f"   Total Return: {results['cumulative_return'].iloc[-1]*100:.2f}%")

        if hasattr(analyzer, "performance_metrics"):
            metrics = analyzer.performance_metrics
            print(f"   Return Stability: {metrics.get('return_stability', 0):.3f}")
            print(f"   Parameter Changes: {metrics.get('parameter_changes', 0)}")

    else:
        print("❌ Walk-forward analysis failed")


if __name__ == "__main__":
    main()
