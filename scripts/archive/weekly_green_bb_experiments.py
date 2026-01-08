# Weekly Green BB Experiments Archive
# Combined on 2026-01-08


# ========== FROM: test_weekly_green_bb_hypothesis.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Hypothesis Test
====================================
Hypothesis: When a completed weekly green candle forms with:
1. Opens below Bollinger Band 1 SD
2. Body bigger than previous candle's body
Then: Trade on next week's first trading day and hold until week close

Test on large basket across multiple years.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

# Configuration
CACHE_DIR = Path("data/cache")
BASKET_FILE = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37  # 0.37% for both entry and exit


def load_basket(path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLC data for symbol from cache."""
    # Try multiple cache patterns
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/dhan_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily data to weekly candles (Monday-Friday)."""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame) -> pd.DataFrame:
    """Identify trading signals based on hypothesis."""
    if len(weekly_df) < 25:  # Need enough data for BB calculation
        return pd.DataFrame()
    
    # Calculate Bollinger Bands on closing prices (period=20 weeks)
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(
        weekly_df["close"], period=20, std_dev=1.0
    )
    
    weekly_df["bb_upper"] = upper_bb
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_lower"] = lower_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)  # 1 SD below MA
    
    # Add 1 SD offset from middle for easier checking
    weekly_df["bb_offset_1sd"] = weekly_df["bb_middle"] - (weekly_df["bb_middle"] - weekly_df["bb_lower"])
    
    # Identify signals
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        # Condition 1: Current week is green (close > open)
        is_green = curr["close"] > curr["open"]
        
        # Condition 2: Opens below 1 SD below middle BB
        opens_below_bb_1sd = curr["open"] < weekly_df.iloc[i]["bb_offset_1sd"]
        
        # Condition 3: Current body is bigger than previous body
        bigger_body = curr["body"] > prev["body"]
        
        if is_green and opens_below_bb_1sd and bigger_body:
            signals.append({
                "signal_date": curr["date"],
                "signal_week_year": f"{curr['year']}-W{curr['week']}",
                "open": curr["open"],
                "close": curr["close"],
                "body": curr["body"],
                "prev_body": prev["body"],
                "bb_offset_1sd": weekly_df.iloc[i]["bb_offset_1sd"],
                "bb_middle": weekly_df.iloc[i]["bb_middle"],
            })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the next Monday after given date."""
    days_ahead = 0 - date.weekday()  # Monday is 0
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def find_week_close(date: pd.Timestamp, df: pd.DataFrame) -> Optional[Tuple[pd.Timestamp, float]]:
    """Find the closing price on the Friday of the week containing given date."""
    # Get the Friday of the same week
    days_ahead = 4 - date.weekday()  # Friday is 4
    if days_ahead < 0:
        days_ahead += 7
    
    target_friday = date + timedelta(days=days_ahead)
    target_friday_start = target_friday.replace(hour=0, minute=0, second=0)
    
    # Find the data point on or closest to that Friday
    mask = (df["date"].dt.date == target_friday.date()) | (df["date"] > target_friday_start)
    candidates = df[mask].head(1)
    
    if len(candidates) > 0:
        row = candidates.iloc[0]
        return row["date"], row["close"]
    
    return None


def calculate_trade_returns(signal_row: Dict, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """Calculate returns for a single trade based on signal."""
    signal_date = signal_row["signal_date"]
    entry_price = signal_row["close"]  # Use closing price of signal week as reference
    
    # Find next Monday - the actual entry day
    next_monday = find_next_monday(signal_date)
    
    # Find entry price on that Monday
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price_actual = entry_actual["open"]  # Open on Monday
    
    # Find week close (Friday) from that Monday
    week_close_result = find_week_close(next_monday, df)
    if week_close_result is None:
        return None
    
    exit_date, exit_price = week_close_result
    
    # Calculate returns
    gross_return = (exit_price - entry_price_actual) / entry_price_actual
    transaction_costs = TRANSACTION_COST_PCT / 100 * 2  # Entry + Exit
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "signal_week": signal_row["signal_week_year"],
        "entry_date": next_monday,
        "entry_price": entry_price_actual,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
        "holding_days": (exit_date - next_monday).days,
    }


def analyze_symbol(symbol: str) -> Tuple[List[Dict], int]:
    """Analyze a single symbol for the hypothesis."""
    trades = []
    
    # Load data
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    # Get weekly candles
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    # Identify signals
    signals_df = identify_signals(weekly_df)
    if len(signals_df) == 0:
        return trades, 0
    
    # Calculate returns for each signal
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_returns(signal_row.to_dict(), df, symbol)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def print_summary(all_trades: List[Dict]) -> None:
    """Print comprehensive analysis summary."""
    if not all_trades:
        print("\n❌ No trades generated from hypothesis signals")
        return
    
    df = pd.DataFrame(all_trades)
    
    print("\n" + "="*100)
    print("WEEKLY GREEN CANDLE BB HYPOTHESIS TEST - RESULTS")
    print("="*100)
    
    # Overall metrics
    total_trades = len(df)
    winning_trades = len(df[df["net_return_pct"] > 0])
    losing_trades = len(df[df["net_return_pct"] <= 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_return = df["net_return_pct"].mean()
    total_return = df["net_return_pct"].sum()
    median_return = df["net_return_pct"].median()
    std_return = df["net_return_pct"].std()
    
    best_trade = df["net_return_pct"].max()
    worst_trade = df["net_return_pct"].min()
    
    print(f"\n📊 OVERALL METRICS")
    print(f"{'─'*100}")
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
    print(f"Losing Trades: {losing_trades} ({100-win_rate:.1f}%)")
    print(f"Average Return/Trade: {avg_return:.2f}%")
    print(f"Median Return/Trade: {median_return:.2f}%")
    print(f"Total Return (Sum): {total_return:.2f}%")
    print(f"Std Dev: {std_return:.2f}%")
    print(f"Best Trade: {best_trade:.2f}%")
    print(f"Worst Trade: {worst_trade:.2f}%")
    
    # By symbol
    print(f"\n📈 TOP PERFORMERS (by symbol)")
    print(f"{'─'*100}")
    symbol_stats = df.groupby("symbol").agg({
        "net_return_pct": ["count", "mean", "sum"],
    }).round(2)
    symbol_stats.columns = ["Trades", "Avg Return %", "Total Return %"]
    symbol_stats = symbol_stats.sort_values("Total Return %", ascending=False).head(10)
    print(symbol_stats.to_string())
    
    # Monthly distribution
    print(f"\n📅 TRADES BY MONTH")
    print(f"{'─'*100}")
    df["year_month"] = pd.to_datetime(df["entry_date"]).dt.to_period("M")
    monthly_stats = df.groupby("year_month").agg({
        "net_return_pct": ["count", "mean", "sum"],
    }).round(2)
    monthly_stats.columns = ["Trades", "Avg Return %", "Total Return %"]
    print(monthly_stats.to_string())
    
    # Return distribution
    print(f"\n📊 RETURN DISTRIBUTION")
    print(f"{'─'*100}")
    bins = [-np.inf, -10, -5, -2, 0, 2, 5, 10, np.inf]
    labels = ["<-10%", "-10 to -5%", "-5 to -2%", "-2 to 0%", "0 to 2%", "2 to 5%", "5 to 10%", ">10%"]
    dist = pd.cut(df["net_return_pct"], bins=bins, labels=labels).value_counts().sort_index()
    print(dist.to_string())
    
    # Recent trades
    print(f"\n🔄 RECENT TRADES (Last 10)")
    print(f"{'─'*100}")
    recent = df.nlargest(10, "entry_date")[["symbol", "entry_date", "exit_date", "entry_price", "exit_price", "net_return_pct"]]
    print(recent.to_string(index=False))


def main():
    """Main execution."""
    print(f"\n🔬 Testing Weekly Green Candle BB Hypothesis")
    print(f"{'─'*100}")
    print(f"Basket: {BASKET_FILE}")
    print(f"Cache: {CACHE_DIR}")
    print(f"Signal Conditions:")
    print(f"  1. Weekly candle is GREEN (close > open)")
    print(f"  2. Opens BELOW Bollinger Band 1-SD")
    print(f"  3. Body BIGGER than previous week's body")
    print(f"Entry: Next Monday at open")
    print(f"Exit: Friday (end of week) at close")
    print()
    
    # Load basket
    symbols = load_basket(BASKET_FILE)
    print(f"📋 Loaded {len(symbols)} symbols from basket")
    
    # Analyze each symbol
    all_trades = []
    symbol_with_signals = 0
    symbols_analyzed = 0
    
    for i, symbol in enumerate(symbols):
        trades, signal_count = analyze_symbol(symbol)
        if signal_count > 0:
            symbol_with_signals += 1
            all_trades.extend(trades)
            print(f"  ✅ {symbol}: {len(trades)} trades from {signal_count} signals")
        symbols_analyzed += 1
        
        if (i + 1) % 20 == 0:
            print(f"     [{i+1}/{len(symbols)}] analyzed...")
    
    print(f"\n📊 Analysis Complete")
    print(f"{'─'*100}")
    print(f"Symbols Analyzed: {symbols_analyzed}")
    print(f"Symbols with Signals: {symbol_with_signals}")
    print(f"Total Trades Generated: {len(all_trades)}")
    
    # Print summary
    print_summary(all_trades)
    
    # Save detailed results
    if all_trades:
        results_df = pd.DataFrame(all_trades)
        output_path = "reports/hypothesis_weekly_green_bb_results.csv"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(output_path, index=False)
        print(f"\n💾 Detailed results saved to: {output_path}")


if __name__ == "__main__":
    main()


# ========== FROM: test_weekly_green_bb_variants.py ==========

#!/usr/bin/env python3
"""
Weekly Green Candle Hypothesis Test - Multiple Variants
========================================================
Tests progressively relaxed versions of the hypothesis to find
the optimal balance between signal frequency and quality.

