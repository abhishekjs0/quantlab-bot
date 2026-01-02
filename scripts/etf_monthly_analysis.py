#!/usr/bin/env python3
"""
ETF Month-wise Returns Analysis
================================
Find which ETF performs best in which month.
"""

import pandas as pd
import numpy as np
from pathlib import Path

CACHE_DIR = Path("data/cache/dhan/daily")
OUTPUT_DIR = Path("reports/analysis/etf_analysis")

def main():
    print("=" * 80)
    print("ETF MONTH-WISE RETURNS ANALYSIS")
    print("=" * 80)
    
    # Load all clean ETF data
    all_monthly = []
    etf_count = 0
    skipped = []
    
    for f in sorted(CACHE_DIR.glob("dhan_*_1d.csv")):
        symbol = f.stem.split("_")[2]
        
        try:
            df = pd.read_csv(f, parse_dates=["time"], index_col="time")
            
            # Skip if too little data
            if len(df) < 60:
                skipped.append((symbol, "too few rows"))
                continue
            
            # Check for bad data - skip if extreme moves
            df["daily_return"] = df["close"].pct_change() * 100
            max_move = df["daily_return"].abs().max()
            if max_move > 30:
                skipped.append((symbol, f"extreme move {max_move:.1f}%"))
                continue
            
            # Check for duplicates
            if df.index.duplicated().sum() > 0:
                skipped.append((symbol, "duplicates"))
                continue
            
            df["month"] = df.index.month
            df["year"] = df.index.year
            
            # Calculate monthly returns (open to close of month)
            for (year, month), group in df.groupby(["year", "month"]):
                if len(group) < 10:  # Skip incomplete months
                    continue
                
                open_price = group["open"].iloc[0]
                close_price = group["close"].iloc[-1]
                monthly_ret = (close_price - open_price) / open_price * 100
                
                all_monthly.append({
                    "symbol": symbol,
                    "year": year,
                    "month": month,
                    "monthly_return": monthly_ret
                })
            
            etf_count += 1
            
        except Exception as e:
            skipped.append((symbol, str(e)))
            continue
    
    print(f"\n✅ Analyzed {etf_count} ETFs with clean data")
    print(f"📊 Total monthly observations: {len(all_monthly)}")
    
    if skipped:
        print(f"⚠️ Skipped {len(skipped)} files (bad data)")
    
    df_monthly = pd.DataFrame(all_monthly)
    
    # Month names
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    # Average return by ETF and month
    etf_month_avg = df_monthly.groupby(["symbol", "month"])["monthly_return"].agg(
        ["mean", "count", "std"]
    ).reset_index()
    etf_month_avg.columns = ["symbol", "month", "avg_return", "observations", "std"]
    
    # Filter for sufficient observations (at least 3 years)
    etf_month_avg = etf_month_avg[etf_month_avg["observations"] >= 3]
    
    # =========================================================================
    # BEST PERFORMING ETF-MONTH COMBINATIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print("TOP 30 ETF-MONTH COMBINATIONS (By Avg Return)")
    print("=" * 80)
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
    print("-" * 50)
    
    top_combos = etf_month_avg.nlargest(30, "avg_return")
    for _, row in top_combos.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")
    
    # =========================================================================
    # WORST PERFORMING ETF-MONTH COMBINATIONS
    # =========================================================================
    print("\n" + "=" * 80)
    print("BOTTOM 20 ETF-MONTH COMBINATIONS (By Avg Return)")
    print("=" * 80)
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg Ret%':>10} {'Obs':>5} {'Std':>8}")
    print("-" * 50)
    
    worst_combos = etf_month_avg.nsmallest(20, "avg_return")
    for _, row in worst_combos.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+10.2f}% {int(row['observations']):>5} {row['std']:>8.2f}")
    
    # =========================================================================
    # BEST MONTH FOR EACH ETF
    # =========================================================================
    print("\n" + "=" * 80)
    print("BEST MONTH FOR EACH ETF (Top 30)")
    print("=" * 80)
    
    best_months = etf_month_avg.loc[etf_month_avg.groupby("symbol")["avg_return"].idxmax()]
    best_months = best_months.sort_values("avg_return", ascending=False)
    
    print(f"\n{'Symbol':<15} {'Best Month':<10} {'Avg Ret%':>10} {'Obs':>5}")
    print("-" * 45)
    for _, row in best_months.head(30).iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<10} {row['avg_return']:>+10.2f}% {int(row['observations']):>5}")
    
    # =========================================================================
    # MONTH RANKING (OVERALL)
    # =========================================================================
    print("\n" + "=" * 80)
    print("MONTH RANKING (Average across all ETFs)")
    print("=" * 80)
    
    month_overall = df_monthly.groupby("month")["monthly_return"].agg(
        ["mean", "median", "std", "count"]
    ).reset_index()
    month_overall = month_overall.sort_values("mean", ascending=False)
    
    print(f"\n{'Month':<10} {'Mean%':>10} {'Median%':>10} {'Std':>8} {'Obs':>8}")
    print("-" * 50)
    for _, row in month_overall.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{m:<10} {row['mean']:>+10.2f} {row['median']:>+10.2f} {row['std']:>8.2f} {int(row['count']):>8}")
    
    # =========================================================================
    # EXCEPTIONAL COMBOS (Risk-Adjusted)
    # =========================================================================
    print("\n" + "=" * 80)
    print("EXCEPTIONAL ETF-MONTH COMBOS (Risk-Adjusted Score)")
    print("Score = Avg Return / Std * sqrt(Obs) -- Higher is better")
    print("=" * 80)
    
    # Calculate Sharpe-like score
    etf_month_avg["score"] = (etf_month_avg["avg_return"] / etf_month_avg["std"]) * np.sqrt(etf_month_avg["observations"])
    etf_month_avg = etf_month_avg.replace([np.inf, -np.inf], np.nan).dropna()
    
    exceptional = etf_month_avg[etf_month_avg["avg_return"] > 1].nlargest(25, "score")
    
    print(f"\n{'Symbol':<15} {'Month':<6} {'Avg%':>8} {'Std':>8} {'Obs':>5} {'Score':>8}")
    print("-" * 55)
    for _, row in exceptional.iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['avg_return']:>+8.2f} {row['std']:>8.2f} {int(row['observations']):>5} {row['score']:>8.2f}")
    
    # =========================================================================
    # WIN RATE BY ETF-MONTH
    # =========================================================================
    print("\n" + "=" * 80)
    print("HIGHEST WIN RATE ETF-MONTH COMBOS (Min 5 obs, Avg > 1%)")
    print("=" * 80)
    
    # Calculate win rate
    win_rate = df_monthly.groupby(["symbol", "month"]).apply(
        lambda x: pd.Series({
            "win_rate": (x["monthly_return"] > 0).mean() * 100,
            "avg_return": x["monthly_return"].mean(),
            "observations": len(x)
        }), include_groups=False
    ).reset_index()
    
    win_rate = win_rate[(win_rate["observations"] >= 5) & (win_rate["avg_return"] > 1)]
    win_rate = win_rate.sort_values("win_rate", ascending=False)
    
    print(f"\n{'Symbol':<15} {'Month':<6} {'WinRate%':>10} {'Avg%':>8} {'Obs':>5}")
    print("-" * 50)
    for _, row in win_rate.head(25).iterrows():
        m = month_names[int(row["month"]) - 1]
        print(f"{row['symbol']:<15} {m:<6} {row['win_rate']:>10.1f} {row['avg_return']:>+8.2f} {int(row['observations']):>5}")
    
    # Save results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    etf_month_avg.to_csv(OUTPUT_DIR / "etf_monthly_performance.csv", index=False)
    print(f"\n💾 Saved: {OUTPUT_DIR / 'etf_monthly_performance.csv'}")


if __name__ == "__main__":
    main()
