#!/usr/bin/env python3
"""
Month-End to Month-Start Trading Strategy Analysis
===================================================
Strategy: Buy at open of 3rd last trading day of month N,
          Sell at close of 3rd trading day of month N+1

Analyzes returns by:
- Overall basket
- Market cap (Large/Mid/Small)
- Sector
- Individual stock performance
"""

import glob
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from calendar import monthrange

import pandas as pd
import numpy as np

# Configuration
CACHE_DIR = Path("data/cache/dhan/daily")
DATA_DIR = Path("data")

# Baskets
BASKETS = {
    "large": "data/baskets/basket_large.txt",
    "mid": "data/baskets/basket_mid.txt",
    "small": "data/baskets/basket_small.txt",
}

# Transaction costs (both legs combined)
TRANSACTION_COST_PCT = 0.37


def load_basket(basket_path: str) -> List[str]:
    """Load symbols from basket file."""
    with open(basket_path) as f:
        return [line.strip() for line in f if line.strip()]


def load_sector_mapping() -> Dict[str, Dict[str, str]]:
    """Load sector mapping from scrip master files."""
    sector_map = {}
    
    # Try dhan scrip master first
    dhan_file = DATA_DIR / "dhan-scrip-master-detailed.csv"
    if dhan_file.exists():
        try:
            df = pd.read_csv(dhan_file, low_memory=False)
            if "SEM_TRADING_SYMBOL" in df.columns and "SECTOR" in df.columns:
                for _, row in df.iterrows():
                    symbol = str(row.get("SEM_TRADING_SYMBOL", "")).strip()
                    sector = str(row.get("SECTOR", "")).strip()
                    cap_type = str(row.get("CAP_TYPE", "")).strip()
                    
                    if symbol and sector and sector != "" and sector != "nan":
                        # Clean symbol
                        clean_symbol = symbol.split("-")[0]
                        if clean_symbol not in sector_map:
                            sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
        except Exception as e:
            print(f"Error loading dhan scrip master: {e}")
    
    # Also load from cap files directly for more accurate mapping
    cap_files = [
        ("Large Cap_NSE_2026-01-02.csv", "Large Cap"),
        ("Mid Cap_NSE_2026-01-02.csv", "Mid Cap"),
        ("Small Cap_NSE_2026-01-02.csv", "Small Cap"),
    ]
    
    for filename, cap_type in cap_files:
        filepath = DATA_DIR / filename
        if filepath.exists():
            try:
                df = pd.read_csv(filepath)
                for _, row in df.iterrows():
                    symbol = str(row.get("Symbol", "")).strip()
                    sector = str(row.get("Sector", "")).strip()
                    if symbol and sector and sector != "nan":
                        clean_symbol = symbol.split(".")[0]
                        sector_map[clean_symbol] = {"sector": sector, "cap_type": cap_type}
            except Exception as e:
                print(f"Error loading {filename}: {e}")
    
    return sector_map


def find_symbol_cache_file(symbol: str, cache_dir: Path) -> Optional[str]:
    """Find the cached CSV file for a symbol."""
    pattern = str(cache_dir / f"dhan_*_{symbol}_1d.csv")
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


def load_ohlc_data(symbol: str, cache_dir: Path) -> Optional[pd.DataFrame]:
    """Load OHLC data for a symbol from cache."""
    cache_file = find_symbol_cache_file(symbol, cache_dir)
    if not cache_file or not os.path.exists(cache_file):
        return None
    
    try:
        df = pd.read_csv(cache_file)
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])
            df = df.set_index("time")
        elif "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        
        required_cols = ["open", "high", "low", "close"]
        if not all(col in df.columns for col in required_cols):
            return None
        
        df = df[~df.index.duplicated(keep='first')]
        return df.sort_index()
    except Exception as e:
        print(f"Error loading {symbol}: {e}")
        return None


