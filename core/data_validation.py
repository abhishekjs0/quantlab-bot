"""Data validation framework for backtest integrity.

Ensures that historical data used in backtests is valid, complete, and matches
what's expected. Prevents data quality issues like stale caches or corrupted files.
"""

import hashlib
import os
from datetime import datetime
from typing import Any, Optional

import pandas as pd


class DataValidation:
    """Validate historical OHLCV data before backtesting."""

    def __init__(self, df: pd.DataFrame, symbol: str, cache_file: Optional[str] = None):
        """
        Initialize validator with OHLCV data.

        Args:
            df: OHLCV DataFrame with index as datetime
            symbol: Stock symbol (for logging)
            cache_file: Path to cache file (optional, for metadata)
        """
        self.df = df
        self.symbol = symbol
        self.cache_file = cache_file
        self.errors = []
        self.warnings = []
        self.fingerprint = None
        self.stats = {}

    def compute_fingerprint(self) -> str:
        """
        Compute data fingerprint for validation.

        Returns hash of data characteristics to detect if data has changed.
        """
        if self.df.empty:
            self.fingerprint = "EMPTY"
            return self.fingerprint

        try:
            high = float(self.df["high"].max())
            low = float(self.df["low"].max())
            close = float(self.df["close"].iloc[-1])
            rows = len(self.df)
            first_date = str(self.df.index.min())[:10]
            last_date = str(self.df.index.max())[:10]

            data_str = f"{high:.4f}|{low:.4f}|{close:.4f}|{rows}|{first_date}|{last_date}"
            self.fingerprint = hashlib.sha256(data_str.encode()).hexdigest()[:8]
            return self.fingerprint
        except Exception as e:
            self.errors.append(f"Fingerprint computation failed: {e}")
            self.fingerprint = "ERROR"
            return self.fingerprint

    def get_stats(self) -> dict:
        """Get data statistics for reporting."""
        if not self.stats:
            try:
                self.stats = {
                    "rows": len(self.df),
                    "high_max": float(self.df["high"].max()),
                    "high_min": float(self.df["high"].min()),
                    "low_max": float(self.df["low"].max()),
                    "low_min": float(self.df["low"].min()),
                    "close_first": float(self.df["close"].iloc[0]),
                    "close_last": float(self.df["close"].iloc[-1]),
                    "date_first": str(self.df.index.min())[:10],
                    "date_last": str(self.df.index.max())[:10],
                }
            except Exception as e:
                self.errors.append(f"Stats computation failed: {e}")
                self.stats = {}
        return self.stats

    def validate_structure(self) -> bool:
        """Validate DataFrame structure (columns, index, types)."""
        # Check required columns
        required_cols = {"open", "high", "low", "close", "volume"}
        if not required_cols.issubset({c.lower() for c in self.df.columns}):
            self.errors.append(
                f"Missing required columns. Found: {list(self.df.columns)}"
            )
            return False

        # Check index is datetime
        if not isinstance(self.df.index, pd.DatetimeIndex):
            try:
                pd.to_datetime(self.df.index)
            except Exception:
                self.errors.append("Index is not datetime-convertible")
                return False

        # Check minimum rows
        if len(self.df) < 100:
            self.warnings.append(
                f"Very small dataset: {len(self.df)} rows (expected 500+)"
            )
            if len(self.df) < 50:
                self.errors.append("Dataset too small: < 50 rows")
                return False

        return True

    def validate_values(self) -> bool:
        """Validate OHLC values are reasonable."""
        errors_found = False

        # Check for NaNs in required columns
        for col in ["open", "high", "low", "close"]:
            col_lower = col.lower()
            if col_lower in [c.lower() for c in self.df.columns]:
                nan_count = self.df[col_lower].isna().sum()
                if nan_count > 0:
                    if nan_count / len(self.df) > 0.1:  # More than 10% NaN
                        self.errors.append(
                            f"Column {col}: {nan_count} NaNs ({nan_count/len(self.df)*100:.1f}%)"
                        )
                        errors_found = True
                    else:
                        self.warnings.append(
                            f"Column {col}: {nan_count} NaNs ({nan_count/len(self.df)*100:.1f}%)"
                        )

        # Check high >= low
        try:
            high_col = [c for c in self.df.columns if c.lower() == "high"][0]
            low_col = [c for c in self.df.columns if c.lower() == "low"][0]
            close_col = [c for c in self.df.columns if c.lower() == "close"][0]

            violations = (self.df[high_col] < self.df[low_col]).sum()
            if violations > 0:
                self.errors.append(f"High < Low in {violations} rows")
                errors_found = True

            # Check close is between high and low
            close_violations = (
                (self.df[close_col] > self.df[high_col])
                | (self.df[close_col] < self.df[low_col])
            ).sum()
            if close_violations > 0:
                self.warnings.append(f"Close outside high/low in {close_violations} rows")

            # Check for zero prices
            zero_count = (self.df[close_col] == 0).sum()
            if zero_count > 0:
                self.warnings.append(f"Zero close prices in {zero_count} rows")

            # Check for negative prices
            neg_count = (self.df[close_col] < 0).sum()
            if neg_count > 0:
                self.errors.append(f"Negative prices in {neg_count} rows")
                errors_found = True
        except Exception as e:
            self.errors.append(f"Value validation failed: {e}")
            errors_found = True

        return not errors_found

    def validate_continuity(self) -> bool:
        """Check for gaps in time series."""
        try:
            # Check index is sorted
            if not self.df.index.is_monotonic_increasing:
                self.warnings.append("Index is not sorted chronologically")

            # For daily data, allow weekends/holidays
            # For intraday, check for larger gaps
            if isinstance(self.df.index, pd.DatetimeIndex):
                freq = pd.infer_freq(self.df.index)
                if freq and freq not in ["D", "B"]:  # D=daily, B=business daily
                    # Intraday data - allow gaps but flag extreme ones
                    gaps = self.df.index.to_series().diff()
                    max_gap = gaps.max()
                    if isinstance(max_gap, pd.Timedelta) and max_gap > pd.Timedelta(hours=24):
                        self.warnings.append(f"Large gap detected: {max_gap}")

            return True
        except Exception as e:
            self.warnings.append(f"Continuity check failed: {e}")
            return True  # Don't fail on this

    def validate_trade_prices(self, entry_price: float, exit_price: Optional[float]) -> bool:
        """
        Validate that entry/exit prices exist in historical data.

        Args:
            entry_price: Entry price to validate
            exit_price: Exit price to validate (optional)

        Returns:
            True if prices are within reasonable historical bounds
        """
        try:
            high_max = float(self.df["high"].max())
            low_min = float(self.df["low"].min())

            tolerance = 0.01  # 1% tolerance for intraday variations

            # Check entry price
            if entry_price > high_max * (1 + tolerance):
                self.errors.append(
                    f"Entry price {entry_price} exceeds max high {high_max:.2f}"
                )
                return False

            if entry_price < low_min * (1 - tolerance):
                self.errors.append(
                    f"Entry price {entry_price} below min low {low_min:.2f}"
                )
                return False

            # Check exit price if provided
            if exit_price is not None and exit_price > 0:
                if exit_price > high_max * (1 + tolerance):
                    self.errors.append(
                        f"Exit price {exit_price} exceeds max high {high_max:.2f}"
                    )
                    return False

                if exit_price < low_min * (1 - tolerance):
                    self.errors.append(
                        f"Exit price {exit_price} below min low {low_min:.2f}"
                    )
                    return False

            return True
        except Exception as e:
            self.errors.append(f"Trade price validation failed: {e}")
            return False

    def validate_cache_file(self) -> bool:
        """Validate cache file exists and is recent."""
        if not self.cache_file:
            self.warnings.append("Cache file path not provided (skip file validation)")
            return True

        try:
            if not os.path.exists(self.cache_file):
                self.errors.append(f"Cache file not found: {self.cache_file}")
                return False

            # Check file size
            file_size = os.path.getsize(self.cache_file)
            if file_size < 1000:  # < 1KB
                self.errors.append(f"Cache file too small: {file_size} bytes")
                return False

            # Check modification time
            mod_time = os.path.getmtime(self.cache_file)
            mod_datetime = datetime.fromtimestamp(mod_time)
            age_days = (datetime.now() - mod_datetime).days

            if age_days > 365:
                self.warnings.append(f"Cache file is {age_days} days old")
            elif age_days > 30:
                self.warnings.append(f"Cache file is {age_days} days old")

            return True
        except Exception as e:
            self.errors.append(f"Cache file validation failed: {e}")
            return False

    def validate_all(self) -> dict:
        """Run all validations and return results."""
        results = {
            "symbol": self.symbol,
            "timestamp": datetime.now().isoformat(),
            "passed": True,
            "checks": {},
        }

        # Run validations
        checks = [
            ("structure", self.validate_structure),
            ("values", self.validate_values),
            ("continuity", self.validate_continuity),
            ("cache_file", self.validate_cache_file),
        ]

        for check_name, check_func in checks:
            try:
                passed = check_func()
                results["checks"][check_name] = {"passed": passed}
            except Exception as e:
                results["checks"][check_name] = {"passed": False, "error": str(e)}
                self.errors.append(f"Check {check_name} exception: {e}")

        # Compute fingerprint
        self.compute_fingerprint()

        results["fingerprint"] = self.fingerprint
        results["stats"] = self.get_stats()
        results["errors"] = self.errors
        results["warnings"] = self.warnings
        results["passed"] = len(self.errors) == 0

        return results

    def report(self) -> str:
        """Generate human-readable validation report."""
        lines = []
        lines.append(f"\n{'='*70}")
        lines.append(f"DATA VALIDATION REPORT: {self.symbol}")
        lines.append(f"{'='*70}")

        # Overall status
        status = "✅ PASSED" if not self.errors else "❌ FAILED"
        lines.append(f"\nStatus: {status}")
        lines.append(f"Fingerprint: {self.fingerprint}")

        # Stats
        if self.stats:
            lines.append("\nData Statistics:")
            lines.append(
                f"  Rows: {self.stats.get('rows')} ({self.stats.get('date_first')} to {self.stats.get('date_last')})"
            )
            lines.append(
                f"  Price range: {self.stats.get('low_min'):.2f} - {self.stats.get('high_max'):.2f}"
            )
            lines.append(f"  Last close: {self.stats.get('close_last'):.2f}")

        # Errors
        if self.errors:
            lines.append(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  • {error}")

        # Warnings
        if self.warnings:
            lines.append(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        if not self.errors and not self.warnings:
            lines.append("\n✅ All validations passed!")

        lines.append(f"\n{'='*70}\n")
        return "\n".join(lines)
