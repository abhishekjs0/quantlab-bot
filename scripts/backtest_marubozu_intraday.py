"""
Bullish Marubozu Intraday Backtest

Backtest version of strategies/groww/marubozu_intraday.py

Strategy Logic:
- Entry: If YESTERDAY formed a Bullish Marubozu (body >= 5% of price, >= 80% of range)
- Buy at today's open
- Exit at today's close (intraday/MIS style)

This simulates buying at market open after detecting a Marubozu pattern
and exiting at market close the same day.
"""

import os
import sys
import glob
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import DATA_DIR

# Strategy Parameters (matching marubozu_intraday.py)
MIN_BODY_PCT = 5.0  # Body must be >= 5% of open price
MIN_BODY_RANGE = 0.80  # Body must be >= 80% of total range


def load_symbol_data(symbol: str) -> pd.DataFrame | None:
    """Load daily OHLC data for a symbol."""
    cache_dir = os.path.join(DATA_DIR, 'cache', 'dhan', 'daily')
    pattern = os.path.join(cache_dir, f'dhan_*_{symbol}_1d.csv')
    matches = glob.glob(pattern)
    
    if not matches:
        return None
    
    df = pd.read_csv(matches[0])
    
    if 'start_time' in df.columns:
        df['Date'] = pd.to_datetime(df['start_time'])
    elif 'datetime' in df.columns:
        df['Date'] = pd.to_datetime(df['datetime'])
    elif 'date' in df.columns:
        df['Date'] = pd.to_datetime(df['date'])
    else:
        df['Date'] = pd.to_datetime(df.iloc[:, 0])
    
    df = df.set_index('Date').sort_index()
    df = df[~df.index.duplicated(keep='last')]
    
    col_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'open' in col_lower:
            col_map[col] = 'Open'
        elif 'high' in col_lower:
            col_map[col] = 'High'
        elif 'low' in col_lower:
            col_map[col] = 'Low'
        elif 'close' in col_lower:
            col_map[col] = 'Close'
        elif 'volume' in col_lower:
            col_map[col] = 'Volume'
    
    df = df.rename(columns=col_map)
    
    if 'Close' not in df.columns or 'Open' not in df.columns:
        return None
    
    return df


def detect_bullish_marubozu(df: pd.DataFrame) -> pd.Series:
    """
    Detect Bullish Marubozu pattern on each day.
    
    Criteria (matching marubozu_intraday.py):
    1. Bullish candle (Close > Open)
    2. Body >= MIN_BODY_PCT (5%) of Open price
    3. Body >= MIN_BODY_RANGE (80%) of total range
    
    Returns Series of booleans.
    """
    o = df['Open']
    h = df['High']
    low = df['Low']
    c = df['Close']
    
    # Body = Close - Open (positive for bullish)
    body = c - o
    
    # Total range
    total_range = h - low
    
    # Body as percentage of Open
    body_pct = (body / o) * 100
    
    # Body as ratio of total range
    body_ratio = body / total_range.replace(0, np.nan)
    
    # Bullish Marubozu conditions
    is_bullish = body > 0
    body_pct_ok = body_pct >= MIN_BODY_PCT
    body_range_ok = body_ratio >= MIN_BODY_RANGE
    
    return is_bullish & body_pct_ok & body_range_ok


