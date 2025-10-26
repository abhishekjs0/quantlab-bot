"""
Universal Indicator Analysis for QuantLab
==========================================

A flexible script to add technical indicators to consolidated trade data for ANY strategy.
This universal version can analyze trades from any strategy and add comprehensive
technical indicators for optimization and analysis purposes.

Features:
- Works with any strategy's consolidated trades output
- Calculates 15+ technical indicators (ATR, ADX, RSI, EMAs, MACD, etc.)
- Supports custom indicator configurations
- Provides comprehensive filter analysis
- Generates optimization insights

Usage:
    python scripts/universal_indicator_analysis.py --trades_file path/to/consolidated_trades.csv
    python scripts/universal_indicator_analysis.py --trades_file path/to/trades.csv --strategy ichimoku
    python scripts/universal_indicator_analysis.py --auto-detect  # Find latest trades files
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.loaders import load_many_india, load_ohlc_yf


class UniversalIndicatorAnalyzer:
    """Universal technical indicator analyzer for any strategy."""

    def __init__(self, use_cache_only: bool = True, verbose: bool = True):
        self.use_cache_only = use_cache_only
        self.verbose = verbose
        self.symbol_data_cache = {}

    def calculate_atr_pct(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Calculate ATR as percentage of close price."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        alpha = 1 / period
        atr = tr.ewm(alpha=alpha, adjust=False).mean()
        atr_pct = (atr / close) * 100
        return atr_pct.fillna(0)

    def calculate_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate ADX and Directional Indicators."""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        plus_dm = high.diff()
        minus_dm = -low.diff()

        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

        alpha = 1 / period
        tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
        plus_dm_smooth = plus_dm.ewm(alpha=alpha, adjust=False).mean()
        minus_dm_smooth = minus_dm.ewm(alpha=alpha, adjust=False).mean()

        plus_di = 100 * plus_dm_smooth / tr_smooth
        minus_di = 100 * minus_dm_smooth / tr_smooth

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        dx = dx.fillna(0)

        adx = dx.ewm(alpha=alpha, adjust=False).mean()
        return adx, plus_di, minus_di

    def calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        alpha = 1 / period
        avg_gain = gain.ewm(alpha=alpha, adjust=False).mean()
        avg_loss = loss.ewm(alpha=alpha, adjust=False).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def calculate_macd(
        self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD indicators."""
        ema_fast = close.ewm(span=fast).mean()
        ema_slow = close.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    def calculate_stochastic(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> tuple[pd.Series, pd.Series]:
        """Calculate Stochastic oscillator."""
        lowest_low = low.rolling(k_period).min()
        highest_high = high.rolling(k_period).max()
        k_percent = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d_percent = k_percent.rolling(d_period).mean()
        return k_percent, d_percent

    def calculate_cci(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
    ) -> pd.Series:
        """Calculate Commodity Channel Index."""
        tp = (high + low + close) / 3
        tp_sma = tp.rolling(period).mean()
        mean_dev = tp.rolling(period).apply(
            lambda x: np.mean(np.abs(x - x.mean())), raw=True
        )
        cci = (tp - tp_sma) / (0.015 * mean_dev)
        return cci.fillna(0)

    def calculate_comprehensive_indicators(
        self, df: pd.DataFrame
    ) -> dict[str, pd.Series]:
        """Calculate all technical indicators for a symbol's data."""
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)
        volume = df.get("volume", pd.Series(index=df.index, dtype=float))

        indicators = {}

        # Basic indicators
        indicators["atr_pct"] = self.calculate_atr_pct(high, low, close, 14)
        indicators["adx"], indicators["plus_di"], indicators["minus_di"] = (
            self.calculate_adx(high, low, close, 14)
        )
        indicators["rsi"] = self.calculate_rsi(close, 14)
        indicators["rsi_21"] = self.calculate_rsi(close, 21)

        # MACD family
        (
            indicators["macd_line"],
            indicators["macd_signal"],
            indicators["macd_histogram"],
        ) = self.calculate_macd(close)

        # Stochastic
        indicators["stoch_k"], indicators["stoch_d"] = self.calculate_stochastic(
            high, low, close
        )

        # CCI
        indicators["cci"] = self.calculate_cci(high, low, close, 20)

        # EMAs (multiple periods)
        for period in [20, 34, 50, 55, 89, 200]:
            indicators[f"ema_{period}"] = close.ewm(span=period).mean()

        # Price position relative to EMAs
        indicators["above_ema_20"] = close > indicators["ema_20"]
        indicators["above_ema_50"] = close > indicators["ema_50"]
        indicators["above_ema_200"] = close > indicators["ema_200"]

        # DI bullish signal
        indicators["di_bullish"] = indicators["plus_di"] > indicators["minus_di"]

        # CMF (if volume available)
        if not volume.isna().all():
            mfm = ((close - low) - (high - close)) / (high - low)
            mfm = mfm.fillna(0)
            mfv = mfm * volume
            indicators["cmf"] = mfv.rolling(20).sum() / volume.rolling(20).sum()
        else:
            indicators["cmf"] = pd.Series(0, index=df.index)

        return indicators

    def load_symbol_data(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        """Load data for all required symbols."""
        if self.verbose:
            print(f"Loading data for {len(symbols)} symbols...")

        if self.use_cache_only:
            # Use individual symbol loading for better cache control
            for symbol in symbols:
                try:
                    df = load_ohlc_yf(
                        symbol, interval="1d", period="max", use_cache_only=True
                    )
                    if df is not None and not df.empty:
                        self.symbol_data_cache[symbol] = df
                        if self.verbose:
                            print(f"✓ {symbol}: {len(df)} days")
                    else:
                        if self.verbose:
                            print(f"✗ {symbol}: No cached data")
                except Exception as e:
                    if self.verbose:
                        print(f"✗ {symbol}: Error - {e}")
        else:
            # Use bulk loading
            try:
                self.symbol_data_cache = load_many_india(
                    symbols, interval="1d", period="max", cache=True
                )
            except Exception as e:
                print(f"Error loading bulk data: {e}")

        return self.symbol_data_cache

    def process_trades_with_indicators(
        self,
        trades_file: str,
        output_file: str | None = None,
        basket_symbols: list[str] | None = None,
    ) -> str:
        """
        Add comprehensive technical indicators to any strategy's trades file.

        Args:
            trades_file: Path to consolidated trades CSV
            output_file: Output path (auto-generated if None)
            basket_symbols: List of symbols (auto-detected if None)

        Returns:
            Path to enhanced trades file
        """
        if output_file is None:
            output_file = trades_file.replace(".csv", "_with_indicators.csv")

        # Read trades
        if self.verbose:
            print(f"Reading trades from: {trades_file}")
        trades_df = pd.read_csv(trades_file)

        if trades_df.empty:
            print("No trades found in file")
            return output_file

        if self.verbose:
            print(f"Found {len(trades_df)} total trade records")

        # Auto-detect symbols from trades if not provided
        if basket_symbols is None:
            basket_symbols = sorted(trades_df["Symbol"].unique())
            if self.verbose:
                print(f"Auto-detected {len(basket_symbols)} unique symbols from trades")

        # Load symbol data
        self.load_symbol_data(basket_symbols)

        # Initialize indicator columns
        indicator_columns = [
            "atr_pct",
            "adx",
            "plus_di",
            "minus_di",
            "rsi",
            "rsi_21",
            "macd_line",
            "macd_signal",
            "macd_histogram",
            "stoch_k",
            "stoch_d",
            "cci",
            "cmf",
            "ema_20",
            "ema_34",
            "ema_50",
            "ema_55",
            "ema_89",
            "ema_200",
            "above_ema_20",
            "above_ema_50",
            "above_ema_200",
            "di_bullish",
        ]

        for col in indicator_columns:
            trades_df[col] = np.nan

        # Process each trade
        processed_count = 0
        for idx, row in trades_df.iterrows():
            symbol = row["Symbol"]
            date_str = row["Date/Time"]

            # Parse trade date (handle multiple formats)
            try:
                if "T" in date_str:
                    trade_date = pd.to_datetime(date_str.split("T")[0])
                else:
                    trade_date = pd.to_datetime(date_str.split(" ")[0])
            except Exception:
                continue

            # Get symbol data
            if symbol not in self.symbol_data_cache:
                continue

            df = self.symbol_data_cache[symbol].copy()
            df.index = pd.to_datetime(df.index)

            # Get data up to trade date
            trade_data = df[df.index <= trade_date]
            if trade_data.empty:
                continue

            # Calculate all indicators
            try:
                indicators = self.calculate_comprehensive_indicators(trade_data)

                # Store latest values in trades dataframe
                for col in indicator_columns:
                    if col in indicators and not indicators[col].empty:
                        value = indicators[col].iloc[-1]
                        if col.startswith("above_") or col == "di_bullish":
                            trades_df.at[idx, col] = bool(value)
                        else:
                            trades_df.at[idx, col] = float(value)

                processed_count += 1

            except Exception as e:
                if self.verbose:
                    print(f"Error processing {symbol} on {trade_date}: {e}")

        if self.verbose:
            print(f"Successfully processed indicators for {processed_count} trades")

        # Add derived analysis columns
        self.add_filter_analysis(trades_df)

        # Save enhanced file
        if self.verbose:
            print(f"Saving enhanced trades to: {output_file}")
        trades_df.to_csv(output_file, index=False)

        # Generate analysis report
        self.generate_analysis_report(trades_df)

        return output_file

    def add_filter_analysis(self, trades_df: pd.DataFrame):
        """Add common filter conditions for analysis."""
        # Standard filter conditions
        trades_df["atr_filter_2_5"] = (trades_df["atr_pct"] >= 2.0) & (
            trades_df["atr_pct"] <= 5.0
        )
        trades_df["adx_filter_20"] = trades_df["adx"] >= 20.0
        trades_df["adx_filter_25"] = trades_df["adx"] >= 25.0
        trades_df["rsi_filter_40_70"] = (trades_df["rsi"] >= 40.0) & (
            trades_df["rsi"] <= 70.0
        )
        trades_df["rsi_filter_30_70"] = (trades_df["rsi"] >= 30.0) & (
            trades_df["rsi"] <= 70.0
        )
        trades_df["rsi_oversold"] = trades_df["rsi"] < 30.0
        trades_df["rsi_overbought"] = trades_df["rsi"] > 70.0

        # Trend filters
        trades_df["bullish_trend"] = (
            trades_df["above_ema_200"] & trades_df["di_bullish"]
        )
        trades_df["strong_trend"] = trades_df["bullish_trend"] & (
            trades_df["adx"] >= 25.0
        )

        # MACD filters
        trades_df["macd_bullish"] = trades_df["macd_line"] > trades_df["macd_signal"]
        trades_df["macd_above_zero"] = trades_df["macd_line"] > 0

        # Multiple EMA alignment
        trades_df["ema_aligned_bull"] = (
            trades_df["above_ema_20"]
            & trades_df["above_ema_50"]
            & trades_df["above_ema_200"]
        )

        # Add profitability analysis (if exit trades exist)
        if "Net P&L %" in trades_df.columns:
            try:
                # Handle both string and numeric formats
                if trades_df["Net P&L %"].dtype == "object":
                    pnl_numeric = trades_df["Net P&L %"].str.rstrip("%").astype(float)
                else:
                    pnl_numeric = trades_df["Net P&L %"]
                trades_df["is_profitable"] = pnl_numeric > 0
            except Exception:
                trades_df["is_profitable"] = False

    def generate_analysis_report(self, trades_df: pd.DataFrame):
        """Generate comprehensive analysis report."""
        if not self.verbose:
            return

        print("\n" + "=" * 80)
        print("UNIVERSAL INDICATOR ANALYSIS REPORT")
        print("=" * 80)

        # Basic statistics
        total_trades = len(trades_df)
        entry_trades = trades_df[trades_df["Type"].str.contains("Entry", na=False)]
        exit_trades = trades_df[trades_df["Type"].str.contains("Exit", na=False)]

        print("📊 TRADE SUMMARY:")
        print(f"   Total records: {total_trades}")
        print(f"   Entry trades: {len(entry_trades)}")
        print(f"   Exit trades: {len(exit_trades)}")

        # Focus on entry trades for indicator analysis
        if len(entry_trades) > 0:
            valid_entries = entry_trades.dropna(subset=["atr_pct", "adx", "rsi"])
            print(f"   Entries with indicators: {len(valid_entries)}")

            if len(valid_entries) > 0:
                print("\n📈 INDICATOR STATISTICS (Entry Trades):")
                for indicator in ["atr_pct", "adx", "rsi", "rsi_21", "cci"]:
                    if indicator in valid_entries.columns:
                        series = valid_entries[indicator]
                        print(
                            f"   {indicator.upper()}: min={series.min():.2f}, max={series.max():.2f}, avg={series.mean():.2f}"
                        )

                # Boolean indicators
                print("\n🎯 TREND INDICATORS:")
                for indicator in [
                    "above_ema_200",
                    "di_bullish",
                    "macd_bullish",
                    "ema_aligned_bull",
                ]:
                    if indicator in valid_entries.columns:
                        count = valid_entries[indicator].sum()
                        pct = (count / len(valid_entries)) * 100
                        print(
                            f"   {indicator}: {count}/{len(valid_entries)} trades ({pct:.1f}%)"
                        )

                # Filter effectiveness
                print("\n🔍 FILTER EFFECTIVENESS:")
                filter_cols = [
                    col
                    for col in valid_entries.columns
                    if col.endswith("_filter_2_5")
                    or col.endswith("_filter_20")
                    or col.endswith("_filter_25")
                    or col.endswith("_filter_40_70")
                ]
                for filter_col in filter_cols:
                    count = valid_entries[filter_col].sum()
                    pct = (count / len(valid_entries)) * 100
                    print(
                        f"   {filter_col}: {count}/{len(valid_entries)} trades ({pct:.1f}%)"
                    )

        # Profitability analysis if available
        if "is_profitable" in trades_df.columns and len(exit_trades) > 0:
            profitable = exit_trades[exit_trades["is_profitable"]]
            print("\n💰 PROFITABILITY ANALYSIS:")
            print(
                f"   Profitable trades: {len(profitable)}/{len(exit_trades)} ({len(profitable)/len(exit_trades)*100:.1f}%)"
            )

        print(
            f"\n✅ Analysis complete! Enhanced file contains {len([col for col in trades_df.columns if col in ['atr_pct', 'adx', 'rsi', 'macd_line', 'ema_20', 'ema_50', 'ema_200']])} core indicators."
        )


def auto_detect_trades_files(reports_dir: str = "reports") -> list[str]:
    """Auto-detect recent consolidated trades files."""
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        return []

    trade_files = []
    for run_dir in sorted(reports_path.iterdir(), reverse=True):
        if run_dir.is_dir():
            for file in run_dir.glob("consolidated_trades*.csv"):
                if "_with_indicators" not in file.name:
                    trade_files.append(str(file))
            if trade_files:  # Found files in latest run
                break

    return trade_files


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Universal Indicator Analysis for QuantLab"
    )
    parser.add_argument(
        "--trades_file", type=str, help="Path to consolidated trades CSV file"
    )
    parser.add_argument("--output_file", type=str, help="Output file path (optional)")
    parser.add_argument("--strategy", type=str, help="Strategy name (for context)")
    parser.add_argument(
        "--auto-detect", action="store_true", help="Auto-detect latest trades files"
    )
    parser.add_argument(
        "--use-cache-only",
        action="store_true",
        default=True,
        help="Use cached data only",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose output")

    args = parser.parse_args()

    analyzer = UniversalIndicatorAnalyzer(
        use_cache_only=args.use_cache_only, verbose=not args.quiet
    )

    if args.auto_detect:
        print("🔍 Auto-detecting latest trades files...")
        trade_files = auto_detect_trades_files()
        if not trade_files:
            print("❌ No consolidated trades files found in reports directory")
            return

        print(f"Found {len(trade_files)} trades files:")
        for file in trade_files:
            print(f"   📄 {file}")

        for trades_file in trade_files:
            print(f"\n{'='*60}")
            print(f"Processing: {Path(trades_file).name}")
            print(f"{'='*60}")
            analyzer.process_trades_with_indicators(trades_file)

    elif args.trades_file:
        if not Path(args.trades_file).exists():
            print(f"❌ Trades file not found: {args.trades_file}")
            return

        if args.strategy:
            print(f"🎯 Processing {args.strategy} strategy trades...")

        analyzer.process_trades_with_indicators(args.trades_file, args.output_file)

    else:
        print("❌ Please specify --trades_file or use --auto-detect")
        parser.print_help()


if __name__ == "__main__":
    main()