Variants:
1. STRICT: All 3 conditions (green + BB 1SD + bigger body)
2. MODERATE: Green + bigger body (drop BB condition)
3. RELAXED: Just green candles (minimal filter)
4. BB_ONLY: Green + opens below BB 1SD (drop size condition)
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import glob
from typing import Dict, List, Tuple, Optional

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
BASKET_FILE = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37  # 0.37% for both entry and exit


def load_basket(path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def load_ohlc_data(symbol: str) -> Optional[pd.DataFrame]:
    """Load OHLC data for symbol from cache."""
    # Try multiple cache patterns
    patterns = [
        f"{CACHE_DIR}/dhan_*_{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}_1d.csv",
        f"{CACHE_DIR}/*{symbol}*.csv",
    ]
    
    for pattern in patterns:
        files = glob.glob(pattern)
        if files:
            try:
                df = pd.read_csv(files[0])
                # Handle different column names
                if "time" in df.columns:
                    df = df.rename(columns={"time": "date"})
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    return df
            except Exception:
                continue
    return None


def get_weekly_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Convert daily data to weekly candles (Monday-Friday)."""
    if len(df) < 10:
        return pd.DataFrame()
    
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"].dt.isocalendar().week
    df["year"] = df["date"].dt.isocalendar().year
    
    weekly = df.groupby(["year", "week"]).agg({
        "date": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).reset_index()
    
    weekly = weekly.sort_values("date").reset_index(drop=True)
    weekly["body"] = abs(weekly["close"] - weekly["open"])
    
    return weekly


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: float = 1.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands."""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    
    return upper, sma, lower


def identify_signals(weekly_df: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Identify trading signals based on variant."""
    if len(weekly_df) < 25:  # Need enough data for BB calculation
        return pd.DataFrame()
    
    # Calculate Bollinger Bands on closing prices
    upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(
        weekly_df["close"], period=20, std_dev=1.0
    )
    
    weekly_df["bb_upper"] = upper_bb
    weekly_df["bb_middle"] = middle_bb
    weekly_df["bb_lower"] = lower_bb
    weekly_df["bb_1sd_below"] = middle_bb - (middle_bb - lower_bb)
    
    signals = []
    
    for i in range(1, len(weekly_df)):
        curr = weekly_df.iloc[i]
        prev = weekly_df.iloc[i - 1]
        
        # Base condition: Current week is green
        is_green = curr["close"] > curr["open"]
        if not is_green:
            continue
        
        # Variant-specific conditions
        if variant == "STRICT":
            # All 3: green + opens below BB 1SD + bigger body
            opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
            bigger_body = curr["body"] > prev["body"]
            if not (opens_below_bb and bigger_body):
                continue
                
        elif variant == "MODERATE":
            # Green + bigger body (no BB)
            bigger_body = curr["body"] > prev["body"]
            if not bigger_body:
                continue
                
        elif variant == "BB_ONLY":
            # Green + opens below BB 1SD (no body size)
            opens_below_bb = curr["open"] < weekly_df.iloc[i]["bb_1sd_below"]
            if not opens_below_bb:
                continue
                
        elif variant == "RELAXED":
            # Just green (no other filters)
            pass
        
        signals.append({
            "signal_date": curr["date"],
            "signal_week_year": f"{curr['year']}-W{curr['week']}",
            "open": curr["open"],
            "close": curr["close"],
            "body": curr["body"],
            "prev_body": prev["body"] if i > 0 else 0,
        })
    
    return pd.DataFrame(signals) if signals else pd.DataFrame()


def find_next_monday(date: pd.Timestamp) -> pd.Timestamp:
    """Find the next Monday after given date."""
    days_ahead = 0 - date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return date + timedelta(days=days_ahead)


def find_week_close(date: pd.Timestamp, df: pd.DataFrame) -> Optional[Tuple[pd.Timestamp, float]]:
    """Find the closing price on the Friday of the week containing given date."""
    days_ahead = 4 - date.weekday()
    if days_ahead < 0:
        days_ahead += 7
    
    target_friday = date + timedelta(days=days_ahead)
    target_friday_start = target_friday.replace(hour=0, minute=0, second=0)
    
    mask = (df["date"].dt.date == target_friday.date()) | (df["date"] > target_friday_start)
    candidates = df[mask].head(1)
    
    if len(candidates) > 0:
        row = candidates.iloc[0]
        return row["date"], row["close"]
    
    return None


def calculate_trade_returns(signal_row: Dict, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """Calculate returns for a single trade."""
    signal_date = signal_row["signal_date"]
    
    next_monday = find_next_monday(signal_date)
    
    entry_candidates = df[df["date"].dt.date == next_monday.date()]
    if len(entry_candidates) == 0:
        return None
    
    entry_actual = entry_candidates.iloc[0]
    entry_price_actual = entry_actual["open"]
    
    week_close_result = find_week_close(next_monday, df)
    if week_close_result is None:
        return None
    
    exit_date, exit_price = week_close_result
    
    gross_return = (exit_price - entry_price_actual) / entry_price_actual
    transaction_costs = TRANSACTION_COST_PCT / 100 * 2
    net_return = gross_return - transaction_costs
    
    return {
        "symbol": symbol,
        "signal_date": signal_date,
        "entry_date": next_monday,
        "entry_price": entry_price_actual,
        "exit_date": exit_date,
        "exit_price": exit_price,
        "gross_return_pct": gross_return * 100,
        "transaction_cost_pct": transaction_costs * 100,
        "net_return_pct": net_return * 100,
    }


def analyze_symbol(symbol: str, variant: str) -> Tuple[List[Dict], int]:
    """Analyze a single symbol."""
    trades = []
    
    df = load_ohlc_data(symbol)
    if df is None or len(df) < 100:
        return trades, 0
    
    weekly_df = get_weekly_candles(df)
    if len(weekly_df) < 25:
        return trades, 0
    
    signals_df = identify_signals(weekly_df, variant)
    if len(signals_df) == 0:
        return trades, 0
    
    for _, signal_row in signals_df.iterrows():
        trade = calculate_trade_returns(signal_row.to_dict(), df, symbol)
        if trade:
            trades.append(trade)
    
    return trades, len(signals_df)


def analyze_variant(variant: str, symbols: List[str]) -> Dict:
    """Analyze all symbols for a variant."""
    all_trades = []
    signal_count = 0
    symbols_with_signals = 0
    
    print(f"\n  Analyzing {variant} variant...")
    
    for symbol in symbols:
        trades, signals = analyze_symbol(symbol, variant)
        if signals > 0:
            symbols_with_signals += 1
            signal_count += signals
            all_trades.extend(trades)
    
    # Calculate metrics
    if all_trades:
        df = pd.DataFrame(all_trades)
        total_return = df["net_return_pct"].sum()
        avg_return = df["net_return_pct"].mean()
        win_rate = (len(df[df["net_return_pct"] > 0]) / len(df) * 100) if len(df) > 0 else 0
        
        return {
            "variant": variant,
            "symbols_with_signals": symbols_with_signals,
            "total_signals": signal_count,
            "total_trades": len(all_trades),
            "total_return_pct": total_return,
            "avg_return_pct": avg_return,
            "win_rate_pct": win_rate,
            "trades_df": df,
        }
    else:
        return {
            "variant": variant,
            "symbols_with_signals": 0,
            "total_signals": 0,
            "total_trades": 0,
            "total_return_pct": 0,
            "avg_return_pct": 0,
            "win_rate_pct": 0,
            "trades_df": pd.DataFrame(),
        }


def print_comparison(results: List[Dict]) -> None:
    """Print comparison of all variants."""
    print("\n" + "="*120)
    print("HYPOTHESIS VARIANT COMPARISON")
    print("="*120)
    
    comparison_data = []
    for r in results:
        comparison_data.append({
            "Variant": r["variant"],
            "Symbols": r["symbols_with_signals"],
            "Signals": r["total_signals"],
            "Trades": r["total_trades"],
            "Total Return %": f"{r['total_return_pct']:.2f}",
            "Avg Return %": f"{r['avg_return_pct']:.2f}",
            "Win Rate %": f"{r['win_rate_pct']:.1f}",
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    print(comparison_df.to_string(index=False))
    
    # Detailed analysis for best variant
    best = max(results, key=lambda x: x["total_return_pct"] if x["total_trades"] > 10 else 0)
    
    if best["total_trades"] > 0:
        print(f"\n{'='*120}")
        print(f"DETAILED ANALYSIS: {best['variant']} (Best Performing)")
        print(f"{'='*120}")
        
        df = best["trades_df"]
        print(f"\n📊 Overall Metrics:")
        print(f"  Total Trades: {len(df)}")
        print(f"  Winning Trades: {len(df[df['net_return_pct'] > 0])} ({(len(df[df['net_return_pct'] > 0])/len(df)*100):.1f}%)")
        print(f"  Total Return: {df['net_return_pct'].sum():.2f}%")
        print(f"  Avg Return/Trade: {df['net_return_pct'].mean():.2f}%")
        print(f"  Best Trade: {df['net_return_pct'].max():.2f}%")
        print(f"  Worst Trade: {df['net_return_pct'].min():.2f}%")
        print(f"  Std Dev: {df['net_return_pct'].std():.2f}%")
        
        print(f"\n📈 Top 5 Symbols:")
        top_symbols = df.groupby("symbol").agg({"net_return_pct": ["count", "mean", "sum"]}).round(2)
        top_symbols.columns = ["Trades", "Avg %", "Total %"]
        top_symbols = top_symbols.sort_values("Total %", ascending=False).head(5)
        print(top_symbols.to_string())
        
        print(f"\n📅 Recent Trades (10):")
        recent = df.nlargest(10, "entry_date")[["symbol", "entry_date", "entry_price", "exit_price", "net_return_pct"]]
        print(recent.to_string(index=False))


def main():
    """Main execution."""
    print(f"\n🔬 COMPREHENSIVE HYPOTHESIS TESTING")
    print(f"{'─'*120}")
    print(f"Basket: {BASKET_FILE}")
    print(f"Entry: Next Monday at open")
    print(f"Exit: Friday (end of week) at close")
    print(f"\nVariants:")
    print(f"  STRICT:   Green + Opens Below BB 1SD + Bigger Body")
    print(f"  MODERATE: Green + Bigger Body (NO BB filter)")
    print(f"  BB_ONLY:  Green + Opens Below BB 1SD (NO size filter)")
    print(f"  RELAXED:  Just Green Candles (minimal filter)")
    print()
    
    # Load basket
    symbols = load_basket(BASKET_FILE)
    print(f"📋 Loaded {len(symbols)} symbols from basket")
    
    # Test each variant
    variants = ["STRICT", "MODERATE", "BB_ONLY", "RELAXED"]
    results = []
    
    for variant in variants:
        result = analyze_variant(variant, symbols)
        results.append(result)
    
    # Print comparison
    print_comparison(results)
    
    # Save best variant results
    best = max(results, key=lambda x: x["total_return_pct"] if x["total_trades"] > 10 else 0)
    if best["total_trades"] > 0:
        output_path = f"reports/hypothesis_weekly_green_{best['variant'].lower()}_results.csv"
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        best["trades_df"].to_csv(output_path, index=False)
        print(f"\n💾 Best variant ({best['variant']}) results saved to: {output_path}")


if __name__ == "__main__":
    main()
