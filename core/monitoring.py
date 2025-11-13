#!/usr/bin/env python3
"""
Performance Monitoring and Checkpointing Utility
Simple utilities to add to run_basket.py for better performance tracking
"""

import json
import os
import subprocess
import time
from typing import Any, Dict, Optional


class BacktestMonitor:
    """Simple monitoring for backtest performance"""

    def __init__(self, output_dir: str, total_symbols: int):
        self.output_dir = output_dir
        self.total_symbols = total_symbols
        self.start_time = time.time()
        self.completed_symbols: list[str] = []
        self.checkpoint_file = os.path.join(output_dir, "backtest_checkpoint.json")

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def log_progress(self, symbol: str, stage: str = "completed") -> None:
        """Log progress for a symbol"""
        if stage == "completed" and symbol not in self.completed_symbols:
            self.completed_symbols.append(symbol)

        progress = len(self.completed_symbols) / self.total_symbols * 100
        elapsed = time.time() - self.start_time

        if len(self.completed_symbols) > 0:
            eta = (
                elapsed
                / len(self.completed_symbols)
                * (self.total_symbols - len(self.completed_symbols))
            )
        else:
            eta = 0

        print(
            f"📊 Progress: {progress:.1f}% ({len(self.completed_symbols)}/{self.total_symbols})"
        )
        print(f"⏱️  Elapsed: {elapsed:.1f}s, ETA: {eta:.1f}s")
        print(f"🔄 Current: {symbol} ({stage})")

        # Save checkpoint
        self.save_checkpoint()

    def save_checkpoint(self) -> None:
        """Save current progress to checkpoint file"""
        checkpoint_data = {
            "completed_symbols": self.completed_symbols,
            "total_symbols": self.total_symbols,
            "progress_percent": len(self.completed_symbols) / self.total_symbols * 100,
            "elapsed_seconds": time.time() - self.start_time,
            "timestamp": time.time(),
        }

        try:
            with open(self.checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Warning: Could not save checkpoint: {e}")

    def load_checkpoint(self):
        """Load checkpoint if it exists"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file) as f:
                    checkpoint = json.load(f)
                print(
                    f"📂 Loaded checkpoint: {checkpoint['progress_percent']:.1f}% complete"
                )
                return checkpoint
            except Exception as e:
                print(f"⚠️  Warning: Could not load checkpoint: {e}")
        return None

    def get_remaining_symbols(self, all_symbols: list[str]) -> list[str]:
        """Get symbols that haven't been completed yet"""
        checkpoint = self.load_checkpoint()
        if checkpoint:
            completed = set(checkpoint.get("completed_symbols", []))
            remaining = [sym for sym in all_symbols if sym not in completed]
            self.completed_symbols = list(completed)
            print(f"🔄 Resuming: {len(completed)} complete, {len(remaining)} remaining")
            return remaining
        return all_symbols

    def monitor_resources(self) -> dict[str, Any]:
        """Monitor system resources (simplified, no psutil dependency)"""
        try:
            # Get process info using ps command
            pid = os.getpid()
            result = subprocess.run(
                ["/bin/ps", "-o", "pid,ppid,%mem,%cpu,comm", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )

            if result.stdout:
                lines = result.stdout.strip().split("\n")
                if len(lines) > 1:
                    data = lines[1].split()
                    return {
                        "memory_percent": float(data[2]) if len(data) > 2 else 0.0,
                        "cpu_percent": float(data[3]) if len(data) > 3 else 0.0,
                        "pid": pid,
                    }
        except Exception as e:
            print(f"⚠️  Could not get resource info: {e}")

        return {"memory_percent": 0.0, "cpu_percent": 0.0, "pid": os.getpid()}


def optimize_window_processing(
    symbol_results: dict, windows_years: list, bars_per_year: int = 252
) -> dict:
    """
    Optimized window processing - run strategy once, filter results for each window

    Args:
        symbol_results: dict with symbol -> {'trades': df, 'equity': df, 'data': df}
        windows_years: List of window years [1, 3, 5, None]
        bars_per_year: Number of bars per year (default 252 for daily, ~1638 for 125m, etc.)

    Returns: dict with window_label -> window_data
    """

    print("⚡ Starting optimized window processing...")
    print(f"📊 Using {bars_per_year} bars per year for window calculations")
    window_labels = {1: "1Y", 3: "3Y", 5: "5Y", None: "MAX"}
    window_results = {}

    for y in windows_years:
        label = window_labels.get(y, f"{y}Y")
        bars_info = (
            f"(using {y * bars_per_year} bars if available)"
            if y is not None
            else "(using all available bars)"
        )
        print(f"🔄 Processing {label} window {bars_info}...")

        window_data = {
            "trades_by_symbol": {},
            "equity_by_symbol": {},
            "data_by_symbol": {},
        }

        for sym, results in symbol_results.items():
            # Filter data and results for this window
            if y is not None:
                # Apply time window filtering
                df_full = results["data"]
                trades_full = results["trades"]
                equity_full = results["equity"]

                # Get window start date using actual bars_per_year (not hardcoded 252)
                window_start = (
                    df_full.index[-(y * bars_per_year) :].min()
                    if len(df_full) >= y * bars_per_year
                    else df_full.index.min()
                )

                # Filter trades to window
                # IMPORTANT: Filter by exit_time (when trade closed), not entry_time
                # This ensures trades that closed within the window are included
                if not trades_full.empty:
                    try:
                        import pandas as pd

                        trades_full_copy = trades_full.copy()
                        # Ensure exit_time is datetime64[ns] - critical for window filtering
                        if "exit_time" in trades_full_copy.columns:
                            trades_full_copy["exit_time"] = pd.to_datetime(
                                trades_full_copy["exit_time"], errors="coerce"
                            )
                            # Ensure window_start is a Timestamp for consistent comparison
                            window_start_ts = pd.Timestamp(window_start)
                            # Filter by exit_time >= window_start to include all trades closed in window
                            # CRITICAL: Also include open trades (exit_time is NaN/None) with entry >= window_start
                            mask = (
                                trades_full_copy["exit_time"] >= window_start_ts
                            ) | (
                                trades_full_copy["exit_time"].isna()
                                & (
                                    pd.to_datetime(
                                        trades_full_copy["entry_time"], errors="coerce"
                                    )
                                    >= window_start_ts
                                )
                            )
                            window_trades = trades_full_copy[mask]
                        else:
                            # Fallback: if no exit_time, use entry_time
                            trades_full_copy["entry_time"] = pd.to_datetime(
                                trades_full_copy.get("entry_time"), errors="coerce"
                            )
                            window_start_ts = pd.Timestamp(window_start)
                            mask = trades_full_copy["entry_time"] >= window_start_ts
                            window_trades = trades_full_copy[mask]
                    except Exception as e:
                        print(
                            f"⚠️  Warning: pandas date filtering failed ({e}), using all trades"
                        )
                        window_trades = trades_full
                else:
                    window_trades = trades_full

                # Filter equity to window
                try:
                    if not equity_full.empty:
                        window_start_ts = pd.Timestamp(window_start)
                        # Ensure index is datetime64
                        equity_idx = pd.to_datetime(equity_full.index, errors="coerce")
                        window_equity = equity_full.loc[equity_idx >= window_start_ts]
                    else:
                        window_equity = equity_full
                except Exception:
                    window_equity = equity_full

                # Filter data to window
                try:
                    window_start_ts = pd.Timestamp(window_start)
                    df_idx = pd.to_datetime(df_full.index, errors="coerce")
                    window_data_df = df_full.loc[df_idx >= window_start_ts]
                except Exception:
                    window_data_df = df_full
            else:
                # MAX window - use full data
                window_trades = results["trades"]
                window_equity = results["equity"]
                window_data_df = results["data"]

            window_data["trades_by_symbol"][sym] = window_trades
            window_data["equity_by_symbol"][sym] = window_equity
            window_data["data_by_symbol"][sym] = window_data_df

        window_results[label] = window_data
        print(f"✅ {label} window complete")

    print("⚡ Optimized window processing complete!")
    return window_results


# Integration example for run_basket.py
def example_integration():
    """
    Example of how to integrate these optimizations into run_basket.py
    """

    integration_code = """
# At the beginning of run_basket function:
def run_basket(strategy_name, basket_file, period="5y", output_dir="reports"):
    # Initialize monitoring
    symbols = load_symbol_list(basket_file)
    monitor = BacktestMonitor(output_dir, len(symbols))

    # Check for resume
    remaining_symbols = monitor.get_remaining_symbols(symbols)

    # OPTIMIZATION 1: Run strategy once per symbol
    print("🚀 Running strategy once per symbol (optimized)...")
    symbol_results = {}

    for i, sym in enumerate(remaining_symbols):
        monitor.log_progress(sym, "processing")

        # Load data
        df_full = load_symbol_data(sym, period)

        # Run strategy ONCE
        strat = make_strategy(strategy_name)
        trades_full, equity_full, _ = BacktestEngine(df_full, strat).run()

        # Store results
        symbol_results[sym] = {
            'trades': trades_full,
            'equity': equity_full,
            'data': df_full
        }

        monitor.log_progress(sym, "completed")

        # Monitor resources every 10 symbols
        if i % 10 == 0:
            resources = monitor.monitor_resources()
            print(f"💾 Memory: {resources['memory_percent']:.1f}%, CPU: {resources['cpu_percent']:.1f}%")

    # OPTIMIZATION 2: Build all windows from cached results
    windows_years = [1, 3, 5, None]
    window_results = optimize_window_processing(symbol_results, windows_years)

    # Continue with existing portfolio building logic using window_results...
"""

    print("🔧 INTEGRATION EXAMPLE:")
    print("=" * 24)
    print(integration_code)


if __name__ == "__main__":
    # Test the monitor
    monitor = BacktestMonitor("test_output", 10)

    print("Testing monitoring functionality...")

    for i in range(3):
        symbol = f"TEST{i+1}"
        monitor.log_progress(symbol, "processing")
        time.sleep(0.1)  # Simulate processing
        monitor.log_progress(symbol, "completed")

    print("\n" + "=" * 50)
    example_integration()
