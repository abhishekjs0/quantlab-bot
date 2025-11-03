#!/usr/bin/env python3
"""
Generate Updated Dashboard - Using the consolidated viz.dashboard module
"""

import sys
from pathlib import Path

# Add the quantlab directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from viz.dashboard import QuantLabDashboard


def main():
    """Generate the updated dashboard with the simplified unified system."""

    # Use the latest report directory
    reports_dir = Path("reports")
    if not reports_dir.exists():
        print("Error: reports directory not found")
        return

    # Find the best report directory with complete data
    report_dirs = [
        d for d in reports_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    ]

    # Look for directories with complete data files
    best_report = None
    for report_dir in sorted(report_dirs, key=lambda x: x.name, reverse=True):  # Sort by name descending (newest first)
        required_files = [
            "strategy_backtests_summary.csv",
            "portfolio_daily_equity_curve_5Y.csv",
            "portfolio_daily_equity_curve_3Y.csv",
        ]
        if all((report_dir / f).exists() for f in required_files):
            best_report = report_dir
            break

    if not best_report:
        # Fallback to latest by name
        latest_report = max(report_dirs, key=lambda x: x.name)
    else:
        latest_report = best_report

    print(f"Using report directory: {latest_report}")

    # Create dashboard instance
    dashboard = QuantLabDashboard(reports_dir)

    # Load comprehensive data using just the folder name
    try:
        data = dashboard.load_comprehensive_data(latest_report.name)
        print(f"Loaded data with {len(data)} components")

        # Generate the final dashboard
        output_path = dashboard.save_dashboard(data, "portfolio")

        print("\n✅ Dashboard Generated Successfully!")
        print(f"📍 Location: {output_path}")
        print(f"🌐 Open in browser: file://{output_path}")
        print("\n📊 Dashboard Features:")
        print("   • Enhanced metrics panel with RoMaD, Volatility, VaR")
        print("   • Period switching (1Y/3Y/5Y)")
        print("   • 9 interactive charts")
        print("   • Professional responsive design")

    except Exception as e:
        print(f"Error generating dashboard: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