def backtest_marubozu_intraday(symbols: list[str]) -> dict:
    """
    Backtest the Marubozu Intraday strategy.
    
    Logic:
    - If yesterday had a Bullish Marubozu, buy at today's Open
    - Sell at today's Close
    - Return = (Close - Open) / Open
    """
    
    print(f"Backtesting Marubozu Intraday on {len(symbols)} symbols...")
    print(f"Parameters: MIN_BODY_PCT={MIN_BODY_PCT}%, MIN_BODY_RANGE={MIN_BODY_RANGE*100}%")
    print("="*90)
    
    all_trades = []
    symbol_stats = []
    
    for sym in symbols:
        df = load_symbol_data(sym)
        if df is None or len(df) < 50:
            continue
        
        # Detect Marubozu pattern
        df['is_marubozu'] = detect_bullish_marubozu(df)
        
        # Yesterday's Marubozu triggers today's trade
        df['signal'] = df['is_marubozu'].shift(1)
        
        # Calculate intraday return: (Close - Open) / Open
        df['intraday_return'] = (df['Close'] - df['Open']) / df['Open'] * 100
        
        # Filter for trade days
        trades = df[df['signal'] == True].copy()
        trades['symbol'] = sym
        
        if len(trades) > 0:
            all_trades.append(trades[['symbol', 'Open', 'Close', 'intraday_return']])
            
            # Per-symbol stats
            symbol_stats.append({
                'symbol': sym,
                'num_trades': len(trades),
                'win_rate': (trades['intraday_return'] > 0).mean() * 100,
                'avg_return': trades['intraday_return'].mean(),
                'total_return': trades['intraday_return'].sum(),
                'max_win': trades['intraday_return'].max(),
                'max_loss': trades['intraday_return'].min(),
            })
    
    if not all_trades:
        print("No trades found!")
        return {}
    
    trades_df = pd.concat(all_trades, ignore_index=False)
    stats_df = pd.DataFrame(symbol_stats)
    
    # Overall statistics
    total_trades = len(trades_df)
    win_rate = (trades_df['intraday_return'] > 0).mean() * 100
    avg_return = trades_df['intraday_return'].mean()
    total_return = trades_df['intraday_return'].sum()
    
    print(f"\n{'='*90}")
    print("📊 MARUBOZU INTRADAY BACKTEST RESULTS")
    print("="*90)
    print(f"\nOverall Performance:")
    print(f"  Total Trades: {total_trades}")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Return per Trade: {avg_return:.3f}%")
    print(f"  Total Return (sum): {total_return:.2f}%")
    print(f"  Max Single Win: {trades_df['intraday_return'].max():.2f}%")
    print(f"  Max Single Loss: {trades_df['intraday_return'].min():.2f}%")
    print(f"  Profit Factor: {trades_df[trades_df['intraday_return']>0]['intraday_return'].sum() / abs(trades_df[trades_df['intraday_return']<0]['intraday_return'].sum()):.2f}")
    
    # Yearly breakdown
    trades_df_with_year = trades_df.copy()
    trades_df_with_year['year'] = trades_df_with_year.index.year
    yearly = trades_df_with_year.groupby('year').agg({
        'intraday_return': ['count', 'mean', 'sum', lambda x: (x > 0).mean() * 100]
    })
    yearly.columns = ['trades', 'avg_return', 'total_return', 'win_rate']
    
    print(f"\n{'Year':<8} {'Trades':>8} {'Win Rate':>10} {'Avg Ret':>10} {'Total Ret':>12}")
    print("-"*50)
    for year, row in yearly.iterrows():
        emoji = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"{emoji} {year:<6} {row['trades']:>8.0f} {row['win_rate']:>9.1f}% {row['avg_return']:>+9.3f}% {row['total_return']:>+11.2f}%")
    
    # Top performing symbols
    print(f"\n{'='*90}")
    print("🏆 TOP 10 PERFORMING SYMBOLS")
    print("="*90)
    top_symbols = stats_df.sort_values('avg_return', ascending=False).head(10)
    print(f"\n{'Symbol':<15} {'Trades':>8} {'Win Rate':>10} {'Avg Ret':>10} {'Total Ret':>12}")
    print("-"*60)
    for _, row in top_symbols.iterrows():
        emoji = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"{emoji} {row['symbol']:<13} {row['num_trades']:>8.0f} {row['win_rate']:>9.1f}% {row['avg_return']:>+9.3f}% {row['total_return']:>+11.2f}%")
    
    # Worst performing symbols
    print(f"\n{'='*90}")
    print("⚠️ BOTTOM 10 PERFORMING SYMBOLS")
    print("="*90)
    bottom_symbols = stats_df.sort_values('avg_return', ascending=True).head(10)
    print(f"\n{'Symbol':<15} {'Trades':>8} {'Win Rate':>10} {'Avg Ret':>10} {'Total Ret':>12}")
    print("-"*60)
    for _, row in bottom_symbols.iterrows():
        emoji = "🟢" if row['avg_return'] > 0 else "🔴"
        print(f"{emoji} {row['symbol']:<13} {row['num_trades']:>8.0f} {row['win_rate']:>9.1f}% {row['avg_return']:>+9.3f}% {row['total_return']:>+11.2f}%")
    
    # By day of week
    trades_df_with_dow = trades_df.copy()
    trades_df_with_dow['day_of_week'] = trades_df_with_dow.index.dayofweek
    dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    print(f"\n{'='*90}")
    print("📅 PERFORMANCE BY DAY OF WEEK")
    print("="*90)
    print(f"\n{'Day':<12} {'Trades':>8} {'Win Rate':>10} {'Avg Ret':>10}")
    print("-"*45)
    for day_num in range(5):
        day_trades = trades_df_with_dow[trades_df_with_dow['day_of_week'] == day_num]
        if len(day_trades) > 0:
            wr = (day_trades['intraday_return'] > 0).mean() * 100
            avg = day_trades['intraday_return'].mean()
            emoji = "🟢" if avg > 0 else "🔴"
            print(f"{emoji} {dow_names[day_num]:<10} {len(day_trades):>8} {wr:>9.1f}% {avg:>+9.3f}%")
    
    # Summary
    print(f"\n{'='*90}")
    print("💡 STRATEGY ASSESSMENT")
    print("="*90)
    
    if avg_return > 0.3:
        print("\n✅ STRONG: Average return per trade > 0.3%")
    elif avg_return > 0:
        print("\n⚠️ MARGINAL: Positive but low edge")
    else:
        print("\n❌ UNPROFITABLE: Negative expected return")
    
    if win_rate > 55:
        print(f"✅ HIGH WIN RATE: {win_rate:.1f}% > 55%")
    elif win_rate > 50:
        print(f"⚠️ MODERATE WIN RATE: {win_rate:.1f}%")
    else:
        print(f"❌ LOW WIN RATE: {win_rate:.1f}%")
    
    profitable_years = (yearly['avg_return'] > 0).sum()
    total_years = len(yearly)
    print(f"\n📆 Profitable Years: {profitable_years}/{total_years}")
    
    return {
        'trades_df': trades_df,
        'stats_df': stats_df,
        'yearly': yearly,
        'summary': {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_return': total_return
        }
    }


def main():
    # Load large basket
    basket_path = os.path.join(DATA_DIR, 'baskets', 'basket_large.txt')
    with open(basket_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]
    
    print(f"Loaded {len(symbols)} symbols from basket_large.txt")
    
    results = backtest_marubozu_intraday(symbols)


if __name__ == "__main__":
    main()
