#!/usr/bin/env python3
"""
Generate Updated Dashboard with Improved Metrics Panel
This script generates a new dashboard using the final_fixed_dashboard.py with the enhanced metrics panel
"""

import sys
from pathlib import Path

# Add the quantlab directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from viz.final_fixed_dashboard import FinalFixedDashboard


def main():
    """Generate the updated dashboard with improved metrics panel."""

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
    for report_dir in report_dirs:
        required_files = [
            "strategy_backtests_summary.csv",
            "portfolio_daily_equity_curve_5Y.csv",
            "consolidated_trades_3Y.csv",
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
    dashboard = FinalFixedDashboard(reports_dir)

    # Load comprehensive data using just the folder name
    try:
        data = dashboard.load_comprehensive_data(latest_report.name)
        print(f"Loaded data with {len(data)} components")

        # Generate the updated dashboard
        output_path = dashboard.save_comprehensive_dashboard(
            data,
            output_name="enhanced_metrics_dashboard",
            report_name="QuantLab Enhanced Portfolio",
        )

        print("\n✅ Enhanced Dashboard Generated Successfully!")
        print(f"📍 Location: {output_path}")
        print(f"🌐 Open in browser: file://{output_path.absolute()}")
        print("\n🎯 Key Improvements:")
        print("   • Replaced old row-based metrics with grid layout")
        print("   • Added highlight styling for key metrics (Net P&L, CAGR, IRR)")
        print("   • Enhanced hover effects and smooth transitions")
        print("   • Improved visual hierarchy and professional styling")
        print("   • Better responsive design for mobile devices")

    except Exception as e:
        print(f"Error generating dashboard: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
