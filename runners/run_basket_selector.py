#!/usr/bin/env python
"""
Wrapper to run either standard or optimized basket backtester.

Usage:
    python runners/run_basket.py [args]              # Use standard version (ORIGINAL)
    python runners/run_basket_optimized.py [args]   # Use optimized version (EXPERIMENTAL)

The optimized version uses itertuples() instead of iterrows() for ~2x speedup
on trade processing but should be tested thoroughly for accuracy.
"""

import sys
import subprocess

if __name__ == "__main__":
    if "--use-optimized" in sys.argv:
        # Remove the flag before passing to subprocess
        sys.argv.remove("--use-optimized")
        module = "runners.run_basket_optimized"
        print("⚡ Using OPTIMIZED runner (itertuples-based)")
    else:
        module = "runners.run_basket"
        print("📊 Using STANDARD runner (original)")

    # Run the selected module
    result = subprocess.run(
        [sys.executable, "-m", module] + sys.argv[1:],
        cwd="/Users/abhishekshah/Desktop/quantlab-workspace",
    )
    sys.exit(result.returncode)