def identify_trading_days_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Add month position information to dataframe."""
    df = df.copy()
    df["year"] = df.index.year
    df["month"] = df.index.month
    df["year_month"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    
    # Calculate trading day position within month
    df["trading_day_in_month"] = df.groupby("year_month").cumcount() + 1
    
    # Calculate trading days from end of month
    df["trading_days_from_end"] = df.groupby("year_month")["trading_day_in_month"].transform("max") - df["trading_day_in_month"] + 1
    
    return df


def calculate_strategy_returns(symbol: str, df: pd.DataFrame) -> List[Dict]:
    """
    Calculate returns for the strategy:
    - Entry: Open of 3rd last trading day of month N
    - Exit: Close of 3rd trading day of month N+1
    """
    df = identify_trading_days_by_month(df)
    
    trades = []
    
    # Get unique year-months
    year_months = sorted(df["year_month"].unique())
    
    for i, ym in enumerate(year_months[:-1]):  # Skip last month (no exit)
        next_ym = year_months[i + 1] if i + 1 < len(year_months) else None
        if not next_ym:
            continue
        
        # Find 3rd last trading day of current month (entry)
        month_data = df[df["year_month"] == ym]
        entry_days = month_data[month_data["trading_days_from_end"] == 3]
        
        if entry_days.empty:
            continue
        
        entry_date = entry_days.index[0]
        entry_price = entry_days.iloc[0]["open"]
        
        # Find 3rd trading day of next month (exit)
        next_month_data = df[df["year_month"] == next_ym]
        exit_days = next_month_data[next_month_data["trading_day_in_month"] == 3]
        
        if exit_days.empty:
            continue
        
        exit_date = exit_days.index[0]
        exit_price = exit_days.iloc[0]["close"]
        
        # Calculate returns
        gross_return_pct = ((exit_price - entry_price) / entry_price) * 100
        net_return_pct = gross_return_pct - TRANSACTION_COST_PCT
        
        trades.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_return_pct": gross_return_pct,
            "net_return_pct": net_return_pct,
            "holding_days": (exit_date - entry_date).days,
            "entry_month": ym,
            "exit_month": next_ym,
        })
    
    return trades


def analyze_basket(basket_name: str, basket_path: str, sector_map: Dict) -> pd.DataFrame:
    """Analyze all symbols in a basket."""
    print(f"\n📊 Analyzing {basket_name} basket...")
    
    symbols = load_basket(basket_path)
    symbols = list(dict.fromkeys(symbols))  # Remove duplicates
    print(f"   Loaded {len(symbols)} symbols")
    
    all_trades = []
    symbols_with_data = 0
    
    for symbol in symbols:
        df = load_ohlc_data(symbol, CACHE_DIR)
        if df is not None and len(df) > 30:
            trades = calculate_strategy_returns(symbol, df)
            if trades:
                # Add sector info
                sector_info = sector_map.get(symbol, {"sector": "Unknown", "cap_type": basket_name.capitalize()})
                for trade in trades:
                    trade["sector"] = sector_info.get("sector", "Unknown")
                    trade["cap_type"] = basket_name.capitalize()
                all_trades.extend(trades)
                symbols_with_data += 1
    
    print(f"   Found data for {symbols_with_data} symbols")
    print(f"   Generated {len(all_trades)} trades")
    
    return pd.DataFrame(all_trades)


def analyze_results(trades_df: pd.DataFrame, group_by: str, title: str):
    """Analyze and print results grouped by a column."""
    if trades_df.empty:
        print(f"\nNo trades to analyze for {title}")
        return pd.DataFrame()
    
    grouped = trades_df.groupby(group_by).agg({
        "gross_return_pct": ["mean", "sum", "std", "count"],
        "net_return_pct": ["mean", "sum"],
    })
    
    grouped.columns = ["_".join(col) for col in grouped.columns]
    grouped = grouped.reset_index()
    
    # Calculate win rate
    win_rates = trades_df.groupby(group_by).apply(
        lambda x: pd.Series({
            "win_rate": (x["net_return_pct"] > 0).mean() * 100,
            "avg_winner": x[x["net_return_pct"] > 0]["net_return_pct"].mean() if (x["net_return_pct"] > 0).any() else 0,
            "avg_loser": x[x["net_return_pct"] <= 0]["net_return_pct"].mean() if (x["net_return_pct"] <= 0).any() else 0,
        }),
        include_groups=False
    ).reset_index()
    
    grouped = grouped.merge(win_rates, on=group_by)
    grouped = grouped.sort_values("net_return_pct_sum", ascending=False)
    
    print(f"\n{'='*80}")
    print(f"{title}")
    print("="*80)
    print(f"{'Category':<25} {'Trades':>8} {'Gross%':>10} {'Net%':>10} {'Win%':>8} {'Avg Win':>10} {'Avg Loss':>10}")
    print("-"*80)
    
    for _, row in grouped.iterrows():
        print(f"{str(row[group_by])[:24]:<25} {int(row['gross_return_pct_count']):>8} "
              f"{row['gross_return_pct_sum']:>10.2f} {row['net_return_pct_sum']:>10.2f} "
              f"{row['win_rate']:>8.1f} {row['avg_winner']:>10.2f} {row['avg_loser']:>10.2f}")
    
    return grouped


def analyze_by_symbol(trades_df: pd.DataFrame, top_n: int = 20):
    """Analyze top and bottom performing symbols."""
    if trades_df.empty:
        return pd.DataFrame()
    
    by_symbol = trades_df.groupby("symbol").agg({
        "gross_return_pct": ["mean", "sum", "count"],
        "net_return_pct": ["mean", "sum"],
        "sector": "first",
        "cap_type": "first",
    })
    
    by_symbol.columns = ["_".join(col) for col in by_symbol.columns]
    by_symbol = by_symbol.reset_index()
    
    # Win rate
    win_rates = trades_df.groupby("symbol").apply(
        lambda x: (x["net_return_pct"] > 0).mean() * 100,
        include_groups=False
    ).reset_index()
    win_rates.columns = ["symbol", "win_rate"]
    
    by_symbol = by_symbol.merge(win_rates, on="symbol")
    
    print(f"\n{'='*80}")
    print(f"TOP {top_n} PERFORMING SYMBOLS (by total net return)")
    print("="*80)
    print(f"{'Symbol':<15} {'Sector':<20} {'Cap':<10} {'Trades':>7} {'Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    top_symbols = by_symbol.nlargest(top_n, "net_return_pct_sum")
    for _, row in top_symbols.iterrows():
        print(f"{row['symbol']:<15} {str(row['sector_first'])[:19]:<20} {str(row['cap_type_first']):<10} "
              f"{int(row['gross_return_pct_count']):>7} {row['net_return_pct_sum']:>10.2f} {row['win_rate']:>8.1f}")
    
    print(f"\n{'='*80}")
    print(f"BOTTOM {top_n} PERFORMING SYMBOLS (by total net return)")
    print("="*80)
    print(f"{'Symbol':<15} {'Sector':<20} {'Cap':<10} {'Trades':>7} {'Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    bottom_symbols = by_symbol.nsmallest(top_n, "net_return_pct_sum")
    for _, row in bottom_symbols.iterrows():
        print(f"{row['symbol']:<15} {str(row['sector_first'])[:19]:<20} {str(row['cap_type_first']):<10} "
              f"{int(row['gross_return_pct_count']):>7} {row['net_return_pct_sum']:>10.2f} {row['win_rate']:>8.1f}")
    
    return by_symbol


def analyze_by_month(trades_df: pd.DataFrame):
    """Analyze performance by entry month (which month you enter)."""
    if trades_df.empty:
        return pd.DataFrame()
    
    # Extract month from entry_month
    trades_df = trades_df.copy()
    trades_df["entry_month_num"] = trades_df["entry_month"].str[-2:].astype(int)
    
    month_names = {1: "January", 2: "February", 3: "March", 4: "April", 
                   5: "May", 6: "June", 7: "July", 8: "August",
                   9: "September", 10: "October", 11: "November", 12: "December"}
    
    trades_df["entry_month_name"] = trades_df["entry_month_num"].map(month_names)
    
    by_month = trades_df.groupby("entry_month_name").agg({
        "gross_return_pct": ["mean", "sum", "count"],
        "net_return_pct": ["mean", "sum"],
    })
    
    by_month.columns = ["_".join(col) for col in by_month.columns]
    by_month = by_month.reset_index()
    
    # Win rate
    win_rates = trades_df.groupby("entry_month_name").apply(
        lambda x: (x["net_return_pct"] > 0).mean() * 100,
        include_groups=False
    ).reset_index()
    win_rates.columns = ["entry_month_name", "win_rate"]
    
    by_month = by_month.merge(win_rates, on="entry_month_name")
    
    # Sort by calendar order
    month_order = list(month_names.values())
    by_month["sort_order"] = by_month["entry_month_name"].map({m: i for i, m in enumerate(month_order)})
    by_month = by_month.sort_values("sort_order")
    
    print(f"\n{'='*80}")
    print("PERFORMANCE BY ENTRY MONTH")
    print("(Which month you enter the trade)")
    print("="*80)
    print(f"{'Month':<15} {'Trades':>8} {'Gross%':>10} {'Net%':>10} {'Avg Net%':>10} {'Win%':>8}")
    print("-"*80)
    
    for _, row in by_month.iterrows():
        print(f"{row['entry_month_name']:<15} {int(row['gross_return_pct_count']):>8} "
              f"{row['gross_return_pct_sum']:>10.2f} {row['net_return_pct_sum']:>10.2f} "
              f"{row['net_return_pct_mean']:>10.2f} {row['win_rate']:>8.1f}")
    
    return by_month


def print_overall_summary(trades_df: pd.DataFrame):
    """Print overall strategy summary."""
    if trades_df.empty:
        print("\nNo trades to summarize")
        return
    
    total_trades = len(trades_df)
    total_gross = trades_df["gross_return_pct"].sum()
    total_net = trades_df["net_return_pct"].sum()
    avg_gross = trades_df["gross_return_pct"].mean()
    avg_net = trades_df["net_return_pct"].mean()
    win_rate = (trades_df["net_return_pct"] > 0).mean() * 100
    avg_holding = trades_df["holding_days"].mean()
    
    # Winners vs Losers
    winners = trades_df[trades_df["net_return_pct"] > 0]
    losers = trades_df[trades_df["net_return_pct"] <= 0]
    
    print("\n" + "="*80)
    print("OVERALL STRATEGY SUMMARY")
    print("="*80)
    print(f"\nStrategy: Buy at OPEN of 3rd last trading day of month")
    print(f"          Sell at CLOSE of 3rd trading day of next month")
    print(f"Transaction Cost: {TRANSACTION_COST_PCT}% (both legs)")
    print(f"\nDate Range: {trades_df['entry_date'].min().date()} to {trades_df['exit_date'].max().date()}")
    print(f"Total Trades: {total_trades}")
    print(f"Average Holding Period: {avg_holding:.1f} days")
    
    print(f"\n--- RETURNS ---")
    print(f"Total Gross Return: {total_gross:.2f}%")
    print(f"Total Net Return:   {total_net:.2f}%")
    print(f"Avg Gross per Trade: {avg_gross:.3f}%")
    print(f"Avg Net per Trade:   {avg_net:.3f}%")
    
    print(f"\n--- WIN/LOSS ANALYSIS ---")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Winners: {len(winners)} trades, avg gain: {winners['net_return_pct'].mean():.2f}%")
    print(f"Losers:  {len(losers)} trades, avg loss: {losers['net_return_pct'].mean():.2f}%")
    
    if len(losers) > 0 and len(winners) > 0:
        profit_factor = abs(winners["net_return_pct"].sum() / losers["net_return_pct"].sum())
        print(f"Profit Factor: {profit_factor:.2f}")


def main():
    print("="*80)
    print("MONTH-END TO MONTH-START TRADING STRATEGY ANALYSIS")
    print("="*80)
    print("\nStrategy Definition:")
    print("  Entry: Open of 3rd last trading day of month N")
    print("  Exit:  Close of 3rd trading day of month N+1")
    print(f"  Transaction Cost: {TRANSACTION_COST_PCT}% (combined for both legs)")
    print("="*80)
    
    # Load sector mapping
    print("\n📂 Loading sector mapping...")
    sector_map = load_sector_mapping()
    print(f"   Loaded sector data for {len(sector_map)} symbols")
    
    # Analyze all baskets
    all_trades = []
    
    for basket_name, basket_path in BASKETS.items():
        if os.path.exists(basket_path):
            trades_df = analyze_basket(basket_name, basket_path, sector_map)
            if not trades_df.empty:
                all_trades.append(trades_df)
    
    if not all_trades:
        print("\n❌ No trades generated. Exiting.")
        return
    
    # Combine all trades
    combined_trades = pd.concat(all_trades, ignore_index=True)
    print(f"\n📈 Total trades across all baskets: {len(combined_trades)}")
    
    # Overall summary
    print_overall_summary(combined_trades)
    
    # Analysis by cap type
    cap_analysis = analyze_results(combined_trades, "cap_type", "PERFORMANCE BY MARKET CAP")
    
    # Analysis by sector
    sector_analysis = analyze_results(combined_trades, "sector", "PERFORMANCE BY SECTOR")
    
    # Analysis by entry month
    month_analysis = analyze_by_month(combined_trades)
    
    # Top/Bottom symbols
    symbol_analysis = analyze_by_symbol(combined_trades, top_n=15)
    
    # Export results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_dir = f"reports/analysis/month_end_strategy_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"\n💾 Saving results to: {output_dir}")
    
    combined_trades.to_csv(f"{output_dir}/all_trades.csv", index=False)
    if not cap_analysis.empty:
        cap_analysis.to_csv(f"{output_dir}/by_cap_type.csv", index=False)
    if not sector_analysis.empty:
        sector_analysis.to_csv(f"{output_dir}/by_sector.csv", index=False)
    if not month_analysis.empty:
        month_analysis.to_csv(f"{output_dir}/by_month.csv", index=False)
    if not symbol_analysis.empty:
        symbol_analysis.to_csv(f"{output_dir}/by_symbol.csv", index=False)
    
    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
