#!/usr/bin/env python3
"""
Extended TOTM (Turn of the Month) Strategy Analysis
====================================================
Strategy: Entry on 25th of month (open), Exit on 3rd of next month (close)
Universe: Large Cap stocks only
"""

import pandas as pd
import numpy as np
import glob
import os
from pathlib import Path

CACHE_DIR = Path("data/cache/dhan/daily")
BASKET_PATH = "data/baskets/basket_large.txt"
TRANSACTION_COST_PCT = 0.37


def load_basket(path):
    with open(path) as f:
        return list(dict.fromkeys([line.strip() for line in f if line.strip()]))


def find_cache_file(symbol):
    matches = glob.glob(str(CACHE_DIR / f"dhan_*_{symbol}_1d.csv"))
    return matches[0] if matches else None


def load_ohlc(symbol):
    cache_file = find_cache_file(symbol)
    if not cache_file:
        return None
    df = pd.read_csv(cache_file)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df = df[~df.index.duplicated(keep="first")]
    return df.sort_index()


def calculate_totm_trades(symbol, df):
    """Extended TOTM: Entry on 25th open, Exit on 3rd close of next month"""
    trades = []
    df = df.copy()
    df["day"] = df.index.day
    df["month"] = df.index.month
    df["year"] = df.index.year
    df["year_month"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)
    
    year_months = sorted(df["year_month"].unique())
    
    for i, ym in enumerate(year_months[:-1]):
        next_ym = year_months[i + 1]
        
        # Find entry: first trading day on or after 25th of current month
        month_data = df[df["year_month"] == ym]
        entry_candidates = month_data[month_data["day"] >= 25]
        
        if entry_candidates.empty:
            continue
        
        entry_date = entry_candidates.index[0]
        entry_price = entry_candidates.iloc[0]["open"]
        
        # Find exit: first trading day on or after 3rd of next month
        next_month_data = df[df["year_month"] == next_ym]
        exit_candidates = next_month_data[next_month_data["day"] >= 3]
        
        if exit_candidates.empty:
            continue
        
        exit_date = exit_candidates.index[0]
        exit_price = exit_candidates.iloc[0]["close"]
        
        gross_ret = ((exit_price - entry_price) / entry_price) * 100
        net_ret = gross_ret - TRANSACTION_COST_PCT
        
        trades.append({
            "symbol": symbol,
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "gross_return_pct": gross_ret,
            "net_return_pct": net_ret,
            "holding_days": (exit_date - entry_date).days,
            "entry_year": entry_date.year,
            "entry_month": ym,
        })
    
    return trades


def main():
    # Load symbols
    symbols = load_basket(BASKET_PATH)
    print(f"Loaded {len(symbols)} symbols from large cap basket")
    
    # Generate all trades
    all_trades = []
    for symbol in symbols:
        df = load_ohlc(symbol)
        if df is not None and len(df) > 30:
            trades = calculate_totm_trades(symbol, df)
            all_trades.extend(trades)
    
    trades_df = pd.DataFrame(all_trades)
    print(f"Generated {len(trades_df)} trades")
    print(f"Date Range: {trades_df['entry_date'].min().date()} to {trades_df['exit_date'].max().date()}")
    print(f"Avg Holding Period: {trades_df['holding_days'].mean():.1f} days")
    
    # Overall Summary
    print("\n" + "="*80)
    print("EXTENDED TOTM STRATEGY - LARGE CAP ONLY")
    print("Entry: Open on/after 25th | Exit: Close on/after 3rd of next month")
    print(f"Transaction Cost: {TRANSACTION_COST_PCT}%")
    print("="*80)
    
    total_trades = len(trades_df)
    winners = trades_df[trades_df["net_return_pct"] > 0]
    losers = trades_df[trades_df["net_return_pct"] <= 0]
    win_rate = len(winners) / total_trades * 100
    pf = abs(winners["net_return_pct"].sum() / losers["net_return_pct"].sum()) if len(losers) > 0 else float("inf")
    
    print(f"\n--- OVERALL ---")
    print(f"Total Trades: {total_trades}")
    print(f"Total Net Return: {trades_df['net_return_pct'].sum():.2f}%")
    print(f"Avg Net P&L per Trade: {trades_df['net_return_pct'].mean():.3f}%")
    print(f"Win Rate: {win_rate:.1f}%")
    print(f"Profit Factor: {pf:.2f}")
    print(f"Avg Winner: {winners['net_return_pct'].mean():.2f}%")
    print(f"Avg Loser: {losers['net_return_pct'].mean():.2f}%")
    
    # Year-wise breakdown
    print("\n" + "="*80)
    print("YEAR-WISE BREAKDOWN")
    print("="*80)
    print(f"{'Year':<8} {'Trades':>8} {'Net Ret%':>12} {'Avg Net%':>12} {'Win Rate':>10} {'PF':>8}")
    print("-"*60)
    
    for year in sorted(trades_df["entry_year"].unique()):
        year_trades = trades_df[trades_df["entry_year"] == year]
        yr_winners = year_trades[year_trades["net_return_pct"] > 0]
        yr_losers = year_trades[year_trades["net_return_pct"] <= 0]
        yr_wr = len(yr_winners) / len(year_trades) * 100
        yr_pf = abs(yr_winners["net_return_pct"].sum() / yr_losers["net_return_pct"].sum()) if len(yr_losers) > 0 and yr_losers["net_return_pct"].sum() != 0 else float("inf")
        
        print(f"{year:<8} {len(year_trades):>8} {year_trades['net_return_pct'].sum():>12.2f} {year_trades['net_return_pct'].mean():>12.3f} {yr_wr:>10.1f}% {yr_pf:>8.2f}")
    
    # Save trades
    os.makedirs("reports/analysis", exist_ok=True)
    trades_df.to_csv("reports/analysis/extended_totm_large_cap.csv", index=False)
    print(f"\n✅ Saved trades to reports/analysis/extended_totm_large_cap.csv")


if __name__ == "__main__":
    main()
